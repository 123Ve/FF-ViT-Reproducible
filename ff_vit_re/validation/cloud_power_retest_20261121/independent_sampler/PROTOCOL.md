# E07 independent power candidate — protocol schema 1

## r10 host thermal capture policy

Diagnostic16/17 collect after at least30s warmup with healthy/fresh temperatures
and at least29s of advancing board-status observations. They do not wait up to
600s for the strict thermal stability predicate. Strict18 retains that predicate.
Every profile still rejects invalid/stale/out-of-range temperature evidence.
Warmup samples and actual elapsed time are preserved; no stable flag is invented.
Analysis recomputes warmup_thermal_stable and reports thermal_qualification on
each phase/CSV and the number of qualified repetitions. A valid diagnostic time
integral is not a thermal-steady-state or matched-temperature comparison claim.
The warmup flag itself assesses the warmup only, not stationarity over the full
measurement interval. R9 firmware and its immutable identities are unchanged.

## Current capture policy (r8, replaces negative-only aborts in diagnostic profiles)

Three immutable CPU images are available: strict18 (all rails), diagnostic17
(exclude7), diagnostic16 (exclude7/15, mask229247). All configure and export18
physical rails. Select the matching image and host --diagnostic17/--diagnostic16;
profile mixing is rejected. Shared firmware ABI is4; the128-byte rail wire record
and INA226 configuration/ADC averaging remain unchanged.

observed_mask / adc_observed_mask records genuine timely CVRF observations,
independently of signed power quality. conversion_ready_mask / power_qualified_mask
records rails that have produced a valid power observation; it is not a current
per-sample quality guarantee. No CVRF flags or valid bits are synthesized.

Strict18 keeps the original negative-value rejection. Diagnostic negative-only
rows (flags256/258) remain raw, invalid for included power, and do not stop
acquisition. included_negative_samples and excluded_negative_samples count such
software observations, including held reads; neither counts independent ADC
conversions. Other flags/errors and the original coverage/clock gates remain fatal.

Diagnostic acceptance authorizes capture integrity only. capture_valid and
power_quality_valid are separate: an included negative can finish all phases
while complete power/energy metrics are null. Excluded rails never contribute,
even when positive. All18rails must still pass raw timing/error/coverage checks.
Rail7 and Rail15 have exact decoded subsets alongside authoritative full raw exports.
No new physical measurement or sensor calibration is claimed.

This is `E07_INDEPENDENT_POWER_V1`, phase `E07_INDEPENDENT_CANDIDATE`.
Every delivered manifest and firmware greeting says `physical_status: "NOT_RUN"`:
this describes the qualification of the candidate, not whether a subsequent user
session has begun. No physical startup or power result is claimed by this build.

## Transport, identity, and fixed input

The board at `192.168.10.2` initiates TCP to the host listening at
`192.168.10.1:5001`. Keep one connection, one request in flight, and read each
complete response before submitting another request. Do not pipeline commands.
The next request normally carries the TCP ACK of the preceding response. A
delayed ACK is counted only when received by the board. Host receipt times and
board completion times are separate observations in separate clocks.

FVIT framing is unchanged. The header is exactly 20 bytes: ASCII `FVIT` at 0,
version byte 1 at 4, kind byte at 5, zero bytes at 6–7, then three unsigned
big-endian 32-bit values at offsets 8,12,16: request_id, metadata_len,
payload_len. Metadata is UTF-8 JSON; payload follows it. Maximum metadata is
65536 bytes and maximum payload is 4194304 bytes. Requests use kind 7. Responses
use kind 1 (Full/binary export), 2 (Compact), 4 (control/health/time), 5 (initial
greeting), 6 (status), or 255 (error). Every response echoes the request ID;
greeting uses ID 0. Use distinct nonzero request IDs, including every business
frame, and persist their stream/sequence/phase association on the host.

The service and sampler use shared ABI version 3 and compare their compiled rail count and firmware identity before sampling can qualify. Both images emit the following fields in the greeting, status, control replies and export metadata. The host binds the same fields to SD receipts, plans, sessions, acceptance and derived CSV rows.

| measurement_profile | scope | included_mask | included_count | excluded_rails |
| --- | --- | ---: | ---: | --- |
| strict18 | 18 monitored supply rails; not external whole-board input power | 262143 | 18 | [] |
| diagnostic17 | 17-rail diagnostic | 262015 | 17 | [7] |

