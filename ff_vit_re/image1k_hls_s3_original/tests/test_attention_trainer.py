import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import torch
from torch import nn
from timm.models.vision_transformer import Block

from src import trainer
from src.quant import BOUNDARIES


def attention_api():
    assert importlib.util.find_spec('src.attention_trainer') is not None, 'strict attention trainer is missing'
    from src import attention_trainer
    return attention_trainer


def fixture():
    api = attention_api()
    model = nn.Module()
    model.vit = nn.Module()
    model.vit.blocks = nn.Sequential(*(Block(12, 3, mlp_ratio=2.) for _ in range(4)))
    scales = {name: [1.] * 4 for name in BOUNDARIES}
    control = api.AttentionController(model, scales)
    return api, model, control


def test_all_attention_domains_keep_fp32_codes_and_lsq_gradients():
    api, model, control = fixture()
    control.set_masks(api.attention_masks([3, 2, 1, 0], 3))
    expected = {'ln1': (-4, 3), 'q': (-4, 3), 'k': (-4, 3), 'v': (-4, 3),
                'a': (-4, 3), 'softmax': (0, 7), 'o': (-4096, 4095),
                'attention_residual': (-16384, 16383), 'ln2': (-4, 3),
                'gelu': (0, 7), 'fc1': (-1024, 1023), 'fc2': (-4096, 4095),
                'mlp_residual': (-4096, 4095)}
    for name, (low, high) in expected.items():
        x = torch.tensor([float(low - 1), .4, float(high + 1)], requires_grad=True)
        y = control.quantize(x, 0, name)
        assert y.tolist() == [low, 0., high]
        y.sum().backward()
        assert x.grad.tolist() == [0., 1., 0.]
        assert control.log_scales[name].grad is not None


def test_progressive_masks_keep_mlp_all12_and_reject_partial_or_invalid_attention():
    api, model, control = fixture()
    masks = api.attention_masks([3, 2, 1, 0], 0)
    assert masks['q'] == [3]
    assert masks['ln2'] == [0, 1, 2, 3]
    control.set_masks(masks)
    for changed in ({**masks, 'q': [2]}, {**masks, 'ln2': [3]}, {**masks, 'q': [4]}):
        with pytest.raises(ValueError):
            control.set_masks(changed)


def test_attention_residual_quantization_propagates_to_the_mlp_skip_path():
    api, model, control = fixture()
    control.set_masks(api.attention_masks([3, 2, 1, 0], 3))
    for parameter in model.parameters():
        parameter.data.zero_()
    # If residual is only quantized before norm2, the unquantized skip leaks .4.
    control.log_scales['mlp_residual'].data.fill_(torch.tensor(.1).log())
    output = model.vit.blocks[0](torch.full((1, 2, 12), .4))
    assert torch.equal(output, torch.zeros_like(output))


def test_real_block_forward_visits_every_enabled_boundary_and_softmax_is_u3():
    api, model, control = fixture()
    control.set_masks(api.attention_masks([3, 2, 1, 0], 0))
    control.log_scales['softmax'].data.fill_(torch.tensor(1 / 7).log())
    observed = {}
    quantize = control.quantize
    def record(value, index, name):
        result = quantize(value, index, name)
        if index in control.masks[name]:
            observed[index, name] = result.detach()
        return result
    control.quantize = record
    output = model.vit.blocks(torch.randn(2, 5, 12))
    assert output.shape == (2, 5, 12) and torch.isfinite(output).all()
    assert set(name for index, name in observed if index == 3) == {
        'ln1', 'q', 'k', 'v', 'a', 'softmax', 'o', 'attention_residual',
        'ln2', 'fc1', 'gelu', 'fc2', 'mlp_residual'}
    assert set(name for index, name in observed if index == 0) == {'ln2', 'fc1', 'gelu', 'fc2', 'mlp_residual'}
    codes = observed[3, 'softmax'] * 7
    assert codes.min() >= 0 and codes.max() <= 7
    assert torch.allclose(codes, codes.round(), atol=1e-6)


def test_attention_freeze_and_joint_unfreeze_update_only_allowed_parameters():
    api, model, control = fixture()
    control.set_masks(api.attention_masks([3, 2, 1, 0], 0))
    groups = api.stage_parameter_groups(model, control, active=[3], joint=False, lr=.01, scale_lr=.02)
    names = {name for name, p in model.named_parameters() if p.requires_grad}
    assert names and all(name.startswith(('vit.blocks.3.attn.', 'vit.blocks.3.norm1.')) for name in names)
    before = {name: p.detach().clone() for name, p in control.named_parameters()}
    optimizer = torch.optim.AdamW(groups)
    sum(p.sum() for p in control.parameters() if p.requires_grad).backward()
    optimizer.step()
    assert torch.equal(before['log_scales.ln2'], control.log_scales['ln2'])
    assert torch.equal(before['log_scales.q'][:3], control.log_scales['q'][:3])
    assert not torch.equal(before['log_scales.q'][3:], control.log_scales['q'][3:])
    api.stage_parameter_groups(model, control, active=list(range(4)), joint=True, lr=.01, scale_lr=.02)
    assert all(p.requires_grad for p in model.parameters())
    assert all(p.requires_grad for p in control.parameters())


