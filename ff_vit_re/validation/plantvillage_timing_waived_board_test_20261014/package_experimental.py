"""One-off PlantVillage setup-waived experiment; never changes formal gates."""
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

TASK = Path(__file__).resolve().parent
SOURCE = TASK.parent / 'u3_full_board_test_20261014'
sys.path.insert(0, str(SOURCE))

from build_firmware import TOOL
from prepare import digest, save_json
from publish import platform_identity, verify_bsp_binding, verify_firmware_config
from qualify import route_values, timing_values, verify_data, verify_fixtures


def setup_waived_timing(text):
    """Keep actual setup failures; reject unknown coverage, hold/pulse failures."""
    for key in ('no_clock', 'unconstrained_internal_endpoints'):
        match = re.search(r'checking ' + key + r' \((\d+)\)', text)
        if match is None or int(match[1]) != 0:
            raise ValueError('missing or failed timing coverage: ' + key)
    if 'WNS(ns)' not in text:
        raise ValueError('missing timing summary')
    rows = [line.split() for line in text.split('WNS(ns)', 1)[1].splitlines()
            if re.match(r'^\s*-?\d+\.\d+\s', line)]
    if not rows or len(rows[0]) != 12:
        raise ValueError('incomplete timing summary')
    values = list(map(float, rows[0]))
    if not all(math.isfinite(v) for v in values):
        raise ValueError('nonfinite timing summary')
    for index in (2, 3, 6, 7, 10, 11):
        if values[index] < 0 or not values[index].is_integer():
            raise ValueError('invalid endpoint count')
    for index in (4, 8):
        if values[index] < 0 or values[index + 1] != 0 or values[index + 2] != 0:
            raise ValueError('hold or pulse failure is outside the recorded waiver')
    if not (values[0] < 0 and values[1] < 0 and values[2] > 0):
        raise ValueError('report is not the expected setup-failed experiment')
    return dict(wns=values[0], tns=values[1], setup_fail=int(values[2]),
                whs=values[4], ths=values[5], hold_fail=int(values[6]),
                wpws=values[8], tpws=values[9], pulse_fail=int(values[10]),
                timing_qualified=False, setup_waived_by_user=True)


