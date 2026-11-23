"""Atomic NWPU export using the reviewed canonical packer and exact arithmetic.

The active HLS ROM contributes declarations and dimensions only. Every initializer
is zeroed before the canonical exporter installs the thirteen NWPU arrays.
"""
from __future__ import annotations

import json
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "scripts/quant"
sys.path[:0] = [str(ROOT), str(QUANT), str(QUANT / "canonical")]
from src.artifact_contract import inventory, sha256
from src.manifest_dataset import load_manifest_bundle, VerifiedSourceIndex
import manifest_adapter
from canonical.deployment import export_hls as canonical
from deployment.generate_fixture import generate
from stage4q_generate_csim_fixture_v2 import make_input_codes
from verify_patch_bitexact import parse_c_array, compute_patch_from_banks

SHAPES = {
    "PATCH_SCALARS": (4,), "PATCH_WEIGHT": (192, 768),
    "PATCH_BIAS": (37632,), "PATCH_CLS": (192,),
    "PATCH_WEIGHT_BANK": (12, 24, 16, 32), "PATCH_BIAS_BANK": (2, 12, 98, 16),
    "PATCH_CLS_BANK": (12, 16), "HEAD_LN_SCALARS": (8,), "HEAD_LNW": (192,),
    "HEAD_LNB": (192,), "HEAD_RSQRT": (128,), "HEAD_WEIGHT": (1000, 192),
    "HEAD_BIAS": (1000,),
}
# Exact audited declarations, not merely types large enough for today's values.
# block0 reads Patch banks directly; Head loading/LN also consumes these types.
# tests/rom_declaration_contract.cpp binds native widths and all thirteen array
# types/dimensions to the installed Vitis C++ implementation.
ROM_TYPES = {
    "PATCH_SCALARS": ("int", 32), "PATCH_WEIGHT": ("int", 32),
    "PATCH_BIAS": ("int", 32), "PATCH_CLS": ("int", 32),
    "PATCH_WEIGHT_BANK": ("int", 32), "PATCH_BIAS_BANK": ("int", 32),
    "PATCH_CLS_BANK": ("int", 32), "HEAD_LN_SCALARS": ("int", 32),
    "HEAD_LNW": ("int", 32), "HEAD_LNB": ("long long", 64),
    "HEAD_RSQRT": ("int", 32), "HEAD_WEIGHT": ("ap_int<8>", 8),
    "HEAD_BIAS": ("ap_int<19>", 19),
}
SIZES = {"weights.bin": 2772096, "weights_hls.bin": 2772096,
         "weights_fields.bin": 5426160, "input.bin": 602112, "output.bin": 4000}
DEFAULT_HLS = Path("/home/user/Desktop/FF_Vit/flash_vit_2/src")


def _json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def _info(path):
    return {"size_bytes": Path(path).stat().st_size, "sha256": sha256(path)}


def boundary_stream(values):
    """Logical [196,192] to active debug_dump_fm [98,192,2] order."""
    return np.asarray(values).reshape(98, 2, 192).transpose(0, 2, 1).reshape(-1)


def _validate_declarations(text):
    """Reject C++ conversions that a literal-only NumPy parser cannot observe."""
    names = re.findall(r"(?m)^const\s+[^\n;]+\b(\w+)\s*\[[^;=]*=", text)
    if len(names) != len(SHAPES) or set(names) != set(SHAPES):
        raise ValueError("ROM contains unknown or missing parameter arrays")
    contracts = {}
    for name, shape in SHAPES.items():
        start, begin, _, _ = canonical._array_span(text, name)
        match = re.fullmatch(
            rf"const\s+(?P<type>[\w\s<>]+?)\s+{name}"
            r"(?P<dims>(?:\s*\[\s*\d+\s*\])+)\s*=\s*", text[start:begin])
        if match is None:
            raise ValueError(f"Invalid ROM declaration: {name}")
        element_type = re.sub(r"\s*([<>])\s*", r"\1", " ".join(match["type"].split()))
        expected_type, bits = ROM_TYPES[name]
        if element_type != expected_type:
            raise ValueError(f"ROM declaration type changed: {name}: expected {expected_type}, got {element_type}")
        dimensions = tuple(map(int, re.findall(r"\[\s*(\d+)\s*\]", match["dims"])))
        if dimensions != shape:
            raise ValueError(f"ROM declaration shape changed: {name}")
        contracts[name] = {"cpp_type": expected_type, "signed": True,
                           "bits": bits, "shape": list(shape)}
    return contracts


