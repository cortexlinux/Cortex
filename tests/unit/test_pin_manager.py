#!/usr/bin/env python3
"""
Unit tests for the Package Version Pinning System.

Tests cover:
- PinConfiguration dataclass
- PinManager core operations (add, remove, get, list)
- Version matching (exact, minor, major, range)
- Update checking
- Export/import functionality
- Validation
- Persistence
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.pin_manager import (
    PackageSource,
    PinCheckResult,
    PinConfiguration,
    PinManager,
    PinType,
    parse_package_spec,
)


class TestPinConfiguration:
    """Tests for PinConfiguration dataclass."""

    def test_create_default_pin(self):
        """Test creating a pin with default values."""
        pin = PinConfiguration(package="nginx", version="1.24.0")

        assert pin.package == "nginx"
        assert pin.version == "1.24.0"
        assert pin.pin_type == PinType.EXACT
        assert pin.source == PackageSource.APT
        assert pin.reason is None
        assert pin.synced_with_apt is False

    def test_create_pin_with_all_fields(self):
        """Test creating a pin with all fields specified."""
        pin = PinConfiguration(
            package="postgresql",
            version="14.10",
            pin_type=PinType.MINOR,
            source=PackageSource.APT,
            pinned_at="2024-12-25T10:00:00",
            reason="Production database",
            synced_with_apt=True,
        )

        assert pin.package == "postgresql"
        assert pin.version == "14.10"
        assert pin.pin_type == PinType.MINOR
        assert pin.reason == "Production database"
        assert pin.synced_with_apt is True

    def test_to_dict(self):
        """Test converting pin to dictionary."""
        pin = PinConfiguration(
            package="nginx",
            version="1.24.0",
            reason="Web server",
        )

        data = pin.to_dict()

        assert data["package"] == "nginx"
        assert data["version"] == "1.24.0"
        assert data["pin_type"] == "exact"
        assert data["source"] == "apt"
        assert data["reason"] == "Web server"

    def test_from_dict(self):
        """Test creating pin from dictionary."""
        data = {
            "package": "redis",
            "version": "7.0.0",
            "pin_type": "exact",
            "source": "apt",
            "pinned_at": "2024-12-25T10:00:00",
            "reason": "Cache server",
            "synced_with_apt": False,
        }

        pin = PinConfiguration.from_dict(data)

        assert pin.package == "redis"
        assert pin.version == "7.0.0"
        assert pin.pin_type == PinType.EXACT
        assert pin.source == PackageSource.APT
        assert pin.reason == "Cache server"

    def test_get_age_days(self):
        """Test calculating pin age in days."""
        # Pin from 5 days ago
        five_days_ago = (datetime.now() - timedelta(days=5)).isoformat()
        pin = PinConfiguration(
            package="nginx",
            version="1.24.0",
            pinned_at=five_days_ago,
        )

        age = pin.get_age_days()
        assert age == 5

    def test_get_age_days_today(self):
        """Test age for pin created today."""
        pin = PinConfiguration(
            package="nginx",
            version="1.24.0",
            pinned_at=datetime.now().isoformat(),
        )

        age = pin.get_age_days()
        assert age == 0

    def test_format_version_display_exact(self):
        """Test version display for exact pin."""
        pin = PinConfiguration(
            package="nginx",
            version="1.24.0",
            pin_type=PinType.EXACT,
        )

        assert pin.format_version_display() == "1.24.0"

    def test_format_version_display_minor(self):
        """Test version display for minor pin."""
        pin = PinConfiguration(
            package="python3",
            version="3.11.*",
            pin_type=PinType.MINOR,
        )

        assert "minor version" in pin.format_version_display()

    def test_format_version_display_range(self):
        """Test version display for range pin."""
        pin = PinConfiguration(
            package="python3",
            version=">=3.11,<3.12",
            pin_type=PinType.RANGE,
        )

        assert "range" in pin.format_version_display()


class TestPinManager:
    """Tests for PinManager core operations."""

    @pytest.fixture
    def temp_pin_file(self):
        """Create a temporary pin file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"version": "1.0", "pins": []}')
            temp_path = Path(f.name)
        yield temp_path
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def pin_manager(self, temp_pin_file):
        """Create a PinManager instance with temporary file."""
        return PinManager(pin_file=temp_pin_file)

    def test_add_pin_exact(self, pin_manager):
        """Test adding an exact version pin."""
        success, message = pin_manager.add_pin(
            package="nginx",
            version="1.24.0",
            reason="Production server",
        )

        assert success is True
        assert "nginx" in message
        assert pin_manager.is_pinned("nginx")

    def test_add_pin_minor(self, pin_manager):
        """Test adding a minor version pin."""
        success, message = pin_manager.add_pin(
            package="python3",
            version="3.11.*",
            pin_type=PinType.MINOR,
        )

        assert success is True
        pin = pin_manager.get_pin("python3")
        assert pin is not None
        assert pin.pin_type == PinType.MINOR

    def test_add_pin_with_reason(self, pin_manager):
        """Test adding a pin with reason."""
        success, _ = pin_manager.add_pin(
            package="postgresql",
            version="14.10",
            reason="Production database - do not upgrade",
        )

        assert success is True
        pin = pin_manager.get_pin("postgresql")
        assert pin.reason == "Production database - do not upgrade"

    def test_add_pin_update_existing(self, pin_manager):
        """Test updating an existing pin."""
        pin_manager.add_pin(package="nginx", version="1.24.0")
        success, message = pin_manager.add_pin(package="nginx", version="1.25.0")

        assert success is True
        assert "Updated" in message
        pin = pin_manager.get_pin("nginx")
        assert pin.version == "1.25.0"

    def test_add_pin_invalid_package_name(self, pin_manager):
        """Test adding pin with invalid package name."""
        success, message = pin_manager.add_pin(package="", version="1.0.0")

        assert success is False
        assert "Invalid" in message

    def test_remove_pin(self, pin_manager):
        """Test removing a pin."""
        pin_manager.add_pin(package="nginx", version="1.24.0")

        success, message = pin_manager.remove_pin("nginx")

        assert success is True
        assert not pin_manager.is_pinned("nginx")

    def test_remove_nonexistent_pin(self, pin_manager):
        """Test removing a pin that doesn't exist."""
        success, message = pin_manager.remove_pin("nonexistent")

        assert success is False
        assert "not pinned" in message

    def test_get_pin(self, pin_manager):
        """Test getting a pin configuration."""
        pin_manager.add_pin(package="nginx", version="1.24.0")

        pin = pin_manager.get_pin("nginx")

        assert pin is not None
        assert pin.package == "nginx"
        assert pin.version == "1.24.0"

    def test_get_pin_nonexistent(self, pin_manager):
        """Test getting a nonexistent pin."""
        pin = pin_manager.get_pin("nonexistent")
        assert pin is None

    def test_is_pinned(self, pin_manager):
        """Test checking if package is pinned."""
        pin_manager.add_pin(package="nginx", version="1.24.0")

        assert pin_manager.is_pinned("nginx") is True
        assert pin_manager.is_pinned("apache2") is False

    def test_list_pins_empty(self, pin_manager):
        """Test listing pins when empty."""
        pins = pin_manager.list_pins()
        assert pins == []

    def test_list_pins_multiple(self, pin_manager):
        """Test listing multiple pins."""
        pin_manager.add_pin(package="nginx", version="1.24.0")
        pin_manager.add_pin(package="postgresql", version="14.10")
        pin_manager.add_pin(package="redis", version="7.0.0")

        pins = pin_manager.list_pins()

        assert len(pins) == 3
        packages = [p.package for p in pins]
        assert "nginx" in packages
        assert "postgresql" in packages
        assert "redis" in packages

    def test_list_pins_filter_by_source(self, pin_manager):
        """Test filtering pins by source."""
        pin_manager.add_pin(package="nginx", version="1.24.0", source=PackageSource.APT)
        pin_manager.add_pin(package="flask", version="2.0.0", source=PackageSource.PIP)

        apt_pins = pin_manager.list_pins(source=PackageSource.APT)
        pip_pins = pin_manager.list_pins(source=PackageSource.PIP)

        assert len(apt_pins) == 1
        assert len(pip_pins) == 1
        assert apt_pins[0].package == "nginx"
        assert pip_pins[0].package == "flask"

    def test_clear_all_pins(self, pin_manager):
        """Test clearing all pins."""
        pin_manager.add_pin(package="nginx", version="1.24.0")
        pin_manager.add_pin(package="postgresql", version="14.10")

        success, message = pin_manager.clear_all_pins()

        assert success is True
        assert "2" in message
        assert len(pin_manager.list_pins()) == 0


