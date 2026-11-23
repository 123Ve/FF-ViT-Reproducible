"""Metrics for matched full/compact uploads, with explicit measurement limits."""
from __future__ import annotations

import math


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * fraction
    lo = math.floor(position)
    hi = math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def summarize_frames(frames, elapsed_s, sent_count, power_samples=()):
    ids = [f['request_id'] for f in frames]
    unique = len(set(ids))
    latencies = [f['receive_monotonic_ns'] - f['send_monotonic_ns'] for f in frames]
    byte_count = sum(f['socket_received_bytes'] for f in frames)
    energy = 0.0
    covered_s = 0.0
    intervals = 0
    for left, right in zip(power_samples, power_samples[1:]):
        if (left['power_uW'] is not None and right['power_uW'] is not None
                and right['monotonic_ns'] >= left['monotonic_ns']):
            energy += ((left['power_uW'] + right['power_uW']) / 2 / 1e6
                       * (right['monotonic_ns'] - left['monotonic_ns']) / 1e9)
            covered_s += (right['monotonic_ns'] - left['monotonic_ns']) / 1e9
            intervals += 1
    return {
        'frames_sent': sent_count, 'frames_received': len(frames),
        'unique_frames_received': unique, 'missing_responses': max(0, sent_count - unique),
        'duplicate_responses': len(ids) - unique,
        'sequence_continuous': all(b == a + 1 for a, b in zip(ids, ids[1:])),
        'socket_received_bytes': byte_count,
        'bytes_received_per_frame': byte_count / len(frames) if frames else None,
        'elapsed_s': elapsed_s,
        'bandwidth_bytes_s': byte_count / elapsed_s if elapsed_s > 0 else None,
        'bandwidth_mbit_s': byte_count * 8 / elapsed_s / 1e6 if elapsed_s > 0 else None,
        'fps': len(frames) / elapsed_s if elapsed_s > 0 else None,
        'command_response_latency_mean_ms': sum(latencies) / len(latencies) / 1e6 if latencies else None,
        'command_response_latency_p95_ms': percentile(latencies, .95) / 1e6 if latencies else None,
        'tcp_retransmissions': None, 'packet_loss': None,
        'monitored_system_energy_J': energy if intervals else None,
        'monitored_system_energy_per_received_frame_J': energy / len(frames) if intervals and frames else None,
        'energy_sample_intervals': intervals,
        'energy_coverage_s': covered_s,
        'energy_coverage_fraction': covered_s / elapsed_s if elapsed_s > 0 else None,
        'nic_transmission_energy_J': None,
    }


def compare_modes(full, compact):
    a, b = full['bytes_received_per_frame'], compact['bytes_received_per_frame']
    full_bw, compact_bw = full['bandwidth_bytes_s'], compact['bandwidth_bytes_s']
    full_energy, compact_energy = full['monitored_system_energy_J'], compact['monitored_system_energy_J']
    return {
        'per_frame_bytes_saved_percent': (1 - b / a) * 100 if a and b is not None else None,
        'observed_bandwidth_saved_percent': (1 - compact_bw / full_bw) * 100 if full_bw and compact_bw is not None else None,
        'system_energy_difference_J': full_energy - compact_energy if full_energy is not None and compact_energy is not None else None,
        'bandwidth_comparison_basis': 'same offered frame rate required for a causal bandwidth-saving claim; otherwise modes may have different FPS',
    }
