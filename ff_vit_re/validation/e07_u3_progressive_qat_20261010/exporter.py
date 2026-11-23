"""Fresh calibration export and E07-width integer software evaluation only."""
from __future__ import annotations
import argparse
import copy
import json
import math
from pathlib import Path
import sys
import numpy as np
import torch
from torch.nn import functional as F
from progressive import HERE,ROOT,ProgressiveModel,sources,helpers,u,exact,split_identities
from runtime import head_layernorm,integer_forward
import finalize as previous_final
import run_experiment as local_audit
import summarize as local_summary
from image1k_hls_s3_original.src import exact_head_fit as hf

def validate_split_binding(expected,actual):
    if expected!=actual:raise ValueError('full validation/test identity differs from selected checkpoint')

def aggregate_rsqrt(rows,ln_rows):
    """Rsqrt has one scalar per LN token, not one per channel output."""
    counts={r['instance']:int(r['count']) for r in ln_rows}
    if len(counts)!=len(ln_rows) or {r['instance'] for r in rows}!=set(counts):
        raise ValueError('Rsqrt/LN instance membership differs')
    weighted=[]
    for r in rows:
        count,remainder=divmod(counts[r['instance']],192)
        if remainder or count!=int(r['input_images'])*196:
            raise ValueError('Rsqrt token count differs from LN output count')
        weighted.append((r,count))
    n=sum(count for _,count in weighted)
    if not n:raise ValueError('empty Rsqrt observations')
    return dict(count=n,real_mae=sum(count*float(r['real_mae']) for r,count in weighted)/n,
        real_rmse=math.sqrt(sum(count*float(r['real_rmse'])**2 for r,count in weighted)/n),
        real_max_ae=max(float(r['real_max_ae']) for r,_ in weighted),
        unit='inverse_input_integer_code',exact_rate='NOT_APPLICABLE')

def fitter_hashes():
    # Resolve the files actually imported by the fitter rather than assuming a copy.
    fitted=exact.fitters()
    paths=[Path(sys.modules[fitted['_fit_rescale'].__module__].__file__),Path(fitted['lut'].__file__),
        Path(hf.__file__),Path(exact.__file__),Path(previous_final.__file__),Path(local_audit.__file__),
        Path(local_summary.__file__),ROOT/'validation/ln_iotj_20261008/ln_numeric.py',
        ROOT/'validation/lut_float_accuracy_20261010/lut_accuracy.py']
    return {str(p):u.digest(p) for p in paths}

def unsigned_statistics(x):
    x=exact.wrap(x.long(),13).cpu()
    raw_sum=x.sum(-1);acc=exact.wrap(raw_sum,15,False)
    product=exact.wrap(acc*683,30,False)
    rounded=exact.wrap(product+65536,30,False)
    mean=exact.wrap(rounded>>17,7,False)
    difference=exact.wrap(x-mean[:,None],13)
    variance=(difference*difference).sum(-1)
    return dict(diff13=difference,var24=exact.wrap(variance,24,False),mean7=mean,
        summary=dict(sum_wrap_rate=float((raw_sum!=acc).double().mean()),
            variance_wrap_rate=float((variance!=exact.wrap(variance,24,False)).double().mean()),
            mean_min=int(mean.min()),mean_max=int(mean.max()),sum_min=int(raw_sum.min()),sum_max=int(raw_sum.max())))

def fit_unsigned_head(x,target,input_scale):
    """Reuse established rsqrt/affine fitters but NEVER signed Head statistics."""
    s=unsigned_statistics(x);target=target.detach().cpu().double()
    rs=hf.fit_head_rsqrt(s['var24'],input_scale,1e-6,cursor_bits=6)
    address=exact.wrap((s['var24']+int(rs['b']))>>int(rs['s1']),6,False).clamp(0,63)
    rint=rs['full_table'][address]
    base=max(float(torch.quantile(target.abs().reshape(-1),.999))/127,1e-6)
    best=None
    for factor in (.8,1.,1.2,1.5):
        scale=base*factor;target_q=(target/scale).round().clamp(-128,127).long()
        af=hf.fit_head_affine(s['diff13'],rint,target_q)
        p=dict(scalars=np.array([683,17,int(rs['b']),int(rs['s1']),63,int(af['s2']),8,0],np.int32),
            lnw=af['lnw'].numpy().astype(np.int32),lnb=af['lnb'].numpy().astype(np.int64),
            rsqrt_table=rs['full_table'].numpy().astype(np.int32),output_scale=scale)
        prediction=head_layernorm(x.cpu(),p)
        mse=float(((prediction.double()*scale-target)**2).mean())
        p['stats']=dict(**s['summary'],real_mse=mse,output_scale=scale,affine_wrap_rate=0.,
            affine_mismatch_rate=af['mismatch_rate'],shifted_S9_wrap_rate=af['rel9_wrap_rate'],
            rsqrt_cursor_wrap_rate=rs['cursor_wrap_rate'],rsqrt_rel_p999=rs['rel_p999'],
            actual_unsigned_Head=True)
        key=(af['rel9_wrap_rate'],mse)
        if best is None or key<best[0]:best=(key,p)
    return best[1]

