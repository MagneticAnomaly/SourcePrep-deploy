# Phase 145 Finding — Stage `progress` regresses at sub-stage boundaries

**Status:** Open. Symptom observed live; root cause suspected but not yet pinned. Suppressed visually by Phase 145 follow-up — see §6.
**Found:** 2026-06-15, dogfooding the dashboard during a Group Reasoning run on this repo.
**Severity:** Low (cosmetic). The bar visibly regresses mid-run, which reads as "work was undone." No actual data loss; the stage still completes.

---

## 1. Symptom

Watching `Deep Enrichment → Group Reasoning` run in the dashboard, the bright-orange wedge of the two-tone incremental progress bar *shrank* a few seconds after appearing, then grew again. Under the original 3-slab `StageProgressBar` ('incremental' variant), the bright orange is computed as `stalePct × progress/100`. For it to shrink, either `stalePct` or `progress` must drop.

`progress_baseline` is set once per stage (verified — see §2), so `stalePct` is fixed for the duration of the run. That means `progress` itself regressed.

## 2. What's frozen and what isn't (verified)

| Field | Source | Mutates during run? |
|---|---|---|
| `progress_baseline` | `BuildSlot.progress_baseline` — `build_orchestrator.py:114, 387` (gated `if baseline > 0`, set on the worker's first non-zero report) | **No** — frozen snapshot |
| `progress_total` | worker callback, updated every tick | Yes (worker can refine total) |
| `progress_current` | worker callback, updated every tick | Yes |

So `donePct = baseline/total` is stable (small wobble possible if `total` is re-estimated), and the regression is in `progress_current / total`.

## 3. Suspected cause — sub-stage progress resets

Group Reasoning has multiple internal phases inside a single backend stage (analyze groups → enrich each group → synthesize). The worker callback is:

```
progress_cb(message, current, total, baseline)
```

If a later phase reports its own 0→N progress against the same `progress_total` (i.e., `current` snaps back to 0 between phases), the UI percentage drops and then re-climbs. That's the regression pattern.

Suspected (not yet confirmed) emitters:

- `src/prep/core/epistemic_enrichment.py:842` —
  `progress_callback("epistemic_enrichment", current_progress + done + failed, total_progress, progress_baseline)`
  Look at how `current_progress` is initialized at the start of each batch.
- Anywhere a stage worker switches loops without carrying the prior loop's `current` forward.

## 4. Why the visual artifact was loud under the 3-slab renderer

Old math (StageProgressBar.tsx incremental variant, pre-fix):

```
greenSlab        = donePct                              // fixed
brightOrangeSlab = stalePct × progress/100              // moves with progress
dimOrangeSlab    = stalePct − brightOrangeSlab          // inverse
```

A regression in `progress` shrinks `brightOrange` and grows `dimOrange` proportionally. Because they were rendered with the *same* hue (just at different opacities), the bar appeared to encode three independent states, which it does not. This made the regression look like a third color flickering in and out.

## 5. What we changed visually (2026-06-15, this commit)

Collapsed the incremental variant to two slabs only:

```
green  = donePct + stalePct × progress/100
orange = stalePct × (1 − progress/100)
```

Functionally identical inputs; one moving boundary instead of two. The 3-color confusion is gone.

**But the underlying regression is *not* fixed.** Under the new renderer, if `progress` regresses, the green slab itself will visibly shrink and the orange grow. That is still wrong — green should only ever grow during a single run.

## 6. Recommended follow-up (not yet scheduled)

Two layers, either or both:

1. **Frontend monotonic guard** (cheap, defensive). Track the highest `progress` seen per stage instance in the dashboard component; clamp the next render to `max(prev, current)`. Reset on `state === 'queued'` or on a fresh `progress_baseline`. This masks any backend regression with no behavior change downstream.

2. **Backend fix** (correct). Audit every stage worker that reports progress with multiple internal phases. The contract should be: `current` is monotonic non-decreasing across the lifetime of a single stage run, and `total` is fixed at the worker's first report (or only ever revised upward). Group Reasoning is the known offender; `epistemic_enrichment.py:842` is the first place to look.

Doing (1) without (2) hides a real correctness bug from operators. Doing (2) without (1) leaves a latent regression class (any future worker can reintroduce it). Recommended: do both, (1) first as a guard, (2) when we audit stage workers next.

## 7. Out of scope here

- The Phase 70 `progress_baseline` semantics (frozen vs rolling) — confirmed frozen, no change needed.
- The `initialize` and `rebuild` variants of `StageProgressBar` — untouched by the 3→2 collapse; this finding does not apply to them.

## 8. Adjacent: progress can also OVERSHOOT the total (2026-06-21)

Captured on Applifier Deep Reasoning row: `1,069 / 1,058 files · 100%`. Numerator exceeds denominator by 11. Same family as the regression documented in §1: worker progress emission isn't bounded against `progress_total`. The 3→2 slab collapse from this finding silently caps overshoot at 100% (the bar maxes out) but the displayed text (`1069 / 1058`) leaks the unboundedness. Full context in [`FINDING_manual-update-click-triggers-ui-cluster.md`](FINDING_manual-update-click-triggers-ui-cluster.md) §6.2. The frontend monotonic guard proposed in §5 should also clamp to `min(current, total)`; the backend audit should ensure `progress_current ≤ progress_total` invariant in every worker.

## 9. Fresh evidence: same overshoot recurred on Applifier 2026-06-25

Eric's 2026-06-25 dashboard screenshot on Applifier (incremental rebuild, stale/new files): Deep Reasoning row reads `1,257 / 1,225 files · 100%`. Ratio 102.6%. Direct sequel to §8's 2026-06-21 `1,069 / 1,058`; same row, same project, same overshoot shape. The progress-bar is also rendering in the Initial style (single-tone), not the two-tone incremental variant — likely a separate UX surface (cf. [`FINDING_edge-discovery-fast-completion-and-rebuild-progress-style-lag.md`](FINDING_edge-discovery-fast-completion-and-rebuild-progress-style-lag.md) §2t-minor).

This is also fresh evidence for [`FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md`](FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md) §3a (the manifest's `quality` block computed from raw JSONL row count with no expected denominator).

Cross-reference to Phase 145 §9.3 #32 work: PR-O (commit `a9663d7d`) FILED a structurally-identical bug for the catalogue stage (`augmented_nodes > total_nodes`). PR-P (`1de94cac`) + PR-P-fixup (`fbb0163d`) + PR-P-fixup-r2 (`93b4f8a8`) shipped the Option A pattern (project-wide denominator + orphan filter + ManifestStore merge-preservation) for the catalogue manifest writer (`TraceAugmenter._write_manifest`). The same pattern needs to be extended to:

  - The deepening / enrichment stage manifest writer (where `1,257 / 1,225` originates today). Likely the orchestrator's v2 `quality.total_items` vs `quality.processed` block for those stages, since both are jsonl line counts of `trace_epistemic.jsonl` (the file that `STAGE_OUTPUT_FILE` maps `enrichment` AND `deepening` to — see stages.py:212-227 in §7 evidence above). Same bug class, different stage.
  - Any other IIFE / route that surfaces cumulative-vs-this-run ratios.

Backend-audit candidates for §6 #2: `epistemic_enrichment.py:842` (suspected sub-stage progress emitter; called out in §6), plus the deepening worker's progress wrapping.

The frontend monotonic guard proposed in §5 + §8 remains the right defensive layer regardless of the backend fix landing first — without it, every newly-audited stage worker is one regression away from re-introducing the overshoot.

**Note on the 2026-06-25 screenshot's "4 downstream Not run" symptom** (Group Reasoning / Module Synthesis / Continuous Deepening / Deep Knowledge Embedding all show "Not run" while Deep Reasoning is mid-stage at 100%): see [`FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md`](FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md) §3a/§3c. The downstream stages have raw state `not_built` for this run cycle and i3SafeStageState's downstream-position override returns `not_built` (correct per the §9.3 #30 contract — coercion to `complete` only fires under `groupPhase === 'completed'`). But for an INCREMENTAL rebuild the UX loses the "previously completed" signal — those stages have run before, and "Not run" reads as "never ran". Distinct UX concern; not the same bug as the overshoot. Documented inline here to keep the screenshot's two symptoms together for future investigators.

---

**Linked code:**
- `packages/ui/src/components/trace/StageProgressBar.tsx` — incremental variant render
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1417-1431` — Group Reasoning `progress` / `rerun` plumbing
- `src/prep/services/build_orchestrator.py:114, 383-388` — `progress_baseline` first-write gate
- `src/prep/core/epistemic_enrichment.py:842` — suspected sub-stage progress emitter
