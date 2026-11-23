"""Deterministic signed-W3 PTQ for the ImageNet FF-ViT HLS196 model."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import pickle
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import torch

from .modeling import (
    ARCHITECTURE,
    HLS196DeiT,
    HLS196_TOKEN_LAYOUT,
    load_deit_checkpoint,
    sha256_file,
)


W3_QMIN = -4
W3_QMAX = 3
W3_CANDIDATES = 101
W3_MANIFEST_SCHEMA = "imagenet1k.ffvit.w3_ptq_manifest.v2"
W3_CHECKPOINT_SCHEMA = "imagenet1k.ffvit.w3_ptq_checkpoint.v2"
W3_INTEGER_SCHEMA = "imagenet1k.ffvit.w3_ptq_integer_weights.v2"
ROUNDING_POLICY = "ties_to_even"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLASS_MAP_PATH = PROJECT_ROOT / "metadata" / "class_mapping.json"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _payload_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _file_record(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"required file does not exist: {resolved}")
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def _validate_file_record(record: Any, *, label: str) -> Path:
    if not isinstance(record, Mapping) or set(record) != {"path", "size_bytes", "sha256"}:
        raise ValueError(f"{label} record is malformed")
    path = Path(record["path"]).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    actual = _file_record(path)
    if dict(record) != actual:
        raise ValueError(f"{label} size or SHA-256 mismatch")
    return path


def round_ties_to_even(tensor: torch.Tensor) -> torch.Tensor:
    """Match the canonical quantizer's :func:`torch.round` tie policy."""

    if not isinstance(tensor, torch.Tensor):
        raise TypeError("tensor must be a torch.Tensor")
    return torch.round(tensor)


def _validate_float_weight(weight: torch.Tensor) -> None:
    if not isinstance(weight, torch.Tensor) or not torch.is_floating_point(weight):
        raise TypeError("weight must be a floating-point tensor")
    if weight.numel() == 0:
        raise ValueError("weight must not be empty")
    if not bool(torch.isfinite(weight).all()):
        raise ValueError("weight must contain only finite values")


def quantize_w3(weight: torch.Tensor, scale: float) -> torch.Tensor:
    """Quantize with zero point zero and the exact signed-W3 range ``[-4, 3]``."""

    _validate_float_weight(weight)
    try:
        numeric_scale = float(scale)
    except (TypeError, ValueError) as error:
        raise ValueError("scale must be finite and positive") from error
    if not math.isfinite(numeric_scale) or numeric_scale <= 0.0:
        raise ValueError("scale must be finite and positive")
    return round_ties_to_even(weight / numeric_scale).clamp(W3_QMIN, W3_QMAX).to(torch.int8)


def search_w3_scale(weight: torch.Tensor, *, candidates: int = W3_CANDIDATES) -> float:
    """Search the canonical 50%-to-100% max-magnitude clipping envelope.

    Candidates are visited from 50% through 100%; strict MSE improvement means
    the first candidate wins exact ties.  Quantization uses the project's
    canonical ties-to-even rule.
    """

    _validate_float_weight(weight)
    if not isinstance(candidates, int) or isinstance(candidates, bool) or candidates < 2:
        raise ValueError("candidates must be an integer of at least 2")
    work = weight.detach().to(device="cpu", dtype=torch.float32)
    maximum = float(work.abs().max().item())
    if maximum == 0.0:
        return 1.0
    best_scale: float | None = None
    best_mse: float | None = None
    for index in range(candidates):
        ratio = 0.5 + 0.5 * index / (candidates - 1)
        scale = maximum * ratio / W3_QMAX
        integer = quantize_w3(work, scale)
        dequantized = integer.to(work.dtype) * scale
        mse = float(torch.mean((work - dequantized) ** 2).item())
        if best_mse is None or mse < best_mse:
            best_mse = mse
            best_scale = scale
    assert best_scale is not None
    return best_scale


