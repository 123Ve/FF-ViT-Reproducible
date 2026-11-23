"""Read-only adapters to the accepted HLS196 and W3 QAT implementations."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import torch
from torch import nn

from .contract import load_contract, validate_mainline_contract


LEGACY_ROOT = Path("/home/user/Desktop/ff_vit_re/image_lianghu/src")
_LEGACY_PACKAGE = "_ffvit_imagenet_legacy_readonly"


def legacy_module(name: str) -> Any:
    """Import an unmodified legacy module under an isolated package name."""

    if not name.isidentifier() or name.startswith("_"):
        raise ValueError(f"invalid legacy module name: {name!r}")
    if _LEGACY_PACKAGE not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            _LEGACY_PACKAGE,
            LEGACY_ROOT / "__init__.py",
            submodule_search_locations=[str(LEGACY_ROOT)],
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load legacy package at {LEGACY_ROOT}")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_LEGACY_PACKAGE] = package
        try:
            spec.loader.exec_module(package)
        except BaseException:
            del sys.modules[_LEGACY_PACKAGE]
            raise
    return importlib.import_module(f"{_LEGACY_PACKAGE}.{name}")


def load_hls196_fp32(checkpoint: str | Path, *, device: str | torch.device = "cpu") -> nn.Module:
    """Load the HLS196 wrapper without copying or rewriting its checkpoint."""

    model = legacy_module("modeling").load_deit_checkpoint(checkpoint, device=device)
    if model._ffvit_token_layout != legacy_module("modeling").HLS196_TOKEN_LAYOUT:
        raise ValueError("source checkpoint does not implement HLS196 token identity")
    model.eval()
    return model


def load_w3_parent(
    checkpoint: str | Path,
    *,
    contract: str | Path,
    device: str | torch.device = "cpu",
) -> tuple[nn.Module, dict[str, Any]]:
    """Validate mainline widths, then strictly restore the accepted head-refit W3 parent."""

    validate_mainline_contract(load_contract(contract))
    model, payload = legacy_module("mlp_activation_quant").load_headrefit_w3_checkpoint(
        checkpoint
    )
    if model._ffvit_token_layout != legacy_module("modeling").HLS196_TOKEN_LAYOUT:
        raise ValueError("W3 parent lost HLS196 token identity")
    model.to(device).eval()
    return model, payload
