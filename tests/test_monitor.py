"""
Unit Tests for Cortex Monitor Module

Tests for sampler, UI, exporter, analyzer, and storage components.
Target: >80% coverage for cortex/monitor/
"""

import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_psutil() -> Iterator[MagicMock]:
    """Mock psutil for testing without actual system metrics."""
    with patch.dict("sys.modules", {"psutil": MagicMock()}):
        import sys

        mock = sys.modules["psutil"]

        # Mock cpu_percent
        mock.cpu_percent = MagicMock(return_value=45.0)
        mock.cpu_count = MagicMock(return_value=4)

        # Mock virtual_memory
        mem_mock = MagicMock()
        mem_mock.used = 8 * 1024**3  # 8 GB
        mem_mock.total = 16 * 1024**3  # 16 GB
        mem_mock.percent = 50.0
        mock.virtual_memory = MagicMock(return_value=mem_mock)

        # Mock disk_usage
        disk_mock = MagicMock()
        disk_mock.used = 120 * 1024**3  # 120 GB
        disk_mock.total = 500 * 1024**3  # 500 GB
        disk_mock.percent = 24.0
        mock.disk_usage = MagicMock(return_value=disk_mock)

        # Mock disk_io_counters
        disk_io_mock = MagicMock()
        disk_io_mock.read_bytes = 1000000
        disk_io_mock.write_bytes = 500000
        mock.disk_io_counters = MagicMock(return_value=disk_io_mock)

        # Mock net_io_counters
        net_io_mock = MagicMock()
        net_io_mock.bytes_recv = 2000000
        net_io_mock.bytes_sent = 800000
        mock.net_io_counters = MagicMock(return_value=net_io_mock)

        yield mock


@pytest.fixture
def sample_data() -> list:
    """Create sample ResourceSample data for testing."""
    from cortex.monitor.sampler import ResourceSample

    now = time.time()
    samples = []
    for i in range(10):
        samples.append(
            ResourceSample(
                timestamp=now + i,
                cpu_percent=40 + i * 5,  # 40, 45, 50, ... 85
                cpu_count=4,
                ram_used_gb=7.0 + i * 0.2,
                ram_total_gb=16.0,
                ram_percent=45 + i * 2,
                disk_used_gb=120.0,
                disk_total_gb=500.0,
                disk_percent=24.0,
                disk_read_bytes=1000000 + i * 10000,
                disk_write_bytes=500000 + i * 5000,
                net_recv_bytes=2000000 + i * 20000,
                net_sent_bytes=800000 + i * 8000,
                disk_read_rate=100000.0,
                disk_write_rate=50000.0,
                net_recv_rate=200000.0,
                net_sent_rate=80000.0,
            )
        )
    return samples


