import numpy as np
import re
import os

NUM_LAYERS = 12
C = 192
MLP_CH = 768
T = 196
CI_PATCH = 768


def parse_txt(filepath, dtype, expected_size):
    if not os.path.exists(filepath):
        print(f"❌ 找不到文件: {filepath}")
        return np.zeros(expected_size, dtype=dtype).tobytes()

    with open(filepath, 'r') as f:
        content = f.read()

    numbers = re.findall(r'-?\d+', content)
    arr = np.array(numbers, dtype=np.int64)
    if len(arr) != expected_size:
        if len(arr) < expected_size:
            arr = np.pad(arr, (0, expected_size - len(arr)), mode='constant', constant_values=0)
        else:
            arr = arr[:expected_size]
    return arr.astype(dtype).tobytes()


# --- 骨干网专用：3-bit 两两打包 ---
def apply_csc_and_pack(arr_bytes, CO, CI, pad_to_max=True):
    arr = np.frombuffer(arr_bytes, dtype=np.int8).reshape(CO, CI)
    col_ptr = np.zeros(CI + 4, dtype=np.uint32)
    packed_data = []
    current_word_idx = 0

    for ci in range(CI):
        col_ptr[ci] = current_word_idx
        col_data = arr[:, ci]
        non_zeros = np.nonzero(col_data)[0]

        col_nz_list = []
        for co in non_zeros:
            val = col_data[co]
            v_bin = int(val) & 0x7
            co_bin = int(co) & 0x7FF
            element = (v_bin << 11) | co_bin
            col_nz_list.append(element)

        for i in range(0, len(col_nz_list), 2):
            elem0 = col_nz_list[i]
            elem1 = col_nz_list[i + 1] if i + 1 < len(col_nz_list) else 0
            packed = (elem1 << 16) | elem0
            packed_data.append(packed)
            current_word_idx += 1

    col_ptr[CI] = current_word_idx
    packed_arr = np.array(packed_data, dtype=np.uint32)

    if pad_to_max:
        max_packed_len = (CO * CI) // 2
        if len(packed_arr) < max_packed_len:
            packed_arr = np.pad(packed_arr, (0, max_packed_len - len(packed_arr)), mode='constant')
    return col_ptr.tobytes(), packed_arr.tobytes()


# --- 🚀 Head 层专用：8-bit 独立打包 ---
def apply_csc_and_pack_8bit(arr_bytes, CO, CI, pad_to_max=True):
    arr = np.frombuffer(arr_bytes, dtype=np.int8).reshape(CO, CI)
    col_ptr = np.zeros(CI + 4, dtype=np.uint32)
    packed_data = []

    current_word_idx = 0
    for ci in range(CI):
        col_ptr[ci] = current_word_idx
        col_data = arr[:, ci]
        non_zeros = np.nonzero(col_data)[0]

        for co in non_zeros:
            val = col_data[co]
            v_bin = int(val) & 0xFF
            co_bin = int(co) & 0x7FF
            packed = (v_bin << 11) | co_bin
            packed_data.append(packed)
            current_word_idx += 1

    col_ptr[CI] = current_word_idx
    packed_arr = np.array(packed_data, dtype=np.uint32)

    if pad_to_max:
        max_packed_len = CO * CI
        if len(packed_arr) < max_packed_len:
            packed_arr = np.pad(packed_arr, (0, max_packed_len - len(packed_arr)), mode='constant')

    return col_ptr.tobytes(), packed_arr.tobytes()


def pad_to_16bytes(b_array):
    rem = len(b_array) % 16
    if rem != 0:
        b_array += b'\x00' * (16 - rem)
    return b_array


