"""Fail-closed checks before export; data and source identities are re-read."""
import argparse
import json
import math
import re
import struct
import zlib
from pathlib import Path
from board_contract import DATASETS, FRAME_BYTES, LOGIT_BYTES, validate_release
from prepare import HERE, digest, save_json

def timing_values(timing):
    for key in ('no_clock','unconstrained_internal_endpoints'):
        match=re.search(r'checking '+key+r' \((\d+)\)',timing)
        if not match or int(match[1])!=0: raise ValueError('missing/failing timing coverage: '+key)
    if 'WNS(ns)' not in timing: raise ValueError('missing timing summary')
    lines=timing.split('WNS(ns)',1)[1].splitlines()
    rows=[s.split() for s in lines if re.match(r'^\s*-?\d+\.\d+\s',s)]
    if not rows or len(rows[0])<12: raise ValueError('incomplete timing summary')
    v=list(map(float,rows[0][:12]))
    if not all(math.isfinite(x) for x in v): raise ValueError('nonfinite timing')
    for a,b,c in ((0,1,2),(4,5,6),(8,9,10)):
        if v[a]<0 or v[b]!=0 or v[c]!=0: raise ValueError('setup/hold/pulse timing failed')
    return dict(wns=v[0],whs=v[4],wpws=v[8],setup_fail=int(v[2]),hold_fail=int(v[6]),pulse_fail=int(v[10]))

def route_values(route):
    counts={}
    for label in ('routable nets','fully routed nets','nets with routing errors'):
        m=re.search(r'# of '+label+r'\.+\s*:\s*(\d+)',route)
        if not m: raise ValueError('missing route count: '+label)
        counts[label]=int(m[1])
    if counts['routable nets']<=0 or counts['routable nets']!=counts['fully routed nets'] or counts['nets with routing errors']!=0:
        raise ValueError('routing incomplete or failed')
    return dict(unrouted=0,routing_errors=0,routable_nets=counts['routable nets'])

