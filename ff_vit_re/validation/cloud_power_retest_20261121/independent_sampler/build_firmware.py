"""Build the isolated two-core candidate without regenerating PL or old BSPs.

Run Python 3 after build_platform.py has generated the A53-1 domain. Build
attempts are retained in distinct directories. Only this candidate SD_CARD is
updated, and each previous generated BOOT remains in its build attempt.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
VITIS=Path('/opt/vivado/2025.1/Vitis')
GCC=VITIS/'gnu/aarch64/lin/aarch64-none/bin/aarch64-none-elf-gcc'
BOOTGEN=VITIS/'bin/bootgen'
FROZEN={
    'bitstream':('design_1_wrapper.bit','2fedb6d70a0916fc9aebfdf3141008690685c0dbd1b5bab0ae58821564ef1037'),
    'xsa':('e07_300mhz_wrapper.xsa','b46ed4b26f11340c9eb9fed1a55822f4a30c7f81627287e9c556a0a5416a5df1'),
    'input':('input.bin','f7fa33c31113271173effc4fb684c432378b85c2f15a6681aa682aacf2ba3a2c'),
    'output':('output.bin','f2da31d910ab48a49c5a803f836478e2b54e0cd9fdd1081cc2eabc1d36afe842'),
    'weights':('weights.bin','0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7')}
REGIONS={'service':(0x100000,0x20000000),'sampler':(0x20000000,0x21000000),
         'shared':(0x30000000,0x34000000)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_segments(images):
    result={}
    for name in ('service','sampler'):
        segments=images[name]
        if not segments:raise ValueError('missing loadable segments: '+name)
        lower,upper=REGIONS[name]
        for begin,end in segments:
            if not lower<=begin<end<=upper:raise ValueError('ELF escapes '+name+' region')
        result[name]={'begin':min(b for b,e in segments),'end':max(e for b,e in segments),
                      'segments':segments,'allowed':REGIONS[name]}
    if result['service']['end']>result['sampler']['begin']:raise ValueError('overlapping ELFs')
    result['shared']={'begin':REGIONS['shared'][0],'end':REGIONS['shared'][1],
                      'attributes':'normal noncacheable inner-shareable XN; 2MiB blocks'}
    return result


def elf_segments(path):
    data=Path(path).read_bytes()
    if data[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',data,18)[0]!=183:
        raise ValueError('expected little endian AArch64 ELF')
    offset=struct.unpack_from('<Q',data,32)[0]
    entry_size,count=struct.unpack_from('<HH',data,54)
    result=[]
    for i in range(count):
        typ,flags,off,vaddr,paddr,filesz,memsz,align=struct.unpack_from('<IIQQQQQQ',data,offset+i*entry_size)
        if typ==1 and memsz:
            if vaddr!=paddr:raise ValueError('unexpected virtual/physical alias')
            result.append((paddr,paddr+memsz))
    return result


def main():
    if len(HERE.parents)<3:
        raise FileNotFoundError('Rebuild requires repository layout validation/cloud_power_retest_20261121/independent_sampler and documented frozen vendor/BSP inputs')
    ROOT=HERE.parents[2]
    VENDOR=ROOT/'Cloud_test/e07/vendor/e07_base'
    if not VENDOR.is_dir():
        raise FileNotFoundError('Rebuild requires repository layout with frozen inputs at '+str(VENDOR))
    from host import profiles
    parser=argparse.ArgumentParser(description=__doc__)
    selection=parser.add_mutually_exclusive_group()
    selection.add_argument('--diagnostic17',action='store_true')
    selection.add_argument('--diagnostic16',action='store_true')
    args=parser.parse_args()
    profile=profiles.DIAGNOSTIC16 if args.diagnostic16 else profiles.DIAGNOSTIC if args.diagnostic17 else profiles.STRICT
    policy=profiles.metadata(profile)
    identity_name,sums_name,sd_name=profiles.paths(profile)
    build=HERE/'build';build.mkdir(exist_ok=True)
    run_dir=Path(tempfile.mkdtemp(prefix='candidate_'+profile+'_',dir=build))
    commands=[]
    def run(command,log):
        commands.append([str(x) for x in command])
        result=subprocess.run(command,cwd=run_dir,text=True,capture_output=True)
        (run_dir/log).write_text(shlex.join(map(str,command))+'\n'+result.stdout+result.stderr)
        (run_dir/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        if result.returncode:raise RuntimeError(str(run_dir/log)+'\n'+result.stderr[-6000:])
        return result.stdout+result.stderr
    inputs={}
    for name,(filename,expected) in FROZEN.items():
        actual=sha(VENDOR/filename)
        if actual!=expected:raise ValueError('immutable input SHA mismatch: '+filename)
        inputs[name]=actual
    run([sys.executable,'-B',str(HERE/'tests/test_firmware.py')],'native_tests.log')
    bsp={
        'service':ROOT/'Cloud_test/e07/build/e06_net_workspace/e06_net_platform/export/e06_net_platform/sw/standalone_psu_cortexa53_0',
        'sampler':build/'platform_workspace/sampler_platform/export/sampler_platform/sw/sampler_a53_1'}
    for path in bsp.values():
        if not (path/'lib/libxilstandalone.a').exists():raise FileNotFoundError('Missing generated BSP '+str(path))
    sources={str(p.relative_to(HERE)):sha(p) for p in sorted((HERE/'firmware').rglob('*')) if p.is_file()}
    sources.update({p.name:sha(p) for p in (HERE/'build_firmware.py',HERE/'build_platform.py')})
    sources['host/profiles.py']=sha(HERE/'host/profiles.py')
    libraries={name:{p.name:sha(p) for p in sorted((path/'lib').glob('*.a'))} for name,path in bsp.items()}
    headers={name:{str(p.relative_to(path)):sha(p) for p in sorted((path/'include').rglob('*.h'))}
             for name,path in bsp.items()}
    for name,path in bsp.items():headers[name]['Xilinx.spec']=sha(path/'Xilinx.spec')
    payload={**policy,'schema':'e07-independent-build-v1','candidate':'E07_INDEPENDENT_POWER_V1',
        'sources':sources,'artifact_hashes':inputs,'bsp_libraries':libraries,'bsp_headers':headers,
        'compiler':str(GCC),'compiler_version':run([str(GCC),'--version'],'compiler_version.log').splitlines()[0],
        'options':['-DE07_PROFILE_RAILS='+str(policy['included_count']),'-include','firmware_build_identity.h','-DSDT','-DE07_BATCH_VERIFY=1','-O2','-g','-Wall','-Wextra','-Werror'],
        'sampler_bsp_cpu':'psu_cortexa53_1','sampler_USE_AMP':1,'regions':REGIONS,
        'fsbl_sha256':sha(VENDOR/'fsbl.elf'),'pmufw_sha256':sha(VENDOR/'pmufw.elf')}
    identity=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (run_dir/'firmware_build_identity.h').write_text('#define E06_FIRMWARE_SHA256 "'+identity+'"\n#define M_BUILD_ID E06_FIRMWARE_SHA256\n')
    elfs={}
    for core in ('service','sampler'):
        src=HERE/'firmware'/core
        common=[HERE/'firmware/common'/name for name in ('board.c','phase.c')]
        common+=[HERE/'firmware/common'/('fvit_protocol.c' if core=='service' else 'sensor.c')]
        flags=[*payload['options'],'-specs='+str(bsp[core]/'Xilinx.spec'),
               '-I'+str(bsp[core]/'include'),'-I'+str(src),
               '-I'+str(HERE/'firmware/common'),'-I'+str(run_dir)]
        if core=='sampler':flags.append('-DUSE_AMP=1')
        objects=[]
        for source in sorted(src.glob('*.c'))+common:
            obj=run_dir/(core+'_'+source.stem+'.o');objects.append(str(obj))
            run([str(GCC),*flags,'-c',str(source),'-o',str(obj)],core+'_'+source.stem+'.log')
        elf=run_dir/(core+'.elf');elfs[core]=elf
        libs=['-lxilstandalone','-lxiltimer']
        if core=='service':libs+=['-lxilffs','-llwip220']
        libs+=['-lxil','-lgcc','-lc','-lm']
        run([str(GCC),*flags,*objects,'-Wl,-T,'+str(src/'lscript.ld'),
             '-Wl,-Map,'+str(run_dir/(core+'.map')),'-L'+str(bsp[core]/'lib'),
             '-Wl,--start-group',*libs,'-Wl,--end-group','-o',str(elf)],core+'_link.log')
        if identity.encode() not in elf.read_bytes():raise ValueError('ELF missing candidate identity')
        run([str(GCC.parent/'aarch64-none-elf-objdump'),'-d',str(elf)],core+'_disassembly.txt')
    memory=validate_segments({name:elf_segments(path) for name,path in elfs.items()})
    (run_dir/'memory_map_check.json').write_text(json.dumps(memory,indent=2)+'\n')
    bif=run_dir/'independent.bif'
    bif.write_text('the_ROM_image:\n{\n  [bootloader] '+str(VENDOR/'fsbl.elf')+'\n'
        '  [pmufw_image] '+str(VENDOR/'pmufw.elf')+'\n'
        '  [destination_device=pl] '+str(VENDOR/'design_1_wrapper.bit')+'\n'
        '  [destination_cpu=a53-0, exception_level=el-3] '+str(elfs['service'])+'\n'
        '  [destination_cpu=a53-1, exception_level=el-3] '+str(elfs['sampler'])+'\n}\n')
    boot=run_dir/'BOOT.BIN'
    run([str(BOOTGEN),'-arch','zynqmp','-image',str(bif),'-o',str(boot),'-w','off'],'bootgen.log')
    partitions=run([str(BOOTGEN),'-arch','zynqmp','-read',str(boot)],'boot_partition_headers.log')
    # Bootgen displays destination CPU enums in the attributes of each partition.
    if 'a53-0' not in partitions.lower() or 'a53-1' not in partitions.lower():
        raise ValueError('Bootgen partition decode did not confirm both CPUs')
    provenance={}
    original=ROOT/'Cloud_test/e07/firmware'
    for p in (HERE/'firmware/service').iterdir():
        upstream=original/'e06_net'/p.name
        if p.is_file() and upstream.is_file():
            provenance[str(p.relative_to(HERE))]={'upstream':str(upstream.relative_to(ROOT)),
                'upstream_sha256':sha(upstream),'candidate_sha256':sha(p),'unchanged':sha(upstream)==sha(p)}
    for p in (HERE/'firmware/common').glob('fvit_protocol.*'):
        upstream=original/'common'/p.name
        provenance[str(p.relative_to(HERE))]={'upstream':str(upstream.relative_to(ROOT)),
            'upstream_sha256':sha(upstream),'candidate_sha256':sha(p),'unchanged':sha(upstream)==sha(p)}
    provenance['rail_mapping']={'upstream':str((original/'e06_net/e06_telemetry.c').relative_to(ROOT)),
        'upstream_sha256':sha(original/'e06_net/e06_telemetry.c'),
        'note':'18 rail mapping/Rshunt retained; polling and conversion rewritten'}
    sampler_bsp=build/'platform_workspace/sampler_platform/psu_cortexa53_1/sampler_a53_1/bsp'
    startup_paths=[sampler_bsp/'bsp.yaml',
        sampler_bsp/'libsrc/standalone/src/arm/ARMv8/64bit/gcc/boot.S',
        sampler_bsp/'libsrc/standalone/src/arm/ARMv8/64bit/gcc/xil-crt0.S',
        sampler_bsp/'libsrc/standalone/src/arm/ARMv8/64bit/xil_mmu.c',
        sampler_bsp/'libsrc/scugic/src/xscugic.c']
    provenance['sampler_startup_inputs']={str(p.relative_to(HERE)):sha(p) for p in startup_paths}
    for p in (HERE/'tests/fake_bsp').iterdir():
        upstream=ROOT/'Cloud_test/firmware/e06_net/tests/fake_bsp'/p.name
        provenance[str(p.relative_to(HERE))]={'upstream':str(upstream.relative_to(ROOT)),
            'upstream_sha256':sha(upstream),'candidate_sha256':sha(p),'unchanged':sha(upstream)==sha(p)}
    for p in (HERE/'tests/fake_lwip').iterdir():
        upstream=ROOT/'Cloud_test/firmware/e06_net/tests/fake_lwip'/p.name
        provenance[str(p.relative_to(HERE))]={'upstream':str(upstream.relative_to(ROOT)),
            'upstream_sha256':sha(upstream),'candidate_sha256':sha(p),'unchanged':sha(upstream)==sha(p)}
    (run_dir/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    for name,(filename,expected) in FROZEN.items():
        if sha(VENDOR/filename)!=expected:raise ValueError('immutable input changed during build')
    sd=HERE/sd_name;sd.mkdir(exist_ok=True)
    shutil.copy2(boot,sd/'BOOT.BIN')
    for name in ('input.bin','weights.bin','output.bin'):shutil.copy2(VENDOR/name,sd/name)
    manifest={**policy,'schema':'e07-independent-firmware-v1','candidate':'E07_INDEPENDENT_POWER_V1',
        'firmware_sha256':identity,'advertised_sha256':identity,'canonical_payload':payload,
        'artifact_hashes':inputs,'physical_status':'NOT_RUN','PL_rebuilt':False,
        'protocol_schema':1,'ELF':{n:{'path':str(p.relative_to(HERE)),'bytes':p.stat().st_size,'sha256':sha(p)} for n,p in elfs.items()},
        'BOOT':{'path':sd_name+'/BOOT.BIN','bytes':boot.stat().st_size,'sha256':sha(boot)},
        'build_directory':str(run_dir.relative_to(HERE)),'memory_map':memory,
        'capacity':{'rail_records':180000,'rail_record_bytes':128,'event_records':262144,
                    'event_record_bytes':64,'temperature_records':1024,'temperature_record_bytes':32,
                    'max_phase_seconds':150,'min_scan_ms':17,'guard_seconds_each':1,
                    'arm_lead_ms':1250,'capacity_checked_seconds':153},
        'checks':{'frozen_inputs':'PASS','native_tests':'PASS','ELF_regions':'PASS','BOOT_cpu_partitions':'PASS',
                  'physical_startup':'NOT_RUN','power_acceptance':'NOT_RUN'}}
    (HERE/identity_name).write_text(json.dumps(manifest,indent=2)+'\n')
    (sd/'FIRMWARE_IDENTITY.json').write_text(json.dumps(manifest,indent=2)+'\n')
    sums={str(p.relative_to(HERE)):{'bytes':p.stat().st_size,'sha256':sha(p)}
          for p in sorted(sd.iterdir()) if p.is_file()}
    (HERE/sums_name).write_text(json.dumps(sums,indent=2)+'\n')
    print(json.dumps({'build_directory':str(run_dir),'firmware_sha256':identity,
                      'BOOT_sha256':sha(boot),'physical_status':'NOT_RUN'},indent=2))


if __name__=='__main__':main()
