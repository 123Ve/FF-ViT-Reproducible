#!/usr/bin/env python3
"""
Stage 4D: MLP hardware-aware activation QAT for FF-ViT.

Purpose
-------
Recover accuracy under the actual MLP boundary widths of the current HLS skeleton:

    LayerNorm output : signed 3-bit
    MLP1 accumulator : signed 11-bit
    GELU output      : unsigned 3-bit
    MLP2 accumulator : signed 13-bit
    block/FM output  : signed 13-bit

This stage intentionally does NOT yet emulate the internal integer LayerNorm rsqrt LUT
or the final GELU address LUT bit-for-bit. Instead it trains the model to tolerate the
same low-bit boundary formats and the scale coupling imposed by the HLS datapath.

After accuracy recovery, the learned scales are converted into:
    ln_scalars / ln_lnw / ln_lnb / ln_rsqrt_table
    ge_scalars / ge_table
    m1_bias / m2_bias / mlp_scalars
and checked with a bit-accurate integer emulator.

The script expects the helper scripts created in the previous stages to be present in
the same working directory.
"""

import argparse
import copy
import json
import math
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from stage4b_activation_ptq_eval import rebuild_stage3_model
from qat_weight3_hls196 import eval_transform


# ---------------------------------------------------------------------
# Quantizer helpers
# ---------------------------------------------------------------------

def ste_round(x):
    return x + (torch.round(x) - x).detach()


def fake_quant_ste(x, scale, qmin, qmax):
    scale = torch.clamp(scale, min=1e-12)
    z = x / scale
    z = torch.clamp(z, qmin, qmax)
    q = ste_round(z)
    return q * scale


def module_weight_scale(module):
    """
    Int3QATLinear from the previous weight-QAT stage stores learnable log_scale.
    MLP fc1/fc2 use one scale per matrix.
    """
    if not hasattr(module, "log_scale"):
        raise RuntimeError(
            f"{type(module).__name__} has no log_scale; "
            "expected the Int3QATLinear module from qat_weight3_hls196.py"
        )

    s = torch.exp(module.log_scale)

    if s.numel() != 1:
        raise RuntimeError(
            f"Expected one weight scale for {type(module).__name__}, "
            f"got shape {tuple(s.shape)}"
        )

    return s.reshape(())


# ---------------------------------------------------------------------
# Hardware-aware MLP activation controller
# ---------------------------------------------------------------------

