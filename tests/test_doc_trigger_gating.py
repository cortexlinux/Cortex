import datetime
import json
from unittest.mock import MagicMock, patch

import pytest

from cortex.installation_history import InstallationHistory, InstallationStatus, InstallationType


@pytest.fixture
def history(tmp_path):
    db_path = tmp_path / "test_history.db"
    return InstallationHistory(db_path=str(db_path))


def test_doc_trigger_gating(history):
    # Mock DocsGenerator
    with patch("cortex.docs_generator.DocsGenerator") as mock_gen_class:
        mock_gen = mock_gen_class.return_value

        # Test cases: (OperationType, Status, ShouldTrigger)
        test_cases = [
            (InstallationType.INSTALL, InstallationStatus.SUCCESS, True),
            (InstallationType.UPGRADE, InstallationStatus.SUCCESS, True),
            (InstallationType.CONFIG, InstallationStatus.SUCCESS, True),
            (InstallationType.REMOVE, InstallationStatus.SUCCESS, False),
            (InstallationType.PURGE, InstallationStatus.SUCCESS, False),
            (InstallationType.ROLLBACK, InstallationStatus.SUCCESS, False),
            (InstallationType.INSTALL, InstallationStatus.FAILED, False),
        ]

        for op_type, status, should_trigger in test_cases:
            mock_gen.generate_software_docs.reset_mock()

            # Record an installation
            packages = ["test-pkg"]
            install_id = history.record_installation(
                operation_type=op_type,
                packages=packages,
                commands=["test command"],
                start_time=datetime.datetime.now(),
            )

            # Update installation
            # We need to mock _create_snapshot to avoid running real dpkg/apt commands
            with patch.object(history, "_create_snapshot", return_value=[]):
                history.update_installation(install_id, status)

            if should_trigger:
                mock_gen.generate_software_docs.assert_called_with("test-pkg")
            else:
                mock_gen.generate_software_docs.assert_not_called()
