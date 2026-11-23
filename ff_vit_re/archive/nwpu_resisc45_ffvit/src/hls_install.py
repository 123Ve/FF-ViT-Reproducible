"""Add an isolated HLS source/config without replacing any existing path."""
from pathlib import Path
import hashlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def inventory(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            result[str(path.relative_to(root))] = {
                'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    return result


def _patch(text):
    subprocess.run(['apply_patch'], input=text, text=True, check=True, capture_output=True)


def install(source, deployment, project):
    source, deployment, project = map(lambda p: Path(p).resolve(), (source, deployment, project))
    target = project / 'src_resisc45'
    config = project / 'flash_vit/hls_config_resisc45.cfg'
    component = project / 'flash_vit/vit_resisc45_bitaccurate'
    for path in (target, config, component):
        if path.exists():
            raise FileExistsError(path)
    if (source / 'block0.cpp').read_bytes() != (deployment / 'block0.cpp').read_bytes():
        raise ValueError('active block0.cpp differs from approved deployment snapshot')
    refs = sorted((deployment / 'refs').glob('*.bin'))
    if len(refs) != 16:
        raise ValueError('all 16 references are required')
    bins = [deployment / n for n in ('weights.bin', 'input.bin', 'output.bin')]
    for path in bins + refs + [deployment / 'fixed_patch_head_rom.h']:
        if not path.is_file():
            raise FileNotFoundError(path)
    target.mkdir(parents=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.glob('*.h')):
        if path.name != 'fixed_patch_head_rom.h':
            shutil.copy2(path, target / path.name)
    shutil.copy2(source / 'block0.cpp', target / 'block0.cpp')
    shutil.copy2(deployment / 'fixed_patch_head_rom.h', target / 'fixed_patch_head_rom.h')
    shutil.copy2(ROOT / 'hls/resisc45_csim_check.h', target / 'resisc45_csim_check.h')
    _patch(f'''*** Begin Patch
*** Update File: {target / 'block0.cpp'}
@@
 #include <stdlib.h>
+#include "resisc45_csim_check.h"
@@
-    if(flag) {{
+    flag = resisc45_check_all() && flag;
+    if(flag) {{
@@
     delete[] input_data; delete[] ref_logits;
 
-    return 0;
+    return flag ? 0 : 1;
 }}
*** End Patch
''')
    lines = ['part=xczu9eg-ffvb1156-2-i', '', '[hls]', 'flow_target=vivado',
             'clock=5ns', 'syn.top=vit_block_top', f'syn.file={target / "block0.cpp"}']
    lines += [f'tb.file={path}' for path in bins + refs]
    lines += ['csim.clean=true', 'csim.code_analyzer=0', 'csim.setup=0']
    _patch('*** Begin Patch\n*** Add File: ' + str(config) + '\n' +
           ''.join('+' + line + '\n' for line in lines) + '*** End Patch\n')
    return {'source': str(target), 'config': str(config), 'component': str(component)}
