import json
from pathlib import Path
import re
import tempfile
import socket
import threading
import time
import subprocess
import shutil
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from Cloud_test.cloud.board_server import _IdentityPolicy
from Cloud_test.cloud.session_store import SessionStore
from Cloud_test.iot_eval.messages import Hello
from Cloud_test.dashboard.app import create_app


class E07CloudTests(unittest.TestCase):
    def test_packaging_rejects_boot_manifest_mismatch(self):
        from Cloud_test.tools.package_e07_cloud import verify_release_inputs
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder)
            boot = candidate / 'e07/boot'
            boot.mkdir(parents=True)
            manifest = root / 'e07/boot/BOOT_E07_NET_V2_2_FINAL.manifest.json'
            shutil.copy2(manifest, boot / manifest.name)
            (boot / 'BOOT_E07_NET_V2_2_FINAL.BIN').write_bytes(b'wrong image')
            with self.assertRaisesRegex(ValueError, 'BOOT.*mismatch'):
                verify_release_inputs(candidate, ('FINAL',), release='V2_2')
    def test_build_identity_binds_window_batch_and_optimization(self):
        from Cloud_test.build_scripts.rebuild_e07_net import bind_profile
        original = {'canonical_payload': {'tool_policy': {}, 'inputs': {}},
                    'advertised_sha256': 'a' * 64}
        profiles = [dict(tcp_wnd=2048, batch_verify=0, ps_optimization='-O0'),
                    dict(tcp_wnd=32768, batch_verify=0, ps_optimization='-O0'),
                    dict(tcp_wnd=32768, batch_verify=1, ps_optimization='-O0'),
                    dict(tcp_wnd=32768, batch_verify=1, ps_optimization='-O2')]
        results = [bind_profile(original, p) for p in profiles]
        self.assertEqual(len({r['advertised_sha256'] for r in results}), 4)
        self.assertEqual(results[-1]['canonical_payload']['tool_policy']['e07_network_profile'], profiles[-1])
        self.assertEqual(original['canonical_payload']['tool_policy'], {})
    def test_compiled_c_replay_verifies_input_and_preserves_full_payload(self):
        compiler = shutil.which('gcc')
        if compiler is None:
            self.skipTest('C contract test needs gcc')
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'replay-test'
            includes = ['e07/firmware/e06_net', 'e07/firmware/common', 'firmware/e06_net/tests/fake_lwip']
            sources = ['e07/tests/test_replay.c', 'e07/firmware/e06_net/e06_network.c',
                       'e07/firmware/common/fvit_protocol.c', 'firmware/e06_net/tests/fake_lwip/fake_lwip.c']
            command = [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-DE06_HOST_TEST',
                '-DE06_FIRMWARE_SHA256="' + 'a'*64 + '"',
                *['-I' + str(root / p) for p in includes], *[str(root / p) for p in sources],
                '-o', str(output)]
            for batch in (0, 1):
                for optimization in ('-O0', '-O2'):
                    subprocess.run(command + [f'-DE07_BATCH_VERIFY={batch}', optimization],
                                   check=True, capture_output=True)
                    for arguments in ([], ['limited-allocation'], ['backpressure'],
                                      ['tail-drain'], ['tail-wrap']):
                        result = subprocess.run([str(output), *arguments],
                                                capture_output=True, text=True, timeout=20)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        marker = ('E07_ACK_DRAIN_OK' if arguments in (['tail-drain'], ['tail-wrap'])
                                  else 'E07_BACKPRESSURE_RECONNECT_OK' if arguments == ['backpressure']
                                  else 'E07_REPLAY_CONTRACT_OK')
                        self.assertIn(marker, result.stdout)

    def test_partial_payload_is_counted_even_when_response_times_out(self):
        from Cloud_test import run_e07_measurements as runner
        from Cloud_test.iot_eval.protocol import HEADER, read_message
        left, right = socket.socketpair()
        with left, right:
            left.settimeout(.03)
            wire = HEADER.pack(b'FVIT', 1, 1, 0, 23, 2, 1000) + b'{}' + b'x' * 117
            right.sendall(wire)
            reader = runner.SocketStream(left)
            with self.assertRaises(TimeoutError):
                read_message(reader)
            self.assertEqual(reader.bytes_received, 139)

    def test_trickle_response_cannot_extend_transaction_deadline(self):
        from Cloud_test import run_e07_measurements as runner
        from Cloud_test.iot_eval.protocol import HEADER, read_message
        left, right = socket.socketpair()
        stop = threading.Event()
        def trickle():
            while not stop.wait(.01):
                try:
                    right.sendall(b'x')
                except OSError:
                    return
        with left, right:
            left.settimeout(.06)
            right.sendall(HEADER.pack(b'FVIT', 1, 1, 0, 23, 2, 1000) + b'{}')
            reader = runner.SocketStream(left)
            thread = threading.Thread(target=trickle)
            thread.start()
            begin = time.monotonic()
            try:
                with self.assertRaises(TimeoutError):
                    read_message(reader)
            finally:
                stop.set()
                thread.join()
            self.assertLess(time.monotonic() - begin, .2)

    def test_transaction_failure_records_partial_body_and_request(self):
        import io
        from Cloud_test import run_e07_measurements as runner
        from Cloud_test.iot_eval.protocol import HEADER
        left, right = socket.socketpair()
        with left, right:
            left.settimeout(.03)
            right.sendall(HEADER.pack(b'FVIT', 1, 1, 0, 23, 2, 1000) + b'{}' + b'x' * 117)
            stream = runner.SocketStream(left)
            raw = io.StringIO()
            with self.assertRaises(TimeoutError):
                runner.transaction(stream, stream, 'replay_full', 23, raw=raw)
            failure = json.loads(raw.getvalue())
            self.assertEqual(failure['kind'], 'transaction_failure')
            self.assertEqual(failure['request_id'], 23)
            self.assertEqual(failure['response_payload_received_bytes'], 117)
            self.assertEqual(failure['expected_response_bytes'], 1022)

    def test_complete_error_response_is_preserved_in_failure_evidence(self):
        import io
        from Cloud_test import run_e07_measurements as runner
        from Cloud_test.iot_eval.protocol import Message, write_message
        wire = io.BytesIO()
        write_message(wire, Message('error', 23, {'code': 'fixture_mismatch'}))
        left, right = socket.socketpair()
        with left, right:
            left.settimeout(.05)
            right.sendall(wire.getvalue())
            stream = runner.SocketStream(left)
            raw = io.StringIO()
            with self.assertRaises(ValueError):
                runner.transaction(stream, stream, 'replay_full', 23, raw=raw)
            self.assertTrue(raw.getvalue(), 'complete error response has no failure evidence')
            failure = json.loads(raw.getvalue())
            self.assertEqual(failure['response_kind_code'], 255)
            self.assertEqual(failure['metadata'], {'code': 'fixture_mismatch'})

    def test_failed_pair_does_not_publish_bandwidth_or_energy_savings(self):
        from Cloud_test import run_e07_measurements as runner
        full = dict(status='FAIL', bytes_received_per_frame=602431,
                    bandwidth_bytes_s=10000, monitored_system_energy_J=18)
        compact = dict(status='COMPLETE', bytes_received_per_frame=326,
                       bandwidth_bytes_s=3000, monitored_system_energy_J=80)
        comparison = runner.compare_replay_modes(full, compact)
        self.assertIsNone(comparison['observed_bandwidth_saved_percent'])
        self.assertIsNone(comparison['system_energy_difference_J'])
        self.assertFalse(comparison['matched_run_valid'])
        self.assertGreater(comparison['per_frame_bytes_saved_percent'], 99.9)

    def test_complete_but_saturated_pair_cannot_claim_bandwidth_savings(self):
        from Cloud_test import run_e07_measurements as runner
        full = self.matched_summary(bytes_received_per_frame=602431, bandwidth_bytes_s=1204862,
                                    fps=2, frames_sent=20, frames_received=20)
        compact = self.matched_summary()
        result = runner.compare_replay_modes(full, compact)
        self.assertIsNone(result['observed_bandwidth_saved_percent'])
        self.assertIsNone(result['system_energy_difference_J'])

    def test_missing_measurement_fields_fail_closed_without_exception(self):
        from Cloud_test import run_e07_measurements as runner
        for key in ('bytes_received_per_frame', 'bandwidth_bytes_s', 'monitored_system_energy_J'):
            with self.subTest(key=key):
                full = self.matched_summary()
                del full[key]
                try:
                    result = runner.compare_replay_modes(full, self.matched_summary())
                except (KeyError, TypeError) as exc:
                    self.fail(f'missing field crashes comparison: {exc}')
                self.assertIsNone(result['observed_bandwidth_saved_percent'])
                self.assertIsNone(result['monitored_mean_power_difference_W'])

    def test_reported_fps_must_match_verified_counts_and_elapsed(self):
        from Cloud_test import run_e07_measurements as runner
        compact = self.matched_summary(frames_sent=50, frames_received=50)
        result = runner.compare_replay_modes(self.matched_summary(), compact)
        self.assertFalse(result['matched_run_valid'])
        self.assertIsNone(result['observed_bandwidth_saved_percent'])

    def test_invalid_numeric_metrics_cannot_break_or_poison_comparison_json(self):
        from Cloud_test import run_e07_measurements as runner
        for key in ('bytes_received_per_frame', 'bandwidth_bytes_s', 'elapsed_s', 'fps'):
            for value in ('bad', float('nan'), float('inf'), True, -1):
                with self.subTest(key=key, value=value):
                    result = runner.compare_replay_modes(self.matched_summary(**{key: value}),
                                                         self.matched_summary())
                    self.assertFalse(result['matched_run_valid'])
                    self.assertIsNone(result['observed_bandwidth_saved_percent'])
                    json.dumps(result, allow_nan=False)

    def test_boolean_offered_rate_is_not_a_matching_numeric_rate(self):
        from Cloud_test import run_e07_measurements as runner
        result = runner.compare_replay_modes(self.matched_summary(offered_fps_per_stream=1),
            self.matched_summary(offered_fps_per_stream=True))
        self.assertFalse(result['matched_run_valid'])

    @staticmethod
    def matched_summary(**changes):
        result = dict(status='COMPLETE', completed_requested_duration=True,
            bytes_received_per_frame=326, bandwidth_bytes_s=3260, fps=10,
            frames_sent=100, frames_received=100, missing_responses=0,
            duplicate_responses=0, sequence_continuous=True, offered_fps_per_stream=10,
            elapsed_s=10, monitored_system_energy_J=50, energy_coverage_s=10,
            energy_coverage_fraction=1)
        result.update(changes)
        return result

    def test_matched_pair_uses_coverage_normalized_power_not_stage_energy_difference(self):
        from Cloud_test import run_e07_measurements as runner
        full = self.matched_summary(bytes_received_per_frame=602431,
            bandwidth_bytes_s=6024310, monitored_system_energy_J=60)
        result = runner.compare_replay_modes(full, self.matched_summary())
        self.assertGreater(result['observed_bandwidth_saved_percent'], 99.9)
        self.assertIsNone(result['system_energy_difference_J'])
        self.assertEqual(result['monitored_mean_power_difference_W'], 1)

    def test_inadequate_power_coverage_cannot_claim_power_difference(self):
        from Cloud_test import run_e07_measurements as runner
        full = self.matched_summary(monitored_system_energy_J=5,
            energy_coverage_s=1, energy_coverage_fraction=.1)
        result = runner.compare_replay_modes(full, self.matched_summary())
        self.assertIsNone(result['system_energy_difference_J'])
        self.assertIsNone(result['monitored_mean_power_difference_W'])

    def test_corrupted_complete_full_response_is_logged_as_transaction_failure(self):
        import io
        from Cloud_test import run_e07_measurements as runner
        from Cloud_test.iot_eval.protocol import Message, write_message
        wire = io.BytesIO()
        write_message(wire, Message('cloud_frame', 23,
            {'fixture': 'E07_FIXED_INPUT', 'mode': 'replay_full', 'mismatch_count': 0}, b'bad'))
        left, right = socket.socketpair()
        with left, right:
            left.settimeout(.05)
            right.sendall(wire.getvalue())
            stream, raw = runner.SocketStream(left), io.StringIO()
            with self.assertRaisesRegex(ValueError, 'payload corruption'):
                runner.transaction(stream, stream, 'replay_full', 23, b'good', raw=raw)
            failure = json.loads(raw.getvalue())
            self.assertEqual(failure['metadata']['mode'], 'replay_full')
            self.assertEqual(failure['response_payload_received_bytes'], 3)

    def test_zero_timer_sync_is_logged_as_validation_failure_not_zero_division(self):
        import io
        from Cloud_test import run_e07_measurements as runner
        from Cloud_test.iot_eval.protocol import Message, write_message
        wire = io.BytesIO()
        write_message(wire, Message('ack', 23,
            {'timer_frequency_hz': 0, 'edge_rx_ticks': 1, 'edge_tx_ticks': 2}))
        left, right = socket.socketpair()
        with left, right:
            left.settimeout(.05)
            right.sendall(wire.getvalue())
            stream, raw = runner.SocketStream(left), io.StringIO()
            with self.assertRaises(Exception) as raised:
                runner.synchronize(stream, stream, lambda: 23, raw)
            self.assertIsInstance(raised.exception, ValueError)
            self.assertIn('timer frequency', str(raised.exception))
            self.assertEqual(json.loads(raw.getvalue())['kind'], 'transaction_failure')

    def test_packet_capture_summary_deduplicates_retransmission_flags(self):
        from Cloud_test.tools.analyze_e07_tcp_capture import summarize_packets
        result = summarize_packets('1.0\t120\t60\t1\t1\t\t0\n1.1\t100\t40\t\t\t1\t1\n')
        self.assertEqual(result['captured_frame_bytes'], 220)
        self.assertEqual(result['tcp_retransmission_packets'], 1)
        self.assertEqual(result['tcp_reset_packets'], 1)
        self.assertEqual(result['suspected_lost_segments'], 1)
        self.assertIsNone(result['packet_loss_rate'])

    def test_real_socket_replay_suite_captures_all_six_modes_and_actual_bytes(self):
        from Cloud_test.run_e07_measurements import physical
        from Cloud_test.iot_eval.protocol import Message, read_message, write_message
        import hashlib
        payload = bytes(602112)
        errors = []
        with socket.socket() as allocation:
            allocation.bind(('127.0.0.1', 0))
            port = allocation.getsockname()[1]
        def board():
            try:
                deadline = time.monotonic() + 5
                while True:
                    try:
                        conn = socket.create_connection(('127.0.0.1', port), timeout=3)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(.01)
                with conn, conn.makefile('rwb') as stream:
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    write_message(stream, Hello('E07_PHYSICAL', 'E07', 'a'*64,
                        {'input': hashlib.sha256(payload).hexdigest()}, '127.0.0.1', 5001).to_message(0))
                    while stream.peek(1):
                        rx = time.monotonic_ns()
                        command = read_message(stream)
                        end = time.monotonic_ns()
                        name = command.metadata['name']
                        m = {'mismatch_count': 0, 'predicted_class': 1, 'total_ticks': 1}
                        data = b''
                        if name == 'time_sync':
                            kind = 'ack'
                            m = {'edge_rx_ticks': rx, 'edge_tx_ticks': end, 'timer_frequency_hz': 1_000_000_000}
                        elif name == 'telemetry':
                            kind = 'telemetry'
                            m = {'timestamp_ticks': end, 'power_uW': 2_000_000,
                                 'temperature_mC': 37000, 'completed_frames': 1, 'sensor_valid': True}
                        elif name == 'compact_result':
                            kind = 'edge_result'
                        else:
                            self.assertEqual(command.payload, payload)
                            kind = 'cloud_frame' if name == 'replay_full' else 'edge_result'
                            data = payload if kind == 'cloud_frame' else b''
                            m.update(fixture='E07_FIXED_INPUT', mode=name, edge_rx_start_ticks=rx,
                                edge_rx_end_ticks=end, inference_start_ticks=end, inference_end_ticks=end,
                                result_queue_ticks=time.monotonic_ns(), timer_frequency_hz=1_000_000_000)
                        write_message(stream, Message(kind, command.request_id, m, data))
            except Exception as exc:
                errors.append(str(exc))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = root / 'input.bin'
            input_path.write_bytes(payload)
            args = SimpleNamespace(host='127.0.0.1', port=port, timeout=5, boot_manifest=root/'unused',
                input=input_path, duration=.15, fps=20, streams=[1, 2, 4], order='full-first')
            report = {'experiments': []}
            thread = threading.Thread(target=board)
            thread.start()
            policy = SimpleNamespace(model='E07', artifact_hashes={'input': hashlib.sha256(payload).hexdigest()},
                                     validate=lambda hello: None)
            with patch('Cloud_test.run_e07_measurements._IdentityPolicy', return_value=policy):
                physical(args, report, root, SessionStore(root/'sessions'))
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(len(report['experiments']), 3)
            for experiment in report['experiments']:
                self.assertGreater(experiment['comparison']['per_frame_bytes_saved_percent'], 99)
                for mode in experiment['modes'].values():
                    self.assertEqual(mode['status'], 'COMPLETE')
                    self.assertEqual(mode['missing_responses'], 0)
                    self.assertGreater(mode['e2e_ms_p95'], 0)

    def test_dashboard_experiment_api_reports_latest_measurements_without_raw_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report_dir = root / 'stream_measurements' / '20261004T000000.000000Z'
            report_dir.mkdir(parents=True)
            (report_dir / 'report.json').write_text(json.dumps({'source': 'E07_PHYSICAL',
                'status': 'COMPLETE', 'raw_path': '/private/evidence', 'experiments': [
                    {'camera_streams': 1, 'modes': {'full': {'bytes_received_per_frame': 602500}}}]}))
            response = create_app(SessionStore(root / 'sessions')).test_client().get('/api/measurements/latest')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['source'], 'E07_PHYSICAL')
            self.assertNotIn('/private', response.get_data(as_text=True))

    def test_latency_breakdown_uses_board_clock_and_marks_estimated_one_way_times(self):
        from Cloud_test.run_e07_measurements import latency_breakdown
        result = latency_breakdown({
            'send_monotonic_ns': 1_000_000_000, 'receive_monotonic_ns': 1_020_000_000,
            'metadata': {'timer_frequency_hz': 1000, 'edge_rx_start_ticks': 1102,
                'edge_rx_end_ticks': 1105, 'inference_start_ticks': 1106,
                'inference_end_ticks': 1110, 'result_queue_ticks': 1111}},
            {'board_minus_host_ns': 100_000_000, 'half_rtt_bound_ns': 2_000_000})
        self.assertEqual(result['e2e_ms'], 20)
        self.assertEqual(result['inference_ms'], 4)
        self.assertEqual(result['uplink_estimated_ms'], 5)
        self.assertEqual(result['result_upload_estimated_ms'], 9)
        self.assertEqual(result['edge_processing_ms'], 2)
        self.assertEqual(result['network_and_receive_ms'], 11)
        self.assertTrue(result['one_way_estimated'])

    def test_e07_manifest_accepts_only_matching_e07_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            hashes = {key: 'a' * 64 for key in ('bitstream', 'input', 'output', 'weights', 'xsa')}
            manifest = root / 'boot.json'
            manifest.write_text(json.dumps({'model': 'E07', 'phase': 'E07_PHYSICAL',
                'firmware_identity': {'advertised_sha256': 'b' * 64,
                    'canonical_payload': {'inputs': {'copied_vendor_inputs': {
                        key: {'sha256': value} for key, value in hashes.items()}}}}}))
            policy = _IdentityPolicy(manifest)
            hello = Hello('E07_PHYSICAL', 'E07', 'b' * 64, hashes, '192.168.10.2', 5001)
            policy.validate(hello)
            store = SessionStore(root / 'sessions')
            session = store.begin(hello)
            self.assertEqual(store.snapshot(session)['model'], 'E07')
            self.assertEqual(store.snapshot(session)['accuracy_reason'], 'E07 model is not PlantVillage')
            with self.assertRaises(ValueError):
                policy.validate(Hello('E06_PHYSICAL', 'E06', 'b' * 64, hashes, '192.168.10.2', 5001))

    def test_rendered_dashboard_and_client_messages_are_english(self):
        with tempfile.TemporaryDirectory() as folder:
            client = create_app(SessionStore(Path(folder) / 'sessions')).test_client()
            for route in ('/', '/static/dashboard.js'):
                response = client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(re.search('[\u4e00-\u9fff]', response.get_data(as_text=True)))
                response.close()
