import argparse
import json
import random
from pathlib import Path

import numpy as np
import timm
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


MEAN = (0.485, 0.456, 0.406)
STD  = (0.229, 0.224, 0.225)


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

    @torch.no_grad()
    def load_from_standard197(self, state):
        state = dict(state)

        old_pos = state.pop("pos_embed")

        if tuple(old_pos.shape) != (1, 197, 192):
            raise RuntimeError(
                f"Expected pos_embed (1,197,192), got {tuple(old_pos.shape)}"
            )

        result = self.vit.load_state_dict(state, strict=False)

        if set(result.missing_keys) != {"pos_embed"}:
            raise RuntimeError(
                f"Unexpected missing keys: {result.missing_keys}"
            )

        if result.unexpected_keys:
            raise RuntimeError(
                f"Unexpected keys: {result.unexpected_keys}"
            )

        # old:
        # pos[0]   = CLS
        # pos[1]   = patch0
        # pos[2]   = patch1
        # ...
        # pos[196] = patch195
        #
        # HLS196:
        # token0   = CLS
        # token1   = patch1
        # ...
        # token195 = patch195

        new_pos = torch.cat(
            [
                old_pos[:, 0:1, :],
                old_pos[:, 2:, :],
            ],
            dim=1,
        )

        assert new_pos.shape == (1, 196, 192)

        self.vit.pos_embed = nn.Parameter(new_pos.clone())

    def forward_features(self, x):
        # [B,3,224,224] -> [B,196,192]
        x = self.vit.patch_embed(x)

        if x.shape[1:] != (196, 192):
            raise RuntimeError(
                f"Unexpected patch shape: {tuple(x.shape)}"
            )

        # drop original patch0
        x = x[:, 1:, :]

        cls = self.vit.cls_token.expand(
            x.shape[0], -1, -1
        )

        # [CLS, patch1, ..., patch195]
        x = torch.cat([cls, x], dim=1)

        if x.shape[1] != 196:
            raise RuntimeError(
                f"Token count is {x.shape[1]}, expected 196"
            )

        if self.vit.pos_embed.shape != (1, 196, 192):
            raise RuntimeError(
                f"pos_embed shape is {self.vit.pos_embed.shape}"
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


def make_transforms():
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(
            224,
            scale=(0.8, 1.0),
        ),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])

    eval_tf = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])

    return train_tf, eval_tf


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
        total += labels.numel()

    return 100.0 * correct / total


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

    for step, (images, labels) in enumerate(loader, 1):
        images = images.to(
            device,
            non_blocking=True,
        )
        labels = labels.to(
            device,
            non_blocking=True,
        )

        optimizer.zero_grad(set_to_none=True)

        with torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
            enabled=(device.type == "cuda"),
        ):
            logits = model(images)
            loss = criterion(logits, labels)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        bs = labels.size(0)

        total += bs
        loss_sum += loss.item() * bs

        correct += int(
            (logits.argmax(1) == labels).sum().item()
        )

        if step % 100 == 0:
            print(
                f"step {step}/{len(loader)} "
                f"loss={loss_sum/total:.5f} "
                f"top1={100*correct/total:.3f}%",
                flush=True,
            )

    return (
        loss_sum / total,
        100.0 * correct / total,
    )