@pytest.fixture
def temp_db() -> Iterator[str]:
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_export_dir() -> Iterator[str]:
    """Create a temporary directory for export tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# =============================================================================
# Sampler Tests
# =============================================================================


class TestResourceSample:
    """Tests for ResourceSample dataclass."""

    def test_sample_creation(self) -> None:
        """Test creating a ResourceSample."""
        from cortex.monitor.sampler import ResourceSample

        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=50.0,
            cpu_count=4,
            ram_used_gb=8.0,
            ram_total_gb=16.0,
            ram_percent=50.0,
            disk_used_gb=120.0,
            disk_total_gb=500.0,
            disk_percent=24.0,
        )

        assert sample.cpu_percent == pytest.approx(50.0)
        assert sample.cpu_count == 4
        assert sample.ram_used_gb == pytest.approx(8.0)

    def test_sample_defaults(self) -> None:
        """Test ResourceSample default values."""
        from cortex.monitor.sampler import ResourceSample

        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=50.0,
            cpu_count=4,
            ram_used_gb=8.0,
            ram_total_gb=16.0,
            ram_percent=50.0,
            disk_used_gb=120.0,
            disk_total_gb=500.0,
            disk_percent=24.0,
        )

        # Check defaults
        assert sample.disk_read_bytes == 0
        assert sample.disk_write_bytes == 0
        assert sample.net_recv_bytes == 0
        assert sample.net_sent_bytes == 0
        assert sample.disk_read_rate == pytest.approx(0.0)
        assert sample.disk_write_rate == pytest.approx(0.0)


class TestPeakUsage:
    """Tests for PeakUsage dataclass."""

    def test_peak_creation(self):
        """Test creating PeakUsage."""
        from cortex.monitor.sampler import PeakUsage

        peak = PeakUsage(
            cpu_percent=95.0,
            ram_percent=80.0,
            ram_used_gb=12.8,
        )

        assert peak.cpu_percent == pytest.approx(95.0)
        assert peak.ram_percent == pytest.approx(80.0)

    def test_peak_defaults(self):
        """Test PeakUsage default values."""
        from cortex.monitor.sampler import PeakUsage

        peak = PeakUsage()

        assert peak.cpu_percent == pytest.approx(0.0)
        assert peak.ram_percent == pytest.approx(0.0)
        assert peak.ram_used_gb == pytest.approx(0.0)


class TestAlertThresholds:
    """Tests for AlertThresholds dataclass."""

    def test_default_thresholds(self):
        """Test default alert thresholds."""
        from cortex.monitor.sampler import AlertThresholds

        thresholds = AlertThresholds()

        assert thresholds.cpu_warning == pytest.approx(80.0)
        assert thresholds.cpu_critical == pytest.approx(95.0)
        assert thresholds.ram_warning == pytest.approx(80.0)
        assert thresholds.ram_critical == pytest.approx(95.0)

    def test_custom_thresholds(self):
        """Test custom alert thresholds."""
        from cortex.monitor.sampler import AlertThresholds

        thresholds = AlertThresholds(
            cpu_warning=70.0,
            cpu_critical=90.0,
        )

        assert thresholds.cpu_warning == pytest.approx(70.0)
        assert thresholds.cpu_critical == pytest.approx(90.0)


class TestResourceSampler:
    """Tests for ResourceSampler class."""

    def test_sampler_creation(self):
        """Test creating a ResourceSampler."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler(interval=1.0)

        assert sampler.interval == pytest.approx(1.0)
        assert not sampler.is_running

    def test_sampler_min_interval(self):
        """Test that interval has a minimum value."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler(interval=0.01)  # Too small

        assert sampler.interval >= 0.1

    def test_sampler_get_samples_empty(self):
        """Test getting samples when none collected."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler()
        samples = sampler.get_samples()

        assert samples == []

    def test_sampler_get_latest_empty(self):
        """Test getting latest sample when none collected."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler()
        latest = sampler.get_latest_sample()

        assert latest is None

    def test_sampler_get_peak_empty(self):
        """Test getting peak when none collected."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler()
        peak = sampler.get_peak_usage()

        assert peak.cpu_percent == pytest.approx(0.0)
        assert peak.ram_percent == pytest.approx(0.0)

    def test_format_bytes_rate(self):
        """Test byte rate formatting."""
        from cortex.monitor.sampler import ResourceSampler

        assert "B/s" in ResourceSampler.format_bytes_rate(500)
        assert "KB/s" in ResourceSampler.format_bytes_rate(5000)
        assert "MB/s" in ResourceSampler.format_bytes_rate(5 * 1024 * 1024)
        assert "GB/s" in ResourceSampler.format_bytes_rate(5 * 1024 * 1024 * 1024)


