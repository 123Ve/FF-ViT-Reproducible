"""Validated metadata messages shared by physical boards and host collectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import ipaddress
import json
import re
from typing import Self

from .protocol import Message


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PHASES = frozenset({"HOST_LOOPBACK", "E06_PHYSICAL", "E07_PHYSICAL", "PLANT_PHYSICAL"})


def _require_nonnegative_int(name: str, value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def _require_sha256(name: str, value: object) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA256 hex string")


def _require_json_object(name: str, value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a JSON object") from exc

    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            if any(not isinstance(key, str) for key in current):
                raise ValueError(f"{name} must have string keys")
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
        elif current is None or type(current) in (str, int, float, bool):
            pass
        else:
            raise ValueError(f"{name} contains a non-JSON value")


def _from_message(cls: type[Self], message: Message, kind: str) -> Self:
    if message.kind != kind:
        raise ValueError(f"expected {kind} message")
    if message.payload:
        raise ValueError(f"{kind} message must have no payload")
    expected = {field.name for field in fields(cls)}
    if not isinstance(message.metadata, dict) or set(message.metadata) != expected:
        raise ValueError(f"{kind} message has missing or unexpected fields")
    return cls(**message.metadata)


@dataclass(frozen=True)
class Hello:
    phase: str
    model: str
    firmware_sha256: str
    artifact_hashes: dict[str, str]
    board_ip: str
    tcp_port: int

    def __post_init__(self) -> None:
        if not isinstance(self.phase, str) or self.phase not in _PHASES:
            raise ValueError("invalid phase")
        if not isinstance(self.model, str) or not self.model:
            raise ValueError("model must be a nonempty string")
        _require_sha256("firmware_sha256", self.firmware_sha256)
        if not isinstance(self.artifact_hashes, dict) or not self.artifact_hashes:
            raise ValueError("artifact_hashes must be a nonempty object")
        for name, digest in self.artifact_hashes.items():
            if not isinstance(name, str) or not name:
                raise ValueError("artifact_hashes keys must be nonempty strings")
            _require_sha256(f"artifact_hashes[{name}]", digest)
        try:
            if not isinstance(self.board_ip, str):
                raise ValueError("board_ip must be IPv4")
            ipaddress.IPv4Address(self.board_ip)
        except ipaddress.AddressValueError as exc:
            raise ValueError("board_ip must be IPv4") from exc
        if type(self.tcp_port) is not int or not 1 <= self.tcp_port <= 65535:
            raise ValueError("tcp_port must be in 1..65535")

    def to_message(self, request_id: int) -> Message:
        return Message("hello", request_id, asdict(self))

    @classmethod
    def from_message(cls, message: Message) -> Self:
        return _from_message(cls, message, "hello")


@dataclass(frozen=True)
class Telemetry:
    timestamp_ticks: int
    power_uW: int | None
    temperature_mC: int | None
    completed_frames: int
    sensor_valid: bool

    def __post_init__(self) -> None:
        _require_nonnegative_int("timestamp_ticks", self.timestamp_ticks)
        _require_nonnegative_int("completed_frames", self.completed_frames)
        if type(self.sensor_valid) is not bool:
            raise ValueError("sensor_valid must be boolean")
        for name in ("power_uW", "temperature_mC"):
            value = getattr(self, name)
            if value is None:
                if self.sensor_valid:
                    raise ValueError(f"{name} required when sensor_valid is true")
            else:
                _require_nonnegative_int(name, value)

    def to_message(self, request_id: int) -> Message:
        return Message("telemetry", request_id, asdict(self))

    @classmethod
    def from_message(cls, message: Message) -> Self:
        return _from_message(cls, message, "telemetry")


@dataclass(frozen=True)
class Command:
    name: str
    arguments: dict[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a nonempty string")
        _require_json_object("arguments", self.arguments)

    def to_message(self, request_id: int) -> Message:
        return Message("command", request_id, asdict(self))

    @classmethod
    def from_message(cls, message: Message) -> Self:
        return _from_message(cls, message, "command")


@dataclass(frozen=True)
class InferenceResult:
    predicted_class: int
    mismatch_count: int
    total_ticks: int
    pl_ticks: int
    mm2s_ticks: int
    s2mm_ticks: int

    def __post_init__(self) -> None:
        for field in fields(self):
            _require_nonnegative_int(field.name, getattr(self, field.name))

    def to_message(self, request_id: int) -> Message:
        return Message("inference_result", request_id, asdict(self))

    @classmethod
    def from_message(cls, message: Message) -> Self:
        return _from_message(cls, message, "inference_result")
