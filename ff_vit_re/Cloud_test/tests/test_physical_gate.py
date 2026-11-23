from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest

from Cloud_test.iot_eval.messages import Hello, InferenceResult, Telemetry
from Cloud_test.iot_eval.protocol import Message, read_message, write_message


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PhysicalCommandPathTests(unittest.TestCase):
    def test_standard_plan_is_exactly_1007_ordered_commands(self):
        from Cloud_test.cloud.command_plan import PhysicalCommandPlan

        runner = PhysicalCommandPlan.standard().new_runner()
        observed = []
        for request_id in range(1, 1008):
            item = runner.next_command()
            self.assertIsNotNone(item)
            message, event = item
            self.assertEqual(message.request_id, request_id)
            self.assertEqual(event["request_id"], request_id)
            observed.append((message.metadata["name"], message.metadata["arguments"],
                             event["plan_phase"], event.get("group"), event.get("frame")))
            name = message.metadata["name"]
            kinds = {
                "health": ("ack",), "run_once": ("inference_result", "telemetry"),
                "telemetry": ("telemetry",), "repeat_latency": ("ack",),
                "full_payload": ("cloud_frame",), "compact_result": ("edge_result",),
            }[name]
            for kind in kinds:
                runner.accept(Message(kind, request_id, {}))
        self.assertTrue(runner.complete.is_set())
        self.assertIsNone(runner.next_command())
        self.assertEqual(observed[:7], [
            ("health", {}, "functional", None, None),
            ("run_once", {}, "functional", None, None),
            ("telemetry", {}, "functional", None, None),
            ("repeat_latency", {"count": 1}, "functional", None, None),
            ("full_payload", {}, "functional", None, None),
            ("compact_result", {}, "functional", None, None),
            ("run_once", {}, "warmup", None, 0),
        ])
        self.assertEqual(observed[-1],
                         ("compact_result", {}, "measurement", 9, 99))

    def test_all_six_commands_use_one_verified_board_connection(self):
        from Cloud_test.cloud.board_server import BoardCollector
        from Cloud_test.cloud.command_plan import PhysicalCommandPlan
        from Cloud_test.cloud.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = {
                "bitstream": "b" * 64, "input": _digest(b"input"),
                "output": "d" * 64, "weights": "e" * 64, "xsa": "f" * 64,
            }
            manifest = root / "boot.json"
            manifest.write_text(json.dumps({"firmware_identity": {
                "advertised_sha256": "a" * 64,
                "canonical_payload": {"inputs": {"copied_vendor_inputs": {
                    name: {"sha256": value} for name, value in artifacts.items()
                }}},
            }}), encoding="utf-8")
            plan = PhysicalCommandPlan.functional_only()
            store = SessionStore(root / "sessions")
            collector = BoardCollector(("127.0.0.1", 0), store,
                                       boot_manifest=manifest, socket_timeout=2,
                                       command_plan=plan)
            collector.start()
            self.addCleanup(collector.shutdown)
            seen: list[str] = []

            with socket.create_connection(collector.bound_address, timeout=2) as connection:
                with connection.makefile("rwb", buffering=0) as stream:
                    write_message(stream, Hello(
                        "E06_PHYSICAL", "E06", "a" * 64, artifacts,
                        "192.168.10.2", 5001).to_message(0))
                    for _ in range(6):
                        command = read_message(stream)
                        self.assertEqual(command.kind, "command")
                        name = command.metadata["name"]
                        seen.append(name)
                        request_id = command.request_id
                        if name == "health":
                            reply = Message("ack", request_id,
                                            {"model": "E06", "phase": "E06_PHYSICAL",
                                             "status": "ok"})
                            write_message(stream, reply)
                        elif name in {"run_once", "compact_result"}:
                            kind = "inference_result" if name == "run_once" else "edge_result"
                            result = InferenceResult(1, 0, 20, 10, 5, 5).to_message(request_id)
                            write_message(stream, Message(kind, request_id, result.metadata))
                            if name == "run_once":
                                write_message(stream, Telemetry(10, None, None, 1, False)
                                              .to_message(request_id))
                        elif name == "telemetry":
                            write_message(stream, Telemetry(11, None, None, 1, False)
                                          .to_message(request_id))
                        elif name == "repeat_latency":
                            write_message(stream, Message("ack", request_id, {
                                "count": 1, "mm2s_ticks": 5, "pl_ticks": 10,
                                "s2mm_ticks": 5, "status": "ok", "total_ticks": 20,
                            }))
                        elif name == "full_payload":
                            write_message(stream, Message("cloud_frame", request_id,
                                {"fixture": "E06_FIXED_INPUT", "mode": "full_payload"},
                                b"input"))
            self.assertEqual(seen, ["health", "run_once", "telemetry",
                                    "repeat_latency", "full_payload", "compact_result"])
            self.assertTrue(collector.wait_for_plan(2))
            sessions = store.list_sessions()
            self.assertEqual(len(sessions), 1)
            events = [json.loads(line) for line in
                      (store.root / sessions[0]["session_id"] / "events.jsonl")
                      .read_text(encoding="utf-8").splitlines()]
            self.assertEqual([event["metadata"]["name"] for event in events
                              if event["kind"] == "command"], seen)


class PhysicalGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cloud = Path(self.temporary.name) / "Cloud_test"
        self.session = self.cloud / "results/sessions/physical-001"
        self.session.mkdir(parents=True)
        (self.cloud / "boot").mkdir()
        (self.cloud / "vendor/e06_base/data").mkdir(parents=True)
        (self.cloud / "vendor/e06_base/hw").mkdir(parents=True)
        (self.cloud / "build/e06_net_workspace/e06_net/build").mkdir(parents=True)
        self.files = {
            "boot": self.cloud / "boot/BOOT_E06_NET.BIN",
            "weights": self.cloud / "vendor/e06_base/data/weights.bin",
            "input": self.cloud / "vendor/e06_base/data/input.bin",
            "reference_output": self.cloud / "vendor/e06_base/data/output.bin",
            "bitstream": self.cloud / "vendor/e06_base/hw/design_1_wrapper.bit",
            "application_elf": self.cloud / "build/e06_net_workspace/e06_net/build/e06_net.elf",
        }
        for name, path in self.files.items():
            path.write_bytes(name.encode())
        self.artifacts = {
            "bitstream": _digest(b"bitstream"), "input": _digest(b"input"),
            "output": _digest(b"reference_output"), "weights": _digest(b"weights"),
            "xsa": "f" * 64,
        }
        self.firmware = "a" * 64
        self.config = self.cloud / "config/e06_physical.json"
        self.config.parent.mkdir()
        self.config.write_text(json.dumps({
            "phase": "E06_PHYSICAL", "model": "E06",
            "network": {"pc_ip": "192.168.10.1", "prefix_length": 24,
                        "board_ip": "192.168.10.2", "tcp_port": 5001},
            "expected_sha256": {
                "firmware_identity": self.firmware,
                **{name: _digest(path.read_bytes()) for name, path in self.files.items()},
            },
        }), encoding="utf-8")
        self.boot_manifest = self.cloud / "boot/BOOT_E06_NET.manifest.json"
        self.boot_manifest.write_text(json.dumps({
            "artifacts": {
                "boot": {"sha256": _digest(b"boot")},
                "app": {"sha256": _digest(b"application_elf")},
            },
            "firmware_identity": {
                "advertised_sha256": self.firmware,
                "canonical_payload": {"inputs": {"copied_vendor_inputs": {
                    name: {"sha256": value} for name, value in self.artifacts.items()
                }}},
            },
        }), encoding="utf-8")
        self.release = self.cloud / "checkpoints/e06_network_release.sha256.json"
        self.release.parent.mkdir()
        # The fixture uses an explicit release marker. Production analysis verifies
        # the actual stable manifest with tree_manifest.
        self.release.write_text(json.dumps({"schema": "fvit-release-manifest-v1",
                                            "files": [], "test_fixture": True}),
                                encoding="utf-8")
        self._write_valid_evidence()

    def _write_valid_evidence(self, phase: str = "E06_PHYSICAL") -> None:
        session = {
            "schema": "fvit-e06-physical-session-v1", "session_id": self.session.name,
            "phase": phase, "model": "E06", "firmware_sha256": self.firmware,
            "artifact_hashes": self.artifacts, "board_ip": "192.168.10.2",
            "tcp_port": 5001,
        }
        (self.session / "session.json").write_text(json.dumps(session), encoding="utf-8")
        uart = ("FVIT_BUILD_PHASE=E06_PHYSICAL\nFVIT_MODEL=E06\n"
                "NETWORK_READY IP=192.168.10.2 PORT=5001\n"
                f"FVIT_FIRMWARE_SHA256={self.firmware}\n"
                f"FVIT_WEIGHTS_SHA256={self.artifacts['weights']}\n"
                "BIT_EXACT_MISMATCHES=0\n")
        (self.session / "uart.log").write_text(uart, encoding="utf-8")
        events = [{"kind": "connection", "state": "connected",
                   "peer_ip": "192.168.10.2", "received_at_ns": 1}]
        request = 1

        def pair(name, response_kind, metadata, *, plan_phase="functional", **extra):
            nonlocal request
            command = {"kind": "command", "request_id": request,
                       "metadata": {"name": name, "arguments": {}},
                       "sent_at_ns": request * 10, "plan_phase": plan_phase, **extra}
            events.append(command)
            events.append({"kind": response_kind, "request_id": request,
                           "metadata": metadata, "received_at_ns": request * 10 + 1,
                           "payload_bytes": 0, "wire_bytes": 20})
            request += 1

        pair("health", "ack", {"model": "E06", "phase": "E06_PHYSICAL", "status": "ok"})
        pair("run_once", "inference_result", {"predicted_class": 1, "mismatch_count": 0,
             "total_ticks": 20, "pl_ticks": 10, "mm2s_ticks": 5, "s2mm_ticks": 5})
        events.append({"kind": "telemetry", "request_id": request - 1,
                       "metadata": {"timestamp_ticks": 1, "power_uW": None,
                                    "temperature_mC": None, "completed_frames": 1,
                                    "sensor_valid": False}, "received_at_ns": 25,
                       "payload_bytes": 0, "wire_bytes": 20})
        pair("telemetry", "telemetry", {"timestamp_ticks": 2, "power_uW": None,
             "temperature_mC": None, "completed_frames": 1, "sensor_valid": False})
        pair("repeat_latency", "ack", {"count": 1, "mm2s_ticks": 5,
             "pl_ticks": 10, "s2mm_ticks": 5, "status": "ok", "total_ticks": 20})
        events[-2]["metadata"]["arguments"] = {"count": 1}
        pair("full_payload", "cloud_frame",
             {"fixture": "E06_FIXED_INPUT", "mode": "full_payload"})
        events[-1]["payload_bytes"] = len(b"input")
        events[-1]["payload_sha256"] = _digest(b"input")
        pair("compact_result", "edge_result", {"predicted_class": 1,
             "mismatch_count": 0, "total_ticks": 20, "pl_ticks": 10,
             "mm2s_ticks": 5, "s2mm_ticks": 5})
        pair("run_once", "inference_result", {"predicted_class": 1,
             "mismatch_count": 0, "total_ticks": 20, "pl_ticks": 10,
             "mm2s_ticks": 5, "s2mm_ticks": 5}, plan_phase="warmup", frame=0)
        events.append({"kind": "telemetry", "request_id": request - 1,
                       "metadata": {"timestamp_ticks": 3, "power_uW": None,
                                    "temperature_mC": None, "completed_frames": 2,
                                    "sensor_valid": False}, "received_at_ns": (request - 1) * 10 + 2,
                       "payload_bytes": 0, "wire_bytes": 20})
        for group in range(10):
            for frame in range(100):
                pair("compact_result", "edge_result", {"predicted_class": 1,
                     "mismatch_count": 0, "total_ticks": 20, "pl_ticks": 10,
                     "mm2s_ticks": 5, "s2mm_ticks": 5},
                     plan_phase="measurement", group=group, frame=frame)
        events.append({"kind": "connection", "state": "disconnected",
                       "received_at_ns": request * 10})
        events.insert(-1, {"kind": "plan_complete", "received_at_ns": request * 10 - 1})
        (self.session / "events.jsonl").write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8")
        # Deliberately wrong: analyzer must ignore/recompute this hand-authored file.
        (self.session / "summary.json").write_text('{"passed":false}', encoding="utf-8")
        capture = {
            "schema": "fvit-e06-physical-capture-v1",
            "evidence_origin": "PHYSICAL_OPERATOR_CAPTURE",
            "real_evidence_acknowledged": True,
            "interface": "enp-test", "uart_device": "/dev/ttyUSB-test",
            "board_ip": "192.168.10.2", "pc_ip": "192.168.10.1",
            "files": {},
        }
        for name, content in {
            "uart.log": uart.encode(), "ip_addr.txt": b"inet 192.168.10.1/24\n",
            "link_state.txt": b"Link detected: yes\n",
            "host_clock.txt": b"2026-09-28T00:00:00.000000Z\n",
        }.items():
            (self.session / name).write_bytes(content)
            capture["files"][name] = _digest(content)
        (self.session / "capture.json").write_text(json.dumps(capture), encoding="utf-8")

    def _analyze(self):
        from Cloud_test.analysis.physical_gate import analyze_gate
        return analyze_gate(self.session, cloud_root=self.cloud,
                            config_path=self.config, boot_manifest_path=self.boot_manifest,
                            release_manifest_path=self.release, allow_test_release=True)

    def test_complete_synthetic_raw_fixture_passes_and_ignores_summary(self):
        result = self._analyze()
        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["measurement"]["groups"], 10)
        self.assertEqual(result["measurement"]["frames_per_group"], 100)
        self.assertEqual(result["measurement"]["dropped_frames"], 0)
        self.assertEqual(result["exact_mismatch_count"], 0)
        self.assertEqual(result["command_count"], 1007)
        self.assertIsNotNone(result["metrics"]["completed_frames_per_second"])
        self.assertIsNotNone(result["metrics"]["total_ticks_mean"])

    def test_reanalysis_is_byte_deterministic(self):
        from Cloud_test.analysis.physical_gate import canonical_gate_bytes
        self.assertEqual(canonical_gate_bytes(self._analyze()),
                         canonical_gate_bytes(self._analyze()))

    def test_missing_tampered_and_host_loopback_evidence_fail(self):
        cases = ("uart_missing", "event_tampered", "payload_tampered",
                 "capture_tampered", "host_loopback")
        for case in cases:
            with self.subTest(case=case):
                self._write_valid_evidence()
                if case == "uart_missing":
                    (self.session / "uart.log").unlink()
                elif case == "event_tampered":
                    text = (self.session / "events.jsonl").read_text(encoding="utf-8")
                    (self.session / "events.jsonl").write_text(
                        text.replace('"mismatch_count": 0', '"mismatch_count": 1', 1),
                        encoding="utf-8")
                elif case == "capture_tampered":
                    (self.session / "link_state.txt").write_text("Link detected: no\n",
                                                                  encoding="utf-8")
                elif case == "payload_tampered":
                    text = (self.session / "events.jsonl").read_text(encoding="utf-8")
                    (self.session / "events.jsonl").write_text(
                        text.replace(_digest(b"input"), "0" * 64, 1), encoding="utf-8")
                else:
                    data = json.loads((self.session / "session.json").read_text())
                    data["phase"] = "HOST_LOOPBACK"
                    (self.session / "session.json").write_text(json.dumps(data), encoding="utf-8")
                result = self._analyze()
                self.assertFalse(result["passed"])
                self.assertEqual(result["status"], "FAIL")
                self.assertTrue(result["failures"])

    def test_adversarial_plan_schema_clock_uart_and_time_tampering_fail(self):
        cases = ("bad_arguments", "bad_request_id", "missing_plan_complete",
                 "bad_typed_ack", "nonmonotonic_time", "valid_sensor_null",
                 "host_clock_tampered", "uart_firmware_missing", "uart_weights_missing")
        for case in cases:
            with self.subTest(case=case):
                self._write_valid_evidence()
                events_path = self.session / "events.jsonl"
                events = [json.loads(line) for line in events_path.read_text().splitlines()]
                if case == "bad_arguments":
                    next(e for e in events if e.get("kind") == "command")["metadata"]["arguments"] = {"x": 1}
                elif case == "bad_request_id":
                    next(e for e in events if e.get("kind") == "command")["request_id"] = 99
                elif case == "missing_plan_complete":
                    events = [e for e in events if e.get("kind") != "plan_complete"]
                elif case == "bad_typed_ack":
                    next(e for e in events if e.get("kind") == "ack")["metadata"]["status"] = "bad"
                elif case == "nonmonotonic_time":
                    next(e for e in events if e.get("kind") == "command")["sent_at_ns"] = -1
                elif case == "valid_sensor_null":
                    telemetry = next(e for e in events if e.get("kind") == "telemetry")
                    telemetry["metadata"]["sensor_valid"] = True
                elif case == "host_clock_tampered":
                    (self.session / "host_clock.txt").write_text("not-a-clock\n")
                else:
                    uart = (self.session / "uart.log").read_text()
                    marker = (f"FVIT_FIRMWARE_SHA256={self.firmware}\n" if case == "uart_firmware_missing"
                              else f"FVIT_WEIGHTS_SHA256={self.artifacts['weights']}\n")
                    uart = uart.replace(marker, "")
                    (self.session / "uart.log").write_text(uart)
                if case not in {"host_clock_tampered", "uart_firmware_missing", "uart_weights_missing"}:
                    events_path.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))
                result = self._analyze()
                self.assertFalse(result["passed"])
                self.assertTrue(result["failures"])

    def test_adversarial_causal_order_reconnect_and_unknown_events_fail(self):
        cases = ("response_before_command", "second_connect", "mid_disconnect",
                 "unknown_event", "duplicate_plan_complete")
        for case in cases:
            with self.subTest(case=case):
                self._write_valid_evidence()
                path = self.session / "events.jsonl"
                events = [json.loads(line) for line in path.read_text().splitlines()]
                # Leave ample integer gaps while preserving the original valid order.
                for event in events:
                    field = "sent_at_ns" if event.get("kind") == "command" else "received_at_ns"
                    event[field] *= 10
                if case == "response_before_command":
                    command_index = next(i for i, e in enumerate(events)
                                         if e.get("kind") == "command")
                    response_index = command_index + 1
                    command = events[command_index]
                    response = events[response_index]
                    old_sent, old_received = command["sent_at_ns"], response["received_at_ns"]
                    response["received_at_ns"], command["sent_at_ns"] = old_sent, old_received
                    events[command_index], events[response_index] = response, command
                elif case in {"second_connect", "mid_disconnect", "unknown_event"}:
                    insert_at = 2
                    timestamp = (events[insert_at - 1].get("received_at_ns")
                                 or events[insert_at - 1].get("sent_at_ns")) + 1
                    if case == "second_connect":
                        extra = {"kind": "connection", "state": "connected",
                                 "peer_ip": "192.168.10.2", "received_at_ns": timestamp}
                    elif case == "mid_disconnect":
                        extra = {"kind": "connection", "state": "disconnected",
                                 "received_at_ns": timestamp}
                    else:
                        extra = {"kind": "hand_authored_claim", "received_at_ns": timestamp}
                    events.insert(insert_at, extra)
                else:
                    index = next(i for i, e in enumerate(events)
                                 if e.get("kind") == "plan_complete")
                    duplicate = dict(events[index])
                    duplicate["received_at_ns"] -= 1
                    events.insert(index, duplicate)
                path.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))
                result = self._analyze()
                self.assertFalse(result["passed"])
                self.assertIn("event_state_machine_mismatch", result["failures"])

    def test_session_path_must_be_contained(self):
        from Cloud_test.analysis.physical_gate import analyze_gate
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        with self.assertRaisesRegex(ValueError, "results/sessions"):
            analyze_gate(outside, cloud_root=self.cloud,
                         config_path=self.config, boot_manifest_path=self.boot_manifest,
                         release_manifest_path=self.release, allow_test_release=True)

    def test_symlinked_sessions_root_is_rejected_before_resolution(self):
        from Cloud_test.analysis.physical_gate import analyze_gate
        other_cloud = Path(self.temporary.name) / "Cloud_link"
        (other_cloud / "results").mkdir(parents=True)
        (other_cloud / "results/sessions").symlink_to(
            self.cloud / "results/sessions", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            analyze_gate(other_cloud / "results/sessions" / self.session.name,
                         cloud_root=other_cloud, config_path=self.config,
                         boot_manifest_path=self.boot_manifest,
                         release_manifest_path=self.release, allow_test_release=True)

    def test_identical_external_evidence_and_manifest_symlinks_are_rejected(self):
        for target_name in ("host_clock.txt", "BOOT_E06_NET.manifest.json"):
            with self.subTest(target_name=target_name):
                self._write_valid_evidence()
                target = (self.session / target_name if target_name == "host_clock.txt"
                          else self.boot_manifest)
                outside = Path(self.temporary.name) / f"external-{target_name}"
                outside.write_bytes(target.read_bytes())
                target.unlink()
                target.symlink_to(outside)
                with self.assertRaisesRegex(ValueError, "symlink|regular file|outside"):
                    self._analyze()
                target.unlink()
                target.write_bytes(outside.read_bytes())


class ReadinessTests(unittest.TestCase):
    def test_default_readiness_is_non_mutating_and_reports_missing_inputs(self):
        from Cloud_test.tools.capture_e06_physical import build_readiness
        with tempfile.TemporaryDirectory() as temporary:
            report = build_readiness(interface="definitely-absent",
                                     uart_device=Path(temporary) / "absent")
        self.assertEqual(report["mode"], "DRY_RUN_READINESS")
        self.assertFalse(report["ready"])
        self.assertIn("network_interface", report["missing_prerequisites"])
        self.assertIn("uart_device", report["missing_prerequisites"])
        self.assertTrue(all("sudo" not in command for command in report["commands_executed"]))

    def test_capture_writer_rejects_broken_symlink_target(self):
        from Cloud_test.tools.capture_e06_physical import _write_capture_files
        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary)
            (session / "host_clock.txt").symlink_to(session / "missing-target")
            with self.assertRaisesRegex((FileExistsError, ValueError), "capture|symlink"):
                _write_capture_files(
                    session, interface="eth-test", uart_device=Path("/dev/null"),
                    clock=b"clock", ip_addr=b"ip", link_state=b"link", uart=b"uart")


if __name__ == "__main__":
    unittest.main()
