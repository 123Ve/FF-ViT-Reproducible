"""Frozen train-only membership and histogram-MSE activation calibration."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

from .provenance import sha256_file
from .quant import BOUNDARIES


def derive_low_sensitivity_order(shards: Mapping[str, Mapping[str, Any]], *, blocks: int) -> tuple[int, ...]:
    """Sort whole-block perturbations by highest retained Top-1, then block ID."""

    if blocks <= 0:
        raise ValueError("blocks must be positive")
    values = []
    for index in range(blocks):
        row = shards[f"layer-{index:02d}-whole-block"]
        top1 = row["top1"]
        if not isinstance(top1, (int, float)) or not math.isfinite(top1) or not 0 <= top1 <= 1:
            raise ValueError(f"invalid layer Top-1 at {index}")
        values.append((index, float(top1)))
    return tuple(index for index, _ in sorted(values, key=lambda row: (-row[1], row[0])))


def select_disjoint_manifests(
    root: str | Path, class_mapping: Mapping[str, int], *, per_class: int, seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Choose two independent roles from one deterministic per-class draw."""

    if per_class <= 0 or not class_mapping:
        raise ValueError("per_class and class_mapping must be positive")
    root = Path(root).resolve()
    roles: tuple[list[dict[str, Any]], list[dict[str, Any]]] = ([], [])
    for class_name, label in sorted(class_mapping.items()):
        folder = root / class_name
        candidates = sorted(path for path in folder.iterdir()
                            if path.is_file() and path.suffix.lower() in (".jpeg", ".jpg", ".png"))
        if len(candidates) < 2 * per_class:
            raise ValueError(f"class {class_name} has fewer than {2 * per_class} images")
        material = f"{seed}:{class_name}:task4".encode("ascii")
        chosen = random.Random(int.from_bytes(hashlib.sha256(material).digest()[:16], "big")).sample(
            candidates, 2 * per_class)
        for role, members in enumerate((chosen[:per_class], chosen[per_class:])):
            for path in sorted(members):
                roles[role].append({
                    "schema": "imagenet1k.train_sample.v1", "path": str(path.resolve()),
                    "relative_path": path.relative_to(root).as_posix(),
                    "class_name": class_name, "label": label,
                    "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                })
    validate_manifest_pair(*roles, class_mapping, per_class=per_class)
    return roles


def validate_manifest_pair(calibration, selection, class_mapping, *, per_class: int) -> None:
    expected = {name: per_class for name in class_mapping}
    identities = []
    for role, records in (("calibration", calibration), ("selection", selection)):
        counts = Counter(record["class_name"] for record in records)
        if counts != expected or len(records) != len(class_mapping) * per_class:
            raise ValueError(f"{role} membership is not stratified")
        names = []
        for record in records:
            relative = record["relative_path"]
            if record["label"] != class_mapping[record["class_name"]] or Path(relative).parts[0] != record["class_name"]:
                raise ValueError(f"{role} label or class mismatch")
            names.append(relative)
        if len(names) != len(set(names)):
            raise ValueError(f"{role} contains duplicate samples")
        identities.append(set(names))
    if identities[0] & identities[1]:
        raise ValueError("calibration and selection overlap")


def atomic_write_jsonl(path: str | Path, records) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def fit_histogram_mse(values: np.ndarray, *, qmin: int, qmax: int, bins: int = 4096):
    """Fit a scalar step on a fixed-grid histogram with ties-to-even codes."""

    values = np.asarray(values, dtype=np.float64).reshape(-1)
    if not values.size or not np.isfinite(values).all() or qmin >= qmax or bins < 32:
        raise ValueError("invalid histogram input")
    minimum, maximum = float(values.min()), float(values.max())
    if minimum == maximum:
        maximum = minimum + 1e-6
    counts, edges = np.histogram(values, bins=bins, range=(minimum, maximum))
    return fit_histogram_counts(counts, minimum, maximum, qmin=qmin, qmax=qmax,
                                observed_min=float(values.min()), observed_max=float(values.max()))


def fit_histogram_counts(counts, minimum: float, maximum: float, *, qmin: int, qmax: int,
                         observed_min: float, observed_max: float):
    counts = np.asarray(counts, dtype=np.float64)
    if counts.ndim != 1 or counts.size < 32 or not np.isfinite(counts).all() or np.any(counts < 0) or counts.sum() == 0:
        raise ValueError("invalid histogram counts")
    centers = minimum + (np.arange(counts.size) + .5) * (maximum - minimum) / counts.size
    positive = counts > 0
    values, weights = centers[positive], counts[positive]
    order = np.argsort(np.abs(values), kind="stable")
    sorted_weights = weights[order]
    rank = np.searchsorted(np.cumsum(sorted_weights), .999 * sorted_weights.sum())
    p999 = abs(values[order[min(rank, len(order) - 1)]])
    code_limit = qmax if qmin >= 0 else min(-qmin, qmax)
    base = max(p999 / code_limit, 1e-8)
    candidates = np.geomspace(base * .2, base * 1.5, 128)
    errors = []
    for scale in candidates:
        reconstruction = np.clip(np.rint(values / scale), qmin, qmax) * scale
        errors.append(float(np.dot(weights, np.square(values - reconstruction))))
    winner = int(np.argmin(errors))
    scale = float(np.float32(candidates[winner]))
    return scale, {"count": int(weights.sum()), "mse_estimate": errors[winner] / weights.sum(),
                   "observed_min": observed_min, "observed_max": observed_max,
                   "histogram_min": minimum, "histogram_max": maximum, "bins": int(counts.size),
                   "candidate_count": len(candidates)}


HISTOGRAM_RANGES = {
    "ln1": (-16., 16.), "q": (-32., 32.), "k": (-32., 32.), "v": (-32., 32.),
    "a": (-32., 32.), "softmax": (0., 1.), "o": (-64., 64.),
    "attention_residual": (-64., 64.), "ln2": (-32., 32.),
    "fc1": (-64., 64.), "gelu": (-1., 64.), "fc2": (-64., 64.),
    "mlp_residual": (-64., 64.),
}


class ActivationHistograms:
    def __init__(self, *, blocks: int, device: str, bins: int = 4096):
        self.blocks, self.device, self.bins = blocks, device, bins
        self.counts = {(i, name): torch.zeros(bins, device=device, dtype=torch.int64)
                       for i in range(blocks) for name in BOUNDARIES}
        self.extrema = {(i, name): [torch.tensor(math.inf, device=device),
                                    torch.tensor(-math.inf, device=device), 0]
                        for i in range(blocks) for name in BOUNDARIES}

    def update(self, index: int, name: str, value: torch.Tensor) -> None:
        minimum, maximum = HISTOGRAM_RANGES[name]
        x = value.detach().float().reshape(-1)
        # Bound checks remain on device until the complete calibration pass.
        self.counts[(index, name)] += torch.histc(x, bins=self.bins, min=minimum, max=maximum).to(torch.int64)
        row = self.extrema[(index, name)]
        row[0] = torch.minimum(row[0], x.min())
        row[1] = torch.maximum(row[1], x.max())
        row[2] += x.numel()

    def fit(self):
        scales = {name: [] for name in BOUNDARIES}
        audits = {}
        failures = []
        for name in BOUNDARIES:
            low, high = HISTOGRAM_RANGES[name]
            for index in range(self.blocks):
                counts = self.counts[(index, name)].cpu().numpy()
                low_tensor, high_tensor, count = self.extrema[(index, name)]
                observed_min, observed_max = float(low_tensor), float(high_tensor)
                if count != int(counts.sum()) or observed_min < low or observed_max > high:
                    failures.append(f"{index}:{name}: {observed_min}, {observed_max}, {count}, {counts.sum()}")
                    continue
                qmin, qmax = BOUNDARIES[name]
                scale, audit = fit_histogram_counts(counts, low, high, qmin=qmin, qmax=qmax,
                                                    observed_min=observed_min, observed_max=observed_max)
                scales[name].append(scale)
                audits[f"{index}:{name}"] = audit
        if failures:
            raise ValueError("histogram range overflow or missing values at " + "; ".join(failures))
        return scales, audits
