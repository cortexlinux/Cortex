"""Update command handler for Cortex CLI.

Provides self-update functionality.
"""

import argparse
from typing import Optional

from rich.console import Console
from rich.table import Table

from cortex.update_checker import UpdateChannel, should_notify_update
from cortex.updater import Updater, UpdateStatus

console = Console()


class UpdateHandler:
    """Handler for update command."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def update(self, args: argparse.Namespace) -> int:
        """Handle update command."""
        subcommand = args.subcommand

        commands = {
            "check": self._update_check,
            "install": self._update_install,
            "rollback": self._update_rollback,
            "list": self._update_list,
            "backups": self._update_backups,
        }

        if subcommand in commands:
            return commands[subcommand](args)
        else:
            console.print(f"Unknown command: {subcommand}")
            return 1

    def _update_check(self, args) -> int:
        """Check for updates."""
        channel = getattr(args, "channel", "stable")
        show_all = getattr(args, "all", False)

        try:
            has_update, current, latest, releases = should_notify_update(channel=channel)

            if has_update:
                console.print(f"Update available: {current} → {latest}", style="green")
                if releases:
                    console.print("\nRecent releases:")
                    for release in releases[:5]:
                        console.print(f"  • {release}")
            else:
                console.print(f"You're on the latest version: {current}", style="blue")
                if show_all:
                    if releases:
                        console.print("\nAll releases:")
                        for release in releases[:10]:
                            console.print(f"  • {release}")
            return 0
        except Exception as e:
            console.print(f"Check failed: {e}", style="red")
            return 1

    def _update_install(self, args) -> int:
        """Install update."""
        version = getattr(args, "version", None)
        channel = getattr(args, "channel", "stable")
        force = getattr(args, "force", False)

        try:
            updater = Updater()
            result = updater.update(version=version, channel=channel, force=force)

            if result.status == UpdateStatus.UPDATED:
                console.print(f"Updated to {result.version}", style="green")
                return 0
            elif result.status == UpdateStatus.ALREADY_LATEST:
                console.print("Already on the latest version", style="blue")
                return 0
            elif result.status == UpdateStatus.DOWNLOADING:
                console.print(f"Downloading {result.version}...", style="blue")
                return 0
            elif result.status == UpdateStatus.ROLLED_BACK:
                console.print("Rolled back to previous version", style="yellow")
                return 0
            else:
                console.print(f"Update failed: {result.message}", style="red")
                return 1
        except Exception as e:
            console.print(f"Update failed: {e}", style="red")
            return 1

    def _update_rollback(self, args) -> int:
        """Rollback update."""
        backup_id = args.backup_id

        try:
            updater = Updater()
            result = updater.rollback(backup_id)

            if result.status == UpdateStatus.ROLLED_BACK:
                console.print(f"Rolled back to {result.version}", style="green")
                return 0
            else:
                console.print(f"Rollback failed: {result.message}", style="red")
                return 1
        except Exception as e:
            console.print(f"Rollback failed: {e}", style="red")
            return 1

    def _update_list(self, args) -> int:
        """List available versions."""
        try:
            updater = Updater()
            releases = updater.list_releases()

            if releases:
                table = Table(title="Available Versions")
                table.add_column("Version")
                table.add_column("Date")

                for release in releases:
                    table.add_row(release["version"], release["date"])

                console.print(table)
            else:
                console.print("No releases found")
            return 0
        except Exception as e:
            console.print(f"List failed: {e}", style="red")
            return 1

    def _update_backups(self, args) -> int:
        """List available backups."""
        try:
            updater = Updater()
            backups = updater.list_backups()

            if backups:
                table = Table(title="Available Backups")
                table.add_column("ID")
                table.add_column("Version")
                table.add_column("Date")

                for backup in backups:
                    table.add_row(backup["id"], backup["version"], backup["date"])

                console.print(table)
            else:
                console.print("No backups found")
            return 0
        except Exception as e:
            console.print(f"List failed: {e}", style="red")
            return 1


def add_update_parser(subparsers) -> argparse.ArgumentParser:
    """Add update parser to subparsers."""
    update_parser = subparsers.add_parser("update", help="Update Cortex")
    update_subparsers = update_parser.add_subparsers(dest="subcommand", required=True)

    check_parser = update_subparsers.add_parser("check", help="Check for updates")
    check_parser.add_argument("--channel", choices=["stable", "beta", "dev"], default="stable")
    check_parser.add_argument("--all", action="store_true", help="Show all releases")

    install_parser = update_subparsers.add_parser("install", help="Install update")
    install_parser.add_argument("version", nargs="?", help="Specific version")
    install_parser.add_argument("--channel", choices=["stable", "beta", "dev"], default="stable")
    install_parser.add_argument("--force", action="store_true", help="Force update")

    rollback_parser = update_subparsers.add_parser("rollback", help="Rollback update")
    rollback_parser.add_argument("backup_id", help="Backup ID to rollback to")

    list_parser = update_subparsers.add_parser("list", help="List available versions")

    backups_parser = update_subparsers.add_parser("backups", help="List available backups")

    return update_parser
