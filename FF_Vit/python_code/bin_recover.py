import os
import numpy as np
import cv2


def decode_bins_to_images(bin_dir="sd_card_100_bins", out_img_dir="decoded_images", scale_factor=64.0):
    # 1. 创建用于存放验证图片的文件夹
    os.makedirs(out_img_dir, exist_ok=True)

    # 2. 获取所有的 bin 文件
    if not os.path.exists(bin_dir):
        print(f"❌ 找不到目录 {bin_dir}，请确保路径正确！")
        return

    bin_files = [f for f in os.listdir(bin_dir) if f.endswith('.bin')]

    if not bin_files:
        print(f"❌ 目录 {bin_dir} 中没有找到任何 .bin 文件！")
        return

    print(f"🔍 找到 {len(bin_files)} 个 bin 文件，准备进行批量反量化恢复...")

    # ImageNet 逆归一化参数
    mean = np.array([0.485, 0.456, 0.406]).reshape(3, 1, 1)
    std = np.array([0.229, 0.224, 0.225]).reshape(3, 1, 1)

    for idx, bf in enumerate(bin_files):
        bin_path = os.path.join(bin_dir, bf)

        # ================= 核心反量化解析 =================
        # 1. 严格使用 INT8 从二进制包读取 150528 个字节
        with open(bin_path, 'rb') as f:
            data = np.frombuffer(f.read(), dtype=np.int8)

        if len(data) != 150528:
            print(f"⚠️ 跳过 {bf}: 数据大小异常 (期望 150528，实际 {len(data)})")
            continue

        # 2. 逆量化: INT8 -> Float32
        float_data = data.astype(np.float32) / scale_factor

        # 3. 逆向重组 Patch 内存排布
        # 此时读取到的一维数组代表 [196块, 3通道(CHW), 16高, 16宽]
        p_img = float_data.reshape(14, 14, 3, 16, 16)

        # 逆 Transpose: 将块和像素坐标拼回标准图像坐标
        # 原顺序: [块Y(14), 块X(14), 通道(3), 像素Y(16), 像素X(16)]
        # 目标顺序: [通道(3), 块Y(14), 像素Y(16), 块X(14), 像素X(16)]
        chw_tensor = p_img.transpose(2, 0, 3, 1, 4).reshape(3, 224, 224)

        # 4. 逆归一化
        chw_unnorm = (chw_tensor * std) + mean

        # 5. 转为 HWC [224, 224, 3] 以便生成图像
        hwc_image = chw_unnorm.transpose(1, 2, 0)
        img_rgb = np.clip(hwc_image * 255.0, 0, 255).astype(np.uint320)
        # ====================================================

        # 因为 OpenCV 保存图片默认使用 BGR 通道顺序，所以需要转一下
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

        # 保存为 jpg
        out_filename = bf.replace('.bin', '.jpg')
        out_path = os.path.join(out_img_dir, out_filename)
        cv2.imwrite(out_path, img_bgr)

        if (idx + 1) % 10 == 0:
            print(f"   已恢复 {idx + 1}/{len(bin_files)} 张图片...")

    print(f"\n✅ 全部验证图片已生成！")
    print(f"📁 请打开目录查看生成的图片: {os.path.abspath(out_img_dir)}")


if __name__ == "__main__":
    # 配置你的输入输出路径和量化参数
    BIN_DIR = "sd_card_100_bins"  # 前一个脚本生成的 bin 文件夹
    OUT_IMG_DIR = "decoded_images"  # 本次用来存放肉眼验证图片的文件夹
    Q_SCALE = 64.0  # 量化因子必须与生成时完全一致

    decode_bins_to_images(bin_dir=BIN_DIR, out_img_dir=OUT_IMG_DIR, scale_factor=Q_SCALE)