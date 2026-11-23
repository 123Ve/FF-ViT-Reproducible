#!/usr/bin/env python3
"""Recompute or initialize the truthful E06 physical-board gate result."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import uuid
from typing import Sequence


CLOUD_ROOT = Path(__file__).resolve().parent
if not __package__:
    sys.path.insert(0, str(CLOUD_ROOT.parent))

from Cloud_test.analysis.physical_gate import (  # noqa: E402
    analyze_gate, canonical_gate_bytes, not_run_gate,
)


DEFAULT_CONFIG = CLOUD_ROOT / "config/e06_physical.json"
DEFAULT_BOOT_MANIFEST = CLOUD_ROOT / "boot/BOOT_E06_NET.manifest.json"
DEFAULT_RELEASE = CLOUD_ROOT / "checkpoints/e06_network_release.sha256.json"
DEFAULT_OUTPUT = CLOUD_ROOT / "results/e06_physical_gate.json"


def _contained_output(path: Path) -> Path:
    results = (CLOUD_ROOT / "results").resolve()
    candidate = path.expanduser().absolute()
    if candidate.is_symlink():
        raise ValueError("gate output must not be a symlink")
    resolved_parent = candidate.parent.resolve()
    if resolved_parent != results:
        raise ValueError("gate output must be directly under Cloud_test/results")
    return resolved_parent / candidate.name


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", type=Path,
                        help="explicit raw physical session; omit to publish NOT_RUN")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--boot-manifest", type=Path, default=DEFAULT_BOOT_MANIFEST)
    parser.add_argument("--release-manifest", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        output = _contained_output(args.output)
        if args.session_dir is None:
            result = not_run_gate([
                "connected ZCU102 E06 board",
                "direct Ethernet carrier and 192.168.10.1/24 host address",
                "APU UART capture containing E06 boot identity",
                "completed physical TCP command session (warm-up + 10x100 frames)",
            ])
        else:
            result = analyze_gate(
                args.session_dir, cloud_root=CLOUD_ROOT, config_path=args.config,
                boot_manifest_path=args.boot_manifest,
                release_manifest_path=args.release_manifest,
            )
        _atomic_write(output, canonical_gate_bytes(result))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"E06_PHYSICAL_GATE={result['status']}")
    print(f"E06_PHYSICAL_GATE_FILE={output}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
