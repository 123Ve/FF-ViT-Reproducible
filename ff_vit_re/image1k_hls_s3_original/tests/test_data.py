import io
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import torch
from PIL import Image

from src.data import (
    FrozenManifestImages, make_calibration_loader, make_crop09_transform,
    make_selection_loader, make_validation_loader, make_validation_probe_loader,
)


def _jpeg_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (300, 240), color=(80, 120, 160)).save(stream, format="JPEG")
    return stream.getvalue()


def test_crop09_is_bicubic_resize248_then_center224():
    transform = make_crop09_transform()
    names = [type(step).__name__ for step in transform.transforms]
    assert names == ["Resize", "CenterCrop", "ToTensor", "Normalize"]
    assert transform.transforms[0].size == 248
    assert transform.transforms[0].interpolation.name == "BICUBIC"
    assert transform.transforms[1].size == (224, 224)
    result = transform(Image.new("RGB", (300, 300), color="white"))
    assert result.shape == (3, 224, 224)
    assert torch.isclose(result[0, 0, 0], torch.tensor((1 - .485) / .229), atol=1e-5)


def test_manifest_preserves_class_and_sample_identity(tmp_path):
    root = tmp_path / "train"
    image = root / "n0001" / "sample.JPEG"
    image.parent.mkdir(parents=True)
    image.write_bytes(_jpeg_bytes())
    manifest = tmp_path / "subset.jsonl"
    manifest.write_text(json.dumps({"path": str(image), "relative_path": "n0001/sample.JPEG", "class_name": "n0001", "label": 0}) + "\n")
    dataset = FrozenManifestImages(manifest, root=root, class_mapping={"n0001": 0}, transform=make_crop09_transform())
    tensor, label, sample_id = dataset[0]
    assert tensor.shape == (3, 224, 224)
    assert (label, sample_id) == (0, "n0001/sample.JPEG")
    manifest.write_text(json.dumps({"path": str(image), "relative_path": "n0001/sample.JPEG", "class_name": "n0001", "label": 1}) + "\n")
    with pytest.raises(ValueError, match="class/label"):
        FrozenManifestImages(manifest, root=root, class_mapping={"n0001": 0}, transform=make_crop09_transform())


def test_validation_loader_uses_stable_parquet_ids(tmp_path):
    root = tmp_path / "val"
    root.mkdir()
    table = pa.table({"image": pa.array([{"bytes": _jpeg_bytes(), "path": "ILSVRC2012_val_0001.JPEG"}]), "label": [4]})
    pq.write_table(table, root / "part-0.parquet")
    model = torch.nn.Module()
    model.pretrained_cfg = {
        "input_size": (3, 224, 224), "interpolation": "bicubic",
        "mean": (0.485, 0.456, 0.406), "std": (0.229, 0.224, 0.225),
        "crop_pct": 0.9, "crop_mode": "center",
    }
    loader = make_validation_probe_loader(root, model=model, batch_size=1, expected_count=1, num_workers=0)
    image, label, sample_id = next(iter(loader))
    assert image.shape == (1, 3, 224, 224)
    assert label.tolist() == [4]
    assert sample_id == ("part-0.parquet:ILSVRC2012_val_0001.JPEG",)


def test_formal_validation_requires_exactly_50000_rows(tmp_path):
    root = tmp_path / "val"
    root.mkdir()
    table = pa.table({"image": pa.array([{"bytes": _jpeg_bytes(), "path": "sample.JPEG"}]), "label": [4]})
    pq.write_table(table, root / "part.parquet")
    model = torch.nn.Module()
    model.pretrained_cfg = {
        "input_size": (3, 224, 224), "interpolation": "bicubic",
        "mean": (0.485, 0.456, 0.406), "std": (0.229, 0.224, 0.225),
        "crop_pct": 0.9, "crop_mode": "center",
    }
    with pytest.raises(ValueError, match="exactly 50000 records"):
        make_validation_loader(root, model=model, batch_size=1)
    with pytest.raises(TypeError):
        make_validation_loader(root, model=model, batch_size=1, expected_count=1)


def test_calibration_and_selection_loaders_keep_manifest_order(tmp_path):
    root = tmp_path / "train"
    paths = []
    for name in ("second", "first"):
        image = root / "n0001" / f"{name}.JPEG"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(_jpeg_bytes())
        paths.append(image)
    manifest = tmp_path / "samples.jsonl"
    manifest.write_text("\n".join(json.dumps({
        "path": str(path), "relative_path": f"n0001/{path.name}",
        "class_name": "n0001", "label": 0,
    }) for path in paths) + "\n")
    for factory in (make_calibration_loader, make_selection_loader):
        loader = factory(manifest, root=root, class_mapping={"n0001": 0}, batch_size=2, expected_count=2)
        assert next(iter(loader))[2] == ("n0001/second.JPEG", "n0001/first.JPEG")
