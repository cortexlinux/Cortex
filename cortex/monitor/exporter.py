"""
Metrics Exporter for Cortex Monitor

Exports monitoring data to JSON and CSV formats.

Author: Cortex Linux Team
SPDX-License-Identifier: BUSL-1.1
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from cortex.monitor.sampler import PeakUsage, ResourceSample

logger = logging.getLogger(__name__)


def export_samples(
    samples: list[ResourceSample],
    filepath: str,
    peak: PeakUsage | None = None,
    metadata: dict | None = None,
) -> None:
    """
    Export monitoring samples to a file.

    Args:
        samples: List of ResourceSample objects
        filepath: Output file path (.json or .csv)
        peak: Optional peak usage statistics
        metadata: Optional metadata dict to include

    Raises:
        ValueError: If file format is not supported
    """
    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".json":
        _export_json(samples, filepath, peak, metadata)
    elif suffix == ".csv":
        _export_csv(samples, filepath, peak, metadata)
    else:
        # Default to JSON if no extension
        if not suffix:
            filepath = filepath + ".json"
            _export_json(samples, filepath, peak, metadata)
        else:
            raise ValueError(f"Unsupported export format: {suffix}. Use .json or .csv")

    logger.info(f"Exported {len(samples)} samples to {filepath}")


def _export_json(
    samples: list[ResourceSample],
    filepath: str,
    peak: PeakUsage | None = None,
    metadata: dict | None = None,
) -> None:
    """Export samples to JSON format."""
    data = {
        "metadata": {
            "exported_at": datetime.now().isoformat(),
            "sample_count": len(samples),
            "format_version": "1.0",
            **(metadata or {}),
        },
        "peak_usage": {
            "cpu_percent": peak.cpu_percent if peak else 0.0,
            "ram_percent": peak.ram_percent if peak else 0.0,
            "ram_used_gb": peak.ram_used_gb if peak else 0.0,
            "disk_read_rate_max": peak.disk_read_rate_max if peak else 0.0,
            "disk_write_rate_max": peak.disk_write_rate_max if peak else 0.0,
            "net_recv_rate_max": peak.net_recv_rate_max if peak else 0.0,
            "net_sent_rate_max": peak.net_sent_rate_max if peak else 0.0,
        },
        "samples": [
            {
                "timestamp": sample.timestamp,
                "cpu_percent": sample.cpu_percent,
                "cpu_count": sample.cpu_count,
                "ram_used_gb": round(sample.ram_used_gb, 2),
                "ram_total_gb": round(sample.ram_total_gb, 2),
                "ram_percent": round(sample.ram_percent, 1),
                "disk_used_gb": round(sample.disk_used_gb, 2),
                "disk_total_gb": round(sample.disk_total_gb, 2),
                "disk_percent": round(sample.disk_percent, 1),
                "disk_read_rate": round(sample.disk_read_rate, 2),
                "disk_write_rate": round(sample.disk_write_rate, 2),
                "net_recv_rate": round(sample.net_recv_rate, 2),
                "net_sent_rate": round(sample.net_sent_rate, 2),
            }
            for sample in samples
        ],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _export_csv(
    samples: list[ResourceSample],
    filepath: str,
    peak: PeakUsage | None = None,
    metadata: dict | None = None,
) -> None:
    """Export samples to CSV format."""
    fieldnames = [
        "timestamp",
        "cpu_percent",
        "cpu_count",
        "ram_used_gb",
        "ram_total_gb",
        "ram_percent",
        "disk_used_gb",
        "disk_total_gb",
        "disk_percent",
        "disk_read_rate",
        "disk_write_rate",
        "net_recv_rate",
        "net_sent_rate",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        # Write metadata as comments
        f.write("# Cortex Monitor Export\n")
        f.write(f"# Exported: {datetime.now().isoformat()}\n")
        f.write(f"# Samples: {len(samples)}\n")
        if peak:
            f.write(f"# Peak CPU: {peak.cpu_percent:.1f}%\n")
            f.write(f"# Peak RAM: {peak.ram_used_gb:.1f} GB ({peak.ram_percent:.1f}%)\n")
        # Write user-supplied metadata
        if metadata:
            for key, value in metadata.items():
                f.write(f"# {key}: {value}\n")
        f.write("#\n")

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for sample in samples:
            writer.writerow(
                {
                    "timestamp": sample.timestamp,
                    "cpu_percent": round(sample.cpu_percent, 1),
                    "cpu_count": sample.cpu_count,
                    "ram_used_gb": round(sample.ram_used_gb, 2),
                    "ram_total_gb": round(sample.ram_total_gb, 2),
                    "ram_percent": round(sample.ram_percent, 1),
                    "disk_used_gb": round(sample.disk_used_gb, 2),
                    "disk_total_gb": round(sample.disk_total_gb, 2),
                    "disk_percent": round(sample.disk_percent, 1),
                    "disk_read_rate": round(sample.disk_read_rate, 2),
                    "disk_write_rate": round(sample.disk_write_rate, 2),
                    "net_recv_rate": round(sample.net_recv_rate, 2),
                    "net_sent_rate": round(sample.net_sent_rate, 2),
                }
            )
