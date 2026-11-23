"""W3 diagnostic using the frozen canonical MSE scale search and grouping."""
import argparse
import json
from pathlib import Path
import torch
from torch.utils.data import DataLoader
from qat_weight3_hls196 import HLS196DeiT, convert_backbone_to_qat, evaluate, export_int3, eval_transform
from manifest_adapter import image_folder


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--data-root", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = HLS196DeiT(checkpoint["num_classes"])
    model.vit.load_state_dict(checkpoint["model"], strict=True)
    convert_backbone_to_qat(model)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    loader = DataLoader(image_folder(Path(args.data_root)/"val", eval_transform()),
                        batch_size=args.batch_size, num_workers=args.workers)
    top1 = evaluate(model.to(device), loader, device)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    export_int3(model, output)
    (output / "report.json").write_text(json.dumps({"validation_top1": top1,
        "method": "canonical mse_init_scale search, independent Q/K/V; per-matrix O/MLP",
        "bits": 3, "range": [-4, 3]}, indent=2)+"\n")


if __name__ == "__main__":
    main()
