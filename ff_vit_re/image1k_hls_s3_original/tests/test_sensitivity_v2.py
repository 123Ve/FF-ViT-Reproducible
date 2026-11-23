import json

import pytest

from src.provenance import sha256_file
from src.sensitivity import enumerate_experiments, experiment_sha256
from scripts.sensitivity_v2 import (
    build_v2_identity,
    freeze_v2_identity,
    inherit_v1_shards,
    partition_v2_cases,
    rank_v2,
    stamp_legacy_affected_shards,
    validate_affected_v2_shard,
    write_affected_v2_shard,
)


BASE = {
    "config_sha256": "a" * 64,
    "checkpoint_sha256": "b" * 64,
    "data_sha256": "c" * 64,
    "scales_sha256": "d" * 64,
    "sample_count": 50_000,
}


def test_v2_identity_rejects_changed_quant_source_and_missing_manifest(tmp_path):
    quant = tmp_path / "quant.py"
    engine = tmp_path / "sensitivity.py"
    quant.write_text("v2 residual before skip\n")
    engine.write_text("same sensitivity engine\n")
    first = build_v2_identity(BASE, quant_path=quant, sensitivity_path=engine)
    root = tmp_path / "shards"
    root.mkdir()
    identity_path = tmp_path / "identity.json"
    freeze_v2_identity(identity_path, first, shard_dir=root, resume=False)
    quant.write_text("changed source\n")
    changed = build_v2_identity(BASE, quant_path=quant, sensitivity_path=engine)
    with pytest.raises(ValueError, match="source or semantics identity"):
        freeze_v2_identity(identity_path, changed, shard_dir=root, resume=True)
    identity_path.unlink()
    (root / "baseline.json").write_text("{}")
    with pytest.raises(ValueError, match="missing"):
        freeze_v2_identity(identity_path, changed, shard_dir=root, resume=True)


def test_v2_identity_tracks_runner_and_model_loader_sources(tmp_path):
    quant = tmp_path / "quant.py"
    engine = tmp_path / "sensitivity.py"
    runner = tmp_path / "runner.py"
    loader = tmp_path / "model.py"
    for path in (quant, engine, runner, loader):
        path.write_text(path.name)
    extra = {"scripts/sensitivity_v2.py": runner, "src/model.py": loader}
    first = build_v2_identity(BASE, quant_path=quant, sensitivity_path=engine,
                              extra_sources=extra)
    assert first["source_sha256"]["src/model.py"] == sha256_file(loader)
    runner.write_text("modified")
    changed = build_v2_identity(BASE, quant_path=quant, sensitivity_path=engine,
                                extra_sources=extra)
    assert changed != first


def test_v2_stages_recompute_ranking_before_cumulative_masks():
    old = enumerate_experiments(12, low_sensitivity_order=range(12))
    inherited, initial, cumulative = partition_v2_cases(old)
    assert (len(inherited), len(initial), len(cumulative)) == (28, 25, 24)
    assert [case.id for case in initial[:1]] == ["operator-attention_residual"]
    assert all("attention_residual" in case.masks for case in (*initial, *cumulative))
    shards = {f"layer-{index:02d}-whole-block": {"top1": (index + 1) / 20}
              for index in range(12)}
    order = rank_v2(shards, block_count=12)
    assert order == tuple(reversed(range(12)))
    revised = enumerate_experiments(12, low_sensitivity_order=order)
    assert revised[-24].id == "cumulative-low-01"
    assert revised[-24].masks["attention_residual"] == (11,)
    assert revised[-24].masks != cumulative[0].masks


def test_inherited_shard_is_byte_identical_and_manifest_hash_is_checked(tmp_path):
    case = enumerate_experiments(1, low_sensitivity_order=(0,))[0]
    v1 = tmp_path / "v1"
    v2 = tmp_path / "v2"
    v1.mkdir()
    source = v1 / "baseline.json"
    source.write_text(json.dumps({
        "schema_version": 1, "experiment_id": case.id,
        "experiment_sha256": experiment_sha256(case), **BASE,
        "top1": .7, "top5": .9, "tensor_metrics": {},
    }))
    manifest = tmp_path / "inherited.json"
    inherit_v1_shards(v1, v2, (case,), expected=BASE, manifest_path=manifest)
    assert (v2 / "baseline.json").read_bytes() == source.read_bytes()
    assert json.loads(manifest.read_text())["shards"][case.id] == sha256_file(source)
    (v2 / "baseline.json").write_text("tampered")
    with pytest.raises(ValueError, match="hash"):
        inherit_v1_shards(v1, v2, (case,), expected=BASE, manifest_path=manifest)


