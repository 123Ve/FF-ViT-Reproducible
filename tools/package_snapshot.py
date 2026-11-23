#!/usr/bin/env python3
"""Create a standalone ZIP with real LFS payload bytes, excluding .git/work."""
import argparse
import hashlib
from pathlib import Path
import zipfile
from verify_repository import ROOT, payload, verify


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.expanduser().resolve()
    if out.exists():raise SystemExit('Refusing to overwrite an existing ZIP')
    if out.is_relative_to(ROOT):raise SystemExit('ZIP must be outside the archived repository')
    print(verify(),flush=True)
    files=list(payload(ROOT))+[ROOT/'provenance/REPOSITORY_SHA256.json']
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for path in files:z.write(path,Path(ROOT.name)/path.relative_to(ROOT))
    # A ZIP provides actual files independently of a Git LFS server.
    h=hashlib.sha256()
    with out.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    checksum=h.hexdigest()
    out.with_suffix(out.suffix+'.sha256').write_text(f'{checksum}  {out.name}\n')
    print(dict(archive=str(out),files=len(files),bytes=out.stat().st_size,sha256=checksum),flush=True)


if __name__=='__main__':main()
