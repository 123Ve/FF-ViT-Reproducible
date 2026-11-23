"""Analyze returned UART logs or DDR_RAW.CSV + DDR_META.TXT. No inferred results."""
import argparse
import csv
import io
import json
import re
from pathlib import Path


def summarize(log):
    if "DDR_TEST_PASS" not in log or "DDR_TEST_FAIL" in log:
        raise ValueError("complete DDR_TEST_PASS log required")
    timer = re.search(r"TIMER_HZ=(\d+)", log)
    idle = re.search(r"IDLE_SHARED_PORT_BYTES=(\d+)", log)
    if not timer or not idle:
        raise ValueError("timer and idle shared-port checks required")
    if int(idle[1]):
        raise ValueError("nonzero idle shared-port traffic prevents application attribution")
    if "DDR_CSV_BEGIN" not in log or "DDR_CSV_END" not in log:
        raise ValueError("complete CSV block required")
    block = log.split("DDR_CSV_BEGIN", 1)[1].split("DDR_CSV_END", 1)[0].strip()
    rows = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(io.StringIO(block))]
    if not rows or any(r["mismatches"] for r in rows):
        raise ValueError("no valid rows or output mismatch")
    if len({r["repeat"] for r in rows}) != len(rows):
        raise ValueError("duplicate repeats")
    expected = re.search(r"REPETITIONS=(\d+)", log)
    if expected and len(rows) != int(expected[1]):
        raise ValueError("incomplete repeat count")
    hz = int(timer[1])
    frames = sum(r["frames"] for r in rows)
    ticks = sum(r["window_ticks"] for r in rows)
    if hz <= 0 or frames <= 0 or ticks <= 0 or any(r["frame_ticks"] <= 0 or r["window_ticks"] < r["frame_ticks"] for r in rows):
        raise ValueError("invalid time or frame count")
    fields = ("weight_read_bytes", "weight_write_bytes", "dma_read_bytes", "dma_write_bytes")
    counts = {k: sum(r[k] for r in rows) for k in fields}
    if any(r[k] < 0 for r in rows for k in r) or any(r[k] == 0 for r in rows for k in ("weight_read_bytes", "dma_read_bytes", "dma_write_bytes")):
        raise ValueError("invalid or inactive byte counters")
    total = sum(counts.values())
    result = {
        "scope": "direct_DDR_controller_AXI_ports_3_4_not_all_PS_DDR_or_DRAM_pins",
        "frames": frames, "repeats": len(rows), "timer_hz": hz,
        "seconds": ticks / hz, "fps": frames * hz / ticks,
        "latency_ms_per_serial_frame": ticks / hz / frames * 1000,
        "port_total_bytes": total, "port_bytes_per_frame": total / frames,
        "port_total_MB_s": total * hz / ticks / 1e6,
        "port_total_MiB_s": total * hz / ticks / 2**20,
        "expected_byte_budget_match": all(
            r["weight_read_bytes"] == r["frames"] * 2994624 and
            r["weight_write_bytes"] == 0 and
            r["dma_read_bytes"] == r["frames"] * 301056 and
            r["dma_write_bytes"] == r["frames"] * 4000 for r in rows),
        "counter_window_note": "outer XTime window includes enable/snapshot/disable overhead; no UART or SD I/O",
    }
    for k, value in counts.items():
        result[k] = value
        result[k.replace("_bytes", "_MB_s")] = value * hz / ticks / 1e6
        result[k.replace("_bytes", "_per_frame")] = value / frames
    fps = [r["frames"] * hz / r["window_ticks"] for r in rows]
    result["fps_min"], result["fps_max"] = min(fps), max(fps)
    if len(fps) > 1:
        import statistics
        result["fps_sample_sd"] = statistics.stdev(fps)
    if "BASELINE_CSV_BEGIN" in log and "BASELINE_CSV_END" in log:
        baseline = log.split("BASELINE_CSV_BEGIN", 1)[1].split("BASELINE_CSV_END", 1)[0].strip()
        br = [{k: int(v) for k, v in r.items()} for r in csv.DictReader(io.StringIO(baseline))]
        if not br or any(r["mismatches"] or r["total_ticks"] <= 0 for r in br):
            raise ValueError("invalid baseline")
        baseline_fps = sum(r["frames"] for r in br) * hz / sum(r["total_ticks"] for r in br)
        result["same_app_unmonitored_fps"] = baseline_fps
        result["monitor_throughput_change_percent"] = (result["fps"] / baseline_fps - 1) * 100
    if not result["expected_byte_budget_match"]:
        result["warning"] = "Direct port counts differ from application budget: investigate port sharing, DDR-port conversion/count semantics or counting boundaries before application-level claims. Do not rescale counters to force a match."
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path, help="UART text or DDR_RAW.CSV")
    parser.add_argument("--meta", type=Path, help="DDR_META.TXT, required for raw CSV")
    args = parser.parse_args()
    text = args.log.read_text(encoding="utf-8-sig")
    if args.meta:
        text = args.meta.read_text(encoding="utf-8-sig") + "\nDDR_CSV_BEGIN\n" + text + "\nDDR_CSV_END\n"
    print(json.dumps(summarize(text), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