The strict18 greeting contains these exact fields.

```json
{"measurement_profile":"strict18","scope":"18 monitored supply rails; not external whole-board input power","included_mask":262143,"included_count":18,"excluded_rails":[],"artifact_hashes":{"bitstream":"64 hex","input":"64 hex","output":"64 hex","weights":"64 hex","xsa":"64 hex"},"board_ip":"192.168.10.2","firmware_sha256":"64 hex","model":"E07","phase":"E07_INDEPENDENT_CANDIDATE","tcp_port":5001,"candidate":"E07_INDEPENDENT_POWER_V1","protocol_schema":1,"physical_status":"NOT_RUN","sampler_cpu":"a53-1","service_cpu":"a53-0"}
```

`firmware_sha256` must equal the selected root identity’s `firmware_sha256` in the
delivered package. It is the SHA-256 of `canonical_payload` encoded by Python
`json.dumps(payload,sort_keys=True,separators=(',',':')).encode()`; it binds both
cores' source, linker scripts, build scripts, BSP libraries, compiler options,
frozen artifacts and bootloader/PMU images. It is not an ELF or BOOT file hash.
Validate those separately against the manifest. Reject old E07_PHYSICAL or
legacy diagnostic firmware, a different measurement profile, a different candidate/schema, or any identity/hash mismatch.

Frozen SHA-256 values:

| artifact_hashes key | File | SHA-256 |
| --- | --- | --- |
| bitstream | design_1_wrapper.bit | 2fedb6d70a0916fc9aebfdf3141008690685c0dbd1b5bab0ae58821564ef1037 |
| xsa | e07_300mhz_wrapper.xsa | b46ed4b26f11340c9eb9fed1a55822f4a30c7f81627287e9c556a0a5416a5df1 |
| input | input.bin | f7fa33c31113271173effc4fb684c432378b85c2f15a6681aa682aacf2ba3a2c |
| output | output.bin | f2da31d910ab48a49c5a803f836478e2b54e0cd9fdd1081cc2eabc1d36afe842 |
| weights | weights.bin | 0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7 |

The board loads exact-size SD fixtures, reorders the fixed input for DMA, and
checks all 1000 reference output codes after every inference. Replay compares
every received input byte to the loaded 602112-byte fixture. Package/SD-file
SHA verification is a host/build responsibility; the firmware does not implement
a cryptographic hash of SD files at runtime. The host must verify the copied SD
files before testing; replay equality alone does not prove the SD file's SHA.

## Commands

Metadata is exactly `{"name":"COMMAND","arguments":{}}` or
`{"name":"COMMAND","arguments":{"count":N}}`. Top-level field order may
vary. Only the two top-level keys and the count argument are accepted; strings
cannot contain escapes. `count` is a decimal integer in 0..1000000, further
restricted below. No signs, fractions, duplicate keys or unknown keys. A control
command never carries a payload. The business commands require the full fixed
input payload. Old telemetry/run_once/compact_result/full_payload/repeat_latency
commands are intentionally unavailable in this independent candidate.

| Command | arguments | Response | Behavior |
| --- | --- | --- | --- |
| health | {} | kind 4 | model, phase, physical_status only |
| time_sync | {} | kind 4 | edge_rx_ticks, edge_tx_ticks, timer_frequency_hz |
| power_status | {} | kind 6 | Cached status below; no sensor I/O |
| power_load | count=0..3 | kind 4 status | Idle only: 0 idle, 1 Full, 2 Compact, 3 continuous DDR inference |
| power_scan | count=17,20,23 | kind 4 status | Idle only; complete-scan target in ms; existing offset must be smaller |
| power_offset | count=0..scan_ms-1 | kind 4 status | Idle only; delay before first scan after arm command is observed |
| power_sampling | count=0 or 1 | kind 4 status | Idle-only short throughput acceptance toggle; arm requires 1 |
| power_arm | count=1..150 | kind 4 status | Start a phase with those formal seconds; 1.25 s scheduling lead, minimum1 s preguard and1 s postguard |
| power_finish | {} | kind 4 status | Requires now>=t1+timer_hz, sampler DONE and no business ACK pending; freezes export |
| power_release | {} | kind 4 status | DONE only; explicitly relinquishes previous logs and permits another phase |
| power_export_config | count=record offset | kind 1 | IDLE or DONE only; 18 configuration records |
| power_export_latest | count=record offset | kind 1 | IDLE or DONE only; coherent cached 18-rail scan; first fatal scan is frozen until reboot |
| power_export_rails | count=record offset | kind 1 | DONE only; rail records |
| power_export_events | count=record offset | kind 1 | DONE only; business-core events |
| power_export_temperatures | count=record offset | kind 1 | DONE only; one-second temperature observations |
| replay_full | {} + 602112 input bytes | kind 1 | Requires mode 1; byte-identical Full payload response; no inference |
| replay_compact | {} + 602112 input bytes | kind 2 | Requires mode 2; fixed-input inference and exact reference check |

