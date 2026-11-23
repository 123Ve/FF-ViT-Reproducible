"""Strict-width QAT, distillation hooks and atomic deterministic continuation."""
from __future__ import annotations

import math
import copy
import os
from pathlib import Path
import random
import tempfile

import numpy as np
import torch
from torch import nn

from .contract import validate_mainline_contract
from .quant import BOUNDARIES
from .provenance import sha256_file

MLP_OPERATORS = ('ln2', 'gelu', 'fc1', 'fc2', 'mlp_residual')


def formal_is_better(candidate, incumbent):
    return incumbent is None or (candidate['top1'], candidate['top5']) > (incumbent['top1'], incumbent['top5'])


def validate_policy_migration(old, new):
    """An explicit controller-approved selection-policy migration, never a recipe reset."""
    before, after = copy.deepcopy(old), copy.deepcopy(new)
    if before.get('selection_policy') is not None or after.pop('selection_policy', None) != 'every_all12_epoch_formal_top1_then_top5':
        raise ValueError('unsupported checkpoint policy migration')
    for recipe in (before, after):
        for key in ('runner_source_sha256', 'trainer_source_sha256'):
            recipe['identity'].pop(key, None)
    if before != after:
        raise ValueError('policy migration cannot change training inputs or hyperparameters')


def epoch_indices(count, *, seed, epoch, offset=0):
    if not 0 <= offset <= count:
        raise ValueError('invalid sample resume offset')
    return torch.randperm(count, generator=torch.Generator().manual_seed(seed + epoch)).tolist()[offset:]


def isolate_training_samples(samples, holdout_records):
    """Exclude reserved paths and prove no retained file duplicates held-out bytes.

    Unequal byte lengths prove unequal contents, so only size-matching files
    require hashing. This does not sample the overlap check.
    """
    reserved = {str(Path(row['path']).resolve()) for row in holdout_records}
    if len(reserved) != len(holdout_records):
        raise ValueError('reserved calibration/selection roles overlap')
    sizes = {row['size_bytes'] for row in holdout_records}
    hashes = {row['sha256'] for row in holdout_records}
    for row in holdout_records:
        if sha256_file(row['path']) != row['sha256'] or Path(row['path']).stat().st_size != row['size_bytes']:
            raise ValueError('reserved role content changed')
    remaining = []
    aliases = []
    excluded = set()
    hashed = 0
    for path, label in samples:
        canonical = str(Path(path).resolve())
        if canonical in reserved:
            excluded.add(canonical)
            continue
        if Path(path).stat().st_size in sizes:
            hashed += 1
            digest = sha256_file(path)
            if digest in hashes:
                aliases.append({'path': canonical, 'sha256': digest})
                continue
        remaining.append((path, label))
    if excluded != reserved:
        raise ValueError('reserved samples are missing from original training set')
    return remaining, {'excluded_count': len(excluded), 'alias_count': len(aliases),
                       'content_aliases': aliases, 'optimizer_count': len(remaining),
                       'path_overlap': 0, 'content_hash_overlap': 0,
                       'retained_files_hashed': hashed, 'method': 'all paths; SHA256 for every matching byte length'}


def freeze_teacher(teacher):
    teacher.requires_grad_(False).eval()


def parameter_groups(model, controller, *, lr, scale_lr):
    model.requires_grad_(True)
    controller.requires_grad_(True)
    return [{'params': list(model.parameters()), 'lr': lr, 'initial_lr': lr, 'weight_decay': .01},
            {'params': list(controller.parameters()), 'lr': scale_lr, 'initial_lr': scale_lr, 'weight_decay': 0.}]


def progressive_masks(order, epoch):
    if sorted(order) != list(range(len(order))) or epoch < 0:
        raise ValueError('invalid progressive block order/epoch')
    active = list(order[:math.ceil(len(order) * min(epoch + 1, 4) / 4)])
    return {name: active for name in MLP_OPERATORS}


def lsq_quantize(value, log_scale, qmin, qmax):
    # FP32 here is essential: BF16 cannot represent every s11/s13 code.
    value = value.float()
    scale = log_scale.float().exp()
    factor = 1. / math.sqrt(value.numel() * qmax)
    scale = scale.detach() + (scale - scale.detach()) * factor
    normalized = (value / scale).clamp(qmin, qmax)
    rounded = normalized + (normalized.round() - normalized).detach()
    return rounded * scale


