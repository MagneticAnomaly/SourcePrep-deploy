# Prep Budgets Policy

This document defines the budget limits and defaults for output size, file handling, and query parameters across Prep's HTTP API, MCP server, and CLI.

## Overview

Budgets prevent runaway resource consumption and ensure predictable behavior. They are enforced at the **server level** and documented across all interfaces.

## Search Budgets

| Parameter | Default | Max | Min | Description |
|-----------|---------|-----|-----|-------------|
| `k` | 5 | 50 | 1 | Number of chunks to return |
| `min_score` | 0.0 | 1.0 | 0.0 | Minimum similarity score threshold |

### Enforcement

```python
# MCP Server (mcp_server.py)
MAX_SEARCH_K = 50

if k > MAX_SEARCH_K:
    raise InvalidParamsError(f"k too large (max {MAX_SEARCH_K})")
```

## Context Assembly Budgets

| Parameter | Default | Max | Min | Description |
|-----------|---------|-----|-----|-------------|
| `k` | 5 | 50 | 1 | Number of chunks to include |
| `max_chars` | 6000 | 20000 | 1 | Maximum characters in assembled context |
| `min_score` | 0.0 | 1.0 | 0.0 | Minimum similarity score threshold |

### Enforcement

```python
# MCP Server (mcp_server.py)
MAX_CONTEXT_K = 50
MAX_CONTEXT_CHARS = 20_000

if k > MAX_CONTEXT_K:
    raise InvalidParamsError(f"k too large (max {MAX_CONTEXT_K})")
if max_chars > MAX_CONTEXT_CHARS:
    raise InvalidParamsError(f"max_chars too large (max {MAX_CONTEXT_CHARS})")
```

### Interface Defaults

| Interface | Default `k` | Default `max_chars` |
|-----------|-------------|---------------------|
| MCP Server | 5 | 6000 |
| CLI | 5 | 8000 |
| Dashboard | 5 | 6000 |

**Note:** CLI uses a slightly higher default (8000) to accommodate terminal output scenarios.

## File Handling Budgets

| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `max_file_bytes` | 400,000 | 500,000 | Maximum file size for indexing |

### Enforcement

Files exceeding `max_file_bytes` are:
- **Skipped during indexing** (not embedded)
- **Rejected by file viewer** (HTTP 413 `FILE_TOO_LARGE`)

### Rationale

- **400KB default**: Balances coverage with indexing speed
- **500KB hard max**: Prevents memory issues during chunking
- Large files (generated code, minified JS, data files) are typically low-value for semantic search

## Watcher Budgets

| Parameter | Default | Max | Min | Description |
|-----------|---------|-----|-----|-------------|
| `debounce_ms` | 5000 | 60000 | 500 | Delay before triggering rebuild |
| `min_gap_ms` | 2000 | 30000 | 500 | Minimum time between rebuilds |

### Rationale

- **5s debounce**: Catches rapid saves during active editing
- **2s min gap**: Prevents thrashing during bulk operations
- **60s max debounce**: Ensures changes are eventually indexed

## Primer Budgets

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_primer_chars` | 2000 | Maximum characters from primer files |
| `score_boost` | 0.25 | Score boost for primer chunks |

## Cross-Interface Alignment

All interfaces (HTTP API, MCP, CLI) should:

1. **Use the same max limits** (server-enforced)
2. **Document defaults clearly** in help text and tool schemas
3. **Return clear errors** when limits are exceeded

### MCP Tool Schema Example

```json
{
  "name": "prep",
  "inputSchema": {
    "properties": {
      "k": {
        "type": "integer",
        "description": "Number of chunks to include. Default: 5, Max: 50.",
        "default": 5
      },
      "max_chars": {
        "type": "integer",
        "description": "Maximum characters in assembled context. Default: 6000, Max: 20000.",
        "default": 6000
      }
    }
  }
}
```

## Changing Budgets

### Server-Side (Authoritative)

Edit constants in `src/prep/mcp_server.py`:

```python
MAX_SEARCH_K = 50
MAX_CONTEXT_K = 50
MAX_CONTEXT_CHARS = 20_000
```

### Client-Side (Defaults)

Update defaults in:
- `src/prep/cli.py` / `cli_new.py` — CLI defaults
- `src/prep/mcp_tools.py` — MCP tool schema defaults
- `src/prep/dashboard/src/App.tsx` — Dashboard UI defaults

### Documentation

When changing budgets, update:
1. This document (`docs/BUDGETS_POLICY.md`)
2. MCP tool descriptions (`src/prep/mcp_tools.py`)
3. CLI help text (`--help` output)
4. API documentation (`docs/API.md`)

## Future Considerations

### Per-Project Budgets

Currently, budgets are global. Future versions may support:
- Per-project `max_file_bytes` overrides
- Per-project context assembly limits
- Team-level budget policies

### Token-Based Budgets

As LLM context windows grow, consider:
- `max_tokens` instead of `max_chars`
- Model-aware token counting
- Budget recommendations based on target LLM

### Rate Limiting

For multi-user deployments:
- Requests per minute limits
- Concurrent build limits
- Query queue depth limits
