"""Streaming LayerNorm numerical audit kernels for the E07 backbone contract.

``fixed_layernorm`` uses either E07 finite widths or unlimited Python integer
arithmetic with *identical exported* mean rounding, LUT, shift, and clipping.
The unlimited path is not an ideal floating point LayerNorm. Numpy int64 is
used only when a conservative bound proves that each operation is safe;
otherwise the operation uses Python integers through dtype=object.

Native signed C++ overflow is modeled as hardware two's-complement wrapping.
A host reproduction needs -fwrapv; this module alone is not HLS csimulation.
Parameter/input arrays and returned traces cover only the caller's batch.
No state retains full dataset traces. NumPy FP32 uses no GPU, autocast or TF32.
"""
from __future__ import annotations

import math
import numpy as np

I64_MAX = (1 << 63) - 1


def _limits(bits):
    return -(1 << (bits - 1)), (1 << (bits - 1)) - 1


def _range(a):
    a = np.asarray(a)
    return (int(a.min()), int(a.max())) if a.size else (None, None)


def _magnitude(a):
    lo, hi = _range(a)
    return max(abs(lo), abs(hi)) if lo is not None else 0


def _binary(a, b, operation):
    a, b = np.asarray(a), np.asarray(b)
    am, bm = _magnitude(a), _magnitude(b)
    bound = am * bm if operation == 'mul' else am + bm
    dtype = object if bound > I64_MAX else np.int64
    a, b = a.astype(dtype, copy=False), b.astype(dtype, copy=False)
    if operation == 'mul':
        return a * b
    if operation == 'sub':
        return a - b
    return a + b


def _sum(a):
    dtype = object if _magnitude(a) * a.shape[-1] > I64_MAX else np.int64
    return np.sum(a.astype(dtype, copy=False), axis=-1, dtype=dtype)


def wrap_signed(a, bits):
    """Signed two's-complement cast, including values outside int64."""
    a = np.asarray(a)
    lo, hi = _limits(bits)
    amin, amax = _range(a)
    if amin is None or (amin >= lo and amax <= hi):
        return a.astype(np.int64 if bits <= 64 else object, copy=False)
    # Int64 modulo 2**64 and addition of 2**63 are unsafe; object avoids both.
    if bits >= 63 or a.dtype == object:
        out = (a.astype(object) + (1 << (bits-1))) % (1 << bits) - (1 << (bits-1))
    else:
        out = (a.astype(np.int64) & ((1 << bits)-1))
        out = np.where(out >= (1 << (bits-1)), out-(1 << bits), out)
    return np.asarray(out, dtype=np.int64 if bits <= 64 else object)


def _record(diagnostics, name, pre, post, bits=None, *, executed=True, clip=False):
    pre, post = np.asarray(pre), np.asarray(post)
    changed = int(np.count_nonzero(pre != post))
    pmin, pmax = _range(pre)
    qmin, qmax = _range(post)
    overflow = 0 if bits is None else int(np.count_nonzero((pre < _limits(bits)[0]) | (pre > _limits(bits)[1])))
    diagnostics[name] = dict(count=int(pre.size), bits=bits, pre_min=pmin, pre_max=pmax,
                             post_min=qmin, post_max=qmax, overflow_count=overflow,
                             wrap_count=changed if executed and not clip else 0,
                             saturation_count=changed if clip else 0,
                             low_clip_count=int(np.count_nonzero(pre < post)) if clip else 0,
                             high_clip_count=int(np.count_nonzero(pre > post)) if clip else 0)


def _cast(diagnostics, name, pre, bits, finite):
    post = wrap_signed(pre, bits) if finite else np.asarray(pre)
    _record(diagnostics, name, pre, post, bits, executed=finite)
    return post


def _integer_array(a, name):
    a = np.asarray(a)
    if a.dtype.kind not in 'iu' and not (a.dtype == object and all(isinstance(v, (int, np.integer)) for v in a.flat)):
        raise ValueError(f'{name} must contain integers')
    return a.astype(object if a.dtype == object or (a.dtype.kind == 'u' and a.size and int(a.max()) > I64_MAX) else np.int64)


