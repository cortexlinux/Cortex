"""
Tests for Permission Auditor & Fixer module.
"""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from cortex.permissions.auditor_fixer import PermissionAuditor


class TestPermissionAuditorBasic:
    """Basic functionality tests for PermissionAuditor"""

    def test_auditor_creation(self):
        """Test that PermissionAuditor can be instantiated"""
        auditor = PermissionAuditor()
        assert auditor is not None
        assert hasattr(auditor, "scan_directory")
        assert hasattr(auditor, "suggest_fix")

    def test_scan_directory_returns_dict(self, tmp_path):
        """Test that scan_directory returns proper dictionary structure"""
        auditor = PermissionAuditor()
        result = auditor.scan_directory(tmp_path)

        assert isinstance(result, dict)
        expected_keys = ["world_writable", "dangerous", "suggestions"]
        for key in expected_keys:
            assert key in result, f"Missing key '{key}' in result"
            assert isinstance(result[key], list), f"Key '{key}' should be a list"

    def test_detect_world_writable_file(self, tmp_path):
        """Test detection of world-writable files (777 permissions)"""
        unsafe_file = tmp_path / "test_777.txt"
        unsafe_file.write_text("dangerous content")
        unsafe_file.chmod(0o777)

        auditor = PermissionAuditor()
        result = auditor.scan_directory(tmp_path)

        assert len(result["world_writable"]) > 0

        found_files = [str(p) for p in result["world_writable"]]
        assert str(unsafe_file) in found_files

    def test_ignore_safe_permissions(self, tmp_path):
        """Test that files with safe permissions are not flagged"""
        safe_file = tmp_path / "safe_644.txt"
        safe_file.write_text("safe content")
        safe_file.chmod(0o644)

        auditor = PermissionAuditor()
        result = auditor.scan_directory(tmp_path)

        assert str(safe_file) not in result["world_writable"]

    def test_suggest_fix_method(self):
        """Test that suggest_fix method works"""
        auditor = PermissionAuditor()

        assert hasattr(auditor, "suggest_fix")

        test_file = "/tmp/test_suggest.txt"
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.chmod(test_file, 0o777)

            suggestion = auditor.suggest_fix(test_file, "777")
            assert isinstance(suggestion, str)
            assert "chmod" in suggestion

            os.remove(test_file)

        except Exception:
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                f.write("test")
                temp_file = f.name
            os.chmod(temp_file, 0o777)

            suggestion = auditor.suggest_fix(temp_file, "777")
            assert isinstance(suggestion, str)
            assert "chmod" in suggestion

            os.remove(temp_file)


def test_pytest_works():
    """Simple test to verify pytest is working"""
    assert 1 + 1 == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