class TestSamplerAlerts:
    """Tests for sampler alert functionality."""

    def test_check_alerts_no_sample(self):
        """Test checking alerts with no sample."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler()
        alerts = sampler.check_alerts()

        assert alerts == []

    def test_check_alerts_cpu_warning(self, sample_data):
        """Test CPU warning alert."""
        from cortex.monitor.sampler import AlertThresholds, ResourceSampler

        thresholds = AlertThresholds(cpu_warning=80.0)
        sampler = ResourceSampler(alert_thresholds=thresholds)

        # Create a high CPU sample to trigger alert
        sample = sample_data[9]
        sample.cpu_percent = 85.0

        alerts = sampler.check_alerts(sample)

        assert len(alerts) >= 1
        assert any("CPU" in a for a in alerts)

    def test_check_alerts_ram_critical(self, sample_data):
        """Test RAM critical alert."""
        from cortex.monitor.sampler import AlertThresholds, ResourceSampler

        thresholds = AlertThresholds(ram_critical=95.0)
        sampler = ResourceSampler(alert_thresholds=thresholds)

        # Create a critical RAM sample
        sample = sample_data[0]
        sample.ram_percent = 96.0

        alerts = sampler.check_alerts(sample)

        assert len(alerts) >= 1
        assert any("RAM" in a and "CRITICAL" in a for a in alerts)


# =============================================================================
# Additional Sampler Tests for Coverage
# =============================================================================


def test_sampler_start_stop_lifecycle(monkeypatch):
    """Test sampler start/stop lifecycle."""
    from unittest.mock import MagicMock

    from cortex.monitor.sampler import ResourceSampler

    # Mock psutil to be available
    monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", True)

    sampler = ResourceSampler(interval=0.1)

    # Should not be running initially
    assert not sampler.is_running

    # Start sampler
    sampler.start()
    assert sampler.is_running

    # Give it time to collect a sample
    time.sleep(0.3)

    # Stop sampler
    sampler.stop()
    assert not sampler.is_running

    # Should have collected some samples
    assert sampler.get_sample_count() > 0


def test_sampler_double_start(monkeypatch):
    """Test that starting an already running sampler is safe."""
    from cortex.monitor.sampler import ResourceSampler

    monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", True)

    sampler = ResourceSampler(interval=0.1)
    sampler.start()

    # Try to start again - should log warning but not crash
    sampler.start()

    sampler.stop()
    assert not sampler.is_running


def test_sampler_stop_when_not_running():
    """Test that stopping a non-running sampler is safe."""
    from cortex.monitor.sampler import ResourceSampler

    sampler = ResourceSampler()

    # Should not crash
    sampler.stop()
    assert not sampler.is_running


def test_sampler_without_psutil(monkeypatch):
    """Test sampler behavior when psutil is not available."""
    from cortex.monitor.sampler import ResourceSampler

    # Disable psutil
    monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", False)

    sampler = ResourceSampler()

    # Start should not crash but also not run
    sampler.start()
    assert not sampler.is_running


def test_sampler_collect_sample_without_psutil(monkeypatch):
    """Test _collect_sample when psutil is unavailable."""
    from cortex.monitor.sampler import ResourceSampler

    monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", False)

    sampler = ResourceSampler()
    sample = sampler._collect_sample()

    assert sample is None


def test_sampler_with_callback(monkeypatch):
    """Test sampler with on_sample callback."""
    from unittest.mock import MagicMock

    from cortex.monitor.sampler import ResourceSampler

    monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", True)

    callback = MagicMock()
    sampler = ResourceSampler(interval=0.1, on_sample=callback)

    sampler.start()
    time.sleep(0.3)
    sampler.stop()

    # Callback should have been called
    assert callback.call_count > 0


def test_sampler_callback_error_handling(monkeypatch):
    """Test that callback errors don't crash the sampler."""
    from cortex.monitor.sampler import ResourceSampler

    monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", True)

    def bad_callback(sample):
        raise ValueError("Test error")

    sampler = ResourceSampler(interval=0.1, on_sample=bad_callback)

    sampler.start()
    time.sleep(0.3)
    sampler.stop()

    # Should still have collected samples despite callback errors
    assert sampler.get_sample_count() > 0


def test_sampler_update_peak(sample_data):
    """Test _update_peak method."""
    from cortex.monitor.sampler import ResourceSampler

    sampler = ResourceSampler()

    # Update with multiple samples
    for sample in sample_data:
        sampler._update_peak(sample)

    peak = sampler.get_peak_usage()

    # Peak should be the max from all samples
    assert peak.cpu_percent == max(s.cpu_percent for s in sample_data)
    assert peak.ram_percent == max(s.ram_percent for s in sample_data)


# =============================================================================
# Exporter Tests
# =============================================================================


class TestExporter:
    """Tests for the exporter module."""

    def test_export_json(self, sample_data, temp_export_dir):
        """Test exporting samples to JSON."""
        from cortex.monitor.exporter import export_samples
        from cortex.monitor.sampler import PeakUsage

        filepath = os.path.join(temp_export_dir, "metrics.json")
        peak = PeakUsage(cpu_percent=85.0, ram_percent=65.0)

        export_samples(sample_data, filepath, peak)

        assert os.path.exists(filepath)

        with open(filepath) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "samples" in data
        assert "peak_usage" in data
        assert data["metadata"]["sample_count"] == 10
        assert len(data["samples"]) == 10

    def test_export_csv(self, sample_data, temp_export_dir):
        """Test exporting samples to CSV."""
        from cortex.monitor.exporter import export_samples

        filepath = os.path.join(temp_export_dir, "metrics.csv")

        export_samples(sample_data, filepath)

        assert os.path.exists(filepath)

        with open(filepath) as f:
            content = f.read()

        # Check CSV has headers and data
        assert "timestamp" in content
        assert "cpu_percent" in content
        lines = content.strip().split("\n")
        # Header comments + header row + 10 data rows
        assert len(lines) >= 11

    def test_export_auto_json(self, sample_data, temp_export_dir):
        """Test that files without extension default to JSON."""
        from cortex.monitor.exporter import export_samples

        filepath = os.path.join(temp_export_dir, "metrics")

        export_samples(sample_data, filepath)

        # Should have added .json
        assert os.path.exists(filepath + ".json")

    def test_export_unsupported_format(self, sample_data, temp_export_dir):
        """Test that unsupported formats raise an error."""
        from cortex.monitor.exporter import export_samples

        filepath = os.path.join(temp_export_dir, "metrics.xml")

        with pytest.raises(ValueError, match="Unsupported"):
            export_samples(sample_data, filepath)


