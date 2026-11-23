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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hls-root",
        type=Path,
        default=Path("/home/user/Desktop/FF_Vit/flash_vit_2"),
    )
    parser.add_argument("--stage3", type=Path, default=Path("stage3_patch_hls"))
    parser.add_argument(
        "--dump",
        type=Path,
        default=Path(
            "/home/user/Desktop/FF_Vit/flash_vit_2/flash_vit/"
            "vit_patch_debug/hls/csim/build/hls_patch_out.bin"
        ),
    )
    parser.add_argument(
        "--safe-head",
        type=Path,
        default=Path("stage4o2_head_safe/generated_head_rom_safe.h"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("bitexact_audit/patch_verification.json"),
    )
    args = parser.parse_args()

    rom = args.hls_root / "src/fixed_patch_head_rom.h"
    shapes = {
        "PATCH_WEIGHT_BANK": (12, 24, 16, 32),
        "PATCH_BIAS_BANK": (2, 12, 98, 16),
        "PATCH_CLS_BANK": (12, 16),
        "PATCH_SCALARS": (4,),
    }
    active = {name: parse_c_array(rom, name, shape) for name, shape in shapes.items()}
    frozen = np.load(args.stage3 / "patch_rom_banks.npz")

    rom_checks = {
        name: compare(active[name], frozen[name])
        for name in shapes
    }

    input_path = args.hls_root / "input.bin"
    semantic = np.fromfile(input_path, dtype="<i4").reshape(196, 768).astype(np.int64)
    physical = semantic.reshape(98, 2, 768).transpose(0, 2, 1)
    logical = compute_patch_from_banks(
        physical,
        active["PATCH_WEIGHT_BANK"],
        active["PATCH_BIAS_BANK"],
        active["PATCH_CLS_BANK"],
        shift=int(active["PATCH_SCALARS"][0]),
        output_bits=13,
    )
    expected_stream = logical.reshape(98, 2, 192).transpose(0, 2, 1).reshape(-1)
    hls_dump = np.fromfile(args.dump, dtype="<i4").astype(np.int64)
    patch_check = compare(hls_dump, expected_stream)

    head_shapes = {
        "HEAD_LN_SCALARS": (8,),
        "HEAD_LNW": (192,),
        "HEAD_LNB": (192,),
        "HEAD_RSQRT": (128,),
        "HEAD_WEIGHT": (1000, 192),
        "HEAD_BIAS": (1000,),
    }
    head_checks = {
        name: compare(
            parse_c_array(rom, name, shape),
            parse_c_array(args.safe_head, name, shape),
        )
        for name, shape in head_shapes.items()
    }

    report = {
        "mapping": {
            "testbench": "pkt[tp] = input_bin[(2*tt+tp)*768+c]",
            "adapter": "vec_i[tp*24+cip] = token[2*tt+tp,24*cit+cip]",
            "patch_output_dump": "[tt,channel,tp] int32",
        },
        "hashes": {
            "input_bin": sha256(input_path),
            "fixed_patch_head_rom_h": sha256(rom),
            "hls_patch_out_bin": sha256(args.dump),
        },
        "active_patch_vs_stage3": rom_checks,
        "active_head_vs_stage4o2": head_checks,
        "hls_patch_vs_integer_reference": patch_check,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    all_checks = [*rom_checks.values(), *head_checks.values(), patch_check]
    return 0 if all(item["mismatches"] == 0 for item in all_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
