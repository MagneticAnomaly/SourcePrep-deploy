# Phase 113 — `.codrag/` Folder Reorganization

**Status:** Drafting (design phase, no code yet)
**Owner:** Eric
**Drafted:** 2026-04-15
**Last updated:** 2026-04-15

## TL;DR

The per-project index directory (`.codrag/` in embedded mode, `~/.local/share/codrag/projects/<id>/` in standalone mode) has accumulated 30+ artifacts at the top level with mixed concerns, ad-hoc marker files, duplicates, and no centralized path resolution for individual files. We are going to fix this in two phases:

- **Phase A (this phase, no semantic change):** Restructure the layout into named buckets — `runtime/`, `index/`, `knowledge/`, `trace/`, `atlas/`, `stages/`, `plans/`, `agents/`, `snapshots/`, plus the existing `architecture/`, `audit/`, `git_evidence/`, `logs/`, `backups/`. Filenames inside buckets are renamed to drop now-redundant prefixes (`trace/nodes.jsonl` instead of `trace_nodes.jsonl`). Old layouts are migrated forward in one shot on daemon startup.
- **Phase B (deferred):** Delete the obvious dead/duplicate files (the two empty `*.db` stubs at root, the legacy `index/repo_policy.json` duplicate, anything else that proves orphaned during Phase A).

The refactor itself is staged so that the layout change is the **last** step, not the first. Step 0 (centralize all path construction into a `project_paths` module) ships first and is independently valuable even if we never reorganize. The actual move is a one-file change to the bodies of those accessors plus a one-shot migrator.

## Why this matters

- **Discoverability:** A new contributor opening `.codrag/` should be able to tell what each thing is from where it lives. Today they see 30 loose files and a few cryptic dotfiles.
- **Reset correctness:** `index_destroy_project()` (the full-wipe RPC) currently enumerates files and dirs by hand. We've already had two regressions where reset missed something (F-78: missed Finalize manifests + most SQLite stores; missed `architecture/` still). Centralized accessors close the loop.
- **Future Phase B (dedupe):** Cannot safely delete duplicates without first knowing every reader/writer. The Phase A.0 centralization makes Phase B a 30-line PR.
- **Future Phase C (versioned schema):** A `version` marker plus a `project_paths.layout_version` constant makes every later migration trivial.

## Document map

| File | Purpose |
|---|---|
| [00_PROBLEM.md](00_PROBLEM.md) | Current state of `.codrag/`, what's wrong, what's a smell vs. a real bug |
| [01_PATH_INVENTORY.md](01_PATH_INVENTORY.md) | Full enumeration of every artifact + where its path is constructed in code |
| [02_TARGET_LAYOUT.md](02_TARGET_LAYOUT.md) | The proposed new layout with per-bucket rationale |
| [03_STRATEGY.md](03_STRATEGY.md) | Why centralize-then-move, not move-and-grep-replace |
| [04_RISKS.md](04_RISKS.md) | Risks, open questions, latent bugs surfaced during planning |
| [05_PHASE_B_DEDUPE.md](05_PHASE_B_DEDUPE.md) | What we are explicitly deferring and the criteria for taking it on |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Step-by-step plan with checkpoints, PR boundaries, and rollback |

## Out of scope

- Changing the *content* of any file (no schema migrations).
- Reorganizing the SQLite stores under `codrag_data/` (separate concern; tracked elsewhere).
- Renaming `.codrag/` itself or its standalone-mode equivalent.
- Touching the global `~/.local/share/codrag/` files (registry.db, active_project.json, etc.).
- Any change visible to MCP clients or the dashboard API surface.

## Acceptance gates

Phase A is done when:

1. All `.codrag/` paths in source go through `src/codrag/core/project_paths.py`. No remaining string literals like `idx_dir / "trace_nodes.jsonl"` outside that module (verifiable by grep).
2. The new layout is the only one written by fresh runs.
3. The migrator converts an old-layout `.codrag/` to the new layout in one daemon startup, idempotently, with no data loss (verified on a copy of the dogfood index).
4. `index_destroy_project()` enumerates from `project_paths` rather than hardcoded lists; the missing `architecture/` and any other gaps are closed.
5. Full pipeline run from a fresh clone produces a directory tree that matches the documented target layout exactly (verifiable by a snapshot test).
6. All tests pass; dogfood index can be wiped and rebuilt successfully.
