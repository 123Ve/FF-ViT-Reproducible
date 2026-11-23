#!/usr/bin/env python3
"""Freeze disjoint train subsets and fit each activation step on calibration only."""

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
from src.data import load_class_mapping, make_calibration_loader
from src.model import load_w3_parent
from src.provenance import atomic_write_json, sha256_file
from src.quant import BOUNDARIES, StrictS3Controller
from src.task4 import ActivationHistograms, atomic_write_jsonl, select_disjoint_manifests


def freeze(config, *, per_class: int, mapping_path: Path) -> None:
    train_root = Path(config["data"]["train"]["path"])
    mapping = load_class_mapping(mapping_path)
    calibration, selection = select_disjoint_manifests(
        train_root, mapping, per_class=per_class, seed=config["experiment"]["seed"])
    for role, records in (("calibration", calibration), ("selection", selection)):
        destination = ROOT / "metadata" / f"{role}_manifest.jsonl"
        if destination.exists():
            existing = [json.loads(line) for line in destination.read_text().splitlines() if line]
            if existing != records:
                raise ValueError(f"frozen {role} manifest differs from deterministic selection")
        else:
            atomic_write_jsonl(destination, records)
    atomic_write_json(ROOT / "metadata" / "subset_recipe.json", {
        "schema_version": 1, "seed": config["experiment"]["seed"],
        "per_class_per_role": per_class, "train_root": str(train_root),
        "class_mapping_sha256": sha256_file(mapping_path),
        "calibration_manifest_sha256": sha256_file(ROOT / "metadata/calibration_manifest.jsonl"),
        "selection_manifest_sha256": sha256_file(ROOT / "metadata/selection_manifest.jsonl"),
        "calibration_count": len(calibration), "selection_count": len(selection),
        "formal_validation_role": config["data"]["validation"]["path"],
    })
    print(json.dumps({"status": "frozen", "calibration": len(calibration), "selection": len(selection)}), flush=True)


def calibrate(config, *, per_class: int, mapping_path: Path, batch_size: int, workers: int, device: str) -> None:
    scales_path = ROOT / "metadata/activation_scales.json"
    if scales_path.exists():
        raise FileExistsError(f"activation scales already frozen: {scales_path}")
    manifest = ROOT / "metadata/calibration_manifest.jsonl"
    mapping = load_class_mapping(mapping_path)
    model, _ = load_w3_parent(config["model"]["w3_qat_checkpoint"],
                              contract=ROOT / "config/original_hls_s3.yaml", device=device)
    loader = make_calibration_loader(manifest, root=config["data"]["train"]["path"],
                                     class_mapping=mapping, batch_size=batch_size,
                                     num_workers=workers, expected_count=per_class * len(mapping))
    hist = ActivationHistograms(blocks=len(model.vit.blocks), device=device)
    controller = StrictS3Controller(model, scales={name: [1.] * len(model.vit.blocks) for name in BOUNDARIES})
    controller.set_masks({name: range(len(model.vit.blocks)) for name in BOUNDARIES})

    def observe(value, index, name):
        hist.update(index, name, value)
        return value

    controller._quantize = observe
    seen = set()
    start = time.perf_counter()
    controller.install()
    try:
        with torch.inference_mode():
            for images, _, ids in loader:
                if seen.intersection(ids):
                    raise ValueError("duplicate calibration sample")
                seen.update(ids)
                model(images.to(device, non_blocking=True))
                if len(seen) % 200 < len(ids):
                    print(json.dumps({"status": "calibrating", "samples": len(seen),
                                      "seconds": round(time.perf_counter() - start, 1)}), flush=True)
    finally:
        controller.remove()
    if len(seen) != per_class * len(mapping):
        raise ValueError("calibration sample count mismatch")
    scales, audits = hist.fit()
    atomic_write_json(scales_path, scales)
    atomic_write_json(ROOT / "metadata/activation_scale_fit.json", {
        "schema_version": 1, "method": "fixed-grid histogram MSE search, 128 geometric candidates, ties-to-even",
        "calibration_manifest_sha256": sha256_file(manifest),
        "checkpoint_sha256": sha256_file(config["model"]["w3_qat_checkpoint"]),
        "config_sha256": sha256_file(ROOT / "config/original_hls_s3.yaml"),
        "sample_count": len(seen), "duration_seconds": time.perf_counter() - start,
        "audits": audits,
    })
    print(json.dumps({"status": "scales_frozen", "path": str(scales_path),
                      "sha256": sha256_file(scales_path)}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "calibrate"))
    parser.add_argument("--per-class", type=int, default=2)
    parser.add_argument("--mapping", type=Path,
                        default=Path("/home/user/Desktop/ff_vit_re/image_lianghu/metadata/class_mapping.json"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    config = load_contract(ROOT / "config/original_hls_s3.yaml")
    validate_mainline_contract(config)
    if args.phase == "freeze":
        freeze(config, per_class=args.per_class, mapping_path=args.mapping)
    else:
        calibrate(config, per_class=args.per_class, mapping_path=args.mapping,
                  batch_size=args.batch_size, workers=args.workers, device=args.device)


if __name__ == "__main__":
    main()