def _neutral_templates(hls_src, destination):
    source = Path(hls_src) / "fixed_patch_head_rom.h"
    text = source.read_text()
    contracts = _validate_declarations(text)
    declarations, review = [], {}
    for name, shape in SHAPES.items():
        start, begin, end, finish = canonical._array_span(text, name)
        declaration = text[start:begin]
        body = text[begin:end]
        if len(re.findall(r"-?\d+", body)) != int(np.prod(shape)):
            raise ValueError(f"Active ROM initializer count changed: {name}")
        if re.sub(r"[\s{},\d-]", "", re.sub(r"(?<=\d)LL\b", "", body)):
            raise ValueError(f"Nonliteral active ROM initializer: {name}")
        # No numerical value from the active model survives this substitution.
        declarations.append(declaration + re.sub(r"-?\d+", "0", body) + ";")
        review[name] = {**contracts[name], "entries": int(np.prod(shape)),
                        "initializer_policy": "all zero; replaced from NWPU producer"}
    destination.mkdir()
    neutral = destination / "fixed_patch_head_rom.h"
    neutral.write_text("#ifndef __FIXED_PATCH_HEAD_ROM_H__\n#define __FIXED_PATCH_HEAD_ROM_H__\n"
                       "#include <ap_int.h>\nnamespace fixed_patch_head_rom {\n"
                       + "\n\n".join(declarations) + "\n}\n#endif\n")
    block = Path(hls_src) / "block0.cpp"
    # Reject unexpected semantic changes instead of silently patching the source.
    if canonical._canonical_block0(block) != block.read_text():
        raise ValueError("Active block0 does not already implement the approved signed Head contract")
    shutil.copyfile(block, destination / "block0.cpp")
    return {"arrays": review, "source_rom": _info(source), "source_block0": _info(block),
            "source_directory": str(Path(hls_src).resolve()),
            "template_is_parameter_authority": False,
            "review": "Exactly 13 literal arrays with audited C++ element types, signedness, widths "
                      "and dimensions; initializers zeroed. "
                      "Only declaration types/shapes and brace layout retained. Canonical exporter "
                      "installs all seven Patch and six Head arrays from the NWPU run. "
                      "block0 is byte-identical to the active signed-Head source."}


def _validate_rom(run, rom):
    _validate_declarations(Path(rom).read_text())
    actual = {name: parse_c_array(rom, name, shape) for name, shape in SHAPES.items()}
    expected = {}
    with np.load(run / "stage3_patch_hls/patch_rom_banks.npz", allow_pickle=False) as banks:
        for name in canonical.PATCH_BANKS:
            expected[name] = banks[name]
    for name, (filename, _) in canonical.PATCH_RAW.items():
        expected[name] = torch.load(run / "stage3_patch_hls" / filename,
                                    map_location="cpu", weights_only=True).numpy().reshape(SHAPES[name])
    for name in canonical.HEAD_NAMES:
        expected[name] = parse_c_array(run / "stage4o2_head_safe/generated_head_rom_safe.h", name, SHAPES[name])
    checks = {}
    for name in SHAPES:
        bad = int(np.count_nonzero(actual[name] != expected[name]))
        if bad:
            raise ValueError(f"NWPU ROM identity mismatch: {name}: {bad}")
        checks[name] = {"values": actual[name].size, "mismatches": bad}
    for name, filename, inactive in (("HEAD_WEIGHT", "head_weight_active.npy", 0),
                                     ("HEAD_BIAS", "head_bias_active.npy", -262144)):
        if not np.array_equal(actual[name][:45], np.load(run / "stage4o2_head_safe" / filename)):
            raise ValueError(f"Active Head mismatch: {name}")
        if not np.all(actual[name][45:] == inactive):
            raise ValueError(f"Unsafe inactive Head: {name}")
    # Independently bind the exported LN arrays to their selected fitted producer.
    for name, filename in (("HEAD_LN_SCALARS", "head_ln_scalars.npy"),
                           ("HEAD_LNW", "head_lnw.npy"), ("HEAD_LNB", "head_lnb.npy"),
                           ("HEAD_RSQRT", "head_rsqrt.npy")):
        if not np.array_equal(actual[name], np.load(run / "stage4o_exact_head_signedfix" / filename)):
            raise ValueError(f"Selected Head LayerNorm mismatch: {name}")
    return checks


