"""Output utilities for Cortex CLI.

Provides print helpers for status, error, and success messages.
"""

import sys
import time
from typing import Any

from rich.console import Console

console = Console()


def _print_status(emoji: str, message: str) -> None:
    """Print a status message with emoji."""
    console.print(f"{emoji} {message}")


def _print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]✗[/red] {message}", file=sys.stderr)


def _print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def _animate_spinner(message: str) -> None:
    """Create a spinner animation context."""
    from contextlib import contextmanager

    @contextmanager
    def spinner():
        """Spinner context manager."""
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        for char in chars:
            sys.stdout.write(f"\r{char} {message}")
            sys.stdout.flush()
            time.sleep(0.05)
        sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
        sys.stdout.flush()

    return spinner()


def _clear_line() -> None:
    """Clear the current line."""
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()


def _debug(message: str, verbose: bool = False) -> None:
    """Print debug message if verbose mode is enabled."""
    if verbose:
        console.print(f"[dim]↳ {message}[/dim]")