Settings cannot change in GUARD/ACTIVE/POST/DONE. After release, wait until
sampler_state==0 and rail_records==temperature_records==0 before the next arm.
Sampling and temperature caching continue outside phases, but raw logs are
retained only for the armed phase and its guards. No previous log is overwritten
before an explicit release. Host must persist and validate all exports first.
Settings responses are status snapshots; sampler acknowledgement of a setting
can lag by one scan. Require ready before arm.

Business response metadata fields are `fixture:"E07_FIXED_INPUT"`,
`mode:"replay_full"|"replay_compact"`, `edge_rx_start_ticks`,
`edge_rx_end_ticks`, `inference_start_ticks`, `inference_end_ticks`,
`result_queue_ticks`, `timer_frequency_hz`, `mismatch_count`, `predicted_class`,
`total_ticks`. Full's inference interval is only its processing interval,
`mismatch_count`, `predicted_class`, and `total_ticks` are zero, and its payload
must equal the complete input. Compact has no payload, `mismatch_count` must be
zero, and its class/timing are returned by the audited inference path.
The actual ACK completion timestamp is exported in event type 5, not guessed
from result_queue_ticks. An error reply is never a successful completion event.

## Status fields and phase sequencing

All integer ticks use the same physical `CNTPCT_EL0` counter on both A53s. The
reported `timer_hz` is read from `CNTFRQ_EL0`. Never subtract host monotonic time
from these values. JSON integers need a 64-bit-capable parser (Python integers
are suitable).

Every successful power control returns the same fields as power_status:

| Fields | Meaning |
| --- | --- |
| schema, physical_status | 1, "NOT_RUN" |
| ready, snapshot_valid | JSON booleans; cached arm prerequisites, coherent snapshot success |
| phase_id, state, faults, sampler_faults | service phase ID (increments each arm), service state and fault bitmasks |
| service_core, sampler_core | must be 0,1 |
| epoch, sampler_epoch | must match; service boot-counter value echoed by sampler |
| timer_hz, sampler_hz | must match, nonzero |
| now_ticks, sampler_heartbeat | current service observation and sampler publication tick |
| clock_checks, heartbeat_advances | successful bracketed clock observations and heartbeat advances |
| configured_mask, configured_tick | must be 262143 (all 18 bits); configuration-complete tick |
| conversion_ready_mask | must contain all included_mask bits before arm. Each set bit requires an actual post-configuration CVRF observation followed by a valid payload |
| observed_mask, sampler_profile_rails, excluded_negative_samples | all 18 timely physical observations (262143), compiled sampler count, cumulative diagnostic Rail7 negative-only rows |
| initializing_samples | cumulative unqualified startup reads before first conversion; not invalid samples or independent ADC conversions |
| mode, sampling_enabled, scan_ms, offset_ms | selected configuration; mode values above |
| t0, t1 | formal half-open board window [t0,t1) |
| sampler_phase, sampler_state | sampler acknowledgement; same phase during logging |
| rail_records, event_records, temperature_records, scan_count | published counts; scan_count can continue outside the phase |
| completed_full, completed_compact, completed_continuous | successful board completions inside [t0,t1), retained separately |
| continuous_begin, continuous_end | observed first loop start and last loop finish during recorded phase+guards; do not use their reciprocal as formal FPS |
| pending_ack | 0 or 1; business response awaiting full TCP ACK |
| temperature_mC, temperature_valid, temperature_tick | cached temperature (signed milli-Celsius), 0/1 validity, read tick |
| i2c_errors, invalid_samples, stale_samples, scan_overruns, overflows, temperature_errors | cumulative sampler counters since boot; save start and end snapshots |

