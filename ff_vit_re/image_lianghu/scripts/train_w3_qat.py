#!/usr/bin/env python3
"""Train and evaluate signed-W3 weight QAT on the fixed ImageNet-1K subset."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, RandomSampler
from torchvision import transforms
from torchvision.transforms import InterpolationMode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_fp32 import DEFAULT_VALIDATION, _evaluation_transform, _validation_provenance  # noqa: E402
from src.evaluation import ParquetValidationSource, evaluate_topk  # noqa: E402
from src.qat_weight import (  # noqa: E402
    FrozenManifestDataset,
    Int3QATLinear,
    build_w3_qat,
    load_qat_checkpoint,
    restore_training_state,
    save_qat_checkpoint,
)


SEED = 20260923
EPOCHS = 8
DEFAULT_SOURCE = PROJECT_ROOT / "checkpoints" / "fp32_hls196.pth"
DEFAULT_CONTRACT = PROJECT_ROOT / "artifacts" / "w3_ptq" / "weight_manifest.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "metadata" / "qat_subset_seed20260923.jsonl"
DEFAULT_LATEST = PROJECT_ROOT / "checkpoints" / "w3_qat" / "latest.pth"
DEFAULT_BEST = PROJECT_ROOT / "checkpoints" / "w3_qat" / "best.pth"
DEFAULT_EVALUATION = PROJECT_ROOT / "reports" / "w3_qat_val50k.json"


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def train_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(
                224, scale=(0.75, 1.0), interpolation=InterpolationMode.BICUBIC
            ),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
            ),
        ]
    )


def parameter_groups(model: nn.Module, weight_lr: float, scale_lr: float, decay: float):
    scales, normal = [], []
    for name, parameter in model.named_parameters():
        (scales if name.endswith("log_scale") else normal).append(parameter)
    if len(scales) != 48:
        raise ValueError(f"expected 48 learnable log-scales; found {len(scales)}")
    return [
        {"params": normal, "lr": weight_lr, "weight_decay": decay},
        {"params": scales, "lr": scale_lr, "weight_decay": 0.0},
    ]


def epoch_loader(dataset, *, epoch: int, batch_size: int, workers: int, device: torch.device):
    generator = torch.Generator().manual_seed(SEED + epoch)
    sampler = RandomSampler(dataset, replacement=False, generator=generator)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        sampler=sampler,
        num_workers=workers,
        pin_memory=device.type == "cuda",
        persistent_workers=False,
        generator=generator,
    )


def train_epoch(model, loader, optimizer, scaler, device):
    model.train()
    criterion = nn.CrossEntropyLoss()
    total = correct = 0
    loss_sum = 0.0
    for step, (images, labels) in enumerate(loader, 1):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(
            device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"
        ):
            logits = model(images)
            loss = criterion(logits, labels)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        batch = labels.numel()
        total += batch
        correct += int((logits.argmax(1) == labels).sum().item())
        loss_sum += float(loss.item()) * batch
        print(
            f"train step={step}/{len(loader)} loss={loss_sum/total:.6f} "
            f"top1={100*correct/total:.3f}% grad_norm={float(gradient_norm):.4f}",
            flush=True,
        )
    return {"loss": loss_sum / total, "top1_correct": correct, "sample_count": total,
            "top1_percent": 100.0 * correct / total}


@torch.inference_mode()
def selection_metric(model, source, *, batch_size: int, workers: int, device: torch.device):
    loader = DataLoader(
        source,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
        persistent_workers=workers > 0,
    )
    model.eval()
    top1 = top5 = total = 0
    started = time.perf_counter()
    for images, labels, _ in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        with torch.autocast(
            device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"
        ):
            logits = model(images)
        predictions = logits.topk(5, dim=1).indices
        matches = predictions.eq(labels[:, None])
        top1 += int(matches[:, :1].any(dim=1).sum().item())
        top5 += int(matches.any(dim=1).sum().item())
        total += labels.numel()
    if total != 50_000:
        raise ValueError(f"selection metric requires all 50,000 images; found {total}")
    elapsed = time.perf_counter() - started
    return {
        "sample_count": total,
        "top1_correct": top1,
        "top1_percent": 100.0 * top1 / total,
        "top5_correct": top5,
        "top5_percent": 100.0 * top5 / total,
        "elapsed_seconds": elapsed,
    }


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "train", "evaluate", "all"), default="all")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--latest", type=Path, default=DEFAULT_LATEST)
    parser.add_argument("--best", type=Path, default=DEFAULT_BEST)
    parser.add_argument("--evaluation-output", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--eval-batch-size", type=int, default=512)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--weight-lr", type=float, default=2e-5)
    parser.add_argument("--scale-lr", type=float, default=5e-4)
    parser.add_argument("--weight-decay", type=float, default=0.02)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _args()
    if args.epochs != EPOCHS:
        raise ValueError("official Task 4 training requires exactly 8 epochs")
    if args.batch_size <= 0 or args.eval_batch_size <= 0 or args.workers < 0:
        raise ValueError("batch sizes must be positive and workers nonnegative")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable")
    seed_everything(SEED)
    torch.set_float32_matmul_precision("highest")
    inputs = {"source": args.source, "contract": args.contract, "manifest": args.manifest}

    if args.mode == "smoke":
        model = build_w3_qat(args.source, args.contract).to(device)
        dataset = FrozenManifestDataset(args.manifest, transform=train_transform())
        loader = epoch_loader(dataset, epoch=1, batch_size=min(8, args.batch_size), workers=0, device=device)
        images, labels = next(iter(loader))
        torch.cuda.reset_peak_memory_stats(device) if device.type == "cuda" else None
        started = time.perf_counter()
        with torch.no_grad(), torch.autocast(
            device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"
        ):
            logits = model(images.to(device))
        print(json.dumps({"samples": labels.numel(), "shape": list(logits.shape),
                          "finite": bool(torch.isfinite(logits).all()),
                          "seconds": time.perf_counter() - started,
                          "peak_cuda_memory_bytes": torch.cuda.max_memory_allocated(device)
                          if device.type == "cuda" else None}, sort_keys=True))
        return 0

    if args.mode in {"train", "all"}:
        dataset = FrozenManifestDataset(args.manifest, transform=train_transform())
        validation = ParquetValidationSource(
            args.validation,
            transform=_evaluation_transform(),
            provenance=_validation_provenance(args.validation, command=list(sys.argv)),
        )
        if args.latest.exists() and not args.fresh:
            model, payload = load_qat_checkpoint(args.latest, expected_inputs=inputs)
            start_epoch = int(payload["epoch"]) + 1
            history = list(payload["history"])
            best_metric = float(payload["best_metric"])
        else:
            model = build_w3_qat(args.source, args.contract)
            payload = None
            start_epoch = 1
            history = []
            best_metric = -1.0
        model.to(device)
        optimizer = torch.optim.AdamW(
            parameter_groups(model, args.weight_lr, args.scale_lr, args.weight_decay)
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
        if payload is not None:
            restore_training_state(payload, optimizer, scheduler, scaler)
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        training_started = time.perf_counter()
        for epoch in range(start_epoch, args.epochs + 1):
            before_lr = [float(group["lr"]) for group in optimizer.param_groups]
            trained = train_epoch(
                model,
                epoch_loader(dataset, epoch=epoch, batch_size=args.batch_size,
                             workers=args.workers, device=device),
                optimizer,
                scaler,
                device,
            )
            selected = selection_metric(
                model, validation, batch_size=args.eval_batch_size, workers=args.workers, device=device
            )
            scheduler.step()
            row = {
                "epoch": epoch,
                "weight_lr": before_lr[0],
                "scale_lr": before_lr[1],
                "train": trained,
                "validation_selection": selected,
            }
            history.append(row)
            improved = selected["top1_percent"] > best_metric
            if improved:
                best_metric = selected["top1_percent"]
            save_qat_checkpoint(
                args.latest,
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                scaler=scaler,
                epoch=epoch,
                best_metric=best_metric,
                history=history,
                inputs=inputs,
            )
            if improved:
                save_qat_checkpoint(
                    args.best,
                    model=model,
                    optimizer=optimizer,
                    scheduler=scheduler,
                    scaler=scaler,
                    epoch=epoch,
                    best_metric=best_metric,
                    history=history,
                    inputs=inputs,
                )
            print(json.dumps(row, sort_keys=True), flush=True)
        print(json.dumps({"training_seconds": time.perf_counter() - training_started,
                          "best_metric": best_metric,
                          "peak_cuda_memory_bytes": torch.cuda.max_memory_allocated(device)
                          if device.type == "cuda" else None}, sort_keys=True), flush=True)
        del model, optimizer, scheduler, scaler
        if device.type == "cuda":
            torch.cuda.empty_cache()

    if args.mode in {"evaluate", "all"}:
        model, payload = load_qat_checkpoint(args.best, expected_inputs=inputs)
        source = ParquetValidationSource(
            args.validation,
            transform=_evaluation_transform(),
            provenance=_validation_provenance(args.validation, command=list(sys.argv)),
        )
        result = evaluate_topk(
            model,
            source,
            output_path=args.evaluation_output,
            batch_size=args.eval_batch_size,
            workers=args.workers,
            device=device,
            resume=True,
        )
        print(json.dumps({"best_epoch": payload["epoch"], "evaluation": {
            key: result[key] for key in ("sample_count", "top1_correct", "top1_percent",
                                         "top5_correct", "top5_percent", "timing")
        }}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
