"""
Unit tests for AI-Powered Dependency Conflict Predictor

Tests cover:
- Rule-based conflict detection
- Resolution strategy generation
- Safety score calculation
- System state parsing
- Version constraint parsing and comparison
- Display formatting
"""

import json
import unittest
from unittest.mock import MagicMock, Mock, patch

from cortex.conflict_predictor import (
    ConflictPrediction,
    ConflictPredictor,
    ConflictType,
    ResolutionStrategy,
    StrategyType,
    check_version_constraint,
    compare_versions,
    find_compatible_version,
    format_conflict_summary,
    format_conflicts_for_display,
    format_resolutions_for_display,
    get_pip_packages,
    parse_dpkg_status,
    parse_version,
)
from cortex.dependency_resolver import Dependency, DependencyGraph


class TestConflictPrediction(unittest.TestCase):
    """Test ConflictPrediction data class"""

    def test_conflict_prediction_creation(self):
        """Test creating a conflict prediction"""
        conflict = ConflictPrediction(
            package1="tensorflow",
            package2="numpy",
            conflict_type=ConflictType.VERSION,
            confidence=0.95,
            explanation="Version mismatch",
            severity="HIGH",
        )

        self.assertEqual(conflict.package1, "tensorflow")
        self.assertEqual(conflict.package2, "numpy")
        self.assertEqual(conflict.confidence, 0.95)
        self.assertEqual(conflict.severity, "HIGH")

    def test_conflict_to_dict(self):
        """Test converting conflict to dictionary"""
        conflict = ConflictPrediction(
            package1="mysql-server",
            package2="mariadb-server",
            conflict_type=ConflictType.MUTUAL_EXCLUSION,
            confidence=1.0,
            explanation="Cannot coexist",
        )

        conflict_dict = conflict.to_dict()
        self.assertEqual(conflict_dict["package1"], "mysql-server")
        self.assertEqual(conflict_dict["conflict_type"], "mutual_exclusion")


class TestResolutionStrategy(unittest.TestCase):
    """Test ResolutionStrategy data class"""

    def test_resolution_strategy_creation(self):
        """Test creating a resolution strategy"""
        strategy = ResolutionStrategy(
            strategy_type=StrategyType.UPGRADE,
            description="Upgrade to version 2.16",
            safety_score=0.85,
            commands=["sudo apt-get install tensorflow=2.16"],
            risks=["May break compatibility"],
            estimated_time_minutes=3.0,
        )

        self.assertEqual(strategy.strategy_type, StrategyType.UPGRADE)
        self.assertEqual(strategy.safety_score, 0.85)
        self.assertEqual(len(strategy.commands), 1)

    def test_strategy_to_dict(self):
        """Test converting strategy to dictionary"""
        strategy = ResolutionStrategy(
            strategy_type=StrategyType.VENV,
            description="Use virtual environment",
            safety_score=0.95,
            commands=["python3 -m venv myenv"],
        )

        strategy_dict = strategy.to_dict()
        self.assertEqual(strategy_dict["strategy_type"], "venv")
        self.assertEqual(strategy_dict["safety_score"], 0.95)


