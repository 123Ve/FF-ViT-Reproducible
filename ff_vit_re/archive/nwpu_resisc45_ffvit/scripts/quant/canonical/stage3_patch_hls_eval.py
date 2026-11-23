#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets

from qat_weight3_hls196 import (
    HLS196DeiT,
    convert_backbone_to_qat,
    eval_transform,
)


# ============================================================
# Frozen HLS contract
# ============================================================

INPUT_SCALE = 1.0 / 64.0
INPUT_MULT = 64.0

INPUT_QMIN = -32768
INPUT_QMAX = 32767

PATCH_W_QMIN = -128
PATCH_W_QMAX = 127

PATCH_SHIFT = 8
PATCH_ROUND_BIAS = 1 << (PATCH_SHIFT - 1)   # 128

FM_BITS = 13
FM_QMIN = -(1 << (FM_BITS - 1))            # -4096
FM_QMAX = (1 << (FM_BITS - 1)) - 1         # 4095


# ============================================================
# Helpers
# ============================================================

def signed_wrap(x, bits):
    """
    Exactly emulate assignment to ap_int<bits>.
    """
    mod = 1 << bits
    half = 1 << (bits - 1)

    return torch.remainder(
        x + half,
        mod
    ) - half


def quantize_patch_weight_int8(weight):
    """
    One global signed-int8 scale for the whole Patch matrix.

        q = clip(round(w / scale), -128, 127)

    Search clipping threshold to minimize weight MSE.

    A single scale is intentional:
    the current HLS Patch path has one common final >>8 shift
    and one common feature-map integer domain.
    """

    w = weight.detach().float().cpu()

    max_abs = float(
        w.abs().max().item()
    )

    best = None

    # int8 is already relatively fine;
    # search 70% ... 100% max range.
    for i in range(121):
        ratio = (
            0.70
            + 0.30 * i / 120
        )

        alpha = (
            max_abs * ratio
        )

        scale = (
            alpha / 127.0
        )

        q = torch.round(
            w / scale
        ).clamp(
            PATCH_W_QMIN,
            PATCH_W_QMAX
        )

        dq = q * scale

        mse = float(
            ((w - dq) ** 2)
            .mean()
            .item()
        )

        sat = float(
            (
                (q == PATCH_W_QMIN)
                | (q == PATCH_W_QMAX)
            )
            .float()
            .mean()
            .item()
        )

        if (
            best is None
            or mse < best["mse"]
        ):
            best = {
                "scale": float(scale),
                "q": q.to(torch.int8),
                "dq": dq,
                "mse": mse,
                "sat": sat,
            }

    return best


def image_to_patch_matrix_int16(x):
    """
    x:
        [B,3,224,224], normalized float tensor

    Returns:
        [B,196,768] signed-int16 semantic values.

    F.unfold order matches Conv2d weight flattening:
        channel -> kernel-row -> kernel-column
    """

    q = torch.round(
        x.float() * INPUT_MULT
    ).clamp(
        INPUT_QMIN,
        INPUT_QMAX
    )

    patches = F.unfold(
        q,
        kernel_size=16,
        stride=16,
    )

    # [B,768,196] -> [B,196,768]
    patches = (
        patches
        .transpose(1, 2)
        .contiguous()
    )

    return patches


def logical_to_hls_input_stream(q_patch):
    """
    q_patch:
        [196,768]

    Current HLS external stream has TP=2, CAP=1.

    Packet order:
        tt=0:
            c0 -> [token0, token1]
            c1 -> [token0, token1]
            ...
        tt=1:
            c0 -> [token2, token3]
            ...

    Output:
        [98,768,2]
    """

    assert tuple(
        q_patch.shape
    ) == (196, 768)

    q = q_patch.reshape(
        98,
        2,
        768,
    )

    q = q.permute(
        0,
        2,
        1,
    ).contiguous()

    return q


# ============================================================
# HLS Patch frontend
# ============================================================

