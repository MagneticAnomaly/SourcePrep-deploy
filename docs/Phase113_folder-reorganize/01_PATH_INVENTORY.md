# 01 — Path Inventory

This is the canonical inventory of every artifact written to the project index directory and where its path is constructed in source. It is the input to the centralization step (Step 0 in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)) and to the migrator (Step 4).

For each entry: **path**, **canonical source** (where the path string is defined), **writers**, **readers** (count + representatives), **target bucket** (the new home in [02_TARGET_LAYOUT.md](02_TARGET_LAYOUT.md)), and **migration risk**.

## Resolver: `.prep/` root

| Field | Value |
|---|---|
| Function | `project_index_dir(project: Project) -> Path` |
| Source | `src/codrag/core/project_registry.py:44` |
| Returns | embedded mode: `<project_root>/.codrag` &nbsp;·&nbsp; standalone mode: `~/.local/share/prep/projects/<id>` &nbsp;·&nbsp; custom mode: `project.config["index_path"]` |
| Status | **Already centralized.** Do not change. |
| Risk | n/a |

All paths in this document are expressed relative to whatever `project_index_dir(proj)` returns.

---

## Group 1 — Identity & policy (root level)

### `project.json`

| Field | Value |
|---|---|
| Constant | `_POINTER_FILENAME = "project.json"` |
| Source | `src/codrag/core/project_registry.py:391` |
| Writers | `update_project_pointer()` (`project_registry.py:398-425`) |
| Readers | Project-resolution helpers; few sites |
| Target bucket | **Root** (identity pointer; stays at `project.json`) |
| Risk | LOW — single constant, single writer |

### `repo_policy.json` (root copy)

| Field | Value |
|---|---|
| Constant | `DEFAULT_POLICY_FILENAME = "repo_policy.json"` |
| Helper | `policy_path_for_index(index_dir) -> Path` |
| Source | `src/codrag/core/repo_policy.py:10,12-13` |
| Writers | `write_repo_policy()` (`repo_policy.py:39-42`) |
| Readers | Walker, parser stages |
| Target bucket | **Root** (kept at `repo_policy.json`) |
| Risk | LOW — single constant + helper, single writer |

### `repo_policy.json` (inside `index/`)

| Field | Value |
|---|---|
| Listed in | `INDEX_FILES` (`api/routers/trace_routes/shared.py:63-71`) |
| Writers | None confirmed (suspected stale) |
| Target bucket | **Delete (Phase B)** if confirmed unused |
| Risk | Confirm-before-delete |

---

## Group 2 — Runtime state & markers

### `pipeline_state.json`

| Field | Value |
|---|---|
| Constant | None — scattered literal |
| Source | `src/codrag/services/pipeline/orchestrator.py:173,194` |
| Writers | Orchestrator |
| Readers | Resume/recovery logic |
| Target bucket | **`runtime/pipeline_state.json`** |
| Risk | MEDIUM — no constant exists; literal is in 2+ places |

### `.pipeline_clean_shutdown`

| Field | Value |
|---|---|
| Constant | `_CLEAN_SHUTDOWN_FILENAME = ".pipeline_clean_shutdown"` |
| Source | `src/codrag/services/pipeline/recovery.py:60` |
| Writers | Recovery on clean shutdown |
| Readers | Recovery on startup |
| Target bucket | **`runtime/clean_shutdown.flag`** (rename, drop dot) |
| Risk | LOW |

### `.reset_barrier`

| Field | Value |
|---|---|
| Constant | `_RESET_BARRIER_FILENAME = ".reset_barrier"` |
| Source | `src/codrag/services/pipeline/recovery.py:61` |
| Writers | `reset_barrier_active()` (recovery.py:64-87) |
| Readers | `clear_reset_barrier()` (recovery.py:90-104) |
| Target bucket | **`runtime/reset_barrier.flag`** (rename, drop dot) |
| Risk | LOW |

### `codrag_settings.db`, `settings.db` (both empty)

| Field | Value |
|---|---|
| References | `src/codrag/server.py:687, 758` (suggest legacy / cross-mode mention) |
| Writers | None active |
| Status | Suspected dead |
| Target bucket | **Delete (Phase B)** after confirming truly unused |
| Risk | Confirm-before-delete |

---

## Group 3 — Plans & roadmap

