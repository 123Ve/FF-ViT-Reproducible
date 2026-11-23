"""Build an isolated V2.5 source/SD candidate; never overwrite older releases."""
from pathlib import Path
import hashlib
import json
import zipfile

from Cloud_test.tools.package_e07_cloud import verify_release_inputs

ARCHIVE = 'E07_Cloud_GUI_Win11_Source_V2_5'
ROOT = Path(__file__).resolve().parents[1]


def package(root, output):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite package: {output}')
    verify_release_inputs(root, ('FINAL',), release='V2_5')
    manifest_path = root / 'e07/boot/BOOT_E07_NET_V2_5_FINAL.manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest['release'] != 'V2_5' or manifest['physical_status'] != 'NOT_RUN':
        raise ValueError('Expected an explicitly unqualified V2.5 candidate')
    elf = root / 'e07/build/variants/V2_5_FINAL/e06_net.elf'
    data = elf.read_bytes()
    if (hashlib.sha256(data).hexdigest() != manifest['artifacts']['app']['sha256']
            or manifest['firmware_identity']['advertised_sha256'].encode() not in data):
        raise ValueError('ELF identity does not match V2.5 BOOT manifest')
    files = [root / name for name in (
        '__init__.py', 'windows_e07_launcher.py', 'run_e07_measurements.py',
        'run_stream_measurements.py', 'boot/BOOT_E06_NET.manifest.json',
        'docs/E07_V25_RUNBOOK_CN.txt', 'tools/__init__.py',
        'tools/package_e07_cloud.py', 'tools/package_e07_v25.py',
        'tools/export_e07_paper.py', 'tools/export_stream_plots.py',
        'tools/analyze_e07_tcp_capture.py',
        'build_scripts/build_e06_net.py', 'build_scripts/make_e06_net_boot.py',
        'build_scripts/rebuild_e07_net.py',
        'windows/E07_Cloud_GUI.spec', 'windows/build_e07_windows.ps1',
        'windows/requirements-build.txt', 'windows/Allow-E07-Collector.ps1',
        'windows/Run-E07-Paper-Suite.ps1', 'windows/Configure-ZCU102-Network.ps1',
        'windows/Restore-ZCU102-Network.ps1',
        'tests/test_e07_tail_recovery.py', 'tests/test_e07_gem_recovery.py', 'tests/test_e07_cloud.py',
        'tests/test_e07_performance.py')]
    for section in ('cloud', 'dashboard', 'iot_eval', 'e07/firmware', 'e07/tests',
                    'firmware/e06_net/tests/fake_lwip'):
        files += [p for p in (root / section).rglob('*') if p.is_file()
                  and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')]
    files += [manifest_path, elf,
              root / 'e07/build/variants/V2_5_FINAL/firmware_identity.json',
              root / 'e07/build/variants/V2_5_FINAL/lwipopts.h',
              root / 'e07/build/variants/V2_5_FINAL/compile_commands.json',
              root / 'e07/vendor/e07_base/input.bin']
    entries = [(str(Path('Cloud_test') / p.relative_to(root)), p) for p in sorted(set(files))]
    entries += [('SD_CARD/BOOT.BIN', root / 'e07/boot/BOOT_E07_NET_V2_5_FINAL.BIN')]
    entries += [('SD_CARD/' + key + '.bin', root / 'e07/vendor/e07_base' / (key + '.bin'))
                for key in ('weights','input','output')]
    entries += [('README_CN.txt', root / 'docs/E07_V25_RUNBOOK_CN.txt')]
    for name in ('e07_v25_verification.json', 'e07_v25_regression.log',
                 'e07_v25_tail.log', 'e07_v25_gem.log', 'e07_v25_build_FINAL.log'):
        path = root / 'results' / name
        if path.is_file():
            entries.append(('verification/' + name, path))
    records = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, path in entries:
            data = path.read_bytes()
            records.append(dict(path=relative, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            archive.writestr(ARCHIVE + '/' + relative, data)
        archive.writestr(ARCHIVE + '/SHA256SUMS.json', json.dumps(records, indent=2))
    return records


if __name__ == '__main__':
    output = ROOT / 'dist' / (ARCHIVE + '.zip')
    records = package(ROOT, output)
    print('E07_PACKAGE=' + str(output))
    print('FILES=' + str(len(records)))
    print('SHA256=' + hashlib.sha256(output.read_bytes()).hexdigest())

