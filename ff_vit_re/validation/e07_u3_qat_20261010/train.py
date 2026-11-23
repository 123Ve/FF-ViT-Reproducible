"""Checkpointed strict E07 QAT. All outputs stay in this validation directory."""
from __future__ import annotations
import argparse
import copy
import csv
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
from torchvision import datasets,transforms
from runtime import HERE,ROOT,StrictQAT,exact,integer_forward,u

E07=Path('/home/user/Desktop/FF_Vit/E04_weight_schedule/E07_timing_300mhz/src')

def select_best(split,score,best):
    if split!='val':raise ValueError('checkpoint selection requires validation, never test')
    if not math.isfinite(score):raise ValueError('nonfinite validation result')
    return score>best

def check_recipe(out,recipe,*,resume):
    path=out/'recipe.json'
    if not resume and any((out/name).exists() for name in ('last.pth','best.pth')):
        raise ValueError('existing checkpoint: no fresh overwrite; recover or use a new isolated run')
    if resume:
        if not path.exists() or json.loads(path.read_text())!=recipe:
            raise ValueError('immutable resume recipe changed or missing')

def reconcile_best(last,best,recipe):
    if last['recipe']!=recipe or best['recipe']!=recipe:
        raise ValueError('checkpoint recipe differs from immutable run recipe')
    scores=(last['best'],best['best'])
    if not all(math.isfinite(s) for s in scores):raise ValueError('nonfinite saved best')
    return max(scores)

def pin_initial(out,path,*,require_existing):
    identity={str(p.relative_to(path)):u.digest(p) for p in sorted(path.rglob('*')) if p.is_file()}
    if not identity:raise ValueError('initial artifact missing')
    target=out/'initial_identity.json'
    if target.exists():
        if json.loads(target.read_text())!=identity:raise ValueError('frozen initial artifact changed')
    elif require_existing:raise ValueError('initial artifact identity missing')
    else:u.save_json(target,identity)
    return identity

def make_recipe(args,spec):
    return dict(dataset=args.dataset,seed=args.seed,effective_batch=args.batch,micro_batch=args.micro_batch,
        epochs=args.epochs,AdamW_model_lr=args.lr,AdamW_table_threshold_lr=args.scale_lr,
        model_weight_decay=.01,scale_weight_decay=0,gradient_clip=1.,loss='CE + 0.5*T^2 KL',T=2.,
        forward='all12 strict E07 blocks each epoch; progressive parameter unfreezing',
        unfreeze=[[6,11],[3,11],[0,11]],selection='full validation, original test NEVER used for tuning',
        learned='six W3 matrices/biases, LN affine gamma/beta, bounded Q/K/V/A/GELU LUT gains, reciprocal U8 gain, W8 Head',
        frozen='Patch, address/shift scalars, residual RM/RS, rsqrt and EXP tables; no additional hardware operation',
        interpretation='learned gains affect exported table codes/weight thresholds; physical reference code scales remain frozen',
        parent_checkpoint=str(spec['checkpoint']),parent_sha256=u.digest(spec['checkpoint']))

def event(out,**data):
    data=dict(time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**data)
    line=json.dumps(data,allow_nan=False)
    print(line,flush=True)
    with (out/'events.jsonl').open('a') as f:f.write(line+'\n')

def atomic_save(path,state):
    temporary=path.with_suffix('.tmp')
    torch.save(state,temporary);os.replace(temporary,path)

def configure(seed):
    torch.set_num_threads(4);torch.set_num_interop_threads(4)
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.use_deterministic_algorithms(True)

def reference(spec):
    result=u.reference_parameters(spec)
    sm=json.loads((spec['reports']/'stage4l_exact_softmax_aq/report.json').read_text())['blocks']
    for b,p in enumerate(result):
        p.update(q_scale=sm[str(b)]['q_scale'],k_scale=sm[str(b)]['k_scale'])
    head=json.loads((spec['reports']/'stage4o2_head_safe/report.json').read_text())
    scales=dict(weight=head['selected_weight_scale'],ln=head['selected_logit_scale']/head['selected_weight_scale'])
    return result,scales

