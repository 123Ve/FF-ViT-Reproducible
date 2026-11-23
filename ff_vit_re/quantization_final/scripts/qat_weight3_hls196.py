#!/usr/bin/env python3

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
import timm
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


MEAN = (0.485, 0.456, 0.406)
STD  = (0.229, 0.224, 0.225)

QMIN = -4
QMAX = 3


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


class HLS196DeiT(nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        self.vit = timm.create_model(
            "deit_tiny_patch16_224",
            pretrained=False,
            num_classes=num_classes,
        )

        self.vit.pos_embed = nn.Parameter(
            torch.zeros(1, 196, 192)
        )

    def forward_features(self, x):
        x = self.vit.patch_embed(x)

        # HLS convention:
        # [CLS, patch1, ..., patch195]
        x = x[:, 1:, :]

        cls = self.vit.cls_token.expand(
            x.shape[0], -1, -1
        )

        x = torch.cat([cls, x], dim=1)

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
        return self.vit.forward_head(
            self.forward_features(x)
        )


def mse_init_scale(w):
    """
    与上一阶段类似，搜索一个初始 per-tensor scale。
    """
    w = w.detach().float().cpu()

    m = float(w.abs().max().item())

    if m == 0:
        return 1.0

    best_mse = None
    best_scale = None

    for i in range(101):
        ratio = 0.50 + 0.50 * i / 100
        alpha = m * ratio
        scale = alpha / 3.0

        q = torch.round(w / scale)
        q = torch.clamp(q, QMIN, QMAX)

        dq = q * scale

        mse = float(
            ((w - dq) ** 2).mean().item()
        )

        if best_mse is None or mse < best_mse:
            best_mse = mse
            best_scale = scale

    return best_scale


def round_ste(x):
    """
    Forward: round(x)
    Backward: identity STE
    """
    return x + (torch.round(x) - x).detach()


class Int3QATLinear(nn.Module):
    """
    保留 float shadow weight，
    forward 中使用 signed 3-bit fake quantized weight。

    qkv 使用 3 个独立 scale：
      Q / K / V

    普通 Linear 使用 1 个 scale。
    """

    def __init__(
        self,
        in_features,
        out_features,
        bias=True,
        segments=None,
    ):
        super().__init__()

        self.in_features = in_features
        self.out_features = out_features

        self.weight = nn.Parameter(
            torch.empty(out_features, in_features)
        )

        if bias:
            self.bias = nn.Parameter(
                torch.empty(out_features)
            )
        else:
            self.register_parameter(
                "bias", None
            )

        if segments is None:
            segments = [out_features]

        if sum(segments) != out_features:
            raise ValueError(
                "segments must sum to out_features"
            )

        self.segments = list(segments)

        # log(scale)，保证 scale > 0
        self.log_scale = nn.Parameter(
            torch.zeros(len(self.segments))
        )

    @classmethod
    def from_linear(cls, linear, segments=None):
        q = cls(
            linear.in_features,
            linear.out_features,
            bias=(linear.bias is not None),
            segments=segments,
        )

        with torch.no_grad():
            q.weight.copy_(linear.weight)

            if linear.bias is not None:
                q.bias.copy_(linear.bias)

            start = 0

            for i, n in enumerate(q.segments):
                part = linear.weight[
                    start:start+n
                ]

                s = mse_init_scale(part)

                q.log_scale[i] = math.log(
                    max(s, 1e-12)
                )

                start += n

        return q

    def get_scales(self):
        return torch.exp(
            self.log_scale
        ).clamp(min=1e-10)

    def fake_quant_weight(self):
        scales = self.get_scales()

        out = []
        start = 0

        for i, n in enumerate(self.segments):
            w = self.weight[
                start:start+n
            ]

            s = scales[i]

            z = w / s
            z = torch.clamp(
                z,
                QMIN,
                QMAX
            )

            q = round_ste(z)

            out.append(
                q * s
            )

            start += n

        return torch.cat(
            out,
            dim=0
        )

    @torch.no_grad()
    def export_integer(self):
        scales = self.get_scales()

        q_all = []
        start = 0

        for i, n in enumerate(self.segments):
            w = self.weight[
                start:start+n
            ]

            s = scales[i]

            q = torch.round(
                w / s
            ).clamp(
                QMIN,
                QMAX
            )

            q_all.append(
                q.to(torch.int8).cpu()
            )

            start += n

        return (
            torch.cat(q_all, dim=0),
            scales.detach().cpu(),
        )

    def forward(self, x):
        wq = self.fake_quant_weight()

        return F.linear(
            x,
            wq,
            self.bias
        )


def convert_backbone_to_qat(model):
    """
    只替换：
      Q/K/V
      O
      MLP1
      MLP2

    Patch、LN、Head 等保持 FP32。
    """

    for b in range(12):
        block = model.vit.blocks[b]

        # qkv = 576 x 192
        # 三个 192x192 matrix 独立 scale
        block.attn.qkv = (
            Int3QATLinear.from_linear(
                block.attn.qkv,
                segments=[192, 192, 192],
            )
        )

        block.attn.proj = (
            Int3QATLinear.from_linear(
                block.attn.proj
            )
        )

        block.mlp.fc1 = (
            Int3QATLinear.from_linear(
                block.mlp.fc1
            )
        )

        block.mlp.fc2 = (
            Int3QATLinear.from_linear(
                block.mlp.fc2
            )
        )


def train_transform():
    return transforms.Compose([
        transforms.RandomResizedCrop(
            224,
            scale=(0.8, 1.0)
        ),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(
            MEAN, STD
        ),
    ])


def eval_transform():
    return transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(
            MEAN, STD
        ),
    ])


