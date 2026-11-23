"""Publish complete SD package only after PL/C-sim/data/PS identity gates."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from board_contract import validate_release
from build_firmware import BOARD, BSP, TOOL, expected_config
from prepare import HERE, digest, save_json
from qualify import qualify, timing_values, route_values

def platform_identity(hw):
    old=BOARD/'workspace/e07_platform/export/e07_platform/hw/e07_300mhz_wrapper.xsa'
    new=hw/'release/u3_platform.xsa'
    with zipfile.ZipFile(old) as original,zipfile.ZipFile(new) as current:
        ps_files={}
        for name in ('psu_init.c','psu_init.h','psu_init.tcl'):
            a,b=original.read(name),current.read(name)
            if a!=b: raise ValueError('PS initialization changed; original FSBL may not be reused: '+name)
            ps_files[name]=hashlib.sha256(b).hexdigest()
        old_hwh=ET.fromstring(original.read('design_1.hwh'))
        new_hwh=ET.fromstring(current.read('design_1.hwh'))
        # Bind all processor-visible address segments, not just the two bases.
        def ranges(root):
            return sorted(tuple(sorted(e.attrib.items())) for e in root.iter('MEMRANGE'))
        if not ranges(old_hwh) or ranges(old_hwh)!=ranges(new_hwh):
            raise ValueError('processor-visible address map differs from BSP')
        # AXI-Lite software register offsets must be byte-identical.
        driver='drivers/vit_block_top_v1_0/src/xvit_block_top_hw.h'
        if original.read(driver)!=current.read(driver): raise ValueError('HLS control ABI changed')
        if (BSP/'include/xvit_block_top_hw.h').read_bytes()!=original.read(driver):
            raise ValueError('compiled BSP HLS control ABI differs from original platform')
    return dict(original_xsa=str(old),original_xsa_sha256=digest(old),new_xsa_sha256=digest(new),
        ps_initialization_sha256=ps_files,address_map_equal=True,hls_control_register_header_equal=True)

def verify_firmware_config(out,record):
    if record['dataset']!=out.name or record['config']!=expected_config(out):
        raise ValueError('ELF dataset/checkpoint/weights/index/warmup/ROM configuration differs')

def verify_bsp_binding(record):
    for path,h in record['bsp_libraries'].items():
        if digest(path)!=h: raise ValueError('linked BSP library changed')
    for path,h in record['bsp_headers'].items():
        if digest(path)!=h: raise ValueError('compiled BSP header changed')
    if digest(BSP/'include/xparameters.h')!=record['xparameters_sha256']:
        raise ValueError('BSP hardware parameters changed')
    if digest(BOARD/'src/weight_layout.h')!=record['board_abi_sha256']:
        raise ValueError('board weight ABI changed')

def main(name):
    out=HERE/'outputs'/name;hw=out/'hardware';sd=out/'SD_CARD'
    record=qualify(name);validate_release(record)
    release=hw/'release'
    final=timing_values((release/'timing_final.rpt').read_text())
    final.update(route_values((release/'route_final.rpt').read_text()))
    drc=(release/'drc_final.rpt').read_text()
    if 'Report DRC' not in drc or re.search(r'\|\s*(Error|Critical Warning)\s*\|',drc): raise ValueError('post-BIT DRC failed')
    platform=platform_identity(hw)
    # The native XSA must contain exactly the bitstream being packaged.
    with zipfile.ZipFile(release/'u3_platform.xsa') as xsa:
        bits=[n for n in xsa.namelist() if n.endswith('.bit')]
        if len(bits)!=1 or xsa.read(bits[0])!=(release/'design_1_wrapper.bit').read_bytes():
            raise ValueError('XSA and BIT differ')
    source_identity=json.loads((hw/'source_identity.json').read_text())
    firmware_identity=json.loads((out/'firmware/identity.json').read_text())
    verify_firmware_config(out,firmware_identity)
    verify_bsp_binding(firmware_identity)
    for filename,h in firmware_identity['sources'].items():
        if digest(out/'firmware'/filename)!=h: raise ValueError('firmware source changed after compilation')
    if digest(out/'firmware/u3_accuracy.elf')!=firmware_identity['elf_sha256']: raise ValueError('ELF identity differs')
    raw=subprocess.check_output([str(TOOL/'aarch64-none-elf-nm'),'-n',str(out/'firmware/u3_accuracy.elf')],text=True)
    symbols={p[2]:int(p[0],16) for line in raw.splitlines() if len(p:=line.split())==3}
    if symbols['__el3_stack']-symbols['_el3_stack_end']<65536:
        raise ValueError('ELF actual stack allocation lacks the required FatFS/summary margin')
    if firmware_identity['config']['FIXED_ROM_SHA256']!=json.dumps(digest(hw/'src/fixed_patch_head_rom.h')):
        raise ValueError('ELF and fixed ROM differ')
    expected=json.loads((HERE.parent/'local4_timing_closure_20261010/firmware_identity.json').read_text())
    if platform['ps_initialization_sha256']['psu_init.c']!=expected['psu_init_sha256']:
        raise ValueError('PS initialization is not the source binding of reused FSBL')
    firmware={}
    for name_ in ('fsbl.elf','pmufw.elf'):
        path=Path(expected['binaries'][name_]['source'])
        if digest(path)!=expected['binaries'][name_]['sha256']: raise ValueError('boot firmware identity differs')
        firmware[name_]=path
    sd.mkdir(exist_ok=False)
    for p in (out/'data').iterdir(): shutil.copy2(p,sd/p.name)
    shutil.copy2(out/'dataset.json',sd/'dataset.json')
    shutil.copy2(release/'design_1_wrapper.bit',sd/'design_1_wrapper.bit')
    shutil.copy2(out/'firmware/u3_accuracy.elf',sd/'u3_accuracy.elf')
    for name_,p in firmware.items(): shutil.copy2(p,sd/name_)
    for name_ in ('summarize_board.py','board_contract.py'): shutil.copy2(HERE/name_,sd/name_)
    first=hw/'fixtures/frame_00000'
    shutil.copy2(first/'input_dma.bin',sd/'WARMUP.I')
    shutil.copy2(first/'expected.bin',sd/'WARMUP.G')
    shutil.copy2(hw/'results/candidate05/clock.txt',sd/'clock.txt')
    for name_ in ('qualification.json','source_identity.json'): shutil.copy2(out/name_,sd/name_)
    shutil.copy2(HERE/'SD_README_CN.txt',sd/'README_CN.txt')
    (sd/'boot.bif').write_text('the_ROM_image:\n{\n'
        ' [bootloader, destination_cpu=a53-0] fsbl.elf\n'
        ' [pmufw_image] pmufw.elf\n'
        ' [destination_device=pl] design_1_wrapper.bit\n'
        ' [destination_cpu=a53-0, exception_level=el-3] u3_accuracy.elf\n}\n')
    command=['/opt/vivado/2025.1/Vivado/bin/bootgen','-arch','zynqmp','-image','boot.bif','-o','BOOT.BIN']
    with (sd/'bootgen.log').open('x') as log: subprocess.run(command,cwd=sd,check=True,stdout=log,stderr=subprocess.STDOUT)
    identity=dict(status='READY_FOR_FULL_BOARD_TEST_NOT_BOARD_MEASURED',dataset=name,
        fixed_rom_sha256=digest(hw/'src/fixed_patch_head_rom.h'),hardware_source_identity=source_identity,
        software_accuracy_is_not_board_accuracy=True,rtl_cosimulation_measured=False,
        qualification=record,post_bit_timing=final,platform_identity=platform,firmware_identity=firmware_identity,
        boot_command=command,files={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sd.iterdir() if p.is_file()})
    save_json(sd/'identity.json',identity)
    for filename,v in identity['files'].items():
        if digest(sd/filename)!=v['sha256']: raise ValueError('published file hash changed')
    archive=HERE/(name+'_U3_FULL_SD_CARD.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for p in sorted(sd.iterdir()): z.write(p,arcname=p.name)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('ZIP verification failed')
    save_json(out/'published.json',dict(status=identity['status'],dataset=name,sd_card=str(sd),
        archive=str(archive),archive_sha256=digest(archive),boot_sha256=digest(sd/'BOOT.BIN')))
    print(json.dumps(dict(dataset=name,sd_card=str(sd),archive=str(archive),status=identity['status'])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=['plantvillage','nwpu'],required=True)
    main(p.parse_args().dataset)
