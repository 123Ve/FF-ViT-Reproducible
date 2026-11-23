"""Pure board-file contract; no inference, build or deployment side effects."""
import math
import numpy as np

DATASETS = {'plantvillage': (5459, 38), 'nwpu': (4500, 45)}
FRAME_BYTES = 301056
LOGIT_BYTES = 4000


def native_padding(blocks):
    result = []
    for block in blocks:
        item = dict(block)
        for key, size in (('_internal_padding', 4), ('_tail_padding', 8)):
            value = item[key]
            if isinstance(value, np.ndarray):
                if value.dtype != np.uint8 or value.shape != (size,):
                    raise ValueError('invalid portable ABI padding')
                value = value.tobytes()
            if not isinstance(value, bytes) or len(value) != size:
                raise ValueError('invalid native ABI padding')
            item[key] = value
        result.append(item)
    return result


def pack_input(image):
    x = np.asarray(image, dtype=np.float32)
    if x.shape != (3, 224, 224) or not np.isfinite(x).all():
        raise ValueError('expected finite normalized FP32 CHW[3,224,224]')
    q = np.clip(np.rint(x * np.float32(64)), -32768, 32767).astype('<i2')
    logical = q.reshape(3, 14, 16, 14, 16).transpose(1, 3, 0, 2, 4).reshape(196, 768)
    return logical.reshape(98, 2, 768).transpose(0, 2, 1).astype('<i2').tobytes()


def decode_s19(values):
    v = np.asarray(values, dtype=np.int64) & 0x7ffff
    return np.where(v >= 262144, v - 524288, v).astype(np.int32)


def top5(logits, classes):
    if not 5 <= classes <= 1000:
        raise ValueError('invalid class count')
    v = decode_s19(logits)
    if v.shape != (1000,):
        raise ValueError('expected 1000 hardware logits')
    return np.argsort(-v[:classes].astype(np.int64), kind='stable')[:5]


def validate_labels(name, labels):
    if name not in DATASETS:
        raise ValueError('unsupported dataset')
    count, classes = DATASETS[name]
    labels = np.asarray(labels)
    if labels.shape != (count,) or labels.dtype.kind not in 'iu':
        raise ValueError('must export the complete saved test split')
    if np.any(labels < 0) or np.any(labels >= classes):
        raise ValueError('invalid class labels')


def compare_logits(actual, reference):
    a, r = decode_s19(actual), decode_s19(reference)
    if a.shape != r.shape or a.ndim != 2 or a.shape[1] != 1000:
        raise ValueError('logit shapes differ or do not contain 1000 codes/frame')
    mismatch = a != r
    first = None
    if mismatch.any():
        i, j = map(int, np.argwhere(mismatch)[0])
        first = dict(frame=i, **{'class':j}, actual=int(a[i,j]), reference=int(r[i,j]))
    return dict(mismatches=int(mismatch.sum()), frames_with_mismatch=int(mismatch.any(1).sum()),
                max_ae=int(np.abs(a.astype(np.int64)-r).max()) if a.size else 0,
                first_mismatch=first)


def validate_release(r):
    for key in ('csim_pass', 'data_complete', 'identity_verified', 'clock_verified'):
        if r.get(key) is not True:
            raise ValueError('missing or failed gate: '+key)
    for key in ('wns', 'whs', 'wpws'):
        value = r.get(key)
        if not isinstance(value, (int,float)) or not math.isfinite(value) or value < 0:
            raise ValueError('missing or failed timing: '+key)
    for key in ('setup_fail', 'hold_fail', 'pulse_fail', 'routing_errors', 'unrouted', 'drc_errors'):
        if r.get(key) != 0:
            raise ValueError('missing or failed hardware check: '+key)
    if not isinstance(r.get('clock_mhz'), (int,float)) or not 300 <= r['clock_mhz'] <= 301:
        raise ValueError('unexpected configured core clock')
