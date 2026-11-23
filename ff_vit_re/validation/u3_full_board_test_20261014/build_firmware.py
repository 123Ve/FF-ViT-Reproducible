"""Compile accuracy firmware only; this does not publish BOOT.BIN."""
import argparse
import json
import shutil
import subprocess
import zlib
from pathlib import Path
from prepare import HERE, digest, save_json

BOARD=Path('/home/user/Desktop/FF_Vit/E04_weight_schedule/E07_timing_300mhz/board_300mhz')
BSP=BOARD/'workspace/e07_platform/export/e07_platform/sw/standalone_psu_cortexa53_0'
TOOL=Path('/opt/vivado/2025.1/Vitis/gnu/aarch64/lin/aarch64-none/bin')

def expected_config(out):
    name=out.name
    data=json.loads((out/'dataset.json').read_text())
    hw=out/'hardware'
    first=hw/'fixtures/frame_00000'
    return {
        'DATASET_NAME':json.dumps(name),'DATASET_FRAMES':str(data['count'])+'u',
        'DATASET_CLASSES':str(data['classes'])+'u',
        'CHECKPOINT_SHA256':json.dumps(data['checkpoint_sha256']),
        'FIXED_ROM_SHA256':json.dumps(digest(hw/'src/fixed_patch_head_rom.h')),
        'WEIGHTS_CRC':hex(zlib.crc32((out/'data/weights.bin').read_bytes()))+'u',
        'HEADER_CRC':hex(zlib.crc32((out/'data/INDEX.BIN').read_bytes()[8:40]))+'u',
        'INDEX_CRC':hex(zlib.crc32((out/'data/INDEX.BIN').read_bytes()))+'u',
        'WARMUP_INPUT_CRC':hex(zlib.crc32((first/'input_dma.bin').read_bytes()))+'u',
        'WARMUP_GOLDEN_CRC':hex(zlib.crc32((first/'expected.bin').read_bytes()))+'u'}

def main(name):
    out=HERE/'outputs'/name
    build=out/'firmware';build.mkdir(exist_ok=False)
    for p in (HERE/'firmware').iterdir(): shutil.copy2(p,build/p.name)
    shutil.copy2(BOARD/'src/weight_layout.h',build/'weight_layout.h')
    shutil.copy2(BOARD/'workspace/e07_inference/src/lscript.ld',build/'lscript.ld')
    config=expected_config(out)
    (build/'dataset_config.h').write_text('/* Generated from verified full-split artifact. */\n'+
        ''.join(f'#define {k} {v}\n' for k,v in config.items()))
    flags=['-DSDT',f'-specs={BSP/"Xilinx.spec"}',f'-I{BSP/"include"}',f'-I{build}',
        '-std=gnu11','-Wall','-Wextra','-Werror','-O0','-g3','-fstack-usage','-U__clang__']
    gcc=str(TOOL/'aarch64-none-elf-gcc')
    elf=build/'u3_accuracy.elf'
    commands=[
        [gcc,*flags,'-c',str(build/'main.c'),'-o',str(build/'main.o')],
        [gcc,*flags,str(build/'main.o'),'-o',str(elf),'-Wl,--defsym,_STACK_SIZE=0x10000',f'-Wl,-T,{build/"lscript.ld"}',
         f'-L{BSP/"lib"}',f'-Wl,-Map,{build/"u3_accuracy.map"}','-Wl,--start-group',
         '-lxilstandalone','-lxiltimer','-lxilffs','-lxil','-lgcc','-lc','-Wl,--end-group'],
        [str(TOOL/'aarch64-none-elf-size'),str(elf)]]
    save_json(build/'commands.json',commands)
    with (build/'build.log').open('x') as log:
        for command in commands: subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    save_json(build/'identity.json',dict(dataset=name,status='COMPILED_NOT_DEPLOYED_NOT_BOARD_MEASURED',
        config=config,compiler=gcc,elf_sha256=digest(elf),
        sources={p.name:digest(p) for p in build.iterdir() if p.suffix in ('.c','.h','.ld')},
        bsp_libraries={str(p):digest(p) for p in sorted((BSP/'lib').glob('*.a'))},
        bsp_headers={str(p):digest(p) for p in sorted((BSP/'include').glob('*.h'))},
        xparameters_sha256=digest(BSP/'include/xparameters.h'),
        el3_stack_bytes=65536,
        board_abi_sha256=digest(BOARD/'src/weight_layout.h')))
    print(json.dumps(dict(dataset=name,firmware=str(elf),status='compiled; new PL qualification pending')),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=['plantvillage','nwpu'],required=True)
    main(p.parse_args().dataset)
