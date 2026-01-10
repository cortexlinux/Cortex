#!/usr/bin/env python3
"""
Tests for AI-Powered Dependency Conflict Predictor

This module tests the conflict prediction system that analyzes
dependency graphs before installation to predict and prevent conflicts.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cortex.conflict_predictor import (
    ConflictPrediction,
    ConflictSeverity,
    DependencyConflictPredictor,
    InstalledPackage,
    PackageEcosystem,
    PredictedConflict,
    ResolutionStrategy,
    ResolutionSuggestion,
    VersionConstraint,
)


class TestVersionConstraint(unittest.TestCase):
    """Test version constraint parsing"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    def test_parse_equal_constraint(self):
        """Test parsing == constraint"""
        constraint = self.predictor._parse_version_constraint("==1.0.0")

        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.operator, "==")
        self.assertEqual(constraint.version, "1.0.0")

    def test_parse_greater_equal_constraint(self):
        """Test parsing >= constraint"""
        constraint = self.predictor._parse_version_constraint(">=2.0.0")

        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.operator, ">=")
        self.assertEqual(constraint.version, "2.0.0")

    def test_parse_less_than_constraint(self):
        """Test parsing < constraint"""
        constraint = self.predictor._parse_version_constraint("<3.0")

        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.operator, "<")
        self.assertEqual(constraint.version, "3.0")

    def test_parse_compatible_release_constraint(self):
        """Test parsing ~= constraint"""
        constraint = self.predictor._parse_version_constraint("~=1.4.2")

        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.operator, "~=")
        self.assertEqual(constraint.version, "1.4.2")

    def test_parse_empty_constraint(self):
        """Test parsing empty constraint"""
        constraint = self.predictor._parse_version_constraint("")

        self.assertIsNone(constraint)


class TestVersionComparison(unittest.TestCase):
    """Test version comparison logic"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    def test_equal_versions(self):
        """Test equal version comparison"""
        result = self.predictor._compare_versions("1.0.0", "1.0.0")
        self.assertEqual(result, 0)

    def test_greater_version(self):
        """Test greater version comparison"""
        result = self.predictor._compare_versions("2.0.0", "1.0.0")
        self.assertEqual(result, 1)

    def test_lesser_version(self):
        """Test lesser version comparison"""
        result = self.predictor._compare_versions("1.0.0", "2.0.0")
        self.assertEqual(result, -1)

    def test_patch_version_comparison(self):
        """Test patch version comparison"""
        result = self.predictor._compare_versions("1.0.1", "1.0.0")
        self.assertEqual(result, 1)

    def test_minor_version_comparison(self):
        """Test minor version comparison"""
        result = self.predictor._compare_versions("1.1.0", "1.0.0")
        self.assertEqual(result, 1)

    def test_different_length_versions(self):
        """Test comparing versions with different lengths"""
        result = self.predictor._compare_versions("1.0", "1.0.0")
        self.assertEqual(result, 0)

    def test_complex_version_strings(self):
        """Test complex version strings with suffixes"""
        result = self.predictor._compare_versions("2.1.0-beta", "2.0.0")
        self.assertEqual(result, 1)


class TestVersionConstraintSatisfaction(unittest.TestCase):
    """Test version constraint satisfaction checking"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    def test_equal_constraint_satisfied(self):
        """Test == constraint satisfaction"""
        constraint = VersionConstraint(operator="==", version="1.0.0", original="==1.0.0")
        self.assertTrue(self.predictor._check_version_satisfies("1.0.0", constraint))
        self.assertFalse(self.predictor._check_version_satisfies("1.0.1", constraint))

    def test_greater_equal_constraint_satisfied(self):
        """Test >= constraint satisfaction"""
        constraint = VersionConstraint(operator=">=", version="2.0.0", original=">=2.0.0")
        self.assertTrue(self.predictor._check_version_satisfies("2.0.0", constraint))
        self.assertTrue(self.predictor._check_version_satisfies("3.0.0", constraint))
        self.assertFalse(self.predictor._check_version_satisfies("1.9.9", constraint))

    def test_less_than_constraint_satisfied(self):
        """Test < constraint satisfaction"""
        constraint = VersionConstraint(operator="<", version="2.0.0", original="<2.0.0")
        self.assertTrue(self.predictor._check_version_satisfies("1.9.9", constraint))
        self.assertFalse(self.predictor._check_version_satisfies("2.0.0", constraint))
        self.assertFalse(self.predictor._check_version_satisfies("2.0.1", constraint))

    def test_not_equal_constraint_satisfied(self):
        """Test != constraint satisfaction"""
        constraint = VersionConstraint(operator="!=", version="1.5.0", original="!=1.5.0")
        self.assertTrue(self.predictor._check_version_satisfies("1.4.0", constraint))
        self.assertTrue(self.predictor._check_version_satisfies("1.6.0", constraint))
        self.assertFalse(self.predictor._check_version_satisfies("1.5.0", constraint))


