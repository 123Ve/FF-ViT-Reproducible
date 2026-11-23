#!/usr/bin/env python3
"""Validate a complete sensitivity shard set and render stable paper tables."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sensitivity import aggregate_probe_shards, aggregate_shards, enumerate_experiments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--ranking", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True,
                        help="JSON with four SHA-256 fields and sample_count")
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--probe", action="store_true", help="write probe_-prefixed development reports")
    args = parser.parse_args()
    ranking = json.loads(args.ranking.read_text(encoding="utf-8"))
    if isinstance(ranking, dict):
        ranking = ranking["low_sensitivity_order"]
    identity = json.loads(args.identity.read_text(encoding="utf-8"))
    experiments = enumerate_experiments(args.blocks, low_sensitivity_order=ranking)
    aggregate = aggregate_probe_shards if args.probe else aggregate_shards
    aggregate(args.shards, args.reports, experiments, expected=identity)
    print(json.dumps({"status": "written", "reports": str(args.reports),
                      "experiments": len(experiments)}))


if __name__ == "__main__":
    main()
