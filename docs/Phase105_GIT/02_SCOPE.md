# 02 — Phase 105 Scope (Option γ)

Upgraded from Option β after a second scrutiny pass surfaced the Atlas
as a higher-leverage second consumer. See `07_SCRUTINY.md` for the full
history. Still substantially tighter than the original T1/T2/T3 tier
plan.

## In scope

Three deliverables. Single PR target.

### Deliverable 1 — `core/git_evidence.py` module

Read-only module wrapping the existing `GitClient`. One primitive useful
immediately; helper for hub classification; cache that will grow as
future phases need more primitives.

**Exposed for Phase 105:**

- `FileChurn` dataclass
- `recent_churn_by_file(window_days)` — returns `{path: FileChurn}`
- `file_touched_in_window(path, window_days)` — boolean helper
- `classify_hub(path, window_days) -> "stable" | "evolving" | "fragile" | "unknown"`
- `hot_zones(top_n, window_days) -> List[str]` — directories by churn
- `refresh()` / `stats()` — cache management

**Deferred to later phases:**

- `cochange_pairs()`
- `commit_message_index()`
- `matching_commits_for_keywords()`
- Debug HTTP endpoints

### Deliverable 2 — TODO churn gating in `core/todo_scanner.py`

Identical to Option β. After the scanner produces `RoadmapNode`s:

- File **not touched in 180 days** → demote priority to `P3`, append
  `[stale: file not touched in 180d]` to description.
- File **touched in window** → unchanged.

No state transitions, no new sources, no retirement. See
`04_INTEGRATION_TODO_GATING.md`.

### Deliverable 3 — Atlas hub & hot-zone decoration

New in Option γ. The Atlas absorbs *labels*, not numbers.

- Hub files grouped by `stable | evolving | fragile` label.
- "Active zones" line added to `cross_cutting` text (up to 5
  directories).
- All labels are deterministic, computed from churn, not LLM-generated.
- Zero raw numbers emitted into atlas text.
- Total atlas token growth **< 50 tokens**.

See `04b_INTEGRATION_ATLAS.md`.

## Out of scope

| Item | Why cut for Phase 105 |
|------|----------------------|
| Node retirement pass on `roadmap_miner` output | Couples with `github_push.py`. Needs an issue-close policy. |
| Churn × centrality confidence boost | Competes with existing `sprint_intelligence.py` scorer. |
| Co-change mining as a new `RoadmapNode` source | Couples with `opportunity_manager.py`. Expected yield small relative to integration cost. |
| Concept promotion pipeline | Rests on unverified assumption that seeds were meant for auto-promotion. |
| LLM narrative synthesis | Premature. |
| Commit-grouped Untraced panel view | UI surface work. Phase 105.5 candidate. |
| New pipeline stage for git evidence | Pipeline state-machine risk (memory notes sequencing bug). Phase 106 candidate once γ proves the signal. |
| Catalogue / Knowledge / Clustering / Concepts / Audit integration | All require LLM-prompt or embedding-pipeline changes. Phase 106+ candidates. |
| Remote (GitHub API) integration | Orthogonal. |

## What changes on disk

Six files total. No schema migrations.

| File | Change |
|------|--------|
| `src/codrag/agents/shared/git_client.py` | **Modify.** Add `log_numstat_since(window_days, max_commits)` and `rev_parse_head()`. |
| `src/codrag/core/git_evidence.py` | **New.** ~250 lines (primitive + classification + hot zones + cache). |
| `src/codrag/services/git_evidence_service.py` | **New.** Per-project singleton wrapper. ~60 lines. |
| `src/codrag/core/todo_scanner.py` | **Modify.** ~15 lines added. |
| `src/codrag/core/atlas/generator.py` | **Modify.** ~30 lines added — hub classifier call + hot-zone line. |
| `tests/core/test_git_evidence.py` | **New.** Fixture-repo tests. |
| `tests/core/test_atlas_evidence.py` | **New.** Atlas decoration + fallback tests. |

Seven files counting tests. No routers, no dashboard, no MCP server, no
pipeline stages, no schema changes.

## What this phase explicitly does not claim

- It does not retire any roadmap node.
- It does not touch concepts, the GitHub push path, the opportunity
  system, or the sprint scorer.
- It does not change any LLM prompt.
- It does not add a new pipeline stage.
- It does not add dashboard UI.

## The claim Phase 105 does make

Three specific, verifiable changes:

1. Dead TODOs in cold files stop ranking like live ones.
2. The Atlas distinguishes stable hubs from evolving ones.
3. The Atlas surfaces current "hot zones" as a short line.

Each ripples automatically through the systems that already consume
atlas output (MCP ambient response, AGENTS.md generation, dashboard
atlas view) without any of those systems being modified.

## Effort estimate

**7–10 working days** for one developer including tests, dogfood pass
on this repo, and documentation updates.

## Acceptance gates

**Module-level:**

1. `recent_churn_by_file()` refresh < 2s on this repo, 60-day window,
   exclusions applied.
2. Cache registered with `index_destroy_project`; destroy removes
   `git_evidence/`.
3. Non-git directory behavior: module returns `None`; consumers fail
   open with no exceptions.
4. `ruff` clean, `mypy` clean, all tests pass.

**TODO gate:**

5. ≥ 1 legitimate stale TODO demoted on this repo; zero live TODOs
   incorrectly demoted (manual review).

**Atlas decoration:**

6. Hub line contains ≥ 1 `stable` and ≥ 1 `evolving` label that Eric
   agrees with on inspection.
7. Active zones line appears with ≥ 2 directories matching actual
   recent work.
8. Atlas token growth < 50 tokens vs baseline.
9. With `atlas_decoration=false`, atlas output matches baseline
   byte-for-byte (golden file test).

Pass all nine → Phase 105 complete.
