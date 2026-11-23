"""Read-only integrity and syntax checks. Does not import training modules."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def verify(root):
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    errors = []
    counts = dict(files=0, python=0, shell=0, json=0)
    expected = set()
    for row in manifest['files']:
        relative = row['path']
        path = root / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            errors.append(dict(path=relative, error='unsafe manifest path'))
            continue
        expected.add(relative)
        try:
            data = path.read_bytes()
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('size or SHA256 mismatch')
            counts['files'] += 1
            if path.suffix == '.py':
                compile(data, relative, 'exec', dont_inherit=True)
                counts['python'] += 1
            elif path.suffix == '.sh':
                result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True)
                if result.returncode:
                    raise ValueError(result.stderr.strip())
                counts['shell'] += 1
            elif path.suffix == '.json':
                json.loads(data)
                counts['json'] += 1
        except Exception as error:
            errors.append(dict(path=relative, error=str(error)))
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    unexpected = sorted(actual - expected - {'MANIFEST.json', 'VERIFICATION.json'})
    if unexpected:
        errors.append(dict(error='unmanifested files', paths=unexpected))
    return dict(status='PASS' if not errors else 'FAIL', checked=counts, errors=errors,
                scope='INTEGRITY_AND_STATIC_SYNTAX_ONLY', training='NOT_RUN',
                accuracy='NOT_REMEASURED', HLS_compilation='NOT_RUN', FPGA='NOT_RUN',
                python=sys.version)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = verify(args.root.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
