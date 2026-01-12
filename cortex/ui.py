"""
Cortex UI Module - Rich formatting with colors, boxes, and spinners.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn
from rich.status import Status
from rich.table import Table
from rich.columns import Columns

console = Console()

BADGE = "[bold white on dark_cyan] CX [/bold white on dark_cyan]"
DEFAULT_BORDER_COLOR = "cyan"
DEFAULT_PANEL_WIDTH = 70


# ============================================================================
# STATUS MESSAGES
# ============================================================================

def success(message: str, details: str = "", badge: bool = True):
    """Green success message with ✓
    
    Args:
        message: Main success message
        details: Optional additional details (dimmed)
        badge: Show CX badge (default: True)
    """
    prefix = f"{BADGE} " if badge else ""
    console.print(f"{prefix}[green]✓[/green] {message}")
    if details:
        console.print(f"    [dim]{details}[/dim]")


def error(message: str, details: str = "", badge: bool = True):
    """Red error message with ✗
    
    Args:
        message: Main error message
        details: Optional error details
        badge: Show CX badge (default: True)
    """
    prefix = f"{BADGE} " if badge else ""
    console.print(f"{prefix}[red]✗[/red] {message}")
    if details:
        console.print(f"    [red]{details}[/red]")


def warning(message: str, details: str = "", badge: bool = True):
    """Yellow warning with ⚠
    
    Args:
        message: Warning message
        details: Optional warning details
        badge: Show CX badge (default: True)
    """
    prefix = f"{BADGE} " if badge else ""
    console.print(f"{prefix}[yellow]⚠[/yellow] {message}")
    if details:
        console.print(f"    [dim]{details}[/dim]")


def info(message: str, badge: bool = False):
    """Info message
    
    Args:
        message: Info message
        badge: Show CX badge (default: True)
    """
    prefix = f"{BADGE} [dim]│[/dim] " if badge else ""
    console.print(f"{prefix}{message}")


def section(title: str, style: str = "bold cyan"):
    """Section header
    
    Args:
        title: Section title
        style: Rich style string (default: "bold cyan")
    """
    console.print()
    console.print(f"[{style}]━━━ {title} ━━━[/{style}]")
    console.print()


# ============================================================================
# SPINNER
# ============================================================================

@contextmanager
def spinner(message: str, spinner_style: str = "dots"):
    """Context manager for showing spinner during long operations [web:15]
    
    Args:
        message: Message to display with spinner
        spinner_style: Spinner animation style (default: "dots")
        
    Usage:
        with spinner("Installing packages..."):
            do_work()
    """
    status = console.status(f"[bold cyan]{message}[/bold cyan]", spinner=spinner_style)
    status.start()
    try:
        yield status
    finally:
        status.stop()


# ============================================================================
# BOXES AND PANELS
# ============================================================================

def status_box(
    title: str,
    items: dict[str, str],
    border_color: str = DEFAULT_BORDER_COLOR,
    width: Optional[int] = DEFAULT_PANEL_WIDTH,
    fit: bool = False,
    padding: tuple[int, int] = (1, 2)
):
    """Display a boxed status with key-value pairs
    
    Args:
        title: Box title
        items: Dictionary of key-value pairs to display
        border_color: Border color (default: cyan)
        width: Fixed width in characters (default: 70), ignored if fit=True
        fit: Auto-fit to content width (default: False)
        padding: Tuple of (vertical, horizontal) padding
        
    Example:
        status_box(
            "CORTEX ML SCHEDULER",
            {
                "Status": "● Active",
                "Uptime": "0.5 seconds"
            }
        )
    """
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="dim", no_wrap=True)
    table.add_column("Value", style="white")

    for key, value in items.items():
        table.add_row(f"{key}:", value)

    if fit:
        panel = Panel.fit(
            table,
            title=f"[bold]{title}[/bold]",
            border_style=border_color,
            padding=padding
        )
    else:
        panel = Panel(
            table,
            title=f"[bold]{title}[/bold]",
            border_style=border_color,
            padding=padding,
            expand=False,
            width=width
        )

    console.print(panel)

def text_box(
    title: str,
    content: str,
    border_color: str = DEFAULT_BORDER_COLOR,
    padding: tuple[int, int] = (1, 2),
):
    """Display free-form text inside a framed panel"""
    panel = Panel(
        content,
        title=f"[bold]{title}[/bold]",
        border_style=border_color,
        padding=padding,
    )
    console.print(panel)

def summary_box(
    title: str,
    items: list[str],
    success: bool = True,
    border_color: Optional[str] = None
):
    """Summary box for operation completion [web:11]
    
    Args:
        title: Summary title
        items: List of items to display
        success: Whether operation succeeded (affects color/icon)
        border_color: Optional override for border color
        
    Example:
        summary_box(
            "INSTALLATION COMPLETE",
            ["nginx 1.18.0", "docker 24.0.5"],
            success=True
        )
    """
    color = border_color or ("green" if success else "red")
    icon = "✓" if success else "✗"

    content = f"[{color}]{icon}[/{color}] {title}\n\n"
    for item in items:
        content += f"  • {item}\n"

    panel = Panel(content, border_style=color, padding=(1, 2),expand=False)
    console.print(panel)


# ============================================================================
# TABLES
# ============================================================================

def data_table(
    columns: list[dict[str, Any]],
    rows: list[list[Any]],
    title: Optional[str] = None,
    show_header: bool = True,
    border_style: str = "dim",
    title_style: str = "bold",
    expand: bool = False
) -> Table:
    """Create and display a data table [web:11]
    
    Args:
        columns: List of column dicts with 'name', optional 'style', 'justify', 'width'
        rows: List of row data (list of values matching column order)
        title: Optional table title
        show_header: Show column headers (default: True)
        border_style: Border style (default: "dim")
        title_style: Title style (default: "bold")
        expand: Expand to full terminal width (default: False)
        
    Returns:
        The created Table object
        
    Example:
        data_table(
            columns=[
                {"name": "Stack", "style": "cyan"},
                {"name": "Description", "style": "white"},
                {"name": "Packages", "justify": "center", "style": "dim"}
            ],
            rows=[
                ["ml", "PyTorch, CUDA, Jupyter", "6"],
                ["webdev", "Node, npm, nginx", "4"]
            ],
            title="📦 Available Stacks"
        )
    """
    table = Table(
        title=title,
        show_header=show_header,
        border_style=border_style,
        title_style=title_style,
        expand=expand,
        padding=(0, 1)
    )
    
    # Add columns with their configurations
    for col in columns:
        table.add_column(
            col["name"],
            style=col.get("style", "white"),
            justify=col.get("justify", "left"),
            no_wrap=col.get("no_wrap", False),
            width=col.get("width")
        )
    
    # Add rows
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
    
    console.print()
    console.print(table)
    console.print()
    
    return table


def compact_list(
    items: list[dict[str, str]],
    title: Optional[str] = None,
    columns_count: int = 2,
    equal: bool = True
):
    """Display items in a compact multi-column layout
    
    Args:
        items: List of dicts with 'title', 'content', optional 'border_color'
        title: Optional section title
        columns_count: Number of columns (default: 2)
        equal: Make columns equal width (default: True)
        
    Example:
        compact_list(
            items=[
                {"title": "ML Stack", "content": "PyTorch, CUDA\\n6 packages", "border_color": "green"},
                {"title": "Web Stack", "content": "Node, npm\\n4 packages", "border_color": "blue"}
            ],
            title="Available Stacks",
            columns_count=2
        )
    """
    if title:
        section(title)
    
    panels = []
    for item in items:
        panel = Panel(
            item["content"],
            title=f"[bold]{item['title']}[/bold]",
            border_style=item.get("border_color", DEFAULT_BORDER_COLOR),
            expand=False
        )
        panels.append(panel)
    
    console.print(Columns(panels, equal=equal, expand=True))
    console.print()


# ============================================================================
# PROGRESS BARS
# ============================================================================

@contextmanager
def progress_bar(transient: bool = False):
    """Context manager for progress bar operations [web:11]
    
    Args:
        transient: Remove progress bar after completion (default: False)
        
    Usage:
        with progress_bar() as progress:
            task = progress.add_task("Downloading...", total=100)
            for i in range(100):
                progress.update(task, advance=1)
    """
    prog = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=transient
    )
    prog.start()
    try:
        yield prog
    finally:
        prog.stop()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_newline(count: int = 1):
    """Print one or more blank lines"""
    for _ in range(count):
        console.print()


def clear():
    """Clear the console"""
    console.clear()


def rule(title: str = "", style: str = "dim"):
    """Print a horizontal rule with optional title
    
    Args:
        title: Optional centered title
        style: Rule style (default: "dim")
    """
    from rich.rule import Rule
    console.print(Rule(title, style=style))
