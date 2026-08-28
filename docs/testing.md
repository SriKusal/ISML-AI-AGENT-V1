# Testing Guide

## Test Structure

```
tests/
├── test_dataset.py           # 50-topic shared fixture (5 domains)
├── test_app.py               # Health endpoint
├── test_deepseek.py          # DeepSeek route error handling
├── test_e2e.py               # Master E2E test (French A1 Greetings)
├── test_evaluation_ranking.py # Scoring + ranking unit tests
├── test_gemini_service.py    # Gemini URL building
├── test_integration.py       # Real external service tests (skipped by default)
├── test_output_validator.py  # Pydantic output schema validation
├── test_quality_thresholds.py # Quality tier classification
├── test_regression.py        # Regression suite for all working APIs
├── test_resource_discovery.py # Discovery engine unit tests
├── test_resource_validator.py # URL normalization + validation
├── test_retry.py             # Retry decorator unit tests
├── test_security.py          # API auth, SSRF, cache, error envelope
├── test_semantic_search.py   # Embedding service unit tests
└── test_workflow_nodes.py    # Individual workflow node unit tests
```

## Running Tests

```bash
# All unit + regression tests (no external deps required)
pytest tests/

# With coverage report
pytest tests/ --cov=app --cov=database --cov-report=term-missing

# Integration tests (requires real PostgreSQL + Gemini key)
INTEGRATION_DB=true INTEGRATION_LLM=true pytest tests/test_integration.py -v

# E2E test only
pytest tests/test_e2e.py -v
```

## Coverage

Current coverage: **75%** (above 70% target).

Low-coverage areas require live external services (DB, LLM) to test:
- `app/services/db_persistence.py` — tested by integration tests
- `app/api/knowledge_routes.py` — tested by integration tests

## Test Configuration

`pytest.ini` — asyncio mode set to `strict`, integration tests excluded from default run.

`.coveragerc` — covers `app/` and `database/`, excludes `__pycache__` and migrations.

## CI Pipeline

`.github/workflows/ci.yml`:
- **Unit/regression job** — runs on every push/PR, no external services needed
- **Integration job** — runs on push to main only, spins up a PostgreSQL + pgvector container
