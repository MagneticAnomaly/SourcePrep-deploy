# Opportunities — Phase 02 (Dashboard)

## Purpose
Capture UX and settings opportunities that increase trust and reduce operational friction.

## Opportunities
- **Freshness UX**: surface *why* a project is stale (changed paths count, last event time, last successful build), not just “stale”.
- **Settings presets**: “Laptop”, “Workstation”, “Monorepo” profiles controlling debounce, concurrency, polling fallback, and embedding batch sizing.
- **Failure playbooks**: show actionable remediation (exclude problematic file, reduce batch size, restart provider) instead of generic errors.

## Opportunities (dashboard tools + settings)
- **“Why is it wrong?” mode**: a single consolidated debug panel that answers:
  - what project is selected (id + path)
  - index freshness (last build, last file event)
  - whether search is operating on the last known-good snapshot
  - what settings are active (include/exclude, max file size, model)
- **Provider connectivity tests**: add explicit “Test Ollama” button that returns a clear pass/fail + hint. (Added to TODOs: P02-I4a, 2026-02-01)
- **Index coverage explorer**: show a bounded table of:
  - included file counts by extension
  - top excluded patterns that matched
  - skipped reasons (too large, parse timeout, binary)
- **Settings diff + audit**: for each project, show “current config” vs “default” and (later) vs “team policy”, so users can understand why results differ across machines.
- **Context controls as UX**: present `k`, `max_chars`, `min_score` as a “budget” UI (presets + advanced overrides) so users learn how to keep outputs bounded.

## Opportunities (meaningful visualization)
- **Build timeline**: per-build phase timeline (scan → chunk → embed → write) with durations and coarse counts.
- **Freshness / rebuild countdown**: surface `stale/pending/building` state as a compact timeline:
  - last event time
  - next rebuild ETA (when debouncing)
  - last successful build time
- **Index growth + disk usage**: simple charts for total chunks/vectors and index size, to make “why is this slow?” debuggable.
- **Search transparency**: optional histogram of result scores (or top-k score list) behind a “debug” toggle to avoid clutter.

## Hazards
- **Trust failure via ambiguity**: if the UI can’t clearly show “right project / fresh index / verifiable sources”, users will assume results are hallucinated or stale.
- **Polling storms**: aggressive polling can increase CPU/network overhead and still fail to communicate state; prefer adaptive polling and clear UI states.
- **Settings overwhelm**: too many knobs without presets leads to misconfiguration and support burden.
- **Remote-mode leaks**: in future network mode, status/errors must not leak server filesystem paths.
- **Schema drift**: dashboard UI fields must remain aligned with `API.md` and MCP tool outputs to avoid “works in UI but not in IDE” inconsistencies.

## References
- ChunkHound issue #161 (config flexibility)
- ChunkHound issue #176 (batch size sensitivity)
- `docs/Phase02_Dashboard/README.md`
- `docs/Phase03_AutoRebuild/README.md`
- `docs/API.md`
- `docs/WORKFLOW_RESEARCH.md`
