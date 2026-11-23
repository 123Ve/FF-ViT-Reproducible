# E07 concurrent virtual camera implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user has approved implementation; no agent delegation is requested. Track the following test-first tasks.

**Goal:** Add independent virtual camera producers with auditable serial FPGA service and CSV/JSON results.

**Architecture:** New host-only queue engine, cached FVIT transport, and standalone runner. Preserve the legacy entry point, firmware, and PL. Use a real local socket peer for offline transport tests.

**Tech Stack:** Python standard library, existing FVIT protocol and identity policy, Windows PowerShell.

**Spec:** `Cloud_test/docs/specs/2026-10-07-e07-multicamera-design.md` (approved chat design recorded without changing scope).

## Global constraints

- Independent producer threads, 30 FPS each; default streams 1/2/4 and duration 20 seconds.
- Each queue holds 3 frames and evicts oldest waiting frame when full.
- One outstanding request, Compact inference, unchanged SD/firmware/HLS/PL.
- Host monotonic timing; no drain throughput inflation or silent logging losses.
- No physical performance claim from offline tests.
- This checkout has no Git metadata; additive files are the change boundary, so commits/worktrees are unavailable.

## Task 1 Queue engine and accounting

Files: create `Cloud_test/iot_eval/camera_load.py` and `Cloud_test/tests/test_e07_multicamera.py`.
Interfaces: `CameraQueues(streams, capacity)`, `run_condition(service, streams, fps, duration, capacity=3, drain_timeout=5, emit=None)`, `summarize_condition(records, start_ns, end_ns, streams, missed_slots)`.

- [x] Write literal FIFO/overflow tests: inserting sequence 1,2,3,4 into capacity 3 evicts 1; dequeue returns 2. Fill two queues, expect service order 1,2,1,2.
- [x] Run `python3 -m unittest Cloud_test.tests.test_e07_multicamera -v` and observe missing behavior failures.
- [x] Implement locked deques, independent producer deadlines, serial dispatch, capture/dispatch/completion timestamps and terminal outcomes.
- [x] Add a slow service test proving producers continue while service blocks and drops occur. Use literal timestamps to assert queue=2 ms, service=5 ms, E2E=8 ms and exclude drain completions from FPS.
- [x] Verify conservation, finite zero-sample metrics, source deadline misses, failure shutdown and round-robin skipping empty queues.

## Task 2 Physical transport and evidence writer

Files: create `Cloud_test/iot_eval/camera_transport.py`; extend tests.
Interfaces: `ReplayTransport(connection, payload, request_id=0).infer(frame)`, `EvidenceWriter(path).emit(event)` and `.close()`.

- [x] Write a socketpair peer decoding two requests, checking distinct IDs and identical payloads, returning real compatible FVIT responses. Corrupt response ID and assert failure diagnostics.
- [x] Run tests red, implement one reusable packet with `HEADER.pack_into`, existing response validation and byte counters.
- [x] Test JSONL writer ordering and disk-failure propagation. Implement bounded event queue, batched writes and deterministic final flush, then run green.

## Task 3 Runner and Windows delivery

Files: create `Cloud_test/run_e07_multicamera.py`, `Cloud_test/windows/Run-E07-MultiCamera.ps1`, `Cloud_test/docs/E07_MULTICAMERA_RUNBOOK_CN.txt`; extend tests.
Interfaces: `main(argv=None)` launches physical listener or explicitly labeled simulation and writes frame/stream/summary CSV, report JSON and raw JSONL.

- [x] Test invalid duration/FPS/capacity rejection, complete simulated CLI outputs, hash validity, and nonzero exit plus partial outputs on transport failure.
- [x] Run red, implement parser, identity validation, warmup, 1/2/4 conditions, final exports and progress, keeping draining and active windows separate.
- [x] Run `python3 -m unittest Cloud_test.tests.test_e07_multicamera Cloud_test.tests.test_e07_cloud -v`.
- [x] Run an offline 1/2/4-camera suite at 30 FPS and slow simulated service; inspect generated CSV/JSON and evidence conservation.
- [x] Document Windows commands and package an additive ZIP patch with SHA256 manifest. Verify ZIP contents exclude firmware/PL/data replacements; no EXE build is claimed.

## Verification and review record

- 20 new multicamera tests; all 180 tests in Cloud_test/tests passed on Linux.
- Two independently reviewed failure-path findings were reproduced with failing
  tests and fixed: barrier cleanup on startup interruption/thread-start failure,
  and retaining current-condition/frame accounting after persistent log failure.
  Re-review reported no remaining Critical/Important findings.
- Offline timer simulations: nine 3-second conditions plus six 2-second
  conditions, all at 30 FPS per producer. Audited 2730 produced frames against
  CSV, JSON and raw capture events, timestamps, outcome conservation and hashes.
  These are HOST_SIMULATION results, not physical measurements.
- Python compilation passed. PowerShell wrapper has only static contract
  coverage here: no native PowerShell/Windows runtime or connected board is
  available. Those qualification steps remain with the user's test setup.
- Packaging test verified archive integrity, the exact host-only member list,
  every archived file digest and the external ZIP SHA256 sidecar. The packaging
  helper is `Cloud_test/tools/package_e07_multicamera_patch.py`.
