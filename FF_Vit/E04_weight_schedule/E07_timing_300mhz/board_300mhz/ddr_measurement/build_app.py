"""Create a new PS component in an independent workspace; do not rebuild platform."""
import shutil
from pathlib import Path
import vitis

root = Path(__file__).resolve().parent
board = root.parent
workspace = root / "workspace"
component = workspace / "e07_ddr_measure"
if component.exists():
    raise RuntimeError(f"refusing to overwrite existing component: {component}")
client = vitis.create_client()
client.set_workspace(path=str(workspace))
app = client.create_app_component(
    name="e07_ddr_measure",
    platform=str(board / "workspace/e07_platform/export/e07_platform/e07_platform.xpfm"),
    domain="standalone_psu_cortexa53_0", template="empty_application")
app_src = component / "src"
for source in (root / "src").glob("*.[ch]"):
    shutil.copy2(source, app_src / source.name)
shutil.copy2(board / "src/weight_layout.h", app_src / "weight_layout.h")
app.build()
vitis.dispose()
