"""Package Windows E07 sources and a separate ready-to-copy SD_CARD directory."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = 'E07_Cloud_GUI_Win11_Source_V2_3'


def verify_release_inputs(root, profiles=('FIX', 'WINDOW', 'BATCH', 'FINAL'), release='V2'):
    """Fail closed on stale images, source, or SD fixtures before making ZIP."""
    for name in profiles:
        base = root / 'e07/boot' / f'BOOT_E07_NET_{release}_{name}'
        manifest = json.loads(base.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        data = base.with_suffix('.BIN').read_bytes()
        expected = manifest['artifacts']['boot']
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError(f'BOOT hash/size mismatch: {name}')
        identity = manifest['firmware_identity']
        canonical = json.dumps(identity['canonical_payload'], sort_keys=True,
                               separators=(',', ':'), ensure_ascii=True).encode('utf-8')
        if hashlib.sha256(canonical).hexdigest() != identity['advertised_sha256']:
            raise ValueError(f'Firmware identity mismatch: {name}')
        inputs = identity['canonical_payload']['inputs']
        source_root = (root / 'e07/firmware').resolve()
        for item in inputs['production_sources']:
            path = (source_root / item['path']).resolve()
            path.relative_to(source_root)
            data = path.read_bytes()
            if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError(f'Firmware source mismatch: {name}/{item["path"]}')
        for key in ('input', 'output', 'weights'):
            data = (root / 'e07/vendor/e07_base' / (key + '.bin')).read_bytes()
            item = inputs['copied_vendor_inputs'][key]
            if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError(f'SD fixture mismatch: {name}/{key}')


def main():
    output = ROOT / ('dist/' + ARCHIVE + '.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite package: {output}')
    # Historical V2 variants intentionally retain their original source identity.
    # Do not mix them with the new timer source in this release.
    verify_release_inputs(ROOT, ('FINAL',), release='V2_2')
    files = [ROOT / name for name in ('__init__.py', 'windows_e07_launcher.py',
        'run_e07_measurements.py', 'run_stream_measurements.py', 'docs/E07_CLOUD_RUNBOOK_CN.md',
        'docs/E07_V23_RUNBOOK_CN.txt', 'tools/export_e07_paper.py', 'tools/__init__.py',
        'tools/export_stream_plots.py', 'tools/analyze_e07_tcp_capture.py', 'tools/package_e07_cloud.py',
        'docs/E07_V2_OFFLINE_AUDIT_CN.md',
        'results/e07_v2_host_characterization.json',
        'results/e07_v2_2_offline_verification.json',
        'results/e07_v2_2_regression_final.log', 'results/e07_v2_2_build_FINAL_retry.log',
        'e07/vendor/e07_base/input.bin', 'boot/BOOT_E06_NET.manifest.json')]
    for section in ('cloud', 'dashboard', 'iot_eval'):
        files += [p for p in (ROOT / section).rglob('*') if p.is_file()
                  and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')]
    files += [ROOT / 'windows' / name for name in ('E07_Cloud_GUI.spec', 'build_e07_windows.ps1',
        'requirements-build.txt', 'Configure-ZCU102-Network.ps1', 'Restore-ZCU102-Network.ps1',
        'Allow-E07-Collector.ps1', 'Run-E07-Paper-Suite.ps1')]
    files += [p for p in (ROOT / 'e07/firmware').rglob('*') if p.is_file() and p.suffix in ('.c', '.h')]
    files += [ROOT / 'build_scripts' / name for name in
              ('build_e06_net.py', 'make_e06_net_boot.py', 'rebuild_e07_net.py')]
    files += [p for p in (ROOT / 'e07/tests').rglob('*') if p.is_file() and p.suffix in ('.c', '.h')]
    files += [ROOT / 'tests/test_e07_tail_recovery.py', ROOT / 'tests/test_e07_cloud.py',
              ROOT / 'tests/test_e07_performance.py', ROOT / 'results/e07_v23_regression.log',
              ROOT / 'results/e07_v23_verification.json',
              ROOT / 'firmware/e06_net/tests/fake_lwip/fake_lwip.c',
              ROOT / 'firmware/e06_net/tests/fake_lwip/fake_lwip.h']
    entries = [(str(Path('Cloud_test') / p.relative_to(ROOT)), p) for p in sorted(set(files))]
    entries += [('SD_CARD/BOOT.BIN', ROOT / 'e07/boot/BOOT_E07_NET_V2_2_FINAL.BIN'),
                ('Cloud_test/e07/boot/BOOT_E07_NET_V2_2_FINAL.manifest.json',
                 ROOT / 'e07/boot/BOOT_E07_NET_V2_2_FINAL.manifest.json')]
    entries += [('SD_CARD/' + name + '.bin', ROOT / 'e07/vendor/e07_base' / (name + '.bin'))
                for name in ('weights', 'input', 'output')]
    for evidence_folder in ('paper_20261007_verified_v22_final', 'physical_v22_20261007T054436.944438Z'):
        entries += [(str(Path('Cloud_test/results') / evidence_folder / p.name), p)
                    for p in (ROOT / 'results' / evidence_folder).iterdir() if p.is_file()]
    manifest = []
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, source in entries:
            data = source.read_bytes()
            manifest.append({'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            archive.writestr(ARCHIVE + '/' + relative, data)
        archive.writestr(ARCHIVE + '/SHA256SUMS.json', json.dumps(manifest, indent=2))
    print('E07_PACKAGE=' + str(output))
    print('SHA256=' + hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
