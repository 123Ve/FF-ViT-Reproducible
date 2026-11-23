"""Decision policy for the W3 QAT 500k continuation."""

from __future__ import annotations

from collections.abc import Sequence


def continuation_action(
    validation_top1: Sequence[float], *, target: float = 70.0,
    minimum_epochs: int = 5, maximum_epochs: int = 8,
) -> str:
    """Apply the approved minimum-five, improving-to-eight stop policy."""
    values = [float(value) for value in validation_top1]
    if len(values) < minimum_epochs:
        return "continue"
    if values[-1] >= target:
        return "target"
    if len(values) >= maximum_epochs:
        return "limit"
    extension_activated = values[minimum_epochs - 1] > values[minimum_epochs - 2]
    return "extend" if extension_activated else "converged"
