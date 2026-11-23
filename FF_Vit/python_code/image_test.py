import numpy as np
from PIL import Image


def decode_vit_hardware_input(txt_input_path, output_image_path="decoded_input.jpg"):
    print(f"🔍 正在解析底层硬件输入数据: {txt_input_path} ...")

    # 1. 严格以有符号 INT8 读取
    with open(txt_input_path, 'r') as f:
        data_str = f.read().replace('\n', '').split(',')
    quantized_data = np.array([int(x.strip()) for x in data_str if x.strip()], dtype=np.int8)

    # 2. 校验数据完整性 (196 * 3 * 16 * 16 = 150528)
    if len(quantized_data) != 150528:
        raise ValueError(f"数据长度异常！期望 150528，实际为 {len(quantized_data)}。")

    # 3. 逆量化 (Scale = 64.0)
    float_data = quantized_data.astype(np.float32) / 64.0

    # 4. 逆向 Un-patchify：[196, 3, 16, 16] -> [3, 224, 224]
    p_img = float_data.reshape(14, 14, 3, 16, 16)
    chw_tensor = p_img.transpose(2, 0, 3, 1, 4).reshape(3, 224, 224)

    # 5. ImageNet 逆归一化
    mean = np.array([0.485, 0.456, 0.406]).reshape(3, 1, 1)
    std = np.array([0.229, 0.224, 0.225]).reshape(3, 1, 1)
    chw_unnorm = (chw_tensor * std) + mean

    # 6. 转为 HWC 并生成图片
    hwc_image = chw_unnorm.transpose(1, 2, 0)
    img_rgb = np.clip(hwc_image * 255.0, 0, 255).astype(np.uint8)

    Image.fromarray(img_rgb, 'RGB').save(output_image_path)
    print(f"✅ 完美解码！原图已恢复至: {output_image_path}")


# 使用示例
if __name__ == "__main__":
    decode_vit_hardware_input('patch_embed_input.txt')