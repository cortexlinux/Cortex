"""Cortex Panels - AI response and status panels."""

from typing import Optional, List
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.console import Group
from .console import console
from .theme import SYMBOLS


def ai_thinking(message: str, animated: bool = False) -> None:
    content = f"[cortex]{SYMBOLS['thinking']} {message}[/]"
    console.print(Panel(content, title="[cortex]─ CORTEX [/]", border_style="cortex", padding=(1, 2)))


def ai_response(message: str, title: str = "CORTEX", show_commands: Optional[List[str]] = None, show_code: Optional[str] = None, code_language: str = "bash") -> None:
    content_parts = [Text(message)]
    if show_commands:
        content_parts.append(Text())
        content_parts.append(Text("Commands to execute:", style="muted"))
        for cmd in show_commands:
            content_parts.append(Text(f"  {cmd}", style="command"))
    if show_code:
        content_parts.append(Text())
        content_parts.append(Syntax(show_code, code_language, theme="monokai", line_numbers=False))
    content = Group(*content_parts) if len(content_parts) > 1 else content_parts[0]
    console.print(Panel(content, title=f"[cortex]─ {title} [/]", border_style="cortex", padding=(1, 2)))


def status_panel(title: str, items: List[str], style: str = "default") -> None:
    content = "\n".join(f"  {item}" for item in items)
    border = {"default": "panel_border", "success": "success", "warning": "warning", "error": "error"}.get(style, "panel_border")
    console.print(Panel(content, title=f"─ {title} ", border_style=border, padding=(1, 2)))


def code_panel(code: str, language: str = "bash", title: str = "Code") -> None:
    console.print(Panel(Syntax(code, language, theme="monokai", line_numbers=True), title=f"─ {title} ", border_style="panel_border", padding=(0, 1)))


def diff_panel(additions: List[str], deletions: List[str], title: str = "Changes") -> None:
    lines = [f"[error]- {line}[/]" for line in deletions] + [f"[success]+ {line}[/]" for line in additions]
    console.print(Panel("\n".join(lines), title=f"─ {title} ", border_style="panel_border", padding=(0, 2)))


def summary_panel(title: str, summary: str, details: Optional[dict] = None) -> None:
    lines = [summary]
    if details:
        lines.append("")
        for key, value in details.items():
            lines.append(f"[muted]{key}:[/] {value}")
    console.print(Panel("\n".join(lines), title=f"[cortex]─ {title} [/]", border_style="cortex", padding=(1, 2)))


def welcome_banner() -> None:
    banner = """[cortex]   ____          _            
  / ___|___  _ __| |_ _____  __
 | |   / _ \\| '__| __/ _ \\ \\/ /
 | |__| (_) | |  | ||  __/>  < 
  \\____\\___/|_|   \\__\\___/_/\\_\\[/]
  
[muted]The AI Layer for Linux[/]"""
    console.print(banner)


def help_footer() -> None:
    console.print("\n [secondary]esc[/] [muted]Cancel[/]  ·  [secondary]tab[/] [muted]Add instructions[/]  ·  [secondary]?[/] [muted]Help[/]")
