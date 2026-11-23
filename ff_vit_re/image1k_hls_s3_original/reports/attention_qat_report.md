# Task 6: strict attention and joint QAT

## Outcome

Completed the full fixed budget without reaching the 69% formal Top-1 target. Terminal status: **budget_exhausted**; process exit code 0.

The selected strict attention+MLP surrogate is mainline epoch 13: **66.954% Top-1 / 87.986% Top-5** on all 50,000 unique crop09 validation images, FP32 with TF32 disabled. This is 2.046 percentage points below 69%, 2.134 points below the strict MLP parent's 69.088%, and 3.066 points below the W3 ancestor's 70.020%. No numeric widths were widened. Exhaustion of this specified budget does not establish that strict3 cannot reach the target under a different authorized recipe.

Selected checkpoint: `checkpoints/attention/main/best.pth`, also hard-linked at `checkpoints/joint/main/best.pth` and `checkpoints/attention/main/candidate_epoch13.pth`.

SHA256: `bf40fc4e40a27943f7b4e27b4b6e9dc9b45320c03b13ba181fb91fd81371fad3`.

Load `ema_model` and `ema_controller` strictly into `load_w3_parent` plus `AttentionController`, then enable all 13 boundaries in all 12 blocks using `attention_masks(frozen_order, 3)`. Do not use the raw model/controller states as the reported EMA candidate. These are surrogate results, not exact-integer or HLS accuracy.

## Implementation and immutable lineage

The parent is the accepted strict MLP EMA at `checkpoints/mlp/main/best.pth`, SHA256 `ecc26c2d04c2e8952324cbc1e1806866b63a418018169a5cfc40af50d44f0e02`. Its five MLP scale vectors, all12 MLP masks, W3 weights and W3 quantizer state are preserved at transfer. With new attention masks disabled, two CPU FP32 test images produced bit-identical logits to the original MLPController parent (maximum difference 0).

Added `src/attention_trainer.py`, `scripts/train_strict_attention.py`, `scripts/train_strict_joint.py`, `config/attention_qat.json`, and controller/trainer tests. The shared checkpoint helper gained a backward-compatible recipe-selected schema and embedded history. Task 6 uses schema `original_hls_s3.attention_qat.v1`.

The new controller learns 156 scalar activation scales across 13 boundaries and 12 blocks. Exact domains are:

| Boundary | Code domain |
| --- | --- |
| W, LN1, Q, K, V, A, LN2 | signed 3-bit, [-4, 3] |
| Softmax, GELU | unsigned 3-bit, [0, 7] |
| O, FC2, block FM / MLP residual | signed 13-bit, [-4096, 4095] |
| Attention residual | signed 15-bit, [-16384, 16383] |
| FC1 | signed 11-bit, [-1024, 1023] |

The attention residual is quantized as the actual tensor before both consumers: LN2 and the MLP residual skip. Softmax and activation code/LSQ arithmetic use FP32 during BF16 training autocast. All inherited W3 quantizers remain enabled.

Four progressive epochs enable 3/6/9/12 attention blocks in the frozen order `[11,10,9,8,7,4,5,3,1,6,2,0]`. Only active attention modules, LN1 parameters and attention scale entries train during progression; all MLP parameters/scales remain frozen. Stable optimizer groups and zero weight decay for scales preserve inactive scale entries. Joint training unfreezes the whole model and all scale vectors.

The progressive endpoint audit found only 96 attention/LN1 model tensors changed relative to the parent, all five inherited MLP scale vectors bit-identical, all13 masks all12, and four full epochs at step 39,912. The selected joint EMA subsequently changed 72 MLP tensors and all five MLP scale vectors relative to the progressive endpoint, confirming actual unfreezing. See `reports/attention_qat_progressive_audit.json` and `reports/attention_qat_final_audit.json`.

