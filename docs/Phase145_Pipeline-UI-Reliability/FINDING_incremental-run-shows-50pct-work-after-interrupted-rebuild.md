# Phase 145 Finding — Incremental Deep Reasoning shows >50% remaining work on a stable repo because a prior rebuild was interrupted

**Status:** Open. Symptom captured from live screenshot 2026-06-17 17:47 EDT. Root cause pinned via on-disk log inspection.
**Found:** 2026-06-17, reported by Eric (dogfooding on the SourcePrep repo).
**Severity:** Medium — the work the pipeline is doing is *correct*; the UI surface that frames it is wrong. The user can't distinguish "I changed a lot of files" from "the last rebuild only managed to re-enrich 20 of 2072 files before stopping." This erodes trust in the incremental signal.
**Linked symptom in README:** §2o (to be added).

---

## 1. Symptom (as reported)

> "There's no reason an incremental build from a well-established repo that's regularly updating should ever claim to have this ratio of green to orange. I absolutely did not update over 50% of the files, something is incorrect."

Screenshot evidence:
- Graph Scope card: `2087/2087 files traced 100%`, `0 stale`, `866/2088 nodes enriched 41%`, `40 enriched & embedded · 2048 in-progress`.
- Deep Reasoning bar: `896 / 2,073 files · 43%`, with the right ~57% of the bar rendered as the in-progress / to-do color.

The dashboard's only signal to the user is "57% remaining" with no UX disambiguation between *new work the user introduced* and *recovery work from a prior interrupted run*.

## 2. What the on-disk logs actually show

Project: SourcePrep (`f1636374-abc6-410d-99ee-822120379e79`), index at `/Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/`.

Timeline reconstructed from `.sourceprep/logs/pipeline_20260617_*.log` (all timestamps EDT):