States are 0 IDLE, 1 GUARD, 2 ACTIVE, 3 POST, 4 DONE. An arm received at `ta`
sets `t0=ta+timer_hz+floor(timer_hz/4)` and `t1=t0+count*timer_hz`; sampling begins
when A53-1 observes the command plus offset_ms. The250ms lead margin permits
inter-core delivery and scan scheduling while retaining at least1 full second
before t0. The sampler latches handshake fault8 if its first scheduled scan
would occur later than t0-timer_hz, or if any rail's first actual Power read
finishes later than that cutoff. Host must use returned t0/t1. Formal boundary
timestamps are scheduled common-counter
values, with actual event publication potentially later by one service loop.
If the sampler has not acknowledged the phase at t0, the phase fails closed.
At least three advancing sampler heartbeats and three repeated bracketed clock
checks are required; sample-side clock ticks must lie between the service ping
and its reply observation and round-trip duration must be <=250 ms. Configuration
must be older than one second, heartbeat <=250 ms old, temperature valid and
<=2 seconds old. Wrong cores, frequencies, epochs, configuration, or faults
prevent arm; no fallback sampler exists.

For each condition: set mode and scan parameters while IDLE; run its actual load
through warmup; observe cached one-second temperatures; arm while retaining that
load; preserve it through both guards; stop submitting business frames only
after the postguard and drain any transaction; finish; export all logs and final
status; validate/persist; release. Full/Compact preguard, formal and postguard
use the same input workload. Idle sends no business frames. Continuous mode
executes serial inferences from DDR from power_load=3 onward, including warmup
and both guards; main-loop overhead and network polling are included in actual
wall time. Count successful inference-end events within [t0,t1), divide by
`(t1-t0)/timer_hz`. It stops when phase finishes or a fault is observed, and a
new mode may be selected only after release.

Fault bit values: 1 configuration, 2 sensor/sample, 4 log overflow, 8
handshake/clock, 16 inference/DMA/output verification, 32 input verification,
64 network/disconnected incomplete business response, 128 temperature. Sampler
faults are latched until reboot; release does not mask a sensor failure.
Service phase faults persist until a subsequent valid arm. Any fault invalidates
the phase; retain/export the raw evidence and do not report normal energy/FPS.
The current implementation keeps sampling to the scheduled postguard even after
a phase fault, so finish still observes that deadline. If sampler heartbeat has
stopped permanently, finish cannot succeed: retain host evidence and declare the
phase incomplete. Do not reboot before attempting evidence recovery.

Errors use kind 255 with exactly `code`, `detail`, `phase` (candidate phase
string). Codes: malformed_command, invalid_count, unexpected_arguments,
unexpected_payload, invalid_offset, unknown_command, unknown_export,
snapshot_busy, phase_busy, not_finished, phase_state, not_ready, load_state,
fixture_mismatch, inference_failed, invalid_header, unsupported_frame,
input_unavailable. Framing errors, pipelining while a response is outstanding,
or transport allocation errors may abort TCP after recording a phase fault.
Every fatal framing/transport failure or disconnect in GUARD/ACTIVE/POST latches
network fault64 even before business ACK tracking begins. Its fault event uses
the pending response ID, otherwise the validated current request ID, or0 when
no request is attributable (for example an invalid header). IDLE/DONE disconnects
do not create a measurement fault.
On snapshot_busy retry; on premature phase_state wait until postguard and drain;
on other measurement failures stop normal analysis and preserve evidence.

## Export metadata and little-endian records

Each export carries the five profile fields and JSON fields `schema:1`, `record_type`, `phase_id`, `first`,
`count`, `total`, `record_bytes`, `next`, `done` (boolean). `first` is a record
index, not a byte offset. `count=min(256,total-first)`, `next=first+count`.
`first==total` returns a zero-length payload with done=true; `first>total` fails.
Read and persist each whole chunk, then request next until done. Payload length
must equal count*record_bytes, well below the FVIT 4MiB limit (max 32768 bytes).
Check contiguous sequence numbers and phase IDs and reject missing, duplicate,
or overlapping chunks. Config records have rail IDs instead of sequence IDs.

All binary fields are little-endian with the exact layouts below. There is no
extra per-record header or padding. UINT64/INT64 sizes are 8 bytes; UINT32/INT32
4 bytes; UINT16 2 bytes. The structs are compile-time size checked.