class HLSPatchFrontend(nn.Module):

    def __init__(
        self,
        q_weight,
        bias_raw,
        cls_raw,
        weight_scale,
    ):
        super().__init__()

        # Store integer values as float32 so GEMM can execute
        # efficiently. Values themselves remain exact integers.
        self.register_buffer(
            "q_weight",
            q_weight.float()
        )

        self.register_buffer(
            "bias_raw",
            bias_raw.float()
        )

        self.register_buffer(
            "cls_raw",
            cls_raw.float()
        )

        self.weight_scale = float(
            weight_scale
        )

        # Raw integer MAC has real scale:
        #
        #    S_acc = S_input * S_weight
        #
        self.acc_scale = (
            INPUT_SCALE
            * self.weight_scale
        )

        # HLS performs >> 8 after the accumulator.
        self.output_scale = (
            self.acc_scale
            * (1 << PATCH_SHIFT)
        )

        self.last_stats = None

    def integer_patch(self, x):
        """
        Returns HLS semantic signed int13 tensor:
            [B,196,192]
        """

        # Force Patch arithmetic to float32 rather than autocast.
        # Integer operands are small enough that these integer
        # sums are exactly representable in float32 for this path.
        with torch.autocast(
            device_type=x.device.type,
            enabled=False,
        ):

            patches = (
                image_to_patch_matrix_int16(
                    x
                )
                .to(
                    device=x.device,
                    dtype=torch.float32,
                )
            )

            # [B,196,768] @ [768,192]
            acc = torch.matmul(
                patches,
                self.q_weight.t()
            )

            # token-dependent Patch bias + position term
            acc = (
                acc
                + self.bias_raw.unsqueeze(0)
            )

            # token0 is replaced by CLS ROM.
            acc[:, 0, :] = (
                self.cls_raw
            )

            # All terms are integer-valued.
            # HLS:
            #
            #   (final_val + 128) >> 8
            #
            # Arithmetic right shift equals floor division
            # for signed integers.
            prewrap = torch.floor(
                (
                    acc
                    + PATCH_ROUND_BIAS
                )
                / float(
                    1 << PATCH_SHIFT
                )
            ).to(torch.int64)

            overflow_mask = (
                (prewrap < FM_QMIN)
                | (prewrap > FM_QMAX)
            )

            wrapped = signed_wrap(
                prewrap,
                FM_BITS
            )

            self.last_stats = {
                "prewrap_min":
                    int(
                        prewrap.min().item()
                    ),

                "prewrap_max":
                    int(
                        prewrap.max().item()
                    ),

                "overflow_count":
                    int(
                        overflow_mask
                        .sum()
                        .item()
                    ),

                "total_count":
                    int(
                        prewrap.numel()
                    ),

                "max_abs_acc":
                    float(
                        acc.abs()
                        .max()
                        .item()
                    ),
            }

            return wrapped

    def forward(self, x):
        q13 = self.integer_patch(x)

        # Convert semantic integer back to its real value
        # only so the remaining PyTorch Transformer can run.
        return (
            q13.float()
            * self.output_scale
        )


# ============================================================
# Full model wrapper
# ============================================================

class HLSStage3Model(nn.Module):

    def __init__(
        self,
        qat_model,
        patch_frontend,
    ):
        super().__init__()

        self.qat_model = qat_model
        self.patch = patch_frontend

    def forward(self, x):
        vit = self.qat_model.vit

        # Already includes:
        # Patch projection
        # Patch bias
        # positional embedding
        # CLS replacement
        y = self.patch(x)

        # Therefore DO NOT add vit.pos_embed here again.
        y = vit.pos_drop(y)

        if hasattr(
            vit,
            "patch_drop"
        ):
            y = vit.patch_drop(y)

        if hasattr(
            vit,
            "norm_pre"
        ):
            y = vit.norm_pre(y)

        y = vit.blocks(y)
        y = vit.norm(y)

        return vit.forward_head(y)


class Input16Baseline(nn.Module):

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        q = torch.round(
            x * INPUT_MULT
        ).clamp(
            INPUT_QMIN,
            INPUT_QMAX
        )

        return self.model(
            q / INPUT_MULT
        )


# ============================================================
# Evaluation
# ============================================================

@torch.inference_mode()
def evaluate(
    model,
    loader,
    device,
):
    model.eval()

    correct = 0
    total = 0

    for images, labels in loader:

        images = images.to(
            device,
            non_blocking=True
        )

        labels = labels.to(
            device,
            non_blocking=True
        )

        # Use FP32 here so Stage3 integer-like Patch arithmetic
        # is not altered by fp16 autocast.
        logits = model(images)

        correct += int(
            (
                logits.argmax(1)
                == labels
            )
            .sum()
            .item()
        )

        total += int(
            labels.numel()
        )

    return (
        100.0
        * correct
        / total
    )


# ============================================================
# Export HLS bank layouts
# ============================================================

