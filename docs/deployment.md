# Deployment Guide

## Prerequisites

- Python 3.12+
- PostgreSQL 15+ with [pgvector extension](https://github.com/pgvector/pgvector)
- Gemini API key (for LLM and embeddings)
- Optional: DeepSeek API key

## Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy from .env.example)
cp .env.example .env   # then fill in your API keys

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The app will attempt to connect to PostgreSQL on startup. If unavailable, it logs a warning and continues — all non-DB endpoints remain functional.

## Environment Variables

See `docs/architecture.md` for the full configuration reference.

Minimum required for full functionality:

```env
GEMINI_API_KEY=your_gemini_key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```

## Production Checklist

- [ ] Set `API_KEY_ENABLED=true` and `API_KEY=<strong-secret>`
- [ ] Set `CORS_ORIGINS=https://yourdomain.com` (not `*`)
- [ ] Set `DEBUG=false`
- [ ] Configure `RATE_LIMIT_PER_MINUTE` appropriate for your workload
- [ ] Use a connection pooler (e.g. PgBouncer) between the app and PostgreSQL
- [ ] Store secrets in a secrets manager (AWS Secrets Manager, GCP Secret Manager, etc.)
- [ ] Run behind a reverse proxy (nginx, Caddy) for TLS termination
- [ ] Enable structured log shipping (logs/app.log → ELK/CloudWatch/etc.)

## Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Database Setup

The app calls `init_db()` at startup which:
1. Creates the `vector` extension if not present
2. Creates all tables via SQLAlchemy `create_all`
3. Creates the HNSW index on `resource_embeddings`

For production, prefer Alembic migrations over `create_all`:

```bash
alembic init alembic
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

## Health Check

```
GET /api/v1/health
→ {"status": "ok"}
```

Use this endpoint for load balancer health checks and Kubernetes readiness probes.
