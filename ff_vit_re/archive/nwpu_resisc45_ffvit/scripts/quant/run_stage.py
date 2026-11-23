#!/usr/bin/env python3
"""Translate an explicit dataset contract into one frozen canonical invocation."""
import argparse
import importlib
import json
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(HERE), str(HERE / "canonical")]
from pipeline import STAGES, verify_ports, parser_for


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", choices=[s[0] for s in STAGES], required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--num-classes", type=int, required=True)
    p.add_argument("--calibration-count", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("arguments", nargs=argparse.REMAINDER)
    args = p.parse_args()
    if not args.arguments or args.arguments.pop(0) != "--":
        p.error("canonical arguments must follow --")
    verify_ports()
    import manifest_adapter
    bundle = manifest_adapter.configure(args.metadata, args.source, args.num_classes, args.calibration_count)
    import torch
    from qat_weight3_hls196 import seed_all
    from src.model_contract import validate_checkpoint_metadata
    from src.artifact_contract import isolated_output, validate_quant_checkpoint, validate_array
    seed_all(args.seed)
    stage = next(item for item in STAGES if item[0] == args.stage)
    script = (HERE / "canonical" / stage[1]).resolve()
    translated = list(args.arguments)
    parser_for(script)[0].parse_args(translated)
    flags = dict(zip(translated[::2], translated[1::2]))
    for flag in ("--checkpoint", "--source-checkpoint"):
        if flag in flags:
            checkpoint = torch.load(flags[flag], map_location="cpu", weights_only=True)
            validate_checkpoint_metadata(checkpoint, bundle.classes,
                expected_token_count=197 if args.stage == "hls196" else 196,
                expected_manifest_hashes=bundle.metadata_hashes)
    for flag, kind in (("--qat-checkpoint", "w3_qat"), ("--mlp-qat-checkpoint", "mlp_qat"),
                       ("--attention-qat-checkpoint", "attention_qat")):
        if flag in flags:
            kind = "attention_qat" if args.stage == "gelu" and flag == "--mlp-qat-checkpoint" else kind
            validate_quant_checkpoint(torch.load(flags[flag], map_location="cpu", weights_only=True), bundle.classes, kind)
    if "--patch-scale" in flags:
        report = json.loads((Path(flags["--stage3-dir"]) / "report.json").read_text())
        scale = float(report["patch_output"]["real_scale"])
        if not scale > 0:
            raise ValueError("Patch real scale must be positive")
        translated[translated.index("--patch-scale")+1] = str(scale)
    output = Path(flags.get("--output", flags.get("--output-dir", "")))
    isolated_output(output, ROOT)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"refusing nonempty stage output: {output}")
    # GELU's canonical API calls the frozen MLP controller 'controller_state'.
    # Attention QAT stores the identical controller under 'mlp_controller_state'.
    # Translate only this key in a stage-local derived checkpoint.
    if args.stage == "gelu":
        checkpoint = torch.load(flags["--mlp-qat-checkpoint"], map_location="cpu", weights_only=True)
        checkpoint["controller_state"] = checkpoint["mlp_controller_state"]
        output.mkdir(parents=True, exist_ok=True)
        bridge = output / "attention_mlp_bridge.pth"
        torch.save(checkpoint, bridge)
        translated[translated.index("--mlp-qat-checkpoint")+1] = str(bridge)
    sys.argv = [str(script), *translated]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as error:
        if error.code not in (0, None):
            raise
    # Canonical activation checkpoints lack redundant count/hash metadata.
    # Add it only after validating the class sequence and model dimensions.
    checkpoints = {"w3_qat": "best_qat_state.pth", "mlp_qat": "best_mlp_qat.pth",
                   "attention_qat": "best_attention_qat.pth"}
    if args.stage in checkpoints:
        path = output / checkpoints[args.stage]
        payload = torch.load(path, map_location="cpu", weights_only=True)
        payload["num_classes"] = len(bundle.classes)
        payload["manifest_hashes"] = dict(bundle.metadata_hashes)
        payload["seed"] = args.seed
        validate_quant_checkpoint(payload, bundle.classes, args.stage)
        torch.save(payload, path)
    import numpy as np
    exporter = runpy.run_path(str(HERE / "canonical/deployment/export_hls.py"))
    for name, producer, filename, shape in exporter["ARRAYS"]:
        if producer == stage[2]:
            validate_array(name, np.load(output / filename, allow_pickle=False), shape)
    if args.stage in {"head_signed", "head_safe"}:
        validate_array("head_weight_active", np.load(output / "head_weight_active.npy"), (args.num_classes, 192))
        validate_array("head_bias_active", np.load(output / "head_bias_active.npy"), (args.num_classes,))
    report = {"stage": args.stage, "command": sys.argv, "seed": args.seed,
              "classes": list(bundle.classes), "manifest_hashes": dict(bundle.metadata_hashes),
              "environment": {"torch": torch.__version__, "cuda": torch.version.cuda}}
    (output / "adapter_report.json").write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    main()
