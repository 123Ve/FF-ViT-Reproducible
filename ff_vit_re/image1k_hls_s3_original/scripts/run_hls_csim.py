#!/usr/bin/env python3
"""Copy immutable original HLS, run Vitis C simulation and compare all blocks."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src import exact
from src.hls_csim import sha256,verify_inventory,validate_input,validate_weights,compare_boundaries


def write_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')


def prepare(args):
    source=Path(args.source).resolve();hls=ROOT/'hls';dest=hls/'src'
    binding=json.loads((ROOT/'exact/source_binding.json').read_text())['sources']
    original={str(p):sha256(p) for p in sorted(source.iterdir()) if p.suffix in ('.h','.cpp')}
    verify_inventory({p:d for p,d in binding.items() if Path(p).parent==source})
    dest.mkdir(parents=True,exist_ok=True)
    needed=set()
    def visit(name):
        if name in needed or name=='fixed_patch_head_rom.h':return
        needed.add(name)
        content=(source/name).read_text()
        for child in re.findall(r'^\s*#include\s+"([^"\n]+)"',content,re.M):visit(child)
    visit('block0.cpp')
    for name in sorted(needed):shutil.copy2(source/name,dest/name)
    artifact=Path(args.artifact).resolve();fixtures=Path(args.fixtures).resolve()
    payload,meta=exact.load_artifact(fixtures)
    if meta['identity']['artifact']!=sha256(artifact/'manifest.json'):
        raise ValueError('fixtures were produced by a different exact artifact')
    exports=json.loads((artifact/'export_hashes.json').read_text())
    # Validate exact BIN and ROM against their frozen export manifest.
    for name in ('weights.bin','fixed_patch_head_rom.h'):
        expected=exports[str(artifact/name)]
        if isinstance(expected,dict):expected=expected['sha256']
        if sha256(artifact/name)!=expected:raise ValueError(f'export hash mismatch: {name}')
    validate_weights(artifact/'weights.bin')
    shutil.copy2(artifact/'fixed_patch_head_rom.h',dest/'fixed_patch_head_rom.h')
    for index,_ in enumerate(meta['ids']):
        sample=hls/'data'/f'sample_{index:03d}';sample.mkdir(parents=True,exist_ok=True)
        validate_input(fixtures/f'input_{index:03d}.bin')
        for src,name in ((artifact/'weights.bin','weights.bin'),
                         (fixtures/f'input_{index:03d}.bin','input.bin'),
                         (fixtures/f'logits_{index:03d}.bin','output.bin')):
            shutil.copy2(src,sample/name)
    verify_inventory(original)
    record={'original_source_directory':str(source),'original_source_hashes':original,
            'copied_sources':{name:sha256(dest/name) for name in sorted(needed)},
            'parameter_rom':sha256(dest/'fixed_patch_head_rom.h'),
            'artifact_manifest_sha256':sha256(artifact/'manifest.json'),
            'fixture_manifest_sha256':sha256(fixtures/'manifest.json'),
            'fixture_ids':meta['ids'],'native_block_stride':231008,
            'input_layout':'logical little-endian int16[196,768]; TB emits [98,768,2]',
            'architecture_changes':[]}
    write_json(hls/'source_manifest.json',record)
    return payload,record


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',default='/home/user/Desktop/FF_Vit/flash_vit_2/src')
    p.add_argument('--artifact',default=str(ROOT/'exact/main'))
    p.add_argument('--fixtures',default=str(ROOT/'reports/exact_probe128_shards/fixtures'))
    p.add_argument('--vitis',default='/opt/vivado/2025.1/Vitis/bin/vitis-run')
    p.add_argument('--prepare-only',action='store_true')
    args=p.parse_args()
    payload,provenance=prepare(args)
    if args.prepare_only:
        print('HLS_PREPARED');return
    run=ROOT/'results/hls'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    run.mkdir(parents=True)
    env=os.environ.copy();env['FVIT_HLS_ROOT']=str(ROOT/'hls')
    env['FVIT_HLS_SAMPLE']=str(ROOT/'hls/data/sample_000')
    command=[args.vitis,'--mode','hls','--tcl',str(ROOT/'hls/run_csim.tcl')]
    start=time.monotonic()
    with (run/'vitis.log').open('w') as log:
        result=subprocess.run(command,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT)
    build=ROOT/'hls/build/project/solution1/csim/build'
    rows=[]
    report={'schema':'original_hls_s3.hls_csim.v1','command':command,'provenance':provenance,
            'vitis_returncode':result.returncode,'samples':rows,'passed':False,
            'status':'FAIL','run_directory':str(run),'scope':'4 fixed samples, Patch + 12 block boundaries + logits; not dataset accuracy'}
    try:
        for index,sample_id in enumerate(provenance['fixture_ids']):
            sample=run/f'sample_{index:03d}';sample.mkdir()
            if index==0:
                for dump in build.glob('hls_*.bin'):shutil.copy2(dump,sample/dump.name)
                rc=result.returncode
            else:
                for item in (ROOT/'hls/data'/f'sample_{index:03d}').iterdir():shutil.copy2(item,sample/item.name)
                with (sample/'csim.log').open('w') as log:
                    rc=subprocess.run([str(build/'csim.exe')],cwd=sample,stdout=log,stderr=subprocess.STDOUT).returncode
            expected={key:value[index] for key,value in payload['traces'].items()}
            comparison=compare_boundaries(sample,expected)
            rows.append({'sample_id':sample_id,'returncode':rc,**comparison})
        verify_inventory(provenance['original_source_hashes'])
        report['originals_unchanged']=True
        report['passed']=result.returncode==0 and all(r['passed'] and r['returncode']==0 for r in rows)
        report['status']='PASS' if report['passed'] else 'FAIL'
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report['vitis_log_sha256']=sha256(run/'vitis.log')
        report['harness_sha256']={str(p.relative_to(ROOT)):sha256(p) for p in
            (ROOT/'hls/testbench.cpp',ROOT/'hls/run_csim.tcl',Path(__file__),ROOT/'src/hls_csim.py')}
        if (build/'csim.exe').exists():report['csim_binary_sha256']=sha256(build/'csim.exe')
        try:
            verify_inventory(provenance['original_source_hashes'])
            report['originals_unchanged']=True
        except ValueError as exc:
            report.update(originals_unchanged=False,passed=False,status='FAIL',error=str(exc))
        report['elapsed_seconds']=time.monotonic()-start
        write_json(ROOT/'reports/hls_csim.json',report)
    print(json.dumps({'status':report['status'],'samples':len(rows),'report':str(ROOT/'reports/hls_csim.json')}))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
