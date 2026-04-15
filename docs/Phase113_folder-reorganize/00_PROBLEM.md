# 00 — The Problem

## Current state of `.codrag/`

A snapshot of the codrag index right now (sizes shown for context):

```
.codrag/
├── .branch_snapshots/                    # 1 file inside
├── .checkpoints/                         # _golden + run-<id>/
├── .pipeline_clean_shutdown              # 18 B marker
├── .reset_barrier                        # 36 B marker
├── architecture/graph_state.json
├── atlas_swarm_synthesis.json            # 3 KB
├── audit/spaghetti.json
├── backups/enrichment_reset_<ts>/
├── codrag_settings.db                    # 0 B (empty stub)
├── git_evidence/{churn_60,signature_60}.json
├── goalposts.json                        # 9 KB
├── hr_roster.json                        # 264 KB (mode 0600)
├── index/                                # 5 files (documents, embeddings, fts.sqlite3, manifest, repo_policy)
├── knowledge_documents.json              # 4 MB
├── knowledge_embeddings.npy              # 25 MB
├── knowledge_manifest.json
├── logs/                                 # 8 pipeline_*.log + mcp-stdio.log
├── pipeline_state.json
├── project.json
├── repo_policy.json                      # ALSO at index/repo_policy.json — duplicate
├── roadmap.json                          # 11 KB
├── settings.db                           # 0 B (empty stub, different name from codrag_settings.db)
├── trace_augmented.jsonl                 # 3.4 MB
├── trace_augment_manifest.json
├── trace_edges.jsonl                     # 3.5 MB
├── trace_inferred_edges.jsonl
├── trace_inferred_hashes.json
├── trace_inferred_manifest.json
├── trace_manifest.json                   # 193 KB
├── trace_nodes.jsonl                     # 3.1 MB
├── trace_swarm_synthesis.json
└── validation_manifest.json
```

This is what's on disk *today*. `TRACE_FILES` in code (see [01_PATH_INVENTORY.md](01_PATH_INVENTORY.md)) enumerates many more — `trace_epistemic.jsonl`, `trace_modules.jsonl`, `trace_group_reasoning.jsonl`, `atlas.json`, `atlas_routing.json`, `atlas_routing_embeddings.npy`, finalize-stage manifests, etc. — that this dogfood index hasn't materialized because some stages haven't been run. The total surface area is bigger than the snapshot suggests.

## Smells, bugs, and design debt

### S1 — Root-level clutter

~30 entries at the top level of `.codrag/`, mixing:

- Identity (`project.json`)
- Configuration (`repo_policy.json`)
- Pipeline state (`pipeline_state.json`)
- Marker files (`.pipeline_clean_shutdown`, `.reset_barrier`)
- Knowledge artifacts (`knowledge_documents.json`, `knowledge_embeddings.npy`, `knowledge_manifest.json`)
- Trace artifacts (8+ `trace_*` files)
- Atlas/synthesis artifacts (`atlas_swarm_synthesis.json`, `trace_swarm_synthesis.json`, `validation_manifest.json`)
- Plans (`goalposts.json`, `roadmap.json`)
- Agent state (`hr_roster.json`)
- Empty database stubs (`codrag_settings.db`, `settings.db`)

A future contributor can't tell from a top-level `ls` what these things are or how they relate. There's no convention being followed; files have accreted as features were added.

### S2 — Duplicates

- `repo_policy.json` lives both at `.codrag/repo_policy.json` (canonical, written by `repo_policy.write_repo_policy()`) and `.codrag/index/repo_policy.json` (referenced in `INDEX_FILES`). Only one is the source of truth.
- `codrag_settings.db` and `settings.db` — two empty SQLite files at root, both 0 bytes, both stubs. No active writers. Likely leftovers from a refactor.

### S3 — Ad-hoc marker files

`.pipeline_clean_shutdown` and `.reset_barrier` are dotfiles at root. They have a real purpose (recovery state) but the convention "important runtime state goes in a hidden file at the project-data root" is invisible and unfamiliar. New code wanting to add a similar marker has no guidance — does it use a dotfile? A folder? A SQLite row? — and we'll keep accreting one-offs.

### S4 — No centralized path resolution for individual files

Path mapping found:

