"""Strict DeiT-Tiny loading and the FF-ViT HLS196 token contract."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import uuid
from collections.abc import Mapping
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import timm
import torch
from torch import nn


ARCHITECTURE = "deit_tiny_patch16_224"
CHECKPOINT_SCHEMA = "imagenet1k.ffvit.hls196_checkpoint.v1"
SOURCE_WRAPPER_FIELDS = frozenset({"model", "epoch", "accuracy"})
HLS196_TOKEN_LAYOUT = {
    "name": "hls196_cls_patch1_to_patch195",
    "total_tokens": 196,
    "cls_tokens": 1,
    "patch_tokens": 195,
    "dropped_patch_index": 0,
    "standard_token_indices": [0, *range(2, 197)],
}
STANDARD197_TOKEN_LAYOUT = {
    "name": "standard197",
    "total_tokens": 197,
    "cls_tokens": 1,
    "patch_tokens": 196,
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_deit() -> nn.Module:
    return timm.create_model(ARCHITECTURE, pretrained=False, num_classes=1000)


def _strict_load(model: nn.Module, state: Any) -> None:
    if not isinstance(state, Mapping) or not state:
        raise ValueError("checkpoint has an incompatible state dictionary: expected a non-empty mapping")
    try:
        incompatible = model.load_state_dict(dict(state), strict=True)
    except (RuntimeError, TypeError) as error:
        raise ValueError(f"checkpoint has an incompatible state dictionary: {error}") from error
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise ValueError(
            "checkpoint has an incompatible state dictionary: "
            f"missing={incompatible.missing_keys}, unexpected={incompatible.unexpected_keys}"
        )
    if not isinstance(model.head, nn.Linear) or tuple(model.head.weight.shape) != (1000, 192):
        raise ValueError("checkpoint classifier Head must have shape (1000, 192)")


def _validate_hls_model(model: nn.Module) -> None:
    if getattr(model, "num_prefix_tokens", None) != 1:
        raise ValueError("HLS196 requires exactly one CLS prefix token")
    if getattr(model, "num_reg_tokens", 0) != 0:
        raise ValueError("HLS196 does not support register tokens")
    if getattr(model, "no_embed_class", False):
        raise ValueError("HLS196 requires the CLS token to retain positional identity 0")
    if getattr(model, "global_pool", None) != "token":
        raise ValueError("HLS196 requires CLS-token classifier pooling")
    if getattr(getattr(model, "patch_embed", None), "num_patches", None) != 196:
        raise ValueError("HLS196 requires exactly 196 standard patch embeddings")
    pos_embed = getattr(model, "pos_embed", None)
    if not isinstance(pos_embed, torch.Tensor) or tuple(pos_embed.shape) != (1, 197, 192):
        raise ValueError("HLS196 requires a standard positional embedding of shape (1, 197, 192)")


def forward_hls196(model: nn.Module, images: torch.Tensor) -> torch.Tensor:
    """Run ``CLS + Patch[1..195]`` with the original 197-position identities."""

    _validate_hls_model(model)
    patches = model.patch_embed(images)
    if patches.ndim != 3 or tuple(patches.shape[1:]) != (196, 192):
        raise ValueError(f"expected patch embeddings [batch, 196, 192], got {tuple(patches.shape)}")
    cls = model.cls_token.expand(patches.shape[0], -1, -1)
    standard_tokens = torch.cat((cls, patches), dim=1) + model.pos_embed
    standard_tokens = model.pos_drop(standard_tokens)
    tokens = torch.cat((standard_tokens[:, :1], standard_tokens[:, 2:]), dim=1)
    tokens = model.patch_drop(tokens)
    tokens = model.norm_pre(tokens)
    tokens = model.blocks(tokens)
    features = model.norm(tokens)
    return model.forward_head(features)


class HLS196DeiT(nn.Module):
    """Portable module wrapper that cannot silently use standard197 forwarding."""

    def __init__(self, vit: nn.Module | None = None) -> None:
        super().__init__()
        self.vit = _new_deit() if vit is None else vit
        _validate_hls_model(self.vit)
        self._ffvit_token_layout = dict(HLS196_TOKEN_LAYOUT)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        return forward_hls196(self.vit, images)


def _load_payload(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"checkpoint does not exist: {path}")
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, TypeError, pickle.UnpicklingError) as error:
        raise ValueError(f"cannot load checkpoint: {path}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("checkpoint must contain a mapping wrapper")
    return payload


def load_deit_checkpoint(path: str | Path, *, device: str | torch.device = "cpu") -> nn.Module:
    """Load the supplied standard wrapper or a self-describing HLS196 artifact."""

    checkpoint_path = Path(path).expanduser().resolve()
    payload = _load_payload(checkpoint_path)
    if payload.get("schema") == CHECKPOINT_SCHEMA:
        required = {
            "schema",
            "architecture",
            "token_layout",
            "source_checkpoint_sha256",
            "num_classes",
            "state_dict",
            "creation_parameters",
        }
        missing = sorted(required.difference(payload))
        if missing:
            raise ValueError(f"HLS196 checkpoint is missing required keys: {missing}")
        if payload["architecture"] != ARCHITECTURE or payload["num_classes"] != 1000:
            raise ValueError("HLS196 checkpoint architecture or class count is incompatible")
        if payload["token_layout"] != HLS196_TOKEN_LAYOUT:
            raise ValueError("HLS196 checkpoint token layout is incompatible")
        model = _new_deit()
        _strict_load(model, payload["state_dict"])
        wrapped: nn.Module = HLS196DeiT(model)
        wrapped.evaluation_provenance = {
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "source_checkpoint_sha256": payload["source_checkpoint_sha256"],
            "token_layout": dict(HLS196_TOKEN_LAYOUT),
        }
    else:
        missing = sorted(SOURCE_WRAPPER_FIELDS.difference(payload))
        if missing:
            raise ValueError("supplied checkpoint wrapper must contain model, epoch, and accuracy")
        if not isinstance(payload["epoch"], Integral) or isinstance(payload["epoch"], bool):
            raise ValueError("supplied checkpoint epoch must be an integer")
        if not isinstance(payload["accuracy"], Real) or isinstance(payload["accuracy"], bool):
            raise ValueError("supplied checkpoint accuracy must be numeric")
        model = _new_deit()
        _strict_load(model, payload["model"])
        model._ffvit_token_layout = dict(STANDARD197_TOKEN_LAYOUT)
        model._ffvit_checkpoint_metadata = {
            "epoch": int(payload["epoch"]),
            "accuracy": float(payload["accuracy"]),
        }
        model.evaluation_provenance = {
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "source_checkpoint_sha256": sha256_file(checkpoint_path),
            "token_layout": dict(STANDARD197_TOKEN_LAYOUT),
        }
        wrapped = model
    return wrapped.to(device)


def _atomic_torch_save(payload: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(output_path):
        raise ValueError(f"refusing to replace existing checkpoint: {output_path}")
    temporary = output_path.parent / f".{output_path.name}.staging-{uuid.uuid4().hex}"
    try:
        with temporary.open("xb") as handle:
            torch.save(dict(payload), handle)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output_path)
        except FileExistsError as error:
            raise ValueError(f"refusing to replace existing checkpoint: {output_path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def create_hls196_checkpoint(
    model: nn.Module,
    *,
    source_checkpoint: str | Path,
    output_path: str | Path,
    creation_parameters: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a portable CPU checkpoint whose loader preserves HLS196 semantics."""

    vit = model.vit if isinstance(model, HLS196DeiT) else model
    _validate_hls_model(vit)
    state = {name: tensor.detach().cpu() for name, tensor in vit.state_dict().items()}
    try:
        portable_parameters = json.loads(
            json.dumps(dict(creation_parameters), sort_keys=True, allow_nan=False)
        )
    except (TypeError, ValueError) as error:
        raise ValueError("creation_parameters must contain portable JSON values") from error
    payload = {
        "schema": CHECKPOINT_SCHEMA,
        "architecture": ARCHITECTURE,
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "source_checkpoint_sha256": sha256_file(source_checkpoint),
        "num_classes": 1000,
        "state_dict": state,
        "creation_parameters": portable_parameters,
    }
    _atomic_torch_save(payload, Path(output_path).expanduser().resolve())
    return payload
