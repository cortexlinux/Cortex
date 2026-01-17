#!/usr/bin/env python3
"""
Unit tests for the conflict_predictor module.

Tests for AI-powered dependency conflict prediction:
- Version constraint parsing
- Known conflict detection
- Declared conflict detection
- Resolution strategy generation
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cortex.conflict_predictor import (
    ConflictPredictor,
    ConflictPrediction,
    ConflictType,
    InstalledPackage,
    PackageCandidate,
    PredictedConflict,
    ResolutionSafety,
    ResolutionStrategy,
    VersionConstraint,
)


class TestVersionConstraint(unittest.TestCase):
    """Tests for VersionConstraint class."""

    def test_exact_constraint(self):
        """Test exact version constraint."""
        constraint = VersionConstraint(raw="(= 1.0.0)", operator="=", version="1.0.0")
        self.assertEqual(constraint.operator, "=")
        self.assertEqual(constraint.version, "1.0.0")

    def test_greater_equal_constraint(self):
        """Test >= version constraint."""
        constraint = VersionConstraint(raw="(>= 2.0)", operator=">=", version="2.0")
        self.assertEqual(constraint.operator, ">=")
        self.assertEqual(constraint.version, "2.0")

    def test_less_constraint(self):
        """Test << version constraint (apt format)."""
        constraint = VersionConstraint(raw="(<< 3.0)", operator="<<", version="3.0")
        self.assertEqual(constraint.operator, "<<")
        self.assertEqual(constraint.version, "3.0")


class TestInstalledPackage(unittest.TestCase):
    """Tests for InstalledPackage dataclass."""

    def test_package_creation(self):
        """Test creating an installed package."""
        pkg = InstalledPackage(
            name="nginx",
            version="1.18.0-0ubuntu1",
            status="installed",
            conflicts=["apache2"],
        )
        self.assertEqual(pkg.name, "nginx")
        self.assertEqual(pkg.version, "1.18.0-0ubuntu1")
        self.assertEqual(pkg.conflicts, ["apache2"])

    def test_package_defaults(self):
        """Test default values for InstalledPackage."""
        pkg = InstalledPackage(name="test", version="1.0")
        self.assertEqual(pkg.status, "installed")
        self.assertEqual(pkg.provides, [])
        self.assertEqual(pkg.depends, [])
        self.assertEqual(pkg.conflicts, [])
        self.assertEqual(pkg.breaks, [])


class TestPackageCandidate(unittest.TestCase):
    """Tests for PackageCandidate dataclass."""

    def test_candidate_creation(self):
        """Test creating a package candidate."""
        candidate = PackageCandidate(
            name="mysql-server",
            version="8.0.32",
            conflicts=["mariadb-server"],
        )
        self.assertEqual(candidate.name, "mysql-server")
        self.assertEqual(candidate.version, "8.0.32")
        self.assertEqual(candidate.conflicts, ["mariadb-server"])

    def test_candidate_with_dependencies(self):
        """Test candidate with version constraints."""
        constraint = VersionConstraint(raw="(>= 2.0)", operator=">=", version="2.0")
        candidate = PackageCandidate(
            name="myapp",
            depends=[("libfoo", constraint), ("libbar", None)],
        )
        self.assertEqual(len(candidate.depends), 2)
        self.assertEqual(candidate.depends[0][0], "libfoo")
        self.assertIsNotNone(candidate.depends[0][1])


class TestPredictedConflict(unittest.TestCase):
    """Tests for PredictedConflict dataclass."""

    def test_conflict_creation(self):
        """Test creating a predicted conflict."""
        conflict = PredictedConflict(
            conflict_type=ConflictType.PACKAGE_CONFLICT,
            package="mysql-server",
            conflicting_with="mariadb-server",
            description="mysql-server conflicts with installed mariadb-server",
            installed_version="10.6.12",
            confidence=1.0,
        )
        self.assertEqual(conflict.conflict_type, ConflictType.PACKAGE_CONFLICT)
        self.assertEqual(conflict.package, "mysql-server")
        self.assertEqual(conflict.conflicting_with, "mariadb-server")
        self.assertEqual(conflict.confidence, 1.0)

    def test_conflict_str(self):
        """Test string representation of conflict."""
        conflict = PredictedConflict(
            conflict_type=ConflictType.VERSION_MISMATCH,
            package="tensorflow",
            conflicting_with="numpy",
            description="Version mismatch",
        )
        self.assertIn("version_mismatch", str(conflict))
        self.assertIn("tensorflow", str(conflict))


class TestResolutionStrategy(unittest.TestCase):
    """Tests for ResolutionStrategy dataclass."""

    def test_strategy_creation(self):
        """Test creating a resolution strategy."""
        strategy = ResolutionStrategy(
            name="Remove conflicting package",
            description="Uninstall mariadb-server",
            safety=ResolutionSafety.MEDIUM_RISK,
            commands=["sudo apt-get remove mariadb-server"],
            side_effects=["Data may be lost"],
        )
        self.assertEqual(strategy.name, "Remove conflicting package")
        self.assertEqual(strategy.safety, ResolutionSafety.MEDIUM_RISK)
        self.assertEqual(len(strategy.commands), 1)

    def test_safety_score(self):
        """Test safety score ordering."""
        safe = ResolutionStrategy(
            name="Safe", description="", safety=ResolutionSafety.SAFE
        )
        low = ResolutionStrategy(
            name="Low", description="", safety=ResolutionSafety.LOW_RISK
        )
        high = ResolutionStrategy(
            name="High", description="", safety=ResolutionSafety.HIGH_RISK
        )

        self.assertLess(safe.safety_score, low.safety_score)
        self.assertLess(low.safety_score, high.safety_score)


class TestConflictPrediction(unittest.TestCase):
    """Tests for ConflictPrediction dataclass."""

    def test_prediction_no_conflicts(self):
        """Test prediction with no conflicts."""
        prediction = ConflictPrediction(package="nginx")
        self.assertEqual(prediction.package, "nginx")
        self.assertEqual(prediction.conflicts, [])
        self.assertTrue(prediction.can_install)

    def test_prediction_with_conflicts(self):
        """Test prediction with conflicts."""
        conflict = PredictedConflict(
            conflict_type=ConflictType.PACKAGE_CONFLICT,
            package="nginx",
            conflicting_with="apache2",
            description="Port conflict",
        )
        prediction = ConflictPrediction(
            package="nginx",
            conflicts=[conflict],
            can_install=False,
        )
        self.assertEqual(len(prediction.conflicts), 1)
        self.assertFalse(prediction.can_install)


class TestConflictPredictor(unittest.TestCase):
    """Tests for ConflictPredictor class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock dpkg status file
        self.temp_dir = tempfile.mkdtemp()
        self.dpkg_status_path = os.path.join(self.temp_dir, "status")

        # Write mock dpkg status
        with open(self.dpkg_status_path, "w") as f:
            f.write(
                """Package: nginx
Status: install ok installed
Version: 1.18.0-0ubuntu1
Depends: libc6
Conflicts: nginx-full
Breaks:

Package: mariadb-server
Status: install ok installed
Version: 10.6.12-0ubuntu0.22.04.1
Depends: mariadb-client
Conflicts: mysql-server
Breaks:

Package: python3
Status: install ok installed
Version: 3.10.6-1~22.04
Depends:
Conflicts:
Breaks:

Package: numpy
Status: install ok installed
Version: 1.21.5
Depends: python3
Conflicts:
Breaks:
"""
            )

    def tearDown(self):
        """Clean up temp files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_dpkg_status(self):
        """Test parsing dpkg status file."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        self.assertTrue(predictor.is_installed("nginx"))
        self.assertTrue(predictor.is_installed("mariadb-server"))
        self.assertFalse(predictor.is_installed("nonexistent-package"))

    def test_get_installed_version(self):
        """Test getting installed package version."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        version = predictor.get_installed_version("nginx")
        self.assertEqual(version, "1.18.0-0ubuntu1")

        version = predictor.get_installed_version("nonexistent")
        self.assertIsNone(version)

    @patch("cortex.conflict_predictor.ConflictPredictor._get_apt_package_info")
    def test_known_conflicts_mysql_mariadb(self, mock_apt):
        """Test detection of known mysql/mariadb conflict."""
        # Mock apt-cache response
        mock_apt.return_value = PackageCandidate(
            name="mysql-server",
            version="8.0.32",
            conflicts=["mariadb-server"],
        )

        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        # mariadb-server is installed, trying to install mysql-server should conflict
        prediction = predictor.predict_conflicts("mysql-server")

        # Should find the known conflict
        conflict_packages = [c.conflicting_with for c in prediction.conflicts]
        self.assertIn("mariadb-server", conflict_packages)

    def test_known_conflicts_list(self):
        """Test that known conflicts are properly defined."""
        self.assertIn("mysql-server", ConflictPredictor.KNOWN_CONFLICTS)
        self.assertIn("mariadb-server", ConflictPredictor.KNOWN_CONFLICTS)
        self.assertIn("nginx", ConflictPredictor.KNOWN_CONFLICTS)
        self.assertIn("apache2", ConflictPredictor.KNOWN_CONFLICTS)

    @patch("cortex.conflict_predictor.ConflictPredictor._run_command")
    def test_get_apt_package_info(self, mock_run):
        """Test getting package info from apt-cache."""
        mock_run.return_value = (
            True,
            """Package: test-package
