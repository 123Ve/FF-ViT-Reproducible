"""Bounded command plans for a verified E06 physical board connection."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Iterable

from Cloud_test.iot_eval.messages import Command
from Cloud_test.iot_eval.protocol import Message


@dataclass(frozen=True)
class CommandStep:
    name: str
    arguments: dict[str, object]
    expected_kinds: tuple[str, ...]
    plan_phase: str = "functional"
    group: int | None = None
    frame: int | None = None


def _functional_steps() -> list[CommandStep]:
    return [
        CommandStep("health", {}, ("ack",)),
        CommandStep("run_once", {}, ("inference_result", "telemetry")),
        CommandStep("telemetry", {}, ("telemetry",)),
        CommandStep("repeat_latency", {"count": 1}, ("ack",)),
        CommandStep("full_payload", {}, ("cloud_frame",)),
        CommandStep("compact_result", {}, ("edge_result",)),
    ]


class PhysicalCommandPlan:
    """A finite, immutable sequence; one runner is created per collector run."""

    def __init__(self, steps: Iterable[CommandStep]) -> None:
        self.steps = tuple(steps)
        if not self.steps:
            raise ValueError("physical command plan must not be empty")

    @classmethod
    def functional_only(cls) -> "PhysicalCommandPlan":
        return cls(_functional_steps())

    @classmethod
    def standard(cls, *, warmup_frames: int = 1, groups: int = 10,
                 frames_per_group: int = 100) -> "PhysicalCommandPlan":
        if type(warmup_frames) is not int or warmup_frames < 1:
            raise ValueError("warmup_frames must be a positive integer")
        if type(groups) is not int or groups < 1:
            raise ValueError("groups must be a positive integer")
        if type(frames_per_group) is not int or frames_per_group < 1:
            raise ValueError("frames_per_group must be a positive integer")
        steps = _functional_steps()
        steps.extend(CommandStep("run_once", {}, ("inference_result", "telemetry"),
                                 plan_phase="warmup", frame=frame)
                     for frame in range(warmup_frames))
        steps.extend(
            CommandStep("compact_result", {}, ("edge_result",),
                        plan_phase="measurement", group=group, frame=frame)
            for group in range(groups) for frame in range(frames_per_group)
        )
        return cls(steps)

    def new_runner(self) -> "CommandPlanRunner":
        return CommandPlanRunner(self.steps)


class CommandPlanRunner:
    def __init__(self, steps: tuple[CommandStep, ...]) -> None:
        self._steps = steps
        self._index = 0
        self._expected_index = 0
        self._active_request: int | None = None
        self.complete = threading.Event()
        self.failed = threading.Event()

    def next_command(self) -> tuple[Message, dict[str, object]] | None:
        if self.complete.is_set() or self.failed.is_set() or self._active_request is not None:
            return None
        if self._index == len(self._steps):
            self.complete.set()
            return None
        step = self._steps[self._index]
        request_id = self._index + 1
        self._active_request = request_id
        self._expected_index = 0
        event: dict[str, object] = {
            "kind": "command", "request_id": request_id,
            "metadata": {"name": step.name, "arguments": step.arguments},
            "plan_phase": step.plan_phase,
        }
        if step.group is not None:
            event["group"] = step.group
        if step.frame is not None:
            event["frame"] = step.frame
        return Command(step.name, step.arguments).to_message(request_id), event

    def accept(self, message: Message) -> bool:
        if self._active_request is None or message.request_id != self._active_request:
            self.failed.set()
            raise ValueError("response does not match active physical command request")
        expected = self._steps[self._index].expected_kinds
        if self._expected_index >= len(expected) or message.kind != expected[self._expected_index]:
            self.failed.set()
            raise ValueError("response kind does not match physical command plan")
        self._expected_index += 1
        if self._expected_index == len(expected):
            self._active_request = None
            self._index += 1
            if self._index == len(self._steps):
                self.complete.set()
                return True
        return False

    def mark_failed(self) -> None:
        self.failed.set()
