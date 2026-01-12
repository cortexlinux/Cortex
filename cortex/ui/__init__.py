"""Cortex UI - Modern terminal interface components."""

from .console import console, CortexConsole
from .theme import COLORS, SYMBOLS, CORTEX_THEME, PANEL_STYLES
from .prompts import CommandPrompt, MenuAction, PromptResult, confirm, select
from .progress import spinner, progress_bar, steps, indeterminate_progress, download_progress
from .errors import show_error, show_conflict, show_warning, auto_suggest_fix, SuggestedFix
from .explain import explain_command, explain_pipeline, CommandPart
from .trust import TrustManager, TrustScope, trust_manager
from .panels import ai_thinking, ai_response, status_panel, code_panel, diff_panel, summary_panel, welcome_banner, help_footer

__all__ = [
    "console", "CortexConsole", "COLORS", "SYMBOLS", "CORTEX_THEME", "PANEL_STYLES",
    "CommandPrompt", "MenuAction", "PromptResult", "confirm", "select",
    "spinner", "progress_bar", "steps", "indeterminate_progress", "download_progress",
    "show_error", "show_conflict", "show_warning", "auto_suggest_fix", "SuggestedFix",
    "explain_command", "explain_pipeline", "CommandPart",
    "TrustManager", "TrustScope", "trust_manager",
    "ai_thinking", "ai_response", "status_panel", "code_panel", "diff_panel", "summary_panel", "welcome_banner", "help_footer",
]
__version__ = "0.1.0"
