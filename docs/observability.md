# Observability Guide

## Structured Logging

Every log line is emitted in two formats simultaneously:
- **Console** (PlainFormatter): `2026-01-01 12:00:00 [corr-id] logger.name INFO - message`
- **File** (`logs/app.log`, JSONFormatter): one JSON object per line

JSON log fields: `timestamp`, `level`, `logger`, `message`, `correlation_id`, plus optional `duration_ms`, `phase`, `node`, `provider`, `resources_count`, `error_type`.

**Correlation ID:** Every HTTP request gets a UUID correlation ID (from `X-Correlation-ID` header or auto-generated). It appears in all log lines for that request and is returned as `X-Correlation-ID` in the response header.

## WorkflowRun Observability Record

Every call to `POST /api/v1/resources/intelligence` creates a `WorkflowRun` record in the database with:

| Field | Description |
|---|---|
| `id` | UUID run identifier |
| `domain / course / topic_name / difficulty_level` | Input parameters |
| `provider / model` | LLM provider used |
| `success` | Whether `is_valid=True` at completion |
| `final_phase` | Last workflow phase reached |
| `attempt_count` | Total LLM attempts |
| `retry_count` | Number of retries (attempts - 1) |
| `duration_ms` | Total request duration in milliseconds |
| `resources_discovered` | Total resources found across all queries |
| `resources_validated` | Resources passing URL + field validation |
| `resources_rejected` | Resources rejected by validator |
| `resources_evaluated` | Resources successfully scored |
| `resources_ranked` | Resources in final ranking |
| `resources_persisted` | Resources saved to DB |
| `embeddings_generated` | Embeddings stored in pgvector |
| `knowledge_retrieved` | True if DB cache was used (discovery skipped) |
| `llm_prompt_tokens` | LLM prompt token count |
| `llm_completion_tokens` | LLM completion token count |
| `llm_total_tokens` | Total tokens used |
| `messages` | JSON array of workflow log messages |
| `errors` | JSON array of validation/error messages |
| `parsed_output` | Final LLM output JSON |

## Query WorkflowRun History

```
GET /api/v1/knowledge/history?limit=20&success_only=true
```

## Node Timing

`NodeTimer` context manager logs execution time for `discover_resources` and `evaluate_resources` nodes:

```
INFO app.agents.workflow - Node 'discover_resources' completed in 342ms
```

## Cache Statistics

```
GET /api/v1/resources/cache/stats
→ {"cache": {"size": 12, "max_size": 128, "hits": 45, "misses": 23, "hit_rate": 0.661}}
```
