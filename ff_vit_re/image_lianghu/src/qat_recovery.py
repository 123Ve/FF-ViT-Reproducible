"""Progressive signed-W3 QAT recovery with frozen-teacher distillation."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from torch import nn

from .modeling import HLS196DeiT, HLS196_TOKEN_LAYOUT, load_deit_checkpoint, sha256_file
from .qat_weight import (
    Int3QATLinear,
    NUMERIC_MODE,
    _file_record,
    _rng_state,
    export_qat_integer_state,
)


RECOVERY_SCHEMA = "imagenet1k.ffvit.w3_qat_recovery_checkpoint.v1"


class ProgressiveInt3QATLinear(Int3QATLinear):
    """An Int3 QAT layer that can temporarily execute its exact FP32 master."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.register_buffer("_quant_enabled", torch.tensor(False, dtype=torch.bool))

    @property
    def quant_enabled(self) -> bool:
        return bool(self._quant_enabled.item())

    def set_quant_enabled(self, enabled: bool) -> None:
        self._quant_enabled.fill_(bool(enabled))

    @classmethod
    def from_qat(cls, module: Int3QATLinear) -> "ProgressiveInt3QATLinear":
        result = cls(
            module.in_features,
            module.out_features,
            bias=module.bias is not None,
            segments=module.segments,
        )
        with torch.no_grad():
            result.weight.copy_(module.weight)
            if module.bias is not None:
                result.bias.copy_(module.bias)
            result.log_scale.copy_(module.log_scale)
        return result

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        weight = self.fake_quant_weight() if self.quant_enabled else self.weight
        return F.linear(value, weight, self.bias)


def _replace_qat_children(module: nn.Module) -> None:
    for name, child in list(module.named_children()):
        if isinstance(child, Int3QATLinear) and not isinstance(child, ProgressiveInt3QATLinear):
            setattr(module, name, ProgressiveInt3QATLinear.from_qat(child))
        else:
            _replace_qat_children(child)


def build_recovery_student(source: str | Path, contract: str | Path) -> HLS196DeiT:
    from .qat_weight import build_w3_qat

    model = build_w3_qat(source, contract)
    _replace_qat_children(model)
    if sum(isinstance(module, ProgressiveInt3QATLinear) for module in model.modules()) != 48:
        raise ValueError("recovery student must contain exactly 48 progressive QAT modules")
    set_active_blocks(model, set())
    return model


def _module_block(name: str) -> int:
    parts = name.split(".")
    if len(parts) < 4 or parts[:2] != ["vit", "blocks"]:
        raise ValueError(f"cannot identify transformer block for {name}")
    return int(parts[2])


def set_active_blocks(model: nn.Module, blocks: set[int]) -> None:
    if any(not isinstance(block, int) or isinstance(block, bool) or not 0 <= block < 12 for block in blocks):
        raise ValueError("active blocks must be integers in [0, 11]")
    found = 0
    for name, module in model.named_modules():
        if isinstance(module, ProgressiveInt3QATLinear):
            module.set_quant_enabled(_module_block(name) in blocks)
            found += 1
    if found != 48:
        raise ValueError(f"expected 48 progressive QAT modules; found {found}")


def active_blocks(model: nn.Module) -> list[int]:
    active = set()
    for name, module in model.named_modules():
        if isinstance(module, ProgressiveInt3QATLinear) and module.quant_enabled:
            active.add(_module_block(name))
    return sorted(active)


def all_blocks_active(model: nn.Module) -> bool:
    modules = [module for module in model.modules() if isinstance(module, ProgressiveInt3QATLinear)]
    return len(modules) == 48 and all(module.quant_enabled for module in modules)


def freeze_teacher(source: str | Path) -> HLS196DeiT:
    teacher = load_deit_checkpoint(source, device="cpu")
    if not isinstance(teacher, HLS196DeiT):
        raise ValueError("distillation teacher must use HLS196 semantics")
    teacher.eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    return teacher


def distillation_loss(
    student_logits: torch.Tensor,
    teacher_logits: torch.Tensor,
    labels: torch.Tensor,
    *,
    alpha: float,
    temperature: float,
) -> tuple[torch.Tensor, dict[str, float]]:
    """Return alpha*CE + (1-alpha)*T^2*KL with finite-value validation."""

    if not 0.0 <= alpha <= 1.0 or temperature <= 0.0:
        raise ValueError("alpha must be in [0,1] and temperature must be positive")
    ce = F.cross_entropy(student_logits.float(), labels)
    kd = F.kl_div(
        F.log_softmax(student_logits.float() / temperature, dim=1),
        F.softmax(teacher_logits.detach().float() / temperature, dim=1),
        reduction="batchmean",
    ) * temperature * temperature
    loss = alpha * ce + (1.0 - alpha) * kd
    if not bool(torch.isfinite(loss)):
        raise ValueError("non-finite distillation loss")
    return loss, {"ce": float(ce.detach()), "kd": float(kd.detach()), "total": float(loss.detach())}


