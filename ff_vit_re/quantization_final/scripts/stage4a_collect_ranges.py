#!/usr/bin/env python3

import argparse
import json
import random
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets
from PIL import Image

from qat_weight3_hls196 import (
    HLS196DeiT,
    convert_backbone_to_qat,
    eval_transform,
)

from stage3_patch_hls_eval import (
    HLSPatchFrontend,
    HLSStage3Model,
)


class ManifestDataset(Dataset):
    def __init__(self, manifest, transform):
        with open(manifest, "r", encoding="utf-8") as f:
            d = json.load(f)

        self.samples = d["samples"]
        self.classes = d["classes"]
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x = self.samples[idx]

        img = Image.open(
            x["path"]
        ).convert("RGB")

        img = self.transform(img)

        return (
            img,
            int(x["class_index"]),
        )


class StatCollector:
    def __init__(
        self,
        sample_limit=200000,
        per_call=4096,
        seed=20260921,
    ):
        self.sample_limit = sample_limit
        self.per_call = per_call
        self.rng = random.Random(seed)

        self.stats = {}

    def update(self, name, x):
        if isinstance(x, (tuple, list)):
            x = x[0]

        x = (
            x.detach()
            .float()
            .reshape(-1)
            .cpu()
        )

        if x.numel() == 0:
            return

        entry = self.stats.setdefault(
            name,
            {
                "min": float("inf"),
                "max": float("-inf"),
                "count": 0,
                "samples": [],
            },
        )

        entry["min"] = min(
            entry["min"],
            float(x.min())
        )

        entry["max"] = max(
            entry["max"],
            float(x.max())
        )

        entry["count"] += int(
            x.numel()
        )

        n = min(
            self.per_call,
            x.numel(),
        )

        if n < x.numel():
            idx = torch.linspace(
                0,
                x.numel() - 1,
                steps=n,
            ).long()
            x = x[idx]

        vals = x.tolist()

        room = (
            self.sample_limit
            - len(entry["samples"])
        )

        if room > 0:
            entry["samples"].extend(
                vals[:room]
            )

    def finish(self):
        out = {}

        for name, s in self.stats.items():
            v = torch.tensor(
                s["samples"],
                dtype=torch.float32,
            )

            av = v.abs()

            def q(p):
                if v.numel() == 0:
                    return 0.0

                return float(
                    torch.quantile(
                        av,
                        torch.tensor(p),
                    )
                )

            # signed 3-bit recommendation:
            # integer domain [-4,3].
            #
            # We use the positive magnitude / 3
            # as a first calibration candidate.
            p999 = q(0.999)

            scale_signed3 = (
                p999 / 3.0
                if p999 > 0
                else 1.0
            )

            out[name] = {
                "count":
                    s["count"],

                "min":
                    s["min"],

                "max":
                    s["max"],

                "abs_p99":
                    q(0.99),

                "abs_p999":
                    p999,

                "abs_p9999":
                    q(0.9999),

                "sample_count":
                    len(s["samples"]),

                "candidate_signed3_scale_p999":
                    scale_signed3,
            }

        return out


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--source-checkpoint",
        required=True,
    )

    ap.add_argument(
        "--qat-checkpoint",
        required=True,
    )

    ap.add_argument(
        "--stage3-dir",
        required=True,
    )

    ap.add_argument(
        "--manifest",
        required=True,
    )

    ap.add_argument(
        "--output",
        default="stage4a_ranges",
    )

    ap.add_argument(
        "--batch-size",
        type=int,
        default=16,
    )

    ap.add_argument(
        "--workers",
        type=int,
        default=4,
    )

    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    source = torch.load(
        args.source_checkpoint,
        map_location="cpu",
        weights_only=True,
    )

    qat = torch.load(
        args.qat_checkpoint,
        map_location="cpu",
        weights_only=True,
    )

    num_classes = int(
        source["num_classes"]
    )

    # --------------------------------------------------
    # Rebuild W3-QAT model
    # --------------------------------------------------

    model = HLS196DeiT(
        num_classes
    )

    model.vit.load_state_dict(
        source["model"],
        strict=True,
    )

    convert_backbone_to_qat(
        model
    )

    model.load_state_dict(
        qat["model_state"],
        strict=True,
    )

    # --------------------------------------------------
    # Rebuild frozen Stage3 HLS Patch
    # --------------------------------------------------

    stage3 = Path(
        args.stage3_dir
    )

    patch_w = torch.load(
        stage3 /
        "patch_weight_int8.pt",
        map_location="cpu",
        weights_only=True,
    )

    patch_bias = torch.load(
        stage3 /
        "patch_bias_raw_int32.pt",
        map_location="cpu",
        weights_only=True,
    )

    patch_cls = torch.load(
        stage3 /
        "patch_cls_raw_int32.pt",
        map_location="cpu",
        weights_only=True,
    )

    with open(
        stage3 / "report.json",
        "r",
        encoding="utf-8",
    ) as f:
        s3 = json.load(f)

    patch_w_scale = float(
        s3["patch_weight"]["scale"]
    )

    patch = HLSPatchFrontend(
        patch_w,
        patch_bias,
        patch_cls,
        patch_w_scale,
    )

    full_model = HLSStage3Model(
        model,
        patch,
    )

    # --------------------------------------------------
    # Calibration data
    # --------------------------------------------------

    ds = ManifestDataset(
        args.manifest,
        eval_transform(),
    )

    loader = DataLoader(
        ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=True,
    )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    full_model = full_model.to(
        device
    )

    full_model.eval()

    collector = StatCollector()

    handles = []

    # --------------------------------------------------
    # Hooks at HLS-relevant boundaries
    # --------------------------------------------------

    for b in range(12):
        block = model.vit.blocks[b]

        # LN1 output:
        # candidate for __attn_lnq_t signed 3-bit
        handles.append(
            block.norm1.register_forward_hook(
                lambda m, i, o, b=b:
                collector.update(
                    f"b{b}.ln1_out",
                    o,
                )
            )
        )

        # QKV linear output before splitting.
        def qkv_hook(m, i, o, b=b):
            q, k, v = torch.chunk(
                o,
                3,
                dim=-1,
            )

            collector.update(
                f"b{b}.q_prequant",
                q,
            )

            collector.update(
                f"b{b}.k_prequant",
                k,
            )

            collector.update(
                f"b{b}.v_prequant",
                v,
            )

        handles.append(
            block.attn.qkv
            .register_forward_hook(
                qkv_hook
            )
        )

        # Input to output projection:
        # concatenated attention result A,
        # candidate for __attn_aq_t signed 3-bit.
        handles.append(
            block.attn.proj
            .register_forward_pre_hook(
                lambda m, i, b=b:
                collector.update(
                    f"b{b}.attn_A_pre_proj",
                    i[0],
                )
            )
        )

        # Output projection result.
        handles.append(
            block.attn.proj
            .register_forward_hook(
                lambda m, i, o, b=b:
                collector.update(
                    f"b{b}.attn_proj_out",
                    o,
                )
            )
        )

        # LN2 output:
        # candidate for __mlp_ln_t signed 3-bit.
        handles.append(
            block.norm2
            .register_forward_hook(
                lambda m, i, o, b=b:
                collector.update(
                    f"b{b}.ln2_out",
                    o,
                )
            )
        )

        # MLP1 accumulator/output before GELU.
        handles.append(
            block.mlp.fc1
            .register_forward_hook(
                lambda m, i, o, b=b:
                collector.update(
                    f"b{b}.mlp1_pre_gelu",
                    o,
                )
            )
        )

        # GELU output:
        # candidate for unsigned 3-bit [0,7].
        handles.append(
            block.mlp.act
            .register_forward_hook(
                lambda m, i, o, b=b:
                collector.update(
                    f"b{b}.gelu_out",
                    o,
                )
            )
        )

        # MLP2 output.
        handles.append(
            block.mlp.fc2
            .register_forward_hook(
                lambda m, i, o, b=b:
                collector.update(
                    f"b{b}.mlp2_out",
                    o,
                )
            )
        )

        # Full block output = next 13-bit FM candidate.
        handles.append(
            block.register_forward_hook(
                lambda m, i, o, b=b:
                collector.update(
                    f"b{b}.block_out",
                    o,
                )
            )
        )

    # --------------------------------------------------
    # Run calibration
    # --------------------------------------------------

    with torch.inference_mode():
        for step, (images, _) in enumerate(
            loader,
            1
        ):
            images = images.to(
                device,
                non_blocking=True,
            )

            _ = full_model(images)

            if (
                step % 10 == 0
                or step == len(loader)
            ):
                print(
                    f"calibration "
                    f"{step}/{len(loader)}",
                    flush=True,
                )

    for h in handles:
        h.remove()

    result = collector.finish()

    # --------------------------------------------------
    # Add hardware target type information
    # --------------------------------------------------

    for b in range(12):
        result[
            f"b{b}.ln1_out"
        ]["target_hls_type"] = (
            "ap_int<3>"
        )

        for n in [
            "q_prequant",
            "k_prequant",
            "v_prequant",
            "attn_A_pre_proj",
        ]:
            result[
                f"b{b}.{n}"
            ]["target_hls_type"] = (
                "ap_int<3>"
            )

        result[
            f"b{b}.ln2_out"
        ]["target_hls_type"] = (
            "ap_int<3>"
        )

        result[
            f"b{b}.gelu_out"
        ]["target_hls_type"] = (
            "ap_uint<3>"
        )

        result[
            f"b{b}.block_out"
        ]["target_hls_type"] = (
            "ap_int<13>"
        )

    payload = {
        "calibration_manifest":
            str(args.manifest),

        "samples":
            len(ds),

        "model":
            "PlantVillage HLS196 + W3-QAT + HLS Patch",

        "statistics":
            result,
    }

    with open(
        out /
        "activation_ranges.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
            indent=2,
        )

    # Concise console summary
    print()
    print(
        "===== STAGE 4A: "
        "ACTIVATION CALIBRATION ====="
    )

    print(
        "Calibration samples:",
        len(ds)
    )

    for b in [0, 1, 11]:
        print()
        print(f"Block {b}")

        for n in [
            "ln1_out",
            "q_prequant",
            "k_prequant",
            "v_prequant",
            "attn_A_pre_proj",
            "ln2_out",
            "mlp1_pre_gelu",
            "gelu_out",
            "block_out",
        ]:
            s = result[
                f"b{b}.{n}"
            ]

            print(
                f"  {n:18s} "
                f"min={s['min']:.5f} "
                f"max={s['max']:.5f} "
                f"|x|p99.9="
                f"{s['abs_p999']:.5f}"
            )

    print()
    print(
        "Saved:",
        out /
        "activation_ranges.json"
    )


if __name__ == "__main__":
    main()
