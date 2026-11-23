# E06 Network BOOT and Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated E06-derived ZCU102 standalone BOOT image with physical TCP communication and a PC dashboard, while preserving every source file outside `Cloud_test`.

**Architecture:** Copy the minimal E06 hardware and boot inputs into a hash-verified vendor bundle, build a new A53 standalone application with lwIP 2.2 on GEM3, and retain the E06 DMA/inference/telemetry functions. A Flask service accepts the same framed protocol used by the host loopback and exposes session metrics to a browser dashboard; E06-stage accuracy remains explicitly unavailable.

**Tech Stack:** Vitis/Vivado 2025.1, Bootgen, Zynq UltraScale+ standalone BSP, lwIP 2.2 raw API, xilffs, AXI DMA/APM, INA226/SysMon, C11, Python 3.13, Flask 3.1, Plotly 6.3, unittest.

**Spec:** `Cloud_test/docs/specs/2026-09-27-e06-plantvillage-iot-cloud-design.md`

## Global Constraints

- Do not modify any file outside `/home/user/Desktop/ff_vit_re/Cloud_test`.
- Treat E06, PlantVillage, HLS, quantization, and dataset trees as read-only source inputs.
- Copy every required build input into `Cloud_test/vendor` and record source path, bytes, and SHA-256.
- Stage 1 uses the original E06 model and must display PlantVillage accuracy as `N/A`.
- Use PC `192.168.10.1/24`, ZCU102 `192.168.10.2/24`, and TCP port `5001`.
- Keep the E06 250 MHz PL image, PS/AXI/DMA/APM topology, stream widths, and weight layout unchanged.
- Report INA226 monitored-rail power, never wall-plug power.
- Generated workspaces, ELF files, BIF files, BOOT images, logs, and results stay under `Cloud_test`.
- The workspace is not a Git repository. Do not initialize one implicitly; use SHA-256 checkpoint manifests instead of commit steps.
- This plan ends at the E06 physical-network gate. PlantVillage hardware integration receives a separate plan after the gate passes.

## File map

- `Cloud_test/tools/import_e06.py`: copy and fingerprint the immutable E06 input set.
- `Cloud_test/vendor/source_manifest.json`: provenance of copied build inputs.
- `Cloud_test/iot_eval/protocol.py`: host protocol codec and message definitions.
- `Cloud_test/firmware/common/fvit_protocol.{h,c}`: portable C wire codec.
- `Cloud_test/firmware/e06_net/e06_inference.{h,c}`: E06 SD/DMA/accelerator wrapper.
- `Cloud_test/firmware/e06_net/e06_telemetry.{h,c}`: INA226/SysMon sampling.
- `Cloud_test/firmware/e06_net/e06_network.{h,c}`: lwIP netif and TCP server.
- `Cloud_test/firmware/e06_net/main.c`: firmware lifecycle and command dispatch.
- `Cloud_test/build_scripts/build_e06_net.py`: isolated Vitis platform/application build.
- `Cloud_test/build_scripts/make_e06_net_boot.py`: BIF and Bootgen invocation.
- `Cloud_test/cloud/session_store.py`: validated event/session aggregation.
- `Cloud_test/cloud/board_server.py`: board-facing TCP collector.
- `Cloud_test/dashboard/app.py`: Flask JSON endpoints and dashboard route.
- `Cloud_test/dashboard/templates/index.html`: browser UI.
- `Cloud_test/dashboard/static/dashboard.js`: polling and Plotly rendering.
- `Cloud_test/dashboard/static/style.css`: dashboard layout.
- `Cloud_test/results/`: physical run outputs only.

---

### Task 1: Immutable E06 Vendor Bundle

**Files:**
- Create: `Cloud_test/tools/import_e06.py`
- Create: `Cloud_test/tests/test_import_e06.py`
- Create on execution: `Cloud_test/vendor/e06_base/*`
- Create on execution: `Cloud_test/vendor/source_manifest.json`

