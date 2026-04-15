# 02 — Target Layout

The target layout for the project index directory after Phase A. Applies identically in embedded mode (`<project_root>/.codrag/`), standalone mode (`~/.local/share/codrag/projects/<id>/`), and custom mode (`project.config["index_path"]`).

## The tree

```
<project_index_dir>/
├── version                              # NEW — layout schema version (single integer line)
├── project.json                         # identity pointer (kept at root)
├── repo_policy.json                     # canonical policy (kept at root; index/repo_policy.json deleted in Phase B)
│
├── runtime/                             # NEW — operational state, locks, markers
│   ├── pipeline_state.json
│   ├── clean_shutdown.flag              # was .pipeline_clean_shutdown
│   └── reset_barrier.flag               # was .reset_barrier
│
├── plans/                               # NEW
│   ├── goalposts.json
│   └── roadmap.json
│
├── agents/                              # NEW
│   └── hr_roster.json                   # mode 0600 preserved
│
├── index/                               # search index (existing subdir; no internal rename)
│   ├── documents.json
│   ├── embeddings.npy
│   ├── manifest.json
│   └── fts.sqlite3
│
├── knowledge/                           # NEW — peeled out of root and out of INDEX_FILES
│   ├── documents.json
│   ├── embeddings.npy
│   └── manifest.json
│
├── trace/                               # NEW — collects all trace_* artifacts
│   ├── nodes.jsonl
│   ├── edges.jsonl
│   ├── manifest.json
│   ├── augmented.jsonl
│   ├── augment_manifest.json
│   ├── inferred_edges.jsonl
│   ├── inferred_manifest.json
│   ├── inferred_hashes.json
│   ├── epistemic.jsonl
│   ├── epistemic_manifest.json
│   ├── modules.jsonl
│   ├── modules_manifest.json
│   ├── group_reasoning.jsonl
│   ├── group_reasoning_manifest.json
│   ├── cluster_swarm_synthesis.json
│   ├── swarm_synthesis.json             # was trace_swarm_synthesis.json
│   ├── deepening_manifest.json
│   ├── deep_knowledge_manifest.json
│   └── validation_manifest.json
│
├── atlas/                               # NEW — peeled out of root + atlas_segments/ + atlas_roles/
│   ├── current.json                     # was atlas.json
│   ├── previous.json                    # was atlas_prev.json
│   ├── manifest.json                    # was atlas_manifest.json
│   ├── segments_manifest.json
│   ├── routing.json
│   ├── routing_embeddings.npy
│   ├── updated.signal                   # was atlas_updated.signal
│   ├── swarm_synthesis.json             # was atlas_swarm_synthesis.json
│   ├── segments/                        # was atlas_segments/
│   └── roles/                           # was atlas_roles/
│
├── stages/                              # NEW — manifests for stages whose data lives in SQLite
│   ├── pipeline_run_metadata.json
│   ├── rules_manifest.json
│   ├── concepts_manifest.json
│   └── antibodies_manifest.json
│
├── architecture/                        # existing (no change)
│   └── graph_state.json
│
├── audit/                               # existing (gains manifest.json)
│   ├── manifest.json                    # was audit_manifest.json at root
│   └── spaghetti.json
│
├── git_evidence/                        # existing (no change)
│   ├── churn_60.json
│   └── signature_60.json
│
├── logs/                                # existing (no change)
│   ├── pipeline_<ts>.log
│   └── mcp-stdio.log
│
├── snapshots/                           # NEW — collects checkpoint + branch snapshot subdirs
│   ├── checkpoints/                     # was .checkpoints/
│   │   ├── _golden/
│   │   └── run-<id>/
│   └── branches/                        # was .branch_snapshots/
│       └── _branch_state.json
│
└── backups/                             # existing (no change)
    └── enrichment_reset_<ts>/
```

## Per-bucket rationale

### Root level — only identity, policy, and the version marker

Three files survive at the root: `version` (schema version), `project.json` (identity pointer used by registry/recovery), and `repo_policy.json` (the file used by the walker before any subdir even exists). Everything else moves into a bucket. The principle: a `ls` of the root tells you what kind of project this is, not what's been computed about it.

### `runtime/` — mutable operational state

Pipeline state, recovery markers, locks. Things that are written/rewritten constantly during normal operation and are about *the running daemon*, not *the indexed project*. Renaming the dotfiles (`.pipeline_clean_shutdown` → `clean_shutdown.flag`) makes them visible — easier to debug, no functional change.

### `plans/` — user-authored or AI-curated planning artifacts

`goalposts.json` and `roadmap.json` are not built by the indexer; they're authored. Grouping them signals "edit-friendly content lives here."

### `agents/` — agent state (HR roster and friends)

Today only `hr_roster.json`. Future agent state (paperclip mappings, agent-specific caches) goes here. Mode 0600 must be preserved by the migrator.

### `index/` — search index (untouched internally)

Already a subdir, already well-structured. Internal filenames stay the same. Only `index/repo_policy.json` is removed (Phase B) once confirmed unused.

### `knowledge/` — knowledge index (mirrors `index/`)

Pulls the three `knowledge_*` files out of the root and out of `INDEX_FILES`. Internal names mirror `index/`'s convention (`documents.json`, `embeddings.npy`, `manifest.json`) — the same shape because they're the same kind of thing (a chunked-and-embedded document store), just over a different corpus.

### `trace/` — all trace stage outputs and manifests

