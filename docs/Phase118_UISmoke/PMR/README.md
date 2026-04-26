# Phase 118 → PowerMateReborn Extended Test Session

## Goal

Apply the full Phase 118 fix-pack to a real (not synthetic-tiny) project and
verify that the UI renders accurately at every transition during a multi-mode
matrix run. Catch any new bug classes that didn't surface on the 4-file
`smoke-test` (rust_repo).

## Target

- **Project**: PowerMateReborn
- **Project ID**: `6955793f-d824-4e1c-8cb6-417a08bd6669`
- **Path**: `/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/real_repos/PowerMateReborn`
- **Size**: ~9.8 MB, 15 code files (Swift / TypeScript / mixed)

This is intermediate scale — bigger than the 4-file smoke project (where
many stages ran sub-2s and were missed by the harness's 2s polling), but
small enough for full T1–T8 to complete within a few hours.

## Methodology

Same harness, same matrix, same anomaly tier. All Phase 118 fixes (G1–G3,
F-NEW-1 through F-NEW-7, U1–U6) are live going into Round 1.

Round 1 = observation + classification.
Round 2 = fix any new bugs + re-validate.

## Key things to watch

These are the user-reported pain points from the smoke-test sessions —
verify they don't reproduce on a larger project:

1. **Hero state never shown post-build** (U1) — at end of full pipeline,
   panel must show all 15 stages green, not "Initialize Trace Graph".
2. **No spurious auto-pauses** (U2) — single project, no other contention,
   pipeline must not flip to paused on its own.
3. **Auto toggle is preference-only** (U5) — toggling Manual→Auto must NOT
   start a new run.
4. **Rebuild preserves prior detail** (U3 + U6) — finalize stage cards show
   prior counts during rebuild; frozen stages are visually distinct
   (`opacity-60` + "prior:" prefix).
5. **Rebuild header labels correct stage** (U3-extra) — back-to-front
   picker; header should read e.g. "Rebuilding 11/15: Atlas Building" not
   "Rebuilding 6/15: Knowledge Embedding".
6. **Group reasoning shows progress** (Issue A) — bar must render even
   during warmup.
7. **Pipeline stalls** (U4) — defensive self-resume should kick in if
   acquire fails on a node with no contenders.

## Files

- `RESULTS_R1.md` — Round 1 raw findings + classification
- `RESULTS_R2.md` — Round 2 (after fixes) verification
- `CLOSEOUT.md` — final disposition
