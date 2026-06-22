# Phase 145 Finding — Multiple Fast Sync rows render as `running` simultaneously during a Rebuild All

**Status:** Open. **Limited-context capture** — two screenshots only, taken 2026-06-17 ~08:49 EDT during a `Rebuild All`. Circumstances around the run (which project, what trigger, what state preceded) were not noted and cannot be reconstructed.
**Found:** 2026-06-17, surfaced by Eric in retrospective dogfooding 2026-06-18.
**Severity:** Medium — UI lies about pipeline state during rebuild. The state machine only allows one stage per group to be `running`; the screenshots show two-to-three rows spinning at once.
**Linked symptom in README:** §2r.

---

## 1. Symptom (from two screenshots only)

### Screenshot A — header says "stage 5/15: Knowledge Embedding · 74%"

Fast Sync rows simultaneously rendered as:

| Stage | Visible state |
|---|---|
| 1. Structural Graph | ✓ complete (3,445 nodes · 8,017 edges) |
| 2. Edge Discovery | **spinner + bar + "Discovering edges…"** |
| 3. Fast Catalogue | ✓ complete (99% coverage · "No run data") |
| 4. Relationship Validation | **spinner + bar + "Validating…"** |
| 5. Knowledge Embedding | **spinner + bar at 6% + "Embedding…"** |

So three rows in the same group claim to be actively running while the header attributes the current stage to one of them (Knowledge Embedding).

### Screenshot B — header says "stage 3/15: Fast Catalogue · 87%" (taken ~12 s earlier)

| Stage | Visible state |
|---|---|
| 1. Structural Graph | ✓ complete |
| 2. Edge Discovery | **spinner + bar + "Discovering edges…"** |
| 3. Fast Catalogue | **spinner + bar at 98% + "157 / 160 files"** |
| 4. Relationship Validation | ✓ complete (0 issues, "yesterday") |
| 5. Knowledge Embedding | ✓ complete (1384 chunks embedded) |

Here two rows spin (Edge Discovery + Fast Catalogue) while two downstream rows (Validation, Knowledge Embedding) show as complete — with **"yesterday"** / **"unknown via"** metadata, i.e., values cached from a previous run. The downstream rows can't actually be complete yet because the current group is on stage 3.

## 2. What's clearly wrong

1. **More than one row rendered as `running` in the same group.** Phase 145 README §4a (UI row states) defines `running` as "stage actively in-flight" — a sequential state machine should have exactly one per group at any moment.
2. **Stale `complete` rows held over from a prior run.** Screenshot B's Relationship Validation and Knowledge Embedding both show stage metadata from earlier runs ("yesterday", `1384 chunks embedded`) while the current Rebuild All has only reached stage 3. They should show `not_built` / `pending` until the current run reaches them.
3. **Edge Discovery shows a spinner in both screenshots.** In B (header at stage 3), Edge Discovery shouldn't still be running — Fast Catalogue (stage 3) only runs after Edge Discovery (stage 2) completes.

## 3. What we can't tell from the screenshots

