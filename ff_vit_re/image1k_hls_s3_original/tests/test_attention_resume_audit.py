"""Regression tests for nanosecond-exact terminal audit publication."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/audit_attention_terminal_resume.py'


def audit_module():
    assert SCRIPT.exists(), 'a reproducible Python terminal-audit generator is required'
    spec = importlib.util.spec_from_file_location('attention_resume_audit', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def terminal_fixture(root, *, mutate_mtime=False):
    artifact = root / 'checkpoints/attention/main/progress.json'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({'status': 'budget_exhausted', 'global_step': 199560}))
    os.utime(artifact, ns=(1790832967048150248, 1790832967048150248))
    scripts = root / 'scripts'
    scripts.mkdir()
    response = "print('{\"status\":\"budget_exhausted\",\"action\":\"already_complete\",\"global_step\":199560}')\n"
    mutation = ("import os\nfrom pathlib import Path\np=Path('checkpoints/attention/main/progress.json')\n"
                "s=p.stat()\nos.utime(p, ns=(s.st_atime_ns, s.st_mtime_ns+1))\n") if mutate_mtime else ''
    (scripts / 'train_strict_attention.py').write_text(mutation + response)
    (scripts / 'train_strict_joint.py').write_text(response)
    return artifact


def test_snapshot_nanoseconds_survive_binary64_json_consumers(tmp_path):
    module = audit_module()
    artifact = tmp_path / 'artifact'
    artifact.write_bytes(b'abc')
    os.utime(artifact, ns=(1790832967048150248, 1790832967048150248))
    snapshot = module.snapshot_artifacts(tmp_path, [artifact])
    # parse_int=float models a binary64 JSON consumer such as JavaScript.
    transferred = json.loads(json.dumps(snapshot), parse_int=float)
    assert transferred['artifact']['mtime_ns'] == '1790832967048150248'
    assert transferred['artifact']['sha256'] == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def test_python_cli_publishes_exact_audit_and_excludes_its_own_output(tmp_path):
    audit_module()
    artifact = terminal_fixture(tmp_path)
    output = tmp_path / 'reports/attention_qat_terminal_resume_audit.json'
    output.parent.mkdir()
    output.write_text('{"obsolete": true}')
    (output.parent / 'attention_qat_final_audit.json').write_text('{"derived_audit": true}')
    run = subprocess.run([sys.executable, str(SCRIPT), '--root', str(tmp_path)],
                         capture_output=True, text=True, check=True)
    result = json.loads(output.read_text())
    assert result['artifact_count'] == 1
    assert result['hashes_sizes_and_mtimes_unchanged'] is True
    assert result['artifacts']['checkpoints/attention/main/progress.json']['mtime_ns'] == '1790832967048150248'
    assert artifact.stat().st_mtime_ns == 1790832967048150248
    assert [r['result']['action'] for r in result['runs']] == ['already_complete', 'already_complete']
    expected_digest = hashlib.sha256(json.dumps(result['artifacts'], sort_keys=True).encode()).hexdigest()
    assert result['snapshot_sha256'] == expected_digest
    assert json.loads(run.stdout)['artifact_count'] == 1


def test_audit_rejects_a_one_nanosecond_resume_mutation(tmp_path):
    module = audit_module()
    terminal_fixture(tmp_path, mutate_mtime=True)
    with pytest.raises(ValueError, match='artifacts changed'):
        module.audit_terminal_resume(tmp_path)