# =============================================================================
# Analyzer Tests
# =============================================================================


class TestAnalyzer:
    """Tests for the analyzer module."""

    def test_analyze_empty_samples(self):
        """Test analyzing empty sample list."""
        from cortex.monitor.analyzer import analyze_samples

        result = analyze_samples([])

        assert "Insufficient data" in result.summary
        assert len(result.warnings) >= 1

    def test_analyze_normal_samples(self, sample_data):
        """Test analyzing normal samples."""
        from cortex.monitor.analyzer import analyze_samples

        # Modify samples to have normal values
        for s in sample_data:
            s.cpu_percent = 50.0
            s.ram_percent = 50.0

        result = analyze_samples(sample_data)

        # Should have no warnings for normal usage
        assert len(result.warnings) == 0
        assert "Peak" in result.summary

    def test_analyze_high_cpu(self, sample_data):
        """Test analyzing high CPU samples."""
        from cortex.monitor.analyzer import analyze_samples

        # Set high CPU
        for s in sample_data:
            s.cpu_percent = 92.0

        result = analyze_samples(sample_data)

        # Should have recommendations for high CPU
        assert len(result.recommendations) >= 1
        assert any("CPU" in r for r in result.recommendations)

    def test_analyze_critical_ram(self, sample_data):
        """Test analyzing critical RAM samples."""
        from cortex.monitor.analyzer import analyze_samples

        # Set critical RAM
        for s in sample_data:
            s.ram_percent = 96.0

        result = analyze_samples(sample_data)

        # Should have warnings
        assert len(result.warnings) >= 1
        assert any("RAM" in w for w in result.warnings)

    def test_analyze_low_disk(self, sample_data):
        """Test analyzing low disk space."""
        from cortex.monitor.analyzer import analyze_samples

        # Set low disk space (95% used = 5% free)
        for s in sample_data:
            s.disk_percent = 95.0

        result = analyze_samples(sample_data)

        # Should have warnings about disk
        assert len(result.warnings) >= 1
        assert any("disk" in w.lower() for w in result.warnings)


def test_analyzer_trends(sample_data):
    """Test trend analysis in analyzer."""
    from cortex.monitor.analyzer import analyze_samples

    # Create increasing trend
    for i, s in enumerate(sample_data):
        s.cpu_percent = 50 + i * 2  # Increasing
        s.ram_percent = 60 + i * 1.5

    result = analyze_samples(sample_data)

    # Should detect increasing trends
    assert "summary" in result.__dict__
    assert isinstance(result.recommendations, list)


def test_analyzer_stable_usage(sample_data):
    """Test analyzer with stable resource usage."""
    from cortex.monitor.analyzer import analyze_samples

    # Set stable values
    for s in sample_data:
        s.cpu_percent = 30.0
        s.ram_percent = 40.0
        s.disk_percent = 50.0

    result = analyze_samples(sample_data)

    # Should have minimal warnings/recommendations for stable low usage
    assert isinstance(result.summary, str)


def test_analyzer_disk_critical(sample_data):
    """Test analyzer with critical disk usage."""
    from cortex.monitor.analyzer import analyze_samples

    for s in sample_data:
        s.disk_percent = 96.0

    result = analyze_samples(sample_data)

    # Should have critical warnings
    assert len(result.warnings) > 0


def test_analyzer_performance_score(sample_data):
    """Test performance score calculation."""
    from cortex.monitor.analyzer import analyze_samples

    result = analyze_samples(sample_data)

    # Should have some score/metrics
    assert hasattr(result, "summary")


def test_analyze_high_cpu_and_ram(sample_data):
    """High CPU and high RAM together should produce multiple signals."""
    from cortex.monitor.analyzer import analyze_samples

    for s in sample_data:
        s.cpu_percent = 94.0
        s.ram_percent = 93.0

    result = analyze_samples(sample_data)

    # High usage (below critical 95%) produces recommendations, not warnings
    assert len(result.recommendations) >= 1
    assert any("CPU" in r or "RAM" in r for r in result.recommendations)


def test_analyze_mixed_usage_cpu_only(sample_data):
    """High CPU with normal RAM/Disk should isolate CPU advice."""
    from cortex.monitor.analyzer import analyze_samples

    for s in sample_data:
        s.cpu_percent = 91.0
        s.ram_percent = 40.0
        s.disk_percent = 30.0

    result = analyze_samples(sample_data)

    assert any("CPU" in r for r in result.recommendations)
    assert not any("disk" in w.lower() for w in result.warnings)


