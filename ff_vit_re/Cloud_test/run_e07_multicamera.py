"""Concurrent virtual captures -> bounded queues -> one Compact FPGA service.

Windows: python -m Cloud_test.run_e07_multicamera --duration 20 --streams 1 2 4
No GUI, firmware, HLS or PL changes. Simulation is explicitly not board evidence.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import socket
import sys
import time

from Cloud_test.cloud.board_server import _IdentityPolicy
from Cloud_test.iot_eval.camera_load import run_condition
from Cloud_test.iot_eval.camera_transport import EvidenceWriter, ReplayTransport
from Cloud_test.iot_eval.messages import Hello
from Cloud_test.iot_eval.protocol import read_message
from Cloud_test.run_e07_measurements import ROOT, SocketStream, transaction


def simulation_service(milliseconds):
    """CPU timer-only simulation: no fabricated network byte measurements."""
    def infer(frame):
        send = time.monotonic_ns()
        if frame.deadline_ns is not None and send + milliseconds * 1e6 >= frame.deadline_ns:
            time.sleep(max(0, (frame.deadline_ns - send) / 1e9))
            raise TimeoutError('simulated service exceeded drain deadline')
        time.sleep(milliseconds / 1000)
        return dict(send_monotonic_ns=send, receive_monotonic_ns=time.monotonic_ns(),
                    socket_sent_bytes=0, socket_received_bytes=0)
    return infer


def write_report(path, report):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(.05 * (attempt + 1))


def write_csv(path, rows):
    keys = sorted(set().union(*(row.keys() for row in rows))) if rows else ['condition_id', 'stream_id', 'status']
    with path.open('x', encoding='utf-8-sig', newline='') as output:
        writer = csv.DictWriter(output, keys)
        writer.writeheader()
        writer.writerows(rows)


def capture_conditions(args, report, writer, service, all_frames):
    for trial in range(1, args.repeats + 1):
        for streams in args.streams:
            context = dict(condition_id=len(report['conditions']) + 1, trial=trial,
                           camera_streams=streams, fps_per_stream=args.fps)
            print(f'E07_MC_STAGE trial={trial} cameras={streams} fps={args.fps:g} '
                  f'queue={args.queue_size} duration={args.duration:g}s', flush=True)
            writer.emit(dict(kind='condition_start', **context, wall_ns=time.time_ns()))
            result = run_condition(service, streams, args.fps, args.duration, args.queue_size,
                args.drain_timeout, emit=lambda event: writer.emit({**context, **event}))
            condition_frames = result.pop('records')
            for row in condition_frames:
                row.update(context)
                row['in_active_window'] = (row['status'] == 'completed'
                    and result['start_monotonic_ns'] <= row['receive_monotonic_ns'] < result['end_monotonic_ns'])
                for metric, left, right in [('queue_ms', 'capture_ns', 'dispatch_ns'),
                        ('service_ms', 'send_monotonic_ns', 'receive_monotonic_ns'),
                        ('e2e_ms', 'capture_ns', 'receive_monotonic_ns')]:
                    row[metric] = (row[right] - row[left]) / 1e6 if row.get(right) is not None and row.get(left) is not None else None
                all_frames.append(row)
            result.update(context)
            report['conditions'].append(result)
            # Preserve every available outcome before an unhealthy writer can
            # interrupt evidence emission. Logging failure still fails the run.
            for row in condition_frames:
                if row['status'] != 'completed':
                    writer.emit(dict(kind='terminal_frame', **row))
            writer.emit(dict(kind='condition_end', **context, status=result['status'], summary=result['summary']))
            s = result['summary']
            print(f'E07_MC_RESULT cameras={streams} fps={s["fps"]:.3f} '
                  f'produced={s["produced"]} overflow={s["dropped_oldest"]} '
                  f'drop_rate={s["drop_rate"]:.4%} drain={s["completed_drain"]}', flush=True)
            if not s['conservation_ok']:
                raise ValueError('produced frame accounting does not conserve frames')
            if result['status'] != 'COMPLETE':
                report['status'] = result['status']
                raise RuntimeError(result['failure'])


def physical(args, report, writer, all_frames):
    policy = _IdentityPolicy(args.boot_manifest)
    if policy.model != 'E07':
        raise ValueError('the concurrent suite requires an E07 BOOT manifest')
    payload = args.input.read_bytes()
    if len(payload) != 602112 or hashlib.sha256(payload).hexdigest() != policy.artifact_hashes['input']:
        raise ValueError('input length/SHA256 differs from the verified E07 SD fixture')
    report['input_sha256'] = hashlib.sha256(payload).hexdigest()
    report['boot_manifest_sha256'] = hashlib.sha256(args.boot_manifest.read_bytes()).hexdigest()
    with socket.socket() as listener:
        listener.bind((args.host, args.port))
        listener.listen(1)
        listener.settimeout(args.timeout)
        print(f'E07_COLLECTOR_LISTENING={args.host}:{args.port}', flush=True)
        print('Power-cycle the V2.5 board now. Stop every other collector first.', flush=True)
        connection, peer = listener.accept()
        with connection:
            connection.settimeout(args.timeout)
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            stream = SocketStream(connection)
            hello = Hello.from_message(read_message(stream))
            policy.validate(hello)
            if peer[0] != hello.board_ip:
                raise ValueError('TCP peer does not match the board identity')
            report['identity'] = asdict(hello)
            writer.emit(dict(kind='identity', identity=report['identity']))
            _, warmup = transaction(stream, stream, 'compact_result', 1)
            writer.emit(dict(kind='warmup', **warmup))
            transport = ReplayTransport(connection, payload, request_id=1)
            capture_conditions(args, report, writer, transport.infer, all_frames)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=20)
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--streams', nargs='+', type=int, choices=(1, 2, 4), default=[1, 2, 4])
    parser.add_argument('--queue-size', type=int, default=3)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--drain-timeout', type=float, default=5)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--host', default='192.168.10.1')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--boot-manifest', type=Path, default=ROOT / 'e07/boot/BOOT_E07_NET_V2_5_FINAL.manifest.json')
    parser.add_argument('--input', type=Path, default=ROOT / 'e07/vendor/e07_base/input.bin')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'results/multicamera_measurements')
    parser.add_argument('--simulate', action='store_true', help='host-only simulation; NEVER physical evidence')
    parser.add_argument('--sim-service-ms', type=float, default=12)
    args = parser.parse_args(argv)
    if any(not math.isfinite(x) or x <= 0 for x in
           (args.duration, args.fps, args.drain_timeout, args.timeout, args.sim_service_ms)):
        parser.error('duration, fps and timeouts must be finite and positive')
    if args.queue_size < 1 or args.repeats < 1 or not 1 <= args.port <= 65535:
        parser.error('queue-size/repeats must be positive; port must be 1..65535')
    if len(args.streams) != len(set(args.streams)):
        parser.error('streams must be unique')
    return args


def main(argv=None):
    args = parse_args(argv)
    directory = args.output_root / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    directory.mkdir(parents=True, exist_ok=False)
    report = dict(schema='fvit-e07-independent-camera-v1', collector_revision='E07_MC_V1',
        source='HOST_SIMULATION' if args.simulate else 'E07_PHYSICAL',
        physical_measurement=not args.simulate, status='RUNNING', conditions=[],
        configuration={key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        host_runtime=dict(platform=platform.platform(), python=sys.version),
        scope=dict(producers='independent 30 FPS by default; absolute host deadlines; no response backpressure',
            queue='per-camera FIFO, bounded, drop oldest waiting frame',
            service='one serial Compact inference request; unchanged FPGA and firmware',
            payload='same verified fixed SD tensor for all virtual cameras; no content diversity',
            fps='verified responses received inside active production window / window seconds',
            queue_latency='dispatch minus actual capture',
            service_latency='complete response received minus request send start; response validation outside timestamp',
            e2e_latency='complete response received minus actual capture; includes queue and dispatcher overhead',
            latency_samples='only verified responses received inside the active window',
            drop_rate='queue overflow evictions / actually produced frames; excludes source missed slots',
            bandwidth='whole protocol bytes of verified active-window completions / window seconds; not NIC wire rate',
            drain='after production stops; separately counted; no throughput inflation',
            clocks='host monotonic only; no board/host one-way clock subtraction',
            control_bytes='HELLO/warmup excluded from business byte rates',
            unmeasured='classification accuracy, power/energy, TCP retransmissions and real camera traffic',
            gui='separate console-and-export runner; legacy GUI unchanged'))
    print('E07_MC_SOURCE=' + report['source'], flush=True)
    print('E07_MC_OUTPUT=' + str(directory.resolve()), flush=True)
    writer = None
    frames = []
    try:
        write_report(directory / 'report.json', report)
        writer = EvidenceWriter(directory / 'events.jsonl')
        if args.simulate:
            capture_conditions(args, report, writer, simulation_service(args.sim_service_ms), frames)
        else:
            physical(args, report, writer, frames)
        report['status'] = 'COMPLETE'
    except KeyboardInterrupt:
        report.update(status='ABORTED', failure='Operator interrupted capture')
    except Exception as exc:
        if report['status'] != 'ABORTED':
            report['status'] = 'FAIL'
        report['failure'] = str(exc)
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception as exc:
                report.update(status='FAIL', evidence_failure=str(exc))
        totals, streams = [], []
        for condition in report['conditions']:
            base = {key: condition[key] for key in ('condition_id', 'trial', 'camera_streams', 'fps_per_stream', 'status')}
            totals.append({**base, **condition['summary']})
            streams.extend({**base, **row} for row in condition['per_stream'])
        try:
            for name, rows in [('frames.csv', frames), ('streams.csv', streams), ('summary.csv', totals)]:
                write_csv(directory / name, rows)
            report['evidence_sha256'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in directory.iterdir() if path.suffix in ('.csv', '.jsonl')}
        except Exception as exc:
            report.update(status='FAIL', export_failure=str(exc))
        write_report(directory / 'report.json', report)
        print('E07_MC_REPORT=' + str((directory / 'report.json').resolve()), flush=True)
        print('E07_MC_STATUS=' + report['status'], flush=True)
    return 0 if report['status'] == 'COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
