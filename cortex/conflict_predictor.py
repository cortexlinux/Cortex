#!/usr/bin/env python3
"""
AI-Powered Dependency Conflict Predictor

Predicts dependency conflicts BEFORE installation starts using:
- Local dependency graph analysis
- System state from dpkg/apt
- Pip package metadata
- AI-powered conflict pattern recognition
- Confidence scoring and resolution suggestions
"""

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConflictSeverity(Enum):
    """Severity levels for predicted conflicts"""

    LOW = "low"  # Minor version mismatch, likely compatible
    MEDIUM = "medium"  # Potential issues, may need attention
    HIGH = "high"  # Likely to cause problems
    CRITICAL = "critical"  # Will definitely fail


class ResolutionStrategy(Enum):
    """Types of resolution strategies"""

    UPGRADE_PACKAGE = "upgrade_package"  # Upgrade target to compatible version
    DOWNGRADE_DEPENDENCY = "downgrade_dependency"  # Downgrade existing package
    USE_VIRTUALENV = "use_virtualenv"  # Isolate in virtual environment
    REMOVE_CONFLICTING = "remove_conflicting"  # Remove conflicting package
    INSTALL_ALTERNATIVE = "install_alternative"  # Use alternative package
    PIN_VERSION = "pin_version"  # Pin specific compatible version
    SKIP_INSTALL = "skip_install"  # Skip this package entirely


class PackageEcosystem(Enum):
    """Package ecosystems supported for conflict detection"""

    APT = "apt"  # Debian/Ubuntu apt packages
    PIP = "pip"  # Python pip packages
    NPM = "npm"  # Node.js npm packages
    SYSTEM = "system"  # System-level conflicts


@dataclass
class InstalledPackage:
    """Represents an installed package"""

    name: str
    version: str
    ecosystem: PackageEcosystem
    source: str = ""  # What installed this package


@dataclass
class VersionConstraint:
    """Version constraint for a dependency"""

    operator: str  # <, <=, ==, >=, >, !=, ~=
    version: str
    original: str = ""  # Original constraint string


@dataclass
class DependencyRequirement:
    """A package's dependency requirement"""

    package_name: str
    constraints: list[VersionConstraint]
    is_optional: bool = False
    extras: list[str] = field(default_factory=list)


@dataclass
class PredictedConflict:
    """A predicted dependency conflict"""

    package_to_install: str
    package_version: str | None
    conflicting_package: str
    conflicting_version: str
    installed_by: str  # What package installed the conflicting dependency
    conflict_type: str  # version_mismatch, mutual_exclusion, etc.
    severity: ConflictSeverity
    confidence: float  # 0.0 to 1.0
    description: str
    ecosystem: PackageEcosystem


@dataclass
class ResolutionSuggestion:
    """A suggested resolution for a conflict"""

    strategy: ResolutionStrategy
    description: str
    command: str | None
    safety_score: float  # 0.0 to 1.0 (higher = safer)
    side_effects: list[str]
    recommended: bool = False


@dataclass
class ConflictPrediction:
    """Complete conflict prediction result"""

    package_name: str
    package_version: str | None
    conflicts: list[PredictedConflict]
    resolutions: list[ResolutionSuggestion]
    overall_risk: ConflictSeverity
    can_proceed: bool
    prediction_confidence: float
    analysis_details: dict[str, Any] = field(default_factory=dict)


