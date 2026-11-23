"""Package a fresh E07 DDR test image, with no regenerated PL or boot firmware."""
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOARD = ROOT.parent
E07 = BOARD.parent
ACCEPTED = BOARD / "deploy"
DEPLOY = ROOT / "deploy"
EXPECTED_BIT = "2fedb6d70a0916fc9aebfdf3141008690685c0dbd1b5bab0ae58821564ef1037"
EXPECTED_BOOT = "7a52f3370ba076a97e18b3d833da0d108a5ed7d5f656e52c39f53817f35913dc"
EXPECTED_POWER_BOOT = "08ed5689b4bde53b4d7580ff77e46535f7be8a720e5e11e98096dd8294060983"
EXPECTED_HLS = "ae9aba847cb8fdffdba289915acd5bc3347a6fd5e9426679e708fbd6cf88a06a"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    frozen = {
        ACCEPTED / "design_1_wrapper.bit": EXPECTED_BIT,
        ACCEPTED / "BOOT.BIN": EXPECTED_BOOT,
        BOARD / "deploy_power/BOOT.BIN": EXPECTED_POWER_BOOT,
        E07 / "src/block0.cpp": EXPECTED_HLS,
    }
    for path, expected in frozen.items():
        if digest(path) != expected:
            raise RuntimeError(f"accepted identity mismatch: {path}")
    if DEPLOY.exists():
        raise RuntimeError(f"refusing to overwrite deployment: {DEPLOY}")
    sources = {name: ACCEPTED / name for name in (
        "fsbl.elf", "pmufw.elf", "design_1_wrapper.bit", "weights.bin", "input.bin", "output.bin", "clock.txt")}
    sources.update({
        "e07_ddr_measure.elf": ROOT / "workspace/e07_ddr_measure/build/e07_ddr_measure.elf",
        "README.txt": ROOT / "README.txt",
        "summarize_ddr.py": ROOT / "summarize_ddr.py",
    })
    for source in sources.values():
        if not source.is_file():
            raise FileNotFoundError(source)
    DEPLOY.mkdir()
    for name, source in sources.items():
        shutil.copy2(source, DEPLOY / name)
    (DEPLOY / "boot.bif").write_text(
        "the_ROM_image:\n{\n"
        " [bootloader, destination_cpu=a53-0] fsbl.elf\n"
        " [pmufw_image] pmufw.elf\n"
        " [destination_device=pl] design_1_wrapper.bit\n"
        " [destination_cpu=a53-0, exception_level=el-3] e07_ddr_measure.elf\n}\n")
    subprocess.run(["/opt/vivado/2025.1/Vivado/bin/bootgen", "-arch", "zynqmp",
                    "-image", "boot.bif", "-o", "BOOT.BIN", "-w", "on"], cwd=DEPLOY, check=True)
    if not (DEPLOY / "BOOT.BIN").is_file() or (DEPLOY / "BOOT.BIN").stat().st_size < 10_000_000:
        raise RuntimeError("boot image missing or unexpectedly short")
    identity = {
        "scope": "PS-only DDR-controller APM; hardware measurement pending",
        "unchanged_bitstream_sha256": EXPECTED_BIT,
        "new_boot_sha256": digest(DEPLOY / "BOOT.BIN"),
        "frozen_files": {str(p): h for p, h in frozen.items()},
        "source_files": {str(p): digest(p) for p in sorted((ROOT / "src").glob("*.[ch]"))},
        "bsp_xparameters_sha256": digest(BOARD / "workspace/e07_platform/export/e07_platform/sw/standalone_psu_cortexa53_0/include/xparameters.h"),
        "apm_base": "0xFD0B0000", "slot_weight": 3, "slot_dma": 4,
        "metric_count_scale": 1, "frames_per_repeat": 100, "repetitions": 10,
    }
    for name in ("fsbl.elf", "pmufw.elf", "design_1_wrapper.bit", "weights.bin", "input.bin", "output.bin"):
        if digest(DEPLOY / name) != digest(ACCEPTED / name):
            raise RuntimeError(f"reuse check failed: {name}")
    (DEPLOY / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    with (DEPLOY / "manifest.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "bytes", "sha256", "source"])
        for path in sorted(DEPLOY.iterdir()):
            if path.is_file() and path.name != "manifest.csv":
                writer.writerow([path.name, path.stat().st_size, digest(path), str(sources.get(path.name, "generated"))])
    print(json.dumps(identity, indent=2))


if __name__ == "__main__":
    main()