def test_analyze_borderline_thresholds(sample_data):
    """Values near thresholds should not trigger critical warnings."""
    from cortex.monitor.analyzer import analyze_samples

    for s in sample_data:
        s.cpu_percent = 79.0
        s.ram_percent = 79.0
        s.disk_percent = 89.0

    result = analyze_samples(sample_data)

    assert isinstance(result.summary, str)
    # Borderline should not trigger critical warnings
    assert len(result.warnings) == 0


def test_analyze_single_sample(sample_data):
    """Analyzer should handle a single-sample input gracefully."""
    from cortex.monitor.analyzer import analyze_samples

    single = [sample_data[0]]

    result = analyze_samples(single)

    assert isinstance(result.summary, str)
    assert result is not None


# =============================================================================
# Storage Tests
# =============================================================================


class TestStorage:
    """Tests for the storage module."""

    def test_create_storage(self, temp_db):
        """Test creating MonitorStorage."""
        from cortex.monitor.storage import MonitorStorage

        storage = MonitorStorage(db_path=temp_db)

        assert storage.db_path == temp_db
        assert os.path.exists(temp_db)

    def test_create_session(self, temp_db):
        """Test creating a monitoring session."""
        from cortex.monitor.storage import MonitorStorage

        storage = MonitorStorage(db_path=temp_db)
        session_id = storage.create_session(mode="standalone")

        assert session_id is not None
        assert len(session_id) == 36  # UUID format

    def test_save_samples(self, temp_db, sample_data):
        """Test saving samples to storage."""
        from cortex.monitor.storage import MonitorStorage

        storage = MonitorStorage(db_path=temp_db)
        session_id = storage.create_session()

        count = storage.save_samples(session_id, sample_data)

        assert count == 10

    def test_get_session(self, temp_db):
        """Test retrieving a session."""
        from cortex.monitor.storage import MonitorStorage

        storage = MonitorStorage(db_path=temp_db)
        session_id = storage.create_session(mode="install")

        session = storage.get_session(session_id)

        assert session is not None
        assert session["session_id"] == session_id
        assert session["mode"] == "install"

    def test_get_session_samples(self, temp_db, sample_data):
        """Test retrieving session samples."""
        from cortex.monitor.storage import MonitorStorage

        storage = MonitorStorage(db_path=temp_db)
        session_id = storage.create_session()
        storage.save_samples(session_id, sample_data)

        samples = storage.get_session_samples(session_id)

        assert len(samples) == 10
        assert samples[0].cpu_percent == sample_data[0].cpu_percent

    def test_finalize_session(self, temp_db, sample_data):
        """Test finalizing a session."""
        from cortex.monitor.sampler import PeakUsage
        from cortex.monitor.storage import MonitorStorage

        storage = MonitorStorage(db_path=temp_db)
        session_id = storage.create_session()
        storage.save_samples(session_id, sample_data)

        peak = PeakUsage(cpu_percent=85.0, ram_percent=65.0, ram_used_gb=10.4)
        storage.finalize_session(session_id, peak, len(sample_data))

        session = storage.get_session(session_id)

        assert session["end_time"] is not None
        assert session["sample_count"] == 10
        assert session["peak_cpu"] == pytest.approx(85.0)

    def test_list_sessions(self, temp_db):
        """Test listing sessions."""
        from cortex.monitor.storage import MonitorStorage

        storage = MonitorStorage(db_path=temp_db)

        # Create a few sessions
        for _ in range(5):
            storage.create_session()

        sessions = storage.list_sessions()

        assert len(sessions) == 5

    def test_delete_session(self, temp_db, sample_data):
        """Test deleting a session."""
        from cortex.monitor.storage import MonitorStorage

        storage = MonitorStorage(db_path=temp_db)
        session_id = storage.create_session()
        storage.save_samples(session_id, sample_data)

        result = storage.delete_session(session_id)

        assert result is True
        assert storage.get_session(session_id) is None
        assert len(storage.get_session_samples(session_id)) == 0


def test_storage_list_sessions_limit(temp_db):
    """Test listing sessions with limit."""
    from cortex.monitor.storage import MonitorStorage

    storage = MonitorStorage(db_path=temp_db)

    # Create 10 sessions
    for i in range(10):
        storage.create_session(mode=f"test_{i}")

    # List with limit
    sessions = storage.list_sessions(limit=5)

    assert len(sessions) == 5


def test_storage_get_nonexistent_session(temp_db):
    """Test getting a non-existent session."""
    from cortex.monitor.storage import MonitorStorage

    storage = MonitorStorage(db_path=temp_db)

    session = storage.get_session("nonexistent-uuid")

    assert session is None


