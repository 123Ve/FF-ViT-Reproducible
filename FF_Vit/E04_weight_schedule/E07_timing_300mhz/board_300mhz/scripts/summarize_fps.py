"""Summarize serial batch FPS; variance is across batch means, not per-image latency."""
import csv
import json
import statistics
import sys
from pathlib import Path

def summarize(path):
    with Path(path).open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('No FPS measurements')
    repeats = [int(row['repeat']) for row in rows]
    if len(set(repeats)) != len(repeats):
        raise ValueError('Duplicate repetitions')
    rates = set(int(row['timer_hz']) for row in rows)
    if len(rates) != 1 or min(rates) <= 0:
        raise ValueError('Invalid or changing timer frequency')
    timer_hz = rates.pop()
    frame_sum = tick_sum = 0
    latency_ms = []
    fps_values = []
    for row in rows:
        frames, ticks = int(row['frames']), int(row['ticks'])
        if min(frames, ticks) <= 0 or int(row['mismatches']) != 0:
            raise ValueError('Invalid timing or numerical output')
        if int(row['average_ns_per_frame']) != ticks*1000000000//(frames*timer_hz):
            raise ValueError('Stored latency disagrees with raw timing')
        if int(row['fps_milli']) != frames*timer_hz*1000//ticks:
            raise ValueError('Stored FPS units disagree with raw timing')
        frame_sum += frames
        tick_sum += ticks
        latency_ms.append(ticks*1000/(frames*timer_hz))
        fps_values.append(frames*timer_hz/ticks)
    return {
        'evidence_class':'BOARD_MEASUREMENT', 'frame_overlap':False,
        'repetitions':len(rows), 'frames':frame_sum, 'timer_hz':timer_hz,
        'total_seconds':tick_sum/timer_hz,
        'serial_throughput_fps':frame_sum*timer_hz/tick_sum,
        'mean_repeat_average_latency_ms':statistics.mean(latency_ms),
        'stddev_repeat_average_latency_ms':statistics.stdev(latency_ms) if len(rows)>1 else 0,
        'mean_repeat_fps':statistics.mean(fps_values),
        'stddev_repeat_fps':statistics.stdev(fps_values) if len(rows)>1 else 0,
        'qualification':'Repeated serial frames; cache, PS scheduling, input DMA, output DMA/ack included. SD/UART/power sampling excluded from dedicated FPS batches. Latency standard deviation is across batch averages, not individual images.'
    }

if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: summarize_fps.py FPS_SUM.CSV SUMMARY.json')
    Path(sys.argv[2]).write_text(json.dumps(summarize(sys.argv[1]), indent=2)+'\n')
