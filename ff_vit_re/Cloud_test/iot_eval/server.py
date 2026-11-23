"""TCP cloud endpoint for the first, host-only E06 workflow test."""

from __future__ import annotations

import json
from pathlib import Path
import socketserver
import threading
import time

from .protocol import Message, ProtocolError, read_message, write_message


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        server: CloudServer = self.server  # type: ignore[assignment]
        started = time.perf_counter_ns()
        try:
            request = read_message(self.rfile)
            if request.kind == "cloud_frame":
                if not request.payload:
                    raise ProtocolError("cloud_frame payload is empty")
                class_id = sum(request.payload) % server.num_classes
                mode = "cloud"
                response = Message(
                    "cloud_result",
                    request.request_id,
                    {
                        "class_id": class_id,
                        "backend": "checksum_smoke_only",
                        "input_bytes": len(request.payload),
                    },
                )
            elif request.kind == "edge_result":
                class_id = int(request.metadata["class_id"])
                if not 0 <= class_id < server.num_classes:
                    raise ProtocolError("edge class_id is out of range")
                mode = "edge"
                response = Message(
                    "ack", request.request_id, {"accepted_class_id": class_id}
                )
            else:
                raise ProtocolError(f"unexpected request kind: {request.kind}")
            server.record_event(
                {
                    "mode": mode,
                    "request_id": request.request_id,
                    "payload_bytes": len(request.payload),
                    "server_processing_ms": (
                        time.perf_counter_ns() - started
                    ) / 1_000_000.0,
                }
            )
        except (ProtocolError, KeyError, TypeError, ValueError) as exc:
            response = Message("error", 0, {"error": str(exc)})
        write_message(self.wfile, response)


class CloudServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        event_log: Path | str,
        num_classes: int,
    ) -> None:
        if num_classes <= 0:
            raise ValueError("num_classes must be positive")
        self.event_log = Path(event_log)
        self.event_log.parent.mkdir(parents=True, exist_ok=True)
        self.num_classes = num_classes
        self._log_lock = threading.Lock()
        super().__init__(server_address, _Handler)

    def record_event(self, event: dict[str, object]) -> None:
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self._log_lock, self.event_log.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
