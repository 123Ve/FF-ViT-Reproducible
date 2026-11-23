#!/usr/bin/env python3
"""Build and evaluate the deterministic signed-W3 PTQ HLS196 milestone."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path

import numpy as np
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_fp32 import (  # noqa: E402
    DEFAULT_VALIDATION,
    _evaluation_transform,
    _validation_provenance,
)
from src.evaluation import ParquetValidationSource, evaluate_topk  # noqa: E402
from src.weight_quant import (  # noqa: E402
    atomic_create_bytes,
    build_w3_ptq,
    load_w3_ptq_checkpoint,
    manifest_json_bytes,
    serialize_w3_checkpoint,
    serialize_w3_integer_artifact,
)


SEED = 20260923
DEFAULT_HLS_CHECKPOINT = PROJECT_ROOT / "checkpoints" / "fp32_hls196.pth"
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "w3_ptq"
DEFAULT_MANIFEST = DEFAULT_ARTIFACT_DIR / "weight_manifest.json"
DEFAULT_INTEGER = DEFAULT_ARTIFACT_DIR / "integer_weights.pt"
DEFAULT_CHECKPOINT = PROJECT_ROOT / "checkpoints" / "w3_ptq_fakequant.pth"
DEFAULT_EVALUATION = PROJECT_ROOT / "reports" / "w3_ptq_val50k.json"


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_w3_outputs(
    model: torch.nn.Module,
    manifest: dict[str, object],
    integer_state: dict[str, torch.Tensor],
    *,
    manifest_path: str | Path,
    integer_path: str | Path,
    checkpoint_path: str | Path,
) -> dict[str, object]:
    """Publish all three PTQ artifacts without replacing any existing path."""

    paths = {
        "manifest": Path(manifest_path).expanduser().resolve(),
        "integer": Path(integer_path).expanduser().resolve(),
        "checkpoint": Path(checkpoint_path).expanduser().resolve(),
    }
    for path in paths.values():
        if os.path.lexists(path):
            raise ValueError(f"refusing to replace existing artifact: {path}")
    contents = {
        "manifest": manifest_json_bytes(manifest),
        "integer": serialize_w3_integer_artifact(manifest, integer_state),
        "checkpoint": serialize_w3_checkpoint(model, manifest, integer_state),
    }
    for name in ("manifest", "integer", "checkpoint"):
        atomic_create_bytes(paths[name], contents[name])
    return {
        f"{name}_{field}": value
        for name in ("manifest", "integer", "checkpoint")
        for field, value in (
            ("path", str(paths[name])),
            ("size_bytes", len(contents[name])),
            ("sha256", _sha256_bytes(contents[name])),
        )
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hls-checkpoint", type=Path, default=DEFAULT_HLS_CHECKPOINT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--integer-output", type=Path, default=DEFAULT_INTEGER)
    parser.add_argument("--checkpoint-output", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--evaluation-output", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--mode", choices=("all", "build", "evaluate"), default="all")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def _seed_everything() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)


def main() -> int:
    args = _parse_args()
    if args.batch_size <= 0 or args.workers < 0:
        raise ValueError("batch-size must be positive and workers nonnegative")
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto":
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("--device cuda requested but CUDA is unavailable")
    _seed_everything()
    torch.set_float32_matmul_precision("highest")

    summary: dict[str, object] = {"seed": SEED}
    if args.mode in {"all", "build"}:
        model, manifest, integer_state = build_w3_ptq(args.hls_checkpoint)
        summary["artifacts"] = write_w3_outputs(
            model,
            manifest,
            integer_state,
            manifest_path=args.manifest_output,
            integer_path=args.integer_output,
            checkpoint_path=args.checkpoint_output,
        )
        del model, integer_state

    if args.mode in {"all", "evaluate"}:
        model = load_w3_ptq_checkpoint(args.checkpoint_output)
        provenance = _validation_provenance(args.data_dir, command=list(sys.argv))
        source = ParquetValidationSource(
            args.data_dir,
            transform=_evaluation_transform(),
            provenance=provenance,
        )
        result = evaluate_topk(
            model,
            source,
            output_path=args.evaluation_output,
            batch_size=args.batch_size,
            workers=args.workers,
            device=device,
            resume=not args.no_resume,
        )
        summary["evaluation"] = {
            "sample_count": result["sample_count"],
            "top1_correct": result["top1_correct"],
            "top1_percent": result["top1_percent"],
            "top5_correct": result["top5_correct"],
            "top5_percent": result["top5_percent"],
            "timing": result["timing"],
        }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
