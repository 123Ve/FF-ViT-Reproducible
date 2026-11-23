import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import torch
from torch import nn

from src import losses, trainer
from src.contract import load_contract


def test_kd_and_feature_losses_detach_teacher_and_retain_student_gradient():
    student = torch.tensor([[2., -1.]], requires_grad=True)
    teacher = torch.tensor([[-1., 2.]], requires_grad=True)
    loss = losses.logit_kd(student, teacher, temperature=2.)
    assert loss.item() > 0
    assert losses.logit_kd(student, student.detach(), temperature=2.).item() == pytest.approx(0., abs=1e-6)
    feature = losses.feature_reconstruction({'block': student}, {'block': teacher})
    assert feature.item() == pytest.approx(3.6)
    (loss + feature).backward()
    assert student.grad.abs().sum() > 0
    assert teacher.grad is None


def test_freeze_and_parameter_groups_are_disjoint_and_trainable():
    model = nn.Linear(2, 2)
    teacher = copy.deepcopy(model)
    trainer.freeze_teacher(teacher)
    assert not teacher.training and not any(p.requires_grad for p in teacher.parameters())
    controller = nn.Linear(2, 1)
    groups = trainer.parameter_groups(model, controller, lr=1e-4, scale_lr=1e-3)
    ids = [id(p) for g in groups for p in g['params']]
    assert len(ids) == len(set(ids)) == 4
    assert groups[1]['lr'] == 1e-3


def test_progressive_masks_preserve_all_five_boundaries_and_sensitivity_order():
    order = [11, 10, 9, 8, 7, 4, 5, 3, 1, 6, 2, 0]
    assert trainer.progressive_masks(order, 0) == {k: [11, 10, 9] for k in ('ln2', 'gelu', 'fc1', 'fc2', 'mlp_residual')}
    assert all(len(v) == 12 for v in trainer.progressive_masks(order, 3).values())
    assert trainer.progressive_masks(order, 10) == trainer.progressive_masks(order, 3)
    with pytest.raises(ValueError):
        trainer.progressive_masks([0, 0], 0)


def test_lsq_matches_codes_and_scales_its_gradient():
    x = torch.tensor([-5., -.2, 1.4, 5.], requires_grad=True)
    log_scale = torch.tensor(0., requires_grad=True)
    y = trainer.lsq_quantize(x, log_scale, -4, 3)
    assert y.tolist() == [-4., 0., 1., 3.]
    y.sum().backward()
    assert x.grad.tolist() == [0., 1., 1., 0.]
    assert log_scale.grad.item() == pytest.approx(-1.2 / (12 ** .5))


def test_atomic_checkpoint_restores_optimizer_ema_rng_and_rejects_recipe_drift(tmp_path):
    model = nn.Linear(2, 2)
    controller = nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(trainer.parameter_groups(model, controller, lr=.01, scale_lr=.02))
    ema = trainer.EMA(model, controller, decay=.9)
    (model(torch.ones(1, 2)).sum() + controller(torch.ones(1, 2)).sum()).backward()
    optimizer.step()
    ema.update(model, controller)
    recipe = {'identity': {'parent': 'abc'}, 'seed': 20260923}
    path = tmp_path / 'latest.pth'
    state = {'epoch': 2, 'next_batch': 8, 'global_step': 12, 'best_selection': .4}
    trainer.save_checkpoint(path, model, controller, optimizer, ema, recipe=recipe, progress=state)
    expected = torch.rand(2)
    with torch.no_grad():
        model.weight.zero_()
    restored = trainer.restore_checkpoint(path, model, controller, optimizer, ema, recipe=recipe)
    assert restored == state
    assert torch.equal(torch.rand(2), expected)
    assert model.weight.abs().sum() > 0 and len(optimizer.state) == 4
    assert not list(tmp_path.glob('*.tmp'))
    with pytest.raises(ValueError, match='recipe'):
        trainer.restore_checkpoint(path, model, controller, optimizer, ema, recipe={'seed': 0})


def test_runtime_strict_contract_rejects_widening_and_w3_disable():
    config = load_contract(Path(__file__).parents[1] / 'config/original_hls_s3.yaml')
    model = nn.Linear(2, 2)
    model.quant_enabled = True
    trainer.validate_training_contract(config, model)
    model.quant_enabled = False
    with pytest.raises(ValueError, match='W3'):
        trainer.validate_training_contract(config, model)
    model.quant_enabled = True
    config['numeric_contract']['gelu_output']['bits'] = 8
    with pytest.raises(ValueError):
        trainer.validate_training_contract(config, model)


def test_scheduler_warms_up_then_decays():
    assert trainer.lr_factor(0, total=100, warmup=10) == pytest.approx(.1)
    assert trainer.lr_factor(9, total=100, warmup=10) == 1.
    assert trainer.lr_factor(99, total=100, warmup=10) < .011


