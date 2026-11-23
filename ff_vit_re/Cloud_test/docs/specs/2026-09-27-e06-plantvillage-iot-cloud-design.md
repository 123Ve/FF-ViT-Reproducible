# E06 / PlantVillage IoT Cloud Evaluation Design

Date: 2026-09-27

## Objective

Build an isolated, reproducible ZCU102 IoT evaluation under
`/home/user/Desktop/ff_vit_re/Cloud_test` without modifying any source artifact
outside that directory. The work first proves physical Ethernet communication
with the existing E06 accelerator, then produces a PlantVillage-specific image
and a PC dashboard for deployment-level measurements.

The final evidence must distinguish host-only loopback, E06 physical-network
bring-up, and PlantVillage hardware inference. No result from an earlier phase
may be presented as evidence for a later phase.

## Immutable source inputs

The following trees are read-only inputs:

- `/home/user/Desktop/FF_Vit/E04_weight_schedule/E06_measurement/`
- `/home/user/Desktop/FF_Vit/flash_vit_2/PlantVillage_bin/`
- `/home/user/Desktop/FF_Vit/flash_vit_2/flash_vit/`
- `/home/user/Desktop/ff_vit_re/quantization_final/`
- `/home/user/Desktop/ff_vit_re/datasets/PlantVillage/`

All required files are copied into `Cloud_test/vendor/` with a manifest that
records source path, byte size, and SHA-256. Generated workspaces, logs,
bitstreams, ELF files, BOOT images, dataset fixtures, and measurements remain
under `Cloud_test`.

The existing E06 and PlantVillage encoder weight files both contain 2,772,096
bytes but have different SHA-256 values. They are not interchangeable evidence.
PlantVillage Patch and Head parameters are also model-specific and may be
embedded in the PL image.

## Approaches considered

### Selected: two-stage standalone bare-metal deployment

Reuse the E06 XSA and measurement application structure, add lwIP on PS GEM3,
and generate a new standalone BOOT image. First use the unmodified E06 model to
prove Ethernet and telemetry. Then rebuild the model-dependent PL contents and
software inputs for PlantVillage.

This approach preserves the measured E06 hardware shell, does not require an
operating system, and isolates model conversion risk from Ethernet bring-up.

### Rejected: direct PlantVillage integration before network bring-up

This combines model, bitstream, firmware, network, and dashboard failures in a
single debugging step. It is slower to diagnose and produces ambiguous results.

### Rejected: PetaLinux deployment

Linux would simplify host networking but adds an unnecessary boot image,
device-tree, driver, and root-filesystem workflow. The existing E06 design and
the available lwIP 2.2 standalone service are sufficient.

## Repository layout

```text
Cloud_test/
├── vendor/
│   ├── e06_base/             # copied XSA, bitstream, boot components and source
│   ├── plantvillage/         # copied model-dependent deployment artifacts
│   └── source_manifest.json
├── firmware/
│   ├── common/               # protocol, CRC, telemetry and network helpers
│   ├── e06_net/              # stage-one standalone application
│   └── plant_iot/            # stage-two PlantVillage application
├── build/                    # generated Vitis workspaces and build logs
├── boot/
│   ├── BOOT_E06_NET.BIN
│   └── BOOT_PLANT_IOT.BIN
├── fixtures/                 # bounded, labeled test fixtures copied locally
├── cloud/                    # board-facing TCP collector and session store
├── dashboard/                # Flask/Plotly browser interface
├── analysis/                 # reproducible metric summaries and paper tables
├── results/                  # raw immutable session data and derived summaries
├── tests/
└── docs/
```

Generated build directories are disposable. Source manifests and raw result
sessions are retained.

## Stage 1: E06 physical Ethernet bring-up

### Firmware

Create a standalone A53 application against the copied E06 XSA. The BSP adds
`xilffs` and `lwip220`. GEM3 uses a static IPv4 address:

- PC: `192.168.10.1/24`
- ZCU102: `192.168.10.2/24`
- TCP port: `5001`

The application loads the copied E06 `weights.bin`, `input.bin`, and
`output.bin` from SD, verifies one inference exactly, initializes Ethernet, and
sends a HELLO message containing build identity and artifact hashes. It then
supports:

- health/identity request;
- one E06 inference request;
- telemetry snapshot;
- repeated latency test;
- full-payload transfer test;
- compact-result transfer test.

The original E06 files are not modified. The new ELF and
`BOOT_E06_NET.BIN` are created under `Cloud_test`.

### Stage-one boundary

This phase establishes physical Ethernet transport and revalidates E06
bit-exact output, latency, throughput, power, and temperature. It does not
report PlantVillage accuracy. Dashboard accuracy fields display `N/A` with an
explicit reason.

## Stage 2: PlantVillage hardware integration

Copy the canonical PlantVillage encoder weights, LUTs, Patch parameters, Head
parameters, and validation fixtures into `vendor/plantvillage`. Rebuild the PL
image only when the copied source audit proves that model-dependent Patch/Head
data are embedded in the existing bitstream. Preserve the E06 PS/AXI/DMA/APM
topology, clock target, stream widths, and external weight layout.

`BOOT_PLANT_IOT.BIN` must:

