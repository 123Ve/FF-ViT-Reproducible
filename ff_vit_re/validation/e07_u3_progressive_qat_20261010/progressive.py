"""Approved original-method progressive fake-quant QAT, NOT RTL/FPGA validation."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'validation/e07_u3_qat_20261010'),str(ROOT/'quantization_final/scripts'),str(ROOT)]
import train as helpers
from runtime import u,exact
from stage4d_mlp_activation_qat import MLPActivationController,fake_quant_ste
from stage4j_attention_activation_qat import AttentionActivationController,set_attention_trainable,distill_loss
from qat_weight3_hls196 import HLS196DeiT,convert_backbone_to_qat

def active_blocks(epoch):
    if epoch<1:raise ValueError('one-based training epoch required')
    return list(range(6,12)) if epoch==1 else list(range(3,12)) if epoch==2 else list(range(12))

def own_state(controller):
    return {k:v.detach().cpu().clone() for k,v in controller.state_dict().items() if not k.startswith('backbone.')}

def load_controller(controller,state):
    expected=set(own_state(controller))
    if set(state)!=expected:raise ValueError('controller state membership differs')
    result=controller.load_state_dict(state,strict=False)
    if result.unexpected_keys or any(not k.startswith('backbone.') for k in result.missing_keys):
        raise ValueError('controller state incomplete')

class U3AttentionController(AttentionActivationController):
    """Original controller plus explicit U3 probabilities and physical MAC domains.

    Boundary QAT uses saturation/STE. The final integer model uses the actual
    finite-width wraps and LUT address arithmetic; these are distinct results.
    """
    def __init__(self,backbone,ranges,ln_input_scales,softmax_scales):
        super().__init__(backbone,ranges,ln_input_scales)
        self.log_softmax_scale=nn.Parameter(torch.as_tensor(softmax_scales,dtype=torch.float32).log())
        self.softmax_calls=[0]*12
    def softmax_scale(self,b):return self.log_softmax_scale[b].exp()
    def install(self):
        super().install()
        # Replace the original fixed int15 domain with A_scale*W_O_scale.
        # E07 has no independent O post-MAC requantizer.
        for b in range(12):self.handles[b*5+4].remove()
        self.handles=[h for i,h in enumerate(self.handles) if i%5!=4]
        for b,block in enumerate(self.backbone.vit.blocks):
            block.attn.fused_attn=False
            def raw_qkv(module,inputs,output,b=b):
                if not self.is_active(b):return output
                parts=output.chunk(3,dim=-1)
                scales=module.log_scale.exp().reshape(-1)
                return torch.cat([fake_quant_ste(v,self.ln1_scale(b)*scales[i],
                    -(1<<(bits-1)),(1<<(bits-1))-1)
                    for i,(v,bits) in enumerate(zip(parts,(12,11,11)))],dim=-1)
            def probability(module,inputs,output,b=b):
                if not self.is_active(b):return output
                self.softmax_calls[b]+=1
                return fake_quant_ste(output,self.softmax_scale(b),0,7)
            def raw_a(module,inputs,b=b):
                if not self.is_active(b):return None
                return (fake_quant_ste(inputs[0],self.softmax_scale(b)*self.v_scale(b),-1024,1023),)
            def residual(module,inputs,b=b):
                if not self.is_active(b):return None
                return (fake_quant_ste(inputs[0],self.o_acc_scale(b),-16384,16383),)
            self.handles.append(block.attn.qkv.register_forward_hook(raw_qkv,prepend=True))
            self.handles.append(block.attn.attn_drop.register_forward_hook(probability))
            self.handles.append(block.attn.proj.register_forward_pre_hook(raw_a,prepend=True))
            self.handles.append(block.norm2.register_forward_pre_hook(residual))

def sources(spec):
    if spec['name']=='plantvillage':
        source=spec['base']/'checkpoints/plantvillage_hls196/best.pth'
        parent=spec['base']/'checkpoints/qat_weight3_hls196/best_qat_state.pth'
        patch_report=spec['reports']/'stage3_patch_hls/report.json'
    else:
        source=spec['run']/'hls196/best.pth';parent=spec['run']/'qat_weight3_hls196/best_qat_state.pth'
        patch_report=spec['run']/'stage3_patch_hls/report.json'
    ranges=spec['run']/'stage4a_ranges/activation_ranges.json'
    ln_input=spec['run']/'stage4h_exact_layernorm_roundfix/ln_input_scales.npy'
    return dict(source=source,parent=parent,patch_report=patch_report,ranges=ranges,ln_input=ln_input)

def read_ranges(path):
    # Original Stage4A saves a metadata wrapper, not a bare boundary mapping.
    return json.loads(Path(path).read_text())['statistics']

def epoch_loader(dataset,batch,workers,seed,epoch):
    generator=torch.Generator().manual_seed(seed+epoch)
    return torch.utils.data.DataLoader(dataset,batch_size=batch,shuffle=True,num_workers=workers,
        pin_memory=True,persistent_workers=False,generator=generator)

def split_identities(datasets):
    result={}
    for split in ('val','test'):
        rows=[dict(path=str(path),label=int(label),sha256=u.digest(path)) for path,label in datasets[split].samples]
        result[split]=dict(count=len(rows),ordered_membership_sha256=hashlib.sha256(
            json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    return result

def dependency_hashes(spec):
    paths=list(sources(spec).values())+[spec['rom'],spec['weights'],spec['calibration'],Path(__file__)]
    initial=ROOT/'validation/e07_u3_qat_20261010/outputs'/spec['name']/'initial_u3/u3_artifact'
    paths += [initial/'manifest.json',initial/'arrays.npz']
    paths += [Path(sys.modules[c.__module__].__file__) for c in
        (MLPActivationController,AttentionActivationController,HLS196DeiT)]
    paths += [Path(module.__file__) for module in (helpers,u,exact,sys.modules['runtime'])]
    paths += [helpers.E07/n for n in ('block0.cpp','layernorm.h','fused_flash_attn.h','quant.h','mlp.h','matmul.h')]
    return {str(p):u.digest(p) for p in paths}

class ProgressiveModel(nn.Module):
    def __init__(self,spec,stage):
        super().__init__();src=sources(spec)
        self.backbone=HLS196DeiT(spec['classes']);convert_backbone_to_qat(self.backbone)
        parent=torch.load(src['parent'],weights_only=True,map_location='cpu')
        self.backbone.load_state_dict(parent['model_state'],strict=True)
        self.patch=u.load_native_artifact(spec)['patch']
        self.patch_scale=float(json.loads(src['patch_report'].read_text())['patch_weight']['scale'])*4
        ranges=read_ranges(src['ranges'])
        self.mlp=MLPActivationController(self.backbone,ranges);self.mlp.install()
        self.attention=None;self.stage=stage
        if stage=='attention':
            initial,_=helpers.load_portable(ROOT/'validation/e07_u3_qat_20261010/outputs'/spec['name']/'initial_u3/u3_artifact')
            scales=[p['softmax']['output_scale'] for p in initial['blocks']]
            self.attention=U3AttentionController(self.backbone,ranges,np.load(src['ln_input']),scales)
            self.attention.install()
        self.activate([])
    def activate(self,blocks):
        if self.stage=='mlp':self.mlp.set_active(blocks)
        else:self.mlp.set_active(range(12));self.attention.set_active(blocks)
    def forward(self,images):
        x=exact.patch_forward(images,self.patch).float()*self.patch_scale
        if tuple(x.shape[1:])!=(196,192):raise ValueError('not HLS196 tokens')
        x=self.backbone.vit.blocks(x)
        return self.backbone.vit.head(self.backbone.vit.norm(x)[:,0])
    def snapshot(self):
        return dict(backbone={k:v.detach().cpu().clone() for k,v in self.backbone.state_dict().items()},
            mlp=own_state(self.mlp),attention=own_state(self.attention) if self.attention else None)
    def restore(self,state):
        self.backbone.load_state_dict(state['backbone'],strict=True);load_controller(self.mlp,state['mlp'])
        if self.attention is not None:load_controller(self.attention,state['attention'])

def optimizer_for(model,args):
    if model.stage=='attention':
        weights=set_attention_trainable(model.backbone)
        for n,p in model.mlp.named_parameters():
            if not n.startswith('backbone.'):p.requires_grad_(False)
        controller=model.attention
    else:
        weights=list(model.backbone.parameters());controller=model.mlp
        for p in weights:p.requires_grad_(True)
    scales=[p for n,p in controller.named_parameters() if not n.startswith('backbone.')]
    if {id(p) for p in weights}&{id(p) for p in scales}:raise ValueError('duplicate optimizer parameter')
    return torch.optim.AdamW([dict(params=weights,lr=args.lr,weight_decay=.02),
        dict(params=scales,lr=args.scale_lr,weight_decay=0)])

def rng_state():
    return dict(python=random.getstate(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state_all())
def restore_rng(state):
    random.setstate(state['python']);torch.set_rng_state(state['torch']);torch.cuda.set_rng_state_all(state['cuda'])

def recipe(args,spec,stage):
    return dict(dataset=args.dataset,stage=stage,seed=args.seed,epochs=args.epochs,batch=args.batch,lr=args.lr,
        scale_lr=args.scale_lr,optimizer='AdamW',model_weight_decay=.02,scale_weight_decay=0,
        alpha=.5,T=2,gradient_clip=1,scheduler='CosineAnnealingLR',precision='FP32, AMP disabled',
        progressive_active_blocks=[active_blocks(e) for e in range(1,args.epochs+1)],
        validation='all12 enabled, full validation only, test never used for selection',
        numeric_mode='FAKE_QUANT_SURROGATE_NOT_BIT_ACCURATE',
        softmax='U3 learned per-block scale, non-fused attention' if stage=='attention' else 'float (MLP-only stage)',
        differences_from_original=['U3 Softmax in Attention','Q12/K11/V11 and A11 raw-MAC boundaries',
            'int15 residual at physical A*W_O domain','frozen calibration256 excluded','FP32 instead of AMP'],
        sources=dependency_hashes(spec))

def run_stage(args,stage,ds,record,training,train_identity):
    out=HERE/'outputs'/args.dataset/stage;out.mkdir(parents=True,exist_ok=True)
    model=ProgressiveModel(u.dataset_spec(args.dataset),stage).to(args.device)
    parent=None
    if stage=='attention':
        parent=HERE/'outputs'/args.dataset/'mlp/best.pth'
        saved=torch.load(parent,weights_only=True,map_location='cpu')
        model.backbone.load_state_dict(saved['state']['backbone'],strict=True)
        load_controller(model.mlp,saved['state']['mlp'])
    teacher=ProgressiveModel(u.dataset_spec(args.dataset),'mlp').to(args.device)
    if parent:
        teacher.backbone.load_state_dict(saved['state']['backbone'],strict=True)
        load_controller(teacher.mlp,saved['state']['mlp']);teacher.activate(range(12))
    teacher.requires_grad_(False);teacher.eval()
    optimizer=optimizer_for(model,args);scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,args.epochs)
    spec=u.dataset_spec(args.dataset);r=recipe(args,spec,stage)
    r.update(dataset_identity=record,training_identity=train_identity,
        source_code_sha256=u.digest(Path(__file__)),parent_mlp_sha256=u.digest(parent) if parent else None)
    last=out/'last.pth';best_path=out/'best.pth'
    if last.exists():
        if not args.resume:raise ValueError('existing run requires --resume')
        if json.loads((out/'recipe.json').read_text())!=r:raise ValueError('immutable resume recipe changed')
        saved_last=torch.load(last,weights_only=True,map_location='cpu')
        saved_best=torch.load(best_path,weights_only=True,map_location='cpu')
        if saved_last['recipe']!=r or saved_best['recipe']!=r:raise ValueError('checkpoint recipe mismatch')
        model.restore(saved_last['state']);optimizer.load_state_dict(saved_last['optimizer']);scheduler.load_state_dict(saved_last['scheduler'])
        best=max(saved_last['best'],saved_best['best']);start=saved_last['epoch']+1;steps=saved_last['steps']
        restore_rng(saved_last['rng'])
    else:
        if best_path.exists():raise ValueError('partial existing run, refuses overwrite')
        u.save_json(out/'recipe.json',r)
        model.activate(range(12));metric=helpers.validate(model,ds['val'],torch.device(args.device),args.batch)
        best=metric['top1_percent'];start=1;steps=0
        state=dict(state=model.snapshot(),epoch=0,steps=0,best=best,validation=metric,recipe=r,
            optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),rng=rng_state())
        helpers.atomic_save(best_path,state);helpers.atomic_save(last,state)
        helpers.event(out,event='initial_all12_fakequant_validation',**metric)
    for epoch in range(start,args.epochs+1):
        loader=epoch_loader(training,args.batch,args.workers,args.seed,epoch)
        blocks=active_blocks(epoch);model.activate(blocks);model.train();total=correct=0;loss_sum=0.;started=time.monotonic()
        helpers.event(out,event='epoch_begin',stage=stage,epoch=epoch,active_quantizers=blocks)
        for images,labels in loader:
            images=images.to(args.device);labels=labels.to(args.device);optimizer.zero_grad(set_to_none=True)
            with torch.no_grad():target=teacher(images)
            logits=model(images);loss,_,_=distill_loss(logits,target,labels,.5,2.)
            if not torch.isfinite(loss):raise ValueError('nonfinite training loss')
            loss.backward();norm=torch.nn.utils.clip_grad_norm_([p for g in optimizer.param_groups for p in g['params']],1.,error_if_nonfinite=True)
            optimizer.step();steps+=1;total+=len(labels);correct+=int((logits.argmax(-1)==labels).sum());loss_sum+=float(loss.detach())*len(labels)
            if steps%100==0:helpers.event(out,event='training_progress',epoch=epoch,steps=steps,images=total,
                loss=loss_sum/total,top1_percent=100*correct/total,gradient_norm=float(norm))
        scheduler.step();model.activate(range(12));metric=helpers.validate(model,ds['val'],torch.device(args.device),args.batch)
        improved=helpers.select_best('val',metric['top1_percent'],best);best=max(best,metric['top1_percent'])
        state=dict(state=model.snapshot(),epoch=epoch,steps=steps,best=best,validation=metric,recipe=r,
            optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),rng=rng_state())
        if improved:helpers.atomic_save(best_path,state)
        helpers.atomic_save(last,state)
        helpers.event(out,event='epoch_complete',epoch=epoch,steps=steps,best=best,selected=improved,
            active_train_quantizers=blocks,validation_quantizers=list(range(12)),validation=metric,
            train_loss=loss_sum/total,train_top1_percent=100*correct/total,elapsed_seconds=time.monotonic()-started)
    selected=torch.load(best_path,weights_only=True,map_location='cpu');model.restore(selected['state']);model.activate(range(12))
    test=helpers.validate(model,ds['test'],torch.device(args.device),args.batch)
    if split_identities(ds)!=record['full_split_identity']:raise ValueError('evaluation split content changed during training')
    for path,sha in r['sources'].items():
        if u.digest(path)!=sha:raise ValueError('pinned source changed during training: '+path)
    u.save_json(out/'fakequant_accuracy.json',dict(validation=selected['validation'],test=test,
        best_epoch=selected['epoch'],best_sha256=u.digest(best_path),numeric_mode='FAKE_QUANT_SOFTWARE_NOT_FPGA'))
    helpers.event(out,event='stage_complete',stage=stage,best_epoch=selected['epoch'],test=test)

def smoke(args,ds):
    results=[]
    for stage in ('mlp','attention'):
        model=ProgressiveModel(u.dataset_spec(args.dataset),stage).to(args.device)
        opt=optimizer_for(model,args);model.activate(active_blocks(1));model.train()
        images=torch.stack([ds['calibration'][i][0] for i in range(2)]).to(args.device)
        labels=torch.tensor([ds['calibration'][i][1] for i in range(2)],device=args.device)
        loss=F.cross_entropy(model(images),labels);loss.backward()
        gradients=[p.grad for g in opt.param_groups for p in g['params'] if p.grad is not None]
        if not gradients or not all(bool(torch.isfinite(g).all()) for g in gradients):raise ValueError('invalid smoke gradient')
        if stage=='attention' and model.attention.softmax_calls!=[0]*6+[1]*6:raise ValueError('U3 Softmax bypassed')
        torch.nn.utils.clip_grad_norm_([p for g in opt.param_groups for p in g['params']],1.,error_if_nonfinite=True);opt.step()
        results.append(dict(stage=stage,loss=float(loss.detach()),finite_gradients=True,
            softmax_calls=model.attention.softmax_calls if model.attention else None))
        del model,opt;torch.cuda.empty_cache()
    out=HERE/'outputs'/args.dataset;out.mkdir(parents=True,exist_ok=True)
    u.save_json(out/'smoke.json',dict(results=results,code_sha256=u.digest(Path(__file__)),training_complete=False))
    print(json.dumps(results),flush=True)

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--dataset',choices=['plantvillage','nwpu'],required=True)
    ap.add_argument('--stage',choices=['mlp','attention','both'],default='both');ap.add_argument('--epochs',type=int,default=10)
    ap.add_argument('--batch',type=int,default=32);ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--lr',type=float,default=1e-5);ap.add_argument('--scale-lr',type=float,default=5e-4)
    ap.add_argument('--seed',type=int,default=20260923);ap.add_argument('--device',default='cuda')
    ap.add_argument('--resume',action='store_true');ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    helpers.configure(args.seed)
    spec=u.dataset_spec(args.dataset);ds,record=u.prepare_datasets(spec)
    if args.smoke:smoke(args,ds);return
    record['full_split_identity']=split_identities(ds)
    training,identity=helpers.train_dataset(spec,record)
    out=HERE/'outputs'/args.dataset;out.mkdir(parents=True,exist_ok=True)
    u.save_json(out/'dataset_identity.json',dict(evaluation=record,training=identity))
    for stage in ('mlp','attention') if args.stage=='both' else (args.stage,):
        run_stage(args,stage,ds,record,training,identity)

if __name__=='__main__':main()
