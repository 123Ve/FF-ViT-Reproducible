"""Small framed protocol used by the host emulator and cloud server."""

from __future__ import annotations

from dataclasses import dataclass
import json
import struct
from typing import BinaryIO, Any


MAGIC = b"FVIT"
VERSION = 1
HEADER = struct.Struct("!4sBBHIII")
MAX_METADATA_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024

_KIND_TO_CODE = {
    "cloud_frame": 1,
    "edge_result": 2,
    "cloud_result": 3,
    "ack": 4,
    # Wire codes 5..8 are reserved for the session and measurement messages.
    # Existing assignments, including error=255, are kept for compatibility.
    "hello": 5,
    "telemetry": 6,
    "command": 7,
    "inference_result": 8,
    "error": 255,
}
_CODE_TO_KIND = {value: key for key, value in _KIND_TO_CODE.items()}


class ProtocolError(ValueError):
    """Raised when a peer sends an invalid or unsupported frame."""


@dataclass(frozen=True)
class Message:
    kind: str
    request_id: int
    metadata: dict[str, Any]
    payload: bytes = b""


def _read_exact(stream: BinaryIO, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ProtocolError("unexpected end of stream")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def write_message(stream: BinaryIO, message: Message) -> int:
    try:
        kind_code = _KIND_TO_CODE[message.kind]
    except KeyError as exc:
        raise ProtocolError(f"unknown message kind: {message.kind}") from exc
    if not 0 <= message.request_id <= 0xFFFFFFFF:
        raise ProtocolError("request_id must fit uint32")
    metadata = json.dumps(
        message.metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    payload = bytes(message.payload)
    if len(metadata) > MAX_METADATA_BYTES or len(payload) > MAX_PAYLOAD_BYTES:
        raise ProtocolError("message exceeds protocol size limit")
    header = HEADER.pack(
        MAGIC, VERSION, kind_code, 0, message.request_id, len(metadata), len(payload)
    )
    stream.write(header)
    stream.write(metadata)
    stream.write(payload)
    if hasattr(stream, "flush"):
        stream.flush()
    return len(header) + len(metadata) + len(payload)


def read_message(stream: BinaryIO) -> Message:
    header = _read_exact(stream, HEADER.size)
    magic, version, kind_code, reserved, request_id, metadata_len, payload_len = HEADER.unpack(
        header
    )
    if magic != MAGIC:
        raise ProtocolError("invalid protocol magic")
    if version != VERSION:
        raise ProtocolError(f"unsupported protocol version: {version}")
    if reserved != 0:
        raise ProtocolError("nonzero reserved header bytes")
    if kind_code not in _CODE_TO_KIND:
        raise ProtocolError(f"unknown message kind code: {kind_code}")
    if metadata_len > MAX_METADATA_BYTES or payload_len > MAX_PAYLOAD_BYTES:
        raise ProtocolError("message exceeds protocol size limit")
    try:
        metadata = json.loads(_read_exact(stream, metadata_len).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid metadata JSON") from exc
    if not isinstance(metadata, dict):
        raise ProtocolError("metadata must be a JSON object")
    return Message(
        kind=_CODE_TO_KIND[kind_code],
        request_id=request_id,
        metadata=metadata,
        payload=_read_exact(stream, payload_len),
    )
