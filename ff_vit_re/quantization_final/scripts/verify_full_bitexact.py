#!/usr/bin/env python3
"""Verify every exported HLS boundary against independent integer references."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from verify_patch_bitexact import compare, sha256


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hls-root",
        type=Path,
        default=Path("/home/user/Desktop/FF_Vit/flash_vit_2"),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(
            "/home/user/Desktop/FF_Vit/flash_vit_2/flash_vit/"
            "vit_plantvillage_bitaccurate"
        ),
    )
    parser.add_argument("--refs", type=Path, default=Path("bitexact_audit/refs"))
    parser.add_argument(
        "--patch-report",
        type=Path,
        default=Path("bitexact_audit/patch_verification.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("bitexact_audit/full_verification.json"),
    )
    args = parser.parse_args()

    build = args.work_dir / "hls/csim/build"
    csim_log = args.work_dir / "hls/csim/report/vit_block_top_csim.log"
    checks: dict[str, dict[str, object]] = {}

    for block in range(12):
        actual = np.fromfile(build / f"hls_block{block}_out.bin", dtype="<i4")
        expected = np.fromfile(args.refs / f"ref_block{block}_out.bin", dtype="<i4")
        checks[f"block{block}"] = compare(actual, expected)

    for name in ("head_input", "head_ln"):
        actual = np.fromfile(build / f"hls_{name}.bin", dtype="<i4")
        expected = np.fromfile(args.refs / f"ref_{name}.bin", dtype="<i4")
        checks[name] = compare(actual, expected)

    actual_logits = np.fromfile(build / "hls_logits.bin", dtype="<i4")
    expected_logits = np.fromfile(args.refs / "ref_logits.bin", dtype="<i4")
    checks["logits"] = compare(actual_logits, expected_logits)

    patch_report = json.loads(args.patch_report.read_text(encoding="utf-8"))
    checks["patch"] = patch_report["hls_patch_vs_integer_reference"]

    log_text = csim_log.read_text(encoding="utf-8", errors="replace")
    trustworthy_pass = (
        "PASS!" in log_text
        and "FAIL!" not in log_text
        and "MISMATCH" not in log_text
        and "CSim done with 0 errors" in log_text
    )

    inactive = actual_logits[38:]
    inactive_unique = np.unique(inactive).astype(np.int64).tolist()
    hashes = {}
    for name, path in {
        "weights.bin": args.hls_root / "weights.bin",
        "fixed_patch_head_rom.h": args.hls_root / "src/fixed_patch_head_rom.h",
        "block0.cpp": args.hls_root / "src/block0.cpp",
        "input.bin": args.hls_root / "input.bin",
        "output.bin": args.hls_root / "output.bin",
    }.items():
        hashes[name] = {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}

    report = {
        "checks": checks,
        "active_predicted_class_id": int(np.argmax(actual_logits[:38])),
        "inactive_38_999_unique_values": inactive_unique,
        "inactive_safe": inactive_unique == [-(1 << 18)],
        "csim_log": str(csim_log),
        "csim_log_trustworthy_pass": trustworthy_pass,
        "hashes": hashes,
        "board_result": "not tested; this report covers software integer reference and HLS C-sim only",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    exact = all(item["mismatches"] == 0 for item in checks.values())
    return 0 if exact and trustworthy_pass and report["inactive_safe"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
