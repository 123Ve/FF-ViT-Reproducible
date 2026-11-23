"""Strict attention LSQ with an inherited all-block strict MLP stage."""
from __future__ import annotations

import math
import os
from pathlib import Path
from types import MethodType

import torch
from torch import nn

from .quant import BOUNDARIES
from .trainer import MLP_OPERATORS, lsq_quantize

ATTENTION_OPERATORS = ('ln1', 'q', 'k', 'v', 'a', 'softmax', 'o', 'attention_residual')


def scale_movements(initial, controller):
    return {name: float((parameter.detach() - initial[name]).abs().max())
            for name, parameter in controller.log_scales.items()}


def publish_candidate(latest, candidate, *, recipe, epoch, global_step):
    source = Path(candidate) if Path(candidate).exists() else Path(latest)
    payload = torch.load(source, map_location='cpu', weights_only=False)
    if payload['recipe'] != recipe or payload['progress'].get('pending_formal') != epoch or payload['progress']['global_step'] != global_step:
        raise ValueError('immutable candidate does not match the pending endpoint')
    if not Path(candidate).exists():
        os.link(latest, candidate)


def attention_masks(order, epoch):
    if sorted(order) != list(range(len(order))) or epoch < 0:
        raise ValueError('invalid progressive attention order/epoch')
    active = list(order[:math.ceil(len(order) * min(epoch + 1, 4) / 4)])
    return {**{name: active for name in ATTENTION_OPERATORS},
            **{name: list(range(len(order))) for name in MLP_OPERATORS}}


class AttentionController(nn.Module):
    def __init__(self, model, scales):
        super().__init__()
        object.__setattr__(self, 'model', model)
        count = len(model.vit.blocks)
        if set(scales) != set(BOUNDARIES):
            raise ValueError('all strict calibrated boundaries are required')
        for values in scales.values():
            if len(values) != count or any(not math.isfinite(x) or x <= 0 for x in values):
                raise ValueError('one finite positive scale per block is required')
        self.log_scales = nn.ParameterDict({name: nn.Parameter(torch.tensor(values, device=next(model.parameters()).device).log()) for name, values in scales.items()})
        self.masks = {name: [] for name in BOUNDARIES}
        self.handles = []
        self.gradient_handles = []
        for index, block in enumerate(model.vit.blocks):
            for name, module in [('ln1', block.norm1), ('o', block.attn.proj),
                                 ('ln2', block.norm2), ('fc1', block.mlp.fc1),
                                 ('gelu', block.mlp.act), ('fc2', block.mlp.fc2),
                                 ('mlp_residual', block)]:
                self.handles.append(module.register_forward_hook(lambda _m, _x, y, i=index, n=name: self.quantize(y, i, n)))
            def qkv_hook(_module, _inputs, output, i=index):
                return torch.cat([self.quantize(x, i, n) for x, n in zip(output.chunk(3, dim=-1), ('q', 'k', 'v'))], dim=-1)
            self.handles.append(block.attn.qkv.register_forward_hook(qkv_hook))
            self.handles.append(block.attn.proj.register_forward_pre_hook(lambda _m, x, i=index: (self.quantize(x[0], i, 'a'),)))
            original = block.attn.forward
            def attention_forward(attn, x, attn_mask=None, i=index, original_forward=original):
                if i not in self.masks['softmax']:
                    return original_forward(x, attn_mask=attn_mask)
                batch, tokens, channels = x.shape
                qkv = attn.qkv(x).reshape(batch, tokens, 3, attn.num_heads, attn.head_dim)
                q, k, v = qkv.permute(2, 0, 3, 1, 4).unbind(0)
                q, k = attn.q_norm(q), attn.k_norm(k)
                logits = (q * attn.scale) @ k.transpose(-2, -1)
                if attn_mask is not None:
                    logits = logits.masked_fill(~attn_mask, float('-inf')) if attn_mask.dtype == torch.bool else logits + attn_mask
                probabilities = self.quantize(logits.float().softmax(-1), i, 'softmax')
                output = attn.attn_drop(probabilities) @ v
                output = output.transpose(1, 2).reshape(batch, tokens, channels)
                return attn.proj_drop(attn.proj(attn.norm(output)))
            block.attn.forward = MethodType(attention_forward, block.attn)
            def block_forward(block, x, attn_mask=None, i=index):
                x = x + block.drop_path1(block.ls1(block.attn(block.norm1(x), attn_mask=attn_mask)))
                x = self.quantize(x, i, 'attention_residual')
                return x + block.drop_path2(block.ls2(block.mlp(block.norm2(x))))
            block.forward = MethodType(block_forward, block)

    def set_masks(self, masks):
        count = len(self.model.vit.blocks)
        if set(masks) != set(BOUNDARIES):
            raise ValueError('all strict attention and MLP boundaries are required')
        normalized = {name: list(indices) for name, indices in masks.items()}
        if any(type(i) is not int or i < 0 or i >= count for indices in normalized.values() for i in indices):
            raise ValueError('invalid active block')
        if any(normalized[name] != normalized['ln1'] for name in ATTENTION_OPERATORS):
            raise ValueError('all attention boundaries must share a mask')
        if any(sorted(normalized[name]) != list(range(count)) for name in MLP_OPERATORS):
            raise ValueError('all MLP blocks must remain strict')
        self.masks = normalized

    def quantize(self, value, index, name):
        return lsq_quantize(value, self.log_scales[name][index], *BOUNDARIES[name]) if index in self.masks[name] else value


def load_mlp_ema(model, controller, payload):
    count = len(model.vit.blocks)
    if payload.get('schema') != 'original_hls_s3.mlp_qat.v1' or any(sorted(payload['progress']['masks'].get(name, [])) != list(range(count)) for name in MLP_OPERATORS):
        raise ValueError('parent must be strict MLP EMA with all blocks enabled')
    model.load_state_dict(payload['ema_model'], strict=True)
    if set(payload['ema_controller']) != {f'log_scales.{name}' for name in MLP_OPERATORS}:
        raise ValueError('incompatible strict MLP controller')
    with torch.no_grad():
        for name in MLP_OPERATORS:
            controller.log_scales[name].copy_(payload['ema_controller'][f'log_scales.{name}'])


def stage_parameter_groups(model, controller, *, active, joint, lr, scale_lr):
    model.requires_grad_(joint)
    controller.requires_grad_(joint)
    for handle in controller.gradient_handles:
        handle.remove()
    controller.gradient_handles.clear()
    if not joint:
        for index in active:
            model.vit.blocks[index].attn.requires_grad_(True)
            model.vit.blocks[index].norm1.requires_grad_(True)
        for name in ATTENTION_OPERATORS:
            parameter = controller.log_scales[name]
            parameter.requires_grad_(True)
            mask = torch.zeros_like(parameter)
            mask[active] = 1
            controller.gradient_handles.append(parameter.register_hook(lambda gradient, mask=mask: gradient * mask))
    # Stable groups retain Adam state across progressive unfreezing and resume.
    return [{'params': list(model.parameters()), 'lr': lr, 'initial_lr': lr, 'weight_decay': .01},
            {'params': list(controller.parameters()), 'lr': scale_lr, 'initial_lr': scale_lr, 'weight_decay': 0.}]
