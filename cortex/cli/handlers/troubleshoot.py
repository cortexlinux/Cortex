"""Troubleshoot command handler for Cortex CLI.

Provides troubleshooting and diagnostic capabilities.
"""

import argparse

from cortex.troubleshoot import Troubleshooter


class TroubleshootHandler:
    """Handler for troubleshoot command."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def troubleshoot(self, no_execute: bool = False) -> int:
        """Run system diagnostics and troubleshooting."""
        troubleshooter = Troubleshooter()
        return troubleshooter.run(full=not no_execute)


def add_troubleshoot_parser(subparsers) -> argparse.ArgumentParser:
    """Add troubleshoot parser to subparsers."""
    troubleshoot_parser = subparsers.add_parser(
        "troubleshoot", help="Run system diagnostics and troubleshooting"
    )
    troubleshoot_parser.add_argument(
        "--no-execute", action="store_true", help="Run diagnostics without making changes"
    )
    return troubleshoot_parser
