"""Stage4P-v2 byte packing, preserving the audited native C++ ABI."""

import numpy as np
import torch

ATTN_STRUCT_BYTES = 78688
MLP_STRUCT_BYTES = 152320
BLOCK_STRUCT_BYTES = 231008
WEIGHTS_BIN_BYTES = BLOCK_STRUCT_BYTES * 12


def as_np(x, dtype=None):
    if torch.is_tensor(x):
        x = x.detach().cpu().numpy()
    a = np.asarray(x)
    if dtype is not None:
        a = a.astype(dtype)
    return a


def pack3_matrix(a) -> bytes:
    a = as_np(a, np.int64)
    if a.ndim != 2 or a.shape[1] % 32 != 0:
        raise ValueError(f"pack3 bad shape {a.shape}")
    if np.any(a < -4) or np.any(a > 3):
        raise ValueError(
            f"int3 out of range [{a.min()}, {a.max()}]"
        )

    out = bytearray()
    for row in a:
        for c0 in range(0, a.shape[1], 32):
            word = 0
            for j, v in enumerate(row[c0:c0 + 32]):
                word |= (int(v) & 0x7) << (3 * j)
            # HLS loaders consume get(0..31), i.e. low 96 bits.
            # High 32 bits are deliberately zero.
            out.extend(word.to_bytes(16, "little", signed=False))
    return bytes(out)


def pack16_vector(a) -> bytes:
    a = as_np(a, np.int64).reshape(-1)
    if a.size % 8 != 0:
        raise ValueError("pack16 element count not divisible by 8")
    if np.any(a < -32768) or np.any(a > 32767):
        raise ValueError(
            f"int16 out of range [{a.min()}, {a.max()}]"
        )

    out = bytearray()
    for i in range(0, a.size, 8):
        word = 0
        for j, v in enumerate(a[i:i + 8]):
            word |= (int(v) & 0xFFFF) << (16 * j)
        out.extend(word.to_bytes(16, "little", signed=False))
    return bytes(out)


def le_bytes(a, dtype: str) -> bytes:
    return (
        np.asarray(a)
        .astype(np.dtype(dtype), copy=False)
        .tobytes(order="C")
    )


def build_attn_struct(q, A, b):
    out = bytearray()

    out += pack3_matrix(q["q_w"])
    out += pack3_matrix(q["k_w"])
    out += pack3_matrix(q["v_w"])
    out += pack16_vector(q["q_b"])
    out += pack16_vector(q["k_b"])
    out += pack16_vector(q["v_b"])
    out += pack3_matrix(q["o_w"])
    out += pack16_vector(q["o_b"])

    out += le_bytes(A["attn_scalars"][b], "<i4")
    out += le_bytes(A["attn_ln_scalars"][b], "<i4")
    out += le_bytes(A["attn_lnw"][b], "<i4")
    out += le_bytes(A["attn_lnb"][b], "<i8")
    out += le_bytes(A["attn_rsqrt"][b], "<i4")

    out += le_bytes(A["qq_scalars"][b], "<i4")
    out += le_bytes(A["qq_table"][b], "i1")
    out += le_bytes(A["kq_scalars"][b], "<i4")
    out += le_bytes(A["kq_table"][b], "i1")
    out += le_bytes(A["vq_scalars"][b], "<i4")
    out += le_bytes(A["vq_table"][b], "i1")
    out += le_bytes(A["aq_scalars"][b], "<i4")
    out += le_bytes(A["aq_table"][b], "i1")

    out += le_bytes(A["softmax_scalars"][b], "<i4")
    out += le_bytes(A["softmax_exp"][b], "<u2")
    out += le_bytes(A["softmax_recip1"][b], "u1")
    out += le_bytes(A["softmax_recip2"][b], "i1")

    if len(out) != ATTN_STRUCT_BYTES:
        raise AssertionError(
            f"Attn bytes {len(out)} != {ATTN_STRUCT_BYTES}"
        )

    return bytes(out)


