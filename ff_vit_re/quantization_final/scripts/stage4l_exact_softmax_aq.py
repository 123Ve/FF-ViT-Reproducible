#!/usr/bin/env python3
"""
Stage 4L: exact fixed-point row-wise Softmax + AQ for FF-ViT.

Reuses:
  * Stage4K exact LN1
  * Stage4K2 refined exact Q/K/V MAC + quant.h LUTs
  * exact W3 O int13 projection

Fits per block:
  softmax_scalars[14]
  softmax_exp_table[32]          uint16
  softmax_recip_table_one[64]    uint8
  softmax_recip_table_two[64]    external int8 -> local ap_uint<8>
  aq_scalars[4]
  aq_table[64]                   signed int3 values stored as int8

Exact active fused_flash_attn.h arithmetic modeled:
  score = sum(q_int3 * k_int3)
  minus = ap_int<11>(row_max - score)
  exp_cursor = ap_uint<8>((minus+b1)>>s1), then clamp
  exp = table32[cursor]
  acc = ap_uint<23>(sum(exp))
  piecewise reciprocal through uint9 / int7 cursors
  affine = ap_uint<23>(exp * recip_uint8)
  rq = unsigned clamp((affine+b3)>>s3, clamp_bits)
  O_acc = sum(rq * v_int3)
  A_raw = ap_int<11>(O_acc)
  AQ uses quant.h: int10 cursor wrap BEFORE clamp -> LUT64 -> signed int3

The fitted normalized weight domain uses clamp_bits=8 and a nominal
weight scale of 256 codes per probability unit. AQ is fit directly from
the actual HLS A_raw code to the Stage4J A signed-int3 target, so it can
absorb residual fixed-point normalization error.

Attention residual output remains the Stage4J int15 surrogate in this
stage. The next stage can fit exact Attention RM/RS after Softmax/AQ is
frozen.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import datasets

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from stage4j_attention_activation_qat import AttentionActivationController
from stage4k_exact_attention_outer import (
    install_exact_ln1,
    quant_qkv_weights,
    quant_qkv_biases,
    quant_o_weight,
    quant_bias,
    apply_quant_lut_torch,
)
from stage4h_exact_layernorm_roundfix import (
    wrap_signed,
    arshift,
)
from qat_weight3_hls196 import eval_transform


T = 196
H = 3
D = 64

EXP_SCALE = 4096
WEIGHT_SCALE = 256
SOFTMAX_SHIFT3 = 11
SOFTMAX_B3 = 1 << (SOFTMAX_SHIFT3 - 1)
SOFTMAX_CLAMP_BITS = 8


class ManifestDataset(Dataset):
    def __init__(self, manifest_path, transform):
        with open(manifest_path, "r", encoding="utf-8") as f:
            d = json.load(f)

        self.samples = d["samples"]
        self.classes = d["classes"]
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        img = Image.open(item["path"]).convert("RGB")
        return self.transform(img), int(item["class_index"])


def balanced_subset(ds, n):
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


def np_wrap_signed(x, bits):
    mod = 1 << bits
    half = 1 << (bits - 1)
    return ((x + half) % mod) - half


def np_wrap_unsigned(x, bits):
    return x % (1 << bits)


def exact_qkv_params(backbone, attn_ctrl):
    meta = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sln = float(
            attn_ctrl.ln1_scale(b)
            .detach()
            .cpu()
        )

        out_scales = [
            float(attn_ctrl.q_scale(b).detach().cpu()),
            float(attn_ctrl.k_scale(b).detach().cpu()),
            float(attn_ctrl.v_scale(b).detach().cpu()),
        ]

        qws, sws = quant_qkv_weights(
            block.attn.qkv
        )

        acc_scales = [
            sln * sws[0],
            sln * sws[1],
            sln * sws[2],
        ]

        qbs = quant_qkv_biases(
            block.attn.qkv,
            acc_scales,
            bits=(12, 11, 11),
        )

        meta.append({
            "sln": sln,
            "qws": qws,
            "qbs": qbs,
            "out_scales": out_scales,
        })

    return meta


def install_exact_qkv_and_cache(
    backbone,
    qkv_meta,
    stage4k2_dir,
    device,
    collect=False,
):
    d = Path(stage4k2_dir)

    qsc = np.load(d / "qq_scalars.npy")
    ksc = np.load(d / "kq_scalars.npy")
    vsc = np.load(d / "vq_scalars.npy")

    qt = np.load(d / "qq_table.npy")
    kt = np.load(d / "kq_table.npy")
    vt = np.load(d / "vq_table.npy")

    cache = [None] * 12
    collected = {
        b: {"q": [], "k": [], "v": []}
        for b in range(12)
    }

    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]
        m = qkv_meta[b]

        sln = m["sln"]

        qws = [
            x.to(device)
            for x in m["qws"]
        ]
        qbs = [
            x.to(device)
            for x in m["qbs"]
        ]

        scales = [
            qsc[b],
            ksc[b],
            vsc[b],
        ]

        tables = [
            torch.tensor(
                qt[b].astype(np.int64),
                device=device,
            ),
            torch.tensor(
                kt[b].astype(np.int64),
                device=device,
            ),
            torch.tensor(
                vt[b].astype(np.int64),
                device=device,
            ),
        ]

        out_scales = m["out_scales"]

        def hook(
            module,
            inputs,
            output,
            b=b,
            sln=sln,
            qws=qws,
            qbs=qbs,
            scales=scales,
            tables=tables,
            out_scales=out_scales,
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

            codes = []
            reals = []

            for qw, qb, bits, sc, tab, so in zip(
                qws,
                qbs,
                (12, 11, 11),
                scales,
                tables,
                out_scales,
            ):
                acc = torch.matmul(
                    xi.to(torch.float32),
                    qw.t().to(torch.float32),
                )
                acc = torch.round(acc).to(torch.int64)
                acc = acc + qb
                acc = wrap_signed(
                    acc,
                    bits,
                )

                qy = apply_quant_lut_torch(
                    acc,
                    sc,
                    tab,
                    cursor_bits=9,
                )

                qy = wrap_signed(
                    qy,
                    3,
                )

                codes.append(qy)
                reals.append(
                    qy.to(x.dtype) * float(so)
                )

            cache[b] = tuple(codes)

            if collect:
                for name, qy in zip(
                    ("q", "k", "v"),
                    codes,
                ):
                    collected[b][name].append(
                        qy.detach()
                        .to(torch.int8)
                        .cpu()
                    )

            return torch.cat(
                reals,
                dim=-1,
            )

        handles.append(
            block.attn.qkv.register_forward_hook(
                hook
            )
        )

    return handles, cache, collected


def reshape_heads(x):
    # [B,T,192] -> [B,H,T,D], contiguous head channel groups.
    B = x.shape[0]

    return (
        x.view(B, T, H, D)
        .permute(0, 2, 1, 3)
        .contiguous()
    )


def fit_exp_lut(q, k, q_scale, k_scale, attn_scale, max_shift=8):
    qf = q.to(torch.float32)
    kf = k.to(torch.float32)

    scores = torch.matmul(
        qf,
        kf.transpose(-1, -2),
    ).round().to(torch.int64)

    row_max = scores.max(dim=-1, keepdim=True).values
    diff_pre = row_max - scores

    minus_over = (
        (diff_pre < -1024)
        | (diff_pre > 1023)
    )

    diff = wrap_signed(
        diff_pre,
        11,
    )

    # For fitting the exponential approximation, use the ideal float score
    # represented by the exact Q/K integer codes.
    lam = float(q_scale) * float(k_scale) * float(attn_scale)

    target_exp = torch.exp(
        -diff_pre.to(torch.float64) * lam
    )

    target_code = torch.round(
        target_exp * EXP_SCALE
    )
    target_code = torch.clamp(
        target_code,
        0,
        65535,
    ).to(torch.int64)

    d = diff.reshape(-1).cpu().numpy()
    y = target_code.reshape(-1).cpu().numpy()

    # Pair histogram by signed int11 difference code and target code mean.
    # Because target is deterministic in diff_pre when no minus overflow,
    # weighted mean per address is sufficient.
    code_vals = np.arange(-1024, 1024, dtype=np.int64)
    counts = np.bincount(
        d + 1024,
        minlength=2048,
    ).astype(np.int64)

    sums = np.bincount(
        d + 1024,
        weights=y.astype(np.float64),
        minlength=2048,
    )

    mask = counts > 0
    xs = code_vals[mask]
    cnt = counts[mask].astype(np.float64)
    mean_y = sums[mask] / cnt

    best = None

    for s in range(int(max_shift) + 1):
        step = 1 << s

        # diff should be nonnegative in normal operation. Search address phase
        # so low differences get the finest available resolution.
        for phase in range(step):
            b = int(phase)

            tmp = (xs + b) // step

            # fused source casts to ap_uint<8> before clamp.
            cur = np_wrap_unsigned(
                tmp,
                8,
            )

            addr = np.clip(
                cur,
                0,
                31,
            ).astype(np.int64)

            table = np.zeros(32, dtype=np.int64)

            used = np.unique(addr)

            for a in used:
                m = addr == a
                table[a] = int(
                    np.clip(
                        np.rint(
                            np.sum(
                                cnt[m] * mean_y[m]
                            )
                            / np.sum(cnt[m])
                        ),
                        0,
                        65535,
                    )
                )

            if used.size:
                for a in range(32):
                    if a not in used:
                        nearest = used[
                            np.argmin(
                                np.abs(used - a)
                            )
                        ]
                        table[a] = table[nearest]

            pred = table[addr].astype(np.float64)
            err = pred - mean_y

            mse = float(
                np.sum(
                    cnt * (err ** 2)
                )
                / np.sum(cnt)
            )

            # Normalized error is more meaningful across layers.
            nmse = mse / max(float(EXP_SCALE ** 2), 1.0)

            wrap_rate = float(
                minus_over.to(torch.float32)
                .mean()
                .item()
            )

            cand = {
                "b1": b,
                "s1": s,
                "bound1": 31,
                "table": table.astype(np.uint16),
                "nmse": nmse,
                "minus_overflow_rate": wrap_rate,
                "lambda": lam,
            }

            key = (
                nmse,
                s,
                phase,
            )

            if best is None:
                best = cand
            else:
                bkey = (
                    best["nmse"],
                    best["s1"],
                    best["b1"],
                )
                if key < bkey:
                    best = cand

    return best, scores, diff_pre


def apply_exp(scores, fit):
    row_max = scores.max(
        dim=-1,
        keepdim=True,
    ).values

    diff = wrap_signed(
        row_max - scores,
        11,
    )

    tmp = arshift(
        diff + int(fit["b1"]),
        int(fit["s1"]),
    )

    cur = torch.remainder(
        tmp,
        256,
    )

    addr = torch.clamp(
        cur,
        0,
        int(fit["bound1"]),
    )

    tab = torch.tensor(
        fit["table"].astype(np.int64),
        device=scores.device,
    )

    return tab[addr]


def fit_recip_tables(acc):
    a = acc.detach().cpu().numpy().reshape(-1).astype(np.int64)

    # Desired local uint8 reciprocal code for the fixed shift-3 convention.
    target = np.rint(
        (WEIGHT_SCALE * (1 << SOFTMAX_SHIFT3))
        / np.maximum(a.astype(np.float64), 1.0)
    ).astype(np.int64)

    target = np.clip(
        target,
        0,
        255,
    )

    amin = int(a.min())
    amax = int(a.max())

    quantiles = [
        0.25,
        0.40,
        0.50,
        0.60,
        0.75,
    ]

    best = None

    for qtile in quantiles:
        thr = int(
            np.quantile(
                a,
                qtile,
            )
        )

        span1 = max(
            thr - amin + 1,
            1,
        )
        span2 = max(
            amax - thr + 1,
            1,
        )

        base_s1 = max(
            0,
            int(
                math.ceil(
                    math.log2(
                        span1 / 64.0
                    )
                )
            ),
        )

        base_s2 = max(
            0,
            int(
                math.ceil(
                    math.log2(
                        span2 / 64.0
                    )
                )
            ),
        )

        for s_one in range(
            max(0, base_s1 - 2),
            base_s1 + 3,
        ):
            step1 = 1 << s_one

            for ph1 in {
                0,
                step1 // 2,
                step1 - 1,
            }:
                # small-acc region starts around address 0
                b_one = -amin + int(ph1)

                c1_raw = (a + b_one) // step1
                c1 = np_wrap_unsigned(
                    c1_raw,
                    9,
                )

                region_one = c1 <= 63

                # Require a meaningful piecewise split.
                frac1 = float(
                    np.mean(region_one)
                )
                if frac1 < 0.05 or frac1 > 0.95:
                    continue

                for s_two in range(
                    max(0, base_s2 - 2),
                    base_s2 + 3,
                ):
                    step2 = 1 << s_two

                    for ph2 in {
                        0,
                        step2 // 2,
                        step2 - 1,
                    }:
                        b_two = -thr + int(ph2)

                        c2_raw = (
                            a + b_two
                        ) // step2

                        c2 = np_wrap_signed(
                            c2_raw,
                            7,
                        )

                        addr1 = np.clip(
                            c1,
                            0,
                            63,
                        ).astype(np.int64)

                        addr2 = np.clip(
                            c2,
                            0,
                            63,
                        ).astype(np.int64)

                        tab1 = np.zeros(
                            64,
                            dtype=np.int64,
                        )
                        tab2 = np.zeros(
                            64,
                            dtype=np.int64,
                        )

                        used1 = np.unique(
                            addr1[region_one]
                        )
                        used2 = np.unique(
                            addr2[~region_one]
                        )

                        for ad in used1:
                            m = (
                                region_one
                                & (addr1 == ad)
                            )
                            tab1[ad] = int(
                                np.clip(
                                    np.rint(
                                        np.mean(
                                            target[m]
                                        )
                                    ),
                                    0,
                                    255,
                                )
                            )

                        for ad in used2:
                            m = (
                                (~region_one)
                                & (addr2 == ad)
                            )
                            tab2[ad] = int(
                                np.clip(
                                    np.rint(
                                        np.mean(
                                            target[m]
                                        )
                                    ),
                                    0,
                                    255,
                                )
                            )

                        if used1.size:
                            for ad in range(64):
                                if ad not in used1:
                                    nearest = used1[
                                        np.argmin(
                                            np.abs(
                                                used1 - ad
                                            )
                                        )
                                    ]
                                    tab1[ad] = tab1[
                                        nearest
                                    ]

                        if used2.size:
                            for ad in range(64):
                                if ad not in used2:
                                    nearest = used2[
                                        np.argmin(
                                            np.abs(
                                                used2 - ad
                                            )
                                        )
                                    ]
                                    tab2[ad] = tab2[
                                        nearest
                                    ]

                        pred = np.where(
                            region_one,
                            tab1[addr1],
                            tab2[addr2],
                        )

                        err = pred - target

                        mse = float(
                            np.mean(
                                err.astype(np.float64) ** 2
                            )
                        )

                        maxerr = int(
                            np.max(
                                np.abs(err)
                            )
                        )

                        # Address-wrap diagnostics.
                        wrap1 = float(
                            np.mean(
                                (c1_raw < 0)
                                | (c1_raw > 511)
                            )
                        )

                        wrap2 = float(
                            np.mean(
                                (c2_raw < -64)
                                | (c2_raw > 63)
                            )
                        )

                        cand = {
                            "b2_one": int(b_one),
                            "s2_one": int(s_one),
                            "bound2_one": 63,
                            "b2_two": int(b_two),
                            "s2_two": int(s_two),
                            "bound2_two": 63,
                            "table_one": tab1.astype(np.uint8),
                            "table_two_uint8": tab2.astype(np.uint8),
                            "mse": mse,
                            "maxerr": maxerr,
                            "region_one_fraction": frac1,
                            "cursor_one_wrap_rate": wrap1,
                            "cursor_two_wrap_rate": wrap2,
                            "acc_min": amin,
                            "acc_max": amax,
                        }

                        key = (
                            mse,
                            maxerr,
                            wrap1 + wrap2,
                        )

                        if best is None:
                            best = cand
                        else:
                            bkey = (
                                best["mse"],
                                best["maxerr"],
                                best["cursor_one_wrap_rate"]
                                + best["cursor_two_wrap_rate"],
                            )
                            if key < bkey:
                                best = cand

    if best is None:
        raise RuntimeError(
            "Could not fit piecewise reciprocal tables"
        )

    return best


def apply_recip(acc, fit):
    # cursor_one: ap_uint<9>, then compare to bound before clamp.
    raw1 = arshift(
        acc + int(fit["b2_one"]),
        int(fit["s2_one"]),
    )

    cur1 = torch.remainder(
        raw1,
        512,
    )

    region_two = (
        cur1 > int(fit["bound2_one"])
    )

    addr1 = torch.clamp(
        cur1,
        0,
        int(fit["bound2_one"]),
    )

    # cursor_two: ap_int<7>, then clamp.
    raw2 = arshift(
        acc + int(fit["b2_two"]),
        int(fit["s2_two"]),
    )

    cur2 = wrap_signed(
        raw2,
        7,
    )

    addr2 = torch.clamp(
        cur2,
        0,
        int(fit["bound2_two"]),
    )

    tab1 = torch.tensor(
        fit["table_one"].astype(np.int64),
        device=acc.device,
    )

    tab2 = torch.tensor(
        fit["table_two_uint8"].astype(np.int64),
        device=acc.device,
    )

    r1 = tab1[addr1]
    r2 = tab2[addr2]

    recip = torch.where(
        region_two,
        r2,
        r1,
    )

    return recip, region_two


def softmax_hls(q, k, v, exp_fit, recip_fit):
    qf = q.to(torch.float32)
    kf = k.to(torch.float32)

    scores = torch.matmul(
        qf,
        kf.transpose(-1, -2),
    ).round().to(torch.int64)

    expv = apply_exp(
        scores,
        exp_fit,
    )

    # HLS acc is ap_uint<23>.
    acc = torch.sum(
        expv,
        dim=-1,
    )
    acc = torch.remainder(
        acc,
        1 << 23,
    )

    recip, region_two = apply_recip(
        acc,
        recip_fit,
    )

    # val is ap_uint<23>.
    val = expv * recip.unsqueeze(-1)
    val = torch.remainder(
        val,
        1 << 23,
    )

    rq = arshift(
        val + SOFTMAX_B3,
        SOFTMAX_SHIFT3,
    )

    rq = torch.clamp(
        rq,
        0,
        (1 << SOFTMAX_CLAMP_BITS) - 1,
    )

    # Long-long O_acc; float32 matmul is exact here for the reachable
    # integer magnitudes and is much faster on GPU.
    o_pre = torch.matmul(
        rq.to(torch.float32),
        v.to(torch.float32),
    )
    o_pre = torch.round(
        o_pre
    ).to(torch.int64)

    # WRITE stage casts long long O_acc -> ap_int<11>.
    o_int11 = wrap_signed(
        o_pre,
        11,
    )

    return {
        "scores": scores,
        "exp": expv,
        "acc": acc,
        "recip": recip,
        "region_two": region_two,
        "rq": rq,
        "o_pre": o_pre,
        "o_int11": o_int11,
    }


def fit_aq_lut(pair_counts, max_shift=10):
    # pair_counts[x_code+1024, target_code+4]
    totals = pair_counts.sum(axis=1)
    xs_all = np.arange(
        -1024,
        1024,
        dtype=np.int64,
    )

    mask = totals > 0
    xs = xs_all[mask]
    pc = pair_counts[mask].astype(np.int64)

    modal = np.argmax(
        pc,
        axis=1,
    ) - 4

    moving = (
        (modal > -4)
        & (modal < 3)
    )

    if np.any(moving):
        xlo = int(xs[moving].min())
    else:
        xlo = int(xs.min())

    best = None

    for s in range(int(max_shift) + 1):
        step = 1 << s

        for offset in (0, 1, 2, 4, 8):
            base = (
                (1 + offset) * step
                - xlo
            )

            for phase in range(step):
                b = int(base + phase)

                raw = (
                    xs + b
                ) // step

                # quant.h AQ cursor is ap_int<10> before clamp.
                cur = np_wrap_signed(
                    raw,
                    10,
                )

                addr = np.clip(
                    cur,
                    0,
                    63,
                ).astype(np.int64)

                table = np.zeros(
                    64,
                    dtype=np.int64,
                )

                total_correct = 0

                used = np.unique(addr)

                for ad in used:
                    rows = (
                        addr == ad
                    )

                    agg = pc[rows].sum(
                        axis=0
                    )

                    y_idx = int(
                        np.argmax(agg)
                    )

                    table[ad] = y_idx - 4
                    total_correct += int(
                        agg[y_idx]
                    )

                if used.size:
                    for ad in range(64):
                        if ad not in used:
                            nearest = used[
                                np.argmin(
                                    np.abs(
                                        used - ad
                                    )
                                )
                            ]
                            table[ad] = table[
                                nearest
                            ]

                total = int(
                    pc.sum()
                )

                mismatch = (
                    1.0
                    - total_correct
                    / max(total, 1)
                )

                wrap_rate = float(
                    np.sum(
                        totals[mask]
                        * (
                            (raw < -512)
                            | (raw > 511)
                        )
                    )
                    / max(
                        np.sum(
                            totals[mask]
                        ),
                        1,
                    )
                )

                cand = {
                    "b": b,
                    "s": s,
                    "bound": 63,
                    "reserved": 0,
                    "table": table.astype(np.int8),
                    "mismatch_rate": float(mismatch),
                    "cursor_wrap_rate": wrap_rate,
                }

                key = (
                    mismatch,
                    wrap_rate,
                    s,
                )

                if best is None:
                    best = cand
                else:
                    bkey = (
                        best["mismatch_rate"],
                        best["cursor_wrap_rate"],
                        best["s"],
                    )
                    if key < bkey:
                        best = cand

    return best


def apply_aq(o_int11, fit):
    raw = arshift(
        o_int11 + int(fit["b"]),
        int(fit["s"]),
    )

    cur = wrap_signed(
        raw,
        10,
    )

    addr = torch.clamp(
        cur,
        0,
        int(fit["bound"]),
    )

    tab = torch.tensor(
        fit["table"].astype(np.int64),
        device=o_int11.device,
    )

    y = tab[addr]
    return wrap_signed(y, 3)


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
    ap.add_argument("--stage4k-dir", required=True)
    ap.add_argument("--stage4k2-dir", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--data-root", required=True)

    ap.add_argument(
        "--output",
        default="stage4l_exact_softmax_aq",
    )

    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fit-images", type=int, default=256)
    ap.add_argument("--exp-max-shift", type=int, default=8)
    ap.add_argument("--aq-max-shift", type=int, default=10)

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

    attn_out_scale = (
        ckpt["attention_controller_state"][
            "attn_out_scale"
        ]
        .detach()
        .cpu()
        .numpy()
    )

    attn_ctrl = AttentionActivationController(
        backbone,
        ranges,
        attn_out_scale,
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

    # Exact LN1 from Stage4K.
    kdir = Path(args.stage4k_dir)

    ln_input_scales = np.load(
        kdir / "ln1_input_scales.npy"
    )
    ln_scalars = np.load(
        kdir / "ln1_scalars.npy"
    )
    ln_lnw = np.load(
        kdir / "ln1_lnw.npy"
    )
    ln_lnb = np.load(
        kdir / "ln1_lnb.npy"
    )
    ln_rsqrt = np.load(
        kdir / "ln1_rsqrt_table.npy"
    )

    ln_handles = install_exact_ln1(
        backbone,
        attn_ctrl,
        ln_input_scales,
        ln_scalars,
        ln_lnw,
        ln_lnb,
        ln_rsqrt,
        device,
    )

    qkv_meta = exact_qkv_params(
        backbone,
        attn_ctrl,
    )

    # Collect exact Q/K/V integer codes on a deterministic, spread-out
    # train-only calibration subset.
    calib_base = ManifestDataset(
        args.manifest,
        eval_transform(),
    )

    if list(calib_base.classes) != classes:
        raise RuntimeError(
            "Calibration class ordering mismatch"
        )

    calib_ds = balanced_subset(
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

    qkv_handles, qkv_cache, collected = install_exact_qkv_and_cache(
        backbone,
        qkv_meta,
        args.stage4k2_dir,
        device,
        collect=True,
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

            if step % 10 == 0 or step == len(calib_loader):
                print(
                    f"Collect QKV {step}/{len(calib_loader)}",
                    flush=True,
                )

    q_all = []
    k_all = []
    v_all = []

    for b in range(12):
        q_all.append(
            torch.cat(
                collected[b]["q"],
                dim=0,
            )
        )
        k_all.append(
            torch.cat(
                collected[b]["k"],
                dim=0,
            )
        )
        v_all.append(
            torch.cat(
                collected[b]["v"],
                dim=0,
            )
        )

    # Validation set.
    val_ds = datasets.ImageFolder(
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

    # Exact O hook, reused for both baseline and final exact-Softmax eval.
    o_handles = []

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

        qw = qw.to(device)
        qb = qb.to(device)

        def o_hook(
            module,
            inputs,
            output,
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
            acc = torch.round(
                acc
            ).to(torch.int64)

            acc = wrap_signed(
                acc + qb,
                13,
            )

            return (
                acc.to(x.dtype)
                * so
            )

        o_handles.append(
            block.attn.proj.register_forward_hook(
                o_hook
            )
        )

    # This should reproduce Stage4K2's refined-QKV + exact-O condition.
    baseline_outer_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Fit per-layer fixed-point Softmax and AQ.
    # ------------------------------------------------------------

    softmax_scalars = np.zeros(
        (12, 14),
        dtype=np.int32,
    )

    exp_tables = np.zeros(
        (12, 32),
        dtype=np.uint16,
    )

    recip_one = np.zeros(
        (12, 64),
        dtype=np.uint8,
    )

    # Store external int8 representation; local hardware sees ap_uint<8>.
    recip_two_ext = np.zeros(
        (12, 64),
        dtype=np.int8,
    )

    aq_scalars = np.zeros(
        (12, 4),
        dtype=np.int32,
    )

    aq_tables = np.zeros(
        (12, 64),
        dtype=np.int8,
    )

    fits = {}

    print()
    print("===== STAGE 4L: FIT SOFTMAX + AQ =====")

    for b in range(12):
        q = reshape_heads(
            q_all[b].to(torch.int64)
        )
        k = reshape_heads(
            k_all[b].to(torch.int64)
        )
        v = reshape_heads(
            v_all[b].to(torch.int64)
        )

        sq = float(
            attn_ctrl.q_scale(b)
            .detach()
            .cpu()
        )
        sk = float(
            attn_ctrl.k_scale(b)
            .detach()
            .cpu()
        )
        sv = float(
            attn_ctrl.v_scale(b)
            .detach()
            .cpu()
        )
        sa = float(
            attn_ctrl.a_scale(b)
            .detach()
            .cpu()
        )

        attn_scale = float(
            backbone.vit.blocks[b].attn.scale
        )

        # DeiT-Tiny default q_norm/k_norm are Identity.
        qn = backbone.vit.blocks[b].attn.q_norm
        kn = backbone.vit.blocks[b].attn.k_norm

        if qn.__class__.__name__ != "Identity":
            raise RuntimeError(
                f"Block {b}: q_norm is not Identity"
            )
        if kn.__class__.__name__ != "Identity":
            raise RuntimeError(
                f"Block {b}: k_norm is not Identity"
            )

        exp_fit, scores, diff_pre = fit_exp_lut(
            q,
            k,
            sq,
            sk,
            attn_scale,
            max_shift=args.exp_max_shift,
        )

        expv = apply_exp(
            scores,
            exp_fit,
        )

        acc = torch.sum(
            expv,
            dim=-1,
        )
        acc = torch.remainder(
            acc,
            1 << 23,
        )

        recip_fit = fit_recip_tables(
            acc
        )

        hls = softmax_hls(
            q,
            k,
            v,
            exp_fit,
            recip_fit,
        )

        # Ideal Stage4J A target from exact Q/K/V signed3 codes.
        real_scores = (
            scores.to(torch.float64)
            * sq
            * sk
            * attn_scale
        )

        p = torch.softmax(
            real_scores,
            dim=-1,
        )

        a_real = torch.matmul(
            p,
            v.to(torch.float64) * sv,
        )

        a_target = torch.round(
            a_real / sa
        ).to(torch.int64)

        a_target = torch.clamp(
            a_target,
            -4,
            3,
        )

        # Build exact AQ input/target joint histogram.
        xcode = (
            hls["o_int11"]
            .reshape(-1)
            .cpu()
            .numpy()
            .astype(np.int64)
        )

        ycode = (
            a_target
            .reshape(-1)
            .cpu()
            .numpy()
            .astype(np.int64)
        )

        pair = np.zeros(
            (2048, 8),
            dtype=np.int64,
        )

        np.add.at(
            pair,
            (
                xcode + 1024,
                ycode + 4,
            ),
            1,
        )

        aq_fit = fit_aq_lut(
            pair,
            max_shift=args.aq_max_shift,
        )

        # Export scalars.
        softmax_scalars[b] = [
            int(exp_fit["b1"]),
            int(exp_fit["s1"]),
            31,

            int(recip_fit["b2_one"]),
            int(recip_fit["s2_one"]),
            63,

            SOFTMAX_B3,
            SOFTMAX_SHIFT3,

            int(recip_fit["b2_two"]),
            int(recip_fit["s2_two"]),
            63,

            SOFTMAX_B3,
            SOFTMAX_SHIFT3,

            SOFTMAX_CLAMP_BITS,
        ]

        exp_tables[b] = exp_fit[
            "table"
        ].astype(np.uint16)

        recip_one[b] = recip_fit[
            "table_one"
        ].astype(np.uint8)

        # External field is int8_t. Preserve exact 8-bit pattern.
        recip_two_ext[b] = recip_fit[
            "table_two_uint8"
        ].view(np.int8)

        aq_scalars[b] = [
            int(aq_fit["b"]),
            int(aq_fit["s"]),
            63,
            0,
        ]

        aq_tables[b] = aq_fit[
            "table"
        ].astype(np.int8)

        pre = hls["o_pre"]

        pre_over = float(
            (
                (pre < -1024)
                | (pre > 1023)
            )
            .to(torch.float32)
            .mean()
            .item()
        )

        fits[str(b)] = {
            "q_scale": sq,
            "k_scale": sk,
            "v_scale": sv,
            "a_scale": sa,
            "attn_scale": attn_scale,

            "exp": {
                "b1": int(exp_fit["b1"]),
                "s1": int(exp_fit["s1"]),
                "bound1": 31,
                "normalized_mse": float(exp_fit["nmse"]),
                "minus_int11_overflow_rate": float(
                    exp_fit["minus_overflow_rate"]
                ),
                "table": exp_fit["table"].astype(int).tolist(),
            },

            "reciprocal": {
                "b2_one": int(recip_fit["b2_one"]),
                "s2_one": int(recip_fit["s2_one"]),
                "bound2_one": 63,
                "b2_two": int(recip_fit["b2_two"]),
                "s2_two": int(recip_fit["s2_two"]),
                "bound2_two": 63,
                "mse": float(recip_fit["mse"]),
                "maxerr": int(recip_fit["maxerr"]),
                "region_one_fraction": float(
                    recip_fit["region_one_fraction"]
                ),
                "cursor_one_wrap_rate": float(
                    recip_fit["cursor_one_wrap_rate"]
                ),
                "cursor_two_wrap_rate": float(
                    recip_fit["cursor_two_wrap_rate"]
                ),
                "acc_min": int(recip_fit["acc_min"]),
                "acc_max": int(recip_fit["acc_max"]),
            },

            "softmax_weight": {
                "shift3": SOFTMAX_SHIFT3,
                "b3": SOFTMAX_B3,
                "clamp_bits": SOFTMAX_CLAMP_BITS,
                "rq_min": int(hls["rq"].min()),
                "rq_max": int(hls["rq"].max()),
                "a_raw_int11_prewrap_overflow_rate": pre_over,
            },

            "aq": {
                "b": int(aq_fit["b"]),
                "s": int(aq_fit["s"]),
                "bound": 63,
                "mismatch_rate": float(
                    aq_fit["mismatch_rate"]
                ),
                "cursor_wrap_rate": float(
                    aq_fit["cursor_wrap_rate"]
                ),
                "table": aq_fit["table"].astype(int).tolist(),
            },
        }

        print(
            f"Block {b:2d}: "
            f"exp_nmse={exp_fit['nmse']:.6e} "
            f"recip_mse={recip_fit['mse']:.4f} "
            f"AQ_mis={100*aq_fit['mismatch_rate']:.3f}% "
            f"Araw_wrap={100*pre_over:.3f}%"
        )

    # ------------------------------------------------------------
    # Exact Softmax + AQ hooks for validation.
    # ------------------------------------------------------------

    exact_softmax_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sa = float(
            attn_ctrl.a_scale(b)
            .detach()
            .cpu()
        )

        exp_fit = {
            "b1": int(softmax_scalars[b, 0]),
            "s1": int(softmax_scalars[b, 1]),
            "bound1": int(softmax_scalars[b, 2]),
            "table": exp_tables[b],
        }

        recip_fit = {
            "b2_one": int(softmax_scalars[b, 3]),
            "s2_one": int(softmax_scalars[b, 4]),
            "bound2_one": int(softmax_scalars[b, 5]),
            "b2_two": int(softmax_scalars[b, 8]),
            "s2_two": int(softmax_scalars[b, 9]),
            "bound2_two": int(softmax_scalars[b, 10]),
            "table_one": recip_one[b],
            "table_two_uint8": recip_two_ext[b].view(np.uint8),
        }

        aq_fit = {
            "b": int(aq_scalars[b, 0]),
            "s": int(aq_scalars[b, 1]),
            "bound": int(aq_scalars[b, 2]),
            "table": aq_tables[b],
        }

        def proj_pre_hook(
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

            qh = reshape_heads(
                q_code
            )
            kh = reshape_heads(
                k_code
            )
            vh = reshape_heads(
                v_code
            )

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

            # [B,H,T,D] -> [B,T,192]
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
                a_flat.to(x.dtype)
                * sa,
            )

        # Registered after Stage4J proj pre-hook, so this exact result wins.
        exact_softmax_handles.append(
            block.attn.proj.register_forward_pre_hook(
                proj_pre_hook
            )
        )

    exact_softmax_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Save artifacts.
    # ------------------------------------------------------------

    np.save(
        out / "softmax_scalars.npy",
        softmax_scalars,
    )
    np.save(
        out / "softmax_exp_table.npy",
        exp_tables,
    )
    np.save(
        out / "softmax_recip_table_one.npy",
        recip_one,
    )
    np.save(
        out / "softmax_recip_table_two_int8.npy",
        recip_two_ext,
    )
    np.save(
        out / "aq_scalars.npy",
        aq_scalars,
    )
    np.save(
        out / "aq_table.npy",
        aq_tables,
    )

    report = {
        "scope": (
            "Exact Stage4K2 QKV + exact fused fixed-point Softmax + "
            "exact AQ quant.h LUT + exact O int13. Attention residual "
            "RM/RS remains the Stage4J int15 surrogate."
        ),
        "fit_images": int(args.fit_images),
        "exp_scale": EXP_SCALE,
        "softmax_weight_scale": WEIGHT_SCALE,
        "shift3": SOFTMAX_SHIFT3,
        "b3": SOFTMAX_B3,
        "clamp_bits": SOFTMAX_CLAMP_BITS,
        "outer_exact_float_softmax_val_top1": baseline_outer_val,
        "exact_softmax_aq_val_top1": exact_softmax_val,
        "softmax_aq_drop_pp": (
            baseline_outer_val
            - exact_softmax_val
        ),
        "softmax_scalars": softmax_scalars.astype(int).tolist(),
        "aq_scalars": aq_scalars.astype(int).tolist(),
        "blocks": fits,
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
    print("===== STAGE 4L: EXACT SOFTMAX + AQ EVAL =====")
    print(
        f"Outer exact + float Softmax val : "
        f"{baseline_outer_val:.4f}%"
    )
    print(
        f"Exact fixed Softmax + AQ val    : "
        f"{exact_softmax_val:.4f}%"
    )
    print(
        f"Softmax/AQ additional drop      : "
        f"{baseline_outer_val-exact_softmax_val:.4f} pp"
    )
    print("Report:", out / "report.json")

    for h in exact_softmax_handles:
        h.remove()
    for h in o_handles:
        h.remove()
    for h in qkv_handles:
        h.remove()
    for h in ln_handles:
        h.remove()

    attn_ctrl.remove()
    mlp_ctrl.remove()


if __name__ == "__main__":
    main()
