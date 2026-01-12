"""
Cortex UI Theme - Color constants and styling definitions.
Based on modern CLI patterns from Claude Code, Cursor, and GitHub Copilot.
"""

from rich.theme import Theme
from rich.style import Style

COLORS = {
    "success": "#22c55e",
    "error": "#ef4444",
    "warning": "#eab308",
    "info": "#3b82f6",
    "command": "#06b6d4",
    "secondary": "#6b7280",
    "primary": "#ffffff",
    "cortex": "#8b5cf6",
    "cortex_dim": "#7c3aed",
    "panel_border": "#4b5563",
    "highlight": "#fbbf24",
    "muted": "#9ca3af",
}

SYMBOLS = {
    "success": "✓",
    "error": "✗",
    "warning": "⚠",
    "info": "●",
    "command": "→",
    "thinking": "🔍",
    "step": "●",
    "prompt": "❯",
}

CORTEX_THEME = Theme({
    "success": Style(color=COLORS["success"], bold=True),
    "error": Style(color=COLORS["error"], bold=True),
    "warning": Style(color=COLORS["warning"], bold=True),
    "info": Style(color=COLORS["info"]),
    "command": Style(color=COLORS["command"], dim=True),
    "secondary": Style(color=COLORS["secondary"], dim=True),
    "primary": Style(color=COLORS["primary"]),
    "cortex": Style(color=COLORS["cortex"], bold=True),
    "cortex_dim": Style(color=COLORS["cortex_dim"]),
    "highlight": Style(color=COLORS["highlight"], bold=True),
    "muted": Style(color=COLORS["muted"]),
    "panel_border": Style(color=COLORS["panel_border"]),
    "success_symbol": Style(color=COLORS["success"]),
    "error_symbol": Style(color=COLORS["error"]),
    "warning_symbol": Style(color=COLORS["warning"]),
    "info_symbol": Style(color=COLORS["info"]),
})

PANEL_STYLES = {
    "default": {"border_style": "panel_border", "title_align": "left", "padding": (1, 2)},
    "cortex": {"border_style": "cortex", "title_align": "left", "padding": (1, 2)},
    "error": {"border_style": "error", "title_align": "left", "padding": (1, 2)},
    "warning": {"border_style": "warning", "title_align": "left", "padding": (1, 2)},
    "action": {"border_style": "highlight", "title_align": "left", "padding": (1, 2)},
}
