#!/usr/bin/env python3
"""Two-epoch W3 QAT continuation on the deterministic ImageNet-1K 700k subset."""

from __future__ import annotations

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
TARGET_TOP1 = 70.0
EPOCHS = 2
DEFAULT_SOURCE = PROJECT_ROOT / "checkpoints" / "fp32_hls196.pth"
DEFAULT_CONTRACT = PROJECT_ROOT / "artifacts" / "w3_ptq" / "weight_manifest.json"
DEFAULT_500K = PROJECT_ROOT / "metadata" / "qat_subset500_seed20260923.jsonl"
DEFAULT_700K = PROJECT_ROOT / "metadata" / "qat_subset700_seed20260923.jsonl"
DEFAULT_500K_PARENT = PROJECT_ROOT / "checkpoints" / "w3_qat_300k" / "best.pth"
DEFAULT_INITIAL = PROJECT_ROOT / "checkpoints" / "w3_qat_500k" / "best.pth"
DEFAULT_DIR = PROJECT_ROOT / "checkpoints" / "w3_qat_700k"
DEFAULT_LATEST = DEFAULT_DIR / "latest.pth"
DEFAULT_BEST = DEFAULT_DIR / "best.pth"
DEFAULT_EVALUATION = PROJECT_ROOT / "reports" / "w3_qat_700k_val50k.json"


def choose_evaluation_checkpoint(branch_best: Path, parent_best: Path) -> tuple[Path, str]:
    """Use the branch best only when this continuation actually improved."""
    return (branch_best, "branch") if branch_best.is_file() else (parent_best, "parent")


def main() -> int:
    device = torch.device("cuda")
    if not torch.cuda.is_available():
        raise ValueError("CUDA is required for the approved 700k continuation")
    seed_everything(SEED)
    torch.set_float32_matmul_precision("highest")
    inputs = {
        "source": DEFAULT_SOURCE,
        "contract": DEFAULT_CONTRACT,
        "manifest": DEFAULT_700K,
        "initial_checkpoint": DEFAULT_INITIAL,
    }
    recipe = {
        "branch": "continue_all48_from_500k_e7_best",
        "alpha": 0.10,
        "temperature": 2.0,
        "weight_lr": 2e-6,
        "scale_lr": 5e-5,
        "weight_decay": 0.02,
        "epochs": EPOCHS,
        "scheduler": "cosine_annealing_tmax_2",
        "target_top1_percent": TARGET_TOP1,
    }
    old_inputs = {
        "source": DEFAULT_SOURCE,
        "contract": DEFAULT_CONTRACT,
        "manifest": DEFAULT_500K,
        "initial_checkpoint": DEFAULT_500K_PARENT,
    }
    train_set = FrozenManifestDataset(
        DEFAULT_700K, transform=train_transform(), expected_count=700_000
    )
    validation = ParquetValidationSource(
        DEFAULT_VALIDATION,
        transform=_evaluation_transform(),
        provenance=_validation_provenance(DEFAULT_VALIDATION, command=list(sys.argv)),
    )
    teacher = freeze_teacher(DEFAULT_SOURCE).to(device)
    if DEFAULT_LATEST.exists():
        student, payload = load_recovery_checkpoint(DEFAULT_LATEST, expected_inputs=inputs)
        if payload.get("recipe") != recipe:
            raise ValueError("700k continuation resume recipe mismatch")
        start_epoch = int(payload["epoch"]) + 1
        history = list(payload["history"])
        best_metric = float(payload["best_metric"])
    else:
        student, initial_payload = load_recovery_checkpoint(
            DEFAULT_INITIAL, expected_inputs=old_inputs, require_all_active=True
        )
        start_epoch, history = 1, []
        best_metric = float(initial_payload["best_metric"])
        payload = None
    set_active_blocks(student, set(range(12)))
    student.to(device)
    optimizer = torch.optim.AdamW(parameter_groups(student, 2e-6, 5e-5, 0.02))
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    scaler = torch.amp.GradScaler("cuda")
    if payload is not None:
        optimizer.load_state_dict(payload["optimizer_state"])
        scheduler.load_state_dict(payload["scheduler_state"])
        scaler.load_state_dict(payload["scaler_state"])
        restore_rng_state(payload["rng_state"])

    for epoch in range(start_epoch, EPOCHS + 1):
        started = time.monotonic()
        lrs = [float(group["lr"]) for group in optimizer.param_groups]
        trained = train_epoch(
            student,
            teacher,
            data_loader(train_set, epoch=epoch, batch_size=384, workers=8, device=device),
            optimizer,
            scaler,
            device,
            alpha=0.10,
            temperature=2.0,
            quiet=True,
        )
        selected = validation_metric(
            student, validation, batch_size=512, workers=8, device=device
        )
        if selected["sample_count"] != 50_000:
            raise ValueError("700k continuation validation requires exactly 50,000 samples")
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
            "elapsed_seconds": time.monotonic() - started,
            "improved": improved,
        }
        history.append(row)
        save_recovery_checkpoint(
            DEFAULT_LATEST, model=student, optimizer=optimizer, scheduler=scheduler,
            scaler=scaler, epoch=epoch, best_metric=best_metric, history=history,
            inputs=inputs, recipe=recipe
        )
        if improved:
            save_recovery_checkpoint(
                DEFAULT_BEST, model=student, optimizer=optimizer, scheduler=scheduler,
                scaler=scaler, epoch=epoch, best_metric=best_metric, history=history,
                inputs=inputs, recipe=recipe
            )
        print(json.dumps({"epoch_result": row, "best_metric": best_metric}, sort_keys=True), flush=True)
        if selected["top1_percent"] >= TARGET_TOP1:
            print(json.dumps({"target_reached": True, "epoch": epoch,
                              "top1_percent": selected["top1_percent"]}), flush=True)
            break
    del student, teacher, optimizer, scheduler, scaler
    torch.cuda.empty_cache()

    evaluation_checkpoint, evaluation_source = choose_evaluation_checkpoint(
        DEFAULT_BEST, DEFAULT_INITIAL
    )
    model, best_payload = load_recovery_checkpoint(
        evaluation_checkpoint,
        expected_inputs=inputs if evaluation_source == "branch" else old_inputs,
        require_all_active=True,
    )
    result = evaluate_topk(
        model,
        validation,
        output_path=DEFAULT_EVALUATION,
        batch_size=512,
        workers=8,
        device=device,
        resume=False,
    )
    print(json.dumps({"evaluation_source": evaluation_source,
                      "best_epoch": best_payload["epoch"], "evaluation": {
        key: result[key] for key in ("sample_count", "top1_correct", "top1_percent",
                                     "top5_correct", "top5_percent", "timing")
    }}, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