The biggest collection. ~18 files. Flat under `trace/` rather than sub-bucketed by stage because (a) the count is manageable, (b) the sub-bucketing would split related files unhelpfully (an inferred-edges manifest belongs next to the inferred edges, not in a `manifests/` orphanage). Filenames drop the `trace_` prefix; the parent dir already disambiguates.

`validation_manifest.json` lives here because it validates trace data. `cluster_swarm_synthesis.json` and `swarm_synthesis.json` live here because they're trace-stage synthesis products.

### `atlas/` — codebase atlas, separate from trace

Atlas is a higher-level synthesis product over the trace, with its own subdirs (`segments/`, `roles/`) and its own update signal. It deserves separation. Renames clean up the prefixes:

- `atlas.json` → `current.json` (the active atlas)
- `atlas_prev.json` → `previous.json` (the previous atlas, used for diffs)
- `atlas_swarm_synthesis.json` → `swarm_synthesis.json`
- `atlas_updated.signal` → `updated.signal` (the watch signal)

### `stages/` — manifests for SQLite-backed stages

`rules_manifest.json`, `concepts_manifest.json`, `antibodies_manifest.json` describe stages whose primary output is rows in `codrag_data/*.db`, not files. The manifests are the only on-disk artifact. They have nowhere else natural to live, so they get a slim shared home.

`pipeline_run_metadata.json` is the "which run last completed" record. It's run-level metadata, not stage-specific, but it shares the trait of being a thin synthesis record — it goes here too.

`audit_manifest.json` does NOT go here — it goes inside `audit/` because `audit/` already exists and the manifest belongs next to its data (`spaghetti.json` and future findings).

### `architecture/`, `audit/`, `git_evidence/`, `logs/`, `backups/` — keep

These are already organized correctly. The only changes:
- `audit/` gains `manifest.json` (moved from root).
- The destroy function gets `architecture/` added to its rmtree list (closing the existing latent-bug gap noted in 00_PROBLEM.md S6).

### `snapshots/` — collected snapshot dirs

Both `.checkpoints/` and `.branch_snapshots/` are *snapshot mechanisms* — checkpoints of pipeline run state, snapshots of prior branch builds. Same family. Collecting them under `snapshots/` (and dropping the dot prefixes) makes the relationship visible. Dotfiles were used to hide them in `ls`; under a non-dotted parent we don't need that.

## Naming conventions adopted

These are the conventions the new layout follows. Future additions should follow the same conventions.

1. **Folders are plural nouns** when they hold a collection (`logs/`, `backups/`, `snapshots/`, `plans/`), singular when they hold one logical thing (`index/`, `knowledge/`, `trace/`, `atlas/`, `architecture/`, `audit/`, `runtime/`).
2. **Filenames inside a bucket do not repeat the bucket name.** `trace/nodes.jsonl`, not `trace/trace_nodes.jsonl`. `atlas/current.json`, not `atlas/atlas_current.json`.
3. **Manifests live next to their data.** `audit/manifest.json` lives in `audit/` because `audit/` is its data dir. The exception is `stages/`, which exists *because* those manifests have no data dir of their own (data is in SQLite).
4. **Operational marker files use `.flag` extension**, not a leading dot. (`runtime/clean_shutdown.flag`, `runtime/reset_barrier.flag`.) Visible, greppable, conventionally typed.
5. **Run-scoped data uses `<dir>/<run_id>/` subdirs** (already in use for `.checkpoints/run-<id>/` and `backups/enrichment_reset_<ts>/`). Continue this pattern.
6. **Dotted filenames at the root are reserved for the version marker only.** The schema version (`version`) is not dotted but lives at the root because it predates everything else. No new dotfiles.

## Comparison: before vs. after

| Concern | Before | After |
|---|---|---|
| Root-level entries | ~30 | 3 (`version`, `project.json`, `repo_policy.json`) + 13 subdirs |
| Where do `trace_*` live? | At root, prefixed | `trace/` |
| Where do `knowledge_*` live? | At root, prefixed | `knowledge/` |
| Where are `atlas_*`? | At root + `atlas_segments/` + `atlas_roles/` | All under `atlas/` |
| Snapshot dirs | `.checkpoints/` + `.branch_snapshots/` (dotted) | `snapshots/checkpoints/` + `snapshots/branches/` |
| Marker files | `.pipeline_clean_shutdown`, `.reset_barrier` | `runtime/clean_shutdown.flag`, `runtime/reset_barrier.flag` |
| `pipeline_state.json` | At root | `runtime/pipeline_state.json` |
| `goalposts`/`roadmap` | At root | `plans/` |
| `hr_roster.json` | At root | `agents/hr_roster.json` |
| Schema version | None | `version` (file at root) |
| Empty `.db` stubs | 2 at root | gone (deferred to Phase B) |
| Duplicate `repo_policy.json` | 2 (root + index/) | 1 (root); index/ copy gone (deferred to Phase B) |

## What stays *exactly* the same

To keep the blast radius small, these aspects are unchanged:

- The `project_index_dir(project)` resolver function and its three modes.
- `.gitignore` rule (`/.codrag/`) — still covers the whole tree.
- Internal file formats — no schema changes, no JSONL → JSON conversions.
- Permissions — `hr_roster.json` keeps 0600.
- Subdir contents inside `index/`, `audit/`, `git_evidence/`, `logs/`, `backups/`, `architecture/`.
- The atomic temp-swap write pattern used by `hr_roster.json` and others.
- The watcher behavior (still triggered by file changes; just at new paths).
