# Phase 128 — Pipeline Recovery Hardening

> **Scope:** Eliminate spurious full-rebuild triggers from Phase 61B
> auto-recovery. Make the pipeline journal authoritative, add a
> build-success marker that survives ungraceful daemon termination,
> fix the dead-code Phase 72 mtime touch source, harden the resume.py
> downstream-stub race, and complete the residual `.runprep → .sourceprep`
> brand-split cleanup.
>
> **Prior art:** Phase 61B (auto-recovery for stale pipelines), Phase 72
> (touch-and-recheck mtime self-heal), Phase 93 (clean-shutdown marker
> gating), F-66/67/75 (recovery gaps), F-78 (full-reset gaps).
>
> **Status:** Implementation complete on branch `phase-128-pipeline-recovery`.
> All 10 tasks landed with TDD coverage; pre-existing test failures on
> main left for separate triage.
>
> **Trigger incident:** 2026-05-05 21:22 — daemon restart after
> ungraceful stop triggered a full deep_enrichment re-run on the user's
> project despite a clean May 3 build, due to a missing clean-shutdown
> marker, dead-code Phase 72 touch (CATALOGUE → STRUCTURAL), and naive
> mtime-based staleness check.

## What changed

Authority order for "is the data healthy?" is now layered, with the
strongest signal winning first:

1. **Pipeline journal** — `journal.has_recent_completed_run(project_id, group, since)`
   answers "is there a completed run more recent than this reference?"
   The journal is SQLite-atomic, written inside a transaction at run
   completion. Any True answer short-circuits Phase 61B before any
   marker or mtime path runs.
2. **Build-success marker** — `.pipeline_last_success` is written on
   deep_enrichment / finalize completion (not fast_sync — see
   `recovery.py:_BUILD_SUCCESS_GROUPS`). Survives kill -9 / USB eject /
   sleep / crash, unlike the SIGTERM-only clean-shutdown marker. Phase
   61B compares its mtime against structural mtime; marker post-dating
   structural ⇒ skip recovery.
3. **Clean-shutdown marker** — `.pipeline_clean_shutdown`, unchanged.
   Written by the FastAPI lifespan shutdown handler.
4. **Mtime touch + recheck** — Phase 72's heal-in-place path. Now
   actually works (Task 3 fix).

## Detailed change manifest

| Task | File(s) | Summary |
|------|---------|---------|
| 1 | `src/prep/core/paths.py` | Warn on orphaned `.runprep` / `.codrag` alongside `.sourceprep`. |
| 2 | `src/prep/core/feature_gate.py`, `src/prep/core/lemon_squeezy.py` | License path resolves `.sourceprep` first, falls back to `.runprep` for legacy installs. |
| 3 | `src/prep/services/pipeline/recovery.py:1432` | Phase 72 `sync_downstream_mtimes` source `CATALOGUE → STRUCTURAL`. The heal-in-place path was dead code. |
| 4 | `src/prep/services/pipeline/recovery.py` (RecoveryManager) | `write_/check_/build_success_marker_mtime/invalidate_build_success_marker` static helpers. |
| 5 | `src/prep/services/pipeline/orchestrator.py`, `src/prep/api/routers/trace_routes/enrichment.py` | Orchestrator refreshes marker on group completion via `record_group_completion`; resets invalidate marker BEFORE wiping outputs. |
| 6 | `src/prep/services/pipeline/recovery.py` (Phase 61B) | Build-success marker gate skips recovery when marker post-dates structural. |
| 7 | `src/prep/services/pipeline_journal.py` | `has_recent_completed_run` helper. |
| 8 | `src/prep/services/pipeline/recovery.py` (Phase 61B) | Journal-authority gate runs FIRST; mtime/markers become advisory. |
| 9 | `src/prep/services/pipeline/resume.py:478` | Downstream-proves-upstream stub writer defers when journal shows active run. Closes F-67 race. |
| 10 | docs + memory | This README + `prep_observe` resolution note. |

## Test coverage

All new tests live under `tests/test_phase128_*.py`:

- `test_phase128_paths_migration_orphan_warning.py` (4 tests)
- `test_phase128_license_path_fallback.py` (3 tests)
- `test_phase128_touch_source.py` (2 tests)
- `test_phase128_build_success_marker.py` (8 tests)
- `test_phase128_marker_writeback.py` (5 tests)
- `test_phase128_phase61b_respects_marker.py` (3 tests)
- `test_phase128_journal_authority.py` (6 tests)
- `test_phase128_phase61b_journal_authority.py` (2 tests)
- `test_phase128_resume_no_stub_during_active_run.py` (2 tests)

Total: **35 new tests, all passing**.

## Pre-existing test failures (NOT from this phase)

8 tests in `test_resume_strategy.py` / `test_pipeline_journal.py` /
`test_index_recovery.py` / `test_pipeline_scheduler.py` fail on main
before this phase. They appear to depend on test fixtures that don't
match current resume-validation behavior. Out of scope for Phase 128;
left for separate triage.

## Live validation pending

Daemon restart needed before any of the recovery-path changes are
exercised against the running daemon. The user's pipeline was active
when this work began; per the user's plan, `.sourceprep/` will be
wiped and a fresh initial build performed after Phase 128 lands.

See `IMPLEMENTATION_PLAN.md` for the bite-sized task breakdown and
self-review.
