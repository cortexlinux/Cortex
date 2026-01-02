"""
AI-Powered Dependency Conflict Predictor

This module predicts and resolves package dependency conflicts BEFORE installation
using LLM analysis instead of hardcoded rules.

Author: Cortex Linux Team
License: Apache 2.0
"""

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from cortex.installation_history import InstallationHistory
from cortex.llm_router import LLMRouter, TaskType

# Use DEPENDENCY_RESOLUTION since DEPENDENCY_ANALYSIS doesn't exist
CONFLICT_TASK_TYPE = TaskType.DEPENDENCY_RESOLUTION

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of dependency conflicts"""

    VERSION = "version"
    PORT = "port"
    LIBRARY = "library"
    FILE = "file"
    MUTUAL_EXCLUSION = "mutual_exclusion"
    CIRCULAR = "circular"


class StrategyType(Enum):
    """Resolution strategy types"""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    ALTERNATIVE = "alternative"
    VENV = "venv"
    REMOVE_CONFLICT = "remove_conflict"
    PORT_CHANGE = "port_change"
    DO_NOTHING = "do_nothing"


@dataclass
class ConflictPrediction:
    """Represents a predicted dependency conflict"""

    package1: str
    package2: str
    conflict_type: ConflictType
    confidence: float
    explanation: str
    affected_packages: list[str] = field(default_factory=list)
    severity: str = "MEDIUM"
    installed_by: str | None = None
    current_version: str | None = None
    required_constraint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "conflict_type": self.conflict_type.value}


@dataclass
class ResolutionStrategy:
    """Suggested resolution for a conflict"""

    strategy_type: StrategyType
    description: str
    safety_score: float
    commands: list[str]
    risks: list[str] = field(default_factory=list)
    benefits: list[str] = field(default_factory=list)
    estimated_time_minutes: float = 2.0
    affects_packages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "strategy_type": self.strategy_type.value}


class ConflictPredictor:
    """
    AI-powered dependency conflict prediction using LLM analysis.

    Instead of hardcoded rules, this sends the system state to an LLM
    which analyzes potential conflicts based on its knowledge of package
    ecosystems.
    """

    def __init__(
        self,
        llm_router: LLMRouter | None = None,
        history: InstallationHistory | None = None,
    ):
        self.llm_router = llm_router
        self.history = history or InstallationHistory()

    def predict_conflicts(
        self, package_name: str, version: str | None = None
    ) -> list[ConflictPrediction]:
        """
        Predict conflicts for a package installation using LLM analysis.
        """
        logger.info(f"Predicting conflicts for {package_name} {version or 'latest'}")

        if not self.llm_router:
            logger.warning("No LLM router available, skipping conflict prediction")
            return []

        # Gather system state
        pip_packages = get_pip_packages()
        apt_packages = get_apt_packages_summary()

        # Build the prompt
        prompt = self._build_analysis_prompt(package_name, version, pip_packages, apt_packages)

        try:
            # Call LLM for analysis
            messages = [
                {"role": "system", "content": CONFLICT_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            response = self.llm_router.complete(
                messages=messages,
                task_type=CONFLICT_TASK_TYPE,
                temperature=0.2,
                max_tokens=2048,
            )

            if not response or not response.content:
                logger.warning("Empty response from LLM")
                return []

            # Parse the JSON response
            conflicts = self._parse_llm_response(response.content, package_name)
            logger.info(f"Found {len(conflicts)} potential conflicts")
            return conflicts

        except Exception as e:
            logger.warning(f"AI conflict detection failed: {e}")
            return []

    def _build_analysis_prompt(
        self,
        package_name: str,
        version: str | None,
        pip_packages: dict[str, str],
        apt_packages: list[str],
    ) -> str:
        """Build the prompt for LLM conflict analysis."""

        # Format pip packages (limit to relevant ones for context size)
        pip_list = "\n".join(
            [f"  - {name}=={ver}" for name, ver in list(pip_packages.items())[:50]]
        )

        # Format apt packages summary
        apt_list = "\n".join([f"  - {pkg}" for pkg in apt_packages[:30]])

        version_str = f"=={version}" if version else " (latest)"

        return f"""Analyze potential dependency conflicts for installing: {package_name}{version_str}

CURRENTLY INSTALLED PIP PACKAGES:
{pip_list or "  (none)"}

RELEVANT APT PACKAGES:
{apt_list or "  (none)"}

Based on your knowledge of Python/Linux package ecosystems, analyze:
1. Will installing {package_name}{version_str} conflict with any installed packages?
2. Are there version incompatibilities?
3. What packages might be affected?

