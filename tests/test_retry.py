"""Tests for the retry utility.

Validates:
- async_retry retries the correct number of times
- Exponential backoff delays increase per attempt
- Non-retryable errors (401, 403, 400) are raised immediately
- Jitter stays within expected bounds
- RetryConfig.delay_for produces bounded values
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.utils.retry import RetryConfig, async_retry, LLM_RETRY_CONFIG, EMBEDDING_RETRY_CONFIG


class TestRetryConfig(unittest.TestCase):

    def test_delay_increases_exponentially(self):
        cfg = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.0, max_delay=100.0)
        d1 = cfg.delay_for(1)
        d2 = cfg.delay_for(2)
        d3 = cfg.delay_for(3)
        self.assertAlmostEqual(d1, 1.0, places=1)
        self.assertAlmostEqual(d2, 2.0, places=1)
        self.assertAlmostEqual(d3, 4.0, places=1)

    def test_delay_capped_at_max(self):
        cfg = RetryConfig(base_delay=1.0, exponential_base=10.0, jitter=0.0, max_delay=5.0)
        self.assertLessEqual(cfg.delay_for(5), 5.0)

    def test_jitter_stays_in_bounds(self):
        cfg = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.25, max_delay=100.0)
        for attempt in range(1, 5):
            delay = cfg.delay_for(attempt)
            base = min(1.0 * (2.0 ** (attempt - 1)), 100.0)
            self.assertGreaterEqual(delay, base)
            self.assertLessEqual(delay, base * 1.30)

    def test_llm_retry_config_values(self):
        self.assertEqual(LLM_RETRY_CONFIG.max_attempts, 3)
        self.assertEqual(LLM_RETRY_CONFIG.base_delay, 2.0)
        self.assertEqual(LLM_RETRY_CONFIG.max_delay, 30.0)

    def test_embedding_retry_config_values(self):
        self.assertEqual(EMBEDDING_RETRY_CONFIG.max_attempts, 2)
        self.assertEqual(EMBEDDING_RETRY_CONFIG.base_delay, 1.0)


class TestAsyncRetryDecorator(unittest.IsolatedAsyncioTestCase):

    async def test_succeeds_on_first_attempt(self):
        call_count = 0

        @async_retry(RetryConfig(max_attempts=3, base_delay=0, jitter=0))
        async def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    async def test_retries_and_succeeds_on_second_attempt(self):
        call_count = 0

        @async_retry(RetryConfig(max_attempts=3, base_delay=0, jitter=0))
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("transient error")
            return "ok"

        result = await func()
        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 2)

    async def test_raises_after_max_attempts(self):
        call_count = 0

        @async_retry(RetryConfig(max_attempts=3, base_delay=0, jitter=0))
        async def func():
            nonlocal call_count
            call_count += 1
            raise Exception("always fails")

        with self.assertRaises(Exception):
            await func()

        self.assertEqual(call_count, 3)

    async def test_does_not_retry_on_401(self):
        call_count = 0

        @async_retry(RetryConfig(max_attempts=3, base_delay=0, jitter=0))
        async def func():
            nonlocal call_count
            call_count += 1
            raise Exception("401 Unauthorized")

        with self.assertRaises(Exception):
            await func()

        self.assertEqual(call_count, 1)

    async def test_does_not_retry_on_403(self):
        call_count = 0

        @async_retry(RetryConfig(max_attempts=3, base_delay=0, jitter=0))
        async def func():
            nonlocal call_count
            call_count += 1
            raise Exception("403 Forbidden")

        with self.assertRaises(Exception):
            await func()

        self.assertEqual(call_count, 1)

    async def test_does_not_retry_on_invalid_api_key(self):
        call_count = 0

        @async_retry(RetryConfig(max_attempts=3, base_delay=0, jitter=0))
        async def func():
            nonlocal call_count
            call_count += 1
            raise Exception("invalid_api_key provided")

        with self.assertRaises(Exception):
            await func()

        self.assertEqual(call_count, 1)

    async def test_retries_on_503(self):
        call_count = 0

        @async_retry(RetryConfig(max_attempts=3, base_delay=0, jitter=0))
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("503 Service Unavailable")
            return "recovered"

        result = await func()
        self.assertEqual(result, "recovered")
        self.assertEqual(call_count, 3)

    async def test_preserves_function_name(self):
        @async_retry()
        async def my_function():
            return True

        self.assertEqual(my_function.__name__, "my_function")
