"""Cortex CLI Handlers.

Modular command handlers for Cortex CLI.
"""

from cortex.cli.handlers.ask import AskHandlerWrapper, add_ask_parser
from cortex.cli.handlers.config import ConfigHandler, add_config_parser
from cortex.cli.handlers.daemon import DaemonHandler, add_daemon_parser
from cortex.cli.handlers.env import EnvHandler, add_env_parser
from cortex.cli.handlers.history import HistoryHandler, add_history_parser, add_rollback_parser
from cortex.cli.handlers.import_deps import ImportDepHandler, add_import_deps_parser
from cortex.cli.handlers.install import InstallHandler, add_install_parser
from cortex.cli.handlers.remove import RemoveHandler, add_remove_parser
from cortex.cli.handlers.sandbox import SandboxHandler, add_sandbox_parser
from cortex.cli.handlers.stack import StackHandler, add_stack_parser
from cortex.cli.handlers.troubleshoot import TroubleshootHandler, add_troubleshoot_parser
from cortex.cli.handlers.update import UpdateHandler, add_update_parser

__all__ = [
    # Ask
    "AskHandlerWrapper",
    "add_ask_parser",
    # Config
    "ConfigHandler",
    "add_config_parser",
    # Daemon
    "DaemonHandler",
    "add_daemon_parser",
    # Env
    "EnvHandler",
    "add_env_parser",
    # History
    "HistoryHandler",
    "add_history_parser",
    "add_rollback_parser",
    # Import
    "ImportDepHandler",
    "add_import_deps_parser",
    # Install
    "InstallHandler",
    "add_install_parser",
    # Remove
    "RemoveHandler",
    "add_remove_parser",
    # Sandbox
    "SandboxHandler",
    "add_sandbox_parser",
    # Stack
    "StackHandler",
    "add_stack_parser",
    # Troubleshoot
    "TroubleshootHandler",
    "add_troubleshoot_parser",
    # Update
    "UpdateHandler",
    "add_update_parser",
]
