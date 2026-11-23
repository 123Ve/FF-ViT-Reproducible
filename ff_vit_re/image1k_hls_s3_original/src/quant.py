"""Strict original-HLS quantization hooks and tensor error measurements."""

from __future__ import annotations

import math
from types import MethodType
from typing import Any, Iterable, Mapping

import torch
from torch import nn
import torch.nn.functional as F


BOUNDARIES = {
    "ln1": (-4, 3),
    "q": (-4, 3),
    "k": (-4, 3),
    "v": (-4, 3),
    "a": (-4, 3),
    "softmax": (0, 7),
    "o": (-4096, 4095),
    "attention_residual": (-16384, 16383),
    "ln2": (-4, 3),
    "fc1": (-1024, 1023),
    "gelu": (0, 7),
    "fc2": (-4096, 4095),
    "mlp_residual": (-4096, 4095),
}
WEIGHT_OPERATORS = frozenset({"fc1_weight", "fc2_weight"})
OPERATORS = frozenset(BOUNDARIES) | WEIGHT_OPERATORS


def fake_quantize(
    value: torch.Tensor,
    scale: float | torch.Tensor,
    *,
    signed: bool,
    bits: int,
) -> torch.Tensor:
    """Clamp, round ties-to-even, then dequantize with an identity STE."""

    if type(bits) is not int or bits < 1 or (signed and bits < 2):
        raise ValueError("invalid quantization width")
    step = torch.as_tensor(scale, dtype=value.dtype, device=value.device)
    if not bool(torch.isfinite(step).all()) or not bool((step > 0).all()):
        raise ValueError("quantization scale must be finite and positive")
    qmin = -(1 << (bits - 1)) if signed else 0
    qmax = (1 << (bits - 1)) - 1 if signed else (1 << bits) - 1
    scaled = (value / step).clamp(qmin, qmax)
    code = scaled + (torch.round(scaled) - scaled).detach()
    return code * step


def tensor_error_statistics(
    before: torch.Tensor,
    after: torch.Tensor,
    *,
    qmin: int,
    qmax: int,
    scale: float | torch.Tensor,
) -> dict[str, float]:
    """Report quantization distortion, saturation, sparsity, and observed range."""

    if before.shape != after.shape or not before.numel():
        raise ValueError("tensor pair must have the same nonempty shape")
    x = before.detach().float().reshape(-1)
    y = after.detach().float().reshape(-1)
    step = torch.as_tensor(scale, dtype=x.dtype, device=x.device)
    if not bool(torch.isfinite(x).all()) or not bool(torch.isfinite(y).all()):
        raise ValueError("tensor pair must be finite")
    if not bool(torch.isfinite(step).all()) or not bool((step > 0).all()):
        raise ValueError("scale must be finite and positive")
    error = x - y
    mse = float(error.square().mean())
    signal = float(x.square().mean())
    return {
        "mse": mse,
        "mae": float(error.abs().mean()),
        "cosine": float(F.cosine_similarity(x.unsqueeze(0), y.unsqueeze(0), dim=1)),
        "sqnr_db": math.inf if mse == 0 else 10 * math.log10(signal / mse) if signal else -math.inf,
        "clip_rate": float(((x / step < qmin) | (x / step > qmax)).float().mean()),
        "zero_rate": float((y == 0).float().mean()),
        "observed_min": float(x.min()),
        "observed_max": float(x.max()),
    }


