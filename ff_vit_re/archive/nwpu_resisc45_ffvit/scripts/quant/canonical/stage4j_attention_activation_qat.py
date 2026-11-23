#!/usr/bin/env python3
"""
Stage 4J: hardware-aware Attention activation QAT for FF-ViT.

Starting point:
  * Stage-4D MLP activation-QAT checkpoint
  * Stage-4D MLP boundary quantizers remain active (differentiable)
  * MLP weights/norm2 are frozen so the exact MLP parameterization from
    Stages 4F/4H/4I is not invalidated

Attention boundary model:
  LN1 output                -> signed int3 [-4, 3]
  Q / K / V requant output -> signed int3 [-4, 3], independent scales
  A = Softmax(QK^T)V       -> signed int3 [-4, 3] before O projection
  O projection accumulator -> signed int13 [-4096,4095]
  Attention residual output / MLP input
                            -> signed int15 [-16384,16383]
                               at the fixed per-block scale generated
                               by Stage 4H

Softmax remains floating-point in this QAT stage. Exact Q/K/V/A LUTs,
integer LayerNorm1, fixed-point Softmax and Attention residual RM/RS are
generated in later stages from the trained checkpoint.
"""

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from stage4b_activation_ptq_eval import rebuild_stage3_model
from stage4d_mlp_activation_qat import (
    MLPActivationController,
    fake_quant_ste,
    module_weight_scale,
)
from qat_weight3_hls196 import eval_transform


def train_transform():
    from src.manifest_dataset import make_train_transform
    return make_train_transform()


def make_loader(ds, batch_size, workers, shuffle, device):
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=workers,
        pin_memory=(device.type == "cuda"),
        persistent_workers=(workers > 0),
    )


def active_blocks_for_epoch(epoch):
    if epoch == 1:
        return list(range(6, 12))
    if epoch == 2:
        return list(range(3, 12))
    return list(range(12))


