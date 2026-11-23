# FF-ViT E06 ZCU102 network evaluation

`Cloud_test` is an isolated, reproducible Stage-1 deployment package. It contains
the generated E06 network `BOOT.BIN`, immutable copied inputs, the PC collector,
an offline Flask/Plotly dashboard, tests and operator documentation. No source
artifact outside this directory is modified.

## Evidence boundaries

- `HOST_LOOPBACK`: PC-only FVIT protocol smoke test with a checksum backend. It
  is not ZCU102, FPGA inference, power, temperature or model-accuracy evidence.
- `E06_PHYSICAL`: physical ZCU102 Ethernet evidence using the E06 model. Exact
  reference mismatch, latency and available telemetry may be reported, but
  PlantVillage Top-1 remains `N/A` because E06 is not a PlantVillage model.
- `PLANT_PHYSICAL`: reserved for a later PlantVillage-specific BOOT and a
  separately accepted physical gate. Nothing in this release claims that phase.

Generating a BOOT image and passing host tests do not pass the physical gate.
Task 10 tooling is complete, but the physical gate remains `NOT_RUN` until real
UART and TCP evidence is captured. The checked-in gate file never substitutes
host evidence for a board run.

## Released artifacts

- `boot/BOOT_E06_NET.BIN` — SHA-256
  `6e02ba90a6fbee3140537145c5236443b26aa3c3ef7f8380e146224578ddf37f`
- `boot/BOOT_E06_NET.manifest.json` — Bootgen and firmware identity provenance
- `config/e06_physical.json` — frozen endpoint and artifact identity
- `docs/E06_BOARD_RUNBOOK_CN.md` — Chinese board procedure and safety notes
- `checkpoints/e06_network_release.sha256.json` — stable release inventory

## Host verification

Run from `/home/user/Desktop/ff_vit_re`:

```bash
python -m unittest discover -s Cloud_test/tests -v
python -m compileall -q Cloud_test
python Cloud_test/run_smoke.py \
  --boot Cloud_test/boot/BOOT_E06_NET.BIN \
  --weights Cloud_test/vendor/e06_base/data/weights.bin \
  --image Cloud_test/fixtures/host_smoke/leaf.jpg \
  --output Cloud_test/results/host_loopback_final
```

The report must contain `HOST_LOOPBACK_PASS` and
`host_protocol_only_not_zcu102_ethernet`.

## Physical services

After the operator configures the dedicated Ethernet interface as described in
the runbook:

```bash
python Cloud_test/run_cloud.py
python Cloud_test/run_dashboard.py
```

The collector binds only `192.168.10.1:5001`; the GUI binds only
`127.0.0.1:8080` and reads the same `results/sessions` store. Both commands use
installation-relative defaults and accept explicit overrides shown by `--help`.
The dashboard intentionally runs without Flask debug mode or a reloader.

## Physical gate capture

The safe readiness command only inspects path availability and prints the
read-only commands that a capture will use:

```bash
python Cloud_test/tools/capture_e06_physical.py readiness \
  --interface enp4s0 --uart-device /dev/ttyUSB0
```

After the operator has manually prepared the SD card, board, host address and
firewall according to the runbook, one explicit command starts UART capture
before board boot, binds the collector, and runs all six command types followed
by one warm-up and 10 groups of 100 serial frames:

```bash
python Cloud_test/tools/capture_e06_physical.py run \
  --interface enp4s0 --uart-device /dev/ttyUSB0 \
  --timeout 900 --confirm-physical
```

The tool prints the new session path. Recompute the gate only from that path:

```bash
python Cloud_test/run_physical_gate.py \
  --session-dir Cloud_test/results/sessions/<session-id>
```

Neither command configures an interface, changes firewall rules, writes an SD
card, or controls board power. Without `--session-dir`, the analyzer deliberately
publishes `NOT_RUN/BLOCKED_PHYSICAL_INPUT`.

## Stable release inventory

Regenerate with:

```bash
python Cloud_test/tools/tree_manifest.py --release Cloud_test \
  > Cloud_test/checkpoints/e06_network_release.sha256.json
```

The release policy excludes interpreter caches, the mutable `results/` tree,
and the manifest itself. Experimental evidence is archived separately and is
never silently folded into the software release identity.