def test_strict_mlp_parent_loads_ema_and_rejects_incomplete_masks():
    api, model, control = fixture()
    masks = {name: list(range(4)) for name in trainer.MLP_OPERATORS}
    parent = {'schema': 'original_hls_s3.mlp_qat.v1', 'ema_model': copy.deepcopy(model.state_dict()),
              'ema_controller': {f'log_scales.{name}': torch.ones(4) for name in trainer.MLP_OPERATORS},
              'progress': {'masks': masks}}
    parent['ema_model']['vit.blocks.0.norm1.weight'].fill_(2.)
    api.load_mlp_ema(model, control, parent)
    assert model.vit.blocks[0].norm1.weight.tolist() == [2.] * 12
    assert control.log_scales['ln2'].tolist() == [1.] * 4
    parent['progress']['masks']['gelu'] = [0]
    with pytest.raises(ValueError, match='all'):
        api.load_mlp_ema(model, control, parent)


def test_attention_resume_preserves_optimizer_freeze_ema_and_rejects_provenance(tmp_path):
    api, model, control = fixture()
    control.set_masks(api.attention_masks([3, 2, 1, 0], 0))
    optimizer = torch.optim.AdamW(api.stage_parameter_groups(model, control, active=[3], joint=False, lr=.01, scale_lr=.02))
    ema = trainer.EMA(model, control)
    recipe = {'checkpoint_schema': 'original_hls_s3.attention_qat.v1', 'parent_sha256': 'abc'}
    progress = {'epoch': 0, 'sample_offset': 3, 'masks': control.masks}
    trainer.save_checkpoint(tmp_path / 'latest.pth', model, control, optimizer, ema, recipe=recipe, progress=progress)
    payload = torch.load(tmp_path / 'latest.pth', weights_only=False)
    assert payload['schema'] == 'original_hls_s3.attention_qat.v1'
    assert trainer.restore_checkpoint(tmp_path / 'latest.pth', model, control, optimizer, ema, recipe=recipe) == progress
    with pytest.raises(ValueError, match='recipe'):
        trainer.restore_checkpoint(tmp_path / 'latest.pth', model, control, optimizer, ema, recipe={**recipe, 'parent_sha256': 'other'})


def test_checkpoint_keeps_epoch_history_with_pending_formal_candidate(tmp_path):
    api, model, control = fixture()
    optimizer = torch.optim.AdamW(api.stage_parameter_groups(model, control, active=[], joint=True, lr=.01, scale_lr=.01))
    history = {'epochs': [{'epoch': 3, 'training_count': 1277128}], 'formal_candidates': []}
    progress = {'epoch': 4, 'pending_formal': 3}
    trainer.save_checkpoint(tmp_path / 'latest.pth', model, control, optimizer, trainer.EMA(model, control),
                            recipe={}, progress=progress, history=history)
    payload = torch.load(tmp_path / 'latest.pth', weights_only=False)
    assert payload['history'] == history and payload['progress']['pending_formal'] == 3


def test_immutable_candidate_reuses_only_matching_pending_endpoint(tmp_path):
    api = attention_api()
    assert hasattr(api, 'publish_candidate'), 'immutable endpoint publishing is missing'
    recipe = {'parent': 'accepted'}
    latest, candidate = tmp_path / 'latest.pth', tmp_path / 'candidate.pth'
    torch.save({'recipe': recipe, 'progress': {'pending_formal': 3, 'global_step': 12}}, latest)
    api.publish_candidate(latest, candidate, recipe=recipe, epoch=3, global_step=12)
    before = (candidate.read_bytes(), candidate.stat().st_mtime_ns)
    api.publish_candidate(latest, candidate, recipe=recipe, epoch=3, global_step=12)
    assert before == (candidate.read_bytes(), candidate.stat().st_mtime_ns)
    with pytest.raises(ValueError, match='candidate'):
        api.publish_candidate(latest, candidate, recipe=recipe, epoch=4, global_step=20)


def test_probe_scale_movement_matches_named_initial_and_final_boundaries():
    api, model, control = fixture()
    assert hasattr(api, 'scale_movements'), 'named probe movement measurement is missing'
    initial = {name: p.detach().clone() for name, p in control.log_scales.items()}
    control.log_scales['ln2'].data.add_(3.)
    control.log_scales['ln1'].data.add_(.25)
    movement = api.scale_movements(initial, control)
    assert movement['ln1'] == .25 and movement['ln2'] == 3. and movement['q'] == 0.


@pytest.mark.parametrize('status', ['target_reached', 'budget_exhausted'])
def test_completed_attention_cli_resume_is_immutable_before_cuda_or_data(tmp_path, status):
    root = Path(__file__).parents[1]
    assert (root / 'scripts/train_strict_attention.py').exists(), 'attention runner is missing'
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'config').mkdir()
    for name in ('train_strict_attention.py', 'train_strict_joint.py'):
        shutil.copyfile(root / 'scripts' / name, tmp_path / 'scripts' / name)
    for name in ('original_hls_s3.yaml', 'attention_qat.json'):
        shutil.copyfile(root / 'config' / name, tmp_path / 'config' / name)
    from src.contract import load_contract
    recipe = {'checkpoint_schema': 'original_hls_s3.attention_qat.v1',
              'numeric_contract': load_contract(root / 'config/original_hls_s3.yaml')['numeric_contract']}
    model, control = nn.Linear(2, 2), nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(trainer.parameter_groups(model, control, lr=.01, scale_lr=.01))
    checkpoint = tmp_path / 'checkpoints/attention/main/latest.pth'
    trainer.save_checkpoint(checkpoint, model, control, optimizer, trainer.EMA(model, control), recipe=recipe,
                            progress={'epoch': 20, 'global_step': 100, 'status': status})
    before = {p.relative_to(tmp_path): (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    result = subprocess.run([sys.executable, str(tmp_path / 'scripts/train_strict_joint.py'), '--resume'],
                            capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE='1'), timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == status
    after = {p.relative_to(tmp_path): (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    assert before == after
