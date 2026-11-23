# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


cloud_root = Path(SPECPATH).resolve().parent
project_root = cloud_root.parent

datas = [
    (str(cloud_root / 'boot/BOOT_E06_NET.manifest.json'), 'Cloud_test/boot'),
    (str(cloud_root / 'dashboard/templates'), 'Cloud_test/dashboard/templates'),
    (str(cloud_root / 'dashboard/static'), 'Cloud_test/dashboard/static'),
    (str(cloud_root / 'dashboard/static/plotly.min.js'), 'Cloud_test/dashboard/static'),
]

a = Analysis(
    [str(cloud_root / 'windows_launcher.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='E06_Cloud_GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='E06_Cloud_GUI',
)
