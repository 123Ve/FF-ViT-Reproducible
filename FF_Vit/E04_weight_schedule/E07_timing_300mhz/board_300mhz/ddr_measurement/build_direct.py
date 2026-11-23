"""Reproduce the accepted Vitis compiler/linker recipe without the IDE server.

The Vitis API failed before component creation (client/server timeout). This
build uses the same compiler, -O0, SDT specs, BSP libraries and linker script.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOARD = ROOT.parent
BSP = BOARD / "workspace/e07_platform/export/e07_platform/sw/standalone_psu_cortexa53_0"
TOOL = Path("/opt/vivado/2025.1/Vitis/gnu/aarch64/lin/aarch64-none/bin")
BUILD = ROOT / "workspace/e07_ddr_measure/build"


def main():
    if BUILD.exists():
        raise RuntimeError(f"refusing to overwrite build: {BUILD}")
    BUILD.mkdir(parents=True)
    linker = BUILD / "lscript.ld"
    shutil.copy2(BOARD / "workspace/e07_inference/src/lscript.ld", linker)
    flags = ["-DSDT", f"-specs={BSP / 'Xilinx.spec'}", f"-I{BSP / 'include'}",
             f"-I{BOARD / 'src'}", "-Wall", "-Wextra", "-Werror", "-O0", "-g3", "-U__clang__"]
    gcc = str(TOOL / "aarch64-none-elf-gcc")
    obj = BUILD / "main.c.obj"
    elf = BUILD / "e07_ddr_measure.elf"
    commands = [
        [gcc, *flags, "-c", str(ROOT / "src/main.c"), "-o", str(obj)],
        [gcc, *flags, str(obj), "-o", str(elf), f"-Wl,-T,{linker}", f"-L{BSP / 'lib'}",
         f"-Wl,-Map,{BUILD / 'e07_ddr_measure.map'}", "-Wl,--start-group",
         "-lxilstandalone", "-lxiltimer", "-lxilffs", "-lxil", "-lgcc", "-lc", "-Wl,--end-group"],
        [str(TOOL / "aarch64-none-elf-size"), str(elf)],
    ]
    (BUILD / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    for command in commands:
        print("RUN", " ".join(command), flush=True)
        subprocess.run(command, check=True)
    paths = [linker, BSP / "Xilinx.spec", BSP / "include/xparameters.h",
             BOARD / "src/weight_layout.h", ROOT / "src/main.c", ROOT / "src/counter_math.h", elf]
    paths += sorted((BSP / "lib").glob("*.a"))
    manifest = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (BUILD / "build_identity.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
