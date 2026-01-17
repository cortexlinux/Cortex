#!/usr/bin/env python3
"""
Package Version Pinning System

Allows users to pin specific package versions to prevent unwanted updates.
Supports exact versions, minor version patterns, and semver ranges.
"""

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PinType(Enum):
    """Type of version pin"""

    EXACT = "exact"  # Pin to exact version (e.g., "14.10")
    MINOR = "minor"  # Pin to minor version (e.g., "14.*" matches 14.x.x)
    MAJOR = "major"  # Pin to major version (e.g., "14" matches 14.x.x)
    RANGE = "range"  # Semver range (e.g., ">=3.11,<3.12")


class PackageSource(Enum):
    """Package source/manager"""

    APT = "apt"
    PIP = "pip"
    NPM = "npm"
    UNKNOWN = "unknown"


@dataclass
class PinConfiguration:
    """Configuration for a pinned package"""

    package: str
    version: str
    pin_type: PinType = PinType.EXACT
    source: PackageSource = PackageSource.APT
    pinned_at: str = field(default_factory=lambda: datetime.now().isoformat())
    reason: str | None = None
    synced_with_apt: bool = False  # Whether synced with apt-mark hold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "package": self.package,
            "version": self.version,
            "pin_type": self.pin_type.value,
            "source": self.source.value,
            "pinned_at": self.pinned_at,
            "reason": self.reason,
            "synced_with_apt": self.synced_with_apt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PinConfiguration":
        """Create from dictionary"""
        return cls(
            package=data["package"],
            version=data["version"],
            pin_type=PinType(data.get("pin_type", "exact")),
            source=PackageSource(data.get("source", "apt")),
            pinned_at=data.get("pinned_at", datetime.now().isoformat()),
            reason=data.get("reason"),
            synced_with_apt=data.get("synced_with_apt", False),
        )

    def get_age_days(self) -> int:
        """Get number of days since pin was created"""
        try:
            pinned_date = datetime.fromisoformat(self.pinned_at)
            return (datetime.now() - pinned_date).days
        except (ValueError, TypeError):
            return 0

    def format_version_display(self) -> str:
        """Format version for display based on pin type"""
        if self.pin_type == PinType.MINOR:
            return f"{self.version} (minor version)"
        elif self.pin_type == PinType.MAJOR:
            return f"{self.version} (major version)"
        elif self.pin_type == PinType.RANGE:
            return f"{self.version} (range)"
        return self.version


@dataclass
class PinCheckResult:
    """Result of checking if an update is allowed"""

    allowed: bool
    pin: PinConfiguration | None = None
    message: str = ""
    requires_force: bool = False


