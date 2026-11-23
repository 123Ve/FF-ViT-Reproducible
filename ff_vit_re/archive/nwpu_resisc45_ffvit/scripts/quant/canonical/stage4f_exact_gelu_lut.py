#!/usr/bin/env python3
"""
Stage 4F: generate and evaluate exact FF-ViT GELU LUTs.

HLS semantics reproduced:
    cursor = (x_int11 + b) >> s
    cursor = clamp(cursor, 0, bound)
    y_uint3 = table[cursor]

The LUT target is the trained Stage-4D GELU output code:
    q_target = clamp(round(GELU(x_int11 * S_m1) / S_ge), 0, 7)

The script:
  1) rebuilds the Stage-3 model and loads the Stage-4D MLP-QAT checkpoint;
  2) collects MLP1 integer-code histograms on a fixed train-only calibration manifest;
  3) searches integer b and shift s for each block;
  4) fits one 64-entry uint3 table per block;
  5) replaces the GELU fake-quant output with the exact HLS address/LUT rule;
  6) evaluates validation accuracy;
  7) exports ge_scalars[12][4], ge_table[12][64], JSON, NPY and a C header fragment.

This is exact for the GELU address/LUT operator. LayerNorm is still the Stage-4D
hardware-aware surrogate until the next stage generates its rsqrt/affine integers.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from qat_weight3_hls196 import eval_transform


from manifest_adapter import CalibrationDataset as ManifestDataset


@torch.inference_mode()
def evaluate(model, loader, device):
    model.eval()
    correct = 0
    total = 0
    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        logits = model(images)
        correct += int((logits.argmax(1) == labels).sum().item())
        total += int(labels.numel())
    return 100.0 * correct / total


def integer_codes(x_real, scale, qmin, qmax):
    q = torch.round(x_real / float(scale))
    q = torch.clamp(q, qmin, qmax)
    return q.to(torch.int64)


def fit_one_lut(hist, s_m1, s_ge, b_search_radius=192, max_shift=8):
    """
    hist: length-2048 counts for signed int11 codes [-1024, 1023].
    """
    codes = np.arange(-1024, 1024, dtype=np.int64)
    counts = hist.astype(np.float64)

    mask = counts > 0
    x = codes[mask]
    w = counts[mask]

    if x.size == 0:
        raise RuntimeError("Empty MLP1 histogram")

    # Oracle target code corresponding to trained Stage4D GELU quantizer.
    xr = torch.from_numpy(x.astype(np.float32)) * float(s_m1)
    yr = F.gelu(xr)
    qt = torch.round(yr / float(s_ge)).clamp(0, 7).to(torch.int64).numpy()

    xmin = int(x.min())
    xmax = int(x.max())

    best = None

    for s in range(max_shift + 1):
        step = 1 << s

        # Center search around mapping the minimum observed code near address 0.
        b0 = -xmin

        lo = b0 - int(b_search_radius)
        hi = b0 + int(b_search_radius)

        for b in range(lo, hi + 1):
            # Python // for positive divisor matches arithmetic >> for signed ints.
            addr = (x + b) // step
            addr = np.clip(addr, 0, 63).astype(np.int64)

            table = np.zeros(64, dtype=np.int64)

            # Fit table entries by weighted least squares in output-code domain.
            for a in range(64):
                m = addr == a
                if not np.any(m):
                    continue
                num = np.sum(w[m] * qt[m])
                den = np.sum(w[m])
                table[a] = int(np.clip(np.rint(num / den), 0, 7))

            # Fill unused addresses by nearest used entry to avoid arbitrary holes.
            used = np.unique(addr)
            if used.size:
                for a in range(64):
                    if a not in used:
                        nearest = used[np.argmin(np.abs(used - a))]
                        table[a] = table[nearest]

            pred = table[addr]
            err = pred - qt
            mse = float(np.sum(w * (err ** 2)) / np.sum(w))
            mismatch = float(np.sum(w * (pred != qt)) / np.sum(w))
            maxerr = int(np.max(np.abs(err)))

            candidate = {
                "mse_code": mse,
                "mismatch_rate": mismatch,
                "max_abs_code_error": maxerr,
                "b": int(b),
                "s": int(s),
                "bound": 63,
                "x_min_observed": xmin,
                "x_max_observed": xmax,
                "table": table,
            }

            if best is None:
                best = candidate
            else:
                key = (
                    candidate["mse_code"],
                    candidate["mismatch_rate"],
                    candidate["s"],
                    abs(candidate["b"] - b0),
                )
                best_key = (
                    best["mse_code"],
                    best["mismatch_rate"],
                    best["s"],
                    abs(best["b"] - b0),
                )
                if key < best_key:
                    best = candidate

    return best


def write_header(path, scalars, tables):
    lines = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("// Generated by stage4f_exact_gelu_lut.py")
    lines.append("// HLS rule: clamp((x+b)>>s, 0, bound) -> table[address]")
    lines.append("")
    lines.append("static const int GE_SCALARS[12][4] = {")
    for row in scalars:
        lines.append(
            "    {" + ", ".join(str(int(v)) for v in row) + "},"
        )
    lines.append("};")
    lines.append("")
    lines.append("static const unsigned char GE_TABLE[12][64] = {")
    for row in tables:
        lines.append(
            "    {" + ", ".join(str(int(v)) for v in row) + "},"
        )
    lines.append("};")
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--source-checkpoint", required=True)
    ap.add_argument("--qat-checkpoint", required=True)
    ap.add_argument("--stage3-dir", required=True)
    ap.add_argument("--ranges", required=True)
    ap.add_argument("--mlp-qat-checkpoint", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--data-root", required=True)

    ap.add_argument(
        "--output",
        default="stage4f_exact_gelu",
    )

    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--b-search-radius", type=int, default=192)
    ap.add_argument("--max-shift", type=int, default=8)

    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    full_model, backbone, source = rebuild_stage3_model(
        args.source_checkpoint,
        args.qat_checkpoint,
        args.stage3_dir,
    )

    with open(args.ranges, "r", encoding="utf-8") as f:
        ranges = json.load(f)["statistics"]

    controller = MLPActivationController(backbone, ranges)

    ckpt = torch.load(
        args.mlp_qat_checkpoint,
        map_location="cpu",
        weights_only=True,
    )

    full_model.load_state_dict(
        ckpt["student_state"],
        strict=True,
    )

    controller.load_state_dict(
        ckpt["controller_state"],
        strict=True,
    )

    full_model = full_model.to(device)
    controller = controller.to(device)

    controller.set_active(range(12))
    controller.install()

    classes = list(source["classes"])

    calib_ds = ManifestDataset(
        args.manifest,
        eval_transform(),
    )

    if list(calib_ds.classes) != classes:
        raise RuntimeError("Calibration manifest class ordering mismatch")

    calib_loader = DataLoader(
        calib_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(device.type == "cuda"),
    )

    val_ds = __import__('manifest_adapter').image_folder(
        Path(args.data_root) / "val",
        transform=eval_transform(),
    )

    if list(val_ds.classes) != classes:
        raise RuntimeError("Validation class ordering mismatch")

    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(device.type == "cuda"),
    )

    scales = controller.export_scales()

    # ----------------------------------------------------------
    # Collect exact MLP1 int11-code histograms.
    # ----------------------------------------------------------
    hist = [
        np.zeros(2048, dtype=np.int64)
        for _ in range(12)
    ]

    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]
        s_m1 = float(scales[str(b)]["m1_int11_scale"])

        def pre_gelu_hook(module, inputs, b=b, s_m1=s_m1):
            x = inputs[0].detach()
            q = integer_codes(x, s_m1, -1024, 1023)
            q = q.reshape(-1).cpu().numpy()
            h = np.bincount(
                q + 1024,
                minlength=2048,
            )
            hist[b] += h.astype(np.int64)

        handles.append(
            block.mlp.act.register_forward_pre_hook(pre_gelu_hook)
        )

    full_model.eval()

    with torch.inference_mode():
        for step, (images, _) in enumerate(calib_loader, 1):
            images = images.to(device, non_blocking=True)
            _ = full_model(images)
            if step % 10 == 0 or step == len(calib_loader):
                print(
                    f"calibration {step}/{len(calib_loader)}",
                    flush=True,
                )

    for h in handles:
        h.remove()

    # ----------------------------------------------------------
    # Fit one HLS GELU table per block.
    # ----------------------------------------------------------
    ge_scalars = np.zeros((12, 4), dtype=np.int32)
    ge_tables = np.zeros((12, 64), dtype=np.uint8)
    fit_report = {}

    print()
    print("===== STAGE 4F: FIT EXACT HLS GELU LUT =====")

    for b in range(12):
        s_m1 = float(scales[str(b)]["m1_int11_scale"])
        s_ge = float(scales[str(b)]["gelu_uint3_scale"])

        fit = fit_one_lut(
            hist[b],
            s_m1,
            s_ge,
            b_search_radius=args.b_search_radius,
            max_shift=args.max_shift,
        )

        ge_scalars[b] = [
            fit["b"],
            fit["s"],
            fit["bound"],
            0,
        ]

        ge_tables[b] = fit["table"].astype(np.uint8)

        fit_report[str(b)] = {
            "m1_int11_scale": s_m1,
            "gelu_uint3_scale": s_ge,
            "b": fit["b"],
            "s": fit["s"],
            "bound": fit["bound"],
            "reserved": 0,
            "input_code_min": fit["x_min_observed"],
            "input_code_max": fit["x_max_observed"],
            "weighted_code_mse": fit["mse_code"],
            "weighted_code_mismatch_rate": fit["mismatch_rate"],
            "max_abs_code_error": fit["max_abs_code_error"],
            "table": ge_tables[b].astype(int).tolist(),
        }

        print(
            f"Block {b:2d}: "
            f"b={fit['b']:4d} "
            f"s={fit['s']} "
            f"x=[{fit['x_min_observed']},{fit['x_max_observed']}] "
            f"MSE={fit['mse_code']:.6f} "
            f"mismatch={100.0*fit['mismatch_rate']:.4f}% "
            f"maxerr={fit['max_abs_code_error']}"
        )

    np.save(
        out / "ge_scalars.npy",
        ge_scalars,
    )
    np.save(
        out / "ge_table.npy",
        ge_tables,
    )

    write_header(
        out / "generated_ge_lut.h",
        ge_scalars,
        ge_tables,
    )

    # ----------------------------------------------------------
    # Baseline Stage4D accuracy before replacing GELU fake-q.
    # ----------------------------------------------------------
    baseline_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ----------------------------------------------------------
    # Replace controller GELU output with exact HLS LUT rule.
    #
    # Controller GELU hook was registered first. This hook runs after it
    # and returns the HLS-LUT output, overriding the earlier hook output.
    # It uses inputs[0], i.e. the MLP1 fake-quant output.
    # ----------------------------------------------------------
    exact_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        s_m1 = float(scales[str(b)]["m1_int11_scale"])
        s_ge = float(scales[str(b)]["gelu_uint3_scale"])

        b_int = int(ge_scalars[b, 0])
        shift = int(ge_scalars[b, 1])
        bound = int(ge_scalars[b, 2])

        table = torch.tensor(
            ge_tables[b].astype(np.int64),
            dtype=torch.int64,
            device=device,
        )

        def exact_gelu_hook(
            module,
            inputs,
            output,
            s_m1=s_m1,
            s_ge=s_ge,
            b_int=b_int,
            shift=shift,
            bound=bound,
            table=table,
        ):
            x = inputs[0]

            x_int = torch.round(
                x / s_m1
            ).to(torch.int64)

            x_int = torch.clamp(
                x_int,
                -1024,
                1023,
            )

            # torch bitwise right shift on signed int64 is arithmetic.
            addr = torch.bitwise_right_shift(
                x_int + b_int,
                shift,
            )

            addr = torch.clamp(
                addr,
                0,
                bound,
            )

            y_int = table[addr]

            return (
                y_int.to(x.dtype)
                * s_ge
            )

        exact_handles.append(
            block.mlp.act.register_forward_hook(
                exact_gelu_hook
            )
        )

    exact_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    for h in exact_handles:
        h.remove()

    payload = {
        "calibration_manifest": args.manifest,
        "calibration_samples": len(calib_ds),
        "stage4d_surrogate_val_top1": baseline_val,
        "exact_hls_gelu_val_top1": exact_val,
        "gelu_lut_drop_pp": baseline_val - exact_val,
        "ge_scalars": ge_scalars.astype(int).tolist(),
        "ge_tables": ge_tables.astype(int).tolist(),
        "blocks": fit_report,
        "scope": (
            "Exact GELU address/LUT semantics only. "
            "LayerNorm still uses Stage4D hardware-aware fake quant."
        ),
    }

    with open(
        out / "report.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
            indent=2,
        )

    print()
    print("===== STAGE 4F: EXACT GELU EVAL =====")
    print(f"Stage4D surrogate val Top-1 : {baseline_val:.4f}%")
    print(f"Exact HLS GELU val Top-1    : {exact_val:.4f}%")
    print(f"GELU LUT drop               : {baseline_val-exact_val:.4f} pp")
    print("Report:", out / "report.json")
    print("Header:", out / "generated_ge_lut.h")

    controller.remove()


if __name__ == "__main__":
    main()
