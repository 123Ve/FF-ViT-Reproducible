"""Original PlantVillage signed-fix Head LN fitter; provenance in exact manifest."""
import math
import numpy as np
import torch
from .exact import wrap as wrap_signed
C = 192
INT36_MIN = -(1 << 35)
INT36_MAX = (1 << 35)-1

def u_wrap(x, bits):
    return torch.remainder(x, 1 << bits)

def arshift(x, shift):
    return x >> shift

def signed_head_stats(
    qx, c1m=683, c1s=17, *, sum_bits=15, mean_bits=7, variance_bits=24
):
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
        (signed_sum < -(1 << (int(sum_bits) - 1)))
        | (signed_sum > (1 << (int(sum_bits) - 1)) - 1)
    )

    acc15 = wrap_signed(
        signed_sum,
        int(sum_bits),
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
        (mean_pre < -(1 << (int(mean_bits) - 1)))
        | (mean_pre > (1 << (int(mean_bits) - 1)) - 1)
    )

    mean7 = wrap_signed(
        mean_pre,
        int(mean_bits),
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
        var_raw > (1 << int(variance_bits)) - 1
    )

    var24 = u_wrap(
        var_raw,
        int(variance_bits),
    )

    return {
        "acc15": acc15,
        "mean7": mean7,
        "diff13": diff13,
        "var24": var24,
        "sum_bits": int(sum_bits),
        "mean_bits": int(mean_bits),
        "variance_bits": int(variance_bits),

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

    sum_bits = int(fit.get("sum_bits", 15))
    mean_bits = int(fit.get("mean_bits", 7))
    variance_bits = int(fit.get("variance_bits", 24))

    acc = wrap_signed(
        qx.sum(dim=1),
        sum_bits,
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
        mean_bits,
    )

    diff = wrap_signed(
        qx - mean[:, None],
        13,
    )

    var = u_wrap(
        (diff * diff).sum(dim=1),
        variance_bits,
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
    *,
    sum_bits=15,
    mean_bits=7,
    variance_bits=24,
):
    stats = signed_head_stats(
        qx_cal,
        sum_bits=sum_bits,
        mean_bits=mean_bits,
        variance_bits=variance_bits,
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
            "sum_bits": int(sum_bits),
            "mean_bits": int(mean_bits),
            "variance_bits": int(variance_bits),
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



