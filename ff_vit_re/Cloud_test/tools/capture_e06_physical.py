#!/usr/bin/env python3
"""Readiness checks and explicit, non-configuring E06 evidence capture."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import termios
import threading
import time
import tty
from typing import Sequence


CLOUD_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_symlink_components(path: Path) -> Path:
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlink is forbidden in capture path: {current}")
    return absolute


def build_readiness(*, interface: str, uart_device: Path | str) -> dict[str, object]:
    network_path = Path("/sys/class/net") / interface
    uart = Path(uart_device).expanduser()
    missing = []
    if not network_path.is_dir():
        missing.append("network_interface")
    if not uart.exists() or not uart.is_char_device():
        missing.append("uart_device")
    commands = [
        "date --iso-8601=ns --utc",
        f"ip -4 address show dev {interface}",
        f"ethtool {interface}",
    ]
    return {
        "schema": "fvit-e06-physical-readiness-v1",
        "mode": "DRY_RUN_READINESS",
        "ready": not missing,
        "interface": interface,
        "uart_device": str(uart),
        "missing_prerequisites": missing,
        "commands_executed": [],
        "commands_to_run_during_capture": commands,
        "safety": "No network, firewall, SD-card, or board state was changed.",
    }


def _run_readonly(command: list[str]) -> bytes:
    result = subprocess.run(command, check=False, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise RuntimeError(f"read-only command failed ({result.returncode}): {' '.join(command)}")
    return result.stdout


def _capture_uart(device: Path, duration: float,
                  stop: threading.Event | None = None) -> bytes:
    descriptor = os.open(device, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY)
    chunks: list[bytes] = []
    deadline = time.monotonic() + duration
    original = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor, termios.TCSANOW)
        configured = termios.tcgetattr(descriptor)
        configured[4] = termios.B115200
        configured[5] = termios.B115200
        configured[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)
        configured[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
        if hasattr(termios, "CRTSCTS"):
            configured[2] &= ~termios.CRTSCTS
        termios.tcsetattr(descriptor, termios.TCSANOW, configured)
        while time.monotonic() < deadline and (stop is None or not stop.is_set()):
            remaining = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([descriptor], [], [], min(0.25, remaining))
            if ready:
                data = os.read(descriptor, 65536)
                if data:
                    chunks.append(data)
    finally:
        termios.tcsetattr(descriptor, termios.TCSANOW, original)
        os.close(descriptor)
    return b"".join(chunks)


def _write_capture_files(session: Path, *, interface: str, uart_device: Path,
                         clock: bytes, ip_addr: bytes, link_state: bytes,
                         uart: bytes) -> dict[str, object]:
    session = _reject_symlink_components(session)
    targets = [session / name for name in
               ("host_clock.txt", "ip_addr.txt", "link_state.txt", "uart.log", "capture.json")]
    if any(os.path.lexists(path) for path in targets):
        raise FileExistsError("capture evidence already exists; refusing to overwrite")
    contents = {"host_clock.txt": clock, "ip_addr.txt": ip_addr,
                "link_state.txt": link_state, "uart.log": uart}
    for name, data in contents.items():
        with (session / name).open("xb") as stream:
            stream.write(data)
    capture_record: dict[str, object] = {
        "schema": "fvit-e06-physical-capture-v1",
        "evidence_origin": "PHYSICAL_OPERATOR_CAPTURE",
        "real_evidence_acknowledged": True,
        "interface": interface,
        "uart_device": str(uart_device.resolve()),
        "board_ip": "192.168.10.2",
        "pc_ip": "192.168.10.1",
        "files": {name: _sha256(session / name) for name in contents},
        "commands_executed": ["ip -4 address show dev <interface>",
                              "ethtool <interface>", "read UART device"],
        "state_changes": ["UART configured as 115200 8N1 raw during capture, then restored"],
    }
    with (session / "capture.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(capture_record, indent=2, sort_keys=True) + "\n")
    return capture_record


def capture(session_dir: Path | str, *, interface: str, uart_device: Path | str,
            duration: float, confirm_physical: bool) -> dict[str, object]:
    if not confirm_physical:
        raise ValueError("capture requires --confirm-physical")
    if duration <= 0:
        raise ValueError("duration must be positive")
    lexical_root = _reject_symlink_components(CLOUD_ROOT / "results/sessions")
    lexical_session = _reject_symlink_components(Path(session_dir))
    sessions_root = lexical_root.resolve()
    session = lexical_session.resolve()
    if session.parent != sessions_root or not session.is_dir():
        raise ValueError("session must be an existing direct child of Cloud_test/results/sessions")
    readiness = build_readiness(interface=interface, uart_device=uart_device)
    if not readiness["ready"]:
        raise ValueError("physical interface/UART prerequisites are not ready")
    clock = (datetime.now(timezone.utc).isoformat(timespec="microseconds")
             .replace("+00:00", "Z") + "\n").encode()
    ip_addr = _run_readonly(["ip", "-4", "address", "show", "dev", interface])
    link_state = _run_readonly(["ethtool", interface])
    uart = _capture_uart(Path(uart_device).expanduser(), duration)
    return _write_capture_files(
        session, interface=interface, uart_device=Path(uart_device).expanduser(),
        clock=clock, ip_addr=ip_addr, link_state=link_state, uart=uart,
    )


def run_physical_session(*, interface: str, uart_device: Path | str,
                         timeout: float, confirm_physical: bool) -> Path:
    """Capture boot UART and execute the bounded plan on one collector connection."""
    if not confirm_physical:
        raise ValueError("physical session requires --confirm-physical")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    uart_path = Path(uart_device).expanduser()
    readiness = build_readiness(interface=interface, uart_device=uart_path)
    if not readiness["ready"]:
        raise ValueError("physical interface/UART prerequisites are not ready")

    from Cloud_test.cloud.board_server import BoardCollector
    from Cloud_test.cloud.command_plan import PhysicalCommandPlan
    from Cloud_test.cloud.session_store import SessionStore

    root = _reject_symlink_components(CLOUD_ROOT / "results/sessions").resolve()
    store = SessionStore(root)
    before = {item["session_id"] for item in store.list_sessions()}
    clock = (datetime.now(timezone.utc).isoformat(timespec="microseconds")
             .replace("+00:00", "Z") + "\n").encode()
    ip_addr = _run_readonly(["ip", "-4", "address", "show", "dev", interface])
    link_state = _run_readonly(["ethtool", interface])
    if b"192.168.10.1/24" not in ip_addr or b"Link detected: yes" not in link_state:
        raise ValueError("host IPv4 address or physical link carrier is not ready")

    stop = threading.Event()
    uart_result: dict[str, object] = {}
    collector = BoardCollector(
        ("192.168.10.1", 5001), store, socket_timeout=10.0,
        command_plan=PhysicalCommandPlan.standard(),
    )

    def read_uart() -> None:
        try:
            uart_result["data"] = _capture_uart(uart_path, timeout, stop)
        except BaseException as exc:  # preserved and re-raised in the caller thread
            uart_result["error"] = exc

    thread = threading.Thread(target=read_uart, name="e06-uart-capture", daemon=True)
    thread.start()
    try:
        collector.start()
        print("E06_CAPTURE_READY: power-cycle the ZCU102 now", flush=True)
        completed = collector.wait_for_plan(timeout)
    finally:
        collector.shutdown()
        stop.set()
        thread.join(timeout=5)
    if "error" in uart_result:
        raise RuntimeError("UART capture failed") from uart_result["error"]
    if not completed:
        raise TimeoutError("physical command plan did not complete before timeout")
    after = [item["session_id"] for item in store.list_sessions()
             if item["session_id"] not in before]
    if len(after) != 1:
        raise RuntimeError("expected exactly one new physical session")
    session = root / after[0]
    _write_capture_files(
        session, interface=interface, uart_device=uart_path, clock=clock,
        ip_addr=ip_addr, link_state=link_state,
        uart=uart_result.get("data", b""),  # type: ignore[arg-type]
    )
    return session


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    ready = subparsers.add_parser("readiness", help="safe dry-run checks only")
    ready.add_argument("--interface", required=True)
    ready.add_argument("--uart-device", type=Path, required=True)
    ready.add_argument("--output", type=Path)
    run = subparsers.add_parser("capture", help="explicitly capture real read-only evidence")
    run.add_argument("--session-dir", type=Path, required=True)
    run.add_argument("--interface", required=True)
    run.add_argument("--uart-device", type=Path, required=True)
    run.add_argument("--duration", type=float, default=60.0)
    run.add_argument("--confirm-physical", action="store_true")
    orchestrated = subparsers.add_parser(
        "run", help="capture UART and execute the complete same-connection gate plan")
    orchestrated.add_argument("--interface", required=True)
    orchestrated.add_argument("--uart-device", type=Path, required=True)
    orchestrated.add_argument("--timeout", type=float, default=900.0)
    orchestrated.add_argument("--confirm-physical", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "readiness":
        result = build_readiness(interface=args.interface, uart_device=args.uart_device)
        data = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(data, encoding="utf-8")
        else:
            print(data, end="")
        return 0 if result["ready"] else 2
    if args.action == "capture":
        capture(args.session_dir, interface=args.interface, uart_device=args.uart_device,
                duration=args.duration, confirm_physical=args.confirm_physical)
    else:
        session = run_physical_session(
            interface=args.interface, uart_device=args.uart_device,
            timeout=args.timeout, confirm_physical=args.confirm_physical,
        )
        print(f"E06_PHYSICAL_SESSION={session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
