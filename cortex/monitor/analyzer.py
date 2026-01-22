"""
Performance Analyzer for Cortex Monitor

Analyzes collected metrics and provides rule-based recommendations.

Author: Cortex Linux Team
SPDX-License-Identifier: BUSL-1.1
"""

import logging
from dataclasses import dataclass

from cortex.monitor.sampler import PeakUsage, ResourceSample

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of performance analysis."""

    recommendations: list[str]
    warnings: list[str]
    summary: str


# Threshold constants for analysis
CPU_HIGH_THRESHOLD = 80.0
CPU_CRITICAL_THRESHOLD = 95.0
RAM_HIGH_THRESHOLD = 80.0
RAM_CRITICAL_THRESHOLD = 95.0
DISK_LOW_THRESHOLD = 10.0  # Less than 10% free
DISK_IO_HIGH_THRESHOLD = 100 * 1024 * 1024  # 100 MB/s sustained


def analyze_samples(
    samples: list[ResourceSample],
    peak: PeakUsage | None = None,
) -> AnalysisResult:
    """
    Analyze collected samples and generate recommendations.

    Args:
        samples: List of ResourceSample objects
        peak: Optional pre-computed peak usage

    Returns:
        AnalysisResult with recommendations and warnings
    """
    if not samples:
        return AnalysisResult(
            recommendations=[],
            warnings=["No samples collected for analysis"],
            summary="Insufficient data for analysis",
        )

    # Compute peak if not provided
    if peak is None:
        peak = _compute_peak(samples)

    recommendations = []
    warnings = []

    # CPU Analysis
    cpu_analysis = _analyze_cpu(samples, peak)
    recommendations.extend(cpu_analysis["recommendations"])
    warnings.extend(cpu_analysis["warnings"])

    # RAM Analysis
    ram_analysis = _analyze_ram(samples, peak)
    recommendations.extend(ram_analysis["recommendations"])
    warnings.extend(ram_analysis["warnings"])

    # Disk Analysis
    disk_analysis = _analyze_disk(samples, peak)
    recommendations.extend(disk_analysis["recommendations"])
    warnings.extend(disk_analysis["warnings"])

    # Network Analysis (informational only)
    net_analysis = _analyze_network(samples, peak)
    recommendations.extend(net_analysis["recommendations"])

    # Generate summary
    summary = _generate_summary(samples, peak, len(recommendations), len(warnings))

    return AnalysisResult(
        recommendations=recommendations,
        warnings=warnings,
        summary=summary,
    )


def _compute_peak(samples: list[ResourceSample]) -> PeakUsage:
    """Compute peak usage from samples."""
    peak = PeakUsage()
    for s in samples:
        peak.cpu_percent = max(peak.cpu_percent, s.cpu_percent)
        peak.ram_percent = max(peak.ram_percent, s.ram_percent)
        peak.ram_used_gb = max(peak.ram_used_gb, s.ram_used_gb)
        peak.disk_read_rate_max = max(peak.disk_read_rate_max, s.disk_read_rate)
        peak.disk_write_rate_max = max(peak.disk_write_rate_max, s.disk_write_rate)
        peak.net_recv_rate_max = max(peak.net_recv_rate_max, s.net_recv_rate)
        peak.net_sent_rate_max = max(peak.net_sent_rate_max, s.net_sent_rate)
    return peak


def _analyze_cpu(samples: list[ResourceSample], peak: PeakUsage) -> dict[str, list[str]]:
    """Analyze CPU usage patterns."""
    recommendations = []
    warnings = []

    # Check peak CPU
    if peak.cpu_percent >= CPU_CRITICAL_THRESHOLD:
        warnings.append(f"⚠️  CPU reached critical levels ({peak.cpu_percent:.0f}%)")
        recommendations.append(
            "Consider reducing parallel build jobs (e.g., make -j2 instead of -j$(nproc))"
        )
    elif peak.cpu_percent >= CPU_HIGH_THRESHOLD:
        recommendations.append(
            f"CPU usage was high ({peak.cpu_percent:.0f}%). "
            "Consider scheduling heavy tasks during off-peak hours."
        )

    # Check sustained high CPU
    high_cpu_count = sum(1 for s in samples if s.cpu_percent >= CPU_HIGH_THRESHOLD)
    if len(samples) > 5 and high_cpu_count / len(samples) > 0.5:
        recommendations.append(
            "Sustained high CPU usage detected. Consider upgrading CPU or "
            "distributing workload across machines."
        )

    return {"recommendations": recommendations, "warnings": warnings}


def _analyze_ram(_samples: list[ResourceSample], peak: PeakUsage) -> dict[str, list[str]]:
    """Analyze RAM usage patterns."""
    recommendations = []
    warnings = []

    # Check peak RAM
    if peak.ram_percent >= RAM_CRITICAL_THRESHOLD:
        warnings.append(f"⚠️  RAM reached critical levels ({peak.ram_percent:.0f}%)")
        recommendations.append(
            "Memory pressure detected. Consider increasing RAM or enabling swap."
        )
    elif peak.ram_percent >= RAM_HIGH_THRESHOLD:
        recommendations.append(
            f"Memory usage was high ({peak.ram_percent:.0f}%). "
            "Close unused applications during installations."
        )

    # Check for potential OOM risk
    if peak.ram_percent >= 90:
        recommendations.append(
            "High memory pressure may cause OOM killer to terminate processes. "
            "Consider adding swap space as a safety buffer."
        )

    return {"recommendations": recommendations, "warnings": warnings}


def _analyze_disk(samples: list[ResourceSample], peak: PeakUsage) -> dict[str, list[str]]:
    """Analyze disk usage patterns."""
    recommendations = []
    warnings = []

    # Check disk space
    if samples:
        latest = samples[-1]
        free_percent = 100 - latest.disk_percent
        if free_percent < DISK_LOW_THRESHOLD:
            warnings.append(f"⚠️  Low disk space ({free_percent:.0f}% free)")
            recommendations.append(
                "Free up disk space before continuing installations. "
                "Run 'sudo apt autoremove' and 'sudo apt clean'."
            )

    # Check disk I/O
    if peak.disk_write_rate_max >= DISK_IO_HIGH_THRESHOLD:
        recommendations.append(
            "High disk I/O detected. Consider using an SSD for faster installations."
        )

    return {"recommendations": recommendations, "warnings": warnings}


def _analyze_network(_samples: list[ResourceSample], peak: PeakUsage) -> dict[str, list[str]]:
    """Analyze network usage patterns."""
    recommendations = []

    # High network throughput is generally fine, just informational
    if peak.net_recv_rate_max >= 50 * 1024 * 1024:  # 50 MB/s
        # This is actually good - fast downloads
        pass

    return {"recommendations": recommendations}


def _generate_summary(
    _samples: list[ResourceSample],
    peak: PeakUsage,
    rec_count: int,
    warn_count: int,
) -> str:
    """Generate analysis summary."""
    if warn_count > 0:
        status = "⚠️  Issues detected"
    elif rec_count > 0:
        status = "💡 Recommendations available"
    else:
        status = "✅ System healthy"

    return (
        f"{status} | "
        f"Peak: CPU {peak.cpu_percent:.0f}%, "
        f"RAM {peak.ram_percent:.0f}% ({peak.ram_used_gb:.1f} GB)"
    )


def _print_rich(result: AnalysisResult) -> bool:
    """Try to print using rich formatting. Returns True if successful."""
    try:
        from rich.console import Console

        console = Console()
        console.print()
        console.print(f"[bold]{result.summary}[/bold]")

        if result.warnings:
            console.print()
            console.print("[bold yellow]Warnings:[/bold yellow]")
            for warning in result.warnings:
                console.print(f"  {warning}")

        if result.recommendations:
            console.print()
            console.print("[bold cyan]Recommendations:[/bold cyan]")
            for i, rec in enumerate(result.recommendations, 1):
                console.print(f"  {i}. {rec}")

        return True
    except ImportError:
        return False


def _print_plain(result: AnalysisResult) -> None:
    """Print analysis results in plain text format."""
    print()
    print(result.summary)

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  {warning}")

    if result.recommendations:
        print("\nRecommendations:")
        for i, rec in enumerate(result.recommendations, 1):
            print(f"  {i}. {rec}")


def print_analysis(result: AnalysisResult, use_rich: bool = True) -> None:
    """
    Print analysis results to console.

    Args:
        result: AnalysisResult to print
        use_rich: Whether to use rich formatting
    """
    if use_rich and _print_rich(result):
        return
    _print_plain(result)
