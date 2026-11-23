"""Resumable, provenance-bound sensitivity experiments for the W3 HLS196 parent."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import torch

from .provenance import atomic_write_json
from .quant import BOUNDARIES, StrictS3Controller


INDIVIDUAL = (
    "ln1", "q", "k", "v", "a", "softmax", "ln2", "gelu",
    "fc1_weight", "fc2_weight", "attention_residual", "mlp_residual",
)
ATTENTION = ("ln1", "q", "k", "v", "a", "softmax", "o", "attention_residual")
MLP = ("ln2", "fc1", "gelu", "fc2", "mlp_residual")
GROUPS = {
    "qkv": ("q", "k", "v"),
    "attention-all": ("ln1", "q", "k", "v", "a"),
    "mlp-all": ("ln2", "gelu"),
    "all-a3": ("ln1", "q", "k", "v", "a", "ln2", "gelu", "mlp_residual"),
}
IDENTITY_FIELDS = ("config_sha256", "checkpoint_sha256", "data_sha256", "scales_sha256")


@dataclass(frozen=True)
class Experiment:
    id: str
    family: str
    masks: dict[str, tuple[int, ...]]
    block: int | None = None
    perturbation: str | None = None
    order: str | None = None
    step: int | None = None


def experiment_sha256(experiment: Experiment) -> str:
    """Bind a shard to its exact operator and block masks, not just its name."""

    payload = {"id": experiment.id, "family": experiment.family,
               "masks": experiment.masks, "block": experiment.block,
               "perturbation": experiment.perturbation, "order": experiment.order,
               "step": experiment.step}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enumerate_experiments(
    block_count: int = 12, *, low_sensitivity_order: Iterable[int]
) -> tuple[Experiment, ...]:
    """Enumerate the fixed comparisons and two complete cumulative schedules."""

    if type(block_count) is not int or block_count <= 0:
        raise ValueError("block_count must be positive")
    low_order = tuple(low_sensitivity_order)
    if len(low_order) != block_count or set(low_order) != set(range(block_count)) or any(type(x) is not int for x in low_order):
        raise ValueError("low_sensitivity_order must be a permutation of block indices")
    all_blocks = tuple(range(block_count))
    cases = [Experiment("baseline", "operator", {})]
    cases += [Experiment(f"operator-{name}", "operator", {name: all_blocks}) for name in INDIVIDUAL]
    cases += [Experiment(f"group-{name}", "operator", {operator: all_blocks for operator in operators})
              for name, operators in GROUPS.items()]
    for index in all_blocks:
        for perturbation, operators in (("attention", ATTENTION), ("mlp", MLP), ("whole-block", ATTENTION + MLP)):
            cases.append(Experiment(
                f"layer-{index:02d}-{perturbation}", "layer",
                {operator: (index,) for operator in operators}, index, perturbation,
            ))
    for order_name, order in (("low", low_order), ("rear", tuple(reversed(all_blocks)))):
        for step in range(1, block_count + 1):
            active = order[:step]
            cases.append(Experiment(
                f"cumulative-{order_name}-{step:02d}", "cumulative",
                {operator: active for operator in ATTENTION + MLP},
                order=order_name, step=step,
            ))
    return tuple(cases)


def _validate_identity(expected: Mapping[str, Any]) -> None:
    for name in IDENTITY_FIELDS:
        value = expected.get(name)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    count = expected.get("sample_count")
    if type(count) is not int or count <= 0:
        raise ValueError("sample_count must be a positive integer")


def _required_metric_keys(experiment: Experiment) -> set[str]:
    return {f"{index}:{name}" for name, indices in experiment.masks.items() for index in indices}


def _validate_metrics(metrics: Any, experiment: Experiment) -> None:
    if not isinstance(metrics, dict) or set(metrics) != _required_metric_keys(experiment):
        raise ValueError("incomplete or unexpected shard tensor_metrics")
    for key, row in metrics.items():
        if not isinstance(row, dict) or type(row.get("elements")) is not int or row["elements"] <= 0:
            raise ValueError(f"invalid tensor_metrics elements for {key}")
        for name in ("mse", "mae", "cosine", "clip_rate", "zero_rate", "observed_min", "observed_max"):
            value = row.get(name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"invalid tensor_metrics {name} for {key}")
        if row["mse"] < 0 or row["mae"] < 0 or not -1 <= row["cosine"] <= 1:
            raise ValueError(f"invalid tensor_metrics error/cosine for {key}")
        if not 0 <= row["clip_rate"] <= 1 or not 0 <= row["zero_rate"] <= 1:
            raise ValueError(f"invalid tensor_metrics rate for {key}")
        if row["observed_min"] > row["observed_max"]:
            raise ValueError(f"invalid tensor_metrics observed range for {key}")
        sqnr = row.get("sqnr_db")
        if sqnr is not None and (type(sqnr) not in (int, float) or not math.isfinite(sqnr)):
            raise ValueError(f"invalid tensor_metrics sqnr_db for {key}")


def _accumulate_pair(
    totals: dict[str, dict[str, float]], key: str,
    before: torch.Tensor, after: torch.Tensor, *, scale: torch.Tensor,
    qmin: int, qmax: int,
) -> None:
    x = before.detach().to(torch.float64).reshape(-1)
    y = after.detach().to(torch.float64).reshape(-1)
    step = torch.as_tensor(scale, dtype=torch.float64, device=x.device).reshape(-1)
    if x.shape != y.shape or not x.numel() or step.numel() not in (1, x.numel()):
        raise ValueError(f"invalid tensor metric pair for {key}")
    if not bool(torch.isfinite(x).all() and torch.isfinite(y).all() and torch.isfinite(step).all()) or not bool((step > 0).all()):
        raise ValueError(f"nonfinite tensor metric pair or scale for {key}")
    error = x - y
    item = totals.setdefault(key, {name: 0.0 for name in (
        "elements", "error_sq", "error_abs", "before_sq", "after_sq", "dot",
        "clip_count", "zero_count",
    )} | {"observed_min": math.inf, "observed_max": -math.inf})
    item["elements"] += x.numel()
    item["error_sq"] += float(error.square().sum())
    item["error_abs"] += float(error.abs().sum())
    item["before_sq"] += float(x.square().sum())
    item["after_sq"] += float(y.square().sum())
    item["dot"] += float((x * y).sum())
    item["clip_count"] += int(((x / step < qmin) | (x / step > qmax)).sum())
    item["zero_count"] += int((y == 0).sum())
    item["observed_min"] = min(item["observed_min"], float(x.min()))
    item["observed_max"] = max(item["observed_max"], float(x.max()))


def _accumulate_selected_weights(
    controller: StrictS3Controller, experiment: Experiment,
    totals: dict[str, dict[str, float]],
) -> None:
    for name in ("fc1_weight", "fc2_weight"):
        for index in experiment.masks.get(name, ()):
            module = getattr(controller.blocks[index].mlp, name.removesuffix("_weight"))
            if not all(hasattr(module, attr) for attr in ("weight", "segments", "scales", "fake_quant_weight")):
                raise TypeError(f"{name} requires an inspectable W3 module")
            with torch.no_grad():
                before = module.weight.detach()
                after = module.fake_quant_weight().detach()
                scales = module.scales().detach()
            segments = tuple(module.segments)
            if sum(segments) != before.shape[0] or len(segments) != scales.numel():
                raise ValueError(f"invalid W3 segments for {name} block {index}")
            rows = torch.repeat_interleave(scales, torch.tensor(segments, device=scales.device))
            expanded_scale = rows[:, None].expand_as(before).reshape(-1)
            _accumulate_pair(totals, f"{index}:{name}", before, after,
                             scale=expanded_scale, qmin=-4, qmax=3)


def _finalize_metrics(totals: Mapping[str, Mapping[str, float]]) -> dict[str, dict[str, float | int | None]]:
    metrics = {}
    for key, item in sorted(totals.items()):
        n = item["elements"]
        error_sq = item["error_sq"]
        signal_sq = item["before_sq"]
        sqnr = math.inf if error_sq == 0 else 10 * math.log10(signal_sq / error_sq) if signal_sq else -math.inf
        cosine = item["dot"] / (max(math.sqrt(signal_sq), 1e-8) * max(math.sqrt(item["after_sq"]), 1e-8))
        metrics[key] = {
            "elements": int(n), "mse": error_sq / n, "mae": item["error_abs"] / n,
            "cosine": max(-1.0, min(1.0, cosine)),
            "sqnr_db": sqnr if math.isfinite(sqnr) else None,
            "clip_rate": item["clip_count"] / n, "zero_rate": item["zero_count"] / n,
            "observed_min": item["observed_min"], "observed_max": item["observed_max"],
        }
    return metrics


def load_compatible_shard(
    path: str | Path, *, experiment_id: str, expected: Mapping[str, Any],
    experiment: Experiment,
) -> dict[str, Any]:
    """Read a finished shard only if its complete run identity still matches."""

    _validate_identity(expected)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("incompatible shard schema_version")
    if payload.get("experiment_id") != experiment_id:
        raise ValueError("incompatible shard experiment_id")
    if payload.get("experiment_sha256") != experiment_sha256(experiment):
        raise ValueError("incompatible shard experiment_sha256")
    for field in (*IDENTITY_FIELDS, "sample_count"):
        if payload.get(field) != expected[field] or type(payload.get(field)) is not type(expected[field]):
            raise ValueError(f"incompatible shard {field}")
    for field in ("top1", "top5"):
        value = payload.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"invalid shard {field}")
    if payload["top1"] > payload["top5"]:
        raise ValueError("shard top1 exceeds top5")
    _validate_metrics(payload.get("tensor_metrics"), experiment)
    return payload


def write_shard(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Publish one complete experiment as an atomic JSON replacement."""

    atomic_write_json(path, dict(payload))