**Interfaces:**
- Consumes: explicit `--e06-root` source directory and `--destination` under `Cloud_test/vendor`.
- Produces: `import_e06(source_root: Path, destination: Path) -> dict[str, ArtifactRecord]`, where each record has `source`, `copied_path`, `bytes`, and `sha256`.

- [ ] **Step 1: Write the failing copy/isolation tests**

```python
def test_import_copies_bytes_and_records_source_hash(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "Cloud_test" / "vendor" / "e06_base"
    make_minimal_e06_fixture(source)
    manifest = import_e06(source, destination)
    assert (destination / "hw/e06_measurement_250mhz.xsa").read_bytes() == b"xsa"
    assert manifest["xsa"]["sha256"] == hashlib.sha256(b"xsa").hexdigest()
    assert manifest["xsa"]["source"] == str((source / "xsa").resolve())

def test_import_refuses_destination_outside_cloud_test(tmp_path):
    with pytest.raises(ValueError, match="Cloud_test/vendor"):
        import_e06(tmp_path / "source", tmp_path / "elsewhere")
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest Cloud_test.tests.test_import_e06 -v`

Expected: import error because `Cloud_test.tools.import_e06` does not exist.

- [ ] **Step 3: Implement the explicit allowlist importer**

The allowlist must copy exactly:

```python
E06_FILES = {
    "xsa": "board_250mhz_advanced/workspace/e06m_platform/export/e06m_platform/hw/e06_measurement_250mhz.xsa",
    "bitstream": "board_250mhz_advanced/deploy/design_1_wrapper.bit",
    "fsbl": "board_250mhz_advanced/deploy/fsbl.elf",
    "pmufw": "board_250mhz_advanced/deploy/pmufw.elf",
    "weights": "inputs/weights.bin",
    "input": "inputs/input.bin",
    "output": "inputs/output.bin",
    "weight_layout": "board_250mhz_advanced/src/weight_layout.h",
    "inference_main": "board_250mhz_advanced/src/main.c",
    "power_main": "board_250mhz_advanced/power_src/main.c",
    "power_monitor_c": "board_250mhz_advanced/power_src/power_monitor.c",
    "power_monitor_h": "board_250mhz_advanced/power_src/power_monitor.h",
    "power_math_c": "board_250mhz_advanced/power_src/power_math.c",
    "power_math_h": "board_250mhz_advanced/power_src/power_math.h",
    "rail_map": "board_250mhz_advanced/power_src/zcu102_ina226_rails.csv",
}
```

Reject symlinks, missing files, duplicate destinations, and destinations outside the resolved `Cloud_test/vendor` root. Copy with `shutil.copy2`, then hash the destination and require source/destination hashes to match.

- [ ] **Step 4: Run tests and import the real bundle**

Run:

```bash
python -m unittest Cloud_test.tests.test_import_e06 -v
python Cloud_test/tools/import_e06.py \
  --e06-root /home/user/Desktop/FF_Vit/E04_weight_schedule/E06_measurement \
  --destination /home/user/Desktop/ff_vit_re/Cloud_test/vendor/e06_base \
  --manifest /home/user/Desktop/ff_vit_re/Cloud_test/vendor/source_manifest.json
```

Expected: tests pass; manifest records the known E06 weights hash `0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7` and BOOT-component hashes.

- [ ] **Step 5: Save a checkpoint manifest**

Run: `python Cloud_test/tools/tree_manifest.py Cloud_test/vendor > Cloud_test/checkpoints/task01.sha256.json`

Expected: only `Cloud_test/vendor` paths occur in the output.

### Task 2: Protocol Extension and Session Identity

**Files:**
- Modify: `Cloud_test/iot_eval/protocol.py`
- Create: `Cloud_test/iot_eval/messages.py`
- Modify: `Cloud_test/tests/test_protocol.py`
- Create: `Cloud_test/tests/test_messages.py`

