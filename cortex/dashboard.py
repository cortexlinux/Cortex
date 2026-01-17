#!/usr/bin/env python3
"""
Interactive TUI Dashboard for Cortex Linux

Issue: #244 - Interactive TUI Dashboard

Live-updating terminal dashboard showing system status, resources,
running processes, and quick actions.
"""

import logging
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class SystemResources:
    """Current system resource usage."""

    cpu_percent: float = 0.0
    cpu_cores: int = 1
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_percent: float = 0.0
    gpu_name: str = ""
    gpu_memory_used_mb: int = 0
    gpu_memory_total_mb: int = 0
    gpu_utilization: float = 0.0
    gpu_available: bool = False


@dataclass
class ProcessInfo:
    """Information about a running process."""

    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    status: str


@dataclass
class HistoryEntry:
    """A command history entry."""

    timestamp: str
    command: str
    status: str


class ResourceMonitor:
    """Monitors system resources."""

    def __init__(self):
        self._psutil_available = False
        self._pynvml_available = False
        self._nvml_initialized = False
        self._init_libraries()

    def _init_libraries(self):
        """Initialize optional libraries."""
        try:
            import psutil

            self._psutil = psutil
            self._psutil_available = True
        except ImportError:
            logger.debug("psutil not available, using fallback")
            self._psutil = None

        try:
            import pynvml

            pynvml.nvmlInit()
            self._pynvml = pynvml
            self._pynvml_available = True
            self._nvml_initialized = True
        except Exception:
            logger.debug("pynvml not available or no NVIDIA GPU")
            self._pynvml = None

    def get_resources(self) -> SystemResources:
        """Get current system resource usage."""
        resources = SystemResources()

        # CPU info
        if self._psutil_available:
            resources.cpu_percent = self._psutil.cpu_percent(interval=0.1)
            resources.cpu_cores = self._psutil.cpu_count() or 1
        else:
            resources.cpu_percent = self._get_cpu_fallback()
            resources.cpu_cores = os.cpu_count() or 1

        # Memory info
        if self._psutil_available:
            mem = self._psutil.virtual_memory()
            resources.memory_total_gb = mem.total / (1024**3)
            resources.memory_used_gb = mem.used / (1024**3)
            resources.memory_percent = mem.percent
        else:
            resources.memory_total_gb, resources.memory_used_gb = self._get_memory_fallback()
            if resources.memory_total_gb > 0:
                resources.memory_percent = (
                    resources.memory_used_gb / resources.memory_total_gb
                ) * 100

        # GPU info
        if self._pynvml_available and self._nvml_initialized:
            try:
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)
                resources.gpu_name = self._pynvml.nvmlDeviceGetName(handle)
                if isinstance(resources.gpu_name, bytes):
                    resources.gpu_name = resources.gpu_name.decode("utf-8")

                mem_info = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                resources.gpu_memory_total_mb = mem_info.total // (1024**2)
                resources.gpu_memory_used_mb = mem_info.used // (1024**2)

                util = self._pynvml.nvmlDeviceGetUtilizationRates(handle)
                resources.gpu_utilization = util.gpu
                resources.gpu_available = True
            except Exception as e:
                logger.debug(f"GPU info error: {e}")
        else:
            # Try nvidia-smi fallback
            gpu_info = self._get_gpu_fallback()
            if gpu_info:
                resources.gpu_name = gpu_info.get("name", "")
                resources.gpu_memory_total_mb = gpu_info.get("total_mb", 0)
                resources.gpu_memory_used_mb = gpu_info.get("used_mb", 0)
                resources.gpu_utilization = gpu_info.get("utilization", 0)
                resources.gpu_available = True

        return resources

    def _get_cpu_fallback(self) -> float:
        """Get CPU usage without psutil."""
        try:
            result = subprocess.run(
                ["grep", "cpu", "/proc/stat"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if lines:
                    parts = lines[0].split()
                    if len(parts) >= 5:
                        idle = int(parts[4])
                        total = sum(int(p) for p in parts[1:])
                        if total > 0:
                            return round((1 - idle / total) * 100, 1)
        except Exception:
            pass
        return 0.0

    def _get_memory_fallback(self) -> tuple[float, float]:
        """Get memory info without psutil."""
        try:
            result = subprocess.run(
                ["free", "-b"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 3:
                            total = int(parts[1]) / (1024**3)
                            used = int(parts[2]) / (1024**3)
                            return (total, used)
        except Exception:
            pass
        return (0.0, 0.0)

    def _get_gpu_fallback(self) -> dict | None:
        """Get GPU info using nvidia-smi."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 4:
                    return {
                        "name": parts[0].strip(),
                        "total_mb": int(parts[1].strip()),
                        "used_mb": int(parts[2].strip()),
                        "utilization": float(parts[3].strip()),
                    }
        except Exception:
            pass
        return None

    def get_processes(self, limit: int = 5) -> list[ProcessInfo]:
        """Get top processes by CPU usage."""
        processes = []

        if self._psutil_available:
            try:
                for proc in self._psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
                    try:
                        info = proc.info
                        processes.append(
                            ProcessInfo(
                                pid=info["pid"],
                                name=info["name"][:20] if info["name"] else "unknown",
                                cpu_percent=info["cpu_percent"] or 0,
                                memory_mb=(info["memory_info"].rss / (1024**2))
                                if info["memory_info"]
                                else 0,
                                status="running",
                            )
                        )
                    except (self._psutil.NoSuchProcess, self._psutil.AccessDenied):
                        pass
                processes.sort(key=lambda p: p.cpu_percent, reverse=True)
            except Exception as e:
                logger.debug(f"Process list error: {e}")

        return processes[:limit]

    def cleanup(self):
        """Cleanup resources."""
        if self._nvml_initialized and self._pynvml:
            try:
                self._pynvml.nvmlShutdown()
            except Exception:
                pass


class HistoryManager:
    """Manages command history."""

    def __init__(self, db_path: str = "/var/lib/cortex/history.db"):
        self.db_path = Path(db_path)
        # Fallback to user directory if system path not accessible
        if not self.db_path.parent.exists():
            self.db_path = Path.home() / ".cortex" / "history.db"

    def get_recent(self, limit: int = 5) -> list[HistoryEntry]:
        """Get recent command history."""
        entries = []

        if not self.db_path.exists():
            return entries

        try:
            import sqlite3

            conn = sqlite3.connect(str(self.db_path), timeout=2)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT timestamp, packages, status
                FROM installations
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )

            for row in cursor.fetchall():
                entries.append(
                    HistoryEntry(
                        timestamp=row[0][:16] if row[0] else "",
                        command=row[1][:30] if row[1] else "",
                        status=row[2] if row[2] else "unknown",
                    )
                )
            conn.close()
        except Exception as e:
            logger.debug(f"History read error: {e}")

        return entries


class Dashboard:
    """Interactive TUI Dashboard."""

    def __init__(self):
        self.monitor = ResourceMonitor()
        self.history = HistoryManager()
        self.running = False
        self.refresh_interval = 1.0
        self._action_callback: Callable[[str], None] | None = None

    def _create_header(self) -> Panel:
        """Create header panel."""
        hostname = platform.node() or "localhost"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header_text = Text()
        header_text.append("🧠 ", style="bold blue")
        header_text.append("CORTEX", style="bold cyan")
        header_text.append(" Dashboard", style="white")
        header_text.append(f"  │  {hostname}", style="dim")
        header_text.append(f"  │  {now}", style="dim")

        return Panel(header_text, style="blue", height=3)

    def _create_resource_bars(self, resources: SystemResources) -> Panel:
        """Create resource usage bars."""
        table = Table.grid(expand=True)
        table.add_column("Label", width=12)
        table.add_column("Bar", ratio=1)
        table.add_column("Value", width=15, justify="right")

        # CPU bar
        cpu_color = "green" if resources.cpu_percent < 60 else "yellow" if resources.cpu_percent < 85 else "red"
        cpu_bar = self._make_bar(resources.cpu_percent, cpu_color)
        table.add_row(
            Text("CPU", style="bold"),
            cpu_bar,
            f"{resources.cpu_percent:.1f}% ({resources.cpu_cores} cores)",
        )

        # Memory bar
        mem_color = "green" if resources.memory_percent < 70 else "yellow" if resources.memory_percent < 90 else "red"
        mem_bar = self._make_bar(resources.memory_percent, mem_color)
        table.add_row(
            Text("Memory", style="bold"),
            mem_bar,
            f"{resources.memory_used_gb:.1f}/{resources.memory_total_gb:.1f} GB",
        )

        # GPU bar (if available)
        if resources.gpu_available:
            gpu_mem_percent = (
                (resources.gpu_memory_used_mb / resources.gpu_memory_total_mb * 100)
                if resources.gpu_memory_total_mb > 0
                else 0
            )
            gpu_color = "green" if resources.gpu_utilization < 60 else "yellow" if resources.gpu_utilization < 85 else "red"
            gpu_bar = self._make_bar(resources.gpu_utilization, gpu_color)
            table.add_row(
                Text("GPU", style="bold"),
                gpu_bar,
                f"{resources.gpu_utilization:.0f}% ({resources.gpu_name[:15]})",
            )

            gpu_mem_bar = self._make_bar(gpu_mem_percent, gpu_color)
            table.add_row(
                Text("GPU Mem", style="bold"),
                gpu_mem_bar,
                f"{resources.gpu_memory_used_mb}/{resources.gpu_memory_total_mb} MB",
            )
        else:
            table.add_row(
                Text("GPU", style="bold dim"),
                Text("No GPU detected", style="dim"),
                "",
            )

        return Panel(table, title="[bold]System Resources[/bold]", border_style="green")

    def _make_bar(self, percent: float, color: str) -> Text:
        """Create a text-based progress bar."""
        width = 30
        filled = int(width * min(percent, 100) / 100)
        empty = width - filled

        bar = Text()
        bar.append("█" * filled, style=color)
        bar.append("░" * empty, style="dim")
        return bar

    def _create_process_panel(self, processes: list[ProcessInfo]) -> Panel:
        """Create process list panel."""
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("PID", width=8)
        table.add_column("Name", ratio=1)
        table.add_column("CPU%", width=8, justify="right")
        table.add_column("MEM", width=10, justify="right")

        for proc in processes[:5]:
            cpu_style = "red" if proc.cpu_percent > 50 else "yellow" if proc.cpu_percent > 20 else "white"
            table.add_row(
                str(proc.pid),
                proc.name,
                Text(f"{proc.cpu_percent:.1f}%", style=cpu_style),
                f"{proc.memory_mb:.0f} MB",
            )

        if not processes:
            table.add_row("--", "No processes found", "--", "--")

        return Panel(table, title="[bold]Top Processes[/bold]", border_style="yellow")

    def _create_history_panel(self, entries: list[HistoryEntry]) -> Panel:
        """Create command history panel."""
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Time", width=16)
        table.add_column("Command", ratio=1)
        table.add_column("Status", width=10)

        for entry in entries[:5]:
            status_style = "green" if entry.status == "success" else "red" if entry.status == "failed" else "yellow"
            table.add_row(
                entry.timestamp,
                entry.command,
                Text(entry.status, style=status_style),
            )

        if not entries:
            table.add_row("--", "No history yet", "--")

        return Panel(table, title="[bold]Recent Commands[/bold]", border_style="magenta")

    def _create_actions_panel(self) -> Panel:
        """Create quick actions panel."""
        actions = Table.grid(expand=True)
        actions.add_column(ratio=1)

        shortcuts = [
            ("[bold cyan]i[/bold cyan]", "Install package"),
            ("[bold cyan]b[/bold cyan]", "Run benchmark"),
            ("[bold cyan]d[/bold cyan]", "Run doctor"),
            ("[bold cyan]s[/bold cyan]", "System status"),
            ("[bold cyan]h[/bold cyan]", "View history"),
            ("[bold red]q[/bold red]", "Quit dashboard"),
        ]

        shortcut_text = "  ".join([f"{key} {desc}" for key, desc in shortcuts])
        actions.add_row(shortcut_text)

        return Panel(actions, title="[bold]Quick Actions[/bold]", border_style="cyan", height=4)

    def _create_layout(self, resources: SystemResources) -> Layout:
        """Create the dashboard layout."""
        layout = Layout()

        # Get data
        processes = self.monitor.get_processes(5)
        history = self.history.get_recent(5)

        # Create layout structure
        layout.split_column(
            Layout(self._create_header(), name="header", size=3),
            Layout(name="main"),
            Layout(self._create_actions_panel(), name="actions", size=4),
        )

        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )

        layout["left"].split_column(
            Layout(self._create_resource_bars(resources), name="resources"),
            Layout(self._create_process_panel(processes), name="processes"),
        )

        layout["right"].split_column(
            Layout(self._create_history_panel(history), name="history"),
            Layout(self._create_model_panel(), name="models"),
        )

        return layout

    def _create_model_panel(self) -> Panel:
        """Create loaded models panel."""
        table = Table(show_header=True, header_style="bold blue", expand=True)
        table.add_column("Model", ratio=1)
        table.add_column("Size", width=10)
        table.add_column("Status", width=10)

        # Check for ollama models
        models = self._get_loaded_models()

        for model in models[:4]:
            table.add_row(
                model.get("name", "unknown")[:25],
                model.get("size", ""),
                Text(model.get("status", ""), style="green"),
            )

        if not models:
            table.add_row("No models loaded", "--", "--")

        return Panel(table, title="[bold]Loaded Models[/bold]", border_style="blue")

    def _get_loaded_models(self) -> list[dict]:
        """Get list of loaded AI models."""
        models = []

        # Check ollama
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")[1:]  # Skip header
                for line in lines[:4]:
                    parts = line.split()
                    if parts:
                        models.append({
                            "name": parts[0],
                            "size": parts[2] if len(parts) > 2 else "",
                            "status": "ready",
                        })
        except Exception:
            pass

        return models

    def run(self):
        """Run the dashboard."""
        self.running = True

        # Handle Ctrl+C gracefully
        def signal_handler(sig, frame):
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)

        console.clear()

        try:
            with Live(
                self._create_layout(self.monitor.get_resources()),
                console=console,
                refresh_per_second=1,
                screen=True,
            ) as live:
                while self.running:
                    # Check for keyboard input (non-blocking)
                    if self._check_input():
                        break

                    # Update display
                    resources = self.monitor.get_resources()
                    live.update(self._create_layout(resources))

                    time.sleep(self.refresh_interval)

        except KeyboardInterrupt:
            pass
        finally:
            self.monitor.cleanup()
            console.clear()
            console.print("[green]Dashboard closed.[/green]")

    def _check_input(self) -> bool:
        """Check for keyboard input. Returns True if should quit."""
        try:
            import select
            import termios
            import tty

            # Check if input is available
            if select.select([sys.stdin], [], [], 0)[0]:
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setraw(sys.stdin.fileno())
                    char = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

                if char.lower() == "q":
                    return True
                elif char.lower() == "i":
                    self._handle_action("install")
                elif char.lower() == "b":
                    self._handle_action("benchmark")
                elif char.lower() == "d":
                    self._handle_action("doctor")
                elif char.lower() == "s":
                    self._handle_action("status")
                elif char.lower() == "h":
                    self._handle_action("history")

        except Exception:
            # Fallback for systems without termios
            pass

        return False

    def _handle_action(self, action: str):
        """Handle a quick action."""
        self.running = False
        console.clear()

        if action == "install":
            console.print("[cyan]Launching install mode...[/cyan]")
            console.print("Run: [bold]cortex install <package>[/bold]")
        elif action == "benchmark":
            console.print("[cyan]Running benchmark...[/cyan]")
            os.system("cortex benchmark")
        elif action == "doctor":
            console.print("[cyan]Running doctor...[/cyan]")
            os.system("cortex doctor")
        elif action == "status":
            console.print("[cyan]Showing status...[/cyan]")
            os.system("cortex status")
        elif action == "history":
            console.print("[cyan]Showing history...[/cyan]")
            os.system("cortex history")


def run_dashboard(verbose: bool = False) -> int:
    """Run the interactive dashboard.

    Args:
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success)
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    dashboard = Dashboard()
    dashboard.run()
    return 0


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cortex Interactive Dashboard")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()
    exit(run_dashboard(verbose=args.verbose))
