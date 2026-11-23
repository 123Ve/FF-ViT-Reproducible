# FF-ViT: reproducible E07 engineering archive

[中文说明](README_CN.md) · [Build and reproduction guide / 构建指南](docs/REPRODUCE.md) · [Known issues / 已知问题](docs/KNOWN_ISSUES.md)

This repository preserves one curated source and deployment snapshot from
`ff_vit_re` and `FF_Vit`: DeiT-Tiny fine-tuning, W3/W8 mixed-precision QAT,
integer/LUT export, HLS, Vivado, Vitis, three task-specific binary fixtures,
the cloud–edge GUI, and the latest independent power-sampling release.
Raw image datasets, full test-set image shards, rejected training branches and
temporary build caches are excluded. **This is an archive, not a new hardware
or accuracy validation.**

## Start here

Git LFS must be installed before cloning the binary artifacts:

```bash
git lfs install
git clone <YOUR_GITHUB_REPOSITORY_URL> FF-ViT-Reproducible
cd FF-ViT-Reproducible
git lfs pull
python3 -B tools/verify_repository.py
```

For a local copy or the standalone ZIP, enter its directory and run the last
command. It uses Python's standard library only. It checks the complete
inventory, SHA-256, original-file provenance and all three deployment BIN sets.
It does not execute training or access a board.

## What is included

| Location | Contents |
| --- | --- |
| `deploy/{plantvillage,nwpu,imagenet}/` | Each task's actual backbone `weights.bin`, one S16 `input.bin`, 1000-logit `output.bin`, matching Patch/Head ROM |
| `deploy/tasks.json` | File identities, input format and each task's verification boundary |
| `FF_Vit/E04_weight_schedule/E07_timing_300mhz/` | E07 candidate05 HLS sources, seed BD, Vivado Tcl, reports, Vitis applications, baseline BIT/XSA/BOOT |
| `ff_vit_re/validation/u3_full_board_test_20261014/` | Task-specific PlantVillage/NWPU HLS ROM/source, BD and accuracy firmware |
| `artifacts/tasks/` | Existing NWPU boot image and explicitly labeled timing-failed PlantVillage experimental image |
| `ff_vit_re/image1k_hls_s3_original/` | ImageNet original strict S3 training, exact integer export, selected checkpoints, complete HLS harness and four fixtures |
| `ff_vit_re/validation/e07_u3_progressive_qat_20261010/` | Canonical PlantVillage/NWPU progressive U3 QAT, selected MLP/attention checkpoints and final integer arrays |
| `ff_vit_re/{quantization_final,archive/nwpu_resisc45_ffvit,image_lianghu}/` | Required parent checkpoints, shared numeric implementations, data adapters and fitting/export dependencies |
| `ff_vit_re/Cloud_test/` | TCP collector, Flask/Plotly dashboard, Windows frontend, PS network firmware and matching frozen network inputs |
| `ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler/` | Exact r10 Windows power-test release, with both A53 ELFs, three BOOT profiles and SD folders |
| `artifacts/bsp/`, `artifacts/ip/` | Original Vitis 2025.1 BSP exports/startup sources and reusable E07 HLS IP |
| `provenance/` | Original-to-repository mapping, hashes, model lineage and environment inventory |
| `tools/` | Integrity check, writable workspace creation and GitHub publication helper |

The original directory hierarchy is intentional: Python scripts import shared
quantization helpers by these relative paths. There is one canonical mainline;
the retained older modules are its dependencies, not additional recommended
training pipelines.

## Task identities and limits

| Task / image | Preserved result or status |
| --- | --- |
| PlantVillage U3 | Historical integer-software Top-1 98.5712%; existing task-specific 300 MHz experimental image has **WNS −0.115 ns**, not timing-qualified |
| NWPU-RESISC45 U3 | Historical integer-software Top-1 88.8222%; matching task-specific timing-qualified BIT/XSA/BOOT preserved; no new physical test |
| ImageNet original strict S3 | Historical exact-software result 68.156%; matching exact parameters and HLS fixtures preserved; no new matching task-specific BOOT is asserted |
| Frozen E07 baseline | Historical routed clock 300.215 MHz and board benchmark 348.655 FPS; its own BIT/XSA/ROM/weights are preserved together |

