#!/usr/bin/env python3
"""
Stage 4Q: generate one deterministic HLS C-sim fixture for the final
PlantVillage FF-ViT deployment.

Outputs:
  input.bin   : 196 x 768 int32 values. Each value is the signed int16
                normalized-image code q=round(x_norm*64), patchified in
                PyTorch Conv2d/F.unfold order.
  output.bin  : 1000 int32 reference logits. The first 38 are the exact
                signed-fix W8/int19 PlantVillage Head outputs; logits
                38..999 equal INT19_MIN, matching the Stage4O2 padded ROM.
  fixture.json: selected image, label, predicted class, ranges, hashes.

The exact encoder reconstruction reuses the frozen Stage4M chain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import torch
import torch.nn.functional as F
from torchvision import datasets

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from stage4j_attention_activation_qat import AttentionActivationController
from stage4n_head_integer_audit import install_stage4m_exact_encoder
from stage4o_exact_head_signedfix import apply_head_ln, exact_head_logits
from stage4o2_head_safe_refit import load_selected_ln
from stage4h_exact_layernorm_roundfix import wrap_signed
from qat_weight3_hls196 import eval_transform


T = 196
PATCH_DIM = 768
INT19_MIN = -(1 << 18)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_input_codes(img_chw: torch.Tensor) -> torch.Tensor:
    """
    img_chw is the normalized eval-transform tensor [3,224,224].

    Stage2 input rule:
        q = round(x_norm * 64)

    HLS testbench stores each stream value in an int32 input_data array,
    while the AXI packet element itself is ap_int<16>.
    """
    if tuple(img_chw.shape) != (3, 224, 224):
        raise RuntimeError(
            f"Expected normalized [3,224,224], got {tuple(img_chw.shape)}"
        )

    q = torch.round(
        img_chw * 64.0
    ).to(torch.int64)

    if bool(((q < -32768) | (q > 32767)).any()):
        raise RuntimeError("Input quantization overflowed signed int16")

    # Conv2d-compatible patch flattening:
    # [1,3,224,224] -> [1,768,196] -> [196,768].
    patches = F.unfold(
        q.unsqueeze(0).to(torch.float32),
        kernel_size=(16, 16),
        stride=(16, 16),
    )

    patches = (
        torch.round(patches)
        .to(torch.int64)
        .squeeze(0)
        .transpose(0, 1)
        .contiguous()
    )

    if tuple(patches.shape) != (T, PATCH_DIM):
        raise RuntimeError(
            f"Patchified input shape {tuple(patches.shape)} != {(T, PATCH_DIM)}"
        )

    return patches


@torch.inference_mode()
def run_exact_encoder_and_capture_cls(
    model,
    backbone,
    image,
    device,
    final_scale,
):
    cache = {"x": None}

    def hook(module, inputs, output):
        cache["x"] = output

    h = backbone.vit.blocks[11].register_forward_hook(hook)

    _ = model(
        image.unsqueeze(0).to(device)
    )

    h.remove()

    x = cache["x"]
    if x is None:
        raise RuntimeError("Final encoder output was not captured")

    cls_real = x[0, 0, :]

    cls_q = torch.round(
        cls_real / float(final_scale)
    ).to(torch.int64)

    cls_q = wrap_signed(
        cls_q,
        13,
    ).cpu()

    return cls_q


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--source-checkpoint",
        default="./plantvillage_hls196/best.pth",
    )
    ap.add_argument(
        "--qat-checkpoint",
        default="./qat_weight3_hls196/best_qat_state.pth",
    )
    ap.add_argument(
        "--stage3-dir",
        default="./stage3_patch_hls",
    )
    ap.add_argument(
        "--ranges",
        default="./stage4a_ranges/activation_ranges.json",
    )
    ap.add_argument(
        "--attention-qat-checkpoint",
        default="./stage4j_attention_qat/best_attention_qat.pth",
    )

    ap.add_argument(
        "--stage4f-dir",
        default="./stage4f_exact_gelu",
    )
    ap.add_argument(
        "--stage4k-dir",
        default="./stage4k_exact_attn_outer",
    )
    ap.add_argument(
        "--stage4k2-dir",
        default="./stage4k2_refined_qkv",
    )
    ap.add_argument(
        "--stage4l-dir",
        default="./stage4l_exact_softmax_aq",
    )
    ap.add_argument(
        "--stage4m-dir",
        default="./stage4m_exact_encoder",
    )
    ap.add_argument(
        "--stage4o-dir",
        default="./stage4o_exact_head_signedfix",
    )
    ap.add_argument(
        "--stage4o2-dir",
        default="./stage4o2_head_safe",
    )

    ap.add_argument(
        "--data-root",
        default="./datasets/PlantVillage/splits",
    )
    ap.add_argument(
        "--split",
        default="val",
        choices=["train", "val", "test"],
    )
    ap.add_argument(
        "--image-index",
        type=int,
        default=0,
    )
    ap.add_argument(
        "--patch-scale",
        type=float,
        default=0.007332006125,
    )
    ap.add_argument(
        "--output",
        default="./stage4q_csim_fixture",
    )
    ap.add_argument(
        "--install-dir",
        default="",
        help=(
            "Optional directory receiving input.bin/output.bin, e.g. "
            "/home/user/Desktop/FF_Vit/flash_vit_2"
        ),
    )

    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    with open(args.ranges, "r", encoding="utf-8") as f:
        ranges = json.load(f)["statistics"]

    model, backbone, source = rebuild_stage3_model(
        args.source_checkpoint,
        args.qat_checkpoint,
        args.stage3_dir,
    )

    mlp_ctrl = MLPActivationController(
        backbone,
        ranges,
    )

    ckpt = torch.load(
        args.attention_qat_checkpoint,
        map_location="cpu",
        weights_only=True,
    )

    model.load_state_dict(
        ckpt["student_state"],
        strict=True,
    )

    mlp_ctrl.load_state_dict(
        ckpt["mlp_controller_state"],
        strict=True,
    )

    old_attn_out = (
        ckpt["attention_controller_state"]["attn_out_scale"]
        .detach()
        .cpu()
        .numpy()
    )

    attn_ctrl = AttentionActivationController(
        backbone,
        ranges,
        old_attn_out,
    )

    attn_ctrl.load_state_dict(
        ckpt["attention_controller_state"],
        strict=True,
    )

    model = model.to(device)
    mlp_ctrl = mlp_ctrl.to(device)
    attn_ctrl = attn_ctrl.to(device)

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

    ds = datasets.ImageFolder(
        Path(args.data_root) / args.split,
        transform=eval_transform(),
    )

    if list(ds.classes) != list(source["classes"]):
        raise RuntimeError("Dataset class ordering mismatch")

    idx = int(args.image_index)
    if idx < 0 or idx >= len(ds):
        raise IndexError(
            f"image-index {idx} outside [0,{len(ds)-1}]"
        )

    image, label = ds[idx]
    image_path, raw_label = ds.samples[idx]

    if int(label) != int(raw_label):
        raise RuntimeError("ImageFolder label inconsistency")

    # ------------------------------------------------------------
    # input.bin
    # ------------------------------------------------------------
    input_codes = make_input_codes(image)

    input_path = out / "input.bin"

    # The C-sim file contract is NOT the AXI wire order.  block0.cpp reads
    # input_data as semantic [token][channel] and performs packetization:
    #
    #   pkt.data[tp] = input_data[(2*tt + tp) * 768 + channel]
    #
    # Thus input.bin must remain ordinary [196,768] row-major.  Writing an
    # already packetized [tt,channel,tp] file here causes the testbench to
    # transpose it a second time before Adapter<...,1,24> sees the values.
    (
        input_codes.numpy()
        .astype("<i4")
        .tofile(input_path)
    )

    expected_input_bytes = T * PATCH_DIM * 4

    if input_path.stat().st_size != expected_input_bytes:
        raise RuntimeError(
            f"input.bin bytes={input_path.stat().st_size}, "
            f"expected={expected_input_bytes}"
        )

    # ------------------------------------------------------------
    # Exact encoder CLS -> exact safe Head logits.
    # ------------------------------------------------------------
    cls_q = run_exact_encoder_and_capture_cls(
        model,
        backbone,
        image,
        device,
        final_scale,
    )

    ln_fit = load_selected_ln(
        args.stage4o_dir
    )

    qln = apply_head_ln(
        cls_q.unsqueeze(0),
        {
            **ln_fit,
            "lnw": ln_fit["lnw"],
            "lnb": ln_fit["lnb"],
            "rsqrt_table": ln_fit["rsqrt_table"],
        },
    )

    o2 = Path(args.stage4o2_dir)

    qw = torch.from_numpy(
        np.load(
            o2 / "head_weight_38.npy"
        ).astype(np.int64)
    )

    qb = torch.from_numpy(
        np.load(
            o2 / "head_bias_38.npy"
        ).astype(np.int64)
    )

    active_logits, wrap = exact_head_logits(
        qln,
        qw,
        qb,
    )

    if bool(wrap.any()):
        raise RuntimeError(
            "Selected C-sim fixture caused an unexpected Head int19 wrap"
        )

    active_logits = active_logits[0].cpu()

    logits1000 = torch.full(
        (1000,),
        INT19_MIN,
        dtype=torch.int64,
    )

    logits1000[:38] = active_logits

    output_path = out / "output.bin"

    (
        logits1000.numpy()
        .astype("<i4")
        .tofile(output_path)
    )

    if output_path.stat().st_size != 1000 * 4:
        raise RuntimeError("output.bin must be exactly 4000 bytes")

    pred = int(
        torch.argmax(
            active_logits
        ).item()
    )

    manifest = {
        "dataset_split": args.split,
        "image_index": idx,
        "image_path": image_path,
        "true_class_id": int(label),
        "true_class_name": ds.classes[int(label)],
        "reference_predicted_class_id": pred,
        "reference_predicted_class_name": ds.classes[pred],
        "reference_correct": bool(pred == int(label)),

        "input_rule": "q=round(normalized_image*64), signed int16 values stored as int32",
        "patch_order": "torch.nn.functional.unfold kernel=16 stride=16; semantic tensor [196,768]",
        "input_bin_order": "semantic [token, channel] row-major; block0.cpp packetizes it",
        "csim_stream_order": "[tt, channel, tp] with TP=2 after testbench packetization",
        "input_shape": [196, 768],
        "input_code_min": int(input_codes.min()),
        "input_code_max": int(input_codes.max()),

        "final_encoder_int13_scale": float(final_scale),
        "cls_code_min": int(cls_q.min()),
        "cls_code_max": int(cls_q.max()),

        "active_logit_min": int(active_logits.min()),
        "active_logit_max": int(active_logits.max()),
        "inactive_logit_value": INT19_MIN,

        "input_bin": {
            "path": str(input_path),
            "bytes": input_path.stat().st_size,
            "sha256": sha256_file(input_path),
        },
        "output_bin": {
            "path": str(output_path),
            "bytes": output_path.stat().st_size,
            "sha256": sha256_file(output_path),
        },
    }

    manifest_path = out / "fixture.json"

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("===== STAGE 4Q: C-SIM FIXTURE =====")
    print("Image :", image_path)
    print(
        f"Label : {label} ({ds.classes[int(label)]})"
    )
    print(
        f"Ref pred: {pred} ({ds.classes[pred]}) "
        f"{'CORRECT' if pred == int(label) else 'WRONG'}"
    )
    print(
        f"Input codes : [{int(input_codes.min())}, "
        f"{int(input_codes.max())}]"
    )
    print(
        f"CLS int13   : [{int(cls_q.min())}, "
        f"{int(cls_q.max())}]"
    )
    print(
        f"Active logits: [{int(active_logits.min())}, "
        f"{int(active_logits.max())}]"
    )
    print(
        f"input.bin   : {input_path} "
        f"({input_path.stat().st_size} bytes)"
    )
    print(
        "input.bin order: semantic [token, channel]; "
        "C-sim testbench emits [tt, channel, tp]"
    )
    print(
        f"output.bin  : {output_path} "
        f"({output_path.stat().st_size} bytes)"
    )
    print("manifest    :", manifest_path)

    if args.install_dir:
        dst = Path(args.install_dir)
        dst.mkdir(parents=True, exist_ok=True)

        for src in (input_path, output_path):
            target = dst / src.name

            if target.exists():
                backup = target.with_name(
                    target.name + ".pre_stage4q.bak"
                )
                if not backup.exists():
                    shutil.copy2(
                        target,
                        backup,
                    )
                    print("Backup:", backup)

            shutil.copy2(
                src,
                target,
            )

            print("Installed:", target)

    for h in exact_handles:
        h.remove()

    attn_ctrl.remove()
    mlp_ctrl.remove()


if __name__ == "__main__":
    main()