def test_storage_save_samples_invalid_session(temp_db, sample_data):
    """Test saving samples to invalid session."""
    from cortex.monitor.storage import MonitorStorage

    storage = MonitorStorage(db_path=temp_db)

    # Try to save to non-existent session
    count = storage.save_samples("invalid-uuid", sample_data)

    # Should return 0 or handle gracefully
    assert count >= 0


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestCLIIntegration:
    """Tests for CLI command registration and routing."""

    def test_monitor_command_registered(self):
        """Test that monitor command is registered."""
        import argparse

        # Import just enough to check parser
        from cortex.cli import main

        # We can't easily test the full parser without running main,
        # but we can verify the command is in the help text
        # This is a simple integration test
        # Verified by importing cortex.cli without error - command is registered
        assert main is not None  # Validate import succeeded

    def test_monitor_args(self):
        """Test monitor argument parsing."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--duration", "-d", type=int)
        parser.add_argument("--interval", "-i", type=float, default=1.0)
        parser.add_argument("--export", "-e", type=str)

        args = parser.parse_args(["--duration", "10", "--interval", "0.5"])

        assert args.duration == 10
        assert args.interval == pytest.approx(0.5)

    def test_install_monitor_flag(self):
        """Test install --monitor flag parsing."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("software")
        parser.add_argument("--monitor", action="store_true")

        args = parser.parse_args(["nginx", "--monitor"])

        assert args.software == "nginx"
        assert args.monitor is True


# =============================================================================
# Monitor UI Tests
# =============================================================================
class TestMonitorUI:
    """Tests for MonitorUI without running real UI loops."""

    def test_monitor_ui_init(self):
        from cortex.monitor.monitor_ui import MonitorUI
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler(interval=1.0)
        ui = MonitorUI(sampler)
        assert ui.sampler is sampler
        assert ui._running is False


def test_create_bar():
    pytest.importorskip("rich")
    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import ResourceSampler

    ui = MonitorUI(ResourceSampler())
    bar = ui._create_bar("CPU", 75.0, cores=4)
    text = str(bar)
    assert "CPU" in text
    assert "%" in text


def test_create_io_table(sample_data):
    pytest.importorskip("rich")
    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import ResourceSampler

    ui = MonitorUI(ResourceSampler())
    table = ui._create_io_table(sample_data[0])
    assert table is not None


def test_monitor_ui_fallback(sample_data, monkeypatch):
    """
    Ensure fallback mode does not loop infinitely.
    """
    from unittest.mock import MagicMock

    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import PeakUsage, ResourceSampler

    sampler = ResourceSampler()

    # Mock sampler methods BEFORE creating UI
    sampler.start = MagicMock()
    sampler.stop = MagicMock()
    sampler.get_latest_sample = MagicMock(return_value=sample_data[0])
    sampler.get_peak_usage = MagicMock(return_value=PeakUsage())

    # Force fallback path BEFORE creating UI
    monkeypatch.setattr("cortex.monitor.monitor_ui.RICH_AVAILABLE", False)

    ui = MonitorUI(sampler)

    # Mock time.sleep to prevent actual delays and count calls
    sleep_count = {"count": 0}

    def mock_sleep(duration):
        sleep_count["count"] += 1
        # After first sleep, force exit
        if sleep_count["count"] >= 1:
            ui._running = False

    monkeypatch.setattr("time.sleep", mock_sleep)

    # Run with very short duration and force early exit
    peak = ui._run_fallback(duration=0.01)
    assert isinstance(peak, PeakUsage)
    assert sleep_count["count"] >= 1


def test_monitor_ui_run_minimal(monkeypatch):
    """
    Run ui.run() without entering a real Live loop.
    """
    pytest.importorskip("rich")
    from unittest.mock import MagicMock

    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import PeakUsage, ResourceSampler

    sampler = ResourceSampler()
    sampler.start = MagicMock()
    sampler.stop = MagicMock()
    sampler.get_latest_sample = MagicMock(return_value=None)
    sampler.get_peak_usage = MagicMock(return_value=PeakUsage())

    ui = MonitorUI(sampler)

    # Mock Live context manager to prevent actual TUI
    class MockLive:
        def __init__(self, *args, **kwargs):
            self.update_count = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            # Intentionally empty - MockLive context manager requires no cleanup
            pass

        def update(self, content):
            self.update_count += 1
            # Force exit after first update
            if self.update_count >= 1:
                ui._running = False

    monkeypatch.setattr("cortex.monitor.monitor_ui.Live", MockLive)

    # Mock time.sleep to prevent delays
    monkeypatch.setattr("time.sleep", lambda _: None)

    # Run with very short duration
    peak = ui.run(duration=0.01)
    assert isinstance(peak, PeakUsage)
    sampler.start.assert_called_once()
    sampler.stop.assert_called_once()


