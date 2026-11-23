#!/usr/bin/env python3
"""
Stage 4I: exact FF-ViT MLP path evaluation.

Adds to Stage 4H:
  * exact signed-int3 MLP1/MLP2 weights
  * integer biases in accumulator domains
  * signed int11 MLP1 accumulator
  * unsigned int3 exact GELU LUT from Stage 4F
  * signed int13 MLP2 accumulator
  * exact HLS residual rescaling:
        ((x_int15 * RM + RB) >> RS)
    followed by ap_int<13> cast/add/wrap

Attention is still not bit-accurate in this stage. Therefore this stage closes
the MLP branch only; the per-block int15 MLP-input scale remains the target
that the future exact Attention/residual path must produce.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from torchvision import datasets

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import (
    MLPActivationController,
    module_weight_scale,
)
from stage4h_exact_layernorm_roundfix import (
    install_exact_layernorm,
    install_exact_gelu,
    wrap_signed,
    arshift,
)
from qat_weight3_hls196 import eval_transform


def quant_weight_int3(module):
    sw = module_weight_scale(module).detach()
    q = torch.round(module.weight.detach() / sw)
    q = torch.clamp(q, -4, 3).to(torch.int64)
    return q, float(sw.cpu())


def quant_bias(module, acc_scale, bits):
    if module.bias is None:
        q = torch.zeros(
            module.weight.shape[0],
            dtype=torch.int64,
            device=module.weight.device,
        )
    else:
        q = torch.round(
            module.bias.detach() / float(acc_scale)
        ).to(torch.int64)
    return wrap_signed(q, bits)


def fit_residual_scalar(input_scale, output_scale, qmin, qmax, max_shift=20):
    """
    Fit HLS RM/RS for:
        round(q * input_scale / output_scale)
    using the actual HLS rule:
        (q*RM + 2^(RS-1)) >> RS
    """
    ratio = float(input_scale) / float(output_scale)

    q = torch.arange(
        int(qmin),
        int(qmax) + 1,
        dtype=torch.int64,
    )

    ideal = torch.round(
        q.to(torch.float64) * ratio
    ).to(torch.int64)

    best = None

    for rs in range(0, int(max_shift) + 1):
        rm = int(round(ratio * (1 << rs)))

        if rm < -(1 << 31) or rm > (1 << 31) - 1:
            continue

        rb = (1 << (rs - 1)) if rs > 0 else 0

        pred = arshift(
            q * rm + rb,
            rs,
        )

        err = pred - ideal

        mismatch = float(
            (err != 0).to(torch.float32).mean()
        )
        mse = float(
            torch.mean(
                err.to(torch.float64) ** 2
            )
        )
        maxerr = int(
            torch.max(torch.abs(err))
        )

        cand = {
            "RM": rm,
            "RS": rs,
            "RB": rb,
            "mismatch_rate": mismatch,
            "mse": mse,
            "max_abs_error": maxerr,
        }

        # Prefer exact/smaller error first; for ties use smaller shift/RM
        # to avoid unnecessarily large integer multipliers.
        key = (
            mismatch,
            mse,
            maxerr,
            rs,
            abs(rm),
        )

        if best is None:
            best = cand
        else:
            bkey = (
                best["mismatch_rate"],
                best["mse"],
                best["max_abs_error"],
                best["RS"],
                abs(best["RM"]),
            )
            if key < bkey:
                best = cand

    if best is None:
        raise RuntimeError("Unable to fit residual RM/RS")

    return best


@torch.inference_mode()
def evaluate(model, loader, device):
    model.eval()
    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        logits = model(images)

        correct += int(
            (logits.argmax(1) == labels).sum().item()
        )
        total += int(labels.numel())

    return 100.0 * correct / total


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--source-checkpoint", required=True)
    ap.add_argument("--qat-checkpoint", required=True)
    ap.add_argument("--stage3-dir", required=True)
    ap.add_argument("--ranges", required=True)
    ap.add_argument("--mlp-qat-checkpoint", required=True)
    ap.add_argument("--gelu-dir", required=True)
    ap.add_argument("--ln-dir", required=True)
    ap.add_argument("--data-root", required=True)

    ap.add_argument(
        "--output",
        default="stage4i_exact_mlp",
    )

    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-residual-shift", type=int, default=20)

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

    controller = MLPActivationController(
        backbone,
        ranges,
    )

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

    scales = controller.export_scales()

    # ------------------------------------------------------------
    # Load exact LayerNorm parameters from Stage 4H
    # ------------------------------------------------------------

    ln_dir = Path(args.ln_dir)

    input_scales = np.load(
        ln_dir / "ln_input_scales.npy"
    )

    ln_scalars = np.load(
        ln_dir / "ln_scalars.npy"
    )

    ln_lnw = np.load(
        ln_dir / "ln_lnw.npy"
    )

    ln_lnb = np.load(
        ln_dir / "ln_lnb.npy"
    )

    ln_rsqrt = np.load(
        ln_dir / "ln_rsqrt_table.npy"
    )

    # Exact LN hooks are registered after controller LN hooks,
    # so they override the Stage4D surrogate output.
    ln_handles = install_exact_layernorm(
        backbone,
        controller,
        input_scales,
        ln_scalars,
        ln_lnw,
        ln_lnb,
        ln_rsqrt,
        device,
    )

    # Exact GELU hooks likewise override the Stage4D GELU surrogate.
    gelu_handles = install_exact_gelu(
        backbone,
        controller,
        args.gelu_dir,
        device,
    )

    classes = list(source["classes"])

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

    # Baseline = Stage4H exact LN + exact GELU,
    # but still Stage4D fake-quant matrix/output/residual surrogate.
    baseline_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Prepare exact matrix parameters and residual RM/RS.
    # ------------------------------------------------------------

    qweights1 = []
    qweights2 = []
    qbias1 = []
    qbias2 = []
    residual_params = []

    ln_report = json.load(
        open(ln_dir / "report.json", "r", encoding="utf-8")
    )

    print()
    print("===== STAGE 4I: FIT MLP RESIDUAL RM/RS =====")

    for b in range(12):
        block = backbone.vit.blocks[b]

        sln = float(scales[str(b)]["ln2_signed3_scale"])
        sge = float(scales[str(b)]["gelu_uint3_scale"])

        sm1 = float(scales[str(b)]["m1_int11_scale"])
        sm2 = float(scales[str(b)]["m2_int13_scale"])

        qw1, sw1 = quant_weight_int3(block.mlp.fc1)
        qw2, sw2 = quant_weight_int3(block.mlp.fc2)

        qb1 = quant_bias(
            block.mlp.fc1,
            sm1,
            11,
        )

        qb2 = quant_bias(
            block.mlp.fc2,
            sm2,
            13,
        )

        qweights1.append(qw1)
        qweights2.append(qw2)
        qbias1.append(qb1)
        qbias2.append(qb2)

        qmin = int(
            ln_report["blocks"][str(b)]["stats"]["input_code_min"]
        )
        qmax = int(
            ln_report["blocks"][str(b)]["stats"]["input_code_max"]
        )

        rp = fit_residual_scalar(
            float(input_scales[b]),
            sm2,
            qmin,
            qmax,
            max_shift=args.max_residual_shift,
        )

        residual_params.append(rp)

        print(
            f"Block {b:2d}: "
            f"Sin={input_scales[b]:.10g} "
            f"Sout={sm2:.10g} "
            f"RM={rp['RM']} RS={rp['RS']} "
            f"mismatch={100.0*rp['mismatch_rate']:.6f}% "
            f"maxerr={rp['max_abs_error']}"
        )

    # ------------------------------------------------------------
    # Cache MLP residual inputs (norm2 input) for final block hook.
    # ------------------------------------------------------------

    residual_cache = [None] * 12
    cache_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        def cache_pre(module, inputs, b=b):
            residual_cache[b] = inputs[0]

        cache_handles.append(
            block.norm2.register_forward_pre_hook(
                cache_pre
            )
        )

    # ------------------------------------------------------------
    # Exact MLP1/M2 integer matmul hooks.
    # ------------------------------------------------------------

    exact_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sln = float(scales[str(b)]["ln2_signed3_scale"])
        sge = float(scales[str(b)]["gelu_uint3_scale"])
        sm1 = float(scales[str(b)]["m1_int11_scale"])
        sm2 = float(scales[str(b)]["m2_int13_scale"])
        sin = float(input_scales[b])

        qw1 = qweights1[b].to(device)
        qw2 = qweights2[b].to(device)
        qb1 = qbias1[b].to(device)
        qb2 = qbias2[b].to(device)

        rp = residual_params[b]
        rm = int(rp["RM"])
        rs = int(rp["RS"])
        rb = int(rp["RB"])

        # MLP1: signed int3 x signed int3 + int11 bias -> ap_int<11>.
        def fc1_hook(
            module,
            inputs,
            output,
            sln=sln,
            sm1=sm1,
            qw1=qw1,
            qb1=qb1,
        ):
            x = inputs[0]
            xi = torch.round(
                x / sln
            ).to(torch.int64)
            xi = torch.clamp(
                xi,
                -4,
                3,
            )

            acc = torch.matmul(
                xi.to(torch.float32),
                qw1.t().to(torch.float32),
            )
            acc = torch.round(acc).to(torch.int64)
            acc = acc + qb1

            # Stage4E proved reachable final accumulators are far inside
            # int11 range. Apply the actual ap_int assignment wrap.
            acc = wrap_signed(acc, 11)

            return acc.to(x.dtype) * sm1

        exact_handles.append(
            block.mlp.fc1.register_forward_hook(
                fc1_hook
            )
        )

        # MLP2: uint3 x signed int3 + int13 bias -> ap_int<13>.
        def fc2_hook(
            module,
            inputs,
            output,
            sge=sge,
            sm2=sm2,
            qw2=qw2,
            qb2=qb2,
        ):
            x = inputs[0]
            xi = torch.round(
                x / sge
            ).to(torch.int64)
            xi = torch.clamp(
                xi,
                0,
                7,
            )

            acc = torch.matmul(
                xi.to(torch.float32),
                qw2.t().to(torch.float32),
            )
            acc = torch.round(acc).to(torch.int64)
            acc = acc + qb2
            acc = wrap_signed(acc, 13)

            return acc.to(x.dtype) * sm2

        exact_handles.append(
            block.mlp.fc2.register_forward_hook(
                fc2_hook
            )
        )

        # Final exact HLS MLP residual merge.
        # Registered after controller block hook, so this return value wins.
        def block_hook(
            module,
            inputs,
            output,
            b=b,
            sin=sin,
            sm2=sm2,
            rm=rm,
            rs=rs,
            rb=rb,
        ):
            x_res = residual_cache[b]

            if x_res is None:
                raise RuntimeError(
                    f"Missing residual cache for block {b}"
                )

            # MLP2 branch in real-valued wrapper -> recover exact int13 code.
            # output currently includes the PyTorch residual; therefore recover
            # the MLP2 code directly from the fc2 module result is not possible
            # here. Recompute only the final residual replacement from the
            # current standard block output by using the identity:
            #
            # standard block output = x_res + exact_mlp2_real
            #
            # because eval-mode DropPath is identity for DeiT.
            mlp2_real = output - x_res

            m2_int = torch.round(
                mlp2_real / sm2
            ).to(torch.int64)
            m2_int = wrap_signed(m2_int, 13)

            x_int15 = torch.round(
                x_res / sin
            ).to(torch.int64)
            x_int15 = wrap_signed(
                x_int15,
                15,
            )

            res_scaled = arshift(
                x_int15 * rm + rb,
                rs,
            )

            # Explicit cast in mlp.h:
            # __mlp_of_t((... ) >> RS)
            res13 = wrap_signed(
                res_scaled,
                13,
            )

            out13 = wrap_signed(
                m2_int + res13,
                13,
            )

            return out13.to(output.dtype) * sm2

        exact_handles.append(
            block.register_forward_hook(
                block_hook
            )
        )

    exact_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Export residual scalars.
    # ------------------------------------------------------------

    mlp_scalars = np.zeros(
        (12, 2),
        dtype=np.int32,
    )

    residual_json = {}

    for b, rp in enumerate(residual_params):
        mlp_scalars[b, 0] = int(rp["RM"])
        mlp_scalars[b, 1] = int(rp["RS"])
        residual_json[str(b)] = {
            k: (
                int(v)
                if isinstance(v, (int, np.integer))
                else float(v)
            )
            for k, v in rp.items()
        }
        residual_json[str(b)]["input_int15_scale"] = float(
            input_scales[b]
        )
        residual_json[str(b)]["output_int13_scale"] = float(
            scales[str(b)]["m2_int13_scale"]
        )

    np.save(
        out / "mlp_scalars.npy",
        mlp_scalars,
    )

    with open(
        out / "mlp_scalars.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "mlp_scalars": mlp_scalars.astype(int).tolist(),
                "blocks": residual_json,
            },
            f,
            indent=2,
        )

    report = {
        "scope": (
            "Exact MLP LayerNorm + MLP1 int11 + exact GELU LUT + "
            "MLP2 int13 + HLS RM/RS residual merge. Attention remains "
            "non-bit-accurate."
        ),
        "stage4h_exact_ln_gelu_val_top1": baseline_val,
        "exact_mlp_val_top1": exact_val,
        "additional_mlp_exact_drop_pp": baseline_val - exact_val,
        "mlp_scalars": mlp_scalars.astype(int).tolist(),
        "residual_fit": residual_json,
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
    print("===== STAGE 4I: EXACT MLP EVAL =====")
    print(f"Stage4H exact LN+GELU val : {baseline_val:.4f}%")
    print(f"Exact full MLP val         : {exact_val:.4f}%")
    print(f"Additional exact-MLP drop  : {baseline_val-exact_val:.4f} pp")
    print("Report:", out / "report.json")
    print("MLP scalars:", out / "mlp_scalars.json")

    for h in exact_handles:
        h.remove()
    for h in cache_handles:
        h.remove()
    for h in gelu_handles:
        h.remove()
    for h in ln_handles:
        h.remove()
    controller.remove()


if __name__ == "__main__":
    main()