### `goalposts.json`

| Field | Value |
|---|---|
| Constant | `GOALPOSTS_FILENAME = "goalposts.json"` |
| Source | `src/codrag/core/goalposts_models.py:222` |
| Writers | `save_goalposts()` (`goalposts_models.py:237-244`) |
| Readers | Goalpost loaders, dashboard |
| Target bucket | **`plans/goalposts.json`** |
| Risk | LOW |

### `roadmap.json`

| Field | Value |
|---|---|
| Constant | `ROADMAP_FILENAME = "roadmap.json"` |
| Source | `src/codrag/core/goalposts_models.py:463` |
| Writers | `save_roadmap()` (`goalposts_models.py:478-488`) |
| Readers | Roadmap loaders, dashboard |
| Target bucket | **`plans/roadmap.json`** |
| Risk | LOW |

---

## Group 4 — Agents

### `hr_roster.json`

| Field | Value |
|---|---|
| Constant | `_ROSTER_FILENAME = "hr_roster.json"` |
| Source | `src/codrag/agents/hr/roster.py:19` |
| Writers | Atomic temp-swap write at `roster.py:51` |
| Readers | HR roster loaders |
| Permissions | 0600 (sensitive) |
| Target bucket | **`agents/hr_roster.json`** (preserve mode 0600) |
| Risk | LOW — but the migrator must preserve the file mode |

---

## Group 5 — Search index (`index/`)

### `index/documents.json`, `index/embeddings.npy`, `index/manifest.json`, `index/fts.sqlite3`

| Field | Value |
|---|---|
| Constants | Hardcoded in `CodeIndex.__init__` (`src/codrag/core/index.py:134-137`) |
| Writers | `CodeIndex.write_documents()`, `write_embeddings()` |
| Readers | `CodeIndex` load/search |
| Target bucket | **`index/documents.json`**, **`index/embeddings.npy`**, **`index/manifest.json`**, **`index/fts.sqlite3`** (no rename) |
| Risk | LOW — well-contained in `CodeIndex` |
| **Open question** | `INDEX_FILES` constant lists these without an `index/` prefix. Either `CodeIndex.index_dir` already includes the `index/` segment (most likely) and `INDEX_FILES` is a destroy-time bug (paths under wrong directory), or the actual disk layout is being written somewhere else. **Verify in Step 0a before continuing.** |

### `index/repo_policy.json`

| Field | Value |
|---|---|
| Listed in | `INDEX_FILES` |
| Writers | None confirmed |
| Status | Likely stale duplicate of root `repo_policy.json` |
| Target bucket | **Delete (Phase B)** if unused |
| Risk | Confirm-before-delete |

---

## Group 6 — Knowledge index (currently at root, moving to `knowledge/`)

### `knowledge_documents.json` (4 MB)

| Field | Value |
|---|---|
| Source | Hardcoded in `KnowledgeIndex.__init__` (`src/codrag/core/knowledge.py:46`) |
| Writers | `KnowledgeIndex` (knowledge.py) |
| Readers | `KnowledgeIndex`, `api/routers/knowledge.py` |
| Target bucket | **`knowledge/documents.json`** |
| Risk | LOW — contained in `KnowledgeIndex` |

### `knowledge_embeddings.npy` (25 MB)

| Field | Value |
|---|---|
| Source | `KnowledgeIndex.__init__` (`knowledge.py:47`) |
| Writers | `KnowledgeIndex` |
| Readers | `KnowledgeIndex` |
| Target bucket | **`knowledge/embeddings.npy`** |
| Risk | LOW |

### `knowledge_manifest.json`

| Field | Value |
|---|---|
| Source | `KnowledgeIndex.__init__` (`knowledge.py:48`) |
| Writers | `KnowledgeIndex` |
| Readers | `KnowledgeIndex` |
| Target bucket | **`knowledge/manifest.json`** |
| Risk | LOW |
| **Note** | Also referenced in `src/codrag/core/trace/maintenance.py:87-88` for cleanup. Update both. |

---

## Group 7 — Trace artifacts (`trace_*` and friends)

This is the largest and highest-risk group. There is one centralization point — `TRACE_FILES` in `api/routers/trace_routes/shared.py:23-61` — but it is used only by the destroy/finalize routines, not by the writers themselves. Writers construct paths as scattered literals.

