# Repo Discovery & Retrieval Policy (Prep)

Prep should work on unknown repositories without assuming any particular folder structure (e.g. “Phase docs”).

This document defines a **deterministic repo discovery step** that:

- Identifies likely code/docs/tests roots
- Suggests include/exclude patterns
- Suggests retrieval weighting policies

Optionally, an LLM can be used to *recommend* policy defaults, but the canonical output is always a **validated config** (not generated code).

## Key principle: trace is mostly agnostic

The **structural trace index** (Phase04) can be built without knowing “what is docs vs code”, because it records relationships like:

- file contains symbol
- file imports file/module

That said, classification is still valuable for:

- UX: choosing sensible default roots in a folder tree
- Retrieval quality: weighting code/docs/tests differently depending on query intent
- Traceability: linking plans/requirements/ADRs ↔ code/tests benefits from knowing what artifacts are “spec-ish”

So the right approach is:

- **Trace core:** agnostic graph + stable IDs
- **Discovery layer:** adds *metadata + policy* that improves search/context UX

## Why not generate a custom Python script per repo?

A “generated script” is hard to trust because it is:

- non-deterministic (LLM output changes)
- hard to audit (codegen can embed subtle mistakes)
- hard to incrementally maintain (script changes become another artifact)

Instead, Prep should have a stable engine and generate a **policy/config** per repo:

- reproducible
- diffable
- easy to validate
- safe to apply

## Deterministic discovery pipeline

### P0 — Fast filesystem scan

Input:
- repo root path

Output (examples):
- top-level directories
- file extension counts (limited depth, ignore vendor dirs)
- presence of build/config “marker files”

### P1 — Language + build-system detection

Signals:
- `pyproject.toml`, `requirements.txt` → Python
- `package.json`, `pnpm-lock.yaml`, `yarn.lock` → JS/TS
- `go.mod` → Go
- `Cargo.toml` → Rust
- `pom.xml`, `build.gradle` → Java

This is deterministic and generally sufficient to pick default include globs.

### P2 — Root classification (docs / code / tests / misc)

Use only local heuristics based on path names + detected file types.

Examples:
- docs-ish:
  - `docs/`, `doc/`, `design/`, `specs/`, `architecture/`, `adr/`, `decisions/`, `rfcs/`
- code-ish:
  - `src/`, `lib/`, `app/`, `apps/`, `packages/`, `server/`, `client/`, `ui/`
- tests-ish:
  - `tests/`, `test/`, `__tests__/`

Output is a list of “path roles” with confidence.

### P3 — Index include/exclude globs

Discovery produces suggested defaults such as:

- include globs:
  - docs formats (`**/*.md`, `**/*.rst`)
  - detected code extensions (`**/*.py`, `**/*.ts`, `**/*.tsx`, ...)
  - important config files (`**/pyproject.toml`, `**/package.json`, ...)

- exclude globs:
  - always: `.git/`, `node_modules/`, `__pycache__/`, `.venv/`
  - usually: `dist/`, `build/`, `target/`, `.next/`, `.cache/`

### P4 — Retrieval policy (weights + intent)

There are two types of weighting that matter:

1. **Path-based weighting** (stable)
   - Example: code = 1.0, docs = 0.9, tests = 0.95

2. **Query-intent weighting** (dynamic)
   - Example intents (deterministic regex, no LLM required):
     - `debug`: upweight code/tests
     - `design`: upweight docs/ADRs
     - `usage`: upweight README/docs

The important point is that weighting is **advisory**, not a correctness requirement.

### P5 — Persist policy snapshot

Once accepted, store a snapshot of the policy used for builds, so results are reproducible.

- Store under `.runprep/` (embedded mode) or index_dir (standalone mode)
- Include it in trace and embedding manifests

## Optional LLM assistance (recommended shape)

An optional “discovery LLM call” can be useful, but only if it is:

- small-input (folder tree summary + detected markers)
- output-only config (strict JSON)
- validated against a schema
- never required for correctness

LLM can help with:

- repos that have unusual naming
- deciding which of multiple code roots is primary
- suggesting path weights for a specific user goal

LLM should not:

- generate executable code
- expand scope to “read the whole repo”

## Proposed output shape (example)

```json
{
  "repo_root": "/path/to/repo",
  "detected": {
    "languages": ["python", "typescript"],
    "marker_files": ["pyproject.toml", "package.json"]
  },
  "paths": [
    {"glob": "src/**", "role": "code", "confidence": 0.9},
    {"glob": "docs/**", "role": "docs", "confidence": 0.9},
    {"glob": "tests/**", "role": "tests", "confidence": 0.9}
  ],
  "index": {
    "include_globs": ["**/*.md", "**/*.py", "**/*.ts", "**/*.tsx"],
    "exclude_globs": ["**/.git/**", "**/node_modules/**"]
  },
  "retrieval": {
    "path_role_weights": {"code": 1.0, "docs": 0.9, "tests": 0.95},
    "intent_overrides": {
      "design": {"docs": 1.0, "code": 0.9},
      "debug": {"code": 1.0, "tests": 0.95}
    }
  }
}
```
