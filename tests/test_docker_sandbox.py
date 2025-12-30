#!/usr/bin/env python3
"""
Tests for Docker-based Package Sandbox Testing Environment.

Tests cover:
- DockerSandbox class methods (create, install, test, promote, cleanup)
- Docker detection and error handling
- CLI integration
- Edge cases and error conditions
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cortex.sandbox.docker_sandbox import (
    DockerNotFoundError,
    DockerSandbox,
    SandboxAlreadyExistsError,
    SandboxExecutionResult,
    SandboxInfo,
    SandboxNotFoundError,
    SandboxState,
    SandboxTestResult,
    SandboxTestStatus,
    docker_available,
)


class TestDockerDetection(unittest.TestCase):
    """Tests for Docker availability detection."""

    @patch("shutil.which")
    def test_docker_not_installed(self, mock_which):
        """Test detection when Docker is not installed."""
        mock_which.return_value = None
        sandbox = DockerSandbox()
        self.assertFalse(sandbox.check_docker())

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_docker_installed_but_not_running(self, mock_run, mock_which):
        """Test detection when Docker is installed but daemon not running."""
        mock_which.return_value = "/usr/bin/docker"
        # First call (--version) succeeds
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Docker version 24.0.0"),
            Mock(returncode=1, stderr="Cannot connect to Docker daemon"),
        ]
        sandbox = DockerSandbox()
        self.assertFalse(sandbox.check_docker())

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_docker_available(self, mock_run, mock_which):
        """Test detection when Docker is fully available."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0, stdout="Docker info")
        sandbox = DockerSandbox()
        self.assertTrue(sandbox.check_docker())

    @patch("shutil.which")
    def test_require_docker_raises_when_not_found(self, mock_which):
        """Test require_docker raises DockerNotFoundError when not installed."""
        mock_which.return_value = None
        sandbox = DockerSandbox()
        with self.assertRaises(DockerNotFoundError) as ctx:
            sandbox.require_docker()
        self.assertIn("Docker is required", str(ctx.exception))

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_require_docker_raises_when_daemon_not_running(self, mock_run, mock_which):
        """Test require_docker raises when daemon not running."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=1, stderr="Cannot connect")
        sandbox = DockerSandbox()
        with self.assertRaises(DockerNotFoundError) as ctx:
            sandbox.require_docker()
        self.assertIn("not running", str(ctx.exception))


class TestSandboxCreate(unittest.TestCase):
    """Tests for sandbox creation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "sandboxes"

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_create_sandbox_success(self, mock_run, mock_which):
        """Test successful sandbox creation."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123def456",
            stderr="",
        )

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.create("test-env")

        self.assertTrue(result.success)
        self.assertIn("test-env", result.message)

        # Verify metadata was saved
        metadata_path = self.data_dir / "test-env.json"
        self.assertTrue(metadata_path.exists())

        with open(metadata_path) as f:
            data = json.load(f)
        self.assertEqual(data["name"], "test-env")
        self.assertEqual(data["state"], "running")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_create_sandbox_already_exists(self, mock_run, mock_which):
        """Test error when sandbox already exists."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0, stdout="abc123")

        sandbox = DockerSandbox(data_dir=self.data_dir)

        # Create first sandbox
        sandbox.create("test-env")

        # Try to create again
        with self.assertRaises(SandboxAlreadyExistsError):
            sandbox.create("test-env")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_create_sandbox_with_custom_image(self, mock_run, mock_which):
        """Test sandbox creation with custom image."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0, stdout="abc123")

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.create("test-env", image="debian:12")

        self.assertTrue(result.success)

        # Verify image in metadata
        info = sandbox.get_sandbox("test-env")
        self.assertEqual(info.image, "debian:12")


class TestSandboxInstall(unittest.TestCase):
    """Tests for package installation in sandbox."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "sandboxes"
        self.data_dir.mkdir(parents=True)

        # Create mock sandbox metadata
        metadata = {
            "name": "test-env",
            "container_id": "abc123",
            "state": "running",
            "created_at": "2024-01-01T00:00:00",
            "image": "ubuntu:22.04",
            "packages": [],
        }
        with open(self.data_dir / "test-env.json", "w") as f:
            json.dump(metadata, f)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_install_package_success(self, mock_run, mock_which):
        """Test successful package installation."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.install("test-env", "nginx")

        self.assertTrue(result.success)
        self.assertIn("nginx", result.packages_installed)

        # Verify package added to metadata
        info = sandbox.get_sandbox("test-env")
        self.assertIn("nginx", info.packages)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_install_package_failure(self, mock_run, mock_which):
        """Test package installation failure."""
        mock_which.return_value = "/usr/bin/docker"
        # First call is docker info (require_docker), second is apt install
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Docker info", stderr=""),  # docker info
            Mock(returncode=100, stdout="", stderr="E: Unable to locate package nonexistent"),
        ]

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.install("test-env", "nonexistent-package")

        self.assertFalse(result.success)
        self.assertIn("Failed to install", result.message)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_install_sandbox_not_found(self, mock_run, mock_which):
        """Test installation in non-existent sandbox."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0, stdout="Docker info", stderr="")  # docker info

        sandbox = DockerSandbox(data_dir=self.data_dir)

        with self.assertRaises(SandboxNotFoundError):
            sandbox.install("nonexistent", "nginx")


