"""Assemble the E07 300-MHz SD-card boot image and deployment payload."""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BRANCH = ROOT.parent
WORKSPACE = ROOT / "workspace"
DEPLOY = ROOT / "deploy"

SOURCES = {
    "fsbl.elf": WORKSPACE / "e07_platform/export/e07_platform/sw/boot/fsbl.elf",
    "pmufw.elf": WORKSPACE / "e07_pmufw/build/e07_pmufw.elf",
    "design_1_wrapper.bit": WORKSPACE / "e07_platform/export/e07_platform/hw/sdt/e07_300mhz_wrapper.bit",
    "e07_inference.elf": WORKSPACE / "e07_inference/build/e07_inference.elf",
    "weights.bin": BRANCH / "inputs/weights.bin",
    "input.bin": BRANCH / "inputs/input.bin",
    "output.bin": BRANCH / "inputs/output.bin",
    "clock.txt": Path(os.environ.get("E07_CLOCK_FILE", str(BRANCH / "results/candidate02/clock.txt"))),
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    missing = [str(path) for path in SOURCES.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing boot inputs:\n" + "\n".join(missing))
    if DEPLOY.exists():
        raise RuntimeError(f"refusing to overwrite existing deployment: {DEPLOY}")
    DEPLOY.mkdir(parents=True)

    for name, source in SOURCES.items():
        shutil.copy2(source, DEPLOY / name)

    bif = DEPLOY / "boot.bif"
    bif.write_text(
        "the_ROM_image:\n"
        "{\n"
        "  [bootloader, destination_cpu=a53-0] fsbl.elf\n"
        "  [pmufw_image] pmufw.elf\n"
        "  [destination_device=pl] design_1_wrapper.bit\n"
        "  [destination_cpu=a53-0, exception_level=el-3] e07_inference.elf\n"
        "}\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["bootgen", "-arch", "zynqmp", "-image", "boot.bif", "-o", "BOOT.BIN", "-w", "on"],
        cwd=DEPLOY,
        check=True,
    )

    files = sorted(path for path in DEPLOY.iterdir() if path.is_file())
    with (DEPLOY / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "bytes", "sha256", "source"])
        for path in files:
            source = SOURCES.get(path.name, "generated")
            writer.writerow([path.name, path.stat().st_size, digest(path), str(source)])


if __name__ == "__main__":
    main()
