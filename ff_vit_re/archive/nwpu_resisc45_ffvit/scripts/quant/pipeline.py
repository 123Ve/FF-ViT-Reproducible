#!/usr/bin/env python3
"""Isolated manifest-driven quantization recipe with strict CLI translation."""
from __future__ import annotations
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from src.artifact_contract import accuracy_gate, check_resume, inventory, isolated_output, prepare_publication, record_stage, sha256

# stage ID, canonical script, private publication directory, direct dependencies
STAGES = [
    ("fp32", "../../train_fp32.py", "fp32", ()),
    ("hls196", "../../make_hls196.py", "hls196", ("fp32",)),
    ("w3_ptq", "../w3_ptq.py", "w3_ptq", ("hls196",)),
    ("w3_qat", "qat_weight3_hls196.py", "qat_weight3_hls196", ("fp32", "hls196", "w3_ptq")),
    ("patch", "stage3_patch_hls_eval.py", "stage3_patch_hls", ("hls196", "w3_qat")),
    ("ranges", "stage4a_collect_ranges.py", "stage4a_ranges", ("hls196", "w3_qat", "patch")),
    ("mlp_qat", "stage4d_mlp_activation_qat.py", "stage4d_mlp_qat", ("hls196", "w3_qat", "patch", "ranges")),
    ("gelu_pre", "stage4f_exact_gelu_lut.py", "stage4f_pre_attention", ("hls196", "w3_qat", "patch", "ranges", "mlp_qat")),
    ("ln", "stage4h_exact_layernorm_roundfix.py", "stage4h_exact_layernorm_roundfix", ("hls196", "w3_qat", "patch", "ranges", "mlp_qat", "gelu_pre")),
    ("exact_mlp", "stage4i_exact_mlp.py", "stage4i_exact_mlp", ("hls196", "w3_qat", "patch", "ranges", "mlp_qat", "gelu_pre", "ln")),
    ("attention_qat", "stage4j_attention_activation_qat.py", "stage4j_attention_qat", ("hls196", "w3_qat", "patch", "ranges", "mlp_qat", "ln")),
    ("gelu", "stage4f_exact_gelu_lut.py", "stage4f_exact_gelu", ("hls196", "w3_qat", "patch", "ranges", "attention_qat")),
    ("qkv_outer", "stage4k_exact_attention_outer.py", "stage4k_exact_attn_outer", ("hls196", "w3_qat", "patch", "ranges", "attention_qat")),
    ("qkv_refine", "stage4k2_refine_qkv_lut.py", "stage4k2_refined_qkv", ("hls196", "w3_qat", "patch", "ranges", "attention_qat", "qkv_outer")),
    ("softmax_aq", "stage4l_exact_softmax_aq.py", "stage4l_exact_softmax_aq", ("hls196", "w3_qat", "patch", "ranges", "attention_qat", "qkv_outer", "qkv_refine")),
    ("encoder", "stage4m_exact_encoder_backbone.py", "stage4m_exact_encoder", ("hls196", "w3_qat", "patch", "ranges", "attention_qat", "gelu", "qkv_outer", "qkv_refine", "softmax_aq")),
    ("head_audit", "stage4n_head_integer_audit.py", "stage4n_head_audit", ("hls196", "w3_qat", "patch", "ranges", "attention_qat", "gelu", "qkv_outer", "qkv_refine", "softmax_aq", "encoder")),
    ("head_signed", "stage4o_exact_head_signedfix.py", "stage4o_exact_head_signedfix", ("hls196", "w3_qat", "patch", "ranges", "attention_qat", "gelu", "qkv_outer", "qkv_refine", "softmax_aq", "encoder", "head_audit")),
    ("head_safe", "stage4o2_head_safe_refit.py", "stage4o2_head_safe", ("fp32", "hls196", "w3_qat", "patch", "ranges", "attention_qat", "gelu", "qkv_outer", "qkv_refine", "softmax_aq", "encoder", "head_audit", "head_signed")),
    ("export", "deployment/export_hls.py", "deployment", ("attention_qat", "patch", "gelu", "qkv_outer", "qkv_refine", "softmax_aq", "encoder", "head_safe")),
    ("fixture", "../generate_fixture.py", "fixture", ("hls196", "w3_qat", "patch", "ranges", "attention_qat", "gelu", "qkv_outer", "qkv_refine", "softmax_aq", "encoder", "head_signed", "head_safe", "export")),
]


def parser_for(script):
    """Extract only literal argparse declarations; never execute model code."""
    parser = argparse.ArgumentParser(add_help=False)
    tree = ast.parse(Path(script).read_text())
    declarations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        names = [arg.value for arg in node.args if isinstance(arg, ast.Constant)]
        kwargs = {}
        for item in node.keywords:
            if item.arg in {"required", "action", "nargs", "choices"}:
                kwargs[item.arg] = ast.literal_eval(item.value)
            elif item.arg == "type" and isinstance(item.value, ast.Name):
                kwargs["type"] = {"int": int, "float": float, "Path": str, "str": str}[item.value.id]
            elif item.arg == "default" and isinstance(item.value, ast.Constant):
                kwargs["default"] = item.value.value
        parser.add_argument(*names, **kwargs)
        declarations.append((names[0], kwargs.get("required", False)))
    return parser, declarations


