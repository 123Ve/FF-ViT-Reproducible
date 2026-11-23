"""Append-only evidence store for physical E06 board sessions."""

from __future__ import annotations

from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import re
import threading
import uuid
from typing import Any

from Cloud_test.iot_eval.messages import Hello


_SESSION_ID = re.compile(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}Z-[0-9a-f]{12}\Z")
_ACCURACY_REASON = "E06 model is not PlantVillage"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json_bytes(value: object) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("value must be JSON serializable with finite numbers") from exc


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    data = _json_bytes(value)
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    """Durably sync a rename where directory file descriptors are supported."""
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EPERM, errno.EINVAL, errno.ENOTSUP}:
            return
        raise
    try:
        os.fsync(directory_fd)
    except OSError as exc:
        if exc.errno not in {errno.EACCES, errno.EPERM, errno.EINVAL, errno.ENOTSUP}:
            raise
    finally:
        os.close(directory_fd)


class SessionStore:
    """Thread-safe store whose raw evidence is never rewritten or truncated."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("session root must be a real directory")
        self._lock = threading.RLock()

    def _directory(self, session_id: str) -> Path:
        if not isinstance(session_id, str) or _SESSION_ID.fullmatch(session_id) is None:
            raise ValueError("invalid session id")
        candidate = (self.root / session_id).resolve()
        if candidate.parent != self.root:
            raise ValueError("invalid session id path")
        return candidate

    def begin(self, hello: Hello) -> str:
        if not isinstance(hello, Hello):
            raise ValueError("hello must be a validated Hello")
        if (hello.model, hello.phase) not in {("E06", "E06_PHYSICAL"), ("E07", "E07_PHYSICAL")}:
            raise ValueError("session must match E06/E06_PHYSICAL or E07/E07_PHYSICAL identity")
        with self._lock:
            while True:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                session_id = f"{stamp}-{uuid.uuid4().hex[:12]}"
                directory = self._directory(session_id)
                try:
                    directory.mkdir(mode=0o750)
                    break
                except FileExistsError:
                    continue
            started = _iso_now()
            manifest = {
                "schema": "fvit-e06-physical-session-v1",
                "session_id": session_id,
                "started_at": started,
                "phase": hello.phase,
                "model": hello.model,
                "firmware_sha256": hello.firmware_sha256,
                "artifact_hashes": dict(hello.artifact_hashes),
                "board_ip": hello.board_ip,
                "tcp_port": hello.tcp_port,
            }
            with (directory / "session.json").open("xb") as stream:
                stream.write(_json_bytes(manifest))
                stream.flush()
                os.fsync(stream.fileno())
            with (directory / "events.jsonl").open("xb") as stream:
                stream.flush()
                os.fsync(stream.fileno())
            _atomic_json(directory / "summary.json", self._summarize(manifest, []))
            return session_id

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            raise ValueError("event must be a JSON object")
        stored = dict(event)
        stored.setdefault("stored_at", _iso_now())
        serialized = _json_bytes(stored)
        with self._lock:
            directory = self._directory(session_id)
            manifest = self._load_manifest(directory)
            events_path = directory / "events.jsonl"
            if not events_path.is_file():
                raise KeyError(f"unknown session: {session_id}")
            with events_path.open("ab") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            events = self._load_events(events_path)
            _atomic_json(directory / "summary.json", self._summarize(manifest, events))

    def snapshot(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            directory = self._directory(session_id)
            manifest = self._load_manifest(directory)
            events_path = directory / "events.jsonl"
            if not events_path.is_file():
                raise KeyError(f"unknown session: {session_id}")
            events = self._load_events(events_path)
            summary = self._summarize(manifest, events)
            summary_path = directory / "summary.json"
            try:
                on_disk = json.loads(summary_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError):
                on_disk = None
            if on_disk != summary:
                _atomic_json(summary_path, summary)
            return summary

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            summaries: list[dict[str, Any]] = []
            for directory in self.root.iterdir():
                if not directory.is_dir() or _SESSION_ID.fullmatch(directory.name) is None:
                    continue
                try:
                    summaries.append(self.snapshot(directory.name))
                except (KeyError, ValueError, OSError, json.JSONDecodeError):
                    continue
            summaries.sort(key=lambda item: (item["started_at"], item["session_id"]), reverse=True)
            return summaries

    @staticmethod
    def _load_manifest(directory: Path) -> dict[str, Any]:
        try:
            value = json.loads((directory / "session.json").read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError(f"unknown session: {directory.name}") from exc
        if not isinstance(value, dict) or value.get("session_id") != directory.name:
            raise ValueError("invalid immutable session manifest")
        return value

    @staticmethod
    def _load_events(path: Path) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid event JSON at line {number}") from exc
                if not isinstance(event, dict):
                    raise ValueError(f"event at line {number} is not an object")
                events.append(event)
        return events

    @staticmethod
    def _summarize(manifest: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        measurements = [event for event in events
                        if event.get("kind") in ("inference_result", "edge_result")]
        latencies = [event.get("metadata", {}).get("total_ticks") for event in measurements]
        latencies = [value for value in latencies if type(value) is int and value >= 0]
        sample_times = [event.get("received_at_ns") for event in measurements]
        sample_times = [value for value in sample_times if type(value) is int and value >= 0]
        fps = None
        if len(sample_times) >= 2 and sample_times[-1] > sample_times[0]:
            fps = (len(sample_times) - 1) * 1_000_000_000 / (sample_times[-1] - sample_times[0])

        cloud_bytes = sum(event.get("wire_bytes", 0) for event in events
                          if event.get("kind") == "cloud_frame"
                          and type(event.get("wire_bytes")) is int)
        edge_bytes = sum(event.get("wire_bytes", 0) for event in events
                         if event.get("kind") == "edge_result"
                         and type(event.get("wire_bytes")) is int)
        reduction = None
        full_count = sum(event.get('kind') == 'cloud_frame' for event in events)
        compact_count = sum(event.get('kind') == 'edge_result' for event in events)
        full_per_frame = cloud_bytes / full_count if full_count else None
        compact_per_frame = edge_bytes / compact_count if compact_count else None
        if full_per_frame and compact_per_frame is not None:
            reduction = (1.0 - compact_per_frame / full_per_frame) * 100.0

        telemetry = [event for event in events if event.get("kind") == "telemetry"]
        power_events = [event for event in telemetry
                        if type(event.get("metadata", {}).get("power_uW")) is int
                        and event["metadata"]["power_uW"] >= 0]
        temperature_events = [event for event in telemetry
                              if type(event.get("metadata", {}).get("temperature_mC")) is int
                              and event["metadata"]["temperature_mC"] >= 0]
        powers = [event["metadata"]["power_uW"] for event in power_events]
        temperatures = [event["metadata"]["temperature_mC"] for event in temperature_events]
        energy_uJ: float | None = None
        if len(telemetry) >= 2:
            energy = 0.0
            intervals = 0
            for left, right in zip(telemetry, telemetry[1:]):
                left_ns, right_ns = left.get("received_at_ns"), right.get("received_at_ns")
                left_power = left.get("metadata", {}).get("power_uW")
                right_power = right.get("metadata", {}).get("power_uW")
                if (type(left_power) is int and left_power >= 0
                        and type(right_power) is int and right_power >= 0
                        and type(left_ns) is int and type(right_ns) is int
                        and right_ns >= left_ns):
                    energy += ((left["metadata"]["power_uW"] + right["metadata"]["power_uW"]) / 2
                               * (right_ns - left_ns) / 1_000_000_000)
                    intervals += 1
            if intervals:
                energy_uJ = energy

        errors = [event for event in events if event.get("kind") == "error"]
        connection_state = "not_connected"
        for event in events:
            if event.get("kind") == "connection" and event.get("state") in {
                "connected", "disconnected", "timed_out"
            }:
                connection_state = event["state"]
        completed = [event.get("metadata", {}).get("completed_frames") for event in events
                     if event.get("kind") == "telemetry"]
        completed = [value for value in completed if type(value) is int and value >= 0]
        updated = events[-1].get("stored_at") if events else manifest["started_at"]
        ended = updated if connection_state in {"disconnected", "timed_out"} else None
        mean_latency: float | int | None = None
        if latencies:
            mean_latency = sum(latencies) / len(latencies)
            if float(mean_latency).is_integer():
                mean_latency = int(mean_latency)
        mean_power: float | int | None = None
        if powers:
            mean_power = sum(powers) / len(powers)
            if float(mean_power).is_integer():
                mean_power = int(mean_power)
        latest_telemetry = telemetry[-1].get("metadata", {}) if telemetry else {}
        latest_power = latest_telemetry.get("power_uW")
        if type(latest_power) is not int or latest_power < 0:
            latest_power = None
        latest_temperature = latest_telemetry.get("temperature_mC")
        if type(latest_temperature) is not int or latest_temperature < 0:
            latest_temperature = None
        return {
            **manifest,
            "updated_at": updated,
            "ended_at": ended,
            "connection_state": connection_state,
            "event_count": len(events),
            "sample_count": len(measurements),
            "latest_latency_ticks": latencies[-1] if latencies else None,
            "mean_latency_ticks": mean_latency,
            "fps": fps,
            "completed_frames": completed[-1] if completed else len(measurements),
            "full_payload_wire_bytes": cloud_bytes,
            "compact_result_wire_bytes": edge_bytes,
            "uplink_reduction_percent": reduction,
            "full_upload_frames": full_count,
            "compact_upload_frames": compact_count,
            "full_bytes_per_frame": full_per_frame,
            "compact_bytes_per_frame": compact_per_frame,
            "uplink_reduction_basis": "mean application protocol bytes per frame",
            "valid_power_samples": len(powers),
            "valid_temperature_samples": len(temperatures),
            "latest_power_uW": latest_power,
            "mean_power_uW": mean_power,
            "monitored_energy_uJ": energy_uJ,
            "latest_temperature_mC": latest_temperature,
            "error_count": len(errors),
            "recent_errors": [event.get("metadata", {}) for event in errors[-10:]],
            "accuracy": None,
            "accuracy_reason": f"{manifest['model']} model is not PlantVillage",
        }