def verify_software(run, deployment):
    """Fresh frozen-model reconstruction consuming input.bin and exported Head ROM.

The encoder is rebuilt from reviewed NWPU checkpoints/arrays. The input file is
decoded back to its exact normalized pixel codes; the Head uses parsed ROM data.
The Patch is checked both against the model and the independent bank-loop oracle.
This is a software check, not an HLS simulation or a separate encoder algorithm.
"""
    from stage4b_activation_ptq_eval import rebuild_stage3_model
    from stage4d_mlp_activation_qat import MLPActivationController
    from stage4j_attention_activation_qat import AttentionActivationController
    from stage4n_head_integer_audit import install_stage4m_exact_encoder
    from stage4o_exact_head_signedfix import apply_head_ln, exact_head_logits
    from stage4h_exact_layernorm_roundfix import wrap_signed

    run, deployment = Path(run), Path(deployment)
    _validate_declarations((deployment / "fixed_patch_head_rom.h").read_text())
    torch.set_num_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    codes = np.fromfile(deployment / "input.bin", dtype="<i4")
    if codes.size != 196 * 768 or np.any(codes < -32768) or np.any(codes > 32767):
        raise ValueError("input.bin violates signed-int16 semantic contract")
    codes = codes.reshape(196, 768)
    image = torch.nn.functional.fold(torch.from_numpy(codes.T.copy()).float().unsqueeze(0),
                                     (224, 224), (16, 16), stride=(16, 16)) / 64.0
    if not np.array_equal(make_input_codes(image[0]).numpy(), codes):
        raise ValueError("input.bin token/channel roundtrip mismatch")
    ranges = json.loads((run / "stage4a_ranges/activation_ranges.json").read_text())["statistics"]
    model, backbone, _ = rebuild_stage3_model(run / "hls196/best.pth",
        run / "qat_weight3_hls196/best_qat_state.pth", run / "stage3_patch_hls")
    mlp = MLPActivationController(backbone, ranges)
    state = torch.load(run / "stage4j_attention_qat/best_attention_qat.pth", map_location="cpu", weights_only=True)
    model.load_state_dict(state["student_state"], strict=True)
    mlp.load_state_dict(state["mlp_controller_state"], strict=True)
    attention = AttentionActivationController(backbone, ranges,
        state["attention_controller_state"]["attn_out_scale"].numpy())
    attention.load_state_dict(state["attention_controller_state"], strict=True)
    model.eval(); mlp.eval(); attention.eval()
    mlp.set_active(range(12)); attention.set_active(range(12))
    mlp.install(); attention.install()
    patch_scale = json.loads((run / "stage3_patch_hls/report.json").read_text())["patch_output"]["real_scale"]
    handles, final_scale = install_stage4m_exact_encoder(backbone, mlp, attention, torch.device("cpu"),
        run / "stage4f_exact_gelu", run / "stage4k_exact_attn_outer", run / "stage4k2_refined_qkv",
        run / "stage4l_exact_softmax_aq", run / "stage4m_exact_encoder", patch_scale)
    outputs = {}
    def capture(name):
        def hook(module, inputs, value):
            outputs[name] = value.detach().cpu()
        return hook
    handles.append(model.patch.register_forward_hook(capture("patch")))
    for i, block in enumerate(backbone.vit.blocks):
        handles.append(block.register_forward_hook(capture(f"block{i}")))
    try:
        with torch.inference_mode():
            model(image)
    finally:
        for handle in handles:
            handle.remove()
        attention.remove(); mlp.remove()
    report_m = json.loads((run / "stage4m_exact_encoder/report.json").read_text())
    scales = [*report_m["block_input_int13_scales"][1:], final_scale]
    boundaries = {"patch": wrap_signed(torch.round(outputs["patch"][0] / patch_scale).long(), 13).numpy()}
    for i, scale in enumerate(scales):
        boundaries[f"block{i}"] = wrap_signed(torch.round(outputs[f"block{i}"][0] / float(scale)).long(), 13).numpy()
    rom = deployment / "fixed_patch_head_rom.h"
    arrays = {name: parse_c_array(rom, name, shape) for name, shape in SHAPES.items()}
    oracle_patch = compute_patch_from_banks(codes.reshape(98, 2, 768).transpose(0, 2, 1),
        arrays["PATCH_WEIGHT_BANK"], arrays["PATCH_BIAS_BANK"], arrays["PATCH_CLS_BANK"],
        shift=int(arrays["PATCH_SCALARS"][0]), output_bits=13)
    if not np.array_equal(oracle_patch, boundaries["patch"]):
        raise ValueError("Independent ROM bank Patch differs from reconstructed model")
    head_input = torch.from_numpy(boundaries["block11"][0]).unsqueeze(0)
    fit = {"cursor_bits": 7, "scalars": arrays["HEAD_LN_SCALARS"],
           "lnw": torch.from_numpy(arrays["HEAD_LNW"]), "lnb": torch.from_numpy(arrays["HEAD_LNB"]),
           "rsqrt_table": torch.from_numpy(arrays["HEAD_RSQRT"])}
    head_ln = apply_head_ln(head_input, fit)
    logits, wraps = exact_head_logits(head_ln, torch.from_numpy(arrays["HEAD_WEIGHT"]),
                                     torch.from_numpy(arrays["HEAD_BIAS"]))
    boundaries.update(head_input=head_input.numpy().reshape(-1), head_ln=head_ln.numpy().reshape(-1),
                      logits=logits.numpy().reshape(-1))
    checks = {}
    for name, values in boundaries.items():
        filename = f"ref_{name}_out.bin" if name.startswith("block") else f"ref_{name}.bin"
        actual = boundary_stream(values) if values.size == 37632 else values.reshape(-1)
        expected = np.fromfile(deployment / "refs" / filename, dtype="<i4")
        bad = int(np.count_nonzero(actual != expected)) if actual.shape == expected.shape else max(actual.size, expected.size)
        if bad:
            raise ValueError(f"Software boundary mismatch: {name}: {bad}")
        checks[name] = {"values": actual.size, "mismatches": bad, "reference_sha256": sha256(deployment / "refs" / filename)}
    if not np.array_equal(boundaries["logits"], np.fromfile(deployment / "output.bin", dtype="<i4")):
        raise ValueError("Software output.bin mismatch")
    if bool(wraps.any()) or not np.all(boundaries["logits"][45:] == -262144) or int(logits.argmax()) >= 45:
        raise ValueError("Fixture Head safety failed")
    return {"passed": True, "boundaries": checks, "total_boundary_values": sum(v["values"] for v in checks.values()),
            "patch_independent_bank_oracle_equal": True, "input_roundtrip_equal": True,
            "head_accumulator_wraps": int(wraps.sum()), "predicted_class_id": int(logits.argmax()),
            "scope": "Fresh CPU exact-model reconstruction from input.bin; all 1000 Head outputs calculated from exported ROM. "
                     "Encoder uses canonical arithmetic and frozen producer arrays; independent C++ verifies packing only.",
            "hls_csim": "not tested", "fpga_board": "not tested"}


