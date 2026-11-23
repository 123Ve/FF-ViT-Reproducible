#!/usr/bin/env python3
"""
Stage 4P: prepare FF-ViT PlantVillage artifacts for HLS C-simulation.

Run this in ~/Desktop/ff_vit_re, where your Stage4 output folders exist.

It produces:
  * fixed_patch_head_rom_plantvillage.h
  * block0_plantvillage.cpp
  * weights.bin                  (expected 2,772,096 bytes)
  * weights_fields.bin
  * pack_weights_hls.cpp         (independent ABI repacker/verifier)
  * deployment_manifest.json

Use --install only after verifying the generated files. It creates backups
before replacing the active HLS ROM, block0.cpp and weights.bin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import torch

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import MLPActivationController
from stage4j_attention_activation_qat import AttentionActivationController
from stage4k_exact_attention_outer import (
    quant_qkv_weights,
    quant_qkv_biases,
    quant_o_weight,
    quant_bias,
)
from stage4i_exact_mlp import quant_weight_int3


C = 192
N_BLOCKS = 12
ATTN_STRUCT_BYTES = 78688
MLP_STRUCT_BYTES = 152320
BLOCK_STRUCT_BYTES = 231008
WEIGHTS_BIN_BYTES = BLOCK_STRUCT_BYTES * N_BLOCKS


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def as_np(x, dtype=None):
    if torch.is_tensor(x):
        x = x.detach().cpu().numpy()
    a = np.asarray(x)
    if dtype is not None:
        a = a.astype(dtype)
    return a


def require_file(path: Path, what: str):
    if not path.is_file():
        raise FileNotFoundError(f"{what} not found: {path}")


def require_shape(name: str, a: np.ndarray, shape):
    if tuple(a.shape) != tuple(shape):
        raise RuntimeError(
            f"{name}: expected shape {shape}, got {tuple(a.shape)}"
        )


def find_array_end(text: str, start: int) -> int:
    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError("Opening brace not found")
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                semi = text.find(";", i)
                if semi < 0:
                    raise RuntimeError("Array semicolon not found")
                return semi + 1
    raise RuntimeError("Unterminated array")


def extract_head_block(text: str) -> str:
    start = text.find("const int HEAD_LN_SCALARS[8]")
    if start < 0:
        raise RuntimeError("HEAD_LN_SCALARS[8] not found")
    bias = text.find("HEAD_BIAS[1000]", start)
    if bias < 0:
        raise RuntimeError("HEAD_BIAS[1000] not found")
    end = find_array_end(text, bias)
    return text[start:end].strip() + "\n"


def replace_head_rom(old_rom: Path, safe_head: Path, out_rom: Path):
    old = old_rom.read_text(encoding="utf-8")
    new = safe_head.read_text(encoding="utf-8")

    start = old.find("const int HEAD_LN_SCALARS[8]")
    if start < 0:
        raise RuntimeError("Old ROM HEAD_LN_SCALARS not found")
    bias = old.find("HEAD_BIAS[1000]", start)
    if bias < 0:
        raise RuntimeError("Old ROM HEAD_BIAS not found")
    end = find_array_end(old, bias)

    new_head = extract_head_block(new)

    patched = (
        old[:start]
        + "// ===== PlantVillage Head: Stage4O2 safe export =====\n"
        + new_head
        + "\n"
        + old[end:]
    )

    # The entire PATCH prefix must remain byte-for-byte identical as text.
    if patched[:start] != old[:start]:
        raise AssertionError("PATCH prefix changed unexpectedly")

    out_rom.write_text(patched, encoding="utf-8")


def patch_block0(block0: Path, out_cpp: Path):
    text = block0.read_text(encoding="utf-8", errors="replace")

    exact_replacements = [
        (
            "typedef ap_uint<15> __head_ln_sum_t;",
            "typedef ap_int<15>  __head_ln_sum_t;",
        ),
        (
            "typedef ap_uint<30> __head_ln_divc_t;",
            "typedef ap_int<30>  __head_ln_divc_t;",
        ),
        (
            "typedef ap_uint<7>  __head_ln_mu_t;",
            "typedef ap_int<7>   __head_ln_mu_t;",
        ),
        (
            "typedef ap_uint<6>  __head_ln_cursor_t;",
            "typedef ap_uint<7>  __head_ln_cursor_t;",
        ),
    ]

    for old, new in exact_replacements:
        if old not in text:
            raise RuntimeError(
                f"Expected active Head typedef not found in {block0}: {old}"
            )
        text = text.replace(old, new)

    out_cpp.write_text(text, encoding="utf-8")


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


def load_arrays(args):
    k = Path(args.stage4k_dir)
    k2 = Path(args.stage4k2_dir)
    l = Path(args.stage4l_dir)
    m = Path(args.stage4m_dir)
    g = Path(args.stage4f_dir)

    A = {
        "attn_ln_scalars": np.load(k / "ln1_scalars.npy"),
        "attn_lnw": np.load(k / "ln1_lnw.npy"),
        "attn_lnb": np.load(k / "ln1_lnb.npy"),
        "attn_rsqrt": np.load(k / "ln1_rsqrt_table.npy"),

        "qq_scalars": np.load(k2 / "qq_scalars.npy"),
        "kq_scalars": np.load(k2 / "kq_scalars.npy"),
        "vq_scalars": np.load(k2 / "vq_scalars.npy"),
        "qq_table": np.load(k2 / "qq_table.npy"),
        "kq_table": np.load(k2 / "kq_table.npy"),
        "vq_table": np.load(k2 / "vq_table.npy"),

        "aq_scalars": np.load(l / "aq_scalars.npy"),
        "aq_table": np.load(l / "aq_table.npy"),
        "softmax_scalars": np.load(l / "softmax_scalars.npy"),
        "softmax_exp": np.load(l / "softmax_exp_table.npy"),
        "softmax_recip1": np.load(l / "softmax_recip_table_one.npy"),
        "softmax_recip2": np.load(
            l / "softmax_recip_table_two_int8.npy"
        ),

        "attn_scalars": np.load(m / "attn_scalars.npy"),
        "mlp_scalars": np.load(m / "mlp_scalars.npy"),
        "mlp_ln_scalars": np.load(m / "ln2_scalars.npy"),
        "mlp_lnw": np.load(m / "ln2_lnw.npy"),
        "mlp_lnb": np.load(m / "ln2_lnb.npy"),
        "mlp_rsqrt": np.load(m / "ln2_rsqrt_table.npy"),

        "ge_scalars": np.load(g / "ge_scalars.npy"),
        "ge_table": np.load(g / "ge_table.npy"),
    }

    shapes = {
        "attn_ln_scalars": (12, 7),
        "attn_lnw": (12, 192),
        "attn_lnb": (12, 192),
        "attn_rsqrt": (12, 128),
        "qq_scalars": (12, 4),
        "kq_scalars": (12, 4),
        "vq_scalars": (12, 4),
        "qq_table": (12, 64),
        "kq_table": (12, 64),
        "vq_table": (12, 64),
        "aq_scalars": (12, 4),
        "aq_table": (12, 64),
        "softmax_scalars": (12, 14),
        "softmax_exp": (12, 32),
        "softmax_recip1": (12, 64),
        "softmax_recip2": (12, 64),
        "attn_scalars": (12, 3),
        "mlp_scalars": (12, 2),
        "mlp_ln_scalars": (12, 7),
        "mlp_lnw": (12, 192),
        "mlp_lnb": (12, 192),
        "mlp_rsqrt": (12, 128),
        "ge_scalars": (12, 4),
        "ge_table": (12, 64),
    }

    for name, shape in shapes.items():
        require_shape(name, A[name], shape)

    return A


def rebuild_final_model(args):
    with open(args.ranges, "r", encoding="utf-8") as f:
        ranges = json.load(f)["statistics"]

    model, backbone, _ = rebuild_stage3_model(
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

    model.eval()
    mlp_ctrl.eval()
    attn_ctrl.eval()

    return backbone, mlp_ctrl, attn_ctrl


def quantize_block(backbone, mlp_ctrl, attn_ctrl, b: int):
    block = backbone.vit.blocks[b]

    s_ln1 = float(
        attn_ctrl.ln1_scale(b).detach().cpu()
    )

    qkv_w, qkv_sw = quant_qkv_weights(
        block.attn.qkv
    )

    qkv_acc_scales = [
        s_ln1 * float(qkv_sw[0]),
        s_ln1 * float(qkv_sw[1]),
        s_ln1 * float(qkv_sw[2]),
    ]

    qkv_b = quant_qkv_biases(
        block.attn.qkv,
        qkv_acc_scales,
        bits=(12, 11, 11),
    )

    q_w, k_w, v_w = [
        as_np(x, np.int8)
        for x in qkv_w
    ]

    q_b, k_b, v_b = [
        as_np(x, np.int16)
        for x in qkv_b
    ]

    a_scale = float(
        attn_ctrl.a_scale(b).detach().cpu()
    )

    o_w_t, o_sw = quant_o_weight(
        block.attn.proj
    )

    o_acc_scale = a_scale * float(o_sw)

    o_b_t = quant_bias(
        block.attn.proj,
        o_acc_scale,
        13,
    )

    o_w = as_np(o_w_t, np.int8)
    o_b = as_np(o_b_t, np.int16)

    s_m1 = float(
        mlp_ctrl.m1_scale(b).detach().cpu()
    )
    s_m2 = float(
        mlp_ctrl.m2_scale(b).detach().cpu()
    )

    m1_w_t, _ = quant_weight_int3(
        block.mlp.fc1
    )
    m2_w_t, _ = quant_weight_int3(
        block.mlp.fc2
    )

    m1_b_t = quant_bias(
        block.mlp.fc1,
        s_m1,
        11,
    )
    m2_b_t = quant_bias(
        block.mlp.fc2,
        s_m2,
        13,
    )

    q = {
        "q_w": as_np(q_w, np.int8),
        "k_w": as_np(k_w, np.int8),
        "v_w": as_np(v_w, np.int8),
        "q_b": as_np(q_b, np.int16),
        "k_b": as_np(k_b, np.int16),
        "v_b": as_np(v_b, np.int16),

        "o_w": as_np(o_w, np.int8),
        "o_b": as_np(o_b, np.int16),

        "m1_w": as_np(m1_w_t, np.int8),
        "m1_b": as_np(m1_b_t, np.int16),
        "m2_w": as_np(m2_w_t, np.int8),
        "m2_b": as_np(m2_b_t, np.int16),

        "scales": {
            "ln1": s_ln1,
            "q_acc": qkv_acc_scales[0],
            "k_acc": qkv_acc_scales[1],
            "v_acc": qkv_acc_scales[2],
            "a": a_scale,
            "o_acc": o_acc_scale,
            "m1_acc": s_m1,
            "m2_acc": s_m2,
        },
    }

    require_shape(f"b{b}.q_w", q["q_w"], (192, 192))
    require_shape(f"b{b}.k_w", q["k_w"], (192, 192))
    require_shape(f"b{b}.v_w", q["v_w"], (192, 192))
    require_shape(f"b{b}.o_w", q["o_w"], (192, 192))
    require_shape(f"b{b}.m1_w", q["m1_w"], (768, 192))
    require_shape(f"b{b}.m2_w", q["m2_w"], (192, 768))

    return q


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


PACKER_CPP = r"""
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <vector>
#include "dataflow.h"

