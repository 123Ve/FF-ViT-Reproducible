"""Hardware-boundary MLP activation QAT on the fixed ImageNet HLS196 model."""

from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from torch import nn

from .modeling import HLS196_TOKEN_LAYOUT, sha256_file
from .qat_weight import (
    Int3QATLinear,
    _rng_state,
    export_qat_integer_state,
    load_qat_checkpoint,
    qat_module_names,
    restore_rng_state,
)


CALIBRATION_SCHEMA = "imagenet1k.ffvit.mlp_activation_calibration.v1"
PROFILE_CALIBRATION_SCHEMA = "imagenet1k.ffvit.mlp_activation_calibration.v2"
CHECKPOINT_SCHEMA = "imagenet1k.ffvit.mlp_activation_qat_checkpoint.v2"
PROFILE_CHECKPOINT_SCHEMA = "imagenet1k.ffvit.mlp_activation_qat_checkpoint.v3"
LEGACY_CHECKPOINT_SCHEMA = "imagenet1k.ffvit.mlp_activation_qat_checkpoint.v1"
NUMERIC_MODE = "signed_w3_with_mlp_activation_qat_surrogate"
BOUNDARY_RANGES = {
    "ln2": (-4, 3),
    "fc1": (-1024, 1023),
    "gelu": (0, 7),
    "fc2": (-4096, 4095),
    "block": (-4096, 4095),
}
BASELINE_BOUNDARY_PROFILE = "ln2_s3_gelu_u3"
BOUNDARY_PROFILES = {
    BASELINE_BOUNDARY_PROFILE: dict(BOUNDARY_RANGES),
    "ln2_s3_gelu_u4": {**BOUNDARY_RANGES, "gelu": (0, 15)},
    "ln2_s4_gelu_u3": {
        **BOUNDARY_RANGES,
        "ln2": (-8, 7),
        "fc1": (-2048, 2047),
    },
    "ln2_s4_gelu_u4": {
        **BOUNDARY_RANGES,
        "ln2": (-8, 7),
        "fc1": (-2048, 2047),
        "gelu": (0, 15),
    },
    "ln2_s5_gelu_u3": {
        **BOUNDARY_RANGES,
        "ln2": (-16, 15),
        "fc1": (-4096, 4095),
    },
    "ln2_s5_gelu_u4": {
        **BOUNDARY_RANGES,
        "ln2": (-16, 15),
        "fc1": (-4096, 4095),
        "gelu": (0, 15),
    },
    "ln2_s5_gelu_u5": {
        **BOUNDARY_RANGES,
        "ln2": (-16, 15),
        "fc1": (-4096, 4095),
        "gelu": (0, 31),
    },
    "ln2_s6_gelu_u5": {
        **BOUNDARY_RANGES,
        "ln2": (-32, 31),
        "fc1": (-8192, 8191),
        "gelu": (0, 31),
    },
    "ln2_s8_gelu_u8": {
        **BOUNDARY_RANGES,
        "ln2": (-128, 127),
        "fc1": (-32768, 32767),
        "gelu": (0, 255),
    },
}


def boundary_ranges_for_profile(profile: str) -> dict[str, tuple[int, int]]:
    """Return one audited MLP HLS boundary profile without exposing mutable globals."""

    try:
        ranges = BOUNDARY_PROFILES[profile]
    except KeyError as error:
        raise ValueError(f"unsupported MLP boundary profile: {profile!r}") from error
    return dict(ranges)


def activation_numeric_mode(controller: "MLPActivationController") -> str:
    if controller._generic_scale_keys:
        mode = f"signed_w3_with_mlp_activation_qat_surrogate.profile.{controller.boundary_profile}"
        if controller.log_m2_scale is not None:
            mode += ".explicit_requant_s13"
        return mode
    return NUMERIC_MODE


def load_w3_source_checkpoint(path: str | Path) -> tuple[nn.Module, dict[str, Any]]:
    """Strictly dispatch supported W3 checkpoint schemas without reinterpretation."""

    checkpoint = Path(path).expanduser().resolve()
    try:
        header = torch.load(checkpoint, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, TypeError) as error:
        raise ValueError(f"cannot safe-load W3 source checkpoint: {checkpoint}") from error
    if not isinstance(header, Mapping):
        raise ValueError("W3 source checkpoint must contain a mapping")
    schema = header.get("schema")
    if schema == "imagenet1k.ffvit.w3_qat_checkpoint.v1":
        return load_qat_checkpoint(checkpoint)
    if schema == "imagenet1k.ffvit.w3_qat_recovery_checkpoint.v1":
        from .qat_recovery import load_recovery_checkpoint

        model, payload = load_recovery_checkpoint(checkpoint, require_all_active=True)
        recipe = payload.get("recipe")
        if isinstance(recipe, Mapping) and recipe.get("branch") == "final_norm_head_only_from_500k_e7":
            _validate_headrefit_payload(payload)
        return model, payload
    raise ValueError(f"unsupported W3 source checkpoint schema: {schema!r}")


