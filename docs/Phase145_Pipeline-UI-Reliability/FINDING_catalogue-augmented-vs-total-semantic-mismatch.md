# FINDING — `augmented_nodes > total_nodes` data-semantics mismatch (§9.3 #32)

**Filed:** 2026-06-25
**Status:** open — root cause identified, fix deferred to backend PR
**Scope:** `src/prep/core/augmenter.py`, `src/prep/api/routers/trace_routes/enrichment.py`
**Companion regression test:** `packages/ui/src/components/trace/__tests__/GraphEnrichmentPipeline.behavioral.test.tsx` Fixture CA8 (PR-M, commit `aa8adb7d`)
**Related:** §9.3 #31 (the cosmetic chip clamp shipped earlier — defense-in-depth above this bug)

## Symptom (already reproduced)

Fast Catalogue chip rendered `5501% coverage · 98% conf` in a live
dashboard session. The underlying numbers were `total_nodes=142`,
`augmented_nodes=7812` → `7812 / 142 × 100 = 5501.4`. The chip clamps
to `100%` since PR-D (§9.3 #31), but the underlying numbers are still
inconsistent.

## Root cause — two different denominators conflated

Each catalogue completion writes a manifest via
`TraceAugmenter._write_manifest` (`src/prep/core/augmenter.py:2133-2166`).
The relevant fields are derived from `result.total_nodes`,
`result.skipped`, and the merged `entries` dict that includes both
this-run and prior-run augmentations.

### `total_nodes` is current-run scope

`augmenter.py:2144`:

```python
augmentable_nodes = result.total_nodes - result.skipped
```

`augmenter.py:2151`:

```python
"total_nodes": augmentable_nodes,
```

Where `result.skipped` is set at `augmenter.py:1714` and `:1992`:

```python
result.skipped = result.total_nodes - total_work
```

Substituting:

```
augmentable_nodes = total_nodes - (total_nodes - total_work) = total_work
```

`total_work` is computed at `augmenter.py:1686`:

```python
total_work = len(to_augment_symbols) + len(to_augment_files)
```

Which is the count of nodes filtered through `_needs_augmentation(n, existing)`
(`augmenter.py:1683-1684`) — **only nodes that need augmentation this run**
(new or stale). On a steady-state incremental run after the project is
fully augmented, `total_work` is small (e.g. 142 = the count of changed
files since the last build).

> **Comment at `augmenter.py:2143` is misleading** — claims `skipped` is
> just external-module nodes, but `result.skipped = total_nodes - total_work`
> includes already-done nodes too. This is part of the root cause.

### `augmented_nodes` is cumulative project-wide

`augmenter.py:2152`:

```python
"augmented": len(entries),
```

Where `entries` is the dict the augmentation loop has been mutating
in place (NOT a separate "merged" dict — `existing` and `entries`
are the same reference, renamed at the call site):
- `existing = self.load_existing()` (`augmenter.py:1669`) reads
  every previously-augmented entry from `trace_augmented.jsonl` on disk
- The augmentation loop mutates `existing` in place, adding entries
  for nodes processed this run (happens between line 1742 and 1992)
- The same dict (`existing` post-mutation, passed as `entries`) is
  what `_write_manifest(result, entries)` receives

After many incremental runs against a large project that's been fully
augmented once, `len(entries)` can grow to thousands while `total_work`
on any given small-change run stays in the dozens.

### Why these collide in the chip

The route at `src/prep/api/routers/trace_routes/enrichment.py:45-69` returns
`augmented_nodes` and `total_nodes` directly from the manifest after
the run completes (the live-overlay branch at lines 62-65 only fires
when `slot.phase == BuildPhase.RUNNING`).

The UI computes `pct = augmented_nodes / total_nodes × 100`
(`packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1298-1300`)
which equates "cumulative project-wide augmentations" with "this run's
work scope" — semantically meaningless. Hence 7812 / 142 = 5501%.

## Fix options

The fix has to make `total_nodes` and `augmented_nodes` share a
denominator. Three coherent options, in increasing scope:

### Option A — `total_nodes` = full project augmentable count

Make `total_nodes` reflect every augmentable node in the project (the
denominator that `len(entries)` is implicitly counting against). The
numerator already does this.

Mechanic: replace the `augmentable_nodes = result.total_nodes - result.skipped`
line with a project-wide augmentable count. Compute once at run-start
by taking the union of the kind-filtered node sets the augmenter
already iterates over (`symbol_nodes` and `file_nodes`):

```python
# Matches the actual filter in the shipped fix
# (augmenter.py:1699 — PR-P):
augmentable_ids = (
    {n["id"] for n in symbol_nodes}
    | {n["id"] for n in file_nodes}
)
project_augmentable_count = len(augmentable_ids)
```

Note: a negative filter like `kind != "external_module"` would
over-count — there are other non-augmentable kinds (`section`,
legacy entries, etc.) that the positive filter correctly excludes.
The shipped PR-P uses the positive filter for this reason.

Pros: matches the user mental model ("X% of my project's nodes are
augmented"), the chip number actually means something useful, fixes
both the current-run inconsistency and the steady-state percentage
display.

Cons: requires identifying the canonical "augmentable" filter
(currently scattered across `_needs_augmentation` and the skip-count
arithmetic). May break consumers downstream that depend on the
"this-run scope" interpretation.

### Option B — `augmented_nodes` = this-run work count

Make the numerator match the denominator's "this-run" scope. Replace
`"augmented": len(entries)` with `"augmented": result.augmented` (the
count of augmentations performed THIS run, per
`augmenter.py:2161`'s "augmented_this_run").

Pros: smaller code change, no new project-wide arithmetic.

Cons: degrades the chip's user-facing meaning ("12 of 142 nodes
augmented THIS RUN" — meaningless after the run completes; the
denominator vanishes from the manifest as soon as the next run starts).
Effectively turns the chip into per-run progress, not cumulative
coverage. Probably wrong.

### Option C — keep both, expose both, drop the chip-as-ratio

Stop computing `pct` from `augmented / total` and replace the chip with
either a static "all augmented" badge or a separate progress field
that's computed in the backend.

Pros: avoids the semantic collision entirely; backend stays free to
report whatever it wants.

Cons: largest UI scope; gives up the at-a-glance percentage feedback
the chip was designed for.

## Recommendation

**Option A**, scoped to a backend-only PR that:

1. Adds a project-wide augmentable-count helper in `augmenter.py`.
2. Updates `_write_manifest` to use it as `total_nodes`.
3. Migrates the v2 manifest path (`augmenter.py:2229-2251`) to
   coherent semantics. NOTE: v2 does NOT have the same root cause
   as v1 — v2's bug is that the orchestrator writes its own
   `total_items`/`processed` that overwrite the v1 counts when both
   manifests are read together. The fix (shipped as PR-P-fixup +
   r2) extends `ManifestStore.write_provenance`'s STRUCTURAL
   merge-preservation pattern to CATALOGUE, preserving the v1
   `counts`/`stats`/`version`/`built_at`/`model` keys across the v2
   write. Different code path, different fix; same user-visible
   symptom.
4. Adds a daemon-side pytest that writes a manifest with the v1 shape,
   reads it via `_project_augment_status` overlaid through the route,
   and asserts `augmented_nodes <= total_nodes`. This is the
   regression-test counterpart to PR-M's CA8 (which only pins the
   rendering clamp).
5. Considers whether the live-overlay branch
   (`enrichment.py:62-65`) needs corresponding changes — during
   `BuildPhase.RUNNING` the slot.progress numbers are coherent with
   each other, but `total_nodes` may need to be the project-wide
   total there too (otherwise the chip swings from "11 of 142"
   during the run to "8000 of 142" after the manifest writes — the
   numerator that grows is `augmented_nodes`, not `total_nodes`;
   the small denominator stays small).

PR-M's Fixture CA8 (the 7812/142 → 100% regression test) already pins
the rendering-side defense. The backend PR closes the actual data
inconsistency.

## Open questions for the backend PR

1. What is the exact filter that defines "augmentable"? `_needs_augmentation`
   uses node kind + hash freshness; the project-wide count needs the
   kind filter only (a node that's already augmented is still
   augmentable — it just doesn't need re-augmentation this run).
2. Does the v2 manifest path (Phase 49 `_write_stage_manifest_and_update_run`)
   suffer the same divergence? `quality.total_items` and
   `quality.processed` semantics need to be verified.
3. Is the live-overlay branch ever the source of the 5501% case? The
   overlay only fires during RUNNING phase, so the 5501% case is
   almost certainly from the POST-run manifest path — but worth
   confirming with a tracing flag during reproduction.
4. ~~Are there other call sites consuming `augmented_nodes / total_nodes`
   that would break if the denominator shifted scope?~~ **ANSWERED
   from grep** — 5 consumer sites identified, all safe under a
   denominator-scope shift:
   - `src/prep/api/routers/trace_routes/enrichment.py:57,64` — live
     overlay writes `slot.progress_current` to `augmented_nodes`
     (same source, just routed; no ratio math here).
   - `src/prep/services/pi_agent.py:868` — `augmented_nodes / total
     * 100` ratio math; already flagged in "Not in scope" below as
     a separate code path (legacy `pi_agent` augmentation).
   - `src/prep/dashboard/src/hooks/useDashboardPanels.tsx:1207` —
     reads `augmented_nodes` as `catalogued_nodes` for panel
     display; no ratio math, just display.
   - `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:462-464`
     — three reads: `aug.augmented_nodes === 0` (gate),
     `aug.low_confidence_count > aug.augmented_nodes * 0.3` (warning
     threshold), `aug.augmented_nodes < aug.total_nodes * 0.5`
     (stale threshold). The stale-threshold check is the only
     ratio-like comparison; under the new scope it would compare
     "cumulative augmentations vs project-wide augmentable" which
     is the semantically-correct check it always should have been.
   - `packages/ui/src/types.ts:375` — TypeScript type declaration;
     no runtime impact.

   Conclusion: shifting `total_nodes` to project-wide augmentable
   count is safe across all 5 consumers. The only ratio-based UI
   read (stale threshold) becomes MORE correct under the new scope.

## Verification of root-cause hypothesis (pending live repro)

This finding identifies the divergence in code but does not have a
captured stack trace from the live 5501% incident. To confirm
empirically:

1. Find a project with a fully-augmented `trace_augmented.jsonl` and
   recent incremental activity.
2. Capture `trace_augment_manifest.json` after an incremental catalogue
   run that touches a small number of files.
3. Verify that `counts.total_nodes` reflects the incremental work
   count, not the project total, while `counts.augmented` matches the
   line count of `trace_augmented.jsonl`.
4. If both numbers match the hypothesis, Option A is confirmed correct.

## Not in scope here

- The §9.3 #31 PR-F F1 CoverageBar clamps in TraceCoveragePanel /
  GraphStructurePanel — those are already fixed.
- The chip clamp at `GraphEnrichmentPipeline.tsx:1299` — already pinned
  by PR-M Fixture CA8 (commit `aa8adb7d`).
- The legacy `pi_agent.py` augmentation site
  (`src/prep/services/pi_agent.py:868`) which has its own
  `augmented_nodes / total` math — likely the same bug class, but a
  separate code path.

## Companion artifacts

- `packages/ui/src/components/trace/__tests__/GraphEnrichmentPipeline.behavioral.test.tsx`
  Fixture CA8 (PR-M, commit `aa8adb7d`) — pins the rendering clamp.
- §9.3 #31 entry in `PROPOSAL_playwright-uat-harness-v1.md` — the
  cosmetic clamp shipped earlier.
- §9.3 #18 cross-group I3 leak — separate concern, may share root
  causes around manifest semantics but tracked independently.
