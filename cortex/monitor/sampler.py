"""
Resource Sampler for Cortex Monitor

Thread-safe system resource sampling using psutil.
Collects CPU, RAM, Disk, and Network metrics at configurable intervals.

Important Notes:
    - All metrics are SYSTEM-WIDE, not per-process
    - Disk metrics apply to the root filesystem (/)
    - Disk and Network I/O are cumulative system totals
    - Monitoring is client-side only; daemon integration is out of scope

Author: Cortex Linux Team
SPDX-License-Identifier: BUSL-1.1
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default maximum samples to prevent unbounded memory growth.
# At 1 sample/second, 3600 samples = 1 hour of monitoring.
# Override via max_samples parameter if needed.
DEFAULT_MAX_SAMPLES = 3600

# Try to import psutil, provide fallback for testing
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None  # type: ignore


@dataclass
class ResourceSample:
    """A single snapshot of system resource usage."""

    timestamp: float
    # CPU metrics
    cpu_percent: float
    cpu_count: int
    # RAM metrics
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    # Disk metrics
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    # Network metrics
    net_recv_bytes: int = 0
    net_sent_bytes: int = 0
    # Computed I/O rates (bytes/sec, calculated from delta)
    disk_read_rate: float = 0.0
    disk_write_rate: float = 0.0
    net_recv_rate: float = 0.0
    net_sent_rate: float = 0.0


@dataclass
class PeakUsage:
    """Peak resource usage during a monitoring session."""

    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    disk_read_rate_max: float = 0.0
    disk_write_rate_max: float = 0.0
    net_recv_rate_max: float = 0.0
    net_sent_rate_max: float = 0.0


@dataclass
class AlertThresholds:
    """Configurable thresholds for resource alerts."""

    cpu_warning: float = 80.0
    cpu_critical: float = 95.0
    ram_warning: float = 80.0
    ram_critical: float = 95.0
    disk_warning: float = 90.0
    disk_critical: float = 95.0


class ResourceSampler:
    """
    Thread-safe system resource sampler.

    Collects system metrics in a background thread at configurable intervals.
    Safe to start/stop multiple times.

    Example:
        sampler = ResourceSampler(interval=1.0)
        sampler.start()
        time.sleep(5)
        sampler.stop()
        for sample in sampler.get_samples():
            print(f"CPU: {sample.cpu_percent}%")
    """

    # Bytes conversion constants
    BYTES_PER_GB = 1024**3
    BYTES_PER_MB = 1024**2

    def __init__(
        self,
        interval: float = 1.0,
        on_sample: Callable[[ResourceSample], None] | None = None,
        alert_thresholds: AlertThresholds | None = None,
        max_samples: int | None = None,
    ):
        """
        Initialize the resource sampler.

        Args:
            interval: Sampling interval in seconds (default: 1.0, min: 0.1)
            on_sample: Optional callback invoked after each sample
            alert_thresholds: Optional custom alert thresholds (single source of truth)
            max_samples: Maximum samples to retain in memory (default: 3600).
                         Oldest samples are discarded when limit is reached.
                         Set to None for unlimited (use with caution).
        """
        self.interval = max(0.1, interval)  # Minimum 100ms
        self.on_sample = on_sample
        self.thresholds = alert_thresholds or AlertThresholds()
        # Guard against negative values; None means use default, 0 means no storage
        if max_samples is None:
            self.max_samples = DEFAULT_MAX_SAMPLES
        else:
            self.max_samples = max(0, max_samples)

        # Thread synchronization
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Sample storage
        self._samples: list[ResourceSample] = []
        self._peak = PeakUsage()

        # Previous I/O counters for rate calculation
        self._prev_disk_io: tuple[int, int] | None = None
        self._prev_net_io: tuple[int, int] | None = None
        self._prev_sample_time: float | None = None

        # State
        self._running = False
        self._cpu_initialized = False

    @property
    def is_running(self) -> bool:
        """Check if the sampler is currently running."""
        return self._running

    def start(self) -> None:
        """Start the background sampling thread."""
        if self._running:
            logger.warning("Sampler already running")
            return

        if not PSUTIL_AVAILABLE:
            logger.error("psutil not available, cannot start sampler")
            return

        # Reset state for new session
        with self._lock:
            self._samples = []
            self._peak = PeakUsage()
            self._prev_disk_io = None
            self._prev_net_io = None
            self._prev_sample_time = None
            self._cpu_initialized = False

        self._stop_event.clear()
        self._running = True

        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        logger.debug(f"Sampler started with interval={self.interval}s")

    def stop(self) -> None:
        """Stop the background sampling thread."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._thread = None
        logger.debug("Sampler stopped")

    def _store_sample(self, sample: ResourceSample) -> None:
        """Store sample and update peak under lock."""
        with self._lock:
            if self.max_samples > 0:
                self._samples.append(sample)
                if len(self._samples) > self.max_samples:
                    self._samples = self._samples[-self.max_samples :]
            self._update_peak(sample)

    def _invoke_callback(self, sample: ResourceSample) -> None:
        """Invoke on_sample callback with error handling."""
        if not self.on_sample:
            return
        try:
            self.on_sample(sample)
        except Exception as e:
            logger.warning(f"on_sample callback error: {e}")

    def _sample_loop(self) -> None:
        """Background thread loop that collects samples."""
        while not self._stop_event.is_set():
            try:
                sample = self._collect_sample()
                if sample:
                    self._store_sample(sample)
                    self._invoke_callback(sample)
            except Exception as e:
                logger.error(f"Sampling error: {e}", exc_info=True)

            self._stop_event.wait(timeout=self.interval)

    def _get_disk_metrics(self) -> tuple[float, float, float]:
        """Get disk usage metrics. Returns (used_gb, total_gb, percent)."""
        try:
            disk = psutil.disk_usage("/")
            return (
                disk.used / self.BYTES_PER_GB,
                disk.total / self.BYTES_PER_GB,
                disk.percent,
            )
        except Exception:
            return 0.0, 0.0, 0.0

    def _get_io_counters(self) -> tuple[int, int, int, int]:
        """Get disk and network I/O counters. Returns (disk_read, disk_write, net_recv, net_sent)."""
        try:
            disk_io = psutil.disk_io_counters()
            disk_read = disk_io.read_bytes if disk_io else 0
            disk_write = disk_io.write_bytes if disk_io else 0
        except Exception:
            disk_read, disk_write = 0, 0

        try:
            net_io = psutil.net_io_counters()
            net_recv = net_io.bytes_recv if net_io else 0
            net_sent = net_io.bytes_sent if net_io else 0
        except Exception:
            net_recv, net_sent = 0, 0

        return disk_read, disk_write, net_recv, net_sent

    def _calculate_io_rates(
        self, now: float, disk_read: int, disk_write: int, net_recv: int, net_sent: int
    ) -> tuple[float, float, float, float]:
        """Calculate I/O rates based on previous sample. Returns (disk_read_rate, disk_write_rate, net_recv_rate, net_sent_rate)."""
        if not (self._prev_sample_time and self._prev_disk_io and self._prev_net_io):
            return 0.0, 0.0, 0.0, 0.0

        time_delta = now - self._prev_sample_time
        if time_delta <= 0:
            return 0.0, 0.0, 0.0, 0.0

        return (
            (disk_read - self._prev_disk_io[0]) / time_delta,
            (disk_write - self._prev_disk_io[1]) / time_delta,
            (net_recv - self._prev_net_io[0]) / time_delta,
            (net_sent - self._prev_net_io[1]) / time_delta,
        )

    def _collect_sample(self) -> ResourceSample | None:
        """Collect a single resource sample."""
        if not PSUTIL_AVAILABLE:
            return None

        now = time.time()

        try:
            # CPU - need to initialize first for accurate readings
            if not self._cpu_initialized:
                psutil.cpu_percent(interval=0.1)
                self._cpu_initialized = True

            cpu_percent = psutil.cpu_percent(interval=None) or 0.0
            cpu_count = psutil.cpu_count() or 1

            # RAM
            mem = psutil.virtual_memory()
            ram_used_gb = mem.used / self.BYTES_PER_GB
            ram_total_gb = mem.total / self.BYTES_PER_GB
            ram_percent = mem.percent

            # Disk and I/O metrics
            disk_used_gb, disk_total_gb, disk_percent = self._get_disk_metrics()
            disk_read, disk_write, net_recv, net_sent = self._get_io_counters()
            disk_read_rate, disk_write_rate, net_recv_rate, net_sent_rate = (
                self._calculate_io_rates(now, disk_read, disk_write, net_recv, net_sent)
            )

            # Store current values for next rate calculation
            self._prev_disk_io = (disk_read, disk_write)
            self._prev_net_io = (net_recv, net_sent)
            self._prev_sample_time = now

            return ResourceSample(
                timestamp=now,
                cpu_percent=max(0.0, min(100.0, cpu_percent)),
                cpu_count=cpu_count,
                ram_used_gb=ram_used_gb,
                ram_total_gb=ram_total_gb,
                ram_percent=max(0.0, min(100.0, ram_percent)),
                disk_used_gb=disk_used_gb,
                disk_total_gb=disk_total_gb,
                disk_percent=max(0.0, min(100.0, disk_percent)),
                disk_read_bytes=disk_read,
                disk_write_bytes=disk_write,
                net_recv_bytes=net_recv,
                net_sent_bytes=net_sent,
                disk_read_rate=max(0, disk_read_rate),
                disk_write_rate=max(0, disk_write_rate),
                net_recv_rate=max(0, net_recv_rate),
                net_sent_rate=max(0, net_sent_rate),
            )

        except Exception as e:
            logger.error(f"Failed to collect sample: {e}")
            return None

    def _update_peak(self, sample: ResourceSample) -> None:
        """Update peak usage values."""
        self._peak.cpu_percent = max(self._peak.cpu_percent, sample.cpu_percent)
        self._peak.ram_percent = max(self._peak.ram_percent, sample.ram_percent)
        self._peak.ram_used_gb = max(self._peak.ram_used_gb, sample.ram_used_gb)
        self._peak.disk_read_rate_max = max(self._peak.disk_read_rate_max, sample.disk_read_rate)
        self._peak.disk_write_rate_max = max(self._peak.disk_write_rate_max, sample.disk_write_rate)
        self._peak.net_recv_rate_max = max(self._peak.net_recv_rate_max, sample.net_recv_rate)
        self._peak.net_sent_rate_max = max(self._peak.net_sent_rate_max, sample.net_sent_rate)

    def get_samples(self) -> list[ResourceSample]:
        """Get all collected samples (thread-safe copy)."""
        with self._lock:
            return list(self._samples)

    def get_latest_sample(self) -> ResourceSample | None:
        """Get the most recent sample."""
        with self._lock:
            return self._samples[-1] if self._samples else None

    def get_peak_usage(self) -> PeakUsage:
        """Get peak usage statistics."""
        with self._lock:
            return PeakUsage(
                cpu_percent=self._peak.cpu_percent,
                ram_percent=self._peak.ram_percent,
                ram_used_gb=self._peak.ram_used_gb,
                disk_read_rate_max=self._peak.disk_read_rate_max,
                disk_write_rate_max=self._peak.disk_write_rate_max,
                net_recv_rate_max=self._peak.net_recv_rate_max,
                net_sent_rate_max=self._peak.net_sent_rate_max,
            )

    def get_sample_count(self) -> int:
        """Get the number of collected samples."""
        with self._lock:
            return len(self._samples)

    def check_alerts(self, sample: ResourceSample | None = None) -> list[str]:
        """
        Check for resource alerts based on current or provided sample.

        Returns:
            List of alert messages (empty if no alerts)
        """
        if sample is None:
            sample = self.get_latest_sample()

        if sample is None:
            return []

        alerts = []

        # CPU alerts
        if sample.cpu_percent >= self.thresholds.cpu_critical:
            alerts.append(f"⚠️  CRITICAL: CPU at {sample.cpu_percent:.0f}%")
        elif sample.cpu_percent >= self.thresholds.cpu_warning:
            alerts.append(f"⚡ CPU high: {sample.cpu_percent:.0f}%")

        # RAM alerts
        if sample.ram_percent >= self.thresholds.ram_critical:
            alerts.append(f"⚠️  CRITICAL: RAM at {sample.ram_percent:.0f}%")
        elif sample.ram_percent >= self.thresholds.ram_warning:
            alerts.append(f"⚡ RAM high: {sample.ram_percent:.0f}%")

        # Disk alerts
        if sample.disk_percent >= self.thresholds.disk_critical:
            alerts.append(f"⚠️  CRITICAL: Disk at {sample.disk_percent:.0f}%")
        elif sample.disk_percent >= self.thresholds.disk_warning:
            alerts.append(f"⚡ Disk low: {sample.disk_percent:.0f}% used")

        return alerts

    @staticmethod
    def format_bytes_rate(bytes_per_sec: float) -> str:
        """Format bytes/sec as human-readable string."""
        if bytes_per_sec >= 1024**3:
            return f"{bytes_per_sec / 1024**3:.1f} GB/s"
        elif bytes_per_sec >= 1024**2:
            return f"{bytes_per_sec / 1024**2:.1f} MB/s"
        elif bytes_per_sec >= 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_sec:.0f} B/s"
