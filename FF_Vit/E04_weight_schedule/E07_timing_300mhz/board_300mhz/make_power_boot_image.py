"""Assemble gated E07 FPS+INA226 image without replacing the inference image."""
import csv
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRANCH = ROOT.parent
WORKSPACE = ROOT/'workspace'
DEPLOY = ROOT/'deploy_power'
SOURCES = {
    'fsbl.elf':WORKSPACE/'e07_platform/export/e07_platform/sw/boot/fsbl.elf',
    'pmufw.elf':WORKSPACE/'e07_pmufw/build/e07_pmufw.elf',
    'design_1_wrapper.bit':WORKSPACE/'e07_platform/export/e07_platform/hw/sdt/e07_300mhz_wrapper.bit',
    'e07_power.elf':WORKSPACE/'e07_power/build/e07_power.elf',
    'weights.bin':BRANCH/'inputs/weights.bin',
    'input.bin':BRANCH/'inputs/input.bin',
    'output.bin':BRANCH/'inputs/output.bin',
    'zcu102_ina226_rails.csv':ROOT/'power_src/zcu102_ina226_rails.csv',
    'POWER_MEASUREMENT_README.md':ROOT/'POWER_MEASUREMENT_README.md',
    'clock.txt':Path(os.environ.get('E07_CLOCK_FILE',str(BRANCH/'results/candidate05/clock.txt'))),
}

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()

def main():
    clock_file = Path(os.environ.get('E07_CLOCK_FILE',str(SOURCES['clock.txt'])))
    # Gate before creating deployment files, even when called outside the build script.
    subprocess.run([sys.executable,str(BRANCH/'scripts/check_release.py'),str(clock_file.parent)],check=True)
    missing = [str(path) for path in SOURCES.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError('Missing boot inputs: '+', '.join(missing))
    if DEPLOY.exists():
        raise RuntimeError('Refusing to overwrite '+str(DEPLOY))
    # Ensure the platform payload really contains the bitstream from this accepted run.
    if digest(SOURCES['design_1_wrapper.bit']) != digest(clock_file.parent/'design_1_wrapper.bit'):
        raise ValueError('Platform bitstream differs from accepted implementation')
    DEPLOY.mkdir(parents=True)
    for name, path in SOURCES.items():
        shutil.copy2(path, DEPLOY/name)
    (DEPLOY/'boot_power.bif').write_text(
        'the_ROM_image:\n{\n'
        ' [bootloader, destination_cpu=a53-0] fsbl.elf\n'
        ' [pmufw_image] pmufw.elf\n'
        ' [destination_device=pl] design_1_wrapper.bit\n'
        ' [destination_cpu=a53-0, exception_level=el-3] e07_power.elf\n}\n')
    subprocess.run(['bootgen','-arch','zynqmp','-image','boot_power.bif',
                    '-o','BOOT.BIN','-w','on'],cwd=DEPLOY,check=True)
    with (DEPLOY/'manifest.csv').open('w',newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['file','bytes','sha256','source'])
        for path in sorted(DEPLOY.iterdir()):
            if path.is_file() and path.name != 'manifest.csv':
                writer.writerow([path.name,path.stat().st_size,digest(path),str(SOURCES.get(path.name,'generated'))])

if __name__ == '__main__':
    main()
