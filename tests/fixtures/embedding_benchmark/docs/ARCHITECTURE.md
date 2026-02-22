# Architecture

## Overview

The application follows a layered architecture:

1. **CLI Layer** (`src/cli.py`) — Command-line interface for server, migrations, and user management
2. **API Layer** (`src/api.py`) — HTTP endpoints for CRUD operations
3. **Service Layer** — Business logic in `auth.py`, `cache.py`, `notifications.py`, `scheduler.py`
4. **Data Layer** (`src/database.py`, `src/models.py`) — Database connections and ORM models
5. **Infrastructure** — Middleware, logging, health checks, event bus

## Request Flow

```
CLI/HTTP Request
  → Middleware (rate limiting, CORS, logging)
  → API Router (endpoint matching)
  → Validation (input sanitization)
  → Service Logic (auth, business rules)
  → Data Layer (database queries)
  → Serialization (JSON/CSV response)
```

## Key Design Decisions

- **Event-driven communication** between services via `EventBus` (see `src/events.py`)
- **Cursor-based pagination** for large result sets (see `src/pagination.py`)
- **Structured JSON logging** for production observability (see `src/logging_config.py`)
- **Custom error hierarchy** with HTTP status codes (see `src/errors.py`)
- **Token bucket rate limiting** per client (see `src/middleware.py`)

## Database

- Connection pooling with configurable pool size
- Migration framework for schema versioning (`src/migrations.py`)
- SQLite for development, PostgreSQL for production

## Security

- JWT-based authentication with configurable token expiry
- bcrypt password hashing with salt rounds
- Input validation and HTML sanitization
- CORS whitelist for allowed origins
- Audit logging for sensitive operations