Implementation commit: `33a01e90c1a82123e84f5d73b2505376f659e62e`. Launch/probe-evidence commit: `e90aaf55f64c8997cba9fb94a72aee81b2db2ce1`. Source and numerical configuration were not changed during the full run; their final hashes match the embedded frozen recipe.

## Data roles, recipe and budget

Environment: `vlm_token`, NVIDIA GeForce RTX 5090. Command:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/anaconda3/envs/vlm_token/bin/python scripts/train_strict_attention.py
```

Log: `results/attention_main.log`. No full-run restarts or nonfinite-gradient failures occurred.

Every completed optimizer epoch consumed exactly **1,277,128 images**: the original 1,281,167 minus 4,000 fixed train-origin calibration/selection holdouts and 39 byte-identical aliases. The membership SHA256 is `55cb2d23aa5a1733d2f4a7a8b21a7abc70e608a520d4b51319ecea38a7b10170`, equal to the strict MLP parent. Path and byte-content role overlap were both zero; the retained-file hash audit covered all matching byte lengths. Calibration and selection samples were never used for optimizer gradients.

The mainline used batch 128, 16 workers, seed 20260923, AdamW, model LR 3e-5, scale LR 1e-3, CE weight 1, logit KD temperature 2 and weight 1, normalized feature weight 0.5, gradient clip 1, EMA 0.999, and 0.25-epoch warmup with the frozen cosine schedule. The teacher was frozen FP32; student training used BF16 autocast with FP32 activation quantization. Evaluation was FP32 without TF32.

Completed **4 progressive + 10 joint + 6 recovery epochs**, exactly 199,560 optimizer steps (9,978 per epoch) and 25,542,560 full-run image presentations. Five separate diagnostic probes consumed another 450 steps / 57,600 image presentations; none became a training parent.

All three predeclared recovery branches ran for two full epochs and restarted from the mainline's frozen best EMA (the SHA256 above), with a fresh optimizer and EMA:

| Recovery branch | Model LR | Scale LR | KD weight | Feature weight | Formal Top-1 by epoch |
| --- | --- | --- | --- | --- | --- |
| 1 | 1e-5 | 3e-4 | 2 | 0.5 | 66.170%, 66.588% |
| 2 | 2e-5 | 5e-4 | 1 | 1 | 66.044%, 66.622% |
| 3 | 5e-6 | 1e-4 | 3 | 0.25 | 66.366%, 66.618% |

No recovery branch improved the mainline best. There were no added branches or budget extensions.

## Probes and test-first evidence

Initial all12 100-step main/conservative probes used batch 128 and were finite with moving weights and a frozen teacher. Their original scale-movement scalar was invalid: it compared initial LN1 scales with final LN2 scales. The artifacts remain explicitly labeled `attention_qat_diagnostic_v0_*`; this scalar is not evidence of scale learning. These diagnostics also overlapped checkpoint-safety source work and are not frozen-source identity proof.

A failing named-scale-movement regression test preceded the fix. Corrected 100-step main and conservative probes were rerun against frozen source. Main/conservative final CE was 4.88244/5.91289, KD 1.71202/1.82948, and feature error 0.86814/0.89573. Both were finite; peak CUDA allocation was 19,839,585,792 bytes. Main moved the first active QKV weight by 0.00008886 and LN1 log scales by 0.00243407. The original main profile was retained and frozen in `reports/attention_qat_probe_selection.json`.

A separate 50-step progressive probe changed exactly 24 attention/LN1 tensors from blocks 9/10/11 while inherited MLP scale tensors remained unchanged. Full training then restarted from the strict MLP parent, not any probe.

The test-first sequence observed missing controller APIs, runner, named movement helper, immutable candidate publication and checkpoint-history support fail before implementation. New tests cover literal domains and LSQ gradients, progressive and all12 masks, the residual's actual MLP skip consumer, Softmax u3, attention-only freezing and joint unfreezing, strict MLP EMA transfer, schema/provenance/resume rejection, pending formal/history restoration, immutable publication, corrected scale movement, and terminal resume immutability.

Final fresh suite: **72 passed**, one existing external PyTorch `torch.jit.interface` deprecation warning, in 8.09 seconds. Command:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/anaconda3/envs/vlm_token/bin/python -m pytest -q --basetemp results/pytest-task6-final
```

