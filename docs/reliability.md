# Reliability Guide

## Retry Strategy

LLM and embedding calls use `async_retry` from `app/utils/retry.py`:

| Config | LLM | Embedding |
|---|---|---|
| Max attempts | 3 | 2 |
| Base delay | 2.0s | 1.0s |
| Max delay | 30s | 10s |
| Backoff | 2× exponential | 2× exponential |
| Jitter | ±25% | ±20% |
| Non-retryable | 401, 403, 400, invalid_api_key | same |

## LLM Output Repair-Retry

If the LLM returns valid JSON but the output fails Pydantic schema validation:

1. `validate_output_node` builds a **repair prompt fragment** describing the exact validation failures.
2. The fragment is prepended to the task prompt in `build_prompt_node`.
3. The LLM is called again (up to `max_retries` times).
4. If all retries fail, the workflow completes with `is_valid=False` and the errors are logged.

## Per-Resource Error Isolation (BUG-017)

Every resource is processed in an individual try/except block. If one resource fails (scoring error, DB write error, embedding error), it is logged and skipped. The remaining resources continue processing.

## Graceful DB Failure

- If PostgreSQL is unavailable at startup, the app logs a warning and continues. All non-DB endpoints remain functional.
- If the DB fails during persistence, the error is logged and the API response is still returned to the client.

## Graceful Embedding Failure

If the embedding API fails for a resource, the resource is still stored in the database — it just won't have a pgvector vector until a future background verification run.

## Knowledge Retrieval Fallback

If the DB is unavailable during the knowledge retrieval check, the node logs a warning and falls through to the normal discovery pipeline. The workflow never fails due to a failed retrieval check.
