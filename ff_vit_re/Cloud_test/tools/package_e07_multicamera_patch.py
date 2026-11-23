"""Build an additive host-only patch; never bundle board/PL/input replacements."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[2]
FILES = (
    'Cloud_test/iot_eval/camera_load.py',
    'Cloud_test/iot_eval/camera_transport.py',
    'Cloud_test/run_e07_multicamera.py',
    'Cloud_test/tests/test_e07_multicamera.py',
    'Cloud_test/windows/Run-E07-MultiCamera.ps1',
    'Cloud_test/docs/E07_MULTICAMERA_RUNBOOK_CN.txt',
    'Cloud_test/docs/specs/2026-10-07-e07-multicamera-design.md',
    'Cloud_test/docs/plans/2026-10-07-e07-multicamera-plan.md',
)
README = '''E07 MC_V1 additive host-only patch for the existing V2_5 source package.
Merge the Cloud_test folder into E07_Cloud_GUI_Win11_Source_V2_5.
Do not delete or replace the existing source directory. No EXE rebuild needed.
Keep the V2.5 SD card unchanged. Python 3.10+ required.

PowerShell from the V2_5 project root:
.\\Cloud_test\\windows\\Run-E07-MultiCamera.ps1 -Duration 20 -Streams 1,2,4

Stop all other collectors, then power-cycle board AFTER LISTENING appears.
Default 30 FPS per producer, queue size 3/drop oldest, one serial FPGA service.
1/2/4-camera windows: 60 seconds total plus startup/drain/export overhead.
Outputs: report.json, summary.csv, streams.csv, frames.csv, events.jsonl.
See Cloud_test/docs/E07_MULTICAMERA_RUNBOOK_CN.txt for Chinese instructions.

All virtual cameras share the verified fixed input tensor; not distinct images.
CLI simulation is HOST_SIMULATION, not measured board performance.
Legacy GUI unchanged. No firmware, HLS, PL, SD, input or model replacements.
Windows native execution and physical throughput require local qualification.
SHA256SUMS.json lists the exact archived host-source contents.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=ROOT / 'Cloud_test/results/releases')
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    contents = {name: (ROOT / name).read_bytes() for name in FILES}
    contents['README_E07_MC_V1.txt'] = README.encode('utf-8')
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    contents['SHA256SUMS.json'] = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = args.output_root / f'E07_V2_5_MultiCamera_MC_V1_Patch_{stamp}.zip'
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError('archive integrity failure')
        for name, digest in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError('archive source digest mismatch: ' + name)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with target.with_suffix('.zip.sha256').open('x', encoding='ascii') as output:
        output.write(digest + '  ' + target.name + '\n')
    print(target)
    print('SHA256=' + digest)


if __name__ == '__main__':
    main()