def _validate_headrefit_payload(payload: Mapping[str, Any]) -> None:
    recipe = payload.get("recipe")
    inputs = payload.get("inputs")
    if (
        not isinstance(recipe, Mapping)
        or recipe.get("branch") != "final_norm_head_only_from_500k_e7"
        or recipe.get("trainable_names")
        != ["vit.head.bias", "vit.head.weight", "vit.norm.bias", "vit.norm.weight"]
        or recipe.get("evaluation_profile") != "official_crop_pct_0.9_resize248"
        or not isinstance(inputs, Mapping)
        or set(inputs) != {"source", "contract", "manifest", "initial_checkpoint", "probe"}
    ):
        raise ValueError("head-refit W3 checkpoint recipe/provenance contract mismatch")
    state = payload.get("model_state")
    if not isinstance(state, Mapping) or not all(
        isinstance(state.get(name), torch.Tensor)
        for name in ("vit.norm.weight", "vit.norm.bias", "vit.head.weight", "vit.head.bias")
    ):
        raise ValueError("head-refit W3 checkpoint fitted norm/head state is missing")


def load_headrefit_w3_checkpoint(path: str | Path) -> tuple[nn.Module, dict[str, Any]]:
    """Strictly restore the accepted crop09 head-refit W3 checkpoint."""

    model, payload = load_w3_source_checkpoint(path)
    _validate_headrefit_payload(payload)
    return model, payload


