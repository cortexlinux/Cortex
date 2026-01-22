"""
Monitor UI for Cortex Monitor

Real-time terminal UI using rich.Live for system resource monitoring.
Follows patterns from cortex/dashboard.py.

Author: Cortex Linux Team
SPDX-License-Identifier: BUSL-1.1
"""

import logging
import sys
import time
from datetime import datetime

from cortex.monitor.sampler import AlertThresholds, PeakUsage, ResourceSample, ResourceSampler

logger = logging.getLogger(__name__)

# Try to import rich components
try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# UI Constants
BAR_WIDTH = 30
# Note: Color thresholds are derived from AlertThresholds in _create_bar()
# to maintain single source of truth for alert configuration.


class MonitorUI:
    """
    Real-time system monitoring UI using rich.Live.

    Displays CPU, RAM, Disk, and Network metrics with progress bars
    and alerts. Handles Ctrl+C gracefully.

    Example:
        sampler = ResourceSampler(interval=1.0)
        ui = MonitorUI(sampler)
        ui.run(duration=30)  # Run for 30 seconds
    """

    def __init__(
        self,
        sampler: ResourceSampler,
        alert_thresholds: AlertThresholds | None = None,
        console: "Console | None" = None,
    ):
        """
        Initialize the monitor UI.

        Args:
            sampler: ResourceSampler instance to get metrics from
            alert_thresholds: Optional custom alert thresholds
            console: Optional rich Console (creates new one if None)
        """
        self.sampler = sampler
        self.thresholds = alert_thresholds or AlertThresholds()
        # Sync thresholds to ensure alerts match UI colors
        self.sampler.thresholds = self.thresholds
        self.console = console or (Console() if RICH_AVAILABLE else None)

        self._running = False
        self._start_time: float | None = None
        self._alerts: list[str] = []

    def run(self, duration: int | None = None) -> PeakUsage:
        """
        Run the monitoring UI.

        Args:
            duration: Optional duration in seconds (None = run until Ctrl+C)

        Returns:
            PeakUsage statistics from the monitoring session
        """
        if not RICH_AVAILABLE:
            return self._run_fallback(duration)

        # Fall back to simple output for non-TTY environments (piped output)
        if not sys.stdout.isatty():
            return self._run_fallback(duration)

        self._running = True
        self._start_time = time.time()
        self._alerts = []

        # Start the sampler
        self.sampler.start()

        try:
            with Live(
                self._render(),
                console=self.console,
                refresh_per_second=2,
                screen=False,
            ) as live:
                while self._running:
                    # Check duration limit
                    if duration is not None and (time.time() - self._start_time) >= duration:
                        break

                    # Update display
                    live.update(self._render())

                    # Small sleep to prevent busy loop
                    time.sleep(0.1)

        except KeyboardInterrupt:
            self.console.print("\n[dim]Monitoring stopped by user[/dim]")
        finally:
            self.sampler.stop()
            self._running = False

        # Show summary
        peak = self.sampler.get_peak_usage()
        self._show_summary(peak)

        return peak

    def _run_fallback(self, duration: int | None = None) -> PeakUsage:
        """Fallback for non-TTY or when rich is unavailable."""
        self._running = True
        self._start_time = time.time()

        self.sampler.start()
        print("Cortex Monitor (non-TTY mode)")
        print("Press Ctrl+C to stop\n")

        try:
            while self._running:
                if duration is not None and (time.time() - self._start_time) >= duration:
                    break

                sample = self.sampler.get_latest_sample()
                if sample:
                    elapsed = time.time() - self._start_time
                    sys.stdout.write(
                        f"\r[{elapsed:.0f}s] "
                        f"CPU: {sample.cpu_percent:.0f}% | "
                        f"RAM: {sample.ram_used_gb:.1f}/{sample.ram_total_gb:.1f}GB | "
                        f"Disk: {sample.disk_percent:.0f}%"
                    )
                    sys.stdout.flush()

                time.sleep(1.0)

        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        finally:
            self.sampler.stop()
            self._running = False

        print()
        peak = self.sampler.get_peak_usage()
        print(f"Peak: CPU {peak.cpu_percent:.0f}%, RAM {peak.ram_used_gb:.1f}GB")
        return peak

    def _render(self) -> Panel:
        """Render the complete monitoring panel."""
        sample = self.sampler.get_latest_sample()

        # Build content
        content_parts = []

        # Header with time
        elapsed = time.time() - self._start_time if self._start_time else 0
        header = Text()
        header.append("🖥️  System Monitor", style="bold cyan")
        header.append(f"  •  {datetime.now().strftime('%H:%M:%S')}", style="dim")
        header.append(f"  •  {elapsed:.0f}s elapsed", style="dim")
        content_parts.append(header)
        content_parts.append(Text())  # Spacer

        if sample:
            # CPU
            cpu_bar = self._create_bar("CPU", sample.cpu_percent, sample.cpu_count, metric="cpu")
            content_parts.append(cpu_bar)

            # RAM
            ram_bar = self._create_bar(
                "RAM",
                sample.ram_percent,
                suffix=f"{sample.ram_used_gb:.1f}/{sample.ram_total_gb:.1f} GB",
                metric="ram",
            )
            content_parts.append(ram_bar)

            # Disk
            disk_bar = self._create_bar(
                "Disk",
                sample.disk_percent,
                suffix=f"{sample.disk_used_gb:.0f}/{sample.disk_total_gb:.0f} GB",
                metric="disk",
            )
            content_parts.append(disk_bar)

            content_parts.append(Text())  # Spacer

            # I/O Table
            io_table = self._create_io_table(sample)
            content_parts.append(io_table)

            # Alerts
            alerts = self.sampler.check_alerts(sample)
            if alerts:
                content_parts.append(Text())
                for alert in alerts:
                    content_parts.append(Text(alert, style="yellow"))
        else:
            content_parts.append(Text("Collecting metrics...", style="dim"))

        return Panel(
            Group(*content_parts),
            title="[bold]Cortex Monitor[/bold]",
            subtitle="[dim]Press Ctrl+C to stop[/dim]",
            border_style="blue",
        )

    def _create_bar(
        self,
        label: str,
        percent: float,
        cores: int | None = None,
        suffix: str = "",
        metric: str = "ram",
    ) -> Text:
        """Create a progress bar with label. Color derived from AlertThresholds.

        Args:
            metric: One of 'cpu', 'ram', 'disk' to select appropriate thresholds.
        """
        # Clamp percent to [0, 100] to prevent bar overflow
        percent = max(0.0, min(100.0, percent))

        # Use metric-specific thresholds
        if metric == "cpu":
            warning = self.thresholds.cpu_warning
            critical = self.thresholds.cpu_critical
        elif metric == "disk":
            warning = self.thresholds.disk_warning
            critical = self.thresholds.disk_critical
        else:  # default to RAM
            warning = self.thresholds.ram_warning
            critical = self.thresholds.ram_critical

        if percent >= critical:
            color = "red"
        elif percent >= warning:
            color = "yellow"
        else:
            color = "green"

        # Build bar with safe width calculation
        filled = int((percent / 100) * BAR_WIDTH)
        filled = min(filled, BAR_WIDTH)  # Ensure we don't exceed bar width
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)

        # Format label
        label_text = f"{label:>6}: "

        result = Text()
        result.append(label_text, style="bold")
        result.append(bar, style=color)
        result.append(f" {percent:5.1f}%", style=color)

        if cores:
            result.append(f" ({cores} cores)", style="dim")
        elif suffix:
            result.append(f" ({suffix})", style="dim")

        return result

    def _create_io_table(self, sample: ResourceSample) -> Table:
        """Create I/O statistics table."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Type", style="dim")
        table.add_column("Read/Recv", style="cyan")
        table.add_column("Write/Send", style="magenta")

        # Disk I/O
        disk_read = ResourceSampler.format_bytes_rate(sample.disk_read_rate)
        disk_write = ResourceSampler.format_bytes_rate(sample.disk_write_rate)
        table.add_row("Disk I/O:", f"↓ {disk_read}", f"↑ {disk_write}")

        # Network I/O
        net_recv = ResourceSampler.format_bytes_rate(sample.net_recv_rate)
        net_sent = ResourceSampler.format_bytes_rate(sample.net_sent_rate)
        table.add_row("Network:", f"↓ {net_recv}", f"↑ {net_sent}")

        return table

    def _show_summary(self, peak: PeakUsage) -> None:
        """Show summary after monitoring ends."""
        if not RICH_AVAILABLE or not self.console:
            return

        samples_count = self.sampler.get_sample_count()
        duration = time.time() - self._start_time if self._start_time else 0

        self.console.print()
        self.console.print("[bold]📊 Monitoring Summary[/bold]")
        self.console.print(f"   Duration: {duration:.0f} seconds")
        self.console.print(f"   Samples:  {samples_count}")
        self.console.print()
        self.console.print("[bold]Peak Usage:[/bold]")
        self.console.print(f"   CPU:  {peak.cpu_percent:.1f}%")
        self.console.print(f"   RAM:  {peak.ram_used_gb:.1f} GB ({peak.ram_percent:.1f}%)")

        if peak.disk_write_rate_max > 0:
            disk_write = ResourceSampler.format_bytes_rate(peak.disk_write_rate_max)
            self.console.print(f"   Disk Write Peak: {disk_write}")

        if peak.net_recv_rate_max > 0:
            net_recv = ResourceSampler.format_bytes_rate(peak.net_recv_rate_max)
            self.console.print(f"   Network Recv Peak: {net_recv}")

    def stop(self) -> None:
        """Stop the monitoring UI."""
        self._running = False


def run_standalone_monitor(
    duration: int | None = None,
    interval: float = 1.0,
    export_path: str | None = None,
) -> int:
    """
    Run standalone monitoring.

    Args:
        duration: Optional duration in seconds
        interval: Sampling interval in seconds
        export_path: Optional path to export metrics

    Returns:
        Exit code (0 for success)
    """
    sampler = ResourceSampler(interval=interval)
    ui = MonitorUI(sampler)

    try:
        peak = ui.run(duration=duration)

        # Export if requested
        if export_path:
            try:
                from cortex.monitor.exporter import export_samples

                samples = sampler.get_samples()
                # Resolve the actual export path (exporter may add extension)
                actual_path = export_path
                if not export_path.endswith((".json", ".csv")):
                    actual_path = export_path + ".json"
                export_samples(samples, actual_path, peak)
                if RICH_AVAILABLE and ui.console:
                    ui.console.print(f"[green]✓[/green] Metrics exported to {actual_path}")
            except Exception as e:
                logger.error(f"Export failed: {e}")
                return 1

        return 0

    except Exception as e:
        logger.error(f"Monitor error: {e}")
        return 1
