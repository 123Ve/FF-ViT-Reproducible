# Manifest-driven quantization stages

Invoke the archive-root shell pipelines with the `vlm_token` interpreter.
Both default to a read-only JSON-lines dry-run. `--run` executes stages.

```bash
bash archive/nwpu_resisc45_ffvit/pipeline_train.sh --dry-run
bash archive/nwpu_resisc45_ffvit/pipeline_train.sh --run --stop-after w3_qat \
  --run-dir /home/user/Desktop/ff_vit_re/archive/nwpu_resisc45_ffvit/runs/nwpu_seed20260923
# After Task 4 review, continue into Task 5 using exactly the same configuration:
bash archive/nwpu_resisc45_ffvit/pipeline_train.sh --run --resume \
  --run-dir /home/user/Desktop/ff_vit_re/archive/nwpu_resisc45_ffvit/runs/nwpu_seed20260923
```

Each stage writes into a fresh hidden staging directory and publishes by
rename after successful execution, shape checks, and provenance generation.
The stage log remains with its artifacts. Failed staging directories are
retained for diagnosis; they are never treated as published checkpoints.
FP32 epoch recovery states are retained in `fp32/training_state/`.
Before promotion, report/checkpoint metadata is rewritten to the final
artifact and recovery paths, and report checkpoint hashes are refreshed.
Report commands use those stable published paths. `execution_history.json`
and `stage.log` separately retain actual execution commands and temporary
paths as historical evidence; they are not artifact-location indexes.
`--resume` skips completed stages only when recipe, source, manifest, input,
and output hashes still match. Interrupted canonical QAT stages restart in a
new staging directory; optimizer/RNG continuation is not implemented by the
canonical trainers and is not claimed here. Interrupted FP32 states retain
the Task 2 direct trainer recovery interface.

The W3 and final exact validation gates compare against the frozen FP32
validation result and stop downstream execution at drops over 2 or 5 points.
Failed-gate artifacts are retained. Task 4/5 milestone test evaluation uses
the frozen `test.json`; non-milestone MLP and Attention fits do not read test
images. The W3 canonical trainer evaluates test once after best-val selection.

The manifest adapter routes old folder-loader calls to the exact Task 1
records and verifies image identities through the Task 2 loader. No image
copy, symlink dataset, historical scale, or historical checkpoint is used.
Calibration receives all 1,440 train-only records. Exact-stage token samplers
retain canonical per-fit token limits. QAT uses the established 32-image
batch size; exact stages retain their smaller canonical defaults unless
`--batch-size` is explicitly supplied.

`canonical/` contains frozen source copies and mechanically adapted dataset
boundaries. `source_inventory.json` records all source and port SHA-256 pairs.
`port_sources.py` documents and reproduces the transformations. The W3 PTQ
diagnostic uses the copied canonical QAT MSE initialization/search because
the audited bundle has no separate weight-PTQ script. The final GELU stage
translates Attention's `mlp_controller_state` key into the MLP-only fitter's
`controller_state` in a stage-local checkpoint, preserving tensors unchanged.
Head arrays use `head_weight_active.npy` and `head_bias_active.npy` with an
explicit 45-row class contract; hardware Head output remains 1,000 rows.

Task 6 supplies the reviewed ROM/block0 source templates explicitly:

```bash
bash archive/nwpu_resisc45_ffvit/pipeline_deploy.sh --run \
  --run-dir /home/user/Desktop/ff_vit_re/archive/nwpu_resisc45_ffvit/runs/nwpu_seed20260923 \
  --rom-template /path/to/reviewed/fixed_patch_head_rom.h \
  --block0-template /path/to/reviewed/block0.cpp
```

Default template paths under `templates/` are intentionally not populated by
Task 3. Missing templates or stage artifacts cause failure before export.
Export and fixture directories are distinct immutable stage outputs; Task 6
is responsible for assembling and validating the final deployment package.
No HLS installation or C-simulation is performed by these pipelines.
