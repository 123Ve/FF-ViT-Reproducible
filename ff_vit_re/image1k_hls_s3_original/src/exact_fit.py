"""Original ABI fitter port; source provenance is recorded by build_exact."""
from __future__ import annotations
import math
from collections.abc import Mapping
import numpy as np
import torch
INPUT_SCALE = 1.0 / 64.0
PATCH_SHIFT = 8
PATCH_OUTPUT_BITS = 13

def _tensor(mapping: Mapping[str, object], name: str) -> torch.Tensor:
    value = mapping.get(name)
    if not isinstance(value, torch.Tensor):
        raise ValueError(f"checkpoint tensor is missing: {name}")
    return value.detach().cpu()


def _positive_exp(mapping: Mapping[str, object], name: str, count: int = 12) -> torch.Tensor:
    value = _tensor(mapping, name).to(torch.float32).exp()
    if value.shape != (count,) or not bool(torch.isfinite(value).all()) or not bool((value > 0).all()):
        raise ValueError(f"invalid positive scale tensor: {name}")
    return value


def _fit_rescale(input_scale: float, output_scale: float, qmin: int, qmax: int) -> dict[str, object]:
    if not all(math.isfinite(value) and value > 0 for value in (input_scale, output_scale)):
        raise ValueError("rescale domains must be finite and positive")
    ratio = input_scale / output_scale
    codes = torch.arange(qmin, qmax + 1, dtype=torch.int64)
    ideal = torch.round(codes.to(torch.float64) * ratio).to(torch.int64)
    best: tuple[tuple[float, float, int, int, int], dict[str, object]] | None = None
    for shift in range(21):
        multiplier = int(round(ratio * (1 << shift)))
        if not -(1 << 31) <= multiplier <= (1 << 31) - 1:
            continue
        bias = (1 << (shift - 1)) if shift else 0
        predicted = torch.bitwise_right_shift(codes * multiplier + bias, shift)
        error = predicted - ideal
        row = {
            "RM": multiplier,
            "RS": shift,
            "RB": bias,
            "input_scale": float(input_scale),
            "output_scale": float(output_scale),
            "qmin": int(qmin),
            "qmax": int(qmax),
            "mismatch_rate": float((error != 0).to(torch.float64).mean()),
            "mse": float((error.to(torch.float64) ** 2).mean()),
            "max_abs_error": int(error.abs().max()),
        }
        key = (
            float(row["mismatch_rate"]),
            float(row["mse"]),
            int(row["max_abs_error"]),
            shift,
            abs(multiplier),
        )
        if best is None or key < best[0]:
            best = (key, row)
    if best is None:
        raise ValueError("no int32 residual multiplier candidate")
    return best[1]


def _wrap_signed_numpy(value: np.ndarray, bits: int) -> np.ndarray:
    modulus = 1 << bits
    half = 1 << (bits - 1)
    return ((np.asarray(value, dtype=np.int64) + half) % modulus) - half


