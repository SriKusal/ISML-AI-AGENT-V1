# ADR-004: Retry Strategy

**Date:** 2026-08  
**Status:** Accepted

## Context

External API calls (LLM, embeddings) fail transiently due to rate limits, network issues, and provider overload. The system must handle these gracefully without cascading failures.

## Decision

Implement a reusable `async_retry` decorator with configurable `RetryConfig`. Apply separately to LLM calls (`LLM_RETRY_CONFIG`: 3 attempts, 2s base, 30s max) and embedding calls (`EMBEDDING_RETRY_CONFIG`: 2 attempts, 1s base). Auth errors (401/403/400) are not retried — they are configuration errors. Jitter (±25%) prevents thundering herd.

A second retry layer exists at the workflow level: `query_provider_node` rewinds to `BUILD_PROMPT` on failure if retries remain.

## Consequences

- Two-layer retry: transport-level (decorator) + workflow-level (phase rewind).
- Non-retryable errors fail fast without burning retry budget.
- Jitter distributes retry load across time.
- Circuit breaker not implemented (acceptable for current scale; document as future work).