`git diff --check` passed before final publication; it is also checked on the staged report/metadata changes.

## Full epoch and formal history

Epoch indices are zero-based. Each row used the complete 1,277,128-image optimizer corpus. Selection is the separate 2,000-image holdout and is not formal accuracy. Every completed all12 epoch (3 through 19) received formal50k evaluation, without gaps.

| Epoch | Stage | Selection Top-1 % | Formal Top-1 % | Formal Top-5 % |
| --- | --- | --- | --- | --- |
| 0 | progressive 1/4 | 72.900 | not all12 | — |
| 1 | progressive 2/4 | 72.600 | not all12 | — |
| 2 | progressive 3/4 | 71.550 | not all12 | — |
| 3 | progressive 4/4 | 69.000 | 64.244 | 86.294 |
| 4 | joint 1/10 | 69.200 | 64.730 | 86.682 |
| 5 | joint 2/10 | 69.150 | 65.236 | 87.096 |
| 6 | joint 3/10 | 68.950 | 65.588 | 87.354 |
| 7 | joint 4/10 | 70.450 | 65.912 | 87.364 |
| 8 | joint 5/10 | 69.950 | 66.006 | 87.532 |
| 9 | joint 6/10 | 70.650 | 66.300 | 87.628 |
| 10 | joint 7/10 | 70.500 | 66.396 | 87.928 |
| 11 | joint 8/10 | 70.200 | 66.552 | 87.888 |
| 12 | joint 9/10 | 70.350 | 66.776 | 87.898 |
| 13 | joint 10/10 | 70.650 | 66.954 | 87.986 |
| 14 | recovery 1, epoch 1/2 | 70.400 | 66.170 | 87.636 |
| 15 | recovery 1, epoch 2/2 | 70.750 | 66.588 | 87.966 |
| 16 | recovery 2, epoch 1/2 | 69.850 | 66.044 | 87.618 |
| 17 | recovery 2, epoch 2/2 | 71.100 | 66.622 | 87.690 |
| 18 | recovery 3, epoch 1/2 | 71.600 | 66.366 | 87.762 |
| 19 | recovery 3, epoch 2/2 | 71.100 | 66.618 | 88.004 |

Formal records are `reports/attention_qat_formal_epochNN.json`; joint records mirror epochs 04–19. All 17 candidates used the same 50,000 unique validation sample identity, SHA256 `303e942396bb6601c0ebfbe889ebe7d29e42c70a457f28132592e6deed920c78`, also matching Task 5. Top-1 and then Top-5 select the winner. Consequently formal50k is used for checkpoint selection and is **not an independent post-selection test estimate**.

## Checkpoint, resume and final audits

Checkpoint/progress writes are atomic. A pending formal epoch and full history are embedded in `latest.pth` before an immutable candidate hard link is published. Resume restores checkpoint history as authoritative, verifies the frozen recipe, and finishes pending formal evaluation before another optimizer epoch. Existing candidates are never silently overwritten. Joint paths alias the same lineage.

The final audit verified every candidate SHA256 against its formal record, pending epoch, step count, recipe and all12 masks; every candidate history has the expected completed epoch count. All six recovery candidate parents equal frozen `base_best.pth`. Latest embedded history/progress exactly matches the final report, and attention/joint aliases and reports agree.

The selected EMA strictly reloaded and passed the training contract. Model/controller tensors are finite; all 156 activation scales and W3 scales are positive and finite. All 48 W3 modules / 72 matrix segments remain enabled and export codes only in [-4, 3].

