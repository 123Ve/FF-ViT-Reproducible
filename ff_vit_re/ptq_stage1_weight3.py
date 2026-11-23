#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import timm
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

QMIN = -4
QMAX = 3


class HLS196DeiT(nn.Module):
    """
    与当前 HLS token 语义一致的软件模型：

        token[0]   = CLS
        token[1:]  = 原标准 DeiT 的 patch1 ... patch195

    总 token 数：
        1 CLS + 195 patches = 196
    """

    def __init__(self, num_classes):
        super().__init__()

        self.vit = timm.create_model(
            "deit_tiny_patch16_224",
            pretrained=False,
            num_classes=num_classes,
        )

        # 当前 checkpoint 已经是 HLS196，
        # 因此 position embedding 长度固定为 196。
        self.vit.pos_embed = nn.Parameter(
            torch.zeros(1, 196, 192)
        )

    def forward_features(self, x):
        # 标准 patch embedding:
        # [B, 3, 224, 224] -> [B, 196, 192]
        x = self.vit.patch_embed(x)

        if tuple(x.shape[1:]) != (196, 192):
            raise RuntimeError(
                f"Unexpected patch embedding shape: {tuple(x.shape)}"
            )

        # 丢弃标准 DeiT 的 patch0，
        # 保留 patch1 ... patch195，共 195 个。
        x = x[:, 1:, :]

        cls = self.vit.cls_token.expand(
            x.shape[0], -1, -1
        )

        # [CLS, patch1, ..., patch195]
        x = torch.cat(
            [cls, x],
            dim=1
        )

        if x.shape[1] != 196:
            raise RuntimeError(
                f"Expected 196 tokens, got {x.shape[1]}"
            )

        if tuple(self.vit.pos_embed.shape) != (1, 196, 192):
            raise RuntimeError(
                f"Unexpected pos_embed shape: "
                f"{tuple(self.vit.pos_embed.shape)}"
            )

        x = x + self.vit.pos_embed

        x = self.vit.pos_drop(x)

        if hasattr(self.vit, "patch_drop"):
            x = self.vit.patch_drop(x)

        if hasattr(self.vit, "norm_pre"):
            x = self.vit.norm_pre(x)

        x = self.vit.blocks(x)
        x = self.vit.norm(x)

        return x

    def forward(self, x):
        x = self.forward_features(x)
        return self.vit.forward_head(x)


def make_eval_transform():
    return transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(
            IMAGENET_MEAN,
            IMAGENET_STD,
        ),
    ])


@torch.inference_mode()
def evaluate(model, loader, device):
    model.eval()

    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(
            device,
            non_blocking=True
        )

        labels = labels.to(
            device,
            non_blocking=True
        )

        with torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
            enabled=(device.type == "cuda"),
        ):
            logits = model(images)

        pred = logits.argmax(dim=1)

        correct += int(
            (pred == labels).sum().item()
        )

        total += int(
            labels.numel()
        )

    return 100.0 * correct / total


def quantize_int3_mse(
    weight,
    grid_steps=101,
):
    """
    单 tensor 对称 signed 3-bit 量化：

        q = clip(round(w / scale), -4, 3)

    但 scale 不直接固定为 max(|w|)/3，
    而是搜索 clipping alpha：

        alpha ∈ [0.5*max_abs, max_abs]

    选使 weight reconstruction MSE 最小的 scale。

    返回：
        q_int       : int8 容器，语义值范围 [-4,3]
        scale       : float
        dequantized : q_int * scale
        mse
        saturation_rate
    """

    w = weight.detach().float().cpu()

    max_abs = float(
        w.abs().max().item()
    )

    if max_abs == 0.0:
        q = torch.zeros_like(
            w,
            dtype=torch.int8
        )

        dq = torch.zeros_like(w)

        return (
            q,
            1.0,
            dq,
            0.0,
            0.0,
        )

    best = None

    for i in range(grid_steps):
        ratio = (
            0.50
            + 0.50
            * i
            / (grid_steps - 1)
        )

        alpha = max_abs * ratio

        # 正侧只有 +3，
        # 因而这里用 alpha / 3。
        scale = alpha / 3.0

        q = torch.round(
            w / scale
        )

        q = torch.clamp(
            q,
            QMIN,
            QMAX
        )

        dq = q * scale

        mse = float(
            torch.mean(
                (w - dq) ** 2
            ).item()
        )

        if (
            best is None
            or mse < best["mse"]
        ):
            saturation_rate = float(
                (
                    (q == QMIN)
                    | (q == QMAX)
                )
                .float()
                .mean()
                .item()
            )

            best = {
                "mse": mse,
                "scale": float(scale),
                "q": q.to(torch.int8),
                "dq": dq,
                "saturation_rate":
                    saturation_rate,
            }

    return (
        best["q"],
        best["scale"],
        best["dq"],
        best["mse"],
        best["saturation_rate"],
    )


