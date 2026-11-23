#!/usr/bin/env python3
"""Run one provenance-bound sensitivity shard against the accepted W3 parent."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyarrow.parquet as pq
import torch
from torch.utils.data import DataLoader, Subset

from src.contract import load_contract, validate_mainline_contract
from src.data import make_validation_loader
from src.model import load_w3_parent
from src.provenance import sha256_file
from src.quant import StrictS3Controller
from src.sensitivity import enumerate_experiments, evaluate_experiment, load_compatible_shard, write_shard


def ranking_from_file(path: Path) -> tuple[int, ...]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value["low_sensitivity_order"]
    if not isinstance(value, list):
        raise ValueError("ranking must be a JSON list or low_sensitivity_order object")
    return tuple(value)


def stratified_indices(root: Path, *, per_class: int, classes: int) -> tuple[int, ...]:
    """Choose stable first occurrences per class from Parquet label columns."""

    if per_class <= 0 or not 1 <= classes <= 1000:
        raise ValueError("probe requires positive per_class and 1..1000 classes")
    selected: list[int] = []
    found: dict[int, int] = {}
    offset = 0
    for path in sorted(root.rglob("*.parquet")):
        labels = pq.read_table(path, columns=["label"])["label"].to_pylist()
        for row, label in enumerate(labels):
            if type(label) is not int or not 0 <= label < classes:
                continue
            if found.get(label, 0) < per_class:
                selected.append(offset + row)
                found[label] = found.get(label, 0) + 1
        offset += len(labels)
    if len(found) != classes or any(found.get(label) != per_class for label in range(classes)):
        raise ValueError("validation data cannot supply requested stratified probe")
    return tuple(sorted(selected))


def dataset_digest(root: Path, indices: tuple[int, ...] | None) -> str:
    """Hash all source Parquet bytes and the exact selected index sequence."""

    paths = sorted(root.rglob("*.parquet"))
    if not paths:
        raise ValueError("validation data has no Parquet files")
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(sha256_file(path).encode("ascii") + b"\0")
    digest.update(json.dumps(indices, separators=(",", ":")).encode("ascii"))
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/original_hls_s3.yaml")
    parser.add_argument("--scales", type=Path, help="JSON mapping of boundary to calibrated per-block scales")
    parser.add_argument("--ranking", type=Path, help="JSON low-sensitivity block permutation")
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--experiment", help="one exact experiment ID")
    parser.add_argument("--shards", type=Path, default=ROOT / "results/sensitivity")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--probe-per-class", type=int, default=0)
    parser.add_argument("--probe-classes", type=int, default=1000)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.batch_size <= 0 or args.workers < 0:
        parser.error("batch-size must be positive and workers nonnegative")
    if args.ranking is None and (args.list or (args.experiment or "").startswith("cumulative-")):
        parser.error("--ranking is required to enumerate cumulative schedules")
    ranking = ranking_from_file(args.ranking) if args.ranking else tuple(range(args.blocks))
    cases = enumerate_experiments(args.blocks, low_sensitivity_order=ranking)
    if args.list:
        print(json.dumps([item.id for item in cases], indent=2))
        return
    if args.experiment is None or args.scales is None:
        parser.error("--experiment and --scales are required for evaluation")
    by_id = {item.id: item for item in cases}
    if args.experiment not in by_id:
        parser.error(f"unknown experiment: {args.experiment}")
    config = load_contract(args.config)
    validate_mainline_contract(config)
    checkpoint = Path(config["model"]["w3_qat_checkpoint"])
    validation_root = Path(config["data"]["validation"]["path"])
    selected = None if args.probe_per_class == 0 else stratified_indices(
        validation_root, per_class=args.probe_per_class, classes=args.probe_classes,
    )
    sample_count = config["protocol"]["full_validation_samples"] if selected is None else len(selected)
    expected = {
        "config_sha256": sha256_file(args.config),
        "checkpoint_sha256": sha256_file(checkpoint),
        "data_sha256": dataset_digest(validation_root, selected),
        "scales_sha256": sha256_file(args.scales),
        "sample_count": sample_count,
    }
    destination = args.shards / f"{args.experiment}.json"
    if destination.exists():
        if not args.resume:
            raise FileExistsError(f"shard exists; pass --resume to validate and reuse: {destination}")
        loaded = load_compatible_shard(destination, experiment_id=args.experiment,
                                       expected=expected, experiment=by_id[args.experiment])
        print(json.dumps({"status": "resumed", "experiment_id": loaded["experiment_id"], "path": str(destination)}))
        return
    scales = json.loads(args.scales.read_text(encoding="utf-8"))
    if not isinstance(scales, dict):
        raise ValueError("scales file must contain a JSON mapping")
    model, _ = load_w3_parent(checkpoint, contract=args.config, device=args.device)
    if len(model.vit.blocks) != args.blocks:
        raise ValueError("model block count differs from --blocks")
    controller = StrictS3Controller(model, scales=scales)
    loader = make_validation_loader(validation_root, model=model, batch_size=args.batch_size,
                                    num_workers=args.workers)
    if selected is not None:
        loader = DataLoader(Subset(loader.dataset, selected), batch_size=args.batch_size,
                            num_workers=args.workers, shuffle=False)
    shard = evaluate_experiment(model, controller, loader, by_id[args.experiment],
                                expected=expected, device=args.device)
    write_shard(destination, shard)
    print(json.dumps({"status": "written", "experiment_id": args.experiment, "path": str(destination)}))


if __name__ == "__main__":
    main()