class TestConflictPredictor(unittest.TestCase):
    """Test ConflictPredictor class"""

    def setUp(self):
        """Set up test fixtures"""
        self.predictor = ConflictPredictor()

    def test_predictor_initialization(self):
        """Test predictor initializes correctly"""
        self.assertIsNotNone(self.predictor.dependency_resolver)
        self.assertIsNotNone(self.predictor.version_conflicts)
        self.assertIsNotNone(self.predictor.port_conflicts)
        self.assertIsNotNone(self.predictor.mutual_exclusions)

    def test_mutual_exclusion_patterns(self):
        """Test mutual exclusion patterns are loaded"""
        self.assertIn("mysql-server", self.predictor.mutual_exclusions)
        self.assertIn("mariadb-server", self.predictor.mutual_exclusions["mysql-server"])

    def test_port_conflict_patterns(self):
        """Test port conflict patterns are loaded"""
        self.assertIn(80, self.predictor.port_conflicts)
        self.assertIn("apache2", self.predictor.port_conflicts[80])
        self.assertIn("nginx", self.predictor.port_conflicts[80])

    @patch("cortex.conflict_predictor.DependencyResolver")
    def test_predict_conflicts_no_conflicts(self, mock_resolver):
        """Test prediction when no conflicts exist"""
        # Mock dependency graph with no conflicts
        mock_graph = MagicMock(spec=DependencyGraph)
        mock_graph.all_dependencies = []
        mock_graph.conflicts = []

        mock_resolver_instance = Mock()
        mock_resolver_instance.resolve_dependencies.return_value = mock_graph
        self.predictor.dependency_resolver = mock_resolver_instance

        conflicts = self.predictor.predict_conflicts("nginx")

        self.assertEqual(len(conflicts), 0)

    @patch("cortex.conflict_predictor.DependencyResolver")
    def test_detect_mutual_exclusion(self, mock_resolver):
        """Test detection of mutual exclusion conflicts"""
        # Mock scenario: trying to install mysql-server when mariadb-server exists
        mock_graph = MagicMock(spec=DependencyGraph)
        mock_graph.all_dependencies = [
            Dependency(
                name="mariadb-server",
                version="10.6",
                is_satisfied=True,  # Already installed
            )
        ]
        mock_graph.conflicts = []

        mock_resolver_instance = Mock()
        mock_resolver_instance.resolve_dependencies.return_value = mock_graph
        self.predictor.dependency_resolver = mock_resolver_instance

        conflicts = self.predictor.predict_conflicts("mysql-server")

        self.assertGreater(len(conflicts), 0)
        conflict = conflicts[0]
        self.assertEqual(conflict.conflict_type, ConflictType.MUTUAL_EXCLUSION)
        self.assertEqual(conflict.confidence, 1.0)
        self.assertIn("mariadb-server", conflict.explanation)

    def test_deduplicate_conflicts(self):
        """Test conflict deduplication"""
        conflicts = [
            ConflictPrediction(
                package1="pkg1",
                package2="pkg2",
                conflict_type=ConflictType.VERSION,
                confidence=0.9,
                explanation="Test",
            ),
            ConflictPrediction(
                package1="pkg1",
                package2="pkg2",
                conflict_type=ConflictType.VERSION,
                confidence=0.8,
                explanation="Test duplicate",
            ),
            ConflictPrediction(
                package1="pkg3",
                package2="pkg4",
                conflict_type=ConflictType.PORT,
                confidence=0.95,
                explanation="Different conflict",
            ),
        ]

        unique = self.predictor._deduplicate_conflicts(conflicts)

        self.assertEqual(len(unique), 2)

    def test_is_complex_scenario(self):
        """Test complex scenario detection"""
        # Simple scenario
        simple_graph = MagicMock(spec=DependencyGraph)
        simple_graph.all_dependencies = [Dependency(name="pkg1")]
        simple_graph.conflicts = []

        self.assertFalse(self.predictor._is_complex_scenario(simple_graph))

        # Complex scenario (many dependencies)
        complex_graph = MagicMock(spec=DependencyGraph)
        complex_graph.all_dependencies = [Dependency(name=f"pkg{i}") for i in range(15)]
        complex_graph.conflicts = []

        self.assertTrue(self.predictor._is_complex_scenario(complex_graph))

        # Complex scenario (has conflicts)
        conflict_graph = MagicMock(spec=DependencyGraph)
        conflict_graph.all_dependencies = [Dependency(name="pkg1")]
        conflict_graph.conflicts = [("pkg1", "pkg2")]

        self.assertTrue(self.predictor._is_complex_scenario(conflict_graph))