class MLPActivationController(nn.Module):
    """
    Learnable per-block activation scales.

    HLS-compatible scale coupling:
        S_m1_acc = S_ln2 * S_w1
        S_m2_acc = S_gelu * S_w2

    Final block/FM output is kept in the same real scale as MLP2 accumulator,
    which is the condition required by the HLS residual merge.
    """

    def __init__(self, backbone, ranges):
        super().__init__()
        self.backbone = backbone

        ln_init = []
        ge_init = []

        for b in range(12):
            ln = float(ranges[f"b{b}.ln2_out"]["abs_p999"]) / 3.0
            ge = float(ranges[f"b{b}.gelu_out"]["abs_p999"]) / 7.0

            ln_init.append(max(ln, 1e-4))
            ge_init.append(max(ge, 1e-4))

        self.log_ln2_scale = nn.Parameter(
            torch.log(torch.tensor(ln_init, dtype=torch.float32))
        )
        self.log_gelu_scale = nn.Parameter(
            torch.log(torch.tensor(ge_init, dtype=torch.float32))
        )

        self.active_blocks = set(range(12))
        self.handles = []

    def ln2_scale(self, b):
        return torch.exp(self.log_ln2_scale[b])

    def gelu_scale(self, b):
        return torch.exp(self.log_gelu_scale[b])

    def m1_scale(self, b):
        block = self.backbone.vit.blocks[b]
        return self.ln2_scale(b) * module_weight_scale(block.mlp.fc1)

    def m2_scale(self, b):
        block = self.backbone.vit.blocks[b]
        return self.gelu_scale(b) * module_weight_scale(block.mlp.fc2)

    def set_active(self, blocks):
        self.active_blocks = set(int(x) for x in blocks)

    def is_active(self, b):
        return b in self.active_blocks

    def install(self):
        if self.handles:
            raise RuntimeError("Hooks are already installed")

        for b in range(12):
            block = self.backbone.vit.blocks[b]

            # LN2 output -> signed int3 [-4,3]
            def ln2_hook(module, inputs, output, b=b):
                if not self.is_active(b):
                    return output
                return fake_quant_ste(
                    output,
                    self.ln2_scale(b),
                    -4,
                    3,
                )

            self.handles.append(
                block.norm2.register_forward_hook(ln2_hook)
            )

            # MLP1 output -> signed int11 [-1024,1023]
            # Scale is coupled to LN2 scale * W1 scale.
            def m1_hook(module, inputs, output, b=b):
                if not self.is_active(b):
                    return output
                return fake_quant_ste(
                    output,
                    self.m1_scale(b),
                    -1024,
                    1023,
                )

            self.handles.append(
                block.mlp.fc1.register_forward_hook(m1_hook)
            )

            # GELU output -> unsigned int3 [0,7]
            def gelu_hook(module, inputs, output, b=b):
                if not self.is_active(b):
                    return output
                return fake_quant_ste(
                    output,
                    self.gelu_scale(b),
                    0,
                    7,
                )

            self.handles.append(
                block.mlp.act.register_forward_hook(gelu_hook)
            )

            # MLP2 output -> signed int13 [-4096,4095]
            # Scale is coupled to GELU scale * W2 scale.
            def m2_hook(module, inputs, output, b=b):
                if not self.is_active(b):
                    return output
                return fake_quant_ste(
                    output,
                    self.m2_scale(b),
                    -4096,
                    4095,
                )

            self.handles.append(
                block.mlp.fc2.register_forward_hook(m2_hook)
            )

            # HLS MLP output / feature-map storage -> signed int13.
            # Use the same real scale as the MLP2 accumulator. This mirrors
            # the HLS residual merge requirement; later RM/RS implements the
            # residual branch scale conversion into this domain.
            def block_hook(module, inputs, output, b=b):
                if not self.is_active(b):
                    return output
                return fake_quant_ste(
                    output,
                    self.m2_scale(b),
                    -4096,
                    4095,
                )

            self.handles.append(
                block.register_forward_hook(block_hook)
            )

    def remove(self):
        for h in self.handles:
            h.remove()
        self.handles = []

    def export_scales(self):
        out = {}

        with torch.no_grad():
            for b in range(12):
                block = self.backbone.vit.blocks[b]

                sw1 = float(module_weight_scale(block.mlp.fc1).cpu())
                sw2 = float(module_weight_scale(block.mlp.fc2).cpu())
                sln = float(self.ln2_scale(b).cpu())
                sge = float(self.gelu_scale(b).cpu())

                out[str(b)] = {
                    "ln2_signed3_scale": sln,
                    "w1_signed3_scale": sw1,
                    "m1_int11_scale": sln * sw1,
                    "gelu_uint3_scale": sge,
                    "w2_signed3_scale": sw2,
                    "m2_int13_scale": sge * sw2,
                    "fm_int13_scale": sge * sw2,
                }

        return out


# ---------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------

def make_train_transform():
    return transforms.Compose([
        transforms.RandomResizedCrop(
            224,
            scale=(0.8, 1.0),
        ),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225),
        ),
    ])


def make_loader(ds, batch_size, workers, shuffle, device):
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=workers,
        pin_memory=(device.type == "cuda"),
        persistent_workers=(workers > 0),
    )


# ---------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------

@torch.inference_mode()
def evaluate(model, loader, device):
    model.eval()

    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        logits = model(images)

        correct += int(
            (logits.argmax(1) == labels).sum().item()
        )
        total += int(labels.numel())

    return 100.0 * correct / total


# ---------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------

def active_blocks_for_epoch(epoch):
    """
    Progressive schedule:
      epoch 1 : blocks 6..11
      epoch 2 : blocks 3..11
      epoch 3+: blocks 0..11

    The sensitivity experiment showed that early blocks are much harder.
    Introducing the easy late blocks first generally gives a more stable
    start than enabling all MLP activation quantizers at once.
    """
    if epoch == 1:
        return list(range(6, 12))
    if epoch == 2:
        return list(range(3, 12))
    return list(range(12))


