#!/usr/bin/env python3
"""
Stage 4O2: zero-wrap / safety-margin refit of the W8 Head classifier.

Reuses the selected signed-fix Head LayerNorm from Stage 4O and changes only
the classifier weight/bias scale. The goal is to keep ap_int<19> unchanged
while creating a numerical safety margin, instead of widening the Head MAC.

Selection uses TRAIN-ONLY calibration data:
  * zero ap_int<19> accumulator wrap on calibration
  * maximum absolute active accumulator <= --safe-abs-limit
  * among safe candidates, minimum centered logit MSE to the float Head

Validation is reported only after the candidate is frozen.

The default safe limit 250000 leaves about 4.6% headroom below the positive
ap_int<19> limit 262143 and above the negative limit -262144.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from stage4j_attention_activation_qat import AttentionActivationController
from stage4l_exact_softmax_aq import ManifestDataset
from stage4n_head_integer_audit import install_stage4m_exact_encoder
from stage4o_exact_head_signedfix import (
    apply_head_ln,
    exact_head_logits,
)
from qat_weight3_hls196 import eval_transform


C = 192
NCLASS = 38
HLS_CO = 1000
INT19_MIN = -(1 << 18)
INT19_MAX = (1 << 18) - 1


def spread_subset(ds, n):
    n = min(int(n), len(ds))
    if n == len(ds):
        return ds

    idx = np.linspace(
        0,
        len(ds) - 1,
        num=n,
        dtype=np.int64,
    )
    return Subset(ds, idx.tolist())


@torch.inference_mode()
def collect_cls_codes(
    model,
    backbone,
    loader,
    device,
    final_scale,
):
    out = []
    labels_all = []
    cache = {"x": None}

    def hook(module, inputs, output):
        cache["x"] = output

    h = backbone.vit.blocks[11].register_forward_hook(hook)

    model.eval()

    for step, (images, labels) in enumerate(loader, 1):
        images = images.to(device, non_blocking=True)
        _ = model(images)

        cls = cache["x"][:, 0, :]

        q = torch.round(
            cls / float(final_scale)
        ).to(torch.int64)

        mod = 1 << 13
        half = 1 << 12
        q = torch.remainder(q + half, mod) - half

        out.append(q.cpu())
        labels_all.append(labels.cpu())

        if step % 10 == 0 or step == len(loader):
            print(
                f"Collect calibration CLS {step}/{len(loader)}",
                flush=True,
            )

    h.remove()

    return (
        torch.cat(out, dim=0),
        torch.cat(labels_all, dim=0),
    )


def load_selected_ln(stage4o_dir):
    d = Path(stage4o_dir)

    report = json.load(
        open(d / "report.json", "r", encoding="utf-8")
    )

    selected = report["selected"]

    return {
        "cursor_bits": int(
            selected["cursor_bits"]
        ),
        "output_scale": float(
            selected["head_ln_output_scale"]
        ),
        "scalars": np.load(
            d / "head_ln_scalars.npy"
        ).astype(np.int32),
        "lnw": torch.from_numpy(
            np.load(
                d / "head_lnw.npy"
            ).astype(np.int64)
        ),
        "lnb": torch.from_numpy(
            np.load(
                d / "head_lnb.npy"
            ).astype(np.int64)
        ),
        "rsqrt_table": torch.from_numpy(
            np.load(
                d / "head_rsqrt.npy"
            ).astype(np.int64)
        ),
    }


def fit_safe_classifier(
    qln_cal,
    float_ln_cal,
    head_module,
    ln_scale,
    old_weight_scale,
    safe_abs_limit,
):
    w = head_module.weight.detach().cpu().to(torch.float64)
    b = head_module.bias.detach().cpu().to(torch.float64)

    float_logits = (
        float_ln_cal.to(torch.float64)
        @ w.t()
        + b
    )

    best = None
    safe_candidates = []

    # Search both slightly below and substantially above the Stage4O scale.
    multipliers = np.concatenate([
        np.linspace(0.95, 1.05, 21),
        np.linspace(1.06, 1.40, 35),
        np.linspace(1.42, 1.80, 20),
    ])

    for mul in multipliers:
        sw = float(
            old_weight_scale * float(mul)
        )

        qw = torch.round(
            w / sw
        ).to(torch.int64)

        qw = torch.clamp(
            qw,
            -128,
            127,
        )

        slogit = float(
            ln_scale * sw
        )

        qb = torch.round(
            b / slogit
        ).to(torch.int64)

        if bool(
            ((qb < INT19_MIN) | (qb > INT19_MAX)).any()
        ):
            continue

        logits_int, any_wrap = exact_head_logits(
            qln_cal,
            qw,
            qb,
        )

        wrap_rate = float(
            any_wrap.to(torch.float32).mean()
        )

        max_abs = int(
            torch.max(
                torch.abs(logits_int)
            )
        )

        real_logits = (
            logits_int.to(torch.float64)
            * slogit
        )

        fl = float_logits - float_logits.mean(
            dim=1,
            keepdim=True,
        )
        rl = real_logits - real_logits.mean(
            dim=1,
            keepdim=True,
        )

        mse = float(
            torch.mean(
                (rl - fl) ** 2
            )
        )

        cand = {
            "multiplier_vs_stage4o": float(mul),
            "weight_scale": sw,
            "logit_scale": slogit,
            "qw": qw,
            "qb": qb,
            "calibration_wrap_rate": wrap_rate,
            "calibration_max_abs_acc": max_abs,
            "centered_logit_mse": mse,
        }

        if (
            wrap_rate == 0.0
            and max_abs <= int(safe_abs_limit)
        ):
            safe_candidates.append(cand)

            key = (
                mse,
                max_abs,
                abs(float(mul) - 1.0),
            )

            if best is None:
                best = cand
            else:
                bkey = (
                    best["centered_logit_mse"],
                    best["calibration_max_abs_acc"],
                    abs(best["multiplier_vs_stage4o"] - 1.0),
                )

                if key < bkey:
                    best = cand

    if best is None:
        raise RuntimeError(
            "No zero-wrap classifier candidate met the requested "
            f"safe_abs_limit={safe_abs_limit}. "
            "Increase --safe-abs-limit slightly or extend the scale search."
        )

    return best, safe_candidates


def evaluate_classifier(
    qval,
    yval,
    ln_fit,
    cls_fit,
):
    qln = apply_head_ln(
        qval,
        {
            **ln_fit,
            "lnw": ln_fit["lnw"],
            "lnb": ln_fit["lnb"],
            "rsqrt_table": ln_fit["rsqrt_table"],
        },
    )

    logits_int, any_wrap = exact_head_logits(
        qln,
        cls_fit["qw"],
        cls_fit["qb"],
    )

    pred = logits_int.argmax(dim=1)

    top1 = (
        100.0
        * float(
            (pred == yval)
            .to(torch.float32)
            .mean()
        )
    )

    return {
        "top1": top1,
        "wrap_rate": float(
            any_wrap.to(torch.float32).mean()
        ),
        "max_abs_acc": int(
            torch.max(
                torch.abs(logits_int)
            )
        ),
        "min_acc": int(
            logits_int.min()
        ),
        "max_acc": int(
            logits_int.max()
        ),
    }


def write_header(
    path,
    ln_fit,
    cls_fit,
):
    w1000 = np.zeros(
        (HLS_CO, C),
        dtype=np.int8,
    )

    b1000 = np.full(
        HLS_CO,
        INT19_MIN,
        dtype=np.int32,
    )

    w1000[:NCLASS] = (
        cls_fit["qw"].numpy().astype(np.int8)
    )

    b1000[:NCLASS] = (
        cls_fit["qb"].numpy().astype(np.int32)
    )

    sc = ln_fit["scalars"]
    lnw = ln_fit["lnw"].numpy().astype(np.int32)
    lnb = ln_fit["lnb"].numpy().astype(np.int64)
    rs = ln_fit["rsqrt_table"].numpy().astype(np.int32)

    lines = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("// Stage4O2 zero-wrap PlantVillage Head ROM.")
    lines.append("// Requires signed Head sum/divc/mean typedef fix.")
    lines.append("")

    lines.append(
        "const int HEAD_LN_SCALARS[8] = {"
        + ", ".join(str(int(v)) for v in sc)
        + "};"
    )
    lines.append("")

    lines.append("const int HEAD_LNW[192] = {")
    for i in range(0, C, 16):
        lines.append(
            "    "
            + ", ".join(str(int(v)) for v in lnw[i:i+16])
            + ","
        )
    lines.append("};")
    lines.append("")

    lines.append("const long long HEAD_LNB[192] = {")
    for i in range(0, C, 8):
        lines.append(
            "    "
            + ", ".join(f"{int(v)}LL" for v in lnb[i:i+8])
            + ","
        )
    lines.append("};")
    lines.append("")

    lines.append("const int HEAD_RSQRT[128] = {")
    for i in range(0, 128, 16):
        lines.append(
            "    "
            + ", ".join(str(int(v)) for v in rs[i:i+16])
            + ","
        )
    lines.append("};")
    lines.append("")

    lines.append(
        "const ap_int<8> HEAD_WEIGHT[1000][192] = {"
    )
    for row in w1000:
        lines.append(
            "    {"
            + ", ".join(str(int(v)) for v in row)
            + "},"
        )
    lines.append("};")
    lines.append("")

    lines.append(
        "const ap_int<19> HEAD_BIAS[1000] = {"
    )
    for i in range(0, HLS_CO, 16):
        lines.append(
            "    "
            + ", ".join(str(int(v)) for v in b1000[i:i+16])
            + ","
        )
    lines.append("};")
    lines.append("")

    Path(path).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


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
    ap.add_argument("--stage4n-dir", required=True)
    ap.add_argument("--stage4o-dir", required=True)

    ap.add_argument("--manifest", required=True)
    ap.add_argument("--patch-scale", type=float, required=True)

    ap.add_argument(
        "--output",
        default="stage4o2_head_safe",
    )

    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fit-images", type=int, default=1216)
    ap.add_argument("--safe-abs-limit", type=int, default=250000)

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
        .detach().cpu().numpy()
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

    calib_base = ManifestDataset(
        args.manifest,
        eval_transform(),
    )

    if list(calib_base.classes) != classes:
        raise RuntimeError("Calibration class ordering mismatch")

    calib_ds = spread_subset(
        calib_base,
        args.fit_images,
    )

    calib_loader = DataLoader(
        calib_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(device.type == "cuda"),
    )

    qcal, _ = collect_cls_codes(
        model,
        backbone,
        calib_loader,
        device,
        final_scale,
    )

    n_dir = Path(args.stage4n_dir)

    qval = torch.from_numpy(
        np.load(
            n_dir / "cls_int13_codes.npy"
        ).astype(np.int64)
    )

    yval = torch.from_numpy(
        np.load(
            n_dir / "labels.npy"
        ).astype(np.int64)
    )

    ln_fit = load_selected_ln(
        args.stage4o_dir
    )

    norm_module = backbone.vit.norm.cpu().eval()
    head_module = backbone.vit.head.cpu().eval()

    qln_cal = apply_head_ln(
        qcal,
        {
            **ln_fit,
            "lnw": ln_fit["lnw"],
            "lnb": ln_fit["lnb"],
            "rsqrt_table": ln_fit["rsqrt_table"],
        },
    )

    with torch.inference_mode():
        float_ln_cal = norm_module(
            qcal.to(torch.float32)
            * float(final_scale)
        )

    old_report = json.load(
        open(
            Path(args.stage4o_dir) / "report.json",
            "r",
            encoding="utf-8",
        )
    )

    old_sw = float(
        old_report["selected"]["head_weight_scale"]
    )

    best, candidates = fit_safe_classifier(
        qln_cal,
        float_ln_cal,
        head_module,
        ln_fit["output_scale"],
        old_sw,
        args.safe_abs_limit,
    )

    val = evaluate_classifier(
        qval,
        yval,
        ln_fit,
        best,
    )

    write_header(
        out / "generated_head_rom_safe.h",
        ln_fit,
        best,
    )

    np.save(
        out / "head_weight_38.npy",
        best["qw"].numpy().astype(np.int8),
    )

    np.save(
        out / "head_bias_38.npy",
        best["qb"].numpy().astype(np.int32),
    )

    report = {
        "scope": (
            "Stage4O selected signed-fix Head LN; classifier-only refit "
            "to preserve ap_int<19> while enforcing zero-wrap calibration "
            "and numerical headroom."
        ),
        "fit_images": len(calib_ds),
        "safe_abs_limit": int(args.safe_abs_limit),
        "stage4o_weight_scale": old_sw,
        "selected_multiplier_vs_stage4o": float(
            best["multiplier_vs_stage4o"]
        ),
        "selected_weight_scale": float(
            best["weight_scale"]
        ),
        "selected_logit_scale": float(
            best["logit_scale"]
        ),
        "calibration_wrap_rate": float(
            best["calibration_wrap_rate"]
        ),
        "calibration_max_abs_acc": int(
            best["calibration_max_abs_acc"]
        ),
        "validation_top1": float(
            val["top1"]
        ),
        "validation_wrap_rate": float(
            val["wrap_rate"]
        ),
        "validation_max_abs_acc": int(
            val["max_abs_acc"]
        ),
        "validation_logit_range": [
            int(val["min_acc"]),
            int(val["max_acc"]),
        ],
        "num_safe_candidates": len(candidates),
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

    print()
    print("===== STAGE 4O2: SAFE INT19 HEAD =====")
    print(
        f"Stage4O weight scale          : {old_sw:.12g}"
    )
    print(
        f"Selected scale multiplier     : "
        f"{best['multiplier_vs_stage4o']:.6f}"
    )
    print(
        f"Calibration max |acc|         : "
        f"{best['calibration_max_abs_acc']}"
    )
    print(
        f"Calibration accumulator wrap  : "
        f"{100*best['calibration_wrap_rate']:.6f}%"
    )
    print(
        f"Validation Top-1              : "
        f"{val['top1']:.4f}%"
    )
    print(
        f"Validation accumulator wrap   : "
        f"{100*val['wrap_rate']:.6f}%"
    )
    print(
        f"Validation max |acc|          : "
        f"{val['max_abs_acc']}"
    )
    print(
        f"Validation active logit range : "
        f"[{val['min_acc']}, {val['max_acc']}]"
    )
    print(
        "ROM:", out / "generated_head_rom_safe.h"
    )
    print(
        "Report:", out / "report.json"
    )

    for h in exact_handles:
        h.remove()

    attn_ctrl.remove()
    mlp_ctrl.remove()


if __name__ == "__main__":
    main()