class TestResolutionGeneration(unittest.TestCase):
    """Test resolution strategy generation"""

    def setUp(self):
        """Set up test fixtures"""
        self.predictor = ConflictPredictor()

    def test_generate_resolutions(self):
        """Test generating resolutions for conflicts"""
        conflicts = [
            ConflictPrediction(
                package1="tensorflow",
                package2="numpy",
                conflict_type=ConflictType.VERSION,
                confidence=0.95,
                explanation="Version conflict",
            )
        ]

        resolutions = self.predictor.generate_resolutions(conflicts)

        self.assertGreater(len(resolutions), 0)
        # Strategies should be sorted by safety score
        for i in range(len(resolutions) - 1):
            self.assertGreaterEqual(resolutions[i].safety_score, resolutions[i + 1].safety_score)

    def test_venv_strategy_generation(self):
        """Test virtual environment strategy is generated"""
        conflicts = [
            ConflictPrediction(
                package1="test-package",
                package2="conflict-package",
                conflict_type=ConflictType.VERSION,
                confidence=0.8,
                explanation="Test",
            )
        ]

        strategies = self.predictor._generate_strategies_for_conflict(conflicts[0])

        venv_strategies = [s for s in strategies if s.strategy_type == StrategyType.VENV]
        self.assertGreater(len(venv_strategies), 0)

        venv = venv_strategies[0]
        self.assertIn("venv", " ".join(venv.commands))

    def test_remove_conflict_strategy_generation(self):
        """Test removal strategy is generated (but with low safety)"""
        conflicts = [
            ConflictPrediction(
                package1="pkg1",
                package2="pkg2",
                conflict_type=ConflictType.MUTUAL_EXCLUSION,
                confidence=1.0,
                explanation="Test",
            )
        ]

        strategies = self.predictor._generate_strategies_for_conflict(conflicts[0])

        remove_strategies = [
            s for s in strategies if s.strategy_type == StrategyType.REMOVE_CONFLICT
        ]
        self.assertGreater(len(remove_strategies), 0)


class TestSafetyScore(unittest.TestCase):
    """Test safety score calculation"""

    def setUp(self):
        """Set up test fixtures"""
        self.predictor = ConflictPredictor()

    def test_venv_has_high_safety(self):
        """Test virtual environment has highest safety score"""
        strategy = ResolutionStrategy(
            strategy_type=StrategyType.VENV,
            description="Test",
            safety_score=0.0,
            commands=["test"],
        )

        score = self.predictor._calculate_safety_score(strategy)
        self.assertGreater(score, 0.9)

    def test_remove_has_low_safety(self):
        """Test removal has low safety score"""
        strategy = ResolutionStrategy(
            strategy_type=StrategyType.REMOVE_CONFLICT,
            description="Test",
            safety_score=0.0,
            commands=["test"],
        )

        score = self.predictor._calculate_safety_score(strategy)
        self.assertLess(score, 0.5)

    def test_risks_reduce_safety(self):
        """Test that risks reduce safety score"""
        no_risk = ResolutionStrategy(
            strategy_type=StrategyType.UPGRADE,
            description="Test",
            safety_score=0.0,
            commands=["test"],
            risks=[],
        )

        with_risks = ResolutionStrategy(
            strategy_type=StrategyType.UPGRADE,
            description="Test",
            safety_score=0.0,
            commands=["test"],
            risks=["Risk 1", "Risk 2", "Risk 3"],
        )

        score_no_risk = self.predictor._calculate_safety_score(no_risk)
        score_with_risks = self.predictor._calculate_safety_score(with_risks)

        self.assertGreater(score_no_risk, score_with_risks)

    def test_many_affected_packages_reduce_safety(self):
        """Test that affecting many packages reduces safety"""
        few_packages = ResolutionStrategy(
            strategy_type=StrategyType.UPGRADE,
            description="Test",
            safety_score=0.0,
            commands=["test"],
            affects_packages=["pkg1", "pkg2"],
        )

        many_packages = ResolutionStrategy(
            strategy_type=StrategyType.UPGRADE,
            description="Test",
            safety_score=0.0,
            commands=["test"],
            affects_packages=[f"pkg{i}" for i in range(15)],
        )

        score_few = self.predictor._calculate_safety_score(few_packages)
        score_many = self.predictor._calculate_safety_score(many_packages)

        self.assertGreater(score_few, score_many)


