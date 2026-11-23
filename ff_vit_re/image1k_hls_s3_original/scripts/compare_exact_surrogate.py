#!/usr/bin/env python3
"""Quantify surrogate-to-exact error on the same deterministic fixture images."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import torch
from src import exact
from src.attention_trainer import AttentionController,attention_masks
from src.provenance import atomic_write_json,sha256_file
from scripts.build_exact import selected_model


@torch.inference_mode()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path,default=ROOT/'exact/main')
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/exact_surrogate_fixtures.json')
    args=parser.parse_args()
    torch.set_num_threads(4)
    artifact,meta=exact.load_artifact(args.artifact)
    fixtures,fixture_meta=exact.load_artifact(args.fixtures)
    if fixture_meta['identity']['artifact']!=sha256_file(args.artifact/'manifest.json'):
        raise ValueError('fixture artifact binding differs')
    model,_,scales,_=selected_model()
    controller=AttentionController(model,scales)
    checkpoint=torch.load(ROOT/'checkpoints/attention/main/best.pth',map_location='cpu',weights_only=False)
    controller.load_state_dict(checkpoint['ema_controller'],strict=True)
    controller.set_masks(attention_masks(list(range(12)),3))
    captured={}
    handles=[]
    for i,block in enumerate(model.vit.blocks):
        for name,module in [('ln1',block.norm1),('ln2',block.norm2),('gelu',block.mlp.act),('mlp_residual',block)]:
            handles.append(module.register_forward_hook(lambda m,x,y,i=i,name=name:captured.__setitem__(f'block{i:02d}.{name}',y.detach().clone())))
    images=torch.from_numpy(fixtures['images'])
    surrogate=model(images)
    integer,traces=exact.forward(images,artifact,trace=True)
    rows=[]
    for key,target in captured.items():
        i=int(key[5:7]);name=key.split('.')[1]
        domain=artifact['blocks'][i]['softmax']['output_scale'] if name=='softmax' else (
            meta['blocks'][i]['output_scale'] if name=='mlp_residual' else scales[name][i])
        prediction=traces[key].double()*domain
        target=target.double()
        error=prediction-target
        cosine=torch.nn.functional.cosine_similarity(prediction.reshape(1,-1),target.reshape(1,-1)).item()
        rows.append(dict(boundary=key,mse=error.square().mean().item(),max_abs=error.abs().max().item(),cosine=cosine,
                         exact_real_min=prediction.min().item(),exact_real_max=prediction.max().item()))
    report=dict(stage='surrogate_vs_exact_fixed_fixtures',sample_count=len(images),sample_ids=fixture_meta['ids'],
                artifact_sha256=sha256_file(args.artifact/'manifest.json'),checkpoint_sha256=exact.CHECKPOINT_SHA256,
                surrogate_predictions=surrogate.argmax(-1).tolist(),exact_predictions=integer.argmax(-1).tolist(),
                top1_agreement=float((surrogate.argmax(-1)==integer.argmax(-1)).double().mean()),boundaries=rows,
                caveat='Approximation/domain differences are expected. Bit-exact gate compares software integers with HLS, not surrogate floats.')
    atomic_write_json(args.output,report)


if __name__=='__main__':
    main()