def generate_all_bins():
    output_dir = "generated_bins_4HP"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"🚀 开始打包纯硬件 4-HP 并发版验证文件，存放至 '{output_dir}'...")

    # 不在主循环里的 Head, Patch 和输入输出直接生成
    with open(os.path.join(output_dir, "patch_weights.bin"), 'wb') as f:
        f.write(parse_txt("refs/patch_embed_scalars.txt", np.int32, 4))
        f.write(parse_txt("refs/patch_embed_matmul_weight.txt", np.int32, C * CI_PATCH))
        f.write(parse_txt("refs/patch_embed_matmul_bias.txt", np.int32, T * C))
        f.write(parse_txt("refs/patch_embed_cls.txt", np.int32, C))

    with open(os.path.join(output_dir, "input.bin"), 'wb') as f:
        f.write(parse_txt("refs/patch_embed_input.txt", np.int32, T * CI_PATCH))

    with open(os.path.join(output_dir, "output.bin"), 'wb') as f:
        f.write(parse_txt("refs/head_output.txt", np.int32, 1000))

    with open(os.path.join(output_dir, "head_weights.bin"), 'wb') as f:
        f.write(parse_txt("refs/head_lnq_scalars.txt", np.int32, 8))
        f.write(parse_txt("refs/head_lnq_lnw_m.txt", np.int32, C))
        f.write(parse_txt("refs/head_lnq_lnb_m.txt", np.int64, C))
        f.write(parse_txt("refs/head_lnq_rsqrt_table_m.txt", np.int32, 128))

        hw_w = parse_txt("refs/head_matmul_weight.txt", np.int8, 1000 * C)
        hw_ptr, hw_data = apply_csc_and_pack_8bit(hw_w, 1000, C, pad_to_max=True)
        f.write(hw_ptr)
        f.write(hw_data)
        f.write(parse_txt("refs/head_matmul_bias.txt", np.int32, 1000))

    # ==========================================
    # 🚀 核心改造：分别打开 4 个 HP 通道的文件，拆分打包
    # ==========================================
    with open(os.path.join(output_dir, "weights_hp0.bin"), 'wb') as f_hp0, \
         open(os.path.join(output_dir, "weights_hp1.bin"), 'wb') as f_hp1, \
         open(os.path.join(output_dir, "weights_hp2.bin"), 'wb') as f_hp2, \
         open(os.path.join(output_dir, "weights_hp3.bin"), 'wb') as f_hp3:

        for layer in range(NUM_LAYERS):
            hp0_bin = bytearray()
            hp1_bin = bytearray()
            hp2_bin = bytearray()
            hp3_bin = bytearray()

            # ----------------------------------------------------
            # 💠 HP0 专属包 (严格遵循 Weights_HP0 的交织顺序)
            # ----------------------------------------------------
            q_w = parse_txt(f"refs/attn_{layer}_gen_q_matmul_weight.txt", np.int8, C * C)
            q_ptr, q_data = apply_csc_and_pack(q_w, C, C, pad_to_max=True)
            hp0_bin += (q_ptr + q_data)
            hp0_bin += parse_txt(f"refs/attn_{layer}_gen_q_matmul_bias.txt", np.int16, C)

            k_w = parse_txt(f"refs/attn_{layer}_gen_k_matmul_weight.txt", np.int8, C * C)
            k_ptr, k_data = apply_csc_and_pack(k_w, C, C, pad_to_max=True)
            hp0_bin += (k_ptr + k_data)
            hp0_bin += parse_txt(f"refs/attn_{layer}_gen_k_matmul_bias.txt", np.int16, C)

            v_w = parse_txt(f"refs/attn_{layer}_gen_v_matmul_weight.txt", np.int8, C * C)
            v_ptr, v_data = apply_csc_and_pack(v_w, C, C, pad_to_max=True)
            hp0_bin += (v_ptr + v_data)
            hp0_bin += parse_txt(f"refs/attn_{layer}_gen_v_matmul_bias.txt", np.int16, C)

            # ----------------------------------------------------
            # 💠 HP1 专属包 (严格遵循 Weights_HP1 顺序)
            # ----------------------------------------------------
            o_w = parse_txt(f"refs/attn_{layer}_gen_o_matmul_weight.txt", np.int8, C * C)
            o_ptr, o_data = apply_csc_and_pack(o_w, C, C, pad_to_max=True)
            hp1_bin += (o_ptr + o_data)
            hp1_bin += parse_txt(f"refs/attn_{layer}_gen_o_matmul_bias.txt", np.int16, C)

            hp1_bin += parse_txt(f"refs/attn_{layer}_scalars.txt", np.int32, 3)
            hp1_bin += parse_txt(f"refs/attn_{layer}_lnq_scalars.txt", np.int32, 7)
            hp1_bin += parse_txt(f"refs/attn_{layer}_lnq_lnw_m.txt", np.int32, C)
            hp1_bin += parse_txt(f"refs/attn_{layer}_lnq_lnb_m.txt", np.int64, C)
            hp1_bin += parse_txt(f"refs/attn_{layer}_lnq_rsqrt_table_m.txt", np.int32, 128)

            hp1_bin += parse_txt(f"refs/attn_{layer}_q_q_scalars.txt", np.int32, 4)
            hp1_bin += parse_txt(f"refs/attn_{layer}_k_q_scalars.txt", np.int32, 4)
            hp1_bin += parse_txt(f"refs/attn_{layer}_v_q_scalars.txt", np.int32, 4)
            hp1_bin += parse_txt(f"refs/attn_{layer}_a_q_scalars.txt", np.int32, 4)

            hp1_bin += parse_txt(f"refs/attn_{layer}_q_q_table_m.txt", np.int8, 64)
            hp1_bin += parse_txt(f"refs/attn_{layer}_k_q_table_m.txt", np.int8, 64)
            hp1_bin += parse_txt(f"refs/attn_{layer}_v_q_table_m.txt", np.int8, 64)
            hp1_bin += parse_txt(f"refs/attn_{layer}_a_q_table_m.txt", np.int8, 64)

            hp1_bin += parse_txt(f"refs/attn_{layer}_softmaxq_scalars.txt", np.int32, 14)
            hp1_bin += parse_txt(f"refs/attn_{layer}_softmaxq_exp_opp_table_m.txt", np.uint16, 32)
            hp1_bin += parse_txt(f"refs/attn_{layer}_softmaxq_recip_scaled_table_m_one.txt", np.uint8, 64)
            hp1_bin += parse_txt(f"refs/attn_{layer}_softmaxq_recip_scaled_table_m_two.txt", np.int8, 64)

            # ----------------------------------------------------
            # 💠 HP2 专属包 (严格遵循 Weights_HP2 顺序)
            # ----------------------------------------------------
            m1_w = parse_txt(f"refs/mlp_{layer}_matmul1_weight.txt", np.int8, MLP_CH * C)
            m1_ptr, m1_data = apply_csc_and_pack(m1_w, MLP_CH, C)
            hp2_bin += (m1_ptr + m1_data)
            hp2_bin += parse_txt(f"refs/mlp_{layer}_matmul1_bias.txt", np.int16, MLP_CH)

            # ----------------------------------------------------
            # 💠 HP3 专属包 (严格遵循 Weights_HP3 顺序)
            # ----------------------------------------------------
            m2_w = parse_txt(f"refs/mlp_{layer}_matmul2_weight.txt", np.int8, C * MLP_CH)
            m2_ptr, m2_data = apply_csc_and_pack(m2_w, C, MLP_CH)
            hp3_bin += (m2_ptr + m2_data)
            hp3_bin += parse_txt(f"refs/mlp_{layer}_matmul2_bias.txt", np.int16, C)

            hp3_bin += parse_txt(f"refs/mlp_{layer}_scalars.txt", np.int32, 2)
            hp3_bin += parse_txt(f"refs/mlp_{layer}_lnq_scalars.txt", np.int32, 7)
            hp3_bin += parse_txt(f"refs/mlp_{layer}_lnq_lnw_m.txt", np.int32, C)

            # 🚨 极其重要：保留为了对齐 int64_t ln_lnb 所需的 4 字节 Padding
            hp3_bin += b'\x00\x00\x00\x00'

            hp3_bin += parse_txt(f"refs/mlp_{layer}_lnq_lnb_m.txt", np.int64, C)
            hp3_bin += parse_txt(f"refs/mlp_{layer}_lnq_rsqrt_table_m.txt", np.int32, 128)
            hp3_bin += parse_txt(f"refs/mlp_{layer}_geluq_scalars.txt", np.int32, 4)
            hp3_bin += parse_txt(f"refs/mlp_{layer}_geluq_table_m.txt", np.uint8, 64)

            # ----------------------------------------------------
            # 对齐 16 字节，保证 HLS 128-bit Burst 完美跨层衔接
            # ----------------------------------------------------
            hp0_bin = pad_to_16bytes(hp0_bin)
            hp1_bin = pad_to_16bytes(hp1_bin)
            hp2_bin = pad_to_16bytes(hp2_bin)
            hp3_bin = pad_to_16bytes(hp3_bin)

            f_hp0.write(hp0_bin)
            f_hp1.write(hp1_bin)
            f_hp2.write(hp2_bin)
            f_hp3.write(hp3_bin)

    print(f"✅ 全部 4-HP 数据打包完成！文件已保存在 './{output_dir}/' 目录下。")


if __name__ == "__main__":
    generate_all_bins()