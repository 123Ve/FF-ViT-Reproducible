import numpy as np
import re
import os


# 强健的文本解析函数
def parse_txt(filepath, dtype, expected_size):
    if not os.path.exists(filepath):
        print(f"❌ 找不到文件: {filepath}")
        return np.zeros(expected_size, dtype=dtype).tobytes()

    with open(filepath, 'r') as f:
        content = f.read()

    numbers = re.findall(r'-?\d+', content)
    arr = np.array(numbers, dtype=dtype)

    if len(arr) != expected_size:
        print(f"⚠️ {filepath} 大小不匹配! 找到 {len(arr)}，期望 {expected_size}")
        arr = np.resize(arr, expected_size)

    return arr.tobytes()


print("开始生成 C-Simulation 测试文件...")

# 1. 生成 Patch Embedding 权重 (需严格匹配 dataflow.h 中的 PatchEmbedWeights 结构体)
# 结构: scalars[4], weight[192*768], bias[196*192], cls[192]
with open("patch_weights.bin", 'wb') as f:
    f.write(parse_txt("refs/patch_embed_scalars.txt", np.int32, 4))
    f.write(parse_txt("refs/patch_embed_matmul_weight.txt", np.int32, 192 * 768))
    # 注意：你的 HLS 代码中 bias 是二维的 [T][CO]，也就是包含了 Positional Embedding
    f.write(parse_txt("refs/patch_embed_matmul_bias.txt", np.int32, 196 * 192))
    f.write(parse_txt("refs/patch_embed_cls.txt", np.int32, 192))
print("✅ 生成 patch_weights.bin 成功！")

# 2. 生成网络原始输入 (196 个 Patch，每个 768 像素)
with open("input.bin", 'wb') as f:
    # 注意：输入图像通常也是以 int32 存储在 txt 中，读取后 C++ 会转成 16-bit
    f.write(parse_txt("refs/patch_embed_input.txt", np.int32, 196 * 768))
print("✅ 生成 input.bin 成功！")

# 生成 Head 二进制整数权重 (纯量化整数)
with open("head_weights.bin", 'wb') as f:
    f.write(parse_txt("refs/head_lnq_scalars.txt", np.int32, 8))
    f.write(parse_txt("refs/head_lnq_lnw_m.txt", np.int32, 192))
    f.write(parse_txt("refs/head_lnq_lnb_m.txt", np.int64, 192)) # 64位无缝写入
    f.write(parse_txt("refs/head_lnq_rsqrt_table_m.txt", np.int32, 128))
    f.write(parse_txt("refs/head_matmul_weight.txt", np.int32, 1000 * 192))
    f.write(parse_txt("refs/head_matmul_bias.txt", np.int32, 1000))
print("✅ 生成 head_weights.bin 成功！")

# 🚨 将你的参考输出改回 1000 个类的整数 txt！
with open("output.bin", 'wb') as f:
    f.write(parse_txt("refs/head_output.txt", np.int32, 1000))