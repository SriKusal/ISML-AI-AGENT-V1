# Security Guide

## Authentication

API key authentication is **disabled by default** for local development. To enable it in production:

```env
API_KEY_ENABLED=true
API_KEY=your-strong-secret-here
```

Clients send the key in the `X-API-Key` header:

```
POST /api/v1/resources/intelligence
X-API-Key: your-strong-secret-here
```

**Implementation details:**
- Uses `hmac.compare_digest` for constant-time comparison (timing attack resistant)
- Only the first 4 characters of an invalid key are logged (key value never logged)
- Returns `401 Unauthorized` with `WWW-Authenticate: ApiKey` on failure

## Rate Limiting

Configure via `RATE_LIMIT_PER_MINUTE` env var (default: 20 requests/minute per IP):

```env
RATE_LIMIT_PER_MINUTE=10
```

Exceeding the limit returns `429 Too Many Requests`.

## CORS Configuration

Default `CORS_ORIGINS=*` is suitable for development only. In production:

```env
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

## SSRF Protection

`normalize_url()` in `app/services/resource_validator.py` blocks:

- `localhost` and loopback addresses (127.x.x.x, ::1)
- Private IP ranges (10.x, 172.16-31.x, 192.168.x)
- Link-local addresses (169.254.x.x — AWS/GCP metadata services)
- CGNAT range (100.64-127.x)
- Non-HTTP schemes (ftp://, file://, etc.)
- Bare hostnames without dots (rejects malformed URLs)

Use `validate_external_url()` from `app/security.py` when the application fetches external URLs directly.

## Secret Management

- All secrets are loaded from environment variables or the `.env` file
- `.env` is listed in `.gitignore` — never commit it
- Never log API keys, database passwords, or other secrets
- For production, use a proper secrets manager (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault)

## Error Handling

The `generic_exception_handler` in `app/errors.py` catches all unhandled exceptions and returns a safe `{"error": {"code": "INTERNAL_ERROR", "message": "..."}}` response. Internal stack traces are logged server-side but **never exposed in API responses**.
