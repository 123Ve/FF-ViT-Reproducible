#!/usr/bin/env python3
"""Evaluate a class-order-validated FP32 or HLS196 checkpoint from a manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import timm
import torch
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT.parent / "Dataset"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.manifest_dataset import ManifestImageDataset, load_manifest_bundle, make_eval_transform  # noqa: E402
from src.model_contract import ARCHITECTURE, HLS196DeiT, atomic_json_write, class_order_hash, iter_limited, sha256_file, validate_checkpoint_metadata  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=PROJECT_ROOT / "metadata")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--split", choices=("val", "test", "calibration"), default="val")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if args.batch_size <= 0 or args.workers < 0:
        raise ValueError("batch-size must be positive and workers nonnegative")
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else args.device if args.device != "auto" else "cpu")
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("--device cuda requested but CUDA is unavailable")
    bundle = load_manifest_bundle(args.metadata)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    token_count = checkpoint.get("token_mode", {}).get("total_tokens", 197)
    validate_checkpoint_metadata(checkpoint, bundle.classes, expected_token_count=token_count, expected_manifest_hashes=bundle.metadata_hashes)
    if token_count == 197:
        model = timm.create_model(ARCHITECTURE, pretrained=False, num_classes=45)
        model.load_state_dict(checkpoint["model"], strict=True)
    elif token_count == 196:
        model = HLS196DeiT(45)
        model.vit.pos_embed = torch.nn.Parameter(torch.zeros(1, 196, 192))
        model.vit.load_state_dict(checkpoint["model"], strict=True)
    else:
        raise ValueError(f"unsupported checkpoint token count: {token_count}")
    loader = DataLoader(ManifestImageDataset(args.source, bundle.records_for(args.split), make_eval_transform()), batch_size=args.batch_size, shuffle=False, num_workers=args.workers, pin_memory=device.type == "cuda", persistent_workers=args.workers > 0)
    model = model.to(device).eval()
    correct = total = 0
    with torch.inference_mode():
        for images, labels in iter_limited(loader, args.max_batches):
            images, labels = images.to(device, non_blocking=True), labels.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
            correct += int((logits.argmax(1) == labels).sum().item())
            total += labels.numel()
    if not total:
        raise ValueError("evaluation processed no images")
    report: dict[str, Any] = {"stage": "evaluation", "command": sys.argv, "checkpoint": str(args.checkpoint.resolve()), "checkpoint_sha256": sha256_file(args.checkpoint), "device": str(device), "torch": torch.__version__, "split": args.split, "samples": total, "top1": 100.0 * correct / total, "classes": list(bundle.classes), "class_order_sha256": class_order_hash(bundle.classes), "manifest_hashes": dict(bundle.metadata_hashes), "token_count": token_count}
    atomic_json_write(report, args.output)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
