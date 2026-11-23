import os
import random
import cv2
import numpy as np


def generate_local_mini_dataset(base_dir, out_bin_dir="sd_card_300_bins", gt_file="gt_300.txt", num_samples=300,
                                scale_factor=64.0):
    os.makedirs(out_bin_dir, exist_ok=True)

    # 1. 获取所有子文件夹并按字母顺序排序，生成 0~999 的 ID 映射
    folder_names = sorted([d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))])

    if not folder_names:
        print(f"❌ 在 {base_dir} 中没有找到任何子文件夹，请检查路径！")
        return

    class_to_idx = {folder: i for i, folder in enumerate(folder_names)}
    print(f"📂 发现 {len(folder_names)} 个类别文件夹。")

    # 2. 全局采样：遍历所有文件夹，把所有图片都收集起来 (解决只能生成 1000 张的问题)
    all_available_images = []
    for folder in folder_names:
        folder_path = os.path.join(base_dir, folder)
        images = [img for img in os.listdir(folder_path) if img.lower().endswith(('.png', '.jpg', '.jpeg'))]
        for img in images:
            all_available_images.append((os.path.join(folder_path, img), class_to_idx[folder]))

    print(f"🖼️ 共找到 {len(all_available_images)} 张有效图片。")

    # 从 50000 张的大池子里随机抽取指定的数量 (5000)
    num_to_sample = min(num_samples, len(all_available_images))
    samples = random.sample(all_available_images, num_to_sample)

    print(f"🎲 已成功随机抽取 {len(samples)} 张图像，开始处理...")

    # 3. 处理图片并生成 bin 和 真值表
    with open(gt_file, 'w') as f_gt:
        for idx, (img_path, true_id) in enumerate(samples):
            # 读取图像并预处理
            img = cv2.imread(img_path)
            if img is None:
                print(f"⚠️ 跳过: 无法读取 {img_path}")
                continue

            img = cv2.resize(img, (224, 224))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # 转回 RGB

            # 归一化 (ImageNet标准)
            img = img / 255.0
            mean = np.array([0.485, 0.456, 0.406])
            std = np.array([0.229, 0.224, 0.225])
            img = (img - mean) / std

            # ================= 🌟 核心内存排布修改区 🌟 =================
            # 目标: [196块, 3通道, 16高, 16宽]
            img_chw = img.transpose(2, 0, 1)  # -> (3, 224, 224)
            img_split = img_chw.reshape(3, 14, 16, 14, 16)

            # 转置为连续的 Patch 流: (块Y, 块X, 通道, 像素Y, 像素X)
            patches = img_split.transpose(1, 3, 0, 2, 4)

            # 强制内存连续并展平
            patches = np.ascontiguousarray(patches).reshape(196, 768)
            # ==========================================================

            # 量化：乘以 scale -> 四舍五入 -> 限制在 INT8 范围 -> 强转 INT32 以满足 DMA 要求 (602112 bytes)
            quantized_patches = np.round(patches * scale_factor)
            quantized_patches = np.clip(quantized_patches, -128, 127).astype(np.int32)

            # 保存图像 bin 文件
            bin_path = os.path.join(out_bin_dir, f"{idx}.bin")
            with open(bin_path, 'wb') as f_bin:
                f_bin.write(quantized_patches.tobytes())

            # 写入文本格式真值表备查
            f_gt.write(f"{idx} {true_id}\n")

            if (idx + 1) % 100 == 0:
                print(f"   已处理 {idx + 1}/{len(samples)} 张...")

    print(f"\n✅ 全部图像转换完成！")
    print(f"📁 Bin 文件已存放至: {os.path.abspath(out_bin_dir)}")


if __name__ == "__main__":
    # 你的本地路径
    BASE_DIR = r"G:\a_graduate_materials\accelerate_FPGA_VIT\my_projects\Deit_tiny\deil_tiny_val\data_sets\val"
    Q_SCALE = 64.0
    TEST_SIZE = 800  # 5000 张测试集

    # 1. 生成 5000 个图像 bin 文件
    generate_local_mini_dataset(
        base_dir=BASE_DIR,
        out_bin_dir="sd_card_800_bins",
        gt_file="gt_800.txt",
        num_samples=TEST_SIZE,
        scale_factor=Q_SCALE
    )

    # 2. 将标签统一打包成连续的 32 位二进制文件 (供 FPGA 一次性读取)
    gt_ids = []
    with open("gt_800.txt", "r") as f:
        for line in f:
            true_id = int(line.strip().split()[1])
            gt_ids.append(true_id)

    np.array(gt_ids, dtype=np.int32).tofile("gt.bin")
    print(f"✅ gt.bin 生成完毕！共包含 {len(gt_ids)} 个标签。")
    print("👉 请将 'sd_card_5000_bins' 文件夹内的所有 .bin 文件，以及 'gt.bin'，全部拷贝到 SD 卡根目录下！")