The frozen E07 50k ImageNet board-test source/image is also preserved under
`board_300mhz/imagenet_frozen_50k_test/`. Its README explicitly states that it
tests the unchanged E07 image, **not** the separate ImageNet strict-S3 software
model. Do not exchange weights/ROM/BOOT across these identities.

The convenience `deploy/` directories are minimal model fixtures, not complete
SD cards for the full-dataset accuracy firmware. That firmware also expects its
generated `INDEX.BIN`, image shards and golden records; regenerate those from
your external datasets with the preserved preparation scripts.
PlantVillage/NWPU inputs use DMA order `[98,768,2]`; the ImageNet HLS fixture
uses logical `[196,768]` order, converted to DMA order by its testbench.

## GUI and power testing

The GUI has a separate lightweight environment:

```bash
python3 -m venv .venv-gui
source .venv-gui/bin/activate
pip install -r requirements-gui.txt
cd ff_vit_re
python -m Cloud_test.run_e07_measurements --help
python -m Cloud_test.run_e07_measurements --gui --duration 15 --streams 1
```

The real collector binds to `192.168.10.1:5001`; the dashboard uses localhost
port 18082. Prepare the host NIC and the matching SD image first. The current
GUI default is the preserved V2.5 network candidate, whose physical acceptance
is not asserted here. The original runbooks and Windows launch/build scripts
are included. **The GUI network firmware and r10 independent-sampler firmware
have different protocols; use their corresponding host programs.**

For independent power tests on Windows, use the unchanged package directory:

```powershell
$Pkg = (Resolve-Path '.\ff_vit_re\validation\cloud_power_retest_20261121\independent_sampler').Path
& "$Pkg\Run-PowerRetest.ps1" -CheckOnly -Diagnostic16
# Then follow its README_CN.txt for PrepareSD, Acceptance and Formal.
```

Strict18, Diagnostic17 (exclude rail 7), and Diagnostic16 (exclude rails 7 and 15)
remain separate. All 18 rails' raw records and quality flags are retained.
Target120 means **four sources × 30 FPS offered load**, 120 seconds per
condition, five repeats; completed FPS and frame drops must be reported.
The reported current ~64 FPS limitation remains unresolved. No new 120 FPS
power value is claimed by this archive.

## Rebuild or retrain without changing the archive

```bash
python3 tools/create_workspace.py --output "$PWD/work/reproduction"
```

This creates a writable copy, relocates historical absolute paths, unpacks the
exact E07 IP and supplies the original BSPs. Numerical arrays, weights and
archived images are unchanged. Every path-only rewrite is listed in
`work/reproduction/WORKSPACE.json`. Datasets can be linked using the script's
`--plantvillage-root`, `--nwpu-root`, `--imagenet-train` and `--imagenet-val`
options. Build/training instructions are in [docs/REPRODUCE.md](docs/REPRODUCE.md).
Training requires your own datasets and GPU environment; exporting an existing
checkpoint is a different operation from retraining it.

## Save to GitHub

The local repository is ready for an owner-selected remote. Log in locally;
do not paste access tokens into documentation or chat:

```bash
gh auth login
bash tools/publish_github.sh OWNER/FF-ViT-Reproducible private
```

Use `public` only if that is your intended visibility. Binary artifacts and
checkpoints are tracked by Git LFS, so a clone must retrieve LFS objects too.
GitHub blocks ordinary Git files above 100 MiB; see
[GitHub large-file documentation](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).
LFS storage/bandwidth depends on the owner account; see
[Git LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs).
The helper follows the official
[existing-project publication workflow](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

See [NOTICE.md](NOTICE.md) for original copyrights and licensing.
