# ADR-006: Response Caching Strategy

**Date:** 2026-08  
**Status:** Accepted

## Context

Identical requests (same domain/course/topic/difficulty/provider) should not trigger the full pipeline repeatedly. A response cache provides the fastest possible response for repeated inputs.

## Decision

Implement an in-process LRU cache (`LRUResponseCache` in `app/services/response_cache.py`) keyed on a SHA-256 hash of the canonical request tuple. Cache size is configurable via `RESPONSE_CACHE_MAX_SIZE` (default 128; set to 0 to disable). Only `is_valid=True` responses are cached. The cache is checked before the workflow runs — on a HIT, the response is returned immediately with `_cached: true`.

The cache abstraction is designed for easy Redis replacement in multi-worker deployments (see `docs/scalability.md`).

## Consequences

- Zero-cost repeat requests within the same process.
- Per-process cache: multiple workers each have their own cache (Redis needed for sharing).
- Cache can be cleared via `DELETE /api/v1/resources/cache` when underlying data changes.
- Cache stats available via `GET /api/v1/resources/cache/stats`.
