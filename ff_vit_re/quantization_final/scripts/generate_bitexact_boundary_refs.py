#!/usr/bin/env python3
"""Generate independent software-integer references at HLS boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from qat_weight3_hls196 import eval_transform
from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from stage4h_exact_layernorm_roundfix import wrap_signed
from stage4j_attention_activation_qat import AttentionActivationController
from stage4n_head_integer_audit import install_stage4m_exact_encoder
from stage4o2_head_safe_refit import load_selected_ln
from stage4o_exact_head_signedfix import apply_head_ln, exact_head_logits
from stage4q_generate_csim_fixture_v2 import make_input_codes


INT19_MIN = -(1 << 18)


def logical_to_fm_stream(logical: np.ndarray) -> np.ndarray:
    """Convert `[token,channel]` to the C++ BRAM dump order `[tt,c,tp]`."""
    logical = np.asarray(logical)
    tokens, channels = logical.shape
    if tokens % 2:
        raise ValueError("token count must be divisible by TP=2")
    return logical.reshape(tokens // 2, 2, channels).transpose(0, 2, 1).reshape(-1)


def write_i32(path: Path, values: np.ndarray) -> None:
    np.asarray(values, dtype="<i4").tofile(path)


@torch.inference_mode()
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("stage4q_csim_fixture/fixture.json"))
    parser.add_argument("--hls-input", type=Path, default=Path("/home/user/Desktop/FF_Vit/flash_vit_2/input.bin"))
    parser.add_argument("--output", type=Path, default=Path("bitexact_audit/refs"))
    parser.add_argument("--source-checkpoint", default="./plantvillage_hls196/best.pth")
    parser.add_argument("--qat-checkpoint", default="./qat_weight3_hls196/best_qat_state.pth")
    parser.add_argument("--stage3-dir", default="./stage3_patch_hls")
    parser.add_argument("--ranges", default="./stage4a_ranges/activation_ranges.json")
    parser.add_argument("--attention-qat-checkpoint", default="./stage4j_attention_qat/best_attention_qat.pth")
    parser.add_argument("--stage4f-dir", default="./stage4f_exact_gelu")
    parser.add_argument("--stage4k-dir", default="./stage4k_exact_attn_outer")
    parser.add_argument("--stage4k2-dir", default="./stage4k2_refined_qkv")
    parser.add_argument("--stage4l-dir", default="./stage4l_exact_softmax_aq")
    parser.add_argument("--stage4m-dir", default="./stage4m_exact_encoder")
    parser.add_argument("--stage4o-dir", default="./stage4o_exact_head_signedfix")
    parser.add_argument("--stage4o2-dir", default="./stage4o2_head_safe")
    parser.add_argument("--patch-scale", type=float, default=0.007332006125)
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    image = eval_transform()(Image.open(fixture["image_path"]).convert("RGB"))
    semantic_input = make_input_codes(image).cpu().numpy().astype(np.int64)
    installed_input = np.fromfile(args.hls_input, dtype="<i4").reshape(196, 768)
    np.testing.assert_array_equal(installed_input, semantic_input)

    with open(args.ranges, "r", encoding="utf-8") as handle:
        ranges = json.load(handle)["statistics"]

    model, backbone, _ = rebuild_stage3_model(
        args.source_checkpoint,
        args.qat_checkpoint,
        args.stage3_dir,
    )
    mlp_ctrl = MLPActivationController(backbone, ranges)
    checkpoint = torch.load(
        args.attention_qat_checkpoint,
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(checkpoint["student_state"], strict=True)
    mlp_ctrl.load_state_dict(checkpoint["mlp_controller_state"], strict=True)
    old_attn_out = checkpoint["attention_controller_state"]["attn_out_scale"].cpu().numpy()
    attn_ctrl = AttentionActivationController(backbone, ranges, old_attn_out)
    attn_ctrl.load_state_dict(checkpoint["attention_controller_state"], strict=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device).eval()
    mlp_ctrl = mlp_ctrl.to(device).eval()
    attn_ctrl = attn_ctrl.to(device).eval()
    mlp_ctrl.set_active(range(12))
    attn_ctrl.set_active(range(12))
    mlp_ctrl.install()
    attn_ctrl.install()

    exact_handles, final_scale = install_stage4m_exact_encoder(
        backbone,
        mlp_ctrl,
        attn_ctrl,
        device,
        args.stage4f_dir,
        args.stage4k_dir,
        args.stage4k2_dir,
        args.stage4l_dir,
        args.stage4m_dir,
        args.patch_scale,
    )

    block_outputs: list[torch.Tensor | None] = [None] * 12
    capture_handles = []
    for block_index, block in enumerate(backbone.vit.blocks):
        def capture(module, inputs, output, block_index=block_index):
            block_outputs[block_index] = output.detach().cpu()
        capture_handles.append(block.register_forward_hook(capture))

    _ = model(image.unsqueeze(0).to(device))
    for handle in capture_handles:
        handle.remove()

    report_m = json.loads((Path(args.stage4m_dir) / "report.json").read_text())
    input_scales = report_m["block_input_int13_scales"]
    output_scales = [*input_scales[1:], float(final_scale)]

    args.output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "source": "Stage4M exact integer hook chain",
        "block_output_scales": output_scales,
        "files": {},
    }
    block_codes = []
    for block_index, (captured, scale) in enumerate(zip(block_outputs, output_scales)):
        if captured is None:
            raise RuntimeError(f"block {block_index} output was not captured")
        codes = torch.round(captured[0] / float(scale)).to(torch.int64)
        codes = wrap_signed(codes, 13).numpy()
        block_codes.append(codes)
        path = args.output / f"ref_block{block_index}_out.bin"
        write_i32(path, logical_to_fm_stream(codes))
        manifest["files"][f"block{block_index}"] = str(path)

    head_input = block_codes[11][0]
    head_input_path = args.output / "ref_head_input.bin"
    write_i32(head_input_path, head_input)

    ln_fit = load_selected_ln(args.stage4o_dir)
    head_ln = apply_head_ln(
        torch.from_numpy(head_input).unsqueeze(0),
        {
            **ln_fit,
            "lnw": ln_fit["lnw"],
            "lnb": ln_fit["lnb"],
            "rsqrt_table": ln_fit["rsqrt_table"],
        },
    )[0].cpu()
    head_ln_path = args.output / "ref_head_ln.bin"
    write_i32(head_ln_path, head_ln.numpy())

    o2 = Path(args.stage4o2_dir)
    head_weight = torch.from_numpy(np.load(o2 / "head_weight_38.npy").astype(np.int64))
    head_bias = torch.from_numpy(np.load(o2 / "head_bias_38.npy").astype(np.int64))
    active_logits, wrap = exact_head_logits(
        head_ln.unsqueeze(0),
        head_weight,
        head_bias,
    )
    if bool(wrap.any()):
        raise RuntimeError("Head int19 wrapped for the selected fixture")
    logits = np.full(1000, INT19_MIN, dtype=np.int64)
    logits[:38] = active_logits[0].cpu().numpy()
    logits_path = args.output / "ref_logits.bin"
    write_i32(logits_path, logits)

    manifest["files"].update({
        "head_input": str(head_input_path),
        "head_ln": str(head_ln_path),
        "logits": str(logits_path),
    })
    manifest["predicted_class_id"] = int(np.argmax(logits[:38]))
    manifest["inactive_unique_values"] = np.unique(logits[38:]).tolist()
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))

    for handle in exact_handles:
        handle.remove()
    attn_ctrl.remove()
    mlp_ctrl.remove()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
