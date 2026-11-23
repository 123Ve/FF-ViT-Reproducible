"""Isolated C-sim and new strict-E07 ROM synthesis/SoC implementation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from prepare import HERE, ROOT, digest, save_json

VIVADO='/opt/vivado/2025.1/Vivado/bin/vivado'
VITIS='/opt/vivado/2025.1/Vitis/bin'

def run(command, root, tag, cwd=None, env=None):
    if shutil.disk_usage(root).free < 10*1024**3:
        raise RuntimeError('less than 10 GiB free')
    if (root/(tag+'.console.log')).exists():
        tag += '_'+str(time.time_ns())
    print(f'{root.parent.name}: {tag} START',flush=True)
    started=time.time()
    with (root/(tag+'.console.log')).open('x') as log:
        result=subprocess.run(list(map(str,command)),cwd=cwd or root,env=env,stdout=log,stderr=subprocess.STDOUT)
    save_json(root/(tag+'_exit.json'),dict(command=list(map(str,command)),exit_code=result.returncode,
        elapsed_seconds=time.time()-started,log_sha256=digest(root/(tag+'.console.log'))))
    print(f'{root.parent.name}: {tag} EXIT {result.returncode}',flush=True)
    if result.returncode: raise RuntimeError(f'{tag} failed; preserved log: {root}')
    return root/(tag+'.console.log')

def main(name, stage):
    out=HERE/'outputs'/name; root=out/'hardware'
    data=json.loads((out/'dataset.json').read_text())
    if data['status']!='FULL_DATA_AND_GOLDEN_READY_NOT_BOARD_MEASURED': raise ValueError('data incomplete')
    identity=json.loads((root/'source_identity.json').read_text())
    for filename,h in identity['source_files'].items():
        if digest(root/'src'/filename)!=h: raise ValueError('hardware source changed')
    if stage=='csim':
        dependency=Path('/home/user/Desktop/FF_Vit/E04_weight_schedule/tests/multi_call.inc')
        (out/'tests').mkdir(exist_ok=True)
        shutil.copy2(dependency,out/'tests/multi_call.inc')
        save_json(root/'csim_dependency.json',dict(path=str(dependency),sha256=digest(dependency),
            copy_sha256=digest(out/'tests/multi_call.inc'),scope='unused renamed embedded test main; no arithmetic changes'))
        shutil.copy2(HERE/'testbench.cpp',root/'testbench.cpp')
        first=root/'fixtures'/f"frame_{data['csim_fixture_indices'][0]:05d}"
        run([VITIS+'/vitis-run','--mode','hls','--tcl',HERE/'csim.tcl'],root,'csim_compile_env',
            env=dict(os.environ,U3_BOARD_HARDWARE=str(root),U3_BOARD_FIXTURE=str(first)))
        executable=root/'csim/project/solution1/csim/build/csim.exe'
        if not executable.exists(): raise ValueError('C-sim executable missing')
        for idx in data['csim_fixture_indices']:
            fixture=root/'fixtures'/f'frame_{idx:05d}'
            log_path=run([executable],root,f'csim_frame_{idx:05d}',cwd=fixture)
            log=log_path.read_text()
            if log.count('LOGIT_MISMATCHES=0')!=2 or 'U3_CSIM_BIT_EXACT_PASS' not in log:
                raise ValueError('C-sim did not validate both calls')
            for fn in ('csim_logits.bin','csim_repeat_logits.bin'):
                if (fixture/fn).read_bytes()!=(fixture/'expected.bin').read_bytes():
                    raise ValueError('C-sim output bytes differ')
        save_json(root/'csim_verified.json',dict(pass_=True,fixture_indices=data['csim_fixture_indices'],
            frames_per_fixture=2,logit_codes_per_call=1000,executable_sha256=digest(executable),
            scope='C simulation only; not RTL cosimulation or board measurement',source_identity=identity))
    elif stage=='synthesis':
        # Synthesis can overlap the remaining C-sim fixtures. Publication still
        # requires the complete fixture gate in qualify.py, never this preflight.
        evidence=sorted(root.glob('csim_compile_env*.console.log'),key=lambda p:p.stat().st_mtime)
        log=evidence[-1].read_text() if evidence else ''
        if log.count('LOGIT_MISMATCHES=0')!=2 or 'U3_CSIM_BIT_EXACT_PASS' not in log:
            raise ValueError('initial two-call C-sim preflight failed')
        save_json(root/'synthesis_preflight.json',dict(first_fixture_two_call_pass=True,
            log_sha256=digest(evidence[-1]),full_csim_required_before_publication=True))
        (root/'hls').mkdir()
        cfg='part=xczu9eg-ffvb1156-2-e\n[hls]\nflow_target=vivado\nclock=3ns\nsyn.top=vit_block_top\nsyn.file=../src/block0.cpp\npackage.output.format=ip_catalog\npackage.output.syn=false\n'
        (root/'hls/hls_config.cfg').write_text(cfg)
        run([VITIS+'/v++','--compile','--mode','hls','--config','hls_config.cfg','--work_dir','work'],root,'hls_synthesis',cwd=root/'hls')
        run([VIVADO,'-mode','batch','-notrace','-source',HERE/'package.tcl','-log',root/'package.log',
            '-journal',root/'package.jou','-tclargs',root],root,'package')
    elif stage=='route':
        base=ROOT/'validation/e07_w3_s8_resource_20261009/baseline'
        (root/'scripts').mkdir()
        shutil.copytree(base/'seed',root/'seed')
        shutil.copy2(base/'scripts/prepare_candidate04.tcl',root/'scripts/prepare_candidate04.tcl')
        run([VIVADO,'-mode','batch','-notrace','-source',root/'scripts/prepare_candidate04.tcl',
             '-log',root/'prepare.log','-journal',root/'prepare.jou'],root,'prepare',env=dict(os.environ,E07_CANDIDATE='candidate05'))
        run([VIVADO,'-mode','batch','-notrace','-source',HERE/'route.tcl','-log',root/'route.log',
             '-journal',root/'route.jou','-tclargs',root],root,'route')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=['plantvillage','nwpu'],required=True)
    p.add_argument('--stage',choices=['csim','synthesis','route'],required=True)
    a=p.parse_args();main(a.dataset,a.stage)
