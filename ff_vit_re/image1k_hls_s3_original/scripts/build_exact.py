#!/usr/bin/env python3
"""Build deterministic original-width integer artifacts from selected strict EMA."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from src import exact
from src.contract import load_contract, validate_mainline_contract
from src.data import make_calibration_loader, load_class_mapping
from src.model import load_w3_parent, legacy_module
from src.provenance import atomic_write_json, sha256_file


def inventory():
    sources = list(exact.HLS_ROOT.glob('*.h')) + [exact.HLS_ROOT/'block0.cpp']
    sources += [ROOT/'src/exact.py',ROOT/'src/exact_fit.py',ROOT/'src/exact_head_fit.py',Path(__file__),
                ROOT/'config/original_hls_s3.yaml', ROOT/'checkpoints/attention/main/best.pth',
                ROOT/'metadata/calibration_manifest.jsonl', ROOT/'metadata/selection_manifest.jsonl',
                ROOT/'../image_lianghu/src/legacy_s3_lut.py', ROOT/'../image_lianghu/src/hls_s3_abi.py',
                ROOT/'../image_lianghu/src/s3_exact_head.py',
                ROOT/'../image_lianghu/scripts/build_exact_integer_artifacts.py',
                ROOT/'../quantization_final/scripts/stage4o_exact_head_signedfix.py']
    return dict(schema='original_hls_s3.source_binding.v1',sources=exact.bind_sources(sources),
        execution={'attention':'attn.h -> fused_flash_attn.h','score':'int S_buf; long long dot product; s10 typedef inactive',
                   'probability':'int rq_val; exported clamp_bits=3 enforces0..7; u3 typedef inactive',
                   'head':'block0.cpp fixed_head_layernorm selected fixed-ROM path',
                   'mac_scales':'activation scale multiplied by W3 scale; no independent FC/O output requant'},
        policy='Original HLS source unchanged. Parameters only. Exact accuracy requires separate full50k measurement.')


def selected_model():
    config = load_contract(ROOT/'config/original_hls_s3.yaml')
    validate_mainline_contract(config)
    checkpoint = ROOT/'checkpoints/attention/main/best.pth'
    if sha256_file(checkpoint) != exact.CHECKPOINT_SHA256:
        raise ValueError('selected checkpoint hash mismatch')
    model,_ = load_w3_parent(config['model']['w3_qat_checkpoint'],contract=ROOT/'config/original_hls_s3.yaml')
    saved = torch.load(checkpoint,map_location='cpu',weights_only=False)
    model.load_state_dict(saved['ema_model'],strict=True)
    scales = {name.removeprefix('log_scales.'):value.exp().tolist() for name,value in saved['ema_controller'].items()}
    exported = legacy_module('qat_weight').export_qat_integer_state(model)
    return model.eval(), exported, scales, config


def npvalue(value):
    return value.detach().cpu().numpy() if torch.is_tensor(value) else np.asarray(value)


def export_hls(destination, artifact):
    abi = legacy_module('hls_s3_abi')
    blocks = artifact['blocks']
    arrays = {}
    for p in blocks:
        row = {'attn_scalars':p['attn_residual'],'mlp_scalars':p['mlp_residual']}
        for key,name in [('attn','ln1'),('mlp','ln2')]:
            for old,new in [('scalars','ln_scalars'),('lnw','lnw'),('lnb','lnb'),('rsqrt_table','rsqrt')]:
                row[key+'_'+new] = p[name][old]
        for key,name in [('qq','q'),('kq','k'),('vq','v'),('aq','a'),('ge','gelu')]:
            row[key+'_scalars'] = p[name+'_lut']['scalars']
            row[key+'_table'] = p[name+'_lut']['table']
        for old,new in [('scalars','scalars'),('exp','exp'),('recip1','recip1'),('recip2','recip2')]:
            row['softmax_'+new] = p['softmax'][old]
        for key,value in row.items():
            arrays.setdefault(key,[]).append(npvalue(value))
    arrays = {name:np.stack(values) for name,values in arrays.items()}
    packed = b''.join(abi.build_attn_struct(p,arrays,i)+abi.build_mlp_struct(p,arrays,i) for i,p in enumerate(blocks))
    (destination/'weights.bin').write_bytes(packed)
    abi.write_fields(destination/'weights_fields.bin',blocks,arrays)
    head = artifact['head']; patch = artifact['patch']
    legacy_module('s3_exact_head').write_complete_patch_head_rom(destination/'fixed_patch_head_rom.h',head,
        patch_weight=patch['weight_code'],patch_bias=patch['bias_raw'],patch_cls=patch['cls_raw'],patch_shift=8)
    np.savez(destination/'encoder_abi_arrays.npz',**arrays)


@torch.inference_mode()
def build(args):
    binding = inventory()
    model,weights,scales,config = selected_model()
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError(out)
    cache = ROOT/'exact/cache'/out.name
    cache.mkdir(parents=True,exist_ok=True)
    source_binding = cache/'source_binding.json'
    if source_binding.exists() and json.loads(source_binding.read_text()) != binding:
        raise ValueError('cached source identity differs')
    atomic_write_json(source_binding,binding)
    f = exact.fitters()
    patch = f['fit_patch_artifacts'](model.state_dict())
    mapping = load_class_mapping(ROOT/'../image_lianghu/metadata/class_mapping.json')
    loader = make_calibration_loader(ROOT/'metadata/calibration_manifest.jsonl',root=config['data']['train']['path'],
        class_mapping=mapping,batch_size=args.batch_size,num_workers=args.workers,expected_count=2000)
    all_codes=[]; ids=[]
    for images,labels,names in loader:
        if len(ids)>=args.samples:
            break
        images=images[:args.samples-len(ids)]; names=names[:len(images)]
        all_codes.append(exact.patch_forward(images.to(args.device),patch).cpu())
        ids.extend(names)
    codes=torch.cat(all_codes)
    scale=float(patch['output_scale'])
    blocks=[]; reports=[]
    for index in range(12):
        stage=cache/f'block{index:02d}'
        if stage.exists():
            saved,meta=exact.load_artifact(stage)
            if meta['source_binding']!=binding or meta['sample_ids']!=ids or meta['fit_tokens']!=args.fit_tokens:
                raise ValueError('block cache provenance mismatch')
            p,report,codes=saved['params'],saved['report'],torch.from_numpy(saved['output'])
        else:
            p,report=exact.fit_block(index,codes,scale,model.state_dict(),weights,scales,fit_tokens=args.fit_tokens)
            outputs=[]
            for batch in codes.split(args.batch_size):
                outputs.append(exact.block_forward(batch.to(args.device),p)[0].cpu())
            codes=torch.cat(outputs)
            exact.save_artifact(stage,dict(params=p,report=report,output=codes.to(torch.int16)),
                dict(source_binding=binding,sample_ids=ids,fit_tokens=args.fit_tokens))
        blocks.append(p); reports.append(report); scale=report['output_scale']
        print(json.dumps({'block':index,'range':[int(codes.min()),int(codes.max())],
                          'physical_output_scale':scale,'m1_wrap':report['m1_wrap_rate']}),flush=True)
    from src import exact_head_fit
    cls=codes[:,0].long()
    target=model.vit.norm(cls.float()*scale).double()
    ln=exact_head_fit.fit_head_ln(cls,target,scale,1e-6,cursor_bits=7)
    qln=exact_head_fit.apply_head_ln(cls,ln).long()
    headfit=legacy_module('s3_exact_head').fit_head_classifier(qln,target,model.vit.head.weight,model.vit.head.bias,
                                                            ln_scale=ln['output_scale'])
    head={ 'head_ln_scalars':npvalue(ln['scalars']).astype(np.int32),'head_lnw':npvalue(ln['lnw']).astype(np.int32),
           'head_lnb':npvalue(ln['lnb']).astype(np.int64),'head_rsqrt':npvalue(ln['rsqrt_table']).astype(np.int32),
           'head_weight':npvalue(headfit['qw']).astype(np.int8),'head_bias':npvalue(headfit['qb']).astype(np.int32)}
    artifact=dict(patch=patch,blocks=blocks,head=head,final_encoder_scale=scale)
    metadata=dict(source_binding=binding,checkpoint_sha256=exact.CHECKPOINT_SHA256,
                  stage='exact_integer_artifacts',formal_accuracy_measured=False,calibration_count=len(ids),
                  calibration_ids=ids,fit_tokens=args.fit_tokens,blocks=reports,
                  head_scale=headfit['logit_scale'],head_top1_agreement=headfit['top1_agreement'])
    exact.save_artifact(out,artifact,metadata)
    export_hls(out,artifact)
    atomic_write_json(out/'export_hashes.json',exact.bind_sources(sorted(p for p in out.iterdir() if p.is_file())))
    print(json.dumps({'artifact':str(out),'status':'BUILT_NOT_EVALUATED'}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory-only',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'exact/main')
    parser.add_argument('--device',default='cpu')
    parser.add_argument('--samples',type=int,default=2000)
    parser.add_argument('--fit-tokens',type=int,default=6272)
    parser.add_argument('--batch-size',type=int,default=8)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--threads',type=int,default=4)
    args=parser.parse_args()
    torch.set_num_threads(args.threads)
    torch.backends.cuda.matmul.allow_tf32=False
    if args.inventory_only:
        atomic_write_json(ROOT/'exact/source_binding.json',inventory())
    else:
        if not 1<=args.samples<=2000 or args.fit_tokens<196:
            raise ValueError('invalid calibration sample/token budget')
        build(args)


if __name__=='__main__':
    main()
