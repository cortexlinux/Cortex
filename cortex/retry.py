"""Smart retry logic with exponential backoff for Cortex operations.

This module provides robust retry mechanisms for network operations,
API calls, and package installations that may fail transiently.

Implements Issue #43: Smart Retry Logic with Exponential Backoff
"""

import time
import random
import logging
import functools
from typing import Callable, TypeVar, Optional, Tuple, Type, Union, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryStrategy(Enum):
    """Available retry strategies."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"
    FIBONACCI = "fibonacci"


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts (including initial try)
        base_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential backoff (default 2)
        jitter: Whether to add random jitter to prevent thundering herd
        jitter_range: Range for jitter as fraction of delay (0.0 to 1.0)
        strategy: Retry strategy to use
        retryable_exceptions: Tuple of exception types that trigger retry
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.25
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be non-negative")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if not 0 <= self.jitter_range <= 1:
            raise ValueError("jitter_range must be between 0 and 1")


@dataclass
class RetryResult:
    """Result of a retry operation.

    Attributes:
        success: Whether the operation ultimately succeeded
        result: The return value if successful, None otherwise
        attempts: Number of attempts made
        total_time: Total time spent including delays
        errors: List of errors encountered during retries
        final_error: The last error if operation failed
    """
    success: bool
    result: Optional[T] = None
    attempts: int = 0
    total_time: float = 0.0
    errors: List[Exception] = field(default_factory=list)
    final_error: Optional[Exception] = None


class RetryManager:
    """Manages retry operations with configurable backoff strategies."""

    # Precomputed Fibonacci sequence for fibonacci backoff
    _FIBONACCI = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize retry manager with configuration.

        Args:
            config: RetryConfig instance, uses defaults if None
        """
        self.config = config or RetryConfig()

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        if self.config.strategy == RetryStrategy.CONSTANT:
            delay = self.config.base_delay

        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay * (attempt + 1)

        elif self.config.strategy == RetryStrategy.FIBONACCI:
            fib_index = min(attempt, len(self._FIBONACCI) - 1)
            delay = self.config.base_delay * self._FIBONACCI[fib_index]

        else:  # EXPONENTIAL (default)
            delay = self.config.base_delay * (self.config.exponential_base ** attempt)

        # Apply max delay cap
        delay = min(delay, self.config.max_delay)

        # Apply jitter if enabled
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_range
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative

        return delay

    def execute(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
        **kwargs
    ) -> RetryResult:
        """Execute a function with retry logic.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            on_retry: Optional callback called before each retry with
                     (attempt_number, exception, delay)
            **kwargs: Keyword arguments for the function

        Returns:
            RetryResult containing success status and result or errors
        """
        start_time = time.time()
        errors: List[Exception] = []

        for attempt in range(self.config.max_attempts):
            try:
                result = func(*args, **kwargs)
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_time=time.time() - start_time,
                    errors=errors
                )

            except self.config.retryable_exceptions as e:
                errors.append(e)

                if attempt < self.config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)

                    logger.warning(
                        f"Attempt {attempt + 1}/{self.config.max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    if on_retry:
                        on_retry(attempt + 1, e, delay)

                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {self.config.max_attempts} attempts failed. "
                        f"Final error: {e}"
                    )

        return RetryResult(
            success=False,
            attempts=self.config.max_attempts,
            total_time=time.time() - start_time,
            errors=errors,
            final_error=errors[-1] if errors else None
        )


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
):
    """Decorator for adding retry logic to functions.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter
        strategy: Retry strategy to use
        retryable_exceptions: Exception types that trigger retry
        on_retry: Callback for retry events

    Returns:
        Decorated function with retry logic

    Example:
        @retry(max_attempts=3, base_delay=1.0)
        def fetch_packages():
            return requests.get("https://api.example.com/packages")
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        strategy=strategy,
        retryable_exceptions=retryable_exceptions
    )
    manager = RetryManager(config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            result = manager.execute(func, *args, on_retry=on_retry, **kwargs)

            if result.success:
                return result.result
            else:
                raise result.final_error

        return wrapper

    return decorator


# Preset configurations for common use cases
NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL,
    jitter=True
)

API_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    strategy=RetryStrategy.EXPONENTIAL,
    jitter=True
)

APT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL,
    jitter=False  # No jitter for apt operations
)


def retry_apt_operation(func: Callable[..., T], *args, **kwargs) -> RetryResult:
    """Convenience function for retrying apt operations.

    Uses preset configuration optimized for package manager operations
    which may fail due to lock files or network issues.

    Args:
        func: The apt operation function
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        RetryResult with operation outcome
    """
    manager = RetryManager(APT_RETRY_CONFIG)
    return manager.execute(func, *args, **kwargs)


def retry_api_call(func: Callable[..., T], *args, **kwargs) -> RetryResult:
    """Convenience function for retrying API calls.

    Uses preset configuration optimized for LLM API calls
    with rate limiting considerations.

    Args:
        func: The API call function
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        RetryResult with operation outcome
    """
    manager = RetryManager(API_RETRY_CONFIG)
    return manager.execute(func, *args, **kwargs)


def retry_network_operation(func: Callable[..., T], *args, **kwargs) -> RetryResult:
    """Convenience function for retrying network operations.

    Uses preset configuration optimized for network requests
    that may fail due to connectivity issues.

    Args:
        func: The network operation function
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        RetryResult with operation outcome
    """
    manager = RetryManager(NETWORK_RETRY_CONFIG)
    return manager.execute(func, *args, **kwargs)
