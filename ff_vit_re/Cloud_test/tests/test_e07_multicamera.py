"""Contracts for independent capture, bounded queues and serial edge service."""
import importlib
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest


class CameraLoadTests(unittest.TestCase):
    def module(self):
        name = 'Cloud_test.iot_eval.camera_load'
        self.assertIsNotNone(importlib.util.find_spec(name), 'camera load engine is not implemented')
        return importlib.import_module(name)

    def test_overflow_evicts_oldest_waiting_frame(self):
        m = self.module()
        q = m.CameraQueues(1, 3)
        for seq in range(1, 5):
            q.put(m.Frame(1, seq, seq, seq))
        self.assertEqual(q.records[0].status, 'dropped_oldest')
        self.assertEqual([q.get_next().sequence for _ in range(3)], [2, 3, 4])
        self.assertIsNone(q.get_next())
        self.assertEqual(q.high_water, [3])

    def test_round_robin_skips_empty_queues_without_starvation(self):
        m = self.module()
        q = m.CameraQueues(4, 3)
        for stream in (1, 3):
            for seq in (1, 2):
                q.put(m.Frame(stream, seq, seq, seq))
        order = [q.get_next().stream_id for _ in range(4)]
        self.assertEqual(order, [1, 3, 1, 3])

    def test_capture_snapshot_is_taken_under_queue_lock(self):
        m = self.module()
        from unittest.mock import patch
        from dataclasses import asdict
        events = []
        q = m.CameraQueues(1, 3, events.append)
        def checked_snapshot(frame):
            self.assertTrue(q.condition._is_owned(), 'snapshot can race serial consumer')
            return asdict(frame)
        with patch.object(m, 'asdict', side_effect=checked_snapshot):
            q.put(m.Frame(1, 1, 0, 0))
        q.get_next().status = 'completed'
        self.assertEqual(events[0]['status'], 'queued')

    def test_timing_and_active_window_exclude_drain(self):
        m = self.module()
        records = [dict(stream_id=1, sequence=1, scheduled_ns=0, capture_ns=1_000_000,
            dispatch_ns=3_000_000, send_monotonic_ns=4_000_000,
            receive_monotonic_ns=9_000_000, status='completed',
            socket_sent_bytes=600, socket_received_bytes=300),
            dict(stream_id=1, sequence=2, scheduled_ns=8_000_000, capture_ns=8_000_000,
            dispatch_ns=9_000_000, send_monotonic_ns=9_000_000,
            receive_monotonic_ns=12_000_000, status='completed',
            socket_sent_bytes=600, socket_received_bytes=300),
            dict(stream_id=1, sequence=3, scheduled_ns=9_000_000, capture_ns=9_000_000,
            status='dropped_oldest')]
        result = m.summarize_condition(records, 0, 10_000_000, 1, [0])
        s = result['summary']
        self.assertEqual(s['completed_active'], 1)
        self.assertEqual(s['completed_drain'], 1)
        self.assertEqual(s['fps'], 100)
        self.assertEqual(s['queue_ms_mean'], 2)
        self.assertEqual(s['service_ms_mean'], 5)
        self.assertEqual(s['e2e_ms_mean'], 8)
        self.assertAlmostEqual(s['drop_rate'], 1 / 3)
        self.assertEqual(s['end_window_backlog'], 1)
        self.assertEqual(s['response_application_mbit_s'], .24)
        self.assertTrue(s['conservation_ok'])

    def test_producers_continue_while_single_service_blocks(self):
        m = self.module()
        active, peak = 0, 0
        def slow_service(frame):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            send = time.monotonic_ns()
            time.sleep(.06)
            active -= 1
            return dict(send_monotonic_ns=send, receive_monotonic_ns=time.monotonic_ns(),
                        socket_sent_bytes=600, socket_received_bytes=300)
        result = m.run_condition(slow_service, 4, 30, .4, capacity=3, drain_timeout=1)
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertEqual(peak, 1)
        self.assertGreater(result['summary']['dropped_oldest'], 0)
        self.assertGreater(result['summary']['produced'], result['summary']['completed_total'])
        self.assertTrue(result['summary']['conservation_ok'])
        self.assertEqual(len(result['per_stream']), 4)
        self.assertTrue(all(s['produced'] >= 9 for s in result['per_stream']))
        self.assertTrue(all(s['produced'] + s['source_missed_slots'] == 12 for s in result['per_stream']))
        self.assertLessEqual(max(result['queue_high_water']), 3)

    def test_service_failure_preserves_partial_accounting_and_stops_threads(self):
        m = self.module()
        def fail(frame):
            raise TimeoutError('simulated missing response')
        result = m.run_condition(fail, 4, 30, 1, capacity=3, drain_timeout=.1)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['summary']['failed'], 1)
        self.assertTrue(result['summary']['conservation_ok'])
        self.assertIn('simulated missing response', result['failure'])
        self.assertEqual(result['summary']['completed_active'], 0)
        self.assertIsNone(result['summary']['e2e_ms_p95'])

    def test_invalid_configuration_is_rejected(self):
        m = self.module()
        for streams, fps, duration, capacity in [(0, 30, 1, 3), (4, 0, 1, 3),
                (4, float('nan'), 1, 3), (4, 30, -1, 3), (4, 30, 1, 0)]:
            with self.subTest(streams=streams, fps=fps, duration=duration, capacity=capacity):
                with self.assertRaises(ValueError):
                    m.run_condition(lambda f: {}, streams, fps, duration, capacity)

    def test_transaction_failure_emits_full_partial_response_diagnostic(self):
        m = self.module()
        from Cloud_test.iot_eval.camera_transport import TransactionError
        events = []
        def fail(frame):
            raise TransactionError('tail timeout', dict(request_id=42,
                response_received_bytes=100, expected_response_bytes=177,
                socket_received_bytes=100, socket_sent_bytes=600,
                send_monotonic_ns=time.monotonic_ns()))
        result = m.run_condition(fail, 1, 30, .1, emit=events.append)
        self.assertEqual(result['status'], 'FAIL')
        failure = next(e for e in events if e['kind'] == 'transaction_failure')
        self.assertEqual(failure['expected_response_bytes'] - failure['response_received_bytes'], 77)
        self.assertEqual(failure['request_id'], 42)
        self.assertEqual(failure['stream_id'], 1)

    def test_startup_interrupt_and_thread_start_failure_do_not_leave_workers(self):
        code = '''
import threading
from unittest.mock import patch
from Cloud_test.iot_eval.camera_load import run_condition
original_wait = threading.Barrier.wait
def interrupted_wait(barrier, *args, **kwargs):
    if threading.current_thread() is threading.main_thread():
        raise KeyboardInterrupt()
    return original_wait(barrier, *args, **kwargs)
with patch.object(threading.Barrier, 'wait', interrupted_wait):
    result = run_condition(lambda frame: {}, 4, 30, .1)
assert result['status'] == 'ABORTED', result
assert not any(t.name.startswith('e07-camera-') for t in threading.enumerate())
original_start = threading.Thread.start
count = 0
def failed_start(thread):
    global count
    count += 1
    if count == 2:
        raise RuntimeError('thread startup failed')
    return original_start(thread)
with patch.object(threading.Thread, 'start', failed_start):
    result = run_condition(lambda frame: {}, 4, 30, .1)
assert result['status'] == 'FAIL', result
assert not any(t.name.startswith('e07-camera-') for t in threading.enumerate())
'''
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CameraTransportTests(unittest.TestCase):
    def module(self):
        name = 'Cloud_test.iot_eval.camera_transport'
        self.assertIsNotNone(importlib.util.find_spec(name), 'cached transport is not implemented')
        return importlib.import_module(name)

    def exchange(self, corrupt_id=False):
        from Cloud_test.iot_eval.protocol import Message, read_message, write_message
        from Cloud_test.iot_eval.camera_load import Frame
        m = self.module()
        host, board = socket.socketpair()
        host.settimeout(1)
        board.settimeout(1)
        errors, commands = [], []
        payload = b'verified-input' * 1000
        def peer():
            try:
                with board, board.makefile('rwb') as stream:
                    for _ in range(1 if corrupt_id else 2):
                        command = read_message(stream)
                        commands.append(command)
                        metadata = dict(fixture='E07_FIXED_INPUT', mode='replay_compact', mismatch_count=0,
                            timer_frequency_hz=100000000, edge_rx_start_ticks=1, edge_rx_end_ticks=2,
                            inference_start_ticks=3, inference_end_ticks=4, result_queue_ticks=5,
                            total_ticks=1, predicted_class=0)
                        write_message(stream, Message('edge_result', command.request_id + int(corrupt_id), metadata))
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=peer)
        thread.start()
        try:
            with host:
                transport = m.ReplayTransport(host, payload, request_id=8)
                packet = transport.packet
                frame = Frame(1, 1, 0, 0)
                if corrupt_id:
                    with self.assertRaises(m.TransactionError) as failure:
                        transport.infer(frame)
                    self.assertGreater(failure.exception.diagnostic['socket_received_bytes'], 0)
                else:
                    events = [transport.infer(frame), transport.infer(frame)]
                    self.assertIs(transport.packet, packet)
                    self.assertEqual([e['request_id'] for e in events], [9, 10])
                    self.assertTrue(all(e['socket_sent_bytes'] == 14060 for e in events))
        finally:
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors, errors)
        self.assertTrue(all(c.payload == payload and c.metadata['name'] == 'replay_compact' for c in commands))
        return commands

    def test_cached_requests_preserve_payload_and_increment_ids(self):
        self.exchange()

    def test_response_id_mismatch_keeps_failure_byte_diagnostics(self):
        self.exchange(corrupt_id=True)

    def test_frame_deadline_bounds_a_partial_response(self):
        from Cloud_test.iot_eval.protocol import HEADER
        from Cloud_test.iot_eval.camera_load import Frame
        m = self.module()
        host, board = socket.socketpair()
        host.settimeout(60)
        frame = Frame(1, 1, 0, 0, deadline_ns=time.monotonic_ns() + 80_000_000)
        # Advertise a response with ten missing bytes, keeping the peer open.
        with host, board:
            board.sendall(HEADER.pack(b'FVIT', 1, 1, 0, 1, 2, 10) + b'{}')
            start = time.monotonic()
            with self.assertRaises(m.TransactionError) as failure:
                m.ReplayTransport(host, b'x').infer(frame)
            self.assertLess(time.monotonic() - start, .5)
            diagnostic = failure.exception.diagnostic
            self.assertEqual(diagnostic['expected_response_bytes'] - diagnostic['response_received_bytes'], 10)

    def test_evidence_writer_flushes_every_event_in_order(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'raw.jsonl'
            writer = m.EvidenceWriter(path)
            for i in range(300):
                writer.emit({'sequence': i})
            writer.close()
            self.assertEqual([json.loads(line)['sequence'] for line in path.read_text().splitlines()], list(range(300)))

    def test_evidence_writer_surfaces_disk_failure(self):
        m = self.module()
        # /dev/full is an actual failing sink, not a mocked writer.
        if not Path('/dev/full').exists():
            self.skipTest('real failing disk device unavailable')
        writer = m.EvidenceWriter(Path('/dev/full'), exclusive=False)
        writer.emit({'value': 'x' * 10000})
        with self.assertRaises(OSError):
            writer.close()


class CameraRunnerTests(unittest.TestCase):
    def runner(self):
        name = 'Cloud_test.run_e07_multicamera'
        self.assertIsNotNone(importlib.util.find_spec(name), 'concurrent runner is not implemented')
        return importlib.import_module(name)

    def test_simulated_cli_exports_all_streams_and_conserves_frames(self):
        self.runner()
        import csv
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, '-m', 'Cloud_test.run_e07_multicamera',
                '--simulate', '--duration', '.3', '--streams', '1', '2', '4', '--fps', '30',
                '--sim-service-ms', '30', '--output-root', folder], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            directory = next(Path(folder).iterdir())
            report = json.loads((directory / 'report.json').read_text())
            self.assertEqual(report['source'], 'HOST_SIMULATION')
            self.assertFalse(report['physical_measurement'])
            self.assertEqual(report['status'], 'COMPLETE')
            self.assertEqual([x['camera_streams'] for x in report['conditions']], [1, 2, 4])
            summaries = list(csv.DictReader((directory / 'summary.csv').read_text(encoding='utf-8-sig').splitlines()))
            streams = list(csv.DictReader((directory / 'streams.csv').read_text(encoding='utf-8-sig').splitlines()))
            frames = list(csv.DictReader((directory / 'frames.csv').read_text(encoding='utf-8-sig').splitlines()))
            self.assertEqual(len(summaries), 3)
            self.assertEqual(len(streams), 7)
            self.assertEqual(len(frames), sum(c['summary']['produced'] for c in report['conditions']))
            self.assertTrue(all(c['summary']['conservation_ok'] for c in report['conditions']))
            self.assertGreater(report['conditions'][-1]['summary']['dropped_oldest'], 0)
            for name, digest in report['evidence_sha256'].items():
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
            raw = [json.loads(x) for x in (directory / 'events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(e['kind'] == 'capture' for e in raw), len(frames))

    def test_cli_rejects_invalid_load_without_creating_run(self):
        m = self.runner()
        for flags in (['--duration', 'nan'], ['--queue-size', '0'], ['--streams', '3'],
                      ['--fps', '0'], ['--drain-timeout', '0']):
            with self.subTest(flags=flags):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                    m.main(['--simulate'] + flags)
                self.assertEqual(exc.exception.code, 2)

    def test_simulation_obeys_drain_deadline_instead_of_sleeping_indefinitely(self):
        m = self.runner()
        from Cloud_test.iot_eval.camera_load import Frame
        frame = Frame(1, 1, 0, 0, deadline_ns=time.monotonic_ns() + 20_000_000)
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            m.simulation_service(500)(frame)
        self.assertLess(time.monotonic() - start, .3)

    def test_windows_wrapper_static_contract_not_execution(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / 'windows/Run-E07-MultiCamera.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('Cloud_test.run_e07_multicamera', script)
        self.assertIn('InvariantCulture', script)
        self.assertIn("'--streams'", script)
        self.assertIn("'--simulate'", script)
        self.assertNotIn('E07_Cloud_GUI.exe', script)
        self.assertNotIn('New-NetFirewallRule', script)
        self.assertTrue((root / 'docs/E07_MULTICAMERA_RUNBOOK_CN.txt').is_file())

    def test_persistent_writer_failure_keeps_all_available_condition_accounting(self):
        m = self.runner()
        import csv
        from unittest.mock import patch
        from Cloud_test.iot_eval.camera_transport import EvidenceWriter
        class FailingWriter(EvidenceWriter):
            broken = False
            def emit(self, event):
                if self.broken or event['kind'] == 'dispatch':
                    self.broken = True
                    raise OSError('injected persistent disk failure')
                return super().emit(event)
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'EvidenceWriter', FailingWriter):
            code = m.main(['--simulate', '--streams', '4', '--duration', '.2', '--output-root', folder])
            self.assertEqual(code, 1)
            directory = next(Path(folder).iterdir())
            report = json.loads((directory / 'report.json').read_text())
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(len(report['conditions']), 1)
            condition = report['conditions'][0]
            self.assertTrue(condition['summary']['conservation_ok'])
            frames = list(csv.DictReader((directory / 'frames.csv').read_text(encoding='utf-8-sig').splitlines()))
            self.assertEqual(len(frames), condition['summary']['produced'])
            self.assertGreater(len(frames), 0)

    def test_failed_condition_exports_partial_data_and_returns_nonzero(self):
        m = self.runner()
        from unittest.mock import patch
        def fail(frame):
            raise TimeoutError('missing test response')
        with tempfile.TemporaryDirectory() as folder:
            # Only the unavailable board service is replaced; producers,
            # dispatcher, timing, evidence writer and exporters remain real.
            with patch.object(m, 'simulation_service', return_value=fail):
                code = m.main(['--simulate', '--streams', '4', '--duration', '.2', '--output-root', folder])
            self.assertEqual(code, 1)
            directory = next(Path(folder).iterdir())
            report = json.loads((directory / 'report.json').read_text())
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(report['conditions'][0]['summary']['failed'], 1)
            self.assertTrue(report['conditions'][0]['summary']['conservation_ok'])
            self.assertTrue((directory / 'frames.csv').is_file())
            self.assertIn('missing test response', report['failure'])


if __name__ == '__main__':
    unittest.main()
