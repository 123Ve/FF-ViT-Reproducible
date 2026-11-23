"""Select the strict S3/U3 workflow and its dependencies from the verified snapshot."""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
NAME = 'FFViT_Strict_S3_Code_20261022'
OLD = 'FFViT_Quantization_Finetuning_LUT_Code_20261022'
P = 'ff_vit_re/'
UP = P + 'image_lianghu/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def csv_bytes(rows, fields):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--input-zip', type=Path, default=HERE.parent / (OLD + '.zip'))
    parser.add_argument('--output-dir', type=Path, default=HERE)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    directory, archive = output / NAME, output / (NAME + '.zip')
    if directory.exists() or archive.exists():
        raise FileExistsError('Refusing to replace existing S3 package')
    with zipfile.ZipFile(args.input_zip) as source:
        old_manifest = json.loads(source.read(OLD + '/MANIFEST.json'))
        rows = {r['path']: r for r in old_manifest['files']}
        data = {p: source.read(OLD + '/' + p) for p in rows}
        for p, blob in data.items():
            if len(blob) != rows[p]['bytes'] or sha(blob) != rows[p]['sha256']:
                raise ValueError('Input snapshot integrity failed: ' + p)

    chosen = {}
    def add(p, role):
        if p not in data:
            raise FileNotFoundError('Required snapshot source missing: ' + p)
        chosen.setdefault(p, role)

    root_names = {'train_plantvillage.py', 'make_hls196_plantvillage.py',
                  'ptq_stage1_weight3.py', 'qat_weight3_hls196.py', 'calib_manifest.json'}
    nw = P + 'archive/nwpu_resisc45_ffvit/'
    validation_names = {'e07_u3_progressive_qat_20261010', 'e07_u3_qat_20261010',
                        'softmax_u3_hls_20261010', 'ln_iotj_20261008', 'lut_float_accuracy_20261010'}
    for p in data:
        q = Path(p)
        if p.startswith(P) and len(q.parts) == 2 and q.name in root_names:
            add(p, 'FP32_W3_initialization')
        elif p.startswith(P + 'image1k_hls_s3_original/'):
            if q.name != 'revise_quant_chapter_docx.py':
                add(p, 'ImageNet_original_strict_S3')
        elif p.startswith(P + 'quantization_final/scripts/'):
            if '/deployment/' not in p:
                add(p, 'shared_legacy_helper_NOT_U8_entrypoint')
        elif p.startswith(P + 'quantization_final/calibration/') or p.startswith(P + 'quantization_final/reports/'):
            add(p, 'historical_initialization_metadata')
        elif p.startswith(nw):
            sub = p[len(nw):]
            if sub.startswith(('src/', 'metadata/', 'runs/')):
                add(p, 'NWPU_initialization_support')
            elif sub.startswith('scripts/quant/'):
                add(p, 'NWPU_shared_stage_helpers_NOT_final_U8_pipeline')
            elif sub in {'scripts/prepare_dataset.py', 'scripts/train_fp32.py',
                         'scripts/make_hls196.py', 'scripts/evaluate_checkpoint.py'}:
                add(p, 'NWPU_FP32_W3_initialization')
        elif p.startswith(P + 'validation/') and q.parts[2] in validation_names:
            name = q.parts[2]
            if name == 'e07_u3_progressive_qat_20261010':
                if '_pre_rsqrt_fix' not in p:
                    add(p, 'PlantVillage_NWPU_strict_E07_U3')
            elif len(q.parts) == 4 and q.suffix == '.py':
                add(p, 'strict_U3_runtime_or_local_audit_dependency')
            elif name == 'e07_u3_qat_20261010' and '/outputs/' in p and q.suffix == '.json':
                add(p, 'E07_U3_initialization_metadata')
            elif name == 'ln_iotj_20261008' and '/outputs/final128/' in p and q.name in {'samples.json', 'summary.json'}:
                add(p, 'frozen_sample_identity_and_reference_metadata')
        elif p.startswith('external_sources/FF_Vit/'):
            add(p, 'external_HLS_reference_source')
        elif p.startswith(UP + 'metadata/'):
            add(p, 'ImageNet_W3_initialization_metadata')
        elif p.startswith(UP + 'scripts/') and (q.name.startswith(('train_w3_qat', 'build_qat_'))
                or q.name in {'evaluate_fp32.py', 'run_w3_ptq.py', 'build_manifests.py'}):
            add(p, 'ImageNet_W3_initialization')

    # Resolve the ImageNet project's static imports and explicit legacy_module calls.
    # Do not import/execute model code; use the immutable source AST only.
    dependency_edges = set()
    pending = list(chosen)
    scanned = set()
    while pending:
        p = pending.pop()
        if p in scanned or not p.endswith('.py'):
            continue
        scanned.add(p)
        tree = ast.parse(data[p], filename=p)
        targets = []
        if p.startswith(UP):
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.level:
                        parent = Path(p).parent
                        for _ in range(node.level - 1): parent = parent.parent
                        stem = str(parent / ((node.module or '').replace('.', '/')))
                    elif node.module and node.module.split('.')[0] in {'src', 'scripts'}:
                        stem = UP + node.module.replace('.', '/')
                    else:
                        continue
                    targets += [stem + '.py', stem + '/__init__.py']
                    targets += [stem + '/' + a.name + '.py' for a in node.names]
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        if a.name.split('.')[0] in {'src', 'scripts'}:
                            stem = UP + a.name.replace('.', '/')
                            targets += [stem + '.py', stem + '/__init__.py']
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'legacy_module':
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    targets.append(UP + 'src/' + node.args[0].value + '.py')
            if len(Path(p).parts) == 2 and isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
                targets += [P + n.replace('.', '/') + '.py' for n in names]
        if p.startswith(UP):
            targets += [UP + 'src/__init__.py', UP + 'scripts/__init__.py']
        for target in targets:
            if target in data:
                dependency_edges.add((p, target))
                if target not in chosen:
                    add(target, 'strict_S3_static_or_dynamic_import_dependency')
                    pending.append(target)

    forbidden = [p for p in chosen if re_forbidden(p)]
    if forbidden:
        raise ValueError('Non-S3 experiment unexpectedly selected: ' + repr(forbidden))
    directory.mkdir(parents=True)
    records = []
    for p, role in sorted(chosen.items()):
        destination = directory / p
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data[p])
        records.append(dict(rows[p], role=role))
    def generated(name, blob):
        (directory / name).write_bytes(blob)
        records.append(dict(path=name, source='S3_packaging_metadata', bytes=len(blob), sha256=sha(blob)))
    generated('README_CN.txt', (HERE / 'README_CN.txt').read_bytes())
    generated('build_s3_bundle.py', Path(__file__).read_bytes())
    generated('verify_package.py', data['verify_package.py'])
    generated('ENVIRONMENT_SNAPSHOT.json', data['ENVIRONMENT_SNAPSHOT.json'])
    generated('DEPENDENCY_ROLES.csv', csv_bytes([dict(path=p, role=r) for p,r in sorted(chosen.items())], ['path','role']))
    generated('IMAGENET_IMPORT_EDGES.csv', csv_bytes([dict(importer=a, dependency=b) for a,b in sorted(dependency_edges)], ['importer','dependency']))
    for filename, column in [('ABSOLUTE_PATHS.csv','file'), ('RECIPE_SOURCE_CHECKS.csv','record'), ('ENTRYPOINTS.csv','path')]:
        reader = csv.DictReader(io.StringIO(data[filename].decode()))
        filtered = [r for r in reader if r[column] in chosen]
        generated(filename, csv_bytes(filtered, reader.fieldnames))
    reader = csv.DictReader(io.StringIO(data['EXTERNAL_INPUTS.csv'].decode()))
    filtered = []
    for row in reader:
        refs = [p for p in row['referred_by'].split('|') if p in chosen]
        if refs:
            row['referred_by'] = '|'.join(refs)
            if row['included_as'] not in chosen: row['included_as'] = ''
            filtered.append(row)
    generated('EXTERNAL_INPUTS.csv', csv_bytes(filtered, reader.fieldnames))
    reader = csv.DictReader(io.StringIO(data['EXCLUDED_METADATA.csv'].decode()))
    filtered = [r for r in reader if '/image_lianghu/metadata/' in r['source']]
    generated('EXCLUDED_METADATA.csv', csv_bytes(filtered, reader.fieldnames))
    manifest = dict(schema=1, name=NAME, scope='STRICT_S3_U3_WORKFLOWS_WITH_SHARED_DEPENDENCIES',
        source_archive_sha256=sha(args.input_zip.read_bytes()), files=records)
    (directory/'MANIFEST.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    spec = importlib.util.spec_from_file_location('_s3_package_verify', directory/'verify_package.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checks = module.verify(directory)
    checks.update(non_S3_experiment_paths='ABSENT', source_snapshot_bytes='UNCHANGED',
                  original_source_files=len(chosen))
    (directory/'VERIFICATION.json').write_text(json.dumps(checks, indent=2)+'\n')
    if checks['status'] != 'PASS': raise ValueError(checks)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(directory.rglob('*')):
            if path.is_file(): z.write(path, str(Path(NAME)/path.relative_to(directory)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in records:
            assert sha(z.read(NAME+'/'+row['path'])) == row['sha256']
    checksum = sha(archive.read_bytes())
    (output/(archive.name+'.sha256')).write_text(checksum+'  '+archive.name+'\n')
    print(json.dumps(dict(archive=str(archive), bytes=archive.stat().st_size, sha256=checksum, verification=checks), indent=2))


def re_forbidden(path):
    low = path.lower()
    return any(s in low for s in ('/local4_', '/local_precision_route_', '/imagenet_conservative_precision_',
        'train_s8_', 'evaluate_s8_', 'canonical_s8_adapter', 's8_exact_', 'run_bulk_exact_s8',
        'train_attention_activation_s8_', 'probe_mlp_activation_mixed_', 'probe_s8_'))


if __name__ == '__main__':
    main()
