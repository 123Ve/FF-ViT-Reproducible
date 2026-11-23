#!/usr/bin/env python3
"""Run or resume all 77 formal sensitivity cases in one checkpoint session."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch

from src.contract import load_contract, validate_mainline_contract
from src.data import make_validation_loader
from src.model import load_w3_parent
from src.provenance import atomic_write_json, sha256_file
from src.quant import StrictS3Controller
from src.sensitivity import (aggregate_shards, enumerate_experiments, evaluate_experiment,
                             load_compatible_shard, write_shard)
from src.task4 import derive_low_sensitivity_order
from scripts.run_sensitivity import dataset_digest


def freeze_sensitivity_identity(
    path: Path, expected: dict[str, object], *, resume: bool,
    shard_dir: Path | None = None,
) -> None:
    """Preserve a previously frozen identity before any resumed shard is used."""

    if path.exists():
        try:
            frozen = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"frozen sensitivity identity is unreadable: {path}") from error
        if frozen != expected or not isinstance(frozen, dict):
            raise ValueError(f"frozen sensitivity identity differs from current inputs: {path}")
        if not resume and shard_dir is not None and any(shard_dir.glob("*.json")):
            raise FileExistsError("sensitivity shards exist; --resume is required")
        return
    if shard_dir is not None and any(shard_dir.glob("*.json")):
        raise ValueError("frozen sensitivity identity is missing for existing shards")
    atomic_write_json(path, expected)


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
    scale_path = ROOT / "metadata/activation_scales.json"
    config = load_contract(config_path)
    validate_mainline_contract(config)
    checkpoint = Path(config["model"]["w3_qat_checkpoint"])
    validation_root = Path(config["data"]["validation"]["path"])
    expected = {
        "config_sha256": sha256_file(config_path),
        "checkpoint_sha256": sha256_file(checkpoint),
        "data_sha256": dataset_digest(validation_root, None),
        "scales_sha256": sha256_file(scale_path),
        "sample_count": 50_000,
    }
    shard_dir = ROOT / "results/sensitivity"
    freeze_sensitivity_identity(ROOT / "metadata/sensitivity_identity.json", expected,
                                resume=args.resume, shard_dir=shard_dir)
    scales = json.loads(scale_path.read_text())
    model, _ = load_w3_parent(checkpoint, contract=config_path, device=args.device)
    blocks = len(model.vit.blocks)
    controller = StrictS3Controller(model, scales=scales)
    loader = make_validation_loader(validation_root, model=model,
                                    batch_size=args.batch_size, num_workers=args.workers)
    shard_dir.mkdir(parents=True, exist_ok=True)
    initial = tuple(case for case in enumerate_experiments(blocks, low_sensitivity_order=range(blocks))
                    if case.family != "cumulative")
    count_new = 0
    started = time.time()

    def run_case(case, completed, total):
        nonlocal count_new
        destination = shard_dir / f"{case.id}.json"
        if destination.exists():
            if not args.resume:
                raise FileExistsError(f"shard exists; --resume required: {destination}")
            shard = load_compatible_shard(destination, experiment_id=case.id,
                                          expected=expected, experiment=case)
            status = "resumed"
        else:
            shard = evaluate_experiment(model, controller, loader, case,
                                        expected=expected, device=args.device)
            write_shard(destination, shard)
            count_new += 1
            status = "written"
        progress = {"schema_version": 1, "status": status, "last_experiment": case.id,
                    "completed": completed, "total": total, "new_this_run": count_new,
                    "last_top1": shard["top1"], "elapsed_seconds": time.time() - started,
                    "identity": expected}
        atomic_write_json(ROOT / "results/sensitivity_progress.json", progress)
        print(json.dumps(progress), flush=True)
        return shard

    initial_shards = {}
    for index, case in enumerate(initial, start=1):
        initial_shards[case.id] = run_case(case, index, 77)
        if args.max_new_cases and count_new >= args.max_new_cases:
            return
    low_order = derive_low_sensitivity_order(initial_shards, blocks=blocks)
    ranking_path = ROOT / "metadata/sensitivity_ranking.json"
    ranking = {"schema_version": 1, "basis": "whole-block Top-1 descending on formal validation",
               "low_sensitivity_order": low_order, "identity": expected}
    if ranking_path.exists() and json.loads(ranking_path.read_text()) != json.loads(json.dumps(ranking)):
        raise ValueError("frozen sensitivity ranking differs from current layer shards")
    atomic_write_json(ranking_path, ranking)
    cases = enumerate_experiments(blocks, low_sensitivity_order=low_order)
    cumulative = [case for case in cases if case.family == "cumulative"]
    for index, case in enumerate(cumulative, start=len(initial) + 1):
        run_case(case, index, 77)
        if args.max_new_cases and count_new >= args.max_new_cases:
            return
    aggregate_shards(shard_dir, ROOT / "reports", cases, expected=expected)
    atomic_write_json(ROOT / "results/sensitivity_progress.json", {
        "schema_version": 1, "status": "complete", "completed": 77, "total": 77,
        "new_this_run": count_new, "elapsed_seconds": time.time() - started,
        "identity": expected,
    })
    print(json.dumps({"status": "complete", "cases": 77}), flush=True)


if __name__ == "__main__":
    main()