class TestVersionMatching:
    """Tests for version matching functionality."""

    @pytest.fixture
    def pin_manager(self):
        """Create a PinManager instance with temporary file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"version": "1.0", "pins": []}')
            temp_path = Path(f.name)
        manager = PinManager(pin_file=temp_path)
        yield manager
        if temp_path.exists():
            temp_path.unlink()

    def test_match_exact_version(self, pin_manager):
        """Test exact version matching."""
        pin = PinConfiguration(
            package="nginx",
            version="1.24.0",
            pin_type=PinType.EXACT,
        )

        assert pin_manager.version_matches_pin(pin, "1.24.0") is True
        assert pin_manager.version_matches_pin(pin, "1.24.1") is False
        assert pin_manager.version_matches_pin(pin, "1.25.0") is False

    def test_match_minor_version(self, pin_manager):
        """Test minor version matching (14.* matches 14.x.x)."""
        pin = PinConfiguration(
            package="postgresql",
            version="14.*",
            pin_type=PinType.MINOR,
        )

        assert pin_manager.version_matches_pin(pin, "14.0") is True
        assert pin_manager.version_matches_pin(pin, "14.10") is True
        assert pin_manager.version_matches_pin(pin, "14.10.1") is True
        assert pin_manager.version_matches_pin(pin, "15.0") is False

    def test_match_minor_version_two_parts(self, pin_manager):
        """Test minor version matching with two parts (3.11.*)."""
        pin = PinConfiguration(
            package="python3",
            version="3.11.*",
            pin_type=PinType.MINOR,
        )

        assert pin_manager.version_matches_pin(pin, "3.11.0") is True
        assert pin_manager.version_matches_pin(pin, "3.11.5") is True
        assert pin_manager.version_matches_pin(pin, "3.12.0") is False

    def test_match_major_version(self, pin_manager):
        """Test major version matching (14 matches 14.x.x)."""
        pin = PinConfiguration(
            package="postgresql",
            version="14",
            pin_type=PinType.MAJOR,
        )

        assert pin_manager.version_matches_pin(pin, "14.0") is True
        assert pin_manager.version_matches_pin(pin, "14.10.1") is True
        assert pin_manager.version_matches_pin(pin, "15.0") is False

    def test_match_range_gte(self, pin_manager):
        """Test range matching with >= constraint."""
        pin = PinConfiguration(
            package="python3",
            version=">=3.10",
            pin_type=PinType.RANGE,
        )

        assert pin_manager.version_matches_pin(pin, "3.10.0") is True
        assert pin_manager.version_matches_pin(pin, "3.11.0") is True
        assert pin_manager.version_matches_pin(pin, "3.9.0") is False

    def test_match_range_lt(self, pin_manager):
        """Test range matching with < constraint."""
        pin = PinConfiguration(
            package="python3",
            version="<3.12",
            pin_type=PinType.RANGE,
        )

        assert pin_manager.version_matches_pin(pin, "3.11.5") is True
        assert pin_manager.version_matches_pin(pin, "3.12.0") is False
        assert pin_manager.version_matches_pin(pin, "3.12.1") is False

    def test_match_range_combined(self, pin_manager):
        """Test range matching with multiple constraints."""
        pin = PinConfiguration(
            package="python3",
            version=">=3.11,<3.12",
            pin_type=PinType.RANGE,
        )

        assert pin_manager.version_matches_pin(pin, "3.11.0") is True
        assert pin_manager.version_matches_pin(pin, "3.11.5") is True
        assert pin_manager.version_matches_pin(pin, "3.10.0") is False
        assert pin_manager.version_matches_pin(pin, "3.12.0") is False


class TestUpdateChecking:
    """Tests for update checking functionality."""

    @pytest.fixture
    def pin_manager(self):
        """Create a PinManager instance with temporary file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"version": "1.0", "pins": []}')
            temp_path = Path(f.name)
        manager = PinManager(pin_file=temp_path)
        yield manager
        if temp_path.exists():
            temp_path.unlink()

    def test_check_update_not_pinned(self, pin_manager):
        """Test update check for non-pinned package."""
        result = pin_manager.check_update_allowed("nginx", "1.25.0")

        assert result.allowed is True
        assert result.pin is None

    def test_check_update_pinned_matches(self, pin_manager):
        """Test update check when version matches pin."""
        pin_manager.add_pin(package="nginx", version="1.24.*", pin_type=PinType.MINOR)

        result = pin_manager.check_update_allowed("nginx", "1.24.5")

        assert result.allowed is True
        assert result.pin is not None

    def test_check_update_pinned_blocked(self, pin_manager):
        """Test update check when version doesn't match pin."""
        pin_manager.add_pin(package="nginx", version="1.24.0", pin_type=PinType.EXACT)

        result = pin_manager.check_update_allowed("nginx", "1.25.0")

        assert result.allowed is False
        assert result.requires_force is True
        assert result.pin is not None

    def test_check_update_force_override(self, pin_manager):
        """Test update check with force override."""
        pin_manager.add_pin(package="nginx", version="1.24.0", pin_type=PinType.EXACT)

        result = pin_manager.check_update_allowed("nginx", "1.25.0", force=True)

        assert result.allowed is True
        assert result.requires_force is True

    def test_get_pinned_packages_in_list(self, pin_manager):
        """Test getting pinned packages from a list."""
        pin_manager.add_pin(package="nginx", version="1.24.0")
        pin_manager.add_pin(package="postgresql", version="14.10")

        packages = ["nginx", "apache2", "postgresql", "redis"]
        pinned = pin_manager.get_pinned_packages_in_list(packages)

        assert len(pinned) == 2
        package_names = [p.package for p in pinned]
        assert "nginx" in package_names
        assert "postgresql" in package_names


