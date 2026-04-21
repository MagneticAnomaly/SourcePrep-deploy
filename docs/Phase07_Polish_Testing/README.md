# Phase 07 — Polish & Testing
 
## Problem statement
CoDRAG’s value is tightly coupled to reliability. Builds must fail gracefully, indexes must not corrupt easily, and performance must remain acceptable as projects scale. This phase formalizes the stability baseline required for MVP.

## Goal
Stabilize: reliability, performance, testing, and documentation completeness.

## Scope
### In scope
- Test suite definition and implementation plan (unit + integration + smoke)
- Performance targets and measurement approach
- Error handling and recovery behaviors
- Troubleshooting docs and operational guidance

### Out of scope
- New major features (trace expansion, enterprise RBAC, etc.)

## Derived from
- `docs/ROADMAP.md`

## Deliverables
- Robust error handling and recovery
- Integration tests and smoke tests
- Performance improvements (lazy load, caching, batching)
- Troubleshooting docs

## Functional specification

### Reliability baseline

CoDRAG should be “boringly reliable” for the core loop:

- Add project → build → search → context

Reliability requirements:
- Search/context requests must continue to work while a build is running (on the last successful index snapshot).
- Builds must be atomic (never expose a partially-written index as “active”).
- The daemon must not crash on:
  - a single bad file
  - a single embedding request failure
  - a transient Ollama outage

### Error taxonomy and user-actionable messaging

CoDRAG errors must be:
- consistent (stable `error.code`)
- actionable (a clear next step)
- non-leaky (no sensitive paths in remote mode)

Minimum error categories:
- **Configuration errors**: invalid paths, invalid globs, missing project
- **Dependency errors**: Ollama unavailable, model not present, compression service unavailable
- **IO errors**: permission denied, disk full, file too large
- **Build errors**: build failed, build already running, corrupted index detected
- **Internal errors**: unexpected exceptions

UI expectations:
- Show a short summary + a “Details” disclosure with:
  - error code
  - error message
  - hint (recommended fix)

CLI expectations:
- Print a concise message + exit non-zero.
- Provide a `--verbose` option (or environment variable) to include traceback/log context.

### Build recovery behaviors

Interrupted builds:
- If CoDRAG detects partial build output on startup or build completion:
  - mark project status as “recovery needed”
  - next build forces a full rebuild (or performs deterministic repair)

Index corruption:
- If `manifest.json` and `documents.json` disagree (counts/ids), treat the index as invalid.
- Do not attempt “best effort search” on a corrupted index.
- Provide a single recommended action: “Full rebuild”.

Disk pressure:
- If disk space is insufficient to complete a build:
  - fail the build early (before writing large files)
  - surface `DISK_FULL` / `INSUFFICIENT_SPACE`.

### Observability and troubleshooting (local-first)

CoDRAG should support debugging without requiring external telemetry.

Logging requirements:
- Per-project build logs (rotated).
- A single global daemon log.
- Logs should include:
  - build start/end + duration
  - counts (files, chunks, embeddings)
  - dependency connectivity checks (Ollama)
  - key errors with stable error codes

Troubleshooting artifacts:
- A “Copy diagnostics” button in the dashboard that copies:
  - CoDRAG version
  - OS and Python version
  - current project id/name/mode
  - last build status + last error code
  - LLM connectivity status

### Test strategy (what exists and what is enforced)

Minimum suites:

- Unit tests
  - chunking and stable chunk id rules
  - manifest read/write
  - vector store load/save
  - trace node/edge serialization

- Integration tests (Python)
  - add project → build → search → context
  - rebuild incremental does not re-embed unchanged files
  - trace enabled build produces trace files

- Dashboard E2E smoke
  - add project → build → search → open chunk → context

Ollama-dependent tests:
- Prefer a test double for embedding calls.
- If running real Ollama in CI is not feasible, mark those as optional “local integration” tests.

Fixture strategy:
- Maintain a small fixture repo under `tests/fixtures/` (or generated on demand) containing:
  - a few Python files
  - a few Markdown files
  - known symbol names for trace search

### CI expectations

MVP CI baseline:
- Lint/typecheck
- Unit + integration tests

Platform matrix:
- At minimum: Linux + macOS.
- Add Windows before Phase 08 packaging.

### Performance benchmarking

Performance work must be measurable.

Benchmarks to track:
- Build throughput (files/s, chunks/s)
- Embedding throughput (chunks/min)
- Search latency (cold/hot)
- Context assembly latency

Targets should align with `docs/ARCHITECTURE.md` performance table.

## Success criteria
- Common failure modes are user-actionable (missing Ollama, permission errors, build failures).
- Regressions are caught by automated tests.
- Performance targets are documented and validated on representative repos.

## Research deliverables
- Test plan (what we test, where the fixtures live, what is CI vs local)
- Performance envelope (repo sizes, vector counts, cold vs hot search)
- Reliability checklist (what “stable enough for MVP” means)

## Dependencies
- Phase 01–05 feature surface is sufficiently stable to test

## Open questions
- Minimum CI matrix (macOS/windows/linux) vs local-only for early phases
- How to test Ollama-dependent flows reliably (mocks vs local runtime)

## Risks
- Under-testing leads to fragile MVP and churn
- Over-testing too early slows iteration

## Testing / evaluation plan
- Integration tests: add project → build → search → context
- Negative tests: missing Ollama, invalid project path, permission denied
- Load test: large repo indexing and search latency checks

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 07 gates)
