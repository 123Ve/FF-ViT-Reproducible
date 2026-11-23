"""Build E07 in Cloud_test/e07 using the audited standalone network build policy."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Cloud_test.build_scripts.build_e06_net import make_build_config, prepare_workspace, build_with_vitis

root = Path(__file__).resolve().parents[1] / 'e07'
config = make_build_config(root / 'vendor/e07_base/e07_300mhz_wrapper.xsa',
                          root / 'build/e06_net_workspace', root / 'firmware', cloud_root=root)
prepare_workspace(config.workspace, False, cloud_root=root)
print('E07_NET_ELF=' + str(build_with_vitis(config)))