def distill_loss(student_logits, teacher_logits, labels, alpha, temperature):
    ce = F.cross_entropy(student_logits, labels)

    log_ps = F.log_softmax(
        student_logits / temperature,
        dim=1,
    )

    pt = F.softmax(
        teacher_logits / temperature,
        dim=1,
    )

    kd = F.kl_div(
        log_ps,
        pt,
        reduction="batchmean",
    ) * (temperature ** 2)

    return (1.0 - alpha) * ce + alpha * kd, ce.detach(), kd.detach()


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--source-checkpoint", required=True)
    ap.add_argument("--qat-checkpoint", required=True)
    ap.add_argument("--stage3-dir", required=True)
    ap.add_argument("--ranges", required=True)
    ap.add_argument("--data-root", required=True)

    ap.add_argument(
        "--output",
        default="stage4d_mlp_qat",
    )

    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--workers", type=int, default=4)

    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--scale-lr", type=float, default=5e-4)
    ap.add_argument("--weight-decay", type=float, default=0.02)

    ap.add_argument("--kd-alpha", type=float, default=0.5)
    ap.add_argument("--kd-temperature", type=float, default=2.0)

    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    # ------------------------------------------------------------
    # Build teacher and student from the same frozen Stage3 model.
    # ------------------------------------------------------------

    teacher, _, source_t = rebuild_stage3_model(
        args.source_checkpoint,
        args.qat_checkpoint,
        args.stage3_dir,
    )

    student, backbone, source_s = rebuild_stage3_model(
        args.source_checkpoint,
        args.qat_checkpoint,
        args.stage3_dir,
    )

    classes = list(source_s["classes"])

    if classes != list(source_t["classes"]):
        raise RuntimeError("Teacher/student class mismatch")

    teacher = teacher.to(device)
    student = student.to(device)

    teacher.eval()
    for p in teacher.parameters():
        p.requires_grad_(False)

    # ------------------------------------------------------------
    # Load activation ranges and install MLP quantizers.
    # ------------------------------------------------------------

    with open(args.ranges, "r", encoding="utf-8") as f:
        ranges = json.load(f)["statistics"]

    controller = MLPActivationController(
        backbone,
        ranges,
    ).to(device)

    controller.install()
    controller.set_active(range(12))

    # ------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------

    data_root = Path(args.data_root)

    train_ds = datasets.ImageFolder(
        data_root / "train",
        transform=make_train_transform(),
    )

    val_ds = datasets.ImageFolder(
        data_root / "val",
        transform=eval_transform(),
    )

    test_ds = datasets.ImageFolder(
        data_root / "test",
        transform=eval_transform(),
    )

    for name, ds in [
        ("train", train_ds),
        ("val", val_ds),
        ("test", test_ds),
    ]:
        if list(ds.classes) != classes:
            raise RuntimeError(
                f"{name} class ordering mismatch"
            )

    train_loader = make_loader(
        train_ds,
        args.batch_size,
        args.workers,
        True,
        device,
    )

    val_loader = make_loader(
        val_ds,
        args.batch_size,
        args.workers,
        False,
        device,
    )

    test_loader = make_loader(
        test_ds,
        args.batch_size,
        args.workers,
        False,
        device,
    )

    # ------------------------------------------------------------
    # Initial all-quantized accuracy
    # ------------------------------------------------------------

    controller.set_active(range(12))

    initial_val = evaluate(
        student,
        val_loader,
        device,
    )

    print()
    print("===== STAGE 4D: MLP ACTIVATION QAT =====")
    print(f"Initial all-MLP-quant val Top-1: {initial_val:.4f}%")
    print()

    # ------------------------------------------------------------
    # Optimizer
    # ------------------------------------------------------------

    activation_scale_params = {
        id(controller.log_ln2_scale),
        id(controller.log_gelu_scale),
    }

    model_params = [
        p for p in student.parameters()
        if p.requires_grad
    ]

    optimizer = torch.optim.AdamW(
        [
            {
                "params": model_params,
                "lr": args.lr,
                "weight_decay": args.weight_decay,
            },
            {
                "params": [
                    controller.log_ln2_scale,
                    controller.log_gelu_scale,
                ],
                "lr": args.scale_lr,
                "weight_decay": 0.0,
            },
        ]
    )

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=args.epochs,
    )

    scaler = torch.amp.GradScaler(
        "cuda",
        enabled=(device.type == "cuda"),
    )

    best_val = -1.0
    best_epoch = -1

    best_path = out / "best_mlp_qat.pth"

    # ------------------------------------------------------------
    # QAT
    # ------------------------------------------------------------

    for epoch in range(1, args.epochs + 1):

        active = active_blocks_for_epoch(epoch)
        controller.set_active(active)

        student.train()
        teacher.eval()

        loss_sum = 0.0
        ce_sum = 0.0
        kd_sum = 0.0

        correct = 0
        total = 0

        for step, (images, labels) in enumerate(
            train_loader,
            1,
        ):
            images = images.to(
                device,
                non_blocking=True,
            )
            labels = labels.to(
                device,
                non_blocking=True,
            )

            optimizer.zero_grad(set_to_none=True)

            with torch.no_grad():
                with torch.autocast(
                    device_type=device.type,
                    dtype=torch.float16,
                    enabled=(device.type == "cuda"),
                ):
                    teacher_logits = teacher(images)

            with torch.autocast(
                device_type=device.type,
                dtype=torch.float16,
                enabled=(device.type == "cuda"),
            ):
                student_logits = student(images)

                loss, ce, kd = distill_loss(
                    student_logits,
                    teacher_logits,
                    labels,
                    args.kd_alpha,
                    args.kd_temperature,
                )

            scaler.scale(loss).backward()

            scaler.unscale_(optimizer)

            torch.nn.utils.clip_grad_norm_(
                list(student.parameters())
                + list(controller.parameters()),
                1.0,
            )

            scaler.step(optimizer)
            scaler.update()

            loss_sum += float(loss.detach()) * labels.size(0)
            ce_sum += float(ce) * labels.size(0)
            kd_sum += float(kd) * labels.size(0)

            correct += int(
                (student_logits.argmax(1) == labels)
                .sum()
                .item()
            )

            total += labels.numel()

            if step % 100 == 0:
                print(
                    f"Epoch {epoch}/{args.epochs} "
                    f"step {step}/{len(train_loader)} "
                    f"loss={loss_sum/total:.5f} "
                    f"top1={100.0*correct/total:.3f}% "
                    f"active={active[0]}..{active[-1]}",
                    flush=True,
                )

        scheduler.step()

        # Validation must always use the final hardware condition:
        # all 12 MLP paths quantized.
        controller.set_active(range(12))

        val_top1 = evaluate(
            student,
            val_loader,
            device,
        )

        train_top1 = 100.0 * correct / total

        print(
            f"Epoch {epoch}: "
            f"loss={loss_sum/total:.6f} "
            f"train_top1={train_top1:.4f}% "
            f"val_top1={val_top1:.4f}%"
        )

        if val_top1 > best_val:
            best_val = val_top1
            best_epoch = epoch

            torch.save(
                {
                    "student_state": student.state_dict(),
                    "controller_state": controller.state_dict(),
                    "epoch": epoch,
                    "val_top1": val_top1,
                    "classes": classes,
                    "scope": (
                        "W3 backbone + Stage3 HLS Patch + "
                        "MLP LN2 signed3 / M1 int11 / GELU uint3 / "
                        "M2 int13 / FM int13 hardware-aware QAT"
                    ),
                },
                best_path,
            )

            print("Saved best:", best_path)

    # ------------------------------------------------------------
    # Reload best and final test
    # ------------------------------------------------------------

    best = torch.load(
        best_path,
        map_location=device,
        weights_only=True,
    )

    student.load_state_dict(
        best["student_state"],
        strict=True,
    )

    controller.load_state_dict(
        best["controller_state"],
        strict=True,
    )

    controller.set_active(range(12))

    final_test = evaluate(
        student,
        test_loader,
        device,
    )

    scales = controller.export_scales()

    with open(
        out / "activation_scales.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            scales,
            f,
            indent=2,
        )

    report = {
        "initial_all_mlp_quant_val_top1": initial_val,
        "best_epoch": best_epoch,
        "best_val_top1": best_val,
        "best_test_top1": final_test,
        "activation_scales": scales,
        "hardware_targets": {
            "ln2_output": "signed int3 [-4,3]",
            "m1_accumulator": "signed int11 [-1024,1023]",
            "gelu_output": "unsigned int3 [0,7]",
            "m2_accumulator": "signed int13 [-4096,4095]",
            "fm_output": "signed int13 [-4096,4095]",
        },
        "note": (
            "This is hardware-aware boundary QAT, not yet the final bit-accurate "
            "LayerNorm-rsqrt/GELU-address LUT emulator. The next stage converts "
            "these learned scales into exact HLS integer scalars/LUTs and checks "
            "overflow/wrap parity."
        ),
    }

    with open(
        out / "report.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            report,
            f,
            indent=2,
        )

    print()
    print("===== FINAL STAGE 4D =====")
    print(f"Initial all-MLP-quant val : {initial_val:.4f}%")
    print(f"Best MLP-QAT val          : {best_val:.4f}%")
    print(f"Best MLP-QAT test         : {final_test:.4f}%")
    print(f"Best epoch                : {best_epoch}")
    print("Checkpoint:", best_path)
    print("Scales:", out / "activation_scales.json")
    print("Report:", out / "report.json")

    controller.remove()


if __name__ == "__main__":
    main()