Respond with JSON only."""

    def _parse_llm_response(self, response: str, package_name: str) -> list[ConflictPrediction]:
        """Parse LLM response into ConflictPrediction objects."""
        conflicts = []

        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                logger.warning("No JSON found in LLM response")
                return []

            data = json.loads(json_match.group())

            # Handle different response formats
            conflict_list = data.get("conflicts", [])
            if not conflict_list and data.get("has_conflicts"):
                # Alternative format
                conflict_list = [data]

            for c in conflict_list:
                try:
                    conflict_type_str = c.get("type", "VERSION").upper()
                    if conflict_type_str not in [ct.name for ct in ConflictType]:
                        conflict_type_str = "VERSION"

                    conflicts.append(
                        ConflictPrediction(
                            package1=package_name,
                            package2=c.get("conflicting_package", c.get("package2", "unknown")),
                            conflict_type=ConflictType[conflict_type_str],
                            confidence=float(c.get("confidence", 0.8)),
                            explanation=c.get(
                                "explanation", c.get("reason", "Potential conflict detected")
                            ),
                            affected_packages=c.get("affected_packages", []),
                            severity=c.get("severity", "HIGH"),
                            installed_by=c.get("installed_by"),
                            current_version=c.get("current_version"),
                            required_constraint=c.get("required_constraint"),
                        )
                    )
                except (KeyError, ValueError) as e:
                    logger.debug(f"Failed to parse conflict entry: {e}")
                    continue

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")

        return conflicts

    def generate_resolutions(self, conflicts: list[ConflictPrediction]) -> list[ResolutionStrategy]:
        """Generate resolution strategies using LLM."""
        if not conflicts:
            return []

        if not self.llm_router:
            # Fallback to basic strategies
            return self._generate_basic_strategies(conflicts)

        # Build prompt for resolution suggestions
        conflict_summary = "\n".join([f"- {c.explanation}" for c in conflicts])

        prompt = f"""Given these dependency conflicts:
{conflict_summary}

Suggest resolution strategies. For each strategy provide:
1. Description of what to do
2. Safety score (0.0-1.0, higher = safer)
3. Commands to execute
4. Benefits and risks

