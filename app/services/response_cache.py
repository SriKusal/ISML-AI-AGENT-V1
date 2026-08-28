"""In-process LRU response cache for workflow results (ENH-007).

Caches the final API response keyed on (domain, course, topic, difficulty_level, provider).
This avoids redundant LLM calls and discovery pipelines for identical repeated requests.

Design decisions
----------------
- Uses Python's functools.lru_cache on a stable string key derived from request fields.
- Cache size is configurable via Settings.RESPONSE_CACHE_MAX_SIZE (default 128).
- Set RESPONSE_CACHE_MAX_SIZE=0 in .env to disable caching entirely.
- Cache is per-process (not shared across workers). For multi-worker deployments,
  use Redis as the backing store (see docs/architecture.md).
- Secrets are never cached. The LLM API key is not part of the cache key.
- Cache entries are dicts (JSON-serializable) to allow easy inspection.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from threading import Lock
from typing import Any, Optional

from app.config import settings
from app.logging import get_logger

logger = get_logger("app.services.response_cache")


class LRUResponseCache:
    """Thread-safe LRU cache for workflow responses.

    Keys are stable SHA-256 hashes of the canonical request tuple.
    Values are complete response dicts (shallow copies stored).
    """

    def __init__(self, max_size: int = 128) -> None:
        self._max_size = max_size
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def make_key(
        domain: str,
        course: str,
        topic: str,
        difficulty_level: str,
        provider: str,
    ) -> str:
        """Return a deterministic cache key for a workflow request."""
        canonical = json.dumps(
            {
                "domain": domain.strip().lower(),
                "course": course.strip().lower(),
                "topic": topic.strip().lower(),
                "difficulty_level": difficulty_level.strip().lower(),
                "provider": provider.strip().lower(),
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:24]

    def get(self, key: str) -> Optional[dict]:
        """Return cached response or None if not found / cache disabled."""
        if self._max_size <= 0:
            return None
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            logger.debug("Cache HIT key=%s (hits=%d misses=%d)", key, self._hits, self._misses)
            return dict(self._cache[key])  # shallow copy

    def set(self, key: str, value: dict) -> None:
        """Store a response. Evicts LRU entry if capacity is exceeded."""
        if self._max_size <= 0:
            return
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = dict(value)  # shallow copy
            if len(self._cache) > self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug("Cache evicted key=%s", evicted_key)

    def invalidate(self, key: str) -> bool:
        """Remove a specific entry. Returns True if it existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict:
        with self._lock:
            size = len(self._cache)
        return {
            "size": size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(1, self._hits + self._misses), 3),
            "enabled": self._max_size > 0,
        }


# ---------------------------------------------------------------------------
# Module-level singleton — shared across all requests in this process
# ---------------------------------------------------------------------------
_cache = LRUResponseCache(max_size=settings.RESPONSE_CACHE_MAX_SIZE)


def get_cache() -> LRUResponseCache:
    """Return the module-level cache instance."""
    return _cache
