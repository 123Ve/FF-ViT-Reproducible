#!/usr/bin/env python3
"""Create a writable, relocated build/training workspace from the frozen archive.

Never edits the archived snapshot. All rewritten path-only files are recorded.
Datasets remain external and are optionally linked into this ignored workspace.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
POWER=Path('ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler')


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--plantvillage-root',type=Path,help='directory containing splits/train,val,test and optional color/')
    p.add_argument('--nwpu-root',type=Path,help='original 45-class image directory')
    p.add_argument('--imagenet-train',type=Path)
    p.add_argument('--imagenet-val',type=Path)
    p.add_argument('--python',type=Path,help='training interpreter for historical shell recipes')
    args=p.parse_args();out=args.output.expanduser().resolve()
    if out.exists():raise SystemExit('Output must not exist; existing workspaces are never replaced')
    if out==ROOT or out in ROOT.parents or out.is_relative_to(ROOT/'ff_vit_re') or out.is_relative_to(ROOT/'FF_Vit'):
        raise SystemExit('Select a fresh work/ directory, outside frozen source trees')
    from verify_repository import verify
    verify(ROOT)
    out.mkdir(parents=True)
    for name in ('ff_vit_re','FF_Vit'):shutil.copytree(ROOT/name,out/name)
    replacements={b'/home/user/Desktop/ff_vit_re':str(out/'ff_vit_re').encode(),
                  b'/home/user/Desktop/FF_Vit':str(out/'FF_Vit').encode()}
    if args.python:
        py=args.python.expanduser().resolve()
        if not py.is_file():raise SystemExit('Training Python does not exist')
        replacements[b'/home/user/anaconda3/envs/vlm_token/bin/python']=str(py).encode()
    # Only path-bearing executable/configuration files are changed, not numerical
    # arrays, checkpoints, reference binaries or original evidence reports.
    changes=[]
    suffixes={'.py','.cfg','.tcl','.bif','.yaml','.yml','.sh','.json','.jsonl'}
    for tree in ('ff_vit_re','FF_Vit'):
        for path in (out/tree).rglob('*'):
            if not path.is_file() or path.suffix not in suffixes:continue
            if path.is_relative_to(out/POWER):continue
            old=path.read_bytes();new=old
            for source,target in replacements.items():new=new.replace(source,target)
            if new!=old:
                path.write_bytes(new)
                changes.append(dict(path=path.relative_to(out).as_posix(),
                    original_sha256=digest(old),workspace_sha256=digest(new),change='absolute path relocation only'))
    # Mount points preserve historical dataset contracts without copying images.
    mounts=[(args.plantvillage_root,Path('ff_vit_re/quantization_final/datasets/PlantVillage')),
            (args.nwpu_root,Path('ff_vit_re/archive/Dataset')),
            (args.imagenet_train,Path('ff_vit_re/image_train/ILSVRC2012_img_train')),
            (args.imagenet_val,Path('ff_vit_re/imagenet_val'))]
    for source,rel in mounts:
        if source:
            source=source.expanduser().resolve()
            if not source.is_dir():raise SystemExit(f'External dataset directory missing: {source}')
            target=out/rel;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise SystemExit(f'Dataset mount already occupied: {target}')
            target.symlink_to(source,target_is_directory=True)
    # Unpack the exact E07 IP instead of keeping thousands of generated files in Git.
    import zipfile
    ip=out/'FF_Vit/E04_weight_schedule/E07_timing_300mhz/hls/work/hls/impl/ip'
    with zipfile.ZipFile(ROOT/'artifacts/ip/e07_vit_block_top_1_0.zip') as z:z.extractall(ip)
    if not (ip/'component.xml').exists():raise RuntimeError('IP archive does not expose component.xml')
    service=out/'ff_vit_re/Cloud_test/e07/build/e06_net_workspace/e06_net_platform/export/e06_net_platform/sw/standalone_psu_cortexa53_0'
    shutil.copytree(ROOT/'artifacts/bsp/service_a53_0',service)
    sampler=out/POWER/'build/platform_workspace/sampler_platform'
    shutil.copytree(ROOT/'artifacts/bsp/sampler_a53_1',sampler/'export/sampler_platform/sw/sampler_a53_1')
    shutil.copytree(ROOT/'artifacts/bsp/sampler_sources',sampler/'psu_cortexa53_1/sampler_a53_1/bsp',dirs_exist_ok=True)
    report=dict(schema=1,workspace=str(out),changes=changes,
        policy='Path relocation only; no arithmetic/weight/BIT/BOOT modification. New builds have new identities.',
        dataset_mounts={str(rel):str(source.resolve()) for source,rel in mounts if source},
        physical_test='NOT_RUN')
    (out/'WORKSPACE.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(workspace=str(out),path_files_relocated=len(changes),physical_test='NOT_RUN')))


if __name__=='__main__':main()
