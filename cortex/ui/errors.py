"""Cortex Errors - Structured error display with context and fixes."""

from typing import Optional, Dict, List
from dataclasses import dataclass
import re
from rich.panel import Panel
from .theme import SYMBOLS
from .console import console


@dataclass
class SuggestedFix:
    command: str
    description: Optional[str] = None


COMMON_ERRORS = {
    "container_conflict": {"pattern": "container name .* already in use", "title": "Container Name Conflict", "fix_template": "docker rm -f {container_name}", "fix_description": "Remove the existing container"},
    "port_in_use": {"pattern": "port .* already in use", "title": "Port Already In Use", "fix_template": "lsof -ti:{port} | xargs kill -9", "fix_description": "Kill the process using the port"},
    "permission_denied": {"pattern": "permission denied", "title": "Permission Denied", "fix_template": "sudo {original_command}", "fix_description": "Run with elevated privileges"},
    "not_found": {"pattern": "command not found|not found", "title": "Command Not Found", "fix_template": "apt install {package}", "fix_description": "Install the missing package"},
}


def show_error(title: str, message: str, context: Optional[Dict[str, str]] = None, suggested_fix: Optional[str] = None, fix_description: Optional[str] = None, actions: Optional[List[str]] = None) -> Optional[str]:
    lines = [f"[error]{SYMBOLS['error']} FAILED:[/] [primary]{title}[/]", "", f"  [error]Error:[/] {message}"]
    if context:
        lines.append("")
        for key, value in context.items():
            display_value = value if len(value) < 50 else value[:47] + "..."
            lines.append(f"  [secondary]{key}:[/] {display_value}")
    
    if suggested_fix:
        fix_content = []
        if fix_description:
            fix_content.append(f"[muted]{fix_description}[/]")
            fix_content.append("")
        fix_content.append(f"[command]{suggested_fix}[/]")
        console.print(Panel("\n".join(lines), border_style="error", padding=(1, 2)))
        console.print(Panel("\n".join(fix_content), title="[success]─ SUGGESTED FIX [/]", border_style="success", padding=(0, 2)))
    else:
        console.print(Panel("\n".join(lines), border_style="error", padding=(1, 2)))
    
    if actions:
        action_text = [f"[highlight][{a[0].upper()}][/][muted]{a[1:]}[/]" for a in actions]
        console.print("  " + "  ".join(action_text))
        console.print()
        while True:
            response = input("  > ").strip().lower()
            for action in actions:
                if response == action[0].lower() or response == action.lower():
                    return action
            console.warning(f"Please enter one of: {', '.join(a[0] for a in actions)}")
    return None


def show_conflict(title: str, description: str, options: List[Dict[str, str]]) -> str:
    lines = [f"[warning]{SYMBOLS['warning']}  CONFLICT DETECTED[/]", "", f"[primary]{description}[/]", "", "[muted]Options:[/]"]
    for opt in options:
        lines.append(f"  [highlight][{opt['key']}][/] {opt['label']}")
        if opt.get('description'):
            lines.append(f"      [secondary]{opt['description']}[/]")
    console.print(Panel("\n".join(lines), title=f"[warning]─ {title} [/]", border_style="warning", padding=(1, 2)))
    valid_keys = [opt['key'].lower() for opt in options]
    while True:
        response = input(f"\n  {SYMBOLS['prompt']} What would you like to do? ").strip().lower()
        if response in valid_keys:
            return response
        console.warning(f"Please enter one of: {', '.join(valid_keys)}")


def show_warning(title: str, message: str, details: Optional[List[str]] = None) -> None:
    lines = [f"[warning]{SYMBOLS['warning']}  {title}[/]", "", f"[primary]{message}[/]"]
    if details:
        lines.append("")
        for detail in details:
            lines.append(f"  [secondary]• {detail}[/]")
    console.print(Panel("\n".join(lines), border_style="warning", padding=(1, 2)))


def auto_suggest_fix(error_message: str, command: str = "") -> Optional[SuggestedFix]:
    error_lower = error_message.lower()
    for error_type, info in COMMON_ERRORS.items():
        if re.search(info["pattern"], error_lower):
            fix_cmd = info["fix_template"]
            if error_type == "container_conflict":
                match = re.search(r'name ["\']?/?(\w+)', error_lower)
                if match:
                    fix_cmd = fix_cmd.format(container_name=match.group(1))
            elif error_type == "port_in_use":
                match = re.search(r'port (\d+)', error_lower)
                if match:
                    fix_cmd = fix_cmd.format(port=match.group(1))
            elif error_type == "permission_denied":
                fix_cmd = fix_cmd.format(original_command=command)
            return SuggestedFix(command=fix_cmd, description=info["fix_description"])
    return None