def _matrix_specs(model: HLS196DeiT) -> list[dict[str, Any]]:
    state = model.vit.state_dict()
    specs: list[dict[str, Any]] = []
    for layer in range(12):
        prefix = f"blocks.{layer}"
        qkv_name = f"{prefix}.attn.qkv.weight"
        qkv = state.get(qkv_name)
        if not isinstance(qkv, torch.Tensor) or qkv.ndim != 2 or qkv.shape[0] % 3:
            raise ValueError(f"{qkv_name} cannot split evenly into Q/K/V matrices")
        rows = qkv.shape[0] // 3
        for index, component in enumerate(("q", "k", "v")):
            specs.append(
                {
                    "name": f"{qkv_name}[{component}]",
                    "parameter_name": qkv_name,
                    "component": component,
                    "row_slice": [index * rows, (index + 1) * rows],
                }
            )
        for component, parameter_name in (
            ("o", f"{prefix}.attn.proj.weight"),
            ("fc1", f"{prefix}.mlp.fc1.weight"),
            ("fc2", f"{prefix}.mlp.fc2.weight"),
        ):
            tensor = state.get(parameter_name)
            if not isinstance(tensor, torch.Tensor) or tensor.ndim != 2:
                raise ValueError(f"missing Linear weight: {parameter_name}")
            specs.append(
                {
                    "name": parameter_name,
                    "parameter_name": parameter_name,
                    "component": component,
                    "row_slice": [0, tensor.shape[0]],
                }
            )
    if len(specs) != 72:
        raise ValueError(f"expected exactly 72 encoder matrices; found {len(specs)}")
    return specs


def _tensor_sha256(tensor: torch.Tensor) -> str:
    data = tensor.detach().to(device="cpu").contiguous().numpy().tobytes()
    return hashlib.sha256(data).hexdigest()


def _histogram(code: torch.Tensor) -> dict[str, int]:
    return {str(value): int((code == value).sum().item()) for value in range(W3_QMIN, W3_QMAX + 1)}


def build_w3_ptq(
    hls_checkpoint: str | Path,
) -> tuple[HLS196DeiT, dict[str, Any], dict[str, torch.Tensor]]:
    """Build the signed-W3 fake-quantized model from the approved HLS196 source."""

    source_path = Path(hls_checkpoint).expanduser().resolve()
    source_record = _file_record(source_path)
    class_map_record = _file_record(CLASS_MAP_PATH)
    model = load_deit_checkpoint(source_path, device="cpu")
    if not isinstance(model, HLS196DeiT) or model._ffvit_token_layout != HLS196_TOKEN_LAYOUT:
        raise ValueError("source checkpoint must enforce the exact HLS196 token layout")
    model.eval()
    matrices: list[dict[str, Any]] = []
    integer_state: dict[str, torch.Tensor] = {}
    with torch.no_grad():
        state = model.vit.state_dict()
        for spec in _matrix_specs(model):
            start, stop = spec["row_slice"]
            weight = state[spec["parameter_name"]][start:stop]
            scale = search_w3_scale(weight)
            code = quantize_w3(weight, scale).detach().cpu().contiguous()
            dequantized = code.to(weight.dtype) * scale
            mse = float(
                torch.mean(
                    (weight.detach().cpu().float() - dequantized.cpu().float()) ** 2
                ).item()
            )
            state[spec["parameter_name"]][start:stop].copy_(dequantized)
            integer_state[spec["name"]] = code
            matrices.append(
                {
                    **spec,
                    "shape": list(code.shape),
                    "bits": 3,
                    "signed": True,
                    "qmin": W3_QMIN,
                    "qmax": W3_QMAX,
                    "zero_point": 0,
                    "scale": scale,
                    "mse": mse,
                    "integer_dtype": "torch.int8",
                    "integer_histogram": _histogram(code),
                    "integer_sha256": _tensor_sha256(code),
                }
            )
    manifest: dict[str, Any] = {
        "schema": W3_MANIFEST_SCHEMA,
        "architecture": ARCHITECTURE,
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "source_hls_checkpoint": source_record,
        "class_map": class_map_record,
        "quantization": {
            "bits": 3,
            "signed": True,
            "qmin": W3_QMIN,
            "qmax": W3_QMAX,
            "zero_point": 0,
            "rounding": ROUNDING_POLICY,
            "scale_granularity": "Q/K/V independent; O/fc1/fc2 per-matrix",
            "scale_search": {
                "method": "deterministic_mse",
                "candidates": W3_CANDIDATES,
                "minimum_clip_ratio": 0.5,
                "maximum_clip_ratio": 1.0,
                "tie_break": "first_candidate",
            },
        },
        "quantized_matrix_count": 72,
        "matrices": matrices,
        "excluded": {
            "patch": "FP32",
            "biases": "FP32",
            "normalization": "FP32",
            "positional_and_cls": "FP32",
            "head": "FP32",
        },
    }
    model._w3_source_hls_checkpoint = dict(source_record)
    model._w3_class_map = dict(class_map_record)
    model.evaluation_provenance = {
        "checkpoint_sha256": source_record["sha256"],
        "source_checkpoint_sha256": source_record["sha256"],
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": "signed_w3_weight_ptq_with_fp32_activations",
    }
    return model, manifest, integer_state


