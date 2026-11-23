# ImageNet-1K Original HLS S3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run an isolated, reproducible ImageNet-1K sensitivity and strict original-HLS-width QAT pipeline, targeting 69% Top-1 without widening any mainline numeric boundary.

**Architecture:** A frozen numeric contract and provenance layer drives reusable ImageNet loaders, quantization hooks, sensitivity runners, progressive QAT, exact export, and copied HLS C simulation. Every long-running stage writes atomic resumable shards before deterministic aggregation.

**Tech Stack:** Python 3, PyTorch/timm/torchvision, pytest, JSON/CSV/Markdown, Vitis HLS C simulation.

**Spec:** `image1k_hls_s3_original/docs/specs/2026-10-01-imagenet1k-original-hls-s3-design.md`

## Global Constraints

- All created or modified task files stay under `/home/user/Desktop/ff_vit_re/image1k_hls_s3_original`; outside inputs are read-only.
- Mainline bit widths exactly match `/home/user/Desktop/FF_Vit/flash_vit_2/src/block0.cpp`; GELU is u3 and LN1/LN2/Q/K/V/A are s3.
- Full validation means exactly 50,000 unique ImageNet-1K samples under the frozen crop09 protocol.
- Use conda environment `/home/user/anaconda3/envs/vlm_token` and seed `20260923`.
- 69% Top-1 is an optimization target, never permission to widen the mainline contract or misreport a surrogate/probe result.
- Every result carries input/config/checkpoint hashes and is resumable without silently reusing incompatible shards.
- MLP budget is four full-data progressive epochs plus eight joint epochs and at most three two-epoch recovery branches; Attention budget is four full-data progressive epochs plus ten joint epochs and at most three two-epoch recovery branches.

---

### Task 1: Frozen contract, provenance, and scaffold

**Files:**
- Create: `image1k_hls_s3_original/config/original_hls_s3.yaml`
- Create: `image1k_hls_s3_original/src/contract.py`
- Create: `image1k_hls_s3_original/src/provenance.py`
- Create: `image1k_hls_s3_original/tests/test_contract.py`
- Create: `image1k_hls_s3_original/tests/test_provenance.py`
- Create: `image1k_hls_s3_original/README.md`

**Interfaces:**
- Produces: `load_contract(path) -> dict`, `validate_mainline_contract(config) -> None`, `sha256_file(path) -> str`, and atomic JSON writing.

- [ ] Write tests asserting the exact signedness/width table, rejecting GELU/LN/weight widening, and hashing files deterministically.
- [ ] Run the focused tests and observe failure because implementation is absent.
- [ ] Implement the minimal validated config/provenance API and directory contract.
- [ ] Run focused tests, then record an immutable input manifest containing all parent checkpoint hashes and external source paths.

### Task 2: Frozen ImageNet protocol and quantized model adapters

**Files:**
- Create: `image1k_hls_s3_original/src/data.py`
- Create: `image1k_hls_s3_original/src/model.py`
- Create: `image1k_hls_s3_original/src/quant.py`
- Create: `image1k_hls_s3_original/tests/test_data.py`
- Create: `image1k_hls_s3_original/tests/test_quant.py`

**Interfaces:**
- Consumes: validated contract from Task 1.
- Produces: deterministic train/calibration/selection/50k loaders; `StrictS3Controller` with per-operator and per-block enable masks; tensor error statistics.

- [ ] Write tests for crop09 transforms, class/sample identity, s3/u3 code domains, ties-to-even behavior, Q/K/V independent hooks, Softmax u3, and mask isolation.
- [ ] Run focused tests and observe expected failures.
- [ ] Adapt the existing HLS-196 and W3 implementations without modifying their source directories.
- [ ] Run tests and a one-batch CUDA smoke test that validates shapes and operator isolation.

### Task 3: Resumable operator/layer sensitivity engine

**Files:**
- Create: `image1k_hls_s3_original/src/sensitivity.py`
- Create: `image1k_hls_s3_original/scripts/run_sensitivity.py`
- Create: `image1k_hls_s3_original/scripts/aggregate_sensitivity.py`
- Create: `image1k_hls_s3_original/tests/test_sensitivity.py`

**Interfaces:**
- Consumes: Task 2 model/controller/loaders.
- Produces: atomic result shard per experiment and deterministic JSON/CSV/Markdown aggregation.

- [ ] Write failing tests for experiment enumeration: all required individual operators, four PlantVillage-compatible groups, 12×3 layer cases, and two cumulative schedules.
- [ ] Write failing tests that reject shards with mismatched config/checkpoint/data hashes or sample counts.
- [ ] Implement resumable evaluation and tensor error metric aggregation.
- [ ] Verify tests and run a stratified smoke set before scheduling full 50k jobs.

### Task 4: Execute full sensitivity suite

**Files:**
- Create: `image1k_hls_s3_original/metadata/calibration_manifest.jsonl`
- Create: `image1k_hls_s3_original/metadata/selection_manifest.jsonl`
- Create: `image1k_hls_s3_original/results/sensitivity/**`
- Create: `image1k_hls_s3_original/reports/{operator,layer,cumulative}_sensitivity.{json,csv,md}`

**Interfaces:**
- Consumes: Task 3 CLI.
- Produces: complete 50k paper-grade sensitivity reports.

