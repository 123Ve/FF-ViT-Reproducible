"""Finalize selected checkpoint: full integer accuracy and same128 local audit."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import zipfile
import numpy as np
import torch
from runtime import HERE,StrictQAT,u,integer_forward,exact
from train import reference,load_portable,portable,event,pin_initial
import run_experiment as prior
import summarize as prior_summary

def weighted_mae(observations):
    count=sum(n for n,_ in observations)
    if count<=0:raise ValueError('empty observations')
    return sum(n*value for n,value in observations)/count

def payload_identity(a):
    h=hashlib.sha256()
    def visit(value):
        if torch.is_tensor(value):value=value.detach().cpu().numpy()
        if isinstance(value,np.ndarray):
            h.update(json.dumps(['array',str(value.dtype),list(value.shape)]).encode());h.update(value.tobytes())
        elif isinstance(value,dict):
            h.update(b'dict')
            for key in sorted(value):h.update(json.dumps(key).encode());visit(value[key])
        elif isinstance(value,(list,tuple)):
            h.update(json.dumps(['sequence',len(value)]).encode())
            for item in value:visit(item)
        else:h.update(json.dumps(value.item() if isinstance(value,np.generic) else value,sort_keys=True).encode())
    visit(a);return h.hexdigest()

def persist_artifact(path,a,checkpoint_sha256):
    if not path.exists():
        exact.save_artifact(path,a,dict(checkpoint_sha256=checkpoint_sha256,
            original_E07_unsigned_head=True,software='EXPORTED_NOT_YET_EVALUATED',
            HLS_C_sim='NOT_MEASURED',RTL='NOT_MEASURED',FPGA='NOT_MEASURED'))
    reloaded,meta=exact.load_artifact(path)
    if meta['checkpoint_sha256']!=checkpoint_sha256 or payload_identity(reloaded)!=payload_identity(a):
        raise ValueError('existing final artifact differs: use a new isolated result directory')

def evaluate(a,ds,device,batch,path):
    correct=correct5=total=0
    loader=torch.utils.data.DataLoader(ds,batch_size=batch,num_workers=4,shuffle=False,pin_memory=True)
    with path.open('w',newline='') as f,torch.inference_mode():
        writer=csv.writer(f);writer.writerow(['index','path','label','prediction','correct','top5_correct'])
        for images,labels in loader:
            logits,_=integer_forward(images.to(device),a)
            top=logits.topk(5,-1).indices.cpu()
            for y,yp in zip(labels.tolist(),top.tolist()):
                ok=int(y==yp[0]);ok5=int(y in yp)
                writer.writerow([total,ds.samples[total][0],y,yp[0],ok,ok5])
                total+=1;correct+=ok;correct5+=ok5
    if total!=len(ds):raise ValueError('incomplete final evaluation')
    return dict(sample_count=total,correct=correct,correct5=correct5,top1_percent=100*correct/total,
        top5_percent=100*correct5/total,complete_split=True,predictions_sha256=u.digest(path),
        numeric_mode='strict E07 integer/LUT software with original unsigned Head; NOT FPGA')

def verify_export(a):
    for b,p in enumerate(a['blocks']):
        if int(p['softmax']['scalars'][13])!=3:raise ValueError('non-U3 probability')
        for name in ('q','k','v','o','m1','m2'):
            if np.min(p[name+'_w']) < -4 or np.max(p[name+'_w'])>3:raise ValueError('non-W3 matrix')
        for name in ('q','k','v','a','gelu'):
            t=p[name+'_lut']['table'];lo=0 if name=='gelu' else -4;hi=7 if name=='gelu' else 3
            if np.min(t)<lo or np.max(t)>hi:raise ValueError('LUT boundary width mismatch')
    raw=u.encode_blocks(a['blocks'])
    if len(raw)!=2772096:raise ValueError('ABI size mismatch')
    decoded=u.decode_blocks(raw)
    if u.encode_blocks(decoded)!=raw:raise ValueError('ABI not stable on reload')
    for p,d in zip(a['blocks'],decoded):
        for name in ('q','k','v','o','m1','m2'):
            if not np.array_equal(p[name+'_w'],d[name+'_w']) or not np.array_equal(p[name+'_b'],d[name+'_b']):
                raise ValueError('matrix/bias ABI narrowing changes codes')
        for name in ('ln1','ln2'):
            for field in ('scalars','lnw','lnb','rsqrt_table'):
                if not np.array_equal(p[name][field],d[name][field]):raise ValueError('LN ABI narrowing changes codes')
        for name in ('q','k','v','a','gelu'):
            for field in ('scalars','table'):
                if not np.array_equal(p[name+'_lut'][field],d[name+'_lut'][field]):raise ValueError('LUT ABI narrowing changes codes')
        for field in ('scalars','exp','recip1','recip2'):
            if not np.array_equal(p['softmax'][field],d['softmax'][field]):raise ValueError('Softmax ABI narrowing changes codes')
    return raw

def finalize(name,out,device,batch):
    contract=json.loads((out/'contract.json').read_text())
    for path,sha in contract['sources'].items():
        if u.digest(path)!=sha:raise ValueError('source changed during experiment: '+path)
    initial_identity=pin_initial(out,out/'initial_u3/u3_artifact',require_existing=True)
    spec=u.dataset_spec(name);refs,hs=reference(spec)
    a,_=load_portable(out/'initial_u3/u3_artifact')
    state=torch.load(spec['checkpoint'],weights_only=True,map_location='cpu')['student_state']
    model=StrictQAT(a,state,refs,spec['classes'],hs).to(device)
    saved=torch.load(out/'best.pth',weights_only=True,map_location='cpu')
    if saved['initial_identity']!=initial_identity:raise ValueError('best checkpoint execution identity differs')
    if saved['recipe']!=json.loads((out/'recipe.json').read_text()):raise ValueError('best checkpoint recipe differs')
    model.load_state_dict(saved['model']);model.eval()
    a=model.export();refs=model.error_reference();raw=verify_export(a)
    final=out/'final';final.mkdir(exist_ok=True)
    persist_artifact(final/'artifact',portable(a),u.digest(out/'best.pth'))
    (final/'weights_e07_u3.bin').write_bytes(raw)
    hp=a['head'];np.savez(final/'head_parameters.npz',**hp)
    reloaded,_=load_portable(final/'artifact')
    ds,record=u.prepare_datasets(spec)
    images=torch.stack([ds['calibration'][i][0] for i in range(2)]).to(device)
    with torch.no_grad():
        wanted=model(images).long();actual,_=integer_forward(images,reloaded)
        if not torch.equal(wanted,actual):raise ValueError('disk-export integer parity failed')
    metrics={}
    for split in ('val','test'):
        metrics[split]=evaluate(reloaded,ds[split],device,batch,final/(split+'_predictions.csv'))
        u.save_json(final/'accuracy.json',metrics);event(out,event='final_accuracy',split=split,**metrics[split])
    prior.natural_audit(name,reloaded,refs,ds['test'],record,final,device)
    rows=prior_summary.read_csv(final/'unit_accuracy.csv');global_rows=[]
    counts=dict(Softmax=177020928,Softmax_EXP=177020928,Softmax_Reciprocal=903168,LayerNorm=115605504,GELU=231211008)
    for operator,count in counts.items():
        result=prior_summary.aggregate([r for r in rows if r['operator']==operator])
        if result['count']!=count:raise ValueError('local metric element count differs')
        global_rows.append(dict(dataset=name,operator=operator,scope='SAME_128_TEST_IMAGES_NEW_CAPTURE',**result))
    rs=prior_summary.read_csv(final/'rsqrt_accuracy.csv')
    if sum(int(r['count']) for r in rs)!=602112:raise ValueError('Rsqrt element count differs')
    n=sum(int(r['count']) for r in rs)
    global_rows.append(dict(dataset=name,operator='LayerNorm_Rsqrt',scope='SAME_128_TEST_IMAGES_NEW_CAPTURE',count=n,
        real_mae=sum(int(r['count'])*float(r['real_mae']) for r in rs)/n,
        real_rmse=math.sqrt(sum(int(r['count'])*float(r['real_rmse'])**2 for r in rs)/n),
        real_max_ae=max(float(r['real_max_ae']) for r in rs),unit='inverse_input_integer_code',exact_rate='NOT_APPLICABLE'))
    exhaustive=prior_summary.read_csv(final/'gelu_exhaustive.csv')
    if sum(int(r['count']) for r in exhaustive)!=24576:raise ValueError('GELU exhaustive count differs')
    global_rows.append(dict(dataset=name,operator='GELU',scope='EXHAUSTIVE_S11_2048',**prior_summary.aggregate(exhaustive)))
    u.write_csv(final/'nonlinear_error.csv',global_rows)
    u.write_csv(final/'accuracy.csv',[dict(dataset=name,split=k,**v) for k,v in metrics.items()])
    contract=json.loads((out/'contract.json').read_text())
    for path,sha in contract['sources'].items():
        if u.digest(path)!=sha:raise ValueError('source changed during experiment: '+path)
    u.save_json(final/'summary.json',dict(status='COMPLETE',accuracy=metrics,nonlinear_error=global_rows,
        best_epoch=saved['epoch'],best_checkpoint_sha256=u.digest(out/'best.pth'),
        native_ABI_roundtrip='PASS',disk_export_parity_integers=2000,original_sources_unchanged=True,
        states=dict(integer_software='MEASURED',new_HLS_C_sim='NOT_MEASURED',RTL_cosim='NOT_MEASURED',FPGA='NOT_MEASURED')))
    lines=['Strict E07 U3 QAT: '+name,'原 E07 无符号 Head；不等同历史有符号 Head U8 对照。',
        '全部数字均为整数/LUT软件测量；新 HLS C-sim / RTL / FPGA = NOT_MEASURED。',
        '原 HLS、RTL、bitstream 与 ImageNet Local4 未修改。',
        f"最佳 epoch: {saved['epoch']}，仅按完整 validation 选择。",
        'Head 参数保存在 head_parameters.npz；weights_e07_u3.bin 只是12 Block参数，不是 BOOT.bin。',
        '如后续部署需重新生成与 Head 参数一致的 ROM 和 bitstream；当前没有上板精度证据。']
    for split,r in metrics.items():lines.append(f"{split}: {r['correct']}/{r['sample_count']} = {r['top1_percent']:.6f}% Top1")
    (final/'report.txt').write_text('\n'.join(lines)+'\n')
    tex=[r'\begin{tabular}{lrrrrr}',r'\hline',r'Unit & MAE (LSB) & RMSE (LSB) & MaxAE & Exact (\%) & $\leq1$ LSB (\%) \\',r'\hline']
    for r in global_rows:
        if r['operator'] not in ('Softmax','LayerNorm','GELU') or r['scope'].startswith('EXHAUSTIVE'):continue
        tex.append(f"{r['operator']} & {r['mae_lsb']:.6f} & {r['rmse_lsb']:.6f} & {r['max_ae_lsb']:g} & {100*r['exact_rate']:.4f} & {100*r['within_1_lsb_rate']:.4f} \\\\")
    tex += [r'\hline',r'\end{tabular}','% Same local integer input; quantized float reference; NOT FPGA.']
    (final/'nonlinear_error.tex').write_text('\n'.join(tex)+'\n')
    archive=HERE/(name+'_e07_u3_qat_evidence.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in final.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(HERE))
        for p in (out/'recipe.json',out/'training.json',out/'dataset_identity.json',out/'events.jsonl',out/'contract.json',out/'initial_identity.json'):
            if p.exists():z.write(p,p.relative_to(HERE))
    event(out,event='evidence_complete',archive=str(archive),SHA256=u.digest(archive))

if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--dataset',choices=['plantvillage','nwpu'],required=True)
    args=parser.parse_args();torch.backends.cuda.matmul.allow_tf32=False;torch.set_num_threads(4)
    finalize(args.dataset,HERE/'outputs'/args.dataset,torch.device('cuda'),64)
