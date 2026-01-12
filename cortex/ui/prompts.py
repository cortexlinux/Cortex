"""Cortex Prompts - Interactive prompt system with modern UX patterns."""

import sys
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass
from rich.panel import Panel
from .theme import SYMBOLS, PANEL_STYLES
from .console import console


class MenuAction(Enum):
    RUN = "run"
    TRUST = "trust"
    DRY_RUN = "dry_run"
    EXPLAIN = "explain"
    EDIT = "edit"
    CANCEL = "cancel"
    ADD_INSTRUCTIONS = "add_instructions"


@dataclass
class MenuOption:
    key: str
    label: str
    action: MenuAction
    description: str = ""


@dataclass
class PromptResult:
    action: MenuAction
    command: str
    additional_instructions: Optional[str] = None
    trust_scope: Optional[str] = None


COMMAND_MENU_OPTIONS = [
    MenuOption("1", "Run it", MenuAction.RUN, "Execute the command now"),
    MenuOption("2", "Run, and trust similar this session", MenuAction.TRUST, "Don't ask again for this command type"),
    MenuOption("3", "Dry run (preview)", MenuAction.DRY_RUN, "Show what would happen without executing"),
    MenuOption("4", "Explain this command", MenuAction.EXPLAIN, "Break down what each part does"),
    MenuOption("5", "Edit before running", MenuAction.EDIT, "Modify the command first"),
    MenuOption("6", "Cancel", MenuAction.CANCEL, "Abort this operation"),
]


class CommandPrompt:
    def __init__(self, command: str, context: str = "", commands: Optional[List[str]] = None, working_dir: Optional[str] = None):
        self.command = command
        self.commands = commands or [command]
        self.context = context
        self.working_dir = working_dir
        self.selected_index = 0
        self.additional_instructions: Optional[str] = None
        
    def _render_command_panel(self) -> Panel:
        content_lines = []
        if self.context:
            content_lines.append(f"[cortex]{SYMBOLS['thinking']} {self.context}[/]")
            content_lines.append("")
        content_lines.append("[muted]Commands to execute:[/]")
        for cmd in self.commands:
            content_lines.append(f"  [command]{cmd}[/]")
        if self.working_dir:
            content_lines.append("")
            content_lines.append(f"[secondary]Directory: {self.working_dir}[/]")
        return Panel("\n".join(content_lines), title="[cortex]─ CORTEX [/]", border_style="cortex", padding=(1, 2))
    
    def _render_menu(self) -> str:
        lines = ["", " [muted]How would you like to proceed?[/]", ""]
        for i, option in enumerate(COMMAND_MENU_OPTIONS):
            if i == self.selected_index:
                lines.append(f" [highlight]{SYMBOLS['prompt']}[/] [highlight]{option.key}. {option.label}[/]")
            else:
                lines.append(f"   [primary]{option.key}. {option.label}[/]")
        lines.append("")
        lines.append(" [secondary]esc[/] [muted]Cancel[/]  ·  [secondary]tab[/] [muted]Add instructions[/]  ·  [secondary]?[/] [muted]Help[/]")
        return "\n".join(lines)
    
    def show(self) -> PromptResult:
        console.print(self._render_command_panel())
        console.print(self._render_menu())
        
        while True:
            try:
                response = input("\n  > ").strip()
            except (KeyboardInterrupt, EOFError):
                return PromptResult(action=MenuAction.CANCEL, command=self.command)
            
            if response in '123456':
                return PromptResult(action=COMMAND_MENU_OPTIONS[int(response) - 1].action, command=self.command, additional_instructions=self.additional_instructions)
            elif response.lower() in ('q', 'esc', 'cancel'):
                return PromptResult(action=MenuAction.CANCEL, command=self.command)
            elif response == '?':
                return PromptResult(action=MenuAction.EXPLAIN, command=self.command)
            elif response.lower() == 'd':
                return PromptResult(action=MenuAction.DRY_RUN, command=self.command)
            elif response.lower() == 'e':
                return PromptResult(action=MenuAction.EDIT, command=self.command)
            else:
                console.warning("Please enter 1-6, or use shortcuts: d=dry run, e=edit, q=cancel")


def confirm(message: str, details: Optional[List[str]] = None, default: bool = True, allow_dont_ask: bool = True) -> tuple:
    content_lines = [f"[primary]{message}[/]"]
    if details:
        content_lines.append("")
        for detail in details:
            content_lines.append(f"  [muted]•[/] {detail}")
    content_lines.append("")
    options = ["[highlight][Y][/] [primary]Yes[/]" if default else "[muted][y][/] [muted]Yes[/]"]
    options.append("[muted][n][/] [muted]No[/]" if default else "[highlight][N][/] [primary]No[/]")
    if allow_dont_ask:
        options.append("[muted][a][/] [muted]Yes, don't ask again[/]")
    content_lines.append("  " + "  ".join(options))
    console.print(Panel("\n".join(content_lines), title="[highlight]─ ACTION REQUIRED [/]", border_style="highlight", padding=(1, 2)))
    
    while True:
        response = input("  > ").strip().lower()
        if response in ('', 'y', 'yes') and default:
            return (True, False)
        elif response in ('y', 'yes'):
            return (True, False)
        elif response in ('n', 'no'):
            return (False, False)
        elif response == 'a' and allow_dont_ask:
            return (True, True)
        elif response == '' and not default:
            return (False, False)
        console.warning("Please enter Y, N" + (", or A" if allow_dont_ask else ""))


def select(message: str, options: List[str], default: int = 0) -> int:
    console.print(f"\n [muted]{message}[/]\n")
    for i, option in enumerate(options):
        prefix = f" [highlight]{SYMBOLS['prompt']}[/]" if i == default else "  "
        style = "highlight" if i == default else "muted"
        console.print(f"{prefix} [{style}]{i + 1}. {option}[/]")
    console.print("\n [secondary]Enter number to select[/]")
    
    while True:
        try:
            response = input("  > ").strip()
            if response.isdigit() and 0 < int(response) <= len(options):
                return int(response) - 1
            console.warning(f"Please enter 1-{len(options)}")
        except (KeyboardInterrupt, EOFError):
            return -1
