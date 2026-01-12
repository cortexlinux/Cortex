"""Cortex Progress - Progress indicators and spinners."""

from typing import Optional
from contextlib import contextmanager
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from .console import console


class StepsProgress:
    def __init__(self, title: str, total: int):
        self.title = title
        self.total = total
        self.current = 0
    
    def step(self, name: str) -> None:
        self.current += 1
        console.step(name, self.current, self.total)
    
    def complete(self) -> None:
        console.success(f"{self.title} complete")


@contextmanager
def spinner(message: str):
    progress = Progress(SpinnerColumn(style="cortex"), TextColumn("[info]{task.description}[/]"), console=console.rich, transient=True)
    with progress:
        progress.add_task(message, total=None)
        yield progress


@contextmanager
def progress_bar(description: str, total: float, show_eta: bool = True):
    columns = [SpinnerColumn(style="cortex"), TextColumn("[info]{task.description}[/]"), BarColumn(bar_width=30, style="secondary", complete_style="cortex", finished_style="success"), TaskProgressColumn()]
    if show_eta:
        columns.append(TimeRemainingColumn())
    progress = Progress(*columns, console=console.rich, transient=True)
    
    with progress:
        task_id = progress.add_task(description, total=total)
        
        class ProgressWrapper:
            def advance(self, amount: float = 1):
                progress.update(task_id, advance=amount)
            def update(self, completed: float):
                progress.update(task_id, completed=completed)
        
        yield ProgressWrapper()


@contextmanager
def steps(title: str, total: int):
    tracker = StepsProgress(title, total)
    console.info(f"{title} ({total} steps)")
    try:
        yield tracker
    finally:
        if tracker.current >= tracker.total:
            tracker.complete()


def indeterminate_progress(message: str) -> Progress:
    return Progress(SpinnerColumn(style="cortex"), TextColumn("[info]{task.description}[/]"), console=console.rich, transient=True)


def download_progress(description: str, total: float) -> Progress:
    return Progress(SpinnerColumn(style="cortex"), TextColumn("[info]{task.description}[/]"), BarColumn(bar_width=30, style="secondary", complete_style="cortex", finished_style="success"), TaskProgressColumn(), "•", TimeRemainingColumn(), console=console.rich, transient=True)
