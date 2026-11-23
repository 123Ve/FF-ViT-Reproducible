#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets

from qat_weight3_hls196 import (
    HLS196DeiT,
    convert_backbone_to_qat,
    eval_transform,
)

from stage3_patch_hls_eval import (
    HLSPatchFrontend,
    HLSStage3Model,
)


# ============================================================
# Hardware semantic ranges
# ============================================================

S3_QMIN = -4
S3_QMAX = 3

U3_QMIN = 0
U3_QMAX = 7

S13_QMIN = -4096
S13_QMAX = 4095


def signed_fake_quant(
    x,
    scale,
    qmin=S3_QMIN,
    qmax=S3_QMAX,
):
    scale = max(
        float(scale),
        1e-12,
    )

    q = torch.round(
        x / scale
    )

    q = torch.clamp(
        q,
        qmin,
        qmax,
    )

    return q * scale


def unsigned_fake_quant(
    x,
    scale,
):
    """
    HLS GELU boundary is ap_uint<3>.

    First-pass convention:
      code 0 represents real zero;
      small negative GELU tail is clipped to zero.
    """

    scale = max(
        float(scale),
        1e-12,
    )

    q = torch.round(
        x / scale
    )

    q = torch.clamp(
        q,
        U3_QMIN,
        U3_QMAX,
    )

    return q * scale


