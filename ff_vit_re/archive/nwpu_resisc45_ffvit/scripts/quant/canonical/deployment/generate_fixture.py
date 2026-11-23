#!/usr/bin/env python3
"""Recompute the corrected semantic-input fixture and every exact boundary on CPU.

Imports are confined to the audited scripts already shipped in this bundle.
No reference output is read by this generator. Stage report/array pairs are
assembled in the fresh output directory because historical helpers expect both
in one directory, while the canonical bundle keeps reports separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def generate(project, output, image_path, classes):
    import numpy as np
    import torch
    from PIL import Image
    from qat_weight3_hls196 import eval_transform
    from stage4b_activation_ptq_eval import rebuild_stage3_model
    from stage4d_mlp_activation_qat import MLPActivationController
    from stage4j_attention_activation_qat import AttentionActivationController
    from stage4n_head_integer_audit import install_stage4m_exact_encoder
    from stage4o_exact_head_signedfix import apply_head_ln, exact_head_logits
    from stage4o2_head_safe_refit import load_selected_ln
    from stage4h_exact_layernorm_roundfix import wrap_signed
    from stage4q_generate_csim_fixture_v2 import make_input_codes
    from verify_patch_bitexact import compute_patch_from_banks

    project, output = Path(project).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("fixture output must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)

    def stage(name):
        return project / name

    stages = {name: stage(name) for name in (
        "stage3_patch_hls", "stage4f_exact_gelu", "stage4k_exact_attn_outer",
        "stage4k2_refined_qkv", "stage4l_exact_softmax_aq", "stage4m_exact_encoder",
        "stage4o_exact_head_signedfix", "stage4o2_head_safe")}
    artifacts = project
    checkpoints = project
    ranges = json.loads((artifacts / "stage4a_ranges/activation_ranges.json").read_text())["statistics"]
    model, backbone, source = rebuild_stage3_model(
        checkpoints / "hls196/best.pth",
        checkpoints / "qat_weight3_hls196/best_qat_state.pth", stages["stage3_patch_hls"])
    mlp = MLPActivationController(backbone, ranges)
    checkpoint = torch.load(checkpoints / "stage4j_attention_qat/best_attention_qat.pth",
                            map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["student_state"], strict=True)
    mlp.load_state_dict(checkpoint["mlp_controller_state"], strict=True)
    attention = AttentionActivationController(backbone, ranges,
        checkpoint["attention_controller_state"]["attn_out_scale"].cpu().numpy())
    attention.load_state_dict(checkpoint["attention_controller_state"], strict=True)
    model.eval()
    mlp.eval()
    attention.eval()
    mlp.set_active(range(12))
    attention.set_active(range(12))
    mlp.install()
    attention.install()
    patch_scale = json.loads((stages["stage3_patch_hls"] / "report.json").read_text())["patch_output"]["real_scale"]
    handles, final_scale = install_stage4m_exact_encoder(
        backbone, mlp, attention, torch.device("cpu"), stages["stage4f_exact_gelu"],
        stages["stage4k_exact_attn_outer"], stages["stage4k2_refined_qkv"],
        stages["stage4l_exact_softmax_aq"], stages["stage4m_exact_encoder"], patch_scale)
    if source["classes"] != classes:
        raise ValueError("checkpoint class order differs from dataset")
    image = eval_transform()(Image.open(image_path).convert("RGB"))
    input_codes = make_input_codes(image).numpy()
    outputs = [None] * 12
    for index, block in enumerate(backbone.vit.blocks):
        def capture(module, inputs, value, index=index):
            outputs[index] = value.detach().cpu()
        handles.append(block.register_forward_hook(capture))
    with torch.inference_mode():
        model(image.unsqueeze(0))
    for handle in handles:
        handle.remove()
    attention.remove()
    mlp.remove()

    refs = output / "refs"
    refs.mkdir()
    def write(path, values):
        np.asarray(values, dtype="<i4").tofile(path)
    def stream(values):
        return values.reshape(98, 2, 192).transpose(0, 2, 1).reshape(-1)
    write(output / "input.bin", input_codes)
    report_m = json.loads((stages["stage4m_exact_encoder"] / "report.json").read_text())
    scales = [*report_m["block_input_int13_scales"][1:], float(final_scale)]
    for index, (value, scale) in enumerate(zip(outputs, scales)):
        codes = wrap_signed(torch.round(value[0] / float(scale)).to(torch.int64), 13).numpy()
        write(refs / f"ref_block{index}_out.bin", stream(codes))
    head_input = torch.from_numpy(codes[0]).unsqueeze(0)
    head_ln = apply_head_ln(head_input, load_selected_ln(stages["stage4o_exact_head_signedfix"]))
    head_dir = stages["stage4o2_head_safe"]
    active, wrapped = exact_head_logits(head_ln,
        torch.from_numpy(np.load(head_dir / "head_weight_active.npy").astype(np.int64)),
        torch.from_numpy(np.load(head_dir / "head_bias_active.npy").astype(np.int64)))
    if bool(wrapped.any()):
        raise ValueError("safe Head unexpectedly wrapped")
    logits = np.full(1000, -262144, dtype=np.int64)
    logits[:len(classes)] = active[0].numpy()
    write(refs / "ref_head_input.bin", head_input.numpy())
    write(refs / "ref_head_ln.bin", head_ln.numpy())
    write(refs / "ref_logits.bin", logits)
    write(output / "output.bin", logits)
    with np.load(stages["stage3_patch_hls"] / "patch_rom_banks.npz") as banks:
        physical = input_codes.reshape(98, 2, 768).transpose(0, 2, 1)
        patch = compute_patch_from_banks(physical, banks["PATCH_WEIGHT_BANK"],
            banks["PATCH_BIAS_BANK"], banks["PATCH_CLS_BANK"],
            shift=int(banks["PATCH_SCALARS"][0]), output_bits=13)
    write(refs / "ref_patch.bin", stream(patch))
    report = {"method": "recomputed from image and frozen exact model",
              "device": "cpu", "image": str(image_path),
              "predicted_class_id": int(logits[:len(classes)].argmax()),
              "inactive_value": -262144, "files": {}}
    for path in sorted(output.glob("*.bin")):
        report["files"][path.name] = {"bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (output / "fixture.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