Respond with JSON only."""

        try:
            messages = [
                {"role": "system", "content": RESOLUTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            response = self.llm_router.complete(
                messages=messages,
                task_type=CONFLICT_TASK_TYPE,
                temperature=0.3,
                max_tokens=2048,
            )

            if response and response.content:
                strategies = self._parse_resolution_response(response.content, conflicts)
                if strategies:
                    return strategies

        except Exception as e:
            logger.warning(f"LLM resolution generation failed: {e}")

        # Fallback to basic strategies
        return self._generate_basic_strategies(conflicts)

    def _parse_resolution_response(
        self, response: str, conflicts: list[ConflictPrediction]
    ) -> list[ResolutionStrategy]:
        """Parse LLM response into ResolutionStrategy objects."""
        strategies = []

        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return []

            data = json.loads(json_match.group())
            strategy_list = data.get("strategies", data.get("resolutions", []))

            for s in strategy_list:
                try:
                    strategy_type_str = s.get("type", "VENV").upper()
                    if strategy_type_str not in [st.name for st in StrategyType]:
                        strategy_type_str = "VENV"

                    strategies.append(
                        ResolutionStrategy(
                            strategy_type=StrategyType[strategy_type_str],
                            description=s.get("description", ""),
                            safety_score=float(s.get("safety_score", 0.5)),
                            commands=s.get("commands", []),
                            benefits=s.get("benefits", []),
                            risks=s.get("risks", []),
                            affects_packages=s.get("affects_packages", []),
                        )
                    )
                except (KeyError, ValueError):
                    continue

        except json.JSONDecodeError:
            pass

        # Sort by safety score
        strategies.sort(key=lambda s: s.safety_score, reverse=True)
        return strategies

    def _generate_basic_strategies(
        self, conflicts: list[ConflictPrediction]
    ) -> list[ResolutionStrategy]:
        """Generate basic resolution strategies without LLM."""
        strategies = []

        for conflict in conflicts:
            pkg = conflict.package1
            conflicting = conflict.package2

            # Strategy 1: Virtual environment (safest)
            strategies.append(
                ResolutionStrategy(
                    strategy_type=StrategyType.VENV,
                    description=f"Install {pkg} in virtual environment (isolate)",
                    safety_score=0.85,
                    commands=[
                        f"python3 -m venv {pkg}_env",
                        f"source {pkg}_env/bin/activate",
                        f"pip install {pkg}",
                    ],
                    benefits=["Complete isolation", "No system impact", "Reversible"],
                    risks=["Must activate venv to use package"],
                    affects_packages=[pkg],
                )
            )

            # Strategy 2: Try newer version
            strategies.append(
                ResolutionStrategy(
                    strategy_type=StrategyType.UPGRADE,
                    description=f"Install newer version of {pkg} (may be compatible)",
                    safety_score=0.75,
                    commands=[f"pip install --upgrade {pkg}"],
                    benefits=["May resolve compatibility", "Gets latest features"],
                    risks=["May have different features than requested version"],
                    affects_packages=[pkg],
                )
            )

            # Strategy 3: Downgrade conflicting package
            if conflict.required_constraint:
                strategies.append(
                    ResolutionStrategy(
                        strategy_type=StrategyType.DOWNGRADE,
                        description=f"Downgrade {conflicting} to compatible version",
                        safety_score=0.50,
                        commands=[f"pip install '{conflicting}{conflict.required_constraint}'"],
                        benefits=[f"Satisfies {pkg} requirements"],
                        risks=[f"May affect packages depending on {conflicting}"],
                        affects_packages=[conflicting],
                    )
                )

            # Strategy 4: Remove conflicting (risky)
            strategies.append(
                ResolutionStrategy(
                    strategy_type=StrategyType.REMOVE_CONFLICT,
                    description=f"Remove {conflicting} (not recommended)",
                    safety_score=0.10,
                    commands=[
                        f"pip uninstall -y {conflicting}",
                        f"pip install {pkg}",
                    ],
                    benefits=["Resolves conflict directly"],
                    risks=["May break dependent packages", "Data loss possible"],
                    affects_packages=[conflicting, pkg],
                )
            )

        # Sort by safety and deduplicate
        strategies.sort(key=lambda s: s.safety_score, reverse=True)
        seen = set()
        unique = []
        for s in strategies:
            key = (s.strategy_type, s.description)
            if key not in seen:
                seen.add(key)
                unique.append(s)

        return unique[:4]  # Return top 4 strategies

    def record_resolution(
        self,
        conflict: ConflictPrediction,
        chosen_strategy: ResolutionStrategy,
        success: bool,
        user_feedback: str | None = None,
    ) -> None:
        """Record conflict resolution for learning."""
        logger.info(
            f"Recording resolution: {chosen_strategy.strategy_type.value} - "
            f"{'success' if success else 'failed'}"
        )


# ============================================================================
# System Prompts for LLM
# ============================================================================

CONFLICT_ANALYSIS_SYSTEM_PROMPT = """You are an expert Linux/Python dependency analyzer.
Your job is to predict package conflicts BEFORE installation.

Analyze the user's installed packages and the package they want to install.
Based on your knowledge of package ecosystems (PyPI, apt), identify potential conflicts.

Common conflict patterns to check:
- numpy version requirements (tensorflow, pandas, scipy often conflict)
- CUDA/GPU library versions
- Flask/Django with specific Werkzeug versions
- Packages that install conflicting system libraries

Respond with JSON in this exact format:
{
  "has_conflicts": true/false,
  "conflicts": [
    {
      "conflicting_package": "numpy",
      "current_version": "2.1.0",
      "required_constraint": "< 2.0",
      "type": "VERSION",
      "confidence": 0.95,
      "severity": "HIGH",
      "explanation": "tensorflow 2.15 requires numpy < 2.0, but numpy 2.1.0 is installed",
      "installed_by": "pandas",
      "affected_packages": ["pandas", "scipy"]
    }
  ]
}

If no conflicts, respond with:
{"has_conflicts": false, "conflicts": []}

IMPORTANT: Only report REAL conflicts you're confident about. Don't make up issues."""

RESOLUTION_SYSTEM_PROMPT = """You are an expert at resolving Python/Linux dependency conflicts.
Given a list of conflicts, suggest practical resolution strategies.

Respond with JSON in this format:
{
  "strategies": [
    {
      "type": "VENV",
      "description": "Install in virtual environment (safest)",
      "safety_score": 0.95,
      "commands": ["python3 -m venv myenv", "source myenv/bin/activate", "pip install package"],
      "benefits": ["Complete isolation", "No system impact"],
      "risks": ["Must activate venv to use"],
      "affects_packages": ["package"]
    }
  ]
}