def test_mlp_controller_applies_all_boundaries_with_fp32_code_precision():
    from test_quant import TinyModel
    model = TinyModel()
    controller = trainer.MLPController(model, {k: [1., 1.] for k in trainer.MLP_OPERATORS})
    controller.set_masks(trainer.progressive_masks([0, 1], 3))
    value = torch.tensor([1023., 1024., -1025.], dtype=torch.float32)
    assert controller.quantize(value, 0, 'fc1').tolist() == [1023., 1023., -1024.]
    assert controller.quantize(torch.tensor([-.2, 8.]), 0, 'gelu').tolist() == [0., 7.]
    with pytest.raises(ValueError):
        controller.set_masks({'ln2': [0]})
    bad = trainer.progressive_masks([0, 1], 3)
    bad['gelu'] = [3]
    with pytest.raises(ValueError):
        controller.set_masks(bad)


def test_epoch_sampler_resumes_exact_remaining_samples_without_duplicates():
    full = list(trainer.epoch_indices(19, seed=4, epoch=2, offset=0))
    tail = list(trainer.epoch_indices(19, seed=4, epoch=2, offset=7))
    assert len(set(full)) == 19 and sorted(full) == list(range(19))
    assert tail == full[7:]
    assert full != list(trainer.epoch_indices(19, seed=4, epoch=3, offset=0))


def test_training_role_isolation_excludes_paths_and_content_aliases(tmp_path):
    from src.provenance import sha256_file
    holdout, retained, alias = [tmp_path / name for name in ('holdout.jpg', 'train.jpg', 'alias.jpg')]
    holdout.write_bytes(b'held-out image')
    retained.write_bytes(b'other training')
    alias.write_bytes(b'held-out image')
    records = [{'path': str(holdout), 'sha256': sha256_file(holdout), 'size_bytes': holdout.stat().st_size}]
    samples, audit = trainer.isolate_training_samples([(str(holdout), 0), (str(retained), 1)], records)
    assert samples == [(str(retained), 1)]
    assert audit['path_overlap'] == audit['content_hash_overlap'] == 0
    assert audit['excluded_count'] == 1
    samples, audit = trainer.isolate_training_samples([(str(holdout), 0), (str(alias), 1), (str(retained), 1)], records)
    assert samples == [(str(retained), 1)]
    assert audit['alias_count'] == 1
    assert audit['content_aliases'] == [{'path': str(alias), 'sha256': sha256_file(alias)}]


def test_formal_selection_uses_top1_then_top5_even_when_selection_is_lower():
    assert trainer.formal_is_better({'top1': .69, 'top5': .88}, {'top1': .68, 'top5': .90})
    assert trainer.formal_is_better({'top1': .69, 'top5': .91}, {'top1': .69, 'top5': .90})
    assert not trainer.formal_is_better({'top1': .689, 'top5': .99}, {'top1': .69, 'top5': .90})
    assert not trainer.formal_is_better({'top1': .69, 'top5': .90}, {'top1': .69, 'top5': .90})


def test_policy_migration_permits_only_selection_policy_and_implementation_hashes():
    old = {'settings': {'learning_rate': .001}, 'identity': {'parent_sha256': 'parent', 'trainer_source_sha256': 'old', 'runner_source_sha256': 'old'}, 'train_count': 19}
    new = copy.deepcopy(old)
    new['selection_policy'] = 'every_all12_epoch_formal_top1_then_top5'
    new['identity']['runner_source_sha256'] = 'new'
    new['identity']['trainer_source_sha256'] = 'new'
    trainer.validate_policy_migration(old, new)
    bad = copy.deepcopy(new)
    bad['settings']['learning_rate'] = .1
    with pytest.raises(ValueError, match='migration'):
        trainer.validate_policy_migration(old, bad)
    bad = copy.deepcopy(new)
    bad['identity']['parent_sha256'] = 'different'
    with pytest.raises(ValueError, match='migration'):
        trainer.validate_policy_migration(old, bad)


@pytest.mark.parametrize('status', ['target_reached', 'budget_exhausted'])
def test_completed_cli_resume_exits_zero_without_changing_artifacts(tmp_path, status):
    root = Path(__file__).parents[1]
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'config').mkdir()
    (tmp_path / 'reports').mkdir()
    shutil.copyfile(root / 'scripts/train_strict_mlp.py', tmp_path / 'scripts/train_strict_mlp.py')
    for name in ('original_hls_s3.yaml', 'mlp_qat.json'):
        shutil.copyfile(root / 'config' / name, tmp_path / 'config' / name)
    model, controller = nn.Linear(2, 2), nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(trainer.parameter_groups(model, controller, lr=.01, scale_lr=.01))
    ema = trainer.EMA(model, controller)
    config = load_contract(tmp_path / 'config/original_hls_s3.yaml')
    recipe = {'numeric_contract': config['numeric_contract'], 'identity': {'runner_source_sha256': 'historical_training_source'}}
    checkpoint = tmp_path / 'checkpoints/mlp/main/latest.pth'
    trainer.save_checkpoint(checkpoint, model, controller, optimizer, ema, recipe=recipe,
                            progress={'epoch': 11, 'global_step': 54879, 'status': status})
    (checkpoint.parent / 'recipe.json').write_text(json.dumps(recipe))
    (tmp_path / 'reports/mlp_qat_training.json').write_text(json.dumps({'status': status, 'history': [10]}))
    before = {p.relative_to(tmp_path): (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    environment = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, str(tmp_path / 'scripts/train_strict_mlp.py'), '--resume'],
                            capture_output=True, text=True, env=environment, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == status
    after = {p.relative_to(tmp_path): (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    assert after == before
