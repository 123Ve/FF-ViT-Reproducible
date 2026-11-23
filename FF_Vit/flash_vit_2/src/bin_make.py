import struct
import re
import os

# 1. 配置文件路径
input_txt_path = r"E:\Z_VIT_transformer\prj\ziyang\Vit_data_flow_v2\src\refs\mlp_11_output.txt"
output_bin_path = "mlp_11_output.bin"
def pack_txt_to_bin():
    if not os.path.exists(input_txt_path):
        print(f"❌ 找不到文件: {input_txt_path}")
        return
    print(f"正在读取文本文件: {input_txt_path} ...")
    with open(input_txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 2. 使用正则表达式提取所有整数 (自动处理逗号、换行、花括号等干扰字符)
    # 匹配可选的负号和数字
    str_numbers = re.findall(r'-?\d+', content)

    # 3. 转换为 Python 整数列表
    int_numbers = [int(num) for num in str_numbers]

    total_nums = len(int_numbers)
    print(f"✅ 成功提取了 {total_nums} 个数据点。")

    # 简单校验一下维度 (通常 196个Patch * 768通道 = 150528，或者你裁剪过的维度)
    if total_nums == 196 * 768:
        print("💡 维度校验匹配: 196 (T) * 768 (C)")
    else:
        print(f"⚠️ 提示: 数据总量为 {total_nums}，请确保与你的 C++ Testbench 期望维度一致。")

    # 4. 打包为二进制文件
    # struct.pack('<i', num) 意思是:
    # '<' 代表小端序 (Little-Endian, 适配 x86 和 ARM CPU)
    # 'i' 代表 4 字节(32-bit)有符号整数
    print(f"正在打包为二进制文件: {output_bin_path} ...")
    with open(output_bin_path, 'wb') as f:
        for num in int_numbers:
            f.write(struct.pack('<i', num))
    print("🎉 打包完成！")
if __name__ == "__main__":
    pack_txt_to_bin()