def test_resume_rejects_v1_affected_shard_without_v2_semantics_identity(tmp_path):
    case = next(case for case in enumerate_experiments(1, low_sensitivity_order=(0,))
                if case.id == "operator-attention_residual")
    metrics = {"elements": 1, "mse": 0., "mae": 0., "cosine": 1.,
               "sqnr_db": None, "clip_rate": 0., "zero_rate": 0.,
               "observed_min": 0., "observed_max": 0.}
    shard = {"schema_version": 1, "experiment_id": case.id,
             "experiment_sha256": experiment_sha256(case), **BASE,
             "top1": .6, "top5": .8,
             "tensor_metrics": {"0:attention_residual": metrics}}
    path = tmp_path / f"{case.id}.json"
    path.write_text(json.dumps(shard))
    identity = {"schema_version": 2, "semantic_revision": "residual-before-skip",
                "source_sha256": {"src/quant.py": "e" * 64}, "base_identity": BASE}
    with pytest.raises(ValueError, match="v2 semantics identity"):
        validate_affected_v2_shard(path, case=case, expected=BASE, v2_identity=identity)
    write_affected_v2_shard(path, shard, v2_identity=identity)
    assert validate_affected_v2_shard(path, case=case, expected=BASE,
                                      v2_identity=identity)["top1"] == .6
    changed = {**identity, "source_sha256": {"src/quant.py": "f" * 64}}
    with pytest.raises(ValueError, match="v2 semantics identity"):
        validate_affected_v2_shard(path, case=case, expected=BASE, v2_identity=changed)


def test_legacy_v2_upgrade_requires_distinct_valid_rerun_and_records_old_hash(tmp_path):
    case = next(case for case in enumerate_experiments(1, low_sensitivity_order=(0,))
                if case.id == "operator-attention_residual")
    metrics = {"elements": 1, "mse": 0., "mae": 0., "cosine": 1.,
               "sqnr_db": None, "clip_rate": 0., "zero_rate": 0.,
               "observed_min": 0., "observed_max": 0.}
    shard = {"schema_version": 1, "experiment_id": case.id,
             "experiment_sha256": experiment_sha256(case), **BASE,
             "top1": .7, "top5": .9,
             "tensor_metrics": {"0:attention_residual": metrics}}
    v1, v2 = tmp_path / "v1", tmp_path / "v2"
    v1.mkdir()
    v2.mkdir()
    original = v1 / f"{case.id}.json"
    rerun = v2 / original.name
    original.write_text(json.dumps(shard))
    rerun.write_bytes(original.read_bytes())
    identity = {"schema_version": 2, "semantic_revision": "residual-before-skip",
                "source_sha256": {"src/quant.py": "e" * 64}, "base_identity": BASE}
    manifest = tmp_path / "migration.json"
    with pytest.raises(ValueError, match="copied v1"):
        stamp_legacy_affected_shards(v1, v2, (case,), expected=BASE,
                                     v2_identity=identity, manifest_path=manifest)
    assert not manifest.exists()
    shard["top1"] = .6
    rerun.write_text(json.dumps(shard))
    before_hash = sha256_file(rerun)
    stamp_legacy_affected_shards(v1, v2, (case,), expected=BASE,
                                 v2_identity=identity, manifest_path=manifest)
    assert json.loads(manifest.read_text())["pre_upgrade_hashes"][case.id] == before_hash
    assert validate_affected_v2_shard(rerun, case=case, expected=BASE,
                                      v2_identity=identity)["top1"] == .6
    stamp_legacy_affected_shards(v1, v2, (case,), expected=BASE,
                                 v2_identity=identity, manifest_path=manifest)
