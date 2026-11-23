#!/usr/bin/env python3
"""Summarize matched E07 INA226 idle/load measurements and load-window FPS."""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


E07_EFFECTIVE_MAC_PER_FRAME = 1_246_416_384


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"empty CSV: {path}")
    return rows


def phase_power_by_repeat(rows: list[dict[str, str]]) -> dict[tuple[int, str], float]:
    samples: dict[tuple[int, str, str], list[float]] = defaultdict(list)
    for row in rows:
        key = (int(row["repeat"]), row["phase"], row["rail"])
        samples[key].append(float(row["power_uW"]) / 1_000_000.0)
    totals: dict[tuple[int, str], float] = defaultdict(float)
    for (repeat, phase, _rail), values in samples.items():
        totals[(repeat, phase)] += statistics.mean(values)
    return dict(totals)


def mean_and_ci95(values: list[float]) -> tuple[float, float]:
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, 0.0
    # Student-t critical value for nine degrees of freedom (the fixed 10-repeat protocol).
    critical = 2.262 if len(values) == 10 else 1.96
    return mean, critical * statistics.stdev(values) / math.sqrt(len(values))


def summarize(raw_path: Path, phase_path: Path, timer_hz: int) -> dict:
    if timer_hz <= 0:
        raise ValueError("timer_hz must be positive")
    powers = phase_power_by_repeat(read_rows(raw_path))
    phases = read_rows(phase_path)
    load_rows = [row for row in phases if row["phase"] == "FFVIT_SUSTAINED_LOAD"]
    if not load_rows or any(int(row["mismatches"]) != 0 for row in load_rows):
        raise ValueError("missing or numerically invalid sustained-load phase")

    repeats = sorted(int(row["repeat"]) for row in load_rows)
    idle = [powers[(repeat, "PL_CONFIGURED_IDLE")] for repeat in repeats]
    load = [powers[(repeat, "FFVIT_SUSTAINED_LOAD")] for repeat in repeats]
    dynamic = [load_value - idle_value for idle_value, load_value in zip(idle, load)]
    idle_mean, idle_ci = mean_and_ci95(idle)
    load_mean, load_ci = mean_and_ci95(load)
    dynamic_mean, dynamic_ci = mean_and_ci95(dynamic)

    frames = sum(int(row["frames"]) for row in load_rows)
    ticks = sum(int(row["ticks"]) for row in load_rows)
    fps = frames * timer_hz / ticks
    effective_gops = 2.0 * E07_EFFECTIVE_MAC_PER_FRAME * fps / 1.0e9
    return {
        "evidence_class": "BOARD_MEASUREMENT",
        "power_scope": "ZCU102_INA226_MONITORED_RAILS_NOT_WALL_POWER",
        "repetitions": len(repeats),
        "measured_frames": frames,
        "timer_hz": timer_hz,
        "sustained_fps": fps,
        "idle_monitored_power_W": idle_mean,
        "idle_power_95ci_half_width_W": idle_ci,
        "load_monitored_power_W": load_mean,
        "load_power_95ci_half_width_W": load_ci,
        "dynamic_monitored_power_W": dynamic_mean,
        "dynamic_power_95ci_half_width_W": dynamic_ci,
        "load_energy_J_per_frame": load_mean / fps,
        "dynamic_energy_J_per_frame": dynamic_mean / fps,
        "effective_GOPS": effective_gops,
        "effective_GOPS_per_W": effective_gops / load_mean,
        "effective_dynamic_GOPS_per_W": effective_gops / dynamic_mean,
        "qualification": (
            "Power is the sum of ZCU102 INA226 monitored rails, not wall-plug power. "
            "FPS uses frames and ticks from the same instrumented load windows."
        ),
    }


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "usage: summarize_power_measurement.py PWR_RAW.CSV PWR_PHS.CSV SUMMARY.json TIMER_HZ",
            file=sys.stderr,
        )
        return 2
    try:
        result = summarize(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[4]))
        Path(sys.argv[3]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
