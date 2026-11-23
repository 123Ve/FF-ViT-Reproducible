"""Build a new immutable portable ZIP, or verify every extracted package file.

Python3.11+ standard library only. --check-only performs no network, board,
SD write, or result creation. SHA256SUMS.json remains the SD-only manifest;
PACKAGE_SHA256SUMS.json covers the archive payload except itself.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import sys
sys.dont_write_bytecode=True
import uuid
import zipfile

ROOT=pathlib.Path(__file__).resolve().parent
MANIFEST='PACKAGE_SHA256SUMS.json'


class PackageError(RuntimeError):
    pass


def require_python(version=None):
    if (sys.version_info if version is None else version)<(3,11):
        raise PackageError('Python3.11+ required')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        while block:=stream.read(1024*1024):h.update(block)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')


def safe_name(name):
    p=pathlib.PurePosixPath(name)
    if not name or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or str(p)!=name:
        raise PackageError('unsafe package path: '+name)
    return name


def verify_package(root=ROOT,profile='strict18'):
    require_python();root=pathlib.Path(root).resolve()
    # Do not import unverified runtime code to parse/check its own manifest.
    def unique_pairs(items):
        result={}
        for key,value in items:
            if key in result:raise PackageError('duplicate manifest key')
            result[key]=value
        return result
    manifest=json.loads((root/MANIFEST).read_text(encoding='utf-8'),object_pairs_hook=unique_pairs)
    if not isinstance(manifest,dict) or not manifest:raise PackageError('empty/malformed package manifest')
    for name in manifest:safe_name(name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and
            p.relative_to(root).as_posix()!=MANIFEST}
    if set(manifest)!=actual:
        raise PackageError('package file inventory differs from manifest: '+json.dumps(dict(
            missing=sorted(set(manifest)-actual),unexpected=sorted(actual-set(manifest))),ensure_ascii=True))
    for name,expected in manifest.items():
        safe_name(name);path=root/name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise PackageError('missing/unsafe package file: '+name)
        if path.stat().st_size!=expected['bytes'] or file_hash(path)!=expected['sha256']:
            raise PackageError('package size/SHA mismatch: '+name)
    from host import collect
    infos={name:collect.preflight(root,name) for name in collect.profiles.ALL_PROFILES}
    info=infos[profile]
    if any(i['identity']['artifact_hashes']!=infos['strict18']['identity']['artifact_hashes'] for i in infos.values()):
        raise PackageError('profiles disagree on frozen artifacts')
    return dict(**collect.profiles.metadata(profile),status='WHOLE_PACKAGE_PREFLIGHT_PASS',file_count=len(manifest)+1,
        firmware_sha256=info['identity']['firmware_sha256'],physical_startup='NOT_RUN',
        power_acceptance='NOT_RUN',copied_SD='NOT_CHECKED')


def selected_files(root):
    from host import collect
    identities=[collect.preflight(root,profile)['identity'] for profile in collect.profiles.ALL_PROFILES]
    identity=identities[0]
    paths=set()
    for name in ('FIRMWARE_IDENTITY.json','SHA256SUMS.json','README_CN.txt','PROTOCOL.md',
                 'Run-PowerRetest.ps1','package.py','build_firmware.py','build_platform.py',
                 'REPAIR_NOTES_CN.txt','REPAIR.diff','DIAGNOSTIC17_NOTES_CN.txt','DIAGNOSTIC17.diff',
                 'FIRMWARE_IDENTITY_DIAG17.json','SHA256SUMS_DIAG17.json',
                 'FIRMWARE_IDENTITY_DIAG16.json','SHA256SUMS_DIAG16.json',
                 'RECORD_COMPLETE_NOTES_CN.txt','RECORD_COMPLETE.diff',
                 'CLOCK_HANDSHAKE_NOTES_CN.txt','CLOCK_HANDSHAKE.diff',
                 'THERMAL_CAPTURE_NOTES_CN.txt','THERMAL_CAPTURE.diff'):
        paths.add(root/name)
    for directory in ('host','firmware','tests','SD_CARD','SD_CARD_DIAG17','SD_CARD_DIAG16'):
        paths.update(p for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for current in identities:
        build=root/current['build_directory']
        paths.update(p for p in build.iterdir() if p.is_file() and p.suffix!='.o')
    paths.add(root/'build/platform_configuration.json')
    audit=root/'execution/diagnostic17_20261122'
    for name in ('red-firmware.log','green-firmware.log','red-host-analysis.log','green-host-analysis.log',
                 'build-strict18.log','build-diagnostic17.log','red-package.log','red-package-cli.log','red-replay.log',
                 'fix1-red.log','fix1-red-load.log','fix1-red-response.log','fix1-green.log','r6-red.log','r6-green.log','r7-green.log','full-suite.log'):
        paths.add(audit/name)
    for name in ('README.txt','red.log','adc-quality-red.log','focused.log','build-strict18.log','build-diagnostic17.log','build-diagnostic16.log'):
        paths.add(root/'execution/record_complete_20261122'/name)
    for name in ('EVIDENCE.txt','red.log','focused.log','build-strict18.log','build-diagnostic17.log','build-diagnostic16.log'):
        paths.add(root/'execution/clock_handshake_20261122'/name)
    for name in ('EVIDENCE.txt','red.log','focused.log'):
        paths.add(root/'execution/thermal_capture_20261122'/name)
    provenance=collect.read_json(root/identity['build_directory']/'provenance.json')
    for name in provenance['sampler_startup_inputs']:paths.add(root/name)
    for path in paths:
        if not path.is_file() or path.is_symlink():raise PackageError('missing/unsafe selected file: '+str(path))
        safe_name(path.relative_to(root).as_posix())
    return sorted(paths),identity


def dependencies(identity):
    payload=identity['canonical_payload']
    return dict(measurement_profile=identity['measurement_profile'],schema='e07-build-dependencies-v1',physical_status='NOT_RUN',
        instructions='Rebuild in a separate repository copy preserving validation/cloud_power_retest_20261121/independent_sampler layout. See README_CN.txt. No PL synthesis is required.',
        compiler=payload['compiler'],compiler_version=payload['compiler_version'],
        toolchain='AMD Vitis/Bootgen 2025.1 Linux installation; Python vitis module for build_platform.py; host cc for native C tests',
        frozen_vendor_directory='Cloud_test/e07/vendor/e07_base',
        frozen_artifact_sha256=identity['artifact_hashes'],
        fsbl_sha256=payload['fsbl_sha256'],pmufw_sha256=payload['pmufw_sha256'],
        service_BSP='Cloud_test/e07/build/e06_net_workspace/e06_net_platform/export/e06_net_platform/sw/standalone_psu_cortexa53_0',
        sampler_BSP='build/platform_workspace/sampler_platform/export/sampler_platform/sw/sampler_a53_1',
        sampler_generation='build_platform.py: CPU psu_cortexa53_1, standalone,64-bit EL3; USE_AMP=1 and explicit proc flags in source',
        required_exact_BSP_libraries=payload['bsp_libraries'],required_exact_BSP_headers=payload['bsp_headers'],
        compiler_options=payload['options'],
        complete_commands=identity['build_directory']+'/commands.json',
        shipped_raw_bitstream=False,shipped_raw_XSA=False,
        qualification='Frozen bit/XSA were hashed during the successful offline firmware build and bound in canonical identity and BOOT; extraction preflight cannot rehash absent raw files. Obtain exact referenced inputs to reproduce.')


def build_archive(root,archive):
    require_python();root=pathlib.Path(root).resolve();archive=pathlib.Path(archive).resolve()
    if archive.exists():raise FileExistsError('archive already exists: '+str(archive))
    files,identity=selected_files(root)
    data={p.relative_to(root).as_posix():p.read_bytes() for p in files}
    data['BUILD_DEPENDENCIES.json']=json_bytes(dependencies(identity))
    diagnostic=json.loads(data['FIRMWARE_IDENTITY_DIAG17.json'])
    data['BUILD_DEPENDENCIES_DIAG17.json']=json_bytes(dependencies(diagnostic))
    data['BUILD_DEPENDENCIES_DIAG16.json']=json_bytes(dependencies(json.loads(data['FIRMWARE_IDENTITY_DIAG16.json'])))
    manifest={name:dict(bytes=len(value),sha256=digest(value)) for name,value in sorted(data.items())}
    data[MANIFEST]=json_bytes(manifest)
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,value in sorted(data.items()):z.writestr(name,value)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise PackageError('ZIP CRC failure')
        if set(z.namelist())!=set(data):raise PackageError('ZIP inventory mismatch')
        for name,entry in manifest.items():
            value=z.read(name)
            if len(value)!=entry['bytes'] or digest(value)!=entry['sha256']:
                raise PackageError('ZIP content hash mismatch: '+name)
    return dict(archive=str(archive),bytes=archive.stat().st_size,sha256=digest(archive.read_bytes()),
        file_count=len(data),firmware_sha256=identity['firmware_sha256'],CRC='PASS',per_file_SHA256='PASS',
        physical_startup='NOT_RUN',power_acceptance='NOT_RUN')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check-only',action='store_true',help='verify whole extracted package before collector use')
    action.add_argument('--build',action='store_true',help='create uniquely named new ZIP; never overwrite')
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--diagnostic17',action='store_true',help='display diagnostic17 identity during verification')
    scope.add_argument('--diagnostic16',action='store_true',help='display diagnostic16 identity during verification')
    parser.add_argument('--root',type=pathlib.Path,default=ROOT)
    parser.add_argument('--output-zip',type=pathlib.Path)
    args=parser.parse_args(argv);require_python()
    if args.check_only:result=verify_package(args.root,"diagnostic16" if args.diagnostic16 else "diagnostic17" if args.diagnostic17 else "strict18")
    else:
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        archive=args.output_zip or args.root/'archives'/f'E07_Independent_Power_v1_{stamp}_{uuid.uuid4().hex[:8]}.zip'
        result=build_archive(args.root,archive)
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,ValueError,KeyError,TypeError) as exc:
        print('FAILED: '+str(exc),file=sys.stderr);sys.exit(2)