def train_dataset(spec,record):
    transform=transforms.Compose([transforms.RandomResizedCrop(224,scale=(.8,1.)),
        transforms.RandomHorizontalFlip(),transforms.ToTensor(),
        transforms.Normalize((.485,.456,.406),(.229,.224,.225))])
    if spec['name']=='plantvillage':
        ds=datasets.ImageFolder(spec['base']/'datasets/PlantVillage/splits/train',transform=transform)
        hashes=[u.digest(p) for p,_ in ds.samples]
        held=set()
        for split in ('val','test'):
            other=datasets.ImageFolder(spec['base']/'datasets/PlantVillage/splits'/split)
            held.update(u.digest(p) for p,_ in other.samples)
    else:
        from archive.nwpu_resisc45_ffvit.src.manifest_dataset import load_manifest_bundle,ManifestImageDataset
        bundle=load_manifest_bundle(spec['base']/'metadata')
        ds=ManifestImageDataset(ROOT/'archive/Dataset',bundle.records_for('train'),transform)
        ds.classes=list(bundle.classes)
        ds.samples=[(str(ds.source_root/r.relative_path),r.label) for r in ds.records]
        hashes=[r.sha256 for r in ds.records]
        held={r.sha256 for split in ('val','test') for r in bundle.records_for(split)}
    if ds.classes!=record['classes']:raise ValueError('train class order differs')
    calibration={r['sha256'] for r in record['calibration_samples']}
    # The selected fitting holdout is excluded from optimizer updates.
    selected=[i for i,h in enumerate(hashes) if h not in held|calibration]
    kept={hashes[i] for i in selected}
    if kept & held:raise ValueError('train content overlaps held-out val/test')
    if not selected:raise ValueError('no isolated training samples')
    details=dict(source_count=len(ds),train_count=len(selected),excluded=len(ds)-len(selected),
        selected_calibration_overlap=0,val_test_content_overlap=0,transform=repr(transform),
        membership_sha256=hashlib.sha256('\n'.join(f'{i}:{hashes[i]}:{ds.samples[i][1]}' for i in selected).encode()).hexdigest())
    return torch.utils.data.Subset(ds,selected),details

class FrozenTeacher(nn.Module):
    """Original W3 checkpoint, FP32 activation teacher, fixed exported Patch.

    Only a distillation teacher; never reported as strict E07 accuracy.
    """
    def __init__(self,state,classes,artifact,patch_scale):
        super().__init__()
        from qat_weight3_hls196 import HLS196DeiT,convert_backbone_to_qat
        self.backbone=HLS196DeiT(classes);convert_backbone_to_qat(self.backbone)
        keys=self.backbone.state_dict()
        bound={k:state[next(n for n in state if n.endswith(k))] for k in keys}
        self.backbone.load_state_dict(bound,strict=True)
        self.artifact=artifact;self.patch_scale=patch_scale
        self.requires_grad_(False);self.eval()
    def forward(self,images):
        x=exact.patch_forward(images,self.artifact['patch']).float()*self.patch_scale
        x=self.backbone.vit.blocks(x)
        x=self.backbone.vit.norm(x)
        return self.backbone.vit.head(x[:,0])

def validate(model,ds,device,batch_size):
    loader=torch.utils.data.DataLoader(ds,batch_size=batch_size,shuffle=False,num_workers=4,pin_memory=True)
    correct=count=0;model.eval()
    with torch.inference_mode():
        for images,labels in loader:
            logits=model(images.to(device));pred=logits.argmax(-1).cpu()
            correct+=int((pred==labels).sum());count+=len(labels)
    if count!=len(ds):raise ValueError('validation incomplete')
    return dict(sample_count=count,correct=correct,top1_percent=100*correct/count)