**Interfaces:**
- Consumes: existing `Message`, `read_message()`, and `write_message()`.
- Produces: `Hello`, `Telemetry`, `Command`, and `InferenceResult` dataclasses with `to_message(request_id: int) -> Message` and `from_message(message: Message)`.

- [ ] **Step 1: Add failing fragmentation, limit, and identity tests**

```python
def test_read_message_accepts_one_byte_reads():
    encoded = encode_for_test(Message("hello", 9, {"model": "E06"}))
    assert read_message(OneByteReader(encoded)).kind == "hello"

def test_hello_requires_phase_and_artifact_hashes():
    with self.assertRaisesRegex(ValueError, "artifact_hashes"):
        Hello(phase="E06_PHYSICAL", firmware_sha256="a" * 64,
              artifact_hashes={})

def test_payload_larger_than_four_megabytes_is_rejected_before_allocation():
    header = make_header(kind="cloud_frame", payload_len=4 * 1024 * 1024 + 1)
    with self.assertRaisesRegex(ProtocolError, "size limit"):
        read_message(io.BytesIO(header))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest Cloud_test.tests.test_protocol Cloud_test.tests.test_messages -v`

Expected: failure because typed messages and new kinds are absent.

- [ ] **Step 3: Implement typed messages and protocol kinds**

Add codes for `hello`, `telemetry`, `command`, and `inference_result`. Validate SHA-256 strings as 64 lowercase hexadecimal characters, phases as `HOST_LOOPBACK`, `E06_PHYSICAL`, or `PLANT_PHYSICAL`, class IDs as non-negative integers, and telemetry units explicitly (`power_uW`, `temperature_mC`, `ticks`).

- [ ] **Step 4: Run all host protocol tests**

Run: `python -m unittest Cloud_test.tests.test_protocol Cloud_test.tests.test_messages Cloud_test.tests.test_network_flow -v`

Expected: all pass without warnings.

- [ ] **Step 5: Save the task checkpoint**

Run: `python Cloud_test/tools/tree_manifest.py Cloud_test/iot_eval Cloud_test/tests > Cloud_test/checkpoints/task02.sha256.json`

### Task 3: Portable C Wire Codec

**Files:**
- Create: `Cloud_test/firmware/common/fvit_protocol.h`
- Create: `Cloud_test/firmware/common/fvit_protocol.c`
- Create: `Cloud_test/firmware/common/tests/test_fvit_protocol.c`
- Create: `Cloud_test/tests/test_c_protocol.py`

**Interfaces:**
- Produces: `int fvit_header_encode(uint8_t out[20], const fvit_header_t *header)` and `int fvit_header_decode(fvit_header_t *out, const uint8_t in[20])`.
- Wire compatibility: header bytes must exactly match Python `HEADER = struct.Struct("!4sBBHIII")`.

- [ ] **Step 1: Write a failing Python-driven C compatibility test**

```python
def test_c_encoder_matches_python_wire_header(tmp_path):
    binary = compile_c_test(tmp_path, "test_fvit_protocol.c", "fvit_protocol.c")
    raw = subprocess.check_output([binary, "encode"]).strip()
    expected = HEADER.pack(b"FVIT", 1, 10, 0, 0x01020304, 17, 150528).hex().encode()
    assert raw == expected
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest Cloud_test.tests.test_c_protocol -v`

Expected: compiler failure because the C codec files are absent.

- [ ] **Step 3: Implement the codec without packed-struct aliasing**

Encode and decode every multibyte field with explicit byte shifts. Reject bad magic, unsupported version, unknown message type, metadata over 65,536 bytes, and payload over 4 MiB. Return named error constants from `fvit_protocol.h`.

- [ ] **Step 4: Run C/Python compatibility tests**

Run: `python -m unittest Cloud_test.tests.test_c_protocol Cloud_test.tests.test_protocol -v`

Expected: Python and C emit identical literal header bytes and reject the same invalid sizes.