class StrictS3Controller(nn.Module):
    """Toggle exact-width surrogate boundaries by operator and transformer block.

    Scales are a mapping from operator to one positive scale per block. They must
    come from calibration data before an operator is enabled in a real run.
    The model owns all parameters; the controller only installs removable hooks.
    """

    def __init__(self, model: nn.Module, *, scales: Mapping[str, Iterable[float]]):
        super().__init__()
        object.__setattr__(self, "model", model)
        self.blocks = tuple(model.vit.blocks)
        if not self.blocks:
            raise ValueError("strict controller requires transformer blocks")
        self.log_scales = nn.ParameterDict()
        model_device = next(model.parameters()).device
        for name, values in scales.items():
            if name not in BOUNDARIES:
                raise ValueError(f"unknown scale boundary: {name}")
            frozen = tuple(float(value) for value in values)
            if len(frozen) != len(self.blocks) or any(not math.isfinite(x) or x <= 0 for x in frozen):
                raise ValueError(f"{name} requires one finite positive scale per block")
            self.log_scales[name] = nn.Parameter(torch.tensor(frozen, device=model_device).log())
        self.enabled: set[str] = set()
        self.active_blocks: set[int] = set(range(len(self.blocks)))
        self.operator_blocks: dict[str, frozenset[int]] = {}
        self.observations: dict[tuple[int, str], dict[str, torch.Tensor]] = {}
        self._handles: list[Any] = []
        self._original_attention: dict[int, Any] = {}
        self._original_block: dict[int, Any] = {}
        self._original_weight_states: dict[tuple[int, str], bool] = {}

    def set_enabled(self, operators: Iterable[str], *, blocks: Iterable[int] | None = None) -> None:
        active = set(range(len(self.blocks))) if blocks is None else set(blocks)
        self.set_masks({name: active for name in operators})

    def set_masks(self, masks: Mapping[str, Iterable[int]]) -> None:
        """Set an independent block mask for each enabled operator."""

        selected = set(masks)
        unknown = selected - OPERATORS
        if unknown:
            raise ValueError(f"unknown strict operators: {sorted(unknown)}")
        normalized = {name: frozenset(indices) for name, indices in masks.items()}
        for active in normalized.values():
            if any(type(index) is not int or index < 0 or index >= len(self.blocks) for index in active):
                raise ValueError("active block index is out of range")
        missing = (selected & BOUNDARIES.keys()) - self.log_scales.keys()
        if missing:
            raise ValueError(f"missing calibrated scales: {sorted(missing)}")
        self._validate_weight_targets(normalized)
        self.enabled = selected
        self.active_blocks = set().union(*normalized.values()) if normalized else set()
        self.operator_blocks = normalized
        self.observations.clear()
        self._update_weight_masks()

    def _validate_weight_targets(self, masks: Mapping[str, frozenset[int]]) -> None:
        for name in WEIGHT_OPERATORS:
            for index in masks.get(name, ()):
                module = getattr(self.blocks[index].mlp, name.removesuffix("_weight"))
                if not hasattr(module, "set_quant_enabled") or not hasattr(module, "quant_enabled"):
                    raise TypeError(f"{name} requires a progressive W3 module")

    def _is_active(self, index: int, name: str) -> bool:
        return index in self.operator_blocks.get(name, ())

    def scale(self, name: str, index: int) -> torch.Tensor:
        return self.log_scales[name][index].exp()

    def _quantize(self, value: torch.Tensor, index: int, name: str) -> torch.Tensor:
        if not self._is_active(index, name):
            return value
        qmin, qmax = BOUNDARIES[name]
        scale = self.scale(name, index)
        result = fake_quantize(value, scale, signed=qmin < 0, bits=(qmax - qmin + 1).bit_length() - 1)
        self.observations[(index, name)] = {
            "before": value.detach(), "after": result.detach()
        }
        return result

    def _update_weight_masks(self) -> None:
        if not self._handles:
            return
        for index, block in enumerate(self.blocks):
            for name, module in (("fc1_weight", block.mlp.fc1), ("fc2_weight", block.mlp.fc2)):
                if not hasattr(module, "set_quant_enabled"):
                    continue
                parent_enabled = self._original_weight_states[(index, name)]
                module.set_quant_enabled(
                    not parent_enabled if self._is_active(index, name) else parent_enabled
                )

    def install(self) -> None:
        if self._handles:
            raise RuntimeError("strict hooks are already installed")
        self._validate_weight_targets(self.operator_blocks)
        try:
            self._install_hooks()
        except BaseException:
            self.remove()
            raise

    def _install_hooks(self) -> None:
        for index, block in enumerate(self.blocks):
            self._handles.append(block.norm1.register_forward_hook(
                lambda _m, _inputs, output, i=index: self._quantize(output, i, "ln1")
            ))

            def qkv_hook(_module, _inputs, output, i=index):
                if output.shape[-1] % 3:
                    raise ValueError("QKV output dimension must divide into Q, K, V")
                q, k, v = output.chunk(3, dim=-1)
                return torch.cat(
                    (self._quantize(q, i, "q"), self._quantize(k, i, "k"), self._quantize(v, i, "v")),
                    dim=-1,
                )

            self._handles.append(block.attn.qkv.register_forward_hook(qkv_hook))
            self._handles.append(block.attn.proj.register_forward_pre_hook(
                lambda _m, inputs, i=index: (self._quantize(inputs[0], i, "a"),)
            ))
            self._handles.append(block.attn.proj.register_forward_hook(
                lambda _m, _inputs, output, i=index: self._quantize(output, i, "o")
            ))
            self._handles.append(block.norm2.register_forward_hook(
                lambda _m, _inputs, output, i=index: self._quantize(output, i, "ln2")
            ))
            for name, module in (("fc1", block.mlp.fc1), ("gelu", block.mlp.act), ("fc2", block.mlp.fc2)):
                self._handles.append(module.register_forward_hook(
                    lambda _m, _inputs, output, i=index, n=name: self._quantize(output, i, n)
                ))
            self._handles.append(block.register_forward_hook(
                lambda _m, _inputs, output, i=index: self._quantize(output, i, "mlp_residual")
            ))
            attention = block.attn
            original = attention.forward
            self._original_attention[index] = original

            def attention_forward(attn, x, attn_mask=None, i=index, original_forward=original):
                if not self._is_active(i, "softmax"):
                    return original_forward(x, attn_mask=attn_mask)
                batch, tokens, channels = x.shape
                qkv = attn.qkv(x).reshape(batch, tokens, 3, attn.num_heads, attn.head_dim)
                q, k, v = qkv.permute(2, 0, 3, 1, 4).unbind(0)
                q, k = attn.q_norm(q), attn.k_norm(k)
                logits = (q * attn.scale) @ k.transpose(-2, -1)
                if attn_mask is not None:
                    if attn_mask.dtype == torch.bool:
                        logits = logits.masked_fill(~attn_mask, float("-inf"))
                    else:
                        logits = logits + attn_mask
                probabilities = self._quantize(logits.softmax(dim=-1), i, "softmax")
                result = attn.attn_drop(probabilities) @ v
                result = result.transpose(1, 2).reshape(batch, tokens, channels)
                result = attn.norm(result)
                return attn.proj_drop(attn.proj(result))

            attention.forward = MethodType(attention_forward, attention)
            original_block_forward = block.forward
            self._original_block[index] = original_block_forward

            def block_forward(module, x, attn_mask=None, i=index, original_forward=original_block_forward):
                if not self._is_active(i, "attention_residual"):
                    return original_forward(x) if attn_mask is None else original_forward(x, attn_mask=attn_mask)
                x = x + module.drop_path1(module.ls1(module.attn(module.norm1(x), attn_mask=attn_mask)))
                x = self._quantize(x, i, "attention_residual")
                return x + module.drop_path2(module.ls2(module.mlp(module.norm2(x))))

            block.forward = MethodType(block_forward, block)
            for name, module in (("fc1_weight", block.mlp.fc1), ("fc2_weight", block.mlp.fc2)):
                if hasattr(module, "quant_enabled"):
                    self._original_weight_states[(index, name)] = module.quant_enabled
        self._update_weight_masks()

    def remove(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()
        for index, original in self._original_attention.items():
            self.blocks[index].attn.forward = original
        self._original_attention.clear()
        for index, original in self._original_block.items():
            self.blocks[index].forward = original
        self._original_block.clear()
        for (index, name), enabled in self._original_weight_states.items():
            module = getattr(self.blocks[index].mlp, name.removesuffix("_weight"))
            module.set_quant_enabled(enabled)
        self._original_weight_states.clear()
        self.observations.clear()

    def statistics(self) -> dict[tuple[int, str], dict[str, float]]:
        return {
            key: tensor_error_statistics(
                pair["before"], pair["after"],
                qmin=BOUNDARIES[key[1]][0], qmax=BOUNDARIES[key[1]][1],
                scale=self.scale(key[1], key[0]).detach(),
            )
            for key, pair in self.observations.items()
        }