def portable(a):
    a=copy.deepcopy(a)
    for p in a['blocks']:
        for key in ('_internal_padding','_tail_padding'):
            if isinstance(p[key],bytes):p[key]=np.frombuffer(p[key],np.uint8).copy()
    return a

def load_portable(path):
    a,meta=exact.load_artifact(path)
    for p in a['blocks']:
        for key in ('_internal_padding','_tail_padding'):p[key]=p[key].tobytes()
    return a,meta

def freeze_contract(spec,out):
    files=[spec['checkpoint'],spec['weights'],spec['rom'],Path(__file__),HERE/'runtime.py',
        HERE/'finalize.py',ROOT/'image1k_hls_s3_original/src/exact.py',Path(u.__file__),
        ROOT/'validation/softmax_u3_hls_20261010/run_experiment.py',
        ROOT/'validation/softmax_u3_hls_20261010/summarize.py',
        ROOT/'validation/lut_float_accuracy_20261010/lut_accuracy.py',
        ROOT/'validation/ln_iotj_20261008/ln_numeric.py',spec['calibration']]
    files += [spec['reports']/stage/'report.json' for stage in ('stage4f_exact_gelu','stage4l_exact_softmax_aq','stage4o2_head_safe')]
    files.append(ROOT/'validation/ln_iotj_20261008/outputs/final128'/spec['name']/'summary.json')
    files += [E07/n for n in ('block0.cpp','fused_flash_attn.h','layernorm.h','quant.h','mlp.h','matmul.h')]
    return dict(sources={str(p):u.digest(p) for p in files},E07=str(E07),
        head=dict(sum='U15',mean_product='U30',mean='U7',variance='U24',cursor='U6',rsqrt='U11',affine='S36',shift='S9',output='S8',weight='S8',MAC='S19'),
        encoder=dict(weight='S3',LN_Q_K_V_AQ='S3',softmax='U3',GELU='U3',Q_MAC='S12',K_V_M1_A_MAC='S11',O_M2_FM='S13',attention_residual='S15',LN_variance='S36',LN_affine='S40'),
        signed_head_fix=False,post_MAC_requant_added=False,
        states=dict(software='PENDING',HLS_full_C_sim='NOT_MEASURED',RTL_cosim='NOT_MEASURED',FPGA='NOT_MEASURED'))

def parity(model,images,out,label):
    with torch.no_grad():
        direct=model(images).long();a=model.export();other,_=integer_forward(images,a,trace=False)
    mismatches=int((direct!=other).sum())
    event(out,event='forward_export_parity',stage=label,integers=direct.numel(),mismatches=mismatches)
    if mismatches:raise ValueError('QAT/export integer-forward mismatch')