- [ ] **Step 5: Save checkpoint hashes**

Run: `python Cloud_test/tools/tree_manifest.py Cloud_test/firmware/common > Cloud_test/checkpoints/task03.sha256.json`

### Task 4: E06 Inference and Telemetry Modules

**Files:**
- Create: `Cloud_test/firmware/e06_net/e06_inference.h`
- Create: `Cloud_test/firmware/e06_net/e06_inference.c`
- Create: `Cloud_test/firmware/e06_net/e06_telemetry.h`
- Create: `Cloud_test/firmware/e06_net/e06_telemetry.c`
- Copy: `Cloud_test/vendor/e06_base/include/weight_layout.h`
- Create: `Cloud_test/tests/test_firmware_source_contract.py`

**Interfaces:**
- Produces: `int e06_inference_init(const char *weights, const char *input, const char *reference)`; `int e06_inference_run(e06_result_t *out)`; `int e06_telemetry_init(void)`; `int e06_telemetry_sample(e06_telemetry_t *out)`.
- `e06_result_t` includes mismatch count, predicted class, total ticks, PL ticks, MM2S ticks, and S2MM ticks.
- `e06_telemetry_t` includes timestamp ticks, monitored power in µW, temperature in m°C, and sensor-valid flags.

- [ ] **Step 1: Write failing source-contract tests**

Tests preprocess/compile both modules against a small fake BSP and require the public functions to link. A runtime fake DMA test must return `mismatch_count == 0` for equal literal output arrays and a nonzero value after changing one code.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest Cloud_test.tests.test_firmware_source_contract -v`

Expected: missing module/source failure.

- [ ] **Step 3: Extract E06 behavior into focused modules**

Copy logic from the vendor snapshot, not the immutable source. Preserve buffer sizes, cache operations, DMA ordering, accelerator timeouts, APM scopes, 19-bit logit sign extension, and exact comparison. Port INA226/SysMon code from the copied power source and propagate sensor failure via flags rather than fabricated zeros.

- [ ] **Step 4: Run host contract tests**

Run: `python -m unittest Cloud_test.tests.test_firmware_source_contract -v`

Expected: modules compile and literal mismatch tests pass.

- [ ] **Step 5: Save checkpoint hashes**

Run: `python Cloud_test/tools/tree_manifest.py Cloud_test/firmware/e06_net > Cloud_test/checkpoints/task04.sha256.json`

### Task 5: lwIP GEM3 TCP Firmware

**Files:**
- Create: `Cloud_test/firmware/e06_net/net_config.h`
- Create: `Cloud_test/firmware/e06_net/e06_network.h`
- Create: `Cloud_test/firmware/e06_net/e06_network.c`
- Create: `Cloud_test/firmware/e06_net/main.c`
- Create: `Cloud_test/tests/test_firmware_network_contract.py`

**Interfaces:**
- Consumes: C codec, inference, and telemetry modules.
- Produces: `int e06_network_start(void)` and `void e06_network_poll(void)` using lwIP raw callbacks; the board at `192.168.10.2` actively connects to the PC collector at `192.168.10.1:5001`.

- [ ] **Step 1: Write failing network state-machine tests**

Compile with a fake lwIP shim and drive callbacks with fragmented headers/payloads. Assert that HELLO is sent once per successful connection, `run_once` calls inference exactly once, an unknown command yields `error`, and disconnect frees the PCB state.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest Cloud_test.tests.test_firmware_network_contract -v`

Expected: missing firmware network module.

- [ ] **Step 3: Implement bounded raw-API state machine**

Use static buffers only. Accumulate the 20-byte header before allocating/accepting metadata, reject payloads over protocol limits, call `tcp_recved()` for consumed bytes, and use `tcp_write(..., TCP_WRITE_FLAG_COPY)` followed by `tcp_output()`. Main initializes platform, SD, inference, telemetry, lwIP timers, and polls forever. UART prints build phase, IP, port, and every terminal error.