def apply_backbone_weight3(
    model
):
    """
    只量化 Transformer 主干的：

        Q
        K
        V
        O
        MLP1
        MLP2

    共：
        12 blocks × 6 matrices = 72 matrices

    暂时不量化：
        Patch Embedding
        activations
        LayerNorm
        Softmax
        GELU
        classification Head
    """

    integer_weights = {}
    quant_spec = {}

    # 直接操作实际 Parameter，
    # 而不是只修改 state_dict 临时副本。
    with torch.no_grad():

        for block_idx in range(12):

            block = model.vit.blocks[
                block_idx
            ]

            # ==================================
            # Q/K/V
            # ==================================

            qkv_weight = (
                block.attn.qkv.weight
                .detach()
                .cpu()
            )

            if tuple(
                qkv_weight.shape
            ) != (576, 192):
                raise RuntimeError(
                    f"Block {block_idx} qkv shape "
                    f"is {tuple(qkv_weight.shape)}"
                )

            q_w, k_w, v_w = torch.chunk(
                qkv_weight,
                3,
                dim=0,
            )

            dq_parts = []

            for label, w in [
                ("q", q_w),
                ("k", k_w),
                ("v", v_w),
            ]:

                (
                    q_int,
                    scale,
                    dq,
                    mse,
                    saturation_rate,
                ) = quantize_int3_mse(w)

                key = (
                    f"blocks.{block_idx}."
                    f"attn.{label}.weight"
                )

                integer_weights[
                    key
                ] = q_int

                quant_spec[
                    key
                ] = {
                    "scale":
                        scale,

                    "qmin":
                        QMIN,

                    "qmax":
                        QMAX,

                    "bitwidth":
                        3,

                    "signed":
                        True,

                    "granularity":
                        "per_tensor",

                    "rounding":
                        "torch.round",

                    "shape":
                        list(
                            q_int.shape
                        ),

                    "mse":
                        mse,

                    "saturation_rate":
                        saturation_rate,
                }

                dq_parts.append(
                    dq
                )

            qkv_dq = torch.cat(
                dq_parts,
                dim=0
            )

            block.attn.qkv.weight.copy_(
                qkv_dq.to(
                    block.attn.qkv.weight.device
                )
            )

            # ==================================
            # O projection
            # ==================================

            (
                q_int,
                scale,
                dq,
                mse,
                saturation_rate,
            ) = quantize_int3_mse(
                block.attn.proj.weight
            )

            key = (
                f"blocks.{block_idx}."
                f"attn.o.weight"
            )

            integer_weights[
                key
            ] = q_int

            quant_spec[
                key
            ] = {
                "source_tensor":
                    (
                        f"blocks.{block_idx}."
                        f"attn.proj.weight"
                    ),

                "scale":
                    scale,

                "qmin":
                    QMIN,

                "qmax":
                    QMAX,

                "bitwidth":
                    3,

                "signed":
                    True,

                "granularity":
                    "per_tensor",

                "rounding":
                    "torch.round",

                "shape":
                    list(
                        q_int.shape
                    ),

                "mse":
                    mse,

                "saturation_rate":
                    saturation_rate,
            }

            block.attn.proj.weight.copy_(
                dq.to(
                    block.attn.proj.weight.device
                )
            )

            # ==================================
            # MLP1
            # ==================================

            (
                q_int,
                scale,
                dq,
                mse,
                saturation_rate,
            ) = quantize_int3_mse(
                block.mlp.fc1.weight
            )

            key = (
                f"blocks.{block_idx}."
                f"mlp1.weight"
            )

            integer_weights[
                key
            ] = q_int

            quant_spec[
                key
            ] = {
                "source_tensor":
                    (
                        f"blocks.{block_idx}."
                        f"mlp.fc1.weight"
                    ),

                "scale":
                    scale,

                "qmin":
                    QMIN,

                "qmax":
                    QMAX,

                "bitwidth":
                    3,

                "signed":
                    True,

                "granularity":
                    "per_tensor",

                "rounding":
                    "torch.round",

                "shape":
                    list(
                        q_int.shape
                    ),

                "mse":
                    mse,

                "saturation_rate":
                    saturation_rate,
            }

            block.mlp.fc1.weight.copy_(
                dq.to(
                    block.mlp.fc1.weight.device
                )
            )

            # ==================================
            # MLP2
            # ==================================

            (
                q_int,
                scale,
                dq,
                mse,
                saturation_rate,
            ) = quantize_int3_mse(
                block.mlp.fc2.weight
            )

            key = (
                f"blocks.{block_idx}."
                f"mlp2.weight"
            )

            integer_weights[
                key
            ] = q_int

            quant_spec[
                key
            ] = {
                "source_tensor":
                    (
                        f"blocks.{block_idx}."
                        f"mlp.fc2.weight"
                    ),

                "scale":
                    scale,

                "qmin":
                    QMIN,

                "qmax":
                    QMAX,

                "bitwidth":
                    3,

                "signed":
                    True,

                "granularity":
                    "per_tensor",

                "rounding":
                    "torch.round",

                "shape":
                    list(
                        q_int.shape
                    ),

                "mse":
                    mse,

                "saturation_rate":
                    saturation_rate,
            }

            block.mlp.fc2.weight.copy_(
                dq.to(
                    block.mlp.fc2.weight.device
                )
            )

    return (
        integer_weights,
        quant_spec,
    )


