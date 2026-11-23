#!/usr/bin/env python3
"""Convert a standard 197-token NWPU checkpoint to the HLS196 token contract."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

import torch
import numpy as np
from torch import nn
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT.parent / "Dataset"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.manifest_dataset import ManifestImageDataset, load_manifest_bundle, make_eval_transform, make_train_transform  # noqa: E402
from src.model_contract import HLS196DeiT, atomic_json_write, atomic_torch_save, checkpoint_metadata, class_order_hash, iter_limited, sha256_file, validate_checkpoint_metadata  # noqa: E402


def _seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _evaluate(model: nn.Module, loader: DataLoader[Any], device: torch.device, max_batches: int | None) -> dict[str, float | int]:
    model.eval()
    correct = total = 0
    with torch.inference_mode():
        for images, labels in iter_limited(loader, max_batches):
            images, labels = images.to(device, non_blocking=True), labels.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
            correct += int((logits.argmax(1) == labels).sum().item())
            total += labels.numel()
    if total == 0:
        raise ValueError("evaluation processed no images")
    return {"top1": 100.0 * correct / total, "samples": total}


def _stage_directory(output: Path) -> Path:
    if output.exists() or output.is_symlink():
        raise ValueError(f"refusing to reuse published output directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    stage.mkdir()
    return stage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=PROJECT_ROOT / "metadata")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "checkpoints" / "hls196")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=0, help="must be zero: this command is conversion-only")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--max-eval-batches", type=int, default=None)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if args.epochs != 0:
        raise ValueError("make_hls196.py is conversion-only; --epochs must be 0")
    if args.batch_size <= 0 or args.workers < 0:
        raise ValueError("batch-size must be positive; workers nonnegative")
    canonical_report = (args.output / "report.json").resolve()
    if args.report is not None and args.report.resolve() != canonical_report:
        raise ValueError("--report must be <output>/report.json; external reports are unsupported")
    if args.report is not None and args.report.exists():
        raise ValueError(f"refusing to reuse published report: {args.report}")
    _seed_all(args.seed)
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else args.device if args.device != "auto" else "cpu")
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("--device cuda requested but CUDA is unavailable")
    bundle = load_manifest_bundle(args.metadata)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    validate_checkpoint_metadata(checkpoint, bundle.classes, expected_token_count=197, expected_manifest_hashes=bundle.metadata_hashes)
    model = HLS196DeiT(45)
    model.load_from_standard197(checkpoint["model"])
    model = model.to(device)
    loader_options = {"num_workers": args.workers, "pin_memory": device.type == "cuda", "persistent_workers": args.workers > 0}
    loader_generator = torch.Generator().manual_seed(args.seed)
    val_loader = DataLoader(ManifestImageDataset(args.source, bundle.records_for("val"), make_eval_transform()), batch_size=args.batch_size, shuffle=False, **loader_options)
    before = _evaluate(model, val_loader, device, args.max_eval_batches)
    history: list[dict[str, Any]] = []
    best_val = float(before["top1"])
    best_epoch = 0
    best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.vit.state_dict().items()}
    final = {"top1": best_val, "samples": before["samples"]}
    stage = _stage_directory(args.output)
    try:
        payload = checkpoint_metadata(classes=bundle.classes, architecture="deit_tiny_hls196", token_count=196, model_state=best_state, epoch=best_epoch, val_top1=final["top1"], source_checkpoint=str(args.checkpoint.resolve()), source_checkpoint_sha256=sha256_file(args.checkpoint), manifest_hashes=dict(bundle.metadata_hashes), seed=args.seed, token_mode={"total_tokens": 196, "cls_tokens": 1, "patch_tokens": 195, "dropped_patch": 0, "mapping": "[CLS,patch1,...,patch195]"})
        atomic_torch_save(payload, stage / "best.pth")
        report = {"stage": "hls196", "command": sys.argv, "device": str(device), "torch": torch.__version__, "seed": args.seed, "classes": list(bundle.classes), "class_order_sha256": class_order_hash(bundle.classes), "manifest_hashes": dict(bundle.metadata_hashes), "source_checkpoint": str(args.checkpoint), "source_checkpoint_sha256": sha256_file(args.checkpoint), "hls196_before_val": before, "history": history, "best_epoch": best_epoch, "best_val_top1": best_val, "final_val": final, "hyperparameters": {"epochs": args.epochs, "batch_size": args.batch_size, "workers": args.workers, "lr": args.lr, "max_train_batches": args.max_train_batches, "max_eval_batches": args.max_eval_batches}, "output": str(args.output / "best.pth"), "output_sha256": sha256_file(stage / "best.pth"), "token_mode": {"total_tokens": 196, "cls_tokens": 1, "patch_tokens": 195, "dropped_patch": 0, "mapping": "[CLS,patch1,...,patch195]"}}
        atomic_json_write(report, stage / "report.json")
        stage.replace(args.output)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
