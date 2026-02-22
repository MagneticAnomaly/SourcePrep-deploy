# Deployment Guide

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ (production) or SQLite (development)
- Redis (optional, for distributed caching)

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `sqlite:///app.db` | Database connection string |
| `SECRET_KEY` | Yes | — | JWT signing key |
| `SMTP_HOST` | No | — | Email notification SMTP server |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `RATE_LIMIT` | No | `100` | Max requests per minute per client |

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python -m src.cli migrate --direction up

# Start server
python -m src.cli serve --host 0.0.0.0 --port 8000 --reload
```

## Health Checks

The application exposes health check endpoints:

- `GET /health` — Full health check with component status
- `GET /ready` — Quick readiness probe (returns 200 or 503)

## Monitoring

- Structured JSON logs when `LOG_LEVEL=INFO` and `--json-logs` flag
- Audit trail for authentication and permission changes
- Background job status via `GET /jobs/status`
