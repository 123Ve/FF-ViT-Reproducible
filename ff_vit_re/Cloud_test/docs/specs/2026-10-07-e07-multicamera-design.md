# E07 concurrent virtual camera load design

The user approved independent 30 FPS producers, per-camera queues of capacity 3,
drop-oldest overflow, round-robin service, and default 20-second 1/2/4-camera
conditions. This host-only extension preserves the existing firmware, PL, and
legacy stop-and-wait suite. Each camera replays the same verified SD fixture;
independent timing is simulated, not diverse image content.

## Components and accounting

One thread per camera uses absolute monotonic deadlines, independent of the
dispatcher. A shared condition protects separate bounded FIFO deques. Overflow
evicts the oldest waiting frame, never an in-flight frame. OS-missed capture slots
are counted separately from generated frames and queue-overflow drops.

The dispatcher visits nonempty queues in strict round-robin order, at most one
request outstanding. Production stops at the measurement deadline. Queued work
may drain for up to 5 seconds, recorded separately. Active-window throughput
counts only verified responses received before the deadline; draining cannot
inflate that throughput. A timeout or invalid response fails the run and closes
the connection instead of risking protocol desynchronization.

All frame clocks are host monotonic clocks. Queue latency is dispatch minus
actual capture; service latency is complete response reception minus send start;
E2E latency is complete response reception minus capture. Latencies and FPS for
the active window exclude drain completions; drain counts remain visible.
Overflow drop rate is overflow drops / produced frames. End-window backlog,
deadline misses, failed requests, and terminal pending frames are separate fields.
Completed, dropped, failed, and terminal pending outcomes conserve every produced
frame. Responses in flight at the deadline are explicitly counted as backlog.

CSV exports include every produced frame and its outcome, per-camera metrics, and
condition totals. JSON contains configuration, runtime and firmware identities,
timing definitions, all summaries, status, and output hashes. A JSONL evidence
writer receives immutable event snapshots and batches writes outside the
dispatcher; overflow or disk failure must fail capture, never silently lose logs.

## Optimization and limitations

The fixed 602112-byte request packet is prepared once; only its request ID is
updated for each send. Producers enqueue tiny frame descriptors, not tensor
copies. Percentiles and CSV generation run after conditions, not for every
response. No periodic clock-sync is needed for host-clock metrics. Validation is
not disabled. The physical path remains one-request-at-a-time Compact inference.

CLI simulation uses a labeled timer-only service with zero network byte counts;
transport tests separately use a real local FVIT socket peer. Neither is board evidence.
The Windows runner launches the new Python module without rebuilding the EXE or
changing the SD card. Legacy GUI and paper exporter remain unchanged; the new
runner exposes progress on the console and exports separate results.
