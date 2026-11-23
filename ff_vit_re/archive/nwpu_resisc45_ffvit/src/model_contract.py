"""Immutable model, checkpoint, and HLS196 contracts for NWPU-RESISC45."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence, TypeVar

import timm
import torch
from torch import nn


ARCHITECTURE = "deit_tiny_patch16_224"
HIDDEN_DIMENSION = 192
STANDARD_TOKENS = 197
HLS_TOKENS = 196
DEFAULT_PRETRAINED = Path("/home/user/Desktop/ff_vit_re/deit_tiny_imagenet_timm.pth")
HLS196_TOKEN_MODE = {
    "total_tokens": 196,
    "cls_tokens": 1,
    "patch_tokens": 195,
    "dropped_patch": 0,
    "mapping": "[CLS,patch1,...,patch195]",
}
Batch = TypeVar("Batch")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of an existing regular file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def class_order_hash(classes: Sequence[str]) -> str:
    """Hash the exact frozen class sequence using a stable compact encoding."""

    payload = json.dumps(list(classes), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_classes(classes: Sequence[str]) -> tuple[str, ...]:
    frozen = tuple(classes)
    if len(frozen) != 45 or frozen != tuple(sorted(frozen)) or len(set(frozen)) != 45:
        raise ValueError("classes must be the frozen bytewise-sorted 45-class order")
    return frozen


def build_standard_deit(
    pretrained_checkpoint: Path = DEFAULT_PRETRAINED, classes: Sequence[str] = ()
) -> tuple[nn.Module, dict[str, str]]:
    """Load the local ImageNet checkpoint strictly, then install a 45-class head."""

    frozen_classes = _validate_classes(classes)
    pretrained_checkpoint = Path(pretrained_checkpoint)
    if not pretrained_checkpoint.is_file():
        raise FileNotFoundError(f"local pretrained checkpoint does not exist: {pretrained_checkpoint}")
    payload = torch.load(pretrained_checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(payload, Mapping) or not isinstance(payload.get("model"), Mapping):
        raise ValueError("pretrained checkpoint must contain a model state dictionary")
    model = timm.create_model(ARCHITECTURE, pretrained=False, num_classes=1000)
    result = model.load_state_dict(payload["model"], strict=True)
    if result.missing_keys or result.unexpected_keys:
        raise ValueError("local pretrained checkpoint did not load strictly")
    model.reset_classifier(len(frozen_classes))
    if not isinstance(model.head, nn.Linear) or model.head.out_features != len(frozen_classes):
        raise RuntimeError("DeiT classifier reset did not produce the requested class count")
    return model, {
        "architecture": ARCHITECTURE,
        "path": str(pretrained_checkpoint.resolve()),
        "sha256": sha256_file(pretrained_checkpoint),
    }


class HLS196DeiT(nn.Module):
    """DeiT-Tiny whose stream is ``[CLS, patch1, ..., patch195]``."""

    def __init__(self, num_classes: int) -> None:
        super().__init__()
        if num_classes != 45:
            raise ValueError(f"NWPU model requires 45 classes, received {num_classes}")
        self.vit = timm.create_model(ARCHITECTURE, pretrained=False, num_classes=num_classes)

    @torch.no_grad()
    def load_from_standard197(self, state: Mapping[str, torch.Tensor]) -> None:
        source = dict(state)
        old_pos = source.pop("pos_embed", None)
        if not isinstance(old_pos, torch.Tensor) or tuple(old_pos.shape) != (1, STANDARD_TOKENS, HIDDEN_DIMENSION):
            shape = None if old_pos is None else tuple(old_pos.shape)
            raise ValueError(f"standard DeiT pos_embed must have shape (1, 197, 192), got {shape}")
        result = self.vit.load_state_dict(source, strict=False)
        if set(result.missing_keys) != {"pos_embed"} or result.unexpected_keys:
            raise ValueError(
                "standard state must match HLS DeiT except pos_embed; "
                f"missing={result.missing_keys} unexpected={result.unexpected_keys}"
            )
        self.vit.pos_embed = nn.Parameter(torch.cat((old_pos[:, :1, :], old_pos[:, 2:, :]), dim=1).clone())
        if tuple(self.vit.pos_embed.shape) != (1, HLS_TOKENS, HIDDEN_DIMENSION):
            raise RuntimeError("HLS196 positional conversion produced the wrong shape")

    def prepare_tokens(self, inputs: torch.Tensor) -> torch.Tensor:
        """Build the exact HLS stream before dropout/pre-norm/encoder blocks."""

        patches = self.vit.patch_embed(inputs)
        if tuple(patches.shape[1:]) != (196, HIDDEN_DIMENSION):
            raise ValueError(f"expected 196x192 patch embeddings, got {tuple(patches.shape[1:])}")
        patches = patches[:, 1:, :]
        cls = self.vit.cls_token.expand(patches.shape[0], -1, -1)
        tokens = torch.cat((cls, patches), dim=1)
        if tuple(tokens.shape[1:]) != (HLS_TOKENS, HIDDEN_DIMENSION):
            raise RuntimeError("HLS196 stream must contain CLS plus 195 image patches")
        if tuple(self.vit.pos_embed.shape) != (1, HLS_TOKENS, HIDDEN_DIMENSION):
            raise RuntimeError("HLS196 model has an incompatible positional embedding")
        return tokens + self.vit.pos_embed

    def forward_features(self, inputs: torch.Tensor) -> torch.Tensor:
        tokens = self.vit.pos_drop(self.prepare_tokens(inputs))
        if hasattr(self.vit, "patch_drop"):
            tokens = self.vit.patch_drop(tokens)
        if hasattr(self.vit, "norm_pre"):
            tokens = self.vit.norm_pre(tokens)
        return self.vit.norm(self.vit.blocks(tokens))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.vit.forward_head(self.forward_features(inputs))


def checkpoint_metadata(
    *,
    classes: Sequence[str],
    architecture: str,
    token_count: int,
    model_state: Mapping[str, torch.Tensor],
    **extra: Any,
) -> dict[str, Any]:
    """Create the common, independently validated checkpoint envelope."""

    frozen_classes = _validate_classes(classes)
    if architecture not in {ARCHITECTURE, "deit_tiny_hls196"}:
        raise ValueError(f"unsupported architecture: {architecture}")
    if token_count not in {STANDARD_TOKENS, HLS_TOKENS}:
        raise ValueError(f"unsupported token count: {token_count}")
    return {
        "model": dict(model_state),
        "architecture": architecture,
        "num_classes": len(frozen_classes),
        "classes": list(frozen_classes),
        "class_order_sha256": class_order_hash(frozen_classes),
        "token_mode": dict(HLS196_TOKEN_MODE) if token_count == HLS_TOKENS else {"total_tokens": token_count},
        **extra,
    }


def validate_checkpoint_metadata(
    checkpoint: Mapping[str, Any], classes: Sequence[str], expected_token_count: int | None = None,
    expected_manifest_hashes: Mapping[str, str] | None = None,
) -> None:
    """Reject class-order, classifier-shape, architecture, and token-mode drift."""

    frozen_classes = _validate_classes(classes)
    if checkpoint.get("num_classes") != len(frozen_classes):
        raise ValueError("checkpoint num_classes does not match the manifest")
    if tuple(checkpoint.get("classes", ())) != frozen_classes:
        raise ValueError("checkpoint class order does not match the frozen manifest")
    if checkpoint.get("class_order_sha256") != class_order_hash(frozen_classes):
        raise ValueError("checkpoint class order hash does not match the frozen manifest")
    architecture = checkpoint.get("architecture")
    if architecture not in {ARCHITECTURE, "deit_tiny_hls196"}:
        raise ValueError(f"checkpoint architecture is unsupported: {architecture}")
    token_mode = checkpoint.get("token_mode", {})
    token_count = token_mode.get("total_tokens", STANDARD_TOKENS) if isinstance(token_mode, Mapping) else None
    if expected_token_count is not None and token_count != expected_token_count:
        raise ValueError(f"checkpoint token count {token_count} does not match expected {expected_token_count}")
    expected_architecture = ARCHITECTURE if token_count == STANDARD_TOKENS else "deit_tiny_hls196" if token_count == HLS_TOKENS else None
    if expected_architecture is None or architecture != expected_architecture:
        raise ValueError("checkpoint architecture does not match token semantics")
    if token_count == HLS_TOKENS and token_mode != HLS196_TOKEN_MODE:
        raise ValueError("checkpoint HLS token semantics do not match [CLS,patch1,...,patch195]")
    if token_count == STANDARD_TOKENS and token_mode != {"total_tokens": STANDARD_TOKENS}:
        raise ValueError("checkpoint standard token semantics are invalid")
    if expected_manifest_hashes is not None:
        actual_hashes = checkpoint.get("manifest_hashes")
        if not isinstance(actual_hashes, Mapping) or dict(actual_hashes) != dict(expected_manifest_hashes):
            raise ValueError("checkpoint manifest input hashes do not match the frozen bundle")
    state = checkpoint.get("model")
    if not isinstance(state, Mapping):
        raise ValueError("checkpoint model is not a state dictionary")
    head_weight = state.get("head.weight")
    head_bias = state.get("head.bias")
    if not isinstance(head_weight, torch.Tensor) or tuple(head_weight.shape) != (45, HIDDEN_DIMENSION):
        raise ValueError("checkpoint classifier weight must have shape (45, 192)")
    if not isinstance(head_bias, torch.Tensor) or tuple(head_bias.shape) != (45,):
        raise ValueError("checkpoint classifier bias must have shape (45,)")


def atomic_torch_save(payload: Mapping[str, Any], target: Path) -> str:
    """Publish one checkpoint atomically and never replace an existing artifact."""

    target = Path(target)
    if os.path.lexists(target):
        raise ValueError(f"refusing to replace published checkpoint: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.staging-{uuid.uuid4().hex}"
    try:
        with temporary.open("xb") as handle:
            torch.save(dict(payload), handle)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as error:
            raise ValueError(f"refusing to replace published checkpoint: {target}") from error
        return sha256_file(target)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json_write(payload: Mapping[str, Any], target: Path) -> str:
    """Publish a JSON report atomically without replacing a prior report."""

    target = Path(target)
    if os.path.lexists(target):
        raise ValueError(f"refusing to replace published report: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.staging-{uuid.uuid4().hex}"
    data = (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as error:
            raise ValueError(f"refusing to replace published report: {target}") from error
        return sha256_file(target)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_replace_torch_save(payload: Mapping[str, Any], target: Path) -> str:
    """Atomically update a private, resumable run-state file."""

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.staging-{uuid.uuid4().hex}"
    try:
        with temporary.open("xb") as handle:
            torch.save(dict(payload), handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
        return sha256_file(target)
    finally:
        temporary.unlink(missing_ok=True)


def save_resume_state(target: Path, payload: Mapping[str, Any]) -> str:
    """Durably replace mutable epoch progress in a private run directory."""

    if not isinstance(payload.get("input_hashes"), Mapping):
        raise ValueError("resume state must include input_hashes")
    return _atomic_replace_torch_save(payload, target)


def load_resume_state(target: Path, expected_input_hashes: Mapping[str, str]) -> dict[str, Any]:
    """Load only a resume state proven to use the exact current stage inputs."""

    try:
        payload = torch.load(target, map_location="cpu", weights_only=False)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"cannot load resume state: {target}") from error
    if not isinstance(payload, Mapping) or dict(payload.get("input_hashes", {})) != dict(expected_input_hashes):
        raise ValueError("resume state input hashes do not match current stage inputs")
    return dict(payload)


def public_checkpoint(state: Mapping[str, Any]) -> dict[str, Any]:
    """Remove private training/RNG state from a weights-only loadable checkpoint."""

    private = {"optimizer", "scaler", "rng", "next_epoch", "history", "best_epoch", "best_val_top1"}
    return {key: value for key, value in state.items() if key not in private}


def iter_limited(batches: Iterable[Batch], max_batches: int | None) -> Iterator[Batch]:
    """Yield at most ``max_batches`` without asking a loader for one more batch."""

    if max_batches is not None and max_batches <= 0:
        raise ValueError("max_batches must be positive when provided")
    yield from batches if max_batches is None else itertools.islice(batches, max_batches)
