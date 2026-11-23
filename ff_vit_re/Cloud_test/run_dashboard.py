#!/usr/bin/env python3
"""Serve the local E06 evidence dashboard."""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path
import sys
from typing import Sequence


CLOUD_ROOT = Path(__file__).resolve().parent
if __package__:
    from .cloud.session_store import SessionStore
    from .dashboard.app import create_app
else:
    sys.path.insert(0, str(CLOUD_ROOT.parent))
    from Cloud_test.cloud.session_store import SessionStore
    from Cloud_test.dashboard.app import create_app


DEFAULT_SESSIONS = CLOUD_ROOT / "results/sessions"


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


def _directory(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise argparse.ArgumentTypeError(f"expected a directory path: {value}")
    return path


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=_ipv4, default="127.0.0.1",
                        help="dashboard bind IPv4 address (default: %(default)s)")
    parser.add_argument("--port", type=_port, default=8080,
                        help="dashboard TCP port (default: %(default)s)")
    parser.add_argument("--sessions-dir", type=_directory, default=DEFAULT_SESSIONS,
                        help=f"session evidence directory (default: {DEFAULT_SESSIONS})")
    args = parser.parse_args(argv)
    args.sessions_dir = _directory(str(args.sessions_dir))
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    app = create_app(SessionStore(args.sessions_dir))
    print(f"E06_DASHBOARD=http://{args.host}:{args.port}", flush=True)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
