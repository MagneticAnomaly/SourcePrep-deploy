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

---

**Linked code:**
- `packages/ui/src/components/trace/StageProgressBar.tsx` — incremental variant render
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1417-1431` — Group Reasoning `progress` / `rerun` plumbing
- `src/prep/services/build_orchestrator.py:114, 383-388` — `progress_baseline` first-write gate
- `src/prep/core/epistemic_enrichment.py:842` — suspected sub-stage progress emitter
