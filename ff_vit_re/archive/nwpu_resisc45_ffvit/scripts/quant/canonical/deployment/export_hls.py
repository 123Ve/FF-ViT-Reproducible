#!/usr/bin/env python3
"""Export canonical T=196 deployment files into a new or empty directory.

Project mode requires explicit ROM and block0 templates. Bundle mode resolves
every input inside its supplied root, using the canonical artifact layout.
Only scripts/lib, NumPy, PyTorch, and a C++17 compiler are runtime dependencies.
The exporter has no install operation and never writes to its input paths.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import numpy as np
import torch

if __package__:
    from ..lib import hls_abi
    from ..lib.frozen_quantization import quantize_checkpoint
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lib import hls_abi
    from lib.frozen_quantization import quantize_checkpoint


# (packing name, exact Stage producer, source file, audited shape)
ARRAYS = (
    ("attn_ln_scalars", "stage4k_exact_attn_outer", "ln1_scalars.npy", (12, 7)),
    ("attn_lnw", "stage4k_exact_attn_outer", "ln1_lnw.npy", (12, 192)),
    ("attn_lnb", "stage4k_exact_attn_outer", "ln1_lnb.npy", (12, 192)),
    ("attn_rsqrt", "stage4k_exact_attn_outer", "ln1_rsqrt_table.npy", (12, 128)),
    ("qq_scalars", "stage4k2_refined_qkv", "qq_scalars.npy", (12, 4)),
    ("kq_scalars", "stage4k2_refined_qkv", "kq_scalars.npy", (12, 4)),
    ("vq_scalars", "stage4k2_refined_qkv", "vq_scalars.npy", (12, 4)),
    ("qq_table", "stage4k2_refined_qkv", "qq_table.npy", (12, 64)),
    ("kq_table", "stage4k2_refined_qkv", "kq_table.npy", (12, 64)),
    ("vq_table", "stage4k2_refined_qkv", "vq_table.npy", (12, 64)),
    ("aq_scalars", "stage4l_exact_softmax_aq", "aq_scalars.npy", (12, 4)),
    ("aq_table", "stage4l_exact_softmax_aq", "aq_table.npy", (12, 64)),
    ("softmax_scalars", "stage4l_exact_softmax_aq", "softmax_scalars.npy", (12, 14)),
    ("softmax_exp", "stage4l_exact_softmax_aq", "softmax_exp_table.npy", (12, 32)),
    ("softmax_recip1", "stage4l_exact_softmax_aq", "softmax_recip_table_one.npy", (12, 64)),
    ("softmax_recip2", "stage4l_exact_softmax_aq", "softmax_recip_table_two_int8.npy", (12, 64)),
    ("attn_scalars", "stage4m_exact_encoder", "attn_scalars.npy", (12, 3)),
    ("mlp_scalars", "stage4m_exact_encoder", "mlp_scalars.npy", (12, 2)),
    ("mlp_ln_scalars", "stage4m_exact_encoder", "ln2_scalars.npy", (12, 7)),
    ("mlp_lnw", "stage4m_exact_encoder", "ln2_lnw.npy", (12, 192)),
    ("mlp_lnb", "stage4m_exact_encoder", "ln2_lnb.npy", (12, 192)),
    ("mlp_rsqrt", "stage4m_exact_encoder", "ln2_rsqrt_table.npy", (12, 128)),
    ("ge_scalars", "stage4f_exact_gelu", "ge_scalars.npy", (12, 4)),
    ("ge_table", "stage4f_exact_gelu", "ge_table.npy", (12, 64)),
)
PATCH_RAW = {
    "PATCH_WEIGHT": ("patch_weight_int8.pt", (192, 768)),
    "PATCH_BIAS": ("patch_bias_raw_int32.pt", (196, 192)),
    "PATCH_CLS": ("patch_cls_raw_int32.pt", (192,)),
}
PATCH_BANKS = {
    "PATCH_SCALARS": (4,), "PATCH_WEIGHT_BANK": (12, 24, 16, 32),
    "PATCH_BIAS_BANK": (2, 12, 98, 16), "PATCH_CLS_BANK": (12, 16),
}
HEAD_NAMES = ("HEAD_LN_SCALARS", "HEAD_LNW", "HEAD_LNB", "HEAD_RSQRT",
              "HEAD_WEIGHT", "HEAD_BIAS")
CHECKPOINT = "checkpoints/stage4j_attention_qat/best_attention_qat.pth"
ROM = "deployment/active/src/fixed_patch_head_rom.h"
BLOCK0 = "deployment/active/src/block0.cpp"
SAFE_HEAD = "artifacts/stage4o2_head_safe/generated_head_rom_safe.h"


def required_paths():
    return (
        CHECKPOINT, ROM, BLOCK0, SAFE_HEAD,
        "artifacts/stage3_patch_hls/patch_rom_banks.npz",
        *(f"artifacts/stage3_patch_hls/{filename}" for filename, _ in PATCH_RAW.values()),
        *(f"artifacts/{stage}/{filename}" for _, stage, filename, _ in ARRAYS),
    )


@dataclass(frozen=True)
class ExportInputs:
    """Explicit mapping from stable bundle names to runtime input files."""

    files: tuple[tuple[str, Path], ...]

    def __post_init__(self):
        names = [name for name, _ in self.files]
        if len(names) != len(set(names)) or set(names) != set(required_paths()):
            raise ValueError("ExportInputs must contain each required input exactly once")
        object.__setattr__(self, "files", tuple(
            (name, Path(path).resolve()) for name, path in self.files))

    @classmethod
    def from_project(cls, project_root, *, rom_template, block0_template):
        root = Path(project_root).resolve()
        files = []
        for name in required_paths():
            if name == ROM:
                path = Path(rom_template)
            elif name == BLOCK0:
                path = Path(block0_template)
            else:
                path = Path(name.split("/", 1)[1])
            files.append((name, path if path.is_absolute() else root / path))
        return cls(tuple(files))

    @classmethod
    def from_bundle(cls, bundle_root):
        root = Path(bundle_root).resolve()
        files = tuple((name, root / name) for name in required_paths())
        for _, path in files:
            if not path.resolve().is_relative_to(root):
                raise ValueError(f"Bundle input escapes bundle root: {path}")
        return cls(files)

    def relative_inputs(self):
        """Expose the complete copy list as (source, canonical destination)."""
        return tuple((path, name) for name, path in self.files)


def _array_span(text, name):
    matches = list(re.finditer(rf"(?m)^const\s+[^\n;]+\b{re.escape(name)}\s*\[[^;=]*=", text))
    if len(matches) != 1:
        raise ValueError(f"Expected one declaration of {name}, found {len(matches)}")
    start = matches[0].start()
    begin = text.index("{", matches[0].end())
    depth = 0
    for index in range(begin, len(text)):
        depth += int(text[index] == "{") - int(text[index] == "}")
        if depth == 0:
            end = index + 1
            if text[end:].lstrip()[:1] != ";":
                raise ValueError(f"Missing semicolon for {name}")
            return start, begin, end, text.index(";", end) + 1
    raise ValueError(f"Unterminated declaration: {name}")


def _install_array(text, name, values):
    # Keep the established ROM layout/whitespace while replacing every value.
    _, begin, end, _ = _array_span(text, name)
    values = np.asarray(values).reshape(-1)
    literals = list(re.finditer(r"-?\d+", text[begin:end]))
    if len(literals) != values.size:
        raise ValueError(f"{name}: template has {len(literals)} entries, source has {values.size}")
    iterator = iter(values)
    body = re.sub(r"-?\d+", lambda _: str(int(next(iterator))), text[begin:end])
    return text[:begin] + body + text[end:]


def _canonical_rom(files):
    text = files[ROM].read_text(encoding="utf-8")
    stage3 = "artifacts/stage3_patch_hls/"
    with np.load(files[stage3 + "patch_rom_banks.npz"], allow_pickle=False) as banks:
        for name, shape in PATCH_BANKS.items():
            if banks[name].shape != shape:
                raise ValueError(f"Invalid {name} shape: {banks[name].shape}")
            text = _install_array(text, name, banks[name])
    for name, (filename, shape) in PATCH_RAW.items():
        values = torch.load(files[stage3 + filename], map_location="cpu", weights_only=True).numpy()
        if values.shape != shape:
            raise ValueError(f"Invalid {name} shape: {values.shape}")
        text = _install_array(text, name, values)

    # Head is deliberately installed after all seven Patch arrays. Never
    # reapply Stage4P's old-ROM prefix when installing the safe classifier.
    safe = files[SAFE_HEAD].read_text(encoding="utf-8")
    for name in HEAD_NAMES:
        start, _, _, end = _array_span(text, name)
        safe_start, _, _, safe_end = _array_span(safe, name)
        text = text[:start] + safe[safe_start:safe_end] + text[end:]
    return text


def _canonical_block0(path):
    text = path.read_text(encoding="utf-8")
    for bits, name, target in ((15, "sum", "ap_int<15>  "),
                               (30, "divc", "ap_int<30>  "),
                               (7, "mu", "ap_int<7>   "),
                               (7, "cursor", "ap_uint<7>  ")):
        pattern = rf"(?m)^typedef\s+ap_u?int<\d+>\s+__head_ln_{name}_t;"
        text, count = re.subn(pattern, f"typedef {target}__head_ln_{name}_t;", text)
        if count != 1:
            raise ValueError(f"Expected one active Head {name} typedef")
    # Reject explicit exits anywhere in the inference body, including after
    # another statement on the same line. Helper functions may return normally.
    # Mask comments/literals before balancing braces; keep newlines so pragma
    # filtering cannot accidentally swallow executable statements.
    code = re.sub(
        r"""//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'""",
        lambda match: re.sub(r"[^\n]", " ", match.group(0)), text, flags=re.S,
    )
    definition = re.search(r"\bvoid\s+vit_block_top\s*\([^)]*\)\s*\{", code)
    if definition is None:
        raise ValueError("block0 template has no vit_block_top definition")
    begin = definition.end()
    depth = 1
    for end in range(begin, len(code)):
        depth += int(code[end] == "{") - int(code[end] == "}")
        if depth == 0:
            break
    else:
        raise ValueError("Unterminated vit_block_top definition")
    body = re.sub(r"(?m)^[ \t]*#pragma\b[^\n]*", "", code[begin:end])
    if re.search(r"\breturn\b", body):
        raise ValueError("vit_block_top contains an early return")
    return text


