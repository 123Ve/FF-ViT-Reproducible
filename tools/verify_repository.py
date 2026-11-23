#!/usr/bin/env python3
"""Verify the archive and byte-identical source provenance, without a board."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='provenance/REPOSITORY_SHA256.json'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def payload(root):
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if set(rel.parts)&{'.git','__pycache__','.pytest_cache','.ruff_cache','.Xil'}:continue
        if rel.parts[0] in {'work','results'} or rel.as_posix().startswith('verification/local/'):continue
        if rel.as_posix()==MANIFEST:continue
        if p.is_file():
            if p.is_symlink():raise ValueError(f'Symlink in frozen archive: {rel}')
            yield p


def source_checks(root):
    rows=list(csv.DictReader((root/'provenance/COPIED_FILES.csv').open(encoding='utf-8')))
    for row in rows:
        p=root/row['path']
        if p.stat().st_size!=int(row['bytes']) or sha(p)!=row['sha256']:
            raise ValueError('Original source/artifact changed: '+row['path'])
    # All three tasks must have actual binary bytes, rather than LFS pointer text.
    tasks=json.loads((root/'deploy/tasks.json').read_text())
    for name,item in tasks.items():
        directory=root/'deploy'/name
        if (directory/'weights.bin').stat().st_size!=12*231008:raise ValueError(f'{name}: backbone ABI size')
        if (directory/'input.bin').stat().st_size!=224*224*3*2:raise ValueError(f'{name}: S16 input size')
        raw=(directory/'output.bin').read_bytes()
        if len(raw)!=4000:raise ValueError(f'{name}: expected 1000 S19 logits in int32 storage')
        if any(not -262144<=x<=262143 for x in struct.unpack('<1000i',raw)):
            raise ValueError(f'{name}: logits out of S19 range')
        for relative,expected in item['files'].items():
            if sha(root/relative)!=expected:raise ValueError(f'{name}: deployment hash mismatch: {relative}')
    return len(rows)


def verify(root=ROOT):
    root=Path(root)
    if not (root/MANIFEST).exists():raise ValueError('Repository manifest missing')
    stored=json.loads((root/MANIFEST).read_text())
    current={p.relative_to(root).as_posix():p for p in payload(root)}
    if set(stored['files'])!=set(current):
        raise ValueError('Inventory differs: '+json.dumps(dict(
            missing=sorted(set(stored['files'])-set(current)),
            unexpected=sorted(set(current)-set(stored['files'])))))
    for name,p in current.items():
        x=stored['files'][name]
        if p.stat().st_size!=x['bytes'] or sha(p)!=x['sha256']:
            raise ValueError('File size/SHA mismatch: '+name)
    originals=source_checks(root)
    return dict(status='OFFLINE_INTEGRITY_PASS',files=len(current),source_artifacts=originals,
        bytes=sum(p.stat().st_size for p in current.values()),tasks=3,dataset_images_included=False,
        physical_acceptance='NOT_RUN',new_120fps_power_measurement='NOT_RUN')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write-manifest',action='store_true',help='maintainer operation after intentional archive changes')
    args=p.parse_args()
    if args.write_manifest:
        source_checks(ROOT)
        items={x.relative_to(ROOT).as_posix():dict(bytes=x.stat().st_size,sha256=sha(x)) for x in payload(ROOT)}
        (ROOT/MANIFEST).write_text(json.dumps(dict(schema=1,files=items),sort_keys=True,indent=2)+'\n')
    print(json.dumps(verify(),indent=2))


if __name__=='__main__':main()
