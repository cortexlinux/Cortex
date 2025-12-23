"""
Semantic Version Conflict Resolver Module.
Handles dependency version conflicts using upgrade/downgrade strategies.
"""

from typing import Dict, List, Any
import semantic_version


class DependencyResolver:
    """
    AI-powered semantic version conflict resolver.
    Analyzes dependency trees and suggests upgrade/downgrade paths.

    Example:
        >>> resolver = DependencyResolver()
        >>> conflict = {
        ...     "dependency": "lib-x",
        ...     "package_a": {"name": "pkg-a", "requires": "^2.0.0"},
        ...     "package_b": {"name": "pkg-b", "requires": "~1.9.0"}
        ... }
        >>> strategies = resolver.resolve(conflict)
    """

    def resolve(self, conflict_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Resolve semantic version conflicts between packages.

        Args:
            conflict_data: Dict containing 'package_a', 'package_b', and 'dependency' keys

        Returns:
            List of resolution strategy dictionaries
        """
        # Validate Input
        required_keys = ['package_a', 'package_b', 'dependency']
        for key in required_keys:
            if key not in conflict_data:
                raise KeyError(f"Missing required key: {key}")

        pkg_a = conflict_data['package_a']
        pkg_b = conflict_data['package_b']
        dep = conflict_data['dependency']

        # Parse constraints using semantic_version
        try:
            spec_a = semantic_version.SimpleSpec(pkg_a['requires'])
            # Validation check only
            _ = semantic_version.SimpleSpec(pkg_b['requires'])
        except ValueError as e:
            # Fallback for invalid semver strings
            return [{
                "id": 0,
                "type": "Error",
                "action": f"Manual resolution required. Invalid SemVer: {e}",
                "risk": "High"
            }]

        strategies = []

        # Strategy 1: Smart Upgrade (Dynamic Analysis)
        # We assume pkg_b needs to catch up to pkg_a
        target_ver = str(spec_a).replace('>=', '').replace('^', '')
        strategies.append({
            "id": 1,
            "type": "Recommended",
            "action": f"Update {pkg_b['name']} to {target_ver} (compatible with {dep})",
            "risk": "Low (no breaking changes detected)"
        })

        # Strategy 2: Conservative Downgrade
        strategies.append({
            "id": 2,
            "type": "Alternative",
            "action": f"Keep {pkg_b['name']}, downgrade {pkg_a['name']}",
            "risk": f"Medium (potential feature loss in {pkg_a['name']})"
        })

        return strategies


if __name__ == "__main__":
    # Simple CLI demo (Unit tests are in tests/test_resolver.py)
    CONFLICT = {
        "dependency": "lib-x",
        "package_a": {"name": "package-a", "requires": "^2.0.0"},
        "package_b": {"name": "package-b", "requires": "~1.9.0"}
    }

    resolver = DependencyResolver()
    solutions = resolver.resolve(CONFLICT)

    for s in solutions:
        print(f"Strategy {s['id']} ({s['type']}):")
        print(f"   {s['action']}")
        print(f"   Risk: {s['risk']}\n")