def main():
    out = SOURCE / 'outputs/plantvillage'
    hw = out / 'hardware'
    reports = hw / 'results/candidate05'
    release = TASK / 'hardware/release'
    sd = TASK / 'SD_CARD'
    if sd.exists() or (TASK / 'published_experimental.json').exists():
        raise ValueError('refusing existing experimental package overwrite')
    waiver = json.loads((TASK / 'USER_WAIVER.json').read_text())
    assert waiver['dataset'] == 'plantvillage' and waiver['timing_qualified'] is False
    protected = [reports / 'postroute.dcp', SOURCE / 'qualify.py',
                 SOURCE / 'board_contract.py', SOURCE / 'publish.py',
                 SOURCE / 'outputs/nwpu/SD_CARD/BOOT.BIN']
    protected_hashes = {str(p): digest(p) for p in protected}
    assert digest(reports / 'postroute.dcp') == waiver['source_dcp_sha256']

    meta = verify_data(out)
    verify_fixtures(out, meta)
    assert (meta['count'], meta['classes']) == (5459, 38)
    assert meta['checkpoint_sha256'] == waiver['source_checkpoint_sha256']
    for path, expected in json.loads((out / 'source_identity.json').read_text())['sources'].items():
        assert digest(path) == expected, path
    source = json.loads((hw / 'source_identity.json').read_text())
    for name, expected in source['source_files'].items():
        assert digest(hw / 'src' / name) == expected, name
    csim = json.loads((hw / 'csim_verified.json').read_text())
    assert csim['source_identity'] == source and csim['pass_'] is True
    assert csim['fixture_indices'] == meta['csim_fixture_indices']
    assert csim['frames_per_fixture'] == 2 and csim['logit_codes_per_call'] == 1000
    assert digest(hw / 'csim/project/solution1/csim/build/csim.exe') == csim['executable_sha256']

    before = setup_waived_timing((reports / 'timing_postroute.rpt').read_text())
    after = setup_waived_timing((release / 'timing_final.rpt').read_text())
    assert before == after, 'timing changed during bitstream generation'
    assert (after['wns'], after['tns'], after['setup_fail']) == (
        waiver['wns_ns'], waiver['tns_ns'], waiver['setup_failing_endpoints'])
    try:
        timing_values((release / 'timing_final.rpt').read_text())
    except ValueError as exc:
        assert str(exc) == 'setup/hold/pulse timing failed'
    else:
        raise ValueError('formal timing gate unexpectedly accepted experiment')
    route = route_values((release / 'route_final.rpt').read_text())
    assert route == route_values((reports / 'route_status.rpt').read_text())
    drc = (release / 'drc_final.rpt').read_text()
    assert 'Report DRC' in drc and not re.search(r'\|\s*(Error|Critical Warning)\s*\|', drc)
    utilization = {}
    for key in ('CLB LUTs', 'CLB Registers', 'Block RAM Tile', 'DSPs'):
        pattern = r'\|\s*' + re.escape(key) + r'\s*\|\s*([\d.]+)\s*\|'
        a = re.search(pattern, (reports / 'utilization_postroute.rpt').read_text())
        b = re.search(pattern, (release / 'utilization_final.rpt').read_text())
        assert a and b and a[1] == b[1], 'resource count changed: ' + key
        utilization[key] = float(b[1])
    clock = dict(line.split('=', 1) for line in (reports / 'clock.txt').read_text().splitlines() if '=' in line)
    for config, implemented in [('MMCM_MULT', 'CLKFBOUT_MULT_F'), ('MMCM_DIVCLK', 'DIVCLK_DIVIDE'),
                                ('MMCM_OUT_DIV', 'CLKOUT0_DIVIDE_F')]:
        assert abs(float(clock[config]) - float(clock['IMPLEMENTED_' + implemented])) < 0.00001
    actual_clock = float(clock['PS_PL_ACTUAL_MHZ']) * float(clock['MMCM_MULT']) / float(clock['MMCM_DIVCLK']) / float(clock['MMCM_OUT_DIV'])
    assert math.isfinite(actual_clock) and abs(actual_clock - waiver['clock_mhz']) < 0.00001
    assert float(clock['PL_PERIOD_NS']) <= 1000 / actual_clock + 0.00051
    assert clock['RESET_LOCK_VERIFIED'] == clock['CORE_CLOCK_CONSUMERS_VERIFIED'] == '1'

    platform = platform_identity(TASK / 'hardware')
    with zipfile.ZipFile(release / 'u3_platform.xsa') as xsa:
        bits = [name for name in xsa.namelist() if name.endswith('.bit')]
        assert len(bits) == 1 and xsa.read(bits[0]) == (release / 'design_1_wrapper.bit').read_bytes()
    fw = json.loads((out / 'firmware/identity.json').read_text())
    verify_firmware_config(out, fw)
    verify_bsp_binding(fw)
    for name, expected in fw['sources'].items():
        assert digest(out / 'firmware' / name) == expected, name
    assert digest(out / 'firmware/u3_accuracy.elf') == fw['elf_sha256'] == waiver['firmware_sha256']
    raw = subprocess.check_output([str(TOOL / 'aarch64-none-elf-nm'), '-n', str(out / 'firmware/u3_accuracy.elf')], text=True)
    symbols = {parts[2]: int(parts[0], 16) for line in raw.splitlines() if len(parts := line.split()) == 3}
    assert symbols['__el3_stack'] - symbols['_el3_stack_end'] >= 65536
    boot_source = json.loads((SOURCE.parent / 'local4_timing_closure_20261010/firmware_identity.json').read_text())
    assert platform['ps_initialization_sha256']['psu_init.c'] == boot_source['psu_init_sha256']
    boot_files = {}
    for name in ('fsbl.elf', 'pmufw.elf'):
        item = boot_source['binaries'][name]
        assert digest(item['source']) == item['sha256']
        boot_files[name] = Path(item['source'])

    sd.mkdir()
    for path in (out / 'data').iterdir():
        shutil.copy2(path, sd / path.name)
    copies = {
        'dataset.json': out / 'dataset.json',
        'source_identity.json': out / 'source_identity.json',
        'hardware_source_identity.json': hw / 'source_identity.json',
        'csim_verified.json': hw / 'csim_verified.json',
        'design_1_wrapper.bit': release / 'design_1_wrapper.bit',
        'u3_accuracy.elf': out / 'firmware/u3_accuracy.elf',
        'WARMUP.I': hw / 'fixtures/frame_00000/input_dma.bin',
        'WARMUP.G': hw / 'fixtures/frame_00000/expected.bin',
        'clock.txt': reports / 'clock.txt',
        'README_CN.txt': TASK / 'README_CN.txt',
        'USER_WAIVER.json': TASK / 'USER_WAIVER.json',
        'boot.bif': TASK / 'boot.bif',
        **boot_files,
    }
    for name in ('timing_final.rpt', 'route_final.rpt', 'drc_final.rpt', 'utilization_final.rpt'):
        copies[name] = release / name
    for name, source_path in copies.items():
        shutil.copy2(source_path, sd / name)
        assert digest(sd / name) == digest(source_path), name
    bootgen = '/opt/vivado/2025.1/Vivado/bin/bootgen'
    command = [bootgen, '-arch', 'zynqmp', '-image', 'boot.bif', '-o', 'BOOT.BIN']
    with (sd / 'bootgen.log').open('x') as log:
        subprocess.run(command, cwd=sd, check=True, stdout=log, stderr=subprocess.STDOUT)
    assert (sd / 'BOOT.BIN').stat().st_size > (sd / 'design_1_wrapper.bit').stat().st_size
    with (sd / 'bootgen_read.log').open('x') as log:
        subprocess.run([bootgen, '-arch', 'zynqmp', '-read', 'BOOT.BIN'], cwd=sd, check=True, stdout=log, stderr=subprocess.STDOUT)
    identity = dict(status='EXPERIMENTAL_TIMING_FAILED_NOT_BOARD_MEASURED', dataset='plantvillage',
                    frames=5459, classes=38, timing_qualified=False, board_measured=False,
                    rtl_cosimulation_measured=False, setup_waived_by_user=True,
                    software_accuracy_is_not_board_accuracy=True, fixed_rom_sha256=digest(hw / 'src/fixed_patch_head_rom.h'),
                    hardware_source_identity=source, firmware_identity=fw, platform_identity=platform,
                    timing=after, route=route, clock_mhz=actual_clock, resources=utilization,
                    csim_pass=True, data_complete=True, boot_command=command,
                    files={path.name: dict(bytes=path.stat().st_size, sha256=digest(path)) for path in sd.iterdir() if path.is_file()})
    for name, expected in meta['files'].items():
        assert identity['files'][name] == expected, 'copied dataset differs: ' + name
    save_json(sd / 'identity.json', identity)
    archive = TASK / 'PlantVillage_U3_5459_TIMING_FAILED_EXPERIMENTAL.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as package:
        for path in sorted(sd.iterdir()):
            package.write(path, arcname=path.name)
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == {path.name for path in sd.iterdir()}
        for name in package.namelist():
            with package.open(name) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == digest(sd / name), name
    for path, expected in protected_hashes.items():
        assert digest(path) == expected, 'protected original changed: ' + path
    result = dict(status=identity['status'], archive=str(archive), archive_sha256=digest(archive),
                  boot_bin=str(sd / 'BOOT.BIN'), boot_sha256=digest(sd / 'BOOT.BIN'),
                  timing_qualified=False, board_measured=False, frames=5459, classes=38,
                  timing=after, resources=utilization, protected_originals_sha256=protected_hashes,
                  zip_crc_and_all_file_hashes_verified=True)
    save_json(TASK / 'published_experimental.json', result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
