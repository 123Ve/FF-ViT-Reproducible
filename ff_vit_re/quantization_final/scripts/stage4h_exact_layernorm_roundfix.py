#!/usr/bin/env python3
"""
Stage 4H: corrected exact FF-ViT integer LayerNorm fit with final-shift rounding compensation.

HLS semantics reproduced from layernorm.h:

    acc      = sum(x_int15)
    tmp      = acc * C_1_m
    tmp     += 1 << (C_1_s - 1)
    mean     = tmp >> C_1_s

    varsum   = sum(x*x) - 2*mean*acc + C*mean*mean
    cursor   = (varsum + b) >> s1
    cursor   = clamp(cursor, 0, bound)
    rsqrt    = rsqrt_table[cursor]

    affine   = (x - mean) * rsqrt * lnw[c] + lnb[c]
    rel      = affine >> s2
    y_int3   = clamp(rel, -4, 3)

The script fits a new hardware-compatible LayerNorm parameterization to the
Stage-4D trained LN2 signed-3-bit target.

Important scope:
  * exact LayerNorm arithmetic/casts/addressing are emulated;
  * exact Stage-4F GELU LUTs are also enabled during calibration/evaluation;
  * the int15 LayerNorm input real scale is fitted per block and exported as
    metadata. It must later be reconciled with the exact Attention/residual
    scale chain before the whole network is called bit-accurate.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from qat_weight3_hls196 import eval_transform


C = 192
INT15_MIN = -(1 << 14)
INT15_MAX = (1 << 14) - 1
INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1
INT36_MIN = -(1 << 35)
INT36_MAX = (1 << 35) - 1
INT40_MIN = -(1 << 39)
INT40_MAX = (1 << 39) - 1


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


class TokenSampler:
    def __init__(self, total_tokens, per_batch):
        self.total_tokens = int(total_tokens)
        self.per_batch = int(per_batch)
        self.x = {b: [] for b in range(12)}
        self.yq = {b: [] for b in range(12)}

    def _n(self, b):
        return sum(t.shape[0] for t in self.x[b])

    def add_input(self, b, x):
        room = self.total_tokens - self._n(b)
        if room <= 0:
            return

        x = x.detach().reshape(-1, x.shape[-1]).cpu()

        n = min(self.per_batch, room, x.shape[0])
        if n <= 0:
            return

        if n == x.shape[0]:
            take = x
        else:
            idx = torch.linspace(
                0,
                x.shape[0] - 1,
                steps=n,
            ).long()
            take = x[idx]

        self.x[b].append(take)

    def add_target(self, b, y, scale):
        # Must mirror the same sampling positions as add_input.
        # The hook sees the same tensor shape/order.
        room = self.total_tokens - sum(t.shape[0] for t in self.yq[b])
        if room <= 0:
            return

        y = y.detach().reshape(-1, y.shape[-1]).cpu()
        n = min(self.per_batch, room, y.shape[0])

        if n <= 0:
            return

        if n == y.shape[0]:
            take = y
        else:
            idx = torch.linspace(
                0,
                y.shape[0] - 1,
                steps=n,
            ).long()
            take = y[idx]

        q = torch.round(take / float(scale))
        q = torch.clamp(q, -4, 3).to(torch.int64)
        self.yq[b].append(q)

    def done(self):
        for b in range(12):
            if self._n(b) < self.total_tokens:
                return False
            ny = sum(t.shape[0] for t in self.yq[b])
            if ny < self.total_tokens:
                return False
        return True

    def get(self, b):
        x = torch.cat(self.x[b], dim=0)[:self.total_tokens]
        yq = torch.cat(self.yq[b], dim=0)[:self.total_tokens]
        return x, yq


def wrap_signed(x, bits):
    mod = 1 << bits
    half = 1 << (bits - 1)
    return torch.remainder(x + half, mod) - half


def arshift(x, s):
    if s == 0:
        return x
    return torch.bitwise_right_shift(x, int(s))


def load_exact_gelu(gelu_dir, device):
    gelu_dir = Path(gelu_dir)
    scalars = np.load(gelu_dir / "ge_scalars.npy")
    tables = np.load(gelu_dir / "ge_table.npy")
    return scalars, tables


def install_exact_gelu(backbone, controller, gelu_dir, device):
    scalars, tables = load_exact_gelu(gelu_dir, device)
    scales = controller.export_scales()
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sm1 = float(scales[str(b)]["m1_int11_scale"])
        sge = float(scales[str(b)]["gelu_uint3_scale"])

        bias = int(scalars[b, 0])
        shift = int(scalars[b, 1])
        bound = int(scalars[b, 2])

        table = torch.tensor(
            tables[b].astype(np.int64),
            dtype=torch.int64,
            device=device,
        )

        def hook(
            module, inputs, output,
            sm1=sm1, sge=sge,
            bias=bias, shift=shift, bound=bound,
            table=table,
        ):
            x = inputs[0]
            xi = torch.round(x / sm1).to(torch.int64)
            xi = torch.clamp(xi, -1024, 1023)

            addr = arshift(xi + bias, shift)
            addr = torch.clamp(addr, 0, bound)

            yi = table[addr]
            return yi.to(x.dtype) * sge

        handles.append(
            block.mlp.act.register_forward_hook(hook)
        )

    return handles


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


def choose_c_recip(acc):
    """
    Choose C_1_m / C_1_s for C=192, while guaranteeing the int32 tmp
    does not overflow on the calibration set.
    """
    best = None
    acc = acc.to(torch.int64)

    for s in range(8, 18):
        m = int(round((1 << s) / C))
        half = 1 << (s - 1)

        prod = acc * m
        tmp = prod + half

        if int(tmp.min()) < INT32_MIN or int(tmp.max()) > INT32_MAX:
            continue

        mean = arshift(tmp, s)
        ideal = acc.to(torch.float64) / float(C)
        mse = float(
            torch.mean(
                (mean.to(torch.float64) - ideal) ** 2
            )
        )

        cand = {
            "m": m,
            "s": s,
            "mse": mse,
        }

        if best is None or (mse, -s) < (best["mse"], -best["s"]):
            best = cand

    if best is None:
        raise RuntimeError("Could not find safe C reciprocal parameters")

    return best


def choose_input_scale(x_real, headroom=0.90):
    """
    Choose an int15 input scale with room for both x and (x - rounded_mean).
    """
    token_mean = x_real.mean(dim=1, keepdim=True)

    mx = float(x_real.abs().max())
    md = float((x_real - token_mean).abs().max())

    need = max(mx, md, 1e-12)
    return need / (headroom * INT15_MAX)


def build_integer_stats(x_real, sx):
    """
    Quantize input to int15 and compute the HLS mean/variance statistics.
    Increase sx outside this function if any critical path overflows.
    """
    qx_pre = torch.round(
        x_real / float(sx)
    ).to(torch.int64)

    input_over = (
        (qx_pre < INT15_MIN)
        | (qx_pre > INT15_MAX)
    )

    qx = wrap_signed(qx_pre, 15)

    acc = qx.sum(dim=1)
    cpar = choose_c_recip(acc)

    tmp_pre = (
        acc * int(cpar["m"])
        + (1 << (int(cpar["s"]) - 1))
    )

    tmp32 = wrap_signed(tmp_pre, 32)
    mean = arshift(tmp32, int(cpar["s"]))

    diff_pre = qx - mean[:, None]
    diff_over = (
        (diff_pre < INT15_MIN)
        | (diff_pre > INT15_MAX)
    )
    diff = wrap_signed(diff_pre, 15)

    sum_sq = (qx * qx).sum(dim=1)

    var_pre = (
        sum_sq
        - 2 * mean * acc
        + C * mean * mean
    )

    var_over = (
        (var_pre < INT36_MIN)
        | (var_pre > INT36_MAX)
    )
    var36 = wrap_signed(var_pre, 36)

    return {
        "qx_pre": qx_pre,
        "qx": qx,
        "input_over": input_over,
        "acc": acc,
        "cpar": cpar,
        "tmp_pre": tmp_pre,
        "mean": mean,
        "diff_pre": diff_pre,
        "diff": diff,
        "diff_over": diff_over,
        "sum_sq": sum_sq,
        "var_pre": var_pre,
        "var36": var36,
        "var_over": var_over,
    }


def settle_input_scale(x_real):
    sx = choose_input_scale(x_real)

    for _ in range(20):
        st = build_integer_stats(x_real, sx)

        bad = (
            bool(st["input_over"].any())
            or bool(st["diff_over"].any())
            or bool(st["var_over"].any())
            or int(st["var36"].min()) < 0
        )

        if not bad:
            return sx, st

        sx *= 1.15

    raise RuntimeError("Failed to find safe int15 LayerNorm input scale")


def fit_rsqrt_table(varsum, sx, eps, r_exp=20):
    """
    Fit exact HLS varsum -> 128-entry integer rsqrt table.

    rsqrt target:
        1 / sqrt(varsum/C + eps/sx^2)
    """
    v = varsum.to(torch.int64).cpu()

    vmin = int(v.min())
    vmax = int(v.max())

    if vmin < 0:
        raise RuntimeError(f"Negative variance statistic encountered: {vmin}")

    # Prefer translating the minimum observed variance to address 0 when b
    # fits a signed int32 scalar. Otherwise keep b=0.
    b_candidates = [0]
    if vmin <= INT32_MAX:
        b_candidates.append(-vmin)

    best = None
    r_scale = float(1 << r_exp)

    ideal = 1.0 / torch.sqrt(
        v.to(torch.float64) / float(C)
        + float(eps) / (float(sx) ** 2)
    )

    for b in sorted(set(b_candidates)):
        shifted_max = vmax + b
        if shifted_max < 0:
            continue

        min_s = 0
        while (shifted_max >> min_s) > 127:
            min_s += 1

        for s1 in range(min_s, min_s + 4):
            addr = arshift(v + int(b), s1)
            addr = torch.clamp(addr, 0, 127)

            table = torch.zeros(128, dtype=torch.int64)
            used = torch.zeros(128, dtype=torch.bool)

            for a in range(128):
                m = addr == a
                if bool(m.any()):
                    val = torch.mean(ideal[m])
                    table[a] = int(round(float(val) * r_scale))
                    used[a] = True

            used_idx = torch.where(used)[0]
            if used_idx.numel() == 0:
                continue

            for a in range(128):
                if not bool(used[a]):
                    j = used_idx[
                        torch.argmin(
                            torch.abs(used_idx - a)
                        )
                    ]
                    table[a] = table[int(j)]

            if int(table.min()) < INT32_MIN or int(table.max()) > INT32_MAX:
                continue

            approx = table[addr].to(torch.float64) / r_scale

            mse = float(
                torch.mean((approx - ideal) ** 2)
            )

            rel = torch.abs(approx - ideal) / torch.clamp(
                torch.abs(ideal),
                min=1e-18,
            )
            rel_p999 = float(
                torch.quantile(
                    rel,
                    torch.tensor(0.999, dtype=rel.dtype),
                )
            )

            cand = {
                "b": int(b),
                "s1": int(s1),
                "bound": 127,
                "r_exp": int(r_exp),
                "table": table,
                "mse": mse,
                "rel_p999": rel_p999,
            }

            key = (
                cand["mse"],
                cand["rel_p999"],
                cand["s1"],
            )

            if best is None:
                best = cand
            else:
                best_key = (
                    best["mse"],
                    best["rel_p999"],
                    best["s1"],
                )
                if key < best_key:
                    best = cand

    if best is None:
        raise RuntimeError("Could not fit rsqrt LUT")

    return best


def fit_affine(diff, rsqrt_int, target_q):
    """
    Search the final shift s2 and fit per-channel lnw/lnb integers.
    """
    u = (
        diff.to(torch.int64)
        * rsqrt_int[:, None].to(torch.int64)
    )

    y = target_q.to(torch.int64)

    uf = u.to(torch.float64)
    yf = y.to(torch.float64)

    mean_u = uf.mean(dim=0)
    var_u = ((uf - mean_u) ** 2).mean(dim=0)

    best = None

    for s2 in range(8, 31):
        scale = float(1 << s2)
        ys = yf * scale

        mean_y = ys.mean(dim=0)
        cov = (
            (uf - mean_u)
            * (ys - mean_y)
        ).mean(dim=0)

        w = torch.zeros(C, dtype=torch.int64)

        nz = var_u > 1e-20
        w[nz] = torch.round(
            cov[nz] / var_u[nz]
        ).to(torch.int64)

        b = torch.round(
            mean_y
            - mean_u * w.to(torch.float64)
        ).to(torch.int64)

        # HLS uses an arithmetic right shift, i.e. floor-like truncation.
        # Stage-4D targets were produced with round-to-nearest.  Add one
        # half-LSB before the final shift so that
        #
        #     (affine + 2^(s2-1)) >> s2
        #
        # approximates the Stage-4D round-to-nearest code instead of
        # systematically falling one code below it for roughly half of
        # the samples.
        b = b + (1 << (s2 - 1))

        if int(w.min()) < INT32_MIN or int(w.max()) > INT32_MAX:
            continue

        val_pre = (
            u * w[None, :]
            + b[None, :]
        )

        affine_over = (
            (val_pre < INT40_MIN)
            | (val_pre > INT40_MAX)
        )

        if bool(affine_over.any()):
            continue

        val40 = wrap_signed(val_pre, 40)
        rel = arshift(val40, s2)
        rel32 = wrap_signed(rel, 32)

        pred = torch.clamp(
            rel32,
            -4,
            3,
        )

        mismatch = float(
            (pred != y).to(torch.float32).mean()
        )

        mse = float(
            torch.mean(
                (pred.to(torch.float32) - y.to(torch.float32)) ** 2
            )
        )

        maxerr = int(
            torch.max(
                torch.abs(pred - y)
            )
        )

        cand = {
            "s2": int(s2),
            "lnw": w,
            "lnb": b,
            "mismatch": mismatch,
            "mse": mse,
            "maxerr": maxerr,
            "val_min": int(val_pre.min()),
            "val_max": int(val_pre.max()),
        }

        key = (
            mismatch,
            mse,
            maxerr,
            s2,
        )

        if best is None:
            best = cand
        else:
            best_key = (
                best["mismatch"],
                best["mse"],
                best["maxerr"],
                best["s2"],
            )
            if key < best_key:
                best = cand

    if best is None:
        raise RuntimeError("Could not fit safe LayerNorm affine parameters")

    return best


def fit_block_layernorm(x_real, target_q, eps):
    sx, st = settle_input_scale(x_real)

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
            "input_code_min": int(st["qx"].min()),
            "input_code_max": int(st["qx"].max()),
            "input_overflow_count": int(st["input_over"].sum()),
            "diff_min": int(st["diff"].min()),
            "diff_max": int(st["diff"].max()),
            "diff_overflow_count": int(st["diff_over"].sum()),
            "var_min": int(st["var36"].min()),
            "var_max": int(st["var36"].max()),
            "var_overflow_count": int(st["var_over"].sum()),
            "c_recip_mse": float(st["cpar"]["mse"]),
            "rsqrt_mse": float(rs["mse"]),
            "rsqrt_rel_p999": float(rs["rel_p999"]),
            "affine_mismatch_rate": float(af["mismatch"]),
            "affine_code_mse": float(af["mse"]),
            "affine_max_abs_code_error": int(af["maxerr"]),
            "affine_pre_min": int(af["val_min"]),
            "affine_pre_max": int(af["val_max"]),
            "lnw_min": int(af["lnw"].min()),
            "lnw_max": int(af["lnw"].max()),
            "lnb_min": int(af["lnb"].min()),
            "lnb_max": int(af["lnb"].max()),
        },
    }


def install_exact_layernorm(
    backbone,
    controller,
    input_scales,
    ln_scalars,
    ln_lnw,
    ln_lnb,
    ln_rsqrt,
    device,
):
    scales = controller.export_scales()
    handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]

        sx = float(input_scales[b])
        sy = float(scales[str(b)]["ln2_signed3_scale"])

        sc = ln_scalars[b]
        c1m = int(sc[0])
        c1s = int(sc[1])
        bias = int(sc[2])
        s1 = int(sc[3])
        bound = int(sc[4])
        s2 = int(sc[5])
        clamp_bits = int(sc[6])

        if clamp_bits != 3:
            raise RuntimeError("Expected LN clamp_bits=3")

        w = torch.tensor(
            ln_lnw[b].astype(np.int64),
            dtype=torch.int64,
            device=device,
        )
        bb = torch.tensor(
            ln_lnb[b].astype(np.int64),
            dtype=torch.int64,
            device=device,
        )
        rt = torch.tensor(
            ln_rsqrt[b].astype(np.int64),
            dtype=torch.int64,
            device=device,
        )

        def hook(
            module, inputs, output,
            sx=sx, sy=sy,
            c1m=c1m, c1s=c1s,
            bias=bias, s1=s1, bound=bound, s2=s2,
            w=w, bb=bb, rt=rt,
        ):
            x = inputs[0]

            qx_pre = torch.round(
                x / sx
            ).to(torch.int64)

            qx = wrap_signed(qx_pre, 15)

            acc = qx.sum(dim=-1)

            tmp = (
                acc * c1m
                + (1 << (c1s - 1))
            )
            tmp = wrap_signed(tmp, 32)

            mean = arshift(tmp, c1s)

            diff = qx - mean.unsqueeze(-1)
            diff = wrap_signed(diff, 15)

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

            rsqrt = rt[addr]

            val = (
                diff
                * rsqrt.unsqueeze(-1)
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
            block.norm2.register_forward_hook(hook)
        )

    return handles


def write_header(path, scalars, lnw, lnb, rsqrt):
    lines = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("// Generated by stage4g_exact_layernorm.py")
    lines.append("")

    lines.append("static const int LN_SCALARS[12][7] = {")
    for row in scalars:
        lines.append(
            "    {" + ", ".join(str(int(v)) for v in row) + "},"
        )
    lines.append("};")
    lines.append("")

    lines.append("static const int LN_LNW[12][192] = {")
    for row in lnw:
        lines.append(
            "    {" + ", ".join(str(int(v)) for v in row) + "},"
        )
    lines.append("};")
    lines.append("")

    lines.append("static const long long LN_LNB[12][192] = {")
    for row in lnb:
        lines.append(
            "    {" + ", ".join(str(int(v)) + "LL" for v in row) + "},"
        )
    lines.append("};")
    lines.append("")

    lines.append("static const int LN_RSQRT[12][128] = {")
    for row in rsqrt:
        lines.append(
            "    {" + ", ".join(str(int(v)) for v in row) + "},"
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
    ap.add_argument("--mlp-qat-checkpoint", required=True)
    ap.add_argument("--gelu-dir", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--data-root", required=True)

    ap.add_argument(
        "--output",
        default="stage4h_exact_layernorm_roundfix",
    )

    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fit-tokens", type=int, default=4096)
    ap.add_argument("--tokens-per-batch", type=int, default=64)

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

    # Keep Stage4F exact GELU active during LN fitting/evaluation.
    gelu_handles = install_exact_gelu(
        backbone,
        controller,
        args.gelu_dir,
        device,
    )

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

    scales = controller.export_scales()

    sampler = TokenSampler(
        args.fit_tokens,
        args.tokens_per_batch,
    )

    sample_handles = []

    for b in range(12):
        block = backbone.vit.blocks[b]
        sy = float(scales[str(b)]["ln2_signed3_scale"])

        def pre_hook(module, inputs, b=b):
            sampler.add_input(
                b,
                inputs[0],
            )

        def post_hook(module, inputs, output, b=b, sy=sy):
            sampler.add_target(
                b,
                output,
                sy,
            )

        sample_handles.append(
            block.norm2.register_forward_pre_hook(pre_hook)
        )
        # This hook is registered after the controller hook, so output is the
        # Stage4D signed-int3 surrogate target.
        sample_handles.append(
            block.norm2.register_forward_hook(post_hook)
        )

    full_model.eval()

    with torch.inference_mode():
        for step, (images, _) in enumerate(calib_loader, 1):
            images = images.to(device, non_blocking=True)
            _ = full_model(images)

            if sampler.done():
                print(
                    f"Collected {args.fit_tokens} LN tokens/block "
                    f"after calibration batch {step}"
                )
                break

            if step % 10 == 0:
                print(
                    f"calibration {step}/{len(calib_loader)}",
                    flush=True,
                )

    for h in sample_handles:
        h.remove()

    # ----------------------------------------------------------
    # Fit exact integer LayerNorm parameters.
    # ----------------------------------------------------------
    ln_scalars = np.zeros((12, 7), dtype=np.int32)
    ln_lnw = np.zeros((12, C), dtype=np.int32)
    ln_lnb = np.zeros((12, C), dtype=np.int64)
    ln_rsqrt = np.zeros((12, 128), dtype=np.int32)
    input_scales = np.zeros(12, dtype=np.float64)

    blocks_report = {}

    print()
    print("===== STAGE 4H: FIT INTEGER LAYERNORM + ROUNDING COMPENSATION =====")

    for b in range(12):
        x_real, target_q = sampler.get(b)
        eps = float(backbone.vit.blocks[b].norm2.eps)

        fit = fit_block_layernorm(
            x_real,
            target_q,
            eps,
        )

        input_scales[b] = fit["input_scale"]
        ln_scalars[b] = fit["scalars"]
        ln_lnw[b] = fit["lnw"]
        ln_lnb[b] = fit["lnb"]
        ln_rsqrt[b] = fit["rsqrt_table"]

        st = fit["stats"]

        blocks_report[str(b)] = {
            "input_int15_scale": float(fit["input_scale"]),
            "ln_scalars": fit["scalars"].astype(int).tolist(),
            "stats": st,
        }

        print(
            f"Block {b:2d}: "
            f"Sx={fit['input_scale']:.10g} "
            f"input=[{st['input_code_min']},{st['input_code_max']}] "
            f"diff=[{st['diff_min']},{st['diff_max']}] "
            f"var=[{st['var_min']},{st['var_max']}] "
            f"LN mismatch={100.0*st['affine_mismatch_rate']:.4f}% "
            f"maxerr={st['affine_max_abs_code_error']}"
        )

    np.save(out / "ln_input_scales.npy", input_scales)
    np.save(out / "ln_scalars.npy", ln_scalars)
    np.save(out / "ln_lnw.npy", ln_lnw)
    np.save(out / "ln_lnb.npy", ln_lnb)
    np.save(out / "ln_rsqrt_table.npy", ln_rsqrt)

    write_header(
        out / "generated_ln_params.h",
        ln_scalars,
        ln_lnw,
        ln_lnb,
        ln_rsqrt,
    )

    # Baseline with Stage4D LN surrogate + exact Stage4F GELU.
    baseline_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    exact_ln_handles = install_exact_layernorm(
        backbone,
        controller,
        input_scales,
        ln_scalars,
        ln_lnw,
        ln_lnb,
        ln_rsqrt,
        device,
    )

    exact_val = evaluate(
        full_model,
        val_loader,
        device,
    )

    report = {
        "scope": (
            "Exact MLP LayerNorm integer arithmetic + exact Stage4F GELU. "
            "LayerNorm input int15 real scales are fitted per block and are "
            "provisional until the Attention/residual scale chain is generated."
        ),
        "calibration_manifest": args.manifest,
        "fit_tokens_per_block": args.fit_tokens,
        "stage4d_ln_surrogate_plus_exact_gelu_val_top1": baseline_val,
        "exact_ln_plus_exact_gelu_val_top1": exact_val,
        "layernorm_drop_pp": baseline_val - exact_val,
        "ln_input_scales": input_scales.tolist(),
        "ln_scalars": ln_scalars.astype(int).tolist(),
        "blocks": blocks_report,
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
    print("===== STAGE 4H: EXACT LN ROUND-FIX EVAL =====")
    print(f"Surrogate LN + exact GELU val : {baseline_val:.4f}%")
    print(f"Exact integer LN + GELU val   : {exact_val:.4f}%")
    print(f"LayerNorm drop                : {baseline_val-exact_val:.4f} pp")
    print("Report:", out / "report.json")
    print("Header:", out / "generated_ln_params.h")

    for h in exact_ln_handles:
        h.remove()
    for h in gelu_handles:
        h.remove()
    controller.remove()


if __name__ == "__main__":
    main()