class TestSandboxTest(unittest.TestCase):
    """Tests for sandbox testing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "sandboxes"
        self.data_dir.mkdir(parents=True)

        # Create mock sandbox with packages
        metadata = {
            "name": "test-env",
            "container_id": "abc123",
            "state": "running",
            "created_at": "2024-01-01T00:00:00",
            "image": "ubuntu:22.04",
            "packages": ["nginx"],
        }
        with open(self.data_dir / "test-env.json", "w") as f:
            json.dump(metadata, f)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_test_all_pass(self, mock_run, mock_which):
        """Test when all tests pass."""
        mock_which.return_value = "/usr/bin/docker"

        # Mock responses for: which, --version, dpkg --audit
        mock_run.side_effect = [
            Mock(returncode=0, stdout="/usr/bin/docker"),  # docker info
            Mock(returncode=0, stdout="/usr/sbin/nginx"),  # which nginx
            Mock(returncode=0, stdout="nginx version: 1.18"),  # nginx --version
            Mock(returncode=0, stdout=""),  # dpkg --audit
        ]

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.test("test-env")

        self.assertTrue(result.success)
        self.assertTrue(len(result.test_results) > 0)

        # Check that at least one test passed
        passed_tests = [t for t in result.test_results if t.result == SandboxTestStatus.PASSED]
        self.assertTrue(len(passed_tests) > 0)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_test_no_packages(self, mock_run, mock_which):
        """Test when no packages installed."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0)

        # Create sandbox with no packages
        metadata = {
            "name": "empty-env",
            "container_id": "abc123",
            "state": "running",
            "created_at": "2024-01-01T00:00:00",
            "image": "ubuntu:22.04",
            "packages": [],
        }
        with open(self.data_dir / "empty-env.json", "w") as f:
            json.dump(metadata, f)

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.test("empty-env")

        self.assertTrue(result.success)
        self.assertEqual(len(result.test_results), 0)


class TestSandboxPromote(unittest.TestCase):
    """Tests for package promotion to main system."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "sandboxes"
        self.data_dir.mkdir(parents=True)

        # Create mock sandbox with packages
        metadata = {
            "name": "test-env",
            "container_id": "abc123",
            "state": "running",
            "created_at": "2024-01-01T00:00:00",
            "image": "ubuntu:22.04",
            "packages": ["nginx"],
        }
        with open(self.data_dir / "test-env.json", "w") as f:
            json.dump(metadata, f)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("subprocess.run")
    def test_promote_dry_run(self, mock_run):
        """Test promotion in dry-run mode."""
        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.promote("test-env", "nginx", dry_run=True)

        self.assertTrue(result.success)
        self.assertIn("Would run", result.message)
        # subprocess.run should not be called for dry run (except docker check)
        # Actually it won't be called at all since we're not checking docker in promote

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_promote_package_not_in_sandbox(self, mock_run, mock_which):
        """Test promotion of package not installed in sandbox."""
        mock_which.return_value = "/usr/bin/docker"

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.promote("test-env", "redis", dry_run=False)

        self.assertFalse(result.success)
        self.assertIn("not installed in sandbox", result.message)

    @patch("subprocess.run")
    def test_promote_success(self, mock_run):
        """Test successful promotion."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.promote("test-env", "nginx", dry_run=False)

        self.assertTrue(result.success)
        self.assertIn("nginx", result.packages_installed)

        # Verify correct command was run on HOST
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, ["sudo", "apt-get", "install", "-y", "nginx"])