def _file_info(path):
    data = path.read_bytes()
    return {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def export_hls(inputs: ExportInputs, output_dir, *, cxx="g++"):
    """Generate and independently verify the canonical deployment bundle."""
    output = Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(f"Output must be a new or empty directory: {output}")
    files = dict(inputs.files)
    for path in files.values():
        if not path.is_file():
            raise FileNotFoundError(f"Required exporter input missing: {path}")
    arrays = {}
    for name, stage, filename, shape in ARRAYS:
        arrays[name] = np.load(files[f"artifacts/{stage}/{filename}"], allow_pickle=False)
        if arrays[name].shape != shape:
            raise ValueError(f"{name}: expected {shape}, got {arrays[name].shape}")
    rom = _canonical_rom(files)
    block0 = _canonical_block0(files[BLOCK0])
    qblocks = quantize_checkpoint(files[CHECKPOINT])
    weights = b"".join(hls_abi.build_attn_struct(q, arrays, b) +
                       hls_abi.build_mlp_struct(q, arrays, b)
                       for b, q in enumerate(qblocks))
    if len(weights) != hls_abi.WEIGHTS_BIN_BYTES:
        raise ValueError(f"Unexpected ABI weights size: {len(weights)}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "weights.bin").write_bytes(weights)
    hls_abi.write_fields(output / "weights_fields.bin", qblocks, arrays)
    packer_source = Path(__file__).resolve().parents[1] / "lib/pack_weights_hls.cpp"
    with tempfile.TemporaryDirectory(prefix="canonical-hls-packer-") as temp:
        executable = Path(temp) / "pack_weights_hls"
        subprocess.run([str(cxx), "-std=c++17", "-O2", str(packer_source), "-o", str(executable)],
                       check=True, capture_output=True, text=True)
        subprocess.run([str(executable), str((output / "weights_fields.bin").resolve()),
                        str((output / "weights_hls.bin").resolve())],
                       check=True, capture_output=True, text=True)
    if weights != (output / "weights_hls.bin").read_bytes():
        raise RuntimeError("Python weights differ from independent C++ ABI packing")
    (output / "fixed_patch_head_rom.h").write_text(rom, encoding="utf-8")
    (output / "block0.cpp").write_text(block0, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "contract": {"tokens": 196, "signed_weight_range": [-4, 3],
                     "weights_bytes": hls_abi.WEIGHTS_BIN_BYTES,
                     "mlp_internal_padding_bytes": 4, "cpp_packing_equal": True},
        "rom_policy": {
            "patch_source": "artifacts/stage3_patch_hls",
            "head_source": SAFE_HEAD,
            "template_is_parameter_authority": False,
            "whole_file_comparison": (
                "All seven Patch arrays are replaced from Stage3, then all six Head arrays "
                "from Stage4O2. The audited active ROM still has stale raw PATCH_WEIGHT, "
                "PATCH_BIAS, and PATCH_CLS arrays; its whole-file hash is not canonical. "
                "Compare active banked Patch/scalars and Head arrays element-for-element."
            ),
        },
        "inputs": {name: _file_info(path) for name, path in sorted(files.items())},
        "outputs": {name: _file_info(output / name) for name in
                    ("weights.bin", "weights_fields.bin", "weights_hls.bin",
                     "fixed_patch_head_rom.h", "block0.cpp")},
    }
    (output / "deployment_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    roots = parser.add_mutually_exclusive_group(required=True)
    roots.add_argument("--project-root", type=Path)
    roots.add_argument("--bundle-root", type=Path)
    parser.add_argument("--rom-template", type=Path)
    parser.add_argument("--block0-template", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    if args.project_root:
        if args.rom_template is None or args.block0_template is None:
            parser.error("project mode requires --rom-template and --block0-template")
        inputs = ExportInputs.from_project(args.project_root, rom_template=args.rom_template,
                                           block0_template=args.block0_template)
    else:
        if args.rom_template is not None or args.block0_template is not None:
            parser.error("bundle mode resolves templates inside the bundle")
        inputs = ExportInputs.from_bundle(args.bundle_root)
    export_hls(inputs, args.output_dir, cxx=args.cxx)
    print("weights.bin bytes = 2772096\nPython packer == C++ struct packer")


if __name__ == "__main__":
    main()