static void die(const char* s) {
    std::fprintf(stderr, "ERROR: %s\n", s);
    std::exit(2);
}

template<class T>
static void rd(FILE* f, T* p, size_t n, const char* what) {
    if (std::fread(p, sizeof(T), n, f) != n) {
        std::fprintf(stderr, "short read: %s\n", what);
        std::exit(3);
    }
}

template<size_t N>
static void rd_pack3(FILE* f, Pack128_3 (&dst)[N],
                     size_t nvals, const char* what) {
    if (nvals % 32 || nvals / 32 != N) die("pack3 count mismatch");

    std::vector<int8_t> v(nvals);
    rd(f, v.data(), nvals, what);

    for (size_t p = 0; p < N; ++p) {
        dst[p].d = 0;
        for (int j = 0; j < 32; ++j) {
            ap_int<3> x = v[p * 32 + j];
            dst[p].d.range(j * 3 + 2, j * 3) = x.range(2, 0);
        }
    }
}

template<size_t N>
static void rd_pack16(FILE* f, Pack128_16 (&dst)[N],
                      size_t nvals, const char* what) {
    if (nvals % 8 || nvals / 8 != N) die("pack16 count mismatch");

    std::vector<int16_t> v(nvals);
    rd(f, v.data(), nvals, what);

    for (size_t p = 0; p < N; ++p) {
        dst[p].d = 0;
        for (int j = 0; j < 8; ++j) {
            ap_int<16> x = v[p * 8 + j];
            dst[p].d.range(j * 16 + 15, j * 16) = x.range(15, 0);
        }
    }
}

