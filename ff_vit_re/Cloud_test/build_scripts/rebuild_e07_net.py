"""Build isolated E07 images with FVIT_E07_PROFILE=FIX/WINDOW/BATCH/FINAL.

Set FVIT_E07_RELEASE=V2_5 for the GEM recovery candidate. Defaults retain V2.2
paths, which are protected against overwrite. Run with Vitis -s.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Cloud_test.build_scripts.build_e06_net import (
    make_build_config, compute_build_identity, _copy_application_sources,
    write_build_identity_header, _atomic_json, verify_vendor_manifest)
from Cloud_test.build_scripts.make_e06_net_boot import make_boot_config, build_boot

PROFILES = {
    'FIX': dict(tcp_wnd=2048, batch_verify=0, ps_optimization='-O0'),
    'WINDOW': dict(tcp_wnd=32768, batch_verify=0, ps_optimization='-O0'),
    'BATCH': dict(tcp_wnd=32768, batch_verify=1, ps_optimization='-O0'),
    'FINAL': dict(tcp_wnd=32768, batch_verify=1, ps_optimization='-O2'),
}
RELEASE = 'V2_2'


def release_paths(root, name, *, release=RELEASE):
    if release not in ('V2_2', 'V2_4', 'V2_5'):
        raise ValueError('Unsupported E07 release')
    return (root / 'boot' / f'BOOT_E07_NET_{release}_{name}.BIN',
            root / 'build/variants' / f'{release}_{name}')


def bind_profile(identity, profile):
    identity = copy.deepcopy(identity)
    identity['canonical_payload']['tool_policy']['e07_network_profile'] = dict(profile)
    data = json.dumps(identity['canonical_payload'], sort_keys=True,
                      separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    identity['advertised_sha256'] = hashlib.sha256(data).hexdigest()
    return identity


def main():
    import vitis
    root = Path(__file__).resolve().parents[1] / 'e07'
    name = os.environ.get('FVIT_E07_PROFILE', 'FINAL')
    release = os.environ.get('FVIT_E07_RELEASE', RELEASE)
    profile = PROFILES[name]
    output, variant = release_paths(root, name, release=release)
    if output.exists() or variant.exists():
        raise FileExistsError(f'Refusing to overwrite published variant {name}')
    config = make_build_config(root / 'vendor/e07_base/e07_300mhz_wrapper.xsa',
                              root / 'build/e06_net_workspace', root / 'firmware', cloud_root=root)
    verify_vendor_manifest(root / 'vendor/source_manifest.json', cloud_root=root)
    identity = bind_profile(compute_build_identity(config), profile)
    _copy_application_sources(config, config.workspace / 'e06_net/src')
    write_build_identity_header(config.workspace / 'e06_net/src/firmware_build_identity.h', identity)
    client = vitis.create_client()
    try:
        client.set_workspace(path=str(config.workspace))
        platform = client.get_component(name='e06_net_platform')
        domain = platform.get_domain(name=config.domain)
        domain.set_config('lib', 'lwip220_tcp_wnd', str(profile['tcp_wnd']), 'lwip220')
        platform.build()
        app = client.get_component(name='e06_net')
        # The existing component has an explicit source list, not a glob.
        # Bind newly added production C files before building the new ELF.
        app.set_app_config('USER_COMPILE_SOURCES', sorted(
            p.name for p in (config.workspace / 'e06_net/src').glob('*.c')))
        app.set_app_config('USER_COMPILE_OPTIMIZATION_LEVEL', profile['ps_optimization'])
        app.set_app_config('USER_COMPILE_DEFINITIONS', f"E07_BATCH_VERIFY={profile['batch_verify']}")
        app.build()
    finally:
        vitis.dispose()
    lwipopts = config.workspace / 'e06_net_platform/export/e06_net_platform/sw' / config.domain / 'include/lwipopts.h'
    header = lwipopts.read_text()
    if not re.search(r'^#define\s+TCP_WND\s+' + str(profile['tcp_wnd']) + r'\s*$', header, re.M):
        raise RuntimeError('BSP TCP window did not propagate to exported application headers')
    commands = json.loads((config.workspace / 'e06_net/build/compile_commands.json').read_text())
    if 'e07_gem_tx.c' not in {Path(item['file']).name for item in commands}:
        raise RuntimeError('GEM recovery source was omitted from the application build')
    for command in commands:
        if command['file'].endswith('.c'):
            flags = command['command']
            if profile['ps_optimization'] not in flags.split() or f"-DE07_BATCH_VERIFY={profile['batch_verify']}" not in flags.split():
                raise RuntimeError('Application flags do not match the advertised profile')
    elf = config.workspace / 'e06_net/build/e06_net.elf'
    data = elf.read_bytes()
    if identity['advertised_sha256'].encode() not in data:
        raise RuntimeError('ELF is not bound to the current production source identity')
    verify_vendor_manifest(root / 'vendor/source_manifest.json', cloud_root=root)
    variant.mkdir(parents=True)
    copied_elf = variant / 'e06_net.elf'
    shutil.copy2(elf, copied_elf)
    shutil.copy2(lwipopts, variant / 'lwipopts.h')
    shutil.copy2(config.workspace / 'e06_net/build/compile_commands.json', variant / 'compile_commands.json')
    identity['built_artifact'] = {'path': str(copied_elf), 'bytes': len(data),
                                 'sha256': hashlib.sha256(data).hexdigest()}
    identity_path = variant / 'firmware_identity.json'
    _atomic_json(identity_path, identity)
    vendor = root / 'vendor/e07_base'
    boot_config = make_boot_config(vendor / 'fsbl.elf', vendor / 'pmufw.elf',
        vendor / 'design_1_wrapper.bit', copied_elf, output,
        firmware_identity=identity_path, cloud_root=root)
    manifest = build_boot(boot_config)
    manifest.update(model='E07', phase='E07_PHYSICAL', schema='fvit-e07-net-boot-v2',
        physical_status='NOT_RUN', release=release, build_profile=name, network_profile=profile,
        tcp_timer_driver='XTime polled tcp_tmr every 250 ms (no BSP tick required)',
        input_protocol='verified fixed preprocessed tensor replay')
    _atomic_json(boot_config.manifest, manifest)
    if release == 'V2_4':
        manifest.update(tail_drain_policy='Service tcp_output until entire response is TCP ACKed',
                        qualification='CANDIDATE: physical tail-stall resolution is not verified')
        _atomic_json(boot_config.manifest, manifest)
    if release == 'V2_5':
        manifest.update(
            tail_drain_policy='Service tcp_output until entire response is TCP ACKed',
            gem_tx_recovery='100ms IRQ-protected vendor completion reclamation; STARTTX only for enabled idle hardware-owned work; no forced pbuf refs or ring reset',
            qualification='CANDIDATE: hardware-model/real-lwIP tests pass; physical GEM recovery is NOT_RUN')
        _atomic_json(boot_config.manifest, manifest)
    print('E07_NET_' + release + '_BOOT=' + str(output))


if __name__ == '__main__':
    main()