def make_patch_banks(
    q_weight,
    bias_raw,
    cls_raw,
):
    """
    HLS layouts:

      PATCH_WEIGHT_BANK[cop][cip][cot][cit]
      PATCH_BIAS_BANK[tp][cop][tt][cot]
      PATCH_CLS_BANK[cop][cot]

    Logical mapping:

      output channel = cot*12 + cop
      input channel  = cit*24 + cip
      token          = tt*2 + tp
    """

    qw = (
        q_weight
        .cpu()
        .numpy()
        .astype(np.int8)
    )

    br = (
        bias_raw
        .cpu()
        .numpy()
        .astype(np.int64)
    )

    cr = (
        cls_raw
        .cpu()
        .numpy()
        .astype(np.int64)
    )

    wbank = np.zeros(
        (12, 24, 16, 32),
        dtype=np.int8,
    )

    bbank = np.zeros(
        (2, 12, 98, 16),
        dtype=np.int64,
    )

    cbank = np.zeros(
        (12, 16),
        dtype=np.int64,
    )

    for co in range(192):
        cop = co % 12
        cot = co // 12

        for ci in range(768):
            cip = ci % 24
            cit = ci // 24

            wbank[
                cop,
                cip,
                cot,
                cit,
            ] = qw[
                co,
                ci,
            ]

        cbank[
            cop,
            cot,
        ] = cr[co]

    for t in range(196):
        tp = t % 2
        tt = t // 2

        for co in range(192):
            cop = co % 12
            cot = co // 12

            bbank[
                tp,
                cop,
                tt,
                cot,
            ] = br[
                t,
                co,
            ]

    return (
        wbank,
        bbank,
        cbank,
    )


# ============================================================
# Main
# ============================================================

