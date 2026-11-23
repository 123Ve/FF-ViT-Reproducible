#!/usr/bin/env python3
"""Fine-tune a frozen-manifest 45-class standard (197-token) DeiT-Tiny."""
from __future__ import annotations
import argparse, json, platform, random, shutil, sys, uuid
from pathlib import Path
from typing import Any
import numpy as np
import timm, torch, torchvision
from torch import nn
from torch.utils.data import DataLoader
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT.parent / "Dataset"
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
from src.manifest_dataset import ManifestImageDataset, VerifiedSourceIndex, load_manifest_bundle, make_eval_transform, make_train_transform  # noqa: E402
from src.model_contract import DEFAULT_PRETRAINED, atomic_json_write, atomic_torch_save, build_standard_deit, checkpoint_metadata, class_order_hash, iter_limited, load_resume_state, public_checkpoint, save_resume_state, sha256_file  # noqa: E402

def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
def _rng(g: torch.Generator) -> dict[str, Any]:
    return {"python": random.getstate(), "numpy": np.random.get_state(), "torch": torch.get_rng_state(), "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None, "loader": g.get_state()}
def _restore(s: dict[str, Any], g: torch.Generator) -> None:
    random.setstate(s["python"]); np.random.set_state(s["numpy"]); torch.set_rng_state(s["torch"]); g.set_state(s["loader"])
    if torch.cuda.is_available() and s.get("cuda") is not None: torch.cuda.set_rng_state_all(s["cuda"])
def evaluate(model: nn.Module, loader: DataLoader[Any], device: torch.device, maximum: int | None) -> dict[str, float | int]:
    model.eval(); correct = total = 0
    with torch.inference_mode():
        for images, labels in iter_limited(loader, maximum):
            images, labels = images.to(device, non_blocking=True), labels.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"): logits = model(images)
            correct += int((logits.argmax(1) == labels).sum()); total += labels.numel()
    if not total: raise ValueError("evaluation processed no images")
    return {"top1": 100.0 * correct / total, "samples": total}
def _preflight(output: Path, report: Path | None, resume: Path | None) -> tuple[Path, Path]:
    output = output.resolve(); canonical = output / "report.json"
    if report is not None and report.resolve() != canonical: raise ValueError("--report must be <output>/report.json; external reports are unsupported")
    if output.exists() or output.is_symlink(): raise ValueError(f"refusing to reuse published output directory: {output}")
    run = resume.resolve() if resume else output.parent / f".{output.name}.run"
    if resume is None and run.exists(): raise ValueError(f"resumable run already exists; use --resume {run}")
    if resume is not None and not run.is_dir(): raise ValueError(f"resume directory does not exist: {run}")
    output.parent.mkdir(parents=True, exist_ok=True); return output, run
def _run_config(a: argparse.Namespace) -> dict[str, Any]:
    """All semantics that must remain immutable across a resumed run."""
    return {"batch_size": a.batch_size, "workers": a.workers, "seed": a.seed, "max_train_batches": a.max_train_batches, "max_eval_batches": a.max_eval_batches, "lr": 5e-5, "weight_decay": .05}
def _worker_seed(seed: int, epoch: int):
    def initialize(worker_id: int) -> None:
        value = seed + epoch * 1_000_003 + worker_id
        random.seed(value); np.random.seed(value); torch.manual_seed(value)
    return initialize
def _latest_epoch(run: Path, inputs: dict[str, str], config: dict[str, Any]) -> dict[str, Any] | None:
    """Epoch files are immutable commits; resume.pth is only a convenience pointer."""
    valid: list[dict[str, Any]] = []
    for path in sorted(run.glob("epoch-*.pth")):
        try: state = load_resume_state(path, inputs)
        except ValueError: continue
        if state.get("run_config") != config: raise ValueError("resume run configuration differs from requested configuration")
        valid.append(state)
    return max(valid, key=lambda item: int(item["next_epoch"])) if valid else None
def _best_epoch_state(run: Path, inputs: dict[str, str], config: dict[str, Any]) -> dict[str, Any]:
    states = []
    for path in sorted(run.glob("epoch-*.pth")):
        state = load_resume_state(path, inputs)
        if state.get("run_config") != config: raise ValueError("epoch checkpoint run configuration differs")
        states.append(state)
    if not states: raise ValueError("run contains no complete epoch checkpoints")
    return max(states, key=lambda item: (float(item["val_top1"]), -int(item["epoch"])))
def _publish(output: Path, checkpoint: dict[str, Any], report: dict[str, Any]) -> None:
    stage = output.parent / f".{output.name}.publish-{uuid.uuid4().hex}"; stage.mkdir()
    try:
        atomic_torch_save(checkpoint, stage / "best.pth")
        final_report = {**report, "output": str(output / "best.pth"), "output_sha256": sha256_file(stage / "best.pth")}
        atomic_json_write(final_report, stage / "report.json")
        if {p.name for p in stage.iterdir()} != {"best.pth", "report.json"}: raise RuntimeError("final stage is incomplete")
        stage.replace(output)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True); raise
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", type=Path, default=PROJECT_ROOT / "metadata"); p.add_argument("--source", type=Path, default=DEFAULT_SOURCE); p.add_argument("--pretrained-checkpoint", type=Path, default=DEFAULT_PRETRAINED)
    p.add_argument("--output", type=Path, default=PROJECT_ROOT / "checkpoints" / "fp32"); p.add_argument("--report", type=Path); p.add_argument("--resume", type=Path)
    p.add_argument("--epochs", type=int, default=8); p.add_argument("--batch-size", type=int, default=32); p.add_argument("--workers", type=int, default=4); p.add_argument("--seed", type=int, default=20260923)
    p.add_argument("--max-train-batches", type=int); p.add_argument("--max-eval-batches", type=int); p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    a = p.parse_args()
    if a.epochs <= 0 or a.batch_size <= 0 or a.workers < 0: raise ValueError("epochs and batch-size must be positive; workers nonnegative")
    output, run = _preflight(a.output, a.report, a.resume); seed_all(a.seed)
    device = torch.device("cuda" if a.device == "auto" and torch.cuda.is_available() else a.device if a.device != "auto" else "cpu")
    if device.type == "cuda" and not torch.cuda.is_available(): raise ValueError("--device cuda requested but CUDA is unavailable")
    bundle = load_manifest_bundle(a.metadata); inputs = {**bundle.metadata_hashes, "pretrained_checkpoint": sha256_file(a.pretrained_checkpoint)}
    index = VerifiedSourceIndex(a.source); gen = torch.Generator().manual_seed(a.seed); opts = {"num_workers": a.workers, "pin_memory": device.type == "cuda", "persistent_workers": False}
    val = DataLoader(ManifestImageDataset(a.source, bundle.records_for("val"), make_eval_transform(), index), batch_size=a.batch_size, shuffle=False, **opts)
    model, pretrained = build_standard_deit(a.pretrained_checkpoint, bundle.classes); model = model.to(device); opt = torch.optim.AdamW(model.parameters(), lr=5e-5, weight_decay=.05); scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda"); criterion = nn.CrossEntropyLoss()
    config = _run_config(a)
    start, best, best_epoch, history = 1, -1.0, 0, []
    run.mkdir(parents=True, exist_ok=a.resume is not None)
    if not a.resume:
        save_resume_state(run / "initial.pth", {"input_hashes": inputs, "run_config": config, "next_epoch": 1})
    if a.resume:
        state = _latest_epoch(run, inputs, config)
        if state is None:
            initial = load_resume_state(run / "initial.pth", inputs)
            if initial.get("run_config") != config: raise ValueError("resume run configuration differs from requested configuration")
        else:
            if a.epochs < state["next_epoch"] - 1: raise ValueError("requested epoch budget is below committed work")
            model.load_state_dict(state["model"]); opt.load_state_dict(state["optimizer"]); scaler.load_state_dict(state["scaler"]); _restore(state["rng"], gen); start, best, best_epoch, history = state["next_epoch"], state["best_val_top1"], state["best_epoch"], state["history"]
    for epoch in range(start, a.epochs + 1):
        for name, param in model.named_parameters(): param.requires_grad = epoch >= 2 or name.startswith("head.")
        epoch_gen = torch.Generator().manual_seed(a.seed + epoch * 1_000_003)
        train = DataLoader(ManifestImageDataset(a.source, bundle.records_for("train"), make_train_transform(), index), batch_size=a.batch_size, shuffle=True, generator=epoch_gen, worker_init_fn=_worker_seed(a.seed, epoch), **opts)
        model.train(); loss_sum = 0.; samples = 0
        for images, labels in iter_limited(train, a.max_train_batches):
            images, labels = images.to(device, non_blocking=True), labels.to(device, non_blocking=True); opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"): loss = criterion(model(images), labels)
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); samples += labels.numel(); loss_sum += loss.item() * labels.numel()
        if not samples: raise ValueError("training processed no images")
        metric = evaluate(model, val, device, a.max_eval_batches); entry = {"epoch": epoch, "train_loss": loss_sum / samples, "train_samples": samples, **metric}; history.append(entry)
        candidate = checkpoint_metadata(classes=bundle.classes, architecture="deit_tiny_patch16_224", token_count=197, model_state=model.state_dict(), epoch=epoch, val_top1=metric["top1"], pretrained=pretrained, manifest_hashes=dict(bundle.metadata_hashes), input_hashes=inputs, seed=a.seed)
        if metric["top1"] > best: best, best_epoch = float(metric["top1"]), epoch
        state = {**candidate, "optimizer": opt.state_dict(), "scaler": scaler.state_dict(), "rng": _rng(gen), "next_epoch": epoch + 1, "best_val_top1": best, "best_epoch": best_epoch, "history": history, "input_hashes": inputs, "run_config": config, "requested_epochs": a.epochs}
        atomic_torch_save(state, run / f"epoch-{epoch:03d}.pth")
        with (run / "progress.jsonl").open("a", encoding="utf-8") as progress:
            progress.write(json.dumps({"epoch": epoch, "event": "epoch_committed", **entry}, sort_keys=True) + "\n")
            progress.flush()
            import os; os.fsync(progress.fileno())
        if best_epoch == epoch: save_resume_state(run / "best.pth", state)
        save_resume_state(run / "resume.pth", state)
    chosen = _best_epoch_state(run, inputs, config)
    report = {"stage": "fp32", "command": sys.argv, "environment": {"python": platform.python_version(), "torch": torch.__version__, "torchvision": torchvision.__version__, "timm": timm.__version__, "cuda": torch.version.cuda, "device": str(device)}, "seed": a.seed, "classes": list(bundle.classes), "class_order_sha256": class_order_hash(bundle.classes), "manifest_hashes": dict(bundle.metadata_hashes), "input_hashes": inputs, "pretrained": pretrained, "hyperparameters": {"epochs": a.epochs, "batch_size": a.batch_size, "workers": a.workers, "lr": 5e-5, "weight_decay": .05, "max_train_batches": a.max_train_batches, "max_eval_batches": a.max_eval_batches}, "history": history, "best_epoch": best_epoch, "best_val_top1": best, "resume_run": str(run), "verified_source_hash_checks": index.hash_checks}
    _publish(output, public_checkpoint(chosen), report); print(json.dumps({**report, "output": str(output / "best.pth")}, sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
