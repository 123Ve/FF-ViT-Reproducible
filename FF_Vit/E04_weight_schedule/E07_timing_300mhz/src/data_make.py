import numpy as np
import re
import os

NUM_LAYERS = 12
C = 192
MLP_CH = 768
T = 196
CI = 768


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


# 🚀 补齐护城河函数
# 🚀 降维：适应 C++ alignas(32) 的 32 字节护城河函数
# 🚀 降维：适应 C++ alignas(16) 的 16 字节护城河函数
def pad_to_16bytes(b_array):
    rem = len(b_array) % 16
    if rem != 0:
        b_array += b'\x00' * (16 - rem)
    return b_array

def generate_all_bins():
    print("🚀 开始打包纯硬件验证文件...")

    with open("patch_weights.bin", 'wb') as f:
        f.write(parse_txt("refs/patch_embed_scalars.txt", np.int32, 4))
        f.write(parse_txt("refs/patch_embed_matmul_weight.txt", np.int32, C * CI))
        f.write(parse_txt("refs/patch_embed_matmul_bias.txt", np.int32, T * C))
        f.write(parse_txt("refs/patch_embed_cls.txt", np.int32, C))

    with open("input.bin", 'wb') as f:
        f.write(parse_txt("refs/patch_embed_input.txt", np.int32, T * CI))

    with open("output.bin", 'wb') as f:
        f.write(parse_txt("refs/head_output.txt", np.int32, 1000))

    with open("head_weights.bin", 'wb') as f:
        f.write(parse_txt("refs/head_lnq_scalars.txt", np.int32, 8))
        f.write(parse_txt("refs/head_lnq_lnw_m.txt", np.int32, C))
        f.write(parse_txt("refs/head_lnq_lnb_m.txt", np.int64, C))
        f.write(parse_txt("refs/head_lnq_rsqrt_table_m.txt", np.int32, 128))
        f.write(parse_txt("refs/head_matmul_weight.txt", np.int8, 1000 * C))
        f.write(parse_txt("refs/head_matmul_bias.txt", np.int32, 1000))

    with open("weights.bin", 'wb') as f_out:
        for layer in range(NUM_LAYERS):
            # ---------- A. Attn 层 ----------
            attn_bin = bytearray()
            attn_bin += parse_txt(f"refs/attn_{layer}_gen_q_matmul_weight.txt", np.int8, C * C)
            attn_bin += parse_txt(f"refs/attn_{layer}_gen_k_matmul_weight.txt", np.int8, C * C)
            attn_bin += parse_txt(f"refs/attn_{layer}_gen_v_matmul_weight.txt", np.int8, C * C)
            attn_bin += parse_txt(f"refs/attn_{layer}_gen_q_matmul_bias.txt", np.int16, C)
            attn_bin += parse_txt(f"refs/attn_{layer}_gen_k_matmul_bias.txt", np.int16, C)
            attn_bin += parse_txt(f"refs/attn_{layer}_gen_v_matmul_bias.txt", np.int16, C)
            attn_bin += parse_txt(f"refs/attn_{layer}_gen_o_matmul_weight.txt", np.int8, C * C)
            attn_bin += parse_txt(f"refs/attn_{layer}_gen_o_matmul_bias.txt", np.int16, C)

            attn_bin += parse_txt(f"refs/attn_{layer}_scalars.txt", np.int32, 3)
            attn_bin += parse_txt(f"refs/attn_{layer}_lnq_scalars.txt", np.int32, 7)
            attn_bin += parse_txt(f"refs/attn_{layer}_lnq_lnw_m.txt", np.int32, C)
            attn_bin += parse_txt(f"refs/attn_{layer}_lnq_lnb_m.txt", np.int64, C)
            attn_bin += parse_txt(f"refs/attn_{layer}_lnq_rsqrt_table_m.txt", np.int32, 128)

            attn_bin += parse_txt(f"refs/attn_{layer}_q_q_scalars.txt", np.int32, 4)
            attn_bin += parse_txt(f"refs/attn_{layer}_q_q_table_m.txt", np.int8, 64)
            attn_bin += parse_txt(f"refs/attn_{layer}_k_q_scalars.txt", np.int32, 4)
            attn_bin += parse_txt(f"refs/attn_{layer}_k_q_table_m.txt", np.int8, 64)
            attn_bin += parse_txt(f"refs/attn_{layer}_v_q_scalars.txt", np.int32, 4)
            attn_bin += parse_txt(f"refs/attn_{layer}_v_q_table_m.txt", np.int8, 64)
            attn_bin += parse_txt(f"refs/attn_{layer}_a_q_scalars.txt", np.int32, 4)
            attn_bin += parse_txt(f"refs/attn_{layer}_a_q_table_m.txt", np.int8, 64)

            attn_bin += parse_txt(f"refs/attn_{layer}_softmaxq_scalars.txt", np.int32, 14)
            attn_bin += parse_txt(f"refs/attn_{layer}_softmaxq_exp_opp_table_m.txt", np.uint16, 32)
            attn_bin += parse_txt(f"refs/attn_{layer}_softmaxq_recip_scaled_table_m_one.txt", np.uint8, 64)
            attn_bin += parse_txt(f"refs/attn_{layer}_softmaxq_recip_scaled_table_m_two.txt", np.int8, 64)

            # 🚨 关键修复1：Attn 层独立补齐，填满 C++ 强制加上的那 32 字节 Padding
            attn_bin = pad_to_16bytes(attn_bin)

            # ---------- B. MLP 层 ----------
            mlp_bin = bytearray()
            mlp_bin += parse_txt(f"refs/mlp_{layer}_matmul1_weight.txt", np.int8, MLP_CH * C)
            mlp_bin += parse_txt(f"refs/mlp_{layer}_matmul1_bias.txt", np.int16, MLP_CH)
            mlp_bin += parse_txt(f"refs/mlp_{layer}_matmul2_weight.txt", np.int8, C * MLP_CH)
            mlp_bin += parse_txt(f"refs/mlp_{layer}_matmul2_bias.txt", np.int16, C)

            mlp_bin += parse_txt(f"refs/mlp_{layer}_scalars.txt", np.int32, 2)
            mlp_bin += parse_txt(f"refs/mlp_{layer}_lnq_scalars.txt", np.int32, 7)
            mlp_bin += parse_txt(f"refs/mlp_{layer}_lnq_lnw_m.txt", np.int32, C)

            # C++ int64_t 的对齐补丁保留不变
            mlp_bin += b'\x00\x00\x00\x00'

            mlp_bin += parse_txt(f"refs/mlp_{layer}_lnq_lnb_m.txt", np.int64, C)
            mlp_bin += parse_txt(f"refs/mlp_{layer}_lnq_rsqrt_table_m.txt", np.int32, 128)
            mlp_bin += parse_txt(f"refs/mlp_{layer}_geluq_scalars.txt", np.int32, 4)
            mlp_bin += parse_txt(f"refs/mlp_{layer}_geluq_table_m.txt", np.uint8, 64)

            # 🚨 关键修复2：MLP 层独立补齐
            mlp_bin = pad_to_16bytes(mlp_bin)

            # 将完美绝缘的两块拼接到一起写入
            f_out.write(attn_bin + mlp_bin)

    print("✅ 全部打包完成！")


if __name__ == "__main__":
    generate_all_bins()