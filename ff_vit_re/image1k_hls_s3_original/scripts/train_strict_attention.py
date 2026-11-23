#!/usr/bin/env python3
"""Run the strict attention and joint training budget, with deterministic atomic continuation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from torch.utils.data import DataLoader
import torch.nn.functional as F

from src.contract import load_contract, validate_mainline_contract
from src.data import FullTrainImages, make_crop09_transform, load_class_mapping, make_selection_loader, make_validation_loader
from src.model import load_w3_parent, load_hls196_fp32
from src.losses import logit_kd, feature_reconstruction
from src.provenance import atomic_write_json, sha256_file
from src.trainer import (EMA, FeatureCapture, MLPController, epoch_indices, freeze_teacher, isolate_training_samples,
                         lr_factor, parameter_groups, progressive_masks, restore_checkpoint,
                         save_checkpoint, validate_training_contract, formal_is_better, validate_policy_migration)
from scripts.run_sensitivity import dataset_digest
from src.attention_trainer import AttentionController, attention_masks, load_mlp_ema, stage_parameter_groups, publish_candidate, scale_movements


@torch.inference_mode()
def evaluate(model, loader, *, expected_count):
    model.eval()
    seen = set()
    correct1 = correct5 = 0
    started = time.time()
    for images, labels, ids in loader:
        ids = list(ids)
        if len(set(ids)) != len(ids) or seen.intersection(ids):
            raise ValueError('evaluation sample identity duplicated')
        seen.update(ids)
        logits = model(images.cuda(non_blocking=True)).float()
        if not torch.isfinite(logits).all():
            raise ValueError('nonfinite evaluation logits')
        labels = labels.cuda(non_blocking=True)
        predicted = logits.topk(5, dim=-1).indices
        correct1 += int((predicted[:, 0] == labels).sum())
        correct5 += int((predicted == labels[:, None]).any(dim=1).sum())
    if len(seen) != expected_count:
        raise ValueError(f'wrong evaluation count {len(seen)} vs {expected_count}')
    return {'top1': correct1 / len(seen), 'top5': correct5 / len(seen), 'sample_count': len(seen),
            'sample_ids_sha256': hashlib.sha256('\n'.join(sorted(map(str, seen))).encode()).hexdigest(),
            'elapsed_seconds': time.time() - started, 'precision': 'fp32',
            'device': torch.cuda.get_device_name(0), 'protocol': 'crop09'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--probe-steps', type=int, default=0)
    parser.add_argument('--probe-joint', action='store_true')
    parser.add_argument('--probe-profile', choices=('main', 'conservative'), default='main')
    args = parser.parse_args()
    settings_path = ROOT / 'config/attention_qat.json'
    settings = json.loads(settings_path.read_text())
    if args.probe_steps and args.probe_profile == 'conservative':
        settings.update(settings['probe_grid']['conservative'])
    config_path = ROOT / 'config/original_hls_s3.yaml'
    config = load_contract(config_path)
    validate_mainline_contract(config)
    if args.resume and not args.probe_steps:
        # A completed run is immutable, even after non-training safety fixes.
        # Keep its historical source identity; do not initialize an optimizer.
        completed = torch.load(ROOT / 'checkpoints/attention/main/latest.pth', map_location='cpu', weights_only=False)
        if completed.get('schema') != 'original_hls_s3.attention_qat.v1':
            raise ValueError('incompatible checkpoint schema')
        status = completed['progress'].get('status')
        if status in ('target_reached', 'budget_exhausted'):
            validate_mainline_contract({'numeric_contract': completed['recipe']['numeric_contract']})
            print(json.dumps({'status': status, 'action': 'already_complete',
                              'global_step': completed['progress']['global_step']}), flush=True)
            return
        del completed
    seed = settings['seed']
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(8)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    scales_path = ROOT / 'metadata/activation_scales.json'
    scales = json.loads(scales_path.read_text())
    ranking_path = ROOT / 'metadata/sensitivity_ranking.json'
    ranking = json.loads(ranking_path.read_text())
    order = ranking['low_sensitivity_order']
    mapping_path = Path('/home/user/Desktop/ff_vit_re/image_lianghu/metadata/class_mapping.json')
    mapping = load_class_mapping(mapping_path)
    model, _ = load_w3_parent(config['model']['w3_qat_checkpoint'], contract=config_path, device='cuda')
    validate_training_contract(config, model)
    teacher = load_hls196_fp32(config['model']['hls196_fp32_checkpoint'], device='cuda')
    freeze_teacher(teacher)
    controller = AttentionController(model, scales)
    parent_path = ROOT / 'checkpoints/mlp/main/best.pth'
    parent = torch.load(parent_path, map_location='cpu', weights_only=False)
    load_mlp_ema(model, controller, parent)
    student_features, teacher_features = FeatureCapture(model), FeatureCapture(teacher)
    dataset = FullTrainImages(config['data']['train']['path'], mapping, make_crop09_transform())
    if len(dataset) != 1_281_167:
        raise ValueError('full training membership is required')
    reserved = []
    for role in ('calibration', 'selection'):
        reserved.extend(json.loads(line) for line in (ROOT / f'metadata/{role}_manifest.jsonl').read_text().splitlines() if line.strip())
    dataset.dataset.samples, isolation = isolate_training_samples(dataset.dataset.samples, reserved)
    dataset.dataset.imgs = dataset.dataset.samples
    dataset.dataset.targets = [label for _, label in dataset.dataset.samples]
    if len(dataset) != 1_277_167 - isolation['alias_count'] or isolation['excluded_count'] != 4000:
        raise ValueError('expected complete optimizer corpus after frozen-role and alias isolation')
    train_digest = hashlib.sha256()
    for path, label in dataset.dataset.samples:
        train_digest.update(f'{Path(path).relative_to(dataset.root).as_posix()}\t{label}\n'.encode())
    identity = {name: sha256_file(path) for name, path in {
        'contract_sha256': config_path, 'training_config_sha256': settings_path,
        'parent_sha256': parent_path, 'w3_ancestor_sha256': config['model']['w3_qat_checkpoint'], 'teacher_sha256': config['model']['hls196_fp32_checkpoint'],
        'scales_sha256': scales_path, 'ranking_sha256': ranking_path,
        'selection_sha256': ROOT / 'metadata/selection_manifest.jsonl',
        'calibration_sha256': ROOT / 'metadata/calibration_manifest.jsonl',
        'class_mapping_sha256': mapping_path,
        'trainer_source_sha256': ROOT / 'src/trainer.py',
        'loss_source_sha256': ROOT / 'src/losses.py',
        'runner_source_sha256': Path(__file__),
        'attention_source_sha256': ROOT / 'src/attention_trainer.py',
        'model_source_sha256': ROOT / 'src/model.py',
        'data_source_sha256': ROOT / 'src/data.py',
        'quant_source_sha256': ROOT / 'src/quant.py'}.items()}
    identity['train_membership_sha256'] = train_digest.hexdigest()
    identity['validation_sha256'] = dataset_digest(Path(config['data']['validation']['path']), None)
    if identity['w3_ancestor_sha256'] != ranking['identity']['checkpoint_sha256'] or identity['scales_sha256'] != ranking['identity']['scales_sha256']:
        raise ValueError('Task4 parent/scales identity mismatch')
    if len(dataset) != 1_277_128 or train_digest.hexdigest() != parent['recipe']['identity']['train_membership_sha256']:
        raise ValueError('optimizer corpus must exactly match the strict MLP parent')
    if identity['parent_sha256'] != 'ecc26c2d04c2e8952324cbc1e1806866b63a418018169a5cfc40af50d44f0e02':
        raise ValueError('strict MLP parent changed')
    del parent
    recipe = {'checkpoint_schema': 'original_hls_s3.attention_qat.v1', 'parent_state': 'ema_model+ema_controller', 'settings': settings, 'identity': identity, 'numeric_contract': config['numeric_contract'],
              'selection_policy': 'every_all12_epoch_formal_top1_then_top5',
              'sensitivity_order': order, 'train_count': len(dataset), 'probe_steps': args.probe_steps, 'probe_joint': args.probe_joint,
              'selection_role': 'fixed 2000 train-origin holdout images, excluded from optimizer training',
              'calibration_role': 'fixed 2000 train-origin holdout images, excluded from optimizer training',
              'role_isolation': isolation,
              'formal_role': '50000 validation images never used for gradients or scale fitting'}
    probe_name = ('probe_joint' if args.probe_joint else 'probe') + f"_b{settings['batch_size']}_{args.probe_profile}_isolated"
    destination = ROOT / 'checkpoints/attention' / (probe_name if args.probe_steps else 'main')
    destination.mkdir(parents=True, exist_ok=True)
    recipe_path = destination / 'recipe.json'
    resume_recipe = recipe
    resume_payload = None
    if args.resume:
        resume_payload = torch.load(destination / 'latest.pth', map_location='cpu', weights_only=False)
        resume_recipe = resume_payload['recipe']
    if resume_recipe != recipe:
        raise ValueError('frozen recipe mismatch')
    if recipe_path.exists() and json.loads(recipe_path.read_text()) != recipe:
        raise ValueError('frozen recipe mismatch')
    if (destination / 'latest.pth').exists() and not args.resume:
        raise FileExistsError('existing checkpoint requires --resume')
    optimizer = torch.optim.AdamW(stage_parameter_groups(model, controller, active=[], joint=True, lr=settings['learning_rate'], scale_lr=settings['scale_learning_rate']), fused=True)
    ema = EMA(model, controller, decay=settings['ema_decay'])
    progress = {'epoch': 0, 'next_batch': 0, 'sample_offset': 0, 'global_step': 0,
                'branch': 0, 'best_selection': -1., 'epochs_completed': 0, 'status': 'training'}
    if args.resume:
        progress = restore_checkpoint(destination / 'latest.pth', model, controller, optimizer, ema, recipe=resume_recipe)
    summary_path = ROOT / 'reports' / (f'attention_qat_{probe_name}.json' if args.probe_steps else 'attention_qat_training.json')
    summary = resume_payload['history'] if resume_payload is not None else {
        'recipe': recipe, 'epochs': [], 'formal_candidates': [], 'status': 'training', 'probe': bool(args.probe_steps)}
    del resume_payload
    summary['recipe'] = recipe
    best_formal = max(summary['formal_candidates'], key=lambda row: (row['top1'], row['top5']), default=None)
    summary['best_formal'] = best_formal
    selection = make_selection_loader(ROOT / 'metadata/selection_manifest.jsonl', root=dataset.root,
                                      class_mapping=mapping, batch_size=settings['batch_size'],
                                      num_workers=settings['workers'], expected_count=2000)
    validation = None
    steps_per_epoch = math.ceil(len(dataset) / settings['batch_size'])
    start = time.time()
    base_epochs = settings['progressive_epochs'] + settings['joint_epochs']
    maximum_epochs = base_epochs + sum(item['epochs'] for item in settings['recovery_grid'])
    probe_weight = model.vit.blocks[order[0]].attn.qkv.weight
    initial_weight = probe_weight.detach().clone()
    initial_scales = {name: p.detach().clone() for name, p in controller.log_scales.items()}
    def checkpoint():
        summary['progress'] = dict(progress)
        save_checkpoint(destination / 'latest.pth', model, controller, optimizer, ema, recipe=recipe, progress=progress, history=summary)
        atomic_write_json(destination / 'progress.json', progress)
        atomic_write_json(summary_path, summary)
        if not args.probe_steps and progress['epoch'] >= 4:
            joint = ROOT / 'checkpoints/joint/main'
            joint.mkdir(parents=True, exist_ok=True)
            for name in ('latest.pth', 'best.pth', 'base_best.pth'):
                if (destination / name).exists():
                    temporary = joint / f'.{name}.new'
                    temporary.unlink(missing_ok=True)
                    os.link(destination / name, temporary)
                    os.replace(temporary, joint / name)
            atomic_write_json(joint / 'progress.json', progress)
            atomic_write_json(joint / 'recipe.json', recipe)
            atomic_write_json(ROOT / 'reports/joint_qat_training.json', summary)

    def finish_pending_formal():
        nonlocal validation, best_formal
        epoch = progress.get('pending_formal')
        if epoch is None:
            return False
        branch = progress['branch']
        controller.set_masks(attention_masks(order, 3))
        candidate_path = destination / f'candidate_epoch{epoch:02d}.pth'
        publish_candidate(destination / 'latest.pth', candidate_path, recipe=recipe, epoch=epoch, global_step=progress['global_step'])
        current_model = {k: v.detach().clone() for k, v in model.state_dict().items()}
        current_controller = {k: v.detach().clone() for k, v in controller.state_dict().items()}
        model.load_state_dict(ema.model)
        controller.load_state_dict(ema.controller)
        if validation is None:
            validation = make_validation_loader(config['data']['validation']['path'], model=model,
                batch_size=settings['batch_size'], num_workers=settings['workers'])
        result = evaluate(model, validation, expected_count=50000)
        result.update(epoch=epoch, branch=branch, checkpoint_sha256=sha256_file(candidate_path),
                      identity=identity, stage='strict_attention_MLP_surrogate',
                      selection_top1=summary['epochs'][-1]['selection']['top1'])
        summary['formal_candidates'].append(result)
        if formal_is_better(result, best_formal):
            best_formal = result
            summary['best_formal'] = result
            for best_name in (('best.pth', 'base_best.pth') if branch == 0 else ('best.pth',)):
                temporary_link = destination / f'.{best_name}.new'
                temporary_link.unlink(missing_ok=True)
                os.link(candidate_path, temporary_link)
                os.replace(temporary_link, destination / best_name)
        atomic_write_json(ROOT / 'reports' / f'attention_qat_formal_epoch{epoch:02d}.json', result)
        if epoch >= 4:
            joint_candidate = ROOT / 'checkpoints/joint/main' / candidate_path.name
            if not joint_candidate.exists():
                os.link(candidate_path, joint_candidate)
            atomic_write_json(ROOT / 'reports' / f'joint_qat_formal_epoch{epoch:02d}.json', result)
        model.load_state_dict(current_model)
        controller.load_state_dict(current_controller)
        teacher_features.clear()
        student_features.clear()
        progress.pop('pending_formal')
        if result['top1'] >= .69:
            summary['status'] = progress['status'] = 'target_reached'
        checkpoint()
        print(json.dumps({'formal': result}), flush=True)
        return result['top1'] >= .69

    atomic_write_json(recipe_path, recipe)
    if finish_pending_formal():
        return
    for epoch in range(progress['epoch'], maximum_epochs):
        branch = 0 if epoch < base_epochs else 1 + (epoch - base_epochs) // 2
        branch_settings = settings if branch == 0 else settings['recovery_grid'][branch - 1]
        if branch != progress['branch']:
            # Every recovery branches from the frozen base-mainline selection winner.
            recovery_parent = destination / 'base_best.pth'
            payload = torch.load(recovery_parent, map_location='cpu', weights_only=False)
            model.load_state_dict(payload['ema_model'])
            controller.load_state_dict(payload['ema_controller'])
            optimizer = torch.optim.AdamW(stage_parameter_groups(model, controller, active=list(range(12)), joint=True,
                lr=branch_settings['learning_rate'], scale_lr=branch_settings['scale_learning_rate']), fused=True)
            ema = EMA(model, controller, decay=settings['ema_decay'])
            progress['branch'] = branch
            progress['branch_parent_sha256'] = sha256_file(recovery_parent)
        mask_epoch = 3 if args.probe_steps and args.probe_joint else epoch
        controller.set_masks(attention_masks(order, mask_epoch))
        stage_parameter_groups(model, controller, active=controller.masks['ln1'],
            joint=epoch >= 4 or args.probe_joint, lr=branch_settings['learning_rate'],
            scale_lr=branch_settings['scale_learning_rate'])
        validate_training_contract(config, model)
        model.train()
        teacher.eval()
        offset = progress['sample_offset'] if progress['epoch'] == epoch else 0
        loader = DataLoader(dataset, batch_size=settings['batch_size'],
            sampler=epoch_indices(len(dataset), seed=seed, epoch=epoch, offset=offset),
            num_workers=settings['workers'], pin_memory=True, prefetch_factor=2,
            generator=torch.Generator().manual_seed(seed + epoch))
        epoch_start = time.time()
        epoch_steps = 0
        loss_total = 0.
        for images, labels, ids in loader:
            images, labels = images.cuda(non_blocking=True), labels.cuda(non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            teacher_features.clear()
            student_features.clear()
            with torch.no_grad():
                teacher_logits = teacher(images)
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(images)
            ce = F.cross_entropy(logits.float(), labels)
            kd = logit_kd(logits, teacher_logits, temperature=settings['temperature'])
            features = feature_reconstruction(student_features.values, teacher_features.values)
            loss = settings['ce_weight'] * ce + branch_settings['kd_weight'] * kd + branch_settings['feature_weight'] * features
            loss.backward()
            grad_norm = torch.nn.utils.clip_grad_norm_([*model.parameters(), *controller.parameters()], settings['gradient_clip'], error_if_nonfinite=True)
            schedule_epoch = epoch if branch == 0 else (epoch - base_epochs) % 2
            schedule_step = schedule_epoch * steps_per_epoch + progress['sample_offset'] // settings['batch_size']
            schedule_total = (base_epochs if branch == 0 else 2) * steps_per_epoch
            factor = lr_factor(schedule_step, total=schedule_total, warmup=int(settings['warmup_epochs'] * steps_per_epoch))
            for group in optimizer.param_groups:
                group['lr'] = group['initial_lr'] * factor
            optimizer.step()
            ema.update(model, controller)
            progress.update(epoch=epoch, sample_offset=progress['sample_offset'] + len(ids),
                            next_batch=progress['next_batch'] + 1, global_step=progress['global_step'] + 1)
            epoch_steps += 1
            loss_total += float(loss.detach())
            progress.update(last_loss=float(loss.detach()), last_ce=float(ce.detach()), last_kd=float(kd.detach()),
                            last_feature=float(features.detach()), last_grad_norm=float(grad_norm),
                            images_per_second=(progress['sample_offset'] - offset) / (time.time() - epoch_start),
                            elapsed_seconds=time.time() - start, masks=controller.masks)
            teacher_features.clear()
            student_features.clear()
            if progress['global_step'] % 25 == 0:
                atomic_write_json(destination / 'progress.json', progress)
                print(json.dumps(progress), flush=True)
            if progress['global_step'] % settings['checkpoint_every_steps'] == 0:
                checkpoint()
            if args.probe_steps and progress['global_step'] >= args.probe_steps:
                summary.update(status='probe_complete', progress=progress,
                    weight_max_change=float((probe_weight.detach() - initial_weight).abs().max()),
                    scale_max_change=scale_movements(initial_scales, controller)['ln1'],
                    scale_movements=scale_movements(initial_scales, controller),
                    peak_cuda_memory_bytes=torch.cuda.max_memory_allocated(),
                    teacher_gradients_absent=all(p.grad is None for p in teacher.parameters()))
                if summary['weight_max_change'] <= 0 or summary['scale_max_change'] <= 0 or not summary['teacher_gradients_absent']:
                    raise ValueError('probe failed actual weight/scale movement or teacher freezing')
                checkpoint()
                print(json.dumps({'status': 'probe_complete', 'report': str(summary_path)}), flush=True)
                return
        if progress['sample_offset'] != len(dataset):
            raise ValueError('incomplete full-data training epoch')
        current_model = {k: v.detach().clone() for k, v in model.state_dict().items()}
        current_controller = {k: v.detach().clone() for k, v in controller.state_dict().items()}
        model.load_state_dict(ema.model)
        controller.load_state_dict(ema.controller)
        selection_result = evaluate(model, selection, expected_count=2000)
        teacher_features.clear()
        student_features.clear()
        row = {'epoch': epoch, 'branch': branch, 'training_count': len(dataset),
               'mean_loss_this_session': loss_total / max(1, epoch_steps),
               'elapsed_seconds_this_session': time.time() - epoch_start, 'selection': selection_result,
               'masks': controller.masks, 'settings': branch_settings}
        summary['epochs'].append(row)
        improved = epoch >= 3 and selection_result['top1'] > progress['best_selection']
        model.load_state_dict(current_model)
        controller.load_state_dict(current_controller)
        progress.update(epoch=epoch + 1, next_batch=0, sample_offset=0, epochs_completed=epoch + 1)
        if improved:
            progress['best_selection'] = selection_result['top1']
        if epoch >= 3:
            progress['pending_formal'] = epoch
            checkpoint()
            if finish_pending_formal():
                return
        checkpoint()
        print(json.dumps(row), flush=True)
    summary['status'] = progress['status'] = 'budget_exhausted'
    checkpoint()


if __name__ == '__main__':
    main()
