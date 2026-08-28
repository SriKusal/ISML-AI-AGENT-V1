# Scalability Guide (ARCH-002)

## Current Design

The application is built for horizontal scaling from the start:

- **Stateless FastAPI app** — no in-process session state between requests. Each request is fully self-contained.
- **Async I/O** — all database, LLM, and embedding calls use `async`/`await` with `asyncpg`. Multiple requests are handled concurrently within a single worker.
- **Connection pooling** — `database/connection.py` configures `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`. Configurable via `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` env vars.
- **Parallel discovery** — `ResourceDiscoveryEngine.discover_all()` uses `asyncio.gather` across all queries and source types simultaneously.
- **Batch embeddings** — `DatabasePersistenceService` generates all embeddings for a run in parallel via `asyncio.gather`.
- **pgvector HNSW index** — approximate nearest-neighbor search stays fast as the vector table grows.

## Scaling Strategies

### Horizontal scaling (multiple instances)

Run multiple uvicorn workers or containers behind a load balancer. Because the app is stateless, any instance can handle any request.

```bash
# Multiple workers in a single process
uvicorn main:app --workers 4

# Or with gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

**In-process LRU cache caveat:** The `LRUResponseCache` is per-process. In a multi-worker deployment, each worker maintains its own cache. For a shared cache across workers, replace `LRUResponseCache` with a Redis-backed implementation (see extension point in `app/services/response_cache.py`).

### Database scaling

- Use connection pooling middleware (PgBouncer in transaction mode) to reduce DB connections from many app instances.
- Read replicas for `GET` endpoints (`/knowledge/resources`, `/knowledge/search`, `/knowledge/history`).
- The pgvector HNSW index handles millions of vectors efficiently. For very large datasets, consider `IVFFlat` with `nlist` tuning.

### Background task offloading

Currently, workflow execution is synchronous within the API request. For very long workflows (many resources, slow LLM responses), consider offloading to a background worker:

```python
# Extension point: replace execute_workflow() with a Celery task
from celery import Celery
app = Celery("isml", broker="redis://localhost:6379/0")

@app.task
def run_workflow_task(domain, course, topic, difficulty_level, provider):
    # Run the full workflow
    ...
```

The application is designed with this split in mind — `execute_workflow()` in `resource_routes.py` is a single await point that can be replaced with a task dispatch.

### Rate limiting at scale

The current `slowapi` rate limiter is per-process. For distributed rate limiting across multiple instances, configure a Redis backend:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",  # shared across instances
)
```

## Estimated Capacity (single instance, 4 workers)

| Metric | Estimate |
|---|---|
| Concurrent requests | 40–80 (async I/O bound) |
| LLM-bound requests | 4–8/min (LLM latency is the bottleneck) |
| Knowledge retrieval (DB cache hit) | 200–400 req/min |
| Semantic search | 100–200 req/min |

These are rough estimates. Profile against your specific LLM provider latency and DB hardware.
