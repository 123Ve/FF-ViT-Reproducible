"""Physical E07 fixed-tensor replay: sustained uploads and multiplexed source streams.

The PC performs both camera-source replay and cloud-receiver roles. This is not
a real camera experiment, an Internet deployment, or a classification benchmark.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import socket
import threading
import time
import platform
import sys

from Cloud_test.cloud.board_server import _IdentityPolicy
from Cloud_test.cloud.session_store import SessionStore
from Cloud_test.iot_eval.cloud_measurements import summarize_frames, percentile
from Cloud_test.iot_eval.messages import Hello, Telemetry
from Cloud_test.iot_eval.protocol import HEADER, Message, read_message, write_message

ROOT = Path(__file__).resolve().parent


def measurement_conditions(args):
    """All conditions share one connection; order alternates between trials."""
    rates = getattr(args, 'fps_list', None) or [args.fps]
    loads = [] if getattr(args, 'saturation_only', False) else [('fixed', r) for r in rates]
    if getattr(args, 'saturation', False) or getattr(args, 'saturation_only', False):
        loads.append(('saturation', None))
    base = ['full', 'compact'] if args.order == 'full-first' else ['compact', 'full']
    return [dict(camera_streams=s, trial=t + 1, load_mode=load,
                 offered_fps_per_stream=rate, mode_order=base if t % 2 == 0 else base[::-1])
            for t in range(getattr(args, 'repeats', 1)) for s in args.streams
            for load, rate in loads]


def performance_summary(frames, elapsed, sent, sensors, rate, load):
    summary = summarize_frames(frames, elapsed, sent, sensors)
    summary.update(load_mode=load, offered_fps_per_stream=rate,
        throughput_scope='single TCP stop-and-wait; telemetry, validation and evidence recording included',
        source_payload_bytes=sum(f.get('source_sent_payload_bytes', 0) for f in frames),
        socket_sent_bytes=sum(f.get('socket_sent_bytes', 0) for f in frames))
    summary['source_payload_mbit_s'] = summary['source_payload_bytes'] * 8 / elapsed / 1e6 if elapsed > 0 else None
    summary['request_application_mbit_s'] = summary['socket_sent_bytes'] * 8 / elapsed / 1e6 if elapsed > 0 else None
    summary['offered_rate_attainment'] = summary['fps'] / rate if rate and summary['fps'] is not None else None
    summary['offered_rate_met_within_5_percent'] = (summary['offered_rate_attainment'] >= .95
        if summary['offered_rate_attainment'] is not None else None)
    for key in ('e2e_ms', 'edge_receive_ms', 'uplink_estimated_ms', 'inference_ms',
                'edge_processing_ms', 'result_upload_estimated_ms', 'network_and_receive_ms', 'sync_half_rtt_ms'):
        values = [f['latency'][key] for f in frames if key in f.get('latency', {})]
        summary[key + '_mean'] = sum(values) / len(values) if values else None
        for suffix, quantile in [('p50', .5), ('p95', .95), ('p99', .99)]:
            summary[key + '_' + suffix] = percentile(values, quantile)
    summary['negative_upload_estimate_count'] = sum(
        f.get('latency', {}).get('result_upload_estimated_ms', 0) < 0 for f in frames)
    # Never promote half-RTT estimates to calibrated one-way measurements: drift is unbounded.
    summary['one_way_time_reliable'] = False
    summary['one_way_time_note'] = 'Diagnostic estimate only; clock drift unbounded; negative samples preserved.'
    energy, coverage = summary['monitored_system_energy_J'], summary['energy_coverage_s']
    summary['monitored_mean_power_W'] = energy / coverage if energy is not None and coverage > 0 else None
    ticks = [f['metadata'].get('total_ticks') for f in frames]
    summary['board_total_ticks_mean'] = sum(ticks) / len(ticks) if ticks and all(type(t) is int for t in ticks) else None
    return summary


def update_live(directory, report, summary, condition, mode, telemetry=None):
    live = dict(summary, mode=mode, camera_streams=condition['camera_streams'],
                trial=condition['trial'], updated_at=datetime.now(timezone.utc).isoformat())
    live['telemetry'] = telemetry or {}
    report['live'] = live
    history = report.setdefault('live_history', [])
    history.append({key: live.get(key) for key in ('updated_at', 'mode', 'trial', 'camera_streams',
        'load_mode', 'frames_received', 'fps', 'e2e_ms_mean', 'bandwidth_mbit_s',
        'monitored_system_energy_J', 'telemetry')})
    del history[:-180]
    publish(directory, report)


class SocketStream:
    """Count each recv immediately, including an incomplete timed-out frame.

    Writes are coalesced until protocol flush, avoiding tiny header sends.
    No BufferedReader sits between the socket and the evidence counter.
    """
    def __init__(self, connection):
        self.connection = connection
        self.bytes_received = 0
        self.pending = bytearray()
        self.prefix = bytearray()
        self.timeout = connection.gettimeout()
        self.begin_message()

    def begin_message(self):
        self.prefix.clear()
        self.deadline = time.monotonic() + self.timeout if self.timeout is not None else None

    def apply_deadline(self):
        if self.deadline is not None:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('transaction deadline exceeded')
            self.connection.settimeout(remaining)

    def read(self, size):
        self.apply_deadline()
        data = self.connection.recv(min(size, 65536)) if size else b''
        self.bytes_received += len(data)
        if len(self.prefix) < HEADER.size + 65536:
            self.prefix.extend(data[:HEADER.size + 65536 - len(self.prefix)])
        return data

    def write(self, data):
        self.pending.extend(data)
        return len(data)

    def flush(self):
        if self.pending:
            self.apply_deadline()
            self.connection.sendall(self.pending)
            self.pending.clear()

    def progress(self, received):
        result = {'response_received_bytes': received}
        if len(self.prefix) >= HEADER.size:
            magic, version, kind, reserved, request_id, metadata, payload = HEADER.unpack(self.prefix[:HEADER.size])
            if magic == b'FVIT' and version == 1 and reserved == 0:
                result.update(response_request_id=request_id, response_kind_code=kind,
                              expected_response_bytes=HEADER.size + metadata + payload,
                              response_payload_received_bytes=max(0, received - HEADER.size - metadata))
        return result


def compare_replay_modes(full, compact):
    def positive(value):
        return type(value) in (int, float) and math.isfinite(value) and value > 0

    def percentage(key):
        a, b = full.get(key), compact.get(key)
        if not positive(a) or not positive(b):
            return None
        value = (1 - b / a) * 100
        return value if math.isfinite(value) else None

    def matched(key):
        a, b = full.get(key), compact.get(key)
        return positive(a) and positive(b) and abs(a - b) <= .05 * max(a, b)

    required = ('bytes_received_per_frame', 'bandwidth_bytes_s', 'monitored_system_energy_J')
    complete = all(all(key in m for key in required)
        and m.get('status') == 'COMPLETE'
        and m.get('completed_requested_duration') is True
        and type(m.get('frames_received')) is int and m['frames_received'] > 0
        and type(m.get('frames_sent')) is int
        and m.get('frames_received') == m.get('frames_sent')
        and m.get('missing_responses') == 0 and m.get('duplicate_responses') == 0
        and m.get('sequence_continuous') is True
        and positive(m.get('bytes_received_per_frame')) and positive(m.get('bandwidth_bytes_s'))
        and positive(m.get('elapsed_s')) and positive(m.get('fps'))
        and math.isclose(m['fps'], m['frames_received'] / m['elapsed_s'], rel_tol=1e-9)
        for m in (full, compact))
    valid = (complete and all(m.get('load_mode', 'fixed') == 'fixed' for m in (full, compact))
             and matched('elapsed_s') and matched('fps')
             and positive(full.get('offered_fps_per_stream'))
             and positive(compact.get('offered_fps_per_stream'))
             and full.get('offered_fps_per_stream') == compact.get('offered_fps_per_stream'))
    comparison = {'per_frame_bytes_saved_percent': percentage('bytes_received_per_frame'),
        'observed_bandwidth_saved_percent': percentage('bandwidth_bytes_s'),
        'bandwidth_comparison_basis': 'Same offered FPS and verified actual rate/duration required; raw difference is descriptive.'}
    comparison['matched_run_valid'] = valid
    comparison['matching_policy'] = 'Complete verified runs; equal offered FPS; actual FPS and duration within 5%.'
    comparison['observed_bandwidth_difference_percent'] = comparison['observed_bandwidth_saved_percent']
    comparison['per_frame_bytes_basis'] = 'successful verified responses; preliminary when a mode failed'
    if not valid:
        comparison.update(observed_bandwidth_saved_percent=None,
                          invalid_reason='Incomplete, unverified or unmatched rate/duration; observed difference is descriptive only.')
    # Stage totals cover different sampling windows, even if both runs finish.
    # Do not subtract Joules and call this an optimization saving.
    comparison['system_energy_difference_J'] = None
    comparison['energy_comparison_basis'] = ('Coverage-normalized mean monitored rail power only; '
        '>=90% coverage in each matched run. Sequential stages are not a causal energy-saving experiment.')
    power = []
    for mode in (full, compact):
        energy, coverage, elapsed = (mode.get(key) for key in
            ('monitored_system_energy_J', 'energy_coverage_s', 'elapsed_s'))
        if (type(energy) not in (int, float) or not math.isfinite(energy) or energy < 0
                or not positive(coverage) or not positive(elapsed)
                or not .9 <= coverage / elapsed <= 1.01):
            break
        power.append(energy / coverage)
    comparison['monitored_mean_power_difference_W'] = power[0] - power[1] if valid and len(power) == 2 else None
    return comparison


def board_timer_frequency(metadata):
    hz = metadata.get('timer_frequency_hz')
    if type(hz) is not int or hz <= 0:
        raise ValueError('invalid board timer frequency')
    return hz


def board_stage_times(metadata):
    hz = board_timer_frequency(metadata)
    names = ('edge_rx_start_ticks', 'edge_rx_end_ticks', 'inference_start_ticks',
             'inference_end_ticks', 'result_queue_ticks')
    ticks = [metadata.get(key) for key in names]
    if any(type(t) is not int or t < 0 for t in ticks) or ticks != sorted(ticks):
        raise ValueError('non-monotonic board stage timestamps')
    return [t * 1e9 / hz for t in ticks]


def validate_response(name, response, payload, event):
    m = response.metadata
    if name in ('replay_full', 'replay_compact'):
        expected = 'cloud_frame' if name == 'replay_full' else 'edge_result'
        if response.kind != expected or m.get('mode') != name:
            raise ValueError('replay response mode/kind mismatch')
        if m.get('fixture') != 'E07_FIXED_INPUT' or type(m.get('mismatch_count')) is not int or m['mismatch_count'] != 0:
            raise ValueError('replay inference/fixture mismatch')
        if name == 'replay_full' and response.payload != payload:
            raise ValueError('full upload payload corruption')
        if name == 'replay_compact' and response.payload:
            raise ValueError('unexpected compact payload')
        board_stage_times(m)
        event['verified_response_payload_bytes'] = len(response.payload)
        if name == 'replay_full':
            event['verified_response_payload_sha256'] = hashlib.sha256(response.payload).hexdigest()
    elif name == 'compact_result':
        if response.kind != 'edge_result' or type(m.get('mismatch_count')) is not int or m['mismatch_count'] != 0:
            raise ValueError('FPGA warmup failed')
        if response.payload:
            raise ValueError('unexpected warmup payload')
    elif name == 'telemetry':
        Telemetry.from_message(response)
    elif name == 'time_sync':
        if response.kind != 'ack' or response.payload:
            raise ValueError('unexpected time synchronization response')
        hz = board_timer_frequency(m)
        rx, tx = m.get('edge_rx_ticks'), m.get('edge_tx_ticks')
        if type(rx) is not int or type(tx) is not int or rx < 0 or tx < rx:
            raise ValueError('invalid synchronization timestamps')
        receive, send = rx * 1e9 / hz, tx * 1e9 / hz
        rtt = event['receive_monotonic_ns'] - event['send_monotonic_ns']
        if rtt < send - receive:
            raise ValueError('invalid synchronization timestamps')
        event['estimate'] = {'board_minus_host_ns': ((receive - event['send_monotonic_ns']) +
            (send - event['receive_monotonic_ns'])) / 2,
            'half_rtt_bound_ns': (rtt - (send - receive)) / 2,
            'timer_frequency_hz': hz,
            'host_monotonic_ns': event['receive_monotonic_ns']}


def latency_breakdown(event, sync):
    rx, rx_end, infer, infer_end, queued = board_stage_times(event['metadata'])
    sent, received = event['send_monotonic_ns'], event['receive_monotonic_ns']
    offset = sync['board_minus_host_ns']
    return {
        'e2e_ms': (received - sent) / 1e6,
        'uplink_estimated_ms': (rx_end - offset - sent) / 1e6,
        'edge_receive_ms': (rx_end - rx) / 1e6,
        'inference_ms': (infer_end - infer) / 1e6,
        'edge_processing_ms': ((infer - rx_end) + (queued - infer_end)) / 1e6,
        'result_upload_estimated_ms': (received - (queued - offset)) / 1e6,
        'network_and_receive_ms': ((received - sent) - (queued - rx)) / 1e6,
        'one_way_estimated': True,
        'sync_half_rtt_ms': sync['half_rtt_bound_ns'] / 1e6,
        'clock_drift_bound_available': False,
    }


def transaction(stream, reader, name, request_id, payload=b'', raw=None, arguments=None):
    event = {'request_id': request_id, 'send_wall_ns': time.time_ns(),
             'send_monotonic_ns': time.monotonic_ns()}
    before = reader.bytes_received
    reader.begin_message()
    try:
        event['socket_sent_bytes'] = write_message(stream, Message('command', request_id,
            {'name': name, 'arguments': arguments or {}}, payload))
        event['source_send_complete_monotonic_ns'] = time.monotonic_ns()
        response = read_message(reader)
        event.update(receive_monotonic_ns=time.monotonic_ns(), receive_wall_ns=time.time_ns(),
                     socket_received_bytes=reader.bytes_received - before, metadata=response.metadata)
        if response.request_id != request_id or response.kind == 'error':
            raise ValueError(f'{name} failed: {response.kind} {response.metadata}')
        validate_response(name, response, payload, event)
        if name == 'repeat_latency':
            m = response.metadata
            if (response.kind != 'ack' or m.get('status') != 'ok'
                    or m.get('count') != (arguments or {}).get('count')
                    or any(type(m.get(k)) is not int or m[k] <= 0
                           for k in ('total_ticks', 'pl_ticks', 'mm2s_ticks', 's2mm_ticks'))):
                raise ValueError('invalid repeated board timing response')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        diagnostic = {'kind': 'transaction_failure', 'command': name, **event,
                      'failure': str(exc), 'failure_type': type(exc).__name__,
                      'failed_monotonic_ns': time.monotonic_ns(),
                      **reader.progress(reader.bytes_received - before)}
        if raw is not None:
            raw.write(json.dumps(diagnostic) + '\n')
            raw.flush()
        print('E07_TRANSACTION_FAILURE=' + json.dumps(diagnostic), flush=True)
        raise
    return response, event


def synchronize(stream, reader, next_id, raw):
    candidates = []
    for _ in range(7):
        response, event = transaction(stream, reader, 'time_sync', next_id(), raw=raw)
        candidate = event['estimate']
        candidates.append(candidate)
        raw.write(json.dumps({'kind': 'time_sync', **event}) + '\n')
    return min(candidates, key=lambda c: c['half_rtt_bound_ns'])


def publish(directory, report):
    temporary = directory / 'report.tmp'
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(directory / 'report.json')


def physical(args, report, directory, store):
    policy = _IdentityPolicy(args.boot_manifest)
    if policy.model != 'E07':
        raise ValueError('E07 suite requires an E07 BOOT manifest')
    payload = args.input.read_bytes()
    if len(payload) != 602112 or hashlib.sha256(payload).hexdigest() != policy.artifact_hashes['input']:
        raise ValueError('replay input must match the E07 SD fixture hash and size')
    with socket.socket() as listener:
        listener.bind((args.host, args.port))
        listener.listen(1)
        listener.settimeout(args.timeout)
        print(f'E07_COLLECTOR_LISTENING={args.host}:{args.port}', flush=True)
        print('Power on the E07 board now. Do not run another collector.', flush=True)
        connection, peer = listener.accept()
        with connection:
            connection.settimeout(args.timeout)
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            reader = stream = SocketStream(connection)
            hello = Hello.from_message(read_message(reader))
            policy.validate(hello)
            if peer[0] != hello.board_ip:
                raise ValueError('TCP peer does not match board identity')
            session = store.begin(hello)
            store.append(session, {'kind': 'connection', 'state': 'connected', 'received_at_ns': time.time_ns()})
            report['identity'] = hello.__dict__
            report['session_id'] = session
            counter = 0
            def next_id():
                nonlocal counter
                counter += 1
                return counter
            try:
                with (directory / 'frames.jsonl').open('x', encoding='utf-8') as raw:
                    response, event = transaction(stream, reader, 'compact_result', next_id(), raw=raw)
                    if response.kind != 'edge_result' or response.metadata['mismatch_count'] != 0:
                        raise ValueError('FPGA warmup failed')
                    raw.write(json.dumps({'kind': 'warmup', **event}) + '\n')
                    if getattr(args, 'board_batches', 0):
                        sync = synchronize(stream, reader, next_id, raw)
                        batches = []
                        begin = time.monotonic()
                        report['active_stage'] = {'mode': 'board_repeat', 'batches': args.board_batches}
                        publish(directory, report)
                        for batch in range(args.board_batches):
                            response, event = transaction(stream, reader, 'repeat_latency', next_id(), raw=raw,
                                arguments={'count': args.board_batch_size})
                            raw.write(json.dumps({'kind': 'board_repeat', 'batch': batch + 1, **event}) + '\n')
                            batches.append(response.metadata)
                        count = sum(m['count'] for m in batches)
                        # repeat_latency has no frequency field; obtain it from an independently validated sync reply.
                        # synchronize stores the explicit board timer frequency below.
                        hz = sync['timer_frequency_hz']
                        total = sum(m['total_ticks'] for m in batches)
                        host_elapsed = time.monotonic() - begin
                        report['board_benchmark'] = dict(status='COMPLETE', frames=count,
                            batch_size=args.board_batch_size, batches=args.board_batches,
                            timer_frequency_hz=hz, total_ticks=total,
                            mean_board_latency_ms=total / count / hz * 1000,
                            reciprocal_board_latency_fps=count * hz / total,
                            host_elapsed_s=host_elapsed, host_batch_throughput_fps=count / host_elapsed,
                            scope='SD-resident fixed input; sums of per-inference PS timer windows, not pipelined throughput',
                            monitored_mean_power_W=None,
                            mean_stage_ticks={k: sum(m[k] for m in batches) / count
                                for k in ('mm2s_ticks', 'pl_ticks', 's2mm_ticks')})
                        raw.flush()
                        publish(directory, report)
                    for condition in measurement_conditions(args):
                        streams = condition['camera_streams']
                        rate, load = condition['offered_fps_per_stream'], condition['load_mode']
                        experiment = {**condition, 'source_mode': 'HOST_MULTIPLEXED_FIXED_TENSOR_REPLAY', 'modes': {}}
                        report['experiments'].append(experiment)
                        order = condition['mode_order']
                        for mode in order:
                            sync = synchronize(stream, reader, next_id, raw)
                            frames, sensors = [], []
                            by_stream = [[] for _ in range(streams)]
                            sent_by_stream = [0] * streams
                            start_ns = time.monotonic_ns()
                            start = start_ns / 1e9
                            start_wall = time.time_ns()
                            raw.write(json.dumps({'kind': 'stage_start', **condition, 'mode': mode,
                                'monotonic_ns': start_ns, 'requested_duration_s': args.duration}) + '\n')
                            next_frame = start
                            next_sensor = start
                            next_sync = start + 10
                            next_publish = start
                            latest_telemetry = {}
                            before = reader.bytes_received
                            report['active_stage'] = {**condition, 'mode': mode, 'duration_s': args.duration}
                            update_live(directory, report, performance_summary([], 0, 0, [], rate, load), condition, mode)
                            failed = None
                            print(f'E07_STAGE trial={condition["trial"]} streams={streams} load={load} fps={rate} mode={mode} duration={args.duration}s', flush=True)
                            try:
                                while time.monotonic() - start < args.duration:
                                    now = time.monotonic()
                                    if now >= next_sensor:
                                        response, event = transaction(stream, reader, 'telemetry', next_id(), raw=raw)
                                        telemetry = Telemetry.from_message(response)
                                        latest_telemetry = response.metadata
                                        sensors.append({'monotonic_ns': event['receive_monotonic_ns'], 'power_uW': telemetry.power_uW})
                                        raw.write(json.dumps({'kind': 'telemetry', **condition, 'mode': mode, **event}) + '\n')
                                        next_sensor = time.monotonic() + 1
                                    if now >= next_sync:
                                        sync = synchronize(stream, reader, next_id, raw)
                                        next_sync = time.monotonic() + 10
                                    delay = next_frame - time.monotonic()
                                    if load == 'fixed' and delay > 0:
                                        time.sleep(min(delay, max(0, args.duration - (time.monotonic() - start))))
                                    if time.monotonic() - start >= args.duration:
                                        break
                                    stream_id = len(frames) % streams
                                    sent_by_stream[stream_id] += 1
                                    raw.write(json.dumps({'kind': 'source_attempt', 'mode': mode,
                                        'stream_id': stream_id + 1, 'stream_sequence': sent_by_stream[stream_id],
                                        'trial': condition['trial'], 'load_mode': load, 'offered_fps_per_stream': rate,
                                        'camera_streams': streams, 'request_id': counter + 1,
                                        'source_payload_bytes': len(payload), 'wall_ns': time.time_ns()}) + '\n')
                                    response, event = transaction(stream, reader, 'replay_' + mode, next_id(), payload, raw=raw)
                                    event['wire_request_id'] = event['request_id']
                                    event['request_id'] = len(frames) + 1
                                    event['stream_id'] = stream_id + 1
                                    event['stream_sequence'] = sent_by_stream[stream_id]
                                    event['source_sent_payload_bytes'] = len(payload)
                                    event['latency'] = latency_breakdown(event, sync)
                                    event['sync'] = sync
                                    raw.write(json.dumps({'kind': response.kind, 'mode': mode, 'camera_streams': streams,
                                        'trial': condition['trial'], 'load_mode': load, 'offered_fps_per_stream': rate, **event}) + '\n')
                                    frames.append(event)
                                    by_stream[stream_id].append({**event, 'request_id': event['stream_sequence']})
                                    if load == 'fixed':
                                        next_frame = max(next_frame + 1 / (rate * streams), time.monotonic())
                                    if time.monotonic() >= next_publish:
                                        elapsed_live = time.monotonic() - start
                                        live_summary = performance_summary(frames, elapsed_live,
                                            sum(sent_by_stream), sensors, rate * streams if rate else None, load)
                                        live_summary['offered_fps_per_stream'] = rate
                                        update_live(directory, report, live_summary, condition, mode, latest_telemetry)
                                        raw.flush()
                                        next_publish = time.monotonic() + 1
                            except (OSError, ValueError, KeyError) as exc:
                                failed = str(exc)
                            end_ns = time.monotonic_ns()
                            elapsed = (end_ns - start_ns) / 1e9
                            raw.write(json.dumps({'kind': 'stage_end', **condition, 'mode': mode,
                                'monotonic_ns': end_ns, 'frames_sent': sum(sent_by_stream)}) + '\n')
                            summary = performance_summary(frames, elapsed, sum(sent_by_stream), sensors,
                                rate * streams if rate else None, load)
                            summary.update(status='FAIL' if failed else 'COMPLETE', failure=failed,
                                host_start_wall_ns=start_wall, host_end_wall_ns=time.time_ns(),
                                completed_requested_duration=not failed and elapsed >= args.duration,
                                offered_fps_per_stream=rate,
                                socket_total_received_bytes_including_control=reader.bytes_received - before,
                                streams=[{'stream_id': i + 1, **summarize_frames(group, elapsed, sent_by_stream[i])}
                                         for i, group in enumerate(by_stream)])
                            # A failed validation is not necessarily a TCP failure; raw errors remain authoritative.
                            summary['tcp_connection_failures'] = None if failed else 0
                            experiment['modes'][mode] = summary
                            if set(experiment['modes']) == {'full', 'compact'}:
                                experiment['comparison'] = compare_replay_modes(experiment['modes']['full'], experiment['modes']['compact'])
                            raw.flush()
                            update_live(directory, report, summary, condition, mode, latest_telemetry)
                            if failed:
                                raise ValueError(failed)
            finally:
                store.append(session, {'kind': 'connection', 'state': 'disconnected', 'received_at_ns': time.time_ns()})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='192.168.10.1')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--fps', type=float, default=10)
    parser.add_argument('--fps-list', type=float, nargs='+', help='fixed offered FPS per source stream')
    parser.add_argument('--saturation', action='store_true', help='also run without deliberate source pacing')
    parser.add_argument('--saturation-only', action='store_true', help='run only stop-and-wait saturation')
    parser.add_argument('--repeats', type=int, default=1, help='alternate Full/Compact order across trials')
    parser.add_argument('--board-batches', type=int, default=0, help='SD-resident repeated inference batches before replay')
    parser.add_argument('--board-batch-size', type=int, default=16)
    parser.add_argument('--streams', type=int, nargs='+', default=[1, 2, 4])
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--order', choices=['full-first', 'compact-first'], default='full-first')
    parser.add_argument('--boot-manifest', type=Path, default=ROOT / 'e07/boot/BOOT_E07_NET_V2_5_FINAL.manifest.json')
    parser.add_argument('--input', type=Path, default=ROOT / 'e07/vendor/e07_base/input.bin')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'results/stream_measurements')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--gui-port', type=int, default=18082)
    parser.add_argument('--keep-gui', action='store_true', help='keep completed evidence visible until Ctrl+C')
    parser.add_argument('--export-paper', action='store_true', help='export verified CSV, LaTeX, PDF/PNG after success')
    parser.add_argument('--no-paper-plots', action='store_true', help='export tables/JSON only')
    args = parser.parse_args(argv)
    import math
    if any(not math.isfinite(v) or v <= 0 for v in (args.duration, args.fps, args.timeout)):
        parser.error('duration, fps and timeout must be finite and positive')
    if args.fps_list and (any(not math.isfinite(v) or v <= 0 for v in args.fps_list)
                          or len(set(args.fps_list)) != len(args.fps_list)):
        parser.error('fps-list must contain unique finite positive rates')
    if args.repeats < 1 or args.board_batches < 0 or not 1 <= args.board_batch_size <= 16:
        parser.error('repeats >=1, board-batches >=0, board-batch-size in 1..16 required')
    if not 1 <= args.port <= 65535 or not 1 <= args.gui_port <= 65535:
        parser.error('ports must be in 1..65535')
    if any(s not in (1, 2, 4) for s in args.streams) or len(set(args.streams)) != len(args.streams):
        parser.error('streams must be unique values from 1, 2, 4')
    directory = args.output_root / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    directory.mkdir(parents=True, exist_ok=False)
    store = SessionStore(args.output_root.parent / 'sessions')
    report = {'schema': 'fvit-e07-replay-measurements-v2', 'source': 'E07_PHYSICAL',
        'status': 'RUNNING', 'collector_revision': 'V2.5', 'experiments': [], 'configuration': vars(args).copy(),
        'limits': ['Fixed preprocessed tensor replay; no live camera and no dataset accuracy evaluation.',
                   'One FPGA and one TCP connection; 1/2/4 multiplexed source streams, not parallel accelerators.',
                   'Socket application bytes exclude TCP/IP/Ethernet overhead and retransmissions.',
                   'PC source and cloud receiver share a clock; board one-way times are synchronization estimates.',
                   'Half-RTT synchronization uncertainty excludes later clock drift; sync is refreshed every 10 seconds.',
                   'result_queue_ticks precedes tcp_write, not NIC departure; result upload includes queueing.',
                   'Full baseline forwards the same tensor without cloud inference; this is not cloud model latency.',
                   'TCP retransmissions and packet loss require independent packet capture; null means unavailable.',
                   'INA226 energy is monitored system-rail energy, not NIC-only or wall power.']}
    report['limits'] += ['Saturation is one outstanding request on one TCP connection, not accelerator peak or pipelined capacity.',
        'One-way time estimates are not publication-grade: clock drift is unbounded; negative estimates are retained.',
        'Offered FPS is a pacing target; unissued scheduled frames are not network packet loss.']
    report['configuration'] = {k: str(v) if isinstance(v, Path) else v for k, v in report['configuration'].items()}
    report['host_runtime'] = dict(platform=platform.platform(), python=sys.version,
        executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
            if getattr(sys, 'frozen', False) else None)
    server = None
    try:
        publish(directory, report)
        if args.gui:
            from werkzeug.serving import make_server
            from Cloud_test.dashboard.app import create_app
            server = make_server('127.0.0.1', args.gui_port,
                create_app(store, measurements_root=args.output_root), threaded=True)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            print(f'E07_DASHBOARD=http://127.0.0.1:{args.gui_port}', flush=True)
        physical(args, report, directory, store)
        report['status'] = 'COMPLETE'
    except KeyboardInterrupt:
        report.update(status='ABORTED', failure='Operator interrupted capture')
    except Exception as exc:
        report.update(status='FAIL', failure=str(exc))
    finally:
        report['evidence_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.jsonl')}
        report['active_stage'] = None
        publish(directory, report)
        rows = [{'camera_streams': e['camera_streams'], 'trial': e['trial'],
                 'load_mode': e['load_mode'], 'mode': mode,
                 **{k: v for k, v in summary.items() if k != 'streams'}}
                for e in report['experiments'] for mode, summary in e['modes'].items()]
        if rows:
            with (directory / 'metrics.csv').open('w', newline='', encoding='utf-8-sig') as out:
                writer = csv.DictWriter(out, fieldnames=sorted(set().union(*(r.keys() for r in rows))))
                writer.writeheader()
                writer.writerows(rows)
        if args.export_paper and report['status'] == 'COMPLETE':
            try:
                from Cloud_test.tools.export_e07_paper import export
                export(directory / 'report.json', directory / 'paper', plots=not args.no_paper_plots)
                print('E07_PAPER=' + str(directory / 'paper'), flush=True)
            except Exception as exc:
                report.update(paper_export_status='FAIL', paper_export_failure=str(exc))
                print('E07_PAPER_EXPORT_FAILURE=' + str(exc), flush=True)
                publish(directory, report)
        print('E07_REPORT=' + str(directory / 'report.json'), flush=True)
        print('E07_STATUS=' + report['status'], flush=True)
        if server:
            if args.keep_gui:
                print('Measurement ended. The dashboard remains available; press Ctrl+C to exit.', flush=True)
                try:
                    threading.Event().wait()
                except KeyboardInterrupt:
                    pass
            server.shutdown()
            server.server_close()
    return 0 if report['status'] == 'COMPLETE' and report.get('paper_export_status') != 'FAIL' else 1


if __name__ == '__main__':
    raise SystemExit(main())
