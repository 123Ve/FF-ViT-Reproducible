"""Fail-closed inventory and semantic acceptance for the frozen NWPU archive.

The manifest is an integrity inventory, not a cryptographic signature. Keep its
digest separately when distributing the archive. Historical review mutations
are inventoried but never used as numerical parameter authorities.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import struct

RUN = 'runs/nwpu_seed20260923'
DEPLOY = 'deployment/nwpu_seed20260923'
BOUNDARIES = [('patch_out', 'patch', 37632)] + [
    (f'block{i}_out', f'block{i}_out', 37632) for i in range(12)] + [
    ('head_input', 'head_input', 192), ('head_ln', 'head_ln', 192), ('logits', 'logits', 1000)]
REQUIRED = ['README.md', 'validation/final_report.json', 'validation/final_report.md',
            'validation/hls_csim.json', 'validation/software_bitexact.json',
            'validation/task8_verified/checks.json', 'validation/task8_verified/software.json',
            'validation/task8_verified/canonical.json', 'validation/task8_verified/ptq_metrics.json',
            'reports/task4_fp32_val.json', 'reports/task4_fp32_test.json',
            'reports/task4_w3_qat_independent_eval.json', 'reports/task5_exact_independent_eval.json',
            f'{RUN}/fp32/best.pth', f'{RUN}/hls196/best.pth',
            f'{RUN}/qat_weight3_hls196/best_qat_state.pth', f'{DEPLOY}/deployment_manifest.json']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f'missing or invalid JSON: {path}') from exc


def info(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def local_path(root, name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and str(path) == name and name != '.',
            f'unsafe inventory path: {name}')
    target = root / name
    require(target.resolve().is_relative_to(root.resolve()), f'external inventory path: {name}')
    for part in (target, *target.parents):
        if part == root:
            break
        require(not part.is_symlink(), f'symlink in bundle: {name}')
    return target


def file_inventory(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), f'symlink in bundle: {path}')
        name = path.relative_to(root).as_posix()
        if '__pycache__' in path.parts or path.suffix == '.pyc' or name == 'MANIFEST.json':
            continue
        if path.is_file():
            result[name] = info(path)
    return result


def verify_inventory(root, inventory):
    require(bool(inventory), 'missing file inventory')
    for name, expected in inventory.items():
        path = local_path(Path(root), name)
        require(path.is_file(), f'missing file: {name}')
        require(info(path) == expected, f'integrity mismatch (size/hash): {name}')
    actual = file_inventory(root)
    require(set(actual) == set(inventory), f'unlisted bundle files: {sorted(set(actual) - set(inventory))[:10]}')


def verify_metadata(metadata):
    from .manifest_dataset import load_manifest_bundle
    bundle = load_manifest_bundle(metadata)
    require(bundle.seed == 20260923, 'split seed drift')
    return bundle


def verify_deployment(deployment):
    from .deployment_export import SIZES, _validate_declarations, parse_c_array, SHAPES
    deployment = Path(deployment)
    manifest = read_json(deployment / 'deployment_manifest.json')
    contract = {'blocks': 12, 'channels': 192, 'tokens': 196, 'input_channels': 768,
                'mlp_channels': 768, 'output_logits': 1000, 'classes_active': 45,
                'classes_inactive': 955, 'inactive_logit': -262144, 'weights_bytes': 2772096,
                'signed_weight_range': [-4, 3], 'cpp_packing_equal': True}
    for key, expected in contract.items():
        require(manifest['contract'].get(key) == expected, f'ABI contract drift: {key}')
    for name, count in SIZES.items():
        require((deployment / name).stat().st_size == count, f'ABI size drift: {name}')
    for name, expected in manifest['outputs'].items():
        actual = info(local_path(deployment, name))
        require(actual == {'bytes': expected['size_bytes'], 'sha256': expected['sha256']},
                f'deployment integrity mismatch: {name}')
    require(info(deployment / 'weights.bin') == info(deployment / 'weights_hls.bin'), 'ABI packer mismatch')
    values = struct.unpack('<1000i', (deployment / 'output.bin').read_bytes())
    require(all(v == -262144 for v in values[45:]), 'unsafe inactive logits')
    require(max(range(1000), key=values.__getitem__) < 45, 'inactive prediction')
    rom = deployment / 'fixed_patch_head_rom.h'
    _validate_declarations(rom.read_text())
    import numpy as np
    for name, expected in [('HEAD_WEIGHT', 0), ('HEAD_BIAS', -262144)]:
        require(bool(np.all(parse_c_array(rom, name, SHAPES[name])[45:] == expected)), 'unsafe inactive ROM')
    return manifest


def compare_boundaries(root, dumps):
    result = {}
    for actual, reference, count in BOUNDARIES:
        a = Path(dumps) / f'hls_{actual}.bin'
        b = Path(root) / DEPLOY / f'refs/ref_{reference}.bin'
        require(a.is_file() and b.is_file(), f'missing C-sim boundary: {actual}')
        av, bv = a.read_bytes(), b.read_bytes()
        require(len(av) == len(bv) == count * 4, f'C-sim boundary size: {actual}')
        require(av == bv, f'C-sim boundary mismatch: {actual}')
        result[actual] = {'values': count, 'mismatches': 0,
                          'actual_sha256': info(a)['sha256'], 'reference_sha256': info(b)['sha256']}
    return result


def verify_csim(root, report):
    require(report.get('status') == 'passed' and report.get('fpga_board') == 'not tested', 'C-sim status/scope')
    require(report['canonical']['returncode'] == 0, 'C-sim nonzero exit')
    require(report['negative']['returncode'] != 0, 'missing failing C-sim negative control')
    require(report.get('total_values') == 490600 and report.get('total_mismatches') == 0, 'C-sim totals')
    require(report['boundaries'] == compare_boundaries(root, Path(root) / 'validation/task7/canonical_dumps'),
            'incomplete or incorrect C-sim boundary evidence')
    for name in ('canonical', 'negative'):
        record = report[name]
        path = Path(root) / f'validation/task7/{name}.log'
        require(info(path)['sha256'] == record['log_sha256'], 'C-sim log hash mismatch')
        text = path.read_text()
        markers = re.findall(r'^RESISC45_CHECK (\S+) values=(\d+) mismatches=(\d+) valid=(\d+)$', text, re.M)
        expected = {(f'hls_{a}.bin', str(n), str(int(name == 'negative' and a == 'logits')), '1')
                    for a, _, n in BOUNDARIES}
        require(len(markers) == 16 and set(markers) == expected, 'incomplete C-sim log markers')
        if name == 'canonical':
            require('PASS!' in text and 'CSim done with 0 errors.' in text and 'FAIL!' not in text, 'C-sim pass marker missing')
        else:
            require('FAIL!' in text and "'main' returns nonzero value '1'" in text, 'negative C-sim failure missing')


def verify_fresh(root):
    root = Path(root)
    rec = read_json(root / 'validation/task8_verified/canonical.json')
    require(rec['returncode'] == 0, 'fresh C-sim failed')
    require(rec['boundaries'] == compare_boundaries(root, root / 'validation/task8_verified/canonical_dumps'), 'fresh boundary evidence')
    require(set(rec['freshness']) == {f'hls_{a}.bin' for a, _, _ in BOUNDARIES}, 'fresh dumps incomplete')
    require(all(v['mtime_ns'] >= rec['start_ns'] for v in rec['freshness'].values()), 'stale C-sim dump')
    require(rec['executable_mtime_ns'] >= rec['start_ns'], 'stale C-sim executable')
    log = root / 'validation/task8_verified/canonical.log'
    require(info(log)['sha256'] == rec['log_sha256'], 'fresh C-sim log changed')
    text = log.read_text()
    markers = re.findall(r'^RESISC45_CHECK (\S+) values=(\d+) mismatches=(\d+) valid=(\d+)$', text, re.M)
    require(len(markers) == 16 and set(markers) == {(f'hls_{a}.bin', str(n), '0', '1') for a, _, n in BOUNDARIES}, 'fresh C-sim log incomplete')
    require('PASS!' in text and 'CSim done with 0 errors.' in text and 'FAIL!' not in text, 'fresh C-sim pass missing')
    software = read_json(root / 'validation/task8_verified/software.json')
    require(software['passed'] and software['total_boundary_values'] == 490600, 'fresh software incomplete')
    wanted = {'patch': 37632, **{f'block{i}': 37632 for i in range(12)}, 'head_input': 192, 'head_ln': 192, 'logits': 1000}
    require(set(software['boundaries']) == set(wanted), 'fresh software boundaries incomplete')
    for name, count in wanted.items():
        record = software['boundaries'][name]
        ref = f'ref_{name}_out.bin' if name.startswith('block') else f'ref_{name}.bin'
        require(record == {'values': count, 'mismatches': 0, 'reference_sha256': info(root / DEPLOY / 'refs' / ref)['sha256']}, 'fresh software boundary mismatch')
    checks = read_json(root / 'validation/task8_verified/checks.json')
    require(set(checks) == {'unittest', 'compileall', 'shell', 'check_cli'}, 'missing final checks')
    for name, check in checks.items():
        require(check['returncode'] == 0, f'failed final check: {name}')
        require(info(root / f'validation/task8_verified/{name}.log')['sha256'] == check['log_sha256'], 'check log changed')


def external_dependencies(root):
    root = Path(root).resolve()
    hls = read_json(root / 'validation/hls_csim.json')
    pretrained = root.parents[1] / 'deit_tiny_imagenet_timm.pth'
    return {'dataset': {'path': str(root.parent / 'Dataset'), 'identity': 'metadata/{train,val,test}.json; every image size/SHA-256'},
            'pretrained': {'path': str(pretrained), **info(pretrained)},
            'python': {'path': '/home/user/anaconda3/envs/vlm_token/bin/python', 'environment': 'vlm_token'},
            'compiler': {'command': 'g++', 'version': '12.4.0'},
            'hls_tool': hls['tool'], 'hls_sources': {'path': hls['installation']['source'], 'files': hls['source_hashes']},
            'hls_config': {'path': hls['installation']['config'], 'sha256': hls['config_sha256']},
            'export_templates': {'path': '/home/user/Desktop/FF_Vit/flash_vit_2/src',
                                 'files': {name: info(Path('/home/user/Desktop/FF_Vit/flash_vit_2/src') / name)
                                           for name in ('block0.cpp', 'fixed_patch_head_rom.h')}},
            'hls_headers': {'path': '/opt/vivado/2025.1/Vitis/include', 'role': 'Vitis ap_int headers for C++ type-contract tests'},
            'hls_build': {'path': hls['installation']['component'], 'role': 'mutable derived C-sim build; no model authority'}}


def verify_external(root, dependencies, bundle):
    require(dependencies == external_dependencies(root), 'external dependency declaration drift')
    source = Path(dependencies['dataset']['path'])
    for split in ('train', 'val', 'test'):
        for rec in bundle.records_for(split):
            require(info(local_path(source, rec.relative_path)) == {'bytes': rec.byte_size, 'sha256': rec.sha256}, 'external dataset identity drift')
    for name, expected in dependencies['hls_sources']['files'].items():
        require(info(local_path(Path(dependencies['hls_sources']['path']), name)) == expected, 'external HLS source drift')
    for name, expected in dependencies['export_templates']['files'].items():
        require(info(local_path(Path(dependencies['export_templates']['path']), name)) == expected, 'external template drift')
    config = dependencies['hls_config']
    require(info(config['path'])['sha256'] == config['sha256'], 'HLS config drift')
    tool = dependencies['hls_tool']
    for key in ('', 'executable_'):
        require(info(tool[key + 'path'])['sha256'] == tool[key + 'sha256'], 'HLS tool drift')


def verify_run_provenance(root, current):
    expected = read_json(Path(root) / 'reports/task5_exact_independent_eval.json')['run_artifact_hashes']
    require(current == expected, 'run provenance differs from independently approved artifacts')
    deployment = read_json(Path(root) / DEPLOY / 'deployment_manifest.json')
    require(deployment['provenance']['run_artifacts'] == expected, 'deployment run provenance differs')


def verify_bundle(root, *, external=False):
    root = Path(root).resolve()
    for name in REQUIRED + ['MANIFEST.json']:
        require(local_path(root, name).is_file(), f'missing required file: {name}')
    manifest = read_json(root / 'MANIFEST.json')
    require(manifest.get('schema_version') == 1, 'manifest schema')
    require(manifest.get('exclusions') == ['MANIFEST.json', '**/__pycache__/**', '**/*.pyc'], 'manifest exclusion drift')
    verify_inventory(root, manifest['files'])
    bundle = verify_metadata(root / 'metadata')
    from .artifact_contract import inventory
    verify_run_provenance(root, inventory(root / RUN))
    deploy = verify_deployment(root / DEPLOY)
    require(deploy['classes'] == list(bundle.classes), 'deployment class order drift')
    verify_csim(root, read_json(root / 'validation/hls_csim.json'))
    verify_fresh(root)
    final = read_json(root / 'validation/final_report.json')
    require(final['fpga_board'] == 'not tested' and final['synthesis'] == 'not run', 'final evidence scope drift')
    require(final['metrics'] == measured_metrics(root), 'final accuracy metric drift')
    require(final['hls']['boundaries'] == read_json(root / 'validation/task8_verified/canonical.json')['boundaries'], 'final HLS summary drift')
    for name, expected in final['evidence_hashes'].items():
        require(info(local_path(root, name)) == expected, f'final evidence integrity: {name}')
    for name in ('reports/task4_fp32_val.json', 'reports/task4_fp32_test.json',
                 'reports/task4_w3_qat_independent_eval.json', 'reports/task5_exact_independent_eval.json',
                 'validation/task8_verified/ptq_metrics.json'):
        record = read_json(root / name)
        recorded_hashes = record['manifest_hashes']
        expected_hashes = dict(bundle.metadata_hashes)
        if 'duplicate_groups.json' in recorded_hashes:
            expected_hashes['duplicate_groups.json'] = info(root / 'metadata/duplicate_groups.json')['sha256']
        require(record['classes'] == list(bundle.classes) and recorded_hashes == expected_hashes,
                f'accuracy provenance/class drift: {name}')
    if external:
        verify_external(root, manifest['external_dependencies'], bundle)
    return {'status': 'passed', 'files': len(manifest['files']), 'bytes': sum(v['bytes'] for v in manifest['files'].values()),
            'external_verified': external, 'hls_values': 490600, 'mismatches': 0, 'fpga_board': 'not tested'}


def measured_metrics(root):
    root = Path(root)
    result = {}
    result['fp32'] = {}
    for split in ('val', 'test'):
        value = read_json(root / f'reports/task4_fp32_{split}.json')
        result['fp32'][split] = {'samples': value['samples'], 'correct': round(value['samples'] * value['top1'] / 100), 'top1': value['top1']}
    result['w3_ptq'] = read_json(root / 'validation/task8_verified/ptq_metrics.json')['metrics']
    result['w3_qat'] = read_json(root / 'reports/task4_w3_qat_independent_eval.json')['metrics']
    exact = read_json(root / 'reports/task5_exact_independent_eval.json')['results']
    result['exact_integer'] = {s: {k: exact[s][k] for k in ('samples', 'correct', 'top1')} for s in ('val', 'test')}
    for stage, splits in result.items():
        for split, value in splits.items():
            require(value['samples'] == {'val': 2700, 'test': 4500}[split], f'incomplete accuracy: {stage}')
            require(abs(value['top1'] - 100 * value['correct'] / value['samples']) < 1e-10, f'accuracy count drift: {stage}')
    for stage, limit in [('w3_qat', 2.0), ('exact_integer', 5.0)]:
        require(result['fp32']['val']['top1'] - result[stage]['val']['top1'] <= limit, f'accuracy gate failed: {stage}')
    return result


def generate_manifest(root):
    root = Path(root).resolve()
    for name in REQUIRED:
        require(local_path(root, name).is_file(), f'missing required file: {name}')
    return {'schema_version': 1, 'hash': 'SHA-256',
            'exclusions': ['MANIFEST.json', '**/__pycache__/**', '**/*.pyc'],
            'inventory_scope': 'Every other regular archive file, including historical negative controls; no symlinks.',
            'authoritative_run': RUN, 'authoritative_deployment': DEPLOY,
            'external_dependencies': external_dependencies(root), 'files': file_inventory(root)}
