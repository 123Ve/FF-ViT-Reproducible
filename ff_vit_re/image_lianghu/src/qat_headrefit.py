"""Strict parameter boundary for final norm/head-only W3 recovery."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn

from .qat_recovery import ProgressiveInt3QATLinear
from .qat_weight import export_qat_integer_state


TRAINABLE_NAMES = (
    "vit.head.bias",
    "vit.head.weight",
    "vit.norm.bias",
    "vit.norm.weight",
)


def configure_headrefit(model: nn.Module) -> tuple[str, ...]:
    """Freeze the model except its final normalization and classifier."""
    allowed = set(TRAINABLE_NAMES)
    found = set()
    for name, parameter in model.named_parameters():
        enabled = name in allowed
        parameter.requires_grad_(enabled)
        if enabled:
            found.add(name)
    if found != allowed:
        raise ValueError(f"head-refit trainable parameter mismatch: {sorted(found)}")
    return tuple(sorted(found))


def configure_activation_headrefit(
    model: nn.Module, controller: nn.Module
) -> tuple[str, ...]:
    """Freeze activation-QAT state while fitting only final norm/classifier.

    The activation controller is intentionally separate from ``model`` in the
    MLP-QAT implementation, so ``configure_headrefit`` alone cannot freeze its
    learned boundary scales.
    """

    trainable = configure_headrefit(model)
    for parameter in controller.parameters():
        parameter.requires_grad_(False)
    if any(parameter.requires_grad for parameter in controller.parameters()):
        raise ValueError("activation head refit left a controller scale trainable")
    return trainable


def w3_snapshot(model: nn.Module) -> dict[str, Any]:
    tensors = {}
    modules = 0
    for name, module in model.named_modules():
        if isinstance(module, ProgressiveInt3QATLinear):
            modules += 1
            tensors[f"{name}.weight"] = module.weight.detach().cpu().clone()
            tensors[f"{name}.log_scale"] = module.log_scale.detach().cpu().clone()
            tensors[f"{name}._quant_enabled"] = module._quant_enabled.detach().cpu().clone()
    if modules != 48:
        raise ValueError(f"expected 48 W3 modules; found {modules}")
    exported = export_qat_integer_state(model)
    return {"tensors": tensors, "integer_export": exported}


def assert_w3_unchanged(model: nn.Module, snapshot: dict[str, Any]) -> None:
    state = model.state_dict()
    for name, expected in snapshot["tensors"].items():
        if not torch.equal(state[name].detach().cpu(), expected):
            raise ValueError(f"head refit changed frozen W3 state: {name}")
    actual = export_qat_integer_state(model)
    expected_export = snapshot["integer_export"]
    if set(actual) != set(expected_export):
        raise ValueError("head refit changed W3 export membership")
    for name, item in actual.items():
        expected = expected_export[name]
        if (
            item["qmin"] != expected["qmin"]
            or item["qmax"] != expected["qmax"]
            or item["segments"] != expected["segments"]
            or item["code_sha256"] != expected["code_sha256"]
            or not torch.equal(item["code"], expected["code"])
            or not torch.equal(item["scales"], expected["scales"])
        ):
            raise ValueError(f"head refit changed frozen W3 export: {name}")