- [ ] **Step 4: Run network and codec tests**

Run: `python -m unittest Cloud_test.tests.test_firmware_network_contract Cloud_test.tests.test_c_protocol -v`

Expected: fragmentation, error, inference-call-count, and disconnect tests pass.

- [ ] **Step 5: Save checkpoint hashes**

Run: `python Cloud_test/tools/tree_manifest.py Cloud_test/firmware > Cloud_test/checkpoints/task05.sha256.json`

### Task 6: Isolated Vitis Build and BOOT Image

**Files:**
- Create: `Cloud_test/build_scripts/build_e06_net.py`
- Create: `Cloud_test/build_scripts/make_e06_net_boot.py`
- Create: `Cloud_test/tests/test_build_contract.py`
- Create on execution: `Cloud_test/build/e06_net_workspace/`
- Create on execution: `Cloud_test/boot/BOOT_E06_NET.BIN`
- Create on execution: `Cloud_test/boot/BOOT_E06_NET.manifest.json`

**Interfaces:**
- `build_e06_net.py --xsa PATH --workspace PATH --source-dir PATH` produces `e06_net.elf`.
- `make_e06_net_boot.py --fsbl PATH --pmufw PATH --bit PATH --app PATH --output PATH` produces BIF, BOOT image, and provenance manifest.

- [ ] **Step 1: Write failing build-policy tests**

```python
def test_build_script_enables_required_bsp_libraries():
    config = make_build_config(...)
    assert config.libraries == {"xilffs", "lwip220"}

def test_boot_builder_refuses_output_outside_cloud_test(tmp_path):
    with self.assertRaisesRegex(ValueError, "Cloud_test/boot"):
        build_boot(..., output=tmp_path / "BOOT.BIN")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest Cloud_test.tests.test_build_contract -v`

Expected: build modules absent.

- [ ] **Step 3: Implement deterministic builders**

Create a standalone 64-bit `psu_cortexa53_0` platform from the copied XSA. Add `xilffs_v5_4` and `lwip220_v1_2`, copy only `Cloud_test/firmware` sources into the generated app, build, and verify the ELF exists. Generate a BIF in this order: FSBL, PMUFW, PL bitstream, A53 EL3 application. Never remove or overwrite a pre-existing workspace; require `--clean-generated` to remove only the exact resolved `Cloud_test/build/e06_net_workspace` path.

- [ ] **Step 4: Run policy tests and actual headless Vitis build**

Run:

```bash
python -m unittest Cloud_test.tests.test_build_contract -v
/opt/vivado/2025.1/Vitis/bin/vitis -s Cloud_test/build_scripts/build_e06_net.py -- \
  --xsa Cloud_test/vendor/e06_base/hw/e06_measurement_250mhz.xsa \
  --workspace Cloud_test/build/e06_net_workspace \
  --source-dir Cloud_test/firmware
python Cloud_test/build_scripts/make_e06_net_boot.py \
  --fsbl Cloud_test/vendor/e06_base/boot/fsbl.elf \
  --pmufw Cloud_test/vendor/e06_base/boot/pmufw.elf \
  --bit Cloud_test/vendor/e06_base/hw/design_1_wrapper.bit \
  --app Cloud_test/build/e06_net_workspace/e06_net/build/e06_net.elf \
  --output Cloud_test/boot/BOOT_E06_NET.BIN
```

Expected: Vitis and Bootgen exit 0; BOOT image is nonempty; manifest hashes every BIF input and output.

- [ ] **Step 5: Verify no external writes and save checkpoint**

Re-hash every immutable source from Task 1 and compare with `source_manifest.json`. Run `find Cloud_test/build Cloud_test/boot -type f` and save it with hashes to `Cloud_test/checkpoints/task06.sha256.json`.

### Task 7: Cloud Session Store and Board Collector