class TestSandboxCleanup(unittest.TestCase):
    """Tests for sandbox cleanup."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "sandboxes"
        self.data_dir.mkdir(parents=True)

        metadata = {
            "name": "test-env",
            "container_id": "abc123",
            "state": "running",
            "created_at": "2024-01-01T00:00:00",
            "image": "ubuntu:22.04",
            "packages": [],
        }
        with open(self.data_dir / "test-env.json", "w") as f:
            json.dump(metadata, f)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_cleanup_success(self, mock_run, mock_which):
        """Test successful cleanup."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.cleanup("test-env")

        self.assertTrue(result.success)
        self.assertIn("removed", result.message)

        # Verify metadata was deleted
        metadata_path = self.data_dir / "test-env.json"
        self.assertFalse(metadata_path.exists())

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_cleanup_force(self, mock_run, mock_which):
        """Test force cleanup."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0)

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.cleanup("test-env", force=True)

        self.assertTrue(result.success)


class TestSandboxList(unittest.TestCase):
    """Tests for listing sandboxes."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "sandboxes"
        self.data_dir.mkdir(parents=True)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_empty(self):
        """Test listing when no sandboxes exist."""
        sandbox = DockerSandbox(data_dir=self.data_dir)
        sandboxes = sandbox.list_sandboxes()
        self.assertEqual(len(sandboxes), 0)

    def test_list_multiple(self):
        """Test listing multiple sandboxes."""
        # Create multiple sandbox metadata files
        for name in ["env1", "env2", "env3"]:
            metadata = {
                "name": name,
                "container_id": f"abc{name}",
                "state": "running",
                "created_at": "2024-01-01T00:00:00",
                "image": "ubuntu:22.04",
                "packages": [],
            }
            with open(self.data_dir / f"{name}.json", "w") as f:
                json.dump(metadata, f)

        sandbox = DockerSandbox(data_dir=self.data_dir)
        sandboxes = sandbox.list_sandboxes()

        self.assertEqual(len(sandboxes), 3)
        names = {s.name for s in sandboxes}
        self.assertEqual(names, {"env1", "env2", "env3"})


class TestSandboxExec(unittest.TestCase):
    """Tests for command execution in sandbox."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "sandboxes"
        self.data_dir.mkdir(parents=True)

        metadata = {
            "name": "test-env",
            "container_id": "abc123",
            "state": "running",
            "created_at": "2024-01-01T00:00:00",
            "image": "ubuntu:22.04",
            "packages": [],
        }
        with open(self.data_dir / "test-env.json", "w") as f:
            json.dump(metadata, f)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_exec_success(self, mock_run, mock_which):
        """Test successful command execution."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0, stdout="Hello\n", stderr="")

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.exec_command("test-env", ["echo", "Hello"])

        self.assertTrue(result.success)
        self.assertIn("Hello", result.stdout)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_exec_blocked_command(self, mock_run, mock_which):
        """Test blocked command is rejected."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0)

        sandbox = DockerSandbox(data_dir=self.data_dir)
        result = sandbox.exec_command("test-env", ["systemctl", "start", "nginx"])

        self.assertFalse(result.success)
        self.assertIn("not supported", result.message)


class TestSandboxCompatibility(unittest.TestCase):
    """Tests for command compatibility checking."""

    def test_allowed_commands(self):
        """Test that normal commands are allowed."""
        is_compat, reason = DockerSandbox.is_sandbox_compatible("apt install nginx")
        self.assertTrue(is_compat)

        is_compat, reason = DockerSandbox.is_sandbox_compatible("nginx --version")
        self.assertTrue(is_compat)

    def test_blocked_commands(self):
        """Test that blocked commands are rejected."""
        is_compat, reason = DockerSandbox.is_sandbox_compatible("systemctl start nginx")
        self.assertFalse(is_compat)
        self.assertIn("systemctl", reason)

        is_compat, reason = DockerSandbox.is_sandbox_compatible("sudo service nginx restart")
        self.assertFalse(is_compat)

        is_compat, reason = DockerSandbox.is_sandbox_compatible("modprobe loop")
        self.assertFalse(is_compat)


class TestSandboxInfo(unittest.TestCase):
    """Tests for SandboxInfo data class."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        info = SandboxInfo(
            name="test",
            container_id="abc123",
            state=SandboxState.RUNNING,
            created_at="2024-01-01T00:00:00",
            image="ubuntu:22.04",
            packages=["nginx", "redis"],
        )
        data = info.to_dict()

        self.assertEqual(data["name"], "test")
        self.assertEqual(data["state"], "running")
        self.assertEqual(data["packages"], ["nginx", "redis"])

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "name": "test",
            "container_id": "abc123",
            "state": "running",
            "created_at": "2024-01-01T00:00:00",
            "image": "ubuntu:22.04",
            "packages": ["nginx"],
        }
        info = SandboxInfo.from_dict(data)

        self.assertEqual(info.name, "test")
        self.assertEqual(info.state, SandboxState.RUNNING)
        self.assertIn("nginx", info.packages)


class TestDockerAvailableFunction(unittest.TestCase):
    """Tests for docker_available() convenience function."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_docker_available_true(self, mock_run, mock_which):
        """Test when Docker is available."""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0)
        self.assertTrue(docker_available())

    @patch("shutil.which")
    def test_docker_available_false(self, mock_which):
        """Test when Docker is not available."""
        mock_which.return_value = None
        self.assertFalse(docker_available())


if __name__ == "__main__":
    unittest.main()