def _validate(x, params, input_bits):
    x = _integer_array(x, 'inputs')
    if x.ndim != 2 or not 1 <= x.shape[1] <= 192 or x.shape[0] == 0:
        raise ValueError('inputs must have shape [nonzero tokens, channels<=192]')
    if not isinstance(input_bits, int) or not 2 <= input_bits <= 31:
        raise ValueError('input_bits must be in [2,31] (E07 uses 13 or 15)')
    lo, hi = _limits(input_bits)
    if int(x.min()) < lo or int(x.max()) > hi:
        raise ValueError('inputs must be actual signed input-width integer codes')
    p = {k: _integer_array(params[k], k) for k in ('scalars', 'lnw', 'lnb', 'rsqrt_table')}
    if p['scalars'].shape != (7,) or p['lnw'].shape != (x.shape[1],) or p['lnb'].shape != (x.shape[1],) or p['rsqrt_table'].shape != (128,):
        raise ValueError('parameter shapes must be scalars[7], lnw/lnb[channels], rsqrt_table[128]')
    m, ms, b, s1, bound, s2, bits = map(int, p['scalars'])
    if not (1 <= ms <= 31 and 0 <= s1 <= 63 and 0 <= s2 <= 63 and 0 <= bound < 128 and bits == 3):
        raise ValueError('invalid shifts/LUT bound; backbone output must be signed S3')
    for key, width in (('scalars', 32), ('lnw', 32), ('lnb', 64), ('rsqrt_table', 32)):
        lo, hi = _limits(width)
        if int(p[key].min()) < lo or int(p[key].max()) > hi:
            raise ValueError(f'{key} exceeds signed {width}-bit source storage')
    return x, p


def fixed_layernorm(x, params, *, input_bits=13, finite_width=True):
    """Return codes, per-batch intermediates and pre/post-cast diagnostics.

    ``finite_width=False`` removes finite-width casts, retaining the exported
    positive-half mean bias, arithmetic right shifts, LUT addressing/clamp,
    stored affine bias (including any fitted rounding), and final [-4,3] clip.
    Overflow_count still reports would-overflow values in that reference;
    wrap_count reports only casts actually executed and changed.
    """
    x, p = _validate(x, params, input_bits)
    m, ms, b, s1, bound, s2, _ = map(int, p['scalars'])
    d = {}
    acc = _cast(d, 'S', _sum(x), 32, finite_width)
    sq = _cast(d, 'S_sq', _sum(_binary(x, x, 'mul')), 64, finite_width)
    prod = _cast(d, 'mean_product', _binary(acc, m, 'mul'), 32, finite_width)
    rounded = _cast(d, 'mean_round_add', _binary(prod, 1 << (ms-1), 'add'), 32, finite_width)
    mean = _cast(d, 'mu', rounded >> ms, 32, finite_width)
    two_mu_s = _cast(d, '2muS', _binary(_binary(2, mean, 'mul'), acc, 'mul'), 64, finite_width)
    # Source has (long long)C * mean_wide * mean_wide, not native int32 C*mu².
    cmu2 = _cast(d, 'Cmu2', _binary(_binary(x.shape[1], mean, 'mul'), mean, 'mul'), 64, finite_width)
    partial = _cast(d, 'variance_sub64', _binary(sq, two_mu_s, 'sub'), 64, finite_width)
    wide = _cast(d, 'variance_add64', _binary(partial, cmu2, 'add'), 64, finite_width)
    var = _cast(d, 'Var_sum', wide, 36, finite_width)
    address_add = _cast(d, 'cursor_add', _binary(var, b, 'add'), 37, finite_width)
    raw_cursor = _cast(d, 'cursor', address_add >> s1, 32, finite_width)
    cursor = np.asarray(np.clip(raw_cursor, 0, bound), dtype=np.int64)
    _record(d, 'cursor_clip', raw_cursor, cursor, clip=True)
    rsqrt = p['rsqrt_table'][cursor]
    diff = _cast(d, 'diff', _binary(x, mean[:, None], 'sub'), input_bits, finite_width)
    affine_pre = _binary(_binary(_binary(diff, rsqrt[:, None], 'mul'), p['lnw'][None, :], 'mul'), p['lnb'][None, :], 'add')
    affine = _cast(d, 'affine', affine_pre, 40, finite_width)
    shifted = _cast(d, 'shifted', affine >> s2, 32, finite_width)
    codes = np.asarray(np.clip(shifted, -4, 3), dtype=np.int64)
    _record(d, 'output_clip', shifted, codes, clip=True)
    return dict(codes=codes, S=acc, S_sq=sq, mean=mean, variance=var,
                variance_wide=wide, cursor_unclamped=raw_cursor, cursor=cursor,
                rsqrt=rsqrt, diff=diff, affine=affine, shifted=shifted,
                diagnostics=d, finite_width=bool(finite_width))