class TestSystemParsing(unittest.TestCase):
    """Test system state parsing functions"""

    @patch("builtins.open", create=True)
    def test_parse_dpkg_status(self, mock_open):
        """Test parsing dpkg status file"""
        mock_data = """Package: nginx
Status: install ok installed
Version: 1.18.0-1ubuntu1

Package: apache2
Status: install ok installed
Version: 2.4.41-4ubuntu3
"""
        mock_open.return_value.__enter__.return_value = mock_data.split("\n")

        packages = parse_dpkg_status()

        self.assertIn("nginx", packages)
        self.assertIn("apache2", packages)
        self.assertEqual(packages["nginx"]["version"], "1.18.0-1ubuntu1")

    @patch("subprocess.run")
    def test_get_pip_packages_success(self, mock_run):
        """Test getting pip packages successfully"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(
                [
                    {"name": "numpy", "version": "1.24.0"},
                    {"name": "pandas", "version": "2.0.0"},
                ]
            ),
        )

        packages = get_pip_packages()

        self.assertEqual(len(packages), 2)
        self.assertEqual(packages["numpy"], "1.24.0")
        self.assertEqual(packages["pandas"], "2.0.0")

    @patch("subprocess.run")
    def test_get_pip_packages_failure(self, mock_run):
        """Test handling pip failure gracefully"""
        mock_run.return_value = Mock(returncode=1, stdout="")

        packages = get_pip_packages()

        self.assertEqual(len(packages), 0)


class TestRecordResolution(unittest.TestCase):
    """Test recording conflict resolutions for learning"""

    def setUp(self):
        """Set up test fixtures"""
        self.predictor = ConflictPredictor()

    def test_record_successful_resolution(self):
        """Test recording a successful resolution"""
        conflict = ConflictPrediction(
            package1="tensorflow",
            package2="numpy",
            conflict_type=ConflictType.VERSION,
            confidence=0.95,
            explanation="Test",
        )

        strategy = ResolutionStrategy(
            strategy_type=StrategyType.UPGRADE,
            description="Upgrade tensorflow",
            safety_score=0.85,
            commands=["apt install tensorflow=2.16"],
        )

        # Should not raise exception
        self.predictor.record_resolution(conflict, strategy, success=True)

    def test_record_failed_resolution(self):
        """Test recording a failed resolution"""
        conflict = ConflictPrediction(
            package1="pkg1",
            package2="pkg2",
            conflict_type=ConflictType.VERSION,
            confidence=0.8,
            explanation="Test",
        )

        strategy = ResolutionStrategy(
            strategy_type=StrategyType.DOWNGRADE,
            description="Downgrade pkg2",
            safety_score=0.6,
            commands=["apt install pkg2=1.0"],
        )

        # Should not raise exception
        self.predictor.record_resolution(
            conflict, strategy, success=False, user_feedback="Did not work"
        )


class TestVersionParsing(unittest.TestCase):
    """Test version parsing and comparison functions"""

    def test_parse_version_simple(self):
        """Test parsing simple version strings"""
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("2.0"), (2, 0))
        self.assertEqual(parse_version("10.5.2"), (10, 5, 2))

    def test_parse_version_with_suffix(self):
        """Test parsing versions with suffixes like rc1, a1"""
        self.assertEqual(parse_version("2.0.0rc1"), (2, 0, 0))
        self.assertEqual(parse_version("1.5.0a1"), (1, 5, 0))
        self.assertEqual(parse_version("3.0dev"), (3, 0))

    def test_parse_version_empty(self):
        """Test parsing empty version string"""
        self.assertEqual(parse_version(""), (0,))
        self.assertEqual(parse_version(None), (0,))

    def test_compare_versions_equal(self):
        """Test comparing equal versions"""
        self.assertEqual(compare_versions("1.0.0", "1.0.0"), 0)
        self.assertEqual(compare_versions("2.5", "2.5.0"), 0)

    def test_compare_versions_less_than(self):
        """Test comparing versions where first is less"""
        self.assertEqual(compare_versions("1.0.0", "2.0.0"), -1)
        self.assertEqual(compare_versions("1.9.9", "2.0.0"), -1)
        self.assertEqual(compare_versions("1.0", "1.0.1"), -1)

    def test_compare_versions_greater_than(self):
        """Test comparing versions where first is greater"""
        self.assertEqual(compare_versions("2.0.0", "1.0.0"), 1)
        self.assertEqual(compare_versions("1.10.0", "1.9.0"), 1)
        self.assertEqual(compare_versions("2.0", "1.99.99"), 1)


class TestVersionConstraints(unittest.TestCase):
    """Test version constraint checking"""

    def test_less_than(self):
        """Test < operator"""
        self.assertTrue(check_version_constraint("1.9.0", "< 2.0"))
        self.assertFalse(check_version_constraint("2.0.0", "< 2.0"))
        self.assertFalse(check_version_constraint("2.1.0", "< 2.0"))

    def test_less_than_or_equal(self):
        """Test <= operator"""
        self.assertTrue(check_version_constraint("1.9.0", "<= 2.0"))
        self.assertTrue(check_version_constraint("2.0.0", "<= 2.0"))
        self.assertFalse(check_version_constraint("2.1.0", "<= 2.0"))

    def test_greater_than(self):
        """Test > operator"""
        self.assertTrue(check_version_constraint("2.1.0", "> 2.0"))
        self.assertFalse(check_version_constraint("2.0.0", "> 2.0"))
        self.assertFalse(check_version_constraint("1.9.0", "> 2.0"))

    def test_greater_than_or_equal(self):
        """Test >= operator"""
        self.assertTrue(check_version_constraint("2.1.0", ">= 2.0"))
        self.assertTrue(check_version_constraint("2.0.0", ">= 2.0"))
        self.assertFalse(check_version_constraint("1.9.0", ">= 2.0"))

    def test_equal(self):
        """Test == operator"""
        self.assertTrue(check_version_constraint("2.0.0", "== 2.0"))
        self.assertFalse(check_version_constraint("2.0.1", "== 2.0"))

    def test_not_equal(self):
        """Test != operator"""
        self.assertTrue(check_version_constraint("2.0.1", "!= 2.0"))
        self.assertFalse(check_version_constraint("2.0.0", "!= 2.0"))

    def test_implied_equal(self):
        """Test version without operator (implied ==)"""
        self.assertTrue(check_version_constraint("2.0.0", "2.0"))


class TestFindCompatibleVersion(unittest.TestCase):
    """Test finding compatible versions"""

    def test_find_compatible_less_than(self):
        """Test finding version less than constraint"""
        versions = ["2.1.0", "2.0.0", "1.9.0", "1.8.0"]
        result = find_compatible_version("numpy", "< 2.0", versions)
        self.assertEqual(result, "1.9.0")

    def test_find_compatible_greater_than(self):
        """Test finding version greater than constraint"""
        versions = ["1.5.0", "1.6.0", "1.7.0", "2.0.0"]
        result = find_compatible_version("pkg", ">= 1.6", versions)
        self.assertEqual(result, "2.0.0")  # Newest compatible

    def test_find_compatible_no_match(self):
        """Test when no compatible version exists"""
        versions = ["3.0.0", "3.1.0", "3.2.0"]
        result = find_compatible_version("pkg", "< 2.0", versions)
        self.assertIsNone(result)

    def test_find_compatible_empty_versions(self):
        """Test with empty versions list"""
        result = find_compatible_version("pkg", "< 2.0", [])
        self.assertIsNone(result)


class TestDisplayFormatting(unittest.TestCase):
    """Test display/UI formatting functions"""

    def test_format_conflicts_empty(self):
        """Test formatting with no conflicts"""
        result = format_conflicts_for_display([])
        self.assertIn("No conflicts predicted", result)

    def test_format_conflicts_with_data(self):
        """Test formatting conflicts with data"""
        conflicts = [
            ConflictPrediction(
                package1="tensorflow",
                package2="numpy",
                conflict_type=ConflictType.VERSION,
                confidence=0.95,
                explanation="tensorflow 2.15 requires numpy < 2.0",
                severity="HIGH",
                installed_by="pandas",
                current_version="2.1.0",
            )
        ]
        result = format_conflicts_for_display(conflicts)

        self.assertIn("tensorflow 2.15 requires numpy < 2.0", result)
        self.assertIn("pandas", result)
        self.assertIn("2.1.0", result)

    def test_format_resolutions_empty(self):
        """Test formatting with no resolutions"""
        result = format_resolutions_for_display([])
        self.assertIn("No automatic resolutions available", result)

    def test_format_resolutions_has_recommended(self):
        """Test that first resolution is marked as RECOMMENDED"""
        strategies = [
            ResolutionStrategy(
                strategy_type=StrategyType.UPGRADE,
                description="Upgrade to 2.16",
                safety_score=0.85,
                commands=["pip install tensorflow==2.16"],
            ),
            ResolutionStrategy(
                strategy_type=StrategyType.DOWNGRADE,
                description="Downgrade numpy",
                safety_score=0.60,
                commands=["pip install numpy==1.26.4"],
            ),
        ]
        result = format_resolutions_for_display(strategies)

        self.assertIn("[RECOMMENDED]", result)
        # RECOMMENDED should only appear once (for first item)
        self.assertEqual(result.count("[RECOMMENDED]"), 1)

    def test_format_resolutions_safety_bar(self):
        """Test that safety bar is shown"""
        strategies = [
            ResolutionStrategy(
                strategy_type=StrategyType.VENV,
                description="Use venv",
                safety_score=0.90,
                commands=["python3 -m venv myenv"],
            ),
        ]
        result = format_resolutions_for_display(strategies)

        self.assertIn("Safety:", result)
        self.assertIn("█", result)  # Should have filled blocks

    def test_format_conflict_summary(self):
        """Test complete conflict summary formatting"""
        conflicts = [
            ConflictPrediction(
                package1="tensorflow",
                package2="numpy",
                conflict_type=ConflictType.VERSION,
                confidence=0.95,
                explanation="Version conflict",
            )
        ]
        strategies = [
            ResolutionStrategy(
                strategy_type=StrategyType.UPGRADE,
                description="Upgrade",
                safety_score=0.85,
                commands=["pip install tensorflow==2.16"],
            ),
        ]
        result = format_conflict_summary(conflicts, strategies)

        self.assertIn("Conflict predicted", result)
        self.assertIn("Suggestions", result)
        self.assertIn("[RECOMMENDED]", result)


class TestConflictPredictionExtendedFields(unittest.TestCase):
    """Test extended fields in ConflictPrediction"""

    def test_conflict_with_installed_by(self):
        """Test conflict with installed_by field"""
        conflict = ConflictPrediction(
            package1="tensorflow",
            package2="numpy",
            conflict_type=ConflictType.VERSION,
            confidence=0.95,
            explanation="Version mismatch",
            installed_by="pandas",
            current_version="2.1.0",
            required_constraint="< 2.0",
        )

        self.assertEqual(conflict.installed_by, "pandas")
        self.assertEqual(conflict.current_version, "2.1.0")
        self.assertEqual(conflict.required_constraint, "< 2.0")

    def test_conflict_to_dict_with_extended_fields(self):
        """Test to_dict includes extended fields"""
        conflict = ConflictPrediction(
            package1="pkg1",
            package2="pkg2",
            conflict_type=ConflictType.VERSION,
            confidence=0.9,
            explanation="Test",
            installed_by="pkg3",
            current_version="1.0.0",
        )

        d = conflict.to_dict()
        self.assertEqual(d["installed_by"], "pkg3")
        self.assertEqual(d["current_version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