def main():

    p = argparse.ArgumentParser()

    p.add_argument(
        "--source-checkpoint",
        required=True
    )

    p.add_argument(
        "--qat-checkpoint",
        required=True
    )

    p.add_argument(
        "--data-root",
        required=True
    )

    p.add_argument(
        "--output",
        default="stage3_patch_hls"
    )

    p.add_argument(
        "--batch-size",
        type=int,
        default=32
    )

    p.add_argument(
        "--workers",
        type=int,
        default=4
    )

    args = p.parse_args()

    out = Path(args.output)

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Rebuild final W3-QAT model
    # --------------------------------------------------------

    source = torch.load(
        args.source_checkpoint,
        map_location="cpu",
        weights_only=True,
    )

    qat = torch.load(
        args.qat_checkpoint,
        map_location="cpu",
        weights_only=True,
    )

    classes = list(
        source["classes"]
    )

    num_classes = int(
        source["num_classes"]
    )

    model = HLS196DeiT(
        num_classes
    )

    model.vit.load_state_dict(
        source["model"],
        strict=True,
    )

    convert_backbone_to_qat(
        model
    )

    model.load_state_dict(
        qat["model_state"],
        strict=True,
    )

    # --------------------------------------------------------
    # Extract final QAT Patch / CLS / position parameters
    # --------------------------------------------------------

    patch_w = (
        model.vit
        .patch_embed
        .proj
        .weight
        .detach()
        .float()
        .cpu()
        .reshape(
            192,
            768,
        )
    )

    patch_b = (
        model.vit
        .patch_embed
        .proj
        .bias
        .detach()
        .float()
        .cpu()
    )

    pos = (
        model.vit
        .pos_embed
        .detach()
        .float()
        .cpu()[0]
    )

    cls = (
        model.vit
        .cls_token
        .detach()
        .float()
        .cpu()[0, 0]
    )

    if tuple(pos.shape) != (
        196,
        192,
    ):
        raise RuntimeError(
            f"bad pos shape "
            f"{tuple(pos.shape)}"
        )

    # --------------------------------------------------------
    # Patch signed int8 quantization
    # --------------------------------------------------------

    qres = (
        quantize_patch_weight_int8(
            patch_w
        )
    )

    patch_qw = qres["q"]

    sw = qres["scale"]

    raw_scale = (
        INPUT_SCALE * sw
    )

    output_scale = (
        raw_scale
        * (1 << PATCH_SHIFT)
    )

    # --------------------------------------------------------
    # Fold:
    #
    # Patch bias + positional embedding
    # --------------------------------------------------------

    bias_real = (
        patch_b.unsqueeze(0)
        + pos
    )

    bias_raw = torch.round(
        bias_real
        / raw_scale
    ).to(torch.int64)

    # token0 is ignored by HLS, but keep a defined value.
    bias_raw[0].zero_()

    # CLS + CLS position
    cls_real = (
        cls
        + pos[0]
    )

    cls_raw = torch.round(
        cls_real
        / raw_scale
    ).to(torch.int64)

    # Current HLS uses int storage for these ROM quantities.
    i32_min = -(1 << 31)
    i32_max = (1 << 31) - 1

    if (
        int(bias_raw.min()) < i32_min
        or int(bias_raw.max()) > i32_max
    ):
        raise RuntimeError(
            "Patch bias raw value "
            "does not fit int32"
        )

    if (
        int(cls_raw.min()) < i32_min
        or int(cls_raw.max()) > i32_max
    ):
        raise RuntimeError(
            "Patch CLS raw value "
            "does not fit int32"
        )

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    test_ds = (
        __import__('manifest_adapter').image_folder(
            Path(args.data_root)
            / "test",
            transform=eval_transform(),
        )
    )

    if list(
        test_ds.classes
    ) != classes:
        raise RuntimeError(
            "class ordering mismatch"
        )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    loader = DataLoader(
        test_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(
            device.type == "cuda"
        ),
    )

    model = model.to(device)

    # --------------------------------------------------------
    # Baseline:
    # W3 QAT + HLS int16 input
    # --------------------------------------------------------

    baseline = Input16Baseline(
        model
    ).to(device)

    baseline_top1 = evaluate(
        baseline,
        loader,
        device
    )

    # --------------------------------------------------------
    # Stage3:
    # int16 input + int8 Patch + int13 output + W3 backbone
    # --------------------------------------------------------

    patch_frontend = (
        HLSPatchFrontend(
            patch_qw,
            bias_raw,
            cls_raw,
            sw,
        )
        .to(device)
    )

    hls_model = HLSStage3Model(
        model,
        patch_frontend,
    ).to(device)

    hls_top1 = evaluate(
        hls_model,
        loader,
        device
    )

    # --------------------------------------------------------
    # Full test-set overflow audit
    # --------------------------------------------------------

    overflow_count = 0
    total_count = 0

    global_pre_min = None
    global_pre_max = None
    max_abs_acc = 0.0

    hls_model.eval()

    with torch.inference_mode():

        for images, _ in loader:

            images = images.to(
                device,
                non_blocking=True
            )

            _ = patch_frontend(
                images
            )

            st = (
                patch_frontend
                .last_stats
            )

            overflow_count += (
                st["overflow_count"]
            )

            total_count += (
                st["total_count"]
            )

            max_abs_acc = max(
                max_abs_acc,
                st["max_abs_acc"]
            )

            if global_pre_min is None:
                global_pre_min = (
                    st["prewrap_min"]
                )
                global_pre_max = (
                    st["prewrap_max"]
                )
            else:
                global_pre_min = min(
                    global_pre_min,
                    st["prewrap_min"]
                )
                global_pre_max = max(
                    global_pre_max,
                    st["prewrap_max"]
                )

    # --------------------------------------------------------
    # Export logical + HLS bank formats
    # --------------------------------------------------------

    torch.save(
        patch_qw,
        out
        / "patch_weight_int8.pt"
    )

    torch.save(
        bias_raw,
        out
        / "patch_bias_raw_int32.pt"
    )

    torch.save(
        cls_raw,
        out
        / "patch_cls_raw_int32.pt"
    )

    (
        wbank,
        bbank,
        cbank,
    ) = make_patch_banks(
        patch_qw,
        bias_raw,
        cls_raw,
    )

    np.savez_compressed(
        out
        / "patch_rom_banks.npz",

        PATCH_WEIGHT_BANK=
            wbank,

        PATCH_BIAS_BANK=
            bbank.astype(
                np.int32
            ),

        PATCH_CLS_BANK=
            cbank.astype(
                np.int32
            ),

        PATCH_SCALARS=
            np.array(
                [8, 0, 0, 0],
                dtype=np.int32
            ),
    )

    # --------------------------------------------------------
    # Export one corrected HLS input stream
    # --------------------------------------------------------

    sample, label = (
        test_ds[0]
    )

    sample_b = (
        sample.unsqueeze(0)
    )

    qpatch = (
        image_to_patch_matrix_int16(
            sample_b
        )[0]
        .to(torch.int16)
        .cpu()
    )

    hls_in = (
        logical_to_hls_input_stream(
            qpatch
        )
        .numpy()
        .astype("<i2")
    )

    input_bin = (
        out
        / "sample0_input_hls_stream_int16.bin"
    )

    hls_in.tofile(
        input_bin
    )

    expected_input_bytes = (
        196
        * 768
        * 2
    )

    if (
        input_bin.stat().st_size
        != expected_input_bytes
    ):
        raise RuntimeError(
            "bad input BIN size"
        )

    # --------------------------------------------------------
    # Export one Patch-output reference
    #
    # Internal FM stream order:
    # [98,192,2]
    # --------------------------------------------------------

    patch_frontend_cpu = (
        HLSPatchFrontend(
            patch_qw,
            bias_raw,
            cls_raw,
            sw,
        )
    )

    with torch.inference_mode():

        q13 = (
            patch_frontend_cpu
            .integer_patch(
                sample_b
            )[0]
            .cpu()
        )

    # logical [196,192]
    np.save(
        out
        / "sample0_patch_output_logical_int13.npy",
        q13.numpy().astype(
            np.int16
        )
    )

    # HLS stream:
    # [tt][channel][tp]
    fm_stream = (
        q13
        .reshape(
            98,
            2,
            192,
        )
        .permute(
            0,
            2,
            1,
        )
        .contiguous()
        .numpy()
        .astype("<i2")
    )

    fm_bin = (
        out
        / "sample0_patch_output_stream_int13.bin"
    )

    fm_stream.tofile(
        fm_bin
    )

    # --------------------------------------------------------
    # Contract report
    # --------------------------------------------------------

    report = {
        "baseline_w3_qat_plus_input16_top1":
            baseline_top1,

        "stage3_hls_patch_top1":
            hls_top1,

        "patch_quant_drop_pp":
            baseline_top1
            - hls_top1,

        "patch_weight": {
            "logical_type":
                "signed int8",

            "range":
                [
                    int(
                        patch_qw.min()
                    ),
                    int(
                        patch_qw.max()
                    ),
                ],

            "scale":
                sw,

            "mse":
                qres["mse"],

            "saturation_rate":
                qres["sat"],

            "logical_shape":
                [192, 768],

            "hls_bank_shape":
                list(
                    wbank.shape
                ),
        },

        "patch_bias": {
            "raw_scale":
                raw_scale,

            "raw_min":
                int(
                    bias_raw.min()
                ),

            "raw_max":
                int(
                    bias_raw.max()
                ),

            "meaning":
                (
                    "patch_embed.bias + "
                    "positional embedding"
                ),

            "hls_bank_shape":
                list(
                    bbank.shape
                ),
        },

        "patch_cls": {
            "raw_min":
                int(
                    cls_raw.min()
                ),

            "raw_max":
                int(
                    cls_raw.max()
                ),

            "meaning":
                (
                    "CLS token + "
                    "CLS positional embedding"
                ),

            "hls_bank_shape":
                list(
                    cbank.shape
                ),
        },

        "patch_output": {
            "hls_type":
                "ap_int<13>",

            "shift":
                PATCH_SHIFT,

            "round_bias":
                PATCH_ROUND_BIAS,

            "real_scale":
                output_scale,

            "prewrap_min":
                global_pre_min,

            "prewrap_max":
                global_pre_max,

            "overflow_count":
                overflow_count,

            "total_values":
                total_count,

            "overflow_rate":
                (
                    overflow_count
                    / total_count
                ),
        },

        "input_stream": {
            "logical_shape":
                [196, 768],

            "physical_stream_shape":
                [98, 768, 2],

            "dtype":
                "signed int16",

            "scale":
                INPUT_SCALE,

            "bytes_per_image":
                expected_input_bytes,

            "ordering":
                (
                    "[tt][ci][tp], "
                    "token pair interleaved"
                ),
        },

        "sample0": {
            "label_index":
                int(label),

            "label_name":
                classes[label],

            "input_bin":
                str(input_bin),

            "patch_output_bin":
                str(fm_bin),
        },
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
            ensure_ascii=False,
        )

    print()
    print(
        "===== STAGE 3: "
        "HLS PATCH ====="
    )

    print(
        f"W3-QAT + input16 Top-1 : "
        f"{baseline_top1:.4f}%"
    )

    print(
        f"+ HLS Patch Top-1       : "
        f"{hls_top1:.4f}%"
    )

    print(
        f"Patch quant drop        : "
        f"{baseline_top1-hls_top1:.4f} pp"
    )

    print(
        f"Patch W int8 range      : "
        f"[{int(patch_qw.min())}, "
        f"{int(patch_qw.max())}]"
    )

    print(
        f"Patch W scale           : "
        f"{sw:.10g}"
    )

    print(
        f"Patch output real scale : "
        f"{output_scale:.10g}"
    )

    print(
        f"Patch int13 prewrap     : "
        f"[{global_pre_min}, "
        f"{global_pre_max}]"
    )

    print(
        f"Patch int13 overflow    : "
        f"{overflow_count}/"
        f"{total_count} "
        f"("
        f"{100*overflow_count/total_count:.8f}%"
        f")"
    )

    print(
        "HLS input stream shape : "
        "(98, 768, 2)"
    )

    print(
        "Patch ROM bank shapes  : "
        f"{wbank.shape}, "
        f"{bbank.shape}, "
        f"{cbank.shape}"
    )

    print(
        "Report:",
        out / "report.json"
    )


if __name__ == "__main__":
    main()