- **`.codrag/` root resolution is centralized** via `project_index_dir(project)` in `core/project_registry.py:44`. Good.
- **Individual file paths are NOT.** Some have per-domain constants (`GOALPOSTS_FILENAME`, `ROADMAP_FILENAME`, `_ROSTER_FILENAME`, `_CLEAN_SHUTDOWN_FILENAME`, `_RESET_BARRIER_FILENAME`, `_POINTER_FILENAME`). Others are scattered string literals — `pipeline_state.json` appears as a literal at `pipeline/orchestrator.py:173,194` with no constant.
- **Trace files are the worst case.** ~40 call sites construct `idx_dir / "trace_nodes.jsonl"` and similar by hand. The only centralization is `TRACE_FILES`, a flat list of basenames used by the destroy/finalize routines — not by the writers themselves.
- **Subdir names are uncentralized.** `.checkpoints`, `.branch_snapshots`, `backups`, `logs`, `audit`, `git_evidence`, `architecture` are hardcoded everywhere they're used and again hardcoded in the destroy function.

This makes any rename a multi-file grep/replace, and worse, makes it easy to miss one (silent regression that surfaces only when that codepath runs).

### S5 — `INDEX_FILES` constant looks wrong (latent bug, must be verified)

`api/routers/trace_routes/shared.py:63-71`:

```python
INDEX_FILES = [
    "documents.json",
    "embeddings.npy",
    "manifest.json",
    "fts.sqlite3",
    "knowledge_documents.json",
    "knowledge_embeddings.npy",
    "knowledge_manifest.json",
]
```

But on disk, `documents.json`/`embeddings.npy`/`manifest.json`/`fts.sqlite3` live at `.codrag/index/documents.json` etc., not at `.codrag/documents.json`. The destroy function does `fp = idx_dir / fname` (i.e., `.codrag/documents.json`) and would silently no-op on these.

Either:
- (a) `CodeIndex.index_dir` actually points at `.codrag/index/`, and `INDEX_FILES` is correctly basename-only and is meant to be used relative to a subdir that the destroy function isn't applying — i.e., the destroy function is broken;
- (b) `CodeIndex.index_dir` points at `.codrag/` and `INDEX_FILES` is correct, and the disk presence of `.codrag/index/` is from a different code path (older builder writing to a subdir that's now ignored?);
- (c) Both code paths exist and are racing.

This must be confirmed in code before we design the migration. Whichever way it resolves, the centralization step kills the ambiguity.

### S6 — Destroy function omits `architecture/`

`enrichment.py:1175-1178` enumerates subdirs to nuke:

```python
for subdir_name in [
    ".checkpoints", ".branch_snapshots", "backups", "logs",
    "atlas_segments", "atlas_roles", "audit", "git_evidence",
]:
```

`architecture/` is missing. The graph state file would survive a "full reset". Either it's not load-bearing (and shouldn't exist), or it is and reset is broken. Investigation TBD; fix during centralization.

### S7 — Inconsistent prefix conventions

- `trace_*` everywhere at root (8 files)
- `knowledge_*` at root (3 files)
- `atlas_*` in some places, plain in others (`atlas.json`, `atlas_prev.json`, `atlas_routing.json`)
- `hr_roster.json` (no prefix even though it's HR-only)
- `goalposts.json`, `roadmap.json` (no prefix)

When everything sits at the root, prefixes are the only grouping mechanism — but they're applied unevenly. Bucketing into folders makes prefixes redundant and we can drop them (`trace/nodes.jsonl` rather than `trace_nodes.jsonl`).

### S8 — No schema version

There's no marker file that says "this `.codrag/` was written by daemon version X with layout version Y." Adding one now (a `version` file containing an integer) costs nothing and makes every future migration possible. Without it, future migrations must heuristically detect the layout — fragile.

## What is NOT a problem

- **`project_index_dir()` itself.** The single resolver for the `.codrag/` root is correct and centralized. We do not change it.
- **Embedded vs. standalone mode.** Both modes share the same internal layout. Whatever we do here applies to both transparently.
- **Gitignore.** `.codrag/` is fully ignored (`/.gitignore:78`). Nothing we do changes git status.
- **Subdir contents that are already well-organized.** `audit/`, `architecture/`, `git_evidence/`, `logs/`, `backups/`, `index/` are fine internally; they just need siblings.

## Why now

- We just shipped Phase 105 (git evidence) which added another root-level subdir and another scattered-literal pattern. The next added artifact will make this worse.
- F-78 (full reset gaps) and F-66/67/68/75 (pipeline resume gaps) both surfaced because reset/resume code didn't know about all the things on disk. Centralization fixes the *class* of bug.
- We're moving toward Phase B work (knowledge layer, retrieval intelligence) that will add more index artifacts. Better to have a place for them.