def verify_ports():
    entries = json.loads((HERE / "source_inventory.json").read_text())
    for entry in entries:
        if sha256(HERE / entry["port"]) != entry["port_sha256"]:
            raise ValueError(f"ported source hash mismatch: {entry['port']}")
    return len(entries)


def recipe(args):
    run = args.run_dir.resolve()
    dirs = {stage: run / directory for stage, _, directory, _ in STAGES}
    context = {"--source-checkpoint": dirs["hls196"] / "best.pth",
        "--qat-checkpoint": dirs["w3_qat"] / "best_qat_state.pth", "--stage3-dir": dirs["patch"],
        "--ranges": dirs["ranges"] / "activation_ranges.json",
        "--mlp-qat-checkpoint": dirs["mlp_qat"] / "best_mlp_qat.pth",
        "--attention-qat-checkpoint": dirs["attention_qat"] / "best_attention_qat.pth",
        "--manifest": args.metadata / "calibration.json", "--data-root": args.source,
        "--gelu-dir": dirs["gelu_pre"], "--ln-dir": dirs["ln"], "--patch-scale": "0",
        "--stage4f-dir": dirs["gelu"], "--stage4k-dir": dirs["qkv_outer"],
        "--stage4k2-dir": dirs["qkv_refine"], "--stage4l-dir": dirs["softmax_aq"],
        "--stage4m-dir": dirs["encoder"], "--stage4n-dir": dirs["head_audit"],
        "--stage4o-dir": dirs["head_signed"]}
    for stage, name, directory, deps in STAGES:
        script = (HERE / "canonical" / name).resolve()
        parser, flags = parser_for(script)
        available = {flag for flag, _ in flags}
        if stage == "fp32":
            values = {"--metadata": args.metadata, "--source": args.source,
                      "--pretrained-checkpoint": args.pretrained_checkpoint, "--epochs": args.fp32_epochs,
                      "--seed": args.seed, "--output": dirs[stage]}
        elif stage == "hls196":
            values = {"--metadata": args.metadata, "--source": args.source,
                      "--checkpoint": dirs["fp32"] / "best.pth", "--output": dirs[stage], "--seed": args.seed}
        elif stage in {"w3_ptq", "w3_qat"}:
            values = {"--checkpoint": dirs["hls196"] / "best.pth", "--data-root": args.source,
                      "--output": dirs[stage]}
            if stage == "w3_qat":
                values.update({"--epochs": args.w3_epochs, "--seed": args.seed})
        elif stage == "export":
            values = {"--project-root": run, "--rom-template": args.rom_template,
                      "--block0-template": args.block0_template, "--output-dir": dirs[stage]}
        elif stage == "fixture":
            values = {"--project-root": run, "--output": dirs[stage], "--fixture-index": args.fixture_index}
        else:
            values = {flag: context[flag] for flag, required in flags if required}
            values["--output"] = dirs[stage]
            if stage == "gelu":
                values["--mlp-qat-checkpoint"] = context["--attention-qat-checkpoint"]
            if "--epochs" in available:
                values["--epochs"] = args.activation_epochs
            if "--fit-images" in available:
                values["--fit-images"] = args.calibration_count
        if stage in {"w3_qat", "mlp_qat", "attention_qat"}:
            values.update({"--lr": 2e-5 if stage == "w3_qat" else 1e-5,
                           "--scale-lr": 5e-4, "--weight-decay": 0.02})
            if stage != "w3_qat":
                values.update({"--kd-alpha": 0.5, "--kd-temperature": 2.0})
        batch_size = args.batch_size if args.batch_size is not None else parser.get_default("batch_size")
        for flag, value in (("--batch-size", batch_size), ("--workers", args.workers)):
            if flag in available:
                values[flag] = value
        translated = [str(value) for pair in values.items() for value in pair]
        parser.parse_args(translated)
        command = [sys.executable, str(HERE / "run_stage.py"), "--stage", stage,
                   "--metadata", str(args.metadata), "--source", str(args.source),
                   "--num-classes", str(args.num_classes), "--calibration-count", str(args.calibration_count),
                   "--seed", str(args.seed), "--", *translated]
        yield {"stage": stage, "script": str(script), "command": command,
               "output": str(dirs[stage]), "dependencies": list(deps),
               "num_classes": args.num_classes, "calibration_count": args.calibration_count,
               "seed": args.seed, "manifests": {split: str(args.metadata / f"{split}.json")
                    for split in ("train", "val", "test", "calibration")}}