def run(args):
    out=HERE/'outputs'/args.dataset;out.mkdir(parents=True,exist_ok=True)
    if (out/'last.pth').exists() and not args.resume:raise ValueError('existing run: use --resume, no overwriting')
    spec=u.dataset_spec(args.dataset);device=torch.device(args.device)
    recipe=make_recipe(args,spec)
    check_recipe(out,recipe,resume=args.resume)
    contract=freeze_contract(spec,out)
    if (out/'contract.json').exists():
        previous=json.loads((out/'contract.json').read_text())
        if previous['sources']!=contract['sources']:
            if (out/'last.pth').exists() or (out/'best.pth').exists():raise ValueError('source hash changed: cannot silently resume')
            # Preserve pre-training smoke provenance; formal run pins final code.
            u.save_json(out/('smoke_contract_'+u.digest(out/'contract.json')[:12]+'.json'),previous)
            u.save_json(out/'contract.json',contract)
    else:u.save_json(out/'contract.json',contract)
    ds,record=u.prepare_datasets(spec)
    train,train_info=train_dataset(spec,record)
    u.save_json(out/'dataset_identity.json',dict(**record,training=train_info))
    event(out,event='data_ready',**train_info)
    refs,hs=reference(spec)
    artifact=u.load_native_artifact(spec)
    init=out/'initial_u3'
    if (init/'u3_artifact/manifest.json').exists():artifact,_=load_portable(init/'u3_artifact')
    else:
        init.mkdir(exist_ok=True)
        artifact=u.calibrate_u3(artifact,ds,refs,init,device,args.micro_batch)
    initial_identity=pin_initial(out,init/'u3_artifact',require_existing=args.resume)
    state=torch.load(spec['checkpoint'],weights_only=True,map_location='cpu')['student_state']
    model=StrictQAT(artifact,state,refs,spec['classes'],hs).to(device)
    optimizer=torch.optim.AdamW(model.optimizer_groups(args.lr,args.scale_lr))
    best=-1.;first_epoch=0;history=[];steps=0
    if args.resume:
        saved=torch.load(out/'last.pth',map_location='cpu',weights_only=True)
        selected=torch.load(out/'best.pth',map_location='cpu',weights_only=True)
        if saved['initial_identity']!=initial_identity or selected['initial_identity']!=initial_identity:
            raise ValueError('checkpoint initial execution identity differs')
        restored_best=reconcile_best(saved,selected,recipe)
        model.load_state_dict(saved['model']);optimizer.load_state_dict(saved['optimizer'])
        first_epoch=saved['epoch']+1;best=restored_best;history=saved['history'];steps=saved['steps']
        torch.set_rng_state(saved['rng_cpu']);torch.cuda.set_rng_state_all(saved['rng_cuda'])
        random.setstate(saved['rng_python'])
    else:u.save_json(out/'recipe.json',recipe)
    smoke_images=torch.stack([ds['calibration'][i][0] for i in range(2)]).to(device)
    parity(model,smoke_images,out,'before_training')
    if args.smoke:
        begun=time.monotonic();model.train();optimizer.zero_grad(set_to_none=True)
        images,labels=next(iter(torch.utils.data.DataLoader(train,batch_size=args.micro_batch,shuffle=False,num_workers=0)))
        images=images.to(device);labels=labels.to(device)
        output=model(images);loss=F.cross_entropy(output[:,:spec['classes']]*model.logit_scale,labels)
        loss.backward();grad=model.blocks[-1].linears['m2'].master.grad
        if grad is None or not torch.isfinite(grad).all() or not float(grad.abs().sum()):raise ValueError('missing/nonfinite/zero W3 gradient')
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True);optimizer.step()
        parity(model,smoke_images,out,'after_real_smoke_update')
        event(out,event='smoke_complete',loss=float(loss.detach()),gradient_norm=float(norm),images=len(labels),
            seconds=time.monotonic()-begun,CUDA_memory_peak=torch.cuda.max_memory_allocated())
        return
    teacher=FrozenTeacher(state,spec['classes'],artifact,refs[0]['ln'][0]['input_scale']).to(device)
    if first_epoch==0 and not args.resume:
        initial=validate(model,ds['val'],device,args.micro_batch)
        event(out,event='initial_validation',**initial)
        best=initial['top1_percent']
        atomic_save(out/'best.pth',dict(model=model.state_dict(),epoch=-1,best=best,recipe=recipe,initial_identity=initial_identity))
        atomic_save(out/'last.pth',dict(model=model.state_dict(),optimizer=optimizer.state_dict(),epoch=-1,
            best=best,history=history,steps=steps,rng_cpu=torch.get_rng_state(),rng_cuda=torch.cuda.get_rng_state_all(),
            rng_python=random.getstate(),recipe=recipe,initial_identity=initial_identity))
    for epoch in range(first_epoch,args.epochs):
        # Epoch-local shuffle and worker seeds reproduce augmentation on resume.
        generator=torch.Generator().manual_seed(args.seed+epoch)
        loader=torch.utils.data.DataLoader(train,batch_size=args.micro_batch,shuffle=True,num_workers=4,
            pin_memory=True,persistent_workers=False,generator=generator)
        active=model.set_progressive(epoch);model.train();optimizer.zero_grad(set_to_none=True)
        factor=.01+.99*(1+math.cos(math.pi*epoch/max(1,args.epochs-1)))/2
        for group,base in zip(optimizer.param_groups,(args.lr,args.scale_lr)):group['lr']=base*factor
        total=correct=0;loss_sum=0.;pending=0;began=time.monotonic()
        for batch_index,(images,labels) in enumerate(loader):
            images=images.to(device,non_blocking=True);labels=labels.to(device,non_blocking=True)
            logits=model(images)[:,:spec['classes']]*model.logit_scale
            with torch.no_grad():target=teacher(images)
            ce=F.cross_entropy(logits,labels)
            kd=F.kl_div(F.log_softmax(logits/2,-1),F.softmax(target/2,-1),reduction='batchmean')*4
            loss=ce+.5*kd
            if not torch.isfinite(loss):raise ValueError('nonfinite training loss; best not replaced')
            n=len(labels);(loss*n/args.batch).backward();pending+=n
            loss_sum+=float(loss.detach())*n;total+=n;correct+=int((logits.argmax(-1)==labels).sum())
            if pending>=args.batch or batch_index==len(loader)-1:
                if pending!=args.batch:
                    for parameter in model.parameters():
                        if parameter.grad is not None:parameter.grad.mul_(args.batch/pending)
                norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
                optimizer.step();optimizer.zero_grad(set_to_none=True);pending=0;steps+=1
                with torch.no_grad():
                    for name,parameter in model.named_parameters():
                        if 'threshold_gain' in name:parameter.clamp_(-math.log(2),math.log(2))
            if batch_index%32==0 or batch_index==len(loader)-1:
                event(out,event='training_progress',epoch=epoch,completed=total,total=len(train),optimizer_steps=steps,
                    train_top1=100*correct/total,loss=loss_sum/total,elapsed_seconds=time.monotonic()-began)
        parity(model,smoke_images,out,f'epoch{epoch}')
        from finalize import verify_export
        verify_export(model.export())
        result=validate(model,ds['val'],device,args.micro_batch)
        row=dict(epoch=epoch,active_blocks=active,train_samples=total,train_top1=100*correct/total,
            loss=loss_sum/total,optimizer_steps=steps,validation=result,seconds=time.monotonic()-began)
        history.append(row);event(out,event='epoch_complete',**row)
        if select_best('val',result['top1_percent'],best):
            best=result['top1_percent']
            atomic_save(out/'best.pth',dict(model=model.state_dict(),epoch=epoch,best=best,recipe=recipe,initial_identity=initial_identity))
        atomic_save(out/'last.pth',dict(model=model.state_dict(),optimizer=optimizer.state_dict(),epoch=epoch,
            best=best,history=history,steps=steps,rng_cpu=torch.get_rng_state(),rng_cuda=torch.cuda.get_rng_state_all(),rng_python=random.getstate(),recipe=recipe,initial_identity=initial_identity))
        u.save_json(out/'training.json',dict(status='RUNNING' if epoch+1<args.epochs else 'TRAINING_COMPLETE',best_val=best,history=history))
    event(out,event='training_complete',best_validation=best,optimizer_steps=steps)
    from finalize import finalize
    finalize(args.dataset,out,device,args.micro_batch)

def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--dataset',required=True,choices=['plantvillage','nwpu'])
    p.add_argument('--device',default='cuda');p.add_argument('--batch',type=int,default=64)
    p.add_argument('--micro-batch',type=int,default=8);p.add_argument('--epochs',type=int,default=12)
    p.add_argument('--lr',type=float,default=1e-5);p.add_argument('--scale-lr',type=float,default=1e-4)
    p.add_argument('--seed',type=int,default=20261010);p.add_argument('--resume',action='store_true');p.add_argument('--smoke',action='store_true')
    args=p.parse_args()
    if args.epochs<1 or args.epochs>12 or args.batch!=64 or args.batch%args.micro_batch:
        p.error('approved contract: epochs1..12, effective batch64 divisible by microbatch')
    configure(args.seed);run(args)

if __name__=='__main__':main()