Rail record, 128 bytes, Python struct format `<4I8H5Q5QqQ`:

| Offset | Fields in order | Type |
| --- | --- | --- |
| 0 | seq, phase, scan, flags | 4 × UINT32 |
| 16 | rail, config, calibration, shunt, bus, current, power, mask | 8 × UINT16 |
| 32 | begin[0..4] | 5 × UINT64 |
| 72 | end[0..4] | 5 × UINT64 |
| 112 | power_uW | INT64 |
| 120 | scan_start | UINT64 |

Read-array storage order is shunt(0x01), bus(0x02), current(0x04), power(0x03),
mask/enable(0x06). Actual transaction order in the2026-11-22 repair is Mask first,
then shunt,bus,current,Power. A valid record requires end[4]<=each payload begin.
Each begin/end pair brackets the actual register transaction.
The Power read time interval is begin[3]..end[3]; do not treat rail/multi-register
reads as simultaneous. `scan_start` is actual scan start; successive scan_start
values measure actual scan period. `scan` may start above zero because warmup
scans are unlogged. `seq` always starts at zero for each phase.

`power_export_latest` uses the same128-byte rail format but seq is the rail
index0..17. It is a diagnostic snapshot, not a phase log: before the first fault
it is the latest complete scan; the first scan containing a fatal sensor reading
is frozen until reboot, preserving pre-arm raw failure evidence even if later
reads recover. A separate seqlock protects the complete18-rail publication, and
the service copies a coherent snapshot into its own stable transmit buffer.
An in-progress snapshot can return snapshot_busy. This command never triggers
I2C. Use it when ready=false or arm fails, along with config export and status.

Rail flags: 1 valid, 2 observed CVRF, 4 I2C failure, 8 INA226 math overflow,
16 saturated raw shunt/current/bus/power, 32 no observed
CVRF for >150 ms, 64 configuration error, 128 backward read clock,256 negative
signed shunt or current,512 first conversion not yet observed. Only a record
with valid bit set is usable. Invalid power_uW is INT64_MIN, never zero. `shunt`
and `current` are unsigned storage for signed int16 raw register codes. CVRF is
the mask register's bit 3, cleared on its read; it is an observation of at least
one completed averaged conversion, not a conversion count. Repeated reads with
no CVRF can still have valid bit set for <=150 ms, and must not be called new
independent ADC updates. Configuration installs CAL before writing CONFIG; the
CONFIG write clears CVRF/restarts averaging. Last-observed-CVRF starts unknown,
never at the configuration timestamp. Reads before the first observation have
flag512, no valid bit and INT64_MIN power. In IDLE they are normal initialization
for at most150ms from that rail's config completion; they do not freeze the fault
scan or increment invalid_samples. Exceeding that deadline adds STALE and faults;
the first observed CVRF timestamp is checked against the same deadline even if
no pending sample happened to be taken after the deadline. Every transaction's
begin must follow the previous transaction's end in physical order4,0,1,2,3;
clock reversal is fatal even if the clock later catches up. Host acceptance and
per-rail integration independently enforce this same transaction ordering.
transport/overflow/clock errors still fault immediately. Formal logging cannot
admit unqualified startup reads. Any faulty sample latches a sampler fault.
The shared-memory ABI version is3; wire record sizes/schema remain unchanged.
Use only matching newly built firmware/host identities, never mixed core images.

A small negative signed reading is not labeled ADC saturation. It can reflect
offset/noise or reverse current. Because the primary Power register is unsigned
and this candidate has no validated reverse-current interpretation, flag256
invalidates the rail power. Under diagnostic17 only, rail 7 with exactly flags 256 or 258 after a timely CVRF increments excluded_negative_samples and does not latch a sensor fault. The record retains INT64_MIN and every raw register. Positive rail 7 also contributes no energy. The metric integrates rails 0–6 and 8–17. The readiness gate still checks physical observations and continued freshness on all 18 rails.
Historical board diagnostics have shown rail15 shunt=-1/-2; this policy may
prevent arm on that board. Preserve the frozen diagnostic scan and resolve the
measurement interpretation before formal testing. Compilation does not qualify
this policy against the physical rail.

