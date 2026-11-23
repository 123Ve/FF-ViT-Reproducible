import unittest
import hashlib
import socket
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from Cloud_test.iot_eval.cloud_measurements import summarize_frames, compare_modes


class MeasurementTests(unittest.TestCase):
    def test_matched_per_frame_ratio_and_duplicate_accounting(self):
        def frame(seq, size, latency):
            return dict(request_id=seq, socket_received_bytes=size,
                        send_monotonic_ns=0, receive_monotonic_ns=latency)
        full = summarize_frames([frame(1, 1000, 1_000_000)], 1, 1)
        compact = summarize_frames([frame(i, 100, 2_000_000) for i in range(1, 11)], 1, 10)
        self.assertEqual(compare_modes(full, compact)['per_frame_bytes_saved_percent'], 90)
        self.assertEqual(compare_modes(full, compact)['observed_bandwidth_saved_percent'], 0)
        self.assertEqual(compact['command_response_latency_p95_ms'], 2)
        broken = summarize_frames([frame(1, 1, 1), frame(1, 1, 1), frame(3, 1, 1)], 1, 3)
        self.assertEqual(broken['missing_responses'], 1)
        self.assertEqual(broken['duplicate_responses'], 1)
        self.assertFalse(broken['sequence_continuous'])

    def test_energy_never_bridges_unavailable_power(self):
        samples = [dict(monotonic_ns=i * 1_000_000_000, power_uW=p)
                   for i, p in enumerate([2_000_000, 4_000_000, None, 9_000_000])]
        result = summarize_frames([], 3, 0, samples)
        self.assertEqual(result['monitored_system_energy_J'], 3)
        self.assertEqual(result['energy_sample_intervals'], 1)
        self.assertIsNone(result['tcp_retransmissions'])
        self.assertIsNone(result['nic_transmission_energy_J'])

    def test_physical_runner_collects_both_modes_with_fake_board(self):
        from Cloud_test.run_stream_measurements import physical
        from Cloud_test.iot_eval.messages import Hello, Telemetry, InferenceResult
        from Cloud_test.iot_eval.protocol import Message, write_message, read_message
        payload = b'fixture'
        with socket.socket() as allocation:
            allocation.bind(('127.0.0.1', 0))
            port = allocation.getsockname()[1]
        failures = []
        def board():
            deadline = time.monotonic() + 2
            while True:
                try:
                    connection = socket.create_connection(('127.0.0.1', port), timeout=1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        failures.append('listener unavailable')
                        return
                    time.sleep(.01)
            try:
                with connection, connection.makefile('rwb') as wire:
                    write_message(wire, Hello('E06_PHYSICAL', 'E06', 'a'*64,
                        {'input': hashlib.sha256(payload).hexdigest()}, '127.0.0.1', 5001).to_message(0))
                    while wire.peek(1):
                        command = read_message(wire)
                        name = command.metadata['name']
                        if name == 'telemetry':
                            response = Telemetry(1, 2_000_000, 37_000, 1, True).to_message(command.request_id)
                        elif name == 'full_payload':
                            response = Message('cloud_frame', command.request_id,
                                {'fixture': 'E06_FIXED_INPUT', 'mode': 'full_payload'}, payload)
                        else:
                            result = InferenceResult(1, 0, 100, 80, 10, 10)
                            response = Message('edge_result', command.request_id, result.to_message(0).metadata)
                        write_message(wire, response)
            except Exception as exc:
                failures.append(str(exc))
        policy = SimpleNamespace(validate=lambda hello: None, phase='E06_PHYSICAL', model='E06',
                                 artifact_hashes={'input': hashlib.sha256(payload).hexdigest()})
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(host='127.0.0.1', port=port, timeout=2,
                boot_manifest=Path('unused'), duration=.2, fps=20, telemetry_interval=.05,
                order='full-first')
            record = {'raw_path': str(Path(directory) / 'frames.jsonl')}
            thread = threading.Thread(target=board)
            thread.start()
            with patch('Cloud_test.run_stream_measurements._IdentityPolicy', return_value=policy):
                physical(args, record)
            thread.join(timeout=2)
            self.assertEqual(record['status'], 'COMPLETE')
            for mode in record['modes'].values():
                self.assertGreater(mode['frames_received'], 0)
                self.assertEqual(mode['missing_responses'], 0)
                self.assertIsNotNone(mode['monitored_system_energy_J'])
            self.assertTrue(Path(record['raw_path']).is_file())
        self.assertEqual(failures, [])