Actual terminal calls to both `scripts/train_strict_attention.py --resume` and `scripts/train_strict_joint.py --resume` exited 0 with `budget_exhausted`, `already_complete`, and step 199,560. Hashes, sizes and mtimes of all 87 pre-existing run/probe artifacts remained identical. The terminal guard executes before CUDA/data/optimizer initialization. Evidence: `reports/attention_qat_terminal_resume_audit.json`.

Terminal `latest.pth` SHA256: `66904026bf4f169badac7fbe8b173e663ed0a86d3569e3962e917d2426bc72ce`. This terminal checkpoint is not the selected accuracy winner.

Primary handoff artifacts:

- `metadata/attention_qat_checkpoint.json`: deployment keys, selected scales, widths, complete formal lineage, artifact hashes and caveats.
- `reports/attention_qat_final_audit.json`: candidate, source/input, domain, coverage and unfreezing audit.
- `reports/attention_qat_training.json` and `reports/joint_qat_training.json`: complete frozen recipe, epochs, formal history and terminal status.
- `reports/attention_qat_report.md`: tracked copy of this report.
- `.superpowers/sdd/2026-10-01-imagenet1k-original-hls-s3/task-6-report.md`: requested local handoff report.

## Independent-review correction: timestamp precision

The original terminal audit compared exact Python snapshots correctly, but its later JSON transfer through JavaScript rounded numeric `mtime_ns` values: all 87 persisted entries differed from filesystem nanoseconds, by at most 230 ns. The model checkpoints, formal results, hashes, sizes and training state were unaffected.

Added `scripts/audit_attention_terminal_resume.py` to capture nanoseconds as decimal strings and atomically publish the audit directly from Python, without a JavaScript serialization round-trip. The generator excludes its own output and the derived final-audit report, preserving the original 87 training/probe artifacts. It reruns both terminal entry points, rejects any membership/hash/size/mtime change, and records a reproducible snapshot digest and generator hash.

The regenerated audit was independently checked against filesystem `st_mtime_ns`: every timestamp string is exact, the snapshot digest recomputes, and all original artifact memberships, SHA256 hashes and sizes are unchanged. A binary64-style JSON parse preserves every timestamp digit. Both real resume commands exited 0 with `already_complete`, `budget_exhausted`, and step 199,560.

Three new tests were written and observed failing before implementation. They cover timestamp transfer through a binary64 JSON consumer, direct Python publication with derived-audit exclusion, and rejection of a resume that changes only one nanosecond. The final scoped suite passed **76 tests**, with one existing PyTorch deprecation warning, in 8.60 seconds:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/anaconda3/envs/vlm_token/bin/python -m pytest -q --ignore=tests/test_sensitivity_v2.py --basetemp results/pytest-task6-audit-final-scoped-green
PYTHONDONTWRITEBYTECODE=1 /home/user/anaconda3/envs/vlm_token/bin/python scripts/audit_attention_terminal_resume.py
```

The only test exclusion is the parent-authorized, unrelated, concurrently developed Task 4 `tests/test_sensitivity_v2.py`; the first unfiltered run could not collect it because its implementation module did not yet exist. No Task 4 source or sensitivity output was edited. The original 72-test training-completion record above is retained as historical evidence; this correction adds the scoped regression verification.

## Remaining concerns

The 69% strict surrogate gate is not passed. Do not present this checkpoint as a successful ≥69% result or as verified integer/HLS accuracy. Any additional training or width change is outside this exhausted budget and requires a new decision.

A separate Task 4 correctness issue was reported to the parent: the older `StrictS3Controller` in `src/quant.py` quantizes attention residual only in the norm2 pre-hook, leaving the MLP skip unquantized. Task 6 fixes the real boundary before both consumers and has a regression test for it. Task 4 source, reports and frozen ranking were deliberately left unchanged during this run. The implication for the prior sensitivity report/ranking should be reviewed separately; it does not change the actual Task 6 boundary audited here.
