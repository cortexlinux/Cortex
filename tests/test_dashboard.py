#!/usr/bin/env python3
"""
Unit tests for the dashboard module.

Tests for Interactive TUI Dashboard:
- Resource monitoring
- History management
- Layout creation
- Keyboard handling
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cortex.dashboard import (
    Dashboard,
    HistoryEntry,
    HistoryManager,
    ProcessInfo,
    ResourceMonitor,
    SystemResources,
)


class TestSystemResources(unittest.TestCase):
    """Tests for SystemResources dataclass."""

    def test_default_values(self):
        """Test default values for SystemResources."""
        resources = SystemResources()
        self.assertEqual(resources.cpu_percent, 0.0)
        self.assertEqual(resources.cpu_cores, 1)
        self.assertEqual(resources.memory_total_gb, 0.0)
        self.assertEqual(resources.memory_used_gb, 0.0)
        self.assertFalse(resources.gpu_available)

    def test_custom_values(self):
        """Test custom values for SystemResources."""
        resources = SystemResources(
            cpu_percent=75.5,
            cpu_cores=8,
            memory_total_gb=16.0,
            memory_used_gb=8.5,
            memory_percent=53.1,
            gpu_name="RTX 3080",
            gpu_memory_total_mb=10240,
            gpu_memory_used_mb=4096,
            gpu_utilization=45.0,
            gpu_available=True,
        )
        self.assertEqual(resources.cpu_percent, 75.5)
        self.assertEqual(resources.cpu_cores, 8)
        self.assertEqual(resources.gpu_name, "RTX 3080")
        self.assertTrue(resources.gpu_available)


class TestProcessInfo(unittest.TestCase):
    """Tests for ProcessInfo dataclass."""

    def test_process_creation(self):
        """Test creating a process info."""
        proc = ProcessInfo(
            pid=1234,
            name="python3",
            cpu_percent=15.5,
            memory_mb=256.0,
            status="running",
        )
        self.assertEqual(proc.pid, 1234)
        self.assertEqual(proc.name, "python3")
        self.assertEqual(proc.cpu_percent, 15.5)
        self.assertEqual(proc.status, "running")


class TestHistoryEntry(unittest.TestCase):
    """Tests for HistoryEntry dataclass."""

    def test_history_entry_creation(self):
        """Test creating a history entry."""
        entry = HistoryEntry(
            timestamp="2026-01-18 12:00",
            command="install nginx",
            status="success",
        )
        self.assertEqual(entry.timestamp, "2026-01-18 12:00")
        self.assertEqual(entry.command, "install nginx")
        self.assertEqual(entry.status, "success")


class TestResourceMonitor(unittest.TestCase):
    """Tests for ResourceMonitor class."""

    def test_init(self):
        """Test ResourceMonitor initialization."""
        monitor = ResourceMonitor()
        # Should not raise even without psutil/pynvml
        self.assertIsNotNone(monitor)

    @patch("cortex.dashboard.ResourceMonitor._get_cpu_fallback")
    @patch("cortex.dashboard.ResourceMonitor._get_memory_fallback")
    def test_get_resources_fallback(self, mock_mem, mock_cpu):
        """Test resource monitoring with fallbacks."""
        mock_cpu.return_value = 25.0
        mock_mem.return_value = (16.0, 8.0)

        monitor = ResourceMonitor()
        # Force fallback mode
        monitor._psutil_available = False
        monitor._pynvml_available = False

        resources = monitor.get_resources()

        self.assertIsInstance(resources, SystemResources)
        self.assertGreaterEqual(resources.cpu_cores, 1)

    def test_cleanup(self):
        """Test cleanup method."""
        monitor = ResourceMonitor()
        # Should not raise
        monitor.cleanup()

    @patch("subprocess.run")
    def test_get_cpu_fallback(self, mock_run):
        """Test CPU fallback method."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="cpu  1000 100 100 8000 100 0 0 0 0 0\n",
        )

        monitor = ResourceMonitor()
        cpu = monitor._get_cpu_fallback()

        # Should return a float
        self.assertIsInstance(cpu, float)

    @patch("subprocess.run")
    def test_get_memory_fallback(self, mock_run):
        """Test memory fallback method."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="              total        used        free\nMem:    17179869184  8589934592  8589934592\n",
        )

        monitor = ResourceMonitor()
        total, used = monitor._get_memory_fallback()

        self.assertIsInstance(total, float)
        self.assertIsInstance(used, float)

    @patch("subprocess.run")
    def test_get_gpu_fallback(self, mock_run):
        """Test GPU fallback method."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NVIDIA GeForce RTX 3080, 10240, 4096, 45\n",
        )

        monitor = ResourceMonitor()
        gpu_info = monitor._get_gpu_fallback()

        self.assertIsNotNone(gpu_info)
        self.assertIn("name", gpu_info)
        self.assertEqual(gpu_info["name"], "NVIDIA GeForce RTX 3080")

    @patch("subprocess.run")
    def test_get_gpu_fallback_no_nvidia(self, mock_run):
        """Test GPU fallback when nvidia-smi not available."""
        mock_run.side_effect = FileNotFoundError()

        monitor = ResourceMonitor()
        gpu_info = monitor._get_gpu_fallback()

        self.assertIsNone(gpu_info)