def _reference_args(x, gamma, beta, input_scale, output_scale, eps):
    x = _integer_array(x, 'inputs')
    gamma, beta = np.asarray(gamma), np.asarray(beta)
    if x.ndim != 2 or gamma.shape != (x.shape[1],) or beta.shape != gamma.shape:
        raise ValueError('reference needs inputs[tokens,channels], gamma/beta[channels]')
    if not all(math.isfinite(float(s)) and float(s) > 0 for s in (input_scale, output_scale, eps)):
        raise ValueError('scales and epsilon must be positive and finite')
    if not np.all(np.isfinite(gamma)) or not np.all(np.isfinite(beta)):
        raise ValueError('gamma/beta must be finite')
    return x, gamma, beta


def fp32_reference(x, *, gamma, beta, input_scale, output_scale, eps=1e-6):
    """Local FP32 LN on the SAME dequantized integer inputs; ties-even codes."""
    x, gamma, beta = _reference_args(x, gamma, beta, input_scale, output_scale, eps)
    real_x = x.astype(np.float32) * np.float32(input_scale)
    mean = np.mean(real_x, axis=-1, keepdims=True, dtype=np.float32)
    diff = real_x - mean
    variance = np.mean(diff * diff, axis=-1, keepdims=True, dtype=np.float32)
    normalized = diff / np.sqrt(variance + np.float32(eps))
    real = normalized * gamma.astype(np.float32)[None, :] + beta.astype(np.float32)[None, :]
    codes = np.clip(np.rint(real / np.float32(output_scale)), -4, 3).astype(np.int64)
    return dict(real=real, codes=codes, normalized=normalized,
                mean=mean[:, 0], variance=variance[:, 0], dtype='float32', eps=float(eps))


def analytic_reference(x, *, gamma, beta, input_scale, output_scale, eps=1e-6):
    """Float64 analytic LN with real mean, distinct from exported arithmetic."""
    x, gamma, beta = _reference_args(x, gamma, beta, input_scale, output_scale, eps)
    xf = x.astype(np.float64)
    mean = xf.mean(axis=-1, keepdims=True)
    centered = xf - mean
    var_code = np.mean(centered * centered, axis=-1)
    rsqrt = 1 / np.sqrt(var_code + float(eps) / float(input_scale)**2)
    normalized = centered * rsqrt[:, None]
    real = normalized * gamma.astype(np.float64)[None, :] + beta.astype(np.float64)[None, :]
    codes = np.clip(np.rint(real / float(output_scale)), -4, 3).astype(np.int64)
    return dict(real=real, codes=codes, normalized=normalized, mean=mean[:, 0],
                variance=var_code * float(input_scale)**2, variance_code=var_code, rsqrt=rsqrt)


