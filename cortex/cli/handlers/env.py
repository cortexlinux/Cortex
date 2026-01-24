"""Env command handler for Cortex CLI.

Provides environment variable management.
"""

import argparse
import json
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table

from cortex.env_manager import EnvironmentManager

console = Console()


class EnvHandler:
    """Handler for env command."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def env(self, args: argparse.Namespace) -> int:
        """Handle env command."""
        command = args.command

        commands = {
            "get": self._env_get,
            "set": self._env_set,
            "list": self._env_list,
            "delete": self._env_delete,
            "export": self._env_export,
            "clear": self._env_clear,
            "template": self._env_template,
            "path": self._env_path,
        }

        if command in commands:
            return commands[command](args)
        else:
            console.print(f"Unknown command: {command}")
            return 1

    def _env_get(self, args) -> int:
        """Get an environment variable."""
        key = args.key
        manager = EnvironmentManager()
        value = manager.get(key)
        if value:
            print(value)
            return 0
        else:
            console.print(f"Variable '{key}' not found", style="yellow")
            return 1

    def _env_set(self, args) -> int:
        """Set an environment variable."""
        key = args.key
        value = args.value
        manager = EnvironmentManager()
        manager.set(key, value)
        console.print(f"Set {key}={value}", style="green")
        return 0

    def _env_list(self, args) -> int:
        """List all environment variables."""
        manager = EnvironmentManager()
        variables = manager.list()

        if not variables:
            console.print("No environment variables set")
            return 0

        table = Table(title="Environment Variables")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")

        for key, value in variables.items():
            display_value = value[:50] + "..." if len(value) > 50 else value
            table.add_row(key, display_value)

        console.print(table)
        return 0

    def _env_delete(self, args) -> int:
        """Delete an environment variable."""
        key = args.key
        manager = EnvironmentManager()
        if manager.delete(key):
            console.print(f"Deleted {key}", style="green")
            return 0
        else:
            console.print(f"Variable '{key}' not found", style="yellow")
            return 1

    def _env_export(self, args) -> int:
        """Export environment variables to a file."""
        path = args.path
        manager = EnvironmentManager()
        manager.export_to_shell(path)
        console.print(f"Exported to {path}", style="green")
        return 0

    def _env_clear(self, args) -> int:
        """Clear all environment variables."""
        manager = EnvironmentManager()
        count = manager.clear()
        console.print(f"Cleared {count} variables", style="green")
        return 0

    def _env_template(self, args) -> int:
        """Handle template subcommands."""
        subcommand = getattr(args, "template_command", "list")

        if subcommand == "list":
            manager = EnvironmentManager()
            templates = manager.list_templates()
            if templates:
                for name in templates:
                    console.print(f"  • {name}")
            else:
                console.print("No templates found")
            return 0

        elif subcommand == "apply":
            name = args.template_name
            manager = EnvironmentManager()
            if manager.apply_template(name):
                console.print(f"Applied template '{name}'", style="green")
                return 0
            else:
                console.print(f"Template '{name}' not found", style="yellow")
                return 1

        return 0

    def _env_path(self, args) -> int:
        """Handle path subcommands."""
        subcommand = getattr(args, "path_command", "list")

        manager = EnvironmentManager()

        if subcommand == "list":
            paths = manager.get_path()
            for i, p in enumerate(paths):
                console.print(f"  {i+1}. {p}")
            return 0

        elif subcommand == "add":
            path = args.path
            manager.add_path(path)
            console.print(f"Added to PATH: {path}", style="green")
            return 0

        elif subcommand == "remove":
            path = args.path
            if manager.remove_path(path):
                console.print(f"Removed from PATH: {path}", style="green")
                return 0
            else:
                console.print(f"Path not found: {path}", style="yellow")
                return 1

        return 0


def add_env_parser(subparsers) -> argparse.ArgumentParser:
    """Add env parser to subparsers."""
    env_parser = subparsers.add_parser("env", help="Manage environment variables")
    env_subparsers = env_parser.add_subparsers(dest="command", required=True)

    get_parser = env_subparsers.add_parser("get", help="Get a variable")
    get_parser.add_argument("key", help="Variable name")

    set_parser = env_subparsers.add_parser("set", help="Set a variable")
    set_parser.add_argument("key", help="Variable name")
    set_parser.add_argument("value", help="Variable value")

    list_parser = env_subparsers.add_parser("list", help="List all variables")

    delete_parser = env_subparsers.add_parser("delete", help="Delete a variable")
    delete_parser.add_argument("key", help="Variable name")

    export_parser = env_subparsers.add_parser("export", help="Export to file")
    export_parser.add_argument("path", help="Output file path")

    clear_parser = env_subparsers.add_parser("clear", help="Clear all variables")

    template_parser = env_subparsers.add_parser("template", help="Template operations")
    template_sub = template_parser.add_subparsers(dest="template_command")
    template_list = template_sub.add_parser("list", help="List templates")
    template_apply = template_sub.add_parser("apply", help="Apply a template")
    template_apply.add_argument("name", help="Template name")

    path_parser = env_subparsers.add_parser("path", help="Path operations")
    path_sub = path_parser.add_subparsers(dest="path_command")
    path_list = path_sub.add_parser("list", help="List PATH entries")
    path_add = path_sub.add_parser("add", help="Add to PATH")
    path_add.add_argument("path", help="Path to add")
    path_remove = path_sub.add_parser("remove", help="Remove from PATH")
    path_remove.add_argument("path", help="Path to remove")

    return env_parser
