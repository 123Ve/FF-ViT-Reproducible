"""Threaded board-facing collector for the E06 physical Ethernet phase."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import socketserver
import threading
import time
from typing import Any

from Cloud_test.iot_eval.messages import Hello, InferenceResult, Telemetry
from Cloud_test.iot_eval.protocol import HEADER, Message, ProtocolError, read_message, write_message

from .session_store import SessionStore
from .command_plan import CommandPlanRunner, PhysicalCommandPlan


DEFAULT_BOOT_MANIFEST = Path(__file__).resolve().parents[1] / "boot" / "BOOT_E06_NET.manifest.json"


def _nonnegative_int(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _wire_bytes(message: Message) -> int:
    metadata = json.dumps(message.metadata, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    return HEADER.size + len(metadata) + len(message.payload)


class _IdentityPolicy:
    def __init__(self, manifest_path: Path | str) -> None:
        self.path = Path(manifest_path).expanduser().resolve()
        try:
            manifest = json.loads(self.path.read_text(encoding="utf-8"))
            self.model = manifest.get("model", "E06")
            self.phase = manifest.get("phase", "E06_PHYSICAL")
            if (self.model, self.phase) not in {("E06", "E06_PHYSICAL"), ("E07", "E07_PHYSICAL")}:
                raise ValueError("unsupported BOOT model/phase")
            identity = manifest["firmware_identity"]
            self.firmware_sha256 = identity["advertised_sha256"]
            copied = identity["canonical_payload"]["inputs"]["copied_vendor_inputs"]
            self.artifact_hashes = {
                name: copied[name]["sha256"]
                for name in ("bitstream", "input", "output", "weights", "xsa")
            }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"invalid BOOT identity manifest: {self.path}") from exc
        digest_values = [self.firmware_sha256, *self.artifact_hashes.values()]
        if any(not isinstance(value, str) or len(value) != 64
               or any(char not in "0123456789abcdef" for char in value)
               for value in digest_values):
            raise ValueError("BOOT identity manifest contains invalid SHA256")

    def validate(self, hello: Hello) -> None:
        if hello.phase != self.phase or hello.model != self.model:
            raise ValueError(f"expected {self.model}/{self.phase} identity")
        if hello.board_ip != "192.168.10.2" or hello.tcp_port != 5001:
            raise ValueError("expected board endpoint 192.168.10.2:5001")
        if hello.firmware_sha256 != self.firmware_sha256:
            raise ValueError("firmware SHA256 does not match current BOOT manifest")
        if hello.artifact_hashes != self.artifact_hashes:
            raise ValueError("artifact hashes do not match current BOOT manifest")


class _CollectorHandler(socketserver.StreamRequestHandler):
    def _send_error(self, code: str, detail: str, request_id: int = 0) -> None:
        try:
            write_message(self.wfile, Message("error", request_id, {
                "code": code, "detail": detail, "phase": "E06_PHYSICAL",
            }))
        except (OSError, ProtocolError):
            pass

    def handle(self) -> None:
        server: _CollectorTCPServer = self.server  # type: ignore[assignment]
        try:
            self.connection.settimeout(server.socket_timeout)
        except OSError:
            return
        session_id: str | None = None
        try:
            while True:
                try:
                    if self.rfile.peek(1) == b"":
                        break
                    message = read_message(self.rfile)
                except socket.timeout:
                    if session_id is not None:
                        server.store.append(session_id, {
                            "kind": "connection", "state": "timed_out",
                            "received_at_ns": time.time_ns(),
                        })
                    return
                except (ProtocolError, OSError, ValueError) as exc:
                    self._send_error("protocol_error", str(exc))
                    if session_id is not None:
                        server.store.append(session_id, {
                            "kind": "error", "request_id": 0,
                            "received_at_ns": time.time_ns(),
                            "metadata": {"code": "protocol_error", "detail": str(exc),
                                         "phase": "E06_PHYSICAL"},
                            "payload_bytes": 0, "wire_bytes": 0,
                        })
                    return

                if session_id is None:
                    if message.kind != "hello":
                        self._send_error("hello_required", "HELLO must be the first message",
                                         message.request_id)
                        return
                    try:
                        hello = Hello.from_message(message)
                        server.identity.validate(hello)
                    except ValueError as exc:
                        self._send_error("identity_mismatch", str(exc), message.request_id)
                        return
                    session_id = server.store.begin(hello)
                    server.store.append(session_id, {
                        "kind": "connection", "state": "connected",
                        "peer_ip": self.client_address[0], "received_at_ns": time.time_ns(),
                    })
                    server.start_command_plan(session_id, self.wfile)
                    continue

                if message.kind == "hello":
                    self._send_error("duplicate_hello", "HELLO is only valid as the first message",
                                     message.request_id)
                    server.store.append(session_id, {
                        "kind": "error", "request_id": message.request_id,
                        "received_at_ns": time.time_ns(),
                        "metadata": {
                            "code": "duplicate_hello",
                            "detail": "HELLO is only valid as the first message",
                            "phase": "E06_PHYSICAL",
                        },
                        "payload_bytes": 0,
                        "wire_bytes": _wire_bytes(message),
                    })
                    return
                try:
                    event = server.validate_event(message)
                except ValueError as exc:
                    self._send_error("invalid_message", str(exc), message.request_id)
                    server.store.append(session_id, {
                        "kind": "error", "request_id": message.request_id,
                        "received_at_ns": time.time_ns(),
                        "metadata": {"code": "invalid_message", "detail": str(exc),
                                     "phase": "E06_PHYSICAL"},
                        "payload_bytes": 0, "wire_bytes": 0,
                    })
                    return
                server.store.append(session_id, event)
                server.accept_plan_response(session_id, message, self.wfile)
        finally:
            if session_id is not None:
                try:
                    current = server.store.snapshot(session_id)
                    if current["connection_state"] not in {"disconnected", "timed_out"}:
                        server.store.append(session_id, {
                            "kind": "connection", "state": "disconnected",
                            "received_at_ns": time.time_ns(),
                        })
                except (KeyError, ValueError, OSError):
                    pass


class _CollectorTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = False
    block_on_close = True

    def __init__(self, address: tuple[str, int], store: SessionStore,
                 identity: _IdentityPolicy, socket_timeout: float,
                 command_plan: PhysicalCommandPlan | None) -> None:
        self.store = store
        self.identity = identity
        self.socket_timeout = socket_timeout
        self.command_plan = command_plan
        self.command_runner: CommandPlanRunner | None = (
            command_plan.new_runner() if command_plan is not None else None
        )
        self.plan_persisted = threading.Event()
        self.plan_lock = threading.Lock()
        self._connections: set[socket.socket] = set()
        self._connections_lock = threading.Lock()
        super().__init__(address, _CollectorHandler)

    def process_request(self, request: socket.socket,
                        client_address: tuple[str, int]) -> None:
        with self._connections_lock:
            self._connections.add(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            with self._connections_lock:
                self._connections.discard(request)
            raise

    def process_request_thread(self, request: socket.socket,
                               client_address: tuple[str, int]) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._connections_lock:
                self._connections.discard(request)

    def close_active_connections(self) -> None:
        with self._connections_lock:
            connections = tuple(self._connections)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass

    def _send_next_command(self, session_id: str, stream: Any) -> None:
        runner = self.command_runner
        if runner is None:
            return
        item = runner.next_command()
        if item is None:
            return
        message, event = item
        event["sent_at_ns"] = time.time_ns()
        self.store.append(session_id, event)
        write_message(stream, message)

    def start_command_plan(self, session_id: str, stream: Any) -> None:
        with self.plan_lock:
            self._send_next_command(session_id, stream)

    def accept_plan_response(self, session_id: str, message: Message, stream: Any) -> None:
        runner = self.command_runner
        if runner is None:
            return
        with self.plan_lock:
            try:
                completed = runner.accept(message)
            except ValueError as exc:
                self.store.append(session_id, {
                    "kind": "error", "request_id": message.request_id,
                    "received_at_ns": time.time_ns(),
                    "metadata": {"code": "command_plan_mismatch", "detail": str(exc),
                                 "phase": "E06_PHYSICAL"},
                    "payload_bytes": 0, "wire_bytes": 0,
                })
                raise
            if completed:
                self.store.append(session_id, {
                    "kind": "plan_complete", "received_at_ns": time.time_ns(),
                })
                self.plan_persisted.set()
            else:
                self._send_next_command(session_id, stream)

    def validate_event(self, message: Message) -> dict[str, Any]:
        if message.kind == "inference_result":
            InferenceResult.from_message(message)
        elif message.kind == "telemetry":
            Telemetry.from_message(message)
        elif message.kind == "edge_result":
            InferenceResult.from_message(Message("inference_result", message.request_id,
                                                 message.metadata, message.payload))
        elif message.kind == "cloud_frame":
            if set(message.metadata) != {"fixture", "mode"} or message.metadata != {
                "fixture": f"{self.identity.model}_FIXED_INPUT", "mode": "full_payload"
            }:
                raise ValueError("cloud_frame metadata does not match frozen E06 schema")
            if not message.payload:
                raise ValueError("cloud_frame payload is empty")
            actual = hashlib.sha256(message.payload).hexdigest()
            if actual != self.identity.artifact_hashes["input"]:
                raise ValueError("cloud_frame payload does not match E06 input identity")
        elif message.kind == "error":
            if message.payload or set(message.metadata) != {"code", "detail", "phase"}:
                raise ValueError("error does not match frozen E06 schema")
            if (not isinstance(message.metadata["code"], str)
                    or not isinstance(message.metadata["detail"], str)
                    or message.metadata["phase"] != self.identity.phase):
                raise ValueError("invalid E06 error metadata")
        elif message.kind == "ack":
            self._validate_ack(message)
        else:
            raise ValueError(f"unexpected board message kind: {message.kind}")
        if message.kind != "cloud_frame" and message.payload:
            raise ValueError(f"{message.kind} must not carry a payload")
        event: dict[str, Any] = {
            "kind": message.kind,
            "request_id": message.request_id,
            "received_at_ns": time.time_ns(),
            "metadata": message.metadata,
            "payload_bytes": len(message.payload),
            "wire_bytes": _wire_bytes(message),
        }
        if message.payload:
            event["payload_sha256"] = hashlib.sha256(message.payload).hexdigest()
        return event

    def _validate_ack(self, message: Message) -> None:
        if message.payload:
            raise ValueError("ack must not carry a payload")
        metadata = message.metadata
        if set(metadata) == {"model", "phase", "status"}:
            if metadata != {"model": self.identity.model, "phase": self.identity.phase, "status": "ok"}:
                raise ValueError("health ack identity is inconsistent")
            return
        expected = {"count", "mm2s_ticks", "pl_ticks", "s2mm_ticks", "status", "total_ticks"}
        if set(metadata) != expected or metadata.get("status") != "ok":
            raise ValueError("ack does not match health or repeat-latency schema")
        count = _nonnegative_int("count", metadata["count"])
        if not 1 <= count <= 16:
            raise ValueError("count must be in 1..16")
        for name in ("mm2s_ticks", "pl_ticks", "s2mm_ticks", "total_ticks"):
            _nonnegative_int(name, metadata[name])


class BoardCollector:
    """Lifecycle wrapper for the board-active TCP collection endpoint."""

    def __init__(self, address: tuple[str, int], store: SessionStore, *,
                 boot_manifest: Path | str = DEFAULT_BOOT_MANIFEST,
                 socket_timeout: float = 5.0,
                 command_plan: PhysicalCommandPlan | None = None) -> None:
        if (not isinstance(address, tuple) or len(address) != 2
                or not isinstance(address[0], str) or type(address[1]) is not int
                or not 0 <= address[1] <= 65535):
            raise ValueError("address must be a (host, port) tuple")
        if not isinstance(store, SessionStore):
            raise ValueError("store must be a SessionStore")
        if not isinstance(socket_timeout, (int, float)) or socket_timeout <= 0:
            raise ValueError("socket_timeout must be positive")
        if command_plan is not None and not isinstance(command_plan, PhysicalCommandPlan):
            raise ValueError("command_plan must be a PhysicalCommandPlan")
        self._server = _CollectorTCPServer(address, store, _IdentityPolicy(boot_manifest),
                                           float(socket_timeout), command_plan)
        self._thread: threading.Thread | None = None

    @property
    def bound_address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("collector is already running")
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        name="e06-board-collector", daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        if self._thread is None:
            self._server.server_close()
            return
        if self._thread.is_alive():
            self._server.shutdown()
            self._thread.join(timeout=5.0)
        self._server.close_active_connections()
        self._server.server_close()
        self._thread = None

    def wait_for_plan(self, timeout: float | None = None) -> bool:
        runner = self._server.command_runner
        if runner is None:
            raise RuntimeError("collector has no physical command plan")
        return self._server.plan_persisted.wait(timeout)

    def __enter__(self) -> "BoardCollector":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.shutdown()
