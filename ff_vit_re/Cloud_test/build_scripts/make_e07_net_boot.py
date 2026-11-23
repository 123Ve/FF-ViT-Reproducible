"""Package copied, unchanged E07 PL with the new network/replay application."""
from pathlib import Path
from Cloud_test.build_scripts.make_e06_net_boot import make_boot_config, build_boot, _atomic_json

root = Path(__file__).resolve().parents[1] / 'e07'
vendor = root / 'vendor/e07_base'
config = make_boot_config(vendor / 'fsbl.elf', vendor / 'pmufw.elf',
    vendor / 'design_1_wrapper.bit', root / 'build/e06_net_workspace/e06_net/build/e06_net.elf',
    root / 'boot/BOOT_E07_NET.BIN', firmware_identity=root / 'build/e06_net_firmware_identity.json',
    cloud_root=root)
manifest = build_boot(config)
manifest.update(model='E07', phase='E07_PHYSICAL', schema='fvit-e07-net-boot-v1',
                physical_status='NOT_RUN', input_protocol='verified fixed preprocessed tensor replay')
_atomic_json(config.manifest, manifest)
print('E07_BOOT=' + str(config.output))
