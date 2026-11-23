"""Build a hardware-targeted ZynqMP PMU firmware from the E07 platform."""

from pathlib import Path

import vitis


root = Path(__file__).resolve().parent
workspace = root / "workspace"
client = vitis.create_client()
client.set_workspace(path=str(workspace))
platform = client.get_component(name="e07_platform")
if platform is None:
    raise RuntimeError("e07_platform component is missing")
try:
    platform.get_domain(name="standalone_psu_pmu_0")
except Exception:
    platform.add_domain(
        cpu="psu_pmu_0",
        os="standalone",
        name="standalone_psu_pmu_0",
        display_name="standalone_psu_pmu_0",
    )
platform.build()

pmufw = client.create_app_component(
    name="e07_pmufw",
    platform=str(workspace / "e07_platform/export/e07_platform/e07_platform.xpfm"),
    domain="standalone_psu_pmu_0",
    template="zynqmp_pmufw",
)
pmufw.build()
vitis.dispose()