Version: 1.0.0
Depends: libc6 (>= 2.17), libfoo (>= 1.0)
Conflicts: old-package
Breaks: legacy-package
""",
            "",
        )

        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)
        candidate = predictor._get_apt_package_info("test-package")

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.name, "test-package")
        self.assertEqual(candidate.version, "1.0.0")
        self.assertIn("old-package", candidate.conflicts)
        self.assertIn("legacy-package", candidate.breaks)

    def test_generate_resolutions_for_package_conflict(self):
        """Test resolution generation for package conflicts."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        conflict = PredictedConflict(
            conflict_type=ConflictType.PACKAGE_CONFLICT,
            package="mysql-server",
            conflicting_with="mariadb-server",
            description="Package conflict",
            installed_version="10.6.12",
        )

        resolutions = predictor._get_resolutions_for_conflict(conflict, "mysql-server")

        self.assertGreater(len(resolutions), 0)
        # Should have a "remove conflicting" resolution
        remove_resolutions = [r for r in resolutions if "Remove" in r.name]
        self.assertGreater(len(remove_resolutions), 0)

    def test_generate_resolutions_for_version_mismatch(self):
        """Test resolution generation for version mismatches."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        conflict = PredictedConflict(
            conflict_type=ConflictType.VERSION_MISMATCH,
            package="tensorflow",
            conflicting_with="numpy",
            description="Requires numpy<2.0",
            installed_version="2.1.0",
            required_version="<2.0",
        )

        resolutions = predictor._get_resolutions_for_conflict(conflict, "tensorflow")

        self.assertGreater(len(resolutions), 0)
        # Should suggest compatible version or upgrade
        strategy_names = [r.name for r in resolutions]
        self.assertTrue(
            any("compatible" in name.lower() or "update" in name.lower() for name in strategy_names)
        )

    def test_find_alternatives(self):
        """Test finding alternative packages."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        mysql_alts = predictor._find_alternatives("mysql-server")
        self.assertIn("mariadb-server", mysql_alts)
        self.assertIn("postgresql", mysql_alts)

        nginx_alts = predictor._find_alternatives("nginx")
        self.assertIn("apache2", nginx_alts)

    def test_is_python_related(self):
        """Test Python package detection."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        self.assertTrue(predictor._is_python_related("python3-numpy"))
        self.assertTrue(predictor._is_python_related("tensorflow"))
        self.assertTrue(predictor._is_python_related("pip3"))
        self.assertFalse(predictor._is_python_related("nginx"))
        self.assertFalse(predictor._is_python_related("mysql-server"))

    def test_resolution_sorting_by_safety(self):
        """Test that resolutions are sorted by safety."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        prediction = ConflictPrediction(package="test")
        prediction.conflicts = [
            PredictedConflict(
                conflict_type=ConflictType.PACKAGE_CONFLICT,
                package="test",
                conflicting_with="other",
                description="Conflict",
            )
        ]

        predictor._generate_resolutions(prediction)

        if len(prediction.resolutions) > 1:
            # First should be safest
            for i in range(len(prediction.resolutions) - 1):
                self.assertLessEqual(
                    prediction.resolutions[i].safety_score,
                    prediction.resolutions[i + 1].safety_score,
                )

    def test_parse_version_constraint(self):
        """Test version constraint parsing from apt format."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        constraint = predictor._parse_version_constraint("libc6 (>= 2.17)")
        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.operator, ">=")
        self.assertEqual(constraint.version, "2.17")

        constraint = predictor._parse_version_constraint("libfoo (= 1.0.0)")
        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.operator, "=")

        constraint = predictor._parse_version_constraint("libbar (<< 2.0)")
        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.operator, "<<")

        # No version constraint
        constraint = predictor._parse_version_constraint("simple-package")
        self.assertIsNone(constraint)

    def test_parse_package_list(self):
        """Test parsing comma-separated package lists."""
        predictor = ConflictPredictor(dpkg_status_path=self.dpkg_status_path)

        packages = predictor._parse_package_list("libc6, libfoo (>= 1.0), libbar")
        self.assertEqual(len(packages), 3)
        self.assertIn("libc6", packages)
        self.assertIn("libfoo", packages)
        self.assertIn("libbar", packages)

        # With alternatives
        packages = predictor._parse_package_list("foo | bar, baz")
        self.assertEqual(len(packages), 2)
        self.assertIn("foo", packages)  # First alternative taken

    def test_empty_dpkg_status(self):
        """Test handling of empty dpkg status file."""
        empty_path = os.path.join(self.temp_dir, "empty_status")
        with open(empty_path, "w") as f:
            f.write("")

        predictor = ConflictPredictor(dpkg_status_path=empty_path)
        self.assertEqual(len(predictor._installed_cache), 0)

    def test_nonexistent_dpkg_status(self):
        """Test handling of nonexistent dpkg status file."""
        predictor = ConflictPredictor(dpkg_status_path="/nonexistent/path/status")
        self.assertEqual(len(predictor._installed_cache), 0)


class TestConflictPredictorIntegration(unittest.TestCase):
    """Integration tests for ConflictPredictor."""

    def test_predict_no_conflicts_for_safe_package(self):
        """Test prediction for package with no conflicts."""
        with tempfile.NamedTemporaryFile(mode="w", suffix="_status", delete=False) as f:
            f.write(
                """Package: vim
