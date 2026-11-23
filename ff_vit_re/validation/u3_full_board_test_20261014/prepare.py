"""Export complete saved test splits, integer Golden and parameter-only ROM copies."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import zlib
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT/'validation/e07_u3_qat_20261010'), str(ROOT)]
from runtime import integer_forward, exact, u
from image1k_hls_s3_original.src.model import legacy_module
from board_contract import DATASETS, FRAME_BYTES, LOGIT_BYTES, pack_input, top5, validate_labels, native_padding


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20), b''): h.update(chunk)
    return h.hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def prepare(name, device, batch):
    count, classes = DATASETS[name]
    original = ROOT/'validation/e07_u3_progressive_qat_20261010/outputs'/name
    final = original/'final'
    artifact, meta = exact.load_artifact(final/'artifact')
    recipe = json.loads((original/'attention/recipe.json').read_text())
    accuracy = json.loads((final/'accuracy.json').read_text())['test']
    if meta['checkpoint_sha256'] != digest(original/'attention/best.pth'):
        raise ValueError('selected checkpoint and exported artifact differ')
    src = ROOT/'validation/e07_w3_s8_resource_20261009/baseline/src'
    for path,h in recipe['sources'].items():
        if path.startswith('/home/user/Desktop/FF_Vit/'):
            if digest(src/Path(path).name) != h:
                raise ValueError('frozen HLS source differs from the training contract: '+path)
    paths = [original/'attention/best.pth', original/'attention/recipe.json', final/'accuracy.json',
             final/'test_predictions.csv', final/'weights_e07_u3.bin', final/'head_parameters.npz',
             final/'artifact/manifest.json', final/'artifact/arrays.npz', final/'calibration.json']
    paths += [p for p in src.iterdir() if p.is_file() and (p.suffix=='.h' or p.name=='block0.cpp')]
    before = {str(p.resolve()):digest(p) for p in paths}
    out = HERE/'outputs'/name
    out.mkdir(parents=True, exist_ok=False)
    data = out/'data'; data.mkdir()
    hardware = out/'hardware'; (hardware/'src').mkdir(parents=True)
    for p in src.iterdir():
        if p.is_file() and (p.suffix=='.h' or p.name=='block0.cpp'):
            shutil.copy2(p, hardware/'src'/p.name)
    patch, head = artifact['patch'], artifact['head']
    legacy_module('s3_exact_head').write_complete_patch_head_rom(
        hardware/'src/fixed_patch_head_rom.h', head,
        patch_weight=np.asarray(patch['weight_code'], dtype=np.int8),
        patch_bias=np.asarray(patch['bias_raw']), patch_cls=np.asarray(patch['cls_raw']),
        patch_shift=int(patch['shift']))
    encoded = u.encode_blocks(native_padding(artifact['blocks']))
    if encoded != (final/'weights_e07_u3.bin').read_bytes() or len(encoded)!=2772096:
        raise ValueError('native Block ABI differs from saved export')
    (data/'weights.bin').write_bytes(encoded)
    datasets, identity = u.prepare_datasets(u.dataset_spec(name))
    ds = datasets['test']
    labels = np.asarray([y for _,y in ds.samples], dtype=np.int32)
    validate_labels(name, labels)
    if len(ds.classes)!=classes or ds.classes!=recipe['dataset_identity']['classes']:
        raise ValueError('class mapping differs from software evaluation')
    old = list(csv.DictReader((final/'test_predictions.csv').open()))
    if len(old)!=count or accuracy['sample_count']!=count:
        raise ValueError('software report is not the expected full test split')
    membership = [dict(path=str(p), label=int(y), sha256=digest(p)) for p,y in ds.samples]
    membership_hash = hashlib.sha256(json.dumps(membership, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    if membership_hash!=recipe['dataset_identity']['full_split_identity']['test']['ordered_membership_sha256']:
        raise ValueError('test split membership/content differs from training/evaluation binding')
    for i,(r,(path,label)) in enumerate(zip(old, ds.samples)):
        if int(r['index'])!=i or r['path']!=str(path) or int(r['label'])!=int(label):
            raise ValueError('software predictions do not match dataset order')
    save_json(data/'CLASSES.JSON', dict(dataset=name, classes=ds.classes))
    save_json(out/'source_identity.json', dict(dataset=name, sources=before,
        checkpoint_sha256=meta['checkpoint_sha256'], software_test_membership_sha256=membership_hash,
        original_software_accuracy=accuracy, HLS_source_scope='frozen E07 unsigned Head; only fixed ROM data replaced'))
    chunk_frames = 1000
    selected = sorted(set(np.linspace(0,count-1,4,dtype=np.int64).tolist()))
    fixtures = hardware/'fixtures'; fixtures.mkdir()
    tx = rx = None
    actual_correct = actual_top5 = replay_correct = replay_top5 = ties = changed_tie_predictions = 0
    frame = 0
    loader = torch.utils.data.DataLoader(ds, batch_size=batch, shuffle=False, num_workers=4, pin_memory=True)
    with (data/'INDEX.BIN').open('xb') as index, (data/'SAMPLES.CSV').open('x',newline='') as mapping, torch.inference_mode():
        index.write(struct.pack('<8s8I', b'FFVITU3\0',1,count,FRAME_BYTES,chunk_frames,12,classes,zlib.crc32(encoded),1000))
        writer = csv.writer(mapping)
        writer.writerow(['index','path','label','image_sha256','transformed_fp32_sha256','input_sha256','input_crc32',
                         'golden_sha256','golden_crc32','chunk','software_prediction','stable_prediction','top1_tied'])
        try:
            for images,ys in loader:
                logits,_ = integer_forward(images.to(device), artifact)
                old_top = logits.topk(5,-1).indices.cpu().tolist()
                golden = logits.cpu().numpy().astype('<i4')
                for image,y,codes,old_preds in zip(images.numpy(),ys.tolist(),golden,old_top):
                    payload = pack_input(image)
                    expected = codes.tobytes()
                    if len(expected)!=LOGIT_BYTES or np.any(codes < -262144) or np.any(codes>262143):
                        raise ValueError('Golden must contain canonical S19 codes in 1000 int32 containers')
                    stable = top5(codes, classes)
                    replay_correct += int(old_preds[0]==y); replay_top5 += int(y in old_preds)
                    if old_preds[0]!=int(old[frame]['prediction']) or int(y in old_preds)!=int(old[frame]['top5_correct']):
                        raise ValueError('replayed saved model differs from software per-image result at '+str(frame))
                    actual_correct += int(stable[0]==y); actual_top5 += int(y in stable)
                    is_tied = int(np.count_nonzero(codes[:classes]==codes[stable[0]])>1)
                    ties += is_tied; changed_tie_predictions += int(stable[0]!=old_preds[0])
                    if frame%chunk_frames==0:
                        if tx is not None: tx.close(); rx.close()
                        tx=(data/f'I{frame//chunk_frames:03d}.BIN').open('xb')
                        rx=(data/f'G{frame//chunk_frames:03d}.BIN').open('xb')
                    tx.write(payload); rx.write(expected)
                    crc, gold_crc = zlib.crc32(payload), zlib.crc32(expected)
                    index.write(struct.pack('<4I',frame,y,crc,gold_crc))
                    path=ds.samples[frame][0]
                    writer.writerow([frame,path,y,membership[frame]['sha256'],hashlib.sha256(image.tobytes()).hexdigest(),
                        hashlib.sha256(payload).hexdigest(),f'{crc:08x}',hashlib.sha256(expected).hexdigest(),
                        f'{gold_crc:08x}',frame//chunk_frames,old_preds[0],int(stable[0]),is_tied])
                    if frame in selected:
                        f=fixtures/f'frame_{frame:05d}';f.mkdir()
                        (f/'input_dma.bin').write_bytes(payload);(f/'expected.bin').write_bytes(expected)
                        shutil.copy2(data/'weights.bin',f/'weights.bin')
                        save_json(f/'identity.json',dict(index=frame,label=y,input_sha256=hashlib.sha256(payload).hexdigest(),
                            expected_sha256=hashlib.sha256(expected).hexdigest()))
                    frame+=1
                if frame%256 < batch or frame==count:
                    print(json.dumps(dict(event='export_progress',dataset=name,frames=frame,total=count)),flush=True)
        finally:
            if tx is not None:tx.close();rx.close()
    if frame!=count or replay_correct!=accuracy['correct'] or replay_top5!=accuracy['correct5']:
        raise ValueError('full software accuracy replay/count differs')
    for path,h in before.items():
        if digest(path)!=h:raise ValueError('original source changed during preparation: '+path)
    dataset = dict(status='FULL_DATA_AND_GOLDEN_READY_NOT_BOARD_MEASURED',dataset=name,count=count,classes=classes,
        chunk_frames=chunk_frames,frame_bytes=FRAME_BYTES,logit_bytes=LOGIT_BYTES,
        membership_sha256=membership_hash,transform=identity['transform'],input_scale=1/64,
        input_dtype='little-endian int16',dma_layout='[98,768,2]',all_196_input_patch_positions=True,
        token_layout='PL replaces first Patch output by CLS; 195 Patch tokens plus CLS',
        class_names=ds.classes,checkpoint_sha256=meta['checkpoint_sha256'],
        software_replay=dict(correct=replay_correct,correct5=replay_top5,top1_percent=100*replay_correct/count),
        board_tie_policy='ascending class ID; only active dataset classes',
        expected_board_policy=dict(correct=actual_correct,correct5=actual_top5,top1_percent=100*actual_correct/count,
                                   top5_percent=100*actual_top5/count,top1_tied_frames=ties,changed_tie_predictions=changed_tie_predictions),
        csim_fixture_indices=selected,files={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(data.iterdir())})
    save_json(out/'dataset.json',dataset)
    save_json(hardware/'source_identity.json',dict(source_files={p.name:digest(p) for p in sorted((hardware/'src').iterdir())},
        original_source=str(src),arithmetic_source_unchanged=True,changed_data=['fixed_patch_head_rom.h'],
        dataset=name,checkpoint_sha256=meta['checkpoint_sha256']))
    print(json.dumps(dict(event='prepare_complete',dataset=name,frames=count,expected_board_top1=dataset['expected_board_policy']['top1_percent'],
                          software_top1=100*replay_correct/count,output=str(out))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=list(DATASETS),required=True)
    p.add_argument('--device',default='cuda');p.add_argument('--batch',type=int,default=16)
    a=p.parse_args();torch.set_num_threads(4);torch.set_num_interop_threads(4)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.use_deterministic_algorithms(True)
    for key in ('TMPDIR','TORCH_HOME','XDG_CACHE_HOME'):
        target=HERE/'cache'/key.lower();target.mkdir(parents=True,exist_ok=True);os.environ[key]=str(target)
    prepare(a.dataset,torch.device(a.device),a.batch)
