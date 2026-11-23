"""Content-addressed stage provenance and quantized artifact validation."""
from __future__ import annotations
import hashlib
import json
import platform
import math
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"symlink artifact is forbidden: {path}")
    if path.is_file():
        return sha256(path)
    if not path.is_dir():
        raise ValueError(f"missing input artifact: {path}")
    result = {}
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError(f"symlink artifact is forbidden: {item}")
        if item.is_file() and "__pycache__" not in item.parts:
            result[str(item.relative_to(path))] = sha256(item)
    return result


def output_inventory(output):
    return {key: value for key, value in inventory(output).items() if key != "provenance.json"}


def record_stage(output, recipe, inputs):
    output = Path(output)
    report = {"schema_version": 1, "status": "complete", "recipe": recipe,
              "environment": {"python": platform.python_version(), "platform": platform.platform()},
              "inputs": {name: inventory(path) for name, path in sorted(inputs.items())},
              "outputs": output_inventory(output)}
    if not report["outputs"]:
        raise ValueError("cannot publish an empty stage")
    (output / "provenance.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report


def check_resume(output, recipe, inputs):
    output = Path(output)
    report_path = output / "provenance.json"
    if not report_path.is_file():
        raise ValueError(f"incomplete stage has no provenance: {output}")
    report = json.loads(report_path.read_text())
    if report.get("status") != "complete" or report.get("recipe") != recipe:
        raise ValueError(f"resume recipe mismatch: {output}")
    if report.get("inputs") != {name: inventory(path) for name, path in sorted(inputs.items())}:
        raise ValueError(f"resume input hash mismatch: {output}")
    if report.get("outputs") != output_inventory(output):
        raise ValueError(f"resume output hash mismatch: {output}")
    return True


def validate_array(name, array, shape):
    import numpy as np
    if tuple(array.shape) != tuple(shape):
        raise ValueError(f"{name} shape: expected {shape}, got {tuple(array.shape)}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains nonfinite values")


def accuracy_gate(fp32_top1, candidate_top1, allowed_drop):
    if not all(math.isfinite(float(value)) and 0 <= float(value) <= 100
               for value in (fp32_top1, candidate_top1, allowed_drop)):
        raise ValueError("accuracy gate requires finite percentages")
    drop = float(fp32_top1) - float(candidate_top1)
    return {"fp32_top1": float(fp32_top1), "candidate_top1": float(candidate_top1),
            "drop_pp": drop, "allowed_drop_pp": float(allowed_drop), "passed": drop <= allowed_drop}


def validate_quant_checkpoint(checkpoint, classes, stage):
    keys = {"w3_qat": ("model_state",), "mlp_qat": ("student_state", "controller_state"),
            "attention_qat": ("student_state", "mlp_controller_state", "attention_controller_state")}
    required = keys[stage]
    if any(key not in checkpoint for key in required):
        raise ValueError(f"{stage} missing checkpoint keys {required}")
    if checkpoint.get("classes") != list(classes) or checkpoint.get("num_classes") != len(classes):
        raise ValueError(f"{stage} checkpoint class order differs")
    state = checkpoint[required[0]]
    for suffix, shape in (("head.weight", (len(classes), 192)), ("head.bias", (len(classes),)),
                          ("pos_embed", (1, 196, 192))):
        found = [value for key, value in state.items() if key.endswith(suffix)]
        if len(found) != 1 or tuple(found[0].shape) != shape:
            raise ValueError(f"{stage} {suffix} shape must equal {shape}")


def isolated_output(path, root):
    path, root = Path(path).absolute(), Path(root).resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(root) or path.resolve() == root:
        raise ValueError("output must be isolated beneath the archive workspace")
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("output parent cannot be a symlink")
    path = path.resolve()
    # Never accept source, manifests, existing checkpoints, or validation as a run root.
    if path.relative_to(root).parts[0] not in {"runs", "validation"}:
        raise ValueError("run output must be beneath archive runs/ or validation/")
    return path


def prepare_publication(staged, published, recovery_source, executed_command):
    """Resolve relocatable metadata before the atomic directory promotion.

    Commands in reports describe the published paths. The separate history
    file and stage.log preserve the actual temporary execution locations and
    are explicitly historical evidence, not artifact-location metadata.
    Checkpoint tensor/optimizer/RNG values are not transformed.
    """
    import torch
    staged, published, recovery_source = map(Path, (staged, published, recovery_source))
    relocations = ((recovery_source, published / "training_state"), (staged, published))

    def relocate(value):
        if isinstance(value, (str, Path)):
            path = Path(value)
            if path.is_absolute():
                for source, target in relocations:
                    if path.is_relative_to(source):
                        result = target / path.relative_to(source)
                        return (str(result) if isinstance(value, str) else result), True
            return value, False
        changed = False
        if isinstance(value, dict):
            # Mutate only private metadata; retain OrderedDict tensor metadata.
            for key, child in list(value.items()):
                rewritten, child_changed = relocate(child)
                if child_changed:
                    value[key] = rewritten
                    changed = True
        elif isinstance(value, (list, tuple)):
            rewritten = []
            for child in value:
                child, child_changed = relocate(child)
                rewritten.append(child)
                changed |= child_changed
            if changed:
                value = tuple(rewritten) if isinstance(value, tuple) else rewritten
        return value, changed

    def physical_path(value):
        path = Path(value)
        return staged / path.relative_to(published) if path.is_relative_to(published) else path

    # These are trusted artifacts generated by the just-completed stage.
    # Recovery checkpoints include NumPy RNG state, so weights_only=False is
    # required. Avoid resaving checkpoints whose metadata did not relocate.
    for path in sorted(staged.rglob("*")):
        if path.is_file() and path.suffix in {".pth", ".pt"}:
            payload = torch.load(path, map_location="cpu", weights_only=False)
            payload, changed = relocate(payload)
            if changed:
                torch.save(payload, path)

    history = {"purpose": "historical execution only; temporary paths are not artifact locations",
               "pipeline_command": list(executed_command), "report_commands": {}}

    def refresh_hashes(value):
        if isinstance(value, dict):
            for key, child in value.items():
                # Reports pair output/source_checkpoint with their SHA-256.
                if key.endswith("_sha256"):
                    reference = value.get(key[:-7])
                    if isinstance(reference, str) and Path(reference).is_absolute():
                        target = physical_path(reference)
                        if target.is_file():
                            value[key] = sha256(target)
                else:
                    refresh_hashes(child)
        elif isinstance(value, list):
            for child in value:
                refresh_hashes(child)

    for path in sorted(staged.rglob("*.json")):
        payload = json.loads(path.read_text())
        if isinstance(payload, dict) and "command" in payload:
            history["report_commands"][str(path.relative_to(staged))] = payload["command"]
        payload, _ = relocate(payload)
        refresh_hashes(payload)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    (staged / "execution_history.json").write_text(json.dumps(history, sort_keys=True, indent=2) + "\n")
