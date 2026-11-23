"""Host-side ZCU102 emulator for exercising the cloud transport."""

from __future__ import annotations

from dataclasses import dataclass
import socket
import time

from .protocol import Message, read_message, write_message


@dataclass(frozen=True)
class TransferResult:
    response: Message
    wire_bytes: int
    payload_bytes: int
    rtt_ms: float


def _exchange(host: str, port: int, message: Message, timeout: float) -> TransferResult:
    started = time.perf_counter_ns()
    with socket.create_connection((host, port), timeout=timeout) as connection:
        connection.settimeout(timeout)
        with connection.makefile("rwb", buffering=0) as stream:
            wire_bytes = write_message(stream, message)
            response = read_message(stream)
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
    return TransferResult(response, wire_bytes, len(message.payload), elapsed_ms)


def send_cloud_frame(
    host: str,
    port: int,
    *,
    request_id: int,
    name: str,
    rgb: bytes,
    timeout: float = 5.0,
) -> TransferResult:
    return _exchange(
        host,
        port,
        Message(
            kind="cloud_frame",
            request_id=request_id,
            metadata={"name": name, "encoding": "rgb8"},
            payload=rgb,
        ),
        timeout,
    )


def send_edge_result(
    host: str,
    port: int,
    *,
    request_id: int,
    class_id: int,
    confidence_q15: int,
    inference_us: int,
    timeout: float = 5.0,
) -> TransferResult:
    return _exchange(
        host,
        port,
        Message(
            kind="edge_result",
            request_id=request_id,
            metadata={
                "class_id": class_id,
                "confidence_q15": confidence_q15,
                "inference_us": inference_us,
            },
        ),
        timeout,
    )
