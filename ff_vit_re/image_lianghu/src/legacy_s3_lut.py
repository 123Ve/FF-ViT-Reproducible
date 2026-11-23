"""Histogram-fitted LUTs for the original FF-ViT signed-3 deployment ABI.

This module is a small, dependency-light extraction of the authoritative
PlantVillage Stage4F/Stage4K2 fitting rules.  It does not train a model and it
does not introduce the experimental s8/u8 deployment profile.  Its purpose is
to let the ImageNet path refit the existing HLS tables after S3/U3 QAT using
the integer-code frequencies actually seen in calibration data.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt
from typing import Iterable

import numpy as np


ORIGINAL_HLS_LUT_CONTRACT = {
    "gelu": (64, "uint3"),
    "ln_rsqrt": (128, "int32"),
    "qkv": (64, "sint3"),
    "aq": (64, "sint3"),
    "softmax_exp": (32, "uint16"),
    "softmax_recip": (64, "uint8", 2),
}


@dataclass(frozen=True)
class AddressLutFit:
    bias: int
    shift: int
    bound: int
    table: np.ndarray
    weighted_mse: float
    weighted_mismatch: float
    max_abs_error: int
    cursor_wrap_rate: float
    observed_min: int
    observed_max: int


def _wrap_signed(values: np.ndarray, bits: int) -> np.ndarray:
    modulus = 1 << int(bits)
    half = 1 << (int(bits) - 1)
    return ((values + half) % modulus) - half


def _validate_histogram(histogram: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    counts = np.asarray(histogram, dtype=np.int64)
    if counts.ndim != 1 or counts.size == 0 or counts.size % 2:
        raise ValueError("histogram must be a non-empty even-length vector")
    if np.any(counts < 0):
        raise ValueError("histogram counts cannot be negative")
    code_min = -(counts.size // 2)
    all_codes = np.arange(code_min, code_min + counts.size, dtype=np.int64)
    mask = counts > 0
    if not np.any(mask):
        raise ValueError("histogram contains no observations")
    return all_codes[mask], counts[mask].astype(np.float64), mask


def _nearest_fill(table: np.ndarray, used: np.ndarray) -> None:
    for address in range(table.size):
        if address not in used:
            nearest = used[np.argmin(np.abs(used - address))]
            table[address] = table[nearest]


def _fit_table(
    *,
    inputs: np.ndarray,
    counts: np.ndarray,
    target: np.ndarray,
    bias: int,
    shift: int,
    qmin: int,
    qmax: int,
    cursor_bits: int | None,
) -> AddressLutFit:
    raw = (inputs + int(bias)) // (1 << int(shift))
    cursor = _wrap_signed(raw, cursor_bits) if cursor_bits is not None else raw
    address = np.clip(cursor, 0, 63).astype(np.int64)
    table = np.zeros(64, dtype=np.int64)
    used = np.unique(address)
    for entry in used:
        selected = address == entry
        weighted_mean = np.sum(counts[selected] * target[selected]) / np.sum(counts[selected])
        table[entry] = int(np.clip(np.rint(weighted_mean), qmin, qmax))
    _nearest_fill(table, used)
    prediction = table[address]
    error = prediction - target
    total = float(np.sum(counts))
    wrap = np.zeros(raw.shape, dtype=bool)
    if cursor_bits is not None:
        half = 1 << (cursor_bits - 1)
        wrap = (raw < -half) | (raw > half - 1)
    return AddressLutFit(
        bias=int(bias),
        shift=int(shift),
        bound=63,
        table=table.astype(np.uint8 if qmin == 0 else np.int8),
        weighted_mse=float(np.sum(counts * error**2) / total),
        weighted_mismatch=float(np.sum(counts * (error != 0)) / total),
        max_abs_error=int(np.max(np.abs(error))),
        cursor_wrap_rate=float(np.sum(counts * wrap) / total),
        observed_min=int(inputs.min()),
        observed_max=int(inputs.max()),
    )


def apply_address_lut(
    codes: np.ndarray, fit: AddressLutFit, *, cursor_bits: int | None
) -> np.ndarray:
    """Apply the HLS order: shift, optional narrow/wrap, clamp, table."""

    values = np.asarray(codes, dtype=np.int64)
    raw = (values + fit.bias) // (1 << fit.shift)
    cursor = _wrap_signed(raw, cursor_bits) if cursor_bits is not None else raw
    address = np.clip(cursor, 0, fit.bound).astype(np.int64)
    return fit.table[address]


def fit_gelu_u3_lut(
    histogram: np.ndarray,
    *,
    input_scale: float,
    output_scale: float,
    shifts: Iterable[int] = range(9),
    bias_radius: int = 192,
) -> AddressLutFit:
    """Refit the original 64-entry GELU U3 LUT from an int11 histogram."""

    if np.asarray(histogram).size != 2048:
        raise ValueError("GELU histogram must cover signed int11 [-1024,1023]")
    if input_scale <= 0 or output_scale <= 0:
        raise ValueError("quantization scales must be positive")
    inputs, counts, _ = _validate_histogram(histogram)
    real = inputs.astype(np.float64) * float(input_scale)
    gelu = 0.5 * real * (1.0 + np.vectorize(erf)(real / sqrt(2.0)))
    target = np.clip(np.rint(gelu / float(output_scale)), 0, 7).astype(np.int64)
    natural_bias = -int(inputs.min())
    best: AddressLutFit | None = None
    for shift in shifts:
        for bias in range(natural_bias - bias_radius, natural_bias + bias_radius + 1):
            candidate = _fit_table(
                inputs=inputs,
                counts=counts,
                target=target,
                bias=bias,
                shift=int(shift),
                qmin=0,
                qmax=7,
                cursor_bits=None,
            )
            key = (
                candidate.weighted_mse,
                candidate.weighted_mismatch,
                candidate.shift,
                abs(candidate.bias - natural_bias),
            )
            if best is None or key < (
                best.weighted_mse,
                best.weighted_mismatch,
                best.shift,
                abs(best.bias - natural_bias),
            ):
                best = candidate
    if best is None:
        raise ValueError("no GELU LUT candidates were requested")
    return best


def fit_signed_s3_requant_lut(
    histogram: np.ndarray,
    *,
    accumulator_scale: float,
    output_scale: float,
    cursor_bits: int,
    shifts: Iterable[int] = range(11),
) -> AddressLutFit:
    """Fit an original Q/K/V/AQ 64-entry signed-3 requantization LUT.

    Q/K/V call this with ``cursor_bits=9``; AQ uses ``cursor_bits=10``.
    Candidate addresses are centered on the unsaturated S3 transition region,
    matching Stage4K2 rather than wasting entries on saturated tails.
    """

    if accumulator_scale <= 0 or output_scale <= 0:
        raise ValueError("quantization scales must be positive")
    if cursor_bits not in (9, 10):
        raise ValueError("original HLS QKV/AQ cursors are signed int9/int10")
    inputs, counts, _ = _validate_histogram(histogram)
    target = np.clip(
        np.rint(inputs.astype(np.float64) * accumulator_scale / output_scale), -4, 3
    ).astype(np.int64)
    moving = (target > -4) & (target < 3)
    transition_min = int(inputs[moving].min()) if np.any(moving) else int(inputs.min())
    best: AddressLutFit | None = None
    best_offset = 0
    for shift in shifts:
        shift = int(shift)
        step = 1 << shift
        for offset in (0, 1, 2, 4, 8):
            base = (1 + offset) * step - transition_min
            for phase in range(step):
                candidate = _fit_table(
                    inputs=inputs,
                    counts=counts,
                    target=target,
                    bias=base + phase,
                    shift=shift,
                    qmin=-4,
                    qmax=3,
                    cursor_bits=cursor_bits,
                )
                key = (
                    candidate.weighted_mismatch,
                    candidate.weighted_mse,
                    candidate.max_abs_error,
                    candidate.cursor_wrap_rate,
                    candidate.shift,
                    abs(offset),
                )
                if best is None or key < (
                    best.weighted_mismatch,
                    best.weighted_mse,
                    best.max_abs_error,
                    best.cursor_wrap_rate,
                    best.shift,
                    abs(best_offset),
                ):
                    best = candidate
                    best_offset = offset
    if best is None:
        raise ValueError("no requantization LUT candidates were requested")
    return best


def fit_aq_joint_s3_lut(
    pair_counts: np.ndarray,
    *,
    shifts: Iterable[int] = range(11),
) -> AddressLutFit:
    """Fit AQ from the joint ``(int11 aggregate, QAT S3 target)`` histogram.

    Unlike Q/K/V, AQ follows an approximate integer Softmax.  Consequently a
    single aggregate input code can have several QAT targets.  Stage4L fits
    each table entry to the most frequent target over all codes sharing that
    address; this function preserves that classification-optimal rule.
    """

    pairs = np.asarray(pair_counts, dtype=np.int64)
    if pairs.ndim != 2 or pairs.shape[1] != 8 or pairs.shape[0] % 2:
        raise ValueError("AQ pair histogram must have shape [even code range, 8]")
    if np.any(pairs < 0):
        raise ValueError("AQ pair counts cannot be negative")
    totals_all = pairs.sum(axis=1)
    mask = totals_all > 0
    if not np.any(mask):
        raise ValueError("AQ pair histogram contains no observations")
    code_min = -(pairs.shape[0] // 2)
    inputs = np.arange(code_min, code_min + pairs.shape[0], dtype=np.int64)[mask]
    observed = pairs[mask]
    totals = totals_all[mask].astype(np.float64)
    modal = np.argmax(observed, axis=1) - 4
    moving = (modal > -4) & (modal < 3)
    transition_min = int(inputs[moving].min()) if np.any(moving) else int(inputs.min())
    target_codes = np.arange(-4, 4, dtype=np.int64)
    best: AddressLutFit | None = None
    best_offset = 0
    for shift in shifts:
        shift = int(shift)
        step = 1 << shift
        for offset in (0, 1, 2, 4, 8):
            base = (1 + offset) * step - transition_min
            for phase in range(step):
                bias = int(base + phase)
                raw = (inputs + bias) // step
                cursor = _wrap_signed(raw, 10)
                address = np.clip(cursor, 0, 63).astype(np.int64)
                table = np.zeros(64, dtype=np.int64)
                used = np.unique(address)
                correct = 0
                squared_error = 0.0
                max_error = 0
                for entry in used:
                    rows = address == entry
                    aggregate = observed[rows].sum(axis=0)
                    selected = int(np.argmax(aggregate))
                    table[entry] = selected - 4
                    correct += int(aggregate[selected])
                    errors = target_codes - table[entry]
                    squared_error += float(np.sum(aggregate * errors**2))
                    nonzero = aggregate > 0
                    if np.any(nonzero):
                        max_error = max(max_error, int(np.max(np.abs(errors[nonzero]))))
                _nearest_fill(table, used)
                total = float(observed.sum())
                wrap = (raw < -512) | (raw > 511)
                candidate = AddressLutFit(
                    bias=bias,
                    shift=shift,
                    bound=63,
                    table=table.astype(np.int8),
                    weighted_mse=squared_error / total,
                    weighted_mismatch=1.0 - correct / total,
                    max_abs_error=max_error,
                    cursor_wrap_rate=float(np.sum(totals * wrap) / total),
                    observed_min=int(inputs.min()),
                    observed_max=int(inputs.max()),
                )
                key = (
                    candidate.weighted_mismatch,
                    candidate.weighted_mse,
                    candidate.max_abs_error,
                    candidate.cursor_wrap_rate,
                    candidate.shift,
                    abs(offset),
                )
                if best is None or key < (
                    best.weighted_mismatch,
                    best.weighted_mse,
                    best.max_abs_error,
                    best.cursor_wrap_rate,
                    best.shift,
                    abs(best_offset),
                ):
                    best = candidate
                    best_offset = offset
    if best is None:
        raise ValueError("no AQ LUT candidates were requested")
    return best
