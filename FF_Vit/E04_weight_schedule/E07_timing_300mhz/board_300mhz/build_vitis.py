"""Build an isolated standalone PS application from the E07 300-MHz XSA."""

import os
import shutil
from pathlib import Path

import vitis


root = Path(__file__).resolve().parent
xsa = Path(os.environ["E07_XSA"]).resolve()
workspace = root / "workspace"
if workspace.exists():
    raise RuntimeError(f"refusing to overwrite existing workspace: {workspace}")

client = vitis.create_client()
client.set_workspace(path=str(workspace))
advanced = client.create_advanced_options_dict(dt_overlay="0")
platform = client.create_platform_component(
    name="e07_platform",
    hw_design=str(xsa),
    os="standalone",
    cpu="psu_cortexa53_0",
    domain_name="standalone_psu_cortexa53_0",
    generate_dtb=False,
    advanced_options=advanced,
    architecture="64-bit",
    compiler="gcc",
)
domain = platform.get_domain(name="standalone_psu_cortexa53_0")
domain.set_lib(
    lib_name="xilffs",
    path="/opt/vivado/2025.1/Vitis/data/embeddedsw/lib/sw_services/xilffs_v5_4",
)
platform.build()

app = client.create_app_component(
    name="e07_inference",
    platform=str(workspace / "e07_platform/export/e07_platform/e07_platform.xpfm"),
    domain="standalone_psu_cortexa53_0",
    template="empty_application",
)
app_src = workspace / "e07_inference/src"
for old in app_src.glob("*.c"):
    old.unlink()
shutil.copy2(root / "src/main.c", app_src / "main.c")
shutil.copy2(root / "src/weight_layout.h", app_src / "weight_layout.h")
app.build()
vitis.dispose()
