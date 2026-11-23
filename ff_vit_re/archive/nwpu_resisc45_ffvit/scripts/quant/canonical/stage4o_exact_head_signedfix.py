#!/usr/bin/env python3
"""
Stage 4O: signed-fix exact HLS Head fitting/evaluation for manifest dataset.

Motivation
----------
Stage 4N proved the current Head LayerNorm unsigned statistics are incompatible
with the transferred encoder:
  * ap_uint<15> sum wraps for nearly all validation CLS vectors
  * true means are usually negative, incompatible with ap_uint<7>

This stage evaluates the minimal signed correction:
    __head_ln_sum_t   : ap_int<15>
    __head_ln_divc_t  : ap_int<30>
    __head_ln_mu_t    : ap_int<7>

It also compares:
    cursor6 : keep current ap_uint<6> rsqrt cursor (64 reachable entries)
    cursor7 : change to ap_uint<7> to use all 128 existing rsqrt entries

Then it fits:
  * exact signed-fix Head LayerNorm -> ap_int<8>
  * shared-scale signed W8 classifier weights
  * ap_int<19> bias/accumulator arithmetic
  * configured class logits active, remaining HLS outputs padded safely

Calibration uses the train-only calibration manifest. Validation reuses
Stage-4N exact-encoder CLS int13 codes, so no validation data is used to fit
integer parameters.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from stage4j_attention_activation_qat import AttentionActivationController
from stage4l_exact_softmax_aq import ManifestDataset
from stage4n_head_integer_audit import install_stage4m_exact_encoder
from stage4h_exact_layernorm_roundfix import wrap_signed, arshift
from qat_weight3_hls196 import eval_transform


C = 192
NCLASS = __import__('manifest_adapter').num_classes()
HLS_CO = 1000

INT19_MIN = -(1 << 18)
INT19_MAX = (1 << 18) - 1
INT36_MIN = -(1 << 35)
INT36_MAX = (1 << 35) - 1


def u_wrap(x, bits):
    return torch.remainder(x, 1 << bits)


def balanced_spread_subset(ds, n):
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
def collect_exact_cls_codes(
    model,
    backbone,
    loader,
    device,
    final_scale,
):
    codes = []
    labels_all = []
    cache = {"x": None}

    def block_hook(module, inputs, output):
        cache["x"] = output

    h = backbone.vit.blocks[11].register_forward_hook(block_hook)

    model.eval()

    for step, (images, labels) in enumerate(loader, 1):
        images = images.to(device, non_blocking=True)
        _ = model(images)

        x = cache["x"]
        if x is None:
            raise RuntimeError("Final block output cache missing")

        cls = x[:, 0, :]

        q = torch.round(
            cls / float(final_scale)
        ).to(torch.int64)

        q = wrap_signed(q, 13)

        codes.append(q.cpu())
        labels_all.append(labels.cpu())

        if step % 10 == 0 or step == len(loader):
            print(
                f"Collect Head calibration CLS {step}/{len(loader)}",
                flush=True,
            )

    h.remove()

    return (
        torch.cat(codes, dim=0),
        torch.cat(labels_all, dim=0),
    )


def signed_head_stats(qx, c1m=683, c1s=17):
    """
    Proposed minimal corrected Head statistics:
      acc  ap_int<15>
      tmp  ap_int<30>
      mean ap_int<7>
      var  ap_uint<24>
    """
    # Sequential signed accumulation is equivalent to final two's-complement
    # wrap. Calibration range is also audited for pre-wrap overflow.
    signed_sum = qx.sum(dim=1)

    sum_over = (
        (signed_sum < -(1 << 14))
        | (signed_sum > (1 << 14) - 1)
    )

    acc15 = wrap_signed(
        signed_sum,
        15,
    )

    tmp_pre = (
        acc15 * int(c1m)
        + (1 << (int(c1s) - 1))
    )

    tmp_over = (
        (tmp_pre < -(1 << 29))
        | (tmp_pre > (1 << 29) - 1)
    )

    tmp30 = wrap_signed(
        tmp_pre,
        30,
    )

    mean_pre = arshift(
        tmp30,
        int(c1s),
    )

    mean_over = (
        (mean_pre < -64)
        | (mean_pre > 63)
    )

    mean7 = wrap_signed(
        mean_pre,
        7,
    )

    diff_pre = qx - mean7[:, None]

    diff_over = (
        (diff_pre < -4096)
        | (diff_pre > 4095)
    )

    diff13 = wrap_signed(
        diff_pre,
        13,
    )

    var_raw = (
        diff13 * diff13
    ).sum(dim=1)

    var_over = (
        var_raw > (1 << 24) - 1
    )

    var24 = u_wrap(
        var_raw,
        24,
    )

    return {
        "acc15": acc15,
        "mean7": mean7,
        "diff13": diff13,
        "var24": var24,

        "sum_overflow_rate": float(
            sum_over.to(torch.float32).mean()
        ),
        "tmp_overflow_rate": float(
            tmp_over.to(torch.float32).mean()
        ),
        "mean_overflow_rate": float(
            mean_over.to(torch.float32).mean()
        ),
        "diff_overflow_rate": float(
            diff_over.to(torch.float32).mean()
        ),
        "var_overflow_rate": float(
            var_over.to(torch.float32).mean()
        ),

        "sum_min": int(signed_sum.min()),
        "sum_max": int(signed_sum.max()),
        "mean_min": int(mean7.min()),
        "mean_max": int(mean7.max()),
        "var_min": int(var24.min()),
        "var_max": int(var24.max()),
    }


def fit_head_rsqrt(var24, input_scale, eps, cursor_bits):
    v = var24.detach().cpu().to(torch.int64)

    vmin = int(v.min())
    vmax = int(v.max())

    bound = (1 << int(cursor_bits)) - 1

    ideal = 1.0 / torch.sqrt(
        v.to(torch.float64) / float(C)
        + float(eps) / (float(input_scale) ** 2)
    )

    best = None

    # Old Head parameters use a negative address bias, so search mappings
    # translating the observed minimum near address 0.
    b_candidates = {
        0,
        -vmin,
    }

    # Include percentile-based origins for robustness to a few low-variance
    # outliers.
    for q in (0.001, 0.01, 0.05):
        b_candidates.add(
            -int(
                torch.quantile(
                    v.to(torch.float64),
                    torch.tensor(q, dtype=torch.float64),
                ).item()
            )
        )

    for b in sorted(b_candidates):
        shifted_max = vmax + int(b)

        if shifted_max < 0:
            continue

        min_s = 0
        while (shifted_max >> min_s) > bound:
            min_s += 1

        for s1 in range(
            max(0, min_s - 1),
            min_s + 4,
        ):
            raw = arshift(
                v + int(b),
                s1,
            )

            # Exact Head source assignment: unsigned narrow cursor BEFORE clamp.
            cur = torch.remainder(
                raw,
                1 << int(cursor_bits),
            )

            addr = torch.clamp(
                cur,
                0,
                bound,
            )

            wrap_rate = float(
                (
                    (raw < 0)
                    | (raw > bound)
                )
                .to(torch.float32)
                .mean()
            )

            # Choose the largest power-of-two rsqrt scale whose fitted table
            # remains inside ap_uint<11>.
            for r_exp in range(20, 5, -1):
                rscale = float(1 << r_exp)

                table = torch.zeros(
                    1 << int(cursor_bits),
                    dtype=torch.int64,
                )

                used = torch.zeros(
                    1 << int(cursor_bits),
                    dtype=torch.bool,
                )

                for a in range(1 << int(cursor_bits)):
                    m = addr == a
                    if bool(m.any()):
                        val = torch.mean(ideal[m])
                        table[a] = int(
                            round(float(val) * rscale)
                        )
                        used[a] = True

                if int(table.max()) > 2047 or int(table.min()) < 0:
                    continue

                used_idx = torch.where(used)[0]
                if used_idx.numel() == 0:
                    continue

                for a in range(1 << int(cursor_bits)):
                    if not bool(used[a]):
                        j = used_idx[
                            torch.argmin(
                                torch.abs(used_idx - a)
                            )
                        ]
                        table[a] = table[int(j)]

                approx = (
                    table[addr].to(torch.float64)
                    / rscale
                )

                mse = float(
                    torch.mean(
                        (approx - ideal) ** 2
                    )
                )

                rel = (
                    torch.abs(approx - ideal)
                    / torch.clamp(
                        torch.abs(ideal),
                        min=1e-18,
                    )
                )

                rel_p999 = float(
                    torch.quantile(
                        rel,
                        torch.tensor(
                            0.999,
                            dtype=rel.dtype,
                        ),
                    )
                )

                cand = {
                    "b": int(b),
                    "s1": int(s1),
                    "bound": int(bound),
                    "r_exp": int(r_exp),
                    "table": table,
                    "mse": mse,
                    "rel_p999": rel_p999,
                    "cursor_wrap_rate": wrap_rate,
                }

                key = (
                    wrap_rate,
                    mse,
                    rel_p999,
                    -r_exp,
                    s1,
                )

                if best is None:
                    best = cand
                else:
                    bkey = (
                        best["cursor_wrap_rate"],
                        best["mse"],
                        best["rel_p999"],
                        -best["r_exp"],
                        best["s1"],
                    )
                    if key < bkey:
                        best = cand

                # largest safe r_exp for this address mapping is preferred
                break

    if best is None:
        raise RuntimeError(
            f"Unable to fit Head rsqrt table for cursor_bits={cursor_bits}"
        )

    # HLS table always has 128 entries. If cursor is 6-bit, duplicate/fill
    # the unreachable upper half deterministically.
    full_table = torch.zeros(
        128,
        dtype=torch.int64,
    )

    n = 1 << int(cursor_bits)
    full_table[:n] = best["table"]

    if n < 128:
        full_table[n:] = best["table"][-1]

    best["full_table"] = full_table

    return best


def fit_head_affine(diff13, rsqrt_int, target_q):
    """
    Head:
      val    -> ap_int<36>
      val>>s -> ap_int<9>
      clamp  -> signed int8
    """
    u = (
        diff13.to(torch.int64)
        * rsqrt_int[:, None].to(torch.int64)
    )

    y = target_q.to(torch.int64)

    uf = u.to(torch.float64)
    yf = y.to(torch.float64)

    mean_u = uf.mean(dim=0)
    var_u = (
        (uf - mean_u) ** 2
    ).mean(dim=0)

    best = None

    for s2 in range(8, 32):
        scale = float(1 << s2)
        ys = yf * scale

        mean_y = ys.mean(dim=0)

        cov = (
            (uf - mean_u)
            * (ys - mean_y)
        ).mean(dim=0)

        w = torch.zeros(
            C,
            dtype=torch.int64,
        )

        nz = var_u > 1e-20

        w[nz] = torch.round(
            cov[nz] / var_u[nz]
        ).to(torch.int64)

        b = torch.round(
            mean_y
            - mean_u * w.to(torch.float64)
        ).to(torch.int64)

        # Compensate HLS arithmetic right-shift truncation.
        b = b + (
            1 << (s2 - 1)
        )

        if (
            int(w.min()) < -(1 << 31)
            or int(w.max()) > (1 << 31) - 1
        ):
            continue

        val_pre = (
            u * w[None, :]
            + b[None, :]
        )

        affine_over = (
            (val_pre < INT36_MIN)
            | (val_pre > INT36_MAX)
        )

        if bool(affine_over.any()):
            continue

        val36 = wrap_signed(
            val_pre,
            36,
        )

        shifted = arshift(
            val36,
            s2,
        )

        # Source assigns shifted result to ap_int<9> before clamp.
        rel9 = wrap_signed(
            shifted,
            9,
        )

        pred = torch.clamp(
            rel9,
            -128,
            127,
        )

        mismatch = float(
            (pred != y)
            .to(torch.float32)
            .mean()
        )

        mse = float(
            torch.mean(
                (
                    pred.to(torch.float64)
                    - y.to(torch.float64)
                ) ** 2
            )
        )

        maxerr = int(
            torch.max(
                torch.abs(pred - y)
            )
        )

        rel9_wrap = float(
            (
                (shifted < -256)
                | (shifted > 255)
            )
            .to(torch.float32)
            .mean()
        )

        cand = {
            "s2": int(s2),
            "lnw": w,
            "lnb": b,
            "mismatch_rate": mismatch,
            "mse_code": mse,
            "max_abs_code_error": maxerr,
            "rel9_wrap_rate": rel9_wrap,
            "affine_min": int(val_pre.min()),
            "affine_max": int(val_pre.max()),
        }

        key = (
            rel9_wrap,
            mismatch,
            mse,
            maxerr,
            s2,
        )

        if best is None:
            best = cand
        else:
            bkey = (
                best["rel9_wrap_rate"],
                best["mismatch_rate"],
                best["mse_code"],
                best["max_abs_code_error"],
                best["s2"],
            )

            if key < bkey:
                best = cand

    if best is None:
        raise RuntimeError(
            "Could not fit safe signed-fix Head affine"
        )

    return best


def apply_head_ln(qx, fit):
    c1m = int(fit["scalars"][0])
    c1s = int(fit["scalars"][1])
    baddr = int(fit["scalars"][2])
    s1 = int(fit["scalars"][3])
    bound = int(fit["scalars"][4])
    s2 = int(fit["scalars"][5])

    cursor_bits = int(
        fit["cursor_bits"]
    )

    acc = wrap_signed(
        qx.sum(dim=1),
        15,
    )

    tmp = (
        acc * c1m
        + (1 << (c1s - 1))
    )
    tmp = wrap_signed(
        tmp,
        30,
    )

    mean = wrap_signed(
        arshift(tmp, c1s),
        7,
    )

    diff = wrap_signed(
        qx - mean[:, None],
        13,
    )

    var = u_wrap(
        (diff * diff).sum(dim=1),
        24,
    )

    raw = arshift(
        var + baddr,
        s1,
    )

    cur = torch.remainder(
        raw,
        1 << cursor_bits,
    )

    addr = torch.clamp(
        cur,
        0,
        bound,
    )

    table = fit["rsqrt_table"].to(
        qx.device
    )

    rr = table[addr]

    w = fit["lnw"].to(
        qx.device
    )
    bb = fit["lnb"].to(
        qx.device
    )

    val = (
        diff * rr[:, None] * w[None, :]
        + bb[None, :]
    )

    val = wrap_signed(
        val,
        36,
    )

    shifted = arshift(
        val,
        s2,
    )

    rel9 = wrap_signed(
        shifted,
        9,
    )

    return torch.clamp(
        rel9,
        -128,
        127,
    )


def fit_head_ln(
    qx_cal,
    target_float,
    input_scale,
    eps,
    cursor_bits,
):
    stats = signed_head_stats(
        qx_cal,
    )

    rs = fit_head_rsqrt(
        stats["var24"],
        input_scale,
        eps,
        cursor_bits,
    )

    raw = arshift(
        stats["var24"]
        + int(rs["b"]),
        int(rs["s1"]),
    )

    cur = torch.remainder(
        raw,
        1 << int(cursor_bits),
    )

    addr = torch.clamp(
        cur,
        0,
        int(rs["bound"]),
    )

    rint = rs["full_table"][addr]

    abs_p999 = float(
        torch.quantile(
            target_float.abs().reshape(-1),
            torch.tensor(
                0.999,
                dtype=target_float.dtype,
            ),
        )
    )

    base = max(
        abs_p999 / 127.0,
        1e-6,
    )

    best = None

    scale_multipliers = np.concatenate([
        np.linspace(0.65, 1.00, 8),
        np.linspace(1.05, 1.60, 12),
    ])

    for mul in scale_multipliers:
        sout = float(
            base * float(mul)
        )

        target_q = torch.round(
            target_float / sout
        ).to(torch.int64)

        target_q = torch.clamp(
            target_q,
            -128,
            127,
        )

        af = fit_head_affine(
            stats["diff13"],
            rint,
            target_q,
        )

        fit = {
            "cursor_bits": int(cursor_bits),
            "output_scale": sout,
            "scalars": np.array([
                683,
                17,
                int(rs["b"]),
                int(rs["s1"]),
                int(rs["bound"]),
                int(af["s2"]),
                8,
                0,
            ], dtype=np.int32),
            "lnw": af["lnw"],
            "lnb": af["lnb"],
            "rsqrt_table": rs["full_table"],
            "rsqrt_rel_p999": float(
                rs["rel_p999"]
            ),
            "rsqrt_cursor_wrap_rate": float(
                rs["cursor_wrap_rate"]
            ),
            "affine_mismatch_rate": float(
                af["mismatch_rate"]
            ),
            "affine_mse_code": float(
                af["mse_code"]
            ),
            "affine_max_abs_code_error": int(
                af["max_abs_code_error"]
            ),
            "rel9_wrap_rate": float(
                af["rel9_wrap_rate"]
            ),
            "stats": {
                k: v
                for k, v in stats.items()
                if not torch.is_tensor(v)
            },
        }

        q_pred = apply_head_ln(
            qx_cal,
            {
                **fit,
                "lnw": fit["lnw"],
                "lnb": fit["lnb"],
                "rsqrt_table": fit["rsqrt_table"],
            },
        )

        real_mse = float(
            torch.mean(
                (
                    q_pred.to(torch.float64) * sout
                    - target_float.to(torch.float64)
                ) ** 2
            )
        )

        fit["real_mse"] = real_mse

        key = (
            fit["rel9_wrap_rate"],
            real_mse,
            fit["affine_mismatch_rate"],
        )

        if best is None:
            best = fit
        else:
            bkey = (
                best["rel9_wrap_rate"],
                best["real_mse"],
                best["affine_mismatch_rate"],
            )

            if key < bkey:
                best = fit

    return best


def quantize_weight_int8_mse(w, grid=101):
    w = w.detach().cpu().to(torch.float64)

    max_abs = float(
        w.abs().max()
    )

    if max_abs == 0.0:
        return (
            torch.zeros_like(
                w,
                dtype=torch.int64,
            ),
            1.0,
        )

    best = None

    for i in range(grid):
        ratio = (
            0.55
            + 0.45 * i / max(grid - 1, 1)
        )

        alpha = max_abs * ratio
        scale = alpha / 127.0

        q = torch.round(
            w / scale
        ).to(torch.int64)

        q = torch.clamp(
            q,
            -128,
            127,
        )

        dq = (
            q.to(torch.float64)
            * scale
        )

        mse = float(
            torch.mean(
                (dq - w) ** 2
            )
        )

        cand = (
            mse,
            scale,
            q,
        )

        if best is None or mse < best[0]:
            best = cand

    return best[2], float(best[1])


def exact_head_logits(
    qln,
    qw,
    qb,
):
    """
    Exact ap_int<19> compound-accumulation semantics.
    qln [N,192], qw [NCLASS,192], qb [NCLASS]
    """
    n = qln.shape[0]
    co = qw.shape[0]

    acc = qb[None, :].repeat(
        n,
        1,
    ).to(torch.int64)

    any_wrap = torch.zeros(
        n,
        co,
        dtype=torch.bool,
    )

    for ci in range(C):
        pre = (
            acc
            + qln[:, ci:ci+1]
            * qw[:, ci][None, :]
        )

        wrap = (
            (pre < INT19_MIN)
            | (pre > INT19_MAX)
        )

        any_wrap |= wrap

        acc = wrap_signed(
            pre,
            19,
        )

    return acc, any_wrap


def fit_head_classifier(
    qln_cal,
    float_ln_cal,
    head_module,
    ln_scale,
):
    w = head_module.weight.detach().cpu()
    b = head_module.bias.detach().cpu()

    if tuple(w.shape) != (NCLASS, C):
        raise RuntimeError(
            f"Expected NCLASSx192 classifier weight, got {tuple(w.shape)}"
        )

    # Base W8 scale from weight MSE, then search around it jointly with
    # the fixed Head-LN output scale.
    _, sw_base = quantize_weight_int8_mse(w)

    float_logits = (
        float_ln_cal.to(torch.float64)
        @ w.to(torch.float64).t()
        + b.to(torch.float64)
    )

    best = None

    for mul in np.linspace(
        0.70,
        1.35,
        27,
    ):
        sw = float(
            sw_base * float(mul)
        )

        qw = torch.round(
            w.to(torch.float64) / sw
        ).to(torch.int64)

        qw = torch.clamp(
            qw,
            -128,
            127,
        )

        slogit = float(
            ln_scale * sw
        )

        qb_pre = torch.round(
            b.to(torch.float64)
            / slogit
        ).to(torch.int64)

        bias_over = (
            (qb_pre < INT19_MIN)
            | (qb_pre > INT19_MAX)
        )

        if bool(bias_over.any()):
            continue

        qb = wrap_signed(
            qb_pre,
            19,
        )

        int_logits, any_wrap = exact_head_logits(
            qln_cal,
            qw,
            qb,
        )

        real_logits = (
            int_logits.to(torch.float64)
            * slogit
        )

        # Remove a per-sample common offset before MSE, since argmax is
        # invariant to such offsets and this better reflects classifier error.
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

        wrap_rate = float(
            any_wrap.to(torch.float32).mean()
        )

        cand = {
            "weight_scale": sw,
            "logit_scale": slogit,
            "qw": qw,
            "qb": qb,
            "logit_mse_centered": mse,
            "accumulator_wrap_rate": wrap_rate,
            "active_logit_min": int(
                int_logits.min()
            ),
            "active_logit_max": int(
                int_logits.max()
            ),
        }

        key = (
            wrap_rate,
            mse,
        )

        if best is None:
            best = cand
        else:
            bkey = (
                best["accumulator_wrap_rate"],
                best["logit_mse_centered"],
            )

            if key < bkey:
                best = cand

    if best is None:
        raise RuntimeError(
            "Unable to find safe W8/Head int19 quantization"
        )

    return best


def evaluate_head(
    qx,
    labels,
    norm_module,
    head_module,
    input_scale,
    ln_fit,
    cls_fit,
):
    qln = apply_head_ln(
        qx,
        {
            **ln_fit,
            "lnw": ln_fit["lnw"],
            "lnb": ln_fit["lnb"],
            "rsqrt_table": ln_fit["rsqrt_table"],
        },
    )

    int_logits, any_wrap = exact_head_logits(
        qln,
        cls_fit["qw"],
        cls_fit["qb"],
    )

    pred = int_logits.argmax(
        dim=1
    )

    top1 = (
        100.0
        * float(
            (pred == labels)
            .to(torch.float32)
            .mean()
        )
    )

    # Float Head baseline on the exact same exact-encoder codes.
    with torch.inference_mode():
        x = (
            qx.to(torch.float32)
            * float(input_scale)
        )

        float_ln = norm_module(
            x
        )

        float_logits = head_module(
            float_ln
        )

        float_pred = float_logits.argmax(
            dim=1
        )

        float_top1 = (
            100.0
            * float(
                (float_pred == labels)
                .to(torch.float32)
                .mean()
            )
        )

    return {
        "top1": top1,
        "float_top1_same_codes": float_top1,
        "accumulator_wrap_rate": float(
            any_wrap.to(torch.float32).mean()
        ),
        "logit_min": int(
            int_logits.min()
        ),
        "logit_max": int(
            int_logits.max()
        ),
    }


def write_head_header(
    path,
    best_ln,
    best_cls,
):
    # Pad active rows to the existing 1000-logit interface.
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
        best_cls["qw"]
        .numpy()
        .astype(np.int8)
    )

    b1000[:NCLASS] = (
        best_cls["qb"]
        .numpy()
        .astype(np.int32)
    )

    sc = best_ln["scalars"]
    lnw = (
        best_ln["lnw"]
        .numpy()
        .astype(np.int32)
    )
    lnb = (
        best_ln["lnb"]
        .numpy()
        .astype(np.int64)
    )
    rs = (
        best_ln["rsqrt_table"]
        .numpy()
        .astype(np.int32)
    )

    lines = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("// Generated Stage4O manifest dataset Head ROM fragment.")
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
            + ", ".join(
                str(int(v))
                for v in lnw[i:i+16]
            )
            + ","
        )
    lines.append("};")
    lines.append("")

    lines.append("const long long HEAD_LNB[192] = {")
    for i in range(0, C, 8):
        lines.append(
            "    "
            + ", ".join(
                f"{int(v)}LL"
                for v in lnb[i:i+8]
            )
            + ","
        )
    lines.append("};")
    lines.append("")

    lines.append("const int HEAD_RSQRT[128] = {")
    for i in range(0, 128, 16):
        lines.append(
            "    "
            + ", ".join(
                str(int(v))
                for v in rs[i:i+16]
            )
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
            + ", ".join(
                str(int(v))
                for v in row
            )
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
            + ", ".join(
                str(int(v))
                for v in b1000[i:i+16]
            )
            + ","
        )
    lines.append("};")
    lines.append("")

    Path(path).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def serializable_ln(fit):
    return {
        "cursor_bits": int(
            fit["cursor_bits"]
        ),
        "output_scale": float(
            fit["output_scale"]
        ),
        "scalars": (
            fit["scalars"]
            .astype(int)
            .tolist()
        ),
        "rsqrt_rel_p999": float(
            fit["rsqrt_rel_p999"]
        ),
        "rsqrt_cursor_wrap_rate": float(
            fit["rsqrt_cursor_wrap_rate"]
        ),
        "affine_mismatch_rate": float(
            fit["affine_mismatch_rate"]
        ),
        "affine_mse_code": float(
            fit["affine_mse_code"]
        ),
        "affine_max_abs_code_error": int(
            fit["affine_max_abs_code_error"]
        ),
        "rel9_wrap_rate": float(
            fit["rel9_wrap_rate"]
        ),
        "real_mse": float(
            fit["real_mse"]
        ),
        "stats": fit["stats"],
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
    ap.add_argument("--stage4n-dir", required=True)

    ap.add_argument("--manifest", required=True)
    ap.add_argument("--patch-scale", type=float, required=True)

    ap.add_argument(
        "--output",
        default="stage4o_exact_head_signedfix",
    )

    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fit-images", type=int, default=512)

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

    calib_base = ManifestDataset(
        args.manifest,
        eval_transform(),
    )

    if list(calib_base.classes) != classes:
        raise RuntimeError(
            "Calibration class ordering mismatch"
        )

    calib_ds = balanced_spread_subset(
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

    qcal, ycal = collect_exact_cls_codes(
        model,
        backbone,
        calib_loader,
        device,
        final_scale,
    )

    # Reuse Stage4N exact-encoder validation codes.
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

    norm_module = backbone.vit.norm.cpu().eval()
    head_module = backbone.vit.head.cpu().eval()

    with torch.inference_mode():
        xcal = (
            qcal.to(torch.float32)
            * float(final_scale)
        )

        float_ln_cal = norm_module(
            xcal
        )

    print()
    print("===== STAGE 4O: FIT SIGNED-FIX HEAD =====")
    print(
        "Proposed mandatory type changes:"
    )
    print(
        "  __head_ln_sum_t  : ap_uint<15> -> ap_int<15>"
    )
    print(
        "  __head_ln_divc_t : ap_uint<30> -> ap_int<30>"
    )
    print(
        "  __head_ln_mu_t   : ap_uint<7>  -> ap_int<7>"
    )
    print()

    results = {}

    for cursor_bits in (6, 7):
        ln_fit = fit_head_ln(
            qcal,
            float_ln_cal,
            final_scale,
            float(norm_module.eps),
            cursor_bits,
        )

        qln_cal = apply_head_ln(
            qcal,
            {
                **ln_fit,
                "lnw": ln_fit["lnw"],
                "lnb": ln_fit["lnb"],
                "rsqrt_table": ln_fit["rsqrt_table"],
            },
        )

        cls_fit = fit_head_classifier(
            qln_cal,
            float_ln_cal,
            head_module,
            ln_fit["output_scale"],
        )

        val_result = evaluate_head(
            qval,
            yval,
            norm_module,
            head_module,
            final_scale,
            ln_fit,
            cls_fit,
        )

        results[cursor_bits] = {
            "ln_fit": ln_fit,
            "cls_fit": cls_fit,
            "val": val_result,
        }

        print(
            f"Cursor {cursor_bits}-bit: "
            f"LN scale={ln_fit['output_scale']:.9g} "
            f"LN mismatch={100*ln_fit['affine_mismatch_rate']:.3f}% "
            f"rsqrt p999={100*ln_fit['rsqrt_rel_p999']:.3f}% "
            f"Head acc wrap={100*val_result['accumulator_wrap_rate']:.6f}% "
            f"val={val_result['top1']:.4f}% "
            f"(float same-code={val_result['float_top1_same_codes']:.4f}%)"
        )

    # Choose the candidate by validation-free criteria first:
    # calibration LN real error, then accumulator safety. If these are
    # effectively tied, prefer 6-bit to minimize hardware change.
    candidates = []

    for bits in (6, 7):
        x = results[bits]

        candidates.append((
            x["cls_fit"]["accumulator_wrap_rate"],
            x["ln_fit"]["real_mse"],
            x["ln_fit"]["rsqrt_rel_p999"],
            bits,
        ))

    candidates.sort()

    best_bits = int(
        candidates[0][-1]
    )

    best_ln = results[best_bits]["ln_fit"]
    best_cls = results[best_bits]["cls_fit"]
    best_val = results[best_bits]["val"]

    write_head_header(
        out / "generated_head_rom_signedfix.h",
        best_ln,
        best_cls,
    )

    np.save(
        out / "head_ln_scalars.npy",
        best_ln["scalars"],
    )
    np.save(
        out / "head_lnw.npy",
        best_ln["lnw"].numpy().astype(np.int32),
    )
    np.save(
        out / "head_lnb.npy",
        best_ln["lnb"].numpy().astype(np.int64),
    )
    np.save(
        out / "head_rsqrt.npy",
        best_ln["rsqrt_table"].numpy().astype(np.int32),
    )
    np.save(
        out / "head_weight_active.npy",
        best_cls["qw"].numpy().astype(np.int8),
    )
    np.save(
        out / "head_bias_active.npy",
        best_cls["qb"].numpy().astype(np.int32),
    )

    report = {
        "scope": (
            "Exact Stage4M encoder + proposed signed Head LayerNorm fix "
            "+ exact W8/int19 active-class classifier. 1000-logit ROM padding "
            "is generated; HLS C-sim parity is still required."
        ),

        "mandatory_type_changes": {
            "__head_ln_sum_t": "ap_int<15>",
            "__head_ln_divc_t": "ap_int<30>",
            "__head_ln_mu_t": "ap_int<7>",
        },

        "cursor_choice": {
            "selected_bits": best_bits,
            "if_selected_7bit_change": (
                "__head_ln_cursor_t: ap_uint<6> -> ap_uint<7>"
            ),
        },

        "final_encoder_int13_scale": float(
            final_scale
        ),

        "cursor6": {
            "ln": serializable_ln(
                results[6]["ln_fit"]
            ),
            "classifier": {
                k: v
                for k, v in results[6]["cls_fit"].items()
                if k not in ("qw", "qb")
            },
            "validation": results[6]["val"],
        },

        "cursor7": {
            "ln": serializable_ln(
                results[7]["ln_fit"]
            ),
            "classifier": {
                k: v
                for k, v in results[7]["cls_fit"].items()
                if k not in ("qw", "qb")
            },
            "validation": results[7]["val"],
        },

        "selected": {
            "cursor_bits": best_bits,
            "head_ln_output_scale": float(
                best_ln["output_scale"]
            ),
            "head_weight_scale": float(
                best_cls["weight_scale"]
            ),
            "head_logit_scale": float(
                best_cls["logit_scale"]
            ),
            "validation_top1": float(
                best_val["top1"]
            ),
            "float_head_same_exact_encoder_codes_top1": float(
                best_val["float_top1_same_codes"]
            ),
            "head_accumulator_wrap_rate": float(
                best_val["accumulator_wrap_rate"]
            ),
            "active_logit_min": int(
                best_val["logit_min"]
            ),
            "active_logit_max": int(
                best_val["logit_max"]
            ),
            "inactive_962_bias": INT19_MIN,
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
    print("===== STAGE 4O: EXACT SIGNED-FIX HEAD RESULT =====")
    print(
        f"Selected cursor bits        : {best_bits}"
    )
    print(
        f"Float Head same encoder     : "
        f"{best_val['float_top1_same_codes']:.4f}%"
    )
    print(
        f"Exact signed-fix W8 Head    : "
        f"{best_val['top1']:.4f}%"
    )
    print(
        f"Head accumulator wrap       : "
        f"{100*best_val['accumulator_wrap_rate']:.6f}%"
    )
    print(
        f"Active int19 logit range    : "
        f"[{best_val['logit_min']}, {best_val['logit_max']}]"
    )
    print(
        "ROM:", out / "generated_head_rom_signedfix.h"
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