def evaluate_experiment(
    model: torch.nn.Module,
    controller: StrictS3Controller,
    loader: Iterable[tuple[torch.Tensor, torch.Tensor, Iterable[str]]],
    experiment: Experiment,
    *,
    expected: Mapping[str, Any],
    device: str | torch.device,
) -> dict[str, Any]:
    """Evaluate every unique sample and combine sufficient tensor statistics."""

    _validate_identity(expected)
    if len(controller.blocks) != len(model.vit.blocks):
        raise ValueError("controller and model block counts differ")
    model.eval()
    controller.set_masks(experiment.masks)
    started = time.perf_counter()
    seen: set[str] = set()
    correct1 = correct5 = count = 0
    totals: dict[str, dict[str, float]] = {}
    controller.install()
    try:
        with torch.inference_mode():
            _accumulate_selected_weights(controller, experiment, totals)
            for images, labels, sample_ids in loader:
                ids = tuple(sample_ids)
                batch = len(ids)
                if batch != len(images) or batch != len(labels):
                    raise ValueError("sample IDs, images, and labels have different lengths")
                if len(set(ids)) != batch or any(sample_id in seen for sample_id in ids):
                    raise ValueError("duplicate sample ID in sensitivity evaluation")
                seen.update(ids)
                images = images.to(device)
                labels = labels.to(device)
                controller.observations.clear()
                logits = model(images)
                if logits.ndim != 2 or logits.shape[0] != batch or logits.shape[1] < 5:
                    raise ValueError("model must return at least five class logits per sample")
                top = logits.topk(5, dim=1).indices
                correct1 += int((top[:, 0] == labels).sum())
                correct5 += int((top == labels[:, None]).any(dim=1).sum())
                count += batch
                for (block, name), pair in controller.observations.items():
                    key = f"{block}:{name}"
                    qmin, qmax = BOUNDARIES[name]
                    _accumulate_pair(totals, key, pair["before"], pair["after"],
                                     scale=controller.scale(name, block).detach(),
                                     qmin=qmin, qmax=qmax)
    finally:
        controller.remove()
    if count != expected["sample_count"]:
        raise ValueError(f"sample_count mismatch: expected {expected['sample_count']}, saw {count}")
    tensor_metrics = _finalize_metrics(totals)
    _validate_metrics(tensor_metrics, experiment)
    return {
        "schema_version": 1, "experiment_id": experiment.id,
        "experiment_sha256": experiment_sha256(experiment),
        **{field: expected[field] for field in IDENTITY_FIELDS},
        "sample_count": count, "top1": correct1 / count, "top5": correct5 / count,
        "duration_seconds": time.perf_counter() - started, "device": str(device),
        "tensor_metrics": tensor_metrics,
    }


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def aggregate_shards(
    shard_dir: str | Path, report_dir: str | Path, experiments: Iterable[Experiment],
    *, expected: Mapping[str, Any],
) -> None:
    """Publish formal paper reports only for a complete 50,000-image set."""

    _validate_identity(expected)
    if expected["sample_count"] != 50_000:
        raise ValueError("formal sensitivity reports require exactly 50,000 samples")
    _aggregate_shards(shard_dir, report_dir, experiments, expected=expected, prefix="")


