# 01 — Existing Infrastructure Audit

Before designing anything new, we catalogue what's already here so Phase
105 builds on it instead of duplicating or fighting it.

## Git already in the codebase

| File | What it does | Reusable for Phase 105? |
|------|-------------|-------------------------|
| `src/codrag/agents/shared/git_client.py` | Thin `subprocess`-based wrapper. Methods: `current_branch`, `branch_exists`, `create_branch`, `switch_branch`, `add_files`, `commit`, `diff`, `delete_files`, `copy_to_branch`. | **Yes — extend.** Missing read-only primitives we need: `log`, `blame`, `diff_between`, `rev_list`, `show`. Extend in place; do not fork. |
| `src/codrag/core/github_push.py` | Pushes to GitHub remote (API). | No — unrelated. Remote-facing. |
| `src/codrag/core/github_sync.py` | Pulls remote state from GitHub. | No — unrelated. |
| `src/codrag/core/github_webhook.py` | Handles GitHub webhooks. | No — unrelated. |
| `src/codrag/core/watcher.py:417` | Comment acknowledges "git pull" can bulk-add files. Watcher never actually asks git. | Not modified by Phase 105 (see Non-goals). |
| `src/codrag/services/branch_backup_manager.py` | Agent feature: snapshot branches. | Related in spirit, not a dependency. |

**Verdict:** one clean subprocess wrapper exists (`GitClient`). We extend
it with read-only history primitives rather than spawning a new one.

## Roadmap / planning engine already in the codebase

| File | Lines | What it does |
|------|-------|-------------|
| `src/codrag/core/roadmap_miner.py` | 366 | Fuses audit findings, orphan modules, structural hotspots, and markdown planning-keyword hits into `RoadmapNode`s. Reads from already-computed pipeline outputs (`audit_cache.json`, `modules.json`, `trace/graph.json`). Invoked from `api/routers/roadmap.py:665`. |
| `src/codrag/core/todo_scanner.py` | 273 | Scans TODO/FIXME/HACK/XXX/OPTIMIZE/PERF/BUG comments. Uses `ripgrep` with Python fallback. Produces `RoadmapNode`s with `source="todo_scan"`. **Phase 105 modifies this file** (and only this file, among the engine pieces). |
| `src/codrag/core/goalposts_models.py` | (dataclasses + helpers) | Defines `RoadmapNode`, tiers, sources, states. Key sets: `ROADMAP_SOURCES = ("manual", "ai_proposed", "todo_scan", "github")`; `ROADMAP_NODE_STATES` includes `"proposed"`, `"accepted"`, `"active"`, `"completed"`, `"dismissed"`. **No schema change in Phase 105.** |
| `src/codrag/api/routers/roadmap.py` | 1,017 | Substantial FastAPI router serving the roadmap to the dashboard. **Untouched by Phase 105.** |
| `src/codrag/dashboard/src/hooks/useRoadmapSystem.ts` | — | Real CRUD handlers: move tier, dismiss, delete, create. The roadmap view is live and used. |

**Verdict:** the engine and the serving layer exist and are active.
Phase 105 adds **no new source** and **no post-processing step** on the
miner output. It modifies only `todo_scanner.py` to demote stale-file
TODOs. Earlier drafts proposed broader integration; those were cut
after scrutiny.

## Downstream surfaces that share `RoadmapNode` (discovered during scrutiny)

These consume `RoadmapNode` and constrain what a Phase 105 integration
can safely do without coordination. None are modified by Phase 105; all
would need to be considered before any future retirement / co-change /
concept phase.

| File | Role | Why it matters for future phases |
|------|------|----------------------------------|
| `src/codrag/core/sprint_intelligence.py` | Scores `RoadmapNode`s for sprint ranking. Reads `priority` among other inputs. | Any future phase that *boosts* priority (churn × centrality, etc.) needs to design for coordination with this scorer. |
| `src/codrag/core/github_push.py` | Pushes `RoadmapNode`s to GitHub as issues. Nodes with `source="github"` originated from issues. | Auto-retiring a pushed node silently diverges local state from an open GitHub issue. Any retirement phase must decide retire-vs-close policy. |
| `src/codrag/core/audit/opportunity_manager.py` | Sibling "opportunities" surface adjacent to the roadmap. | Adding new roadmap node sources (co-change, concept-derived) risks duplicate surfacing across roadmap and opportunities. |
| `src/codrag/core/goalposts_planner.py` | Related planner subsystem that extracts fields into `RoadmapNode`s. | Same integration question as the scorer — priority changes propagate through. |

Phase 105 touches none of these, which is exactly why it is safe to
ship. Noting them here so future-phase authors don't rediscover them
the hard way.

## Concept store (the dormant leg)

| File | Status |
|------|--------|
| `src/codrag/services/concept_store.py` | Exists, active. |
| Active concept count (per CLAUDE.md atlas) | **0** |
| Seed concept count | **366** |

The concept store works. The **promotion pipeline** (seed → active) does
not have a clear trigger today. This matters for T2: git evidence is
well-suited to be that trigger, but wiring it requires touching the
concept store, which is a larger surface than T1 and where the
brainstorm specifically flagged risk.

## Related pre-existing pain (from memory)

- **Pipeline sequencing bug** — deep enrichment stages stall. Phase 105
  reads pipeline outputs, does not write them. Side-car posture keeps
  us away from this bug.
- **Pipeline resume gaps (F-66/67/68/75)** — daemon restart loses
  progress. Phase 105 cache must be recoverable independent of pipeline
  resume state.
- **Full reset gaps (F-78)** — `index_destroy_project` missed several
  SQLite stores. Phase 105 cache must be registered with whatever
  "destroy" path we land on, or kept as an opt-in standalone artifact.
- **SQLite WAL unreliable on USB (4TB-BAD)** — any SQLite we add runs
  in DELETE journal mode on this machine. Prefer JSON files or a small
  SQLite with explicit DELETE mode.
- **AGENTS.md not in graph** — and also not in co-change analysis. We
  exclude CoDRAG-managed files from co-change mining to avoid massive
  false-pair signals from auto-regenerated files.

## Summary: the building blocks Phase 105 uses

```
GitClient  (subprocess wrapper, write-ish ops for agents)
    └── extend with two read-only methods (log_numstat_since, rev_parse_head)

todo_scanner.py (TODO scanner)
    └── add a churn gate in post-processing

NEW: git_evidence.py (read-only primitive + JSON cache)
NEW: git_evidence_service.py (per-project singleton wrapper)
```

Phase 105 adds **two new modules** and modifies **two existing files**
(`git_client.py`, `todo_scanner.py`). Plus tests. Five files total, no
schema migration, no router or dashboard change. Scope deliberately
chosen to avoid touching any of the downstream surfaces listed above.
