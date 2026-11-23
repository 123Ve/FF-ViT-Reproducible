"""Original-ABI strict-S3 final LayerNorm and 1000-class Head artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch


HEAD_SCHEMA = "imagenet1k.ffvit.exact_head.original_s3.v1"
INT19_MIN = -(1 << 18)
INT19_MAX = (1 << 18) - 1

HEAD_ARRAY_SPECS: dict[str, tuple[tuple[int, ...], np.dtype[Any]]] = {
    "head_ln_scalars": ((8,), np.dtype("int32")),
    "head_lnw": ((192,), np.dtype("int32")),
    "head_lnb": ((192,), np.dtype("int64")),
    "head_rsqrt": ((128,), np.dtype("int32")),
    "head_weight": ((1000, 192), np.dtype("int8")),
    "head_bias": ((1000,), np.dtype("int32")),
}


@dataclass(frozen=True)
class S3ExactHead:
    root: Path
    manifest: dict[str, Any]
    arrays: dict[str, np.ndarray]


def _wrap_signed(value: torch.Tensor, bits: int) -> torch.Tensor:
    half = 1 << (bits - 1)
    return torch.remainder(value + half, 1 << bits) - half


def exact_head_logits(
    qln: torch.Tensor, qw: torch.Tensor, qb: torch.Tensor
) -> torch.Tensor:
    """Apply the HLS W8/int19 Head to every one of the 1000 classes.

    Addition in a fixed-width two's-complement ring is associative, so wrapping
    the complete dot product is bit-identical to the HLS compound accumulation.
    """

    qln = qln.to(torch.int64)
    qw = qw.to(torch.int64)
    qb = qb.to(torch.int64)
    if qln.ndim != 2 or tuple(qln.shape[1:]) != (192,):
        raise ValueError("Head LayerNorm codes must have shape [batch,192]")
    if tuple(qw.shape) != (1000, 192) or tuple(qb.shape) != (1000,):
        raise ValueError("strict-S3 Head requires 1000 active classes")
    # CUDA has no int64 GEMM kernel.  This accumulator is bounded below 2^24
    # (192 signed8 products plus signed19 bias), so float32 GEMM represents
    # every reachable integer exactly on both CPU and CUDA.
    accumulator = torch.round(
        torch.matmul(qln.to(torch.float32), qw.t().to(torch.float32))
    ).to(torch.int64) + qb
    return _wrap_signed(accumulator, 19)


def audit_head_accumulation(
    qln: torch.Tensor, qw: torch.Tensor, qb: torch.Tensor
) -> dict[str, int | float]:
    """Replay compound signed19 accumulation and expose transient wrapping."""

    qln = qln.to(torch.int64)
    qw = qw.to(torch.int64)
    qb = qb.to(torch.int64)
    if qln.ndim != 2 or qln.shape[1] != 192:
        raise ValueError("Head LayerNorm codes must have shape [batch,192]")
    if tuple(qw.shape) != (1000, 192) or tuple(qb.shape) != (1000,):
        raise ValueError("strict-S3 Head requires 1000 active classes")
    accumulator = qb.reshape(1, 1000).expand(qln.shape[0], -1).clone()
    any_wrap = torch.zeros_like(accumulator, dtype=torch.bool)
    for channel in range(192):
        before_wrap = accumulator + qln[:, channel : channel + 1] * qw[:, channel]
        any_wrap |= (before_wrap < INT19_MIN) | (before_wrap > INT19_MAX)
        accumulator = _wrap_signed(before_wrap, 19)
    count = int(any_wrap.sum())
    return {
        "intermediate_wrap_count": count,
        "intermediate_wrap_rate": float(count / any_wrap.numel()),
        "final_logit_min": int(accumulator.min()),
        "final_logit_max": int(accumulator.max()),
    }


def apply_head_layernorm(
    input_codes: torch.Tensor, arrays: Mapping[str, np.ndarray | torch.Tensor]
) -> torch.Tensor:
    """Replay the signed-fix HLS final LayerNorm at its original widths."""
    x = input_codes.to(torch.int64)
    if x.ndim != 2 or x.shape[1] != 192:
        raise ValueError("Head input codes must have shape [batch,192]")
    device = x.device
    scalars = torch.as_tensor(arrays["head_ln_scalars"], device=device, dtype=torch.int64)
    if tuple(scalars.shape) != (8,):
        raise ValueError("head_ln_scalars must have shape [8]")
    c1m, c1s, address_bias, shift1, bound, shift2, output_bits, _ = map(int, scalars.tolist())
    if output_bits != 8:
        raise ValueError("strict-S3 Head LayerNorm must output signed8")
    accumulator = _wrap_signed(x.sum(dim=1), 15)
    temporary = _wrap_signed(accumulator * c1m + (1 << (c1s - 1)), 30)
    mean = _wrap_signed(torch.bitwise_right_shift(temporary, c1s), 7)
    difference = _wrap_signed(x - mean[:, None], 13)
    variance = torch.remainder((difference * difference).sum(dim=1), 1 << 24)
    raw_address = torch.bitwise_right_shift(variance + address_bias, shift1)
    cursor = torch.remainder(raw_address, 1 << 7).clamp(0, bound)
    rsqrt = torch.as_tensor(arrays["head_rsqrt"], device=device, dtype=torch.int64)
    weight = torch.as_tensor(arrays["head_lnw"], device=device, dtype=torch.int64)
    bias = torch.as_tensor(arrays["head_lnb"], device=device, dtype=torch.int64)
    affine = _wrap_signed(
        difference * rsqrt[cursor][:, None] * weight[None, :] + bias[None, :], 36
    )
    rel9 = _wrap_signed(torch.bitwise_right_shift(affine, shift2), 9)
    return rel9.clamp(-128, 127)


def _quantize_weight_int8_mse(weight: torch.Tensor, grid: int = 101) -> float:
    weight = weight.detach().cpu().to(torch.float64)
    maximum = float(weight.abs().max())
    if maximum == 0.0:
        return 1.0
    best: tuple[float, float] | None = None
    for ratio in np.linspace(0.55, 1.0, grid):
        scale = maximum * float(ratio) / 127.0
        code = torch.round(weight / scale).clamp(-128, 127)
        mse = float(torch.mean((code * scale - weight) ** 2))
        if best is None or mse < best[0]:
            best = (mse, scale)
    assert best is not None
    return best[1]


def fit_head_classifier(
    qln: torch.Tensor,
    float_ln: torch.Tensor,
    weight: torch.Tensor,
    bias: torch.Tensor,
    *,
    ln_scale: float,
    scale_multipliers: tuple[float, ...] | list[float] | np.ndarray = tuple(
        np.linspace(0.70, 1.35, 27)
    ),
) -> dict[str, Any]:
    """Fit all 1000 W8/int19 classifier rows against real calibration features."""

    qln = qln.detach().cpu().to(torch.int64)
    float_ln = float_ln.detach().cpu().to(torch.float64)
    weight = weight.detach().cpu().to(torch.float64)
    bias = bias.detach().cpu().to(torch.float64)
    if tuple(weight.shape) != (1000, 192) or tuple(bias.shape) != (1000,):
        raise ValueError("strict-S3 classifier source must have shape [1000,192]/[1000]")
    if qln.ndim != 2 or tuple(qln.shape) != tuple(float_ln.shape) or qln.shape[1] != 192:
        raise ValueError("classifier calibration features must be matching [batch,192] tensors")
    if not np.isfinite(ln_scale) or ln_scale <= 0:
        raise ValueError("Head LayerNorm scale must be finite and positive")
    target = float_ln @ weight.t() + bias
    target_centered = target - target.mean(dim=1, keepdim=True)
    base = _quantize_weight_int8_mse(weight)
    best: dict[str, Any] | None = None
    for multiplier in scale_multipliers:
        weight_scale = base * float(multiplier)
        if not np.isfinite(weight_scale) or weight_scale <= 0:
            continue
        qw = torch.round(weight / weight_scale).clamp(-128, 127).to(torch.int64)
        logit_scale = float(ln_scale * weight_scale)
        qb = torch.round(bias / logit_scale).to(torch.int64)
        if bool(((qb <= INT19_MIN) | (qb > INT19_MAX)).any()):
            continue
        pre = torch.matmul(qln, qw.t()) + qb
        wrapped = _wrap_signed(pre, 19)
        wrap_rate = float(((pre < INT19_MIN) | (pre > INT19_MAX)).double().mean())
        real = wrapped.double() * logit_scale
        centered = real - real.mean(dim=1, keepdim=True)
        mse = float(torch.mean((centered - target_centered) ** 2))
        agreement = float((real.argmax(1) == target.argmax(1)).double().mean())
        candidate = {
            "class_count": 1000,
            "weight_scale": weight_scale,
            "logit_scale": logit_scale,
            "qw": qw,
            "qb": qb,
            "logit_mse_centered": mse,
            "top1_agreement": agreement,
            "accumulator_wrap_rate": wrap_rate,
            "logit_min": int(wrapped.min()),
            "logit_max": int(wrapped.max()),
        }
        key = (wrap_rate, mse)
        if best is None or key < (
            best["accumulator_wrap_rate"],
            best["logit_mse_centered"],
        ):
            best = candidate
    if best is None:
        raise RuntimeError("unable to fit a valid 1000-class W8/int19 Head")
    return best


def validate_head_arrays(arrays: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    if set(arrays) != set(HEAD_ARRAY_SPECS):
        missing = sorted(set(HEAD_ARRAY_SPECS) - set(arrays))
        extra = sorted(set(arrays) - set(HEAD_ARRAY_SPECS))
        raise ValueError(f"Head array membership mismatch; missing={missing}, extra={extra}")
    checked: dict[str, np.ndarray] = {}
    for name, (shape, dtype) in HEAD_ARRAY_SPECS.items():
        value = np.asarray(arrays[name])
        if value.shape != shape or value.dtype != dtype:
            raise ValueError(f"{name} must be {shape}/{dtype}, got {value.shape}/{value.dtype}")
        checked[name] = value
    bias = checked["head_bias"]
    if np.any(bias < INT19_MIN) or np.any(bias > INT19_MAX):
        raise ValueError("Head bias exceeds signed19")
    if np.any(bias == INT19_MIN):
        raise ValueError("Head contains legacy INT19_MIN inactive-class padding")
    return checked


def _lines(values: np.ndarray, width: int, suffix: str = "") -> list[str]:
    flat = np.asarray(values).reshape(-1)
    return [
        "    " + ", ".join(f"{int(v)}{suffix}" for v in flat[i : i + width]) + ","
        for i in range(0, flat.size, width)
    ]


def _head_declarations(arrays: Mapping[str, np.ndarray]) -> list[str]:
    a = validate_head_arrays(arrays)
    rows = [
        "const int HEAD_LN_SCALARS[8] = {"
        + ", ".join(str(int(v)) for v in a["head_ln_scalars"])
        + "};",
        "const int HEAD_LNW[192] = {",
        *_lines(a["head_lnw"], 16),
        "};",
        "const long long HEAD_LNB[192] = {",
        *_lines(a["head_lnb"], 8, "LL"),
        "};",
        "const int HEAD_RSQRT[128] = {",
        *_lines(a["head_rsqrt"], 16),
        "};",
        "const ap_int<8> HEAD_WEIGHT[1000][192] = {",
    ]
    rows.extend(
        "    {" + ", ".join(str(int(v)) for v in row) + "},"
        for row in a["head_weight"]
    )
    rows.extend(["};", "const ap_int<19> HEAD_BIAS[1000] = {"])
    rows.extend(_lines(a["head_bias"], 16))
    rows.append("};")
    return rows


def write_fixed_patch_head_rom(
    path: str | Path, arrays: Mapping[str, np.ndarray]
) -> None:
    """Write the Head namespace fragment consumed by ``block0.cpp``."""

    rows = [
        "#pragma once",
        "#include <ap_int.h>",
        "namespace fixed_patch_head_rom {",
        *_head_declarations(arrays),
        "}  // namespace fixed_patch_head_rom",
        "",
    ]
    Path(path).write_text("\n".join(rows), encoding="utf-8")


def _patch_banks(
    weight: np.ndarray, bias: np.ndarray, cls: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    weight_bank = np.empty((12, 24, 16, 32), dtype=np.int8)
    bias_bank = np.empty((2, 12, 98, 16), dtype=np.int64)
    cls_bank = np.empty((12, 16), dtype=np.int64)
    for co in range(192):
        cop, cot = co % 12, co // 12
        cls_bank[cop, cot] = cls[co]
        for ci in range(768):
            cip, cit = ci % 24, ci // 24
            weight_bank[cop, cip, cot, cit] = weight[co, ci]
        for token in range(196):
            tp, tt = token % 2, token // 2
            bias_bank[tp, cop, tt, cot] = bias[token, co]
    return weight_bank, bias_bank, cls_bank


def _nested_initializer(value: np.ndarray, indent: int = 0) -> list[str]:
    value = np.asarray(value)
    prefix = "    " * indent
    if value.ndim == 1:
        return [prefix + "{" + ", ".join(str(int(v)) for v in value) + "}"]
    rows = [prefix + "{"]
    children = [_nested_initializer(child, indent + 1) for child in value]
    for index, child in enumerate(children):
        child[-1] += "," if index + 1 < len(children) else ""
        rows.extend(child)
    rows.append(prefix + "}")
    return rows


def write_complete_patch_head_rom(
    path: str | Path,
    arrays: Mapping[str, np.ndarray],
    *,
    patch_weight: np.ndarray,
    patch_bias: np.ndarray,
    patch_cls: np.ndarray,
    patch_shift: int,
) -> None:
    """Write the compile-ready existing Patch ABI plus the fitted Head ABI."""

    weight = np.asarray(patch_weight)
    bias = np.asarray(patch_bias)
    cls = np.asarray(patch_cls)
    if weight.shape != (192, 768) or weight.dtype != np.dtype("int8"):
        raise ValueError("Patch weight must be int8[192,768]")
    if bias.shape != (196, 192) or cls.shape != (192,):
        raise ValueError("Patch bias/CLS shapes are incompatible")
    i32 = np.iinfo(np.int32)
    if (
        bias.min() < i32.min
        or bias.max() > i32.max
        or cls.min() < i32.min
        or cls.max() > i32.max
    ):
        raise ValueError("Patch bias/CLS exceed the existing int32 ROM interface")
    weight_bank, bias_bank, cls_bank = _patch_banks(weight, bias, cls)
    rows = [
        "#ifndef __FIXED_PATCH_HEAD_ROM_H__",
        "#define __FIXED_PATCH_HEAD_ROM_H__",
        "#include <ap_int.h>",
        "namespace fixed_patch_head_rom {",
        f"const int PATCH_SCALARS[4] = {{{int(patch_shift)}, 0, 0, 0}};",
        "const int PATCH_WEIGHT[192][768] =",
        *_nested_initializer(weight),
        ";",
        "const int PATCH_BIAS[37632] = {",
        *_lines(bias, 16),
        "};",
        "const int PATCH_CLS[192] = {",
        *_lines(cls, 16),
        "};",
        "const int PATCH_WEIGHT_BANK[12][24][16][32] =",
        *_nested_initializer(weight_bank),
        ";",
        "const int PATCH_BIAS_BANK[2][12][98][16] =",
        *_nested_initializer(bias_bank),
        ";",
        "const int PATCH_CLS_BANK[12][16] =",
        *_nested_initializer(cls_bank),
        ";",
        *_head_declarations(arrays),
        "}  // namespace fixed_patch_head_rom",
        "#endif",
        "",
    ]
    Path(path).write_text("\n".join(rows), encoding="utf-8")


def load_s3_exact_head(path: str | Path) -> S3ExactHead:
    root = Path(path).expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != HEAD_SCHEMA:
        raise ValueError("strict-S3 Head schema mismatch")
    if manifest.get("complete") is not True:
        raise ValueError("strict-S3 Head artifact is incomplete")
    checkpoint = manifest.get("checkpoint")
    encoder = manifest.get("encoder")
    digest = checkpoint.get("sha256") if isinstance(checkpoint, dict) else None
    encoder_digest = encoder.get("checkpoint_sha256") if isinstance(encoder, dict) else None
    if not isinstance(digest, str) or len(digest) != 64 or encoder_digest != digest:
        raise ValueError("Head/encoder checkpoint binding mismatch")
    archive = root / "head_arrays.npz"
    output = manifest.get("outputs", {}).get("head_arrays.npz", {})
    expected = output.get("sha256") if isinstance(output, dict) else None
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if expected != actual:
        raise ValueError("head_arrays.npz SHA-256 mismatch")
    with np.load(archive, allow_pickle=False) as payload:
        arrays = validate_head_arrays({name: payload[name].copy() for name in payload.files})
    return S3ExactHead(root=root, manifest=manifest, arrays=arrays)


__all__ = [
    "HEAD_ARRAY_SPECS",
    "HEAD_SCHEMA",
    "INT19_MAX",
    "INT19_MIN",
    "S3ExactHead",
    "apply_head_layernorm",
    "exact_head_logits",
    "audit_head_accumulation",
    "fit_head_classifier",
    "load_s3_exact_head",
    "validate_head_arrays",
    "write_fixed_patch_head_rom",
    "write_complete_patch_head_rom",
]
