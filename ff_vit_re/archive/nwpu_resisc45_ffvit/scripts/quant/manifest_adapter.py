"""Explicit manifest context for mechanically ported canonical stages."""
from pathlib import Path

_context = None


def configure(metadata, source, count=45, calibration_count=1440):
    from src.manifest_dataset import load_manifest_bundle, VerifiedSourceIndex
    global _context
    bundle = load_manifest_bundle(Path(metadata))
    if len(bundle.classes) != count or len(bundle.records_for("calibration")) != calibration_count:
        raise ValueError("class/calibration contract differs from explicit arguments")
    _context = (bundle, Path(source).resolve(), Path(metadata).resolve(), VerifiedSourceIndex(source))
    return bundle


def context():
    if _context is None:
        raise ValueError("configure explicit manifest/class context through run_stage.py first")
    return _context


def num_classes():
    return len(context()[0].classes)


def image_folder(root, transform):
    from src.manifest_dataset import ManifestImageDataset
    bundle, source, metadata, index = context()
    root = Path(root)
    if root.parent.resolve() != source or root.name not in {"train", "val", "test"}:
        raise ValueError(f"unrecognized split routing: {root}")
    dataset = ManifestImageDataset(source, bundle.records_for(root.name), transform, index)
    dataset.classes = list(bundle.classes)
    dataset.class_to_idx = {name: i for i, name in enumerate(bundle.classes)}
    dataset.samples = [(str(source / r.relative_path), r.label) for r in dataset.records]
    dataset.targets = [r.label for r in dataset.records]
    return dataset


class CalibrationDataset:
    def __new__(cls, manifest, transform):
        from src.manifest_dataset import ManifestImageDataset
        bundle, source, metadata, index = context()
        if Path(manifest).resolve() != metadata / "calibration.json":
            raise ValueError("calibration must use the fixed train-only calibration manifest")
        dataset = ManifestImageDataset(source, bundle.records_for("calibration"), transform, index)
        dataset.classes = list(bundle.classes)
        dataset.targets = [r.label for r in dataset.records]
        return dataset
