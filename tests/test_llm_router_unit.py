"""
Unit tests for cortex/llm_router.py - LLM Router logic.

These tests use mocks and don't require Ollama or any LLM service running.
For integration tests with real Ollama, see test_ollama_integration.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from cortex.llm_router import (
    LLMProvider,
    LLMResponse,
    LLMRouter,
    RoutingDecision,
    TaskType,
)


class TestLLMProviderEnum:
    """Test the LLMProvider enum."""

    def test_all_providers_exist(self):
        assert LLMProvider.OLLAMA.value == "ollama"
        assert LLMProvider.CLAUDE.value == "claude"
        assert LLMProvider.KIMI_K2.value == "kimi_k2"


class TestTaskTypeEnum:
    """Test the TaskType enum."""

    def test_common_task_types(self):
        assert TaskType.USER_CHAT.value == "user_chat"
        assert TaskType.SYSTEM_OPERATION.value == "system_operation"
        assert TaskType.ERROR_DEBUGGING.value == "error_debugging"
        assert TaskType.REQUIREMENT_PARSING.value == "requirement_parsing"
        assert TaskType.CODE_GENERATION.value == "code_generation"


class TestLLMResponse:
    """Test the LLMResponse dataclass."""

    def test_basic_creation(self):
        response = LLMResponse(
            content="Hello world",
            provider=LLMProvider.OLLAMA,
            model="tinyllama",
            tokens_used=10,
            cost_usd=0.0,
            latency_seconds=1.5,
        )
        assert response.content == "Hello world"
        assert response.provider == LLMProvider.OLLAMA
        assert response.tokens_used == 10
        assert response.cost_usd == 0.0

    def test_ollama_is_free(self):
        """Ollama should always have $0 cost."""
        response = LLMResponse(
            content="Test",
            provider=LLMProvider.OLLAMA,
            model="llama3",
            tokens_used=1000,
            cost_usd=0.0,
            latency_seconds=2.0,
        )
        assert response.cost_usd == 0.0

    def test_with_raw_response(self):
        response = LLMResponse(
            content="Test",
            provider=LLMProvider.CLAUDE,
            model="claude-3",
            tokens_used=100,
            cost_usd=0.01,
            latency_seconds=1.0,
            raw_response={"id": "msg_123"},
        )
        assert response.raw_response is not None
        assert response.raw_response["id"] == "msg_123"


class TestRoutingDecision:
    """Test the RoutingDecision dataclass."""

    def test_basic_creation(self):
        decision = RoutingDecision(
            provider=LLMProvider.OLLAMA,
            task_type=TaskType.USER_CHAT,
            reasoning="Local model preferred for privacy",
            confidence=0.9,
        )
        assert decision.provider == LLMProvider.OLLAMA
        assert decision.task_type == TaskType.USER_CHAT
        assert "Local" in decision.reasoning
        assert decision.confidence == 0.9

    def test_confidence_bounds(self):
        # Confidence should be 0.0 to 1.0
        decision = RoutingDecision(
            provider=LLMProvider.CLAUDE,
            task_type=TaskType.REQUIREMENT_PARSING,
            reasoning="Best for natural language",
            confidence=1.0,
        )
        assert 0.0 <= decision.confidence <= 1.0


class TestLLMRouterInit:
    """Test LLMRouter initialization."""

    def test_init_with_ollama(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )
        assert router.ollama_model == "tinyllama"
        assert router.ollama_base_url == "http://localhost:11434"

    def test_init_with_claude_api_key(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            router = LLMRouter(claude_api_key="test-key")
            assert router.claude_api_key == "test-key"


class TestLLMRouterStats:
    """Test LLMRouter stats tracking."""

    def test_initial_stats_empty(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )

        stats = router.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_cost_usd"] == 0.0

    def test_stats_structure(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )

        stats = router.get_stats()
        assert "total_requests" in stats
        assert "total_cost_usd" in stats
        assert "providers" in stats
        assert "ollama" in stats["providers"]


class TestLLMRouterComplete:
    """Test LLMRouter complete method with mocks."""

    def test_complete_with_mocked_ollama(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )

        # Mock the internal _complete_ollama method
        mock_response = LLMResponse(
            content="Mocked response",
            provider=LLMProvider.OLLAMA,
            model="tinyllama",
            tokens_used=15,
            cost_usd=0.0,
            latency_seconds=0.5,
        )

        with patch.object(router, "_complete_ollama", return_value=mock_response):
            response = router.complete(
                messages=[{"role": "user", "content": "Hello"}],
                force_provider=LLMProvider.OLLAMA,
            )

        assert response.content == "Mocked response"
        assert response.provider == LLMProvider.OLLAMA
        assert response.cost_usd == 0.0

    def test_complete_updates_stats(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )

        mock_response = LLMResponse(
            content="Test",
            provider=LLMProvider.OLLAMA,
            model="tinyllama",
            tokens_used=100,
            cost_usd=0.0,
            latency_seconds=1.0,
        )

        with patch.object(router, "_complete_ollama", return_value=mock_response):
            router.complete(
                messages=[{"role": "user", "content": "Test"}],
                force_provider=LLMProvider.OLLAMA,
            )

        stats = router.get_stats()
        assert stats["total_requests"] >= 1
        assert stats["providers"]["ollama"]["requests"] >= 1


class TestLLMRouterCostTracking:
    """Test LLMRouter cost tracking."""

    def test_ollama_always_free(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )

        mock_response = LLMResponse(
            content="Test",
            provider=LLMProvider.OLLAMA,
            model="tinyllama",
            tokens_used=10000,  # Many tokens
            cost_usd=0.0,  # Still free
            latency_seconds=5.0,
        )

        with patch.object(router, "_complete_ollama", return_value=mock_response):
            response = router.complete(
                messages=[{"role": "user", "content": "Long prompt"}],
                force_provider=LLMProvider.OLLAMA,
            )

        assert response.cost_usd == 0.0
        stats = router.get_stats()
        assert stats["providers"]["ollama"]["cost_usd"] == 0.0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_messages(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )

        # Should handle empty messages gracefully
        mock_response = LLMResponse(
            content="",
            provider=LLMProvider.OLLAMA,
            model="tinyllama",
            tokens_used=0,
            cost_usd=0.0,
            latency_seconds=0.1,
        )

        with patch.object(router, "_complete_ollama", return_value=mock_response):
            response = router.complete(
                messages=[],
                force_provider=LLMProvider.OLLAMA,
            )

        assert response is not None

    def test_long_conversation(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )

        # Create a long conversation
        messages = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
            for i in range(100)
        ]

        mock_response = LLMResponse(
            content="Response to long conversation",
            provider=LLMProvider.OLLAMA,
            model="tinyllama",
            tokens_used=500,
            cost_usd=0.0,
            latency_seconds=2.0,
        )

        with patch.object(router, "_complete_ollama", return_value=mock_response):
            response = router.complete(
                messages=messages,
                force_provider=LLMProvider.OLLAMA,
            )

        assert response is not None
        assert response.tokens_used == 500

    def test_response_latency_tracked(self):
        router = LLMRouter(
            ollama_base_url="http://localhost:11434",
            ollama_model="tinyllama",
        )

        mock_response = LLMResponse(
            content="Test",
            provider=LLMProvider.OLLAMA,
            model="tinyllama",
            tokens_used=10,
            cost_usd=0.0,
            latency_seconds=2.5,
        )

        with patch.object(router, "_complete_ollama", return_value=mock_response):
            response = router.complete(
                messages=[{"role": "user", "content": "Test"}],
                force_provider=LLMProvider.OLLAMA,
            )

        # Latency is measured by complete(), not from mock response
        # Just verify it exists and is a positive number
        assert response.latency_seconds >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