| Time | Event | Evidence |
|---|---|---|
| **15:32** | Incremental deep_enrichment start, **healthy state** | `pipeline_20260617_185456.log`: `Epistemic enrichment: 94 files to enrich (788 existing, 851 total file nodes)` |
| ~15:33–15:42 | (between-run gap; presumably structural / fast_sync activity introduced new nodes) | — |
| **15:43:16** | **Force-from-start rebuild dispatched.** Epistemic stage wiped to zero. | `pipeline_20260617_193937.log`: `decision_type: stage_wipe_for_rebuild, choice: wiped, stage: enrichment, files: [trace_epistemic.jsonl, trace_epistemic_manifest.json]` |
| 15:43:19 | Worker resumes against the wiped file. Total work surfaced. | `Epistemic enrichment: 2072 files to enrich (0 existing, 2072 total file nodes)` |
| 15:43:19 | Tier dispatch begins. | `BATCHED epistemic enrichment: 2072 files in 11 tiers, code_batch_size=5, doc_batch_size=3 (cloud_small profile)` |
| **15:44:52** | Enrichment stage marked **complete with `total_items: 20, processed: 20, success_rate: 1.0`** | `.sourceprep/trace_epistemic_manifest.json.f67_pending` (the manifest written by that run and later renamed to `.f67_pending` at the next run start). Elapsed: 95.71s. |
| 15:44:52 → 15:49 | The on-disk JSONL grew from 20 lines (manifest count) to 40 lines (next run's PRE-FLIGHT count). Source not pinned. | `pipeline_20260617_212734.log` IntegrityGuard PRE-FLIGHT: `trace_epistemic.jsonl 97.5 KB, records 40, modified 2026-06-17T15:49:14` |
| **17:27:34** | Current run starts. **Sees only 40 existing entries.** Decides 2033 of 2073 file nodes need enrichment. | `Epistemic enrichment: 2033 files to enrich (40 existing, 2073 total file nodes)` |
| 17:27:34–17:53 | Current run grinds through the 2033 files. JSONL grows to 1068 lines. UI screenshot at ~17:47 shows 43% done. | `wc -l trace_epistemic.jsonl` at 17:53 = `1068` |

**The work the pipeline is doing right now is genuine, but it is *recovery work* — replaying the enrichment the 15:43 rebuild was supposed to finish and didn't.** The user's intuition that they didn't touch 50% of the files is correct.

## 3. What this surfaces — multiple distinct issues stacked

### 3a. (Primary) Enrichment stage reported `success_rate=1.0` after processing 20 of 2072 items

The `.f67_pending` manifest is the canonical record of the 15:43 run's enrichment stage:

```json
{
  "stage_id": "enrichment",
  "started_at": "2026-06-17T19:43:16.705355+00:00",
  "finished_at": "2026-06-17T19:44:52.424521+00:00",
  "elapsed_seconds": 95.71,
  "quality": {
    "total_items": 20, "processed": 20, "skipped": 0, "failed": 0,
    "success_rate": 1.0, "avg_confidence": 0.877
  },
  "output_files": {
    "trace_epistemic.jsonl": { "item_count": 20 }
  }
}
```

The worker dispatched 2072 files in 11 tiers (`BATCHED epistemic enrichment: 2072 files in 11 tiers`) but the resulting manifest claims `success_rate: 1.0` with `processed: 20`. The manifest's `quality` block is computed from the current `trace_epistemic.jsonl` row count via `aggregate_quality_metrics` (`orchestrator.py:4644`) — it does not know the expected denominator. So the stage exits in what the orchestrator considers a "completed" state even though only ~1% of the expected work landed.

**This is the structural bug.** Without it, downstream stages would still see the stage as incomplete and the next run wouldn't have to do recovery. With it, every run can leave the project in a silently-degraded state if the enrichment stage exits early.

### 3b. (Causal precondition) What triggered the 15:43 rebuild is unknown from the log

The 15:43 run is logged as `force_from_start`-equivalent (every stage hits `stage_wipe_for_rebuild` and `Freshness check bypassed (rebuild / force_from_start)`). The log does not record the *caller* — was it the dashboard "Rebuild" button, a `/pipeline/rebuild` API call, an internal selfheal path, or something else? The pipeline file logger emits the *decision* to wipe, not the *trigger* that requested the rebuild.

This is a gap in observability. A future log line like `{"event": "rebuild_triggered", "data": {"source": "ui_button" | "api_call" | "selfheal" | ..., "actor": "<request_id>"}}` would close it.

### 3c. (UX gap) The dashboard cannot distinguish "user changes" from "recovery work"

`GraphEnrichmentPipeline.tsx`'s Deep Reasoning bar shows `896 / 2,073 files · 43%`. The two-tone bar logic (F-76) is supposed to use an `incremental_baseline` to render the previously-complete portion in green and only the new increment in the active color — but in the current run the "baseline" the worker sees is the (degraded) 40 existing entries, so even a correct F-76 render shows 40/2073 ≈ 2% green and a giant ~57% to-do segment. The bar is not lying about the underlying state — but it is the only signal the user has, and it carries no copy explaining *why* the work is so large.

The dashboard does have a `Run` source signal somewhere (the `pipeline_run_metadata.json` carries `started_at` and we could derive "this run started after a wipe"). It just isn't surfaced anywhere in the Deep Reasoning card.

### 3d. (Possibly orthogonal) Mid-task progress (20 → 40 records between 15:44 and 15:49) without a manifest update

The integrity guard at 17:27 reports `records: 40` for a file whose manifest at 15:44 said `item_count: 20`. Something added 20 more rows between 15:44:52 and 15:49:14 but did not rewrite the manifest. Candidates:
- A subsequent partial run that started, wrote rows, but didn't reach manifest-write (would leave the file at >20 rows + the original 15:44 manifest in place).
- The orchestrator's `_write_stage_manifest_and_update_run` ran with a partial result.
- A different worker (group_reasoning, deepening) wrote into the same file — unlikely since `STAGE_OUTPUT_FILE[ENRICHMENT] == STAGE_OUTPUT_FILE[DEEPENING] == "trace_epistemic.jsonl"` (stages.py:218 + 222). Deepening shares the file. The 15:43 rebuild's deepening stage starting at 15:45:22 could have added the missing 20 rows.

This is plausibly explanatory — and if so, it means the 20 → 40 jump is normal stage-share behavior, not a bug. Still worth pinning.

### 3e. (Cross-cutting) Log file scoped by `.sourceprep/logs/` is mixing projects

`pipeline_20260617_193937.log` lives in the SourcePrep `.sourceprep/logs/` directory. Inside it, the actual `[Epistemic] Sending LLM call for: App/Shared/UITestSeeding.swift` lines reference Applifier files (project `7cdea5e4-c94d-4612-be67-81597da3d6ec`), not SourcePrep ones (e.g. `src/prep/...`). Multiple `stage_completed` events also reference the Applifier project_id.

This is the cross-project log-pollution shadow of §2k (concurrency undershoot + cross-project work loss). It's worth a separate note here because it makes per-project forensics harder: you cannot trust that a log under `<project>/logs/` contains only that project's events.

## 4. Hypotheses (ranked)

| # | Hypothesis | Pinned? |
|---|---|---|
| **H1** | The 15:43 enrichment run was interrupted (paused / cancelled / daemon-killed) after the first tier completed, but the orchestrator wrote a "stage complete" manifest because the worker returned a normal result for the 20 items it had processed. | **Strong but not pinned to a single cause yet.** The .f67_pending manifest exists and `finished_at` is recorded, which suggests the stage returned cleanly (not cancelled). Need to check the worker's return contract — does it ever return early without raising? |
| **H2** | The worker hit an unhandled exception during tier 2 that was swallowed, and the stage exit code still wrote a manifest. | Plausible. Needs grep for `enrichment.*error` / traceback in the 15:43–15:44 window of `pipeline_20260617_193937.log`. |
| **H3** | The 95s elapsed includes only tier-1 dispatch; the manifest was written *before* the remaining tiers were scheduled. | Less likely — the BATCHED log says "2072 files in 11 tiers" but doesn't log a per-tier completion event, so we can't pin which tiers ran. |
| **H4** | The two-tone bar's baseline is being computed live each run from `existing` count rather than persisted across runs (memory: "two-tone bar baseline not persisted"). Even if §3a is fixed, the user-perceived "tiny incremental delta" would still render as a huge orange bar if the baseline doesn't survive across runs. | Likely orthogonal to §3a. Both could be true. |

## 5. Diagnostic checklist

For the user's next dogfooding session:

1. **Look at the run-trigger log line just before any `stage_wipe_for_rebuild` decision.**
   ```bash
   grep -B2 'stage_wipe_for_rebuild' .sourceprep/logs/pipeline_*.log | head -30
   ```
   If we can correlate the wipe with a dashboard click or API call, §3b closes.
2. **Grep for swallowed exceptions in the 15:43 window of `pipeline_20260617_193937.log`.**
   ```bash
   grep -aE 'Error|Exception|Traceback|cancelled|paused' \
     .sourceprep/logs/pipeline_20260617_193937.log \
     | grep -v '"epistemic_enrichment.*reasoning_trade-off"'  # drop LLM payload noise
   ```
3. **Trace why tier 2+ didn't dispatch.** The BATCHED log line `2072 files in 11 tiers` is the last anchor. Find the next epistemic_enrichment log line and see what state we're in.
4. **Cross-reference `pipeline_run_metadata.json` `stage_metadata.enrichment` from each historical run** to see whether `status` ever transitioned to `paused` or `cancelled` mid-stage.
5. **Confirm the §3d hypothesis (deepening writing into trace_epistemic.jsonl).** Either pin it or rule it out — it affects how we interpret per-stage row counts in the future.

## 6. Design questions raised (for a future PROPOSAL_)

- **Q1.** Should the enrichment worker carry an *expected denominator* into its result payload so `_write_stage_manifest_and_update_run` can detect "processed 20 of 2072" and refuse to mark the stage complete?
- **Q2.** Should "this run is recovering from an interrupted prior run" surface in the UI? A signal like `metadata.is_recovery` could drive an explicit banner above the Deep Reasoning card ("Resuming a partial rebuild from 17:43 — 2033 of 2073 files needed re-enrichment because the prior run was interrupted").
- **Q3.** Should the two-tone bar's baseline be persisted on disk across runs (per the user's memory note: "two-tone bar baseline not persisted")? Or is the right fix to anchor the baseline to the manifest's `incremental_baseline` field that F-76 already added?
- **Q4.** Should `.sourceprep/logs/<project>/` contain *only* that project's events? Today, daemon-level events for other projects leak in (§3e). A per-project file logger handle keyed on the active project_id at log-emit time would close this.
- **Q5.** Should every `force_from_start` dispatch write a `rebuild_triggered` event with the calling source recorded explicitly?