int main(int argc, char** argv) {
    if (argc != 3) {
        std::fprintf(stderr, "usage: %s fields.bin weights.bin\n", argv[0]);
        return 1;
    }

    std::printf("sizeof(Pack128_3)         = %zu\n", sizeof(Pack128_3));
    std::printf("sizeof(Pack128_16)        = %zu\n", sizeof(Pack128_16));
    std::printf("sizeof(AttnLayerWeights)  = %zu\n", sizeof(AttnLayerWeights));
    std::printf("sizeof(MlpLayerWeights)   = %zu\n", sizeof(MlpLayerWeights));
    std::printf("sizeof(BlockLayerWeights) = %zu\n", sizeof(BlockLayerWeights));

    if (sizeof(Pack128_3) != 16 ||
        sizeof(Pack128_16) != 16 ||
        sizeof(AttnLayerWeights) != 78688 ||
        sizeof(MlpLayerWeights) != 152320 ||
        sizeof(BlockLayerWeights) != 231008) {
        die("ABI differs from audited layout");
    }

    FILE* fi = std::fopen(argv[1], "rb");
    if (!fi) die("cannot open fields.bin");

    BlockLayerWeights L[12] = {};

    for (int b = 0; b < 12; ++b) {
        auto& a = L[b].attn_weights;
        auto& m = L[b].mlp_weights;

        rd_pack3(fi, a.q_weight, 192 * 192, "q_weight");
        rd_pack3(fi, a.k_weight, 192 * 192, "k_weight");
        rd_pack3(fi, a.v_weight, 192 * 192, "v_weight");

        rd_pack16(fi, a.q_bias, 192, "q_bias");
        rd_pack16(fi, a.k_bias, 192, "k_bias");
        rd_pack16(fi, a.v_bias, 192, "v_bias");

        rd_pack3(fi, a.o_weight, 192 * 192, "o_weight");
        rd_pack16(fi, a.o_bias, 192, "o_bias");

        rd(fi, a.attn_scalars, 3, "attn_scalars");
        rd(fi, a.ln_scalars, 7, "attn_ln_scalars");
        rd(fi, a.ln_lnw, 192, "attn_lnw");
        rd(fi, a.ln_lnb, 192, "attn_lnb");
        rd(fi, a.ln_rsqrt_table, 128, "attn_rsqrt");

        rd(fi, a.qq_scalars, 4, "qq_scalars");
        rd(fi, a.qq_table, 64, "qq_table");
        rd(fi, a.kq_scalars, 4, "kq_scalars");
        rd(fi, a.kq_table, 64, "kq_table");
        rd(fi, a.vq_scalars, 4, "vq_scalars");
        rd(fi, a.vq_table, 64, "vq_table");
        rd(fi, a.aq_scalars, 4, "aq_scalars");
        rd(fi, a.aq_table, 64, "aq_table");

        rd(fi, a.softmax_scalars, 14, "softmax_scalars");
        rd(fi, a.softmax_exp_table, 32, "softmax_exp");
        rd(fi, a.softmax_recip_table_one, 64, "softmax_recip1");
        rd(fi, a.softmax_recip_table_two, 64, "softmax_recip2");

        rd_pack3(fi, m.m1_weight, 768 * 192, "m1_weight");
        rd_pack16(fi, m.m1_bias, 768, "m1_bias");
        rd_pack3(fi, m.m2_weight, 192 * 768, "m2_weight");
        rd_pack16(fi, m.m2_bias, 192, "m2_bias");

        rd(fi, m.mlp_scalars, 2, "mlp_scalars");
        rd(fi, m.ln_scalars, 7, "mlp_ln_scalars");
        rd(fi, m.ln_lnw, 192, "mlp_lnw");
        rd(fi, m.ln_lnb, 192, "mlp_lnb");
        rd(fi, m.ln_rsqrt_table, 128, "mlp_rsqrt");
        rd(fi, m.ge_scalars, 4, "ge_scalars");
        rd(fi, m.ge_table, 64, "ge_table");
    }

    if (std::fgetc(fi) != EOF) die("fields.bin has trailing bytes");
    std::fclose(fi);

    FILE* fo = std::fopen(argv[2], "wb");
    if (!fo) die("cannot create weights.bin");

    if (std::fwrite(L, sizeof(BlockLayerWeights), 12, fo) != 12)
        die("short write");

    std::fclose(fo);

    std::printf("wrote %zu bytes\n", sizeof(BlockLayerWeights) * 12);
    return 0;
}
"""


def install(args, rom_out, cpp_out, weights_out):
    hls_src = Path(args.hls_src_dir)
    active_rom = hls_src / "fixed_patch_head_rom.h"
    active_cpp = hls_src / "block0.cpp"
    active_weights = Path(args.hls_weights)

    for p in (active_rom, active_cpp):
        require_file(p, str(p))

    for p in (active_rom, active_cpp, active_weights):
        if p.exists():
            bak = p.with_name(p.name + ".pre_stage4p.bak")
            if not bak.exists():
                shutil.copy2(p, bak)
                print("Backup:", bak)

    shutil.copy2(rom_out, active_rom)
    shutil.copy2(cpp_out, active_cpp)
    shutil.copy2(weights_out, active_weights)

    print("Installed:", active_rom)
    print("Installed:", active_cpp)
    print("Installed:", active_weights)


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--hls-src-dir",
        default="/home/user/Desktop/FF_Vit/flash_vit_2/src",
    )
    ap.add_argument(
        "--hls-weights",
        default="/home/user/Desktop/FF_Vit/flash_vit_2/weights.bin",
    )
    ap.add_argument(
        "--old-rom",
        default="/home/user/Desktop/FF_Vit/flash_vit_2/src/fixed_patch_head_rom.h",
    )
    ap.add_argument(
        "--block0",
        default="/home/user/Desktop/FF_Vit/flash_vit_2/src/block0.cpp",
    )
    ap.add_argument(
        "--safe-head",
        default="./stage4o2_head_safe/generated_head_rom_safe.h",
    )

    ap.add_argument(
        "--source-checkpoint",
        default="./plantvillage_hls196/best.pth",
    )
    ap.add_argument(
        "--qat-checkpoint",
        default="./qat_weight3_hls196/best_qat_state.pth",
    )
    ap.add_argument(
        "--stage3-dir",
        default="./stage3_patch_hls",
    )
    ap.add_argument(
        "--ranges",
        default="./stage4a_ranges/activation_ranges.json",
    )
    ap.add_argument(
        "--attention-qat-checkpoint",
        default="./stage4j_attention_qat/best_attention_qat.pth",
    )

    ap.add_argument(
        "--stage4f-dir",
        default="./stage4f_exact_gelu",
    )
    ap.add_argument(
        "--stage4k-dir",
        default="./stage4k_exact_attn_outer",
    )
    ap.add_argument(
        "--stage4k2-dir",
        default="./stage4k2_refined_qkv",
    )
    ap.add_argument(
        "--stage4l-dir",
        default="./stage4l_exact_softmax_aq",
    )
    ap.add_argument(
        "--stage4m-dir",
        default="./stage4m_exact_encoder",
    )

    ap.add_argument(
        "--output",
        default="./stage4p_hls_deploy",
    )
    ap.add_argument(
        "--install",
        action="store_true",
    )

    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    old_rom = Path(args.old_rom)
    block0 = Path(args.block0)
    safe_head = Path(args.safe_head)

    require_file(old_rom, "active fixed_patch_head_rom.h")
    require_file(block0, "active block0.cpp")
    require_file(safe_head, "Stage4O2 generated_head_rom_safe.h")
    require_file(
        Path(args.attention_qat_checkpoint),
        "Stage4J checkpoint",
    )

    print("Stage4O2 Head:", safe_head.resolve())

    rom_out = out / "fixed_patch_head_rom_plantvillage.h"
    cpp_out = out / "block0_plantvillage.cpp"

    replace_head_rom(
        old_rom,
        safe_head,
        rom_out,
    )
    patch_block0(
        block0,
        cpp_out,
    )

    A = load_arrays(args)
    backbone, mlp_ctrl, attn_ctrl = rebuild_final_model(args)

    qblocks = []

    print()
    print("===== FINAL W3/W8 PARAMETER EXPORT =====")

    for b in range(12):
        q = quantize_block(
            backbone,
            mlp_ctrl,
            attn_ctrl,
            b,
        )
        qblocks.append(q)

        print(
            f"Block {b:2d}: "
            f"Q[{q['q_w'].min()},{q['q_w'].max()}] "
            f"K[{q['k_w'].min()},{q['k_w'].max()}] "
            f"V[{q['v_w'].min()},{q['v_w'].max()}] "
            f"O[{q['o_w'].min()},{q['o_w'].max()}] "
            f"M1[{q['m1_w'].min()},{q['m1_w'].max()}] "
            f"M2[{q['m2_w'].min()},{q['m2_w'].max()}]"
        )

    weights_out = out / "weights.bin"

    with open(weights_out, "wb") as f:
        for b, q in enumerate(qblocks):
            block_bytes = (
                build_attn_struct(q, A, b)
                + build_mlp_struct(q, A, b)
            )

            if len(block_bytes) != BLOCK_STRUCT_BYTES:
                raise AssertionError(
                    f"Block {b}: {len(block_bytes)} bytes"
                )

            f.write(block_bytes)

    if weights_out.stat().st_size != WEIGHTS_BIN_BYTES:
        raise RuntimeError(
            f"weights.bin size = {weights_out.stat().st_size}, "
            f"expected {WEIGHTS_BIN_BYTES}"
        )

    fields_out = out / "weights_fields.bin"
    write_fields(
        fields_out,
        qblocks,
        A,
    )

    packer = out / "pack_weights_hls.cpp"
    packer.write_text(
        PACKER_CPP.lstrip(),
        encoding="utf-8",
    )

    manifest = {
        "weights_bin": {
            "bytes": weights_out.stat().st_size,
            "expected_bytes": WEIGHTS_BIN_BYTES,
            "sha256": sha256_file(weights_out),
        },
        "fixed_patch_head_rom": {
            "sha256": sha256_file(rom_out),
            "head_source": str(safe_head),
        },
        "block0": {
            "sha256": sha256_file(cpp_out),
            "head_type_changes": [
                "sum: ap_uint<15> -> ap_int<15>",
                "divc: ap_uint<30> -> ap_int<30>",
                "mean: ap_uint<7> -> ap_int<7>",
                "cursor: ap_uint<6> -> ap_uint<7>",
            ],
        },
        "provenance": {
            "weights_checkpoint": args.attention_qat_checkpoint,
            "attention_ln1": args.stage4k_dir,
            "qkv_luts": args.stage4k2_dir,
            "softmax_aq": args.stage4l_dir,
            "attention_residual_mlp_ln2_mlp_residual": args.stage4m_dir,
            "gelu": args.stage4f_dir,
            "head": args.safe_head,
        },
    }

    (out / "deployment_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print()
    print("===== STAGE 4P COMPLETE =====")
    print("ROM        :", rom_out)
    print("block0.cpp :", cpp_out)
    print(
        "weights.bin:",
        weights_out,
        f"({weights_out.stat().st_size} bytes)",
    )
    print("fields.bin :", fields_out)
    print("C++ verifier:", packer)
    print("manifest   :", out / "deployment_manifest.json")

    print()
    print("VERIFY PACKING BEFORE HLS C-SIM:")
    print("  source /path/to/Xilinx/Vitis/settings64.sh")
    print(
        f'  g++ -std=c++17 -Wno-unknown-pragmas '
        f'-I"$XILINX_HLS/include" -I"{args.hls_src_dir}" '
        f'"{packer}" -o "{out / "pack_weights_hls"}"'
    )
    print(
        f'  "{out / "pack_weights_hls"}" '
        f'"{fields_out}" "{out / "weights_hls.bin"}"'
    )
    print(
        f'  cmp -s "{weights_out}" "{out / "weights_hls.bin"}" '
        f'&& echo "PACKING MATCH" || echo "PACKING MISMATCH - STOP"'
    )

    if args.install:
        install(
            args,
            rom_out,
            cpp_out,
            weights_out,
        )


if __name__ == "__main__":
    main()
