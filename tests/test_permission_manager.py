import os
from unittest.mock import MagicMock, patch

import pytest

from cortex.permission_manager import PermissionManager


@pytest.fixture
def manager():
    """Create a permission manager instance with fixed host IDs for consistency."""
    # We use create=True because getuid/getgid do not exist on Windows.
    # This allows the test suite to run on any OS while simulating a Linux environment.
    with (
        patch("os.getuid", create=True, return_value=1000),
        patch("os.getgid", create=True, return_value=1000),
    ):
        return PermissionManager(os.path.normpath("/dummy/path"))


def test_diagnose_finds_mismatched_uids(manager):
    """Confirm the tool identifies files not owned by the host (UID 1000)."""
    with (
        patch("cortex.permission_manager.os.walk") as mock_walk,
        patch("cortex.permission_manager.os.stat") as mock_stat,
    ):
        base = os.path.normpath("/dummy/path")
        # File 1: Owned by root (0) - Should be flagged
        # File 2: Owned by host (1000) - Should be ignored
        mock_walk.return_value = [(base, [], ["root_file.txt", "user_file.txt"])]

        root_stat = MagicMock()
        root_stat.st_uid = 0

        user_stat = MagicMock()
        user_stat.st_uid = 1000

        mock_stat.side_effect = [root_stat, user_stat]

        results = manager.diagnose()

        # Only the root-owned file should be in the list
        assert len(results) == 1
        assert os.path.join(base, "root_file.txt") in results


def test_check_compose_config_generates_settings(manager):
    """Confirm the tool generates the correct YAML snippet for the host user."""
    with (
        patch("cortex.permission_manager.os.path.exists", return_value=True),
        patch(
            "builtins.open",
            MagicMock(
                return_value=MagicMock(__enter__=lambda s: MagicMock(read=lambda: "services: {}"))
            ),
        ),
        patch("cortex.permission_manager.console.print") as mock_console,
    ):
        manager.check_compose_config()

        # Check that the output contains the specific generated mapping for UID 1000
        mock_console.assert_called()
        combined_output = "".join([str(call.args[0]) for call in mock_console.call_args_list])

        assert "user:" in combined_output
        assert "1000:1000" in combined_output  # Verifies Requirement #4


@patch("cortex.permission_manager.subprocess.run")
@patch("cortex.permission_manager.platform.system", return_value="Linux")
def test_fix_permissions_uses_manager_ids(mock_platform, mock_run, manager):
    """Confirm the repair command uses the IDs detected during manager initialization."""
    test_file = os.path.normpath("/path/to/locked_file.txt")

    # We use the manager created by the fixture (already set to host 1000)
    success = manager.fix_permissions([test_file])

    assert success is True
    # Verify the chown command uses the cached 1000:1000 IDs
    mock_run.assert_called_once_with(
        ["sudo", "chown", "1000:1000", test_file], check=True, capture_output=True, timeout=60
    )