class TestKnownConflictPatterns(unittest.TestCase):
    """Test detection of known conflict patterns"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()
        # Mock the pip cache with numpy 2.1.0 installed
        self.predictor._installed_pip_cache = {
            "numpy": InstalledPackage(
                name="numpy",
                version="2.1.0",
                ecosystem=PackageEcosystem.PIP,
                source="pip3",
            ),
        }

    def test_tensorflow_numpy_conflict(self):
        """Test detection of TensorFlow + NumPy conflict"""
        conflicts = self.predictor._analyze_known_conflicts(
            "tensorflow", PackageEcosystem.PIP
        )

        self.assertGreater(len(conflicts), 0)
        numpy_conflict = next(
            (c for c in conflicts if c.conflicting_package == "numpy"), None
        )
        self.assertIsNotNone(numpy_conflict)
        self.assertIn("numpy", numpy_conflict.description.lower())

    def test_no_conflict_when_compatible(self):
        """Test no conflict when versions are compatible"""
        # Set numpy to a compatible version
        self.predictor._installed_pip_cache["numpy"] = InstalledPackage(
            name="numpy",
            version="1.24.0",
            ecosystem=PackageEcosystem.PIP,
            source="pip3",
        )

        conflicts = self.predictor._analyze_known_conflicts(
            "tensorflow", PackageEcosystem.PIP
        )

        numpy_conflict = next(
            (c for c in conflicts if c.conflicting_package == "numpy"), None
        )
        self.assertIsNone(numpy_conflict)


class TestMutualExclusionConflicts(unittest.TestCase):
    """Test detection of mutually exclusive packages"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()
        # Mock mariadb-server being installed
        self.predictor._installed_apt_cache = {
            "mariadb-server": InstalledPackage(
                name="mariadb-server",
                version="10.6.12",
                ecosystem=PackageEcosystem.APT,
                source="dpkg",
            ),
        }

    def test_mysql_mariadb_conflict(self):
        """Test MySQL/MariaDB mutual exclusion conflict"""
        conflicts = self.predictor._analyze_known_conflicts(
            "mysql-server", PackageEcosystem.APT
        )

        self.assertGreater(len(conflicts), 0)
        mariadb_conflict = next(
            (c for c in conflicts if c.conflicting_package == "mariadb-server"), None
        )
        self.assertIsNotNone(mariadb_conflict)
        self.assertEqual(mariadb_conflict.conflict_type, "mutual_exclusion")
        self.assertEqual(mariadb_conflict.severity, ConflictSeverity.CRITICAL)