class AttentionActivationController(nn.Module):
    def __init__(self, backbone, ranges, ln_input_scales):
        super().__init__()
        self.backbone = backbone

        self.log_ln1_scale = nn.Parameter(torch.log(torch.tensor([
            max(float(ranges[f"b{b}.ln1_out"]["abs_p999"]) / 3.0, 1e-4)
            for b in range(12)
        ], dtype=torch.float32)))

        self.log_q_scale = nn.Parameter(torch.log(torch.tensor([
            max(float(ranges[f"b{b}.q_prequant"]["abs_p999"]) / 3.0, 1e-4)
            for b in range(12)
        ], dtype=torch.float32)))

        self.log_k_scale = nn.Parameter(torch.log(torch.tensor([
            max(float(ranges[f"b{b}.k_prequant"]["abs_p999"]) / 3.0, 1e-4)
            for b in range(12)
        ], dtype=torch.float32)))

        self.log_v_scale = nn.Parameter(torch.log(torch.tensor([
            max(float(ranges[f"b{b}.v_prequant"]["abs_p999"]) / 3.0, 1e-4)
            for b in range(12)
        ], dtype=torch.float32)))

        self.log_a_scale = nn.Parameter(torch.log(torch.tensor([
            max(float(ranges[f"b{b}.attn_A_pre_proj"]["abs_p999"]) / 3.0, 1e-4)
            for b in range(12)
        ], dtype=torch.float32)))

        self.register_buffer(
            "attn_out_scale",
            torch.tensor(
                ln_input_scales,
                dtype=torch.float32,
            ),
        )

        self.active_blocks = set(range(12))
        self.handles = []

    def ln1_scale(self, b):
        return torch.exp(self.log_ln1_scale[b])

    def q_scale(self, b):
        return torch.exp(self.log_q_scale[b])

    def k_scale(self, b):
        return torch.exp(self.log_k_scale[b])

    def v_scale(self, b):
        return torch.exp(self.log_v_scale[b])

    def a_scale(self, b):
        return torch.exp(self.log_a_scale[b])

    def o_acc_scale(self, b):
        block = self.backbone.vit.blocks[b]
        return self.a_scale(b) * module_weight_scale(block.attn.proj)

    def set_active(self, blocks):
        self.active_blocks = set(int(x) for x in blocks)

    def is_active(self, b):
        return b in self.active_blocks

    def install(self):
        if self.handles:
            raise RuntimeError("Attention hooks already installed")

        for b in range(12):
            block = self.backbone.vit.blocks[b]

            # LN1 -> signed int3
            def ln1_hook(module, inputs, output, b=b):
                if not self.is_active(b):
                    return output
                return fake_quant_ste(
                    output,
                    self.ln1_scale(b),
                    -4,
                    3,
                )

            self.handles.append(
                block.norm1.register_forward_hook(ln1_hook)
            )

            # qkv output: split Q/K/V and quantize independently.
            def qkv_hook(module, inputs, output, b=b):
                if not self.is_active(b):
                    return output

                q, k, v = torch.chunk(
                    output,
                    3,
                    dim=-1,
                )

                q = fake_quant_ste(
                    q,
                    self.q_scale(b),
                    -4,
                    3,
                )
                k = fake_quant_ste(
                    k,
                    self.k_scale(b),
                    -4,
                    3,
                )
                v = fake_quant_ste(
                    v,
                    self.v_scale(b),
                    -4,
                    3,
                )

                return torch.cat(
                    [q, k, v],
                    dim=-1,
                )

            self.handles.append(
                block.attn.qkv.register_forward_hook(qkv_hook)
            )

            # A = softmax(QK^T)V -> signed int3 before O projection.
            def proj_pre_hook(module, inputs, b=b):
                if not self.is_active(b):
                    return None

                x = fake_quant_ste(
                    inputs[0],
                    self.a_scale(b),
                    -4,
                    3,
                )

                return (x,)

            self.handles.append(
                block.attn.proj.register_forward_pre_hook(
                    proj_pre_hook
                )
            )

            # O projection accumulator/output -> signed int13.
            def proj_post_hook(module, inputs, output, b=b):
                if not self.is_active(b):
                    return output

                return fake_quant_ste(
                    output,
                    self.o_acc_scale(b),
                    -4096,
                    4095,
                )

            self.handles.append(
                block.attn.proj.register_forward_hook(
                    proj_post_hook
                )
            )

            # Attention residual output is exactly the input to norm2.
            # Use Stage-4H's fixed int15 real scale so later integer
            # LayerNorm2 and residual generation share the same domain.
            def norm2_pre_hook(module, inputs, b=b):
                if not self.is_active(b):
                    return None

                x = fake_quant_ste(
                    inputs[0],
                    self.attn_out_scale[b],
                    -16384,
                    16383,
                )

                return (x,)

            self.handles.append(
                block.norm2.register_forward_pre_hook(
                    norm2_pre_hook
                )
            )

    def remove(self):
        for h in self.handles:
            h.remove()
        self.handles = []

    def export_scales(self):
        out = {}

        with torch.no_grad():
            for b in range(12):
                out[str(b)] = {
                    "ln1_signed3_scale": float(
                        self.ln1_scale(b).cpu()
                    ),
                    "q_signed3_scale": float(
                        self.q_scale(b).cpu()
                    ),
                    "k_signed3_scale": float(
                        self.k_scale(b).cpu()
                    ),
                    "v_signed3_scale": float(
                        self.v_scale(b).cpu()
                    ),
                    "a_signed3_scale": float(
                        self.a_scale(b).cpu()
                    ),
                    "o_int13_scale": float(
                        self.o_acc_scale(b).cpu()
                    ),
                    "attn_out_int15_scale": float(
                        self.attn_out_scale[b].cpu()
                    ),
                }

        return out


@torch.inference_mode()
def evaluate(model, loader, device):
    model.eval()

    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(
            device,
            non_blocking=True,
        )
        labels = labels.to(
            device,
            non_blocking=True,
        )

        logits = model(images)

        correct += int(
            (logits.argmax(1) == labels)
            .sum()
            .item()
        )
        total += labels.numel()

    return 100.0 * correct / total