def fit_classifier(qln,float_ln,weight,bias,ln_scale):
    # E07 exposes 1000 logits even when only38/45 classes are used. Inactive
    # rows have zero weights and -262143 bias, NOT modulo-minimum underflow.
    qln=qln.cpu().long();target=F.linear(float_ln.cpu().double(),weight.cpu().double(),bias.cpu().double())
    w=weight.detach().cpu().double();b=bias.detach().cpu().double();classes=len(b)
    base=max(float(w.abs().max())/127,1e-9);best=None
    for factor in np.linspace(.55,1.5,24):
        sw=base*float(factor);domain=ln_scale*sw
        qw=(w/sw).round().clamp(-128,127).long();qb=(b/domain).round().long()
        if bool(((qb < -262144)|(qb>262143)).any()):continue
        pre=qln@qw.T+qb;wrapped=exact.wrap(pre,19)
        real=wrapped.double()*domain
        mse=float(((real-real.mean(-1,keepdim=True))-(target-target.mean(-1,keepdim=True))).square().mean())
        rate=float((pre!=wrapped).double().mean());key=(rate,mse)
        if best is None or key<best[0]:
            ww=torch.zeros((1000,192),dtype=torch.int8);bb=torch.full((1000,),-262143,dtype=torch.int32)
            ww[:classes]=qw.to(torch.int8);bb[:classes]=qb.to(torch.int32)
            best=(key,dict(qw=ww,qb=bb,weight_scale=sw,logit_scale=domain,accumulator_wrap_rate=rate,
                logit_mse_centered=mse,top1_agreement=float((real.argmax(-1)==target.argmax(-1)).double().mean()),
                class_count=classes,inactive_bias=-262143))
    if best is None:raise ValueError('no valid E07 W8/S19 classifier')
    return best[1]

def exported_weights(model):
    out={}
    for b,block in enumerate(model.backbone.vit.blocks):
        for name,module in (('attn.qkv',block.attn.qkv),('attn.proj',block.attn.proj),
                            ('mlp.fc1',block.mlp.fc1),('mlp.fc2',block.mlp.fc2)):
            code,scale=module.export_integer()
            out[f'vit.blocks.{b}.{name}']=dict(code=code,scales=scale)
    return out

def scale_lists(model):
    m=model.mlp;a=model.attention
    if a is None:raise ValueError('final export requires U3 Attention checkpoint')
    return {name:[float(fn(b).detach().cpu()) for b in range(12)] for name,fn in
        [('ln1',a.ln1_scale),('ln2',m.ln2_scale),('q',a.q_scale),('k',a.k_scale),('v',a.v_scale),
         ('a',a.a_scale),('softmax',a.softmax_scale),('gelu',m.gelu_scale),('fc1',m.m1_scale),('fc2',m.m2_scale)]}

@torch.inference_mode()
def smoke_build(args):
    spec=u.dataset_spec(args.dataset);ds,_=u.prepare_datasets(spec)
    model=ProgressiveModel(spec,'attention').eval();scales=scale_lists(model)
    images=torch.stack([ds['calibration'][i][0] for i in range(2)]).to(args.device)
    x=exact.patch_forward(images,model.patch).cpu()
    p,report=exact.fit_block(0,x,model.patch_scale,model.backbone.state_dict(),exported_weights(model),scales,fit_tokens=392)
    y,_=exact.block_forward(x.to(args.device),p)
    cls=y.cpu()[:,0];target=model.backbone.vit.norm(cls.float()*report['output_scale']).double()
    head=fit_unsigned_head(cls,target,report['output_scale'])
    q=head_layernorm(cls,head);classifier=fit_classifier(q,target,model.backbone.vit.head.weight,model.backbone.vit.head.bias,head['output_scale'])
    out=HERE/'outputs'/args.dataset;out.mkdir(parents=True,exist_ok=True)
    row=dict(scope='ONE_BLOCK_AND_HEAD_INTEGRATION_SMOKE_NOT_ACCURACY',block_output_shape=list(y.shape),
        softmax_bits=int(p['softmax']['scalars'][13]),fit_images=report['fit_images'],
        head_cursor_bound=int(head['scalars'][4]),head_rsqrt_max=int(np.max(head['rsqrt_table'])),
        classifier_shape=list(classifier['qw'].shape),software='PASS',HLS='NOT_MEASURED',FPGA='NOT_MEASURED',
        exporter_sha256=u.digest(Path(__file__)))
    u.save_json(out/'export_smoke.json',row);print(json.dumps(row),flush=True)