class TestConflictPrediction(unittest.TestCase):
    """Test the main prediction functionality"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    @patch.object(DependencyConflictPredictor, "_run_command")
    def test_predict_no_conflicts(self, mock_run):
        """Test prediction when no conflicts exist"""
        # Mock empty caches
        mock_run.return_value = (True, "", "")
        self.predictor._installed_pip_cache = {}
        self.predictor._installed_apt_cache = {}

        prediction = self.predictor.predict_conflicts("flask")

        self.assertIsInstance(prediction, ConflictPrediction)
        self.assertEqual(len(prediction.conflicts), 0)
        self.assertEqual(prediction.overall_risk, ConflictSeverity.LOW)
        self.assertTrue(prediction.can_proceed)

    def test_predict_with_conflicts(self):
        """Test prediction when conflicts exist"""
        # Set up conflicting state
        self.predictor._installed_pip_cache = {
            "numpy": InstalledPackage(
                name="numpy",
                version="2.1.0",
                ecosystem=PackageEcosystem.PIP,
                source="pip3",
            ),
        }

        prediction = self.predictor.predict_conflicts("tensorflow")

        self.assertIsInstance(prediction, ConflictPrediction)
        self.assertGreater(len(prediction.conflicts), 0)
        self.assertIn(
            prediction.overall_risk,
            [ConflictSeverity.HIGH, ConflictSeverity.CRITICAL],
        )

    def test_predict_multiple_packages(self):
        """Test predicting conflicts for multiple packages"""
        self.predictor._installed_pip_cache = {}
        self.predictor._installed_apt_cache = {}

        predictions = self.predictor.predict_multiple(["flask", "django", "numpy"])

        self.assertEqual(len(predictions), 3)
        for pred in predictions:
            self.assertIsInstance(pred, ConflictPrediction)


class TestResolutionSuggestions(unittest.TestCase):
    """Test resolution suggestion generation"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    def test_virtualenv_suggestion_for_pip(self):
        """Test that virtualenv is suggested for pip conflicts"""
        conflicts = [
            PredictedConflict(
                package_to_install="tensorflow",
                package_version=None,
                conflicting_package="numpy",
                conflicting_version="2.1.0",
                installed_by="pandas",
                conflict_type="version_too_high",
                severity=ConflictSeverity.HIGH,
                confidence=0.9,
                description="TensorFlow requires numpy<2.0",
                ecosystem=PackageEcosystem.PIP,
            )
        ]

        resolutions = self.predictor._generate_resolutions(conflicts, "tensorflow")

        self.assertGreater(len(resolutions), 0)

        # Check for virtualenv suggestion
        venv_suggestions = [
            r for r in resolutions if r.strategy == ResolutionStrategy.USE_VIRTUALENV
        ]
        self.assertGreater(len(venv_suggestions), 0)
        self.assertTrue(venv_suggestions[0].recommended)

    def test_resolution_safety_ranking(self):
        """Test that resolutions are ranked by safety"""
        conflicts = [
            PredictedConflict(
                package_to_install="tensorflow",
                package_version=None,
                conflicting_package="numpy",
                conflicting_version="2.1.0",
                installed_by="pandas",
                conflict_type="version_too_high",
                severity=ConflictSeverity.HIGH,
                confidence=0.9,
                description="Test conflict",
                ecosystem=PackageEcosystem.PIP,
            )
        ]

        resolutions = self.predictor._generate_resolutions(conflicts, "tensorflow")

        # Check that resolutions are sorted by safety score (descending)
        for i in range(len(resolutions) - 1):
            self.assertGreaterEqual(
                resolutions[i].safety_score, resolutions[i + 1].safety_score
            )

    def test_mutual_exclusion_resolution(self):
        """Test resolution suggestions for mutual exclusion conflicts"""
        conflicts = [
            PredictedConflict(
                package_to_install="mysql-server",
                package_version=None,
                conflicting_package="mariadb-server",
                conflicting_version="10.6.12",
                installed_by="system",
                conflict_type="mutual_exclusion",
                severity=ConflictSeverity.CRITICAL,
                confidence=0.95,
                description="Cannot have both MySQL and MariaDB",
                ecosystem=PackageEcosystem.APT,
            )
        ]

        resolutions = self.predictor._generate_resolutions(conflicts, "mysql-server")

        # Should have remove and skip options
        strategies = [r.strategy for r in resolutions]
        self.assertIn(ResolutionStrategy.REMOVE_CONFLICTING, strategies)
        self.assertIn(ResolutionStrategy.SKIP_INSTALL, strategies)