- identify itself as PlantVillage and report every artifact hash;
- reject E06 weights by expected SHA-256;
- load bounded labeled fixtures from SD;
- perform FPGA inference and transmit the predicted class and logits summary;
- collect matched latency, power, temperature, and byte counters;
- support an image-upload baseline using the same fixture payload.

PlantVillage accuracy is enabled only after a local fixture passes software
bit-exact comparison and the board returns the same predicted class/logit codes.

## Network protocol

The existing `FVIT` framed protocol remains the host reference. The wire header
contains magic, protocol version, message kind, request ID, metadata length,
and payload length in network byte order. Metadata is UTF-8 JSON and bulk data
is binary.

Required message classes are:

- `hello`: board/build/model/artifact identity;
- `cloud_frame`: full fixture payload for cloud-only baseline;
- `edge_result`: class, confidence/logit summary, inference ticks and label ID;
- `telemetry`: rail power, temperature and frame counters;
- `command`: bounded test commands;
- `ack`, `cloud_result`, and `error`.

Every message is size-bounded and request IDs pair commands with responses.
Malformed messages yield an error and do not start the accelerator.

## Dataset and experimental protocol

The initial physical test uses one fixed E06 fixture. The final PlantVillage
test uses a deterministic stratified subset copied under `Cloud_test/fixtures`.
The manifest records original relative path, ground-truth class, payload hash,
and split provenance.

For each PlantVillage fixture, measure two modes:

1. Cloud-only baseline: transfer the complete input payload to the PC; the PC
   evaluates or verifies the cloud prediction.
2. Edge inference: run FF-ViT on ZCU102 and transfer only prediction metadata.

Accuracy uses the same ordered fixture manifest in both modes. Transfer byte
counts include the complete application protocol but exclude Ethernet framing
unless a packet capture is explicitly used. Timing scopes are reported
separately for PL inference, board application, network RTT, and end-to-end
latency.

## Telemetry and metrics

Reuse the E06 measurement definitions:

- ZCU102 power is the sum of monitored INA226 rails, not wall-plug power;
- dynamic power is matched load minus configured idle;
- temperature is on-chip SysMon temperature;
- inference timing includes explicitly documented DMA/control boundaries;
- SD file loading is excluded from accelerator latency and reported separately
  if measured.

The final summary reports:

- sample count and Top-1 accuracy;
- per-class counts and confusion matrix;
- PL, board, network, and end-to-end latency distributions;
- completed frames/s;
- full-frame and compact-result uplink bytes;
- uplink reduction percentage;
- configured-idle, cloud-transfer, and edge-inference power;
- load and dynamic energy per completed frame;
- temperature versus time during a sustained run;
- inference/network errors and dropped samples.

Transmission energy is reported only as a measured board-level phase delta.
It is not described as radio, PHY-only, or wall-plug energy.

## Dashboard

The PC runs a Flask service. A browser page polls session JSON and uses Plotly
for charts. It displays:

- board connection, IP, firmware/model identity and artifact hashes;
- current image, ground truth, prediction and confidence;
- cumulative Top-1 and evaluated sample count;
- latency and throughput;
- bytes per mode and uplink reduction;
- rail power, energy/frame and temperature timeline;
- confusion matrix and recent errors;
- evidence phase (`HOST_LOOPBACK`, `E06_PHYSICAL`, or `PLANT_PHYSICAL`).

The dashboard never converts host-loopback values into board measurements.
Each exported result contains the phase and session manifest.

## Failure handling

- Artifact hash mismatch: stop before accelerator or network testing.
- Missing SD fixture: report filename and remain available for diagnostics.
- Link unavailable: retry initialization for a bounded interval, then expose a
  UART error without silently switching to host-loopback data.
- TCP disconnect: close the current request, preserve counters, and accept a
  new connection.
- Accelerator timeout or output mismatch: stop the measurement phase and mark
  the session invalid.
- Telemetry sensor unavailable: retain inference data but mark power/thermal
  fields unavailable; never synthesize values.

## Testing strategy

Host tests cover protocol framing, fragmented reads, invalid sizes, artifact
hashing, session aggregation, accuracy, confusion matrix, and dashboard API.
Firmware host-unit tests cover portable protocol and metric functions. Vitis
build verification records BSP libraries, ELF identity, BIF inputs, Bootgen
output, and SHA-256.

Hardware gates are sequential:

1. UART boot identity;
2. Ethernet link and HELLO identity;
3. exact E06 fixture inference;
4. E06 latency/telemetry session;
5. PlantVillage one-fixture software/board parity;
6. bounded PlantVillage accuracy session;
7. sustained thermal/power session.

Failure at a gate blocks claims for later gates but retains diagnostic data.

## Acceptance criteria

Stage 1 is complete when `BOOT_E06_NET.BIN` is reproducibly generated under
`Cloud_test`, the board establishes a physical TCP connection, reports the
expected hashes, and returns zero mismatches for the E06 fixture.

Stage 2 is complete when `BOOT_PLANT_IOT.BIN` is reproducibly generated,
one-fixture software/board parity passes, the fixed PlantVillage evaluation
session completes without dropped samples, and dashboard/exported summaries
agree with independently recomputed metrics.

Host-only tests and generated BOOT files alone do not satisfy either physical
acceptance criterion.
