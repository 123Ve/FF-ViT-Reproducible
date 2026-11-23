"""End-to-end host loopback smoke workflow for the existing E06 artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading

from .artifacts import inspect_artifacts
from .client import send_cloud_frame, send_edge_result
from .metrics import summarize_transfers
from .server import CloudServer


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_loopback_smoke(
    boot_path: Path | str,
    weights_path: Path | str,
    image_path: Path | str,
    output_dir: Path | str,
) -> dict[str, object]:
    boot = Path(boot_path)
    weights = Path(weights_path)
    image = Path(image_path)
    output = Path(output_dir)
    if not image.is_file():
        raise FileNotFoundError(f"missing input image: {image}")
    output.mkdir(parents=True, exist_ok=True)

    artifacts = inspect_artifacts({"boot": boot, "weights": weights})
    _write_json(output / "artifact_manifest.json", artifacts)
    image_bytes = image.read_bytes()
    event_log = output / "events.jsonl"
    event_log.unlink(missing_ok=True)

    server = CloudServer(("127.0.0.1", 0), event_log=event_log, num_classes=38)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        cloud = send_cloud_frame(
            host, port, request_id=1, name=image.name, rgb=image_bytes
        )
        class_id = int(cloud.response.metadata["class_id"])
        edge = send_edge_result(
            host,
            port,
            request_id=2,
            class_id=class_id,
            confidence_q15=32767,
            inference_us=3370,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    transfers = [
        {
            "mode": "cloud",
            "wire_bytes": cloud.wire_bytes,
            "payload_bytes": cloud.payload_bytes,
            "rtt_ms": cloud.rtt_ms,
        },
        {
            "mode": "edge",
            "wire_bytes": edge.wire_bytes,
            "payload_bytes": edge.payload_bytes,
            "rtt_ms": edge.rtt_ms,
        },
    ]
    report: dict[str, object] = {
        "status": "HOST_LOOPBACK_PASS",
        "scope": "host_protocol_only_not_zcu102_ethernet",
        "backend": "checksum_smoke_only_not_plantvillage_inference",
        "artifacts": artifacts,
        "input_image": {
            "path": str(image.resolve()),
            "bytes": len(image_bytes),
            "sha256": hashlib.sha256(image_bytes).hexdigest(),
        },
        "responses": {
            "cloud_class_id": class_id,
            "edge_accepted_class_id": edge.response.metadata["accepted_class_id"],
        },
        "transfers": transfers,
        "metrics": summarize_transfers(transfers),
        "limitations": [
            "The client is a PC-side emulator, not ZCU102 firmware.",
            "The cloud classifier is a checksum smoke backend, not the PlantVillage model.",
            "Power, temperature, and physical Ethernet measurements are not produced.",
        ],
    }
    _write_json(output / "smoke_report.json", report)
    return report
