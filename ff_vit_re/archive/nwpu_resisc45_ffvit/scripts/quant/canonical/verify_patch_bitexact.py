#!/usr/bin/env python3
"""Independent integer oracle for the active FF-ViT Patch frontend."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np


def signed_wrap(values: np.ndarray, bits: int) -> np.ndarray:
    values = np.asarray(values, dtype=np.int64)
    modulus = 1 << bits
    half = 1 << (bits - 1)
    return ((values + half) % modulus) - half


def compute_patch_from_banks(
    physical_input: np.ndarray,
    weight_bank: np.ndarray,
    bias_bank: np.ndarray,
    cls_bank: np.ndarray,
    *,
    shift: int,
    output_bits: int,
) -> np.ndarray:
    """Return logical `[token, channel]` output using the HLS loop contract."""
    physical_input = np.asarray(physical_input, dtype=np.int64)
    weight_bank = np.asarray(weight_bank, dtype=np.int64)
    bias_bank = np.asarray(bias_bank, dtype=np.int64)
    cls_bank = np.asarray(cls_bank, dtype=np.int64)

    cop, cip, cot, cit = weight_bank.shape
    tt, ci, tp = physical_input.shape
    if ci != cit * cip:
        raise ValueError(f"input channels {ci} != CIT*CIP {cit * cip}")
    if bias_bank.shape != (tp, cop, tt, cot):
        raise ValueError(
            f"bias shape {bias_bank.shape} != {(tp, cop, tt, cot)}"
        )
    if cls_bank.shape != (cop, cot):
        raise ValueError(f"CLS shape {cls_bank.shape} != {(cop, cot)}")

    # Adapter<...,CIP=1,COP=24> emits [tt,cit,tp,cip].
    adapted = physical_input.reshape(tt, cit, cip, tp).transpose(0, 1, 3, 2)
    accum = np.einsum(
        "acpi,qibc->apbq",
        adapted,
        weight_bank,
        optimize=True,
    )
    accum += bias_bank.transpose(2, 0, 3, 1)
    accum[0, 0] = cls_bank.T

    round_bias = (1 << (shift - 1)) if shift > 0 else 0
    shifted = (accum + round_bias) >> shift
    wrapped = signed_wrap(shifted, output_bits)
    return wrapped.reshape(tt * tp, cot * cop)


def parse_c_array(path: Path, name: str, shape: tuple[int, ...]) -> np.ndarray:
    text = path.read_text(encoding="utf-8")
    declaration = re.search(
        rf"(?m)^const\s+[^\n;]+\b{re.escape(name)}\s*\[[^;=]*=",
        text,
    )
    if declaration is None:
        raise KeyError(f"{name} not found in {path}")

    begin = text.index("{", declaration.end())
    depth = 0
    end = None
    for index in range(begin, len(text)):
        depth += int(text[index] == "{")
        depth -= int(text[index] == "}")
        if depth == 0:
            end = index
            break
    if end is None:
        raise ValueError(f"unterminated array {name} in {path}")

    values = np.array(
        [int(item) for item in re.findall(r"(?<![A-Za-z_])-?\d+", text[begin + 1:end])],
        dtype=np.int64,
    )
    expected = int(np.prod(shape))
    if values.size != expected:
        raise ValueError(f"{name} has {values.size} values, expected {expected}")
    return values.reshape(shape)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare(actual: np.ndarray, expected: np.ndarray) -> dict[str, object]:
    actual = np.asarray(actual).reshape(-1)
    expected = np.asarray(expected).reshape(-1)
    if actual.size != expected.size:
        return {
            "actual_values": int(actual.size),
            "expected_values": int(expected.size),
            "matches": 0,
            "mismatches": max(int(actual.size), int(expected.size)),
            "first_mismatches": [],
        }
    bad = np.flatnonzero(actual != expected)
    return {
        "actual_values": int(actual.size),
        "expected_values": int(expected.size),
        "matches": int(actual.size - bad.size),
        "mismatches": int(bad.size),
        "first_mismatches": [
            {
                "index": int(index),
                "actual": int(actual[index]),
                "expected": int(expected[index]),
            }
            for index in bad[:20]
        ],
    }