class TestHistoryManager(unittest.TestCase):
    """Tests for HistoryManager class."""

    def test_init_default_path(self):
        """Test HistoryManager with default path."""
        manager = HistoryManager()
        self.assertIsNotNone(manager.db_path)

    def test_init_custom_path(self):
        """Test HistoryManager with custom path."""
        manager = HistoryManager(db_path="/tmp/test_history.db")
        self.assertEqual(str(manager.db_path), "/tmp/test_history.db")

    def test_get_recent_no_db(self):
        """Test getting history when DB doesn't exist."""
        manager = HistoryManager(db_path="/nonexistent/path/history.db")
        entries = manager.get_recent()
        self.assertEqual(entries, [])

    def test_get_recent_with_db(self):
        """Test getting history from real DB."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = f.name

        try:
            import sqlite3

            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE installations (
                    timestamp TEXT,
                    packages TEXT,
                    status TEXT
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO installations (timestamp, packages, status)
                VALUES ('2026-01-18 12:00:00', 'nginx', 'success')
                """
            )
            conn.commit()
            conn.close()

            manager = HistoryManager(db_path=temp_path)
            entries = manager.get_recent()

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].command, "nginx")
            self.assertEqual(entries[0].status, "success")
        finally:
            os.unlink(temp_path)


class TestDashboard(unittest.TestCase):
    """Tests for Dashboard class."""

    def test_init(self):
        """Test Dashboard initialization."""
        dashboard = Dashboard()
        self.assertIsNotNone(dashboard.monitor)
        self.assertIsNotNone(dashboard.history)
        self.assertFalse(dashboard.running)

    def test_make_bar(self):
        """Test progress bar creation."""
        dashboard = Dashboard()

        bar_0 = dashboard._make_bar(0, "green")
        bar_50 = dashboard._make_bar(50, "yellow")
        bar_100 = dashboard._make_bar(100, "red")

        # Should return Text objects
        from rich.text import Text

        self.assertIsInstance(bar_0, Text)
        self.assertIsInstance(bar_50, Text)
        self.assertIsInstance(bar_100, Text)

    def test_create_header(self):
        """Test header panel creation."""
        dashboard = Dashboard()
        header = dashboard._create_header()

        from rich.panel import Panel

        self.assertIsInstance(header, Panel)

    def test_create_actions_panel(self):
        """Test actions panel creation."""
        dashboard = Dashboard()
        actions = dashboard._create_actions_panel()

        from rich.panel import Panel

        self.assertIsInstance(actions, Panel)

    def test_create_resource_bars(self):
        """Test resource bars panel creation."""
        dashboard = Dashboard()
        resources = SystemResources(
            cpu_percent=50.0,
            cpu_cores=4,
            memory_total_gb=16.0,
            memory_used_gb=8.0,
            memory_percent=50.0,
        )
        panel = dashboard._create_resource_bars(resources)

        from rich.panel import Panel

        self.assertIsInstance(panel, Panel)

    def test_create_resource_bars_with_gpu(self):
        """Test resource bars with GPU."""
        dashboard = Dashboard()
        resources = SystemResources(
            cpu_percent=50.0,
            cpu_cores=4,
            memory_total_gb=16.0,
            memory_used_gb=8.0,
            memory_percent=50.0,
            gpu_name="RTX 3080",
            gpu_memory_total_mb=10240,
            gpu_memory_used_mb=4096,
            gpu_utilization=45.0,
            gpu_available=True,
        )
        panel = dashboard._create_resource_bars(resources)

        from rich.panel import Panel

        self.assertIsInstance(panel, Panel)

    def test_create_process_panel_empty(self):
        """Test process panel with no processes."""
        dashboard = Dashboard()
        panel = dashboard._create_process_panel([])

        from rich.panel import Panel

        self.assertIsInstance(panel, Panel)

    def test_create_process_panel_with_processes(self):
        """Test process panel with processes."""
        dashboard = Dashboard()
        processes = [
            ProcessInfo(pid=1, name="python", cpu_percent=10, memory_mb=100, status="running"),
            ProcessInfo(pid=2, name="nginx", cpu_percent=5, memory_mb=50, status="running"),
        ]
        panel = dashboard._create_process_panel(processes)

        from rich.panel import Panel

        self.assertIsInstance(panel, Panel)

    def test_create_history_panel_empty(self):
        """Test history panel with no entries."""
        dashboard = Dashboard()
        panel = dashboard._create_history_panel([])

        from rich.panel import Panel

        self.assertIsInstance(panel, Panel)

    def test_create_history_panel_with_entries(self):
        """Test history panel with entries."""
        dashboard = Dashboard()
        entries = [
            HistoryEntry(timestamp="2026-01-18", command="install nginx", status="success"),
            HistoryEntry(timestamp="2026-01-17", command="install redis", status="failed"),
        ]
        panel = dashboard._create_history_panel(entries)

        from rich.panel import Panel

        self.assertIsInstance(panel, Panel)

    def test_create_model_panel(self):
        """Test model panel creation."""
        dashboard = Dashboard()
        panel = dashboard._create_model_panel()

        from rich.panel import Panel

        self.assertIsInstance(panel, Panel)

    @patch("cortex.dashboard.ResourceMonitor.get_resources")
    def test_create_layout(self, mock_resources):
        """Test layout creation."""
        mock_resources.return_value = SystemResources()

        dashboard = Dashboard()
        layout = dashboard._create_layout(SystemResources())

        from rich.layout import Layout

        self.assertIsInstance(layout, Layout)


class TestDashboardIntegration(unittest.TestCase):
    """Integration tests for Dashboard."""

    def test_full_dashboard_creation(self):
        """Test creating all dashboard components."""
        dashboard = Dashboard()

        # Create all panels
        resources = SystemResources(
            cpu_percent=25.0,
            cpu_cores=4,
            memory_total_gb=16.0,
            memory_used_gb=4.0,
            memory_percent=25.0,
        )

        header = dashboard._create_header()
        resource_panel = dashboard._create_resource_bars(resources)
        process_panel = dashboard._create_process_panel([])
        history_panel = dashboard._create_history_panel([])
        model_panel = dashboard._create_model_panel()
        actions_panel = dashboard._create_actions_panel()

        # All should be valid panels
        from rich.panel import Panel

        self.assertIsInstance(header, Panel)
        self.assertIsInstance(resource_panel, Panel)
        self.assertIsInstance(process_panel, Panel)
        self.assertIsInstance(history_panel, Panel)
        self.assertIsInstance(model_panel, Panel)
        self.assertIsInstance(actions_panel, Panel)


if __name__ == "__main__":
    unittest.main()