@torch.inference_mode()
def evaluate(
    model,
    loader,
    device,
):
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
            enabled=(
                device.type == "cuda"
            ),
        ):
            logits = model(images)

        pred = logits.argmax(dim=1)

        correct += int(
            (pred == labels)
            .sum()
            .item()
        )

        total += labels.numel()

    return (
        100.0
        * correct
        / total
    )


def train_epoch(
    model,
    loader,
    optimizer,
    scaler,
    device,
):
    model.train()

    criterion = nn.CrossEntropyLoss()

    total = 0
    correct = 0
    loss_sum = 0.0

    for step, (
        images,
        labels
    ) in enumerate(loader, 1):

        images = images.to(
            device,
            non_blocking=True
        )

        labels = labels.to(
            device,
            non_blocking=True
        )

        optimizer.zero_grad(
            set_to_none=True
        )

        with torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
            enabled=(
                device.type == "cuda"
            ),
        ):
            logits = model(images)

            loss = criterion(
                logits,
                labels
            )

        scaler.scale(
            loss
        ).backward()

        scaler.unscale_(
            optimizer
        )

        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            1.0
        )

        scaler.step(
            optimizer
        )

        scaler.update()

        bs = labels.numel()

        total += bs

        loss_sum += (
            float(loss.item())
            * bs
        )

        correct += int(
            (
                logits.argmax(1)
                == labels
            )
            .sum()
            .item()
        )

        if step % 100 == 0:
            print(
                f"step "
                f"{step}/{len(loader)} "
                f"loss="
                f"{loss_sum/total:.5f} "
                f"top1="
                f"{100*correct/total:.3f}%",
                flush=True,
            )

    return (
        loss_sum / total,
        100.0 * correct / total,
    )