Status: install ok installed
Version: 8.2.0
Depends:
Conflicts:
"""
            )
            temp_path = f.name

        try:
            predictor = ConflictPredictor(dpkg_status_path=temp_path)

            # Mock apt-cache to return safe package info
            with patch.object(predictor, "_get_apt_package_info") as mock_apt:
                mock_apt.return_value = PackageCandidate(
                    name="nano",
                    version="6.0",
                    conflicts=[],
                    breaks=[],
                )

                prediction = predictor.predict_conflicts("nano")
                self.assertEqual(len(prediction.conflicts), 0)
                self.assertTrue(prediction.can_install)
        finally:
            os.unlink(temp_path)

    def test_json_output_format(self):
        """Test JSON output format for predictions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix="_status", delete=False) as f:
            f.write(
                """Package: mariadb-server
Status: install ok installed
Version: 10.6.0
"""
            )
            temp_path = f.name

        try:
            predictor = ConflictPredictor(dpkg_status_path=temp_path)
            prediction = predictor.predict_conflicts("mysql-server")

            # Convert to JSON format
            output = {
                "package": prediction.package,
                "can_install": prediction.can_install,
                "conflicts": [
                    {
                        "type": c.conflict_type.value,
                        "package": c.package,
                        "conflicting_with": c.conflicting_with,
                    }
                    for c in prediction.conflicts
                ],
            }

            # Should be valid JSON
            json_str = json.dumps(output)
            parsed = json.loads(json_str)
            self.assertEqual(parsed["package"], "mysql-server")
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
