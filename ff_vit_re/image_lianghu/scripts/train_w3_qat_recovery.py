#!/usr/bin/env python3
"""Progressive W3 QAT recovery with frozen HLS196 teacher distillation."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, RandomSampler, Subset
from torchvision import transforms
from torchvision.transforms import InterpolationMode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_fp32 import DEFAULT_VALIDATION, _evaluation_transform, _validation_provenance  # noqa: E402
from src.evaluation import ParquetValidationSource, evaluate_topk  # noqa: E402
from src.qat_recovery import (  # noqa: E402
    ProgressiveInt3QATLinear,
    active_blocks,
    all_blocks_active,
    build_recovery_student,
    distillation_loss,
    freeze_teacher,
    load_recovery_checkpoint,
    save_recovery_checkpoint,
    set_active_blocks,
)
from src.qat_weight import FrozenManifestDataset, restore_rng_state  # noqa: E402


SEED = 20260923
ACCEPTANCE_TOP1 = 67.098
DEFAULT_SOURCE = PROJECT_ROOT / "checkpoints" / "fp32_hls196.pth"
DEFAULT_CONTRACT = PROJECT_ROOT / "artifacts" / "w3_ptq" / "weight_manifest.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "metadata" / "qat_subset_seed20260923.jsonl"
DEFAULT_DIR = PROJECT_ROOT / "checkpoints" / "w3_qat_recovery"
DEFAULT_LATEST = DEFAULT_DIR / "latest.pth"
DEFAULT_BEST = DEFAULT_DIR / "best.pth"
DEFAULT_EVALUATION = PROJECT_ROOT / "reports" / "w3_qat_recovery_val50k.json"
PROBE_RECIPES = ((0.10, 1.0), (0.10, 2.0), (0.25, 2.0), (0.25, 4.0), (0.50, 2.0))


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


def epoch_active_blocks(epoch: int) -> set[int]:
    """Enable one rear-to-front block every two epochs; all active by epoch 23."""

    count = min(12, (int(epoch) + 1) // 2)
    return set(range(12 - count, 12))


def recovery_lr_multiplier(completed_epochs: int, maximum_epochs: int) -> float:
    """Hold LR through progression, then cosine-decay during all-W3 refinement."""

    if completed_epochs <= 24:
        return 1.0
    refinement = max(1, maximum_epochs - 24)
    progress = min(1.0, (completed_epochs - 24) / refinement)
    return 0.5 * (1.0 + math.cos(math.pi * progress))


def parameter_groups(model: nn.Module, weight_lr: float, scale_lr: float, decay: float):
    scales, normal = [], []
    for name, parameter in model.named_parameters():
        (scales if name.endswith("log_scale") else normal).append(parameter)
    if len(scales) != 48:
        raise ValueError(f"expected 48 scale parameters; found {len(scales)}")
    return [
        {"params": normal, "lr": weight_lr, "weight_decay": decay},
        {"params": scales, "lr": scale_lr, "weight_decay": 0.0},
    ]


def data_loader(dataset, *, epoch: int, batch_size: int, workers: int, device: torch.device):
    generator = torch.Generator().manual_seed(SEED + epoch)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        sampler=RandomSampler(dataset, generator=generator),
        num_workers=workers,
        pin_memory=device.type == "cuda",
        persistent_workers=False,
        generator=generator,
    )


def train_epoch(
    student,
    teacher,
    loader,
    optimizer,
    scaler,
    device,
    *,
    alpha: float,
    temperature: float,
    quiet: bool = False,
):
    student.train()
    teacher.eval()
    totals = {"total": 0.0, "ce": 0.0, "kd": 0.0}
    count = correct = 0
    for step, (images, labels) in enumerate(loader, 1):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.no_grad(), torch.autocast(
            device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"
        ):
            teacher_logits = teacher(images)
        with torch.autocast(
            device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"
        ):
            student_logits = student(images)
        loss, parts = distillation_loss(
            student_logits, teacher_logits, labels, alpha=alpha, temperature=temperature
        )
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        gradient_norm = torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        batch = labels.numel()
        count += batch
        correct += int((student_logits.argmax(1) == labels).sum().item())
        for name in totals:
            totals[name] += parts[name] * batch
        if not quiet:
            print(
                f"train step={step}/{len(loader)} loss={totals['total']/count:.6f} "
                f"ce={totals['ce']/count:.6f} kd={totals['kd']/count:.6f} "
                f"top1={100*correct/count:.3f}% grad_norm={float(gradient_norm):.4f}",
                flush=True,
            )
    return {
        "loss": totals["total"] / count,
        "ce": totals["ce"] / count,
        "kd": totals["kd"] / count,
        "top1_correct": correct,
        "sample_count": count,
        "top1_percent": 100.0 * correct / count,
    }


@torch.inference_mode()
def validation_metric(model, dataset, *, batch_size: int, workers: int, device: torch.device):
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
        persistent_workers=workers > 0,
    )
    model.eval()
    top1 = top5 = count = 0
    started = time.perf_counter()
    for images, labels, _ in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        with torch.autocast(
            device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"
        ):
            logits = model(images)
        predictions = logits.topk(5, 1).indices
        matches = predictions.eq(labels[:, None])
        top1 += int(matches[:, :1].any(1).sum())
        top5 += int(matches.any(1).sum())
        count += labels.numel()
    return {
        "sample_count": count,
        "top1_correct": top1,
        "top1_percent": 100.0 * top1 / count,
        "top5_correct": top5,
        "top5_percent": 100.0 * top5 / count,
        "elapsed_seconds": time.perf_counter() - started,
    }


def run_probes(args, device: torch.device) -> dict[str, object]:
    full_train = FrozenManifestDataset(args.manifest, transform=train_transform())
    train = Subset(full_train, range(min(args.probe_train_samples, len(full_train))))
    validation_source = ParquetValidationSource(
        args.validation,
        transform=_evaluation_transform(),
        provenance=_validation_provenance(args.validation, command=list(sys.argv)),
    )
    validation = Subset(validation_source, range(args.probe_validation_samples))
    teacher = freeze_teacher(args.source).to(device)
    results = []
    for index, (alpha, temperature) in enumerate(PROBE_RECIPES):
        seed_everything(SEED)
        student = build_recovery_student(args.source, args.contract).to(device)
        set_active_blocks(student, {8, 9, 10, 11})
        optimizer = torch.optim.AdamW(
            parameter_groups(student, args.weight_lr, args.scale_lr, args.weight_decay)
        )
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
        trained = train_epoch(
            student,
            teacher,
            data_loader(train, epoch=1, batch_size=args.batch_size, workers=args.workers, device=device),
            optimizer,
            scaler,
            device,
            alpha=alpha,
            temperature=temperature,
            quiet=True,
        )
        metric = validation_metric(
            student, validation, batch_size=args.eval_batch_size, workers=args.workers, device=device
        )
        row = {"index": index, "alpha": alpha, "temperature": temperature,
               "active_blocks": [8, 9, 10, 11], "train": trained, "validation": metric}
        results.append(row)
        print(json.dumps({"probe": row}, sort_keys=True), flush=True)
        del student, optimizer, scaler
        if device.type == "cuda":
            torch.cuda.empty_cache()
    best = max(results, key=lambda row: (row["validation"]["top1_percent"], -row["train"]["kd"]))
    summary = {"probe_train_samples": len(train), "probe_validation_samples": len(validation),
               "results": results, "selected": {"alpha": best["alpha"],
               "temperature": best["temperature"]}}
    print(json.dumps({"probe_summary": summary}, indent=2, sort_keys=True), flush=True)
    return summary


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("probe", "train", "evaluate", "all"), default="all")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--latest", type=Path, default=DEFAULT_LATEST)
    parser.add_argument("--best", type=Path, default=DEFAULT_BEST)
    parser.add_argument("--evaluation-output", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--epochs", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=384)
    parser.add_argument("--eval-batch-size", type=int, default=512)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--weight-lr", type=float, default=2e-5)
    parser.add_argument("--scale-lr", type=float, default=5e-4)
    parser.add_argument("--weight-decay", type=float, default=0.02)
    parser.add_argument("--alpha", type=float, default=0.10)
    parser.add_argument("--temperature", type=float, default=2.0)
    parser.add_argument("--probe-train-samples", type=int, default=2048)
    parser.add_argument("--probe-validation-samples", type=int, default=5000)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = _args()
    if not 24 <= args.epochs <= 32:
        raise ValueError("recovery training must use 24-32 epochs")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable")
    seed_everything(SEED)
    torch.set_float32_matmul_precision("highest")
    inputs = {"source": args.source, "contract": args.contract, "manifest": args.manifest}
    recipe = {
        "alpha": args.alpha,
        "temperature": args.temperature,
        "progression": "one rear-to-front block every two epochs; all 12 active from epoch 23",
        "maximum_epochs": args.epochs,
        "validation_interval_epochs": 2,
        "early_stop_non_improving_validations": 4,
        "acceptance_top1_percent": ACCEPTANCE_TOP1,
    }

    if args.mode == "probe":
        run_probes(args, device)
        return 0

    if args.mode in {"train", "all"}:
        train_set = FrozenManifestDataset(args.manifest, transform=train_transform())
        validation = ParquetValidationSource(
            args.validation,
            transform=_evaluation_transform(),
            provenance=_validation_provenance(args.validation, command=list(sys.argv)),
        )
        teacher = freeze_teacher(args.source).to(device)
        if args.latest.exists():
            student, payload = load_recovery_checkpoint(args.latest, expected_inputs=inputs)
            if payload.get("recipe") != recipe:
                raise ValueError("recovery resume recipe mismatch")
            start_epoch = int(payload["epoch"]) + 1
            history = list(payload["history"])
            best_metric = float(payload["best_metric"])
        else:
            student = build_recovery_student(args.source, args.contract)
            payload = None
            start_epoch, history, best_metric = 1, [], -1.0
        student.to(device)
        optimizer = torch.optim.AdamW(
            parameter_groups(student, args.weight_lr, args.scale_lr, args.weight_decay)
        )
        scheduler = torch.optim.lr_scheduler.LambdaLR(
            optimizer, lr_lambda=lambda step: recovery_lr_multiplier(step, args.epochs)
        )
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
        if payload is not None:
            optimizer.load_state_dict(payload["optimizer_state"])
            scheduler.load_state_dict(payload["scheduler_state"])
            scaler.load_state_dict(payload["scaler_state"])
            restore_rng_state(payload["rng_state"])
        non_improving = 0
        for prior in reversed(history):
            if prior.get("official_ready"):
                if prior.get("improved"):
                    break
                non_improving += 1
        stopped_for_acceptance = False
        for epoch in range(start_epoch, args.epochs + 1):
            blocks = epoch_active_blocks(epoch)
            set_active_blocks(student, blocks)
            lrs = [float(group["lr"]) for group in optimizer.param_groups]
            trained = train_epoch(
                student,
                teacher,
                data_loader(train_set, epoch=epoch, batch_size=args.batch_size,
                            workers=args.workers, device=device),
                optimizer,
                scaler,
                device,
                alpha=args.alpha,
                temperature=args.temperature,
            )
            scheduler.step()
            row = {"epoch": epoch, "active_blocks": sorted(blocks), "weight_lr": lrs[0],
                   "scale_lr": lrs[1], "train": trained, "official_ready": len(blocks) == 12}
            if epoch % 2 == 0:
                selected = validation_metric(
                    student, validation, batch_size=args.eval_batch_size,
                    workers=args.workers, device=device
                )
                if selected["sample_count"] != 50_000:
                    raise ValueError("recovery selection requires all 50,000 validation samples")
                row["validation_selection"] = selected
                improved = len(blocks) == 12 and selected["top1_percent"] > best_metric
                row["improved"] = improved
                if len(blocks) == 12:
                    if improved:
                        best_metric = selected["top1_percent"]
                        non_improving = 0
                    else:
                        non_improving += 1
            history.append(row)
            save_recovery_checkpoint(
                args.latest, model=student, optimizer=optimizer, scheduler=scheduler,
                scaler=scaler, epoch=epoch, best_metric=best_metric, history=history,
                inputs=inputs, recipe=recipe
            )
            if row.get("improved"):
                save_recovery_checkpoint(
                    args.best, model=student, optimizer=optimizer, scheduler=scheduler,
                    scaler=scaler, epoch=epoch, best_metric=best_metric, history=history,
                    inputs=inputs, recipe=recipe
                )
            print(json.dumps({"epoch_result": row, "best_metric": best_metric,
                              "non_improving": non_improving}, sort_keys=True), flush=True)
            if row.get("official_ready") and row.get("validation_selection", {}).get(
                "top1_percent", -1.0
            ) >= ACCEPTANCE_TOP1:
                stopped_for_acceptance = True
                print(json.dumps({"acceptance_candidate": True, "epoch": epoch,
                                  "top1_percent": row["validation_selection"]["top1_percent"]}),
                      flush=True)
                break
            if len(blocks) == 12 and non_improving >= 4:
                print(json.dumps({"early_stop": True, "epoch": epoch,
                                  "non_improving_validations": non_improving}), flush=True)
                break
        print(json.dumps({"training_complete": True, "best_metric": best_metric,
                          "stopped_for_acceptance": stopped_for_acceptance}, sort_keys=True), flush=True)
        del student, teacher, optimizer, scheduler, scaler
        if device.type == "cuda":
            torch.cuda.empty_cache()

    if args.mode in {"evaluate", "all"}:
        model, payload = load_recovery_checkpoint(
            args.best, expected_inputs=inputs, require_all_active=True
        )
        validation = ParquetValidationSource(
            args.validation,
            transform=_evaluation_transform(),
            provenance=_validation_provenance(args.validation, command=list(sys.argv)),
        )
        result = evaluate_topk(
            model, validation, output_path=args.evaluation_output,
            batch_size=args.eval_batch_size, workers=args.workers, device=device, resume=True
        )
        print(json.dumps({"best_epoch": payload["epoch"], "evaluation": {
            key: result[key] for key in ("sample_count", "top1_correct", "top1_percent",
                                         "top5_correct", "top5_percent", "timing")
        }}, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
