"""Copy frozen E07 release artifacts and seed an isolated network application."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
E07 = Path('/home/user/Desktop/FF_Vit/E04_weight_schedule/E07_timing_300mhz')


def main():
    target = ROOT / 'e07'
    if target.exists():
        raise RuntimeError(f'Refusing to overwrite prepared sources: {target}')
    release = E07 / 'board_300mhz/deploy_power'
    inputs = {'xsa': E07 / 'results/candidate05/board_release/e07_300mhz_wrapper.xsa',
              'bitstream': release / 'design_1_wrapper.bit', 'fsbl': release / 'fsbl.elf',
              'pmufw': release / 'pmufw.elf',
              **{name: release / (name + '.bin') for name in ('weights', 'input', 'output')}}
    for path in inputs.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    manifest = {}
    for name, source in inputs.items():
        destination = target / 'vendor/e07_base' / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest[name] = dict(source_path=str(source), copied_path=str(destination),
                             bytes=destination.stat().st_size,
                             sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    (target / 'vendor/source_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for section in ('common', 'e06_net'):
        for source in (ROOT / 'firmware' / section).glob('*'):
            if source.suffix in ('.c', '.h'):
                destination = target / 'firmware' / section / source.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    network = target / 'firmware/e06_net/e06_network.c'
    network.write_text(network.read_text().replace('E06_PHYSICAL', 'E07_PHYSICAL').replace('\\"E06\\"', '\\"E07\\"'))
    config = target / 'firmware/e06_net/net_config.h'
    text = config.read_text().replace('"E06_PHYSICAL"', '"E07_PHYSICAL"').replace('"E06"', '"E07"')
    import re
    for key in ('weights', 'input', 'output', 'bitstream', 'xsa'):
        text = re.sub(r'(#define E06_' + key.upper() + r'_SHA256\s+\\\s*)"[a-f0-9]{64}"',
                      lambda m: m[1] + '"' + manifest[key]['sha256'] + '"', text)
    config.write_text(text)
    # E07 has no dedicated PL measurement APM; do not use a PS APM as a substitute.
    inference = target / 'firmware/e06_net/e06_inference.c'
    text = inference.read_text()
    text = text.replace('#include "xaxipmon.h"\n', '').replace('static XAxiPmon apm;\n', '')
    start = text.index('    XAxiPmon_Config *pc =')
    end = text.index('    if (!dc || !vc || !pc)', start)
    text = text[:start] + text[end:]
    text = text.replace('if (!dc || !vc || !pc)', 'if (!dc || !vc)')
    text = text.replace(' ||\n        XAxiPmon_CfgInitialize(&apm, pc, pc->BaseAddress) != XST_SUCCESS', '')
    start = text.index('    for (u8 i = 0; i < 10; ++i)')
    end = text.index('    return E06_OK;', start)
    text = text[:start] + text[end:]
    text = re.sub(r'^\s*XAxiPmon_(?:DisableMetricsCounter|ResetMetricCounter|EnableMetricsCounter)\(&apm\);\n', '\n', text, flags=re.M)
    inference.write_text(text)
    print(target)


if __name__ == '__main__':
    main()