def compare_batch(x, params, *, input_bits=13, gamma, beta, input_scale, output_scale, eps=1e-6, r_exp=20):
    """One bounded batch of E07/unlimited/local FP32/analytic comparisons.

    real fields on fixed results mean dequantized OUTPUT CODES. FP32 real
    fields are continuous prequantization outputs. Compare code fields for
    exact-code and <=1 LSB metrics; compare real fields for physical units.
    Attribution benchmarks use the unlimited integer mean/variance so width
    effects are isolated by E07 versus unlimited, separately from LUT error.
    """
    hw = fixed_layernorm(x, params, input_bits=input_bits)
    ideal = fixed_layernorm(x, params, input_bits=input_bits, finite_width=False)
    args = dict(gamma=gamma, beta=beta, input_scale=input_scale, output_scale=output_scale, eps=eps)
    fp = fp32_reference(x, **args)
    analytic = analytic_reference(x, **args)
    hw['real'] = hw['codes'].astype(np.float64) * float(output_scale)
    ideal['real'] = ideal['codes'].astype(np.float64) * float(output_scale)
    var_code = np.asarray(ideal['variance'], dtype=np.float64) / np.asarray(x).shape[1]
    exact_rs = 1 / np.sqrt(var_code + float(eps) / float(input_scale)**2)
    lut_rs = np.asarray(ideal['rsqrt'], dtype=np.float64) / float(1 << r_exp)
    abs_terms = (np.abs(np.asarray(ideal['S_sq'], dtype=np.float64))
                 + 2 * np.abs(np.asarray(ideal['mean'], dtype=np.float64) * np.asarray(ideal['S'], dtype=np.float64))
                 + np.asarray(x).shape[1] * np.asarray(ideal['mean'], dtype=np.float64)**2)
    diff = np.asarray(ideal['diff'], dtype=np.float64)
    attribution = dict(mean_variance_real=var_code * float(input_scale)**2,
                       rounded_mean_variance_code=var_code,
                       analytic_variance_code=analytic['variance_code'],
                       exact_mean_rsqrt=exact_rs, lut_rsqrt=lut_rs,
                       rsqrt_error=lut_rs-exact_rs,
                       rsqrt_relative_error=np.abs(lut_rs-exact_rs)/exact_rs,
                       normalized_exact_rounded_mean=diff*exact_rs[:, None],
                       normalized_lut=diff*lut_rs[:, None],
                       variance_cancellation_ratio=abs_terms/np.maximum(np.asarray(ideal['variance'], dtype=np.float64), 1.))
    return dict(e07=hw, unlimited=ideal, fp32=fp, analytic=analytic, attribution=attribution)


class MetricAccumulator:
    """Element-weighted metrics with O(1) retained state and explicit units."""
    def __init__(self):
        self.count = self.exact = self.within1 = 0
        self.real_abs = self.real_sq = self.real_max = 0.
        self.code_abs = self.code_sq = self.code_max = 0.

    def update(self, pred, reference, code_pred, code_reference):
        pred, reference = np.asarray(pred, dtype=np.float64), np.asarray(reference, dtype=np.float64)
        cp, cr = _integer_array(code_pred, 'code prediction'), _integer_array(code_reference, 'code reference')
        if pred.shape != reference.shape or pred.shape != cp.shape or pred.shape != cr.shape:
            raise ValueError('metric arrays must have identical shapes')
        if not np.all(np.isfinite(pred)) or not np.all(np.isfinite(reference)):
            raise ValueError('metric arrays must be finite')
        re = np.abs(pred-reference)
        ce = np.asarray(np.abs(_binary(cp, cr, 'sub')), dtype=np.float64)
        self.count += pred.size
        self.real_abs += float(re.sum())
        self.real_sq += float(np.square(re).sum())
        self.code_abs += float(ce.sum())
        self.code_sq += float(np.square(ce).sum())
        self.real_max = max(self.real_max, float(re.max(initial=0)))
        self.code_max = max(self.code_max, float(ce.max(initial=0)))
        self.exact += int(np.count_nonzero(ce == 0))
        self.within1 += int(np.count_nonzero(ce <= 1))
        return self

    def merge(self, other):
        for key in ('count', 'exact', 'within1', 'real_abs', 'real_sq', 'code_abs', 'code_sq'):
            setattr(self, key, getattr(self, key)+getattr(other, key))
        self.real_max = max(self.real_max, other.real_max)
        self.code_max = max(self.code_max, other.code_max)
        return self

    def summary(self):
        n = self.count
        return dict(count=n, real_mae=self.real_abs/n if n else None,
                    real_rmse=math.sqrt(self.real_sq/n) if n else None,
                    real_maxae=self.real_max if n else None,
                    code_mae=self.code_abs/n if n else None,
                    code_rmse=math.sqrt(self.code_sq/n) if n else None,
                    code_maxae=self.code_max if n else None,
                    exact_code_agreement=self.exact/n if n else None,
                    within_1_lsb=self.within1/n if n else None)