Strategy types: UPGRADE, DOWNGRADE, VENV, REMOVE_CONFLICT, ALTERNATIVE
Safety scores: 0.0-1.0 (higher = safer)

Rank strategies by safety. Always include VENV as a safe option."""


# ============================================================================
# Display Functions
# ============================================================================


def format_conflict_summary(
    conflicts: list[ConflictPrediction], strategies: list[ResolutionStrategy]
) -> str:
    """Format conflicts and strategies for CLI display."""
    if not conflicts:
        return ""

    output = "\n"

    # Show conflicts
    for conflict in conflicts:
        output += f"⚠️  Conflict predicted: {conflict.explanation}\n"

        if conflict.current_version:
            installed_by = (
                f" (installed by {conflict.installed_by})" if conflict.installed_by else ""
            )
            output += f"    Your system has {conflict.package2} {conflict.current_version}{installed_by}\n"

        output += (
            f"    Confidence: {int(conflict.confidence * 100)}% | Severity: {conflict.severity}\n"
        )

        if conflict.affected_packages:
            other = [
                p
                for p in conflict.affected_packages
                if p not in (conflict.package1, conflict.package2)
            ]
            if other:
                output += f"    Also affects: {', '.join(other[:5])}\n"

        output += "\n"

    # Show strategies
    if strategies:
        output += "\n    Suggestions (ranked by safety):\n"

        for i, strategy in enumerate(strategies[:4], 1):
            recommended = " [RECOMMENDED]" if i == 1 else ""
            output += f"    {i}. {strategy.description}{recommended}\n"

            # Safety bar
            pct = int(strategy.safety_score * 100)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            output += f"       Safety: [{bar}] {pct}%\n"

            if strategy.benefits:
                output += f"       ✓ {strategy.benefits[0]}\n"
            if strategy.risks:
                output += f"       ⚠ {strategy.risks[0]}\n"

            output += "\n"

    return output


def prompt_resolution_choice(
    strategies: list[ResolutionStrategy], auto_select: bool = False
) -> tuple[ResolutionStrategy | None, int]:
    """Prompt user to choose a resolution strategy."""
    if not strategies:
        return None, -1

    if auto_select:
        return strategies[0], 0

    max_choices = min(4, len(strategies))

    try:
        prompt = f"\n    Proceed with option 1? [Y/n/2-{max_choices}]: "
        choice = input(prompt).strip().lower()

        if choice in ("", "y", "yes"):
            return strategies[0], 0

        if choice in ("n", "no", "q"):
            return None, -1

        try:
            idx = int(choice) - 1
            if 0 <= idx < max_choices:
                return strategies[idx], idx
        except ValueError:
            pass

        print("    Invalid choice. Using option 1.")
        return strategies[0], 0

    except (EOFError, KeyboardInterrupt):
        print("\n    Cancelled.")
        return None, -1


# ============================================================================
# Helper Functions
# ============================================================================


def get_pip_packages() -> dict[str, str]:
    """Get installed pip packages."""
    try:
        result = subprocess.run(
            ["pip3", "list", "--format=json"], capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return {pkg["name"]: pkg["version"] for pkg in packages}
    except Exception as e:
        logger.debug(f"Failed to get pip packages: {e}")
    return {}


def get_apt_packages_summary() -> list[str]:
    """Get summary of relevant apt packages."""
    relevant_prefixes = [
        "python",
        "lib",
        "cuda",
        "nvidia",
        "tensorflow",
        "torch",
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
    ]

    try:
        result = subprocess.run(
            ["dpkg", "--get-selections"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            packages = []
            for line in result.stdout.split("\n"):
                if "\tinstall" in line:
                    pkg = line.split()[0]
                    if any(pkg.startswith(p) for p in relevant_prefixes):
                        packages.append(pkg)
            return packages[:30]
    except Exception as e:
        logger.debug(f"Failed to get apt packages: {e}")
    return []


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Predict dependency conflicts")
    parser.add_argument("package", help="Package name to analyze")
    parser.add_argument("--version", help="Specific version")
    parser.add_argument("--resolve", action="store_true", help="Show resolutions")

    args = parser.parse_args()

    predictor = ConflictPredictor()

    print(f"\n🔍 Analyzing {args.package}...")
    conflicts = predictor.predict_conflicts(args.package, args.version)

    if not conflicts:
        print("✅ No conflicts predicted!")
    else:
        strategies = predictor.generate_resolutions(conflicts) if args.resolve else []
        print(format_conflict_summary(conflicts, strategies))