@torch.inference_mode()
def build(name,out,device,batch,fit_tokens):
    spec=u.dataset_spec(name);ds,record=u.prepare_datasets(spec)
    checkpoint=out/'attention/best.pth';saved=torch.load(checkpoint,weights_only=True,map_location='cpu')
    record['full_split_identity']=split_identities(ds)
    validate_split_binding(saved['recipe']['dataset_identity'],record)
    for path,sha in saved['recipe']['sources'].items():
        if u.digest(path)!=sha:raise ValueError('training source identity changed: '+path)
    model=ProgressiveModel(spec,'attention');model.restore(saved['state']);model.eval()
    scales=scale_lists(model);weights=exported_weights(model);state=model.backbone.state_dict()
    frozen=u.load_native_artifact(spec);source=sources(spec)
    binding=dict(checkpoint_sha256=u.digest(checkpoint),calibration=record['calibration_samples'],
        exporter_sha256=u.digest(Path(__file__)),fit_tokens=fit_tokens,patch_rom_sha256=u.digest(spec['rom']),
        full_split_identity=split_identities(ds),training_sources=saved['recipe']['sources'],
        source_sha256={**fitter_hashes(),str(source['patch_report']):u.digest(source['patch_report'])})
    cache=out/'export_cache';cache.mkdir(exist_ok=True)
    if (cache/'binding.json').exists():
        if json.loads((cache/'binding.json').read_text())!=binding:raise ValueError('export cache identity changed')
    else:u.save_json(cache/'binding.json',binding)
    loader=torch.utils.data.DataLoader(ds['calibration'],batch_size=batch,shuffle=False,num_workers=4)
    codes=torch.cat([exact.patch_forward(images.to(device),frozen['patch']).cpu() for images,_ in loader])
    if len(codes)!=record['selected_calibration_count']:raise ValueError('calibration count differs')
    scale=model.patch_scale;blocks=[];reports=[];refs=[]
    for b in range(12):
        stage=cache/f'block{b:02d}'
        if stage.exists():
            artifact,metadata=exact.load_artifact(stage)
            if metadata['binding']!=binding:raise ValueError('cached block binding differs')
            p,report,codes=artifact['params'],artifact['report'],torch.as_tensor(artifact['output']).long()
        else:
            p,report=exact.fit_block(b,codes,scale,state,weights,scales,fit_tokens=fit_tokens)
            codes=torch.cat([exact.block_forward(x.to(device),p)[0].cpu() for x in codes.split(batch)])
            exact.save_artifact(stage,dict(params=p,report=report,output=codes.to(torch.int16)),dict(binding=binding))
        p['_internal_padding']=frozen['blocks'][b]['_internal_padding'];p['_tail_padding']=frozen['blocks'][b]['_tail_padding']
        if int(p['softmax']['scalars'][13])!=3:raise ValueError('fitted Softmax is not U3')
        norms=[dict(gamma=state[f'vit.blocks.{b}.norm{j+1}.weight'].numpy(),
            beta=state[f'vit.blocks.{b}.norm{j+1}.bias'].numpy(),
            input_scale=scale if j==0 else report['physical_o_scale'],output_scale=scales[f'ln{j+1}'][b],
            eps=1e-6,input_bits=13 if j==0 else 15) for j in range(2)]
        refs.append(dict(ln=norms,score_scale=scales['q'][b]*scales['k'][b]/8,v_scale=scales['v'][b],
            a_scale=scales['a'][b],gelu_input_scale=report['physical_m1_scale'],gelu_output_scale=scales['gelu'][b]))
        blocks.append(p);reports.append(report);scale=report['output_scale']
        helpers.event(out,event='fresh_integer_block_fitted',block=b,fit_images=report['fit_images'],
            physical_output_scale=scale,m1_wrap=report['m1_wrap_rate'])
    cls=codes[:,0].long();target=model.backbone.vit.norm(cls.float()*scale).double()
    ln=fit_unsigned_head(cls,target,scale);qln=head_layernorm(cls,ln)
    classifier=fit_classifier(qln,target,model.backbone.vit.head.weight,model.backbone.vit.head.bias,ln['output_scale'])
    head=dict(head_ln_scalars=ln['scalars'],head_lnw=ln['lnw'],head_lnb=ln['lnb'],head_rsqrt=ln['rsqrt_table'],
        head_weight=classifier['qw'].numpy(),head_bias=classifier['qb'].numpy())
    result=dict(patch=copy.deepcopy(frozen['patch']),blocks=blocks,head=head,final_encoder_scale=scale)
    raw=previous_final.verify_export(result)
    final=out/'final';final.mkdir(exist_ok=True)
    previous_final.persist_artifact(final/'artifact',helpers.portable(result),binding['checkpoint_sha256'])
    (final/'weights_e07_u3.bin').write_bytes(raw);np.savez(final/'head_parameters.npz',**head)
    u.save_json(final/'calibration.json',dict(binding=binding,blocks=reports,head=ln['stats'],
        classifier={k:v for k,v in classifier.items() if k not in ('qw','qb')},labels_used=False))
    return result,refs,ds,record,binding