### Stage outputs (jsonl/npy)

| Path today | Writer source | Target |
|---|---|---|
| `trace_nodes.jsonl` | `core/trace/builder.py` | `trace/nodes.jsonl` |
| `trace_edges.jsonl` | `core/trace/builder.py` | `trace/edges.jsonl` |
| `trace_augmented.jsonl` | `core/augmenter.py:278` | `trace/augmented.jsonl` |
| `trace_inferred_edges.jsonl` | `core/inferred_edges.py` | `trace/inferred_edges.jsonl` |
| `trace_inferred_hashes.json` | `core/inferred_edges.py` | `trace/inferred_hashes.json` |
| `trace_epistemic.jsonl` | `core/epistemic_enrichment.py` | `trace/epistemic.jsonl` |
| `trace_modules.jsonl` | (modules stage) | `trace/modules.jsonl` |
| `trace_group_reasoning.jsonl` | `core/group_reasoning.py` | `trace/group_reasoning.jsonl` |

### Manifests

| Path today | Target |
|---|---|
| `trace_manifest.json` | `trace/manifest.json` |
| `trace_augment_manifest.json` | `trace/augment_manifest.json` |
| `trace_inferred_manifest.json` | `trace/inferred_manifest.json` |
| `trace_epistemic_manifest.json` | `trace/epistemic_manifest.json` |
| `trace_modules_manifest.json` | `trace/modules_manifest.json` |
| `group_reasoning_manifest.json` | `trace/group_reasoning_manifest.json` |
| `validation_manifest.json` | `trace/validation_manifest.json` |
| `deepening_manifest.json` | `trace/deepening_manifest.json` |
| `deep_knowledge_manifest.json` | `trace/deep_knowledge_manifest.json` |

### Synthesis

| Path today | Target |
|---|---|
| `trace_swarm_synthesis.json` | `trace/swarm_synthesis.json` |
| `trace_cluster_swarm_synthesis.json` | `trace/cluster_swarm_synthesis.json` |

**Risk: HIGH.** ~40 read/write call sites. Strategy 2 (centralize first, then move) exists specifically to defuse this group.

---

## Group 8 — Atlas (currently at root + `atlas_segments/` + `atlas_roles/` subdirs)

### Files

| Path today | Target |
|---|---|
| `atlas.json` | `atlas/current.json` |
| `atlas_prev.json` | `atlas/previous.json` |
| `atlas_manifest.json` | `atlas/manifest.json` |
| `atlas_segments_manifest.json` | `atlas/segments_manifest.json` |
| `atlas_routing.json` | `atlas/routing.json` |
| `atlas_routing_embeddings.npy` | `atlas/routing_embeddings.npy` |
| `atlas_updated.signal` | `atlas/updated.signal` |
| `atlas_swarm_synthesis.json` | `atlas/swarm_synthesis.json` |

### Subdirs

| Path today | Target |
|---|---|
| `atlas_segments/` | `atlas/segments/` |
| `atlas_roles/` | `atlas/roles/` |

| Field | Value |
|---|---|
| Writers | `core/atlas/generator.py:1071` (synthesis); other atlas modules |
| Readers | Atlas consumers, dashboard |
| Risk | MEDIUM — multi-file, several literals, but contained to `core/atlas/` |

---

## Group 9 — Stage manifests (no on-disk siblings)

These are manifests for stages whose primary output is a SQLite store, not a file. They have no neighbors today; we collect them in `stages/`.

| Path today | Target |
|---|---|
| `pipeline_run_metadata.json` | `stages/pipeline_run_metadata.json` |
| `rules_manifest.json` | `stages/rules_manifest.json` |
| `concepts_manifest.json` | `stages/concepts_manifest.json` |
| `antibodies_manifest.json` | `stages/antibodies_manifest.json` |

(Note: `audit_manifest.json` goes inside `audit/` next to `spaghetti.json`, not `stages/`.)

| Field | Value |
|---|---|
| Listed in | `TRACE_FILES` (despite not being trace artifacts — accreted that way) |
| Writers | Each owning stage |
| Risk | MEDIUM — must update writers + the destroy enumeration |

---

## Group 10 — Existing well-organized subdirs (keeping)

### `architecture/`

