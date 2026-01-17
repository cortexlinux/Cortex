#!/usr/bin/env python3
"""
AI-Powered Dependency Conflict Prediction

Issue: #428 - AI-powered dependency conflict prediction

Predicts dependency conflicts BEFORE installation starts.
Analyzes version constraints, detects transitive conflicts,
and suggests resolution strategies ranked by safety.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()


class ConflictType(Enum):
    """Types of dependency conflicts."""

    VERSION_MISMATCH = "version_mismatch"  # Incompatible version requirements
    PACKAGE_CONFLICT = "package_conflict"  # Mutually exclusive packages
    MISSING_DEPENDENCY = "missing_dependency"  # Required package not available
    CIRCULAR_DEPENDENCY = "circular_dependency"  # A depends on B depends on A
    FILE_CONFLICT = "file_conflict"  # Same file owned by multiple packages


class ResolutionSafety(Enum):
    """Safety level for resolution strategies."""

    SAFE = 1  # No risk, recommended
    LOW_RISK = 2  # Minor changes, likely safe
    MEDIUM_RISK = 3  # May affect other packages
    HIGH_RISK = 4  # Significant changes, manual review needed


@dataclass
class VersionConstraint:
    """Version constraint from apt/dpkg."""

    raw: str
    operator: str  # =, >=, <=, >>, <<
    version: str

    def satisfies(self, installed_version: str) -> bool:
        """Check if installed version satisfies this constraint."""
        if not installed_version or not self.version:
            return True

        try:
            result = subprocess.run(
                ["dpkg", "--compare-versions", installed_version, self.operator, self.version],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            # Fallback to string comparison
            if self.operator in ("=", "=="):
                return installed_version == self.version
            elif self.operator in (">=", "ge"):
                return installed_version >= self.version
            elif self.operator in ("<=", "le"):
                return installed_version <= self.version
            elif self.operator in (">>", "gt", ">"):
                return installed_version > self.version
            elif self.operator in ("<<", "lt", "<"):
                return installed_version < self.version
            return True


@dataclass
class InstalledPackage:
    """Represents an installed system package."""

    name: str
    version: str
    status: str = "installed"
    provides: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    breaks: list[str] = field(default_factory=list)


@dataclass
class PackageCandidate:
    """Package to be installed with its dependencies."""

    name: str
    version: str | None = None
    depends: list[tuple[str, VersionConstraint | None]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    breaks: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)


@dataclass
class PredictedConflict:
    """A predicted dependency conflict."""

    conflict_type: ConflictType
    package: str
    conflicting_with: str
    description: str
    installed_version: str | None = None
    required_version: str | None = None
    confidence: float = 1.0  # 0.0 to 1.0

    def __str__(self) -> str:
        return f"{self.conflict_type.value}: {self.package} vs {self.conflicting_with}"


@dataclass
class ResolutionStrategy:
    """A strategy for resolving a conflict."""

    name: str
    description: str
    safety: ResolutionSafety
    commands: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)

    @property
    def safety_score(self) -> int:
        """Lower is safer."""
        return self.safety.value


@dataclass
class ConflictPrediction:
    """Complete conflict prediction result."""

    package: str
    conflicts: list[PredictedConflict] = field(default_factory=list)
    resolutions: list[ResolutionStrategy] = field(default_factory=list)
    can_install: bool = True
    warnings: list[str] = field(default_factory=list)


class ConflictPredictor:
    """AI-powered dependency conflict predictor."""

    # Common package conflicts (expanded from dependency_resolver.py)
    KNOWN_CONFLICTS = {
        # Database conflicts
        "mysql-server": ["mariadb-server", "percona-server-server"],
        "mariadb-server": ["mysql-server", "percona-server-server"],
        "percona-server-server": ["mysql-server", "mariadb-server"],
        # Web server conflicts (port 80)
        "apache2": ["nginx-full", "nginx-light", "nginx-extras"],
        "nginx": ["apache2"],
        "nginx-full": ["apache2", "nginx-light", "nginx-extras"],
        "nginx-light": ["apache2", "nginx-full", "nginx-extras"],
        # MTA conflicts
        "postfix": ["exim4", "sendmail-bin"],
        "exim4": ["postfix", "sendmail-bin"],
        "sendmail-bin": ["postfix", "exim4"],
        # Python conflicts
        "python-is-python2": ["python-is-python3"],
        "python-is-python3": ["python-is-python2"],
        # Java conflicts
        "openjdk-8-jdk": [],
        "openjdk-11-jdk": [],
        "openjdk-17-jdk": [],
        # Docker conflicts
        "docker.io": ["docker-ce"],
        "docker-ce": ["docker.io"],
    }

    # Common Python package conflicts for pip
    PIP_CONFLICTS = {
        "tensorflow": {"numpy": "<2.0"},
        "tensorflow-gpu": {"numpy": "<2.0"},
        "torch": {},
        "numpy": {},
        "pandas": {"numpy": ">=1.20"},
    }

    def __init__(self, dpkg_status_path: str = "/var/lib/dpkg/status"):
        """Initialize the conflict predictor.

        Args:
            dpkg_status_path: Path to dpkg status file
        """
        self.dpkg_status_path = Path(dpkg_status_path)
        self._installed_cache: dict[str, InstalledPackage] = {}
        self._apt_cache: dict[str, PackageCandidate] = {}
        self._pip_cache: dict[str, tuple[str, str]] = {}  # name -> (version, location)
        self._refresh_installed_packages()

    def _run_command(self, cmd: list[str], timeout: int = 30) -> tuple[bool, str, str]:
        """Execute command and return success, stdout, stderr."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return (result.returncode == 0, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "", "Command timed out")
        except FileNotFoundError:
            return (False, "", f"Command not found: {cmd[0]}")
        except Exception as e:
            return (False, "", str(e))

    def _refresh_installed_packages(self) -> None:
        """Parse dpkg status to get installed packages."""
        logger.info("Parsing dpkg status...")
        self._installed_cache.clear()

        if not self.dpkg_status_path.exists():
            logger.warning(f"dpkg status file not found: {self.dpkg_status_path}")
            return

        try:
            content = self.dpkg_status_path.read_text()
        except Exception as e:
            logger.error(f"Failed to read dpkg status: {e}")
            return

        # Parse package entries
        current_pkg: dict = {}
        for line in content.split("\n"):
            if line.startswith("Package:"):
                if current_pkg.get("Package") and current_pkg.get("Status", "").startswith(
                    "install ok"
                ):
                    self._add_installed_package(current_pkg)
                current_pkg = {"Package": line.split(":", 1)[1].strip()}
            elif line.startswith("Version:"):
                current_pkg["Version"] = line.split(":", 1)[1].strip()
            elif line.startswith("Status:"):
                current_pkg["Status"] = line.split(":", 1)[1].strip()
            elif line.startswith("Depends:"):
                current_pkg["Depends"] = line.split(":", 1)[1].strip()
            elif line.startswith("Conflicts:"):
                current_pkg["Conflicts"] = line.split(":", 1)[1].strip()
            elif line.startswith("Breaks:"):
                current_pkg["Breaks"] = line.split(":", 1)[1].strip()
            elif line.startswith("Provides:"):
                current_pkg["Provides"] = line.split(":", 1)[1].strip()

        # Don't forget the last package
        if current_pkg.get("Package") and current_pkg.get("Status", "").startswith("install ok"):
            self._add_installed_package(current_pkg)

        logger.info(f"Found {len(self._installed_cache)} installed packages")

    def _add_installed_package(self, pkg_dict: dict) -> None:
        """Add a parsed package to the cache."""
        name = pkg_dict.get("Package", "")
        if not name:
            return

        pkg = InstalledPackage(
            name=name,
            version=pkg_dict.get("Version", ""),
            status=pkg_dict.get("Status", ""),
            provides=self._parse_package_list(pkg_dict.get("Provides", "")),
            depends=self._parse_dependency_list(pkg_dict.get("Depends", "")),
            conflicts=self._parse_package_list(pkg_dict.get("Conflicts", "")),
            breaks=self._parse_package_list(pkg_dict.get("Breaks", "")),
        )
        self._installed_cache[name] = pkg

    def _parse_package_list(self, dep_str: str) -> list[str]:
        """Parse comma-separated package list."""
        if not dep_str:
            return []

        packages = []
        for part in dep_str.split(","):
            part = part.strip()
            # Remove version constraints for simple list
            name = re.sub(r"\s*\(.*?\)", "", part).strip()
            # Handle alternatives (take first)
            if "|" in name:
                name = name.split("|")[0].strip()
            if name:
                packages.append(name)
        return packages

    def _parse_dependency_list(self, dep_str: str) -> list[str]:
        """Parse dependency string including version constraints."""
        return self._parse_package_list(dep_str)

    def _parse_version_constraint(self, constraint_str: str) -> VersionConstraint | None:
        """Parse version constraint from apt format: (>= 1.0.0)."""
        match = re.search(r"\(\s*(>>|>=|=|<=|<<)\s*([^\)]+)\)", constraint_str)
        if match:
            return VersionConstraint(
                raw=constraint_str,
                operator=match.group(1),
                version=match.group(2).strip(),
            )
        return None

    def _get_apt_package_info(self, package_name: str) -> PackageCandidate | None:
        """Get package information from apt-cache."""
        if package_name in self._apt_cache:
            return self._apt_cache[package_name]

        # Get package details
        success, stdout, _ = self._run_command(["apt-cache", "show", package_name])
        if not success:
            return None

        candidate = PackageCandidate(name=package_name)

        for line in stdout.split("\n"):
            if line.startswith("Version:"):
                candidate.version = line.split(":", 1)[1].strip()
            elif line.startswith("Depends:"):
                deps_str = line.split(":", 1)[1].strip()
                for dep in deps_str.split(","):
                    dep = dep.strip()
                    # Handle alternatives
                    if "|" in dep:
                        dep = dep.split("|")[0].strip()
                    name = re.sub(r"\s*\(.*?\)", "", dep).strip()
                    constraint = self._parse_version_constraint(dep)
                    candidate.depends.append((name, constraint))
            elif line.startswith("Conflicts:"):
                candidate.conflicts = self._parse_package_list(line.split(":", 1)[1])
            elif line.startswith("Breaks:"):
                candidate.breaks = self._parse_package_list(line.split(":", 1)[1])
            elif line.startswith("Provides:"):
                candidate.provides = self._parse_package_list(line.split(":", 1)[1])

        self._apt_cache[package_name] = candidate
        return candidate

    def _refresh_pip_packages(self) -> None:
        """Get installed pip packages."""
        self._pip_cache.clear()

        success, stdout, _ = self._run_command(["pip3", "list", "--format=json"])
        if not success:
            # Try pip instead of pip3
            success, stdout, _ = self._run_command(["pip", "list", "--format=json"])

        if success:
            try:
                packages = json.loads(stdout)
                for pkg in packages:
                    name = pkg.get("name", "").lower()
                    version = pkg.get("version", "")
                    self._pip_cache[name] = (version, "pip")
            except json.JSONDecodeError:
                logger.warning("Failed to parse pip list output")

    def is_installed(self, package_name: str) -> bool:
        """Check if a package is installed."""
        return package_name in self._installed_cache

    def get_installed_version(self, package_name: str) -> str | None:
        """Get version of installed package."""
        pkg = self._installed_cache.get(package_name)
        return pkg.version if pkg else None

    def predict_conflicts(self, package_name: str) -> ConflictPrediction:
        """Predict conflicts before installing a package.

        Args:
            package_name: Name of package to install

        Returns:
            ConflictPrediction with all detected conflicts and resolutions
        """
        logger.info(f"Predicting conflicts for {package_name}...")
        prediction = ConflictPrediction(package=package_name)

        # Get candidate package info
        candidate = self._get_apt_package_info(package_name)
        if not candidate:
            prediction.warnings.append(f"Package {package_name} not found in apt cache")
            return prediction

        # Check 1: Known package conflicts
        self._check_known_conflicts(package_name, prediction)

        # Check 2: Declared package conflicts (Conflicts/Breaks fields)
        self._check_declared_conflicts(candidate, prediction)

        # Check 3: Version constraint conflicts
        self._check_version_conflicts(candidate, prediction)

        # Check 4: Transitive dependency conflicts
        self._check_transitive_conflicts(candidate, prediction, visited=set())

        # Check 5: Pip package conflicts (if relevant)
        if self._is_python_related(package_name):
            self._check_pip_conflicts(package_name, prediction)

        # Generate resolution strategies
        if prediction.conflicts:
            prediction.can_install = False
            self._generate_resolutions(prediction)

        return prediction

    def _check_known_conflicts(self, package_name: str, prediction: ConflictPrediction) -> None:
        """Check against known conflicting packages."""
        conflicts_with = self.KNOWN_CONFLICTS.get(package_name, [])

        for conflicting in conflicts_with:
            if self.is_installed(conflicting):
                installed_ver = self.get_installed_version(conflicting)
                prediction.conflicts.append(
                    PredictedConflict(
                        conflict_type=ConflictType.PACKAGE_CONFLICT,
                        package=package_name,
                        conflicting_with=conflicting,
                        description=f"{package_name} conflicts with installed {conflicting}",
                        installed_version=installed_ver,
                        confidence=1.0,
                    )
                )

    def _check_declared_conflicts(
        self, candidate: PackageCandidate, prediction: ConflictPrediction
    ) -> None:
        """Check package's declared Conflicts and Breaks."""
        for conflicting in candidate.conflicts + candidate.breaks:
            if self.is_installed(conflicting):
                installed_ver = self.get_installed_version(conflicting)
                prediction.conflicts.append(
                    PredictedConflict(
                        conflict_type=ConflictType.PACKAGE_CONFLICT,
                        package=candidate.name,
                        conflicting_with=conflicting,
                        description=f"{candidate.name} declares conflict with {conflicting}",
                        installed_version=installed_ver,
                        confidence=1.0,
                    )
                )

        # Also check if installed packages conflict with this one
        for pkg_name, pkg in self._installed_cache.items():
            if candidate.name in pkg.conflicts or candidate.name in pkg.breaks:
                prediction.conflicts.append(
                    PredictedConflict(
                        conflict_type=ConflictType.PACKAGE_CONFLICT,
                        package=candidate.name,
                        conflicting_with=pkg_name,
                        description=f"Installed {pkg_name} conflicts with {candidate.name}",
                        installed_version=pkg.version,
                        confidence=1.0,
                    )
                )

    def _check_version_conflicts(
        self, candidate: PackageCandidate, prediction: ConflictPrediction
    ) -> None:
        """Check for version constraint conflicts."""
        for dep_name, constraint in candidate.depends:
            if not self.is_installed(dep_name):
                continue

            if constraint:
                installed_ver = self.get_installed_version(dep_name)
                if installed_ver and not constraint.satisfies(installed_ver):
                    prediction.conflicts.append(
                        PredictedConflict(
                            conflict_type=ConflictType.VERSION_MISMATCH,
                            package=candidate.name,
                            conflicting_with=dep_name,
                            description=(
                                f"{candidate.name} requires {dep_name} {constraint.raw}, "
                                f"but {installed_ver} is installed"
                            ),
                            installed_version=installed_ver,
                            required_version=constraint.version,
                            confidence=0.95,
                        )
                    )

    def _check_transitive_conflicts(
        self,
        candidate: PackageCandidate,
        prediction: ConflictPrediction,
        visited: set[str],
        depth: int = 0,
    ) -> None:
        """Recursively check transitive dependency conflicts."""
        if depth > 5:  # Limit recursion depth
            return

        if candidate.name in visited:
            return

        visited.add(candidate.name)

        for dep_name, _ in candidate.depends:
            if dep_name in visited:
                continue

            dep_candidate = self._get_apt_package_info(dep_name)
            if not dep_candidate:
                continue

            # Check if this dependency has conflicts
            for conflicting in dep_candidate.conflicts + dep_candidate.breaks:
                if self.is_installed(conflicting):
                    prediction.conflicts.append(
                        PredictedConflict(
                            conflict_type=ConflictType.PACKAGE_CONFLICT,
                            package=dep_name,
                            conflicting_with=conflicting,
                            description=(
                                f"Dependency {dep_name} (required by {candidate.name}) "
                                f"conflicts with installed {conflicting}"
                            ),
                            installed_version=self.get_installed_version(conflicting),
                            confidence=0.9,
                        )
                    )

            # Recurse into dependencies
            self._check_transitive_conflicts(dep_candidate, prediction, visited, depth + 1)

    def _is_python_related(self, package_name: str) -> bool:
        """Check if package is Python-related."""
        python_patterns = ["python", "pip", "numpy", "scipy", "tensorflow", "torch", "pandas"]
        return any(p in package_name.lower() for p in python_patterns)

    def _check_pip_conflicts(self, package_name: str, prediction: ConflictPrediction) -> None:
        """Check for pip package conflicts."""
        if not self._pip_cache:
            self._refresh_pip_packages()

        # Map apt package to pip equivalent
        pip_mapping = {
            "python3-numpy": "numpy",
            "python3-pandas": "pandas",
            "python3-scipy": "scipy",
            "python3-tensorflow": "tensorflow",
            "python3-torch": "torch",
        }

        pip_name = pip_mapping.get(package_name, package_name.replace("python3-", ""))

        if pip_name in self.PIP_CONFLICTS:
            required_constraints = self.PIP_CONFLICTS[pip_name]

            for dep_name, constraint in required_constraints.items():
                if dep_name in self._pip_cache:
                    installed_ver, _ = self._pip_cache[dep_name]
                    # Simple version check
                    if constraint.startswith("<"):
                        max_ver = constraint[1:]
                        if installed_ver >= max_ver:
                            prediction.conflicts.append(
                                PredictedConflict(
                                    conflict_type=ConflictType.VERSION_MISMATCH,
                                    package=pip_name,
                                    conflicting_with=dep_name,
                                    description=(
                                        f"{pip_name} requires {dep_name}{constraint}, "
                                        f"but {installed_ver} is installed via pip"
                                    ),
                                    installed_version=installed_ver,
                                    required_version=constraint,
                                    confidence=0.85,
                                )
                            )

    def _generate_resolutions(self, prediction: ConflictPrediction) -> None:
        """Generate resolution strategies for conflicts."""
        for conflict in prediction.conflicts:
            resolutions = self._get_resolutions_for_conflict(conflict, prediction.package)
            prediction.resolutions.extend(resolutions)

        # Sort by safety (safest first)
        prediction.resolutions.sort(key=lambda r: r.safety_score)

        # Remove duplicates
        seen = set()
        unique_resolutions = []
        for r in prediction.resolutions:
            if r.name not in seen:
                seen.add(r.name)
                unique_resolutions.append(r)
        prediction.resolutions = unique_resolutions

    def _get_resolutions_for_conflict(
        self, conflict: PredictedConflict, target_package: str
    ) -> list[ResolutionStrategy]:
        """Get resolution strategies for a specific conflict."""
        resolutions = []

        if conflict.conflict_type == ConflictType.VERSION_MISMATCH:
            # Strategy 1: Check for compatible version
            resolutions.append(
                ResolutionStrategy(
                    name=f"Install compatible {target_package} version",
                    description=f"Find a version of {target_package} compatible with {conflict.conflicting_with} {conflict.installed_version}",
                    safety=ResolutionSafety.SAFE,
                    commands=[
                        f"apt-cache madison {target_package}",
                        f"sudo apt-get install {target_package}=<compatible_version>",
                    ],
                    side_effects=[],
                )
            )

            # Strategy 2: Upgrade/downgrade conflicting package
            resolutions.append(
                ResolutionStrategy(
                    name=f"Update {conflict.conflicting_with}",
                    description=f"Update {conflict.conflicting_with} to version {conflict.required_version or 'compatible'}",
                    safety=ResolutionSafety.LOW_RISK,
                    commands=[
                        f"sudo apt-get install {conflict.conflicting_with}={conflict.required_version}"
                        if conflict.required_version
                        else f"sudo apt-get install --only-upgrade {conflict.conflicting_with}"
                    ],
                    side_effects=[f"May affect packages depending on {conflict.conflicting_with}"],
                )
            )

            # Strategy 3: Use virtual environment (for Python)
            if "python" in target_package.lower() or "pip" in conflict.conflicting_with.lower():
                resolutions.append(
                    ResolutionStrategy(
                        name="Use Python virtual environment",
                        description="Isolate Python packages in a virtual environment",
                        safety=ResolutionSafety.SAFE,
                        commands=[
                            "python3 -m venv .venv",
                            "source .venv/bin/activate",
                            f"pip install {target_package}",
                        ],
                        side_effects=["Packages only available within the virtual environment"],
                    )
                )

        elif conflict.conflict_type == ConflictType.PACKAGE_CONFLICT:
            # Strategy 1: Remove conflicting package
            resolutions.append(
                ResolutionStrategy(
                    name=f"Remove {conflict.conflicting_with}",
                    description=f"Uninstall {conflict.conflicting_with} to allow {target_package} installation",
                    safety=ResolutionSafety.MEDIUM_RISK,
                    commands=[
                        f"sudo apt-get remove {conflict.conflicting_with}",
                        f"sudo apt-get install {target_package}",
                    ],
                    side_effects=[
                        f"Packages depending on {conflict.conflicting_with} will be removed"
                    ],
                )
            )

            # Strategy 2: Use alternative package (if available)
            alternatives = self._find_alternatives(target_package)
            for alt in alternatives:
                resolutions.append(
                    ResolutionStrategy(
                        name=f"Use alternative: {alt}",
                        description=f"Install {alt} instead of {target_package}",
                        safety=ResolutionSafety.LOW_RISK,
                        commands=[f"sudo apt-get install {alt}"],
                        side_effects=[f"Some features may differ from {target_package}"],
                    )
                )

        return resolutions

    def _find_alternatives(self, package_name: str) -> list[str]:
        """Find alternative packages."""
        alternatives_map = {
            "mysql-server": ["mariadb-server", "postgresql"],
            "mariadb-server": ["mysql-server", "postgresql"],
            "nginx": ["apache2", "caddy"],
            "apache2": ["nginx", "caddy"],
            "postfix": ["exim4", "msmtp"],
            "docker.io": ["docker-ce", "podman"],
            "docker-ce": ["docker.io", "podman"],
        }
        return alternatives_map.get(package_name, [])

    def display_prediction(self, prediction: ConflictPrediction) -> None:
        """Display conflict prediction results."""
        if not prediction.conflicts:
            console.print(
                Panel(
                    f"[green]No conflicts predicted for {prediction.package}[/green]\n"
                    "Installation should proceed safely.",
                    title="Conflict Prediction",
                    style="green",
                )
            )
            return

        # Show conflicts
        console.print(
            Panel(
                f"[bold red]Conflict predicted![/bold red]\n"
                f"{len(prediction.conflicts)} issue(s) found for {prediction.package}",
                title="Conflict Prediction",
                style="red",
            )
        )

        # Conflicts table
        table = Table(title="Detected Conflicts", show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Package")
        table.add_column("Conflicts With")
        table.add_column("Details")
        table.add_column("Confidence")

        for conflict in prediction.conflicts:
            conf_color = "green" if conflict.confidence > 0.9 else "yellow"
            table.add_row(
                conflict.conflict_type.value,
                conflict.package,
                conflict.conflicting_with,
                conflict.description[:50] + "..." if len(conflict.description) > 50 else conflict.description,
                f"[{conf_color}]{conflict.confidence:.0%}[/{conf_color}]",
            )

        console.print(table)

        # Show resolutions
        if prediction.resolutions:
            console.print("\n[bold cyan]Suggested Resolutions:[/bold cyan]\n")

            for i, resolution in enumerate(prediction.resolutions, 1):
                safety_colors = {
                    ResolutionSafety.SAFE: "green",
                    ResolutionSafety.LOW_RISK: "yellow",
                    ResolutionSafety.MEDIUM_RISK: "orange3",
                    ResolutionSafety.HIGH_RISK: "red",
                }
                color = safety_colors.get(resolution.safety, "white")
                rec = " [green](Recommended)[/green]" if i == 1 else ""

                console.print(f"[bold]{i}. {resolution.name}[/bold]{rec}")
                console.print(f"   [{color}]{resolution.safety.name}[/{color}]")
                console.print(f"   {resolution.description}")

                if resolution.commands:
                    console.print("   Commands:")
                    for cmd in resolution.commands:
                        console.print(f"      $ {cmd}")

                if resolution.side_effects:
                    console.print("   [yellow]Side effects:[/yellow]")
                    for effect in resolution.side_effects:
                        console.print(f"      - {effect}")
                console.print()

    def predict_and_display(self, package_name: str) -> ConflictPrediction:
        """Predict conflicts and display results.

        Args:
            package_name: Package to analyze

        Returns:
            ConflictPrediction result
        """
        prediction = self.predict_conflicts(package_name)
        self.display_prediction(prediction)
        return prediction


def run_conflict_predictor(
    package_name: str,
    verbose: bool = False,
) -> int:
    """Run the conflict predictor CLI.

    Args:
        package_name: Package to analyze
        verbose: Enable verbose output

    Returns:
        Exit code (0 if no conflicts, 1 if conflicts found)
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    predictor = ConflictPredictor()
    prediction = predictor.predict_and_display(package_name)

    return 0 if prediction.can_install else 1


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Predict dependency conflicts before installation")
    parser.add_argument("package", help="Package name to analyze")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.json:
        predictor = ConflictPredictor()
        prediction = predictor.predict_conflicts(args.package)

        output = {
            "package": prediction.package,
            "can_install": prediction.can_install,
            "conflicts": [
                {
                    "type": c.conflict_type.value,
                    "package": c.package,
                    "conflicting_with": c.conflicting_with,
                    "description": c.description,
                    "confidence": c.confidence,
                }
                for c in prediction.conflicts
            ],
            "resolutions": [
                {
                    "name": r.name,
                    "description": r.description,
                    "safety": r.safety.name,
                    "commands": r.commands,
                }
                for r in prediction.resolutions
            ],
            "warnings": prediction.warnings,
        }
        print(json.dumps(output, indent=2))
    else:
        exit(run_conflict_predictor(args.package, args.verbose))