def _cpu_state(model: HLS196DeiT) -> dict[str, torch.Tensor]:
    return {
        name: tensor.detach().to(device="cpu").contiguous().clone()
        for name, tensor in model.vit.state_dict().items()
    }


def _cpu_integer_state(integer_state: Mapping[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {
        name: tensor.detach().to(device="cpu").contiguous().clone()
        for name, tensor in integer_state.items()
    }


def _torch_bytes(payload: Mapping[str, Any]) -> bytes:
    stream = io.BytesIO()
    torch.save(dict(payload), stream, _use_new_zipfile_serialization=True)
    return stream.getvalue()


def serialize_w3_checkpoint(
    model: HLS196DeiT,
    manifest: Mapping[str, Any],
    integer_state: Mapping[str, torch.Tensor],
) -> bytes:
    """Return deterministic, safe-loadable bytes for the complete PTQ checkpoint."""

    if not isinstance(model, HLS196DeiT):
        raise TypeError("model must be HLS196DeiT")
    portable_manifest = json.loads(_canonical_json(dict(manifest)))
    payload = {
        "schema": W3_CHECKPOINT_SCHEMA,
        "architecture": ARCHITECTURE,
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "num_classes": 1000,
        "source_hls_checkpoint": dict(portable_manifest["source_hls_checkpoint"]),
        "class_map": dict(portable_manifest["class_map"]),
        "manifest": portable_manifest,
        "manifest_sha256": _payload_sha256(portable_manifest),
        "integer_state": _cpu_integer_state(integer_state),
        "state_dict": _cpu_state(model),
    }
    _validate_checkpoint_payload(payload)
    return _torch_bytes(payload)


def serialize_w3_integer_artifact(
    manifest: Mapping[str, Any], integer_state: Mapping[str, torch.Tensor]
) -> bytes:
    """Return deterministic, safe-loadable bytes for the standalone W3 codes."""

    portable_manifest = json.loads(_canonical_json(dict(manifest)))
    tensors = _cpu_integer_state(integer_state)
    _validate_integer_state(tensors, portable_manifest)
    payload = {
        "schema": W3_INTEGER_SCHEMA,
        "token_layout": dict(portable_manifest["token_layout"]),
        "source_hls_checkpoint": dict(portable_manifest["source_hls_checkpoint"]),
        "class_map": dict(portable_manifest["class_map"]),
        "manifest_sha256": _payload_sha256(portable_manifest),
        "tensors": tensors,
    }
    return _torch_bytes(payload)


def _expected_manifest_keys() -> set[str]:
    return {
        "schema",
        "architecture",
        "token_layout",
        "source_hls_checkpoint",
        "class_map",
        "quantization",
        "quantized_matrix_count",
        "matrices",
        "excluded",
    }


def _validate_manifest(manifest: Any, source_model: HLS196DeiT) -> list[dict[str, Any]]:
    if not isinstance(manifest, Mapping) or set(manifest) != _expected_manifest_keys():
        raise ValueError("W3 manifest has missing or extra keys")
    if (
        manifest.get("schema") != W3_MANIFEST_SCHEMA
        or manifest.get("architecture") != ARCHITECTURE
        or manifest.get("token_layout") != HLS196_TOKEN_LAYOUT
        or manifest.get("quantized_matrix_count") != 72
    ):
        raise ValueError("W3 manifest architecture or token layout mismatch")
    quantization = manifest.get("quantization")
    expected_quantization = {
        "bits": 3,
        "signed": True,
        "qmin": W3_QMIN,
        "qmax": W3_QMAX,
        "zero_point": 0,
        "rounding": ROUNDING_POLICY,
        "scale_granularity": "Q/K/V independent; O/fc1/fc2 per-matrix",
        "scale_search": {
            "method": "deterministic_mse",
            "candidates": W3_CANDIDATES,
            "minimum_clip_ratio": 0.5,
            "maximum_clip_ratio": 1.0,
            "tie_break": "first_candidate",
        },
    }
    if quantization != expected_quantization:
        raise ValueError("W3 manifest quantization policy mismatch")
    entries = manifest.get("matrices")
    specs = _matrix_specs(source_model)
    if not isinstance(entries, list) or len(entries) != 72:
        raise ValueError("W3 manifest must describe exactly 72 matrices")
    entry_keys = {
        "name",
        "parameter_name",
        "component",
        "row_slice",
        "shape",
        "bits",
        "signed",
        "qmin",
        "qmax",
        "zero_point",
        "scale",
        "mse",
        "integer_dtype",
        "integer_histogram",
        "integer_sha256",
    }
    source_state = source_model.vit.state_dict()
    validated: list[dict[str, Any]] = []
    for spec, raw_entry in zip(specs, entries, strict=True):
        if not isinstance(raw_entry, Mapping) or set(raw_entry) != entry_keys:
            raise ValueError("W3 matrix manifest entry has missing or extra keys")
        entry = dict(raw_entry)
        if any(entry.get(key) != value for key, value in spec.items()):
            raise ValueError("W3 manifest matrix list or component mapping mismatch")
        start, stop = spec["row_slice"]
        expected_shape = list(source_state[spec["parameter_name"]][start:stop].shape)
        if entry.get("shape") != expected_shape:
            raise ValueError(f"wrong shape in W3 manifest for {spec['name']}")
        if (
            entry.get("bits") != 3
            or entry.get("signed") is not True
            or entry.get("qmin") != W3_QMIN
            or entry.get("qmax") != W3_QMAX
            or entry.get("zero_point") != 0
            or entry.get("integer_dtype") != "torch.int8"
        ):
            raise ValueError(f"quantizer metadata mismatch for {spec['name']}")
        scale = entry.get("scale")
        if (
            not isinstance(scale, (int, float))
            or isinstance(scale, bool)
            or not math.isfinite(float(scale))
            or float(scale) <= 0.0
        ):
            raise ValueError(f"invalid scale for {spec['name']}")
        mse = entry.get("mse")
        if (
            not isinstance(mse, (int, float))
            or isinstance(mse, bool)
            or not math.isfinite(float(mse))
            or float(mse) < 0.0
        ):
            raise ValueError(f"invalid MSE for {spec['name']}")
        source_weight = source_state[spec["parameter_name"]][start:stop]
        canonical_scale = search_w3_scale(source_weight)
        if float(scale) != canonical_scale:
            raise ValueError(f"canonical scale mismatch for {spec['name']}")
        canonical_integer = quantize_w3(source_weight, canonical_scale).detach().cpu().contiguous()
        if (
            entry.get("integer_sha256") != _tensor_sha256(canonical_integer)
            or entry.get("integer_histogram") != _histogram(canonical_integer)
        ):
            raise ValueError(f"canonical integer metadata mismatch for {spec['name']}")
        canonical_dequantized = canonical_integer.to(source_weight.dtype) * canonical_scale
        canonical_mse = float(
            torch.mean(
                (source_weight.detach().cpu().float() - canonical_dequantized.cpu().float()) ** 2
            ).item()
        )
        if float(mse) != canonical_mse:
            raise ValueError(f"canonical MSE mismatch for {spec['name']}")
        validated.append(entry)
    return validated


def _validate_integer_state(
    integer_state: Any, manifest: Mapping[str, Any], source_model: HLS196DeiT | None = None
) -> None:
    if not isinstance(integer_state, Mapping):
        raise ValueError("integer state must be a mapping")
    entries = manifest.get("matrices")
    if not isinstance(entries, list):
        raise ValueError("manifest matrices are malformed")
    expected_names = [entry.get("name") for entry in entries if isinstance(entry, Mapping)]
    if len(expected_names) != 72 or set(integer_state) != set(expected_names):
        raise ValueError("integer keys do not exactly match the 72 manifest matrices")
    for entry in entries:
        name = entry["name"]
        code = integer_state[name]
        if not isinstance(code, torch.Tensor) or code.dtype != torch.int8:
            raise ValueError(f"wrong dtype for integer tensor {name}; expected torch.int8")
        if list(code.shape) != entry.get("shape"):
            raise ValueError(f"wrong shape for integer tensor {name}")
        if code.device.type != "cpu":
            raise ValueError(f"integer tensor {name} must be stored on CPU")
        if code.numel() == 0 or int(code.min()) < W3_QMIN or int(code.max()) > W3_QMAX:
            raise ValueError(f"integer tensor {name} contains code outside W3 range")
        if _tensor_sha256(code) != entry.get("integer_sha256"):
            raise ValueError(f"integer SHA-256 mismatch for {name}")
        if _histogram(code) != entry.get("integer_histogram"):
            raise ValueError(f"integer histogram mismatch for {name}")


def _validate_checkpoint_payload(payload: Any) -> tuple[HLS196DeiT, dict[str, Any]]:
    required = {
        "schema",
        "architecture",
        "token_layout",
        "num_classes",
        "source_hls_checkpoint",
        "class_map",
        "manifest",
        "manifest_sha256",
        "integer_state",
        "state_dict",
    }
    if not isinstance(payload, Mapping) or set(payload) != required:
        raise ValueError("W3 checkpoint has missing or extra keys")
    if (
        payload.get("schema") != W3_CHECKPOINT_SCHEMA
        or payload.get("architecture") != ARCHITECTURE
        or payload.get("num_classes") != 1000
    ):
        raise ValueError("W3 checkpoint architecture mismatch")
    if payload.get("token_layout") != HLS196_TOKEN_LAYOUT:
        raise ValueError("W3 checkpoint token layout mismatch")
    source_path = _validate_file_record(
        payload.get("source_hls_checkpoint"), label="source HLS checkpoint"
    )
    _validate_file_record(payload.get("class_map"), label="class map")
    source_model = load_deit_checkpoint(source_path, device="cpu")
    if not isinstance(source_model, HLS196DeiT):
        raise ValueError("source HLS checkpoint loader did not return HLS196DeiT")
    manifest = payload.get("manifest")
    entries = _validate_manifest(manifest, source_model)
    if manifest.get("source_hls_checkpoint") != payload.get("source_hls_checkpoint"):
        raise ValueError("source HLS checkpoint record differs between manifest and checkpoint")
    if manifest.get("class_map") != payload.get("class_map"):
        raise ValueError("class map record differs between manifest and checkpoint")
    if payload.get("manifest_sha256") != _payload_sha256(manifest):
        raise ValueError("W3 manifest SHA-256 mismatch")
    integer_state = payload.get("integer_state")
    _validate_integer_state(integer_state, manifest, source_model)

    state = payload.get("state_dict")
    base_state = source_model.vit.state_dict()
    if not isinstance(state, Mapping) or set(state) != set(base_state):
        raise ValueError("W3 state dictionary has missing or extra keys")
    quantized_parameters = {entry["parameter_name"] for entry in entries}
    for name, base_tensor in base_state.items():
        value = state[name]
        if not isinstance(value, torch.Tensor) or value.shape != base_tensor.shape or value.dtype != base_tensor.dtype:
            raise ValueError(f"W3 state dictionary tensor mismatch for {name}")
        if name not in quantized_parameters and not torch.equal(value, base_tensor):
            raise ValueError(f"excluded FP32 parameter changed: {name}")
    for entry in entries:
        start, stop = entry["row_slice"]
        actual = state[entry["parameter_name"]][start:stop]
        expected = integer_state[entry["name"]].to(actual.dtype) * float(entry["scale"])
        if not torch.equal(actual, expected):
            raise ValueError(f"dequantized state mismatch for {entry['name']}")
    try:
        source_model.vit.load_state_dict(dict(state), strict=True)
    except (RuntimeError, TypeError) as error:
        raise ValueError(f"W3 state dictionary is incompatible: {error}") from error
    return source_model, dict(manifest)


def _safe_load(path: Path, *, label: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, TypeError, pickle.UnpicklingError) as error:
        raise ValueError(f"cannot safe-load {label}: {path}") from error
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must contain a mapping")
    return payload


def load_w3_ptq_checkpoint(path: str | Path) -> HLS196DeiT:
    """Strictly restore and validate a self-contained W3 PTQ HLS196 checkpoint."""

    checkpoint_path = Path(path).expanduser().resolve()
    payload = _safe_load(checkpoint_path, label="W3 checkpoint")
    model, _ = _validate_checkpoint_payload(payload)
    source_sha256 = payload["source_hls_checkpoint"]["sha256"]
    model._w3_source_hls_checkpoint = dict(payload["source_hls_checkpoint"])
    model._w3_class_map = dict(payload["class_map"])
    model.evaluation_provenance = {
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "source_checkpoint_sha256": source_sha256,
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": "signed_w3_weight_ptq_with_fp32_activations",
    }
    model.eval()
    return model


def load_w3_integer_artifact(
    path: str | Path, *, manifest: Mapping[str, Any]
) -> dict[str, torch.Tensor]:
    """Safe-load standalone W3 codes and bind them to the supplied manifest."""

    artifact_path = Path(path).expanduser().resolve()
    payload = _safe_load(artifact_path, label="W3 integer artifact")
    required = {
        "schema",
        "token_layout",
        "source_hls_checkpoint",
        "class_map",
        "manifest_sha256",
        "tensors",
    }
    if set(payload) != required or payload.get("schema") != W3_INTEGER_SCHEMA:
        raise ValueError("W3 integer artifact has missing, extra, or incompatible keys")
    portable_manifest = json.loads(_canonical_json(dict(manifest)))
    if payload.get("token_layout") != HLS196_TOKEN_LAYOUT:
        raise ValueError("W3 integer artifact token layout mismatch")
    if payload.get("source_hls_checkpoint") != portable_manifest.get("source_hls_checkpoint"):
        raise ValueError("W3 integer artifact source HLS checkpoint mismatch")
    if payload.get("class_map") != portable_manifest.get("class_map"):
        raise ValueError("W3 integer artifact class map mismatch")
    _validate_file_record(payload.get("source_hls_checkpoint"), label="source HLS checkpoint")
    _validate_file_record(payload.get("class_map"), label="class map")
    if payload.get("manifest_sha256") != _payload_sha256(portable_manifest):
        raise ValueError("W3 integer artifact manifest SHA-256 mismatch")
    tensors = payload.get("tensors")
    _validate_integer_state(tensors, portable_manifest)
    return {name: tensor.detach().cpu().contiguous() for name, tensor in tensors.items()}


def atomic_create_bytes(path: str | Path, content: bytes) -> None:
    """Create an artifact atomically without replacing any existing path."""

    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(output):
        raise ValueError(f"refusing to replace existing artifact: {output}")
    temporary = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError as error:
            raise ValueError(f"refusing to replace existing artifact: {output}") from error
    finally:
        temporary.unlink(missing_ok=True)


def manifest_json_bytes(manifest: Mapping[str, Any]) -> bytes:
    """Encode the audited manifest in a stable human-readable representation."""

    return json.dumps(
        dict(manifest), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ).encode("utf-8") + b"\n"
