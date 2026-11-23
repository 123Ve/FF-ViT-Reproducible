#!/usr/bin/env python3
"""
Stage 4N: audit the exact HLS Classification-Head arithmetic contract
against the Stage-4M exact encoder output.

This stage does NOT quantize the new active-class Head yet. It first checks
whether the existing Head integer types are numerically compatible with
the transferred manifest dataset model.

Active HLS Head source contract:
  input / CLS feature        : ap_int<13>
  LN sum accumulator         : ap_uint<15>
  LN divide temporary        : ap_uint<30>
  LN mean                    : ap_uint<7>
  LN variance accumulator    : ap_uint<24>
  LN rsqrt cursor            : ap_uint<6>
  LN rsqrt output            : ap_uint<11>
  LN affine                  : ap_int<36>
  LN final shift             : ap_int<9>
  LN output                  : ap_int<8>
  Head weight                : ap_int<8>
  Head bias / accumulator    : ap_int<19>

The exact Stage-4M encoder is reconstructed, then the final CLS int13 codes
are collected. The script audits the unusual unsigned Head mean/variance
path before any new ROM parameters are generated.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from torchvision import datasets

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from stage4j_attention_activation_qat import AttentionActivationController
from stage4h_exact_layernorm_roundfix import wrap_signed
from stage4k_exact_attention_outer import install_exact_ln1
from stage4l_exact_softmax_aq import (
    exact_qkv_params,
    install_exact_qkv_and_cache,
)
from stage4m_exact_encoder_backbone import (
    install_exact_softmax_aq,
    prepare_exact_o,
    install_exact_o_and_cache,
    install_attention_input_cache,
    install_exact_attention_residual,
    install_exact_ln2,
    prepare_exact_mlp,
    install_exact_mlp_mats,
    install_mlp_residual_cache,
    install_exact_mlp_residual,
)
from stage4h_exact_layernorm_roundfix import install_exact_gelu
from qat_weight3_hls196 import eval_transform


C = 192


def u_wrap(x, bits):
    return torch.remainder(
        x,
        1 << bits,
    )


def load_scalar_pairs(path, width):
    arr = np.load(path)
    if arr.shape[1] < width:
        raise RuntimeError(
            f"{path} shape {arr.shape} has fewer than {width} columns"
        )
    return arr


def install_stage4m_exact_encoder(
    backbone,
    mlp_ctrl,
    attn_ctrl,
    device,
    stage4f_dir,
    stage4k_dir,
    stage4k2_dir,
    stage4l_dir,
    stage4m_dir,
    patch_scale,
):
    handles = []

    kdir = Path(stage4k_dir)
    mdir = Path(stage4m_dir)

    # Exact LN1.
    ln1_input_scales = np.load(
        kdir / "ln1_input_scales.npy"
    )
    ln1_scalars = np.load(
        kdir / "ln1_scalars.npy"
    )
    ln1_lnw = np.load(
        kdir / "ln1_lnw.npy"
    )
    ln1_lnb = np.load(
        kdir / "ln1_lnb.npy"
    )
    ln1_rsqrt = np.load(
        kdir / "ln1_rsqrt_table.npy"
    )

    handles += install_exact_ln1(
        backbone,
        attn_ctrl,
        ln1_input_scales,
        ln1_scalars,
        ln1_lnw,
        ln1_lnb,
        ln1_rsqrt,
        device,
    )

    # Exact Q/K/V and cache.
    qkv_meta = exact_qkv_params(
        backbone,
        attn_ctrl,
    )

    qkv_handles, qkv_cache, _ = install_exact_qkv_and_cache(
        backbone,
        qkv_meta,
        stage4k2_dir,
        device,
        collect=False,
    )
    handles += qkv_handles

    # Exact fixed Softmax + AQ.
    handles += install_exact_softmax_aq(
        backbone,
        attn_ctrl,
        qkv_cache,
        stage4l_dir,
    )

    # Exact O projection.
    o_params = prepare_exact_o(
        backbone,
        attn_ctrl,
        device,
    )
    o_handles, o_cache = install_exact_o_and_cache(
        backbone,
        o_params,
    )
    handles += o_handles

    # Block-input int13 real scales.
    mlp_scales = mlp_ctrl.export_scales()

    block_input_scales = np.zeros(
        12,
        dtype=np.float64,
    )
    block_input_scales[0] = float(
        patch_scale
    )

    for b in range(1, 12):
        block_input_scales[b] = float(
            mlp_scales[str(b - 1)]["m2_int13_scale"]
        )

    # Stage4M Attention output scales are the exact O accumulator scales.
    attn_out_scales = np.load(
        mdir / "ln2_input_scales.npy"
    )

    # Exact Attention residual.
    attn_scalars = np.load(
        mdir / "attn_scalars.npy"
    )

    attn_residual_params = []
    for b in range(12):
        rs = int(attn_scalars[b, 1])
        attn_residual_params.append({
            "RM": int(attn_scalars[b, 0]),
            "RS": rs,
            "RB": (1 << (rs - 1)) if rs > 0 else 0,
        })

    h, attn_resi_cache = install_attention_input_cache(
        backbone
    )
    handles += h

    handles += install_exact_attention_residual(
        backbone,
        attn_resi_cache,
        o_cache,
        block_input_scales,
        attn_out_scales,
        attn_residual_params,
    )

    # Exact Stage4M LN2.
    ln2_scalars = np.load(
        mdir / "ln2_scalars.npy"
    )
    ln2_lnw = np.load(
        mdir / "ln2_lnw.npy"
    )
    ln2_lnb = np.load(
        mdir / "ln2_lnb.npy"
    )
    ln2_rsqrt = np.load(
        mdir / "ln2_rsqrt_table.npy"
    )

    handles += install_exact_ln2(
        backbone,
        mlp_ctrl,
        attn_out_scales,
        ln2_scalars,
        ln2_lnw,
        ln2_lnb,
        ln2_rsqrt,
        device,
    )

    # Exact MLP1/GELU/MLP2.
    handles += install_exact_gelu(
        backbone,
        mlp_ctrl,
        stage4f_dir,
        device,
    )

    mlp_params = prepare_exact_mlp(
        backbone,
        mlp_ctrl,
        device,
    )

    h, m2_cache = install_exact_mlp_mats(
        backbone,
        mlp_params,
    )
    handles += h

    # Exact MLP residual.
    mlp_scalars_arr = np.load(
        mdir / "mlp_scalars.npy"
    )

    mlp_residual_params = []
    for b in range(12):
        rs = int(mlp_scalars_arr[b, 1])
        mlp_residual_params.append({
            "RM": int(mlp_scalars_arr[b, 0]),
            "RS": rs,
            "RB": (1 << (rs - 1)) if rs > 0 else 0,
        })

    h, mlp_resi_cache = install_mlp_residual_cache(
        backbone
    )
    handles += h

    handles += install_exact_mlp_residual(
        backbone,
        mlp_resi_cache,
        m2_cache,
        attn_out_scales,
        mlp_params,
        mlp_residual_params,
    )

    final_scale = float(
        mlp_params[11]["sm2"]
    )

    return handles, final_scale


@torch.inference_mode()
def evaluate_and_collect(
    model,
    backbone,
    loader,
    device,
    final_scale,
):
    cls_codes = []
    labels_all = []

    correct = 0
    total = 0

    cache = {"x": None}

    def block_hook(
        module,
        inputs,
        output,
    ):
        cache["x"] = output

    h = backbone.vit.blocks[11].register_forward_hook(
        block_hook
    )

    model.eval()

    for images, labels in loader:
        images = images.to(
            device,
            non_blocking=True,
        )
        labels_dev = labels.to(
            device,
            non_blocking=True,
        )

        logits = model(images)

        correct += int(
            (logits.argmax(1) == labels_dev)
            .sum()
            .item()
        )
        total += int(labels.numel())

        x = cache["x"]
        if x is None:
            raise RuntimeError(
                "Final block output cache missing"
            )

        cls = x[:, 0, :]

        q = torch.round(
            cls / float(final_scale)
        ).to(torch.int64)

        q = wrap_signed(
            q,
            13,
        )

        cls_codes.append(
            q.cpu()
        )
        labels_all.append(
            labels.cpu()
        )

    h.remove()

    return (
        100.0 * correct / total,
        torch.cat(cls_codes, dim=0),
        torch.cat(labels_all, dim=0),
    )


def audit_head_unsigned_path(qx):
    # qx: [N,192], signed int13 codes.

    signed_sum = qx.sum(
        dim=1
    )

    # HLS: ap_uint<15> acc += signed ap_int<13>
    # Modular addition is equivalent to wrapping the final sum mod 2^15.
    acc_u15 = u_wrap(
        signed_sum,
        15,
    )

    acc_wrap = (
        signed_sum != acc_u15
    )

    true_mean_round = torch.round(
        signed_sum.to(torch.float64)
        / float(C)
    ).to(torch.int64)

    mean_negative = (
        true_mean_round < 0
    )

    mean_outside_u7 = (
        (true_mean_round < 0)
        | (true_mean_round > 127)
    )

    # Canonical reciprocal used successfully in the backbone LN fit:
    # 683 / 2^17 ≈ 1/192.
    c1m = 683
    c1s = 17

    tmp_u30 = u_wrap(
        acc_u15 * c1m
        + (1 << (c1s - 1)),
        30,
    )

    mean_u7 = u_wrap(
        torch.bitwise_right_shift(
            tmp_u30,
            c1s,
        ),
        7,
    )

    mean_err = (
        mean_u7
        - true_mean_round
    )

    # HLS diff is assigned to ap_int<13>.
    diff_pre = (
        qx
        - mean_u7[:, None]
    )

    diff_wrap = (
        (diff_pre < -4096)
        | (diff_pre > 4095)
    )

    diff13 = wrap_signed(
        diff_pre,
        13,
    )

    diff_sq = (
        diff13 * diff13
    )

    var_raw = diff_sq.sum(
        dim=1
    )

    # HLS sum is ap_uint<24> and wraps after each add; final mod is equivalent.
    var_u24 = u_wrap(
        var_raw,
        24,
    )

    var_wrap = (
        var_raw != var_u24
    )

    return {
        "cls_code_min": int(qx.min()),
        "cls_code_max": int(qx.max()),

        "signed_sum_min": int(signed_sum.min()),
        "signed_sum_max": int(signed_sum.max()),

        "acc_u15_min": int(acc_u15.min()),
        "acc_u15_max": int(acc_u15.max()),

        "acc_u15_wrap_count": int(acc_wrap.sum()),
        "acc_u15_wrap_rate": float(
            acc_wrap.to(torch.float32).mean()
        ),

        "true_rounded_mean_min": int(
            true_mean_round.min()
        ),
        "true_rounded_mean_max": int(
            true_mean_round.max()
        ),

        "negative_true_mean_count": int(
            mean_negative.sum()
        ),
        "negative_true_mean_rate": float(
            mean_negative.to(torch.float32).mean()
        ),

        "true_mean_outside_uint7_count": int(
            mean_outside_u7.sum()
        ),
        "true_mean_outside_uint7_rate": float(
            mean_outside_u7.to(torch.float32).mean()
        ),

        "canonical_C_1_m": c1m,
        "canonical_C_1_s": c1s,

        "head_mean_u7_min": int(
            mean_u7.min()
        ),
        "head_mean_u7_max": int(
            mean_u7.max()
        ),

        "head_mean_error_min": int(
            mean_err.min()
        ),
        "head_mean_error_max": int(
            mean_err.max()
        ),

        "head_mean_exact_match_rate": float(
            (mean_err == 0)
            .to(torch.float32)
            .mean()
        ),

        "diff_pre_min": int(
            diff_pre.min()
        ),
        "diff_pre_max": int(
            diff_pre.max()
        ),

        "diff_int13_overflow_count": int(
            diff_wrap.sum()
        ),
        "diff_int13_overflow_rate": float(
            diff_wrap.to(torch.float32).mean()
        ),

        "var_raw_min": int(
            var_raw.min()
        ),
        "var_raw_max": int(
            var_raw.max()
        ),

        "var_u24_min": int(
            var_u24.min()
        ),
        "var_u24_max": int(
            var_u24.max()
        ),

        "var_u24_wrap_count": int(
            var_wrap.sum()
        ),
        "var_u24_wrap_rate": float(
            var_wrap.to(torch.float32).mean()
        ),
    }


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--source-checkpoint", required=True)
    ap.add_argument("--qat-checkpoint", required=True)
    ap.add_argument("--stage3-dir", required=True)
    ap.add_argument("--ranges", required=True)
    ap.add_argument("--attention-qat-checkpoint", required=True)

    ap.add_argument("--stage4f-dir", required=True)
    ap.add_argument("--stage4k-dir", required=True)
    ap.add_argument("--stage4k2-dir", required=True)
    ap.add_argument("--stage4l-dir", required=True)
    ap.add_argument("--stage4m-dir", required=True)

    ap.add_argument("--data-root", required=True)
    ap.add_argument("--patch-scale", type=float, required=True)

    ap.add_argument(
        "--output",
        default="stage4n_head_audit",
    )

    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)

    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    with open(
        args.ranges,
        "r",
        encoding="utf-8",
    ) as f:
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

    classes = list(source["classes"])

    val_ds = __import__('manifest_adapter').image_folder(
        Path(args.data_root) / "val",
        transform=eval_transform(),
    )

    if list(val_ds.classes) != classes:
        raise RuntimeError(
            "Validation class ordering mismatch"
        )

    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(device.type == "cuda"),
    )

    val_top1, cls_codes, labels = evaluate_and_collect(
        model,
        backbone,
        val_loader,
        device,
        final_scale,
    )

    audit = audit_head_unsigned_path(
        cls_codes
    )

    report = {
        "scope": (
            "Audit only. Exact Stage4M encoder + floating-point current "
            "active-class final norm/head; no new integer Head parameters yet."
        ),
        "exact_encoder_plus_float_head_val_top1": val_top1,
        "final_encoder_int13_scale": final_scale,
        "num_validation_images": int(
            cls_codes.shape[0]
        ),
        "head_source_types": {
            "input": "ap_int<13>",
            "ln_sum": "ap_uint<15>",
            "ln_divc": "ap_uint<30>",
            "ln_mean": "ap_uint<7>",
            "ln_var": "ap_uint<24>",
            "ln_cursor": "ap_uint<6>",
            "ln_rsqrt": "ap_uint<11>",
            "ln_affine": "ap_int<36>",
            "ln_shift": "ap_int<9>",
            "ln_output": "ap_int<8>",
            "weight": "ap_int<8>",
            "bias_accumulator": "ap_int<19>",
        },
        "audit": audit,
    }

    with open(
        out / "report.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            report,
            f,
            indent=2,
        )

    np.save(
        out / "cls_int13_codes.npy",
        cls_codes.numpy().astype(np.int16),
    )

    np.save(
        out / "labels.npy",
        labels.numpy().astype(np.int64),
    )

    print()
    print("===== STAGE 4N: HEAD INTEGER CONTRACT AUDIT =====")
    print(
        f"Exact encoder + float Head val : "
        f"{val_top1:.4f}%"
    )
    print(
        f"Final encoder int13 scale      : "
        f"{final_scale:.12g}"
    )
    print(
        f"CLS int13 range                : "
        f"[{audit['cls_code_min']}, {audit['cls_code_max']}]"
    )
    print(
        f"Signed sum range               : "
        f"[{audit['signed_sum_min']}, {audit['signed_sum_max']}]"
    )
    print(
        f"Head ap_uint<15> sum wrap      : "
        f"{100*audit['acc_u15_wrap_rate']:.4f}%"
    )
    print(
        f"True mean range                : "
        f"[{audit['true_rounded_mean_min']}, "
        f"{audit['true_rounded_mean_max']}]"
    )
    print(
        f"True mean outside uint7        : "
        f"{100*audit['true_mean_outside_uint7_rate']:.4f}%"
    )
    print(
        f"Canonical mean exact match     : "
        f"{100*audit['head_mean_exact_match_rate']:.4f}%"
    )
    print(
        f"Diff int13 overflow            : "
        f"{100*audit['diff_int13_overflow_rate']:.6f}%"
    )
    print(
        f"Variance ap_uint<24> wrap      : "
        f"{100*audit['var_u24_wrap_rate']:.4f}%"
    )
    print("Report:", out / "report.json")

    for h in exact_handles:
        h.remove()

    attn_ctrl.remove()
    mlp_ctrl.remove()


if __name__ == "__main__":
    main()
