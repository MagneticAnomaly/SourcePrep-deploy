# Phase 105 — Git Evidence: Primitive, TODO Gate, Atlas Decoration

Status: **Planning complete. Ready for implementation plan.**
Scope: **Option γ** (β + Atlas decoration as a second consumer).
Author: Eric + Claude session, 2026-04-14.

## One-paragraph summary

Ship a small, read-only `git_evidence.py` module that wraps the existing
`GitClient` and exposes file churn plus two helpers
(`classify_hub`, `hot_zones`). Use it in exactly two places:
the TODO scanner (demote TODOs in cold files) and the Atlas generator
(label hub files `stable | evolving | fragile` and append a "hot zones"
line). **Labels only, no raw numbers in Atlas text.** No retirement, no
co-change mining, no concept promotion, no new pipeline stage, no
router or dashboard changes. Seven files touched. Nine acceptance
gates. One PR.

## Why Option γ and not β or δ

- **β (TODO gate only)** was too narrow — it improves a surface few
  users look at directly.
- **δ (new pipeline stage)** commits us to a pipeline state-machine
  change while the existing sequencing bug is still outstanding.
- **γ** sits in the middle: add the Atlas as a second consumer on
  demand. The atlas decoration ripples into the MCP ambient response,
  AGENTS.md generation, and the dashboard Atlas panel without any of
  those surfaces being modified — three surfaces get smarter from one
  integration point.

See `07_SCRUTINY.md` for the full scope history (β → γ upgrade).

## What this phase does

- Adds `core/git_evidence.py` — read-only primitive + classification
  helpers + JSON-backed cache.
- Adds `services/git_evidence_service.py` — per-project singleton.
- Extends `agents/shared/git_client.py` with two new read methods.
- Adjusts `core/todo_scanner.py` to demote TODOs in files untouched
  for 180 days.
- Adjusts `core/atlas/generator.py` to group hub files by `stable |
  evolving | fragile` and append an "Active zones" line.

## What this phase does not do

- No raw churn numbers in atlas text.
- No new pipeline stage.
- No LLM prompt changes.
- No `roadmap_miner` integration.
- No concept-promotion pipeline.
- No `github_push` coordination.
- No dashboard changes.
- No MCP endpoint changes.
- No retirement of any roadmap node.

All of those are potential future phases gated on γ dogfood results —
see `06_FUTURE_PATH.md`.

## Documents

| # | Doc | Purpose |
|---|-----|---------|
| 00 | [PROBLEM.md](00_PROBLEM.md) | Why the phase exists; origin in the Untraced panel observation |
| 01 | [EXISTING_INFRASTRUCTURE.md](01_EXISTING_INFRASTRUCTURE.md) | What we reuse vs build, plus the downstream surfaces we must not touch |
| 02 | [SCOPE.md](02_SCOPE.md) | Option γ: three deliverables, explicit in/out, file list, acceptance gates |
| 03 | [ARCHITECTURE.md](03_ARCHITECTURE.md) | `git_evidence.py` module design, classification thresholds, cache layout |
| 04 | [INTEGRATION_TODO_GATING.md](04_INTEGRATION_TODO_GATING.md) | Deliverable 2: TODO churn gating |
| 04b | [INTEGRATION_ATLAS.md](04b_INTEGRATION_ATLAS.md) | Deliverable 3: Atlas hub & hot-zone decoration, terseness rules |
| 05 | [RISKS.md](05_RISKS.md) | Risks that apply to Option γ, mitigations, rollback flags |
| 06 | [FUTURE_PATH.md](06_FUTURE_PATH.md) | Sequenced later phases with unlock-signal gates |
| 07 | [SCRUTINY.md](07_SCRUTINY.md) | Review findings: β narrowing, γ expansion, what stayed out |

## Effort

**7–10 working days** for one developer including tests, dogfood pass
on this repo, and doc updates.

## Acceptance gates (all nine must pass)

**Module-level:**
1. `recent_churn_by_file()` refreshes < 2s on this repo.
2. Cache registered with `index_destroy_project`.
3. Non-git-repo behavior: fail open, no exceptions.
4. `ruff` clean, `mypy` clean, tests pass.

**TODO gate:**
5. ≥ 1 legitimate stale TODO demoted; zero live TODOs incorrectly
   demoted.

**Atlas decoration:**
6. Hub line contains ≥ 1 `stable` and ≥ 1 `evolving` label Eric agrees
   with.
7. "Active zones" line appears with ≥ 2 real recent-work directories.
8. Atlas token growth **< 50 tokens** vs baseline.
9. With `atlas_decoration=false`, atlas output matches baseline
   byte-for-byte.

## What unlocks the next phase

See `06_FUTURE_PATH.md`. Each follow-on (105.5 Untraced commit-grouping,
106 pipeline stage, 107 catalogue/knowledge enrichment, 108 retirement,
109 co-change clustering) has a specific unlock signal. γ dogfood data
informs those decisions.

## Three decisions needed before writing-plans step

1. **Window defaults.** 180 days (TODO), 60 days (hub classification).
   Confirm.
2. **Atlas label set.** `stable | evolving | fragile | unknown`.
   Confirm or propose alternative.
3. **Settings namespace.** `settings.git_evidence.enabled` +
   `settings.git_evidence.atlas_decoration`. Confirm namespace.

Everything else has safe defaults; implementation can begin once these
three are settled.

## Next step

Invoke `superpowers:writing-plans` skill to produce a step-by-step
implementation plan from these design docs.
