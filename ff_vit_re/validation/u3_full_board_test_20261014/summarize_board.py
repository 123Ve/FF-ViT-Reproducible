"""Check returned SD output against every Golden code; never accepts partial runs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
from board_contract import DATASETS, compare_logits, top5

def summarize(folder):
    folder=Path(folder)
    binding=json.loads((folder/'identity.json').read_text())
    if binding['status']!='READY_FOR_FULL_BOARD_TEST_NOT_BOARD_MEASURED': raise ValueError('package was not qualified')
    for name,item in binding['files'].items():
        p=folder/name
        if p.stat().st_size!=item['bytes']: raise ValueError('published file size differs: '+name)
        with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
        if h!=item['sha256']: raise ValueError('published file hash differs: '+name)
    meta=json.loads((folder/'dataset.json').read_text())
    if binding['dataset']!=meta['dataset'] or binding['firmware_identity']['config']['CHECKPOINT_SHA256']!=json.dumps(meta['checkpoint_sha256']):
        raise ValueError('package/model/checkpoint metadata differs')
    count,classes=DATASETS[meta['dataset']]
    if meta['count']!=count or meta['classes']!=classes: raise ValueError('invalid full test split')
    summary=dict(s.split('=',1) for s in (folder/'ACCSUM.TXT').read_text().splitlines() if '=' in s)
    for key,value in [('DATASET',meta['dataset']),('CHECKPOINT_SHA256',meta['checkpoint_sha256']),
                      ('BOARD_EVALUATION_COMPLETE','YES'),('REQUESTED_FRAMES',str(count)),
                      ('COMPLETED_FRAMES',str(count)),('FAILED_FRAMES','0'),
                      ('TOPK_TIE_POLICY','ASCENDING_ACTIVE_CLASS_ID')]:
        if summary.get(key)!=value: raise ValueError('incomplete/mismatched board run: '+key)
    if summary.get('FIXED_ROM_SHA256')!=binding['fixed_rom_sha256']: raise ValueError('ROM identity differs')
    for name,item in meta['files'].items():
        p=folder/name
        if p.stat().st_size!=item['bytes']: raise ValueError('reference size differs')
        with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
        if h!=item['sha256']: raise ValueError('reference hash differs')
    raw=(folder/'INDEX.BIN').read_bytes()
    labels=np.asarray([struct.unpack_from('<4I',raw,40+i*16)[1] for i in range(count)])
    actual=np.fromfile(folder/'LOGITS.BIN',dtype='<i4')
    if actual.size!=count*1000: raise ValueError('not all board logits returned')
    actual=actual.reshape(count,1000)
    reference=np.concatenate([np.fromfile(folder/f'G{i:03d}.BIN',dtype='<i4') for i in range((count+999)//1000)]).reshape(count,1000)
    result=compare_logits(actual,reference)
    rows=list(csv.DictReader((folder/'RESULT.CSV').open()))
    if len(rows)!=count: raise ValueError('partial/duplicated result CSV')
    correct1=correct5=0;inference_ticks=0
    for i,(r,v,label) in enumerate(zip(rows,actual,labels)):
        record=struct.unpack_from('<4I',raw,40+i*16)
        pred=top5(v,classes).tolist()
        if int(r['index'])!=i or int(r['label'])!=label or [int(r[f'pred{k}']) for k in range(1,6)]!=pred:
            raise ValueError('CSV order/label/prediction inconsistent with actual logits')
        if (int(r['input_crc32'],16),int(r['golden_crc32'],16))!=record[2:]: raise ValueError('CSV CRC differs')
        hit1=int(pred[0]==label);hit5=int(label in pred)
        mismatch=int(np.count_nonzero(v!=reference[i]));maxae=int(np.abs(v.astype(np.int64)-reference[i]).max())
        if (int(r['correct1']),int(r['correct5']),int(r['logit_mismatches']),int(r['max_ae']))!=(hit1,hit5,mismatch,maxae):
            raise ValueError('CSV correctness/error counts inconsistent')
        correct1+=hit1;correct5+=hit5;inference_ticks+=int(r['inference_ticks'])
    for k,v in [('TOP1_CORRECT',correct1),('TOP5_CORRECT',correct5),('LOGIT_MISMATCHES',result['mismatches']),
                ('MISMATCHED_FRAMES',result['frames_with_mismatch']),('MAX_LOGIT_AE',result['max_ae']),
                ('INFERENCE_TICKS',inference_ticks)]:
        if int(summary[k])!=v: raise ValueError('summary count inconsistent: '+k)
    if summary['BIT_EXACT_PASS']!=('YES' if result['mismatches']==0 else 'NO'): raise ValueError('inconsistent bit-exact status')
    timer=int(summary['TIMER_HZ']);wall=int(summary['DATASET_WALL_TICKS'])
    if min(timer,wall,inference_ticks)<=0: raise ValueError('invalid measured times')
    result.update(dataset=meta['dataset'],frames=count,correct1=correct1,correct5=correct5,
        top1_percent=100*correct1/count,top5_percent=100*correct5/count,
        software_top1_percent=meta['software_replay']['top1_percent'],
        inference_window_fps=count*timer/inference_ticks,dataset_wall_fps=count*timer/wall,
        measurement_scope='physical board outputs; inference excludes SD read/CRC/Golden compare/logging/UART; dataset wall includes them',
        status='BOARD_BIT_EXACT_PASS' if result['mismatches']==0 else 'BOARD_BIT_EXACT_FAIL',
        returned_files_sha256={name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
            for name in ('RESULT.CSV','LOGITS.BIN','ACCSUM.TXT')})
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('sd_folder');p.add_argument('--output');a=p.parse_args()
    report=summarize(a.sd_folder);text=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if a.output:
        with Path(a.output).open('x') as f: f.write(text)
    print(text)
