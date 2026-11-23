#!/usr/bin/env python3
"""Separate full50k exact accuracy from probes and fixed HLS fixtures."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from src import exact
from src.data import make_validation_loader
from src.model import load_hls196_fp32
from src.contract import load_contract
from src.provenance import atomic_write_json,sha256_file


def rank_logits(logits):
    return torch.argsort(logits,dim=-1,descending=True,stable=True)[:,:5]


def validate_shard(row,ids,labels):
    if row['ids']!=list(ids) or row['labels']!=labels.tolist():
        raise ValueError('resume validation identity/label mismatch')
    prediction=torch.tensor(row['top5'])
    if prediction.shape!=(len(ids),5) or bool(((prediction<0)|(prediction>=1000)).any()):
        raise ValueError('invalid prediction shape/range')
    one=int((prediction[:,0]==labels).sum())
    five=int((prediction==labels[:,None]).any(-1).sum())
    if (row['correct1'],row['correct5'])!=(one,five):
        raise ValueError('prediction/count mismatch')
    return one,five


@torch.inference_mode()
def evaluate(args):
    artifact,metadata=exact.load_artifact(args.artifact)
    exact.verify_sources(metadata['source_binding']['sources'])
    if metadata['checkpoint_sha256']!=exact.CHECKPOINT_SHA256:
        raise ValueError('selected checkpoint mismatch')
    config=load_contract(ROOT/'config/original_hls_s3.yaml')
    model=load_hls196_fp32(config['model']['hls196_fp32_checkpoint'])
    loader=make_validation_loader(config['data']['validation']['path'],model=model,
                                  batch_size=args.batch_size,num_workers=args.workers)
    output=args.output
    if output.exists():
        raise FileExistsError(output)
    session=output.parent/(output.stem+'_shards')
    session.mkdir(parents=True,exist_ok=True)
    identity=dict(artifact=sha256_file(args.artifact/'manifest.json'),arrays=sha256_file(args.artifact/'arrays.npz'),
                  source=sha256_file(ROOT/'src/exact.py'),runner=sha256_file(Path(__file__)),
                  data_adapter=sha256_file(ROOT/'src/data.py'),limit=args.limit,protocol='crop09',
                  batch_size=args.batch_size,torch_version=torch.__version__)
    binding=session/'identity.json'
    if binding.exists() and json.loads(binding.read_text())!=identity:
        raise ValueError('resume identity differs')
    atomic_write_json(binding,identity)
    seen=set();top1=0;top5=0;start=time.perf_counter()
    for batch,(images,labels,ids) in enumerate(loader):
        if args.limit and len(seen)>=args.limit:
            break
        if args.limit:
            remaining=args.limit-len(seen);images=images[:remaining];labels=labels[:remaining];ids=ids[:remaining]
        if seen.intersection(ids) or len(set(ids))!=len(ids):
            raise ValueError('duplicate validation samples')
        shard=session/f'{batch:06d}.json'
        if shard.exists():
            saved=json.loads(shard.read_text())
            one,five=validate_shard(saved,ids,labels)
        else:
            logits,trace=exact.forward(images.to(args.device),artifact,trace=batch==0 and args.fixtures>0)
            predicted=rank_logits(logits).cpu()
            one=int((predicted[:,0]==labels).sum());five=int((predicted==labels[:,None]).any(-1).sum())
            atomic_write_json(shard,dict(ids=list(ids),labels=labels.tolist(),top5=predicted.tolist(),correct1=one,correct5=five))
            if trace:
                n=min(args.fixtures,len(images))
                fixture=session/'fixtures'
                if not fixture.exists():
                    raw=torch.nn.functional.unfold((images[:n]*64).round().clamp(-32768,32767),kernel_size=16,stride=16).transpose(1,2).long()
                    exact.save_artifact(fixture,dict(images=images[:n],raw_patch_input=raw,
                        traces={key:value[:n].cpu() for key,value in trace.items()}),dict(ids=list(ids[:n]),identity=identity))
                    for i in range(n):
                        raw[i].numpy().astype('<i2').tofile(fixture/f'input_{i:03d}.bin')
                        trace['logits'][i].cpu().numpy().astype('<i4').tofile(fixture/f'logits_{i:03d}.bin')
        seen.update(ids);top1+=one;top5+=five
        if batch%20==0:
            print(json.dumps(dict(samples=len(seen),top1=top1/len(seen),seconds=time.perf_counter()-start)),flush=True)
    expected=args.limit or 50000
    if len(seen)!=expected:
        raise ValueError(f'expected{expected} unique validation samples, got{len(seen)}')
    report=dict(stage='exact_integer_50k' if not args.limit else 'exact_integer_probe',sample_count=len(seen),
                top1=top1/len(seen),top5=top5/len(seen),correct1=top1,correct5=top5,
                identity=identity,sample_ids_sha256=hashlib.sha256('\n'.join(sorted(seen)).encode()).hexdigest(),
                elapsed_seconds=time.perf_counter()-start,hls_verified=False,
                target_69_reached=top1/len(seen)>=.69,calibration_count=metadata['calibration_count'],
                tie_policy='descending integer logit, ascending class id')
    atomic_write_json(output,report)
    print(json.dumps(report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path,default=ROOT/'exact/main')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/exact_50k.json')
    parser.add_argument('--device',default='cuda')
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--batch-size',type=int,default=16)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--fixtures',type=int,default=4)
    args=parser.parse_args()
    if args.limit<0 or args.limit>50000 or args.batch_size<1:
        raise ValueError('invalid evaluation sample/batch count')
    if args.limit and args.output.name=='exact_50k.json':
        raise ValueError('probe must use a separate report filename')
    torch.set_num_threads(args.threads);torch.backends.cuda.matmul.allow_tf32=False
    evaluate(args)


if __name__=='__main__':
    main()
