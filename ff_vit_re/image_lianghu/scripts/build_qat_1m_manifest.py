#!/usr/bin/env python3
"""Build the deterministic 1,000-images/class metadata-only QAT manifest."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.qat_large_manifest import build_metadata_expansion_with_resampling, jsonl_bytes  # noqa: E402


DEFAULT_BASE = PROJECT_ROOT / "metadata" / "qat_subset700_seed20260923.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "metadata" / "qat_subset1000_seed20260923.jsonl"
DEFAULT_TRAIN_ROOT = PROJECT_ROOT.parent / "image_train" / "ILSVRC2012_img_train"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--train-root", type=Path, default=DEFAULT_TRAIN_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if os.path.lexists(output):
        raise ValueError(f"refusing to replace existing manifest: {output}")
    records = build_metadata_expansion_with_resampling(
        args.base,
        args.train_root,
        seed=20260923,
        per_class=1000,
        expected_classes=1000,
        spot_checks_per_class=1,
    )
    content = jsonl_bytes(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"created {output} with {len(records)} records and {len(content)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
