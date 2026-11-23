"""Timed E06 uploads using the existing BOOT, or labelled host multi-stream simulation.

Run from the source bundle root: python -m Cloud_test.run_stream_measurements --help
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import socket
import threading
import time
import platform
from datetime import datetime, timezone

from Cloud_test.cloud.board_server import _IdentityPolicy, DEFAULT_BOOT_MANIFEST
from Cloud_test.iot_eval.cloud_measurements import summarize_frames, compare_modes
from Cloud_test.iot_eval.messages import Command, Hello, InferenceResult, Telemetry
from Cloud_test.iot_eval.protocol import Message, read_message, write_message


class CountedReader:
    def __init__(self, stream):
        self.stream = stream
        self.bytes_received = 0

    def read(self, size):
        data = self.stream.read(size)
        self.bytes_received += len(data)
        return data


def exchange(stream, reader, name, request_id):
    start = time.monotonic_ns()
    sent_wall = time.time_ns()
    write_message(stream, Command(name, {}).to_message(request_id))
    before = reader.bytes_received
    response = read_message(reader)
    received = time.monotonic_ns()
    wall = time.time_ns()
    if response.request_id != request_id or response.kind == 'error':
        raise ValueError(f'Invalid response to {name}: {response}')
    return response, {
        'request_id': request_id, 'send_monotonic_ns': start,
        'receive_monotonic_ns': received, 'send_wall_ns': sent_wall,
        'receive_wall_ns': wall, 'socket_received_bytes': reader.bytes_received - before,
        'metadata': response.metadata,
    }


def physical(args, record):
    policy = _IdentityPolicy(args.boot_manifest)
    record['source'] = policy.phase
    with socket.socket() as listener:
        listener.bind((args.host, args.port))
        listener.listen(1)
        listener.settimeout(args.timeout)
        print(f'STREAM_LISTENING={args.host}:{args.port}', flush=True)
        print('Now power on the board; stop the other collector before this run.', flush=True)
        connection, peer = listener.accept()
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        with connection, connection.makefile('rwb') as stream:
            connection.settimeout(args.timeout)
            reader = CountedReader(stream)
            hello = Hello.from_message(read_message(reader))
            policy.validate(hello)
            if peer[0] != hello.board_ip:
                raise ValueError('TCP peer does not match board identity')
            record['identity'] = hello.__dict__
            record['host_tcp_nodelay'] = True
            request_id = 0
            modes = {}
            raw_path = Path(record['raw_path'])
            # Buffered evidence is flushed at phase boundaries, outside timed frames.
            with raw_path.open('x', encoding='utf-8') as raw:
                request_id += 1
                response, event = exchange(stream, reader, 'compact_result', request_id)
                raw.write(json.dumps({'mode': 'warmup', 'kind': response.kind, **event}) + '\n')
                warmup = InferenceResult.from_message(Message('inference_result', response.request_id, response.metadata))
                if response.kind != 'edge_result' or warmup.mismatch_count:
                    raise ValueError('Warm-up failed')
                stages = [('full', 'full_payload', 'cloud_frame'),
                          ('compact', 'compact_result', 'edge_result')]
                if args.order == 'compact-first':
                    stages.reverse()
                for mode, command, kind in stages:
                    samples = []
                    frames = []
                    sent = 0
                    total_before = reader.bytes_received
                    start = time.monotonic()
                    next_frame = start
                    next_sensor = start
                    phase_error = None
                    try:
                        while time.monotonic() - start < args.duration:
                            if time.monotonic() >= next_sensor:
                                request_id += 1
                                response, event = exchange(stream, reader, 'telemetry', request_id)
                                telemetry = Telemetry.from_message(response)
                                samples.append({'monotonic_ns': event['receive_monotonic_ns'],
                                                'power_uW': telemetry.power_uW})
                                raw.write(json.dumps({'mode': mode, 'kind': 'telemetry', **event}) + '\n')
                                next_sensor = time.monotonic() + args.telemetry_interval
                            delay = next_frame - time.monotonic()
                            if delay > 0:
                                time.sleep(min(delay, max(0, args.duration - (time.monotonic() - start))))
                            if time.monotonic() - start >= args.duration:
                                break
                            request_id += 1
                            sent += 1
                            response, event = exchange(stream, reader, command, request_id)
                            event['wire_request_id'] = event['request_id']
                            event['request_id'] = sent
                            raw.write(json.dumps({'mode': mode, 'kind': response.kind, **event}) + '\n')
                            if response.kind != kind:
                                raise ValueError(f'Expected {kind}, got {response.kind}')
                            if mode == 'full':
                                if response.metadata != {'fixture': f'{policy.model}_FIXED_INPUT', 'mode': 'full_payload'}:
                                    raise ValueError('Full upload metadata mismatch')
                                if hashlib.sha256(response.payload).hexdigest() != policy.artifact_hashes['input']:
                                    raise ValueError('Full input hash mismatch')
                            else:
                                result = InferenceResult.from_message(Message('inference_result', response.request_id, response.metadata))
                                if result.mismatch_count:
                                    raise ValueError('FPGA output mismatch')
                            # Sequence within this mode excludes interleaved telemetry requests.
                            frames.append(event)
                            next_frame = max(next_frame + 1 / args.fps, time.monotonic())
                        request_id += 1
                        response, event = exchange(stream, reader, 'telemetry', request_id)
                        telemetry = Telemetry.from_message(response)
                        samples.append({'monotonic_ns': event['receive_monotonic_ns'], 'power_uW': telemetry.power_uW})
                        raw.write(json.dumps({'mode': mode, 'kind': 'telemetry', **event}) + '\n')
                    except (OSError, ValueError) as exc:
                        phase_error = str(exc)
                    elapsed = time.monotonic() - start
                    summary = summarize_frames(frames, elapsed, sent, samples)
                    summary['socket_total_received_bytes_including_telemetry'] = reader.bytes_received - total_before
                    summary['sequence_continuous'] = summary['missing_responses'] == 0
                    summary['status'] = 'FAIL' if phase_error else 'COMPLETE'
                    summary['failure'] = phase_error
                    summary['offered_fps'] = args.fps
                    summary['measurement_seconds_requested'] = args.duration
                    summary['completed_requested_duration'] = elapsed >= args.duration and not phase_error
                    for field in ('total_ticks', 'pl_ticks', 'mm2s_ticks', 's2mm_ticks'):
                        values = [f['metadata'][field] for f in frames if field in f['metadata']]
                        summary[field + '_mean'] = sum(values) / len(values) if values else None
                    summary['timer_frequency_hz'] = 99990005
                    ticks = summary['total_ticks_mean']
                    summary['board_latency_mean_ms'] = ticks / 99990005 * 1000 if ticks else None
                    summary['reciprocal_board_latency_fps'] = 99990005 / ticks if ticks else None
                    modes[mode] = summary
                    raw.flush()
                    print(f'{mode.upper()}={json.dumps(summary)}', flush=True)
                    if phase_error:
                        break
            record['modes'] = modes
            if len(modes) == 2:
                record['comparison'] = compare_modes(modes['full'], modes['compact'])
            record['status'] = 'COMPLETE' if len(modes) == 2 and all(m['status'] == 'COMPLETE' for m in modes.values()) else 'FAIL'


def simulate(args, record):
    """Real loopback socket traffic, synthetic frames; no FPGA inference claim."""
    experiments = []
    for streams in (1, 2, 4):
        modes = {}
        for mode, payload_size in [('full', args.full_bytes), ('compact', args.compact_bytes)]:
            results = []
            failures = []
            sender_counts = {}
            lock = threading.Lock()
            def worker(stream_id):
                try:
                    with socket.socket() as listener:
                        listener.bind(('127.0.0.1', 0))
                        listener.listen(1)
                        address = listener.getsockname()
                        def sender():
                            try:
                                with socket.create_connection(address, timeout=10) as client, client.makefile('rwb') as wire:
                                    seq = 0
                                    start = time.monotonic()
                                    while time.monotonic() - start < args.duration:
                                        seq += 1
                                        sender_counts[stream_id] = seq
                                        write_message(wire, Message('cloud_frame' if mode == 'full' else 'edge_result', seq,
                                            {'stream_id': stream_id, 'send_monotonic_ns': time.monotonic_ns()}, bytes(payload_size)))
                                        read_message(wire)  # receiver ACK bounds outstanding data
                                        delay = start + seq / args.fps - time.monotonic()
                                        if delay > 0:
                                            time.sleep(delay)
                            except Exception as exc:
                                with lock:
                                    failures.append(str(exc))
                        thread = threading.Thread(target=sender)
                        thread.start()
                        connection, _ = listener.accept()
                        connection.settimeout(10)
                        frames = []
                        start = time.monotonic()
                        evidence = Path(record['raw_path']).parent / f'simulation_{streams}_{mode}_{stream_id}.jsonl'
                        with connection, connection.makefile('rwb') as wire, evidence.open('x', encoding='utf-8') as raw:
                            reader = CountedReader(wire)
                            while wire.peek(1):
                                before = reader.bytes_received
                                try:
                                    message = read_message(reader)
                                except ValueError:
                                    if reader.bytes_received != before:
                                        raise
                                    break
                                frames.append({'request_id': message.request_id,
                                    'send_monotonic_ns': message.metadata['send_monotonic_ns'],
                                    'receive_monotonic_ns': time.monotonic_ns(),
                                    'socket_received_bytes': reader.bytes_received - before})
                                raw.write(json.dumps(frames[-1]) + '\n')
                                write_message(wire, Message('ack', message.request_id, {}))
                        thread.join(timeout=10)
                        summary = summarize_frames(frames, time.monotonic() - start, sender_counts.get(stream_id, 0))
                        summary['stream_id'] = stream_id
                        with lock:
                            results.append(summary)
                except Exception as exc:
                    with lock:
                        failures.append(str(exc))
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(streams)]
            start = time.monotonic()
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            elapsed = time.monotonic() - start
            modes[mode] = {'streams': sorted(results, key=lambda r: r['stream_id']),
                'total_received_bytes': sum(r['socket_received_bytes'] for r in results),
                'aggregate_bandwidth_mbit_s': sum(r['socket_received_bytes'] for r in results) * 8 / elapsed / 1e6,
                'elapsed_s': elapsed, 'failures': failures}
            print(f'SIMULATION streams={streams} mode={mode} frames={sum(r["frames_received"] for r in results)} failures={len(failures)}', flush=True)
        experiments.append({'camera_streams': streams, 'modes': modes})
    record['experiments'] = experiments
    record['status'] = 'COMPLETE' if not any(m['failures'] for e in experiments for m in e['modes'].values()) else 'FAIL'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['physical', 'simulation'], required=True)
    parser.add_argument('--order', choices=['full-first', 'compact-first'], default='full-first')
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--fps', type=float, default=10)
    parser.add_argument('--host', default='192.168.10.1')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--telemetry-interval', type=float, default=1)
    parser.add_argument('--boot-manifest', type=Path, default=DEFAULT_BOOT_MANIFEST)
    parser.add_argument('--full-bytes', type=int, default=602112)
    parser.add_argument('--compact-bytes', type=int, default=0)
    parser.add_argument('--output-root', type=Path, default=Path('Cloud_test/results/stream_measurements'))
    args = parser.parse_args(argv)
    import math
    if any(not math.isfinite(v) or v <= 0 for v in (args.duration, args.fps, args.timeout, args.telemetry_interval)):
        parser.error('duration, fps, timeout and telemetry interval must be finite and positive')
    if not 0 <= args.full_bytes <= 4 * 1024 * 1024 or not 0 <= args.compact_bytes <= 4 * 1024 * 1024:
        parser.error('payload sizes must be in 0..4194304')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    directory = args.output_root / stamp
    directory.mkdir(parents=True, exist_ok=False)
    record = {'schema': 'fvit-cloud-stream-measurements-v1',
        'source': 'E06_PHYSICAL' if args.mode == 'physical' else 'HOST_LOOPBACK_SYNTHETIC',
        'status': 'RUNNING', 'raw_path': str(directory / 'frames.jsonl'),
        'mode_order': args.order,
        'host_platform': platform.platform(),
        'python_version': platform.python_version(),
        'configuration': {'duration_s_per_mode': args.duration, 'fps_target': args.fps,
                          'simulation_full_payload_bytes': args.full_bytes,
                          'simulation_compact_payload_bytes': args.compact_bytes,
                          'telemetry_interval_s': args.telemetry_interval},
        'limits': ['socket bytes exclude TCP/IP/Ethernet headers and retransmitted packets',
                   'command response latency does not measure camera-to-cloud latency',
                   'existing BOOT does not expose separate network-stage timestamps',
                   'power integrates monitored rails across the stage, not NIC-only energy',
                   'synthetic streams do not represent multiple physical cameras or FPGA concurrency']}
    try:
        (physical if args.mode == 'physical' else simulate)(args, record)
    except KeyboardInterrupt:
        record['status'] = 'ABORTED'
        record['failure'] = 'Interrupted by operator; use raw evidence for partial analysis'
    except Exception as exc:
        record['status'] = 'FAIL'
        record['failure'] = str(exc)
    finally:
        raw_path = directory / 'frames.jsonl'
        if raw_path.exists():
            record['raw_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        record['evidence_sha256'] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.glob('*.jsonl')
        }
        path = directory / 'report.json'
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
        import csv
        rows = []
        if 'modes' in record:
            rows = [{'mode': mode, **values} for mode, values in record['modes'].items()]
        elif 'experiments' in record:
            rows = [{'camera_streams': e['camera_streams'], 'mode': mode, **stream}
                    for e in record['experiments'] for mode, values in e['modes'].items()
                    for stream in values['streams']]
        if rows:
            columns = sorted(set().union(*(row.keys() for row in rows)))
            with (directory / 'metrics.csv').open('w', newline='', encoding='utf-8-sig') as output:
                writer = csv.DictWriter(output, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
        print(f'STREAM_REPORT={path.resolve()}', flush=True)
    return 0 if record['status'] == 'COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
