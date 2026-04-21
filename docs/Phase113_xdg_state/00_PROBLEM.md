# Phase 113 — XDG State Consolidation

## Problem

CoDRAG's daemon-wide state (SQLite stores, UI config, active-project
signals, audit log) is currently split across **two** locations that
neither the code nor the user chose consciously:

1. `./codrag_data/` — **CWD-relative**. Resolves to the repo root when
   the daemon is launched with no `--index-dir` flag from the repo root
   (which is how most dev sessions start). On a user's machine, it
   resolves to wherever they happened to `cd` before running
   `codrag serve`.
2. `~/.local/share/prep/` — the proper XDG-style per-user data dir
   (`project_registry.codrag_data_dir()` returns this).

Both exist on disk today. Both have active, non-stale data. Neither is
a mirror of the other — they contain **disjoint** subsets of stores,
and one store (`codrag_settings.db`) has a live copy in each, with no
code path keeping them in sync.

### Observed fragmentation (dev machine, 2026-04-17)

| Store | `./codrag_data/` | `~/.local/share/prep/` | Authoritative |
|---|---|---|---|
| `registry.db` (project registry) | 0 B stale | 280 KB | **XDG** |
| `active_project.json` | — | present | **XDG** |
| `audit_log.db` | — | 32 MB | **XDG** |
| `projects/` (standalone index dirs) | — | present | **XDG** |
| `codrag_antibodies.db` | 80 KB | — | **./codrag_data** |
| `codrag_concepts.db` | 400 KB | — | **./codrag_data** |
| `codrag_observations.db` | 45 KB | — | **./codrag_data** |
| `codrag_pipeline_journal.db` | 40 KB | 0 B stale | **./codrag_data** |
| `codrag_pipeline_history.db` | 57 KB | — | **./codrag_data** |
| `codrag_token_telemetry.db` | 680 KB | — | **./codrag_data** |
| `codrag_settings.db` | 40 KB | 180 KB | **ambiguous — both active** |
| `ui_config.json` | present | — | **./codrag_data** |
| legacy `projects.db`, `registry.db` | 0 B, 32 KB | — | stale — leftovers |
| `codrag_settings.db.corrupt.bak` (2 files, ~40 MB) | present | — | leftover — should be cleaned up |

### How it got this way

- `project_registry.codrag_data_dir()` was written assuming XDG.
- The daemon's `--index-dir` argument was added separately, defaulting
  to `"./codrag_data"` (see `server.py:716, 1091`,
  `services/config_manager.py:232`, `services/build_manager.py:574`).
- Various SQLite stores (`antibody_store`, `concept_store`, journal,
  history, telemetry) were wired up one at a time, each picking a
  path convention independently. Most landed on the daemon
  `index_dir`, a few hit `codrag_data_dir()`.
- `ui_config.json` was committed to the repo at `codrag_data/ui_config.json`.
  This forced the CWD-relative location to be git-tracked and
  turned user runtime state into a source of merge conflicts.

### Why it matters

- **Users can't back up their CoDRAG state** without knowing about both
  directories. A "portable install" or data-dir migration tool would
  ship with the wrong mental model.
- **The daemon silently fragments per launch directory.** Running
  `cd /tmp && codrag serve` creates a *third* `codrag_data/` at
  `/tmp/codrag_data/` with zero user awareness. Stores reset to empty.
  This is the "I rebuilt the whole project and all my concepts
  disappeared" failure mode.
- **Git noise.** The tracked `codrag_data/*.db` files accumulate diffs
  on every commit because the dev's own daemon writes to them. We end
  up either committing user state (bad) or excluding them (we already
  skipped them on the Phase 115 push).
- **Self-ingestion exclude list already confused.** Phase 115 L1
  lists `codrag_data` as a self-ingestion guard, but that only helps
  when the daemon happens to run from a project root. XDG-located
  state is never at risk of being re-ingested — the exclude is a
  symptom of the ambiguity, not a principled default.

### What's in scope

Consolidating **daemon-wide state** — i.e. the stores whose identity
is "the installation of CoDRAG on this machine," not "one specific
project's index."

### What's NOT in scope

- **Embedded mode `.prep/`** — per-project, co-located with the
  user's source tree, intentionally git-trackable. Stays put.
- **Standalone mode project index dirs** (`~/.local/share/prep/projects/<id>/`)
  — already XDG, already correct.
- **The Rust engine's on-disk cache format** — untouched.
- **A user-facing settings UI for relocating the data dir** — future
  work; Phase 113 establishes the single canonical path and leaves
  the override as an env var.

### Success criteria

1. A fresh `codrag serve` (any CWD) writes all daemon-wide state to
   exactly one location: `$CODRAG_DATA_DIR` if set, else
   `~/.local/share/prep/`.
2. No code path references `./codrag_data` as a default.
3. Existing users with data in `./codrag_data/` get a one-time
   migration on daemon startup with a clear log line and no data loss.
4. `ui_config.json` either moves to XDG or — if it must stay
   repo-local for a good reason — is documented and `.gitignore`'d.
5. Phase 115's self-ingestion guard for `codrag_data` becomes
   belt-and-suspenders rather than load-bearing.
6. The git repo stops accumulating diffs in `codrag_data/`.