class TestExportImport:
    """Tests for export/import functionality."""

    @pytest.fixture
    def pin_manager(self):
        """Create a PinManager instance with temporary file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"version": "1.0", "pins": []}')
            temp_path = Path(f.name)
        manager = PinManager(pin_file=temp_path)
        yield manager
        if temp_path.exists():
            temp_path.unlink()

    def test_export_pins(self, pin_manager):
        """Test exporting pins to file."""
        pin_manager.add_pin(package="nginx", version="1.24.0")
        pin_manager.add_pin(package="postgresql", version="14.10")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            export_path = Path(f.name)

        try:
            success, message = pin_manager.export_pins(export_path)

            assert success is True
            assert "2 pins" in message

            # Verify file contents
            with open(export_path) as f:
                data = json.load(f)

            assert "pins" in data
            assert len(data["pins"]) == 2
        finally:
            if export_path.exists():
                export_path.unlink()

    def test_import_pins_merge(self, pin_manager):
        """Test importing pins with merge."""
        pin_manager.add_pin(package="nginx", version="1.24.0")

        # Create import file
        import_data = {
            "version": "1.0",
            "pins": [
                {"package": "postgresql", "version": "14.10", "pin_type": "exact", "source": "apt"},
                {"package": "redis", "version": "7.0.0", "pin_type": "exact", "source": "apt"},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(import_data, f)
            import_path = Path(f.name)

        try:
            success, message, imported = pin_manager.import_pins(import_path, merge=True)

            assert success is True
            assert len(imported) == 2

            # Check all pins exist (original + imported)
            pins = pin_manager.list_pins()
            assert len(pins) == 3
        finally:
            if import_path.exists():
                import_path.unlink()

    def test_import_pins_replace(self, pin_manager):
        """Test importing pins with replace."""
        pin_manager.add_pin(package="nginx", version="1.24.0")

        # Create import file
        import_data = {
            "version": "1.0",
            "pins": [
                {"package": "postgresql", "version": "14.10", "pin_type": "exact", "source": "apt"},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(import_data, f)
            import_path = Path(f.name)

        try:
            success, message, imported = pin_manager.import_pins(import_path, merge=False)

            assert success is True

            # Check only imported pins exist
            pins = pin_manager.list_pins()
            assert len(pins) == 1
            assert pins[0].package == "postgresql"
        finally:
            if import_path.exists():
                import_path.unlink()

    def test_import_nonexistent_file(self, pin_manager):
        """Test importing from nonexistent file."""
        success, message, imported = pin_manager.import_pins("/nonexistent/file.json")

        assert success is False
        assert "not found" in message.lower()


class TestValidation:
    """Tests for validation functionality."""

    @pytest.fixture
    def pin_manager(self):
        """Create a PinManager instance with temporary file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"version": "1.0", "pins": []}')
            temp_path = Path(f.name)
        manager = PinManager(pin_file=temp_path)
        yield manager
        if temp_path.exists():
            temp_path.unlink()

    def test_validate_pin_valid(self, pin_manager):
        """Test validating a valid pin."""
        valid, message = pin_manager.validate_pin("nginx", "1.24.0")
        assert valid is True

    def test_validate_pin_invalid_package(self, pin_manager):
        """Test validating pin with invalid package name."""
        valid, message = pin_manager.validate_pin("", "1.0.0")
        assert valid is False

    def test_validate_pin_empty_version(self, pin_manager):
        """Test validating pin with empty version."""
        valid, message = pin_manager.validate_pin("nginx", "")
        assert valid is False

    def test_validate_version_exact(self, pin_manager):
        """Test validating exact version format."""
        valid, _ = pin_manager._validate_version("1.24.0", PinType.EXACT)
        assert valid is True

        valid, _ = pin_manager._validate_version("1.24.0-beta", PinType.EXACT)
        assert valid is True

    def test_validate_version_minor(self, pin_manager):
        """Test validating minor version format."""
        valid, _ = pin_manager._validate_version("14.*", PinType.MINOR)
        assert valid is True

        valid, _ = pin_manager._validate_version("3.11.*", PinType.MINOR)
        assert valid is True

    def test_validate_version_range(self, pin_manager):
        """Test validating range version format."""
        valid, _ = pin_manager._validate_version(">=3.11,<3.12", PinType.RANGE)
        assert valid is True

        valid, _ = pin_manager._validate_version(">=1.0.0", PinType.RANGE)
        assert valid is True