| Field | Value |
|---|---|
| Writer | `architecture_state.py:25` |
| Files | `graph_state.json` |
| Target | **`architecture/graph_state.json`** (no change) |
| Risk | LOW for path; **but**: the destroy function omits this dir — fix in Step 1 |

### `audit/`

| Field | Value |
|---|---|
| Writers | `core/audit/runner.py`, `core/audit/spaghetti_scorer.py` |
| Files | `spaghetti.json`, future `findings.json`, `audit_manifest.json` (moved in Phase A) |
| Target | **`audit/`** (unchanged; gains `manifest.json`) |
| Risk | LOW |

### `git_evidence/`

| Field | Value |
|---|---|
| Writer | `core/git_evidence.py:280` (disk cache) |
| Path constructor | `git_evidence_service.py:41,53` |
| Files | `churn_60.json`, `signature_60.json` |
| Target | **`git_evidence/`** (no change) |
| Risk | LOW |

### `logs/`

| Field | Value |
|---|---|
| Writer | `services/pipeline_logger.py` |
| Files | `pipeline_<ts>.log`, `mcp-stdio.log` |
| Target | **`logs/`** (no change) |
| Risk | LOW |

### `backups/`

| Field | Value |
|---|---|
| Writers | `services/branch_backup_manager.py`, `_backup_files_if_debug()` (enrichment.py:1154) |
| Subdirs | `enrichment_reset_<ts>/`, etc. |
| Target | **`backups/`** (no change) |
| Risk | LOW |

---

## Group 11 — Snapshot/checkpoint dirs (currently dotfiles)

### `.checkpoints/`

| Field | Value |
|---|---|
| Constructor | `idx_dir / ".checkpoints" / run_id / <file>` (scattered) |
| Writer | `services/pipeline_checkpoint.py` |
| Target | **`snapshots/checkpoints/`** (drop the dot) |
| Risk | MEDIUM — scattered literals |

### `.branch_snapshots/`

| Field | Value |
|---|---|
| Constructor | `idx_dir / ".branch_snapshots" / branch / <file>` |
| Writer | `services/branch_backup_manager.py:226` |
| Target | **`snapshots/branches/`** (drop the dot) |
| Risk | MEDIUM |

---

## Group 12 — Schema version (NEW)

### `version`

| Field | Value |
|---|---|
| Constant | `LAYOUT_VERSION = 2` (new in this phase) |
| Writer | Migrator + bootstrap |
| Readers | Migrator |
| Target | **`version`** (file at root, single integer line) |
| Risk | n/a — purely additive |

`version == 1` represents "old layout" (everything we have today). `version == 2` represents the new layout. The migrator keys off this and writes "2" when done.

---

## Cross-cutting: who needs to change

This is the rough cardinality of the centralization PR (Step 0):

| Module group | Files touched | Sites changed |
|---|---|---|
| `core/trace/*` | 3-5 | ~15 |
| `core/augmenter.py` | 1 | 2 |
| `core/inferred_edges.py` | 1 | 4 |
| `core/epistemic_enrichment.py` | 1 | 2 |
| `core/group_reasoning.py` | 1 | 2 |
| `core/atlas/*` | 5-8 | ~12 |
| `core/knowledge.py` | 1 | 3 |
| `core/index.py` | 1 | 4-5 |
| `core/repo_policy.py` | 1 | 1 |
| `core/architecture_state.py` | 1 | 1 |
| `core/git_evidence.py` | 1 | 2 |
| `core/audit/runner.py`, `spaghetti_scorer.py` | 2 | 3 |
| `services/pipeline/orchestrator.py` | 1 | 2 |
| `services/pipeline/recovery.py` | 1 | 2 |
| `services/pipeline_checkpoint.py` | 1 | 3 |
| `services/pipeline_logger.py` | 1 | 2 |
| `services/branch_backup_manager.py` | 1 | 4 |
| `agents/hr/roster.py` | 1 | 2 |
| `core/goalposts_models.py` | 1 | 2 |
| `api/routers/trace_routes/shared.py` | 1 | rewrite `TRACE_FILES`/`INDEX_FILES`/`ALL_DATA_FILES` to use the new module |
| `api/routers/trace_routes/enrichment.py` | 1 | rewrite destroy to enumerate from new module |
| **Total** | **~25 files** | **~70 call sites** |

These numbers are estimates from the path-mapping pass. Actual count is established empirically during Step 0.
