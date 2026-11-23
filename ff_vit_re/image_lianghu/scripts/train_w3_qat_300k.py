#!/usr/bin/env python3
"""Four-epoch W3 QAT continuation on the deterministic ImageNet-1K 300k subset."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_fp32 import DEFAULT_VALIDATION, _evaluation_transform, _validation_provenance  # noqa: E402
from scripts.train_w3_qat_recovery import (  # noqa: E402
    ACCEPTANCE_TOP1,
    data_loader,
    parameter_groups,
    seed_everything,
    train_epoch,
    train_transform,
    validation_metric,
)
from src.evaluation import ParquetValidationSource, evaluate_topk  # noqa: E402
from src.qat_recovery import (  # noqa: E402
    freeze_teacher,
    load_recovery_checkpoint,
    save_recovery_checkpoint,
    set_active_blocks,
)
from src.qat_weight import FrozenManifestDataset, restore_rng_state  # noqa: E402


SEED = 20260923
EPOCHS = 4
DEFAULT_SOURCE = PROJECT_ROOT / "checkpoints" / "fp32_hls196.pth"
DEFAULT_CONTRACT = PROJECT_ROOT / "artifacts" / "w3_ptq" / "weight_manifest.json"
DEFAULT_100K = PROJECT_ROOT / "metadata" / "qat_subset100_seed20260923.jsonl"
DEFAULT_300K = PROJECT_ROOT / "metadata" / "qat_subset300_seed20260923.jsonl"
DEFAULT_100K_PARENT = PROJECT_ROOT / "checkpoints" / "w3_qat_recovery" / "best.pth"
DEFAULT_INITIAL = PROJECT_ROOT / "checkpoints" / "w3_qat_100k" / "best.pth"
DEFAULT_DIR = PROJECT_ROOT / "checkpoints" / "w3_qat_300k"
DEFAULT_LATEST = DEFAULT_DIR / "latest.pth"
DEFAULT_BEST = DEFAULT_DIR / "best.pth"
DEFAULT_EVALUATION = PROJECT_ROOT / "reports" / "w3_qat_300k_val50k.json"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("train", "evaluate", "all"), default="all")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--manifest100k", type=Path, default=DEFAULT_100K)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_300K)
    parser.add_argument("--initial100k-parent", type=Path, default=DEFAULT_100K_PARENT)
    parser.add_argument("--initial-checkpoint", type=Path, default=DEFAULT_INITIAL)
    parser.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--latest", type=Path, default=DEFAULT_LATEST)
    parser.add_argument("--best", type=Path, default=DEFAULT_BEST)
    parser.add_argument("--evaluation-output", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch-size", type=int, default=384)
    parser.add_argument("--eval-batch-size", type=int, default=512)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--weight-lr", type=float, default=7.5e-6)
    parser.add_argument("--scale-lr", type=float, default=1.875e-4)
    parser.add_argument("--weight-decay", type=float, default=0.02)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = _args()
    if args.epochs != EPOCHS:
        raise ValueError("the approved 300k continuation has a fixed four-epoch maximum")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable")
    seed_everything(SEED)
    torch.set_float32_matmul_precision("highest")
    inputs = {
        "source": args.source,
        "contract": args.contract,
        "manifest": args.manifest,
        "initial_checkpoint": args.initial_checkpoint,
    }
    recipe = {
        "branch": "continue_all48_from_100k_best",
        "alpha": 0.10,
        "temperature": 2.0,
        "weight_lr": args.weight_lr,
        "scale_lr": args.scale_lr,
        "weight_decay": args.weight_decay,
        "epochs": EPOCHS,
        "scheduler": "cosine_annealing",
        "acceptance_top1_percent": ACCEPTANCE_TOP1,
    }

    if args.mode in {"train", "all"}:
        train_set = FrozenManifestDataset(
            args.manifest, transform=train_transform(), expected_count=300_000
        )
        validation = ParquetValidationSource(
            args.validation,
            transform=_evaluation_transform(),
            provenance=_validation_provenance(args.validation, command=list(sys.argv)),
        )
        teacher = freeze_teacher(args.source).to(device)
        if args.latest.exists():
            student, payload = load_recovery_checkpoint(args.latest, expected_inputs=inputs)
            if payload.get("recipe") != recipe:
                raise ValueError("300k continuation resume recipe mismatch")
            start_epoch = int(payload["epoch"]) + 1
            history = list(payload["history"])
            best_metric = float(payload["best_metric"])
        else:
            old_inputs = {
                "source": args.source,
                "contract": args.contract,
                "manifest": args.manifest100k,
                "initial_checkpoint": args.initial100k_parent,
            }
            student, _ = load_recovery_checkpoint(
                args.initial_checkpoint, expected_inputs=old_inputs, require_all_active=True
            )
            start_epoch, history, best_metric, payload = 1, [], -1.0, None
        set_active_blocks(student, set(range(12)))
        student.to(device)
        optimizer = torch.optim.AdamW(
            parameter_groups(student, args.weight_lr, args.scale_lr, args.weight_decay)
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
        if payload is not None:
            optimizer.load_state_dict(payload["optimizer_state"])
            scheduler.load_state_dict(payload["scheduler_state"])
            scaler.load_state_dict(payload["scaler_state"])
            restore_rng_state(payload["rng_state"])

        for epoch in range(start_epoch, EPOCHS + 1):
            epoch_started = time.monotonic()
            lrs = [float(group["lr"]) for group in optimizer.param_groups]
            trained = train_epoch(
                student,
                teacher,
                data_loader(train_set, epoch=epoch, batch_size=args.batch_size,
                            workers=args.workers, device=device),
                optimizer,
                scaler,
                device,
                alpha=0.10,
                temperature=2.0,
                quiet=True,
            )
            selected = validation_metric(
                student, validation, batch_size=args.eval_batch_size,
                workers=args.workers, device=device
            )
            if selected["sample_count"] != 50_000:
                raise ValueError("300k continuation validation requires exactly 50,000 samples")
            scheduler.step()
            improved = selected["top1_percent"] > best_metric
            if improved:
                best_metric = selected["top1_percent"]
            row = {
                "epoch": epoch,
                "branch": recipe["branch"],
                "active_blocks": list(range(12)),
                "official_ready": True,
                "weight_lr": lrs[0],
                "scale_lr": lrs[1],
                "train": trained,
                "validation_selection": selected,
                "elapsed_seconds": time.monotonic() - epoch_started,
                "improved": improved,
            }
            history.append(row)
            save_recovery_checkpoint(
                args.latest, model=student, optimizer=optimizer, scheduler=scheduler,
                scaler=scaler, epoch=epoch, best_metric=best_metric, history=history,
                inputs=inputs, recipe=recipe
            )
            if improved:
                save_recovery_checkpoint(
                    args.best, model=student, optimizer=optimizer, scheduler=scheduler,
                    scaler=scaler, epoch=epoch, best_metric=best_metric, history=history,
                    inputs=inputs, recipe=recipe
                )
            print(json.dumps({"epoch_result": row, "best_metric": best_metric}, sort_keys=True), flush=True)
            if selected["top1_percent"] >= ACCEPTANCE_TOP1:
                print(json.dumps({"acceptance_candidate": True, "epoch": epoch,
                                  "top1_percent": selected["top1_percent"]}), flush=True)
                break
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