def _patch_banks(
    weight: np.ndarray, bias: np.ndarray, cls: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if weight.shape != (192, 768) or bias.shape != (196, 192) or cls.shape != (192,):
        raise ValueError("invalid logical Patch artifact shape")
    weight_bank = np.zeros((12, 24, 16, 32), dtype=np.int8)
    bias_bank = np.zeros((2, 12, 98, 16), dtype=np.int64)
    cls_bank = np.zeros((12, 16), dtype=np.int64)
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


def fit_patch_artifacts(student_state: Mapping[str, object]) -> dict[str, object]:
    """Fit the verified Stage3 global-int8 Patch contract from real tensors."""

    weight = _tensor(student_state, "vit.patch_embed.proj.weight").to(torch.float32)
    bias = _tensor(student_state, "vit.patch_embed.proj.bias").to(torch.float32)
    pos = _tensor(student_state, "vit.pos_embed").to(torch.float32)
    cls = _tensor(student_state, "vit.cls_token").to(torch.float32)
    if weight.shape != (192, 3, 16, 16) or bias.shape != (192,):
        raise ValueError("checkpoint Patch projection shape mismatch")
    if pos.shape != (1, 197, 192) or cls.shape != (1, 1, 192):
        raise ValueError("checkpoint HLS196 CLS/position shape mismatch")
    flat = weight.reshape(192, 768)
    maximum = float(flat.abs().max())
    if not math.isfinite(maximum) or maximum <= 0:
        raise ValueError("Patch weight must contain finite nonzero values")
    best: tuple[float, float, torch.Tensor, float] | None = None
    for index in range(121):
        alpha = maximum * (0.70 + 0.30 * index / 120)
        scale = alpha / 127.0
        code = torch.round(flat / scale).clamp(-128, 127).to(torch.int8)
        dequant = code.to(torch.float32) * scale
        mse = float(((flat - dequant) ** 2).mean())
        saturation = float(((code == -128) | (code == 127)).to(torch.float32).mean())
        if best is None or mse < best[0]:
            best = (mse, scale, code, saturation)
    assert best is not None
    mse, weight_scale, weight_code, saturation = best
    raw_scale = INPUT_SCALE * weight_scale
    output_scale = raw_scale * (1 << PATCH_SHIFT)
    # HLS196 keeps standard token indices [0,2..196]: CLS at 0 and Patch[1..195].
    selected_pos = torch.cat((pos[0, :1], pos[0, 2:]), dim=0)
    bias_raw = torch.round((bias.unsqueeze(0) + selected_pos) / raw_scale).to(torch.int64)
    bias_raw[0].zero_()
    cls_raw = torch.round((cls[0, 0] + pos[0, 0]) / raw_scale).to(torch.int64)
    i32_min, i32_max = -(1 << 31), (1 << 31) - 1
    if int(bias_raw.min()) < i32_min or int(bias_raw.max()) > i32_max:
        raise ValueError("Patch bias raw values do not fit int32")
    if int(cls_raw.min()) < i32_min or int(cls_raw.max()) > i32_max:
        raise ValueError("Patch CLS raw values do not fit int32")
    logical_weight = weight_code.numpy()
    logical_bias = bias_raw.numpy()
    logical_cls = cls_raw.numpy()
    weight_bank, bias_bank, cls_bank = _patch_banks(logical_weight, logical_bias, logical_cls)
    return {
        "weight_code": logical_weight,
        "bias_raw": logical_bias,
        "cls_raw": logical_cls,
        "weight_bank": weight_bank,
        "bias_bank": bias_bank,
        "cls_bank": cls_bank,
        "scalars": np.asarray([PATCH_SHIFT, 0, 0, 0], dtype=np.int32),
        "shift": PATCH_SHIFT,
        "input_scale": INPUT_SCALE,
        "weight_scale": weight_scale,
        "raw_scale": raw_scale,
        "output_scale": output_scale,
        "weight_mse": mse,
        "weight_saturation_rate": saturation,
    }


def integer_patch_codes(input_codes: torch.Tensor, patch: Mapping[str, object]) -> torch.Tensor:
    code = input_codes.detach().cpu().to(torch.int64)
    if tuple(code.shape[-2:]) != (196, 768):
        raise ValueError("Patch input codes must end with [196,768]")
    if code.numel() and (int(code.min()) < -32768 or int(code.max()) > 32767):
        raise ValueError("Patch input codes exceed signed int16")
    weight = torch.from_numpy(np.asarray(patch["weight_code"], dtype=np.int8)).to(torch.int64)
    bias = torch.from_numpy(np.asarray(patch["bias_raw"], dtype=np.int64))
    cls = torch.from_numpy(np.asarray(patch["cls_raw"], dtype=np.int64))
    accumulator = torch.matmul(code, weight.t()) + bias
    accumulator[..., 0, :] = cls
    shifted = torch.bitwise_right_shift(accumulator + (1 << (PATCH_SHIFT - 1)), PATCH_SHIFT)
    modulus, half = 1 << PATCH_OUTPUT_BITS, 1 << (PATCH_OUTPUT_BITS - 1)
    return torch.remainder(shifted + half, modulus) - half


def image_to_patch_codes(image: torch.Tensor) -> torch.Tensor:
    """Quantize normalized CHW input and unfold in Conv2d/HLS semantic order."""

    if image.shape != (3, 224, 224) or not image.is_floating_point():
        raise ValueError("normalized Patch image must be floating [3,224,224]")
    # CPU im2col does not implement integer dtypes.  Preserve Stage3 ordering:
    # round/clamp to integer-valued float, unfold, then cast to int64 codes.
    quantized_float = torch.round(image.detach().cpu().to(torch.float32) * 64.0).clamp(
        -32768, 32767
    )
    return (
        torch.nn.functional.unfold(
            quantized_float.unsqueeze(0), kernel_size=16, stride=16
        )
        .transpose(1, 2)
        .contiguous()[0]
        .to(torch.int64)
    )


def patch_from_banks(
    physical_input: np.ndarray,
    weight_bank: np.ndarray,
    bias_bank: np.ndarray,
    cls_bank: np.ndarray,
    *,
    shift: int,
) -> np.ndarray:
    """Independent HLS-loop-layout Patch oracle returning logical token/channel order."""

    physical = np.asarray(physical_input, dtype=np.int64)
    if physical.shape != (98, 768, 2):
        raise ValueError("physical Patch input must have shape [98,768,2]")
    adapted = physical.reshape(98, 32, 24, 2).transpose(0, 1, 3, 2)
    accumulator = np.einsum(
        "acpi,qibc->apbq", adapted, np.asarray(weight_bank, dtype=np.int64), optimize=True
    )
    accumulator += np.asarray(bias_bank, dtype=np.int64).transpose(2, 0, 3, 1)
    accumulator[0, 0] = np.asarray(cls_bank, dtype=np.int64).T
    rounding = (1 << (shift - 1)) if shift else 0
    shifted = (accumulator + rounding) >> shift
    return _wrap_signed_numpy(shifted, PATCH_OUTPUT_BITS).reshape(196, 192)


def diagnose_patch_codes(
    input_codes: torch.Tensor,
    patch: Mapping[str, object],
    student_state: Mapping[str, object],
) -> dict[str, object]:
    """Compare exact Patch codes to an independent bank oracle and FP32 surrogate."""

    code = input_codes.detach().cpu().to(torch.int64)
    if code.shape != (196, 768):
        raise ValueError("Patch diagnostic requires one semantic [196,768] input")
    exact = integer_patch_codes(code, patch)
    physical = code.reshape(98, 2, 768).permute(0, 2, 1).contiguous().numpy()
    independent = patch_from_banks(
        physical,
        np.asarray(patch["weight_bank"]),
        np.asarray(patch["bias_bank"]),
        np.asarray(patch["cls_bank"]),
        shift=int(patch["shift"]),
    )
    bank_mismatches = int(np.count_nonzero(exact.numpy() != independent))

    weight = _tensor(student_state, "vit.patch_embed.proj.weight").to(torch.float32).reshape(192, 768)
    bias = _tensor(student_state, "vit.patch_embed.proj.bias").to(torch.float32)
    pos = _tensor(student_state, "vit.pos_embed").to(torch.float32)[0]
    cls = _tensor(student_state, "vit.cls_token").to(torch.float32)[0, 0]
    surrogate = torch.matmul(code.to(torch.float32) * INPUT_SCALE, weight.t()) + bias
    surrogate[0] = cls + pos[0]
    surrogate[1:] += pos[2:]
    output_scale = float(patch["output_scale"])
    dequantized = exact.to(torch.float32) * output_scale
    target_unwrapped = torch.round(surrogate / output_scale).to(torch.int64)
    target = torch.from_numpy(_wrap_signed_numpy(target_unwrapped.numpy(), PATCH_OUTPUT_BITS))
    difference = dequantized - surrogate
    return {
        "independent_bank_mismatches": bank_mismatches,
        "value_count": int(exact.numel()),
        "surrogate_code_agreement_count": int((exact == target).sum()),
        "surrogate_code_agreement_rate": float((exact == target).to(torch.float64).mean()),
        "surrogate_mae": float(difference.abs().mean()),
        "surrogate_max_abs_error": float(difference.abs().max()),
        "input_code_min": int(code.min()),
        "input_code_max": int(code.max()),
        "exact_code_min": int(exact.min()),
        "exact_code_max": int(exact.max()),
        "output_scale": output_scale,
    }


def _wrap_signed_torch(value: torch.Tensor, bits: int) -> torch.Tensor:
    modulus, half = 1 << bits, 1 << (bits - 1)
    return torch.remainder(value.to(torch.int64) + half, modulus) - half


def _choose_channel_reciprocal(accumulator: torch.Tensor) -> dict[str, int | float]:
    best: tuple[tuple[float, int], dict[str, int | float]] | None = None
    for shift in range(8, 18):
        multiplier = int(round((1 << shift) / 192))
        temporary = accumulator * multiplier + (1 << (shift - 1))
        if int(temporary.min()) < -(1 << 31) or int(temporary.max()) > (1 << 31) - 1:
            continue
        mean = torch.bitwise_right_shift(temporary, shift)
        mse = float(((mean.to(torch.float64) - accumulator / 192.0) ** 2).mean())
        row = {"m": multiplier, "s": shift, "mse": mse}
        key = (mse, -shift)
        if best is None or key < best[0]:
            best = (key, row)
    if best is None:
        raise ValueError("no safe LayerNorm channel reciprocal")
    return best[1]


def fit_layernorm_codes(
    input_codes: torch.Tensor,
    target_codes: torch.Tensor,
    *,
    input_scale: float,
    eps: float,
    output_bits: int,
    input_bits: int = 13,
) -> dict[str, object]:
    """Fit the verified 128-entry HLS LayerNorm using integer input/target codes."""

    x = input_codes.detach().cpu().to(torch.int64)
    target = target_codes.detach().cpu().to(torch.int64)
    if x.ndim != 2 or x.shape[1] != 192 or target.shape != x.shape:
        raise ValueError("LayerNorm fitting expects matching [tokens,192] codes")
    qmin, qmax = -(1 << (output_bits - 1)), (1 << (output_bits - 1)) - 1
    if int(target.min()) < qmin or int(target.max()) > qmax:
        raise ValueError("LayerNorm target is outside the requested output width")
    in_min, in_max = -(1 << (input_bits - 1)), (1 << (input_bits - 1)) - 1
    if int(x.min()) < in_min or int(x.max()) > in_max:
        raise ValueError("LayerNorm input code overflows its HLS width")
    accumulator = x.sum(dim=1)
    reciprocal = _choose_channel_reciprocal(accumulator)
    temporary = _wrap_signed_torch(
        accumulator * int(reciprocal["m"]) + (1 << (int(reciprocal["s"]) - 1)), 32
    )
    mean = torch.bitwise_right_shift(temporary, int(reciprocal["s"]))
    diff_pre = x - mean[:, None]
    centered_wrap = (diff_pre < in_min) | (diff_pre > in_max)
    centered_wrap_rows = centered_wrap.any(dim=1)
    diff = _wrap_signed_torch(diff_pre, input_bits)
    variance_pre = (x * x).sum(dim=1) - 2 * mean * accumulator + 192 * mean * mean
    if int(variance_pre.min()) < 0 or int(variance_pre.max()) > (1 << 35) - 1:
        raise ValueError("LayerNorm variance path overflows signed int36")
    variance = _wrap_signed_torch(variance_pre, 36)

    ideal_rsqrt = 1.0 / torch.sqrt(
        variance.to(torch.float64) / 192.0 + float(eps) / (float(input_scale) ** 2)
    )
    vmin, vmax = int(variance.min()), int(variance.max())
    rsqrt_best = None
    for address_bias in sorted({0, -vmin if vmin <= (1 << 31) - 1 else 0}):
        shifted_max = vmax + address_bias
        minimum_shift = 0
        while (shifted_max >> minimum_shift) > 127:
            minimum_shift += 1
        for shift1 in range(minimum_shift, minimum_shift + 4):
            address = torch.bitwise_right_shift(variance + address_bias, shift1).clamp(0, 127)
            table = torch.zeros(128, dtype=torch.int64)
            used = torch.zeros(128, dtype=torch.bool)
            for index in range(128):
                mask = address == index
                if bool(mask.any()):
                    table[index] = int(round(float(ideal_rsqrt[mask].mean()) * (1 << 20)))
                    used[index] = True
            used_indices = torch.where(used)[0]
            for index in range(128):
                if not bool(used[index]):
                    nearest = used_indices[torch.argmin((used_indices - index).abs())]
                    table[index] = table[int(nearest)]
            approximation = table[address].to(torch.float64) / float(1 << 20)
            mse = float(((approximation - ideal_rsqrt) ** 2).mean())
            relative = (approximation - ideal_rsqrt).abs() / ideal_rsqrt.abs().clamp_min(1e-18)
            p999 = float(torch.quantile(relative, 0.999))
            key = (mse, p999, shift1)
            row = {
                "b": address_bias,
                "s1": shift1,
                "bound": 127,
                "table": table,
                "mse": mse,
                "rel_p999": p999,
            }
            if rsqrt_best is None or key < rsqrt_best[0]:
                rsqrt_best = (key, row)
    if rsqrt_best is None:
        raise ValueError("could not fit LayerNorm rsqrt table")
    rsqrt = rsqrt_best[1]
    address = torch.bitwise_right_shift(
        variance + int(rsqrt["b"]), int(rsqrt["s1"])
    ).clamp(0, int(rsqrt["bound"]))
    rsqrt_codes = rsqrt["table"][address]
    u = diff * rsqrt_codes[:, None]
    uf, yf = u.to(torch.float64), target.to(torch.float64)
    mean_u = uf.mean(dim=0)
    variance_u = ((uf - mean_u) ** 2).mean(dim=0)
    affine_best = None
    for shift2 in range(8, 31):
        scaled_target = yf * float(1 << shift2)
        mean_y = scaled_target.mean(dim=0)
        covariance = ((uf - mean_u) * (scaled_target - mean_y)).mean(dim=0)
        weight = torch.zeros(192, dtype=torch.int64)
        nonzero = variance_u > 1e-20
        weight[nonzero] = torch.round(covariance[nonzero] / variance_u[nonzero]).to(torch.int64)
        bias = torch.round(mean_y - mean_u * weight).to(torch.int64) + (1 << (shift2 - 1))
        value_pre = u * weight[None, :] + bias[None, :]
        if int(value_pre.min()) < -(1 << 39) or int(value_pre.max()) > (1 << 39) - 1:
            continue
        shifted = torch.bitwise_right_shift(_wrap_signed_torch(value_pre, 40), shift2)
        predicted = _wrap_signed_torch(shifted, 32).clamp(qmin, qmax)
        error = predicted - target
        row = {
            "s2": shift2,
            "lnw": weight,
            "lnb": bias,
            "mismatch": float((error != 0).to(torch.float64).mean()),
            "mse": float((error.to(torch.float64) ** 2).mean()),
            "maxerr": int(error.abs().max()),
        }
        key = (row["mismatch"], row["mse"], row["maxerr"], shift2)
        if affine_best is None or key < affine_best[0]:
            affine_best = (key, row)
    if affine_best is None:
        raise ValueError("could not fit safe LayerNorm affine")
    affine = affine_best[1]
    return {
        "input_scale": float(input_scale),
        "scalars": np.asarray(
            [
                int(reciprocal["m"]),
                int(reciprocal["s"]),
                int(rsqrt["b"]),
                int(rsqrt["s1"]),
                int(rsqrt["bound"]),
                int(affine["s2"]),
                int(output_bits),
            ],
            dtype=np.int32,
        ),
        "lnw": affine["lnw"].numpy().astype(np.int32),
        "lnb": affine["lnb"].numpy().astype(np.int64),
        "rsqrt_table": rsqrt["table"].numpy().astype(np.int32),
        "stats": {
            "input_min": int(x.min()),
            "input_max": int(x.max()),
            "diff_pre_min": int(diff_pre.min()),
            "diff_pre_max": int(diff_pre.max()),
            "centered_wrap_value_count": int(centered_wrap.sum()),
            "centered_wrap_value_rate": float(centered_wrap.to(torch.float64).mean()),
            "centered_wrap_row_count": int(centered_wrap_rows.sum()),
            "centered_wrap_row_rate": float(centered_wrap_rows.to(torch.float64).mean()),
            "diff_min": int(diff.min()),
            "diff_max": int(diff.max()),
            "var_min": int(variance.min()),
            "var_max": int(variance.max()),
            "rsqrt_rel_p999": float(rsqrt["rel_p999"]),
            "affine_mismatch_rate": float(affine["mismatch"]),
            "affine_code_mse": float(affine["mse"]),
            "affine_max_abs_code_error": int(affine["maxerr"]),
        },
    }


def apply_layernorm_codes(
    input_codes: torch.Tensor,
    fitted: Mapping[str, object],
    *,
    input_bits: int,
    output_bits: int,
) -> torch.Tensor:
    x = input_codes.detach().cpu().to(torch.int64)
    scalars = np.asarray(fitted["scalars"], dtype=np.int64)
    c1m, c1s, address_bias, shift1, bound, shift2, recorded_bits = map(int, scalars)
    if recorded_bits != output_bits:
        raise ValueError("LayerNorm output width disagrees with fitted scalars")
    accumulator = x.sum(dim=-1)
    temporary = _wrap_signed_torch(accumulator * c1m + (1 << (c1s - 1)), 32)
    mean = torch.bitwise_right_shift(temporary, c1s)
    diff = _wrap_signed_torch(x - mean.unsqueeze(-1), input_bits)
    variance = _wrap_signed_torch(
        (x * x).sum(dim=-1) - 2 * mean * accumulator + 192 * mean * mean, 36
    )
    address = torch.bitwise_right_shift(variance + address_bias, shift1).clamp(0, bound)
    table = torch.from_numpy(np.asarray(fitted["rsqrt_table"], dtype=np.int32)).to(torch.int64)
    weight = torch.from_numpy(np.asarray(fitted["lnw"], dtype=np.int32)).to(torch.int64)
    bias = torch.from_numpy(np.asarray(fitted["lnb"], dtype=np.int64))
    affine = _wrap_signed_torch(diff * table[address].unsqueeze(-1) * weight + bias, 40)
    shifted = torch.bitwise_right_shift(affine, shift2)
    qmin, qmax = -(1 << (output_bits - 1)), (1 << (output_bits - 1)) - 1
    return _wrap_signed_torch(shifted, 32).clamp(qmin, qmax)



