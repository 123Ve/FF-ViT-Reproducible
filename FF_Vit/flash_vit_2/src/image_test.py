import torch
import numpy as np
from PIL import Image
from torchvision import transforms

# 1. 定义标准的 ImageNet 预处理
transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# 2. 读取图片并预处理
img = Image.open("cat.jpg").convert('RGB')
img_tensor = transform(img).unsqueeze(0) # 形状变为 [1, 3, 224, 224]

# 3. 将输入图片量化/转换为你的 FPGA 期望的输入格式，并保存为 input.bin
# (注意：根据你之前的 patch_embed 逻辑，你可能需要将像素展平或按特征导出)
# 这里假设你之前是怎么把随机输入保存为 txt/bin 的，现在就怎么保存 img_tensor
export_input_to_fpga(img_tensor, "image/network_raw_input.txt")

# 4. 让 PyTorch 跑一遍完整的 TinyViT 前向传播
model.eval()
with torch.no_grad():
    logits = model(img_tensor) # 大小为 [1, 1000]

# 5. 打印 Python 端的 Top-5 分类结果
probs = torch.nn.functional.softmax(logits[0], dim=0)
top5_prob, top5_catid = torch.topk(probs, 5)

print("🎯 Python (PyTorch) 端的标准答案:")
for i in range(5):
    print(f"Top {i+1}: 类别 ID {top5_catid[i].item()} (置信度 {top5_prob[i].item():.4f})")