class RangeAccumulator:
    """Merge pre/post ranges and executed wrap/clip counts without traces."""
    def __init__(self):
        self.rows = {}

    def update(self, diagnostics):
        for name, row in diagnostics.items():
            if name not in self.rows:
                self.rows[name] = dict(row)
                continue
            old = self.rows[name]
            if old['bits'] != row['bits']:
                raise ValueError('cannot combine different widths for same stage')
            for key in ('count', 'overflow_count', 'wrap_count', 'saturation_count', 'low_clip_count', 'high_clip_count'):
                old[key] += row[key]
            for key in ('pre_min', 'post_min'):
                if row[key] is not None:
                    old[key] = row[key] if old[key] is None else min(old[key], row[key])
            for key in ('pre_max', 'post_max'):
                if row[key] is not None:
                    old[key] = row[key] if old[key] is None else max(old[key], row[key])
        return self

    def merge(self, other):
        return self.update(other.rows)

    def summary(self):
        return {name: dict(row) for name, row in self.rows.items()}


class ErrorAccumulator:
    """Continuous error reduction for LUT/variance attribution, O(1) state."""
    def __init__(self):
        self.count = 0
        self.absolute_sum = self.square_sum = self.signed_sum = self.maximum = 0.

    def update(self, predicted, reference):
        predicted, reference = np.asarray(predicted, dtype=np.float64), np.asarray(reference, dtype=np.float64)
        if predicted.shape != reference.shape or not np.all(np.isfinite(predicted)) or not np.all(np.isfinite(reference)):
            raise ValueError('attribution arrays need identical shapes and finite values')
        error = predicted-reference
        self.count += error.size
        self.absolute_sum += float(np.abs(error).sum())
        self.square_sum += float(np.square(error).sum())
        self.signed_sum += float(error.sum())
        self.maximum = max(self.maximum, float(np.abs(error).max(initial=0)))
        return self

    def merge(self, other):
        for key in ('count', 'absolute_sum', 'square_sum', 'signed_sum'):
            setattr(self, key, getattr(self, key)+getattr(other, key))
        self.maximum = max(self.maximum, other.maximum)
        return self

    def summary(self):
        n = self.count
        return dict(count=n, mae=self.absolute_sum/n if n else None,
                    rmse=math.sqrt(self.square_sum/n) if n else None,
                    maxae=self.maximum if n else None, bias=self.signed_sum/n if n else None)


class AttributionAccumulator:
    """Independent variance, LUT and normalized-output error reductions.

    variance_code/real compare exported integer mean against FP64 real mean;
    lut_rsqrt isolates LUT versus analytic rsqrt at the SAME integer mean;
    normalized_lut includes only that LUT error; normalized_mean isolates
    mean approximation before exported affine fitting/final quantization.
    """
    def __init__(self):
        self.metrics = {k: ErrorAccumulator() for k in
                        ('variance_code', 'variance_real', 'lut_rsqrt',
                         'lut_rsqrt_relative', 'normalized_lut', 'normalized_mean')}
        self.cancellation_max = None

    def update(self, batch):
        a, analytic = batch['attribution'], batch['analytic']
        pairs = dict(variance_code=(a['rounded_mean_variance_code'], analytic['variance_code']),
                     variance_real=(a['mean_variance_real'], analytic['variance']),
                     lut_rsqrt=(a['lut_rsqrt'], a['exact_mean_rsqrt']),
                     lut_rsqrt_relative=(a['rsqrt_relative_error'], np.zeros_like(a['rsqrt_relative_error'])),
                     normalized_lut=(a['normalized_lut'], a['normalized_exact_rounded_mean']),
                     normalized_mean=(a['normalized_exact_rounded_mean'], analytic['normalized']))
        for key, values in pairs.items():
            self.metrics[key].update(*values)
        cm = float(np.asarray(a['variance_cancellation_ratio']).max())
        self.cancellation_max = cm if self.cancellation_max is None else max(self.cancellation_max, cm)
        return self

    def merge(self, other):
        for key in self.metrics:
            self.metrics[key].merge(other.metrics[key])
        if other.cancellation_max is not None:
            self.cancellation_max = other.cancellation_max if self.cancellation_max is None else max(self.cancellation_max, other.cancellation_max)
        return self

    def summary(self):
        return dict({k: v.summary() for k, v in self.metrics.items()},
                    variance_cancellation_ratio_max=self.cancellation_max)


