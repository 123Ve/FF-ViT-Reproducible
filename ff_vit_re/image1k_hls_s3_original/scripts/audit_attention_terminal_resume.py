#!/usr/bin/env python3
"""Publish a terminal resume audit directly in Python, preserving nanoseconds."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.provenance import atomic_write_json, sha256_file


def snapshot_artifacts(root, paths):
    root = Path(root)
    snapshot = {}
    for path in paths:
        path = Path(path)
        stat = path.stat()
        snapshot[str(path.relative_to(root))] = {
            'sha256': sha256_file(path), 'size': stat.st_size,
            # Epoch nanoseconds exceed binary64's exact integer range. Strings
            # retain every digit across JavaScript and other JSON consumers.
            'mtime_ns': str(stat.st_mtime_ns),
        }
    return snapshot


def audit_terminal_resume(root, *, output_path=None):
    root = Path(root).resolve()
    output_path = Path(output_path or root / 'reports/attention_qat_terminal_resume_audit.json').resolve()
    # Preserve the original training/probe artifact scope; derived audit reports
    # are not run artifacts and the output cannot snapshot itself.
    excluded_audits = {output_path, root / 'reports/attention_qat_final_audit.json'}
    progress = json.loads((root / 'checkpoints/attention/main/progress.json').read_text())
    if progress['status'] not in ('target_reached', 'budget_exhausted'):
        raise ValueError('terminal checkpoint required')
    expected = {'status': progress['status'], 'action': 'already_complete',
                'global_step': progress['global_step']}

    def collect():
        paths = [*root.glob('checkpoints/attention/main/*'), *root.glob('checkpoints/joint/main/*'),
                 *root.glob('reports/attention_qat_*.json'), *root.glob('reports/joint_qat_*.json')]
        return sorted(p for p in paths if p.is_file() and p.resolve() not in excluded_audits)

    before = snapshot_artifacts(root, collect())
    runs = []
    for runner in ('scripts/train_strict_attention.py', 'scripts/train_strict_joint.py'):
        run = subprocess.run([sys.executable, str(root / runner), '--resume'], cwd=root,
                             capture_output=True, text=True, check=True,
                             env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        result = json.loads(run.stdout)
        if result != expected:
            raise ValueError('unexpected terminal resume result')
        runs.append({'runner': runner, 'exit_code': run.returncode, 'result': result, 'stderr': run.stderr})
    if snapshot_artifacts(root, collect()) != before:
        raise ValueError('terminal resume artifacts changed')
    return {'artifact_count': len(before), 'artifacts': before, 'runs': runs,
            'hashes_sizes_and_mtimes_unchanged': True,
            'mtime_ns_encoding': 'decimal_string',
            'snapshot_sha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
            'generator': 'scripts/audit_attention_terminal_resume.py',
            'generator_sha256': sha256_file(__file__),
            'excluded_generated_audits': sorted(map(str, excluded_audits))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    output = args.root.resolve() / 'reports/attention_qat_terminal_resume_audit.json'
    result = audit_terminal_resume(args.root, output_path=output)
    # Do not round-trip this evidence through JavaScript before publication.
    atomic_write_json(output, result)
    print(json.dumps({'artifact_count': result['artifact_count'],
                      'hashes_sizes_and_mtimes_unchanged': True, 'output': str(output)}))


if __name__ == '__main__':
    main()
