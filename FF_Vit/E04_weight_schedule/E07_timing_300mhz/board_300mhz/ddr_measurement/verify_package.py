"""Read-only release verification, including actual embedded boot partitions."""
import csv
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy"
ACCEPTED = ROOT.parent / "deploy"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def partitions(path):
    data = path.read_bytes()
    word = lambda offset: struct.unpack_from("<I", data, offset)[0]
    assert word(0x20) == 0xaa995566 and word(0x24) == 0x584c4e58
    offset = word(0x9c)
    result = []
    while offset:
        length = word(offset + 0x08) * 4
        start = word(offset + 0x20) * 4
        result.append(data[start:start + length])
        assert len(result[-1]) == length
        offset = word(offset + 0x0c) * 4
        assert len(result) <= 4
    return result


def main():
    checks = []
    with (DEPLOY / "manifest.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            path = DEPLOY / row["file"]
            assert path.stat().st_size == int(row["bytes"]), path
            assert digest(path) == row["sha256"], path
            checks.append("manifest " + row["file"])
    identity = json.loads((DEPLOY / "identity.json").read_text())
    for group in ("frozen_files", "source_files"):
        for name, expected in identity[group].items():
            assert digest(Path(name)) == expected, name
            checks.append(group + " " + name)
    for name, expected in json.loads((ROOT / "workspace/e07_ddr_measure/build/build_identity.json").read_text()).items():
        assert digest(Path(name)) == expected, name
        checks.append("build_identity " + name)
    for name in ("fsbl.elf", "pmufw.elf", "design_1_wrapper.bit", "weights.bin", "input.bin", "output.bin"):
        assert digest(DEPLOY / name) == digest(ACCEPTED / name), name
        checks.append("unchanged " + name)
    assert digest(DEPLOY / "e07_ddr_measure.elf") == digest(ROOT / "workspace/e07_ddr_measure/build/e07_ddr_measure.elf")
    original, new = partitions(ACCEPTED / "BOOT.BIN"), partitions(DEPLOY / "BOOT.BIN")
    assert len(original) == len(new) == 3
    assert original[0] == new[0], "embedded FSBL/PMU firmware differs"
    assert original[1] == new[1], "embedded PL payload differs"
    assert original[2] != new[2], "new PS app is missing"
    checks += ["embedded FSBL/PMU identical", "embedded PL identical", "new PS app differs"]
    print(json.dumps({"checks_passed": len(checks), "checks": checks,
                      "hardware_test_status": "PENDING: board run and counter reconciliation required",
                      "boot_sha256": digest(DEPLOY / "BOOT.BIN")}, indent=2))


if __name__ == "__main__":
    main()