def get_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("train", "deploy", "check-cli"))
    action = p.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--stop-after", choices=[stage[0] for stage in STAGES])
    p.add_argument("--run-dir", type=Path, default=ROOT / "runs/nwpu_seed20260923")
    p.add_argument("--metadata", type=Path, default=ROOT / "metadata")
    p.add_argument("--source", type=Path, default=ROOT.parent / "Dataset")
    p.add_argument("--pretrained-checkpoint", type=Path, default=ROOT.parents[1] / "deit_tiny_imagenet_timm.pth")
    p.add_argument("--num-classes", type=int, default=45)
    p.add_argument("--calibration-count", type=int, default=1440)
    p.add_argument("--seed", type=int, default=20260923)
    p.add_argument("--fp32-epochs", type=int, default=8)
    p.add_argument("--w3-epochs", type=int, default=8)
    p.add_argument("--activation-epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, help="override canonical per-stage batch sizes; QAT default is 32")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--rom-template", type=Path, default=ROOT / "templates/fixed_patch_head_rom.h")
    p.add_argument("--block0-template", type=Path, default=ROOT / "templates/block0.cpp")
    p.add_argument("--fixture-index", type=int, default=0)
    return p


def inputs_for(row, rows, args):
    inputs = {"metadata": args.metadata, "quant_source": HERE,
              "contract": ROOT / "src", "task2_scripts": ROOT / "scripts/train_fp32.py",
              "conversion_script": ROOT / "scripts/make_hls196.py"}
    inputs.update({dep: Path(rows[dep]["output"]) for dep in row["dependencies"]})
    if row["stage"] == "fp32":
        inputs["pretrained"] = args.pretrained_checkpoint
    if row["stage"] == "export":
        inputs.update(rom_template=args.rom_template, block0_template=args.block0_template)
    return inputs


def check_gate(stage, output, run):
    if stage not in {"w3_qat", "head_safe"}:
        return
    baseline = json.loads((run / "fp32/report.json").read_text())["best_val_top1"]
    report = json.loads((output / "report.json").read_text())
    candidate = report["best_val"] if stage == "w3_qat" else report["validation_top1"]
    gate = accuracy_gate(baseline, candidate, 2.0 if stage == "w3_qat" else 5.0)
    if not gate["passed"]:
        raise ValueError(f"{stage} accuracy gate failed; checkpoint retained: {json.dumps(gate)}")


def main():
    args = get_parser().parse_args()
    try:
        args.run_dir = isolated_output(args.run_dir, ROOT)
        args.metadata, args.source = args.metadata.resolve(), args.source.resolve()
        if args.num_classes != 45 or args.calibration_count != 1440:
            raise ValueError("NWPU requires 45 classes and 1440 calibration images")
        count = verify_ports()
        rows = list(recipe(args))
        if args.mode == "check-cli":
            print(json.dumps({"stages_checked": len(rows)-2, "canonical_sources_verified": count}))
            return 0
        selected = rows[:19] if args.mode == "train" else rows[19:]
        if args.stop_after:
            ids = [row["stage"] for row in selected]
            if args.stop_after not in ids:
                raise ValueError("stop-after does not belong to this pipeline")
            selected = selected[:ids.index(args.stop_after)+1]
        lookup = {row["stage"]: row for row in rows}
        if args.mode == "train" and args.run_dir.exists() and any(args.run_dir.iterdir()) and not args.resume:
            raise ValueError("refusing nonempty run directory; --resume requires matching provenance")
        for row in selected:
            out = Path(row["output"])
            if out.exists() and any(out.iterdir()) and not args.resume:
                raise ValueError(f"refusing nonempty stage output: {out}")
        if args.run:
            from src.manifest_dataset import load_manifest_bundle
            load_manifest_bundle(args.metadata)
        for row in selected:
            out = Path(row["output"])
            if args.resume and out.exists() and any(out.iterdir()):
                check_resume(out, row, inputs_for(row, lookup, args))
                check_gate(row["stage"], out, args.run_dir)
                print(json.dumps({**row, "resumed": True}), flush=True)
                continue
            print(json.dumps(row), flush=True)
            if not args.run:
                continue
            inputs = inputs_for(row, lookup, args)
            # Every dependency is a fully published stage with valid input/output hashes.
            for dep in row["dependencies"]:
                check_resume(lookup[dep]["output"], lookup[dep], inputs_for(lookup[dep], lookup, args))
                check_gate(dep, Path(lookup[dep]["output"]), args.run_dir)
            before = {name: inventory(path) for name, path in inputs.items()}
            args.run_dir.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=f".{row['stage']}-", dir=args.run_dir))
            destination = staging / "result"
            command = list(row["command"])
            flag = "--output-dir" if row["stage"] == "export" else "--output"
            command[command.index(flag)+1] = str(destination)
            with (staging / "stage.log").open("w") as log:
                subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT,
                               env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            if before != {name: inventory(path) for name, path in inputs.items()}:
                raise ValueError("stage inputs changed during execution")
            (staging / "stage.log").rename(destination / "stage.log")
            training_state = staging / ".result.run"
            if training_state.exists():
                training_state.rename(destination / "training_state")
            prepare_publication(destination, out, training_state, command)
            record_stage(destination, row, inputs)
            if out.exists():
                out.rmdir()  # only an empty destination is replaceable
            destination.rename(out)
            staging.rmdir()
            check_gate(row["stage"], out, args.run_dir)
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
