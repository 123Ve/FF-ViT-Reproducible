"""Recompute one manifest-selected image and all exact boundaries on CPU."""
import argparse
from pathlib import Path
from manifest_adapter import context
from deployment.generate_fixture import generate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture-index", type=int, default=0)
    args = parser.parse_args()
    bundle, source, _, index = context()
    records = bundle.records_for("test")
    if not 0 <= args.fixture_index < len(records):
        raise ValueError("fixture-index is outside the frozen test manifest")
    record = records[args.fixture_index]
    index.verify(record)
    generate(args.project_root, args.output, source / record.relative_path, list(bundle.classes))


if __name__ == "__main__":
    main()
