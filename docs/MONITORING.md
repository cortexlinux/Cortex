# System Resource Monitoring

Cortex includes built-in system resource monitoring to help track CPU, RAM, disk, and network usage during package installations or as a standalone diagnostic tool.

## Overview

| Capability | Description |
|------------|-------------|
| **CPU Monitoring** | Real-time CPU utilization percentage across all cores |
| **RAM Monitoring** | Memory usage in GB and percentage of total |
| **Disk Monitoring** | Disk space usage and I/O read/write rates |
| **Network Monitoring** | Network throughput (receive/send rates) |
| **Historical Storage** | SQLite-backed session storage in `~/.cortex/history.db` |
| **Rule-Based Analysis** | Automatic warnings and recommendations based on thresholds |
| **Export** | JSON and CSV export formats for external analysis |

---

## CLI Usage

### Standalone Monitoring

Run the monitor independently to observe system resources in real-time:

```bash
# Monitor for 30 seconds with live TUI display
cortex monitor --duration 30

# Monitor with custom sampling interval (default: 1 second)
cortex monitor --duration 60 --interval 0.5
```

### Exporting Metrics

Export collected metrics to JSON or CSV for analysis:

```bash
# Export to JSON
cortex monitor --duration 60 --export metrics.json

# Export to CSV
cortex monitor --duration 60 --export metrics.csv

# Export without extension defaults to JSON
cortex monitor --duration 30 --export report
```

### Install-Time Monitoring

Monitor resource usage during package installation:

```bash
# Preview commands with monitoring enabled (dry-run, no metrics collected)
cortex install nginx --monitor

# Actually install and collect peak usage metrics
cortex install nginx --monitor --execute
```

> **Note:** `cortex install` defaults to dry-run mode. Use `--execute` to run commands and capture peak resource usage.

---

## Install-Time Monitoring Behavior

When using `--monitor` with `cortex install`, monitoring runs **in the background**:

- **No live TUI**: Install-time monitoring does not display a real-time dashboard
- **Peak capture**: Records peak CPU, RAM, and I/O values during installation
- **Summary display**: Shows a summary after installation completes
- **Non-intrusive**: Does not interfere with installation output or prompts

### Design Rationale

This design ensures:
1. Installation output remains readable and uncluttered
2. No interference with interactive prompts or progress bars
3. Minimal performance overhead during critical operations
4. Clean terminal experience while still capturing useful metrics

---

## Fallback Behavior

Cortex monitoring degrades gracefully when dependencies are unavailable:

### psutil Unavailable

If `psutil` is not installed:
- Monitoring commands will log a warning and exit cleanly
- No crash or error trace
- Install with: `pip install psutil>=6.1.0`

### rich Unavailable

If `rich` is not installed:
- Falls back to simple text-based output
- Metrics still collected and exportable
- Install with: `pip install rich>=13.0.0`

### Non-TTY Environments

When output is piped or redirected (e.g., `cortex monitor | tee log.txt`):
- Automatically switches to line-based output
- No ANSI escape codes or cursor movements
- Progress updates written as simple text lines

---

## Collected Metrics

Each sample includes:

| Metric | Unit | Description |
|--------|------|-------------|
| `cpu_percent` | % | System-wide CPU utilization |
| `cpu_count` | count | Number of logical CPUs |
| `ram_used_gb` | GB | Memory in use |
| `ram_total_gb` | GB | Total system memory |
| `ram_percent` | % | Memory utilization |
| `disk_used_gb` | GB | Disk space used (root partition) |
| `disk_total_gb` | GB | Total disk capacity |
| `disk_percent` | % | Disk utilization |
| `disk_read_rate` | bytes/s | Disk read throughput |
| `disk_write_rate` | bytes/s | Disk write throughput |
| `net_recv_rate` | bytes/s | Network receive throughput |
| `net_sent_rate` | bytes/s | Network send throughput |

---

## Alert Thresholds

Default thresholds for warnings and critical alerts:

| Resource | Warning | Critical |
|----------|---------|----------|
| CPU | 80% | 95% |
| RAM | 80% | 95% |
| Disk | 90% | 95% |

When thresholds are exceeded, the analyzer provides actionable recommendations.

---

## Non-Goals

The following are **intentionally not included** in this implementation:

| Non-Goal | Rationale |
|----------|-----------|
| **Per-process monitoring** | Adds complexity; system-wide metrics are sufficient for install tracking |
| **GPU monitoring** | Optional dependency; available via separate dashboard feature |
| **Automatic install cancellation** | Too risky; users should make abort decisions |
| **Daemon-based monitoring** | Out of scope; this is client-side tooling only |

---

## Related Documentation

- [Commands Reference](COMMANDS.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Graceful Degradation](GRACEFUL_DEGRADATION.md)
