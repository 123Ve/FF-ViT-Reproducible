from pathlib import Path

cloud = Path(SPECPATH).resolve().parent
datas = [
    (str(cloud / 'e07/boot/BOOT_E07_NET_V2_5_FINAL.manifest.json'), 'Cloud_test/e07/boot'),
    (str(cloud / 'e07/vendor/e07_base/input.bin'), 'Cloud_test/e07/vendor/e07_base'),
    (str(cloud / 'dashboard/templates'), 'Cloud_test/dashboard/templates'),
    (str(cloud / 'dashboard/static'), 'Cloud_test/dashboard/static'),
]
a = Analysis([str(cloud / 'windows_e07_launcher.py')], pathex=[str(cloud.parent)],
             binaries=[], datas=datas, hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='E07_Cloud_GUI',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
          console=True, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name='E07_Cloud_GUI')