class ActivationQuantManager:

    def __init__(
        self,
        model,
        ranges,
        percentile_key="abs_p999",
    ):
        self.model = model
        self.ranges = ranges
        self.percentile_key = percentile_key

        self.handles = []

        self.scales = {}

    def s3_scale(self, key):
        """
        signed 3-bit:
            [-4,3]

        Positive representable maximum is 3*scale.
        """

        v = float(
            self.ranges[key][
                self.percentile_key
            ]
        )

        s = max(
            v / 3.0,
            1e-12,
        )

        self.scales[key] = {
            "scale": s,
            "dtype": "signed3",
            "qmin": -4,
            "qmax": 3,
        }

        return s

    def u3_scale(self, key):
        """
        GELU output:
            unsigned 3-bit [0,7]

        GELU negative tail is very small (~ -0.17),
        therefore first PTQ test clips it to zero.
        """

        # GELU is mostly nonnegative.
        max_val = float(
            self.ranges[key]["max"]
        )

        # p99.9 gives a less outlier-sensitive
        # first hardware calibration.
        p = float(
            self.ranges[key][
                self.percentile_key
            ]
        )

        threshold = min(
            max_val,
            max(p, 1e-12),
        )

        s = threshold / 7.0

        self.scales[key] = {
            "scale": s,
            "dtype": "unsigned3",
            "qmin": 0,
            "qmax": 7,
        }

        return s

    def s13_scale(self, key):
        v = float(
            self.ranges[key][
                self.percentile_key
            ]
        )

        s = max(
            v / 4095.0,
            1e-12,
        )

        self.scales[key] = {
            "scale": s,
            "dtype": "signed13",
            "qmin": -4096,
            "qmax": 4095,
        }

        return s

    def install(self):

        for b in range(12):

            block = (
                self.model
                .vit
                .blocks[b]
            )

            # --------------------------------
            # LN1 -> signed 3-bit
            # --------------------------------

            key = f"b{b}.ln1_out"
            s = self.s3_scale(key)

            def ln1_hook(
                module,
                inputs,
                output,
                s=s,
            ):
                return signed_fake_quant(
                    output,
                    s,
                )

            self.handles.append(
                block.norm1
                .register_forward_hook(
                    ln1_hook
                )
            )

            # --------------------------------
            # Q/K/V -> separate signed 3-bit
            # --------------------------------

            sq = self.s3_scale(
                f"b{b}.q_prequant"
            )

            sk = self.s3_scale(
                f"b{b}.k_prequant"
            )

            sv = self.s3_scale(
                f"b{b}.v_prequant"
            )

            def qkv_hook(
                module,
                inputs,
                output,
                sq=sq,
                sk=sk,
                sv=sv,
            ):

                q, k, v = torch.chunk(
                    output,
                    3,
                    dim=-1,
                )

                q = signed_fake_quant(
                    q, sq
                )

                k = signed_fake_quant(
                    k, sk
                )

                v = signed_fake_quant(
                    v, sv
                )

                return torch.cat(
                    [q, k, v],
                    dim=-1,
                )

            self.handles.append(
                block.attn.qkv
                .register_forward_hook(
                    qkv_hook
                )
            )

            # --------------------------------
            # Attention A -> signed 3-bit
            #
            # input of output projection
            # --------------------------------

            sa = self.s3_scale(
                f"b{b}.attn_A_pre_proj"
            )

            def a_pre_hook(
                module,
                inputs,
                sa=sa,
            ):
                x = inputs[0]

                x = signed_fake_quant(
                    x,
                    sa,
                )

                return (x,)

            self.handles.append(
                block.attn.proj
                .register_forward_pre_hook(
                    a_pre_hook
                )
            )

            # --------------------------------
            # LN2 -> signed 3-bit
            # --------------------------------

            sln2 = self.s3_scale(
                f"b{b}.ln2_out"
            )

            def ln2_hook(
                module,
                inputs,
                output,
                s=sln2,
            ):
                return signed_fake_quant(
                    output,
                    s,
                )

            self.handles.append(
                block.norm2
                .register_forward_hook(
                    ln2_hook
                )
            )

            # --------------------------------
            # GELU -> unsigned 3-bit
            # --------------------------------

            sg = self.u3_scale(
                f"b{b}.gelu_out"
            )

            def gelu_hook(
                module,
                inputs,
                output,
                s=sg,
            ):
                return unsigned_fake_quant(
                    output,
                    s,
                )

            self.handles.append(
                block.mlp.act
                .register_forward_hook(
                    gelu_hook
                )
            )

            # --------------------------------
            # Block output / FM -> signed13
            # --------------------------------

            sfm = self.s13_scale(
                f"b{b}.block_out"
            )

            def block_hook(
                module,
                inputs,
                output,
                s=sfm,
            ):
                return signed_fake_quant(
                    output,
                    s,
                    qmin=S13_QMIN,
                    qmax=S13_QMAX,
                )

            self.handles.append(
                block.register_forward_hook(
                    block_hook
                )
            )

    def remove(self):
        for h in self.handles:
            h.remove()

        self.handles = []


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
            non_blocking=True,
        )

        labels = labels.to(
            device,
            non_blocking=True,
        )

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