def build_mlp_struct(q, A, b):
    out = bytearray()

    out += pack3_matrix(q["m1_w"])
    out += pack16_vector(q["m1_b"])
    out += pack3_matrix(q["m2_w"])
    out += pack16_vector(q["m2_b"])

    out += le_bytes(A["mlp_scalars"][b], "<i4")
    out += le_bytes(A["mlp_ln_scalars"][b], "<i4")
    out += le_bytes(A["mlp_lnw"][b], "<i4")

    # C++ ABI alignment:
    # MlpLayerWeights::ln_lnb is int64_t[192], so it must start on an
    # 8-byte boundary. After ln_lnw the running offset is 150180,
    # which is only 4-byte aligned. The compiler inserts 4 padding bytes.
    out += bytes(4)

    out += le_bytes(A["mlp_lnb"][b], "<i8")
    out += le_bytes(A["mlp_rsqrt"][b], "<i4")
    out += le_bytes(A["ge_scalars"][b], "<i4")
    out += le_bytes(A["ge_table"][b], "u1")

    # sizeof(MlpLayerWeights)=152320. After the 4-byte internal pad above,
    # the field payload ends at 152312, leaving 8 bytes of tail padding.
    if len(out) != 152312:
        raise AssertionError(
            f"MLP field payload size {len(out)} != 152312"
        )

    out += bytes(8)

    return bytes(out)


def write_primitive(f, x, dtype):
    f.write(le_bytes(x, dtype))


def write_fields(path, qblocks, A):
    with open(path, "wb") as f:
        for b, q in enumerate(qblocks):
            write_primitive(f, q["q_w"], "i1")
            write_primitive(f, q["k_w"], "i1")
            write_primitive(f, q["v_w"], "i1")
            write_primitive(f, q["q_b"], "<i2")
            write_primitive(f, q["k_b"], "<i2")
            write_primitive(f, q["v_b"], "<i2")
            write_primitive(f, q["o_w"], "i1")
            write_primitive(f, q["o_b"], "<i2")

            write_primitive(f, A["attn_scalars"][b], "<i4")
            write_primitive(f, A["attn_ln_scalars"][b], "<i4")
            write_primitive(f, A["attn_lnw"][b], "<i4")
            write_primitive(f, A["attn_lnb"][b], "<i8")
            write_primitive(f, A["attn_rsqrt"][b], "<i4")
            write_primitive(f, A["qq_scalars"][b], "<i4")
            write_primitive(f, A["qq_table"][b], "i1")
            write_primitive(f, A["kq_scalars"][b], "<i4")
            write_primitive(f, A["kq_table"][b], "i1")
            write_primitive(f, A["vq_scalars"][b], "<i4")
            write_primitive(f, A["vq_table"][b], "i1")
            write_primitive(f, A["aq_scalars"][b], "<i4")
            write_primitive(f, A["aq_table"][b], "i1")
            write_primitive(f, A["softmax_scalars"][b], "<i4")
            write_primitive(f, A["softmax_exp"][b], "<u2")
            write_primitive(f, A["softmax_recip1"][b], "u1")
            write_primitive(f, A["softmax_recip2"][b], "i1")

            write_primitive(f, q["m1_w"], "i1")
            write_primitive(f, q["m1_b"], "<i2")
            write_primitive(f, q["m2_w"], "i1")
            write_primitive(f, q["m2_b"], "<i2")
            write_primitive(f, A["mlp_scalars"][b], "<i4")
            write_primitive(f, A["mlp_ln_scalars"][b], "<i4")
            write_primitive(f, A["mlp_lnw"][b], "<i4")
            write_primitive(f, A["mlp_lnb"][b], "<i8")
            write_primitive(f, A["mlp_rsqrt"][b], "<i4")
            write_primitive(f, A["ge_scalars"][b], "<i4")
            write_primitive(f, A["ge_table"][b], "u1")