class PinManager:
    """
    Manages package version pinning.

    Features:
    - Pin specific versions to prevent unwanted updates
    - Support for exact, minor, major, and range pins
    - Export/import pin configurations
    - Integration with apt-mark hold
    - Validation of pin configurations
    """

    PIN_FILE_VERSION = "1.0"

    def __init__(self, pin_file: Path | str | None = None):
        """
        Initialize PinManager.

        Args:
            pin_file: Path to pin configuration file.
                      Defaults to ~/.cortex/pins.json
        """
        if pin_file is None:
            self.pin_file = Path.home() / ".cortex" / "pins.json"
        else:
            self.pin_file = Path(pin_file)

        self._pins: dict[str, PinConfiguration] = {}
        self._ensure_directory()
        self._load_pins()

    def _ensure_directory(self) -> None:
        """Ensure pin file directory exists"""
        self.pin_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_pins(self) -> None:
        """Load pins from file"""
        if not self.pin_file.exists():
            self._pins = {}
            return

        try:
            with open(self.pin_file) as f:
                data = json.load(f)

            pins_data = data.get("pins", [])
            self._pins = {}
            for pin_data in pins_data:
                pin = PinConfiguration.from_dict(pin_data)
                self._pins[pin.package] = pin

            logger.info(f"Loaded {len(self._pins)} pins from {self.pin_file}")

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error loading pins file: {e}")
            self._pins = {}

    def _save_pins(self) -> bool:
        """Save pins to file"""
        try:
            data = {
                "version": self.PIN_FILE_VERSION,
                "pins": [pin.to_dict() for pin in self._pins.values()],
                "metadata": {
                    "last_modified": datetime.now().isoformat(),
                    "cortex_version": "0.2.0",
                },
            }

            with open(self.pin_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self._pins)} pins to {self.pin_file}")
            return True

        except OSError as e:
            logger.error(f"Error saving pins file: {e}")
            return False

    # -------------------------------------------------------------------------
    # Core Pin Operations
    # -------------------------------------------------------------------------

    def add_pin(
        self,
        package: str,
        version: str,
        reason: str | None = None,
        pin_type: PinType | str = PinType.EXACT,
        source: PackageSource | str = PackageSource.APT,
        sync_apt: bool = False,
    ) -> tuple[bool, str]:
        """
        Add or update a package pin.

        Args:
            package: Package name
            version: Version to pin (e.g., "14.10", "14.*", ">=3.11,<3.12")
            reason: Optional reason for pinning
            pin_type: Type of pin (exact, minor, major, range)
            source: Package source (apt, pip, npm)
            sync_apt: Whether to also run apt-mark hold

        Returns:
            Tuple of (success, message)
        """
        # Normalize inputs
        package = package.strip().lower()
        version = version.strip()

        if isinstance(pin_type, str):
            try:
                pin_type = PinType(pin_type)
            except ValueError:
                return False, f"Invalid pin type: {pin_type}"

        if isinstance(source, str):
            try:
                source = PackageSource(source)
            except ValueError:
                source = PackageSource.UNKNOWN

        # Validate package name
        if not self._validate_package_name(package):
            return False, f"Invalid package name: {package}"

        # Validate version based on pin type
        valid, msg = self._validate_version(version, pin_type)
        if not valid:
            return False, msg

        # Check if package exists (optional validation)
        exists, exists_msg = self._check_package_exists(package, source)
        if not exists:
            logger.warning(f"Package validation warning: {exists_msg}")

        # Create pin configuration
        is_update = package in self._pins
        pin = PinConfiguration(
            package=package,
            version=version,
            pin_type=pin_type,
            source=source,
            reason=reason,
            pinned_at=datetime.now().isoformat(),
        )

        # Sync with apt-mark if requested
        if sync_apt and source == PackageSource.APT:
            apt_success = self._apt_mark_hold(package)
            pin.synced_with_apt = apt_success

        self._pins[package] = pin

        if not self._save_pins():
            return False, "Failed to save pin configuration"

        action = "Updated" if is_update else "Pinned"
        return True, f"{action} {package} to version {pin.format_version_display()}"

    def remove_pin(self, package: str, sync_apt: bool = False) -> tuple[bool, str]:
        """
        Remove a package pin.

        Args:
            package: Package name
            sync_apt: Whether to also run apt-mark unhold

        Returns:
            Tuple of (success, message)
        """
        package = package.strip().lower()

        if package not in self._pins:
            return False, f"Package {package} is not pinned"

        pin = self._pins[package]

        # Sync with apt-mark if requested
        if sync_apt and pin.source == PackageSource.APT:
            self._apt_mark_unhold(package)

        del self._pins[package]

        if not self._save_pins():
            return False, "Failed to save pin configuration"

        return True, f"Removed pin for {package}"

    def get_pin(self, package: str) -> PinConfiguration | None:
        """Get pin configuration for a package"""
        return self._pins.get(package.strip().lower())

    def is_pinned(self, package: str) -> bool:
        """Check if a package is pinned"""
        return package.strip().lower() in self._pins

    def list_pins(self, source: PackageSource | None = None) -> list[PinConfiguration]:
        """
        List all pins, optionally filtered by source.

        Args:
            source: Optional filter by package source

        Returns:
            List of pin configurations
        """
        pins = list(self._pins.values())

        if source is not None:
            pins = [p for p in pins if p.source == source]

        # Sort by pinned_at date (newest first)
        pins.sort(key=lambda p: p.pinned_at, reverse=True)

        return pins

    def clear_all_pins(self) -> tuple[bool, str]:
        """Remove all pins"""
        count = len(self._pins)
        self._pins = {}

        if not self._save_pins():
            return False, "Failed to save pin configuration"

        return True, f"Removed {count} pins"

    # -------------------------------------------------------------------------
    # Version Matching
    # -------------------------------------------------------------------------

    def version_matches_pin(self, pin: PinConfiguration, candidate_version: str) -> bool:
        """
        Check if a candidate version matches the pin constraint.

        Args:
            pin: Pin configuration
            candidate_version: Version to check

        Returns:
            True if version matches the pin constraint
        """
        if pin.pin_type == PinType.EXACT:
            return self._match_exact(pin.version, candidate_version)
        elif pin.pin_type == PinType.MINOR:
            return self._match_minor(pin.version, candidate_version)
        elif pin.pin_type == PinType.MAJOR:
            return self._match_major(pin.version, candidate_version)
        elif pin.pin_type == PinType.RANGE:
            return self._match_range(pin.version, candidate_version)

        return False

    def _match_exact(self, pinned: str, candidate: str) -> bool:
        """Match exact version"""
        return pinned.strip() == candidate.strip()

    def _match_minor(self, pinned: str, candidate: str) -> bool:
        """
        Match minor version pattern.
        E.g., "14.*" matches "14.0", "14.10", "14.10.1"
        """
        # Handle patterns like "14.*" or just "14"
        pattern = pinned.replace(".*", "").replace("*", "")

        # Extract major.minor from pinned version
        pinned_parts = pattern.split(".")
        candidate_parts = candidate.split(".")

        # Compare major and minor (first two parts)
        try:
            for i in range(min(2, len(pinned_parts))):
                if i >= len(candidate_parts):
                    return False
                # Remove any non-numeric suffix for comparison
                pinned_num = re.match(r"(\d+)", pinned_parts[i])
                candidate_num = re.match(r"(\d+)", candidate_parts[i])

                if not pinned_num or not candidate_num:
                    return False

                if pinned_num.group(1) != candidate_num.group(1):
                    return False

            return True
        except (IndexError, ValueError):
            return False

    def _match_major(self, pinned: str, candidate: str) -> bool:
        """
        Match major version.
        E.g., "14" matches "14.0", "14.10", "14.10.1"
        """
        pattern = pinned.replace(".*", "").replace("*", "")
        pinned_major = pattern.split(".")[0]

        candidate_parts = candidate.split(".")
        if not candidate_parts:
            return False

        candidate_major = re.match(r"(\d+)", candidate_parts[0])
        if not candidate_major:
            return False

        return pinned_major == candidate_major.group(1)

    def _match_range(self, pinned: str, candidate: str) -> bool:
        """
        Match semver range constraints.
        E.g., ">=3.11,<3.12" or ">=1.0.0"
        """
        try:
            candidate_tuple = self._parse_version(candidate)
            if candidate_tuple is None:
                return False

            # Parse constraints
            constraints = [c.strip() for c in pinned.split(",")]

            for constraint in constraints:
                if not self._check_constraint(constraint, candidate_tuple):
                    return False

            return True
        except Exception:
            return False

    def _parse_version(self, version: str) -> tuple[int, ...] | None:
        """Parse version string to tuple of integers"""
        try:
            # Extract numeric parts
            match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version)
            if not match:
                return None

            parts = [int(p) if p else 0 for p in match.groups()]
            return tuple(parts)
        except (ValueError, AttributeError):
            return None

    def _check_constraint(self, constraint: str, version_tuple: tuple[int, ...]) -> bool:
        """Check a single version constraint"""
        # Parse operator and version
        match = re.match(r"(>=|<=|>|<|==|!=|~=)?\s*(.+)", constraint)
        if not match:
            return False

        operator = match.group(1) or "=="
        constraint_version = self._parse_version(match.group(2))

        if constraint_version is None:
            return False

        # Pad tuples to same length
        max_len = max(len(version_tuple), len(constraint_version))
        v = version_tuple + (0,) * (max_len - len(version_tuple))
        c = constraint_version + (0,) * (max_len - len(constraint_version))

        if operator == ">=":
            return v >= c
        elif operator == "<=":
            return v <= c
        elif operator == ">":
            return v > c
        elif operator == "<":
            return v < c
        elif operator == "==":
            return v == c
        elif operator == "!=":
            return v != c
        elif operator == "~=":
            # Compatible release: ~=1.4.2 means >=1.4.2,<1.5.0
            return v >= c and v[:2] == c[:2]

        return False

    # -------------------------------------------------------------------------
    # Update Checking
    # -------------------------------------------------------------------------

    def check_update_allowed(
        self, package: str, new_version: str, force: bool = False
    ) -> PinCheckResult:
        """
        Check if updating a package to a new version is allowed.

        Args:
            package: Package name
            new_version: Proposed new version
            force: Whether to allow override

        Returns:
            PinCheckResult with decision and details
        """
        package = package.strip().lower()
        pin = self.get_pin(package)

        if pin is None:
            return PinCheckResult(
                allowed=True,
                message=f"Package {package} is not pinned",
            )

        # Check if new version matches pin
        if self.version_matches_pin(pin, new_version):
            return PinCheckResult(
                allowed=True,
                pin=pin,
                message=f"Version {new_version} matches pin constraint",
            )

        # Version doesn't match pin
        if force:
            return PinCheckResult(
                allowed=True,
                pin=pin,
                message=f"Force override: updating pinned package {package}",
                requires_force=True,
            )

        return PinCheckResult(
            allowed=False,
            pin=pin,
            message=f"Package {package} is pinned to {pin.format_version_display()}",
            requires_force=True,
        )

    def get_pinned_packages_in_list(self, packages: list[str]) -> list[PinConfiguration]:
        """Get list of pinned packages from a package list"""
        pinned = []
        for pkg in packages:
            pin = self.get_pin(pkg)
            if pin:
                pinned.append(pin)
        return pinned

    # -------------------------------------------------------------------------
    # Export/Import
    # -------------------------------------------------------------------------

    def export_pins(self, filepath: Path | str) -> tuple[bool, str]:
        """
        Export pins to a file.

        Args:
            filepath: Output file path

        Returns:
            Tuple of (success, message)
        """
        filepath = Path(filepath)

        try:
            data = {
                "version": self.PIN_FILE_VERSION,
                "exported_at": datetime.now().isoformat(),
                "pins": [pin.to_dict() for pin in self._pins.values()],
                "metadata": {
                    "total_pins": len(self._pins),
                    "cortex_version": "0.2.0",
                },
            }

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

            return True, f"Exported {len(self._pins)} pins to {filepath}"

        except OSError as e:
            return False, f"Failed to export pins: {e}"

    def import_pins(self, filepath: Path | str, merge: bool = True) -> tuple[bool, str, list[str]]:
        """
        Import pins from a file.

        Args:
            filepath: Input file path
            merge: If True, merge with existing pins. If False, replace all.

        Returns:
            Tuple of (success, message, list of imported package names)
        """
        filepath = Path(filepath)

        if not filepath.exists():
            return False, f"File not found: {filepath}", []

        try:
            with open(filepath) as f:
                data = json.load(f)

            pins_data = data.get("pins", [])

            if not merge:
                self._pins = {}

            imported = []
            errors = []

            for pin_data in pins_data:
                try:
                    pin = PinConfiguration.from_dict(pin_data)
                    self._pins[pin.package] = pin
                    imported.append(pin.package)
                except (KeyError, ValueError) as e:
                    errors.append(f"Invalid pin data: {e}")

            if not self._save_pins():
                return False, "Failed to save imported pins", []

            msg = f"Imported {len(imported)} pins"
            if errors:
                msg += f" ({len(errors)} errors)"

            return True, msg, imported

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON file: {e}", []
        except OSError as e:
            return False, f"Failed to read file: {e}", []

    # -------------------------------------------------------------------------
    # apt-mark Integration
    # -------------------------------------------------------------------------

    def sync_with_apt_mark(self) -> tuple[int, int, list[str]]:
        """
        Sync all apt pins with apt-mark hold.

        Returns:
            Tuple of (success_count, fail_count, error_messages)
        """
        success = 0
        failed = 0
        errors = []

        for pin in self._pins.values():
            if pin.source != PackageSource.APT:
                continue

            if self._apt_mark_hold(pin.package):
                pin.synced_with_apt = True
                success += 1
            else:
                failed += 1
                errors.append(f"Failed to hold {pin.package}")

        self._save_pins()

        return success, failed, errors

    def _apt_mark_hold(self, package: str) -> bool:
        """Run apt-mark hold on a package"""
        try:
            result = subprocess.run(
                ["sudo", "apt-mark", "hold", package],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"apt-mark hold failed for {package}: {e}")
            return False

    def _apt_mark_unhold(self, package: str) -> bool:
        """Run apt-mark unhold on a package"""
        try:
            result = subprocess.run(
                ["sudo", "apt-mark", "unhold", package],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"apt-mark unhold failed for {package}: {e}")
            return False

    def get_apt_held_packages(self) -> list[str]:
        """Get list of packages currently held by apt-mark"""
        try:
            result = subprocess.run(
                ["apt-mark", "showhold"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            return []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_package_name(self, package: str) -> bool:
        """Validate package name format"""
        if not package:
            return False

        # Allow alphanumeric, hyphens, underscores, dots, and @ for scoped npm packages
        pattern = r"^[@a-zA-Z0-9][\w\-\./@]*$"
        return bool(re.match(pattern, package))

    def _validate_version(self, version: str, pin_type: PinType) -> tuple[bool, str]:
        """
        Validate version format based on pin type.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not version:
            return False, "Version cannot be empty"

        if pin_type == PinType.EXACT:
            # Allow typical version formats: 1.0, 1.0.0, 1.0.0-beta, etc.
            if not re.match(r"^[\d][\w\.\-\+]*$", version):
                return False, f"Invalid exact version format: {version}"

        elif pin_type == PinType.MINOR:
            # Allow: 14.*, 14, 14.10.*
            if not re.match(r"^[\d]+(?:\.[\d\*]+)*\*?$", version):
                return False, f"Invalid minor version pattern: {version}"

        elif pin_type == PinType.MAJOR:
            # Allow: 14, 14.*
            if not re.match(r"^[\d]+(?:\.\*)?$", version):
                return False, f"Invalid major version pattern: {version}"

        elif pin_type == PinType.RANGE:
            # Allow semver constraints
            constraints = [c.strip() for c in version.split(",")]
            for constraint in constraints:
                if not re.match(r"^(>=|<=|>|<|==|!=|~=)?\s*[\d][\w\.\-]*$", constraint):
                    return False, f"Invalid range constraint: {constraint}"

        return True, ""

    def _check_package_exists(self, package: str, source: PackageSource) -> tuple[bool, str]:
        """
        Check if a package exists in the repository.
        This is a non-blocking validation that logs warnings.

        Returns:
            Tuple of (exists, message)
        """
        try:
            if source == PackageSource.APT:
                result = subprocess.run(
                    ["apt-cache", "show", package],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    return False, f"Package {package} not found in apt repository"

            elif source == PackageSource.PIP:
                result = subprocess.run(
                    ["pip", "show", package],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    return False, f"Package {package} not found (may need to be installed)"

            elif source == PackageSource.NPM:
                result = subprocess.run(
                    ["npm", "view", package, "version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    return False, f"Package {package} not found in npm registry"

            return True, "Package exists"

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True, "Could not verify package (command not available)"

    def validate_pin(self, package: str, version: str) -> tuple[bool, str]:
        """
        Validate a potential pin configuration.

        Args:
            package: Package name
            version: Version string

        Returns:
            Tuple of (is_valid, message)
        """
        # Validate package name
        if not self._validate_package_name(package):
            return False, f"Invalid package name: {package}"

        # Try to detect pin type from version string
        pin_type = self._detect_pin_type(version)

        # Validate version
        valid, msg = self._validate_version(version, pin_type)
        if not valid:
            return False, msg

        return True, f"Valid {pin_type.value} pin"

    def _detect_pin_type(self, version: str) -> PinType:
        """Detect pin type from version string"""
        if "," in version or any(op in version for op in [">=", "<=", ">", "<", "!="]):
            return PinType.RANGE
        elif version.endswith(".*") or version.count(".") == 0:
            if "." in version:
                return PinType.MINOR
            return PinType.MAJOR
        elif "*" in version:
            return PinType.MINOR
        return PinType.EXACT


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------


def parse_package_spec(spec: str) -> tuple[str, str | None]:
    """
    Parse a package specification like "postgresql@14.10" or "nginx".

    Args:
        spec: Package specification

    Returns:
        Tuple of (package_name, version or None)
    """
    if "@" in spec:
        parts = spec.rsplit("@", 1)
        return parts[0].strip(), parts[1].strip()
    return spec.strip(), None


def get_pin_manager(pin_file: Path | str | None = None) -> PinManager:
    """Get a PinManager instance (factory function)"""
    return PinManager(pin_file)
