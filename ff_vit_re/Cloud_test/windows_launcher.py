#!/usr/bin/env python3
"""Start the E06 board collector and local dashboard as one application."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import ipaddress
import math
from pathlib import Path
import signal
import sys
import threading
from typing import Sequence
import webbrowser

from werkzeug.serving import BaseWSGIServer, make_server

from Cloud_test.cloud.board_server import BoardCollector
from Cloud_test.cloud.command_plan import PhysicalCommandPlan
from Cloud_test.cloud.session_store import SessionStore
from Cloud_test.dashboard.app import create_app


@dataclass(frozen=True)
class RuntimePaths:
    sessions_dir: Path
    boot_manifest: Path


def resolve_runtime_paths(*, frozen: bool | None = None,
                          executable: Path | None = None,
                          bundle_root: Path | None = None) -> RuntimePaths:
    """Resolve writable evidence and read-only bundled resource paths."""
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    executable_path = Path(sys.executable if executable is None else executable).resolve()
    if is_frozen:
        resource_root = Path(
            getattr(sys, "_MEIPASS", executable_path.parent)
            if bundle_root is None else bundle_root
        ).resolve()
        writable_root = executable_path.parent
    else:
        resource_root = Path(__file__).resolve().parent.parent
        writable_root = Path(__file__).resolve().parent
    return RuntimePaths(
        sessions_dir=writable_root / "results/sessions",
        boot_manifest=resource_root / "Cloud_test/boot/BOOT_E06_NET.manifest.json",
    )


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


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be positive") from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _existing_file(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"expected an existing file: {value}")
    return path


def _directory(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise argparse.ArgumentTypeError(f"expected a directory path: {value}")
    return path


def _arguments(argv: Sequence[str] | None = None,
               paths: RuntimePaths | None = None) -> argparse.Namespace:
    defaults = resolve_runtime_paths() if paths is None else paths
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collector-host", type=_ipv4, default="192.168.10.1")
    parser.add_argument("--collector-port", type=_port, default=5001)
    parser.add_argument("--gui-host", type=_ipv4, default="127.0.0.1")
    parser.add_argument("--gui-port", type=_port, default=8080)
    parser.add_argument("--sessions-dir", type=_directory, default=defaults.sessions_dir)
    parser.add_argument("--boot-manifest", type=_existing_file,
                        default=defaults.boot_manifest)
    parser.add_argument("--socket-timeout", type=_positive_float, default=5.0)
    parser.add_argument("--physical-gate-plan", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    # argparse does not apply type converters to defaults.
    args.sessions_dir = _directory(args.sessions_dir)
    args.boot_manifest = _existing_file(args.boot_manifest)
    return args


class CloudGuiRuntime:
    """Own the collector and dashboard lifecycle as a single unit."""

    def __init__(self, *, collector_address: tuple[str, int],
                 dashboard_address: tuple[str, int], sessions_dir: Path,
                 boot_manifest: Path, socket_timeout: float,
                 physical_gate_plan: bool = False) -> None:
        self._requested_collector = collector_address
        self._requested_dashboard = dashboard_address
        self._sessions_dir = Path(sessions_dir)
        self._boot_manifest = Path(boot_manifest)
        self._socket_timeout = socket_timeout
        self._physical_gate_plan = physical_gate_plan
        self._collector: BoardCollector | None = None
        self._dashboard: BaseWSGIServer | None = None
        self._dashboard_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def collector_address(self) -> tuple[str, int]:
        if self._collector is None:
            raise RuntimeError("runtime is not started")
        return self._collector.bound_address

    @property
    def dashboard_address(self) -> tuple[str, int]:
        if self._dashboard is None:
            raise RuntimeError("runtime is not started")
        return str(self._dashboard.host), int(self._dashboard.port)

    def start(self) -> None:
        if self._running:
            raise RuntimeError("runtime is already running")
        self._stop.clear()
        store = SessionStore(self._sessions_dir)
        collector = BoardCollector(
            self._requested_collector,
            store,
            boot_manifest=self._boot_manifest,
            socket_timeout=self._socket_timeout,
            command_plan=(PhysicalCommandPlan.standard()
                          if self._physical_gate_plan else None),
        )
        dashboard: BaseWSGIServer | None = None
        try:
            dashboard = make_server(
                self._requested_dashboard[0],
                self._requested_dashboard[1],
                create_app(store),
                threaded=True,
            )
            collector.start()
            dashboard_thread = threading.Thread(
                target=dashboard.serve_forever,
                name="e06-dashboard",
                daemon=True,
            )
            dashboard_thread.start()
        except BaseException:
            if dashboard is not None:
                dashboard.server_close()
            collector.shutdown()
            raise
        self._collector = collector
        self._dashboard = dashboard
        self._dashboard_thread = dashboard_thread
        self._running = True

    def wait(self) -> None:
        if not self._running:
            raise RuntimeError("runtime is not started")
        self._stop.wait()

    def request_stop(self) -> None:
        self._stop.set()

    def stop(self) -> None:
        if not self._running:
            return
        self._stop.set()
        dashboard = self._dashboard
        thread = self._dashboard_thread
        collector = self._collector
        if dashboard is not None:
            dashboard.shutdown()
        if thread is not None:
            thread.join(timeout=5.0)
        if dashboard is not None:
            dashboard.server_close()
        if collector is not None:
            collector.shutdown()
        self._dashboard = None
        self._dashboard_thread = None
        self._collector = None
        self._running = False


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _arguments(argv)
        runtime = CloudGuiRuntime(
            collector_address=(args.collector_host, args.collector_port),
            dashboard_address=(args.gui_host, args.gui_port),
            sessions_dir=args.sessions_dir,
            boot_manifest=args.boot_manifest,
            socket_timeout=args.socket_timeout,
            physical_gate_plan=args.physical_gate_plan,
        )
        runtime.start()
    except (OSError, ValueError) as exc:
        print(f"E06_STARTUP_ERROR={exc}", file=sys.stderr, flush=True)
        return 2

    def stop_handler(signum: int, frame: object) -> None:
        del signum, frame
        runtime.request_stop()

    previous = {
        sig: signal.signal(sig, stop_handler)
        for sig in (signal.SIGINT, signal.SIGTERM)
    }
    collector_host, collector_port = runtime.collector_address
    gui_host, gui_port = runtime.dashboard_address
    gui_url = f"http://{gui_host}:{gui_port}"
    print(f"E06_COLLECTOR_LISTENING={collector_host}:{collector_port}", flush=True)
    print(f"E06_DASHBOARD={gui_url}", flush=True)
    print(f"E06_SESSION_ROOT={args.sessions_dir}", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(gui_url,)).start()
    try:
        runtime.wait()
    except KeyboardInterrupt:
        runtime.request_stop()
    finally:
        runtime.stop()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print("E06_CLOUD_GUI_STOPPED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
