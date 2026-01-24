"""Sandbox command handler for Cortex CLI.

Provides sandboxed execution for testing commands.
"""

import argparse
from typing import Optional

from rich.console import Console

from cortex.sandbox.sandbox_executor import SandboxExecutor

console = Console()


class SandboxHandler:
    """Handler for sandbox command."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def sandbox(self, args: argparse.Namespace) -> int:
        """Handle sandbox command."""
        subcommand = args.subcommand

        commands = {
            "create": self._sandbox_create,
            "list": self._sandbox_list,
            "cleanup": self._sandbox_cleanup,
        }

        if subcommand in commands:
            return commands[subcommand](args)
        else:
            console.print(f"Unknown command: {subcommand}")
            return 1

    def _sandbox_create(self, args) -> int:
        """Create a new sandbox."""
        name = getattr(args, "name", None)
        packages = getattr(args, "packages", "")
        isolate_network = getattr(args, "isolate_network", False)

        try:
            executor = SandboxExecutor()
            sandbox = executor.create_sandbox(
                name=name,
                packages=packages.split(",") if packages else None,
                isolate_network=isolate_network,
            )
            console.print(f"Created sandbox: {sandbox.id}", style="green")
            return 0
        except Exception as e:
            console.print(f"Failed to create sandbox: {e}", style="red")
            return 1

    def _sandbox_list(self, args) -> int:
        """List all sandboxes."""
        try:
            executor = SandboxExecutor()
            sandboxes = executor.list_sandboxes()

            if sandboxes:
                for sb in sandboxes:
                    console.print(f"  • {sb['id']} ({sb['status']})")
            else:
                console.print("No sandboxes found")
            return 0
        except Exception as e:
            console.print(f"Failed to list sandboxes: {e}", style="red")
            return 1

    def _sandbox_cleanup(self, args) -> int:
        """Cleanup old sandboxes."""
        all_sandboxes = getattr(args, "all", False)

        try:
            executor = SandboxExecutor()
            count = executor.cleanup(include_active=bool(all_sandboxes))
            console.print(f"Cleaned up {count} sandbox(es)", style="green")
            return 0
        except Exception as e:
            console.print(f"Failed to cleanup sandboxes: {e}", style="red")
            return 1


def add_sandbox_parser(subparsers) -> argparse.ArgumentParser:
    """Add sandbox parser to subparsers."""
    sandbox_parser = subparsers.add_parser("sandbox", help="Manage sandboxes for testing")
    sandbox_subparsers = sandbox_parser.add_subparsers(dest="subcommand", required=True)

    create_parser = sandbox_subparsers.add_parser("create", help="Create a new sandbox")
    create_parser.add_argument("--name", help="Sandbox name")
    create_parser.add_argument("--packages", help="Comma-separated packages to install")
    create_parser.add_argument("--isolate-network", action="store_true", help="Isolate network")

    list_parser = sandbox_subparsers.add_parser("list", help="List all sandboxes")

    cleanup_parser = sandbox_subparsers.add_parser("cleanup", help="Cleanup old sandboxes")
    cleanup_parser.add_argument("--all", action="store_true", help="Include active sandboxes")

    return sandbox_parser
