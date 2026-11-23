#!/usr/bin/env python3
"""Final norm/head-only W3 recovery under the official crop09 evaluation."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

import torch
from torch.utils.data import Subset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_fp32 import DEFAULT_VALIDATION, _evaluation_transform, _validation_provenance  # noqa: E402
from scripts.train_w3_qat_recovery import (  # noqa: E402
    data_loader,
    seed_everything,
    train_epoch,
    train_transform,
    validation_metric,
)
from src.evaluation import ParquetValidationSource, evaluate_topk  # noqa: E402
from src.qat_headrefit import assert_w3_unchanged, configure_headrefit, w3_snapshot  # noqa: E402
from src.qat_recovery import (  # noqa: E402
    freeze_teacher,
    load_recovery_checkpoint,
    save_recovery_checkpoint,
)
from src.qat_weight import FrozenManifestDataset, restore_rng_state  # noqa: E402


SEED = 20260923
TARGET_TOP1 = 70.0
PARENT_TOP1 = 69.896
LRS = (1e-5, 3e-5, 1e-4)
EPOCHS = 2
DEFAULT_SOURCE = PROJECT_ROOT / "checkpoints" / "fp32_hls196.pth"
DEFAULT_CONTRACT = PROJECT_ROOT / "artifacts" / "w3_ptq" / "weight_manifest.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "metadata" / "qat_subset500_seed20260923.jsonl"
DEFAULT_PARENT_PARENT = PROJECT_ROOT / "checkpoints" / "w3_qat_300k" / "best.pth"
DEFAULT_PARENT = PROJECT_ROOT / "checkpoints" / "w3_qat_500k" / "best.pth"
DEFAULT_DIR = PROJECT_ROOT / "checkpoints" / "w3_qat_500k_headrefit"
DEFAULT_LATEST = DEFAULT_DIR / "latest.pth"
DEFAULT_BEST = DEFAULT_DIR / "best.pth"
DEFAULT_PROBE = PROJECT_ROOT / "reports" / "w3_qat_500k_headrefit_probe.json"
DEFAULT_EVALUATION = PROJECT_ROOT / "reports" / "w3_qat_500k_headrefit_val50k_official_crop09.json"


def _publish_json(path: Path, value: object) -> None:
    if os.path.lexists(path):
        raise ValueError(f"refusing to replace existing head-refit artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.staging-{uuid.uuid4().hex}"
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _optimizer(model, lr: float) -> torch.optim.AdamW:
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if len(parameters) != 4:
        raise ValueError(f"head refit requires exactly four trainable tensors; found {len(parameters)}")
    return torch.optim.AdamW(parameters, lr=lr, weight_decay=0.0)


def main() -> int:
    device = torch.device("cuda")
    if not torch.cuda.is_available():
        raise ValueError("CUDA is required for the approved head refit")
    seed_everything(SEED)
    torch.set_float32_matmul_precision("highest")
    parent_inputs = {
        "source": DEFAULT_SOURCE,
        "contract": DEFAULT_CONTRACT,
        "manifest": DEFAULT_MANIFEST,
        "initial_checkpoint": DEFAULT_PARENT_PARENT,
    }
    parent_model, _ = load_recovery_checkpoint(
        DEFAULT_PARENT, expected_inputs=parent_inputs, require_all_active=True
    )
    frozen_w3 = w3_snapshot(parent_model)
    train_set = FrozenManifestDataset(
        DEFAULT_MANIFEST, transform=train_transform(), expected_count=500_000
    )
    validation = ParquetValidationSource(
        DEFAULT_VALIDATION,
        transform=_evaluation_transform(),
        provenance=_validation_provenance(DEFAULT_VALIDATION, command=list(sys.argv)),
    )

    if DEFAULT_PROBE.exists():
        probe_record = json.loads(DEFAULT_PROBE.read_text(encoding="utf-8"))
        selected_lr = float(probe_record["selected_lr"])
    else:
        teacher = freeze_teacher(DEFAULT_SOURCE).to(device)
        probe_train = Subset(train_set, range(20_000))
        probe_validation = Subset(validation, range(5_000))
        results = []
        for lr in LRS:
            seed_everything(SEED)
            student, _ = load_recovery_checkpoint(
                DEFAULT_PARENT, expected_inputs=parent_inputs, require_all_active=True
            )
            configure_headrefit(student)
            student.to(device)
            optimizer = _optimizer(student, lr)
            scaler = torch.amp.GradScaler("cuda")
            trained = train_epoch(
                student,
                teacher,
                data_loader(probe_train, epoch=1, batch_size=384, workers=8, device=device),
                optimizer,
                scaler,
                device,
                alpha=0.10,
                temperature=2.0,
                quiet=True,
            )
            metric = validation_metric(
                student, probe_validation, batch_size=512, workers=8, device=device
            )
            assert_w3_unchanged(student, frozen_w3)
            results.append({"lr": lr, "train": trained, "validation_5k": metric})
            del student, optimizer, scaler
            torch.cuda.empty_cache()
        selected = max(
            results,
            key=lambda item: (
                item["validation_5k"]["top1_correct"],
                item["validation_5k"]["top5_correct"],
                -item["lr"],
            ),
        )
        selected_lr = float(selected["lr"])
        probe_record = {
            "schema": "imagenet1k.ffvit.w3_qat_headrefit_probe.v1",
            "seed": SEED,
            "train_subset": {"kind": "fixed_manifest_prefix", "start": 0, "stop": 20_000},
            "validation_subset": {"kind": "fixed_validation_prefix", "start": 0, "stop": 5_000},
            "selection_rule": "top1_correct, top5_correct, lower_lr",
            "results": results,
            "selected_lr": selected_lr,
        }
        _publish_json(DEFAULT_PROBE, probe_record)
        print(json.dumps({"probe": probe_record}, sort_keys=True), flush=True)
        del teacher
        torch.cuda.empty_cache()

    inputs = dict(parent_inputs)
    inputs.update({"initial_checkpoint": DEFAULT_PARENT, "probe": DEFAULT_PROBE})
    recipe = {
        "branch": "final_norm_head_only_from_500k_e7",
        "trainable_names": ["vit.head.bias", "vit.head.weight", "vit.norm.bias", "vit.norm.weight"],
        "alpha": 0.10,
        "temperature": 2.0,
        "lr": selected_lr,
        "weight_decay": 0.0,
        "epochs": EPOCHS,
        "scheduler": "cosine_annealing_tmax_2",
        "target_top1_percent": TARGET_TOP1,
        "evaluation_profile": "official_crop_pct_0.9_resize248",
    }
    teacher = freeze_teacher(DEFAULT_SOURCE).to(device)
    if DEFAULT_LATEST.exists():
        student, payload = load_recovery_checkpoint(DEFAULT_LATEST, expected_inputs=inputs)
        if payload.get("recipe") != recipe:
            raise ValueError("head-refit resume recipe mismatch")
        configure_headrefit(student)
        start_epoch = int(payload["epoch"]) + 1
        history = list(payload["history"])
        best_metric = float(payload["best_metric"])
    else:
        student, _ = load_recovery_checkpoint(
            DEFAULT_PARENT, expected_inputs=parent_inputs, require_all_active=True
        )
        configure_headrefit(student)
        start_epoch, history, best_metric, payload = 1, [], PARENT_TOP1, None
    student.to(device)
    optimizer = _optimizer(student, selected_lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    scaler = torch.amp.GradScaler("cuda")
    if payload is not None:
        optimizer.load_state_dict(payload["optimizer_state"])
        scheduler.load_state_dict(payload["scheduler_state"])
        scaler.load_state_dict(payload["scaler_state"])
        restore_rng_state(payload["rng_state"])

    for epoch in range(start_epoch, EPOCHS + 1):
        started = time.monotonic()
        lr = float(optimizer.param_groups[0]["lr"])
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
        scheduler.step()
        assert_w3_unchanged(student, frozen_w3)
        improved = selected["top1_percent"] > best_metric
        if improved:
            best_metric = selected["top1_percent"]
        row = {
            "epoch": epoch,
            "learning_rate": lr,
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

    branch_improved = DEFAULT_BEST.exists()
    evaluation_checkpoint = DEFAULT_BEST if branch_improved else DEFAULT_PARENT
    evaluation_inputs = inputs if branch_improved else parent_inputs
    model, best_payload = load_recovery_checkpoint(
        evaluation_checkpoint, expected_inputs=evaluation_inputs, require_all_active=True
    )
    assert_w3_unchanged(model, frozen_w3)
    result = evaluate_topk(
        model,
        validation,
        output_path=DEFAULT_EVALUATION,
        batch_size=512,
        workers=8,
        device=device,
        resume=False,
    )
    print(json.dumps({"evaluation_source": "branch" if branch_improved else "parent",
                      "best_epoch": best_payload["epoch"], "evaluation": {
        key: result[key] for key in ("sample_count", "top1_correct", "top1_percent",
                                     "top5_correct", "top5_percent", "timing")
    }}, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
