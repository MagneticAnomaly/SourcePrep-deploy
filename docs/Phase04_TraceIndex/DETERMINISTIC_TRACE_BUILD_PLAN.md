# Deterministic Trace Build Plan (Draft)

This document is a **first draft** plan for building Prep’s Trace Index in a way that is:

- Deterministic (repeatable given the same inputs)
- Robust across diverse repository structures (no “Phase” assumptions)
- Bounded (does not explode on large repos)
- Transparent (diffable outputs; failures are reported, not hidden)

It complements:

- `./README.md` (schema + API)
- `./REPO_DISCOVERY_AND_POLICY.md` (repo profiling → include/exclude + weighting)

## Core principle

- The **Trace Index** is a structural graph: files, symbols, and relationships.
- The build process must be **deterministic-by-default** and degrade gracefully:
  - unknown language → still produce file nodes
  - parse error → record failure; do not fail the entire build

## Inputs

### Required inputs

- `repo_root` (Path)
- `index_dir` (Path)

### Optional inputs

- `include_globs`, `exclude_globs`, `max_file_bytes`
  - If not provided, load from persisted repo policy (see below).
- `changed_paths` (set of repo-relative paths)
  - For incremental trace rebuild (Phase03 watcher).

### Persisted repo policy

The build should prefer a persisted config snapshot (diffable, audit-friendly):

- `<index_dir>/repo_policy.json`

The trace build can reuse:

- `include_globs` / `exclude_globs`
- detected languages
- path-role classification (docs/code/tests)

## Outputs

Trace files live alongside the embedding index under the project’s `index_dir`:

- `trace_manifest.json`
- `trace_nodes.jsonl`
- `trace_edges.jsonl`

### Deterministic serialization

- JSON objects must be serialized with **stable key ordering**.
- JSONL line order must be stable (see “Ordering and determinism”).
- Paths are **repo-relative** with `/` separators.

## Node/edge kinds (MVP)

### Nodes

- `file`
- `symbol`
- `external_module` (optional)

### Edges

- `contains` (file → symbol)
- `imports` (file → file or file → external_module)

## Stable ID strategy (deterministic + diff-friendly)

IDs should be stable when the entity identity is stable.

### Files

- Stable key: `file:{file_path}`
- Notes:
  - renames create new IDs
  - file_path must be repo-relative

### Symbols

- Stable key: `sym:{qualname}@{file_path}:{start_line}`
- Notes:
  - `start_line` is a practical disambiguator
  - it is acceptable for IDs to change if a symbol moves significantly

### External modules

- Stable key: `ext:{module_name}`

### Edges

- Stable key: `edge:{kind}:{source}:{target}:{disambiguator}`
  - for `contains`: disambiguator can be empty
  - for `imports`: disambiguator should include a normalized import string

## Ordering and determinism

The trace build must be independent of filesystem enumeration order.

### File enumeration

- Expand include globs
- De-duplicate
- Sort by repo-relative POSIX path

### Node ordering (write order)

- File nodes: sorted by `file_path`
- Symbol nodes: sorted by `(file_path, start_line, name)`
- External module nodes: sorted by `name`

### Edge ordering

- Sort by `(kind, source, target, id)`

## Multi-language strategy (robust-by-default)

The trace builder should be pluggable by language.

### Draft support matrix

- Python (`.py`)
  - **Analyzer:** `ast` (stdlib)
  - **Extract:** functions, classes, methods, imports
  - **Resolve imports:** best-effort to repo files
- TypeScript/JavaScript (`.ts/.tsx/.js/.jsx`)
  - **Analyzer:** optional tree-sitter later
  - **MVP fallback:** file nodes only (optional: regex-based import edges)
- Go/Rust/Java/C/C++
  - **MVP:** file nodes only

This keeps the trace build useful on *any* repo, even before deep parsers exist.

## Python analyzer (MVP) details

### Symbol extraction

- Module-level:
  - `function`
  - `class`
- Class body:
  - `method` (`def` / `async def`)

Metadata recommendations:

- `symbol_kind`: `function|async_function|class|method|async_method`
- `qualname`
- `decorators` (best-effort)
- `docstring` (truncated; deterministic)

### Import extraction

Parse:

- `import x`
- `import x as y`
- `from x import y`
- `from .x import y`
- `from . import y`

### Import resolution

Deterministic best-effort (no environment imports):

- Relative imports resolve within the filesystem rooted at `repo_root`.
- Absolute imports attempt to resolve to repo files using:
  - `{mod}.py`
  - `{mod}/__init__.py`

If resolution fails:

- Option A: create `external_module` node (preferred for trace completeness)
- Option B: omit unresolved edges (preferred if noise is too high)

## File filtering edge cases (robustness)

The builder must consistently handle:

- **Symlinks:** skip symlinked files to avoid cycles and non-deterministic resolution.
- **Large files:** skip if `size_bytes > max_file_bytes`.
- **Binary / encoding:** read as UTF-8 with `errors="ignore"` (deterministic).
- **Glob overlap:** de-duplicate paths.

## Failure handling (must not crash whole build)

Per-file errors must not fail the entire build.

Manifest must include:

- `files_parsed`
- `files_failed`
- `last_error` (nullable)

Additionally (recommended):

- `file_errors` (bounded list; e.g. first 50 failures)
  - `{file_path, error_type, message}`

## Post-build validation (triple-check invariants)

Before writing final outputs:

- Node IDs are unique
- Edge IDs are unique
- All edges refer to existing nodes
- All `file_path` values are repo-relative (no absolute paths)

If validation fails:

- Fail the trace build (do not write partial outputs)
- Record `last_error`

## Atomic write

To avoid partially-written trace indexes:

- Write outputs to temp files in `index_dir`
- fsync/close
- rename into place

## Incremental rebuild (Phase03 integration)

Incremental trace rebuild should reuse unchanged file results.

Requirements:

- Store per-file hash in trace metadata (either in manifest or a sidecar index).
- When `changed_paths` is provided:
  - re-parse only changed files
  - reuse nodes/edges for unchanged files

Fallback:

- if prior trace missing or manifest incompatible → full rebuild

## Bounded complexity knobs (safety)

Hard caps to prevent runaway behavior:

- `max_files` scanned for trace
- `max_nodes` / `max_edges`
- `max_failures` recorded in manifest

## Test strategy (do not run now)

Planned checks:

- Build trace for a small fixture repo
- Validate invariants:
  - IDs unique
  - edges reference existing nodes
  - counts match manifest
- “Golden file” regression:
  - compare output JSONL to expected fixtures (ignoring `built_at`)

A script will exist to run these later.