def _file_record(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def round_ste(value: torch.Tensor) -> torch.Tensor:
    """Ties-to-even forward rounding with an identity backward path."""

    return value + (torch.round(value) - value).detach()


def fake_quant_ste(
    value: torch.Tensor, scale: torch.Tensor, qmin: int, qmax: int
) -> torch.Tensor:
    """Apply the canonical clamp/round/dequantize activation surrogate."""

    if qmin >= qmax:
        raise ValueError("qmin must be smaller than qmax")
    safe_scale = scale.clamp_min(1e-12)
    code = round_ste((value / safe_scale).clamp(qmin, qmax))
    return code * safe_scale


def _module_weight_scale(module: nn.Module) -> torch.Tensor:
    if not isinstance(module, Int3QATLinear) or module.log_scale.numel() != 1:
        raise ValueError("MLP boundaries require a one-scale signed-W3 QAT Linear")
    return module.scales().reshape(())


def build_explicit_requant_scales(
    model: nn.Module,
    high_precision_scales: Mapping[str, Mapping[str, Any]],
    reference_scales: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    """Keep the reference s13 output domain after a finer GELU quantizer."""

    count = len(model.vit.blocks)
    expected = {str(block) for block in range(count)}
    if set(high_precision_scales) != expected or set(reference_scales) != expected:
        raise ValueError("requant scale inputs must cover every MLP block exactly once")
    result: dict[str, dict[str, float]] = {}
    for block, module in enumerate(model.vit.blocks):
        key = str(block)
        high = high_precision_scales[key]
        reference = reference_scales[key]
        ln2_scale = float(high.get("ln2_scale", float("nan")))
        gelu_scale = float(high.get("gelu_scale", float("nan")))
        reference_gelu = float(reference.get("gelu_scale", float("nan")))
        values = (ln2_scale, gelu_scale, reference_gelu)
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("requant scale inputs must be finite and positive")
        weight_scale = float(_module_weight_scale(module.mlp.fc2).detach().cpu())
        result[key] = {
            "ln2_scale": ln2_scale,
            "gelu_scale": gelu_scale,
            "m2_int13_scale": reference_gelu * weight_scale,
        }
    return result


class HistogramAbsPercentileObserver:
    """Deterministic fixed-grid observer that counts every finite activation."""

    def __init__(self, *, bins: int = 65536, histogram_max: float = 128.0) -> None:
        if bins <= 0 or not math.isfinite(histogram_max) or histogram_max <= 0:
            raise ValueError("observer bins and histogram_max must be positive")
        self.bins = int(bins)
        self.histogram_max = float(histogram_max)
        self.histogram = torch.zeros(self.bins, dtype=torch.int64)
        self.positive_histogram = torch.zeros(self.bins, dtype=torch.int64)
        self.value_count = 0
        self.nonfinite_count = 0
        self.overflow_count = 0
        self.max_abs = 0.0

    @torch.no_grad()
    def update(self, value: torch.Tensor) -> None:
        flat = value.detach().float().reshape(-1)
        finite = torch.isfinite(flat)
        self.nonfinite_count += int((~finite).sum().item())
        if not bool(finite.any()):
            return
        absolute = flat[finite].abs()
        count = absolute.numel()
        self.value_count += count
        current_max = float(absolute.max().item())
        self.max_abs = max(self.max_abs, current_max)
        self.overflow_count += int((absolute > self.histogram_max).sum().item())
        width = self.histogram_max / self.bins
        indices = torch.ceil(absolute / width).to(torch.int64).sub_(1).clamp_(0, self.bins - 1)
        # Reduce on the activation device and transfer only the fixed-size counts.
        self.histogram += torch.bincount(indices, minlength=self.bins).cpu()
        positive = flat[finite & (flat >= 0)].abs()
        if positive.numel():
            positive_indices = (
                torch.ceil(positive / width).to(torch.int64).sub_(1).clamp_(0, self.bins - 1)
            )
            self.positive_histogram += torch.bincount(
                positive_indices, minlength=self.bins
            ).cpu()

    def export(self, *, percentile: float = 0.999) -> dict[str, Any]:
        if not 0.0 < percentile <= 1.0:
            raise ValueError("percentile must be in (0, 1]")
        if self.value_count <= 0:
            raise ValueError("observer has no finite values")
        rank = max(1, math.ceil(percentile * self.value_count))
        index = int(torch.searchsorted(self.histogram.cumsum(0), rank).item())
        value = min((index + 1) * self.histogram_max / self.bins, self.histogram_max)
        return {
            "method": "deterministic_fixed_histogram_upper_edge",
            "bins": self.bins,
            "histogram_max": self.histogram_max,
            "percentile": float(percentile),
            "abs_percentile": float(value),
            "value_count": self.value_count,
            "nonfinite_count": self.nonfinite_count,
            "overflow_count": self.overflow_count,
            "max_abs": self.max_abs,
            "histogram_sha256": hashlib.sha256(
                self.histogram.numpy().tobytes()
            ).hexdigest(),
            "positive_histogram_sha256": hashlib.sha256(
                self.positive_histogram.numpy().tobytes()
            ).hexdigest(),
        }

    def clipped_mse_scale(
        self,
        qmin: int,
        qmax: int,
        *,
        candidates: Sequence[float] | None = None,
    ) -> dict[str, Any]:
        """Choose a positive HLS-representable scale by histogram-weighted MSE."""

        if qmin >= qmax or qmax <= 0:
            raise ValueError("invalid quantizer range for MSE scale search")
        magnitude_limit = qmax if qmin >= 0 else min(-qmin, qmax)
        if candidates is None:
            base = self.export(percentile=0.999)["abs_percentile"] / magnitude_limit
            candidates = torch.logspace(
                math.log10(max(base * 0.20, 1e-8)),
                math.log10(max(base * 1.25, 1.01e-8)),
                96,
            ).tolist()
        candidate_values = [float(value) for value in candidates]
        if not candidate_values or any(
            not math.isfinite(value) or value <= 0 for value in candidate_values
        ):
            raise ValueError("MSE scale candidates must be finite and positive")
        histogram = self.positive_histogram if qmin >= 0 else self.histogram
        if int(histogram.sum()) == 0:
            raise ValueError("observer has no values for MSE scale search")
        width = self.histogram_max / self.bins
        representative = torch.arange(1, self.bins + 1, dtype=torch.float64) * width
        counts = histogram.to(torch.float64)
        weighted_signal_energy = float(((representative**2) * counts).sum().item())
        best_scale = candidate_values[0]
        best_error = float("inf")
        for scale in candidate_values:
            reconstructed = torch.round(representative / scale).clamp(0, magnitude_limit) * scale
            error = float((((representative - reconstructed) ** 2) * counts).sum().item())
            if error < best_error:
                best_error = error
                best_scale = scale
        return {
            "scale": best_scale,
            "weighted_squared_error": best_error,
            "weighted_signal_energy": weighted_signal_energy,
            "nmse": best_error / max(weighted_signal_energy, 1e-30),
            "candidate_count": len(candidate_values),
            "qmin": int(qmin),
            "qmax": int(qmax),
        }


class SaturationCounter:
    def __init__(self, qmin: int, qmax: int, scale: float) -> None:
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("saturation scale must be finite and positive")
        self.qmin = int(qmin)
        self.qmax = int(qmax)
        self.scale = float(scale)
        self.value_count = 0
        self.nonfinite_count = 0
        self.below_count = 0
        self.above_count = 0

    @torch.no_grad()
    def update(self, value: torch.Tensor) -> None:
        flat = value.detach().float().reshape(-1)
        finite = torch.isfinite(flat)
        self.nonfinite_count += int((~finite).sum().item())
        finite_value = flat[finite]
        self.value_count += finite_value.numel()
        self.below_count += int((finite_value / self.scale < self.qmin).sum().item())
        self.above_count += int((finite_value / self.scale > self.qmax).sum().item())

    def export(self) -> dict[str, Any]:
        saturated = self.below_count + self.above_count
        return {
            "qmin": self.qmin,
            "qmax": self.qmax,
            "scale": self.scale,
            "value_count": self.value_count,
            "nonfinite_count": self.nonfinite_count,
            "below_count": self.below_count,
            "above_count": self.above_count,
            "saturated_count": saturated,
            "saturation_percent": 100.0 * saturated / max(1, self.value_count),
        }


def _read_jsonl(path: str | Path, label: str) -> list[dict[str, Any]]:
    resolved = Path(path).expanduser().resolve()
    try:
        rows = [json.loads(line) for line in resolved.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label} manifest: {resolved}") from error
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{label} manifest records must be mappings")
    return rows


def load_calibration_records(
    calibration_manifest: str | Path,
    qat_manifest: str | Path,
    *,
    expected_count: int = 2000,
    expected_classes: int = 1000,
    per_class: int = 2,
) -> tuple[dict[str, Any], ...]:
    """Validate that calibration is exactly the frozen two/class QAT subset."""

    calibration = _read_jsonl(calibration_manifest, "calibration")
    qat = _read_jsonl(qat_manifest, "QAT")
    if len(calibration) != expected_count:
        raise ValueError(f"calibration manifest must contain exactly {expected_count} records")
    qat_members = {
        (str(Path(str(row.get("path", ""))).expanduser().resolve()), row.get("label"))
        for row in qat
    }
    paths: list[str] = []
    labels: Counter[int] = Counter()
    for row in calibration:
        path = Path(str(row.get("path", ""))).expanduser().resolve()
        label = row.get("label")
        if not path.is_file() or not isinstance(label, int) or isinstance(label, bool):
            raise ValueError("calibration manifest contains an invalid path or label")
        identity = (str(path), label)
        if identity not in qat_members:
            raise ValueError("calibration record is not present in the frozen QAT manifest")
        paths.append(str(path))
        labels[label] += 1
    if len(set(paths)) != len(paths):
        raise ValueError("calibration manifest contains duplicate paths")
    if set(labels) != set(range(expected_classes)) or any(
        count != per_class for count in labels.values()
    ):
        raise ValueError(
            f"calibration manifest must contain exactly {per_class} records for each of "
            f"{expected_classes} classes"
        )
    return tuple(calibration)


def active_blocks_for_epoch(epoch: int) -> list[int]:
    """Canonical rear-to-front Stage4D activation schedule."""

    if epoch < 1:
        raise ValueError("epoch must be positive")
    if epoch == 1:
        return list(range(6, 12))
    if epoch == 2:
        return list(range(3, 12))
    return list(range(12))


def recovery_active_blocks_for_epoch(epoch: int) -> list[int]:
    """Slower 300k rear-to-front schedule for an already-converged W3 base."""

    if epoch < 1:
        raise ValueError("epoch must be positive")
    if epoch == 1:
        return list(range(9, 12))
    if epoch == 2:
        return list(range(6, 12))
    if epoch == 3:
        return list(range(3, 12))
    return list(range(12))


def headrefit_active_blocks_for_epoch(epoch: int) -> list[int]:
    """Two-block rear-to-front schedule for the accepted head-refit base."""

    if epoch < 1:
        raise ValueError("epoch must be positive")
    first = max(0, 12 - 2 * epoch)
    return list(range(first, 12))


class MLPActivationController(nn.Module):
    """Per-block positive scales and ordered MLP boundary fake quantizers."""

    boundary_ranges = dict(BOUNDARY_RANGES)

    def __init__(
        self,
        student: nn.Module,
        initial_scales: Mapping[str, Any],
        *,
        boundary_profile: str = BASELINE_BOUNDARY_PROFILE,
    ) -> None:
        super().__init__()
        # The student owns the weights. Keeping a non-registered reference prevents
        # duplicated model tensors in controller state/checkpoints/optimizers.
        object.__setattr__(self, "_student", student)
        blocks = student.vit.blocks
        self.boundary_profile = boundary_profile
        self.boundary_ranges = boundary_ranges_for_profile(boundary_profile)
        ln2, gelu, m2 = [], [], []
        generic_keys: bool | None = None
        explicit_m2: bool | None = None
        for block in range(len(blocks)):
            entry = initial_scales.get(str(block))
            if not isinstance(entry, Mapping):
                raise ValueError(f"missing activation scales for block {block}")
            this_generic = "ln2_scale" in entry or "gelu_scale" in entry
            if generic_keys is None:
                generic_keys = this_generic
            if this_generic != generic_keys:
                raise ValueError("activation scale key style must be consistent across blocks")
            if this_generic:
                if not {"ln2_scale", "gelu_scale"}.issubset(entry):
                    raise ValueError("mixed precision manifests require both generic scale keys")
                sln = float(entry.get("ln2_scale", float("nan")))
                sge = float(entry.get("gelu_scale", float("nan")))
                this_explicit_m2 = "m2_int13_scale" in entry
                if explicit_m2 is None:
                    explicit_m2 = this_explicit_m2
                if this_explicit_m2 != explicit_m2:
                    raise ValueError("explicit downstream scale must be present for every block")
                if this_explicit_m2:
                    sm2 = float(entry.get("m2_int13_scale", float("nan")))
                    if not math.isfinite(sm2) or sm2 <= 0:
                        raise ValueError("explicit downstream scale must be finite and positive")
                    m2.append(sm2)
            else:
                if boundary_profile != BASELINE_BOUNDARY_PROFILE:
                    raise ValueError("mixed precision profiles require generic scale keys")
                sln = float(entry.get("ln2_signed3_scale", float("nan")))
                sge = float(entry.get("gelu_uint3_scale", float("nan")))
            if not all(math.isfinite(x) and x > 0 for x in (sln, sge)):
                raise ValueError("initial activation scales must be finite and positive")
            ln2.append(sln)
            gelu.append(sge)
        self._generic_scale_keys = bool(generic_keys)
        self.log_ln2_scale = nn.Parameter(torch.tensor(ln2).log())
        self.log_gelu_scale = nn.Parameter(torch.tensor(gelu).log())
        if explicit_m2:
            self.log_m2_scale = nn.Parameter(torch.tensor(m2).log())
        else:
            self.register_parameter("log_m2_scale", None)
        self.active_blocks: set[int] = set(range(len(blocks)))
        self._handles: list[Any] = []

    @property
    def student(self) -> nn.Module:
        return object.__getattribute__(self, "_student")

    def ln2_scale(self, block: int) -> torch.Tensor:
        return self.log_ln2_scale[block].exp()

    def gelu_scale(self, block: int) -> torch.Tensor:
        return self.log_gelu_scale[block].exp()

    def m1_scale(self, block: int) -> torch.Tensor:
        return self.ln2_scale(block) * _module_weight_scale(
            self.student.vit.blocks[block].mlp.fc1
        )

    def m2_scale(self, block: int) -> torch.Tensor:
        if self.log_m2_scale is not None:
            return self.log_m2_scale[block].exp()
        return self.gelu_scale(block) * _module_weight_scale(
            self.student.vit.blocks[block].mlp.fc2
        )

    def set_active(self, blocks: Sequence[int] | range) -> None:
        active = {int(block) for block in blocks}
        count = len(self.student.vit.blocks)
        if any(block < 0 or block >= count for block in active):
            raise ValueError("active block index is out of range")
        self.active_blocks = active

    def assert_finite_scales(self) -> None:
        for name, parameter in (
            ("ln2", self.log_ln2_scale),
            ("gelu", self.log_gelu_scale),
        ):
            scale = parameter.detach().exp()
            if not bool(torch.isfinite(scale).all()) or not bool((scale > 0).all()):
                raise FloatingPointError(f"nonfinite or nonpositive {name} activation scale")
        if self.log_m2_scale is not None:
            scale = self.log_m2_scale.detach().exp()
            if not bool(torch.isfinite(scale).all()) or not bool((scale > 0).all()):
                raise FloatingPointError("nonfinite or nonpositive downstream activation scale")

    def install(self) -> None:
        if self._handles:
            raise RuntimeError("MLP activation hooks are already installed")
        for block_index, block in enumerate(self.student.vit.blocks):
            def quantize(output: torch.Tensor, boundary: str, index: int) -> torch.Tensor:
                if index not in self.active_blocks:
                    return output
                if boundary == "ln2":
                    scale = self.ln2_scale(index)
                elif boundary == "fc1":
                    scale = self.m1_scale(index)
                elif boundary == "gelu":
                    scale = self.gelu_scale(index)
                else:
                    scale = self.m2_scale(index)
                qmin, qmax = self.boundary_ranges[boundary]
                return fake_quant_ste(output, scale, qmin, qmax)

            def ln2_hook(module, inputs, output, index=block_index):
                return quantize(output, "ln2", index)

            def fc1_hook(module, inputs, output, index=block_index):
                return quantize(output, "fc1", index)

            def gelu_hook(module, inputs, output, index=block_index):
                return quantize(output, "gelu", index)

            def fc2_hook(module, inputs, output, index=block_index):
                return quantize(output, "fc2", index)

            def block_hook(module, inputs, output, index=block_index):
                return quantize(output, "block", index)

            self._handles.extend(
                [
                    block.norm2.register_forward_hook(ln2_hook),
                    block.mlp.fc1.register_forward_hook(fc1_hook),
                    block.mlp.act.register_forward_hook(gelu_hook),
                    block.mlp.fc2.register_forward_hook(fc2_hook),
                    block.register_forward_hook(block_hook),
                ]
            )

    def remove(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()

    def export_scales(self) -> dict[str, dict[str, Any]]:
        self.assert_finite_scales()
        ln2 = self.log_ln2_scale.detach().cpu().exp()
        gelu = self.log_gelu_scale.detach().cpu().exp()
        # Export on one canonical device.  CUDA and CPU expf differ by one ULP
        # for real trained values, so exp-before-copy makes a GPU-saved
        # checkpoint fail its strict CPU reload comparison.
        m2 = (
            self.log_m2_scale.detach().cpu().exp()
            if self.log_m2_scale is not None
            else None
        )
        result: dict[str, dict[str, float]] = {}
        for block, module in enumerate(self.student.vit.blocks):
            sw1 = float(module.mlp.fc1.log_scale.detach().cpu().exp().reshape(()))
            sw2 = float(module.mlp.fc2.log_scale.detach().cpu().exp().reshape(()))
            sln = float(ln2[block])
            sge = float(gelu[block])
            if self._generic_scale_keys:
                # Keep the historical Python-float multiplication for derived
                # profile-v3 exports.  Computing the product as an FP32 tensor
                # changes the final bits and breaks strict old-checkpoint load.
                m2_scale = (
                    float(m2[block])
                    if m2 is not None
                    else sge * sw2
                )
                result[str(block)] = {
                    "boundary_profile": self.boundary_profile,
                    "ln2_scale": sln,
                    "w1_signed3_scale": sw1,
                    "m1_scale": sln * sw1,
                    "gelu_scale": sge,
                    "w2_signed3_scale": sw2,
                    "m2_int13_scale": m2_scale,
                    "fm_int13_scale": m2_scale,
                }
                # Preserve byte-for-byte compatibility with existing profile-v3
                # checkpoints.  Only the new explicit-requant extension needs a
                # discriminator; legacy derived m2 exports had no source field.
                if self.log_m2_scale is not None:
                    result[str(block)]["m2_scale_source"] = "explicit_requant"
            else:
                result[str(block)] = {
                    "ln2_signed3_scale": sln,
                    "w1_signed3_scale": sw1,
                    "m1_int11_scale": sln * sw1,
                    "gelu_uint3_scale": sge,
                    "w2_signed3_scale": sw2,
                    "m2_int13_scale": sge * sw2,
                    "fm_int13_scale": sge * sw2,
                }
        return result


def read_activation_manifest(
    path: str | Path, *, source_w3_qat: str | Path | None = None
) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read activation calibration manifest: {resolved}") from error
    if not isinstance(payload, Mapping) or payload.get("schema") not in (
        CALIBRATION_SCHEMA,
        PROFILE_CALIBRATION_SCHEMA,
    ):
        raise ValueError("activation calibration schema mismatch")
    profile_manifest = payload.get("schema") == PROFILE_CALIBRATION_SCHEMA
    if profile_manifest:
        profile = payload.get("boundary_profile")
        if not isinstance(profile, str):
            raise ValueError("mixed precision activation manifest boundary profile is missing")
        ranges = boundary_ranges_for_profile(profile)
        expected_quantization = {
            name: {"qmin": bounds[0], "qmax": bounds[1]}
            for name, bounds in ranges.items()
        }
        if payload.get("quantization") != expected_quantization:
            raise ValueError("boundary profile and quantization contract mismatch")
        scale_keys = ("ln2_scale", "gelu_scale")
    else:
        profile = BASELINE_BOUNDARY_PROFILE
        scale_keys = ("ln2_signed3_scale", "gelu_uint3_scale")
    calibration_count = payload.get("calibration_image_count")
    if calibration_count not in (2000, 10_000) or payload.get(
        "calibration_unique_image_count"
    ) != calibration_count:
        raise ValueError("activation calibration must use exactly 2,000 or 10,000 unique images")
    if source_w3_qat is not None and payload.get("source_w3_qat_checkpoint") != _file_record(
        source_w3_qat
    ):
        raise ValueError("activation calibration source checkpoint provenance mismatch")
    for field in ("source_w3_qat_checkpoint", "calibration_manifest", "qat_manifest"):
        record = payload.get(field)
        if not isinstance(record, Mapping) or dict(record) != _file_record(record.get("path", "")):
            raise ValueError(f"activation calibration provenance mismatch: {field}")
    scales = payload.get("initial_scales")
    if not isinstance(scales, Mapping) or set(scales) != {str(i) for i in range(12)}:
        raise ValueError("activation calibration must contain scales for all 12 blocks")
    for entry in scales.values():
        if not isinstance(entry, Mapping) or any(
            not math.isfinite(float(entry.get(name, float("nan"))))
            or float(entry[name]) <= 0
            for name in scale_keys
        ):
            raise ValueError("activation calibration scales must be finite and positive")
    return dict(payload)


def build_mlp_activation_qat(
    source_w3_qat: str | Path, activation_manifest: str | Path
) -> tuple[nn.Module, MLPActivationController, dict[str, Any]]:
    """Strictly restore Task 4 and add only the canonical MLP boundary hooks."""

    manifest = read_activation_manifest(activation_manifest, source_w3_qat=source_w3_qat)
    student, _ = load_w3_source_checkpoint(source_w3_qat)
    if student._ffvit_token_layout != HLS196_TOKEN_LAYOUT or len(qat_module_names(student)) != 48:
        raise ValueError("source does not preserve the signed-W3 HLS196 contract")
    controller = MLPActivationController(
        student,
        manifest["initial_scales"],
        boundary_profile=manifest.get("boundary_profile", BASELINE_BOUNDARY_PROFILE),
    )
    controller.install()
    controller.set_active(range(12))
    return student, controller, manifest


def _verify_inputs(recorded: Mapping[str, Any], expected: Mapping[str, str | Path]) -> None:
    if set(recorded) != set(expected):
        raise ValueError("activation checkpoint input provenance key mismatch")
    for name, path in expected.items():
        if dict(recorded[name]) != _file_record(path):
            raise ValueError(f"activation checkpoint input provenance mismatch: {name}")


def save_activation_checkpoint(
    path: str | Path,
    *,
    student: nn.Module,
    controller: MLPActivationController,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    scaler: Any,
    epoch: int,
    best_metric: float,
    history: Sequence[Mapping[str, Any]],
    initial_metric: Mapping[str, Any],
    inputs: Mapping[str, str | Path],
) -> dict[str, Any]:
    required = {
        "source_w3_qat",
        "qat_manifest",
        "calibration_manifest",
        "activation_manifest",
    }
    if set(inputs) != required:
        raise ValueError("activation checkpoint requires all fixed input paths")
    controller.assert_finite_scales()
    exported = controller.export_scales()
    profile_checkpoint = controller._generic_scale_keys
    payload = {
        "schema": PROFILE_CHECKPOINT_SCHEMA if profile_checkpoint else CHECKPOINT_SCHEMA,
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": activation_numeric_mode(controller),
        "epoch": int(epoch),
        "best_metric": float(best_metric),
        "history": [dict(row) for row in history],
        "initial_metric": dict(initial_metric),
        "inputs": {name: _file_record(value) for name, value in inputs.items()},
        "student_state": {
            name: value.detach().cpu() for name, value in student.state_dict().items()
        },
        "controller_state": {
            name: value.detach().cpu() for name, value in controller.state_dict().items()
        },
        "controller_active_blocks": sorted(controller.active_blocks),
        "optimizer_state": optimizer.state_dict(),
        "scheduler_state": scheduler.state_dict(),
        "scaler_state": scaler.state_dict(),
        "rng_state": _rng_state(),
        "exported_scales": exported,
        "w3_integer_export": export_qat_integer_state(student),
    }
    if profile_checkpoint:
        payload["boundary_profile"] = controller.boundary_profile
        payload["boundary_ranges"] = dict(controller.boundary_ranges)
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    try:
        torch.save(payload, temporary)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def load_activation_checkpoint(
    path: str | Path,
    *,
    expected_inputs: Mapping[str, str | Path] | None = None,
) -> tuple[nn.Module, MLPActivationController, dict[str, Any]]:
    checkpoint_path = Path(path).expanduser().resolve()
    try:
        payload = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, TypeError) as error:
        raise ValueError(f"cannot safe-load activation checkpoint: {checkpoint_path}") from error
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema") not in (
            PROFILE_CHECKPOINT_SCHEMA,
            CHECKPOINT_SCHEMA,
            LEGACY_CHECKPOINT_SCHEMA,
        )
        or payload.get("token_layout") != HLS196_TOKEN_LAYOUT
    ):
        raise ValueError("activation checkpoint schema or HLS196 contract mismatch")
    recorded = payload.get("inputs")
    if not isinstance(recorded, Mapping):
        raise ValueError("activation checkpoint input provenance is missing")
    if expected_inputs is None:
        expected_inputs = {name: record["path"] for name, record in recorded.items()}
    _verify_inputs(recorded, expected_inputs)
    student, controller, _ = build_mlp_activation_qat(
        recorded["source_w3_qat"]["path"], recorded["activation_manifest"]["path"]
    )
    expected_numeric_mode = activation_numeric_mode(controller)
    if payload.get("numeric_mode") != expected_numeric_mode:
        raise ValueError("activation checkpoint numeric mode mismatch")
    if payload.get("schema") == PROFILE_CHECKPOINT_SCHEMA and (
        payload.get("boundary_profile") != controller.boundary_profile
        or payload.get("boundary_ranges") != controller.boundary_ranges
    ):
        raise ValueError("activation checkpoint boundary profile mismatch")
    if payload.get("schema") != PROFILE_CHECKPOINT_SCHEMA and controller._generic_scale_keys:
        raise ValueError("mixed precision checkpoint requires the profile checkpoint schema")
    try:
        student.load_state_dict(payload["student_state"], strict=True)
        controller.load_state_dict(payload["controller_state"], strict=True)
        controller.set_active(payload["controller_active_blocks"])
    except (KeyError, RuntimeError, TypeError, ValueError) as error:
        raise ValueError(f"activation checkpoint state is incompatible: {error}") from error
    controller.assert_finite_scales()
    if payload.get("exported_scales") != controller.export_scales():
        raise ValueError("activation checkpoint exported scales do not match restored state")
    if payload.get("schema") in (CHECKPOINT_SCHEMA, PROFILE_CHECKPOINT_SCHEMA):
        actual_w3 = export_qat_integer_state(student)
        stored_w3 = payload.get("w3_integer_export")
        if not isinstance(stored_w3, Mapping) or set(stored_w3) != set(actual_w3):
            raise ValueError("activation checkpoint W3 export is missing or incomplete")
        for name, actual in actual_w3.items():
            stored = stored_w3[name]
            if (
                stored.get("qmin") != actual["qmin"]
                or stored.get("qmax") != actual["qmax"]
                or stored.get("segments") != actual["segments"]
                or stored.get("code_sha256") != actual["code_sha256"]
                or not torch.equal(stored.get("code"), actual["code"])
                or not torch.equal(stored.get("scales"), actual["scales"])
            ):
                raise ValueError(f"activation checkpoint W3 export mismatch: {name}")
    if len(qat_module_names(student)) != 48 or student._ffvit_token_layout != HLS196_TOKEN_LAYOUT:
        raise ValueError("restored activation checkpoint lost W3 or HLS196 structure")
    student.evaluation_provenance = {
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "source_checkpoint_sha256": recorded["source_w3_qat"]["sha256"],
        "training_manifest_sha256": recorded["qat_manifest"]["sha256"],
        "calibration_manifest_sha256": recorded["calibration_manifest"]["sha256"],
        "activation_manifest_sha256": recorded["activation_manifest"]["sha256"],
        "token_layout": dict(HLS196_TOKEN_LAYOUT),
        "numeric_mode": payload["numeric_mode"],
    }
    student.eval()
    return student, controller, dict(payload)