def rebuild_stage3_model(
    source_path,
    qat_path,
    stage3_dir,
):

    source = torch.load(
        source_path,
        map_location="cpu",
        weights_only=True,
    )

    qat = torch.load(
        qat_path,
        map_location="cpu",
        weights_only=True,
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

    s3dir = Path(
        stage3_dir
    )

    patch_w = torch.load(
        s3dir
        / "patch_weight_int8.pt",
        map_location="cpu",
        weights_only=True,
    )

    patch_bias = torch.load(
        s3dir
        / "patch_bias_raw_int32.pt",
        map_location="cpu",
        weights_only=True,
    )

    patch_cls = torch.load(
        s3dir
        / "patch_cls_raw_int32.pt",
        map_location="cpu",
        weights_only=True,
    )

    with open(
        s3dir / "report.json",
        "r",
        encoding="utf-8",
    ) as f:
        s3report = json.load(f)

    patch_scale = float(
        s3report[
            "patch_weight"
        ]["scale"]
    )

    patch = HLSPatchFrontend(
        patch_w,
        patch_bias,
        patch_cls,
        patch_scale,
    )

    full = HLSStage3Model(
        model,
        patch,
    )

    return (
        full,
        model,
        source,
    )


def main():

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--source-checkpoint",
        required=True,
    )

    ap.add_argument(
        "--qat-checkpoint",
        required=True,
    )

    ap.add_argument(
        "--stage3-dir",
        required=True,
    )

    ap.add_argument(
        "--ranges",
        required=True,
    )

    ap.add_argument(
        "--data-root",
        required=True,
    )

    ap.add_argument(
        "--output",
        default="stage4b_activation_ptq",
    )

    ap.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )

    ap.add_argument(
        "--workers",
        type=int,
        default=4,
    )

    args = ap.parse_args()

    out = Path(
        args.output
    )

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        full_model,
        backbone,
        source,
    ) = rebuild_stage3_model(
        args.source_checkpoint,
        args.qat_checkpoint,
        args.stage3_dir,
    )

    with open(
        args.ranges,
        "r",
        encoding="utf-8",
    ) as f:
        rd = json.load(f)

    ranges = rd[
        "statistics"
    ]

    classes = list(
        source["classes"]
    )

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

    full_model = (
        full_model.to(
            device
        )
    )

    # ----------------------------------
    # Stage3 baseline
    # ----------------------------------

    baseline = evaluate(
        full_model,
        loader,
        device,
    )

    # ----------------------------------
    # Install HLS-width activation fakeq
    # ----------------------------------

    manager = ActivationQuantManager(
        backbone,
        ranges,
        percentile_key="abs_p999",
    )

    manager.install()

    quant_top1 = evaluate(
        full_model,
        loader,
        device,
    )

    # ----------------------------------
    # Save scales
    # ----------------------------------

    report = {
        "stage3_top1":
            baseline,

        "activation_ptq_top1":
            quant_top1,

        "top1_drop_pp":
            baseline
            - quant_top1,

        "scope": {
            "ln1":
                "signed 3-bit",

            "q":
                "signed 3-bit",

            "k":
                "signed 3-bit",

            "v":
                "signed 3-bit",

            "attention_A":
                "signed 3-bit",

            "ln2":
                "signed 3-bit",

            "gelu":
                "unsigned 3-bit",

            "block_feature_map":
                "signed 13-bit",

            "softmax":
                "still floating-point",

            "layernorm_arithmetic":
                "still floating-point",

            "requant_lut":
                "not yet generated",
        },

        "activation_scales":
            manager.scales,
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

    with open(
        out /
        "activation_scales.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            manager.scales,
            f,
            indent=2,
        )

    print()
    print(
        "===== STAGE 4B: "
        "HLS ACTIVATION PTQ ====="
    )

    print(
        f"Stage3 Top-1          : "
        f"{baseline:.4f}%"
    )

    print(
        f"W3 + A3-boundary Top-1: "
        f"{quant_top1:.4f}%"
    )

    print(
        f"Activation drop       : "
        f"{baseline-quant_top1:.4f} pp"
    )

    print()
    print(
        "Representative scales:"
    )

    for b in [
        0,
        1,
        8,
        11,
    ]:

        print(
            f"Block {b}:",
            "LN1",
            manager.scales[
                f"b{b}.ln1_out"
            ]["scale"],

            "Q",
            manager.scales[
                f"b{b}.q_prequant"
            ]["scale"],

            "K",
            manager.scales[
                f"b{b}.k_prequant"
            ]["scale"],

            "V",
            manager.scales[
                f"b{b}.v_prequant"
            ]["scale"],

            "A",
            manager.scales[
                f"b{b}.attn_A_pre_proj"
            ]["scale"],

            "LN2",
            manager.scales[
                f"b{b}.ln2_out"
            ]["scale"],

            "GELU",
            manager.scales[
                f"b{b}.gelu_out"
            ]["scale"],
        )

    print()
    print(
        "Saved:",
        out / "report.json"
    )

    manager.remove()


if __name__ == "__main__":
    main()
