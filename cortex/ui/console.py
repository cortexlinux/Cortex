"""Cortex Console - Themed console singleton with semantic message methods."""

from typing import Optional
from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from .theme import CORTEX_THEME, SYMBOLS, PANEL_STYLES


class CortexConsole:
    """Themed console with semantic message methods."""
    
    _instance: Optional['CortexConsole'] = None
    
    def __new__(cls) -> 'CortexConsole':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._console = RichConsole(theme=CORTEX_THEME)
        return cls._instance
    
    @property
    def rich(self) -> RichConsole:
        return self._console
    
    def print(self, *args, **kwargs) -> None:
        self._console.print(*args, **kwargs)
    
    def success(self, message: str) -> None:
        self._console.print(f"[success_symbol]{SYMBOLS['success']}[/] [success]{message}[/]")
    
    def error(self, message: str, details: Optional[str] = None) -> None:
        self._console.print(f"[error_symbol]{SYMBOLS['error']}[/] [error]{message}[/]")
        if details:
            self._console.print(f"  [secondary]{details}[/]")
    
    def warning(self, message: str) -> None:
        self._console.print(f"[warning_symbol]{SYMBOLS['warning']}[/]  [warning]{message}[/]")
    
    def info(self, message: str) -> None:
        self._console.print(f"[info_symbol]{SYMBOLS['info']}[/] [info]{message}[/]")
    
    def command(self, cmd: str) -> None:
        self._console.print(f"[command]{SYMBOLS['command']} {cmd}[/]")
    
    def step(self, message: str, current: int, total: int) -> None:
        self._console.print(f"[info_symbol]{SYMBOLS['step']}[/] [info]{message}[/] [secondary]({current}/{total})[/]")
    
    def thinking(self, message: str) -> None:
        self._console.print(f"[cortex]{SYMBOLS['thinking']} {message}[/]")
    
    def secondary(self, message: str) -> None:
        self._console.print(f"  [secondary]{message}[/]")
    
    def blank(self) -> None:
        self._console.print()
    
    def rule(self, title: str = "") -> None:
        self._console.rule(title, style="panel_border")
    
    def code(self, code: str, language: str = "bash") -> None:
        syntax = Syntax(code, language, theme="monokai", line_numbers=False)
        self._console.print(syntax)
    
    def markdown(self, text: str) -> None:
        self._console.print(Markdown(text))
    
    def cortex_panel(self, content: str, title: str = "CORTEX") -> None:
        panel = Panel(content, title=f"[cortex]─ {title} [/]", **PANEL_STYLES["cortex"])
        self._console.print(panel)
    
    def panel(self, content: str, title: str = "", style: str = "default") -> None:
        panel_style = PANEL_STYLES.get(style, PANEL_STYLES["default"])
        panel = Panel(content, title=f"─ {title} " if title else None, **panel_style)
        self._console.print(panel)


console = CortexConsole()
