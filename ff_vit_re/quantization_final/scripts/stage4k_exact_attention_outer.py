#!/usr/bin/env python3
"""
Stage 4K: exact FF-ViT Attention outer integer chain.

This stage intentionally keeps:
  * Softmax in floating point
  * A=Softmax(QK^T)V boundary as the Stage-4J signed-int3 surrogate
  * Attention-output int15 boundary as the Stage-4J surrogate

It converts the parts whose integer domains are already fully defined:
  1. exact integer LayerNorm1, with fixed block-input int13 scale
  2. exact W3 Q/K/V MAC accumulators
  3. exact qq/kq/vq Quant LUT64 using quant.h semantics
  4. exact W3 O projection int13 accumulator

Why A/Softmax are deferred:
The HLS A input to aq is produced by the fixed-point Softmax/value-aggregation
path. Its integer scale cannot be made bit-accurate independently of that path.
Stage 4L should generate Softmax and aq together.

quant.h semantics reproduced exactly at the LUT address boundary:
    cursor_tmp = (x + b) >> s
    cursor     = ap_int<CURSOR_BITS>(cursor_tmp)  # wrap before clamp
    cursor     = clamp(cursor, 0, bound)
    y          = table[cursor]

Current source uses 9-bit signed cursor for Q/K/V requant.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import (
    MLPActivationController,
    module_weight_scale,
)
from stage4j_attention_activation_qat import AttentionActivationController
from stage4h_exact_layernorm_roundfix import (
    wrap_signed,
    arshift,
    choose_c_recip,
    fit_rsqrt_table,
    fit_affine,
)
from qat_weight3_hls196 import eval_transform


C = 192
QKV_OUT = 192
INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1


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


def np_wrap_signed(x, bits):
    mod = 1 << bits
    half = 1 << (bits - 1)
    return ((x + half) % mod) - half


def qkv_weight_scales(module):
    if not hasattr(module, "log_scale"):
        raise RuntimeError(
            "qkv module has no log_scale; expected Stage-1 W3-QAT module"
        )

    s = torch.exp(module.log_scale.detach()).reshape(-1)

    if s.numel() != 3:
        raise RuntimeError(
            f"Expected 3 independent Q/K/V weight scales, got {tuple(s.shape)}"
        )

    return [float(v.cpu()) for v in s]


def quant_qkv_weights(module):
    scales = qkv_weight_scales(module)
    chunks = torch.chunk(module.weight.detach(), 3, dim=0)

    out = []
    for w, s in zip(chunks, scales):
        q = torch.round(w / float(s))
        q = torch.clamp(q, -4, 3).to(torch.int64)
        out.append(q)

    return out, scales


def quant_qkv_biases(module, acc_scales, bits=(12, 11, 11)):
    if module.bias is None:
        chunks = [
            torch.zeros(
                QKV_OUT,
                dtype=torch.float32,
                device=module.weight.device,
            )
            for _ in range(3)
        ]
    else:
        chunks = torch.chunk(
            module.bias.detach(),
            3,
            dim=0,
        )

    out = []
    for b, s, nbits in zip(chunks, acc_scales, bits):
        q = torch.round(
            b / float(s)
        ).to(torch.int64)
        q = wrap_signed(q, nbits)
        out.append(q)

    return out


def quant_o_weight(module):
    sw = float(
        module_weight_scale(module).detach().cpu()
    )
    qw = torch.round(module.weight.detach() / sw)
    qw = torch.clamp(qw, -4, 3).to(torch.int64)
    return qw, sw


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


class LNSampler:
    def __init__(self, tokens_per_block=4096, per_batch=64):
        self.tokens_per_block = int(tokens_per_block)
        self.per_batch = int(per_batch)
        self.x = {b: [] for b in range(12)}
        self.y = {b: [] for b in range(12)}

    def _count(self, d, b):
        return sum(v.shape[0] for v in d[b])

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
            q = torch.round(take / float(scale))
            q = torch.clamp(q, -4, 3).to(torch.int64)
            self.y[b].append(q)

    def done(self):
        for b in range(12):
            if self._count(self.x, b) < self.tokens_per_block:
                return False
            if self._count(self.y, b) < self.tokens_per_block:
                return False
        return True

    def get(self, b):
        x = torch.cat(self.x[b], dim=0)[:self.tokens_per_block]
        y = torch.cat(self.y[b], dim=0)[:self.tokens_per_block]
        return x, y


def fixed_input_ln_stats(x_real, sx, input_bits=13):
    qmin = -(1 << (input_bits - 1))
    qmax = (1 << (input_bits - 1)) - 1

    q_pre = torch.round(
        x_real / float(sx)
    ).to(torch.int64)

    input_over = (
        (q_pre < qmin) | (q_pre > qmax)
    )

    qx = wrap_signed(q_pre, input_bits)

    acc = qx.sum(dim=1)
    cpar = choose_c_recip(acc)

    tmp_pre = (
        acc * int(cpar["m"])
        + (1 << (int(cpar["s"]) - 1))
    )
    tmp = wrap_signed(tmp_pre, 32)
    mean = arshift(tmp, int(cpar["s"]))

    diff_pre = qx - mean[:, None]
    diff_over = (
        (diff_pre < qmin) | (diff_pre > qmax)
    )
    diff = wrap_signed(diff_pre, input_bits)

    sum_sq = (qx * qx).sum(dim=1)

    var_pre = (
        sum_sq
        - 2 * mean * acc
        + C * mean * mean
    )

    var_min = -(1 << 35)
    var_max = (1 << 35) - 1
    var_over = (
        (var_pre < var_min) | (var_pre > var_max)
    )
    var36 = wrap_signed(var_pre, 36)

    return {
        "qx": qx,
        "input_over": input_over,
        "acc": acc,
        "cpar": cpar,
        "mean": mean,
        "diff": diff,
        "diff_over": diff_over,
        "var36": var36,
        "var_over": var_over,
    }


def fit_fixed_scale_layernorm(x_real, target_q, sx, eps, input_bits=13):
    st = fixed_input_ln_stats(
        x_real,
        sx,
        input_bits=input_bits,
    )

    if bool(st["input_over"].any()):
        raise RuntimeError(
            f"LayerNorm input overflows ap_int<{input_bits}> at scale {sx}"
        )
    if bool(st["diff_over"].any()):
        raise RuntimeError(
            f"LayerNorm diff overflows ap_int<{input_bits}> at scale {sx}"
        )
    if bool(st["var_over"].any()) or int(st["var36"].min()) < 0:
        raise RuntimeError(
            "LayerNorm variance path overflow/negative statistic"
        )

    rs = fit_rsqrt_table(
        st["var36"],
        sx,
        eps,
        r_exp=20,
    )

    addr = arshift(
        st["var36"] + int(rs["b"]),
        int(rs["s1"]),
    )
    addr = torch.clamp(
        addr,
        0,
        int(rs["bound"]),
    )
    rint = rs["table"][addr]

    af = fit_affine(
        st["diff"],
        rint,
        target_q,
    )

    scalars = np.array(
        [
            int(st["cpar"]["m"]),
            int(st["cpar"]["s"]),
            int(rs["b"]),
            int(rs["s1"]),
            int(rs["bound"]),
            int(af["s2"]),
            3,
        ],
        dtype=np.int32,
    )

    return {
        "input_scale": float(sx),
        "scalars": scalars,
        "lnw": af["lnw"].numpy().astype(np.int32),
        "lnb": af["lnb"].numpy().astype(np.int64),
        "rsqrt_table": rs["table"].numpy().astype(np.int32),
        "stats": {
            "input_min": int(st["qx"].min()),
            "input_max": int(st["qx"].max()),
            "diff_min": int(st["diff"].min()),
            "diff_max": int(st["diff"].max()),
            "var_min": int(st["var36"].min()),
            "var_max": int(st["var36"].max()),
            "rsqrt_rel_p999": float(rs["rel_p999"]),
            "affine_mismatch_rate": float(af["mismatch"]),
            "affine_code_mse": float(af["mse"]),
            "affine_max_abs_code_error": int(af["maxerr"]),
        },
    }


def install_exact_ln1(
    backbone,
    attn_ctrl,
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
        sy = float(attn_ctrl.ln1_scale(b).detach().cpu())

        sc = scalars[b]
        c1m, c1s, bias, s1, bound, s2, clamp_bits = [
            int(v) for v in sc
        ]

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
            qx = wrap_signed(qx, 13)

            acc = qx.sum(dim=-1)

            tmp = (
                acc * c1m
                + (1 << (c1s - 1))
            )
            tmp = wrap_signed(tmp, 32)
            mean = arshift(tmp, c1s)

            diff = qx - mean.unsqueeze(-1)
            diff = wrap_signed(diff, 13)

            sum_sq = (qx * qx).sum(dim=-1)

            var = (
                sum_sq
                - 2 * mean * acc
                + C * mean * mean
            )
            var = wrap_signed(var, 36)

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
            val = wrap_signed(val, 40)

            rel = arshift(val, s2)
            rel = wrap_signed(rel, 32)

            qy = torch.clamp(
                rel,
                -4,
                3,
            )

            return qy.to(x.dtype) * sy

        handles.append(
            block.norm1.register_forward_hook(hook)
        )

    return handles


def fit_quant_lut(
    hist,
    acc_scale,
    out_scale,
    cursor_bits,
    b_search_radius=256,
    max_shift=9,
):
    code_min = -(len(hist) // 2)
    codes = np.arange(
        code_min,
        code_min + len(hist),
        dtype=np.int64,
    )
    counts = hist.astype(np.float64)

    mask = counts > 0
    x = codes[mask]
    w = counts[mask]

    if x.size == 0:
        raise RuntimeError("Empty accumulator histogram")

    # Stage4J target code.
    target = np.rint(
        x.astype(np.float64)
        * float(acc_scale)
        / float(out_scale)
    ).astype(np.int64)
    target = np.clip(target, -4, 3)

    xmin = int(x.min())
    xmax = int(x.max())

    best = None

    for s in range(int(max_shift) + 1):
        step = 1 << s
        b0 = -xmin

        for b in range(
            b0 - int(b_search_radius),
            b0 + int(b_search_radius) + 1,
        ):
            tmp = (x + b) // step

            # quant.h: assignment to narrow signed cursor BEFORE clamp.
            cur = np_wrap_signed(
                tmp,
                int(cursor_bits),
            )
            addr = np.clip(
                cur,
                0,
                63,
            ).astype(np.int64)

            table = np.zeros(64, dtype=np.int64)

            used = np.unique(addr)

            for a in used:
                m = addr == a
                num = np.sum(w[m] * target[m])
                den = np.sum(w[m])
                table[a] = int(
                    np.clip(
                        np.rint(num / den),
                        -4,
                        3,
                    )
                )

            if used.size:
                for a in range(64):
                    if a not in used:
                        nearest = used[
                            np.argmin(np.abs(used - a))
                        ]
                        table[a] = table[nearest]

            pred = table[addr]
            err = pred - target

            mismatch = float(
                np.sum(w * (pred != target))
                / np.sum(w)
            )
            mse = float(
                np.sum(w * (err ** 2))
                / np.sum(w)
            )
            maxerr = int(
                np.max(np.abs(err))
            )

            cand = {
                "b": int(b),
                "s": int(s),
                "bound": 63,
                "reserved": 0,
                "mismatch_rate": mismatch,
                "mse_code": mse,
                "max_abs_code_error": maxerr,
                "x_min": xmin,
                "x_max": xmax,
                "table": table,
            }

            key = (
                mismatch,
                mse,
                maxerr,
                s,
                abs(b - b0),
            )

            if best is None:
                best = cand
            else:
                bkey = (
                    best["mismatch_rate"],
                    best["mse_code"],
                    best["max_abs_code_error"],
                    best["s"],
                    abs(best["b"] - b0),
                )
                if key < bkey:
                    best = cand

    return best


def apply_quant_lut_torch(
    acc,
    scalars,
    table,
    cursor_bits,
):
    b, s, bound, _ = [
        int(v) for v in scalars
    ]

    tmp = arshift(
        acc + b,
        s,
    )
    cur = wrap_signed(
        tmp,
        cursor_bits,
    )
    addr = torch.clamp(
        cur,
        0,
        bound,
    )

    return table[addr]


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
        total += labels.numel()

    return 100.0 * correct / total


def write_header(path, ln_scalars, lnw, lnb, rsqrt, qsc, ksc, vsc, qt, kt, vt):
    lines = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("// Stage4K generated Attention LN1 + Q/K/V requant parameters.")
    lines.append("")

    def emit_2d(name, arr, ctype):
        lines.append(
            f"static const {ctype} {name}[{arr.shape[0]}][{arr.shape[1]}] = {{"
        )
        for row in arr:
            vals = []
            for v in row:
                if ctype == "long long":
                    vals.append(f"{int(v)}LL")
                else:
                    vals.append(str(int(v)))
            lines.append("    {" + ", ".join(vals) + "},")
        lines.append("};")
        lines.append("")

    emit_2d("ATTN_LN_SCALARS", ln_scalars, "int")
    emit_2d("ATTN_LN_LNW", lnw, "int")
    emit_2d("ATTN_LN_LNB", lnb, "long long")
    emit_2d("ATTN_LN_RSQRT", rsqrt, "int")

    emit_2d("QQ_SCALARS", qsc, "int")
    emit_2d("KQ_SCALARS", ksc, "int")
    emit_2d("VQ_SCALARS", vsc, "int")

    emit_2d("QQ_TABLE", qt, "signed char")
    emit_2d("KQ_TABLE", kt, "signed char")
    emit_2d("VQ_TABLE", vt, "signed char")

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
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--patch-scale", type=float, required=True)

    ap.add_argument(
        "--output",
        default="stage4k_exact_attn_outer",
    )

    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fit-tokens", type=int, default=4096)
    ap.add_argument("--tokens-per-batch", type=int, default=64)
    ap.add_argument("--b-search-radius", type=int, default=256)
    ap.add_argument("--max-shift", type=int, default=9)

    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    with open(args.ranges, "r", encoding="utf-8") as f:
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

    # Attention-output int15 scales in Stage4J were loaded from Stage4H.
    # Recover them directly from the Stage4J controller state.
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
        ckpt["attention_controller_state"]["attn_out_scale"]
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

    val_ds = datasets.ImageFolder(
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

    mlp_scales = mlp_ctrl.export_scales()

    block_input_scales = np.zeros(12, dtype=np.float64)
    block_input_scales[0] = float(args.patch_scale)
    for b in range(1, 12):
        block_input_scales[b] = float(
            mlp_scales[str(b - 1)]["m2_int13_scale"]
        )

    # ------------------------------------------------------------
    # Step 1: fit exact LN1 with fixed block-input int13 scales.
    # ------------------------------------------------------------
    sampler = LNSampler(
        tokens_per_block=args.fit_tokens,
        per_batch=args.tokens_per_batch,
    )

    sample_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]
        sy = float(attn_ctrl.ln1_scale(b).detach().cpu())

        def pre_hook(module, inputs, b=b):
            sampler.add_input(b, inputs[0])

        def post_hook(module, inputs, output, b=b, sy=sy):
            sampler.add_target(b, output, sy)

        sample_handles.append(
            block.norm1.register_forward_pre_hook(pre_hook)
        )
        sample_handles.append(
            block.norm1.register_forward_hook(post_hook)
        )

    full_model.eval()

    with torch.inference_mode():
        for step, (images, _) in enumerate(calib_loader, 1):
            images = images.to(device, non_blocking=True)
            _ = full_model(images)

            if sampler.done():
                print(
                    f"Collected {args.fit_tokens} LN1 tokens/block "
                    f"after calibration batch {step}"
                )
                break

            if step % 10 == 0:
                print(
                    f"LN1 calibration {step}/{len(calib_loader)}",
                    flush=True,
                )

    for h in sample_handles:
        h.remove()

    ln_scalars = np.zeros((12, 7), dtype=np.int32)
    ln_lnw = np.zeros((12, 192), dtype=np.int32)
    ln_lnb = np.zeros((12, 192), dtype=np.int64)
    ln_rsqrt = np.zeros((12, 128), dtype=np.int32)

    ln_report = {}

    print()
    print("===== STAGE 4K: FIT EXACT LN1 =====")

    for b in range(12):
        x, yq = sampler.get(b)

        fit = fit_fixed_scale_layernorm(
            x,
            yq,
            block_input_scales[b],
            float(backbone.vit.blocks[b].norm1.eps),
            input_bits=13,
        )

        ln_scalars[b] = fit["scalars"]
        ln_lnw[b] = fit["lnw"]
        ln_lnb[b] = fit["lnb"]
        ln_rsqrt[b] = fit["rsqrt_table"]

        ln_report[str(b)] = {
            "input_int13_scale": float(block_input_scales[b]),
            "ln_scalars": fit["scalars"].astype(int).tolist(),
            "stats": fit["stats"],
        }

        st = fit["stats"]

        print(
            f"Block {b:2d}: "
            f"Sin={block_input_scales[b]:.10g} "
            f"in=[{st['input_min']},{st['input_max']}] "
            f"LN mismatch={100.0*st['affine_mismatch_rate']:.4f}% "
            f"maxerr={st['affine_max_abs_code_error']}"
        )

    ln_handles = install_exact_ln1(
        backbone,
        attn_ctrl,
        block_input_scales,
        ln_scalars,
        ln_lnw,
        ln_lnb,
        ln_rsqrt,
        device,
    )

    ln_exact_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Step 2: collect exact Q/K/V accumulator histograms using the
    # exact LN1 output.
    # ------------------------------------------------------------

    hist_q = [np.zeros(4096, dtype=np.int64) for _ in range(12)]  # int12
    hist_k = [np.zeros(2048, dtype=np.int64) for _ in range(12)]  # int11
    hist_v = [np.zeros(2048, dtype=np.int64) for _ in range(12)]

    qkv_meta = []

    pre_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sln = float(attn_ctrl.ln1_scale(b).detach().cpu())
        out_scales = [
            float(attn_ctrl.q_scale(b).detach().cpu()),
            float(attn_ctrl.k_scale(b).detach().cpu()),
            float(attn_ctrl.v_scale(b).detach().cpu()),
        ]

        qws, sws = quant_qkv_weights(block.attn.qkv)

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

        qkv_meta.append({
            "qws": qws,
            "qbs": qbs,
            "sws": sws,
            "acc_scales": acc_scales,
            "out_scales": out_scales,
        })

        def qkv_pre(
            module,
            inputs,
            b=b,
            sln=sln,
            qws=qws,
            qbs=qbs,
        ):
            x = inputs[0]

            xi = torch.round(
                x / sln
            ).to(torch.int64)
            xi = torch.clamp(xi, -4, 3)

            hs = []
            for qw, qb, bits in zip(
                qws,
                qbs,
                (12, 11, 11),
            ):
                acc = torch.matmul(
                    xi.to(torch.float32),
                    qw.t().to(device=device, dtype=torch.float32),
                )
                acc = torch.round(acc).to(torch.int64)
                acc = acc + qb.to(device)
                acc = wrap_signed(acc, bits)
                hs.append(acc)

            for arr, h, offset, size in [
                (hist_q, hs[0], 2048, 4096),
                (hist_k, hs[1], 1024, 2048),
                (hist_v, hs[2], 1024, 2048),
            ]:
                bc = torch.bincount(
                    (h.reshape(-1).cpu() + offset),
                    minlength=size,
                ).numpy()
                arr[b] += bc.astype(np.int64)

        pre_handles.append(
            block.attn.qkv.register_forward_pre_hook(qkv_pre)
        )

    full_model.eval()

    with torch.inference_mode():
        for step, (images, _) in enumerate(calib_loader, 1):
            images = images.to(device, non_blocking=True)
            _ = full_model(images)

            if step % 10 == 0 or step == len(calib_loader):
                print(
                    f"QKV histogram {step}/{len(calib_loader)}",
                    flush=True,
                )

    for h in pre_handles:
        h.remove()

    qq_scalars = np.zeros((12, 4), dtype=np.int32)
    kq_scalars = np.zeros((12, 4), dtype=np.int32)
    vq_scalars = np.zeros((12, 4), dtype=np.int32)

    qq_table = np.zeros((12, 64), dtype=np.int8)
    kq_table = np.zeros((12, 64), dtype=np.int8)
    vq_table = np.zeros((12, 64), dtype=np.int8)

    lut_report = {}

    print()
    print("===== STAGE 4K: FIT EXACT Q/K/V REQUANT LUTS =====")

    for b in range(12):
        meta = qkv_meta[b]

        fits = []
        for hist, acc_s, out_s in zip(
            (hist_q[b], hist_k[b], hist_v[b]),
            meta["acc_scales"],
            meta["out_scales"],
        ):
            fits.append(
                fit_quant_lut(
                    hist,
                    acc_s,
                    out_s,
                    cursor_bits=9,
                    b_search_radius=args.b_search_radius,
                    max_shift=args.max_shift,
                )
            )

        fq, fk, fv = fits

        qq_scalars[b] = [fq["b"], fq["s"], fq["bound"], 0]
        kq_scalars[b] = [fk["b"], fk["s"], fk["bound"], 0]
        vq_scalars[b] = [fv["b"], fv["s"], fv["bound"], 0]

        qq_table[b] = fq["table"].astype(np.int8)
        kq_table[b] = fk["table"].astype(np.int8)
        vq_table[b] = fv["table"].astype(np.int8)

        lut_report[str(b)] = {
            "q": {
                k: (
                    v.astype(int).tolist()
                    if isinstance(v, np.ndarray)
                    else v
                )
                for k, v in fq.items()
            },
            "k": {
                k: (
                    v.astype(int).tolist()
                    if isinstance(v, np.ndarray)
                    else v
                )
                for k, v in fk.items()
            },
            "v": {
                k: (
                    v.astype(int).tolist()
                    if isinstance(v, np.ndarray)
                    else v
                )
                for k, v in fv.items()
            },
        }

        print(
            f"Block {b:2d}: "
            f"Q mis={100*fq['mismatch_rate']:.4f}% "
            f"K mis={100*fk['mismatch_rate']:.4f}% "
            f"V mis={100*fv['mismatch_rate']:.4f}%"
        )

    # ------------------------------------------------------------
    # Step 3: install exact Q/K/V MAC + exact Quant LUT.
    # ------------------------------------------------------------

    exact_qkv_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]
        meta = qkv_meta[b]

        sln = float(attn_ctrl.ln1_scale(b).detach().cpu())

        qws = [q.to(device) for q in meta["qws"]]
        qbs = [q.to(device) for q in meta["qbs"]]

        tables = [
            torch.tensor(qq_table[b].astype(np.int64), device=device),
            torch.tensor(kq_table[b].astype(np.int64), device=device),
            torch.tensor(vq_table[b].astype(np.int64), device=device),
        ]

        scalars = [
            qq_scalars[b],
            kq_scalars[b],
            vq_scalars[b],
        ]

        out_scales = meta["out_scales"]

        def exact_qkv_hook(
            module,
            inputs,
            output,
            sln=sln,
            qws=qws,
            qbs=qbs,
            tables=tables,
            scalars=scalars,
            out_scales=out_scales,
        ):
            x = inputs[0]

            xi = torch.round(x / sln).to(torch.int64)
            xi = torch.clamp(xi, -4, 3)

            outs = []

            for qw, qb, bits, sc, tab, so in zip(
                qws,
                qbs,
                (12, 11, 11),
                scalars,
                tables,
                out_scales,
            ):
                acc = torch.matmul(
                    xi.to(torch.float32),
                    qw.t().to(torch.float32),
                )
                acc = torch.round(acc).to(torch.int64)
                acc = acc + qb
                acc = wrap_signed(acc, bits)

                qy = apply_quant_lut_torch(
                    acc,
                    sc,
                    tab,
                    cursor_bits=9,
                )

                # local_table is __of_t=ap_int<3>.
                qy = wrap_signed(qy, 3)

                outs.append(
                    qy.to(x.dtype) * float(so)
                )

            return torch.cat(outs, dim=-1)

        exact_qkv_handles.append(
            block.attn.qkv.register_forward_hook(
                exact_qkv_hook
            )
        )

    qkv_exact_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Step 4: exact O projection. A remains Stage4J signed3 surrogate.
    # ------------------------------------------------------------

    exact_o_handles = []
    o_report = {}

    for b in range(12):
        block = backbone.vit.blocks[b]

        sa = float(attn_ctrl.a_scale(b).detach().cpu())

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

        o_report[str(b)] = {
            "a_signed3_scale": sa,
            "o_weight_scale": sw,
            "o_int13_scale": so,
            "bias_min": int(qb.min().cpu()),
            "bias_max": int(qb.max().cpu()),
        }

        def exact_o_hook(
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
            acc = torch.round(acc).to(torch.int64)
            acc = acc + qb
            acc = wrap_signed(acc, 13)

            return acc.to(x.dtype) * so

        exact_o_handles.append(
            block.attn.proj.register_forward_hook(
                exact_o_hook
            )
        )

    outer_exact_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    # ------------------------------------------------------------
    # Export
    # ------------------------------------------------------------

    np.save(out / "ln1_input_scales.npy", block_input_scales)
    np.save(out / "ln1_scalars.npy", ln_scalars)
    np.save(out / "ln1_lnw.npy", ln_lnw)
    np.save(out / "ln1_lnb.npy", ln_lnb)
    np.save(out / "ln1_rsqrt_table.npy", ln_rsqrt)

    np.save(out / "qq_scalars.npy", qq_scalars)
    np.save(out / "kq_scalars.npy", kq_scalars)
    np.save(out / "vq_scalars.npy", vq_scalars)

    np.save(out / "qq_table.npy", qq_table)
    np.save(out / "kq_table.npy", kq_table)
    np.save(out / "vq_table.npy", vq_table)

    write_header(
        out / "generated_attn_outer_params.h",
        ln_scalars,
        ln_lnw,
        ln_lnb,
        ln_rsqrt,
        qq_scalars,
        kq_scalars,
        vq_scalars,
        qq_table,
        kq_table,
        vq_table,
    )

    report = {
        "scope": (
            "Exact LN1 + exact Q/K/V W3 MAC + exact quant.h qq/kq/vq LUTs "
            "+ exact O W3 int13. Float Softmax, A signed3 surrogate and "
            "Attention-output int15 surrogate remain."
        ),
        "patch_scale": float(args.patch_scale),
        "block_input_scales": block_input_scales.tolist(),
        "exact_ln1_val_top1": ln_exact_val,
        "exact_ln1_qkv_val_top1": qkv_exact_val,
        "exact_attn_outer_val_top1": outer_exact_val,
        "ln1": ln_report,
        "qkv_luts": lut_report,
        "o_projection": o_report,
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
    print("===== STAGE 4K: EXACT ATTENTION OUTER EVAL =====")
    print(f"Exact LN1 only val           : {ln_exact_val:.4f}%")
    print(f"+ exact Q/K/V MAC+LUT val   : {qkv_exact_val:.4f}%")
    print(f"+ exact O int13 val          : {outer_exact_val:.4f}%")
    print("Report:", out / "report.json")
    print("Header:", out / "generated_attn_outer_params.h")

    for h in exact_o_handles:
        h.remove()
    for h in exact_qkv_handles:
        h.remove()
    for h in ln_handles:
        h.remove()
    attn_ctrl.remove()
    mlp_ctrl.remove()


if __name__ == "__main__":
    main()