- Which project this was on (the panel doesn't show the project name in this crop).
- What kicked off the rebuild (UI Rebuild All button, force_from_start API, selfheal, watcher).
- Whether the same rows were spinning ~30 s earlier or this is a transient flash during a state machine handoff.
- Whether the header is from `current_stage_index` (orchestrator) or from `slot_phase` (build orchestrator) — those are independent signals (Phase 145 §3 data flow) and could disagree, which would explain part of this.

These would all be worth capturing next time, but the user explicitly noted the original circumstances are lost; treating this as a documented "we saw this once, here's what's visibly wrong" entry rather than a diagnostic plan.

## 4. Most likely cause class (hypothesis, not pinned)

This is the same shape as §2a (skipped stages render as "Running" forever) and §2l/§2n (UI rollup drift), but at the level of the per-row spinner state during an active rebuild. The `compute*State` family in `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` decides each row's state from a mix of (a) the API's per-stage running flag, (b) cross-stage SSE flags ("forward-progression hints"), and (c) cold-state checks. The "multiple spinners" pattern is what happens when (b) flips a downstream row to `running` *before* (a) clears the upstream row.

Concretely the lines worth re-reading first time this is investigated: `computeEpistemicState` and its siblings (`packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505+`) where the F-NEW-3 (Phase 118) reordering "the API's per-stage running flag for THIS stage is the freshest signal we have" was added — that fix may have an inverse direction issue when *upstream* stages haven't been cleared.

## 5. Relationship to other open findings

- **§2a** — same shape (UI shows running when state machine says otherwise), but specifically the freshness-skipped case. Fix landed (P2 / `mark_stage_skipped`); doesn't cover this Rebuild All case.
- **§2l** — UI rollup drift, fix proposed in `PROPOSAL_threads-B-and-C-v2-…md` Thread C. Same family of code paths (`compute*State`).
- **§2n** — Immune System never appears complete (different direction — should be complete but renders not-run).
- **§2o** — header / progress / per-row drift after an interrupted rebuild.

This entry is consistent with the broader pattern: **the per-row state in `GraphEnrichmentPipeline.tsx` derives from multiple signals that the orchestrator does not guarantee are mutually consistent during a transition.** A focused audit of those signals (the §2l/§2n/§2o common factor) would likely close this finding alongside the others.

## 6. Suggested action — for the next reviewer, when bandwidth allows

Add a single Playwright assertion to the eventual Phase 145.3 invariant test suite (README §6.3) that during any single SSE-derived snapshot, no group has more than one stage in `running` state. That assertion would catch this entire class of bug without depending on knowing the original circumstances of these screenshots.

## 8. Recurrence 2026-06-19 08:11 + 08:13 — Relationship Validation row spinning while header says Stage 5

Same project (SourcePrep), 2 minutes apart screenshots. Header reads `Rebuilding All stage 5/15: Knowledge Embedding · 87%` then `· 90%`. Row states at both timestamps:

| Stage | Header position | Row state |
|---|---|---|
| 1. Structural Graph | done | ✓ complete (30,491 nodes, 5s today) |
| 2. Edge Discovery | done | ✓ complete (214 edges, today) |
| 3. Fast Catalogue | done | ✓ complete (100% coverage, 14 auto-filled, today) |
| 4. Relationship Validation | done (header is on Stage 5) | **spinner + bar + "Validating…"** |
| 5. Knowledge Embedding | CURRENT per header | spinner + bar at 4% → 48% (progressing normally) |

Per Phase 145 §4a, exactly one row per group should be `running` at a time — the one at `current_stage_index`. Stage 4 should be `complete` since the orchestrator advanced past it. The Relationship Validation row spinning is the same `compute*State` race documented in §1 — SSE forward-progression hints from a downstream stage flipped this row's state, OR cold-state derivation didn't see the manifest update before the next-stage hint landed.

**This recurrence has full context** (unlike the §1 + §2 screenshots which were "limited-context"). The user actively triggered this Rebuild All; the daemon was just restarted; the symptom appeared immediately on first dashboard view post-restart. **Post-restart freshness is now part of the symptom signature** — worth investigating whether SSE event replay during reconnect emits prior `running` flags for already-completed stages.

The Phase 145 Playwright invariant I1 from `REFERENCE_canonical-pipeline-behavior.md` §8 (`exactly one row per group has data-state="running"`) would have caught this immediately.

## 9. Cross-references

- Phase 145 README §4a (UI row states contract), §4c (UI invariants).
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505+` (`compute*State` family + the F-NEW-3 Phase 118 reordering).
- Related findings: §2a, §2l, §2n, §2o, §2s.
- Playwright invariant that would catch this: `REFERENCE_canonical-pipeline-behavior.md` §8 I1.