class MLPController(nn.Module):
    def __init__(self, model, scales):
        super().__init__()
        object.__setattr__(self, 'model', model)
        self.log_scales = nn.ParameterDict({name: nn.Parameter(torch.tensor(scales[name], device=next(model.parameters()).device).log()) for name in MLP_OPERATORS})
        self.masks = {name: [] for name in MLP_OPERATORS}
        self.handles = []
        for index, block in enumerate(model.vit.blocks):
            for name, module in [('ln2', block.norm2), ('gelu', block.mlp.act), ('fc1', block.mlp.fc1), ('fc2', block.mlp.fc2), ('mlp_residual', block)]:
                self.handles.append(module.register_forward_hook(lambda _m, _x, y, i=index, n=name: self.quantize(y, i, n)))

    def set_masks(self, masks):
        if set(masks) != set(MLP_OPERATORS):
            raise ValueError('all strict MLP boundaries are required')
        normalized = {name: list(indices) for name, indices in masks.items()}
        if any(v != normalized['ln2'] for v in normalized.values()):
            raise ValueError('MLP boundaries must share the progressive mask')
        self.masks = normalized

    def quantize(self, value, index, name):
        if index not in self.masks[name]:
            return value
        return lsq_quantize(value, self.log_scales[name][index], *BOUNDARIES[name])


class FeatureCapture:
    def __init__(self, model):
        self.values = {}
        self.handles = []
        for index, block in enumerate(model.vit.blocks):
            for name, module in [('block', block), ('attention', block.attn), ('mlp', block.mlp)]:
                self.handles.append(module.register_forward_hook(lambda _m, _x, y, key=f'{index}:{name}': self.values.__setitem__(key, y)))

    def clear(self):
        self.values.clear()


def validate_training_contract(config, model):
    validate_mainline_contract(config)
    for module in model.modules():
        if hasattr(module, 'quant_enabled') and not module.quant_enabled:
            raise ValueError('W3 quantization must remain enabled')


def lr_factor(step, *, total, warmup):
    if step < warmup:
        return (step + 1) / warmup
    fraction = min(1., (step - warmup) / max(1, total - warmup - 1))
    return .01 + .99 * .5 * (1. + math.cos(math.pi * fraction))


class EMA:
    def __init__(self, model, controller, *, decay=.999):
        self.decay = decay
        self.model = {k: v.detach().clone() for k, v in model.state_dict().items()}
        self.controller = {k: v.detach().clone() for k, v in controller.state_dict().items()}
        self.updates = 0

    @torch.no_grad()
    def update(self, model, controller):
        self.updates += 1
        decay = min(self.decay, (1 + self.updates) / (10 + self.updates))
        for shadow, live in [(self.model, model.state_dict()), (self.controller, controller.state_dict())]:
            for key, value in live.items():
                if value.is_floating_point():
                    shadow[key].lerp_(value, 1 - decay)
                else:
                    shadow[key].copy_(value)


def save_checkpoint(path, model, controller, optimizer, ema, *, recipe, progress, history=None):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {'schema': recipe.get('checkpoint_schema', 'original_hls_s3.mlp_qat.v1'), 'recipe': recipe, 'progress': progress,
               'model': model.state_dict(), 'controller': controller.state_dict(),
               'optimizer': optimizer.state_dict(), 'ema_model': ema.model,
               'ema_controller': ema.controller, 'ema_updates': ema.updates,
               'rng_torch': torch.get_rng_state(), 'rng_cuda': torch.cuda.get_rng_state_all(),
               'rng_python': random.getstate(), 'rng_numpy': np.random.get_state()}
    if history is not None:
        payload['history'] = history
    fd, temporary = tempfile.mkstemp(prefix=f'.{destination.name}.', suffix='.tmp', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            torch.save(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restore_checkpoint(path, model, controller, optimizer, ema, *, recipe):
    payload = torch.load(path, map_location='cpu', weights_only=False)
    if payload['recipe'] != recipe or payload['schema'] != recipe.get('checkpoint_schema', 'original_hls_s3.mlp_qat.v1'):
        raise ValueError('checkpoint recipe differs from current training inputs')
    model.load_state_dict(payload['model'], strict=True)
    controller.load_state_dict(payload['controller'], strict=True)
    optimizer.load_state_dict(payload['optimizer'])
    device = next(model.parameters()).device
    ema.model = {k: v.to(device) for k, v in payload['ema_model'].items()}
    ema.controller = {k: v.to(device) for k, v in payload['ema_controller'].items()}
    ema.updates = payload['ema_updates']
    torch.set_rng_state(payload['rng_torch'])
    if payload['rng_cuda']:
        torch.cuda.set_rng_state_all(payload['rng_cuda'])
    random.setstate(payload['rng_python'])
    np.random.set_state(payload['rng_numpy'])
    return payload['progress']
