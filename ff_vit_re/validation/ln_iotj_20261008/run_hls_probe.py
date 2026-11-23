"""Supplementary HOST_HLS_C_MODEL, explicitly not official Vitis csim."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import numpy as np
from capture_ln import HERE, checked_output, setup_environment, sha256
from run_validation import write_json

HLS=Path('/home/user/Desktop/FF_Vit/E04_weight_schedule/E07_timing_300mhz/src')
AP=Path('/opt/vivado/2025.1/Vitis/include')


def compile_probe():
    setup_environment()
    build=HERE/'hls_host'; build.mkdir(exist_ok=True)
    executable=build/'hls_ln_probe'
    source=HERE/'hls_ln_probe.cpp'
    command=['g++','-std=c++17','-O2','-fwrapv','-Wno-unknown-pragmas',
             '-I'+str(AP),'-I'+str(HLS),str(source),'-o',str(executable)]
    binding={str(p):sha256(p) for p in [source,HLS/'layernorm.h',HLS/'common.h',HLS/'utils.h',HLS/'adapter.h']}
    stamp=build/'compile.json'
    try: cached=json.loads(stamp.read_text())
    except (OSError,ValueError): cached={}
    if (executable.exists() and cached.get('returncode')==0 and cached.get('source_hashes')==binding
            and cached.get('command')==command and cached.get('binary_sha256')==sha256(executable)):
        return executable
    fd,pending_name=tempfile.mkstemp(prefix='hls_ln_probe-',dir=build)
    os.close(fd); pending=Path(pending_name)
    try:
        actual_command=command[:-1]+[str(pending)]
        result=subprocess.run(actual_command,cwd=build,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (build/'compile.log').write_text(result.stdout)
        if result.returncode:
            write_json(build/'compile_failed.json',dict(command=actual_command,returncode=result.returncode,source_hashes=binding))
            raise RuntimeError('HLS host compilation failed: '+str(build/'compile.log'))
        pending.replace(executable)
        write_json(stamp,dict(command=command,compilation_command=actual_command,returncode=0,
            source_hashes=binding,binary_sha256=sha256(executable),
            compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
            assumption='-fwrapv defines native signed overflow as two-complement wrapping for this supplementary host check'))
    finally:
        pending.unlink(missing_ok=True)
    return executable


def run_case(x, params, bits, expected, output, executable=None):
    output=checked_output(output); output.mkdir(parents=True,exist_ok=True)
    x=np.asarray(x); expected=np.asarray(expected)
    if x.shape!=(4,192) or expected.shape!=x.shape: raise ValueError('host fixtures require four tokens')
    executable=compile_probe() if executable is None else executable
    values=[bits]+[int(v) for key in ('scalars','lnw','lnb','rsqrt_table') for v in np.asarray(params[key]).flat]+x.ravel().tolist()
    source=output/'input.txt'; target=output/'output.txt'
    source.write_text('\n'.join(map(str,values))+'\n')
    result=subprocess.run([str(executable),str(source),str(target)],cwd=output,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (output/'run.log').write_text(result.stdout)
    if result.returncode: raise RuntimeError('HLS host run failed')
    actual=np.loadtxt(target,dtype=np.int64).reshape(4,192)
    mismatch=int(np.count_nonzero(actual!=expected))
    if mismatch: np.savez_compressed(output/'mismatch.npz',x=x,expected=expected,actual=actual,**params)
    return dict(method='HOST_HLS_C_MODEL',status='FAIL' if mismatch else 'PASS',mismatch_codes=mismatch,
                compared_codes=int(x.size),tokens=4,input_bits=bits,source_header_sha256=sha256(HLS/'layernorm.h'),
                input_sha256=sha256(source),output_sha256=sha256(target),command=[str(executable),str(source),str(target)])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True,help='dataset output directory with fixtures/')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(); source=args.input.resolve()
    out=checked_output(args.output or source/'hls_host'); out.mkdir(parents=True,exist_ok=True)
    executable=compile_probe(); rows=[]
    fixtures=sorted((source/'fixtures').glob('*.npz'))
    if len(fixtures)!=72: raise ValueError(f'expected 24 sampled + 48 synthetic fixtures; got {len(fixtures)}')
    for fixture in fixtures:
        with np.load(fixture,allow_pickle=False) as f:
            params={k:f[k] for k in ('scalars','lnw','lnb','rsqrt_table')}
            row=run_case(f['x'],params,int(f['bits']),f['e07'],out/fixture.stem,executable)
            row.update(fixture=str(fixture),fixture_sha256=sha256(fixture),scope='SAMPLED_FIRST_FOUR_TOKENS' if 'actual' in f else 'SYNTHETIC')
            if 'actual' in f:
                output=np.loadtxt(out/fixture.stem/'output.txt',dtype=np.int64).reshape(4,192)
                row['actual_runtime_mismatch_codes']=int(np.count_nonzero(output!=f['actual']))
                row['actual_runtime_equivalence']='FAIL' if row['actual_runtime_mismatch_codes'] else 'PASS'
                row['host_vs_core_status']=row['status']
                if row['actual_runtime_mismatch_codes']: row['status']='FAIL'
            rows.append(row)
    status='FAIL' if any(r['status']=='FAIL' for r in rows) else 'PASS'
    report=dict(method='HOST_HLS_C_MODEL',status=status,fixtures=len(rows),compared_codes=sum(r['compared_codes'] for r in rows),results=rows,
                original_header_unchanged=True,template='T=4,TP=2,C=192,CP=1; full ping/pong and drain; reduced token count',
                VITIS_CSIM={'status':'NOT_MEASURED','reason':'No existing isolated official csim project for this parameter-only LN harness was executed; unchanged AP-header host execution supplements but does not replace Vitis csim'},
                RTL_COSIM='NOT_MEASURED',FPGA='NOT_MEASURED')
    write_json(out/'report.json',report); print(json.dumps({k:v for k,v in report.items() if k!='results'}))
    raise SystemExit(0 if status=='PASS' else 2)


if __name__=='__main__': main()