class TestRiskAssessment(unittest.TestCase):
    """Test overall risk level determination"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    def test_no_conflicts_low_risk(self):
        """Test that no conflicts means low risk"""
        risk = self.predictor._determine_overall_risk([])
        self.assertEqual(risk, ConflictSeverity.LOW)

    def test_critical_conflict_critical_risk(self):
        """Test that critical conflicts result in critical risk"""
        conflicts = [
            PredictedConflict(
                package_to_install="test",
                package_version=None,
                conflicting_package="other",
                conflicting_version="1.0",
                installed_by="system",
                conflict_type="test",
                severity=ConflictSeverity.CRITICAL,
                confidence=0.9,
                description="Test",
                ecosystem=PackageEcosystem.APT,
            )
        ]

        risk = self.predictor._determine_overall_risk(conflicts)
        self.assertEqual(risk, ConflictSeverity.CRITICAL)

    def test_mixed_severity_highest_wins(self):
        """Test that highest severity determines overall risk"""
        conflicts = [
            PredictedConflict(
                package_to_install="test",
                package_version=None,
                conflicting_package="pkg1",
                conflicting_version="1.0",
                installed_by="system",
                conflict_type="test",
                severity=ConflictSeverity.LOW,
                confidence=0.9,
                description="Test",
                ecosystem=PackageEcosystem.APT,
            ),
            PredictedConflict(
                package_to_install="test",
                package_version=None,
                conflicting_package="pkg2",
                conflicting_version="1.0",
                installed_by="system",
                conflict_type="test",
                severity=ConflictSeverity.HIGH,
                confidence=0.9,
                description="Test",
                ecosystem=PackageEcosystem.APT,
            ),
        ]

        risk = self.predictor._determine_overall_risk(conflicts)
        self.assertEqual(risk, ConflictSeverity.HIGH)


class TestEcosystemDetection(unittest.TestCase):
    """Test package ecosystem detection"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    def test_detect_pip_package(self):
        """Test detection of pip packages"""
        ecosystem = self.predictor._detect_ecosystem("numpy")
        self.assertEqual(ecosystem, PackageEcosystem.PIP)

    def test_detect_apt_package(self):
        """Test detection of apt packages"""
        ecosystem = self.predictor._detect_ecosystem("nginx")
        self.assertEqual(ecosystem, PackageEcosystem.APT)


class TestOutputFormatting(unittest.TestCase):
    """Test output formatting functions"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    def test_format_no_conflicts(self):
        """Test formatting when no conflicts"""
        prediction = ConflictPrediction(
            package_name="flask",
            package_version=None,
            conflicts=[],
            resolutions=[],
            overall_risk=ConflictSeverity.LOW,
            can_proceed=True,
            prediction_confidence=0.9,
        )

        output = self.predictor.format_prediction(prediction)

        self.assertIn("No conflicts predicted", output)
        self.assertIn("flask", output)

    def test_format_with_conflicts(self):
        """Test formatting with conflicts"""
        prediction = ConflictPrediction(
            package_name="tensorflow",
            package_version=None,
            conflicts=[
                PredictedConflict(
                    package_to_install="tensorflow",
                    package_version=None,
                    conflicting_package="numpy",
                    conflicting_version="2.1.0",
                    installed_by="pandas",
                    conflict_type="version_too_high",
                    severity=ConflictSeverity.HIGH,
                    confidence=0.9,
                    description="TensorFlow requires numpy<2.0",
                    ecosystem=PackageEcosystem.PIP,
                )
            ],
            resolutions=[
                ResolutionSuggestion(
                    strategy=ResolutionStrategy.USE_VIRTUALENV,
                    description="Use virtual environment",
                    command="python3 -m venv .venv",
                    safety_score=0.95,
                    side_effects=[],
                    recommended=True,
                )
            ],
            overall_risk=ConflictSeverity.HIGH,
            can_proceed=True,
            prediction_confidence=0.85,
        )

        output = self.predictor.format_prediction(prediction)

        self.assertIn("tensorflow", output)
        self.assertIn("numpy", output)
        self.assertIn("Suggestions", output)

    def test_export_json(self):
        """Test JSON export of predictions"""
        prediction = ConflictPrediction(
            package_name="tensorflow",
            package_version="2.15.0",
            conflicts=[],
            resolutions=[],
            overall_risk=ConflictSeverity.LOW,
            can_proceed=True,
            prediction_confidence=0.9,
            analysis_details={"test": "value"},
        )

        exported = self.predictor.export_prediction_json(prediction)

        self.assertIsInstance(exported, dict)
        self.assertEqual(exported["package_name"], "tensorflow")
        self.assertEqual(exported["overall_risk"], "low")
        self.assertTrue(exported["can_proceed"])
        self.assertEqual(exported["analysis_details"]["test"], "value")


class TestTransitiveConflicts(unittest.TestCase):
    """Test transitive dependency conflict detection"""

    def setUp(self):
        self.predictor = DependencyConflictPredictor()

    def test_transitive_tensorflow_conflicts(self):
        """Test detection of TensorFlow's transitive dependency conflicts"""
        # Set up a scenario where numpy is installed and could conflict
        self.predictor._installed_pip_cache = {
            "numpy": InstalledPackage(
                name="numpy",
                version="1.24.0",
                ecosystem=PackageEcosystem.PIP,
                source="pip3",
            ),
            "protobuf": InstalledPackage(
                name="protobuf",
                version="3.20.0",
                ecosystem=PackageEcosystem.PIP,
                source="pip3",
            ),
        }

        conflicts = self.predictor._analyze_transitive_conflicts(
            "tensorflow", PackageEcosystem.PIP
        )

        # Should detect potential transitive conflicts
        self.assertIsInstance(conflicts, list)