def verify_data(out):
    meta=json.loads((out/'dataset.json').read_text()); data=out/'data'
    count,classes=DATASETS[meta['dataset']]
    if meta['count']!=count or meta['classes']!=classes: raise ValueError('wrong split')
    for name,v in meta['files'].items():
        if (data/name).stat().st_size!=v['bytes'] or digest(data/name)!=v['sha256']:
            raise ValueError('dataset file changed: '+name)
    raw=(data/'INDEX.BIN').read_bytes()
    if len(raw)!=40+count*16: raise ValueError('index size differs')
    h=struct.unpack('<8s8I',raw[:40])
    if h!=(b'FFVITU3\0',1,count,FRAME_BYTES,1000,12,classes,zlib.crc32((data/'weights.bin').read_bytes()),1000):
        raise ValueError('index header differs')
    records=[struct.unpack('<4I',raw[40+i*16:56+i*16]) for i in range(count)]
    for chunk in range((count+999)//1000):
        n=min(1000,count-chunk*1000)
        with (data/f'I{chunk:03d}.BIN').open('rb') as inputs,(data/f'G{chunk:03d}.BIN').open('rb') as goldens:
            for offset in range(n):
                i=chunk*1000+offset; record=records[i]
                inp=inputs.read(FRAME_BYTES); gold=goldens.read(LOGIT_BYTES)
                if record[0]!=i or not 0<=record[1]<classes or len(inp)!=FRAME_BYTES or len(gold)!=LOGIT_BYTES:
                    raise ValueError('invalid dataset record')
                if (zlib.crc32(inp),zlib.crc32(gold))!=record[2:]: raise ValueError('frame CRC differs')
            if inputs.read(1) or goldens.read(1): raise ValueError('extra chunk data')
    return meta

def verify_fixtures(out,meta):
    hw=out/'hardware';data=out/'data'
    selected=sorted(set((i*(meta['count']-1))//3 for i in range(4)))
    if meta['csim_fixture_indices']!=selected: raise ValueError('missing or changed C-sim sample set')
    for idx in selected:
        chunk,offset=divmod(idx,meta['chunk_frames'])
        with (data/f'I{chunk:03d}.BIN').open('rb') as f:
            f.seek(offset*FRAME_BYTES);inp=f.read(FRAME_BYTES)
        with (data/f'G{chunk:03d}.BIN').open('rb') as f:
            f.seek(offset*LOGIT_BYTES);gold=f.read(LOGIT_BYTES)
        fixture=hw/'fixtures'/f'frame_{idx:05d}'
        if (fixture/'input_dma.bin').read_bytes()!=inp or (fixture/'expected.bin').read_bytes()!=gold:
            raise ValueError('C-sim fixture input/Golden differs from frozen full split')
        if (fixture/'weights.bin').read_bytes()!=(data/'weights.bin').read_bytes():
            raise ValueError('C-sim fixture uses another weight export')
        for fn in ('csim_logits.bin','csim_repeat_logits.bin'):
            if (fixture/fn).read_bytes()!=gold: raise ValueError('C-sim output differs from frozen full split')

def qualify(name):
    out=HERE/'outputs'/name;hw=out/'hardware';rpts=hw/'results/candidate05'
    meta=verify_data(out)
    for path,h in json.loads((out/'source_identity.json').read_text())['sources'].items():
        if digest(path)!=h: raise ValueError('frozen original changed: '+path)
    source=json.loads((hw/'source_identity.json').read_text())
    for filename,h in source['source_files'].items():
        if digest(hw/'src'/filename)!=h: raise ValueError('HLS source changed after synthesis')
    csim=json.loads((hw/'csim_verified.json').read_text())
    if csim['source_identity']!=source or csim['pass_'] is not True: raise ValueError('C-sim identity failed')
    if csim['fixture_indices']!=meta['csim_fixture_indices'] or csim['frames_per_fixture']!=2 or csim['logit_codes_per_call']!=1000:
        raise ValueError('C-sim coverage differs from requested vectors')
    if digest(hw/'csim/project/solution1/csim/build/csim.exe')!=csim['executable_sha256']:
        raise ValueError('C-sim executable changed after verification')
    verify_fixtures(out,meta)
    record=timing_values((rpts/'timing_postroute.rpt').read_text())
    record.update(route_values((rpts/'route_status.rpt').read_text()))
    drc=(rpts/'drc.rpt').read_text()
    if 'Report DRC' not in drc or re.search(r'\|\s*(Error|Critical Warning)\s*\|',drc):
        raise ValueError('missing/failed DRC')
    clock=dict(s.split('=',1) for s in (rpts/'clock.txt').read_text().splitlines() if '=' in s)
    def number(key):
        v=float(clock[key])
        if not math.isfinite(v) or v<=0: raise ValueError('invalid clock')
        return v
    for config,implemented in [('MMCM_MULT','CLKFBOUT_MULT_F'),('MMCM_DIVCLK','DIVCLK_DIVIDE'),('MMCM_OUT_DIV','CLKOUT0_DIVIDE_F')]:
        if abs(number(config)-number('IMPLEMENTED_'+implemented))>0.00001: raise ValueError('MMCM differs')
    actual=number('PS_PL_ACTUAL_MHZ')*number('MMCM_MULT')/number('MMCM_DIVCLK')/number('MMCM_OUT_DIV')
    if abs(actual-number('PL_ACTUAL_MHZ'))>0.0005: raise ValueError('core frequency differs')
    if number('PL_PERIOD_NS')>1000/actual+0.00051: raise ValueError('clock constraint slower than hardware')
    if number('RESET_LOCK_VERIFIED')!=1 or number('CORE_CLOCK_CONSUMERS_VERIFIED')!=1: raise ValueError('clock topology unverified')
    record.update(csim_pass=True,data_complete=True,identity_verified=True,clock_verified=True,
        clock_mhz=actual,drc_errors=0,dataset=name,frames=meta['count'],board_measured=False,rtl_cosimulation_measured=False,
        hardware_source_identity=source,
        reports_sha256={p.name:digest(p) for p in rpts.iterdir() if p.is_file() and p.suffix in ('.rpt','.txt')})
    validate_release(record)
    save_json(out/'qualification.json',record)
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=list(DATASETS),required=True)
    p.add_argument('--data-only',action='store_true');a=p.parse_args()
    r=verify_data(HERE/'outputs'/a.dataset) if a.data_only else qualify(a.dataset)
    print(json.dumps(dict(dataset=a.dataset,status='PASS',frames=r.get('count',r.get('frames')))))
