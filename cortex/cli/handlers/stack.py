"""Stack command handler for Cortex CLI.

Provides stack management for multi-package installations.
"""

import argparse
from typing import Any

from rich.console import Console

from cortex.stack_manager import StackManager

console = Console()


class StackHandler:
    """Handler for stack command."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def stack(self, args: argparse.Namespace) -> int:
        """Handle stack command."""
        subcommand = args.subcommand

        commands = {
            "list": self._handle_stack_list,
            "describe": self._handle_stack_describe,
            "install": self._handle_stack_install,
            "update": self._handle_stack_update,
            "delete": self._handle_stack_delete,
        }

        if subcommand in commands:
            return commands[subcommand](args)
        else:
            console.print(f"Unknown command: {subcommand}")
            return 1

    def _handle_stack_list(self, manager: StackManager) -> int:
        """List all stacks."""
        stacks = manager.list_stacks()

        if not stacks:
            console.print("No stacks found. Create one with: cortex stack install <name> <packages...>")
            return 0

        console.print("Stacks:")
        for name, stack in stacks.items():
            console.print(f"  • {name} ({len(stack['packages'])} packages)")
        return 0

    def _handle_stack_describe(self, manager: StackManager, stack_id: str) -> int:
        """Describe a stack."""
        stack = manager.get_stack(stack_id)

        if not stack:
            console.print(f"Stack not found: {stack_id}", style="yellow")
            return 1

        console.print(f"Stack: {stack_id}")
        console.print(f"Packages: {', '.join(stack['packages'])}")
        console.print(f"Created: {stack['created_at']}")
        return 0

    def _handle_stack_install(self, manager: StackManager, args: argparse.Namespace) -> int:
        """Install a stack."""
        stack_name = args.name
        packages = args.packages

        if manager.stack_exists(stack_name):
            console.print(f"Stack '{stack_name}' already exists", style="yellow")
            return 1

        success = manager.create_stack(stack_name, packages)

        if success:
            console.print(f"Stack '{stack_name}' created with {len(packages)} packages", style="green")
            return 0
        else:
            console.print(f"Failed to create stack", style="red")
            return 1

    def _handle_stack_update(self, manager: StackManager, args: argparse.Namespace) -> int:
        """Update a stack."""
        stack_name = args.name
        packages = args.packages

        if not manager.stack_exists(stack_name):
            console.print(f"Stack not found: {stack_name}", style="yellow")
            return 1

        success = manager.update_stack(stack_name, packages)

        if success:
            console.print(f"Stack '{stack_name}' updated", style="green")
            return 0
        else:
            console.print(f"Failed to update stack", style="red")
            return 1

    def _handle_stack_delete(self, manager: StackManager, stack_id: str) -> int:
        """Delete a stack."""
        if not manager.stack_exists(stack_id):
            console.print(f"Stack not found: {stack_id}", style="yellow")
            return 1

        success = manager.delete_stack(stack_id)

        if success:
            console.print(f"Stack '{stack_id}' deleted", style="green")
            return 0
        else:
            console.print(f"Failed to delete stack", style="red")
            return 1


def add_stack_parser(subparsers) -> argparse.ArgumentParser:
    """Add stack parser to subparsers."""
    stack_parser = subparsers.add_parser("stack", help="Manage application stacks")
    stack_subparsers = stack_parser.add_subparsers(dest="subcommand", required=True)

    list_parser = stack_subparsers.add_parser("list", help="List all stacks")

    describe_parser = stack_subparsers.add_parser("describe", help="Describe a stack")
    describe_parser.add_argument("name", help="Stack name")

    install_parser = stack_subparsers.add_parser("install", help="Create and install a stack")
    install_parser.add_argument("name", help="Stack name")
    install_parser.add_argument("packages", nargs="+", help="Packages to include")

    update_parser = stack_subparsers.add_parser("update", help="Update a stack")
    update_parser.add_argument("name", help="Stack name")
    update_parser.add_argument("packages", nargs="+", help="New package list")

    delete_parser = stack_subparsers.add_parser("delete", help="Delete a stack")
    delete_parser.add_argument("name", help="Stack name")

    return stack_parser
