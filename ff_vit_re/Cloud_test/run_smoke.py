#!/usr/bin/env python3
"""Run the host-only cloud transport smoke test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .iot_eval.workflow import run_loopback_smoke
else:
    from iot_eval.workflow import run_loopback_smoke


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boot", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_loopback_smoke(args.boot, args.weights, args.image, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
