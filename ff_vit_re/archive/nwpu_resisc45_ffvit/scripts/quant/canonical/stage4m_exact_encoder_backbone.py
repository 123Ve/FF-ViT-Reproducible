#!/usr/bin/env python3
"""
Stage 4M: close the exact integer encoder backbone.

Starting point:
  Stage 4J trained checkpoint
  Stage 4K exact LN1
  Stage 4K2 refined Q/K/V quant.h LUTs
  Stage 4L exact fixed-point Softmax + AQ
  Stage 4F exact GELU LUT
  Stage 4D trained MLP boundary scales

This stage adds the missing HLS-consistent scale chain:
  * exact Attention residual RM/RS
  * Attention output scale is the O-projection int13 accumulator scale
  * refit exact LN2 at that fixed int15 input scale
  * exact MLP1 / GELU / MLP2
  * refit exact MLP residual RM/RS using the new Attention-output scale

The final block output is signed int13 in the MLP2 accumulator scale and
feeds the next block's exact LN1 input domain.

The classifier Head is intentionally still floating-point here. Therefore
the result is "exact encoder-backbone accuracy", not yet full-model
bit-accurate FPGA accuracy.
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
from stage4h_exact_layernorm_roundfix import (
    install_exact_gelu,
    wrap_signed,
    arshift,
)
from stage4i_exact_mlp import (
    fit_residual_scalar,
    quant_weight_int3,
    quant_bias,
)
from stage4k_exact_attention_outer import (
    install_exact_ln1,
    fit_fixed_scale_layernorm,
    quant_o_weight,
)
from stage4l_exact_softmax_aq import (
    ManifestDataset,
    exact_qkv_params,
    install_exact_qkv_and_cache,
    reshape_heads,
    softmax_hls,
    apply_aq,
)
from qat_weight3_hls196 import eval_transform


T = 196
H = 3
D = 64


class LN2Sampler:
    def __init__(self, tokens_per_block=4096, per_batch=64):
        self.tokens_per_block = int(tokens_per_block)
        self.per_batch = int(per_batch)
        self.x = {b: [] for b in range(12)}
        self.y = {b: [] for b in range(12)}

    def _count(self, d, b):
        return sum(t.shape[0] for t in d[b])

    def _take(self, x, room):
        x = x.detach().reshape(-1, x.shape[-1]).cpu()
        n = min(self.per_batch, room, x.shape[0])

        if n <= 0:
            return None

        if n == x.shape[0]:
            return x

        idx = torch.linspace(
            0,
            x.shape[0] - 1,
            steps=n,
        ).long()

        return x[idx]

    def add_input(self, b, x):
        room = self.tokens_per_block - self._count(self.x, b)
        take = self._take(x, room)
        if take is not None:
            self.x[b].append(take)

    def add_target(self, b, y, scale):
        room = self.tokens_per_block - self._count(self.y, b)
        take = self._take(y, room)

        if take is not None:
            q = torch.round(
                take / float(scale)
            ).to(torch.int64)

            q = torch.clamp(
                q,
                -4,
                3,
            )

            self.y[b].append(q)

    def done(self):
        for b in range(12):
            if self._count(self.x, b) < self.tokens_per_block:
                return False
            if self._count(self.y, b) < self.tokens_per_block:
                return False
        return True

    def get(self, b):
        x = torch.cat(
            self.x[b],
            dim=0,
        )[:self.tokens_per_block]

        y = torch.cat(
            self.y[b],
            dim=0,
        )[:self.tokens_per_block]

        return x, y


def load_softmax_block(stage4l_dir, b):
    d = Path(stage4l_dir)

    sc = np.load(
        d / "softmax_scalars.npy"
    )[b]

    exp_table = np.load(
        d / "softmax_exp_table.npy"
    )[b]

    recip_one = np.load(
        d / "softmax_recip_table_one.npy"
    )[b]

    recip_two_ext = np.load(
        d / "softmax_recip_table_two_int8.npy"
    )[b]

    aq_sc = np.load(
        d / "aq_scalars.npy"
    )[b]

    aq_table = np.load(
        d / "aq_table.npy"
    )[b]

    exp_fit = {
        "b1": int(sc[0]),
        "s1": int(sc[1]),
        "bound1": int(sc[2]),
        "table": exp_table,
    }

    recip_fit = {
        "b2_one": int(sc[3]),
        "s2_one": int(sc[4]),
        "bound2_one": int(sc[5]),
        "b2_two": int(sc[8]),
        "s2_two": int(sc[9]),
        "bound2_two": int(sc[10]),
        "table_one": recip_one,
        # Preserve the external int8 bit pattern as local ap_uint<8>.
        "table_two_uint8": recip_two_ext.view(np.uint8),
    }

    aq_fit = {
        "b": int(aq_sc[0]),
        "s": int(aq_sc[1]),
        "bound": int(aq_sc[2]),
        "table": aq_table,
    }

    return exp_fit, recip_fit, aq_fit


def install_exact_softmax_aq(
    backbone,
    attn_ctrl,
    qkv_cache,
    stage4l_dir,
):
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sa = float(
            attn_ctrl.a_scale(b)
            .detach()
            .cpu()
        )

        exp_fit, recip_fit, aq_fit = load_softmax_block(
            stage4l_dir,
            b,
        )

        def hook(
            module,
            inputs,
            b=b,
            sa=sa,
            exp_fit=exp_fit,
            recip_fit=recip_fit,
            aq_fit=aq_fit,
        ):
            cached = qkv_cache[b]

            if cached is None:
                raise RuntimeError(
                    f"Missing QKV cache for block {b}"
                )

            q_code, k_code, v_code = cached

            qh = reshape_heads(q_code)
            kh = reshape_heads(k_code)
            vh = reshape_heads(v_code)

            hls = softmax_hls(
                qh,
                kh,
                vh,
                exp_fit,
                recip_fit,
            )

            aq = apply_aq(
                hls["o_int11"],
                aq_fit,
            )

            a_flat = (
                aq.permute(0, 2, 1, 3)
                .contiguous()
                .view(
                    aq.shape[0],
                    T,
                    H * D,
                )
            )

            x = inputs[0]

            return (
                a_flat.to(x.dtype) * sa,
            )

        handles.append(
            block.attn.proj.register_forward_pre_hook(
                hook
            )
        )

    return handles


def prepare_exact_o(
    backbone,
    attn_ctrl,
    device,
):
    params = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sa = float(
            attn_ctrl.a_scale(b)
            .detach()
            .cpu()
        )

        qw, sw = quant_o_weight(
            block.attn.proj
        )

        so = sa * sw

        qb = quant_bias(
            block.attn.proj,
            so,
            13,
        )

        params.append({
            "sa": sa,
            "qw": qw.to(device),
            "qb": qb.to(device),
            "sw": sw,
            "so": so,
        })

    return params


def install_exact_o_and_cache(
    backbone,
    o_params,
):
    cache = [None] * 12
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]
        p = o_params[b]

        sa = p["sa"]
        so = p["so"]
        qw = p["qw"]
        qb = p["qb"]

        def hook(
            module,
            inputs,
            output,
            b=b,
            sa=sa,
            so=so,
            qw=qw,
            qb=qb,
        ):
            x = inputs[0]

            xi = torch.round(
                x / sa
            ).to(torch.int64)

            xi = torch.clamp(
                xi,
                -4,
                3,
            )

            acc = torch.matmul(
                xi.to(torch.float32),
                qw.t().to(torch.float32),
            )
            acc = torch.round(acc).to(torch.int64)
            acc = wrap_signed(
                acc + qb,
                13,
            )

            cache[b] = acc

            return (
                acc.to(x.dtype)
                * so
            )

        handles.append(
            block.attn.proj.register_forward_hook(
                hook
            )
        )

    return handles, cache


def collect_block_input_ranges(
    model,
    backbone,
    loader,
    device,
):
    mins = [
        10**18 for _ in range(12)
    ]
    maxs = [
        -(10**18) for _ in range(12)
    ]

    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        # At this point the block input is already fake-quantized to the
        # signed-int13 MLP2 scale by the Stage4D controller.
        def hook(module, inputs, b=b):
            x = inputs[0].detach()

            # The actual code scale will be supplied later.
            # Store real extrema for now.
            mins[b] = min(
                mins[b],
                float(x.min().cpu()),
            )
            maxs[b] = max(
                maxs[b],
                float(x.max().cpu()),
            )

        handles.append(
            block.norm1.register_forward_pre_hook(
                hook
            )
        )

    model.eval()

    with torch.inference_mode():
        for images, _ in loader:
            images = images.to(
                device,
                non_blocking=True,
            )
            _ = model(images)

    for h in handles:
        h.remove()

    return mins, maxs


def install_attention_input_cache(
    backbone,
):
    cache = [None] * 12
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        def hook(module, inputs, b=b):
            cache[b] = inputs[0]

        handles.append(
            block.norm1.register_forward_pre_hook(
                hook
            )
        )

    return handles, cache


def install_exact_attention_residual(
    backbone,
    residual_cache,
    o_cache,
    block_input_scales,
    o_scales,
    residual_params,
):
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sin = float(
            block_input_scales[b]
        )
        so = float(
            o_scales[b]
        )

        rp = residual_params[b]
        rm = int(rp["RM"])
        rs = int(rp["RS"])
        rb = int(rp["RB"])

        def hook(
            module,
            inputs,
            b=b,
            sin=sin,
            so=so,
            rm=rm,
            rs=rs,
            rb=rb,
        ):
            x_res = residual_cache[b]
            o_int13 = o_cache[b]

            if x_res is None:
                raise RuntimeError(
                    f"Missing Attention residual input for block {b}"
                )
            if o_int13 is None:
                raise RuntimeError(
                    f"Missing exact O int13 for block {b}"
                )

            x_int13 = torch.round(
                x_res / sin
            ).to(torch.int64)

            x_int13 = wrap_signed(
                x_int13,
                13,
            )

            scaled = arshift(
                x_int13 * rm + rb,
                rs,
            )

            # attn.h explicitly casts this term to __attn_of_t=ap_int<15>.
            scaled15 = wrap_signed(
                scaled,
                15,
            )

            out15 = wrap_signed(
                o_int13 + scaled15,
                15,
            )

            x = inputs[0]

            return (
                out15.to(x.dtype) * so,
            )

        # Registered after the Stage4J norm2-pre surrogate, so exact HLS
        # Attention residual output overrides it.
        handles.append(
            block.norm2.register_forward_pre_hook(
                hook
            )
        )

    return handles


def install_exact_ln2(
    backbone,
    mlp_ctrl,
    input_scales,
    scalars,
    lnw,
    lnb,
    rsqrt,
    device,
):
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sx = float(input_scales[b])
        sy = float(
            mlp_ctrl.ln2_scale(b)
            .detach()
            .cpu()
        )

        sc = scalars[b]

        c1m = int(sc[0])
        c1s = int(sc[1])
        bias = int(sc[2])
        s1 = int(sc[3])
        bound = int(sc[4])
        s2 = int(sc[5])

        w = torch.tensor(
            lnw[b].astype(np.int64),
            dtype=torch.int64,
            device=device,
        )

        bb = torch.tensor(
            lnb[b].astype(np.int64),
            dtype=torch.int64,
            device=device,
        )

        rt = torch.tensor(
            rsqrt[b].astype(np.int64),
            dtype=torch.int64,
            device=device,
        )

        def hook(
            module,
            inputs,
            output,
            sx=sx,
            sy=sy,
            c1m=c1m,
            c1s=c1s,
            bias=bias,
            s1=s1,
            bound=bound,
            s2=s2,
            w=w,
            bb=bb,
            rt=rt,
        ):
            x = inputs[0]

            qx = torch.round(
                x / sx
            ).to(torch.int64)

            qx = wrap_signed(
                qx,
                15,
            )

            acc = qx.sum(
                dim=-1
            )

            tmp = (
                acc * c1m
                + (1 << (c1s - 1))
            )
            tmp = wrap_signed(
                tmp,
                32,
            )

            mean = arshift(
                tmp,
                c1s,
            )

            diff = qx - mean.unsqueeze(-1)
            diff = wrap_signed(
                diff,
                15,
            )

            sum_sq = (
                qx * qx
            ).sum(dim=-1)

            var = (
                sum_sq
                - 2 * mean * acc
                + 192 * mean * mean
            )

            var = wrap_signed(
                var,
                36,
            )

            addr = arshift(
                var + bias,
                s1,
            )

            addr = torch.clamp(
                addr,
                0,
                bound,
            )

            rr = rt[addr]

            val = (
                diff
                * rr.unsqueeze(-1)
                * w
                + bb
            )

            val = wrap_signed(
                val,
                40,
            )

            rel = arshift(
                val,
                s2,
            )

            rel = wrap_signed(
                rel,
                32,
            )

            qy = torch.clamp(
                rel,
                -4,
                3,
            )

            return (
                qy.to(x.dtype)
                * sy
            )

        handles.append(
            block.norm2.register_forward_hook(
                hook
            )
        )

    return handles


def prepare_exact_mlp(
    backbone,
    mlp_ctrl,
    device,
):
    params = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sln = float(
            mlp_ctrl.ln2_scale(b)
            .detach()
            .cpu()
        )

        sge = float(
            mlp_ctrl.gelu_scale(b)
            .detach()
            .cpu()
        )

        sm1 = float(
            mlp_ctrl.m1_scale(b)
            .detach()
            .cpu()
        )

        sm2 = float(
            mlp_ctrl.m2_scale(b)
            .detach()
            .cpu()
        )

        qw1, _ = quant_weight_int3(
            block.mlp.fc1
        )
        qw2, _ = quant_weight_int3(
            block.mlp.fc2
        )

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

        params.append({
            "sln": sln,
            "sge": sge,
            "sm1": sm1,
            "sm2": sm2,
            "qw1": qw1.to(device),
            "qw2": qw2.to(device),
            "qb1": qb1.to(device),
            "qb2": qb2.to(device),
        })

    return params


def install_exact_mlp_mats(
    backbone,
    params,
):
    m2_cache = [None] * 12
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]
        p = params[b]

        sln = p["sln"]
        sge = p["sge"]
        sm1 = p["sm1"]
        sm2 = p["sm2"]

        qw1 = p["qw1"]
        qw2 = p["qw2"]
        qb1 = p["qb1"]
        qb2 = p["qb2"]

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
            acc = torch.round(
                acc
            ).to(torch.int64)

            acc = wrap_signed(
                acc + qb1,
                11,
            )

            return (
                acc.to(x.dtype)
                * sm1
            )

        handles.append(
            block.mlp.fc1.register_forward_hook(
                fc1_hook
            )
        )

        def fc2_hook(
            module,
            inputs,
            output,
            b=b,
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
            acc = torch.round(
                acc
            ).to(torch.int64)

            acc = wrap_signed(
                acc + qb2,
                13,
            )

            m2_cache[b] = acc

            return (
                acc.to(x.dtype)
                * sm2
            )

        handles.append(
            block.mlp.fc2.register_forward_hook(
                fc2_hook
            )
        )

    return handles, m2_cache


def install_mlp_residual_cache(
    backbone,
):
    cache = [None] * 12
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        def hook(module, inputs, b=b):
            cache[b] = inputs[0]

        # This is registered after exact Attention-residual pre-hook and
        # therefore sees the exact int15-domain Attention output.
        handles.append(
            block.norm2.register_forward_pre_hook(
                hook
            )
        )

    return handles, cache


def install_exact_mlp_residual(
    backbone,
    residual_cache,
    m2_cache,
    input_scales,
    params,
    residual_params,
):
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sin = float(
            input_scales[b]
        )
        sm2 = float(
            params[b]["sm2"]
        )

        rp = residual_params[b]

        rm = int(rp["RM"])
        rs = int(rp["RS"])
        rb = int(rp["RB"])

        def hook(
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
            m2_int = m2_cache[b]

            if x_res is None:
                raise RuntimeError(
                    f"Missing MLP residual input for block {b}"
                )
            if m2_int is None:
                raise RuntimeError(
                    f"Missing MLP2 int13 for block {b}"
                )

            x_int15 = torch.round(
                x_res / sin
            ).to(torch.int64)

            x_int15 = wrap_signed(
                x_int15,
                15,
            )

            scaled = arshift(
                x_int15 * rm + rb,
                rs,
            )

            # mlp.h explicitly casts scaled residual to __mlp_of_t=ap_int<13>.
            scaled13 = wrap_signed(
                scaled,
                13,
            )

            out13 = wrap_signed(
                m2_int + scaled13,
                13,
            )

            return (
                out13.to(output.dtype)
                * sm2
            )

        # Registered after Stage4D block-output surrogate; exact result wins.
        handles.append(
            block.register_forward_hook(
                hook
            )
        )

    return handles


@torch.inference_mode()
def evaluate(model, loader, device):
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
            (logits.argmax(1) == labels)
            .sum()
            .item()
        )
        total += int(labels.numel())

    return 100.0 * correct / total


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

    ap.add_argument("--manifest", required=True)
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--patch-scale", type=float, required=True)

    ap.add_argument(
        "--output",
        default="stage4m_exact_encoder",
    )

    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fit-tokens", type=int, default=4096)
    ap.add_argument("--tokens-per-batch", type=int, default=64)
    ap.add_argument("--max-residual-shift", type=int, default=20)

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

    full_model, backbone, source = rebuild_stage3_model(
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

    full_model.load_state_dict(
        ckpt["student_state"],
        strict=True,
    )

    mlp_ctrl.load_state_dict(
        ckpt["mlp_controller_state"],
        strict=True,
    )

    attn_out_old = (
        ckpt["attention_controller_state"]["attn_out_scale"]
        .detach()
        .cpu()
        .numpy()
    )

    attn_ctrl = AttentionActivationController(
        backbone,
        ranges,
        attn_out_old,
    )

    attn_ctrl.load_state_dict(
        ckpt["attention_controller_state"],
        strict=True,
    )

    full_model = full_model.to(device)
    mlp_ctrl = mlp_ctrl.to(device)
    attn_ctrl = attn_ctrl.to(device)

    mlp_ctrl.set_active(range(12))
    attn_ctrl.set_active(range(12))

    mlp_ctrl.install()
    attn_ctrl.install()

    classes = list(source["classes"])

    calib_ds = ManifestDataset(
        args.manifest,
        eval_transform(),
    )

    if list(calib_ds.classes) != classes:
        raise RuntimeError(
            "Calibration class ordering mismatch"
        )

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

    # ------------------------------------------------------------
    # Existing exact Attention operators.
    # ------------------------------------------------------------

    kdir = Path(args.stage4k_dir)

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

    ln1_handles = install_exact_ln1(
        backbone,
        attn_ctrl,
        ln1_input_scales,
        ln1_scalars,
        ln1_lnw,
        ln1_lnb,
        ln1_rsqrt,
        device,
    )

    qkv_meta = exact_qkv_params(
        backbone,
        attn_ctrl,
    )

    qkv_handles, qkv_cache, _ = install_exact_qkv_and_cache(
        backbone,
        qkv_meta,
        args.stage4k2_dir,
        device,
        collect=False,
    )

    softmax_handles = install_exact_softmax_aq(
        backbone,
        attn_ctrl,
        qkv_cache,
        args.stage4l_dir,
    )

    o_params = prepare_exact_o(
        backbone,
        attn_ctrl,
        device,
    )

    o_handles, o_cache = install_exact_o_and_cache(
        backbone,
        o_params,
    )

    # ------------------------------------------------------------
    # Block input scales:
    # Block0 = Patch int13 scale.
    # Block b>0 = previous exact MLP2 int13 scale.
    # ------------------------------------------------------------

    mlp_scales = mlp_ctrl.export_scales()

    block_input_scales = np.zeros(
        12,
        dtype=np.float64,
    )

    block_input_scales[0] = float(
        args.patch_scale
    )

    for b in range(1, 12):
        block_input_scales[b] = float(
            mlp_scales[str(b - 1)]["m2_int13_scale"]
        )

    o_scales = np.array(
        [p["so"] for p in o_params],
        dtype=np.float64,
    )

    # ------------------------------------------------------------
    # Fit exact Attention residual RM/RS.
    # HLS output scale is O-projection accumulator scale.
    # ------------------------------------------------------------

    # Use a short calibration pass to get actual block-input code ranges.
    real_min, real_max = collect_block_input_ranges(
        full_model,
        backbone,
        calib_loader,
        device,
    )

    attn_residual_params = []

    print()
    print("===== STAGE 4M: FIT ATTENTION RESIDUAL RM/RS =====")

    for b in range(12):
        sin = float(
            block_input_scales[b]
        )

        so = float(
            o_scales[b]
        )

        qmin = int(
            np.floor(
                real_min[b] / sin
            )
        )
        qmax = int(
            np.ceil(
                real_max[b] / sin
            )
        )

        qmin = max(qmin, -4096)
        qmax = min(qmax, 4095)

        rp = fit_residual_scalar(
            sin,
            so,
            qmin,
            qmax,
            max_shift=args.max_residual_shift,
        )

        attn_residual_params.append(
            rp
        )

        print(
            f"Block {b:2d}: "
            f"Sin={sin:.10g} "
            f"So={so:.10g} "
            f"ratio={sin/so:.6g} "
            f"RM={rp['RM']} RS={rp['RS']} "
            f"mis={100*rp['mismatch_rate']:.6f}% "
            f"maxerr={rp['max_abs_error']}"
        )

    attn_input_handles, attn_residual_cache = install_attention_input_cache(
        backbone
    )

    attn_residual_handles = install_exact_attention_residual(
        backbone,
        attn_residual_cache,
        o_cache,
        block_input_scales,
        o_scales,
        attn_residual_params,
    )

    exact_attn_residual_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Refit LN2 using the ACTUAL HLS Attention-output scale = So.
    # ------------------------------------------------------------

    sampler = LN2Sampler(
        tokens_per_block=args.fit_tokens,
        per_batch=args.tokens_per_batch,
    )

    sample_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sy = float(
            mlp_ctrl.ln2_scale(b)
            .detach()
            .cpu()
        )

        def pre_hook(
            module,
            inputs,
            b=b,
        ):
            sampler.add_input(
                b,
                inputs[0],
            )

        def post_hook(
            module,
            inputs,
            output,
            b=b,
            sy=sy,
        ):
            sampler.add_target(
                b,
                output,
                sy,
            )

        # Both are registered after exact Attention residual.
        sample_handles.append(
            block.norm2.register_forward_pre_hook(
                pre_hook
            )
        )

        sample_handles.append(
            block.norm2.register_forward_hook(
                post_hook
            )
        )

    full_model.eval()

    with torch.inference_mode():
        for step, (images, _) in enumerate(
            calib_loader,
            1,
        ):
            images = images.to(
                device,
                non_blocking=True,
            )

            _ = full_model(images)

            if sampler.done():
                print(
                    f"Collected {args.fit_tokens} LN2 tokens/block "
                    f"after calibration batch {step}"
                )
                break

            if step % 10 == 0:
                print(
                    f"LN2 calibration {step}/{len(calib_loader)}",
                    flush=True,
                )

    for h in sample_handles:
        h.remove()

    ln2_scalars = np.zeros(
        (12, 7),
        dtype=np.int32,
    )
    ln2_lnw = np.zeros(
        (12, 192),
        dtype=np.int32,
    )
    ln2_lnb = np.zeros(
        (12, 192),
        dtype=np.int64,
    )
    ln2_rsqrt = np.zeros(
        (12, 128),
        dtype=np.int32,
    )

    ln2_report = {}

    print()
    print("===== STAGE 4M: REFIT EXACT LN2 AT HLS ATTENTION SCALE =====")

    for b in range(12):
        x, yq = sampler.get(b)

        fit = fit_fixed_scale_layernorm(
            x,
            yq,
            float(o_scales[b]),
            float(backbone.vit.blocks[b].norm2.eps),
            input_bits=15,
        )

        ln2_scalars[b] = fit["scalars"]
        ln2_lnw[b] = fit["lnw"]
        ln2_lnb[b] = fit["lnb"]
        ln2_rsqrt[b] = fit["rsqrt_table"]

        ln2_report[str(b)] = {
            "input_int15_scale": float(
                o_scales[b]
            ),
            "ln_scalars": fit["scalars"].astype(int).tolist(),
            "stats": fit["stats"],
        }

        st = fit["stats"]

        print(
            f"Block {b:2d}: "
            f"Sx={o_scales[b]:.10g} "
            f"in=[{st['input_min']},{st['input_max']}] "
            f"LN mismatch={100*st['affine_mismatch_rate']:.4f}% "
            f"maxerr={st['affine_max_abs_code_error']}"
        )

    ln2_handles = install_exact_ln2(
        backbone,
        mlp_ctrl,
        o_scales,
        ln2_scalars,
        ln2_lnw,
        ln2_lnb,
        ln2_rsqrt,
        device,
    )

    exact_ln2_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Exact MLP1 / GELU / MLP2.
    # ------------------------------------------------------------

    gelu_handles = install_exact_gelu(
        backbone,
        mlp_ctrl,
        args.stage4f_dir,
        device,
    )

    mlp_params = prepare_exact_mlp(
        backbone,
        mlp_ctrl,
        device,
    )

    mlp_mat_handles, m2_cache = install_exact_mlp_mats(
        backbone,
        mlp_params,
    )

    # ------------------------------------------------------------
    # Refit MLP residual RM/RS with actual Attention-output scale So.
    # ------------------------------------------------------------

    mlp_residual_params = []

    print()
    print("===== STAGE 4M: REFIT MLP RESIDUAL RM/RS =====")

    for b in range(12):
        sin = float(
            o_scales[b]
        )

        sout = float(
            mlp_params[b]["sm2"]
        )

        # Use observed LN2 input integer range from refitting.
        st = ln2_report[str(b)]["stats"]

        qmin = int(st["input_min"])
        qmax = int(st["input_max"])

        rp = fit_residual_scalar(
            sin,
            sout,
            qmin,
            qmax,
            max_shift=args.max_residual_shift,
        )

        mlp_residual_params.append(
            rp
        )

        print(
            f"Block {b:2d}: "
            f"Sin={sin:.10g} "
            f"Sout={sout:.10g} "
            f"RM={rp['RM']} RS={rp['RS']} "
            f"mis={100*rp['mismatch_rate']:.6f}% "
            f"maxerr={rp['max_abs_error']}"
        )

    mlp_resi_cache_handles, mlp_residual_cache = install_mlp_residual_cache(
        backbone
    )

    mlp_residual_handles = install_exact_mlp_residual(
        backbone,
        mlp_residual_cache,
        m2_cache,
        o_scales,
        mlp_params,
        mlp_residual_params,
    )

    exact_encoder_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Export artifacts.
    # ------------------------------------------------------------

    attn_scalars = np.zeros(
        (12, 3),
        dtype=np.int32,
    )

    mlp_scalars = np.zeros(
        (12, 2),
        dtype=np.int32,
    )

    for b in range(12):
        attn_scalars[b, 0] = int(
            attn_residual_params[b]["RM"]
        )
        attn_scalars[b, 1] = int(
            attn_residual_params[b]["RS"]
        )
        # active attn.h currently loads only [0] and [1]
        attn_scalars[b, 2] = 0

        mlp_scalars[b, 0] = int(
            mlp_residual_params[b]["RM"]
        )
        mlp_scalars[b, 1] = int(
            mlp_residual_params[b]["RS"]
        )

    np.save(
        out / "attn_scalars.npy",
        attn_scalars,
    )

    np.save(
        out / "ln2_input_scales.npy",
        o_scales,
    )

    np.save(
        out / "ln2_scalars.npy",
        ln2_scalars,
    )

    np.save(
        out / "ln2_lnw.npy",
        ln2_lnw,
    )

    np.save(
        out / "ln2_lnb.npy",
        ln2_lnb,
    )

    np.save(
        out / "ln2_rsqrt_table.npy",
        ln2_rsqrt,
    )

    np.save(
        out / "mlp_scalars.npy",
        mlp_scalars,
    )

    report = {
        "scope": (
            "All 12 encoder blocks use exact HLS-aligned Attention "
            "LN1/QKV/Softmax/AQ/O/residual and exact MLP "
            "LN2/MLP1/GELU/MLP2/residual. Head remains floating point."
        ),

        "exact_attention_plus_surrogate_mlp_val_top1": (
            exact_attn_residual_val
        ),

        "exact_attention_plus_exact_ln2_val_top1": (
            exact_ln2_val
        ),

        "exact_encoder_backbone_val_top1": (
            exact_encoder_val
        ),

        "block_input_int13_scales": (
            block_input_scales.tolist()
        ),

        "attention_output_int15_scales": (
            o_scales.tolist()
        ),

        "old_stage4j_attention_output_scales": (
            attn_out_old.tolist()
        ),

        "attn_scalars": (
            attn_scalars.astype(int).tolist()
        ),

        "mlp_scalars": (
            mlp_scalars.astype(int).tolist()
        ),

        "ln2": ln2_report,

        "attention_residual_fit": {
            str(b): attn_residual_params[b]
            for b in range(12)
        },

        "mlp_residual_fit": {
            str(b): mlp_residual_params[b]
            for b in range(12)
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
        )

    print()
    print("===== STAGE 4M: EXACT ENCODER BACKBONE =====")
    print(
        f"Exact Attention residual + surrogate MLP : "
        f"{exact_attn_residual_val:.4f}%"
    )
    print(
        f"+ exact refit LN2                     : "
        f"{exact_ln2_val:.4f}%"
    )
    print(
        f"+ exact full MLP / full encoder       : "
        f"{exact_encoder_val:.4f}%"
    )
    print("Report:", out / "report.json")
    print("Attention scalars:", out / "attn_scalars.npy")
    print("MLP scalars:", out / "mlp_scalars.npy")

    for h in mlp_residual_handles:
        h.remove()
    for h in mlp_resi_cache_handles:
        h.remove()
    for h in mlp_mat_handles:
        h.remove()
    for h in gelu_handles:
        h.remove()
    for h in ln2_handles:
        h.remove()
    for h in attn_residual_handles:
        h.remove()
    for h in attn_input_handles:
        h.remove()
    for h in o_handles:
        h.remove()
    for h in softmax_handles:
        h.remove()
    for h in qkv_handles:
        h.remove()
    for h in ln1_handles:
        h.remove()

    attn_ctrl.remove()
    mlp_ctrl.remove()


if __name__ == "__main__":
    main()