def distill_loss(student_logits, teacher_logits, labels, alpha, temperature):
    ce = F.cross_entropy(
        student_logits,
        labels,
    )

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

    return (
        (1.0 - alpha) * ce + alpha * kd,
        ce.detach(),
        kd.detach(),
    )


def set_attention_trainable(student):
    """
    Preserve the already-closed MLP/patch path.

    Train:
      * norm1
      * attention qkv/proj
      * final norm/head where present

    Freeze:
      * norm2
      * MLP
      * patch/pos/cls front-end
    """
    for p in student.parameters():
        p.requires_grad_(False)

    trainable = []

    for name, p in student.named_parameters():
        enable = False

        if ".norm1." in name:
            enable = True
        elif ".attn." in name:
            enable = True
        elif name.endswith("vit.norm.weight"):
            enable = True
        elif name.endswith("vit.norm.bias"):
            enable = True
        elif ".head." in name or name.endswith("head.weight") or name.endswith("head.bias"):
            enable = True

        if enable:
            p.requires_grad_(True)
            trainable.append((name, p))

    if not trainable:
        raise RuntimeError(
            "No attention parameters were enabled. "
            "Inspect parameter names from rebuild_stage3_model()."
        )

    print("Trainable attention-side tensors:", len(trainable))

    return [p for _, p in trainable]


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--source-checkpoint", required=True)
    ap.add_argument("--qat-checkpoint", required=True)
    ap.add_argument("--stage3-dir", required=True)
    ap.add_argument("--ranges", required=True)
    ap.add_argument("--mlp-qat-checkpoint", required=True)
    ap.add_argument("--ln-dir", required=True)
    ap.add_argument("--data-root", required=True)

    ap.add_argument(
        "--output",
        default="stage4j_attention_qat",
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

    with open(args.ranges, "r", encoding="utf-8") as f:
        ranges = json.load(f)["statistics"]

    ln_input_scales = np.load(
        Path(args.ln_dir) / "ln_input_scales.npy"
    )

    # ------------------------------------------------------------
    # Teacher
    # ------------------------------------------------------------
    teacher, teacher_backbone, source_t = rebuild_stage3_model(
        args.source_checkpoint,
        args.qat_checkpoint,
        args.stage3_dir,
    )

    teacher_mlp = MLPActivationController(
        teacher_backbone,
        ranges,
    )

    # ------------------------------------------------------------
    # Student
    # ------------------------------------------------------------
    student, backbone, source_s = rebuild_stage3_model(
        args.source_checkpoint,
        args.qat_checkpoint,
        args.stage3_dir,
    )

    student_mlp = MLPActivationController(
        backbone,
        ranges,
    )

    mlp_ckpt = torch.load(
        args.mlp_qat_checkpoint,
        map_location="cpu",
        weights_only=True,
    )

    teacher.load_state_dict(
        mlp_ckpt["student_state"],
        strict=True,
    )
    student.load_state_dict(
        mlp_ckpt["student_state"],
        strict=True,
    )

    teacher_mlp.load_state_dict(
        mlp_ckpt["controller_state"],
        strict=True,
    )
    student_mlp.load_state_dict(
        mlp_ckpt["controller_state"],
        strict=True,
    )

    teacher = teacher.to(device)
    student = student.to(device)
    teacher_mlp = teacher_mlp.to(device)
    student_mlp = student_mlp.to(device)

    teacher_mlp.set_active(range(12))
    student_mlp.set_active(range(12))
    teacher_mlp.install()
    student_mlp.install()

    teacher.eval()
    for p in teacher.parameters():
        p.requires_grad_(False)
    for p in teacher_mlp.parameters():
        p.requires_grad_(False)

    attn_ctrl = AttentionActivationController(
        backbone,
        ranges,
        ln_input_scales,
    ).to(device)

    attn_ctrl.install()
    attn_ctrl.set_active(range(12))

    classes = list(source_s["classes"])

    if classes != list(source_t["classes"]):
        raise RuntimeError("Teacher/student class mismatch")

    # ------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------
    root = Path(args.data_root)

    train_ds = __import__('manifest_adapter').image_folder(
        root / "train",
        transform=train_transform(),
    )
    val_ds = __import__('manifest_adapter').image_folder(
        root / "val",
        transform=eval_transform(),
    )
    test_ds = __import__('manifest_adapter').image_folder(
        root / "test",
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
    # Initial all-attention-boundary accuracy.
    # ------------------------------------------------------------
    initial_val = evaluate(
        student,
        val_loader,
        device,
    )

    print()
    print("===== STAGE 4J: ATTENTION ACTIVATION QAT =====")
    print(
        f"Initial all-attention-quant val Top-1: "
        f"{initial_val:.4f}%"
    )
    print()

    model_params = set_attention_trainable(student)

    scale_params = [
        attn_ctrl.log_ln1_scale,
        attn_ctrl.log_q_scale,
        attn_ctrl.log_k_scale,
        attn_ctrl.log_v_scale,
        attn_ctrl.log_a_scale,
    ]

    optimizer = torch.optim.AdamW(
        [
            {
                "params": model_params,
                "lr": args.lr,
                "weight_decay": args.weight_decay,
            },
            {
                "params": scale_params,
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
    best_path = out / "best_attention_qat.pth"

    # ------------------------------------------------------------
    # QAT
    # ------------------------------------------------------------
    for epoch in range(1, args.epochs + 1):
        active = active_blocks_for_epoch(epoch)
        attn_ctrl.set_active(active)

        student.train()
        teacher.eval()

        loss_sum = 0.0
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

                loss, _, _ = distill_loss(
                    student_logits,
                    teacher_logits,
                    labels,
                    args.kd_alpha,
                    args.kd_temperature,
                )

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)

            torch.nn.utils.clip_grad_norm_(
                model_params + scale_params,
                1.0,
            )

            scaler.step(optimizer)
            scaler.update()

            loss_sum += float(
                loss.detach()
            ) * labels.size(0)

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

        # Validation always uses the final all-12-block hardware condition.
        attn_ctrl.set_active(range(12))

        val_top1 = evaluate(
            student,
            val_loader,
            device,
        )

        train_top1 = (
            100.0 * correct / total
        )

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
                    "attention_controller_state": attn_ctrl.state_dict(),
                    "mlp_controller_state": student_mlp.state_dict(),
                    "epoch": epoch,
                    "val_top1": val_top1,
                    "classes": classes,
                    "scope": (
                        "Stage4D MLP surrogate frozen + "
                        "Attention LN1/QKV/A int3, O int13, "
                        "Attention-output int15 hardware-aware QAT"
                    ),
                },
                best_path,
            )

            print(
                "Saved best:",
                best_path,
            )

    # ------------------------------------------------------------
    # Best test
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

    attn_ctrl.load_state_dict(
        best["attention_controller_state"],
        strict=True,
    )

    attn_ctrl.set_active(range(12))

    test_top1 = None  # test reserved for frozen milestones

    scales = attn_ctrl.export_scales()

    with open(
        out / "attention_scales.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            scales,
            f,
            indent=2,
        )

    report = {
        "initial_all_attention_quant_val_top1": initial_val,
        "best_epoch": best_epoch,
        "best_val_top1": best_val,
        "best_test_top1": test_top1,
        "attention_scales": scales,
        "note": (
            "Attention-aware QAT uses exact HLS boundary widths, but "
            "Softmax and requant LUT arithmetic remain surrogate. "
            "MLP parameters are frozen to preserve Stage4I closure."
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
    print("===== FINAL STAGE 4J =====")
    print(f"Initial attention-quant val : {initial_val:.4f}%")
    print(f"Best Attention-QAT val      : {best_val:.4f}%")
    print(f"Best Attention-QAT test     : {test_top1}%")
    print(f"Best epoch                  : {best_epoch}")
    print("Checkpoint:", best_path)
    print("Scales:", out / "attention_scales.json")
    print("Report:", out / "report.json")

    attn_ctrl.remove()
    student_mlp.remove()
    teacher_mlp.remove()


if __name__ == "__main__":
    main()
