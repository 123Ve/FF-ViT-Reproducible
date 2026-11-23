from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import unittest

from Cloud_test.cloud.session_store import SessionStore
from Cloud_test.iot_eval.messages import Hello


HASH = "a" * 64


def _hello() -> Hello:
    return Hello(
        phase="E06_PHYSICAL",
        model="E06",
        firmware_sha256=HASH,
        artifact_hashes={"weights": "b" * 64, "input": "c" * 64},
        board_ip="192.168.10.2",
        tcp_port=5001,
    )


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SessionStore(Path(self.temp.name) / "sessions")
        from Cloud_test.dashboard.app import create_app

        self.app = create_app(self.store)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def _populated_session(self) -> str:
        session_id = self.store.begin(_hello())
        events = [
            {"kind": "connection", "state": "connected", "received_at_ns": 1_000_000_000},
            {
                "kind": "cloud_frame",
                "request_id": 1,
                "received_at_ns": 2_000_000_000,
                "metadata": {"fixture": "E06_FIXED_INPUT", "mode": "full_payload"},
                "payload_bytes": 1000,
                "payload_sha256": "d" * 64,
                "wire_bytes": 1100,
            },
            {
                "kind": "edge_result",
                "request_id": 2,
                "received_at_ns": 3_000_000_000,
                "metadata": {
                    "predicted_class": 7,
                    "mismatch_count": 0,
                    "total_ticks": 125,
                    "pl_ticks": 80,
                    "mm2s_ticks": 20,
                    "s2mm_ticks": 25,
                },
                "payload_bytes": 0,
                "wire_bytes": 110,
            },
            {
                "kind": "telemetry",
                "request_id": 3,
                "received_at_ns": 4_000_000_000,
                "metadata": {
                    "timestamp_ticks": 10,
                    "power_uW": None,
                    "temperature_mC": None,
                    "completed_frames": 1,
                    "sensor_valid": False,
                },
                "payload_bytes": 0,
                "wire_bytes": 100,
            },
            {
                "kind": "error",
                "request_id": 4,
                "received_at_ns": 5_000_000_000,
                "metadata": {
                    "code": "unsafe",
                    "detail": '<img src=x onerror="alert(1)">',
                    "phase": "E06_PHYSICAL",
                },
                "payload_bytes": 0,
                "wire_bytes": 90,
            },
        ]
        for event in events:
            self.store.append(session_id, event)
        return session_id

    def test_empty_store_apis_are_json_and_health_waits_for_board(self):
        sessions = self.client.get("/api/sessions")
        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(sessions.content_type, "application/json")
        self.assertEqual(sessions.get_json(), {"sessions": []})

        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.content_type, "application/json")
        self.assertEqual(health.get_json(), {
            "status": "ok",
            "collector_state": "waiting_for_board",
            "phase": None,
            "latest_phase": None,
            "session_count": 0,
        })

    def test_populated_session_preserves_evidence_nulls_and_hides_paths(self):
        session_id = self._populated_session()

        listing = self.client.get("/api/sessions")
        payload = listing.get_json()
        self.assertEqual(len(payload["sessions"]), 1)
        summary = payload["sessions"][0]
        self.assertEqual(summary["session_id"], session_id)
        self.assertIsNone(summary["accuracy"])
        self.assertEqual(summary["accuracy_reason"], "E06 model is not PlantVillage")
        self.assertNotIn(str(self.store.root), json.dumps(payload))
        self.assertFalse(any("path" in key.lower() for key in summary))

        response = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        detail = response.get_json()
        self.assertIsNone(detail["latest_power_uW"])
        self.assertIsNone(detail["latest_temperature_mC"])
        self.assertEqual(detail["artifact_hashes"], _hello().artifact_hashes)
        self.assertEqual(detail["recent_errors"][0]["detail"],
                         '<img src=x onerror="alert(1)">')

        health = self.client.get("/api/health").get_json()
        self.assertEqual(health["collector_state"], "connected")
        self.assertEqual(health["phase"], "E06_PHYSICAL")
        self.assertEqual(health["latest_phase"], "E06_PHYSICAL")
        self.assertEqual(health["session_count"], 1)

    def test_unknown_and_invalid_session_ids_return_bounded_json_errors(self):
        unknown = "20260928T120000.000000Z-0123456789ab"
        response = self.client.get(f"/api/sessions/{unknown}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json(), {"error": "session_not_found"})

        response = self.client.get("/api/sessions/not-a-session")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json(), {"error": "invalid_session_id"})

        unsafe_paths = (
            ("../escape", "..%2Fescape"),
            ("nested/session", "nested%2Fsession"),
            ("leading slash", "%2Fetc"),
            ("null byte", "bad%00id"),
        )
        for unsafe_path, encoded in unsafe_paths:
            response = self.client.get(f"/api/sessions/{encoded}")
            self.assertEqual(response.status_code, 400, unsafe_path)
            self.assertEqual(response.content_type, "application/json", unsafe_path)
            self.assertEqual(response.get_json(), {"error": "invalid_session_id"})

    def test_index_is_offline_responsive_and_uses_safe_rendering(self):
        self._populated_session()
        response = self.client.get("/")
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/html; charset=utf-8")
        html = response.get_data(as_text=True)
        self.assertIn("FF-ViT IoT Dashboard", html)
        self.assertIn('name="viewport"', html)
        self.assertIn('/static/plotly.min.js', html)
        self.assertIn('/static/dashboard.js', html)
        self.assertNotIn('<img src=x onerror="alert(1)">', html)
        script_sources = re.findall(r'<script[^>]+src=["\']([^"\']+)', html)
        self.assertTrue(script_sources)
        self.assertTrue(all(not source.startswith(("http://", "https://", "//"))
                            for source in script_sources))

        script = self.client.get("/static/dashboard.js")
        style = self.client.get("/static/style.css")
        plotly = self.client.get("/static/plotly.min.js")
        for asset in (script, style, plotly):
            self.addCleanup(asset.close)
            self.assertEqual(asset.status_code, 200)
            self.assertGreater(len(asset.data), 100)
        javascript = script.get_data(as_text=True)
        self.assertNotIn("innerHTML", javascript)
        self.assertIn("textContent", javascript)
        self.assertIn("AbortController", javascript)
        self.assertIn("Plotly.react", javascript)
        self.assertIn("value == null", javascript)
        self.assertIn("health.phase", javascript)
        policy = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("style-src 'self' 'unsafe-inline'", policy)
        self.assertIn("script-src 'self'", policy)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_headless_chrome_renders_plotly_without_csp_violations(self):
        chrome = shutil.which("google-chrome") or shutil.which("chromium")
        if chrome is None:
            self.skipTest("Chrome/Chromium is unavailable")

        from werkzeug.serving import make_server

        server = make_server("127.0.0.1", 0, self.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop_server() -> None:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()

        self.addCleanup(stop_server)
        browser_profile = Path(self.temp.name) / "chrome-profile"
        result = subprocess.run(
            [
                chrome,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                f"--user-data-dir={browser_profile}",
                "--virtual-time-budget=2500",
                "--dump-dom",
                "--enable-logging=stderr",
                "--v=1",
                f"http://127.0.0.1:{server.server_port}/",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('class="main-svg"', result.stdout)
        console = "\n".join(line for line in result.stderr.splitlines()
                            if "INFO:CONSOLE" in line)
        self.assertNotIn("Content Security Policy", console)
        self.assertNotIn("Refused to apply inline style", console)
        self.assertNotIn("Cannot addRelatedStyleRule, probably due to strict CSP", console)
        self.assertNotIn('"WARN:', console)


if __name__ == "__main__":
    unittest.main()