Config=0x4527 encodes reserved default bit14, averaging code2 (16 averages), bus
code4 (1.1 ms), shunt code4 (1.1 ms), mode7 (continuous bus+shunt). CAL=2048;
nominal combined averaging period is 35.2 ms. Primary power derives from Power:
`power_uW = power_code*62500000/shunt_uohm`. VCCINT is 31250 uW/code; all other
rails are 12500 uW/code. Example: VCCINT power_code=192 is exactly 6000000 uW.
Current LSB is 1.25 mA for 2mΩ, 0.5 mA for 5mΩ; bus LSB 1.25 mV, shunt LSB
2.5 uV. Do not substitute average bus × average current for primary power.

Configuration record, 32 bytes, `<II4HQQ`: rail(UINT32) at0, flags(UINT32) at4,
manufacturer/die/config/calibration(UINT16 each) at8/10/12/14, begin/end(UINT64)
at16/24. Valid requires manufacturer0x5449, (die&0xfff0)==0x2260, config0x4527,
calibration2048, flags1. Failure flags64.

Temperature record, 32 bytes, `<4IQiI`: seq/phase/flags/raw(UINT32) at0/4/8/12,
tick(UINT64) at16, temperature_mC(INT32) at24, reserved(UINT32=0) at28. Valid
flags1; invalid INT32_MIN. Hardware reads have no explicit freshness/error API;
reject raw0/65535 and nonfinite/out-of-range -55..150°C conversions. Sampling is
once per second; the record is a read observation, not proof of ADC conversion
freshness. Strict18 applies the thermal stability gate to these/cached warmup
readings. Diagnostic profiles preserve the separate warmup qualification and
use the fixed minimum warmup policy described in the r10 section above.

Event record, 64 bytes, `<8I4Q`: seq/phase/type/request_id/mode/flags/
mismatch_count/reserved(UINT32) at0..28; begin/end/tick/aux(UINT64) at32/40/48/56.

| type | Meaning and populated fields |
| --- | --- |
| 1 ARM | tick=arm time; begin=t0,end=t1,mode=selected load |
| 2 START | tick=t0 |
| 3 END | tick=t1 |
| 4 FINISH | tick=finish command processing; flags=phase faults |
| 5 ACK | request_id=business ID, mode=1/2, flags=1, begin=request RX start, end=processing/response preparation end, tick=full response ACK observed, aux=TCP final acknowledged sequence |
| 6 INFERENCE | request_id=Compact ID or0 continuous, mode=2/3, flags=1, mismatch_count=0, begin/end=actual full inference function interval, tick=end |
| 7 INPUT_ERROR | request_id, tick=validation failure |
| 8 INFERENCE_ERROR | request_id, mode, mismatch_count, begin/end, tick=end, flags=0 |
| 9 FAULT | request_id when attributable, tick, flags=fault bits |
| 10 CLOCK | begin=service ping, end=service reply observation, tick=sampler counter observation, aux=ping sequence, flags=1 valid or128 invalid |
| 11 LOAD | reserved in schema1; not currently emitted |

Unlisted fields are zero. For Full/Compact N_ok count type5/mode1 or2 with
t0<=tick<t1; separately retain post-window drain events. For continuous count
type6/mode3 inside that window. Cross-check against status completed counters.
Inference intervals and rail read intervals permit temporal overlap checks;
they do not prove ADC conversion windows overlap PL activity.

## Acceptance replay and drop accounting

Live authorization and offline analysis evaluate each phase against the same binary records, coherent statuses, board markers and error events, verified host responses, and matched completion IDs. Excluded-negative counters must be monotonic through warmup, the pre-arm status, arm ACK, subsequent observations, and frozen end. The pre-arm-to-end delta must cover every exported Rail7 warning. Additional unexported warnings may occur. An invalid parent phase/session clears complete rail metrics. Identity and profile contradictions in linked acceptance stop analysis before derived files are created.

Stage `dropped_frames` counts eventual evictions of frames produced in the half-open host monotonic window. `missed_slots` counts skipped scheduled deadlines in that window, including the appropriate part of a missed block that straddles a boundary. Producers persist the schedule origin. Whole-run totals retain warmup, guards and drain. The host window is recorded separately from board [t0,t1), so `board_window_dropped_frames` is null.

## Rail table, memory and manifest contract

