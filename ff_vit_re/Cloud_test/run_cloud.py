#!/usr/bin/env python3
"""Run the E06 physical-board TCP collector."""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path
import signal
import sys
import threading
from typing import Sequence


CLOUD_ROOT = Path(__file__).resolve().parent
if __package__:
    from .cloud.board_server import BoardCollector
    from .cloud.command_plan import PhysicalCommandPlan
    from .cloud.session_store import SessionStore
else:
    sys.path.insert(0, str(CLOUD_ROOT.parent))
    from Cloud_test.cloud.board_server import BoardCollector
    from Cloud_test.cloud.command_plan import PhysicalCommandPlan
    from Cloud_test.cloud.session_store import SessionStore


DEFAULT_SESSIONS = CLOUD_ROOT / "results/sessions"
DEFAULT_BOOT_MANIFEST = CLOUD_ROOT / "boot/BOOT_E06_NET.manifest.json"


def _ipv4(value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid IPv4 address: {value}") from exc


def _port(value: str) -> int:
    try:
        port = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be in 1..65535") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be in 1..65535")
    return port


def _existing_file(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"expected an existing file: {value}")
    return path


def _directory(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise argparse.ArgumentTypeError(f"expected a directory path: {value}")
    return path


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=_ipv4, default="192.168.10.1",
                        help="collector bind IPv4 address (default: %(default)s)")
    parser.add_argument("--port", type=_port, default=5001,
                        help="collector TCP port (default: %(default)s)")
    parser.add_argument("--sessions-dir", type=_directory, default=DEFAULT_SESSIONS,
                        help=f"session evidence directory (default: {DEFAULT_SESSIONS})")
    parser.add_argument("--boot-manifest", type=_existing_file,
                        default=DEFAULT_BOOT_MANIFEST,
                        help=f"generated BOOT identity manifest (default: {DEFAULT_BOOT_MANIFEST})")
    parser.add_argument("--socket-timeout", type=float, default=5.0,
                        help="per-connection read timeout in seconds (default: %(default)s)")
    parser.add_argument("--physical-gate-plan", action="store_true",
                        help="send the six functional commands plus warm-up and 10x100 frames")
    args = parser.parse_args(argv)
    if args.socket_timeout <= 0:
        parser.error("socket timeout must be positive")
    # argparse does not run type converters over defaults.
    args.boot_manifest = _existing_file(str(args.boot_manifest))
    args.sessions_dir = _directory(str(args.sessions_dir))
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    store = SessionStore(args.sessions_dir)
    collector = BoardCollector(
        (args.host, args.port), store,
        boot_manifest=args.boot_manifest,
        socket_timeout=args.socket_timeout,
        command_plan=PhysicalCommandPlan.standard() if args.physical_gate_plan else None,
    )
    stopped = threading.Event()

    def request_shutdown(signum: int, frame: object) -> None:
        del signum, frame
        stopped.set()

    previous = {
        sig: signal.signal(sig, request_shutdown)
        for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with collector:
            host, port = collector.bound_address
            print(f"E06_COLLECTOR_LISTENING={host}:{port}", flush=True)
            print(f"E06_SESSION_ROOT={store.root}", flush=True)
            plan_announced = False
            while not stopped.wait(1.0):
                if args.physical_gate_plan and not plan_announced and collector.wait_for_plan(0):
                    print("E06_PHYSICAL_COMMAND_PLAN=COMPLETE", flush=True)
                    plan_announced = True
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print("E06_COLLECTOR_STOPPED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
