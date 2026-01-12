"""Cortex Explain - Command explanation and breakdown."""

from typing import List, Tuple
from dataclasses import dataclass
import shlex
from rich.panel import Panel
from .console import console


@dataclass
class CommandPart:
    text: str
    explanation: str
    is_flag: bool = False


COMMAND_EXPLANATIONS = {
    "docker": {
        "run": "Creates and starts a new container", "-d": "Runs in background (detached)", "--detach": "Runs in background",
        "-v": "Mounts a volume (host:container)", "--volume": "Mounts a volume", "-p": "Maps a port (host:container)",
        "--publish": "Maps a port", "--name": "Names the container", "--gpus": "Grants GPU access",
        "--rm": "Auto-removes when exits", "-it": "Interactive with TTY", "-e": "Sets environment variable",
        "pull": "Downloads an image", "stop": "Stops container", "rm": "Removes container", "-f": "Force operation",
    },
    "apt": {
        "install": "Installs packages", "update": "Refreshes package index", "upgrade": "Upgrades all packages",
        "remove": "Removes package", "purge": "Removes package + config", "-y": "Auto-yes to prompts",
    },
    "pip": {
        "install": "Installs Python packages", "-e": "Editable/dev mode", "-r": "From requirements file",
        "--upgrade": "Upgrades to latest", "-U": "Upgrades to latest", "--break-system-packages": "Allows system Python changes",
    },
    "git": {
        "clone": "Downloads repository", "pull": "Fetches and merges", "push": "Uploads commits",
        "add": "Stages files", "commit": "Records changes", "-m": "Commit message", "checkout": "Switches branches", "-b": "Creates new branch",
    },
}


def parse_command(cmd: str) -> Tuple[str, List[str]]:
    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()
    return (parts[0], parts[1:]) if parts else ("", [])


def get_explanation(base_cmd: str, part: str) -> str:
    cmd_exp = COMMAND_EXPLANATIONS.get(base_cmd, {})
    if part in cmd_exp:
        return cmd_exp[part]
    if part.lstrip('-') in cmd_exp:
        return cmd_exp[part.lstrip('-')]
    if part.startswith('-'):
        return "Option flag"
    if ':' in part:
        return "Mapping (source:destination)"
    if '/' in part and not part.startswith('/'):
        return "Image or path reference"
    return "Argument or value"


def explain_command(cmd: str, show_panel: bool = True) -> List[CommandPart]:
    base_cmd, args = parse_command(cmd)
    parts = [CommandPart(text=base_cmd, explanation=f"The {base_cmd} command")]
    
    i = 0
    while i < len(args):
        arg = args[i]
        exp = get_explanation(base_cmd, arg)
        if arg.startswith('-') and i + 1 < len(args) and not args[i + 1].startswith('-'):
            parts.append(CommandPart(text=f"{arg} {args[i+1]}", explanation=f"{exp}: {args[i+1]}", is_flag=True))
            i += 2
        else:
            parts.append(CommandPart(text=arg, explanation=exp, is_flag=arg.startswith('-')))
            i += 1
    
    if show_panel:
        lines = [f"[command]{cmd}[/]", ""]
        for j, part in enumerate(parts):
            lines.append(f"[{'cortex' if j == 0 else 'info'}]{part.text}[/]")
            lines.append(f"└─ [secondary]{part.explanation}[/]")
            if j < len(parts) - 1:
                lines.append("")
        console.print(Panel("\n".join(lines), title="[cortex]─ EXPLANATION [/]", border_style="cortex", padding=(1, 2)))
        console.print("\n [secondary]Press Enter to return to options[/]")
        input()
    return parts


def explain_pipeline(cmd: str) -> None:
    import re
    parts = re.split(r'\s*(\||\&\&|\|\|)\s*', cmd)
    lines = ["[muted]Pipeline breakdown:[/]", ""]
    step = 1
    for part in parts:
        if part in ('|', '&&', '||'):
            ops = {'|': 'pipes output to', '&&': 'then (if successful)', '||': 'or (if failed)'}
            lines.append(f"   [warning]{ops.get(part, part)}[/]")
        elif part.strip():
            lines.append(f"[info]{step}.[/] [command]{part.strip()}[/]")
            step += 1
    console.print(Panel("\n".join(lines), title="[cortex]─ PIPELINE [/]", border_style="cortex", padding=(1, 2)))
