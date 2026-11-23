#!/usr/bin/env python3
"""Curate the two original trees without changing them; no dataset payloads.

Run only into an empty destination (or this newly created repository skeleton).
Every copied file is recorded with its original path, size and SHA-256.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile

SKIP = {'.git', '__pycache__', '.pytest_cache', '.ruff_cache', '.Xil', '.idea',
        '.superpowers', 'node_modules', '.venv', 'datasets', 'dataset'}
SOURCE_SUFFIX = {'.py', '.h', '.hpp', '.c', '.cpp', '.S', '.ld', '.tcl', '.cfg',
                 '.xdc', '.bd', '.json', '.yaml', '.yml', '.md', '.txt', '.ps1',
                 '.bat', '.spec', '.html', '.css', '.js', '.csv', '.sh', '.cmake'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, default=Path('/home/user/Desktop/ff_vit_re'))
    parser.add_argument('--hardware', type=Path, default=Path('/home/user/Desktop/FF_Vit'))
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    research, hardware, output = args.research.resolve(), args.hardware.resolve(), args.output.resolve()
    if output == research or output == hardware or output.is_relative_to(research) or output.is_relative_to(hardware):
        raise SystemExit('Select a new output outside both original trees')
    if (output / 'provenance/COPIED_FILES.csv').exists():
        raise SystemExit('Snapshot already assembled; choose a fresh output')
    records, exclusions = {}, []

    def copy(source, dest=None, *, reason='selected source/artifact'):
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        if dest is None:
            if source.is_relative_to(research): dest = Path('ff_vit_re') / source.relative_to(research)
            elif source.is_relative_to(hardware): dest = Path('FF_Vit') / source.relative_to(hardware)
            else: raise ValueError(source)
        dest = Path(dest)
        target = output / dest
        digest = sha(source)
        if target.exists():
            if sha(target) != digest:
                raise RuntimeError(f'Conflicting canonical sources for {dest}')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        records[dest.as_posix()] = dict(path=dest.as_posix(), original_path=str(source),
            bytes=source.stat().st_size, sha256=digest, reason=reason)

    def tree(source, dest=None, *, allow=None, deny=(), reason='selected source/artifact'):
        source = Path(source)
        if not source.is_dir(): raise FileNotFoundError(source)
        for current, dirs, names in os.walk(source, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP and d not in deny and not d.startswith('.venv'))
            for name in sorted(names):
                p = Path(current) / name
                if p.is_symlink():
                    exclusions.append(dict(path=str(p), reason='symlink, not a portable payload'))
                    continue
                if allow is None or allow(p):
                    copy(p, Path(dest)/p.relative_to(source) if dest else None, reason=reason)

    # A previously audited import closure, rather than every experimental branch.
    bundle = research/'validation/quantization_code_bundle_20261022/s3_only/FFViT_Strict_S3_Code_20261022'
    tree(bundle/'ff_vit_re', 'ff_vit_re', reason='20261022 strict S3/U3 Python dependency closure')
    tree(bundle/'external_sources/FF_Vit', 'FF_Vit', reason='Python snapshot HLS reference closure')
    for p in bundle.iterdir():
        if p.is_file(): copy(p, Path('provenance/python_snapshot')/p.name, reason='original source-package audit')

    # Final trained states and deployment arrays; never copy images or every epoch.
    quant = research/'quantization_final'
    for folder in ('artifacts', 'reports'):
        tree(quant/folder, allow=lambda p: p.suffix in {'.npy','.npz','.json','.csv'},
             deny=('before',), reason='PlantVillage initialization / exact integer parameters')
    tree(quant/'deployment', allow=lambda p: p.parent == quant/'deployment' and p.suffix in {'.bin','.h','.cpp','.json'},
         deny=tuple(p.name for p in (quant/'deployment').iterdir() if p.is_dir()))
    for rel in ('checkpoints/deit_tiny_imagenet_timm.pth','checkpoints/plantvillage_deit_tiny/best.pth',
                'checkpoints/plantvillage_hls196/best.pth','checkpoints/qat_weight3_hls196/best_qat_state.pth'):
        copy(quant/rel, reason='frozen pretrained/FP32/W3 parent checkpoint')
    # Category order is metadata, not image data.
    for p in (quant/'datasets/PlantVillage').glob('*.json'):
        copy(p, Path('metadata/plantvillage')/p.name, reason='class IDs only, no dataset images')
    nwpu = research/'archive/nwpu_resisc45_ffvit'
    run = nwpu/'runs/nwpu_seed20260923'
    for folder in run.iterdir():
        if folder.is_dir():
            tree(folder, allow=lambda p: 'training_state' not in p.parts and (p.suffix in {'.npy','.npz','.json','.csv'} or p.name in {'best.pth','best_qat_state.pth','best_mlp_qat.pth','best_attention_qat.pth'}),
                 reason='NWPU parent checkpoints and integer initialization arrays')
    tree(nwpu/'deployment', allow=lambda p: p.suffix in {'.bin','.h','.json'}, reason='NWPU ABI / patch and head ROM')
    progressive = research/'validation/e07_u3_progressive_qat_20261010'
    for ds in ('plantvillage','nwpu'):
        task = progressive/'outputs'/ds
        for stage in ('mlp','attention'):
            for name in ('best.pth','recipe.json','fakequant_accuracy.json','events.jsonl'):
                copy(task/stage/name, reason='selected final U3 QAT lineage, not all epochs')
        tree(task/'final', reason='final U3 weights / arrays / accuracy and fitting reports')
        # Final arrays are authoritative; large calibration activation caches can be regenerated.
        tree(research/'validation/e07_u3_qat_20261010/outputs'/ds/'initial_u3/u3_artifact',
             reason='strict U3 initialization required by progressive QAT')
    original = research/'image1k_hls_s3_original'
    for stage in ('attention','mlp'):
        copy(original/'checkpoints'/stage/'main/best.pth', reason='ImageNet selected strict S3 checkpoint')
    tree(original/'exact/main', reason='ImageNet exact integer model, ABI and ROM')
    tree(original/'hls', allow=lambda p: 'build' not in p.relative_to(original/'hls').parts,
         deny=('build',), reason='ImageNet complete HLS sources and four small fixtures')
    for p in (research/'image_1k/deit_tiny_patch16_224-a1311bcf.pth',
              research/'image_lianghu/checkpoints/fp32_hls196.pth',
              research/'image_lianghu/checkpoints/w3_qat_500k_headrefit/best.pth'):
        copy(p, reason='ImageNet frozen pretrained / FP32 / W3 parent')
    copy(quant/'checkpoints/stage4j_attention_qat/best_attention_qat.pth',
         reason='historical controller parent required by U3 runtime initialization')

    e07 = hardware/'E04_weight_schedule/E07_timing_300mhz'
    for folder in ('src','inputs','seed','scripts','tests'):
        tree(e07/folder, reason='E07 candidate05 HLS / Vivado build closure')
    copy(e07/'hls/hls_config.cfg')
    copy(e07/'hls/work/hls/impl/ip/xilinx_com_hls_vit_block_top_1_0.zip',
         'artifacts/ip/e07_vit_block_top_1_0.zip', reason='exact reusable E07 HLS IP; unpack before Vivado')
    for folder in ('candidate05/board_release','paper_evidence','paper_rtl_20261003_singleframe_fixed','power_csv_20261008'):
        tree(e07/'results'/folder, allow=lambda p:p.suffix in {'.json','.csv','.txt','.rpt','.log','.sha256'} or p.name in {'build.exit','clock.txt'},
             deny=('project',), reason='selected timing/RTL/board evidence; no new measurement')
    copy(e07/'results/candidate05/board_release/e07_300mhz_wrapper.xsa')
    for folder in ('src','power_src','scripts','tests','deploy','deploy_power'):
        tree(e07/'board_300mhz'/folder, reason='bare-metal Vitis sources and matching baseline images')
    for p in (e07/'board_300mhz').iterdir():
        if p.is_file() and p.suffix in SOURCE_SUFFIX: copy(p)
    tree(e07/'board_300mhz/ddr_measurement', allow=lambda p:p.suffix in SOURCE_SUFFIX or p.suffix in {'.elf','.bit','.BIN','.bin'},
         deny=('deploy','build'), reason='DDR measurement firmware sources')
    frozen_image=e07/'board_300mhz/imagenet_frozen_50k_test'
    for p in list(frozen_image.glob('*.py'))+list(frozen_image.glob('*.txt')):
        copy(p,reason='unchanged frozen E07 ImageNet accuracy-test program; not the separate strict-S3 model')
    tree(frozen_image/'src')
    for name in ('BOOT.BIN','boot.bif','identity.json','e07_image_accuracy.elf'):
        copy(frozen_image/'deploy'/name,reason='existing E07 ImageNet board-test image; bulk image shards omitted')
    # HLS reference CSV is named by the historical hls_config.cfg.
    for p in (hardware/'E04_weight_schedule/results').glob('e04_reference.csv'): copy(p)
    tree(hardware/'python_code', allow=lambda p:p.suffix in {'.py','.json','.md','.txt'},
         deny=('generated_bins','generated_bins_4HP','refs'), reason='original data preparation frontend')

    # Model-specific U3 builds are distinct from the canonical E07 network image.
    full = research/'validation/u3_full_board_test_20261014'
    tree(full, allow=lambda p:p.parent == full and p.suffix in SOURCE_SUFFIX,
         deny=tuple(p.name for p in full.iterdir() if p.is_dir()))
    for folder in ('firmware','tests'): tree(full/folder)
    for ds in ('plantvillage','nwpu'):
        task = full/'outputs'/ds
        for name in ('source_identity.json','dataset.json','build_status.json'):
            copy(task/name)
        for folder in ('src','seed','scripts','fixtures'):
            tree(task/'hardware'/folder, reason=f'{ds} task-specific HLS ROM/BD and small C-sim fixtures')
        for name in ('testbench.cpp','csim_verified.json','source_identity.json','hls/hls_config.cfg'):
            copy(task/'hardware'/name)
        tree(task/'firmware', allow=lambda p:p.suffix in SOURCE_SUFFIX or p.suffix in {'.elf','.map','.su'}, reason=f'{ds} Vitis accuracy-test firmware')
        tree(task/'hardware/results/candidate05', allow=lambda p:p.suffix in {'.rpt','.txt','.json'}, reason=f'{ds} original implementation qualification')
    tree(full/'outputs/nwpu/hardware/release', reason='NWPU U3 task-specific hardware')
    for name in ('BOOT.BIN','identity.json','source_identity.json','README_CN.txt'):
        copy(full/'outputs/nwpu/SD_CARD'/name,
             Path('artifacts/tasks/nwpu')/name, reason='NWPU original published image; bulk dataset BIN omitted')
    waived = research/'validation/plantvillage_timing_waived_board_test_20261014'
    for name in ('CURRENT_RESULT_CN.txt','README_CN.txt','USER_WAIVER.json','published_experimental.json','boot.bif','export_experimental.tcl','package_experimental.py'):
        copy(waived/name)
    tree(waived/'hardware/release', reason='PlantVillage task-specific hardware and original implementation reports')
    copy(waived/'SD_CARD/BOOT.BIN','artifacts/tasks/plantvillage/BOOT.BIN',reason='PlantVillage task-specific boot image')

    cloud = research/'Cloud_test'
    tree(cloud, allow=lambda p:p.suffix in SOURCE_SUFFIX or p.suffix in {'.png','.svg','.jpg','.ico'},
         deny=('build','dist','results','vendor','boot','checkpoints','e07'), reason='cloud-edge TCP + Flask GUI + Windows frontend')
    tree(cloud/'e07/firmware')
    tree(cloud/'e07/vendor')
    tree(cloud/'vendor', reason='E06 compatibility inputs imported by cloud frontend')
    for prefix in ('BOOT_E07_NET','BOOT_E07_NET_V2_2_FINAL','BOOT_E07_NET_V2_5_FINAL'):
        for p in (cloud/'e07/boot').glob(prefix+'.*'):copy(p)
    tree(cloud/'boot')
    for name in ('e07_v25_verification.json','e07_v25_regression.log','e07_v25_build_FINAL.log'):
        copy(cloud/'results'/name,Path('provenance/cloud_gui')/name)

    # Preserve the exact Windows payload so its inventory check stays meaningful.
    power = research/'validation/cloud_power_retest_20261121/independent_sampler'
    archive = power/'archives/E07_Independent_Power_ThermalCapture_20261122_r10.zip'
    dest = output/'ff_vit_re'/power.relative_to(research)
    with zipfile.ZipFile(archive) as z:
        if z.testzip(): raise RuntimeError('Corrupt power ZIP')
        for member in z.infolist():
            rel = Path(member.filename)
            if rel.is_absolute() or '..' in rel.parts:raise ValueError(member.filename)
            if member.is_dir():continue
            target=dest/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            data=z.read(member)
            if target.exists() and target.read_bytes()!=data:raise RuntimeError('Power payload collision')
            target.write_bytes(data)
            name=target.relative_to(output).as_posix()
            records[name]=dict(path=name,original_path=f'{archive}!{member.filename}',bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),reason='exact r10 Windows release payload, unchanged')
    # BSPs live outside the immutable Windows package; build workspace is generated.
    bsp=cloud/'e07/build/e06_net_workspace/e06_net_platform/export/e06_net_platform/sw/standalone_psu_cortexa53_0'
    tree(bsp,'artifacts/bsp/service_a53_0',reason='original Vitis2025.1 exported service BSP')
    sampler=power/'build/platform_workspace/sampler_platform'
    tree(sampler/'export/sampler_platform/sw/sampler_a53_1','artifacts/bsp/sampler_a53_1',reason='original A53-1 exported BSP')
    tree(sampler/'psu_cortexa53_1/sampler_a53_1/bsp','artifacts/bsp/sampler_sources',
         reason='original sampler startup/driver source and BSP configuration')

    for name in ('checkpoint_identities.csv','supplement_cn.tex','supplement_en.tex'):
        p=research/'validation/submission_reproducibility_20261013'/name
        if p.exists():copy(p,Path('provenance/model_lineage')/name)
    tasks={}
    for ds in ('plantvillage','nwpu','imagenet'):
        if ds=='imagenet':
            fixture=original/'hls/data/sample_000'
            files={'weights.bin':fixture/'weights.bin','input.bin':fixture/'input.bin',
                   'output.bin':fixture/'output.bin','fixed_patch_head_rom.h':original/'exact/main/fixed_patch_head_rom.h'}
            status='archived exact-integer model and HLS reference fixture'
        else:
            hw=full/'outputs'/ds/'hardware';fixture=hw/'fixtures/frame_00000'
            files={'weights.bin':fixture/'weights.bin','input.bin':fixture/'input_dma.bin',
                   'output.bin':fixture/'expected.bin','fixed_patch_head_rom.h':hw/'src/fixed_patch_head_rom.h'}
            status='archived task-specific model, HLS and boot artifacts'
        hashes={}
        for name,source in files.items():
            dest=Path('deploy')/ds/name
            copy(source,dest,reason='task deployment convenience entry, identical to archived canonical file')
            hashes[dest.as_posix()]=records[dest.as_posix()]['sha256']
        tasks[ds]=dict(scope='one S16 input + complete 1000-logit reference; not a full dataset',
            status=status,data_type='input int16 little-endian, output int32 containing signed S19 codes',
            weights_bytes=2772096,files=hashes,
            input_layout='logical [196,768], reordered by HLS testbench to DMA [98,768,2]' if ds=='imagenet' else 'DMA [98,768,2]')
    (output/'deploy/tasks.json').write_text(json.dumps(tasks,indent=2)+'\n')
    (output/'provenance').mkdir(exist_ok=True)
    with (output/'provenance/COPIED_FILES.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['path','original_path','bytes','sha256','reason'])
        writer.writeheader();writer.writerows(records[k] for k in sorted(records))
    summary=dict(schema=1,files=len(records),bytes=sum(v['bytes'] for v in records.values()),
        original_roots=[str(research),str(hardware)],datasets_included=False,bulk_dataset_bins_included=False,
        new_training=False,new_PL_build=False,new_board_test=False,
        excluded=['raw datasets and full test-set image tensors','temporary build workspaces',
                  'intermediate epochs / rejected model branches','old duplicate ZIP releases'],
        skipped_symlinks=exclusions)
    (output/'provenance/ASSEMBLY.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