def run(args):
    out=HERE/'outputs'/args.dataset;device=torch.device(args.device)
    result,refs,ds,record,binding=build(args.dataset,out,device,args.batch,args.fit_tokens)
    final=out/'final';reloaded,_=helpers.load_portable(final/'artifact')
    images=torch.stack([ds['calibration'][i][0] for i in range(2)]).to(device)
    with torch.inference_mode():
        first,_=integer_forward(images,result);second,_=integer_forward(images,reloaded)
    if not torch.equal(first,second):raise ValueError('integer disk export/reload differs')
    metrics={}
    for split in ('val','test'):
        metrics[split]=previous_final.evaluate(reloaded,ds[split],device,args.batch,final/(split+'_predictions.csv'))
        u.save_json(final/'accuracy.json',metrics);helpers.event(out,event='final_integer_accuracy',split=split,**metrics[split])
    local_audit.natural_audit(args.dataset,reloaded,refs,ds['test'],record,final,device)
    rows=local_summary.read_csv(final/'unit_accuracy.csv');global_rows=[]
    counts=dict(Softmax=177020928,Softmax_EXP=177020928,Softmax_Reciprocal=903168,LayerNorm=115605504,GELU=231211008)
    for operator,count in counts.items():
        r=local_summary.aggregate([row for row in rows if row['operator']==operator])
        if r['count']!=count:raise ValueError('local measurement count differs')
        global_rows.append(dict(dataset=args.dataset,operator=operator,scope='SAME128_NATURAL',**r))
    rs=local_summary.read_csv(final/'rsqrt_accuracy.csv')
    rs_result=aggregate_rsqrt(rs,[r for r in rows if r['operator']=='LayerNorm'])
    if rs_result['count']!=602112:raise ValueError('rsqrt count differs')
    global_rows.append(dict(dataset=args.dataset,operator='LayerNorm_Rsqrt',scope='SAME128_NATURAL',**rs_result))
    rows=local_summary.read_csv(final/'gelu_exhaustive.csv')
    if sum(int(r['count']) for r in rows)!=24576:raise ValueError('GELU exhaustive count differs')
    global_rows.append(dict(dataset=args.dataset,operator='GELU',scope='EXHAUSTIVE_S11_2048',**local_summary.aggregate(rows)))
    validate_split_binding(binding['full_split_identity'],split_identities(ds))
    for row in record['calibration_samples']:
        if u.digest(row['path'])!=row['sha256']:raise ValueError('calibration image changed during experiment')
    for path,sha in {**binding['source_sha256'],**binding['training_sources']}.items():
        if u.digest(path)!=sha:raise ValueError('bound source changed during evaluation: '+path)
    if u.digest(out/'attention/best.pth')!=binding['checkpoint_sha256']:raise ValueError('selected checkpoint changed during export')
    u.write_csv(final/'nonlinear_error.csv',global_rows)
    u.write_csv(final/'accuracy.csv',[dict(dataset=args.dataset,split=split,**m) for split,m in metrics.items()])
    u.save_json(final/'summary.json',dict(status='COMPLETE_SOFTWARE_EXPERIMENT',binding=binding,accuracy=metrics,
        nonlinear_error=global_rows,numeric_mode='E07 integer/LUT software original unsigned Head',
        disk_export_logits_compared=2000,disk_export_mismatches=0,HLS_C_sim='NOT_MEASURED',RTL='NOT_MEASURED',FPGA='NOT_MEASURED',
        weights_bin_is='Block parameter data, NOT BOOT.bin; updated Head ROM required for future deployment'))

if __name__=='__main__':
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--dataset',choices=['plantvillage','nwpu'],required=True)
    ap.add_argument('--device',default='cuda');ap.add_argument('--batch',type=int,default=16)
    ap.add_argument('--fit-tokens',type=int,default=6272);ap.add_argument('--smoke',action='store_true')
    args=ap.parse_args();helpers.configure(20260923)
    if args.smoke:smoke_build(args)
    else:run(args)