| rail | name | domain | address | shunt_uohm |
| --- | --- | --- | --- | --- |
| 0 | VCCPSINTFP | 0 | 0x40 | 5000 |
| 1 | VCCPSINTLP | 0 | 0x41 | 5000 |
| 2 | VCCPSAUX | 0 | 0x42 | 5000 |
| 3 | VCCPSPLL | 0 | 0x43 | 5000 |
| 4 | MGTRAVCC | 0 | 0x44 | 5000 |
| 5 | MGTRAVTT | 0 | 0x45 | 5000 |
| 6 | VCCO_PSDDR_504 | 0 | 0x46 | 5000 |
| 7 | VCCOPS | 0 | 0x47 | 5000 |
| 8 | VCCOPS3 | 0 | 0x4a | 5000 |
| 9 | VCCPSDDRPLL | 0 | 0x4b | 5000 |
| 10 | VCCINT | 1 | 0x40 | 2000 |
| 11 | VCCBRAM | 1 | 0x41 | 5000 |
| 12 | VCCAUX | 1 | 0x42 | 5000 |
| 13 | VCC1V2 | 1 | 0x43 | 5000 |
| 14 | VCC3V3 | 1 | 0x44 | 5000 |
| 15 | VADJ_FMC | 1 | 0x45 | 5000 |
| 16 | MGTAVCC | 1 | 0x46 | 5000 |
| 17 | MGTAVTT | 1 | 0x47 | 5000 |

Rails0..9 are the historical PS monitoring group,10..17 PL monitoring group.
These are monitored rail totals, not whole-board external input power. Domain
selection writes 4|domain to mux0x75 on I2C0 at400kHz; A53-1 exclusively owns it.
The small1..3-byte controller transactions use bounded MMIO polling: each bus
idle wait and each transfer has a2ms software deadline, and NACK, hardware
timeout, arbitration and FIFO errors fail. Each INA226 read is a register-pointer
write followed by a2-byte read; both operations have independent deadlines.
This adapter is covered by fake-register tests and remains physically NOT_RUN.

A53-0's link region is [0x00100000,0x20000000), A53-1's is
[0x20000000,0x21000000), shared DDR is [0x30000000,0x34000000). Shared blocks
are normal noncacheable, inner-shareable, execute-never on both cores. Each ELF
has its own code/data/BSS/heap/stacks/translation tables. DMA/weights/input/output
remain inside the service region with the audited flush/invalidate operations.
Control and business events have A53-0 as sole writer; configurations, samples,
temperature and sampler status have A53-1 as sole writer. Status uses a seqlock
and release/acquire barriers; record bytes are written before published counts.

Rail capacity180000×128=23040000 bytes covers150 formal seconds, both guards and
the scheduling margin. The conservative build check uses153 total seconds at
17ms (162000 records) with spare room. Event capacity262144×64=16777216;
temperature capacity1024×32=32768. Full buffers latch fault4 and never overwrite.
The whole shared structure is statically checked below64MiB. No sample-by-sample
SD writes or UART prints occur during a measurement.

`FIRMWARE_IDENTITY.json` top-level fields: schema, candidate, firmware_sha256,
advertised_sha256, canonical_payload, artifact_hashes, physical_status,
PL_rebuilt, protocol_schema, ELF, BOOT, build_directory, memory_map, capacity,
checks plus the five profile fields above. The diagnostic package uses FIRMWARE_IDENTITY_DIAG17.json, SHA256SUMS_DIAG17.json and SD_CARD_DIAG17. ELF has service/sampler entries, each path/bytes/sha256. BOOT has
path/bytes/sha256. memory_map has service/sampler begin/end/segments/allowed and
shared begin/end/attributes. capacity has rail_records,rail_record_bytes,
event_records,event_record_bytes,temperature_records,temperature_record_bytes,
max_phase_seconds,min_scan_ms,guard_seconds_each,arm_lead_ms,
capacity_checked_seconds. checks has frozen_inputs,
native_tests,ELF_regions,BOOT_cpu_partitions,physical_startup,power_acceptance.
`SHA256SUMS.json` maps candidate SD_CARD relative paths to bytes/sha256.
Each selected build directory contains its own provenance.json with copied-source origin and SHA-256. Each build
attempt retains commands.json, native_tests.log, compiler/link logs, both maps,
disassemblies, memory_map_check.json, independent.bif, bootgen.log and
boot_partition_headers.log. These are offline evidence, not board validation.
