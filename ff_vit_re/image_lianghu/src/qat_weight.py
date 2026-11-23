"""Signed-W3 weight QAT for the fixed ImageNet HLS196 DeiT-Tiny model."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, UnidentifiedImageError
from torch import nn
from torch.utils.data import Dataset

from .modeling import HLS196DeiT, HLS196_TOKEN_LAYOUT, load_deit_checkpoint, sha256_file


QMIN = -4
QMAX = 3
QAT_SCHEMA = "imagenet1k.ffvit.w3_qat_checkpoint.v1"
NUMERIC_MODE = "signed_w3_weight_qat_with_fp32_activations"


def _file_record(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def round_ste(value: torch.Tensor) -> torch.Tensor:
    """Ties-to-even forward with identity straight-through gradient."""

    return value + (torch.round(value) - value).detach()


class Int3QATLinear(nn.Module):
    """Linear with FP32 master weights and learnable positive log-scales."""

    def __init__(
        self,
        in_features: int,
        out_features: int,
        *,
        bias: bool,
        segments: Sequence[int],
    ) -> None:
        super().__init__()
        if sum(segments) != out_features or any(int(size) <= 0 for size in segments):
            raise ValueError("segments must be positive and sum to out_features")
        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.segments = tuple(int(size) for size in segments)
        self.weight = nn.Parameter(torch.empty(out_features, in_features))
        if bias:
            self.bias = nn.Parameter(torch.empty(out_features))
        else:
            self.register_parameter("bias", None)
        self.log_scale = nn.Parameter(torch.empty(len(self.segments)))

    @classmethod
    def from_linear(
        cls,
        linear: nn.Linear,
        *,
        scales: Sequence[float],
        segments: Sequence[int] | None = None,
    ) -> "Int3QATLinear":
        sizes = tuple(segments or (linear.out_features,))
        if len(scales) != len(sizes):
            raise ValueError("one scale is required for each segment")
        if any(not math.isfinite(float(scale)) or float(scale) <= 0 for scale in scales):
            raise ValueError("scales must be finite and positive")
        result = cls(
            linear.in_features,
            linear.out_features,
            bias=linear.bias is not None,
            segments=sizes,
        )
        with torch.no_grad():
            result.weight.copy_(linear.weight)
            if linear.bias is not None:
                result.bias.copy_(linear.bias)
            result.log_scale.copy_(torch.tensor([math.log(float(x)) for x in scales]))
        return result

    def scales(self) -> torch.Tensor:
        return self.log_scale.exp().clamp_min(1e-10)

    def fake_quant_weight(self) -> torch.Tensor:
        parts = []
        start = 0
        for rows, scale in zip(self.segments, self.scales(), strict=True):
            part = self.weight[start : start + rows]
            code = round_ste((part / scale).clamp(QMIN, QMAX))
            parts.append(code * scale)
            start += rows
        return torch.cat(parts, dim=0)

    @torch.no_grad()
    def export_integer(self) -> tuple[torch.Tensor, torch.Tensor]:
        parts = []
        start = 0
        # Derive deployment scales from the serialized CPU log-scales. CUDA and
        # CPU expf can differ by one ULP, which would make an otherwise portable
        # checkpoint fail exact scale restoration.
        scales = self.log_scale.detach().cpu().exp().clamp_min(1e-10)
        for rows, scale in zip(self.segments, scales, strict=True):
            code = torch.round(self.weight[start : start + rows].detach().cpu() / scale)
            parts.append(code.clamp(QMIN, QMAX).to(torch.int8))
            start += rows
        return torch.cat(parts, dim=0), scales

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return F.linear(value, self.fake_quant_weight(), self.bias)


def _read_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path).expanduser().resolve()
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read PTQ contract: {contract_path}") from error
    quant = contract.get("quantization", {})
    if (
        contract.get("quantized_matrix_count") != 72
        or quant.get("qmin") != QMIN
        or quant.get("qmax") != QMAX
        or quant.get("rounding") != "ties_to_even"
        or contract.get("token_layout") != HLS196_TOKEN_LAYOUT
    ):
        raise ValueError("PTQ contract does not match signed-W3 HLS196 QAT")
    entries = contract.get("matrices")
    if not isinstance(entries, list) or len(entries) != 72:
        raise ValueError("PTQ contract must contain exactly 72 matrices")
    source = contract.get("source_hls_checkpoint")
    if not isinstance(source, Mapping):
        raise ValueError("PTQ contract lacks source checkpoint provenance")
    return contract


def build_w3_qat(
    hls_checkpoint: str | Path,
    ptq_manifest: str | Path,
) -> HLS196DeiT:
    """Build QAT from the FP32 master checkpoint and audited PTQ scales."""

    source_record = _file_record(hls_checkpoint)
    contract_record = _file_record(ptq_manifest)
    contract = _read_contract(ptq_manifest)
    if dict(contract["source_hls_checkpoint"]) != source_record:
        raise ValueError("PTQ contract source checkpoint provenance mismatch")
    model = load_deit_checkpoint(hls_checkpoint, device="cpu")
    if not isinstance(model, HLS196DeiT):
        raise ValueError("QAT source must be an HLS196 checkpoint")
    by_name = {entry["name"]: entry for entry in contract["matrices"]}
    for block_index in range(12):
        block = model.vit.blocks[block_index]
        prefix = f"blocks.{block_index}"
        qkv_names = [f"{prefix}.attn.qkv.weight[{part}]" for part in ("q", "k", "v")]
        qkv_scales = [float(by_name[name]["scale"]) for name in qkv_names]
        rows = block.attn.qkv.out_features // 3
        block.attn.qkv = Int3QATLinear.from_linear(
            block.attn.qkv, scales=qkv_scales, segments=(rows, rows, rows)
        )
        for attribute, name in (
            ("attn.proj", f"{prefix}.attn.proj.weight"),
            ("mlp.fc1", f"{prefix}.mlp.fc1.weight"),
            ("mlp.fc2", f"{prefix}.mlp.fc2.weight"),
        ):
            owner_name, child_name = attribute.split(".")
            owner = getattr(block, owner_name)
            setattr(
                owner,
                child_name,
                Int3QATLinear.from_linear(
                    getattr(owner, child_name), scales=(float(by_name[name]["scale"]),)
                ),
            )
    model._qat_source_hls_checkpoint = source_record
    model._qat_ptq_contract = contract_record
    model.evaluation_provenance = {
        "checkpoint_sha256": source_record["sha256"],
        "source_checkpoint_sha256": source_record["sha256"],
        "quant_contract_sha256": contract_record["sha256"],
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": NUMERIC_MODE,
    }
    return model


def qat_module_names(model: nn.Module) -> list[str]:
    return [name for name, module in model.named_modules() if isinstance(module, Int3QATLinear)]


class FrozenManifestDataset(Dataset[tuple[Any, int]]):
    """Dataset whose complete membership and labels come from one JSONL manifest."""

    def __init__(
        self,
        manifest: str | Path,
        *,
        transform: Any,
        expected_count: int = 10_000,
        allow_resampled_duplicates: bool = False,
    ):
        self.manifest_path = Path(manifest).expanduser().resolve()
        self.transform = transform
        records = []
        try:
            for line in self.manifest_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    records.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot read frozen training manifest: {self.manifest_path}") from error
        if len(records) != expected_count:
            raise ValueError(f"frozen manifest requires {expected_count} records; found {len(records)}")
        paths = []
        for record in records:
            path = Path(record.get("path", "")).expanduser().resolve()
            label = record.get("label")
            if not path.is_file() or not isinstance(label, int) or isinstance(label, bool):
                raise ValueError("frozen manifest contains an invalid path or label")
            paths.append(str(path))
        if len(set(paths)) != len(paths):
            if not allow_resampled_duplicates:
                raise ValueError("frozen manifest contains duplicate paths")
            by_path: dict[str, list[dict[str, Any]]] = {}
            for path, record in zip(paths, records, strict=True):
                by_path.setdefault(path, []).append(record)
            for path, duplicates in by_path.items():
                if len(duplicates) == 1:
                    continue
                originals = [
                    record
                    for record in duplicates
                    if record.get("schema") != "imagenet1k.train_sample_resample.v1"
                ]
                repeats = [
                    record
                    for record in duplicates
                    if record.get("schema") == "imagenet1k.train_sample_resample.v1"
                ]
                ordinals = [record.get("resample_ordinal") for record in repeats]
                if (
                    len(originals) != 1
                    or len(repeats) != len(duplicates) - 1
                    or any(record.get("resampled_from_path") != path for record in repeats)
                    or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in ordinals)
                    or len(set(ordinals)) != len(ordinals)
                    or any(record.get("label") != originals[0].get("label") for record in repeats)
                ):
                    raise ValueError("frozen manifest resample duplicate contract mismatch")
        self.records = tuple(records)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[Any, int]:
        record = self.records[index]
        path = Path(record["path"])
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGB")
                image.load()
        except (OSError, ValueError, UnidentifiedImageError) as error:
            raise ValueError(f"unreadable frozen-manifest image: {path}") from error
        return self.transform(image), int(record["label"])


def export_qat_integer_state(model: nn.Module) -> dict[str, dict[str, Any]]:
    exported = {}
    for name, module in model.named_modules():
        if isinstance(module, Int3QATLinear):
            code, scales = module.export_integer()
            if code.dtype != torch.int8 or int(code.min()) < QMIN or int(code.max()) > QMAX:
                raise ValueError(f"invalid final integer code for {name}")
            exported[name] = {
                "code": code.contiguous(),
                "scales": scales.contiguous(),
                "segments": list(module.segments),
                "qmin": QMIN,
                "qmax": QMAX,
                "code_sha256": hashlib.sha256(code.contiguous().numpy().tobytes()).hexdigest(),
            }
    if len(exported) != 48:
        raise ValueError(f"expected 48 QAT Linear modules; found {len(exported)}")
    return exported


def _rng_state() -> dict[str, Any]:
    numpy_state = np.random.get_state()
    return {
        "python": random.getstate(),
        "numpy": {
            "name": numpy_state[0],
            "keys": torch.from_numpy(numpy_state[1].copy()),
            "position": int(numpy_state[2]),
            "has_gauss": int(numpy_state[3]),
            "cached_gaussian": float(numpy_state[4]),
        },
        "torch_cpu": torch.get_rng_state(),
        "torch_cuda": [state.cpu() for state in torch.cuda.get_rng_state_all()] if torch.cuda.is_available() else [],
    }


def restore_rng_state(state: Mapping[str, Any]) -> None:
    random.setstate(tuple(state["python"]))
    numpy_state = state["numpy"]
    np.random.set_state(
        (
            numpy_state["name"],
            numpy_state["keys"].cpu().numpy(),
            numpy_state["position"],
            numpy_state["has_gauss"],
            numpy_state["cached_gaussian"],
        )
    )
    torch.set_rng_state(state["torch_cpu"].cpu())
    if torch.cuda.is_available() and state["torch_cuda"]:
        torch.cuda.set_rng_state_all([item.cpu() for item in state["torch_cuda"]])


def save_qat_checkpoint(
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
) -> dict[str, Any]:
    """Atomically save resumable FP32 masters, log-scales, state, RNG and hashes."""

    records = {name: _file_record(value) for name, value in inputs.items()}
    payload = {
        "schema": QAT_SCHEMA,
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": NUMERIC_MODE,
        "epoch": int(epoch),
        "best_metric": float(best_metric),
        "history": [dict(item) for item in history],
        "inputs": records,
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
        raise ValueError("checkpoint input provenance key mismatch")
    for name, path in expected.items():
        if dict(recorded[name]) != _file_record(path):
            raise ValueError(f"checkpoint input provenance mismatch: {name}")


def load_qat_checkpoint(
    path: str | Path,
    *,
    expected_inputs: Mapping[str, str | Path] | None = None,
) -> tuple[HLS196DeiT, dict[str, Any]]:
    checkpoint_path = Path(path).expanduser().resolve()
    try:
        payload = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, TypeError) as error:
        raise ValueError(f"cannot safe-load QAT checkpoint: {checkpoint_path}") from error
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema") != QAT_SCHEMA
        or payload.get("token_layout") != HLS196_TOKEN_LAYOUT
    ):
        raise ValueError("QAT checkpoint schema or HLS196 token layout mismatch")
    recorded = payload.get("inputs")
    if not isinstance(recorded, Mapping) or "source" not in recorded or "contract" not in recorded:
        raise ValueError("QAT checkpoint input provenance is missing")
    if expected_inputs is None:
        expected_inputs = {name: record["path"] for name, record in recorded.items()}
    _verify_inputs(recorded, expected_inputs)
    model = build_w3_qat(recorded["source"]["path"], recorded["contract"]["path"])
    try:
        model.load_state_dict(payload["model_state"], strict=True)
    except (KeyError, RuntimeError, TypeError) as error:
        raise ValueError(f"QAT model state is incompatible: {error}") from error
    actual_export = export_qat_integer_state(model)
    stored_export = payload.get("integer_export")
    if not isinstance(stored_export, Mapping) or set(stored_export) != set(actual_export):
        raise ValueError("QAT integer export is missing or incomplete")
    for name, actual in actual_export.items():
        stored = stored_export[name]
        if (
            stored.get("qmin") != QMIN
            or stored.get("qmax") != QMAX
            or stored.get("segments") != actual["segments"]
            or stored.get("code_sha256") != actual["code_sha256"]
            or not torch.equal(stored.get("code"), actual["code"])
            or not torch.equal(stored.get("scales"), actual["scales"])
        ):
            raise ValueError(f"QAT integer export mismatch: {name}")
    model.evaluation_provenance = {
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "source_checkpoint_sha256": recorded["source"]["sha256"],
        "quant_contract_sha256": recorded["contract"]["sha256"],
        "training_manifest_sha256": recorded.get("manifest", {}).get("sha256"),
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": NUMERIC_MODE,
    }
    model.eval()
    return model, dict(payload)


def restore_training_state(
    payload: Mapping[str, Any], optimizer: Any, scheduler: Any, scaler: Any
) -> None:
    optimizer.load_state_dict(payload["optimizer_state"])
    scheduler.load_state_dict(payload["scheduler_state"])
    scaler.load_state_dict(payload["scaler_state"])
    restore_rng_state(payload["rng_state"])