def export_int3(
    model,
    output_dir
):
    integer_weights = {}
    spec = {}

    for b in range(12):
        block = model.vit.blocks[b]

        modules = {
            "qkv": block.attn.qkv,
            "o": block.attn.proj,
            "mlp1": block.mlp.fc1,
            "mlp2": block.mlp.fc2,
        }

        # QKV
        q_int, scales = (
            modules["qkv"]
            .export_integer()
        )

        q, k, v = torch.chunk(
            q_int,
            3,
            dim=0
        )

        for i, (
            label,
            tensor
        ) in enumerate([
            ("q", q),
            ("k", k),
            ("v", v),
        ]):
            key = (
                f"blocks.{b}."
                f"attn.{label}.weight"
            )

            integer_weights[
                key
            ] = tensor

            spec[key] = {
                "scale":
                    float(
                        scales[i].item()
                    ),

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
            }

        # O / MLP1 / MLP2
        for label, module in [
            ("o", modules["o"]),
            ("mlp1", modules["mlp1"]),
            ("mlp2", modules["mlp2"]),
        ]:

            q_int, scales = (
                module.export_integer()
            )

            key = (
                f"blocks.{b}."
                f"{label}.weight"
            )

            integer_weights[
                key
            ] = q_int

            spec[key] = {
                "scale":
                    float(
                        scales[0].item()
                    ),

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
            }

    torch.save(
        integer_weights,
        output_dir
        / "backbone_int3_weights.pt"
    )

    with open(
        output_dir
        / "weight_quant_spec.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            spec,
            f,
            indent=2
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
        default="qat_weight3_hls196"
    )

    p.add_argument(
        "--epochs",
        type=int,
        default=8
    )

    p.add_argument(
        "--batch-size",
        type=int,
        default=32
    )

    p.add_argument(
        "--workers",
        type=int,
        default=4
    )

    p.add_argument(
        "--lr",
        type=float,
        default=2e-5
    )

    p.add_argument(
        "--scale-lr",
        type=float,
        default=5e-4
    )

    p.add_argument(
        "--weight-decay",
        type=float,
        default=0.02
    )

    p.add_argument(
        "--seed",
        type=int,
        default=20260921
    )

    args = p.parse_args()

    seed_all(
        args.seed
    )

    out = Path(
        args.output
    )

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    ckpt = torch.load(
        args.checkpoint,
        map_location="cpu",
        weights_only=True
    )

    if tuple(
        ckpt["model"][
            "pos_embed"
        ].shape
    ) != (1, 196, 192):
        raise RuntimeError(
            "Expected HLS196 checkpoint"
        )

    classes = list(
        ckpt["classes"]
    )

    num_classes = int(
        ckpt["num_classes"]
    )

    root = Path(
        args.data_root
    )

    train_ds = (
        datasets.ImageFolder(
            root / "train",
            transform=train_transform()
        )
    )

    val_ds = (
        datasets.ImageFolder(
            root / "val",
            transform=eval_transform()
        )
    )

    test_ds = (
        datasets.ImageFolder(
            root / "test",
            transform=eval_transform()
        )
    )

    if not (
        train_ds.classes
        == val_ds.classes
        == test_ds.classes
        == classes
    ):
        raise RuntimeError(
            "Class ordering mismatch"
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

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=(
            device.type == "cuda"
        ),
    )

    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(
            device.type == "cuda"
        ),
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

    # --------------------------
    # Build FP32 HLS196
    # --------------------------

    model = HLS196DeiT(
        num_classes
    )

    model.vit.load_state_dict(
        ckpt["model"],
        strict=True
    )

    # --------------------------
    # Replace 72 backbone
    # matrices by QAT layers
    # --------------------------

    convert_backbone_to_qat(
        model
    )

    model = model.to(
        device
    )

    initial_val = evaluate(
        model,
        val_loader,
        device
    )

    initial_test = evaluate(
        model,
        test_loader,
        device
    )

    print(
        "\n===== INITIAL "
        "W3 FAKE-QUANT ====="
    )

    print(
        f"Val Top-1 : "
        f"{initial_val:.4f}%"
    )

    print(
        f"Test Top-1: "
        f"{initial_test:.4f}%"
    )

    # --------------------------
    # Separate scale LR
    # --------------------------

    scale_params = []
    normal_params = []

    for name, param in (
        model.named_parameters()
    ):
        if "log_scale" in name:
            scale_params.append(
                param
            )
        else:
            normal_params.append(
                param
            )

    optimizer = torch.optim.AdamW(
        [
            {
                "params":
                    normal_params,

                "lr":
                    args.lr,

                "weight_decay":
                    args.weight_decay,
            },

            {
                "params":
                    scale_params,

                "lr":
                    args.scale_lr,

                "weight_decay":
                    0.0,
            },
        ]
    )

    scheduler = (
        torch.optim.lr_scheduler
        .CosineAnnealingLR(
            optimizer,
            T_max=args.epochs,
        )
    )

    scaler = (
        torch.amp.GradScaler(
            "cuda",
            enabled=(
                device.type
                == "cuda"
            ),
        )
    )

    best_val = -1.0

    best_path = (
        out
        / "best_qat_state.pth"
    )

    history = []

    # --------------------------
    # QAT
    # --------------------------

    for epoch in range(
        1,
        args.epochs + 1
    ):

        print(
            f"\nEpoch "
            f"{epoch}/{args.epochs}"
        )

        loss, train_top1 = (
            train_epoch(
                model,
                train_loader,
                optimizer,
                scaler,
                device,
            )
        )

        val_top1 = evaluate(
            model,
            val_loader,
            device,
        )

        scheduler.step()

        print(
            f"Epoch {epoch}: "
            f"loss={loss:.6f} "
            f"train_top1="
            f"{train_top1:.4f}% "
            f"val_top1="
            f"{val_top1:.4f}%"
        )

        history.append({
            "epoch": epoch,
            "loss": loss,
            "train_top1":
                train_top1,
            "val_top1":
                val_top1,
        })

        if val_top1 > best_val:
            best_val = val_top1

            torch.save({
                "model_state":
                    model.state_dict(),

                "classes":
                    classes,

                "num_classes":
                    num_classes,

                "epoch":
                    epoch,

                "val_top1":
                    val_top1,

                "architecture":
                    (
                        "deit_tiny_"
                        "hls196_"
                        "weight3_qat"
                    ),

            }, best_path)

            print(
                "Saved best:",
                best_path
            )

    # --------------------------
    # Reload best
    # --------------------------

    best = torch.load(
        best_path,
        map_location="cpu",
        weights_only=True
    )

    final_model = (
        HLS196DeiT(
            num_classes
        )
    )

    final_model.vit.load_state_dict(
        ckpt["model"],
        strict=True
    )

    convert_backbone_to_qat(
        final_model
    )

    final_model.load_state_dict(
        best["model_state"],
        strict=True
    )

    final_model = (
        final_model.to(
            device
        )
    )

    final_val = evaluate(
        final_model,
        val_loader,
        device,
    )

    final_test = evaluate(
        final_model,
        test_loader,
        device,
    )

    # --------------------------
    # Export int3 semantics
    # --------------------------

    export_int3(
        final_model,
        out
    )

    report = {
        "source_checkpoint":
            str(args.checkpoint),

        "initial_w3_val":
            initial_val,

        "initial_w3_test":
            initial_test,

        "best_val":
            final_val,

        "best_test":
            final_test,

        "epochs":
            history,

        "quantization": {
            "backbone_weight_bits":
                3,

            "integer_range":
                [-4, 3],

            "QKV_scales":
                "one per Q/K/V matrix",

            "O_MLP_scales":
                "one per matrix",

            "activations":
                "still floating point",

            "patch_head":
                "still floating point",
        }
    }

    with open(
        out / "report.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            report,
            f,
            indent=2
        )

    print()
    print(
        "===== FINAL "
        "WEIGHT-ONLY QAT ====="
    )

    print(
        f"Initial W3 test : "
        f"{initial_test:.4f}%"
    )

    print(
        f"Best QAT val    : "
        f"{final_val:.4f}%"
    )

    print(
        f"Best QAT test   : "
        f"{final_test:.4f}%"
    )

    print(
        "Output directory:",
        out
    )


if __name__ == "__main__":
    main()
