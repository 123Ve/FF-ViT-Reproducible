"""Deterministically recompute the E06 physical-board acceptance gate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from Cloud_test.cloud.command_plan import PhysicalCommandPlan
from Cloud_test.iot_eval.messages import InferenceResult, Telemetry
from Cloud_test.iot_eval.protocol import Message
from Cloud_test.tools.tree_manifest import build_release_manifest


EXPECTED_RESPONSES = {
    "health": ("ack",),
    "run_once": ("inference_result", "telemetry"),
    "telemetry": ("telemetry",),
    "repeat_latency": ("ack",),
    "full_payload": ("cloud_frame",),
    "compact_result": ("edge_result",),
}
ARTIFACT_PATHS = {
    "boot": "boot/BOOT_E06_NET.BIN",
    "weights": "vendor/e06_base/data/weights.bin",
    "input": "vendor/e06_base/data/input.bin",
    "reference_output": "vendor/e06_base/data/output.bin",
    "bitstream": "vendor/e06_base/hw/design_1_wrapper.bit",
    "application_elf": "build/e06_net_workspace/e06_net/build/e06_net.elf",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_regular_file(path: Path | str, *, scope: Path, label: str) -> Path:
    """Return an in-scope regular file without following any symlink component."""
    lexical_scope = scope.expanduser().absolute()
    lexical = Path(path).expanduser().absolute()
    try:
        lexical.relative_to(lexical_scope)
    except ValueError as exc:
        raise ValueError(f"{label} is outside allowed scope: {lexical}") from exc
    for candidate in (lexical_scope, lexical):
        current = Path(candidate.anchor)
        for part in candidate.parts[1:]:
            current /= part
            if current.is_symlink():
                raise ValueError(f"symlink is forbidden for {label}: {current}")
    resolved_scope = lexical_scope.resolve()
    resolved = lexical.resolve()
    try:
        resolved.relative_to(resolved_scope)
    except ValueError as exc:
        raise ValueError(f"{label} resolves outside allowed scope: {lexical}") from exc
    if not resolved.is_file() or not os.path.lexists(lexical):
        raise ValueError(f"{label} must be an in-scope regular file: {lexical}")
    return resolved


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def canonical_gate_bytes(result: dict[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def not_run_gate(missing_prerequisites: list[str]) -> dict[str, Any]:
    return {
        "schema": "fvit-e06-physical-gate-v1",
        "status": "NOT_RUN",
        "passed": False,
        "blocker": "BLOCKED_PHYSICAL_INPUT",
        "phase": "E06_PHYSICAL",
        "missing_prerequisites": sorted(set(missing_prerequisites)),
        "failures": [],
        "truth_boundary": (
            "Software/tooling is complete; no physical gate claim exists without "
            "raw ZCU102 UART and TCP evidence."
        ),
    }


def _contained_session(session_dir: Path, cloud_root: Path) -> Path:
    lexical_root = (cloud_root / "results/sessions").expanduser().absolute()
    lexical_candidate = session_dir.expanduser().absolute()
    for path in (lexical_root, lexical_candidate):
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            if current.is_symlink():
                raise ValueError(f"symlink is forbidden in physical evidence path: {current}")
    root = lexical_root.resolve()
    candidate_absolute = session_dir.expanduser().absolute()
    candidate = candidate_absolute.resolve()
    if candidate.parent != root:
        raise ValueError("session must be a direct child of Cloud_test/results/sessions")
    return candidate


def analyze_gate(session_dir: Path | str, *, cloud_root: Path | str,
                 config_path: Path | str, boot_manifest_path: Path | str,
                 release_manifest_path: Path | str,
                 allow_test_release: bool = False) -> dict[str, Any]:
    cloud = Path(cloud_root).expanduser().resolve()
    session_path = _contained_session(Path(session_dir), cloud)
    failures: list[str] = []

    def fail(code: str) -> None:
        if code not in failures:
            failures.append(code)

    required = ["session.json", "events.jsonl", "uart.log", "host_clock.txt", "ip_addr.txt",
                "link_state.txt", "capture.json"]
    evidence_files: dict[str, Path] = {}
    for name in required:
        candidate = session_path / name
        if not os.path.lexists(candidate):
            fail(f"missing:{name}")
        else:
            evidence_files[name] = _safe_regular_file(
                candidate, scope=session_path, label=f"session evidence {name}")
    if failures:
        return _gate_result(session_path.name, failures, {}, [], None)

    config_file = _safe_regular_file(config_path, scope=cloud, label="physical config")
    boot_manifest_file = _safe_regular_file(
        boot_manifest_path, scope=cloud, label="BOOT manifest")
    release_manifest_file = _safe_regular_file(
        release_manifest_path, scope=cloud, label="release manifest")
    try:
        config = _load_object(config_file)
        boot_manifest = _load_object(boot_manifest_file)
        release_manifest = _load_object(release_manifest_file)
        session = _load_object(evidence_files["session.json"])
        capture = _load_object(evidence_files["capture.json"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return _gate_result(session_path.name, [f"invalid_metadata:{type(exc).__name__}"],
                            {}, [], None)

    if (not allow_test_release or not release_manifest.get("test_fixture")):
        try:
            if release_manifest != build_release_manifest(cloud):
                fail("release_manifest_mismatch")
        except (OSError, ValueError):
            fail("release_manifest_invalid")

    expected = config.get("expected_sha256", {})
    for name, relative in ARTIFACT_PATHS.items():
        try:
            path = _safe_regular_file(cloud / relative, scope=cloud,
                                      label=f"release artifact {name}")
            actual = _sha256(path)
        except (OSError, ValueError):
            fail(f"artifact_missing:{name}")
            continue
        if expected.get(name) != actual:
            fail(f"artifact_hash_mismatch:{name}")

    network = config.get("network", {})
    if config.get("phase") != "E06_PHYSICAL" or config.get("model") != "E06":
        fail("invalid_config_identity")
    if session.get("phase") != "E06_PHYSICAL":
        fail("phase_not_physical")
    if session.get("model") != "E06":
        fail("model_identity_mismatch")
    if session.get("board_ip") != network.get("board_ip") or session.get("tcp_port") != network.get("tcp_port"):
        fail("board_endpoint_mismatch")
    firmware = expected.get("firmware_identity")
    if session.get("firmware_sha256") != firmware:
        fail("firmware_identity_mismatch")
    identity = boot_manifest.get("firmware_identity", {})
    if identity.get("advertised_sha256") != firmware:
        fail("boot_manifest_firmware_mismatch")
    copied = identity.get("canonical_payload", {}).get("inputs", {}).get(
        "copied_vendor_inputs", {})
    session_artifacts = session.get("artifact_hashes")
    for name in ("bitstream", "input", "output", "weights", "xsa"):
        expected_hash = (copied.get(name, {}).get("sha256") if name == "xsa" else
                         expected.get("reference_output" if name == "output" else name))
        if copied.get(name, {}).get("sha256") != expected_hash:
            fail(f"boot_manifest_artifact_mismatch:{name}")
        if not isinstance(session_artifacts, dict) or session_artifacts.get(name) != expected_hash:
            fail(f"session_artifact_mismatch:{name}")
    if boot_manifest.get("artifacts", {}).get("boot", {}).get("sha256") != expected.get("boot"):
        fail("boot_manifest_boot_mismatch")
    if boot_manifest.get("artifacts", {}).get("app", {}).get("sha256") != expected.get("application_elf"):
        fail("boot_manifest_application_mismatch")

    if (capture.get("schema") != "fvit-e06-physical-capture-v1"
            or capture.get("evidence_origin") != "PHYSICAL_OPERATOR_CAPTURE"
            or capture.get("real_evidence_acknowledged") is not True):
        fail("capture_not_physical")
    if capture.get("board_ip") != network.get("board_ip") or capture.get("pc_ip") != network.get("pc_ip"):
        fail("capture_network_identity_mismatch")
    capture_files = capture.get("files")
    for name in ("uart.log", "host_clock.txt", "ip_addr.txt", "link_state.txt"):
        try:
            actual = _sha256(evidence_files[name])
        except OSError:
            continue
        if not isinstance(capture_files, dict) or capture_files.get(name) != actual:
            fail(f"capture_hash_mismatch:{name}")

    try:
        uart = evidence_files["uart.log"].read_text(encoding="utf-8", errors="strict")
        host_clock = evidence_files["host_clock.txt"].read_text(encoding="utf-8", errors="strict")
        ip_addr = evidence_files["ip_addr.txt"].read_text(encoding="utf-8", errors="strict")
        link = evidence_files["link_state.txt"].read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        uart = host_clock = ip_addr = link = ""
        fail("capture_text_unreadable")
    for marker in ("FVIT_BUILD_PHASE=E06_PHYSICAL", "FVIT_MODEL=E06",
                   f"NETWORK_READY IP={network.get('board_ip')} PORT={network.get('tcp_port')}"):
        if marker not in uart:
            fail(f"uart_marker_missing:{marker.split('=')[0]}")
    for marker, code in (
        (f"FVIT_FIRMWARE_SHA256={firmware}", "uart_firmware_identity_missing"),
        (f"FVIT_WEIGHTS_SHA256={expected.get('weights')}", "uart_weights_identity_missing"),
    ):
        if marker not in uart:
            fail(code)
    if "BIT_EXACT_MISMATCHES=" in uart and "BIT_EXACT_MISMATCHES=0" not in uart:
        fail("uart_bit_exact_mismatch")
    if f"inet {network.get('pc_ip')}/{network.get('prefix_length')}" not in ip_addr:
        fail("pc_ipv4_evidence_missing")
    if "Link detected: yes" not in link:
        fail("link_carrier_not_detected")
    try:
        from datetime import datetime
        parsed_clock = datetime.fromisoformat(host_clock.strip().replace("Z", "+00:00"))
        if parsed_clock.tzinfo is None or parsed_clock.utcoffset() is None:
            raise ValueError
    except ValueError:
        fail("host_clock_invalid")

    events: list[dict[str, Any]] = []
    try:
        for line in evidence_files["events.jsonl"].read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError
            events.append(event)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        fail("events_invalid")
        events = []

    connected = [event for event in events if event.get("kind") == "connection"
                 and event.get("state") == "connected"
                 and event.get("peer_ip") == network.get("board_ip")]
    if not connected:
        fail("physical_tcp_connection_missing")
    if any(event.get("kind") == "error" for event in events):
        fail("board_or_protocol_error")

    commands = [event for event in events if event.get("kind") == "command"]
    responses: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("kind") in {"ack", "inference_result", "telemetry",
                                 "cloud_frame", "edge_result"}:
            request_id = event.get("request_id")
            if type(request_id) is int:
                responses.setdefault(request_id, []).append(event)

    event_times: list[int] = []
    for event in events:
        field = "sent_at_ns" if event.get("kind") == "command" else "received_at_ns"
        value = event.get(field)
        if type(value) is not int or value < 0:
            fail("event_timestamp_invalid")
            break
        event_times.append(value)
    if event_times and any(current <= previous
                           for previous, current in zip(event_times, event_times[1:])):
        fail("event_timestamps_not_strictly_monotonic")

    expected_steps = PhysicalCommandPlan.standard().steps
    if len(commands) != len(expected_steps):
        fail("command_plan_length_mismatch")
    for index, (command, step) in enumerate(zip(commands, expected_steps), start=1):
        expected_event = {
            "request_id": index, "name": step.name, "arguments": step.arguments,
            "plan_phase": step.plan_phase, "group": step.group, "frame": step.frame,
        }
        metadata = command.get("metadata")
        actual = {
            "request_id": command.get("request_id"),
            "name": metadata.get("name") if isinstance(metadata, dict) else None,
            "arguments": metadata.get("arguments") if isinstance(metadata, dict) else None,
            "plan_phase": command.get("plan_phase"),
            "group": command.get("group"), "frame": command.get("frame"),
        }
        if actual != expected_event or (isinstance(metadata, dict)
                                        and set(metadata) != {"name", "arguments"}):
            fail(f"command_plan_mismatch:{index}")
            break
    plan_complete = [event for event in events if event.get("kind") == "plan_complete"]
    if len(plan_complete) != 1:
        fail("plan_complete_count_mismatch")
    else:
        trailing = events[events.index(plan_complete[0]) + 1:]
        if any(event.get("kind") != "connection"
               or event.get("state") not in {"disconnected", "timed_out"}
               for event in trailing):
            fail("plan_complete_not_terminal")

    cursor = 0
    state_valid = True
    if (not events or events[0].get("kind") != "connection"
            or events[0].get("state") != "connected"
            or events[0].get("peer_ip") != network.get("board_ip")):
        state_valid = False
    else:
        cursor = 1
    if state_valid:
        for request_id, step in enumerate(expected_steps, start=1):
            if cursor >= len(events):
                state_valid = False
                break
            command_event = events[cursor]
            metadata = command_event.get("metadata")
            if (command_event.get("kind") != "command"
                    or command_event.get("request_id") != request_id
                    or not isinstance(metadata, dict)
                    or metadata != {"name": step.name, "arguments": step.arguments}):
                state_valid = False
                break
            cursor += 1
            for response_kind in step.expected_kinds:
                if (cursor >= len(events) or events[cursor].get("kind") != response_kind
                        or events[cursor].get("request_id") != request_id):
                    state_valid = False
                    break
                cursor += 1
            if not state_valid:
                break
    if state_valid:
        if cursor >= len(events) or events[cursor].get("kind") != "plan_complete":
            state_valid = False
        else:
            cursor += 1
    if state_valid and cursor < len(events):
        if (cursor + 1 != len(events) or events[cursor].get("kind") != "connection"
                or events[cursor].get("state") not in {"disconnected", "timed_out"}):
            state_valid = False
        else:
            cursor += 1
    if not state_valid or cursor != len(events):
        fail("event_state_machine_mismatch")

    full_payload_events = [event for event in events if event.get("kind") == "cloud_frame"]
    input_path = cloud / ARTIFACT_PATHS["input"]
    try:
        input_bytes = input_path.stat().st_size
    except OSError:
        input_bytes = None
    if len(full_payload_events) != 1:
        fail("full_payload_response_count_mismatch")
    elif (full_payload_events[0].get("payload_sha256") != expected.get("input")
          or full_payload_events[0].get("payload_bytes") != input_bytes):
        fail("full_payload_identity_mismatch")

    for command in commands:
        metadata = command.get("metadata")
        name = metadata.get("name") if isinstance(metadata, dict) else None
        request_id = command.get("request_id")
        expected_kinds = EXPECTED_RESPONSES.get(name)
        if expected_kinds is None:
            fail("unknown_command_in_evidence")
            continue
        actual_kinds = tuple(event.get("kind") for event in responses.pop(request_id, []))
        if actual_kinds != expected_kinds:
            fail(f"request_response_mismatch:{request_id}")
    if responses:
        fail("orphan_responses")

    for event in events:
        kind = event.get("kind")
        if kind not in {"ack", "inference_result", "telemetry", "cloud_frame", "edge_result"}:
            continue
        metadata = event.get("metadata")
        request_id = event.get("request_id")
        if (not isinstance(metadata, dict) or type(request_id) is not int
                or type(event.get("payload_bytes")) is not int
                or type(event.get("wire_bytes")) is not int
                or event["payload_bytes"] < 0 or event["wire_bytes"] < 0):
            fail(f"typed_response_envelope_invalid:{request_id}")
            continue
        try:
            if kind in {"inference_result", "edge_result"}:
                InferenceResult.from_message(Message("inference_result", request_id, metadata))
            elif kind == "telemetry":
                Telemetry.from_message(Message("telemetry", request_id, metadata))
            elif kind == "ack":
                command_name = next(
                    (item.get("metadata", {}).get("name") for item in commands
                     if item.get("request_id") == request_id), None)
                if command_name == "health":
                    if metadata != {"model": "E06", "phase": "E06_PHYSICAL", "status": "ok"}:
                        raise ValueError
                elif command_name == "repeat_latency":
                    if (set(metadata) != {"count", "mm2s_ticks", "pl_ticks", "s2mm_ticks",
                                         "status", "total_ticks"}
                            or metadata.get("count") != 1 or metadata.get("status") != "ok"
                            or any(type(metadata.get(name)) is not int or metadata[name] < 0
                                   for name in ("mm2s_ticks", "pl_ticks", "s2mm_ticks",
                                                "total_ticks"))):
                        raise ValueError
                else:
                    raise ValueError
            elif kind == "cloud_frame":
                if metadata != {"fixture": "E06_FIXED_INPUT", "mode": "full_payload"}:
                    raise ValueError
        except ValueError:
            fail(f"typed_response_schema_invalid:{request_id}")
    names = {event.get("metadata", {}).get("name") for event in commands
             if isinstance(event.get("metadata"), dict)}
    for name in EXPECTED_RESPONSES:
        if name not in names:
            fail(f"command_missing:{name}")

    mismatch_total = 0
    for event in events:
        if event.get("kind") in {"inference_result", "edge_result"}:
            value = event.get("metadata", {}).get("mismatch_count")
            if type(value) is not int or value < 0:
                fail("invalid_mismatch_count")
            else:
                mismatch_total += value
    if mismatch_total != 0:
        fail("bit_exact_mismatch_nonzero")

    telemetry = [event for event in events if event.get("kind") == "telemetry"]
    if not telemetry:
        fail("telemetry_response_missing")
    for event in telemetry:
        metadata = event.get("metadata", {})
        valid = metadata.get("sensor_valid")
        if type(valid) is not bool:
            fail("telemetry_availability_invalid")
        elif not valid and not (metadata.get("power_uW") is None
                                and metadata.get("temperature_mC") is None):
            fail("telemetry_unavailable_not_explicit")

    warmups = [event for event in commands if event.get("plan_phase") == "warmup"]
    measurements = [event for event in commands if event.get("plan_phase") == "measurement"]
    expected_coordinates = {(group, frame) for group in range(10) for frame in range(100)}
    actual_coordinates = {(event.get("group"), event.get("frame")) for event in measurements}
    if not warmups:
        fail("warmup_missing")
    if actual_coordinates != expected_coordinates or len(measurements) != 1000:
        fail("bounded_measurement_dimensions_mismatch")
    dropped = sum(1 for failure in failures if failure.startswith("request_response_mismatch:"))

    measurement = {
        "groups": 10,
        "frames_per_group": 100,
        "requested_frames": len(measurements),
        "warmup_frames": len(warmups),
        "dropped_frames": dropped,
    }
    inference_events = [event for event in events
                        if event.get("kind") in {"inference_result", "edge_result"}]
    tick_values = [event.get("metadata", {}).get("total_ticks")
                   for event in inference_events]
    valid_ticks = [value for value in tick_values if type(value) is int and value >= 0]
    measurement_responses = [event for event in events if event.get("kind") == "edge_result"
                             and any(command.get("request_id") == event.get("request_id")
                                     and command.get("plan_phase") == "measurement"
                                     for command in measurements)]
    response_times = [event.get("received_at_ns") for event in measurement_responses
                      if type(event.get("received_at_ns")) is int]
    elapsed_ns = (max(response_times) - min(response_times)) if len(response_times) > 1 else None
    completed_fps = ((len(measurement_responses) - 1) * 1_000_000_000 / elapsed_ns
                     if elapsed_ns and elapsed_ns > 0 else None)
    metrics = {
        "physical_tcp_connections": len(connected),
        "inference_responses": len(inference_events),
        "telemetry_responses": len(telemetry),
        "valid_power_samples": sum(
            event.get("metadata", {}).get("power_uW") is not None for event in telemetry),
        "valid_temperature_samples": sum(
            event.get("metadata", {}).get("temperature_mC") is not None for event in telemetry),
        "sensor_unavailable_samples": sum(
            event.get("metadata", {}).get("sensor_valid") is False for event in telemetry),
        "total_ticks_min": min(valid_ticks) if valid_ticks else None,
        "total_ticks_max": max(valid_ticks) if valid_ticks else None,
        "total_ticks_mean": (sum(valid_ticks) / len(valid_ticks)) if valid_ticks else None,
        "measurement_elapsed_ns": elapsed_ns,
        "completed_frames_per_second": completed_fps,
        "full_payload_wire_bytes": sum(event.get("wire_bytes", 0)
                                       for event in full_payload_events
                                       if type(event.get("wire_bytes", 0)) is int),
        "compact_result_wire_bytes": sum(
            event.get("wire_bytes", 0) for event in measurement_responses
            if type(event.get("wire_bytes", 0)) is int),
    }
    hashes = {
        "session_json": _sha256(evidence_files["session.json"]),
        "events_jsonl": _sha256(evidence_files["events.jsonl"]),
        "uart_log": _sha256(evidence_files["uart.log"]),
        "host_clock": _sha256(evidence_files["host_clock.txt"]),
        "capture_json": _sha256(evidence_files["capture.json"]),
        "boot_manifest": _sha256(boot_manifest_file),
        "release_manifest": _sha256(release_manifest_file),
    }
    return _gate_result(session_path.name, failures, measurement, commands,
                        mismatch_total, hashes=hashes, metrics=metrics,
                        validated_identity={
                            "firmware_sha256": firmware,
                            "artifact_sha256": session_artifacts,
                            "boot_sha256": expected.get("boot"),
                            "application_elf_sha256": expected.get("application_elf"),
                        })


def _gate_result(session_id: str, failures: list[str], measurement: dict[str, Any],
                 commands: list[dict[str, Any]], mismatch: int | None,
                 *, hashes: dict[str, Any] | None = None,
                 metrics: dict[str, Any] | None = None,
                 validated_identity: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": "fvit-e06-physical-gate-v1",
        "status": "PASS" if not failures else "FAIL",
        "passed": not failures,
        "phase": "E06_PHYSICAL",
        "session_id": session_id,
        "failures": sorted(failures),
        "exact_mismatch_count": mismatch,
        "command_count": len(commands),
        "measurement": measurement,
        "metrics": metrics or {},
        "validated_identity": validated_identity or {},
        "evidence_sha256": hashes or {},
        "accuracy": None,
        "accuracy_reason": "E06 model is not PlantVillage",
    }