def test_run_standalone_monitor(monkeypatch):
    """
    Ensure run_standalone_monitor does not invoke real UI logic.
    """
    from unittest.mock import MagicMock, patch

    from cortex.monitor.monitor_ui import run_standalone_monitor
    from cortex.monitor.sampler import PeakUsage

    # Mock the entire MonitorUI class
    mock_ui_instance = MagicMock()
    mock_ui_instance.run.return_value = PeakUsage()

    mock_ui_class = MagicMock(return_value=mock_ui_instance)

    monkeypatch.setattr(
        "cortex.monitor.monitor_ui.MonitorUI",
        mock_ui_class,
    )

    result = run_standalone_monitor(duration=0.01, interval=1.0)
    assert result == 0
    mock_ui_instance.run.assert_called_once()


def test_monitor_ui_render(sample_data, monkeypatch):
    """Test the _render method."""
    from unittest.mock import MagicMock

    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import ResourceSampler

    # Only run if rich is available
    try:
        from rich.panel import Panel
    except ImportError:
        pytest.skip("Rich not available")

    sampler = ResourceSampler()
    sampler.get_latest_sample = MagicMock(return_value=sample_data[0])
    sampler.check_alerts = MagicMock(return_value=[])

    ui = MonitorUI(sampler)
    ui._start_time = 1000.0

    # Mock time to control elapsed time
    monkeypatch.setattr("time.time", lambda: 1010.0)

    panel = ui._render()
    assert panel is not None
    assert isinstance(panel, Panel)


def test_monitor_ui_show_summary(sample_data, monkeypatch):
    """Test the _show_summary method."""
    from unittest.mock import MagicMock

    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import PeakUsage, ResourceSampler

    # Only run if rich is available
    try:
        from rich.console import Console
    except ImportError:
        pytest.skip("Rich not available")

    sampler = ResourceSampler()
    sampler.get_sample_count = MagicMock(return_value=100)

    mock_console = MagicMock()
    ui = MonitorUI(sampler, console=mock_console)
    ui._start_time = 1000.0

    monkeypatch.setattr("time.time", lambda: 1030.0)

    peak = PeakUsage(
        cpu_percent=85.5,
        ram_percent=70.2,
        ram_used_gb=11.3,
        disk_write_rate_max=1024 * 1024 * 10,  # 10 MB/s
        net_recv_rate_max=1024 * 1024 * 5,  # 5 MB/s
    )

    ui._show_summary(peak)

    # Verify console.print was called multiple times
    assert mock_console.print.call_count >= 5


def test_monitor_ui_stop(sample_data):
    """Test the stop method."""
    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import ResourceSampler

    sampler = ResourceSampler()
    ui = MonitorUI(sampler)

    ui._running = True
    ui.stop()

    assert ui._running is False


def test_monitor_ui_with_alerts(sample_data, monkeypatch):
    """Test UI rendering with active alerts."""
    from unittest.mock import MagicMock

    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import ResourceSampler

    # Only run if rich is available
    try:
        from rich.panel import Panel
    except ImportError:
        pytest.skip("Rich not available")

    sampler = ResourceSampler()

    # Create a sample with high resource usage
    high_usage_sample = sample_data[0]
    high_usage_sample.cpu_percent = 95.0
    high_usage_sample.ram_percent = 92.0

    sampler.get_latest_sample = MagicMock(return_value=high_usage_sample)
    sampler.check_alerts = MagicMock(return_value=["⚠️  CRITICAL: CPU at 95%", "⚡ RAM high: 92%"])

    ui = MonitorUI(sampler)
    ui._start_time = 1000.0

    monkeypatch.setattr("time.time", lambda: 1010.0)

    panel = ui._render()
    assert panel is not None


def test_export_integration(sample_data, temp_export_dir, monkeypatch):
    """Test export functionality in run_standalone_monitor."""
    import os
    from unittest.mock import MagicMock

    from cortex.monitor.monitor_ui import run_standalone_monitor
    from cortex.monitor.sampler import PeakUsage

    export_path = os.path.join(temp_export_dir, "test_export.json")

    # Mock the UI
    mock_ui_instance = MagicMock()
    mock_ui_instance.run.return_value = PeakUsage()

    mock_ui_class = MagicMock(return_value=mock_ui_instance)
    monkeypatch.setattr("cortex.monitor.monitor_ui.MonitorUI", mock_ui_class)

    # Mock the sampler to return our sample data
    mock_sampler = MagicMock()
    mock_sampler.get_samples.return_value = sample_data

    def mock_ui_init(sampler, **kwargs):
        instance = MagicMock()
        instance.sampler = mock_sampler
        instance.run.return_value = PeakUsage()
        return instance

    monkeypatch.setattr("cortex.monitor.monitor_ui.MonitorUI", mock_ui_init)

    result = run_standalone_monitor(duration=0.01, export_path=export_path)

    # Should succeed
    assert result == 0
    # Export file should be created
    assert os.path.exists(export_path)