**Files:**
- Create: `Cloud_test/cloud/__init__.py`
- Create: `Cloud_test/cloud/session_store.py`
- Create: `Cloud_test/cloud/board_server.py`
- Create: `Cloud_test/tests/test_session_store.py`
- Create: `Cloud_test/tests/test_board_server.py`

**Interfaces:**
- Produces: `SessionStore.begin(hello: Hello) -> str`, `append(session_id: str, event: dict)`, and `snapshot(session_id: str) -> dict`.
- Produces: `BoardCollector(address, store)` which accepts HELLO, inference, telemetry, and error messages.

- [ ] **Step 1: Write failing real-socket and aggregation tests**

Assert E06 HELLO creates phase `E06_PHYSICAL`, mismatched hashes reject the session, telemetry preserves integer units, reconnect retains completed events, and `accuracy` is `None` for every E06-stage snapshot.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest Cloud_test.tests.test_session_store Cloud_test.tests.test_board_server -v`

Expected: modules absent.

- [ ] **Step 3: Implement append-only JSONL sessions**

Write `session.json`, `events.jsonl`, and atomic `summary.json` below `Cloud_test/results/sessions/<session-id>`. Validate phase/model/hash identity before accepting measurement events. Derive latency, FPS, bytes, power, temperature, and error counts; keep `accuracy: null` and `accuracy_reason: "E06 model is not PlantVillage"`.

- [ ] **Step 4: Run session and existing integration tests**

Run: `python -m unittest Cloud_test.tests.test_session_store Cloud_test.tests.test_board_server Cloud_test.tests.test_network_flow -v`

Expected: all pass using real localhost sockets and temporary result directories.

- [ ] **Step 5: Save checkpoint hashes**

Run: `python Cloud_test/tools/tree_manifest.py Cloud_test/cloud > Cloud_test/checkpoints/task07.sha256.json`

### Task 8: Flask/Plotly Dashboard

**Files:**
- Create: `Cloud_test/dashboard/__init__.py`
- Create: `Cloud_test/dashboard/app.py`
- Create: `Cloud_test/dashboard/templates/index.html`
- Create: `Cloud_test/dashboard/static/dashboard.js`
- Create: `Cloud_test/dashboard/static/style.css`
- Create: `Cloud_test/tests/test_dashboard.py`

**Interfaces:**
- `create_app(store: SessionStore) -> flask.Flask`.
- Endpoints: `GET /`, `GET /api/sessions`, `GET /api/sessions/<id>`, `GET /api/health`.

- [ ] **Step 1: Write failing Flask client tests**

```python
def test_e06_dashboard_never_displays_numeric_accuracy(client, e06_session):
    payload = client.get(f"/api/sessions/{e06_session}").get_json()
    assert payload["accuracy"] is None
    assert payload["accuracy_reason"] == "E06 model is not PlantVillage"

def test_health_reports_collector_and_latest_phase(client):
    assert client.get("/api/health").get_json()["phase"] == "E06_PHYSICAL"
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest Cloud_test.tests.test_dashboard -v`

Expected: dashboard package absent.

- [ ] **Step 3: Implement API and browser dashboard**

Render connection/model cards; latency/throughput, bytes/reduction, power/energy, and temperature charts; recent errors; and artifact hashes. Use responsive HTML/CSS and local Plotly package assets or a vendored minified file under `Cloud_test/dashboard/static`; do not require an internet CDN during experiments. Show a visible evidence-phase badge and `N/A` accuracy card for E06.

- [ ] **Step 4: Run dashboard and session tests**

Run: `python -m unittest Cloud_test.tests.test_dashboard Cloud_test.tests.test_session_store -v`

Expected: all API assertions pass; Flask reports no template/static errors.

- [ ] **Step 5: Save checkpoint hashes**

Run: `python Cloud_test/tools/tree_manifest.py Cloud_test/dashboard > Cloud_test/checkpoints/task08.sha256.json`

### Task 9: Operator Commands and Physical-Test Handoff

**Files:**
- Create: `Cloud_test/run_cloud.py`
- Create: `Cloud_test/run_dashboard.py`
- Create: `Cloud_test/config/e06_physical.json`
- Modify: `Cloud_test/README.md`
- Create: `Cloud_test/docs/E06_BOARD_RUNBOOK_CN.md`
- Create: `Cloud_test/tests/test_cli_help.py`

**Interfaces:**
- `run_cloud.py` starts the board collector at `192.168.10.1:5001` and writes sessions below `Cloud_test/results`.
- `run_dashboard.py` serves the GUI at `127.0.0.1:8080`.

- [ ] **Step 1: Write failing CLI help/config tests**

Run each entry point with `--help`, require exit code 0, and load `e06_physical.json` to assert board IP, PC IP, port, expected E06 weights hash, and phase.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest Cloud_test.tests.test_cli_help -v`

