from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from Cloud_test.iot_eval.messages import Hello


HASH = "a" * 64


def e06_hello() -> Hello:
    return Hello(
        phase="E06_PHYSICAL",
        model="E06",
        firmware_sha256=HASH,
        artifact_hashes={"weights": "b" * 64, "input": "c" * 64},
        board_ip="192.168.10.2",
        tcp_port=5001,
    )


class SessionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        from Cloud_test.cloud.session_store import SessionStore

        self.root = Path(self.temp.name) / "sessions"
        self.store = SessionStore(self.root)

    def test_session_is_append_only_recoverable_and_keeps_e06_accuracy_unavailable(self):
        session_id = self.store.begin(e06_hello())
        self.store.append(session_id, {
            "kind": "connection", "state": "connected", "received_at_ns": 1_000_000_000,
        })
        self.store.append(session_id, {
            "kind": "inference_result", "request_id": 7, "received_at_ns": 2_000_000_000,
            "metadata": {"predicted_class": 4, "mismatch_count": 0,
                         "total_ticks": 120, "pl_ticks": 80,
                         "mm2s_ticks": 20, "s2mm_ticks": 20},
            "payload_bytes": 0, "wire_bytes": 151,
        })
        self.store.append(session_id, {
            "kind": "telemetry", "request_id": 7, "received_at_ns": 2_500_000_000,
            "metadata": {"timestamp_ticks": 900, "power_uW": 3_000_000,
                         "temperature_mC": 51_250, "completed_frames": 1,
                         "sensor_valid": True},
            "payload_bytes": 0, "wire_bytes": 143,
        })
        self.store.append(session_id, {
            "kind": "telemetry", "request_id": 8, "received_at_ns": 3_500_000_000,
            "metadata": {"timestamp_ticks": 1000, "power_uW": None,
                         "temperature_mC": None, "completed_frames": 1,
                         "sensor_valid": False},
            "payload_bytes": 0, "wire_bytes": 138,
        })
        self.store.append(session_id, {
            "kind": "connection", "state": "disconnected", "received_at_ns": 4_000_000_000,
        })

        session_dir = self.root / session_id
        original_manifest = (session_dir / "session.json").read_bytes()
        lines_before = (session_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines_before), 5)

        from Cloud_test.cloud.session_store import SessionStore
        reopened = SessionStore(self.root)
        snapshot = reopened.snapshot(session_id)
        self.assertEqual((session_dir / "session.json").read_bytes(), original_manifest)
        self.assertEqual(snapshot["sample_count"], 1)
        self.assertEqual(snapshot["latest_latency_ticks"], 120)
        self.assertEqual(snapshot["mean_latency_ticks"], 120)
        self.assertIsNone(snapshot["latest_power_uW"])
        self.assertIsNone(snapshot["latest_temperature_mC"])
        self.assertEqual(snapshot["mean_power_uW"], 3_000_000)
        self.assertEqual(snapshot["valid_power_samples"], 1)
        self.assertEqual(snapshot["valid_temperature_samples"], 1)
        self.assertEqual(snapshot["connection_state"], "disconnected")
        self.assertIsNone(snapshot["accuracy"])
        self.assertEqual(snapshot["accuracy_reason"], "E06 model is not PlantVillage")
        self.assertEqual(snapshot["artifact_hashes"], e06_hello().artifact_hashes)

        reopened.append(session_id, {
            "kind": "error", "request_id": 9, "received_at_ns": 5_000_000_000,
            "metadata": {"code": "inference_failed", "detail": "timeout",
                         "phase": "E06_PHYSICAL"},
            "payload_bytes": 0, "wire_bytes": 99,
        })
        self.assertEqual(len((session_dir / "events.jsonl").read_text().splitlines()), 6)
        self.assertEqual(reopened.snapshot(session_id)["error_count"], 1)
        self.assertEqual(reopened.list_sessions()[0]["session_id"], session_id)

    def test_atomic_summary_survives_platforms_that_cannot_open_directories(self):
        """Windows cannot open a directory fd for the POSIX durability fsync."""
        with mock.patch(
            "Cloud_test.cloud.session_store.os.open",
            side_effect=PermissionError(13, "directory open is unsupported"),
        ):
            session_id = self.store.begin(e06_hello())

        summary = self.store.snapshot(session_id)
        self.assertEqual(summary["session_id"], session_id)
        self.assertEqual(summary["connection_state"], "not_connected")

    def test_wire_reduction_fps_energy_and_invalid_sensor_are_derived_without_raw_float_loss(self):
        session_id = self.store.begin(e06_hello())
        events = [
            {"kind": "cloud_frame", "request_id": 1, "received_at_ns": 1_000_000_000,
             "metadata": {"fixture": "E06_FIXED_INPUT", "mode": "full_payload"},
             "payload_bytes": 1000, "payload_sha256": "d" * 64, "wire_bytes": 1100},
            {"kind": "edge_result", "request_id": 2, "received_at_ns": 2_000_000_000,
             "metadata": {"predicted_class": 1, "mismatch_count": 0,
                          "total_ticks": 100, "pl_ticks": 60,
                          "mm2s_ticks": 20, "s2mm_ticks": 20},
             "payload_bytes": 0, "wire_bytes": 110},
            {"kind": "edge_result", "request_id": 3, "received_at_ns": 3_000_000_000,
             "metadata": {"predicted_class": 1, "mismatch_count": 0,
                          "total_ticks": 200, "pl_ticks": 120,
                          "mm2s_ticks": 40, "s2mm_ticks": 40},
             "payload_bytes": 0, "wire_bytes": 110},
            {"kind": "telemetry", "request_id": 4, "received_at_ns": 3_000_000_000,
             "metadata": {"timestamp_ticks": 1, "power_uW": 2_000_000,
                          "temperature_mC": 50_000, "completed_frames": 2,
                          "sensor_valid": True}, "payload_bytes": 0, "wire_bytes": 100},
            {"kind": "telemetry", "request_id": 5, "received_at_ns": 4_000_000_000,
             "metadata": {"timestamp_ticks": 2, "power_uW": 4_000_000,
                          "temperature_mC": 52_000, "completed_frames": 2,
                          "sensor_valid": True}, "payload_bytes": 0, "wire_bytes": 100},
        ]
        for event in events:
            self.store.append(session_id, event)
        summary = self.store.snapshot(session_id)
        self.assertEqual(summary["full_payload_wire_bytes"], 1100)
        self.assertEqual(summary["compact_result_wire_bytes"], 220)
        self.assertEqual(summary["uplink_reduction_percent"], 90.0)
        self.assertEqual(summary["full_bytes_per_frame"], 1100)
        self.assertEqual(summary["compact_bytes_per_frame"], 110)
        self.assertEqual(summary["mean_latency_ticks"], 150)
        self.assertEqual(summary["fps"], 1.0)
        self.assertEqual(summary["mean_power_uW"], 3_000_000)
        self.assertEqual(summary["monitored_energy_uJ"], 3_000_000)
        raw = [json.loads(line) for line in (self.root / session_id / "events.jsonl").read_text().splitlines()]
        self.assertIs(type(raw[3]["metadata"]["power_uW"]), int)

    def test_rejects_unsafe_session_ids_non_json_and_non_e06_identity(self):
        with self.assertRaisesRegex(ValueError, "E06_PHYSICAL"):
            self.store.begin(Hello(**(e06_hello().__dict__ | {"phase": "HOST_LOOPBACK"})))
        with self.assertRaisesRegex(ValueError, "E06"):
            self.store.begin(Hello(**(e06_hello().__dict__ | {"model": "other"})))
        session_id = self.store.begin(e06_hello())
        with self.assertRaisesRegex(ValueError, "session id"):
            self.store.snapshot("../escape")
        with self.assertRaisesRegex(ValueError, "JSON"):
            self.store.append(session_id, {"kind": "error", "bad": object()})

    def test_concurrent_snapshot_reads_never_observe_partial_json(self):
        import threading

        session_id = self.store.begin(e06_hello())
        failures = []
        done = threading.Event()

        def reader():
            while not done.is_set():
                try:
                    snapshot = self.store.snapshot(session_id)
                    self.assertEqual(snapshot["session_id"], session_id)
                except BaseException as exc:
                    failures.append(exc)
                    done.set()

        thread = threading.Thread(target=reader)
        thread.start()
        try:
            for index in range(20):
                self.store.append(session_id, {
                    "kind": "inference_result", "request_id": index,
                    "received_at_ns": index + 1,
                    "metadata": {"predicted_class": 0, "mismatch_count": 0,
                                 "total_ticks": index, "pl_ticks": index,
                                 "mm2s_ticks": 0, "s2mm_ticks": 0},
                    "payload_bytes": 0, "wire_bytes": 100,
                })
        finally:
            done.set()
            thread.join(timeout=2)
        self.assertEqual(failures, [])
        self.assertEqual(self.store.snapshot(session_id)["sample_count"], 20)

    def test_energy_does_not_bridge_an_invalid_telemetry_gap(self):
        session_id = self.store.begin(e06_hello())
        samples = [
            (1_000_000_000, 2_000_000, 50_000, True),
            (2_000_000_000, None, None, False),
            (3_000_000_000, 4_000_000, 52_000, True),
        ]
        for index, (received, power, temperature, valid) in enumerate(samples):
            self.store.append(session_id, {
                "kind": "telemetry", "request_id": index,
                "received_at_ns": received,
                "metadata": {"timestamp_ticks": index, "power_uW": power,
                             "temperature_mC": temperature,
                             "completed_frames": 0, "sensor_valid": valid},
                "payload_bytes": 0, "wire_bytes": 100,
            })
        self.assertIsNone(self.store.snapshot(session_id)["monitored_energy_uJ"])


if __name__ == "__main__":
    unittest.main()
