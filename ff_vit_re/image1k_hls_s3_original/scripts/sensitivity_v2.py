#!/usr/bin/env python3
"""Rebuild the residual-sensitive ImageNet-1K tables with frozen v2 semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.contract import load_contract, validate_mainline_contract
from src.data import make_validation_loader
from src.model import load_w3_parent
from src.provenance import atomic_write_json, sha256_file
from src.quant import StrictS3Controller
from src.sensitivity import (Experiment, aggregate_shards, enumerate_experiments,
                             evaluate_experiment, load_compatible_shard, write_shard)
from src.task4 import derive_low_sensitivity_order
from scripts.run_sensitivity import dataset_digest


SEMANTIC_REVISION = "attention_residual_before_ln2_and_mlp_skip.v2"


def build_v2_identity(base: Mapping[str, Any], *, quant_path: Path,
                      sensitivity_path: Path,
                      extra_sources: Mapping[str, Path] | None = None) -> dict[str, Any]:
    sources = {
        "src/quant.py": quant_path,
        "src/sensitivity.py": sensitivity_path,
        **(extra_sources or {}),
    }
    return {
        "schema_version": 2,
        "semantic_revision": SEMANTIC_REVISION,
        "base_identity": dict(base),
        "source_sha256": {name: sha256_file(path) for name, path in sorted(sources.items())},
    }


def full_v2_identity(base: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    dependencies = {
        "src/contract.py": root / "src/contract.py",
        "src/data.py": root / "src/data.py",
        "src/model.py": root / "src/model.py",
        "src/task4.py": root / "src/task4.py",
        "scripts/run_sensitivity.py": root / "scripts/run_sensitivity.py",
        "scripts/sensitivity_v2.py": root / "scripts/sensitivity_v2.py",
        "image_lianghu/src/modeling.py": root.parent / "image_lianghu/src/modeling.py",
        "image_lianghu/src/mlp_activation_quant.py": root.parent / "image_lianghu/src/mlp_activation_quant.py",
    }
    return build_v2_identity(base, quant_path=root / "src/quant.py",
                             sensitivity_path=root / "src/sensitivity.py",
                             extra_sources=dependencies)


def freeze_v2_identity(path: Path, identity: Mapping[str, Any], *, shard_dir: Path,
                       resume: bool) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != identity:
            raise ValueError("v2 source or semantics identity differs from frozen run")
        if not resume and any(shard_dir.glob("*.json")):
            raise FileExistsError("v2 shards exist; --resume is required")
        return
    if any(shard_dir.glob("*.json")):
        raise ValueError("v2 source or semantics identity is missing for existing shards")
    atomic_write_json(path, dict(identity))


def partition_v2_cases(cases: tuple[Experiment, ...]):
    inherited = tuple(case for case in cases if "attention_residual" not in case.masks)
    initial = tuple(case for case in cases if "attention_residual" in case.masks
                    and case.family != "cumulative")
    cumulative = tuple(case for case in cases if case.family == "cumulative")
    return inherited, initial, cumulative


def inherit_v1_shards(v1: Path, v2: Path, cases: tuple[Experiment, ...], *,
                      expected: Mapping[str, Any], manifest_path: Path) -> None:
    hashes = {}
    for case in cases:
        source = v1 / f"{case.id}.json"
        load_compatible_shard(source, experiment_id=case.id, expected=expected,
                              experiment=case)
        hashes[case.id] = sha256_file(source)
    manifest = {
        "schema_version": 2,
        "inheritance": "byte-identical v1 shards whose masks exclude attention_residual",
        "base_identity": dict(expected),
        "shards": hashes,
    }
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("v2 inherited shard manifest or v1 source hash differs")
    else:
        if any((v2 / f"{case.id}.json").exists() for case in cases):
            raise ValueError("v2 inherited shard manifest is missing")
        atomic_write_json(manifest_path, manifest)
    v2.mkdir(parents=True, exist_ok=True)
    for case in cases:
        source = v1 / f"{case.id}.json"
        destination = v2 / source.name
        if destination.exists():
            if sha256_file(destination) != hashes[case.id]:
                raise ValueError(f"v2 inherited shard hash differs: {case.id}")
        else:
            shutil.copyfile(source, destination)
            if sha256_file(destination) != hashes[case.id]:
                raise ValueError(f"v2 inherited shard copy hash differs: {case.id}")


def rank_v2(shards: Mapping[str, Mapping[str, Any]], *, block_count: int) -> tuple[int, ...]:
    return derive_low_sensitivity_order(shards, blocks=block_count)


def v2_identity_digest(identity: Mapping[str, Any]) -> str:
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_affected_v2_shard(path: Path, *, case: Experiment,
                               expected: Mapping[str, Any],
                               v2_identity: Mapping[str, Any]) -> dict[str, Any]:
    shard = load_compatible_shard(path, experiment_id=case.id,
                                  expected=expected, experiment=case)
    if shard.get("v2_semantics_sha256") != v2_identity_digest(v2_identity):
        raise ValueError(f"affected shard lacks frozen v2 semantics identity: {case.id}")
    return shard


def write_affected_v2_shard(path: Path, shard: Mapping[str, Any], *,
                            v2_identity: Mapping[str, Any]) -> None:
    write_shard(path, {**shard, "v2_semantics_sha256": v2_identity_digest(v2_identity)})


def stamp_legacy_affected_shards(v1: Path, v2: Path, cases: tuple[Experiment, ...], *,
                                 expected: Mapping[str, Any],
                                 v2_identity: Mapping[str, Any],
                                 manifest_path: Path) -> None:
    """Upgrade this already completed run after validating every legacy rerun."""

    identity_hash = v2_identity_digest(v2_identity)
    v1_hashes = {}
    for case in cases:
        path = v1 / f"{case.id}.json"
        load_compatible_shard(path, experiment_id=case.id, expected=expected,
                              experiment=case)
        v1_hashes[case.id] = sha256_file(path)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest.get("schema_version") != 2 or
                manifest.get("v2_identity_sha256") != identity_hash or
                manifest.get("v1_hashes") != v1_hashes or
                set(manifest.get("pre_upgrade_hashes", {})) != set(v1_hashes)):
            raise ValueError("legacy v2 migration manifest differs from frozen inputs")
    else:
        before_hashes = {}
        for case in cases:
            path = v2 / f"{case.id}.json"
            shard = load_compatible_shard(path, experiment_id=case.id,
                                          expected=expected, experiment=case)
            if "v2_semantics_sha256" in shard:
                raise ValueError(f"affected shard already stamped without migration manifest: {case.id}")
            before_hashes[case.id] = sha256_file(path)
            if before_hashes[case.id] == v1_hashes[case.id]:
                raise ValueError(f"affected shard is a copied v1 result: {case.id}")
        manifest = {"schema_version": 2, "v2_identity_sha256": identity_hash,
                    "base_identity": dict(expected), "v1_hashes": v1_hashes,
                    "pre_upgrade_hashes": before_hashes}
        atomic_write_json(manifest_path, manifest)
    for case in cases:
        path = v2 / f"{case.id}.json"
        shard = load_compatible_shard(path, experiment_id=case.id,
                                      expected=expected, experiment=case)
        marker = shard.get("v2_semantics_sha256")
        if marker == identity_hash:
            continue
        if marker is not None or sha256_file(path) != manifest["pre_upgrade_hashes"][case.id]:
            raise ValueError(f"affected shard differs from pre-upgrade hash: {case.id}")
        write_affected_v2_shard(path, shard, v2_identity=v2_identity)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-new-cases", type=int, default=0)
    args = parser.parse_args()
    if args.batch_size <= 0 or args.workers < 0 or args.max_new_cases < 0:
        parser.error("batch-size must be positive and workers/max-new-cases nonnegative")

    config_path = ROOT / "config/original_hls_s3.yaml"
    scales_path = ROOT / "metadata/activation_scales.json"
    config = load_contract(config_path)
    validate_mainline_contract(config)
    checkpoint = Path(config["model"]["w3_qat_checkpoint"])
    validation_root = Path(config["data"]["validation"]["path"])
    expected = {
        "config_sha256": sha256_file(config_path),
        "checkpoint_sha256": sha256_file(checkpoint),
        "data_sha256": dataset_digest(validation_root, None),
        "scales_sha256": sha256_file(scales_path),
        "sample_count": 50_000,
    }
    original_identity = json.loads((ROOT / "metadata/sensitivity_identity.json").read_text())
    if expected != original_identity:
        raise ValueError("v1 frozen data/model/scales identity differs")
    v1 = ROOT / "results/sensitivity"
    v2 = ROOT / "results/sensitivity_v2"
    identity_path = ROOT / "metadata/sensitivity_v2_identity.json"
    identity = full_v2_identity(expected, root=ROOT)
    freeze_v2_identity(identity_path, identity, shard_dir=v2, resume=args.resume)
    old_order = json.loads((ROOT / "metadata/sensitivity_ranking.json").read_text())["low_sensitivity_order"]
    initial_cases = enumerate_experiments(12, low_sensitivity_order=old_order)
    inherited, initial, _ = partition_v2_cases(initial_cases)
    if (len(inherited), len(initial)) != (28, 25):
        raise ValueError("unexpected v2 initial case partition")
    inherit_v1_shards(v1, v2, inherited, expected=expected,
                      manifest_path=ROOT / "metadata/sensitivity_v2_inherited.json")

    scales = json.loads(scales_path.read_text())
    model, _ = load_w3_parent(checkpoint, contract=config_path, device=args.device)
    controller = StrictS3Controller(model, scales=scales)
    loader = make_validation_loader(validation_root, model=model,
                                    batch_size=args.batch_size, num_workers=args.workers)
    started = time.time()
    new_count = 0
    progress_path = ROOT / "results/sensitivity_v2_progress.json"

    def run_case(case: Experiment) -> dict[str, Any]:
        nonlocal new_count
        destination = v2 / f"{case.id}.json"
        if destination.exists():
            if not args.resume:
                raise FileExistsError(f"v2 shard exists; --resume required: {destination}")
            shard = validate_affected_v2_shard(destination, case=case,
                                               expected=expected, v2_identity=identity)
            status = "resumed"
        else:
            shard = evaluate_experiment(model, controller, loader, case,
                                        expected=expected, device=args.device)
            write_affected_v2_shard(destination, shard, v2_identity=identity)
            new_count += 1
            status = "written"
        progress = {
            "schema_version": 2, "status": status, "last_experiment": case.id,
            "new_this_run": new_count, "last_top1": shard["top1"],
            "elapsed_seconds": time.time() - started,
            "v2_identity": identity,
        }
        atomic_write_json(progress_path, progress)
        print(json.dumps(progress), flush=True)
        return shard

    layer_shards = {}
    for case in initial:
        shard = run_case(case)
        if case.id.endswith("whole-block"):
            layer_shards[case.id] = shard
        if args.max_new_cases and new_count >= args.max_new_cases:
            return
    order = rank_v2(layer_shards, block_count=12)
    ranking = {
        "schema_version": 2,
        "basis": "corrected whole-block Top-1 descending on formal 50k",
        "low_sensitivity_order": order,
        "v2_identity": identity,
    }
    ranking_path = ROOT / "metadata/sensitivity_ranking_v2.json"
    if ranking_path.exists() and json.loads(ranking_path.read_text()) != json.loads(json.dumps(ranking)):
        raise ValueError("frozen v2 ranking differs from corrected layer shards")
    atomic_write_json(ranking_path, ranking)

    cases = enumerate_experiments(12, low_sensitivity_order=order)
    _, _, cumulative = partition_v2_cases(cases)
    if len(cumulative) != 24:
        raise ValueError("unexpected v2 cumulative case partition")
    for case in cumulative:
        run_case(case)
        if args.max_new_cases and new_count >= args.max_new_cases:
            return
    aggregate_shards(v2, ROOT / "reports/sensitivity_v2", cases, expected=expected)
    hashes = {case.id: sha256_file(v2 / f"{case.id}.json") for case in cases}
    atomic_write_json(ROOT / "metadata/sensitivity_v2_shards.json", {
        "schema_version": 2, "v2_identity": identity, "ranking": ranking,
        "shards": hashes,
    })
    atomic_write_json(progress_path, {
        "schema_version": 2, "status": "complete", "completed": 77,
        "new_this_run": new_count, "elapsed_seconds": time.time() - started,
        "v2_identity": identity,
    })
    print(json.dumps({"status": "complete", "cases": 77,
                      "v2_order": order, "new_this_run": new_count}), flush=True)


if __name__ == "__main__":
    main()