## 7. Out of scope

- Implementing the UX banner.
- The structural fix to §3a (manifest must not say `success_rate: 1.0` when work was abandoned).
- Cross-project log scoping.
- The two-tone bar baseline persistence question.

Per Phase 145 working principles, this finding documents the symptom and pins the proximate code paths. Fixes belong in a later PROPOSAL_ once §5 diagnostic step 1 produces evidence on whether the trigger was UI / API / selfheal.

## 8. Recurrence on Applifier 2026-06-25

Same row, same project, same family. Live dashboard screenshot during an incremental rebuild (stale/new files): Deep Reasoning row reads `1,257 / 1,225 files · 100%`. The pattern (numerator > denominator while displayed as 100%) is identical to §3a — the enrichment manifest's `quality` block reports a numerator drawn from cumulative jsonl content while the denominator reflects a different scope (likely the smaller current-run-work set or a stale `progress_total`).

The 2026-06-21 occurrence (1,069 / 1,058) is captured in [`FINDING_stage-progress-non-monotonic.md`](FINDING_stage-progress-non-monotonic.md) §8; the 2026-06-25 occurrence is in §9 of that file. This is now a repeatedly-reproduced bug, not a one-off.

**Cross-reference: the catalogue-stage analogue of this bug class** was filed under §9.3 #32 as `FINDING_catalogue-augmented-vs-total-semantic-mismatch.md` (commit `a9663d7d`). The fix landed for catalogue across three commits — PR-P `1de94cac` + PR-P-fixup `fbb0163d` (ManifestStore CATALOGUE merge-preservation) + PR-P-fixup-r2 `93b4f8a8` (`built_at`/`model` preservation + load-bearing tests). Recipe:

  1. Augmenter writes a v1 manifest with a project-wide augmentable denominator (`AugmentResult.project_augmentable_count`) and an orphan-filtered numerator (`valid_node_ids` excludes entries whose node_id is not in the kind-filtered current trace).
  2. `ManifestStore.write_provenance` preserves the v1 fields (`counts`, `stats`, `version`, `built_at`, `model`) when the orchestrator's v2 blob overwrites the same file. Without this, the v1 fix is dead code in pipeline mode (the v2 write happens milliseconds after v1).
  3. `augmenter.status()` reads v1 first; falls back to v2 only when v1 is absent.

