"""Tests for the smart retry logic module.

Tests Issue #43: Smart Retry Logic with Exponential Backoff
"""

import pytest
import time
from unittest.mock import Mock, patch, call

from cortex.retry import (
    RetryConfig,
    RetryStrategy,
    RetryResult,
    RetryManager,
    retry,
    NETWORK_RETRY_CONFIG,
    API_RETRY_CONFIG,
    APT_RETRY_CONFIG,
    retry_apt_operation,
    retry_api_call,
    retry_network_operation,
)


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.jitter_range == 0.25
        assert config.strategy == RetryStrategy.EXPONENTIAL

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            strategy=RetryStrategy.LINEAR
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.strategy == RetryStrategy.LINEAR

    def test_invalid_max_attempts(self):
        """Test that invalid max_attempts raises error."""
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=0)

    def test_invalid_base_delay(self):
        """Test that negative base_delay raises error."""
        with pytest.raises(ValueError, match="base_delay must be non-negative"):
            RetryConfig(base_delay=-1)

    def test_invalid_max_delay(self):
        """Test that max_delay < base_delay raises error."""
        with pytest.raises(ValueError, match="max_delay must be >= base_delay"):
            RetryConfig(base_delay=10, max_delay=5)

    def test_invalid_jitter_range(self):
        """Test that invalid jitter_range raises error."""
        with pytest.raises(ValueError, match="jitter_range must be between 0 and 1"):
            RetryConfig(jitter_range=1.5)


class TestRetryManager:
    """Tests for RetryManager class."""

    def test_successful_first_attempt(self):
        """Test operation succeeds on first attempt."""
        config = RetryConfig(max_attempts=3, jitter=False)
        manager = RetryManager(config)

        mock_func = Mock(return_value="success")
        result = manager.execute(mock_func)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
        assert len(result.errors) == 0
        mock_func.assert_called_once()

    def test_successful_after_retries(self):
        """Test operation succeeds after initial failures."""
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)
        manager = RetryManager(config)

        mock_func = Mock(side_effect=[Exception("fail1"), Exception("fail2"), "success"])
        result = manager.execute(mock_func)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3
        assert len(result.errors) == 2

    def test_all_attempts_fail(self):
        """Test when all attempts fail."""
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)
        manager = RetryManager(config)

        mock_func = Mock(side_effect=Exception("always fails"))
        result = manager.execute(mock_func)

        assert result.success is False
        assert result.result is None
        assert result.attempts == 3
        assert len(result.errors) == 3
        assert result.final_error is not None

    def test_exponential_backoff_delays(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=100.0,
            exponential_base=2.0,
            jitter=False,
            strategy=RetryStrategy.EXPONENTIAL
        )
        manager = RetryManager(config)

        # Expected delays: 1, 2, 4, 8
        assert manager._calculate_delay(0) == 1.0
        assert manager._calculate_delay(1) == 2.0
        assert manager._calculate_delay(2) == 4.0
        assert manager._calculate_delay(3) == 8.0

    def test_linear_backoff_delays(self):
        """Test linear backoff delay calculation."""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=100.0,
            jitter=False,
            strategy=RetryStrategy.LINEAR
        )
        manager = RetryManager(config)

        # Expected delays: 1, 2, 3, 4
        assert manager._calculate_delay(0) == 1.0
        assert manager._calculate_delay(1) == 2.0
        assert manager._calculate_delay(2) == 3.0
        assert manager._calculate_delay(3) == 4.0

    def test_constant_backoff_delays(self):
        """Test constant backoff delay calculation."""
        config = RetryConfig(
            base_delay=2.0,
            jitter=False,
            strategy=RetryStrategy.CONSTANT
        )
        manager = RetryManager(config)

        # All delays should be constant
        assert manager._calculate_delay(0) == 2.0
        assert manager._calculate_delay(1) == 2.0
        assert manager._calculate_delay(5) == 2.0

    def test_fibonacci_backoff_delays(self):
        """Test fibonacci backoff delay calculation."""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=100.0,
            jitter=False,
            strategy=RetryStrategy.FIBONACCI
        )
        manager = RetryManager(config)

        # Expected: 1, 1, 2, 3, 5, 8
        assert manager._calculate_delay(0) == 1.0
        assert manager._calculate_delay(1) == 1.0
        assert manager._calculate_delay(2) == 2.0
        assert manager._calculate_delay(3) == 3.0
        assert manager._calculate_delay(4) == 5.0
        assert manager._calculate_delay(5) == 8.0

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(
            base_delay=10.0,
            max_delay=15.0,
            exponential_base=2.0,
            jitter=False,
            strategy=RetryStrategy.EXPONENTIAL
        )
        manager = RetryManager(config)

        # 10 * 2^2 = 40, but should be capped at 15
        assert manager._calculate_delay(2) == 15.0

    def test_jitter_adds_randomness(self):
        """Test that jitter adds variation to delays."""
        config = RetryConfig(
            base_delay=10.0,
            jitter=True,
            jitter_range=0.5
        )
        manager = RetryManager(config)

        delays = [manager._calculate_delay(0) for _ in range(20)]

        # With jitter, delays should vary
        assert len(set(delays)) > 1
        # All delays should be within expected range
        for delay in delays:
            assert 5.0 <= delay <= 15.0  # 10 +/- 50%

    def test_on_retry_callback(self):
        """Test that on_retry callback is called."""
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)
        manager = RetryManager(config)

        callback = Mock()
        mock_func = Mock(side_effect=[Exception("fail"), "success"])

        manager.execute(mock_func, on_retry=callback)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == 1  # attempt number
        assert isinstance(args[1], Exception)  # exception
        assert isinstance(args[2], float)  # delay

    def test_retryable_exceptions_filter(self):
        """Test that only specified exceptions trigger retry."""
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ValueError,)
        )
        manager = RetryManager(config)

        # ValueError should be retried
        mock_func = Mock(side_effect=[ValueError("retry this"), "success"])
        result = manager.execute(mock_func)
        assert result.success is True
        assert result.attempts == 2

        # TypeError should NOT be retried (not in retryable_exceptions)
        mock_func = Mock(side_effect=TypeError("don't retry"))
        with pytest.raises(TypeError):
            manager.execute(mock_func)

    def test_function_arguments_passed(self):
        """Test that args and kwargs are passed to function."""
        config = RetryConfig(max_attempts=1)
        manager = RetryManager(config)

        mock_func = Mock(return_value="ok")
        manager.execute(mock_func, "arg1", "arg2", kwarg1="value1")

        mock_func.assert_called_with("arg1", "arg2", kwarg1="value1")

    def test_total_time_tracked(self):
        """Test that total execution time is tracked."""
        config = RetryConfig(max_attempts=2, base_delay=0.05, jitter=False)
        manager = RetryManager(config)

        mock_func = Mock(side_effect=[Exception("fail"), "success"])
        result = manager.execute(mock_func)

        # Should include delay time
        assert result.total_time >= 0.05