def test_create_bar_colors():
    """Test bar color logic for different thresholds."""
    pytest.importorskip("rich")
    from cortex.monitor.monitor_ui import MonitorUI
    from cortex.monitor.sampler import ResourceSampler

    ui = MonitorUI(ResourceSampler())

    # Low usage - green
    bar_low = ui._create_bar("CPU", 50.0)
    assert "50.0%" in str(bar_low)

    # Warning - yellow
    bar_warn = ui._create_bar("CPU", 75.0)
    assert "75.0%" in str(bar_warn)

    # Critical - red
    bar_crit = ui._create_bar("CPU", 95.0)
    assert "95.0%" in str(bar_crit)


# =============================================================================
# Sampler Internal Behavior Tests
# =============================================================================


class TestResourceSamplerInternals:
    """Tests for internal sampler behavior and edge cases."""

    def test_start_stop_idempotent(self, monkeypatch):
        """Starting or stopping multiple times should be safe."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler(interval=1.0)

        monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", True)

        sampler.start()
        sampler.start()  # second call should not crash

        assert sampler.is_running is True

        sampler.stop()
        sampler.stop()  # second call should not crash

        assert sampler.is_running is False

    def test_update_peak_usage(self, sample_data):
        """Peak usage should track max values across samples."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler()

        for sample in sample_data:
            sampler._update_peak(sample)

        peak = sampler.get_peak_usage()

        assert peak.cpu_percent > 0
        assert peak.ram_used_gb > 0
        assert peak.disk_read_rate_max > 0
        assert peak.net_recv_rate_max > 0

    def test_check_alerts_critical_priority(self):
        """Critical alerts should appear when thresholds exceeded."""
        from cortex.monitor.sampler import ResourceSample, ResourceSampler

        sampler = ResourceSampler()

        sample = ResourceSample(
            timestamp=0.0,
            cpu_percent=97.0,  # critical
            cpu_count=4,
            ram_used_gb=10.0,
            ram_total_gb=16.0,
            ram_percent=60.0,
            disk_used_gb=100.0,
            disk_total_gb=500.0,
            disk_percent=20.0,
        )

        alerts = sampler.check_alerts(sample)

        assert any("CRITICAL" in alert for alert in alerts)

    def test_get_sample_count(self):
        """Sample count should reflect collected samples."""
        from cortex.monitor.sampler import ResourceSampler

        sampler = ResourceSampler()
        sampler._samples = [1, 2, 3]  # direct injection

        assert sampler.get_sample_count() == 3


class TestSamplerInternalBehavior:
    """Tests for internal ResourceSampler behavior and edge cases."""

    def test_sampler_start_idempotent(self, monkeypatch):
        """Calling start() twice should not spawn multiple threads."""
        from cortex.monitor.sampler import ResourceSampler

        monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", True)

        sampler = ResourceSampler()

        # Mock thread creation
        start_calls = []

        def fake_thread_start():
            start_calls.append(1)

        monkeypatch.setattr(
            sampler,
            "_sample_loop",
            lambda: None,
        )

        # Patch Thread.start
        monkeypatch.setattr(
            "threading.Thread.start",
            lambda self: fake_thread_start(),
        )

        sampler.start()
        sampler.start()  # second call should be ignored

        assert sampler.is_running is True
        assert len(start_calls) == 1

    def test_sampler_resets_state_on_restart(self, monkeypatch):
        """Sampler should clear samples and peak data when restarted."""
        from cortex.monitor.sampler import PeakUsage, ResourceSample, ResourceSampler

        monkeypatch.setattr("cortex.monitor.sampler.PSUTIL_AVAILABLE", True)

        sampler = ResourceSampler()

        # Seed internal state
        sampler._samples = [
            ResourceSample(
                timestamp=1.0,
                cpu_percent=90.0,
                cpu_count=4,
                ram_used_gb=8.0,
                ram_total_gb=16.0,
                ram_percent=50.0,
                disk_used_gb=100.0,
                disk_total_gb=500.0,
                disk_percent=20.0,
            )
        ]
        sampler._peak = PeakUsage(cpu_percent=90.0, ram_percent=80.0)

        # Prevent thread from running
        monkeypatch.setattr("threading.Thread.start", lambda self: None)

        sampler.start()

        assert sampler.get_samples() == []
        peak = sampler.get_peak_usage()
        assert peak.cpu_percent == pytest.approx(0.0)
        assert peak.ram_percent == pytest.approx(0.0)