The deepening / enrichment stages share the file (`trace_epistemic.jsonl`, per the `STAGE_OUTPUT_FILE` linked code below). The same recipe should apply, with the additional complication that the file is shared by two stages so the v1-writer-equivalent will need to know which stage's counts it owns. That's the scope of a follow-up PR (proposed PR-Q in the Phase 145 sweep).

The frontend monotonic / clamp guard from [`FINDING_stage-progress-non-monotonic.md`](FINDING_stage-progress-non-monotonic.md) §5 remains the right defensive layer in addition to the backend fix.

---

**Linked code:**
- `src/prep/services/pipeline/orchestrator.py:2475-2517` — F-67 manifest rename at stage start
- `src/prep/services/pipeline/orchestrator.py:4535-4710` — generic manifest writer (`_write_stage_manifest_and_update_run`)
- `src/prep/services/pipeline/orchestrator.py:4639-4666` — quality block from JSONL row count (the structural bug surface for §3a)
- `src/prep/core/epistemic_enrichment.py` — `Epistemic enrichment: N files to enrich (M existing, T total file nodes)` log line + tier dispatch
- `src/prep/services/pipeline/stages.py:212-227` — `STAGE_OUTPUT_FILE` map (enrichment + deepening both → `trace_epistemic.jsonl`)
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — Deep Reasoning two-tone bar (F-76 baseline logic)

**Evidence files** (under `/Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/`):
- `logs/pipeline_20260617_185456.log` — healthy run (788 existing → 94 to enrich)
- `logs/pipeline_20260617_193937.log` — rebuild run; reports stage complete after 20/2072
- `logs/pipeline_20260617_212734.log` — current recovery run (40 existing → 2033 to enrich)
- `trace_epistemic_manifest.json.f67_pending` — frozen manifest from the 15:43 run
- `pipeline_run_metadata.json` — current run metadata