class TestRetryDecorator:
    """Tests for the @retry decorator."""

    def test_decorator_success(self):
        """Test decorator with successful function."""
        @retry(max_attempts=3, base_delay=0.01, jitter=False)
        def always_works():
            return "worked"

        assert always_works() == "worked"

    def test_decorator_with_retries(self):
        """Test decorator retries on failure."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01, jitter=False)
        def works_third_time():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "finally"

        assert works_third_time() == "finally"
        assert call_count == 3

    def test_decorator_exhausts_retries(self):
        """Test decorator raises exception when retries exhausted."""
        @retry(max_attempts=2, base_delay=0.01, jitter=False)
        def always_fails():
            raise RuntimeError("permanent failure")

        with pytest.raises(RuntimeError, match="permanent failure"):
            always_fails()

    def test_decorator_with_arguments(self):
        """Test decorator preserves function arguments."""
        @retry(max_attempts=1)
        def add(a, b, c=0):
            return a + b + c

        assert add(1, 2) == 3
        assert add(1, 2, c=3) == 6

    def test_decorator_preserves_metadata(self):
        """Test decorator preserves function name and docstring."""
        @retry(max_attempts=1)
        def documented_function():
            """This is the docstring."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."


class TestPresetConfigs:
    """Tests for preset configurations."""

    def test_network_retry_config(self):
        """Test NETWORK_RETRY_CONFIG preset."""
        assert NETWORK_RETRY_CONFIG.max_attempts == 5
        assert NETWORK_RETRY_CONFIG.base_delay == 1.0
        assert NETWORK_RETRY_CONFIG.max_delay == 30.0
        assert NETWORK_RETRY_CONFIG.jitter is True

    def test_api_retry_config(self):
        """Test API_RETRY_CONFIG preset."""
        assert API_RETRY_CONFIG.max_attempts == 3
        assert API_RETRY_CONFIG.base_delay == 0.5
        assert API_RETRY_CONFIG.max_delay == 10.0

    def test_apt_retry_config(self):
        """Test APT_RETRY_CONFIG preset."""
        assert APT_RETRY_CONFIG.max_attempts == 3
        assert APT_RETRY_CONFIG.base_delay == 2.0
        assert APT_RETRY_CONFIG.jitter is False  # No jitter for apt


class TestConvenienceFunctions:
    """Tests for convenience retry functions."""

    def test_retry_apt_operation(self):
        """Test retry_apt_operation helper."""
        mock_func = Mock(return_value="installed")
        result = retry_apt_operation(mock_func)

        assert result.success is True
        assert result.result == "installed"

    def test_retry_api_call(self):
        """Test retry_api_call helper."""
        mock_func = Mock(return_value={"status": "ok"})
        result = retry_api_call(mock_func)

        assert result.success is True
        assert result.result == {"status": "ok"}

    def test_retry_network_operation(self):
        """Test retry_network_operation helper."""
        mock_func = Mock(return_value=b"data")
        result = retry_network_operation(mock_func)

        assert result.success is True
        assert result.result == b"data"


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    def test_transient_network_failure(self):
        """Simulate transient network failure recovery."""
        attempt = 0

        def flaky_network_call():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ConnectionError("Network unreachable")
            return {"data": "response"}

        result = retry_network_operation(flaky_network_call)

        assert result.success is True
        assert result.result == {"data": "response"}
        assert result.attempts == 3

    def test_rate_limit_recovery(self):
        """Simulate API rate limit with recovery."""
        config = RetryConfig(
            max_attempts=4,
            base_delay=0.01,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=False
        )
        manager = RetryManager(config)

        call_count = 0

        def rate_limited_api():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Rate limit exceeded")
            return {"result": "success"}

        result = manager.execute(rate_limited_api)

        assert result.success is True
        assert result.attempts == 3

    def test_permanent_failure_gives_up(self):
        """Test that permanent failures eventually give up."""
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)
        manager = RetryManager(config)

        def always_fails():
            raise PermissionError("Access denied")

        result = manager.execute(always_fails)

        assert result.success is False
        assert result.attempts == 3
        assert isinstance(result.final_error, PermissionError)