class TestPersistence:
    """Tests for pin persistence."""

    def test_persistence_across_instances(self):
        """Test that pins persist across manager instances."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"version": "1.0", "pins": []}')
            temp_path = Path(f.name)

        try:
            # Add pin with first instance
            manager1 = PinManager(pin_file=temp_path)
            manager1.add_pin(package="nginx", version="1.24.0")

            # Create new instance and verify pin exists
            manager2 = PinManager(pin_file=temp_path)
            assert manager2.is_pinned("nginx") is True
            pin = manager2.get_pin("nginx")
            assert pin.version == "1.24.0"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_corrupted_file_handling(self):
        """Test handling of corrupted pin file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            temp_path = Path(f.name)

        try:
            # Should not raise, should handle gracefully
            manager = PinManager(pin_file=temp_path)
            assert len(manager.list_pins()) == 0
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_parse_package_spec_with_version(self):
        """Test parsing package@version spec."""
        package, version = parse_package_spec("postgresql@14.10")
        assert package == "postgresql"
        assert version == "14.10"

    def test_parse_package_spec_without_version(self):
        """Test parsing package spec without version."""
        package, version = parse_package_spec("nginx")
        assert package == "nginx"
        assert version is None

    def test_parse_package_spec_scoped_npm(self):
        """Test parsing scoped npm package."""
        package, version = parse_package_spec("@angular/core@15.0.0")
        assert package == "@angular/core"
        assert version == "15.0.0"

    def test_parse_package_spec_with_spaces(self):
        """Test parsing package spec with spaces."""
        package, version = parse_package_spec("  nginx@1.24.0  ")
        assert package == "nginx"
        assert version == "1.24.0"