class TestDataclasses(unittest.TestCase):
    """Test dataclass structures"""

    def test_installed_package_creation(self):
        """Test InstalledPackage dataclass"""
        pkg = InstalledPackage(
            name="test-pkg",
            version="1.0.0",
            ecosystem=PackageEcosystem.PIP,
            source="pip3",
        )

        self.assertEqual(pkg.name, "test-pkg")
        self.assertEqual(pkg.version, "1.0.0")
        self.assertEqual(pkg.ecosystem, PackageEcosystem.PIP)

    def test_predicted_conflict_creation(self):
        """Test PredictedConflict dataclass"""
        conflict = PredictedConflict(
            package_to_install="tensorflow",
            package_version="2.15.0",
            conflicting_package="numpy",
            conflicting_version="2.1.0",
            installed_by="pandas",
            conflict_type="version_too_high",
            severity=ConflictSeverity.HIGH,
            confidence=0.9,
            description="Test conflict",
            ecosystem=PackageEcosystem.PIP,
        )

        self.assertEqual(conflict.package_to_install, "tensorflow")
        self.assertEqual(conflict.severity, ConflictSeverity.HIGH)
        self.assertEqual(conflict.confidence, 0.9)

    def test_resolution_suggestion_creation(self):
        """Test ResolutionSuggestion dataclass"""
        suggestion = ResolutionSuggestion(
            strategy=ResolutionStrategy.USE_VIRTUALENV,
            description="Create virtual environment",
            command="python3 -m venv .venv",
            safety_score=0.95,
            side_effects=["Isolates packages"],
            recommended=True,
        )

        self.assertEqual(suggestion.strategy, ResolutionStrategy.USE_VIRTUALENV)
        self.assertEqual(suggestion.safety_score, 0.95)
        self.assertTrue(suggestion.recommended)


class TestEnums(unittest.TestCase):
    """Test enum values"""

    def test_conflict_severity_values(self):
        """Test ConflictSeverity enum values"""
        self.assertEqual(ConflictSeverity.LOW.value, "low")
        self.assertEqual(ConflictSeverity.MEDIUM.value, "medium")
        self.assertEqual(ConflictSeverity.HIGH.value, "high")
        self.assertEqual(ConflictSeverity.CRITICAL.value, "critical")

    def test_resolution_strategy_values(self):
        """Test ResolutionStrategy enum values"""
        self.assertEqual(ResolutionStrategy.UPGRADE_PACKAGE.value, "upgrade_package")
        self.assertEqual(ResolutionStrategy.USE_VIRTUALENV.value, "use_virtualenv")
        self.assertEqual(ResolutionStrategy.SKIP_INSTALL.value, "skip_install")

    def test_package_ecosystem_values(self):
        """Test PackageEcosystem enum values"""
        self.assertEqual(PackageEcosystem.APT.value, "apt")
        self.assertEqual(PackageEcosystem.PIP.value, "pip")
        self.assertEqual(PackageEcosystem.NPM.value, "npm")


if __name__ == "__main__":
    unittest.main()
