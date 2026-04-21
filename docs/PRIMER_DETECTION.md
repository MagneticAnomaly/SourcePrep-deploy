# Primer Detection & Precedence

This document defines how Prep detects and handles primer files (project context documents like `AGENTS.md`).

## Overview

Primer files provide high-level project context that should be prioritized in search results. Prep automatically detects these files and applies score boosts to ensure they surface when relevant.

## Default Primer Filenames

**Precedence order (first match wins):**

1. `AGENTS.md` — Primary (Anthropic/Windsurf convention)
2. `PREP_PRIMER.md` — Prep-specific
3. `PROJECT_PRIMER.md` — Generic fallback

All three are checked; any match is treated as a primer.

## Detection Rules

### Location Constraint

Primers are **only detected in the repository root**:

```python
# Check if file is in repo root (no directory separators)
if "/" not in source_path and "\\" not in source_path:
    if source_path.lower() in primer_names:
        # This is a primer
```

**Rationale:**
- Avoids false positives from nested docs (e.g., `docs/AGENTS.md`)
- Clear ownership (one primer per repo)
- Matches convention from Anthropic's MCP documentation

### Case Insensitivity

Filename matching is case-insensitive:
- `AGENTS.md` ✓
- `agents.md` ✓
- `Agents.MD` ✓

## Configuration

Primer behavior is configured in `repo_policy.json`:

```json
{
  "primer": {
    "enabled": true,
    "filenames": ["AGENTS.md", "PREP_PRIMER.md", "PROJECT_PRIMER.md"],
    "score_boost": 0.25,
    "always_include": false,
    "max_primer_chars": 2000
  }
}
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | `true` | Enable primer detection |
| `filenames` | `["AGENTS.md", "PREP_PRIMER.md", "PROJECT_PRIMER.md"]` | Files to treat as primers |
| `score_boost` | `0.25` | Score added to primer chunks |
| `always_include` | `false` | Always include primers in context |
| `max_primer_chars` | `2000` | Max chars when `always_include=true` |

## Score Boosting

When primers are enabled, chunks from primer files receive a score boost:

```python
final_score = semantic_score + keyword_boost + fts_boost + primer_boost
```

**Default boost:** `0.25` (25% of max similarity score)

This ensures primer content surfaces for relevant queries without completely overriding semantic relevance.

## Always-Include Mode

When `always_include: true`:

1. Primer chunks are **prepended** to every context assembly
2. Limited by `max_primer_chars` budget
3. Marked with `[PRIMER]` header
4. Get `score: 1.0` in metadata

**Use case:** Ensuring LLMs always see project conventions/guidelines.

```python
# Example context output with always_include=true
"""
[PRIMER | @AGENTS.md]
This project uses Python 3.10+ and follows PEP 8...

---

[@src/main.py:1-50]
def main():
    ...
"""
```

## Customization

### Adding Custom Primer Names

Edit `repo_policy.json`:

```json
{
  "primer": {
    "filenames": ["AGENTS.md", "CONTRIBUTING.md", "ARCHITECTURE.md"]
  }
}
```

### Disabling Primers

```json
{
  "primer": {
    "enabled": false
  }
}
```

### Increasing Boost

```json
{
  "primer": {
    "score_boost": 0.4
  }
}
```

## API Access

### Get Primer Chunks

```python
from prep.core import CodeIndex

index = CodeIndex(index_dir=...)
primer_chunks = index.get_primer_chunks()

for chunk in primer_chunks:
    print(f"File: {chunk['source_path']}")
    print(f"Content: {chunk['content'][:100]}...")
```

### Check if File is Primer

```python
def is_primer(source_path: str, config: dict) -> bool:
    filenames = config.get("primer", {}).get("filenames", [])
    primer_names = {f.lower() for f in filenames}
    
    # Must be in root (no path separators)
    if "/" in source_path or "\\" in source_path:
        return False
    
    return source_path.lower() in primer_names
```

## Best Practices

### Writing Effective Primers

1. **Keep it concise** — Under 2000 characters is ideal
2. **Focus on conventions** — Coding style, architecture patterns
3. **Include key context** — Tech stack, important APIs
4. **Avoid duplication** — Don't repeat README content

### Example AGENTS.md

```markdown
# Project Context

## Tech Stack
- Python 3.10+
- FastAPI for HTTP API
- SQLite for persistence
- NumPy for embeddings

## Conventions
- Use type hints everywhere
- Prefer `pathlib.Path` over `os.path`
- Error handling via `ApiException`

## Key Modules
- `prep.core.index` — Embedding index
- `prep.core.trace` — Code graph
- `prep.server` — HTTP API
```

## Limitations

### Single-Level Detection

Primers are only detected at repo root. Nested primers (e.g., `packages/core/AGENTS.md`) are not recognized.

**Workaround:** Add nested paths explicitly to `filenames`:
```json
{
  "primer": {
    "filenames": ["AGENTS.md", "packages/core/AGENTS.md"]
  }
}
```

### No Glob Support

Primer detection uses exact filename matching, not globs.

**Future:** May add `"primer_globs": ["**/AGENTS.md"]` support.

## Related Documentation

- `docs/MANIFEST_SCHEMA.md` — Config snapshot in manifest
- `docs/BUDGETS_POLICY.md` — `max_primer_chars` limits
- `tests/test_primer.py` — Primer feature tests
