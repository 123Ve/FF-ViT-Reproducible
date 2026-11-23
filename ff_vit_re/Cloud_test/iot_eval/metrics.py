"""Transfer-level metrics for the host-only cloud workflow smoke test."""

from __future__ import annotations

from statistics import mean
from typing import Iterable, Mapping, Any


def summarize_transfers(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {"cloud": [], "edge": []}
    for record in records:
        mode = record.get("mode")
        if mode not in grouped:
            raise ValueError(f"unknown transfer mode: {mode}")
        grouped[mode].append(record)
    if not grouped["cloud"] or not grouped["edge"]:
        raise ValueError("both cloud and edge transfer records are required")

    summary: dict[str, Any] = {}
    for mode, items in grouped.items():
        summary[mode] = {
            "samples": len(items),
            "mean_wire_bytes": mean(float(item["wire_bytes"]) for item in items),
            "mean_rtt_ms": mean(float(item["rtt_ms"]) for item in items),
        }
    cloud_bytes = summary["cloud"]["mean_wire_bytes"]
    edge_bytes = summary["edge"]["mean_wire_bytes"]
    summary["uplink_reduction_percent"] = (1.0 - edge_bytes / cloud_bytes) * 100.0
    return summary
