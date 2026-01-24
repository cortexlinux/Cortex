"""Daemon command handler for Cortex CLI.

Provides daemon (cortexd) management.
"""

import argparse
import json
import socket
from typing import Any, Optional

from rich.console import Console

from cortex.daemon_client import DaemonClient, DaemonResponse

console = Console()


class DaemonHandler:
    """Handler for daemon command."""

    DEFAULT_PORT = 1717

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def daemon(self, args: argparse.Namespace) -> int:
        """Handle daemon command."""
        command = args.command

        commands = {
            "install": self._daemon_install,
            "uninstall": self._daemon_uninstall,
            "start": self._daemon_start,
            "stop": self._daemon_stop,
            "restart": self._daemon_restart,
            "status": self._daemon_status,
            "config": self._daemon_config,
            "reload": self._daemon_reload_config,
            "version": self._daemon_version,
            "ping": self._daemon_ping,
            "shutdown": self._daemon_shutdown,
            "run-tests": self._daemon_run_tests,
        }

        if command in commands:
            return commands[command](args)
        else:
            console.print(f"Unknown command: {command}")
            return 1

    def _daemon_ipc_call(self, method: str, params: Optional[dict[str, Any]] = None) -> DaemonResponse:
        """Make IPC call to daemon."""
        try:
            client = DaemonClient()
            return client.call(method, params or {})
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            console.print(f"Daemon not responding: {e}", style="yellow")
            return DaemonResponse(success=False, error=str(e), data=None)

    def _daemon_install(self, args) -> int:
        """Install daemon service."""
        result = self._daemon_ipc_call("system.install_service")
        if result.success:
            console.print("Daemon installed successfully", style="green")
            return 0
        else:
            console.print(f"Installation failed: {result.error}", style="red")
            return 1

    def _daemon_uninstall(self, args) -> int:
        """Uninstall daemon service."""
        result = self._daemon_ipc_call("system.uninstall_service")
        if result.success:
            console.print("Daemon uninstalled", style="green")
            return 0
        else:
            console.print(f"Uninstall failed: {result.error}", style="red")
            return 1

    def _daemon_start(self, args) -> int:
        """Start daemon service."""
        result = self._daemon_ipc_call("system.start_service")
        if result.success:
            console.print("Daemon started", style="green")
            return 0
        else:
            console.print(f"Start failed: {result.error}", style="red")
            return 1

    def _daemon_stop(self, args) -> int:
        """Stop daemon service."""
        result = self._daemon_ipc_call("system.stop_service")
        if result.success:
            console.print("Daemon stopped", style="green")
            return 0
        else:
            console.print(f"Stop failed: {result.error}", style="red")
            return 1

    def _daemon_restart(self, args) -> int:
        """Restart daemon service."""
        result = self._daemon_ipc_call("system.restart_service")
        if result.success:
            console.print("Daemon restarted", style="green")
            return 0
        else:
            console.print(f"Restart failed: {result.error}", style="red")
            return 1

    def _daemon_status(self, args) -> int:
        """Check daemon status."""
        result = self._daemon_ipc_call("system.status")
        if result.success:
            data = result.data or {}
            console.print(f"Status: {data.get('status', 'unknown')}")
            console.print(f"Uptime: {data.get('uptime', 'unknown')}")
            return 0
        else:
            console.print("Daemon not running", style="yellow")
            return 1

    def _daemon_config(self, args) -> int:
        """Configure daemon."""
        key = args.key
        value = args.value

        result = self._daemon_ipc_call("config.set", {"key": key, "value": value})
        if result.success:
            console.print(f"Config set: {key}={value}", style="green")
            return 0
        else:
            console.print(f"Config failed: {result.error}", style="red")
            return 1

    def _daemon_reload_config(self, args) -> int:
        """Reload daemon configuration."""
        result = self._daemon_ipc_call("config.reload")
        if result.success:
            console.print("Config reloaded", style="green")
            return 0
        else:
            console.print(f"Reload failed: {result.error}", style="red")
            return 1

    def _daemon_version(self, args) -> int:
        """Get daemon version."""
        result = self._daemon_ipc_call("system.version")
        if result.success:
            console.print(f"Daemon version: {result.data}")
            return 0
        else:
            console.print(f"Version check failed: {result.error}", style="red")
            return 1

    def _daemon_ping(self, args) -> int:
        """Ping daemon."""
        result = self._daemon_ipc_call("system.ping")
        if result.success:
            console.print("Pong", style="green")
            return 0
        else:
            console.print("Ping failed", style="red")
            return 1

    def _daemon_shutdown(self, args) -> int:
        """Shutdown daemon."""
        result = self._daemon_ipc_call("system.shutdown")
        if result.success:
            console.print("Daemon shutdown", style="green")
            return 0
        else:
            console.print(f"Shutdown failed: {result.error}", style="red")
            return 1

    def _daemon_run_tests(self, args) -> int:
        """Run daemon tests."""
        result = self._daemon_ipc_call("test.run")
        if result.success:
            console.print("Tests passed", style="green")
            return 0
        else:
            console.print(f"Tests failed: {result.error}", style="red")
            return 1


def add_daemon_parser(subparsers) -> argparse.ArgumentParser:
    """Add daemon parser to subparsers."""
    daemon_parser = subparsers.add_parser("daemon", help="Manage cortexd daemon")
    daemon_subparsers = daemon_parser.add_subparsers(dest="command", required=True)

    install_parser = daemon_subparsers.add_parser("install", help="Install daemon service")
    uninstall_parser = daemon_subparsers.add_parser("uninstall", help="Uninstall daemon service")
    start_parser = daemon_subparsers.add_parser("start", help="Start daemon")
    stop_parser = daemon_subparsers.add_parser("stop", help="Stop daemon")
    restart_parser = daemon_subparsers.add_parser("restart", help="Restart daemon")
    status_parser = daemon_subparsers.add_parser("status", help="Check daemon status")

    config_parser = daemon_subparsers.add_parser("config", help="Configure daemon")
    config_parser.add_argument("key", help="Config key")
    config_parser.add_argument("value", help="Config value")

    reload_parser = daemon_subparsers.add_parser("reload", help="Reload configuration")
    version_parser = daemon_subparsers.add_parser("version", help="Get daemon version")
    ping_parser = daemon_subparsers.add_parser("ping", help="Ping daemon")
    shutdown_parser = daemon_subparsers.add_parser("shutdown", help="Shutdown daemon")
    tests_parser = daemon_subparsers.add_parser("run-tests", help="Run daemon tests")

    return daemon_parser
