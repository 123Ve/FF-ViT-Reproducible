# ImageNet-1K Original HLS S3

This repository is an isolated reproduction of the original PlantVillage HLS
numeric contract on ImageNet-1K. Mainline configurations must pass the frozen
validator in `src/contract.py`; wider operators are not accepted in the mainline.

## Frozen inputs and contract

- `config/original_hls_s3.yaml` defines the ImageNet paths, crop09 evaluation
  protocol, seed, training budgets, and signedness/width table.
- `metadata/input_manifest.json` records SHA-256 hashes for parent checkpoints
  and the authoritative HLS source, along with their external paths.
- Training and validation datasets, checkpoints, and the HLS source are read
  only inputs. All experiment artifacts belong under this repository.

The principal directories are `src/` for reusable code, `scripts/` for entry
points, `tests/` for focused checks, `metadata/` for immutable provenance,
`results/` and `reports/` for measured outcomes, and `checkpoints/`, `exact/`,
`hls/`, and `paper/` for later pipeline stages.

## Contract checks

Run the focused contract/provenance suite from this directory:

```sh
python -m pytest -q tests/test_contract.py tests/test_provenance.py
```

Load and validate a contract from Python with `load_contract(path)` and
`validate_mainline_contract(config)`.