Expected: entry points/config absent.

- [ ] **Step 3: Implement entry points and Chinese runbook**

The runbook must specify SD files, ZCU102 switch/boot steps, direct Ethernet static-IP commands, firewall port, UART expected lines, cloud/dashboard commands, test sequence, and how to archive a session. It must state that `BOOT_E06_NET.BIN` does not provide PlantVillage accuracy.

- [ ] **Step 4: Run the full automated verification suite**

Run:

```bash
python -m unittest discover -s Cloud_test/tests -v
python -m compileall -q Cloud_test
python Cloud_test/run_smoke.py \
  --boot Cloud_test/boot/BOOT_E06_NET.BIN \
  --weights Cloud_test/vendor/e06_base/data/weights.bin \
  --image Cloud_test/fixtures/host_smoke/leaf.jpg \
  --output Cloud_test/results/host_loopback_final
```

Expected: all tests pass, compileall exits 0, host loopback status is `HOST_LOOPBACK_PASS`, and the report explicitly says it is not physical-board evidence.

- [ ] **Step 5: Create the release manifest**

Run: `python Cloud_test/tools/tree_manifest.py Cloud_test > Cloud_test/checkpoints/e06_network_release.sha256.json`.

Expected: manifest includes BOOT, source, tests, dashboard, and documentation; immutable-source recheck still matches Task 1.

### Task 10: Physical ZCU102 Gate

**Files:**
- Create during run: `Cloud_test/results/sessions/<session-id>/*`
- Create after run: `Cloud_test/results/e06_physical_gate.json`

**Interfaces:**
- Consumes: SD card with `BOOT_E06_NET.BIN`, E06 `weights.bin`, `input.bin`, and `output.bin`; direct Ethernet connection; UART console.
- Produces: signed-off physical gate containing firmware/artifact identity, exact mismatch count, TCP event log, latency/throughput, power/temperature availability, and failures.

- [ ] **Step 1: Configure and verify the PC link**

Set `192.168.10.1/24`, confirm link carrier, and start collector/dashboard. Record `ip addr`, `ethtool`, collector startup, and host clock in the session directory.

- [ ] **Step 2: Boot the board and verify identity before inference**

Require UART phase `E06_PHYSICAL`, board IP `192.168.10.2`, expected firmware hash, and expected E06 weights hash. Reject a session if any identity differs.

- [ ] **Step 3: Run exact inference and network transfer commands**

Require `BIT_EXACT_MISMATCHES=0`, one successful inference response, one telemetry response or an explicit sensor-unavailable flag, and successful full-payload/compact-result transfers.

- [ ] **Step 4: Run the bounded measurement session**

Perform warm-up plus ten repetitions of 100 serial frames. Preserve UART, TCP events, summary JSON, power/temperature samples, and dashboard export.

- [ ] **Step 5: Independently verify and publish the gate**

Run the analysis CLI twice from raw events and require identical summaries. Write `e06_physical_gate.json` with `passed: true` only if hashes match, mismatch count is zero, no requested frame is dropped, and physical TCP events are present. Otherwise record `passed: false` and stop before the PlantVillage implementation plan.
