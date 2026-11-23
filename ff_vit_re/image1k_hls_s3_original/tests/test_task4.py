import json

import pytest
import torch

from src.task4 import derive_low_sensitivity_order, fit_histogram_mse, select_disjoint_manifests, validate_manifest_pair
from scripts.task4_suite import freeze_sensitivity_identity


def test_manifest_selection_is_balanced_deterministic_and_disjoint(tmp_path):
    root = tmp_path / "train"
    mapping = {"n0": 0, "n1": 1}
    for name in mapping:
        (root / name).mkdir(parents=True)
        for index in range(8):
            (root / name / f"{index}.JPEG").write_bytes(bytes([index]))
    calibration, selection = select_disjoint_manifests(root, mapping, per_class=2, seed=7)
    assert (calibration, selection) == select_disjoint_manifests(root, mapping, per_class=2, seed=7)
    assert len(calibration) == len(selection) == 4
    assert {r["relative_path"] for r in calibration}.isdisjoint(r["relative_path"] for r in selection)
    assert {r["label"] for r in calibration} == {0, 1}
    validate_manifest_pair(calibration, selection, mapping, per_class=2)
    with pytest.raises(ValueError, match="overlap"):
        validate_manifest_pair(calibration, calibration, mapping, per_class=2)


def test_histogram_mse_fits_known_signed_and_unsigned_values():
    signed = torch.tensor([-3., -2., -1., 0., 1., 2., 3.]).numpy()
    scale, audit = fit_histogram_mse(signed, qmin=-4, qmax=3, bins=1024)
    assert 0.9 < scale < 1.1
    assert audit["count"] == 7
    unsigned = torch.tensor([0., 1., 2., 3., 4., 5., 6., 7.]).numpy()
    scale, audit = fit_histogram_mse(unsigned, qmin=0, qmax=7, bins=1024)
    assert 0.9 < scale < 1.1
    assert audit["count"] == 8


def test_ranking_uses_whole_block_top1_drop_with_stable_ties():
    shards = {f"layer-{i:02d}-whole-block": {"top1": value}
              for i, value in enumerate((.7, .6, .7, .5))}
    assert derive_low_sensitivity_order(shards, blocks=4) == (0, 2, 1, 3)


def test_incompatible_resume_preserves_frozen_identity_bytes(tmp_path):
    path = tmp_path / "sensitivity_identity.json"
    original = b'{"config_sha256":"' + b"a" * 64 + b'","sample_count":50000}\n'
    path.write_bytes(original)
    with pytest.raises(ValueError, match="frozen sensitivity identity"):
        freeze_sensitivity_identity(path, {"config_sha256": "b" * 64,
                                           "sample_count": 50_000}, resume=True)
    assert path.read_bytes() == original


def test_compatible_resume_does_not_rewrite_frozen_identity(tmp_path):
    path = tmp_path / "sensitivity_identity.json"
    original = b'{"sample_count":50000,"config_sha256":"' + b"a" * 64 + b'"}\n'
    path.write_bytes(original)
    freeze_sensitivity_identity(path, {"config_sha256": "a" * 64,
                                       "sample_count": 50_000}, resume=True)
    assert path.read_bytes() == original


def test_resume_with_shards_but_missing_identity_does_not_create_new_identity(tmp_path):
    path = tmp_path / "sensitivity_identity.json"
    shards = tmp_path / "shards"
    shards.mkdir()
    (shards / "baseline.json").write_text("{}")
    with pytest.raises(ValueError, match="identity is missing"):
        freeze_sensitivity_identity(path, {"sample_count": 50_000}, resume=True,
                                    shard_dir=shards)
    assert not path.exists()
