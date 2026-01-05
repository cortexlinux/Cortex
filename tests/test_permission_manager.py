import os
from unittest.mock import MagicMock, patch

import pytest

from cortex.permission_manager import PermissionManager


@pytest.fixture
def manager():
    """Fixture to initialize PermissionManager with a dummy path."""
    return PermissionManager(os.path.normpath("/dummy/path"))


def test_diagnose_finds_root_files(manager):
    """Test that diagnose correctly identifies root-owned files (UID 0)."""
    # Patching the modules where they are used in permission_manager
    with (
        patch("cortex.permission_manager.os.walk") as mock_walk,
        patch("cortex.permission_manager.os.stat") as mock_stat,
    ):

        base = os.path.normpath("/dummy/path")
        locked_file = os.path.join(base, "locked.txt")

        # Mocking a directory structure
        mock_walk.return_value = [(base, [], ["locked.txt", "normal.txt"])]

        root_stat = MagicMock()
        root_stat.st_uid = 0  # Root UID
        user_stat = MagicMock()
        user_stat.st_uid = 1000  # Normal User UID

        mock_stat.side_effect = [root_stat, user_stat]

        results = manager.diagnose()

        assert len(results) == 1
        assert os.path.normpath(locked_file) in [os.path.normpath(r) for r in results]


def test_check_compose_config_suggests_fix(manager):
    """Test that it detects missing 'user:' and prints the tip to the Rich console."""
    # Patch console.print inside permission_manager to verify output
    with (
        patch("cortex.permission_manager.os.path.exists", return_value=True),
        patch(
            "builtins.open",
            MagicMock(
                return_value=MagicMock(__enter__=lambda s: MagicMock(read=lambda: "version: '3'"))
            ),
        ),
        patch("cortex.permission_manager.console.print") as mock_console,
    ):

        manager.check_compose_config()

        # Verify the tip was printed
        mock_console.assert_called_once()
        # Verify the content of the tip
        call_args = mock_console.call_args[0][0]
        assert "user:" in call_args
        assert "docker-compose.yml" in call_args


@patch("cortex.permission_manager.subprocess.run")
@patch("cortex.permission_manager.platform.system", return_value="Linux")
def test_fix_permissions_executes_chown(mock_platform, mock_run, manager):
    """Test that fix_permissions triggers the correct sudo chown command with timeout."""
    with (
        patch("os.getuid", create=True, return_value=1000),
        patch("os.getgid", create=True, return_value=1000),
    ):

        test_file = os.path.normpath("/path/to/file1.txt")
        files = [test_file]
        success = manager.fix_permissions(files)

        assert success is True
        # Ensure chown uses correct UID:GID, flags, and the new 60s timeout
        mock_run.assert_called_once_with(
            ["sudo", "chown", "1000:1000", test_file], check=True, capture_output=True, timeout=60
        )
