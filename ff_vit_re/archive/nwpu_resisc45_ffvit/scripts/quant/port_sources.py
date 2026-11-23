"""Reproducible mechanical port; arithmetic bodies are preserved verbatim.

This maintenance command reads canonical source only and emits unified additions
through apply_patch. It never reads historical checkpoints, arrays, or fixtures.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE = REPO / "quantization_final/scripts"
FILES = ["qat_weight3_hls196.py", "stage3_patch_hls_eval.py", "stage4a_collect_ranges.py",
    "stage4b_activation_ptq_eval.py", "stage4d_mlp_activation_qat.py", "stage4f_exact_gelu_lut.py",
    "stage4h_exact_layernorm_roundfix.py", "stage4i_exact_mlp.py", "stage4j_attention_activation_qat.py",
    "stage4k_exact_attention_outer.py", "stage4k2_refine_qkv_lut.py", "stage4l_exact_softmax_aq.py",
    "stage4m_exact_encoder_backbone.py", "stage4n_head_integer_audit.py",
    "stage4o_exact_head_signedfix.py", "stage4o2_head_safe_refit.py",
    "verify_patch_bitexact.py", "lib/hls_abi.py", "lib/frozen_quantization.py",
    "lib/pack_weights_hls.cpp", "deployment/export_hls.py",
    "deployment/generate_fixture.py", "stage4q_generate_csim_fixture_v2.py"]


def adapt(text, filename):
    if not filename.endswith(".py"):
        return text
    if filename == "verify_patch_bitexact.py":
        return text[:text.index("\ndef main()")]+"\n"
    if filename == "stage4q_generate_csim_fixture_v2.py":
        tree = ast.parse(text)
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "make_input_codes")
        return ("\"\"\"Canonical semantic input conversion; no historical fixture loading.\"\"\"\n"
                "import torch\nimport torch.nn.functional as F\nT = 196\nPATCH_DIM = 768\n\n"
                + ast.get_source_segment(text, node) + "\n")
    if filename == "deployment/generate_fixture.py":
        text = text.replace("def generate(root, output, project=None):", "def generate(project, output, image_path, classes):")
        start = text.index("    root, output =")
        end = text.index("    if output.exists()", start)
        text = text[:start] + "    project, output = Path(project).resolve(), Path(output).resolve()\n" + text[end:]
        start = text.index("    def stage(name):")
        end = text.index("    stages =", start)
        text = text[:start] + "    def stage(name):\n        return project / name\n\n" + text[end:]
        text = text.replace('artifacts = project if project is not None else root / "artifacts"', 'artifacts = project')
        text = text.replace('checkpoints = project if project is not None else root / "checkpoints"', 'checkpoints = project')
        text = text.replace('"plantvillage_hls196/best.pth"', '"hls196/best.pth"')
        start = text.index('    fixture = json.loads(')
        end = text.index('    if source["classes"]', start)
        text = text[:start] + text[end:]
        text = text.replace('fixture["image_path"]', 'str(image_path)')
        text = text.replace('head_weight_38.npy', 'head_weight_active.npy').replace('head_bias_38.npy', 'head_bias_active.npy')
        text = text.replace('[:38]', '[:len(classes)]')
        text = text[:text.index('\ndef main():')] + '\n'
        return text
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    edits = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ManifestDataset":
            edits.append((node.lineno - 1, node.end_lineno,
                          "from manifest_adapter import CalibrationDataset as ManifestDataset\n"))
        if isinstance(node, ast.FunctionDef) and node.name in {"eval_transform", "train_transform"}:
            target = "make_eval_transform" if node.name == "eval_transform" else "make_train_transform"
            edits.append((node.lineno - 1, node.end_lineno,
                          f"def {node.name}():\n    from src.manifest_dataset import {target}\n    return {target}()\n"))
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement]
    text = "".join(lines)
    text = text.replace("datasets.ImageFolder(", "__import__('manifest_adapter').image_folder(")
    text = text.replace("NCLASS = 38", "NCLASS = __import__('manifest_adapter').num_classes()")
    text = text.replace("head_weight_38.npy", "head_weight_active.npy").replace("head_bias_38.npy", "head_bias_active.npy")
    text = text.replace("PlantVillage", "manifest dataset").replace("plantvillage", "dataset")
    text = text.replace("38-class", "active-class").replace("38x192", "NCLASSx192").replace("[38,192]", "[NCLASS,192]").replace("[38]", "[NCLASS]")
    text = text.replace("first 38 logits active, remaining 962", "configured class logits active, remaining")
    text = text.replace("Pad 38 active rows", "Pad active rows")
    # Preserve test evaluation only at frozen milestones (W3 QAT is one).
    if filename in {"stage4d_mlp_activation_qat.py", "stage4j_attention_activation_qat.py"}:
        tree = ast.parse(text)
        lines = text.splitlines(keepends=True)
        changes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                names = [x.id for x in node.targets if isinstance(x, ast.Name)]
                if names in [["final_test"], ["test_top1"]]:
                    changes.append((node.lineno-1, node.end_lineno, "    " + names[0] + " = None  # test reserved for frozen milestones\n"))
        for start, end, replacement in sorted(changes, reverse=True):
            lines[start:end] = [replacement]
        text = "".join(lines).replace("{final_test:.4f}", "{final_test}").replace("{test_top1:.4f}", "{test_top1}")
    if filename == "qat_weight3_hls196.py":
        tree = ast.parse(text)
        lines = text.splitlines(keepends=True)
        for node in sorted(ast.walk(tree), key=lambda n: getattr(n, "lineno", 0), reverse=True):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "initial_test" for t in node.targets):
                lines[node.lineno-1:node.end_lineno] = ["    initial_test = None  # diagnostic baseline uses validation only\n"]
        text = "".join(lines).replace("{initial_test:.4f}", "{initial_test}")
    return text


def main():
    inventory = []
    patches = ["*** Begin Patch"]
    for name in FILES:
        original = (SOURCE / name).read_bytes()
        ported = adapt(original.decode(), name)
        target = HERE / "canonical" / name
        if target.exists():
            if target.read_text().rstrip() != ported.rstrip():
                prior = json.loads((HERE / "source_inventory.json").read_text())
                expected = next(item["port_sha256"] for item in prior if item["port"] == str(target.relative_to(HERE)))
                if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                    raise ValueError(f"refusing to replace changed port: {target}")
                patches.extend([f"*** Update File: {target}", "@@",
                                *["-"+line for line in target.read_text().splitlines()],
                                *["+"+line for line in ported.splitlines()]])
        else:
            patches.extend([f"*** Add File: {target}", *["+" + line for line in ported.splitlines()]])
        inventory.append({"source": str((SOURCE / name).relative_to(REPO)),
                          "source_sha256": hashlib.sha256(original).hexdigest(),
                          "port": str(target.relative_to(HERE)),
                          "port_sha256": hashlib.sha256(target.read_bytes() if target.exists() and target.read_text().rstrip() == ported.rstrip()
                                                        else ('\n'.join(ported.splitlines())+'\n').encode()).hexdigest()})
    manifest = HERE / 'source_inventory.json'
    if manifest.exists():
        patches.extend([f"*** Update File: {manifest}", "@@",
                        *["-"+line for line in manifest.read_text().splitlines()],
                        *["+"+line for line in json.dumps(inventory, indent=2).splitlines()]])
    else:
        patches.extend([f"*** Add File: {manifest}", *["+"+line for line in json.dumps(inventory, indent=2).splitlines()]])
    patches.append("*** End Patch")
    subprocess.run(["apply_patch"], input="\n".join(patches)+"\n", text=True, check=True,
                   stdout=subprocess.DEVNULL)
    print(f"Ported {len(inventory)} canonical source files")


if __name__ == "__main__":
    main()
