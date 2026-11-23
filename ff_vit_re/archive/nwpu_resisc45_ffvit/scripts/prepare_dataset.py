#!/usr/bin/env python3
"""Create the immutable NWPU-RESISC45 split and calibration manifests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dataset_manifest import build_inventory, make_splits, write_manifests  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="immutable Dataset root")
    parser.add_argument("--output", type=Path, required=True, help="metadata output directory")
    parser.add_argument("--seed", type=int, default=20260923, help="deterministic split seed")
    args = parser.parse_args()

    inventory = build_inventory(args.source)
    manifest = make_splits(inventory, seed=args.seed)
    hashes = write_manifests(manifest, args.output)
    duplicate_payload = json.loads((args.output / "duplicate_groups.json").read_text(encoding="utf-8"))
    print(f"classes={len(manifest.classes)} inventory={len(inventory)} seed={manifest.seed}")
    print(
        "splits=" + " ".join(f"{name}={len(records)}" for name, records in manifest.splits.items())
    )
    print(f"calibration={len(manifest.calibration)}")
    print(
        "duplicates="
        f"groups={duplicate_payload['duplicate_group_count']} "
        f"paths={duplicate_payload['duplicate_path_count']}"
    )
    for filename, digest in hashes.items():
        print(f"sha256 {filename} {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