def main():
    p = argparse.ArgumentParser()

    p.add_argument(
        "--data-root",
        required=True,
    )

    p.add_argument(
        "--checkpoint",
        required=True,
    )

    p.add_argument(
        "--output",
        default="plantvillage_hls196",
    )

    p.add_argument(
        "--epochs",
        type=int,
        default=4,
    )

    p.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )

    p.add_argument(
        "--workers",
        type=int,
        default=4,
    )

    p.add_argument(
        "--lr",
        type=float,
        default=1e-5,
    )

    p.add_argument(
        "--seed",
        type=int,
        default=20260921,
    )

    args = p.parse_args()

    seed_all(args.seed)

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("Device:", device)

    train_tf, eval_tf = make_transforms()

    root = Path(args.data_root)

    train_ds = datasets.ImageFolder(
        root / "train",
        transform=train_tf,
    )

    val_ds = datasets.ImageFolder(
        root / "val",
        transform=eval_tf,
    )

    test_ds = datasets.ImageFolder(
        root / "test",
        transform=eval_tf,
    )

    if not (
        train_ds.classes
        == val_ds.classes
        == test_ds.classes
    ):
        raise RuntimeError(
            "Class ordering differs between splits"
        )

    print(
        f"Classes={len(train_ds.classes)} "
        f"Train={len(train_ds)} "
        f"Val={len(val_ds)} "
        f"Test={len(test_ds)}"
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=True,
    )

    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=True,
    )

    test_loader = DataLoader(
        test_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=True,
    )

    ckpt = torch.load(
        args.checkpoint,
        map_location="cpu",
        weights_only=True,
    )

    state = ckpt["model"]

    classes = ckpt.get("classes")

    if classes is not None:
        if list(classes) != train_ds.classes:
            raise RuntimeError(
                "Checkpoint class order does not "
                "match dataset"
            )

    num_classes = len(train_ds.classes)

    print(
        "Source pos_embed:",
        tuple(state["pos_embed"].shape),
    )

    # -----------------------------
    # Standard 197-token baseline
    # -----------------------------

    standard = timm.create_model(
        "deit_tiny_patch16_224",
        pretrained=False,
        num_classes=num_classes,
    )

    standard.load_state_dict(
        state,
        strict=True,
    )

    standard = standard.to(device)

    std_val = evaluate(
        standard,
        val_loader,
        device,
    )

    std_test = evaluate(
        standard,
        test_loader,
        device,
    )

    print(
        f"\nStandard197 "
        f"val={std_val:.4f}% "
        f"test={std_test:.4f}%"
    )

    del standard

    if device.type == "cuda":
        torch.cuda.empty_cache()

    # -----------------------------
    # Convert to HLS196
    # -----------------------------

    model = HLS196DeiT(num_classes)

    model.load_from_standard197(
        state
    )

    model = model.to(device)

    pre_val = evaluate(
        model,
        val_loader,
        device,
    )

    pre_test = evaluate(
        model,
        test_loader,
        device,
    )

    print(
        f"HLS196 before finetune "
        f"val={pre_val:.4f}% "
        f"test={pre_test:.4f}%"
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=0.05,
    )

    scheduler = (
        torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=args.epochs,
        )
    )

    scaler = torch.amp.GradScaler(
        "cuda",
        enabled=(device.type == "cuda"),
    )

    out_dir = Path(args.output)
    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    best_val = -1.0
    best_path = out_dir / "best.pth"

    history = []

    for epoch in range(
        1,
        args.epochs + 1,
    ):
        print(
            f"\nEpoch {epoch}/{args.epochs}"
        )

        train_loss, train_top1 = train_epoch(
            model,
            train_loader,
            optimizer,
            scaler,
            device,
        )

        val_top1 = evaluate(
            model,
            val_loader,
            device,
        )

        scheduler.step()

        print(
            f"Epoch {epoch}: "
            f"loss={train_loss:.6f} "
            f"train_top1={train_top1:.4f}% "
            f"val_top1={val_top1:.4f}%"
        )

        history.append({
            "epoch": epoch,
            "loss": train_loss,
            "train_top1": train_top1,
            "val_top1": val_top1,
        })

        if val_top1 > best_val:
            best_val = val_top1

            torch.save({
                "model":
                    model.vit.state_dict(),

                "classes":
                    train_ds.classes,

                "num_classes":
                    num_classes,

                "epoch":
                    epoch,

                "val_top1":
                    val_top1,

                "architecture":
                    "deit_tiny_hls196",

                "token_mode": {
                    "total_tokens": 196,
                    "cls_tokens": 1,
                    "patch_tokens": 195,
                    "dropped_patch": 0,
                    "mapping":
                        "[CLS,patch1,...,patch195]",
                },

                "source_checkpoint":
                    str(args.checkpoint),

            }, best_path)

            print(
                "Saved:",
                best_path,
            )

    # -----------------------------
    # Final test
    # -----------------------------

    best = torch.load(
        best_path,
        map_location="cpu",
        weights_only=True,
    )

    final_model = HLS196DeiT(
        num_classes
    )

    final_model.vit.pos_embed = nn.Parameter(
        torch.zeros(
            1,
            196,
            192,
        )
    )

    final_model.vit.load_state_dict(
        best["model"],
        strict=True,
    )

    final_model = final_model.to(device)

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

    report = {
        "standard197_val": std_val,
        "standard197_test": std_test,

        "hls196_before_val": pre_val,
        "hls196_before_test": pre_test,

        "hls196_final_val": final_val,
        "hls196_final_test": final_test,

        "history": history,
    }

    with open(
        out_dir / "report.json",
        "w",
    ) as f:
        json.dump(
            report,
            f,
            indent=2,
        )

    print("\n===== FINAL =====")

    print(
        f"Standard197 test : "
        f"{std_test:.4f}%"
    )

    print(
        f"HLS196 pre-test  : "
        f"{pre_test:.4f}%"
    )

    print(
        f"HLS196 final val : "
        f"{final_val:.4f}%"
    )

    print(
        f"HLS196 final test: "
        f"{final_test:.4f}%"
    )

    print(
        "Saved checkpoint:",
        best_path,
    )

    print(
        "Saved pos_embed:",
        tuple(
            best["model"]["pos_embed"].shape
        ),
    )


if __name__ == "__main__":
    main()
