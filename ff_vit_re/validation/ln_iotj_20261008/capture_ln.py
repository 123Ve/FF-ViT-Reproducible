"""Read-only dataset adapters. Invoke one dataset in each fresh interpreter."""
from __future__ import annotations
import bisect
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import shutil
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGES = ('stage3_patch_hls', 'stage4f_exact_gelu', 'stage4k_exact_attn_outer',
          'stage4k2_refined_qkv', 'stage4l_exact_softmax_aq', 'stage4m_exact_encoder')
KEYS = ('scalars', 'lnw', 'lnb', 'rsqrt_table')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def checked_output(path):
    path = Path(path).resolve()
    if not path.is_relative_to(HERE) or path == HERE:
        raise ValueError('output must be a child of the validation directory')
    return path


def setup_environment():
    sys.dont_write_bytecode = True
    for key, leaf in [('TMPDIR', 'tmp'), ('XDG_CACHE_HOME', 'cache'),
                      ('TORCH_HOME', 'cache/torch'), ('HF_HOME', 'cache/huggingface'),
                      ('MPLCONFIGDIR', 'cache/matplotlib'), ('TRITON_CACHE_DIR', 'cache/triton')]:
        target = HERE / leaf; target.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(target)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '4'


def selected_indices(total, count):
    if type(count) is not int or count < 1 or count > total:
        raise ValueError('samples must be in [1, manifest length]')
    return [total // 2] if count == 1 else np.linspace(0, total - 1, count, dtype=np.int64).tolist()


def legacy_parameters(stages):
    params = []
    arrays = {n: {k: np.load(Path(stages) / stage / f'{n}_{k}.npy', allow_pickle=False)
                  for k in KEYS} for n, stage in [('ln1', STAGES[2]), ('ln2', STAGES[5])]}
    for b in range(12):
        for n in ('ln1', 'ln2'): params.append({k: arrays[n][k][b].copy() for k in KEYS})
    return params


def verify_binary(path, params):
    raw = Path(path).read_bytes()
    if len(raw) != 2772096 or len(params) != 24: raise ValueError('unexpected binary ABI size')
    for b in range(12):
        for j in range(2):
            base = b * 231008 + (75276 if j == 0 else 78688 + 149384)
            offsets = [base, base + 28, base + 28 + 768 + (4 if j else 0),
                       base + 28 + 768 + (4 if j else 0) + 1536]
            for key, off, count, dtype in zip(KEYS, offsets, [7, 192, 192, 128], ['<i4', '<i4', '<i8', '<i4']):
                binary = np.frombuffer(raw, dtype=dtype, count=count, offset=off)
                if not np.array_equal(binary, params[b * 2 + j][key]):
                    raise ValueError(f'binary mismatch block{b:02d}.ln{j+1}.{key}')
    return dict(status='PASS', instances=24, arrays=96, path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def file_identity(paths):
    return [{ 'path': str(Path(p).resolve()), 'sha256': sha256(p), 'bytes': Path(p).stat().st_size }
            for p in dict.fromkeys(paths)]


def verify_source_binding(records):
    if not records: raise ValueError('empty source binding')
    for path, expected in records.items():
        if sha256(path) != expected: raise ValueError('source hash mismatch: '+str(path))
    return dict(status='PASS', count=len(records), sources=records)


class Adapter:
    def __init__(self, dataset, output, samples):
        setup_environment()
        import torch
        torch.set_num_threads(4); torch.set_num_interop_threads(4)
        torch.manual_seed(0); np.random.seed(0)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        self.dataset_name, self.output = dataset, checked_output(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.torch, self.specs, self.sources = torch, [], []
        self.records, self.current, self.callback = [], None, None
        if dataset == 'imagenet': self._imagenet()
        elif dataset in ('plantvillage', 'nwpu'): self._legacy(dataset)
        else: raise ValueError('unknown dataset')
        self.indices = selected_indices(len(self.dataset), samples)
        imported_sources = sorted({Path(module.__file__).resolve() for module in list(sys.modules.values())
            if getattr(module, '__file__', None) and str(module.__file__).endswith('.py')
            and Path(module.__file__).resolve().is_relative_to(ROOT)
            and not Path(module.__file__).resolve().is_relative_to(HERE)})
        self.sources += imported_sources
        self.provenance.update(dataset=dataset, manifest_size=len(self.dataset), selected_indices=self.indices,
                               sample_count=samples, cpu_threads=4, autocast=False, tf32=False,
                               input_identity='same captured signed integer codes for all local references',
                               accuracy_evaluation='NOT_MEASURED', board_weights='EXCLUDED',
                               versions={'python':platform.python_version(), **{p:importlib.metadata.version(p)
                                   for p in ('numpy','torch','torchvision','timm','Pillow','pyarrow')}},
                               imported_model_source_files=[str(p) for p in imported_sources],
                               files=file_identity(self.sources))

    def _legacy(self, name):
        torch = self.torch
        if name == 'plantvillage':
            base = ROOT / 'quantization_final'
            sys.path.insert(0, str(base / 'scripts'))
            stage_root = self.output / 'parameters'; stage_root.mkdir(exist_ok=True)
            for stage in STAGES:
                target = stage_root / stage
                shutil.copytree(base / 'artifacts' / stage, target, dirs_exist_ok=True)
                shutil.copy2(base / 'reports' / stage / 'report.json', target / 'report.json')
            checkpoint_root, original_stages = base / 'checkpoints', base / 'artifacts'
            model_path = checkpoint_root / 'plantvillage_hls196/best.pth'
            binary = base / 'deployment/weights.bin'
        else:
            base = ROOT / 'archive/nwpu_resisc45_ffvit'
            sys.path[:0] = [str(base), str(base / 'scripts/quant'), str(base / 'scripts/quant/canonical')]
            import manifest_adapter
            manifest_adapter.configure(base / 'metadata', ROOT / 'archive/Dataset', 45, 1440)
            stage_root = checkpoint_root = original_stages = base / 'runs/nwpu_seed20260923'
            model_path = checkpoint_root / 'hls196/best.pth'
            binary = base / 'deployment/nwpu_seed20260923/weights.bin'
        from qat_weight3_hls196 import eval_transform
        from stage4b_activation_ptq_eval import rebuild_stage3_model
        from stage4d_mlp_activation_qat import MLPActivationController
        from stage4j_attention_activation_qat import AttentionActivationController
        from stage4n_head_integer_audit import install_stage4m_exact_encoder
        qat_path = checkpoint_root / 'qat_weight3_hls196/best_qat_state.pth'
        attention_path = checkpoint_root / 'stage4j_attention_qat/best_attention_qat.pth'
        ranges_path = original_stages / 'stage4a_ranges/activation_ranges.json'
        ranges = json.loads(ranges_path.read_text())['statistics']
        model, backbone, source = rebuild_stage3_model(model_path, qat_path, stage_root / STAGES[0])
        mlp = MLPActivationController(backbone, ranges)
        saved = torch.load(attention_path, map_location='cpu', weights_only=True)
        model.load_state_dict(saved['student_state'], strict=True)
        mlp.load_state_dict(saved['mlp_controller_state'], strict=True)
        attention = AttentionActivationController(backbone, ranges, saved['attention_controller_state']['attn_out_scale'].numpy())
        attention.load_state_dict(saved['attention_controller_state'], strict=True)
        model.eval(); mlp.eval(); attention.eval()
        mlp.set_active(range(12)); attention.set_active(range(12)); mlp.install(); attention.install()
        patch_scale = json.loads((stage_root / STAGES[0] / 'report.json').read_text())['patch_output']['real_scale']
        handles, final_scale = install_stage4m_exact_encoder(backbone, mlp, attention, torch.device('cpu'),
            *(stage_root / s for s in STAGES[1:]), patch_scale)
        params = legacy_parameters(original_stages)
        sx1 = np.load(original_stages / STAGES[2] / 'ln1_input_scales.npy')
        sx2 = np.load(original_stages / STAGES[5] / 'ln2_input_scales.npy')
        report_m = json.loads((stage_root / STAGES[5] / 'report.json').read_text())
        mlp_scales = mlp.export_scales()
        for b, block in enumerate(backbone.vit.blocks):
            for j, norm in enumerate((block.norm1, block.norm2)):
                sy = float(attention.ln1_scale(b).detach()) if j == 0 else float(mlp_scales[str(b)]['ln2_signed3_scale'])
                spec = dict(name=f'block{b:02d}.ln{j+1}', params=params[b*2+j], bits=13 if j == 0 else 15,
                            gamma=norm.weight.detach().numpy().copy(), beta=norm.bias.detach().numpy().copy(),
                            sx=float((sx1 if j == 0 else sx2)[b]), sy=sy, eps=float(norm.eps))
                self.specs.append(spec)
                def capture(module, inputs, value, spec=spec):
                    q = torch.round(inputs[0] / spec['sx']).to(torch.int64)
                    half = 1 << (spec['bits'] - 1)
                    q = (q + half).remainder(2 * half) - half
                    actual = torch.round(value / spec['sy']).to(torch.int64)
                    self.callback(spec, q.detach().cpu().numpy().reshape(-1, 192),
                                  actual.detach().cpu().numpy().reshape(-1, 192), self.current)
                handles.append(norm.register_forward_hook(capture))
        self.model, self.handles = model, handles
        self.controllers = (attention, mlp)
        transform = eval_transform()
        if name == 'plantvillage':
            from torchvision.datasets import ImageFolder
            self.dataset = ImageFolder(str(base / 'datasets/PlantVillage/splits/test'), transform=transform)
            if self.dataset.classes != source['classes']: raise ValueError('class order differs from checkpoint')
            self.source_manifest = [dict(index=i, path=str(Path(p).resolve()), label=y) for i, (p,y) in enumerate(self.dataset.samples)]
            self.provenance = {'manifest_kind': 'sorted ImageFolder test samples', 'manifest_sha256': hashlib.sha256(json.dumps(self.source_manifest, sort_keys=True).encode()).hexdigest()}
        else:
            self.dataset = manifest_adapter.image_folder(ROOT / 'archive/Dataset/test', transform)
            self.provenance = {'manifest_kind': 'frozen test.json', 'manifest_sha256': sha256(base / 'metadata/test.json')}
            self.sources.append(base / 'metadata/test.json')
        self.provenance.update(path='original installed Stage4K LN1 + Stage4M LN2 PyTorch integer replacement hooks; capture hook appended after replacement',
            binary_association=verify_binary(binary, params), transform=repr(transform), tokens_per_image=196,
            ln1_input_scale_source=str(original_stages / STAGES[2] / 'ln1_input_scales.npy'),
            ln1_scale_vs_stage4m_report={'stage4k': sx1.tolist(), 'stage4m': report_m.get('block_input_int13_scales'),
                'equal': bool(np.array_equal(sx1, report_m.get('block_input_int13_scales')))},
            ln2_input_scale_source=str(original_stages / STAGES[5] / 'ln2_input_scales.npy'))
        self.sources += [model_path, qat_path, attention_path, ranges_path, binary]
        self.sources += [p for stage in STAGES for p in (original_stages / stage).rglob('*') if p.is_file()]
        if name == 'plantvillage': self.sources += [base / 'reports' / s / 'report.json' for s in STAGES]

    def _imagenet(self):
        torch = self.torch
        base = ROOT / 'image1k_hls_s3_original'; sys.path.insert(0, str(base))
        from src import exact
        from src.contract import load_contract
        from src.model import load_hls196_fp32
        from src.data import make_validation_loader
        artifact_path = base / 'exact/main'
        artifact, metadata = exact.load_artifact(artifact_path)
        checkpoint = base / 'checkpoints/attention/main/best.pth'
        checkpoint_hash = sha256(checkpoint)
        if checkpoint_hash != exact.CHECKPOINT_SHA256 or checkpoint_hash != metadata['checkpoint_sha256']:
            raise ValueError('final S3 checkpoint identity mismatch')
        binding = verify_source_binding(metadata['source_binding']['sources'])
        saved = torch.load(checkpoint, map_location='cpu', weights_only=False)
        state, controller = saved['ema_model'], saved['ema_controller']
        config = load_contract(base / 'config/original_hls_s3.yaml')
        fp_model = load_hls196_fp32(config['model']['hls196_fp32_checkpoint'])
        self.dataset = make_validation_loader(config['data']['validation']['path'], model=fp_model, batch_size=1, num_workers=0).dataset
        eps = [float(n.eps) for block in fp_model.vit.blocks for n in (block.norm1, block.norm2)]
        for b, p in enumerate(artifact['blocks']):
            for j, n in enumerate(('ln1', 'ln2')):
                prefix = f'vit.blocks.{b}.norm{j+1}'
                meta = metadata['blocks'][b]
                self.specs.append(dict(name=f'block{b:02d}.{n}', params=p[n], bits=13 if j == 0 else 15,
                    gamma=state[prefix+'.weight'].numpy(), beta=state[prefix+'.bias'].numpy(),
                    sx=float(meta['input_scale' if j == 0 else 'physical_o_scale']),
                    sy=float(controller['log_scales.'+n][b].exp()), eps=eps[b*2+j]))
        self.exact, self.artifact = exact, artifact
        self.provenance = dict(path='final strict S3 exact/main: src.exact.patch_forward + block_forward(trace=True)',
            upstream='model-specific strict S3 Softmax u3; not third-party E07 board trace',
            checkpoint_state='ema_model / ema_controller', tokens_per_image=196,
            source_binding_verification=binding,
            binary_association=verify_binary(artifact_path / 'weights.bin', [s['params'] for s in self.specs]),
            transform=repr(self.dataset.transform), transform_provenance=self.dataset.provenance,
            epsilon_source='original HLS196 model norm eps; EMA checkpoint has no epsilon state',
            manifest_kind='sorted Parquet files and row groups',
            parquet_manifest=[dict(path=str(p), row_group=g, file_row_start=start, rows=n) for p,g,start,n in self.dataset._groups])
        self.provenance['manifest_sha256'] = hashlib.sha256(json.dumps(self.provenance['parquet_manifest'],sort_keys=True).encode()).hexdigest()
        self.sources += [checkpoint, artifact_path / 'manifest.json', artifact_path / 'arrays.npz', artifact_path / 'weights.bin',
                         base / 'config/original_hls_s3.yaml', Path(config['model']['hls196_fp32_checkpoint'])]

    def sample(self, index):
        item = self.dataset[index]; image, label = item[:2]
        record = dict(index=index, label=int(label), transformed_fp32_sha256=hashlib.sha256(image.numpy().tobytes()).hexdigest())
        if self.dataset_name == 'imagenet':
            record['identity'] = item[2]
            gi = bisect.bisect_right(self.dataset._ends, index)
            path, group, start, count = self.dataset._groups[gi]
            offset = index - (0 if gi == 0 else self.dataset._ends[gi-1])
            row = self.dataset._row_group(path, group)[offset]
            record.update(parquet=str(path), row_group=group, row_offset=offset,
                          source_image_sha256=hashlib.sha256(bytes(row['image']['bytes'])).hexdigest())
        else:
            path, _ = self.dataset.samples[index]
            record.update(identity=str(Path(path).resolve()), source_image_sha256=sha256(path))
            if self.dataset_name == 'nwpu':
                expected = self.dataset.records[index].sha256
                if record['source_image_sha256'] != expected: raise ValueError('selected source image hash mismatch')
                record['manifest_image_sha256'] = expected
        return image, record

    def run(self, callback):
        self.callback = callback
        try:
            with self.torch.inference_mode():
                for index in self.indices:
                    image, record = self.sample(index)
                    self.current = record['identity']; self.records.append(record)
                    if self.dataset_name == 'imagenet':
                        x = self.exact.patch_forward(image.unsqueeze(0), self.artifact['patch'])
                        for b, p in enumerate(self.artifact['blocks']):
                            previous = x
                            x, trace = self.exact.block_forward(x, p, trace=True)
                            for j, (a, out) in enumerate(((previous, trace['ln1']), (trace['attention_residual'], trace['ln2']))):
                                callback(self.specs[b*2+j], a.numpy().reshape(-1,192), out.numpy().reshape(-1,192), self.current)
                    else: self.model(image.unsqueeze(0))
                    print(json.dumps(dict(event='sample_complete', dataset=self.dataset_name, index=index)), flush=True)
        finally:
            for handle in getattr(self, 'handles', []): handle.remove()
            for controller in getattr(self, 'controllers', []): controller.remove()


if __name__ == '__main__':
    from run_validation import main
    main()