def export_deployment(run, output, *, hls_src=DEFAULT_HLS, metadata=None, source=None, fixture_index=0, cxx="g++"):
    run, output = Path(run).resolve(), Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(f"Refusing to overwrite deployment: {output}")
    metadata = Path(metadata or ROOT / "metadata").resolve()
    source = Path(source or ROOT.parent / "Dataset").resolve()
    if output == run or output.is_relative_to(run) or output == source or output.is_relative_to(source):
        raise ValueError("Deployment must be isolated from run artifacts and dataset")
    evidence_path = ROOT / "reports/stage4_exact_chain.json"
    evidence = json.loads(evidence_path.read_text())
    fresh_path = ROOT / "reports/task5_exact_independent_eval.json"
    fresh = json.loads(fresh_path.read_text())
    gate = evidence["validation_gate"]
    measured_drop = float(gate["fp32_top1"]) - float(fresh["results"]["val"]["top1"])
    if evidence["verdict"] != "APPROVED" or not gate["passed"] or measured_drop > 5.0:
        raise ValueError("Task 5 exact-integer validation gate did not pass")
    before = inventory(run)
    if before != fresh["run_artifact_hashes"]:
        raise ValueError("Run artifacts differ from approved Task 5 independent review")
    bundle = manifest_adapter.configure(metadata, source)
    if list(bundle.classes) != evidence["classes"] or list(bundle.classes) != fresh["classes"]:
        raise ValueError("Frozen class order differs from Task 5 evidence")
    if inventory(metadata) != fresh["manifest_hashes"]:
        raise ValueError("Frozen manifests differ from Task 5 evidence")
    records = bundle.records_for("test")
    if not 0 <= fixture_index < len(records):
        raise ValueError("fixture-index is outside the frozen test manifest")
    record = records[fixture_index]
    VerifiedSourceIndex(source).verify(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Same-filesystem staging; rename only after every numerical check passes.
    with tempfile.TemporaryDirectory(prefix=".nwpu-deployment-", dir=output.parent) as temp:
        staging = Path(temp)
        payload = staging / "payload"
        templates = staging / "source_templates"
        template_review = _neutral_templates(Path(hls_src), templates)
        inputs = canonical.ExportInputs.from_project(run, rom_template=templates / "fixed_patch_head_rom.h",
                                                    block0_template=templates / "block0.cpp")
        canonical_manifest = canonical.export_hls(inputs, payload, cxx=cxx)
        array_checks = _validate_rom(run, payload / "fixed_patch_head_rom.h")
        fixture_dir = staging / "fixture"
        generate(run, fixture_dir, source / record.relative_path, list(bundle.classes))
        for item in fixture_dir.iterdir():
            shutil.move(str(item), payload / item.name)
        software = verify_software(run, payload)
        # Repeat the original image preprocessing/model path in a fresh instance.
        repeated = staging / "repeat"
        generate(run, repeated, source / record.relative_path, list(bundle.classes))
        for path in repeated.rglob("*.bin"):
            if path.read_bytes() != (payload / path.relative_to(repeated)).read_bytes():
                raise ValueError(f"Fixture determinism failed: {path.name}")
        software["fixture_deterministic"] = True
        for name, size in SIZES.items():
            if (payload / name).stat().st_size != size:
                raise ValueError(f"Invalid output byte count: {name}")
        shutil.move(str(templates), payload / "source_templates")
        shutil.copyfile(QUANT / "canonical/lib/pack_weights_hls.cpp", payload / "pack_weights_hls.cpp")
        after = inventory(run)
        if before != after:
            raise ValueError("Input run changed during export")
        manifest = {"schema_version": 1, "dataset": "NWPU-RESISC45", "classes": list(bundle.classes),
            "contract": {**canonical_manifest["contract"], "classes_active": 45, "classes_inactive": 955,
                         "inactive_logit": -262144, "channels": 192, "input_channels": 768,
                         "blocks": 12, "mlp_channels": 768, "output_logits": 1000,
                         "input_order": "[token, channel], little-endian int32 carrying signed-int16 codes",
                         "boundary_order": "[token_pair, channel, token_lane], little-endian int32"},
            "fixture": {"split": "test", "index": fixture_index, "relative_path": record.relative_path,
                        "image_sha256": record.sha256, "label": record.label,
                        "preprocessing": "canonical deterministic eval_transform; round(64 * normalized RGB); first token replaced by CLS ROM"},
            "template_review": template_review, "rom_array_checks": array_checks,
            "software_verification": software, "accuracy": {"validation_gate": gate, "milestones": evidence["metrics"],
                                                            "exact_independent": fresh["results"]},
            "provenance": {"run_directory": str(run), "run_artifacts": before, "metadata": inventory(metadata),
                           "stage5_evidence": _info(evidence_path), "stage5_independent": _info(fresh_path),
                           "canonical_export_inputs": canonical_manifest["inputs"],
                           "exporter": _info(Path(__file__)), "canonical_sources": inventory(QUANT / "canonical")},
            "environment": {"python": platform.python_version(), "interpreter": sys.executable,
                            "torch": torch.__version__, "numpy": np.__version__, "device": "cpu"},
            "run_artifacts_unchanged": True,
            "publication": "atomic rename after verification; existing nonempty destinations refused",
            "outputs": {str(p.relative_to(payload)): _info(p) for p in sorted(payload.rglob("*"))
                        if p.is_file() and p.name != "deployment_manifest.json"}}
        _json(payload / "deployment_manifest.json", manifest)
        # Recheck destination immediately before atomic publication.
        if output.exists():
            if any(output.iterdir()):
                raise FileExistsError(f"Output became nonempty: {output}")
            output.rmdir()
        payload.rename(output)
    return manifest
