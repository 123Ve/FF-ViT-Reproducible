"""One-command sequential rerun of the reviewed audit and publication export."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from capture_ln import HERE, setup_environment


def commands():
    prefix = [sys.executable, '-B']
    return [prefix+[str(HERE/'run_validation.py'),'--dataset','all','--samples','128','--output','outputs/final128']]+[
        prefix+[str(HERE/'run_hls_probe.py'),'--input','outputs/final128/'+dataset]
        for dataset in ('plantvillage','nwpu','imagenet')]+[
        prefix+[str(HERE/'export_results.py'),'--input','outputs/final128','--output','outputs/paper']]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    setup_environment()
    for command in commands():
        print(json.dumps({'argv':command,'cwd':str(HERE)}),flush=True)
        if not args.dry_run:
            result=subprocess.run(command,cwd=HERE)
            if result.returncode: raise SystemExit(result.returncode)
