"""API utilities for Cortex CLI.

Provides API key and provider detection helpers.
"""

import os
from typing import Optional


def _get_api_key() -> Optional[str]:
    """Get API key from environment or user input.

    Returns:
        API key string or None if not available.
    """
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")


def _get_provider() -> str:
    """Determine which LLM provider to use.

    Returns:
        Provider name string.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    elif os.environ.get("OPENAI_API_KEY"):
        return "openai"
    elif os.environ.get("OLLAMA_HOST"):
        return "ollama"
    elif os.environ.get("KIMI_API_KEY"):
        return "kimi"
    else:
        return "auto"