def _validate_export(model: nn.Module, stored: Any) -> None:
    actual = export_qat_integer_state(model)
    if not isinstance(stored, Mapping) or set(stored) != set(actual):
        raise ValueError("recovery integer export is missing or incomplete")
    for name, expected in actual.items():
        item = stored[name]
        if (
            item.get("qmin") != -4
            or item.get("qmax") != 3
            or item.get("segments") != expected["segments"]
            or item.get("code_sha256") != expected["code_sha256"]
            or not torch.equal(item.get("code"), expected["code"])
            or not torch.equal(item.get("scales"), expected["scales"])
        ):
            raise ValueError(f"recovery integer export mismatch: {name}")


def save_recovery_checkpoint(
    path: str | Path,
    *,
    model: HLS196DeiT,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    scaler: Any,
    epoch: int,
    best_metric: float,
    history: Sequence[Mapping[str, Any]],
    inputs: Mapping[str, str | Path],
    recipe: Mapping[str, Any],
) -> dict[str, Any]:
    records = {name: _file_record(value) for name, value in inputs.items()}
    payload = {
        "schema": RECOVERY_SCHEMA,
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": NUMERIC_MODE,
        "epoch": int(epoch),
        "best_metric": float(best_metric),
        "history": [dict(item) for item in history],
        "inputs": records,
        "recipe": dict(recipe),
        "active_blocks": active_blocks(model),
        "model_state": {name: value.detach().cpu() for name, value in model.state_dict().items()},
        "optimizer_state": optimizer.state_dict(),
        "scheduler_state": scheduler.state_dict(),
        "scaler_state": scaler.state_dict(),
        "rng_state": _rng_state(),
        "integer_export": export_qat_integer_state(model),
    }
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    try:
        torch.save(payload, temporary)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def _verify_inputs(recorded: Mapping[str, Any], expected: Mapping[str, str | Path]) -> None:
    if set(recorded) != set(expected):
        raise ValueError("recovery checkpoint input provenance key mismatch")
    for name, path in expected.items():
        if dict(recorded[name]) != _file_record(path):
            raise ValueError(f"recovery checkpoint input provenance mismatch: {name}")


def load_recovery_checkpoint(
    path: str | Path,
    *,
    expected_inputs: Mapping[str, str | Path] | None = None,
    require_all_active: bool = False,
) -> tuple[HLS196DeiT, dict[str, Any]]:
    checkpoint = Path(path).expanduser().resolve()
    try:
        payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, TypeError) as error:
        raise ValueError(f"cannot safe-load recovery checkpoint: {checkpoint}") from error
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema") != RECOVERY_SCHEMA
        or payload.get("token_layout") != HLS196_TOKEN_LAYOUT
    ):
        raise ValueError("recovery checkpoint schema or HLS196 layout mismatch")
    recorded = payload.get("inputs")
    if not isinstance(recorded, Mapping) or not {"source", "contract"}.issubset(recorded):
        raise ValueError("recovery checkpoint input provenance is missing")
    expected = expected_inputs or {name: item["path"] for name, item in recorded.items()}
    _verify_inputs(recorded, expected)
    model = build_recovery_student(recorded["source"]["path"], recorded["contract"]["path"])
    try:
        model.load_state_dict(payload["model_state"], strict=True)
    except (KeyError, RuntimeError, TypeError) as error:
        raise ValueError(f"recovery model state is incompatible: {error}") from error
    if active_blocks(model) != payload.get("active_blocks"):
        raise ValueError("recovery active-block metadata mismatch")
    if require_all_active and not all_blocks_active(model):
        raise ValueError("official recovery evaluation requires all 12 blocks active")
    _validate_export(model, payload.get("integer_export"))
    model.evaluation_provenance = {
        "checkpoint_sha256": sha256_file(checkpoint),
        "source_checkpoint_sha256": recorded["source"]["sha256"],
        "quant_contract_sha256": recorded["contract"]["sha256"],
        "training_manifest_sha256": recorded.get("manifest", {}).get("sha256"),
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": NUMERIC_MODE,
        "recovery": True,
    }
    model.eval()
    return model, dict(payload)
