"""Build a separate PS-only power application against the accepted E07 platform."""

import shutil
from pathlib import Path

import vitis


root = Path(__file__).resolve().parent
workspace = root / "workspace"
component_dir = workspace / "e07_power"
if component_dir.exists():
    raise RuntimeError(f"refusing to overwrite existing component: {component_dir}")

client = vitis.create_client()
client.set_workspace(path=str(workspace))
app = client.create_app_component(
    name="e07_power",
    platform=str(workspace / "e07_platform/export/e07_platform/e07_platform.xpfm"),
    domain="standalone_psu_cortexa53_0",
    template="empty_application",
)
app_src = component_dir / "src"
for old in app_src.glob("*.c"):
    old.unlink()
for source in (root / "power_src").glob("*.[ch]"):
    shutil.copy2(source, app_src / source.name)
shutil.copy2(root / "src/weight_layout.h", app_src / "weight_layout.h")
app.build()
vitis.dispose()