def restore_activation_training_state(
    payload: Mapping[str, Any],
    optimizer: Any,
    scheduler: Any,
    scaler: Any,
    *,
    restore_scaler: bool = True,
) -> None:
    optimizer.load_state_dict(payload["optimizer_state"])
    scheduler.load_state_dict(payload["scheduler_state"])
    if restore_scaler:
        scaler.load_state_dict(payload["scaler_state"])
    restore_rng_state(payload["rng_state"])


def distillation_loss(
    student_logits: torch.Tensor,
    teacher_logits: torch.Tensor,
    labels: torch.Tensor,
    *,
    alpha: float = 0.5,
    temperature: float = 2.0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    ce = F.cross_entropy(student_logits, labels)
    kd = F.kl_div(
        F.log_softmax(student_logits / temperature, dim=1),
        F.softmax(teacher_logits / temperature, dim=1),
        reduction="batchmean",
    ) * temperature**2
    return (1.0 - alpha) * ce + alpha * kd, ce.detach(), kd.detach()


class _BoundaryCollector:
    def __init__(self, model: nn.Module, factories: Mapping[str, Any]) -> None:
        self.values: dict[str, Any] = {}
        self.handles: list[Any] = []
        for block_index, block in enumerate(model.vit.blocks):
            for boundary, module in (
                ("ln2", block.norm2),
                ("fc1", block.mlp.fc1),
                ("gelu", block.mlp.act),
                ("fc2", block.mlp.fc2),
                ("block", block),
            ):
                key = f"b{block_index}.{boundary}_out"
                observer = factories[boundary](block_index)
                self.values[key] = observer

                def hook(owner, inputs, output, observer=observer):
                    observer.update(output)

                self.handles.append(module.register_forward_hook(hook))

    def remove(self) -> None:
        for handle in self.handles:
            handle.remove()
        self.handles.clear()


@torch.inference_mode()
def _calibration_pass(
    model: nn.Module, loader: Any, device: torch.device, *, expected_count: int
) -> int:
    model.eval()
    total = 0
    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        logits = model(images)
        if not bool(torch.isfinite(logits).all()):
            raise FloatingPointError("nonfinite logits during MLP activation calibration")
        total += int(labels.numel())
    if total != expected_count:
        raise ValueError(
            f"activation calibration requires exactly {expected_count:,} images; found {total}"
        )
    return total


def calibrate_activation_manifest(
    model: nn.Module,
    loader: Any,
    *,
    device: str | torch.device,
    source_w3_qat: str | Path,
    calibration_manifest: str | Path,
    qat_manifest: str | Path,
    expected_count: int = 2000,
    boundary_profile: str | None = None,
) -> dict[str, Any]:
    """Observe all 2,000 images and return initial scales plus exact saturation counts."""

    profile = boundary_profile or BASELINE_BOUNDARY_PROFILE
    boundary_ranges = boundary_ranges_for_profile(profile)
    generic_scale_keys = boundary_profile is not None
    ln_scale_key = "ln2_scale" if generic_scale_keys else "ln2_signed3_scale"
    gelu_scale_key = "gelu_scale" if generic_scale_keys else "gelu_uint3_scale"
    resolved_device = torch.device(device)
    model.to(resolved_device)
    histogram_max = {"ln2": 16.0, "fc1": 128.0, "gelu": 64.0, "fc2": 128.0, "block": 128.0}
    observers = _BoundaryCollector(
        model,
        {
            name: (lambda block, maximum=maximum: HistogramAbsPercentileObserver(
                bins=65536, histogram_max=maximum
            ))
            for name, maximum in histogram_max.items()
        },
    )
    try:
        first_count = _calibration_pass(
            model, loader, resolved_device, expected_count=expected_count
        )
    finally:
        observers.remove()
    statistics = {name: observer.export(percentile=0.999) for name, observer in observers.values.items()}
    if any(row["nonfinite_count"] for row in statistics.values()):
        raise FloatingPointError("nonfinite MLP activation observed during calibration")
    initial_scales: dict[str, dict[str, float]] = {}
    mse_scales: dict[str, dict[str, float]] = {}
    mse_search: dict[str, dict[str, Any]] = {}
    for block in range(12):
        ln_qmin, ln_qmax = boundary_ranges["ln2"]
        ge_qmin, ge_qmax = boundary_ranges["gelu"]
        sln = max(
            float(statistics[f"b{block}.ln2_out"]["abs_percentile"]) / ln_qmax,
            1e-8,
        )
        sge = max(
            float(statistics[f"b{block}.gelu_out"]["abs_percentile"]) / ge_qmax,
            1e-8,
        )
        initial_scales[str(block)] = {
            ln_scale_key: sln,
            gelu_scale_key: sge,
        }
        ln_search = observers.values[f"b{block}.ln2_out"].clipped_mse_scale(
            ln_qmin, ln_qmax
        )
        ge_search = observers.values[f"b{block}.gelu_out"].clipped_mse_scale(
            ge_qmin, ge_qmax
        )
        mse_scales[str(block)] = {
            ln_scale_key: float(ln_search["scale"]),
            gelu_scale_key: float(ge_search["scale"]),
        }
        mse_search[str(block)] = {"ln2": ln_search, "gelu": ge_search}

    def saturation_factories(scales: Mapping[str, Mapping[str, float]]) -> dict[str, Any]:
        factories: dict[str, Any] = {}
        for boundary, (qmin, qmax) in boundary_ranges.items():
            def factory(block: int, boundary=boundary, qmin=qmin, qmax=qmax):
                entry = scales[str(block)]
                if boundary == "ln2":
                    scale = entry[ln_scale_key]
                elif boundary == "gelu":
                    scale = entry[gelu_scale_key]
                elif boundary == "fc1":
                    sw = float(model.vit.blocks[block].mlp.fc1.log_scale.detach().cpu().exp())
                    scale = entry[ln_scale_key] * sw
                else:
                    sw = float(model.vit.blocks[block].mlp.fc2.log_scale.detach().cpu().exp())
                    scale = entry[gelu_scale_key] * sw
                return SaturationCounter(qmin, qmax, scale)

            factories[boundary] = factory
        return factories

    saturation = _BoundaryCollector(model, saturation_factories(initial_scales))
    mse_saturation = _BoundaryCollector(model, saturation_factories(mse_scales))
    try:
        second_count = _calibration_pass(
            model, loader, resolved_device, expected_count=expected_count
        )
    finally:
        saturation.remove()
        mse_saturation.remove()
    for name, counter in saturation.values.items():
        statistics[name]["saturation"] = counter.export()
        statistics[name]["saturation_candidates"] = {
            "p999": counter.export(),
            "clipped_mse": mse_saturation.values[name].export(),
        }
        if counter.nonfinite_count:
            raise FloatingPointError("nonfinite MLP activation observed during saturation pass")
    result = {
        "schema": PROFILE_CALIBRATION_SCHEMA if generic_scale_keys else CALIBRATION_SCHEMA,
        "source_w3_qat_checkpoint": _file_record(source_w3_qat),
        "calibration_manifest": _file_record(calibration_manifest),
        "qat_manifest": _file_record(qat_manifest),
        "calibration_image_count": first_count,
        "calibration_unique_image_count": first_count,
        "calibration_passes": 2,
        "images_per_pass": [first_count, second_count],
        "percentile": 0.999,
        "quantization": {
            name: {"qmin": bounds[0], "qmax": bounds[1]}
            for name, bounds in boundary_ranges.items()
        },
        "initial_scales": initial_scales,
        "alternative_initial_scales": {"clipped_mse": mse_scales},
        "clipped_mse_search": mse_search,
        "statistics": statistics,
    }
    if generic_scale_keys:
        result["boundary_profile"] = profile
    return result