def main():

    p = argparse.ArgumentParser()

    p.add_argument(
        "--checkpoint",
        required=True
    )

    p.add_argument(
        "--data-root",
        required=True
    )

    p.add_argument(
        "--output",
        default=
            "ptq_stage1_weight3"
    )

    p.add_argument(
        "--batch-size",
        type=int,
        default=64
    )

    p.add_argument(
        "--workers",
        type=int,
        default=4
    )

    args = p.parse_args()

    checkpoint_path = Path(
        args.checkpoint
    )

    output_dir = Path(
        args.output
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # ======================================
    # Load HLS196 checkpoint
    # ======================================

    ckpt = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=True
    )

    if (
        not isinstance(ckpt, dict)
        or "model" not in ckpt
    ):
        raise RuntimeError(
            "Checkpoint must contain "
            "'model'"
        )

    state = ckpt["model"]

    if tuple(
        state["pos_embed"].shape
    ) != (1, 196, 192):
        raise RuntimeError(
            "Expected HLS196 checkpoint "
            "with pos_embed=(1,196,192), "
            f"got "
            f"{tuple(state['pos_embed'].shape)}"
        )

    classes = list(
        ckpt["classes"]
    )

    num_classes = int(
        ckpt["num_classes"]
    )

    # ======================================
    # Fixed test dataset
    # ======================================

    eval_tf = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(
            IMAGENET_MEAN,
            IMAGENET_STD,
        ),
    ])

    test_root = (
        Path(args.data_root)
        / "test"
    )

    test_ds = datasets.ImageFolder(
        test_root,
        transform=eval_tf
    )

    if list(
        test_ds.classes
    ) != classes:
        raise RuntimeError(
            "Test class ordering differs "
            "from checkpoint class ordering"
        )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        "Device:",
        device
    )

    print(
        "Test samples:",
        len(test_ds)
    )

    test_loader = DataLoader(
        test_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(
            device.type == "cuda"
        ),
    )

    # ======================================
    # FP32 HLS196 baseline
    # ======================================

    fp_model = HLS196DeiT(
        num_classes
    )

    fp_model.vit.load_state_dict(
        state,
        strict=True
    )

    fp_model = fp_model.to(
        device
    )

    fp32_top1 = evaluate(
        fp_model,
        test_loader,
        device
    )

    del fp_model

    if device.type == "cuda":
        torch.cuda.empty_cache()

    # ======================================
    # Weight-only W3 fake quant
    # ======================================

    w3_model = HLS196DeiT(
        num_classes
    )

    w3_model.vit.load_state_dict(
        state,
        strict=True
    )

    (
        integer_weights,
        quant_spec,
    ) = apply_backbone_weight3(
        w3_model
    )

    w3_model = w3_model.to(
        device
    )

    w3_top1 = evaluate(
        w3_model,
        test_loader,
        device
    )

    # ======================================
    # Save semantic integer weights
    # ======================================

    int_weight_path = (
        output_dir
        / "backbone_int3_weights.pt"
    )

    torch.save(
        integer_weights,
        int_weight_path
    )

    # Verify semantic integer range
    global_min = 999
    global_max = -999
    total_values = 0

    for name, tensor in (
        integer_weights.items()
    ):
        tmin = int(
            tensor.min().item()
        )

        tmax = int(
            tensor.max().item()
        )

        if (
            tmin < QMIN
            or tmax > QMAX
        ):
            raise RuntimeError(
                f"{name}: integer range "
                f"[{tmin},{tmax}] "
                f"outside [{QMIN},{QMAX}]"
            )

        global_min = min(
            global_min,
            tmin
        )

        global_max = max(
            global_max,
            tmax
        )

        total_values += (
            tensor.numel()
        )

    # ======================================
    # Quantization summary
    # ======================================

    spec_path = (
        output_dir
        / "weight_quant_spec.json"
    )

    with open(
        spec_path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            quant_spec,
            f,
            indent=2
        )

    avg_mse = sum(
        v["mse"]
        for v in quant_spec.values()
    ) / len(quant_spec)

    avg_sat = sum(
        v["saturation_rate"]
        for v in quant_spec.values()
    ) / len(quant_spec)

    report = {
        "checkpoint":
            str(
                checkpoint_path
                .resolve()
            ),

        "test_samples":
            len(test_ds),

        "num_classes":
            num_classes,

        "quantized_matrices":
            len(integer_weights),

        "total_quantized_weights":
            total_values,

        "semantic_integer_range":
            [
                global_min,
                global_max
            ],

        "fp32_hls196_top1":
            fp32_top1,

        "weight3_fakequant_top1":
            w3_top1,

        "top1_drop_pp":
            fp32_top1
            - w3_top1,

        "average_weight_mse":
            avg_mse,

        "average_saturation_rate":
            avg_sat,

        "scope":
            (
                "Only Transformer backbone "
                "Q/K/V/O and MLP1/MLP2 "
                "weights are quantized. "
                "Activations, Patch, "
                "LayerNorm, Softmax, GELU "
                "and Head remain floating "
                "point."
            )
    }

    report_path = (
        output_dir
        / "report.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            report,
            f,
            indent=2
        )

    print()
    print(
        "===== STAGE 1: "
        "WEIGHT-ONLY 3-BIT ====="
    )

    print(
        f"Quantized matrices     : "
        f"{len(integer_weights)}"
    )

    print(
        f"Quantized weight count : "
        f"{total_values}"
    )

    print(
        f"Semantic int range     : "
        f"[{global_min}, {global_max}]"
    )

    print(
        f"FP32 HLS196 Top-1      : "
        f"{fp32_top1:.4f}%"
    )

    print(
        f"W3 fake-quant Top-1    : "
        f"{w3_top1:.4f}%"
    )

    print(
        f"Top-1 drop             : "
        f"{fp32_top1-w3_top1:.4f} pp"
    )

    print(
        f"Average weight MSE     : "
        f"{avg_mse:.8g}"
    )

    print(
        f"Average saturation     : "
        f"{100*avg_sat:.4f}%"
    )

    print(
        "Integer weights:",
        int_weight_path
    )

    print(
        "Quant spec:",
        spec_path
    )

    print(
        "Report:",
        report_path
    )


if __name__ == "__main__":
    main()