def aggregate_probe_shards(
    shard_dir: str | Path, report_dir: str | Path, experiments: Iterable[Experiment],
    *, expected: Mapping[str, Any],
) -> None:
    """Render explicitly named development reports from a smaller fixed probe."""

    _validate_identity(expected)
    if expected["sample_count"] >= 50_000:
        raise ValueError("probe sensitivity reports require fewer than 50,000 samples")
    _aggregate_shards(shard_dir, report_dir, experiments, expected=expected, prefix="probe_")


def _aggregate_shards(
    shard_dir: str | Path, report_dir: str | Path, experiments: Iterable[Experiment],
    *, expected: Mapping[str, Any], prefix: str,
) -> None:
    cases = tuple(experiments)
    by_id = {item.id: item for item in cases}
    if len(by_id) != len(cases) or "baseline" not in by_id:
        raise ValueError("experiment list requires unique IDs and a baseline")
    root = Path(shard_dir)
    found = {path.stem for path in root.glob("*.json")}
    if found != set(by_id):
        raise ValueError(f"shard completeness mismatch: missing={sorted(set(by_id) - found)}, extra={sorted(found - set(by_id))}")
    loaded = {name: load_compatible_shard(root / f"{name}.json", experiment_id=name,
                                          expected=expected, experiment=by_id[name])
              for name in sorted(by_id)}
    baseline = loaded["baseline"]["top1"]
    output = Path(report_dir)
    columns = ("experiment_id", "family", "block", "perturbation", "order", "step",
               "sensitivity_rank", "perturbation_direction", "tensor_metric_direction",
               "sample_count", "top1", "top5", "top1_drop_pp",
               "duration_seconds", "device", "experiment_sha256", *IDENTITY_FIELDS)
    for family in ("operator", "layer", "cumulative"):
        records = []
        for case in cases:
            if case.family != family:
                continue
            shard = loaded[case.id]
            if case.id == "baseline":
                perturbation_direction, tensor_metric_direction = "no_perturbation", "not_applicable"
            elif case.id in ("operator-fc1_weight", "operator-fc2_weight"):
                perturbation_direction = "W3_to_FP32_removal_ablation"
                tensor_metric_direction = "FP32_master_to_W3_quantized"
            else:
                perturbation_direction = tensor_metric_direction = "FP32_activation_to_strict_quantized"
            records.append({**shard, "family": family, "block": case.block,
                            "perturbation": case.perturbation, "order": case.order,
                            "step": case.step, "masks": case.masks,
                            "perturbation_direction": perturbation_direction,
                            "tensor_metric_direction": tensor_metric_direction,
                            "top1_drop_pp": round((baseline - shard["top1"]) * 100, 10)})
        payload: dict[str, Any] = {"schema_version": 1, "identity": dict(expected), "records": records}
        if family in ("operator", "layer"):
            ranked = sorted((record for record in records if record["experiment_id"] != "baseline"),
                            key=lambda row: (-row["top1_drop_pp"], row["experiment_id"]))
            payload["ranking"] = [record["experiment_id"] for record in ranked]
            ranks = {record["experiment_id"]: index for index, record in enumerate(ranked, start=1)}
            for record in records:
                record["sensitivity_rank"] = ranks.get(record["experiment_id"])
        else:
            for record in records:
                record["sensitivity_rank"] = None
        if family == "layer":
            payload["matrix"] = {str(record["block"]): {
                part: next(row["top1_drop_pp"] for row in records
                           if row["block"] == record["block"] and row["perturbation"] == part)
                for part in ("attention", "mlp", "whole-block")}
                for record in records if record["perturbation"] == "attention"}
        atomic_write_json(output / f"{prefix}{family}_sensitivity.json", payload)
        csv_stream = io.StringIO(newline="")
        writer = csv.DictWriter(csv_stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: "" if record[key] is None else record[key] for key in columns} for record in records)
        _atomic_text(output / f"{prefix}{family}_sensitivity.csv", csv_stream.getvalue())
        headings = ("| Rank | Experiment | Perturbation direction | Tensor metric direction | Top-1 | Top-5 | Drop (pp) | Samples |\n"
                    "|---:|---|---|---|---:|---:|---:|---:|\n")
        rows = "".join(f"| {row['sensitivity_rank'] or '—'} | {row['experiment_id']} | {row['perturbation_direction']} | {row['tensor_metric_direction']} | {row['top1']:.6f} | {row['top5']:.6f} | {row['top1_drop_pp']:.6f} | {row['sample_count']} |\n" for row in records)
        title = f"Probe {family.title()}" if prefix else family.title()
        identity = "\n".join(f"- {name}: `{expected[name]}`" for name in IDENTITY_FIELDS)
        _atomic_text(output / f"{prefix}{family}_sensitivity.md",
                     f"# {title} sensitivity\n\n{headings}{rows}\n"
                     "Perturbation direction describes the model change; tensor metric direction describes the before/after pair used for error statistics.\n\n"
                     f"Top-1 drop is relative to the baseline in percentage points. All rows use the same 50,000-image crop09 role when this is a formal report.\n\n"
                     f"## Frozen identity\n\n{identity}\n")