def mathematical_bounds(params, *, input_bits=13, channels=192):
    """Sufficient full-domain bounds, not extrapolations from sampled data.

    Popoviciu: centered real-mean variance sum <= C*(hi-lo)^2/4.
    For any exported integer mean mu, sum(x-mu)^2 equals that centered
    statistic plus C*(mu-mean_real)^2, so it is nonnegative exactly.
    Conservative mean extrema below include native 32-bit product wrapping
    and the possibility of overflow while adding the mean rounding bias.
    40-bit affine sufficiency uses the actual input-width diff after cast.
    """
    if channels < 1 or channels > 192 or input_bits not in (13, 15):
        raise ValueError('published bounds support C<=192 and E07 S13/S15')
    p = {k: _integer_array(params[k], k) for k in ('scalars', 'lnw', 'lnb', 'rsqrt_table')}
    m, ms, _, _, _, _, _ = map(int, p['scalars'])
    lo, hi = _limits(input_bits)
    smin, smax = channels*lo, channels*hi
    pmin, pmax = sorted((smin*m, smax*m))
    bias = 1 << (ms-1)
    mean_safe = pmin >= -(1 << 31) and pmax+bias <= (1 << 31)-1
    if mean_safe:
        mu_min, mu_max = (pmin+bias) >> ms, (pmax+bias) >> ms
    else:
        mu_min, mu_max = -(1 << 31) >> ms, ((1 << 31)-1) >> ms
    delta = max(abs(lo-mu_max), abs(hi-mu_min))
    variance_bound = channels*delta*delta
    rsmax = _magnitude(p['rsqrt_table'])
    wmax, bmax = _magnitude(p['lnw']), _magnitude(p['lnb'])
    affine_bound = (1 << (input_bits-1))*rsmax*wmax+bmax
    balanced = (channels//2)*(lo*lo+hi*hi) + (lo*lo if channels % 2 else 0)
    return dict(channels=channels, input_bits=input_bits, S_min=smin, S_max=smax,
                S_sq_max=channels*lo*lo, mean_product_min=pmin, mean_product_max=pmax,
                mean_product32_full_domain_sufficient=mean_safe,
                mu_min_bound=mu_min, mu_max_bound=mu_max,
                two_mu_S_abs_bound=2*max(abs(mu_min), abs(mu_max))*max(abs(smin), abs(smax)),
                Cmu2_max_bound=channels*max(abs(mu_min), abs(mu_max))**2,
                centered_real_mean_variance_max_numerator=channels*(hi-lo)**2,
                centered_real_mean_variance_max_denominator=4,
                balanced_extrema_variance=balanced,
                variance_sum_nonnegative_exact=True, variance_sum_upper_bound=variance_bound,
                variance36_limit=(1 << 35)-1,
                variance36_full_domain_sufficient=variance_bound <= (1 << 35)-1,
                diff_abs_bound_after_cast=1 << (input_bits-1),
                affine_abs_upper_bound=affine_bound, affine40_limit=(1 << 39)-1,
                affine40_full_domain_sufficient=affine_bound <= (1 << 39)-1,
                note='Sufficient conservative parameter-dependent bounds; a false sufficiency result is not an actual-data overflow claim.')