class TestAptMarkIntegration:
    """Tests for apt-mark integration (mocked)."""

    @pytest.fixture
    def pin_manager(self):
        """Create a PinManager instance with temporary file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"version": "1.0", "pins": []}')
            temp_path = Path(f.name)
        manager = PinManager(pin_file=temp_path)
        yield manager
        if temp_path.exists():
            temp_path.unlink()

    @patch("subprocess.run")
    def test_apt_mark_hold_success(self, mock_run, pin_manager):
        """Test successful apt-mark hold."""
        mock_run.return_value = MagicMock(returncode=0)

        success, _ = pin_manager.add_pin(package="nginx", version="1.24.0", sync_apt=True)

        assert success is True
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_apt_mark_hold_failure(self, mock_run, pin_manager):
        """Test apt-mark hold failure (pin still succeeds)."""
        mock_run.return_value = MagicMock(returncode=1)

        success, _ = pin_manager.add_pin(package="nginx", version="1.24.0", sync_apt=True)

        # Pin should still succeed even if apt-mark fails
        assert success is True
        pin = pin_manager.get_pin("nginx")
        assert pin.synced_with_apt is False

    @patch("subprocess.run")
    def test_get_apt_held_packages(self, mock_run, pin_manager):
        """Test getting apt held packages."""
        mock_run.return_value = MagicMock(returncode=0, stdout="nginx\npostgresql\nredis\n")

        held = pin_manager.get_apt_held_packages()

        assert len(held) == 3
        assert "nginx" in held
        assert "postgresql" in held


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
