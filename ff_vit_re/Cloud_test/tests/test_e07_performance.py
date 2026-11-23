"""Observable contracts for the E07 performance and live evidence workflow."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import hashlib
import socket
import threading
import time
import shutil
import subprocess
from unittest.mock import patch

from Cloud_test import run_e07_measurements as runner
from Cloud_test.cloud.session_store import SessionStore
from Cloud_test.dashboard.app import create_app


class PerformanceTests(unittest.TestCase):
    def test_firewall_helper_preserves_chinese_interface_name_on_windows_powershell(self):
        data = (runner.ROOT/'windows/Allow-E07-Collector.ps1').read_bytes()
        # Windows PowerShell 5.1 otherwise decodes non-ASCII scripts using the ANSI code page.
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        self.assertIn("[string]$InterfaceAlias = '以太网'", data.decode('utf-8-sig'))

    def test_paper_export_checks_raw_hash_and_derives_quantiles(self):
        from Cloud_test.tools import export_e07_paper as exporter
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = [dict(kind='edge_result', mode='compact', camera_streams=1,
                request_id=i, stream_id=1, stream_sequence=i, source_sent_payload_bytes=600,
                socket_received_bytes=300, send_monotonic_ns=0,
                receive_monotonic_ns=i * 1000000, metadata={'mismatch_count': 0},
                latency={'e2e_ms': i}) for i in range(1, 5)]
            raw = root / 'frames.jsonl'
            raw.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            report = dict(source='E07_PHYSICAL', status='COMPLETE',
                configuration={'fps': 10}, identity={'model': 'E07'},
                evidence_sha256={'frames.jsonl': hashlib.sha256(raw.read_bytes()).hexdigest()},
                experiments=[dict(camera_streams=1, modes={'compact': dict(status='COMPLETE',
                    frames_sent=4, frames_received=4, socket_received_bytes=1200, elapsed_s=1,
                    missing_responses=0, duplicate_responses=0)})])
            (root/'report.json').write_text(json.dumps(report))
            result = exporter.export(root/'report.json', root/'paper', plots=False)
            self.assertEqual(result['rows'][0]['e2e_ms_p50'], 2.5)
            self.assertAlmostEqual(result['rows'][0]['e2e_ms_p99'], 3.97)
            self.assertTrue((root/'paper'/'measurements.tex').exists())
            self.assertIn('Target FPS/stream', (root/'paper'/'measurements.tex').read_text())
            self.assertEqual(result['unmeasured']['cloud_model_latency'], 'NOT_MEASURED')
            mode_summary = report['experiments'][0]['modes']['compact']
            mode_summary['fps'] = 99999
            (root/'report.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'fps'):
                exporter.export(root/'report.json', root/'false_fps', plots=False)
            del mode_summary['fps']
            report['board_benchmark'] = {'status': 'COMPLETE', 'frames': 32}
            (root/'report.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'board repeat'):
                exporter.export(root/'report.json', root/'unverified_board', plots=False)
            raw.write_text(raw.read_text()+'\n')
            with self.assertRaisesRegex(ValueError, 'hash'):
                exporter.export(root/'report.json', root/'rejected', plots=False)

    def test_browser_cards_follow_live_report_instead_of_empty_session(self):
        chrome = shutil.which('google-chrome') or shutil.which('chromium')
        if not chrome:
            self.skipTest('headless browser unavailable')
        from werkzeug.serving import make_server
        from flask import request
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'stream_measurements' / '20261007T000000.000000Z'
            target.mkdir(parents=True)
            report = {'source': 'E07_PHYSICAL', 'status': 'RUNNING', 'experiments': [],
                'identity': {'model': 'E07', 'board_ip': '192.168.10.2', 'tcp_port': 5001},
                'live': dict(frames_received=7, frames_sent=7, fps=20, e2e_ms_mean=8.3,
                    mode='compact', trial=1, load_mode='fixed', camera_streams=2,
                    updated_at='2026-10-07T00:00:00Z', socket_received_bytes=2300,
                    telemetry={'power_uW': 5700000, 'temperature_mC': 37000})}
            runner.publish(target, report)
            app = create_app(SessionStore(root/'sessions'))
            @app.after_request
            def change_next_snapshot(response):
                if request.path == '/api/measurements/latest':
                    report['live'].update(frames_received=9, updated_at='2026-10-07T00:00:01Z')
                    runner.publish(target, report)
                return response
            server = make_server('127.0.0.1', 0, app, threaded=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
                    '--disable-dev-shm-usage', '--virtual-time-budget=6500', '--dump-dom',
                    f'--user-data-dir={root / "chrome"}', f'http://127.0.0.1:{server.server_port}/'],
                    capture_output=True, text=True, timeout=25)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertRegex(result.stdout, r'id="completed-frames">9<')
                self.assertRegex(result.stdout, r'id="power">5\.7 W<')
                self.assertIn('class="main-svg"', result.stdout)
            finally:
                server.shutdown()
                thread.join(3)
                server.server_close()

    def test_load_schedule_preserves_rates_repeats_and_alternates_order(self):
        args = SimpleNamespace(streams=[1, 2], fps=10, fps_list=[10, 30],
                               repeats=2, saturation=True, saturation_only=False,
                               order='full-first')
        schedule = runner.measurement_conditions(args)
        self.assertEqual(len(schedule), 12)
        self.assertEqual(schedule[0]['offered_fps_per_stream'], 10)
        self.assertEqual(schedule[2]['load_mode'], 'saturation')
        self.assertIsNone(schedule[2]['offered_fps_per_stream'])
        self.assertEqual(schedule[6]['mode_order'], ['compact', 'full'])
        self.assertEqual(schedule[-1]['trial'], 2)

    def test_live_api_exposes_current_counters_without_local_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'stream_measurements' / '20261007T000000.000000Z'
            target.mkdir(parents=True)
            runner.publish(target, {'source': 'E07_PHYSICAL', 'status': 'RUNNING',
                'experiments': [], 'live': {'frames_received': 7, 'fps': 19.5},
                'identity': {'model': 'E07'}, 'configuration': {'input': '/secret/input'}})
            result = create_app(SessionStore(root / 'sessions')).test_client().get(
                '/api/measurements/latest').get_json()
            self.assertEqual(result.get('live', {}).get('frames_received'), 7)
            self.assertEqual(result.get('identity', {}).get('model'), 'E07')
            self.assertNotIn('/secret', json.dumps(result))

    def test_live_api_can_follow_custom_measurement_output_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root/'custom_capture'/'20261007T000000.000000Z'
            target.mkdir(parents=True)
            runner.publish(target, {'source': 'E07_PHYSICAL', 'status': 'RUNNING',
                                    'live': {'frames_received': 13}})
            app = create_app(SessionStore(root/'sessions'), measurements_root=root/'custom_capture')
            result = app.test_client().get('/api/measurements/latest').get_json()
            self.assertEqual(result['live']['frames_received'], 13)

    def test_summary_reports_quantiles_input_bytes_and_unreliable_clock(self):
        frames = []
        for i, milliseconds in enumerate([1, 2, 3, 4], 1):
            frames.append({'request_id': i, 'send_monotonic_ns': 0,
                'receive_monotonic_ns': milliseconds * 1000000,
                'socket_received_bytes': 300, 'socket_sent_bytes': 620,
                'source_sent_payload_bytes': 600, 'metadata': {'total_ticks': 100},
                'latency': {'e2e_ms': milliseconds, 'inference_ms': .1,
                    'edge_receive_ms': .5, 'result_upload_estimated_ms': -.1,
                    'uplink_estimated_ms': .6, 'edge_processing_ms': .01,
                    'network_and_receive_ms': .3, 'sync_half_rtt_ms': .02}})
        result = runner.performance_summary(frames, 2, 4, [], 10, 'fixed')
        self.assertEqual(result['e2e_ms_p50'], 2.5)
        self.assertAlmostEqual(result['e2e_ms_p99'], 3.97)
        self.assertEqual(result['source_payload_bytes'], 2400)
        self.assertEqual(result['socket_sent_bytes'], 2480)
        self.assertEqual(result['edge_receive_ms_mean'], .5)
        self.assertFalse(result['one_way_time_reliable'])
        self.assertEqual(result['negative_upload_estimate_count'], 4)

    def test_saturation_pair_never_claims_matched_rate_bandwidth_saving(self):
        from Cloud_test.tests.test_e07_cloud import E07CloudTests
        mode = E07CloudTests.matched_summary(load_mode='saturation')
        result = runner.compare_replay_modes(mode, mode)
        self.assertFalse(result['matched_run_valid'])
        self.assertIsNone(result['observed_bandwidth_saved_percent'])

    def test_repeat_command_is_sent_with_count_and_validated(self):
        import io
        from Cloud_test.iot_eval.protocol import Message, read_message, write_message
        outgoing = io.BytesIO()
        incoming = io.BytesIO()
        write_message(incoming, Message('ack', 7, {'status': 'ok', 'count': 16,
            'total_ticks': 1600, 'pl_ticks': 1500, 'mm2s_ticks': 50, 's2mm_ticks': 1550}))
        incoming.seek(0)
        reader = SimpleNamespace(bytes_received=0, begin_message=lambda: None,
                                 read=incoming.read)
        response, event = runner.transaction(outgoing, reader, 'repeat_latency', 7,
                                              arguments={'count': 16})
        outgoing.seek(0)
        self.assertEqual(read_message(outgoing).metadata['arguments'], {'count': 16})
        self.assertEqual(response.metadata['count'], 16)
        self.assertGreater(event['socket_sent_bytes'], 0)

    def test_socket_suite_publishes_during_stage_and_runs_saturation_and_board_batches(self):
        from Cloud_test.iot_eval.protocol import Message, read_message, write_message
        from Cloud_test.iot_eval.messages import Hello
        payload = bytes(602112)
        errors, observed = [], []
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture = root / 'input.bin'
            fixture.write_bytes(payload)
            with socket.socket() as allocate:
                allocate.bind(('127.0.0.1', 0))
                port = allocate.getsockname()[1]
            def board():
                try:
                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            conn = socket.create_connection(('127.0.0.1', port), timeout=3)
                            break
                        except OSError:
                            if time.monotonic() > deadline:
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
                            kind, data = 'edge_result', b''
                            m = {'mismatch_count': 0, 'total_ticks': 100, 'predicted_class': 0}
                            if name == 'time_sync':
                                kind = 'ack'
                                m = {'edge_rx_ticks': rx, 'edge_tx_ticks': end, 'timer_frequency_hz': 10**9}
                            elif name == 'repeat_latency':
                                kind = 'ack'
                                m = dict(status='ok', count=16, total_ticks=16000000,
                                         pl_ticks=15000000, mm2s_ticks=1000000, s2mm_ticks=15000000)
                            elif name == 'telemetry':
                                kind = 'telemetry'
                                m = dict(timestamp_ticks=end, power_uW=5000000, temperature_mC=36000,
                                         sensor_valid=True, completed_frames=1)
                            elif name.startswith('replay_'):
                                self.assertEqual(command.payload, payload)
                                kind = 'cloud_frame' if name == 'replay_full' else 'edge_result'
                                data = payload if kind == 'cloud_frame' else b''
                                m.update(fixture='E07_FIXED_INPUT', mode=name, edge_rx_start_ticks=rx,
                                    edge_rx_end_ticks=end, inference_start_ticks=end, inference_end_ticks=end,
                                    result_queue_ticks=end, timer_frequency_hz=10**9)
                                saved = json.loads((root / 'report.json').read_text())
                                if saved.get('live', {}).get('frames_received', 0) > 0:
                                    observed.append(saved['live']['mode'])
                            write_message(stream, Message(kind, command.request_id, m, data))
                except Exception as exc:
                    errors.append(repr(exc))
            args = SimpleNamespace(host='127.0.0.1', port=port, timeout=5, boot_manifest=root/'unused',
                input=fixture, duration=.06, fps=200, streams=[1], order='full-first', repeats=2,
                saturation=True, saturation_only=True, board_batches=2, board_batch_size=16)
            report = {'experiments': []}
            policy = SimpleNamespace(model='E07', artifact_hashes={'input': hashlib.sha256(payload).hexdigest()},
                                     validate=lambda hello: None)
            thread = threading.Thread(target=board)
            thread.start()
            with patch('Cloud_test.run_e07_measurements._IdentityPolicy', return_value=policy):
                runner.physical(args, report, root, SessionStore(root/'sessions'))
            thread.join(5)
            self.assertEqual(errors, [])
            self.assertTrue(observed, 'no report was published before the stage ended')
            self.assertEqual(report.get('board_benchmark', {}).get('frames'), 32)
            self.assertAlmostEqual(report['board_benchmark']['mean_board_latency_ms'], 1)
            self.assertEqual(len(report['experiments']), 2)
            self.assertTrue(all(e['load_mode'] == 'saturation' for e in report['experiments']))
            self.assertEqual(list(report['experiments'][1]['modes']), ['compact', 'full'])
            self.assertGreater(report['live']['frames_received'], 0)
            from Cloud_test.tools.export_e07_paper import export
            report.update(source='E07_PHYSICAL', status='COMPLETE', collector_revision='V2.3',
                evidence_sha256={'frames.jsonl': hashlib.sha256((root/'frames.jsonl').read_bytes()).hexdigest()})
            runner.publish(root, report)
            evidence = export(root/'report.json', root/'paper', plots=False)
            self.assertEqual(len(evidence['rows']), 4)
            self.assertIn('raw monotonic', evidence['rows'][0]['duration_verification_basis'])
            self.assertEqual(evidence['board_benchmark']['frames'], 32)


if __name__ == '__main__':
    unittest.main()