class DependencyConflictPredictor:
    """
    AI-powered dependency conflict prediction engine.

    Analyzes dependency graphs and predicts conflicts BEFORE installation,
    providing resolution suggestions ranked by safety.
    """

    # Known version conflict patterns (pre-trained knowledge)
    KNOWN_CONFLICTS = {
        # Python/pip conflicts
        "tensorflow": {
            "numpy": {"max_version": "2.0.0", "reason": "TensorFlow <2.16 requires numpy<2.0"},
            "protobuf": {"max_version": "4.0.0", "reason": "TensorFlow requires specific protobuf"},
        },
        "torch": {
            "numpy": {"min_version": "1.19.0", "reason": "PyTorch requires numpy>=1.19"},
        },
        "pandas": {
            "numpy": {"min_version": "1.20.0", "reason": "Pandas 2.x requires numpy>=1.20"},
        },
        "scipy": {
            "numpy": {"min_version": "1.19.0", "reason": "SciPy requires numpy>=1.19"},
        },
        # APT package conflicts
        "mysql-server": {
            "mariadb-server": {"mutual_exclusion": True, "reason": "Cannot have both MySQL and MariaDB"},
        },
        "mariadb-server": {
            "mysql-server": {"mutual_exclusion": True, "reason": "Cannot have both MariaDB and MySQL"},
        },
        "apache2": {
            "nginx": {"port_conflict": True, "reason": "Both use port 80 by default"},
        },
        "nginx": {
            "apache2": {"port_conflict": True, "reason": "Both use port 80 by default"},
        },
        "python3.10": {
            "python3.11": {"conflict_type": "alternative", "reason": "Different Python versions"},
            "python3.12": {"conflict_type": "alternative", "reason": "Different Python versions"},
        },
    }

    # Common transitive dependency issues
    TRANSITIVE_PATTERNS = {
        "grpcio": ["protobuf"],
        "tensorflow": ["numpy", "protobuf", "grpcio", "h5py"],
        "torch": ["numpy", "pillow", "typing-extensions"],
        "pandas": ["numpy", "python-dateutil", "pytz"],
        "scikit-learn": ["numpy", "scipy", "joblib"],
        "matplotlib": ["numpy", "pillow", "pyparsing"],
    }

    def __init__(self, llm_router=None):
        """
        Initialize the conflict predictor.

        Args:
            llm_router: Optional LLMRouter instance for AI-powered analysis
        """
        self.llm_router = llm_router
        self._installed_apt_cache: dict[str, InstalledPackage] = {}
        self._installed_pip_cache: dict[str, InstalledPackage] = {}
        self._refresh_caches()

    def _run_command(self, cmd: list[str], timeout: int = 30) -> tuple[bool, str, str]:
        """Execute command and return success, stdout, stderr"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return (result.returncode == 0, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "", "Command timed out")
        except FileNotFoundError:
            return (False, "", f"Command not found: {cmd[0]}")
        except Exception as e:
            return (False, "", str(e))

    def _refresh_caches(self) -> None:
        """Refresh caches of installed packages"""
        self._refresh_apt_cache()
        self._refresh_pip_cache()

    def _refresh_apt_cache(self) -> None:
        """Parse dpkg status to get installed apt packages"""
        logger.debug("Refreshing apt package cache...")
        self._installed_apt_cache = {}

        success, stdout, _ = self._run_command(["dpkg-query", "-W", "-f=${Package} ${Version}\n"])
        if success:
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split(maxsplit=1)
                    if len(parts) >= 2:
                        name, version = parts[0], parts[1]
                        self._installed_apt_cache[name] = InstalledPackage(
                            name=name,
                            version=version,
                            ecosystem=PackageEcosystem.APT,
                            source="dpkg",
                        )

        logger.debug(f"Found {len(self._installed_apt_cache)} installed apt packages")

    def _refresh_pip_cache(self) -> None:
        """Get installed pip packages using pip list"""
        logger.debug("Refreshing pip package cache...")
        self._installed_pip_cache = {}

        # Try pip3 first, then pip
        for pip_cmd in ["pip3", "pip"]:
            success, stdout, _ = self._run_command([pip_cmd, "list", "--format=json"])
            if success:
                try:
                    packages = json.loads(stdout)
                    for pkg in packages:
                        name = pkg.get("name", "").lower()
                        version = pkg.get("version", "")
                        if name:
                            self._installed_pip_cache[name] = InstalledPackage(
                                name=name,
                                version=version,
                                ecosystem=PackageEcosystem.PIP,
                                source=pip_cmd,
                            )
                    logger.debug(f"Found {len(self._installed_pip_cache)} installed pip packages")
                    return
                except json.JSONDecodeError:
                    continue

    def _parse_version_constraint(self, constraint: str) -> VersionConstraint | None:
        """Parse a version constraint string like '>=1.0,<2.0'"""
        constraint = constraint.strip()
        if not constraint:
            return None

        # Handle operators
        operators = ["<=", ">=", "==", "!=", "~=", "<", ">"]
        for op in operators:
            if constraint.startswith(op):
                version = constraint[len(op) :].strip()
                return VersionConstraint(operator=op, version=version, original=constraint)

        # No operator means exact match
        return VersionConstraint(operator="==", version=constraint, original=constraint)

    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two version strings.
        Returns: -1 if v1 < v2, 0 if equal, 1 if v1 > v2
        """

        def normalize(v: str) -> list[int]:
            parts = []
            for part in re.split(r"[.\-+]", v):
                # Extract numeric prefix
                match = re.match(r"(\d+)", part)
                if match:
                    parts.append(int(match.group(1)))
            return parts

        v1_parts = normalize(v1)
        v2_parts = normalize(v2)

        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        for p1, p2 in zip(v1_parts, v2_parts):
            if p1 < p2:
                return -1
            if p1 > p2:
                return 1
        return 0

    def _check_version_satisfies(self, installed_version: str, constraint: VersionConstraint) -> bool:
        """Check if installed version satisfies a constraint"""
        cmp = self._compare_versions(installed_version, constraint.version)

        if constraint.operator == "==":
            return cmp == 0
        elif constraint.operator == "!=":
            return cmp != 0
        elif constraint.operator == "<":
            return cmp < 0
        elif constraint.operator == "<=":
            return cmp <= 0
        elif constraint.operator == ">":
            return cmp > 0
        elif constraint.operator == ">=":
            return cmp >= 0
        elif constraint.operator == "~=":
            # Compatible release (e.g., ~=1.4 means >=1.4, <2.0)
            return cmp >= 0  # Simplified
        return True

    def _get_pip_package_requirements(self, package_name: str) -> list[DependencyRequirement]:
        """Get requirements for a pip package using pip show"""
        requirements = []

        success, stdout, _ = self._run_command(["pip3", "show", package_name])
        if not success:
            success, stdout, _ = self._run_command(["pip", "show", package_name])

        if success:
            for line in stdout.split("\n"):
                if line.startswith("Requires:"):
                    deps = line.split(":", 1)[1].strip()
                    if deps:
                        for dep in deps.split(","):
                            dep = dep.strip()
                            if dep:
                                requirements.append(
                                    DependencyRequirement(
                                        package_name=dep.lower(),
                                        constraints=[],
                                    )
                                )

        return requirements

    def _get_apt_package_requirements(self, package_name: str) -> list[DependencyRequirement]:
        """Get requirements for an apt package"""
        requirements = []

        success, stdout, _ = self._run_command(["apt-cache", "depends", package_name])
        if success:
            for line in stdout.split("\n"):
                line = line.strip()
                if line.startswith("Depends:"):
                    dep_name = line.split(":", 1)[1].strip()
                    # Handle alternatives
                    if "|" in dep_name:
                        dep_name = dep_name.split("|")[0].strip()
                    # Remove version constraint for simple matching
                    dep_name = re.sub(r"\s*\(.*?\)", "", dep_name)
                    if dep_name:
                        requirements.append(
                            DependencyRequirement(
                                package_name=dep_name,
                                constraints=[],
                            )
                        )

        return requirements

    def _analyze_known_conflicts(
        self, package_name: str, ecosystem: PackageEcosystem
    ) -> list[PredictedConflict]:
        """Check against known conflict patterns"""
        conflicts = []
        pkg_lower = package_name.lower()

        if pkg_lower not in self.KNOWN_CONFLICTS:
            return conflicts

        known = self.KNOWN_CONFLICTS[pkg_lower]
        cache = self._installed_pip_cache if ecosystem == PackageEcosystem.PIP else self._installed_apt_cache

        for dep_name, constraint_info in known.items():
            if dep_name in cache:
                installed = cache[dep_name]

                # Check for mutual exclusion
                if constraint_info.get("mutual_exclusion"):
                    conflicts.append(
                        PredictedConflict(
                            package_to_install=package_name,
                            package_version=None,
                            conflicting_package=dep_name,
                            conflicting_version=installed.version,
                            installed_by="system",
                            conflict_type="mutual_exclusion",
                            severity=ConflictSeverity.CRITICAL,
                            confidence=0.95,
                            description=constraint_info.get("reason", "Packages are mutually exclusive"),
                            ecosystem=ecosystem,
                        )
                    )
                    continue

                # Check for port conflicts
                if constraint_info.get("port_conflict"):
                    conflicts.append(
                        PredictedConflict(
                            package_to_install=package_name,
                            package_version=None,
                            conflicting_package=dep_name,
                            conflicting_version=installed.version,
                            installed_by="system",
                            conflict_type="port_conflict",
                            severity=ConflictSeverity.HIGH,
                            confidence=0.85,
                            description=constraint_info.get("reason", "Services use same port"),
                            ecosystem=ecosystem,
                        )
                    )
                    continue

                # Check version constraints
                max_ver = constraint_info.get("max_version")
                min_ver = constraint_info.get("min_version")

                if max_ver:
                    if self._compare_versions(installed.version, max_ver) >= 0:
                        conflicts.append(
                            PredictedConflict(
                                package_to_install=package_name,
                                package_version=None,
                                conflicting_package=dep_name,
                                conflicting_version=installed.version,
                                installed_by="unknown",
                                conflict_type="version_too_high",
                                severity=ConflictSeverity.HIGH,
                                confidence=0.9,
                                description=f"{constraint_info.get('reason', '')} "
                                f"(requires {dep_name}<{max_ver}, you have {installed.version})",
                                ecosystem=ecosystem,
                            )
                        )

                if min_ver:
                    if self._compare_versions(installed.version, min_ver) < 0:
                        conflicts.append(
                            PredictedConflict(
                                package_to_install=package_name,
                                package_version=None,
                                conflicting_package=dep_name,
                                conflicting_version=installed.version,
                                installed_by="unknown",
                                conflict_type="version_too_low",
                                severity=ConflictSeverity.MEDIUM,
                                confidence=0.85,
                                description=f"{constraint_info.get('reason', '')} "
                                f"(requires {dep_name}>={min_ver}, you have {installed.version})",
                                ecosystem=ecosystem,
                            )
                        )

        return conflicts

    def _analyze_transitive_conflicts(
        self, package_name: str, ecosystem: PackageEcosystem
    ) -> list[PredictedConflict]:
        """Analyze potential transitive dependency conflicts"""
        conflicts = []
        pkg_lower = package_name.lower()

        if pkg_lower not in self.TRANSITIVE_PATTERNS:
            return conflicts

        transitive_deps = self.TRANSITIVE_PATTERNS[pkg_lower]
        cache = self._installed_pip_cache if ecosystem == PackageEcosystem.PIP else self._installed_apt_cache

        # Check if any transitive dependencies are installed and might conflict
        for dep in transitive_deps:
            if dep in self.KNOWN_CONFLICTS.get(pkg_lower, {}):
                # Already handled by known conflicts
                continue

            if dep in cache:
                # Check if this dep has known conflicts with other installed packages
                for other_pkg, other_info in cache.items():
                    if other_pkg == dep:
                        continue
                    if dep in self.KNOWN_CONFLICTS.get(other_pkg, {}):
                        conflicts.append(
                            PredictedConflict(
                                package_to_install=package_name,
                                package_version=None,
                                conflicting_package=dep,
                                conflicting_version=cache[dep].version,
                                installed_by=other_pkg,
                                conflict_type="transitive_conflict",
                                severity=ConflictSeverity.MEDIUM,
                                confidence=0.7,
                                description=f"Installing {package_name} may affect {dep} "
                                f"which is also used by {other_pkg}",
                                ecosystem=ecosystem,
                            )
                        )

        return conflicts

    def _generate_resolutions(
        self, conflicts: list[PredictedConflict], package_name: str
    ) -> list[ResolutionSuggestion]:
        """Generate resolution suggestions for conflicts"""
        resolutions: list[ResolutionSuggestion] = []

        if not conflicts:
            return resolutions

        # Group by severity
        critical_conflicts = [c for c in conflicts if c.severity == ConflictSeverity.CRITICAL]
        high_conflicts = [c for c in conflicts if c.severity == ConflictSeverity.HIGH]
        medium_conflicts = [c for c in conflicts if c.severity == ConflictSeverity.MEDIUM]

        # Handle critical conflicts first
        for conflict in critical_conflicts:
            if conflict.conflict_type == "mutual_exclusion":
                resolutions.append(
                    ResolutionSuggestion(
                        strategy=ResolutionStrategy.REMOVE_CONFLICTING,
                        description=f"Remove {conflict.conflicting_package} before installing {package_name}",
                        command=f"sudo apt-get remove {conflict.conflicting_package}",
                        safety_score=0.4,
                        side_effects=[
                            f"Will remove {conflict.conflicting_package} and dependent packages",
                            "May affect running services",
                        ],
                        recommended=False,
                    )
                )
                resolutions.append(
                    ResolutionSuggestion(
                        strategy=ResolutionStrategy.SKIP_INSTALL,
                        description=f"Skip installing {package_name}, keep {conflict.conflicting_package}",
                        command=None,
                        safety_score=0.9,
                        side_effects=["Target package will not be installed"],
                        recommended=True,
                    )
                )

        # Handle version conflicts
        for conflict in high_conflicts + medium_conflicts:
            if conflict.conflict_type in ["version_too_high", "version_too_low"]:
                # Suggest virtual environment for pip packages
                if conflict.ecosystem == PackageEcosystem.PIP:
                    resolutions.append(
                        ResolutionSuggestion(
                            strategy=ResolutionStrategy.USE_VIRTUALENV,
                            description=f"Create virtual environment to isolate {package_name}",
                            command=f"python3 -m venv .venv && source .venv/bin/activate && pip install {package_name}",
                            safety_score=0.95,
                            side_effects=["Package installed in isolated environment only"],
                            recommended=True,
                        )
                    )

                # Suggest upgrading/downgrading
                if conflict.conflict_type == "version_too_high":
                    resolutions.append(
                        ResolutionSuggestion(
                            strategy=ResolutionStrategy.UPGRADE_PACKAGE,
                            description=f"Install newer version of {package_name} that supports {conflict.conflicting_package} {conflict.conflicting_version}",
                            command=f"pip install --upgrade {package_name}",
                            safety_score=0.8,
                            side_effects=["May get different version than expected"],
                            recommended=True,
                        )
                    )
                    resolutions.append(
                        ResolutionSuggestion(
                            strategy=ResolutionStrategy.DOWNGRADE_DEPENDENCY,
                            description=f"Downgrade {conflict.conflicting_package} to compatible version",
                            command=f"pip install {conflict.conflicting_package}<{conflict.conflicting_version}",
                            safety_score=0.5,
                            side_effects=[
                                f"May break packages depending on {conflict.conflicting_package}"
                            ],
                            recommended=False,
                        )
                    )

            if conflict.conflict_type == "port_conflict":
                resolutions.append(
                    ResolutionSuggestion(
                        strategy=ResolutionStrategy.PIN_VERSION,
                        description=f"Configure {package_name} to use a different port",
                        command=None,
                        safety_score=0.85,
                        side_effects=["Requires manual configuration"],
                        recommended=True,
                    )
                )

        # Sort by safety score (highest first)
        resolutions.sort(key=lambda r: (-r.safety_score, not r.recommended))

        # Mark the safest recommended option
        for i, res in enumerate(resolutions):
            if res.recommended:
                resolutions[i] = ResolutionSuggestion(
                    strategy=res.strategy,
                    description=res.description + " [RECOMMENDED]",
                    command=res.command,
                    safety_score=res.safety_score,
                    side_effects=res.side_effects,
                    recommended=True,
                )
                break

        return resolutions

    def _determine_overall_risk(self, conflicts: list[PredictedConflict]) -> ConflictSeverity:
        """Determine overall risk level from conflicts"""
        if not conflicts:
            return ConflictSeverity.LOW

        severities = [c.severity for c in conflicts]

        if ConflictSeverity.CRITICAL in severities:
            return ConflictSeverity.CRITICAL
        if ConflictSeverity.HIGH in severities:
            return ConflictSeverity.HIGH
        if ConflictSeverity.MEDIUM in severities:
            return ConflictSeverity.MEDIUM
        return ConflictSeverity.LOW

    def _detect_ecosystem(self, package_name: str) -> PackageEcosystem:
        """Detect which ecosystem a package belongs to"""
        # Check if it's a known pip package
        pip_indicators = [
            "numpy",
            "pandas",
            "tensorflow",
            "torch",
            "pytorch",
            "flask",
            "django",
            "requests",
            "scipy",
            "matplotlib",
            "scikit-learn",
            "pillow",
        ]
        if package_name.lower() in pip_indicators:
            return PackageEcosystem.PIP

        # Check if it's a known apt package
        apt_indicators = [
            "nginx",
            "apache2",
            "mysql-server",
            "mariadb-server",
            "postgresql",
            "redis-server",
            "docker",
            "nodejs",
        ]
        if package_name.lower() in apt_indicators:
            return PackageEcosystem.APT

        # Try to detect by checking package availability
        success, _, _ = self._run_command(["apt-cache", "show", package_name])
        if success:
            return PackageEcosystem.APT

        success, _, _ = self._run_command(["pip3", "show", package_name])
        if success:
            return PackageEcosystem.PIP

        # Default to system for unknown
        return PackageEcosystem.SYSTEM

    async def predict_conflicts_async(
        self, package_name: str, version: str | None = None
    ) -> ConflictPrediction:
        """
        Async version that uses LLM for enhanced conflict analysis.
        """
        # Start with local analysis
        prediction = self.predict_conflicts(package_name, version)

        # If LLM router available, enhance with AI analysis
        if self.llm_router and prediction.conflicts:
            try:
                from cortex.llm_router import TaskType

                # Build context for LLM
                conflict_descriptions = [
                    f"- {c.conflicting_package} {c.conflicting_version}: {c.description}"
                    for c in prediction.conflicts
                ]

                prompt = f"""Analyze these potential dependency conflicts for installing {package_name}:

{chr(10).join(conflict_descriptions)}

Installed packages context:
- Pip packages: {len(self._installed_pip_cache)}
- Apt packages: {len(self._installed_apt_cache)}

Provide:
1. Risk assessment (low/medium/high/critical)
2. Most likely cause of conflicts
3. Best resolution approach
4. Any additional conflicts I might have missed

Be concise and actionable."""

                response = await self.llm_router.acomplete(
                    messages=[
                        {"role": "system", "content": "You are a Linux package dependency expert."},
                        {"role": "user", "content": prompt},
                    ],
                    task_type=TaskType.DEPENDENCY_RESOLUTION,
                    temperature=0.3,
                    max_tokens=1000,
                )

                # Add LLM analysis to details
                prediction.analysis_details["llm_analysis"] = response.content
                prediction.analysis_details["llm_provider"] = response.provider.value

            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")
                prediction.analysis_details["llm_error"] = str(e)

        return prediction

    def predict_conflicts(
        self, package_name: str, version: str | None = None
    ) -> ConflictPrediction:
        """
        Predict potential conflicts before installing a package.

        Args:
            package_name: Name of package to install
            version: Optional specific version to install

        Returns:
            ConflictPrediction with all conflicts and resolutions
        """
        logger.info(f"Predicting conflicts for {package_name}...")

        # Refresh caches for latest state
        self._refresh_caches()

        # Detect ecosystem
        ecosystem = self._detect_ecosystem(package_name)
        logger.debug(f"Detected ecosystem: {ecosystem.value}")

        all_conflicts: list[PredictedConflict] = []

        # 1. Check known conflict patterns
        known_conflicts = self._analyze_known_conflicts(package_name, ecosystem)
        all_conflicts.extend(known_conflicts)

        # 2. Analyze transitive dependencies
        transitive_conflicts = self._analyze_transitive_conflicts(package_name, ecosystem)
        all_conflicts.extend(transitive_conflicts)

        # 3. Generate resolutions
        resolutions = self._generate_resolutions(all_conflicts, package_name)

        # 4. Determine overall risk
        overall_risk = self._determine_overall_risk(all_conflicts)

        # 5. Calculate can_proceed
        can_proceed = overall_risk != ConflictSeverity.CRITICAL

        # 6. Calculate prediction confidence
        if all_conflicts:
            avg_confidence = sum(c.confidence for c in all_conflicts) / len(all_conflicts)
        else:
            avg_confidence = 0.9  # High confidence that there are no conflicts

        prediction = ConflictPrediction(
            package_name=package_name,
            package_version=version,
            conflicts=all_conflicts,
            resolutions=resolutions,
            overall_risk=overall_risk,
            can_proceed=can_proceed,
            prediction_confidence=avg_confidence,
            analysis_details={
                "ecosystem": ecosystem.value,
                "installed_pip_packages": len(self._installed_pip_cache),
                "installed_apt_packages": len(self._installed_apt_cache),
                "known_conflicts_checked": len(self.KNOWN_CONFLICTS),
                "transitive_patterns_checked": len(self.TRANSITIVE_PATTERNS),
            },
        )

        return prediction

    def predict_multiple(self, packages: list[str]) -> list[ConflictPrediction]:
        """
        Predict conflicts for multiple packages.

        Args:
            packages: List of package names

        Returns:
            List of ConflictPrediction objects
        """
        predictions = []
        for pkg in packages:
            prediction = self.predict_conflicts(pkg)
            predictions.append(prediction)
        return predictions

    def format_prediction(self, prediction: ConflictPrediction) -> str:
        """Format prediction for CLI output"""
        lines = []

        if not prediction.conflicts:
            lines.append(f"No conflicts predicted for {prediction.package_name}")
            lines.append(f"   Confidence: {prediction.prediction_confidence:.0%}")
            return "\n".join(lines)

        # Header with risk indicator
        risk_emoji = {
            ConflictSeverity.LOW: "",
            ConflictSeverity.MEDIUM: "",
            ConflictSeverity.HIGH: "",
            ConflictSeverity.CRITICAL: "",
        }

        lines.append(
            f"{risk_emoji.get(prediction.overall_risk, '')}  "
            f"Conflict predicted for {prediction.package_name}"
        )
        lines.append("")

        # List conflicts
        for i, conflict in enumerate(prediction.conflicts, 1):
            severity_badge = f"[{conflict.severity.value.upper()}]"
            lines.append(f"   {i}. {severity_badge} {conflict.description}")
            lines.append(
                f"      Package: {conflict.conflicting_package} {conflict.conflicting_version}"
            )
            lines.append(f"      Type: {conflict.conflict_type}")
            lines.append(f"      Confidence: {conflict.confidence:.0%}")
            lines.append("")

        # Suggestions
        if prediction.resolutions:
            lines.append("   Suggestions (ranked by safety):")
            for i, res in enumerate(prediction.resolutions[:4], 1):
                recommended = " [RECOMMENDED]" if res.recommended else ""
                lines.append(f"   {i}. {res.description}")
                if res.command:
                    lines.append(f"      Command: {res.command}")
                lines.append(f"      Safety: {res.safety_score:.0%}{recommended}")
                if res.side_effects:
                    lines.append(f"      Note: {res.side_effects[0]}")
                lines.append("")

        return "\n".join(lines)

    def export_prediction_json(self, prediction: ConflictPrediction) -> dict[str, Any]:
        """Export prediction to JSON-serializable dict"""
        return {
            "package_name": prediction.package_name,
            "package_version": prediction.package_version,
            "conflicts": [
                {
                    "package_to_install": c.package_to_install,
                    "conflicting_package": c.conflicting_package,
                    "conflicting_version": c.conflicting_version,
                    "conflict_type": c.conflict_type,
                    "severity": c.severity.value,
                    "confidence": c.confidence,
                    "description": c.description,
                    "ecosystem": c.ecosystem.value,
                }
                for c in prediction.conflicts
            ],
            "resolutions": [
                {
                    "strategy": r.strategy.value,
                    "description": r.description,
                    "command": r.command,
                    "safety_score": r.safety_score,
                    "side_effects": r.side_effects,
                    "recommended": r.recommended,
                }
                for r in prediction.resolutions
            ],
            "overall_risk": prediction.overall_risk.value,
            "can_proceed": prediction.can_proceed,
            "prediction_confidence": prediction.prediction_confidence,
            "analysis_details": prediction.analysis_details,
        }


# CLI Interface
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Predict dependency conflicts before installation")
    parser.add_argument("package", help="Package name to analyze")
    parser.add_argument("--version", "-v", help="Specific version to check")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    predictor = DependencyConflictPredictor()
    prediction = predictor.predict_conflicts(args.package, args.version)

    if args.json:
        print(json.dumps(predictor.export_prediction_json(prediction), indent=2))
    else:
        print(predictor.format_prediction(prediction))

        if prediction.overall_risk == ConflictSeverity.CRITICAL:
            sys.exit(1)
        elif prediction.overall_risk == ConflictSeverity.HIGH:
            sys.exit(2)
