E07 PS-only direct DDR traffic / bandwidth board test (2026-10-09)
================================================================

This is a NEW measurement image, not an already measured bandwidth result.
Frozen E07 HLS, generated RTL, accepted FSBL, PMU firmware, bitstream and model
fixtures are reused. No HLS synthesis, RTL simulation or Vivado run is needed.
PL configured frequency remains 300.215099 MHz.

SD card instructions
--------------------
Back up the SD card's original BOOT.BIN and any previous DDR_RAW.CSV and
DDR_META.TXT before copying files. This app replaces its own result files on
each boot; it does not replace power-result files.

Copy these FOUR files from this deploy folder to the FAT SD partition root:
  BOOT.BIN
  weights.bin
  input.bin
  output.bin       (golden reference, NOT the app's result log)

Use the normal SD boot mode and the SAME UART settings as the accepted E07
image (typically 115200 baud, 8N1). Power-cycle the board. The first boot banner
must say: E07 PS-only direct DDR APM measurement 20261009.
No need to put the .elf, .bit, .bif, JSON or Python script on the card.

Sequence: mount SD and load fixtures; two warmup frames with exact-logit checks;
0.1-second idle-port sanity check; 10 x 100 serial baseline frames with counters
disabled; 10 x 100 measured serial frames with counters enabled. Check the last
frame of each repeat against all 1000 golden logits. Computation is approximately
6 seconds at the prior FPS; allow about 10-30 seconds including boot, SD and UART.
This is NOT the ten-minute power test. On normal completion UART prints
DDR_TEST_PASS and the card contains DDR_RAW.CSV and DDR_META.TXT.

What is measured directly
-------------------------
The Zynq MPSoC HARDENED PS DDR APM at 0xFD0B0000 is used, not an added PL IP.
Accepted E07 design wiring:
  vit_block_top m_axi -> axi_smc_1 -> PS HP0 -> DDR port/APM slot 3 (weights)
  DMA MM2S/S2MM -> axi_smc_2 -> PS HP1 -> DDR port/APM slot 4 (input/output)

Counters 0..7 are respectively:
  slot3 read bytes, slot3 write bytes, slot4 read bytes, slot4 write bytes,
  slot3 read requests, slot3 write requests, slot4 read requests, slot4 write requests.
Metric selectors are 3(read bytes), 2(write bytes), 1(read requests), 0(write requests).
BSP declares counter scale 1; no empirical rescaling is applied.
Selector readback must match, byte counters must be active, and idle shared-port
traffic must be zero. The app does not configure or start DisplayPort or HP2.
Port 3 also serves DisplayPort; port 4 also serves HP2. They cannot be separated
by this monitor. Reconcile the returned counts before attributing all traffic
to inference. A quiet idle test alone cannot prove that no unrelated traffic
appeared later during load.

32-bit modulo deltas are accumulated into 64-bit totals every 10 frames. A
snapshot chunk longer than 0.1 seconds is rejected to guard against multiple
wraps. At 19.2 GB/s peak DRAM payload, a 0.1-second interval is below 2^32 bytes.
No sample-register reads/reset-on-read are used. Snapshots are sequential MMIO
reads, not atomic time captures; no PL DMA/compute overlap ratio is claimed.

window_ticks: conservative outer timer duration including enable/disable and
counter reads; this is the bandwidth/FPS denominator. frame_ticks: sum of frame
loops, excluding between-chunk counter reads. The difference measures most
observer bookkeeping; the unmonitored baseline also checks perturbation.
Input DDR->PL DMA, PL execution, output DMA/ack, cache maintenance and PS
scheduling are included. SD file I/O, UART output, and per-repeat numerical
comparison are outside measured windows. Inputs/weights already reside in DDR.
Frames are SERIAL; input images are not a validation dataset stream.

This is controller AXI-port traffic, NOT DDR-pin utilization, DRAM commands or
refresh/ECC overhead; NOT all PS DDR traffic, and NOT actual beat-active time.
CPU cache accesses, SD DMA, other DDR ports and cold image-file loading are not
covered by these two monitored ports. No beat-level overlap is inferred.

Independent reconciliation budget (NOT a measurement)
-----------------------------------------------------
For each full frame the previously accepted evidence gives:
  input:   301,056 bytes
  weights: 2,994,624 bytes
  output:  4,000 bytes
  total:   3,299,680 bytes
At the previous 348.677480 FPS this predicts about 1150.524 MB/s. Only returned
counter data can establish measured bandwidth. DDR-port request splitting,
byte-counter semantics or shared traffic can cause differences: never force
counter scaling to match this budget.

Analysis
--------
On the host, in this deploy folder, run:
  python3 summarize_ddr.py /path/to/DDR_RAW.CSV --meta /path/to/DDR_META.TXT
Or preserve the full UART output in uart.txt and run:
  python3 summarize_ddr.py /path/to/uart.txt

MB/s = measured bytes * TIMER_HZ / window_ticks / 1,000,000
MiB/s = measured bytes * TIMER_HZ / window_ticks / 1,048,576
Bytes/frame = measured bytes / completed frames
FPS = completed frames * TIMER_HZ / window_ticks

If expected_byte_budget_match is false, retain raw direct port counts but do not
claim reconciled accelerator-only traffic until the discrepancy is explained.
If DDR_TEST_FAIL, inactive counters, selector failure or a nonzero idle test is
reported, return the COMPLETE UART log instead of quoting a bandwidth number.

Primary documentation
---------------------
AMD UG1085, Chapter 15, PS Interconnect / AXI Performance Monitor:
https://docs.amd.com/api/khub/documents/xzMsp_c5sG9J6A3u7NkJYQ/content
AMD UG1087, MSR_1 (APMDDR), slot/metric selectors:
https://docs.amd.com/r/en-US/ug1087-zynq-ultrascale-registers/MSR_1-APMDDR-Register
AMD UG1087, SICR (APMDDR), reset-on-sample-read behavior:
https://docs.amd.com/r/en-US/ug1087-zynq-ultrascale-registers/SICR-APMDDR-Register
AMD UG1221, Performance Monitor Library, DDR slot mapping:
https://docs.amd.com/api/khub/documents/NUscSlzRkhr9oAk4NBd0Tg/content
