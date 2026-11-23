import argparse
import random
from pathlib import Path

import timm
import torch
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", required=True)
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--output", default="plantvillage_deit_tiny")
    args = p.parse_args()

    torch.manual_seed(42)
    random.seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.75, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(
            [0.485, 0.456, 0.406],
            [0.229, 0.224, 0.225],
        ),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(
            [0.485, 0.456, 0.406],
            [0.229, 0.224, 0.225],
        ),
    ])

    train_ds = datasets.ImageFolder(args.data_root, transform=train_tf)
    eval_ds = datasets.ImageFolder(args.data_root, transform=eval_tf)

    if len(train_ds.classes) != 38:
        raise ValueError(
            f"期望 38 类，实际找到 {len(train_ds.classes)} 类；"
            "请检查 --data-root 是否指向彩色图像类别目录"
        )

    rng = random.Random(42)
    train_ids, val_ids, test_ids = [], [], []
    for class_id in range(len(train_ds.classes)):
        ids = [
            i for i, (_, target) in enumerate(train_ds.samples)
            if target == class_id
        ]
        rng.shuffle(ids)
        n_test = max(1, round(len(ids) * 0.1))
        n_val = max(1, round(len(ids) * 0.1))
        test_ids.extend(ids[:n_test])
        val_ids.extend(ids[n_test:n_test + n_val])
        train_ids.extend(ids[n_test + n_val:])

    def loader(dataset, ids, shuffle):
        return DataLoader(
            Subset(dataset, ids),
            batch_size=args.batch_size,
            shuffle=shuffle,
            num_workers=args.workers,
            pin_memory=device.type == "cuda",
            persistent_workers=args.workers > 0,
        )

    train_loader = loader(train_ds, train_ids, True)
    val_loader = loader(eval_ds, val_ids, False)
    test_loader = loader(eval_ds, test_ids, False)

    print(
        f"Classes={len(train_ds.classes)} "
        f"Train={len(train_ids)} Val={len(val_ids)} "
        f"Test={len(test_ids)} Device={device}",
        flush=True,
    )

    model = timm.create_model(
        "deit_tiny_patch16_224",
        pretrained=True,
        num_classes=38,
    ).to(device)

    if device.type == "cuda":
        model = model.to(memory_format=torch.channels_last)

    # 第一轮只训练新分类头，之后微调整个网络。
    for name, param in model.named_parameters():
        param.requires_grad = name.startswith("head.")

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=5e-5, weight_decay=0.05
    )
    criterion = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler(
        "cuda", enabled=device.type == "cuda"
    )
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    @torch.no_grad()
    def evaluate(data_loader):
        model.eval()
        correct = total = 0
        for images, labels in data_loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            with torch.autocast(
                device_type=device.type,
                enabled=device.type == "cuda",
            ):
                logits = model(images)
            correct += (logits.argmax(1) == labels).sum().item()
            total += labels.numel()
        return 100.0 * correct / total

    best = -1.0
    for epoch in range(args.epochs):
        if epoch == 1:
            for param in model.parameters():
                param.requires_grad = True
            print("Backbone unfrozen", flush=True)

        model.train()
        total_loss = 0.0

        for step, (images, labels) in enumerate(train_loader, 1):
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)

            with torch.autocast(
                device_type=device.type,
                enabled=device.type == "cuda",
            ):
                logits = model(images)
                loss = criterion(logits, labels)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            total_loss += loss.item()

            if step % 100 == 0:
                print(
                    f"Epoch {epoch+1}/{args.epochs} "
                    f"Step {step}/{len(train_loader)} "
                    f"Loss {loss.item():.4f}",
                    flush=True,
                )

        val_acc = evaluate(val_loader)
        print(
            f"Epoch {epoch+1}/{args.epochs}: "
            f"loss={total_loss/len(train_loader):.4f}, "
            f"val_top1={val_acc:.2f}%",
            flush=True,
        )

        if val_acc > best:
            best = val_acc
            torch.save(
                {
                    "model": model.state_dict(),
                    "classes": train_ds.classes,
                    "num_classes": 38,
                    "epoch": epoch + 1,
                    "val_top1": val_acc,
                    "architecture": "deit_tiny_patch16_224",
                },
                out / "best.pth",
            )

    checkpoint = torch.load(
        out / "best.pth", map_location=device, weights_only=False
    )
    model.load_state_dict(checkpoint["model"])
    test_acc = evaluate(test_loader)
    print(
        f"Best validation Top-1: {best:.2f}% | "
        f"Test Top-1: {test_acc:.2f}%",
        flush=True,
    )
    print(f"Checkpoint: {out / 'best.pth'}", flush=True)


if __name__ == "__main__":
    main()
