"""
Semantic Version Conflict Resolver Module.
Handles dependency version conflicts using AI-driven intelligent analysis.
"""

import json
import logging
from typing import List, Dict

import semantic_version as sv
from cortex.llm.interpreter import CommandInterpreter

logger = logging.getLogger(__name__)


class DependencyResolver:
    """
    AI-powered semantic version conflict resolver.
    Analyzes dependency version conflicts and suggests intelligent
    upgrade/downgrade paths.
    """

    def __init__(self):
        self.interpreter = CommandInterpreter(
            api_key="ollama",
            provider="ollama",
        )

    async def resolve(self, conflict_data: dict) -> List[Dict]:
        """
        Resolve semantic version conflicts using deterministic analysis first,
        followed by AI-powered reasoning as a fallback.
        """
        required_keys = ["package_a", "package_b", "dependency"]
        for key in required_keys:
            if key not in conflict_data:
                raise KeyError(f"Missing required key: {key}")

        strategies = self._deterministic_resolution(conflict_data)
        if strategies:
            return strategies

        prompt = self._build_prompt(conflict_data)

        try:
            response_list = self.interpreter.parse(prompt)
            response_text = " ".join(response_list)
            return self._parse_ai_response(response_text, conflict_data)
        except Exception as e:
            logger.error(f"AI Resolution failed: {e}")
            return [
                {
                    "id": 0,
                    "type": "Error",
                    "action": f"AI analysis unavailable. Manual resolution required: {e}",
                    "risk": "High",
                }
            ]

    def _deterministic_resolution(self, data: dict) -> List[Dict]:
        """
        Perform semantic-version constraint analysis without relying on AI.
        """
        try:
            dependency = data["dependency"]
            a_req = sv.NpmSpec(data["package_a"]["requires"])
            b_req = sv.NpmSpec(data["package_b"]["requires"])

            intersection = a_req & b_req
            if intersection:
                return [
                    {
                        "id": 1,
                        "type": "Recommended",
                        "action": f"Use {dependency} {intersection}",
                        "risk": "Low",
                        "explanation": "Version constraints are compatible",
                    }
                ]

            a_major = a_req.specs[0].version.major
            b_major = b_req.specs[0].version.major

            strategies = [
                {
                    "id": 1,
                    "type": "Recommended",
                    "action": (
                        f"Upgrade {data['package_b']['name']} "
                        f"to support {dependency} ^{a_major}.0.0"
                    ),
                    "risk": "Medium",
                    "explanation": "Major version upgrade required",
                },
                {
                    "id": 2,
                    "type": "Alternative",
                    "action": (
                        f"Downgrade {data['package_a']['name']} "
                        f"to support {dependency} ~{b_major}.x"
                    ),
                    "risk": "High",
                    "explanation": "Downgrade may remove features or fixes",
                },
            ]

            return strategies
        except Exception as e:
            logger.debug(f"Deterministic resolution skipped: {e}")
            return []

    def _build_prompt(self, data: dict) -> str:
        """Constructs a detailed AI prompt."""
        return f"""
        Act as an expert DevOps Engineer. Analyze this dependency conflict:
        Dependency: {data['dependency']}

        Conflict Context:
        1. {data['package_a']['name']} requires {data['package_a']['requires']}
        2. {data['package_b']['name']} requires {data['package_b']['requires']}

        Task:
        - Detect breaking changes beyond major version numbers.
        - Provide a recommended upgrade strategy.
        - Provide an alternative downgrade strategy.

        Return ONLY valid JSON containing resolution strategies.
        """

    def _parse_ai_response(self, response: str, data: dict) -> List[Dict]:
        """Parse AI response into structured strategies."""
        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start != -1 and end != 0:
                json_str = response[start:end].replace("'", '"')
                return json.loads(json_str)
            raise ValueError("No JSON array found")
        except Exception:
            return [
                {
                    "id": 1,
                    "type": "Recommended",
                    "action": (
                        f"Update {data['package_b']['name']} "
                        f"to match {data['package_a']['requires']}"
                    ),
                    "risk": "Low (AI fallback applied)",
                },
                {
                    "id": 2,
                    "type": "Alternative",
                    "action": (
                        f"Keep {data['package_b']['name']}, "
                        f"downgrade {data['package_a']['name']}"
                    ),
                    "risk": "Medium (Potential feature loss)",
                },
            ]
