"""Retry utility with exponential backoff and jitter.

Provides:
- async_retry decorator — wraps any async function with configurable retry logic
- RetryConfig          — dataclass for tuning retry behaviour per use case
"""

import asyncio
import random
import functools
from dataclasses import dataclass, field
from typing import Callable, Type

from app.logging import get_logger

logger = get_logger("app.utils.retry")


@dataclass
class RetryConfig:
    """Configuration for retry behaviour.

    Attributes
    ----------
    max_attempts    : Total attempts including the first (default 3)
    base_delay      : Initial backoff in seconds (default 1.0)
    max_delay       : Cap on backoff delay in seconds (default 30.0)
    exponential_base: Multiplier per retry (default 2.0)
    jitter          : Add random jitter up to this fraction of the delay (default 0.25)
    retryable_exceptions: Exception types that trigger a retry
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: float = 0.25
    retryable_exceptions: tuple[Type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )

    def delay_for(self, attempt: int) -> float:
        """Compute the delay before the next attempt.

        attempt starts at 1 for the first retry (second overall attempt).
        """
        delay = min(
            self.base_delay * (self.exponential_base ** (attempt - 1)),
            self.max_delay,
        )
        # Add ±jitter to prevent thundering herd
        delay += random.uniform(0, self.jitter * delay)
        return round(delay, 3)


# Sensible defaults for LLM provider calls
LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=0.25,
)

# Fast retry for embedding calls (cheaper, rate limits differ)
EMBEDDING_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=0.20,
)


def async_retry(config: RetryConfig | None = None):
    """Decorator that retries an async function with exponential backoff.

    Usage::

        @async_retry(LLM_RETRY_CONFIG)
        async def call_llm(...):
            ...

        # Or with defaults
        @async_retry()
        async def call_api(...):
            ...
    """
    cfg = config or RetryConfig()

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc: Exception | None = None

            for attempt in range(1, cfg.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except cfg.retryable_exceptions as exc:
                    last_exc = exc
                    error_str = str(exc)

                    # Do NOT retry on auth / bad-request errors
                    if any(code in error_str for code in ("401", "403", "400", "invalid_api_key")):
                        logger.error(
                            "%s failed with non-retryable error: %s",
                            func.__name__, exc,
                        )
                        raise

                    if attempt == cfg.max_attempts:
                        logger.error(
                            "%s exhausted %d attempts. Last error: %s",
                            func.__name__, cfg.max_attempts, exc,
                        )
                        raise

                    delay = cfg.delay_for(attempt)
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying in %.1fs",
                        func.__name__, attempt, cfg.max_attempts, exc, delay,
                        extra={"error_type": type(exc).__name__},
                    )
                    await asyncio.sleep(delay)

            raise last_exc  # pragma: no cover

        return wrapper
    return decorator