- [ ] Freeze stratified calibration and selection manifests without overlap with the formal validation role.
- [ ] Fit histogram-MSE scales on calibration data only and freeze them.
- [ ] Run baseline, individual operator, grouped operator, 36 layer, and cumulative 50k cases with resume enabled.
- [ ] Aggregate and validate uniqueness, exact 50,000 sample counts, completeness, hash consistency, and sensitivity rankings.

### Task 5: Strict MLP S3/U3 progressive QAT

**Files:**
- Create: `image1k_hls_s3_original/src/losses.py`
- Create: `image1k_hls_s3_original/src/trainer.py`
- Create: `image1k_hls_s3_original/scripts/train_strict_mlp.py`
- Create: `image1k_hls_s3_original/tests/test_trainer.py`
- Create: `image1k_hls_s3_original/checkpoints/mlp/**`
- Create: `image1k_hls_s3_original/reports/mlp_qat_*.json`

**Interfaces:**
- Consumes: frozen sensitivity ranking, W3 QAT parent, full train loader.
- Produces: strict LN2 s3/GELU u3/M1 s11/M2 s13/FM s13 checkpoint and formal 50k result.

- [ ] Write failing tests for teacher freezing, trainable parameter groups, feature/logit KD, progressive masks, checkpoint recipe, resume state, and strict contract validation.
- [ ] Implement trainer with warmup+cosine, EMA, gradient clipping, LSQ scale gradients, feature reconstruction, atomic latest/best checkpoints.
- [ ] Run probe training and verify actual loss/gradient movement before full training.
- [ ] Train four progressive and eight joint full-data epochs, evaluate fixed selection checkpoints, run formal 50k on candidates, and if needed execute at most three two-epoch recovery branches until ≥69% or budget exhaustion.

### Task 6: Strict Attention S3 progressive QAT and joint recovery

**Files:**
- Create: `image1k_hls_s3_original/scripts/train_strict_attention.py`
- Create: `image1k_hls_s3_original/scripts/train_strict_joint.py`
- Create: `image1k_hls_s3_original/checkpoints/attention/**`
- Create: `image1k_hls_s3_original/checkpoints/joint/**`
- Create: `image1k_hls_s3_original/reports/attention_qat_*.json`
- Create: `image1k_hls_s3_original/reports/joint_qat_*.json`

**Interfaces:**
- Consumes: best strict MLP checkpoint and layer sensitivity ranking.
- Produces: full strict original-width encoder checkpoint and formal 50k result.

- [ ] Write failing tests for LN1/Q/K/V/A s3, Softmax u3, O s13/residual s15, Attention-side freeze/unfreeze, and joint recovery masks.
- [ ] Implement sensitivity-ordered Attention activation plus later joint full-encoder recovery without widening.
- [ ] Run probes to select stable learning/KD/feature-loss settings.
- [ ] Train four progressive and ten joint full-data epochs; formally evaluate candidates and if needed execute at most three two-epoch recovery branches until ≥69% or budget exhaustion.

### Task 7: Exact integer rebuild and export

**Files:**
- Create: `image1k_hls_s3_original/src/exact.py`
- Create: `image1k_hls_s3_original/scripts/build_exact.py`
- Create: `image1k_hls_s3_original/scripts/evaluate_exact.py`
- Create: `image1k_hls_s3_original/tests/test_exact.py`
- Create: `image1k_hls_s3_original/exact/**`

**Interfaces:**
- Consumes: best strict joint checkpoint.
- Produces: LUTs, integer scalar tables, packed weights, fixtures, layer traces, and exact 50k report.

- [ ] Write failing unit vectors for HLS rounding, clamp/wrap, requant, LN, GELU, Softmax, residuals, and packing.
- [ ] Port the PlantVillage LUT histogram/search logic while binding it to ImageNet calibration tensors.
- [ ] Build exact artifacts and verify deterministic rebuild hashes.
- [ ] Compare surrogate vs exact per layer on fixed fixtures, resolve all arithmetic mismatches, then run full exact 50k evaluation.

### Task 8: Isolated HLS C simulation and paper package

**Files:**
- Create: `image1k_hls_s3_original/hls/src/**`
- Create: `image1k_hls_s3_original/hls/data/**`
- Create: `image1k_hls_s3_original/hls/run_csim.tcl`
- Create: `image1k_hls_s3_original/scripts/run_hls_csim.py`
- Create: `image1k_hls_s3_original/reports/hls_csim.json`
- Create: `image1k_hls_s3_original/reports/stage_accuracy_summary.md`
- Create: `image1k_hls_s3_original/paper/**`

**Interfaces:**
- Consumes: Task 7 HLS-compatible artifacts and traces.
- Produces: reproducible C simulation logs, bit-exact comparison, and paper tables/plot data.

- [ ] Copy only required original HLS sources into the isolated directory and assert source-directory hashes remain unchanged.
- [ ] Generate testbench fixtures and run C simulation for fixed samples with layer trace comparison.
- [ ] Run deterministic report aggregation for all stages and clearly label probe, surrogate 50k, exact 50k, and HLS sample results.
- [ ] Run the complete test suite, completeness validator, hash audit, and produce the final Chinese methodology/results document.
