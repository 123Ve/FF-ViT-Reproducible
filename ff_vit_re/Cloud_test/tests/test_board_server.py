from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from Cloud_test.iot_eval.messages import Hello, InferenceResult, Telemetry
from Cloud_test.iot_eval.protocol import Message, HEADER, read_message, write_message


FIRMWARE = "a" * 64
ARTIFACTS = {
    "bitstream": "b" * 64,
    "input": hashlib.sha256(b"fixed-input").hexdigest(),
    "output": "d" * 64,
    "weights": "e" * 64,
    "xsa": "f" * 64,
}


def hello(**changes) -> Hello:
    values = dict(phase="E06_PHYSICAL", model="E06", firmware_sha256=FIRMWARE,
                  artifact_hashes=ARTIFACTS, board_ip="192.168.10.2", tcp_port=5001)
    values.update(changes)
    return Hello(**values)


class BoardCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.manifest = root / "BOOT.manifest.json"
        copied = {name: {"sha256": digest, "bytes": 1} for name, digest in ARTIFACTS.items()}
        self.manifest.write_text(json.dumps({
            "firmware_identity": {
                "advertised_sha256": FIRMWARE,
                "canonical_payload": {"inputs": {"copied_vendor_inputs": copied}},
            }
        }), encoding="utf-8")
        from Cloud_test.cloud.session_store import SessionStore
        from Cloud_test.cloud.board_server import BoardCollector
        self.store = SessionStore(root / "sessions")
        self.collector = BoardCollector(("127.0.0.1", 0), self.store,
                                        boot_manifest=self.manifest, socket_timeout=0.5)
        self.collector.start()
        self.addCleanup(self.collector.shutdown)

    def connect(self):
        return socket.create_connection(self.collector.bound_address, timeout=2)

    def wait_for(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.01)
        self.fail("collector state did not update")

    def test_fragmented_real_socket_flow_persists_frozen_firmware_schemas(self):
        with self.connect() as connection:
            with connection.makefile("rwb", buffering=0) as stream:
                encoded = bytearray()
                class Sink:
                    def write(self, data):
                        encoded.extend(data)
                        return len(data)

                    def flush(self):
                        pass
                write_message(Sink(), hello().to_message(0))
                for byte in encoded:
                    connection.sendall(bytes([byte]))
                write_message(stream, Message("ack", 1,
                    {"model": "E06", "phase": "E06_PHYSICAL", "status": "ok"}))
                write_message(stream, InferenceResult(3, 0, 120, 80, 20, 20).to_message(2))
                write_message(stream, Telemetry(99, 3_000_000, 51_000, 1, True).to_message(2))
                write_message(stream, Message("cloud_frame", 3,
                    {"fixture": "E06_FIXED_INPUT", "mode": "full_payload"}, b"fixed-input"))
                write_message(stream, Message("edge_result", 4,
                    {"predicted_class": 3, "mismatch_count": 0, "total_ticks": 125,
                     "pl_ticks": 85, "mm2s_ticks": 20, "s2mm_ticks": 20}))
        summaries = self.wait_for(lambda: self.store.list_sessions())
        session_id = summaries[0]["session_id"]
        snapshot = self.wait_for(lambda: (
            self.store.snapshot(session_id)
            if self.store.snapshot(session_id)["connection_state"] == "disconnected" else None))
        self.assertEqual(snapshot["event_count"], 7)  # connect, five frames, disconnect
        self.assertEqual(snapshot["sample_count"], 2)
        self.assertEqual(snapshot["full_payload_wire_bytes"],
                         HEADER.size + len(b'{"fixture":"E06_FIXED_INPUT","mode":"full_payload"}') + 11)
        self.assertEqual(snapshot["accuracy_reason"], "E06 model is not PlantVillage")

    def test_rejects_out_of_order_and_identity_mismatch_without_killing_server(self):
        with self.connect() as connection:
            with connection.makefile("rwb", buffering=0) as stream:
                write_message(stream, Telemetry(1, None, None, 0, False).to_message(1))
                error = read_message(stream)
                self.assertEqual(error.kind, "error")
                self.assertEqual(error.metadata["code"], "hello_required")
        with self.connect() as connection:
            with connection.makefile("rwb", buffering=0) as stream:
                write_message(stream, hello(firmware_sha256="1" * 64).to_message(0))
                error = read_message(stream)
                self.assertEqual(error.metadata["code"], "identity_mismatch")
        self.assertEqual(self.store.list_sessions(), [])

        with self.connect() as connection:
            with connection.makefile("rwb", buffering=0) as stream:
                write_message(stream, hello().to_message(0))
                write_message(stream, Message("error", 8, {
                    "code": "inference_failed", "detail": "timeout", "phase": "E06_PHYSICAL"}))
        summary = self.wait_for(lambda: self.store.list_sessions())
        session_id = summary[0]["session_id"]
        self.wait_for(lambda: self.store.snapshot(session_id)["error_count"] == 1)

    def test_malformed_frame_and_reconnect_preserve_completed_session(self):
        with self.connect() as connection:
            connection.sendall(b"BAD!" + bytes(HEADER.size - 4))
            with connection.makefile("rwb", buffering=0) as stream:
                error = read_message(stream)
                self.assertEqual(error.metadata["code"], "protocol_error")
        with self.connect() as connection:
            with connection.makefile("rwb", buffering=0) as stream:
                write_message(stream, hello().to_message(0))
                write_message(stream, InferenceResult(2, 0, 10, 6, 2, 2).to_message(1))
        first = self.wait_for(lambda: self.store.list_sessions())
        first_id = first[0]["session_id"]
        self.wait_for(lambda: self.store.snapshot(first_id)["connection_state"] == "disconnected")
        with self.connect() as connection:
            with connection.makefile("rwb", buffering=0) as stream:
                write_message(stream, hello().to_message(0))
        sessions = self.wait_for(lambda: self.store.list_sessions() if len(self.store.list_sessions()) == 2 else None)
        self.assertEqual(self.store.snapshot(first_id)["sample_count"], 1)
        self.assertEqual(len({item["session_id"] for item in sessions}), 2)

    def test_hello_requires_the_frozen_board_address_and_port(self):
        for changes in ({"board_ip": "192.168.10.3"}, {"tcp_port": 5002}):
            with self.subTest(changes=changes), self.connect() as connection:
                with connection.makefile("rwb", buffering=0) as stream:
                    write_message(stream, hello(**changes).to_message(0))
                    error = read_message(stream)
                    self.assertEqual(error.kind, "error")
                    self.assertEqual(error.metadata["code"], "identity_mismatch")
        self.assertEqual(self.store.list_sessions(), [])

    def test_duplicate_hello_is_persisted_as_a_session_error(self):
        with self.connect() as connection:
            with connection.makefile("rwb", buffering=0) as stream:
                write_message(stream, hello().to_message(0))
                write_message(stream, hello().to_message(9))
                error = read_message(stream)
                self.assertEqual(error.metadata["code"], "duplicate_hello")
        sessions = self.wait_for(lambda: self.store.list_sessions())
        session_id = sessions[0]["session_id"]
        summary = self.wait_for(
            lambda: self.store.snapshot(session_id)
            if self.store.snapshot(session_id)["connection_state"] == "disconnected" else None
        )
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["recent_errors"][0]["code"], "duplicate_hello")

    def test_shutdown_closes_active_board_socket_and_persists_disconnect(self):
        self.collector._server.socket_timeout = 30.0
        connection = self.connect()
        stream = connection.makefile("rwb", buffering=0)
        try:
            write_message(stream, hello().to_message(0))
            sessions = self.wait_for(lambda: self.store.list_sessions())
            session_id = sessions[0]["session_id"]
            self.wait_for(
                lambda: self.store.snapshot(session_id)["connection_state"] == "connected"
            )

            self.collector.shutdown()

            summary = self.wait_for(
                lambda: self.store.snapshot(session_id)
                if self.store.snapshot(session_id)["connection_state"] == "disconnected"
                else None,
                timeout=1.0,
            )
            self.assertEqual(summary["connection_state"], "disconnected")
            connection.settimeout(0.2)
            self.assertEqual(connection.recv(1), b"")
        finally:
            stream.close()
            connection.close()

    def test_shutdown_cannot_miss_socket_before_worker_thread_runs(self):
        server = self.collector._server
        worker_entered = threading.Event()
        release_worker = threading.Event()
        close_snapshot_taken = threading.Event()
        original_worker = server.process_request_thread
        original_close = server.close_active_connections

        def delayed_worker(request, client_address):
            worker_entered.set()
            release_worker.wait(timeout=2.0)
            original_worker(request, client_address)

        def observed_close():
            original_close()
            close_snapshot_taken.set()

        server.process_request_thread = delayed_worker
        server.close_active_connections = observed_close
        connection = self.connect()
        shutdown_thread = threading.Thread(target=self.collector.shutdown)
        try:
            self.assertTrue(worker_entered.wait(timeout=1.0))
            shutdown_thread.start()
            self.assertTrue(close_snapshot_taken.wait(timeout=1.0))
            connection.settimeout(0.2)
            self.assertEqual(connection.recv(1), b"")
        finally:
            release_worker.set()
            connection.close()
            shutdown_thread.join(timeout=2.0)
        self.assertFalse(shutdown_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
