# PROPOSAL v2 — Threads B (barrier auto-clear) + C (resume-detector output check) + D (UI safety chip)

> **STATUS: DRAFT v2 — awaiting scrutiny — 2026-06-15.** Do not execute as-is. This proposal incorporates the corrected diagnoses uncovered by the v1 scrutiny pass (defects D1–D5, banner in [`PROPOSAL_threads-B-and-C-v1-barrier-and-rollup.md`](PROPOSAL_threads-B-and-C-v1-barrier-and-rollup.md)), but Thread C still depends on evidence being gathered by [`DIAGNOSTIC_2026-06-15_resume-point-and-failure-paths.md`](DIAGNOSTIC_2026-06-15_resume-point-and-failure-paths.md) (specifically DG2 — resume-detector decision tree). Thread B's evidence is complete; Thread C's is partial. Where confidence is asymmetric, this proposal labels each task `[evidence: solid]` or `[evidence: partial, needs DG2]`.

**Goal:** When this proposal is ready to execute, the user-visible result is: (B) a failed pipeline group no longer leaves `.reset_barrier` on disk forever; (C) the orchestrator stops claiming "PIPELINE_UP_TO_DATE" when a stage's manifest exists but its output file is empty; (D) the dashboard surfaces a clearly-named warning chip if any stage ever reaches that broken state again in the future.

**Architecture:** Three surgical, independent fixes. Thread B is a Python orchestrator refactor — move barrier-clear into a shared post-run hook so every failure path covers it. Thread C is a Python resume-detector fix — `_detect_resume_point` (via `ResumeStrategy.detect_resume_point` in `src/prep/services/pipeline/resume.py`) must reject COMPLETE when the manifest exists but output is empty OR the manifest is a Phase 72C stub. Thread D is a small TypeScript addition to `GraphEnrichmentPipeline.tsx` rendering a `complete-but-empty` warning chip from already-available API data (no backend change).

**Tech stack:** Python 3.11 + pytest for B and C; TypeScript + (newly-installed) vitest for D. Both editing existing files plus one new test file each.

**Independence:** B can ship without C or D. C can ship without B (but B makes C's symptoms much less likely to recur). D can ship without B or C — it's pure UI defense-in-depth. **Recommended order: B first (it's the simplest and most pinned), then C (it's the upstream true cause), then D (UI net for future regressions).**

**Out of scope (still):** Thread A (§2k concurrency + work-loss). Soft-hold lifecycle audit (open question in `FINDING_reset-barrier-stuck-on-failed-finalize.md` §5.2). "Unstick" UI button (incidentally provided by Force Reset, lower priority).

---

## Pre-flight: what changed since v1

Five defects fixed in this v2:

| # | v1 mistake | v2 correction |
|---|---|---|
| D1 | Thread C fixed the UI rollup because I thought `provenance.state == "match"` meant "complete on disk." | `provenance.state` only compares model names (`src/prep/services/pipeline_provenance.py:184-191`). Thread C now targets the actual upstream cause: the resume detector's `manifest_size > 0 ⇒ COMPLETE` heuristic that misses empty outputs and stub manifests. |
| D2 | Thread B test imported `Event.PIPELINE_STARTED` / `Event.STAGE_STARTED`, which don't exist. | v2 uses `Event.START` (IDLE → RUNNING) and `Event.STAGE_COMPLETED` (advance stage); `Event.STAGE_FAILED` to drive the failure transition. Verified against `src/prep/services/pipeline/state_machine.py:112-191`. |
| D3 | Thread B fix touched only `_on_build_transition`'s FAILED branch; the Write-Guard-Blocked path (orch:2673) and three other STAGE_FAILED callsites bypass it. | v2 refactors to a single shared post-run hook (`_post_run_cleanup`) called from every terminal-transition site — success branch at `_advance_pipeline`, FAILED branch at `_on_build_transition`, Write-Guard-Blocked path, and the direct `STAGE_FAILED` calls at orch:1596/2837/2872 (inventoried in DG3). |
| D4 | Thread C TDD plan assumed vitest was already wired in `packages/ui`. It isn't. | v2's Thread D (the only UI thread now) includes "install vitest" as Task D1 before any test is authored. Thread C is now backend pytest, no vitest needed. |
| D5 | v1 described `enabled: false` as a config flag the user could toggle. | v2 acknowledges `enabled: false ≡ output_count == 0` (`src/prep/api/routers/pipeline.py:623, 652`). Thread D uses that directly as its warning trigger: `provenance.state == "match" && stage_count == 0 ⇒ render chip`. |

Three of those five corrections (D1, D3, D5) directly *reshape* what gets built. D2 and D4 are mechanical.

---

## Thread B — promote barrier-clear into a shared post-run hook  *[evidence: solid]*

### B-pre — read DG3 output first (recommended, not required)

If `EVIDENCE_failure-path-inventory.md` from DG3 has been authored, read it before B1. It enumerates every failure path; this proposal assumes the five we already know about (1596, 2673, 2737, 2837, 2872) but DG3 may surface a sixth. If DG3 hasn't run yet, proceed with the five known paths and treat any DG3 follow-up as a v3 amendment.

### B1 — write the failing tests (corrected enums)

**Files:**
- Create: `tests/test_phase145_barrier_clears_on_failure.py`

Same test file as v1, but with two corrections:

1. Imports use the real enum values (`Event.START`, not `Event.PIPELINE_STARTED`).
2. Two additional cases exercise the Write-Guard-Blocked path and the direct `STAGE_FAILED` path (lines 1596 / 2837 / 2872) so the new shared hook is covered from every entry point, not just `_on_build_transition`.

Concrete sketch (full test bodies authored at execution time, not in this draft):

```python
def test_finalize_failure_via_on_build_transition_clears_barrier(client, tmp_path):
    """Path A: BuildPhase.FAILED routed through _on_build_transition."""

def test_finalize_failure_via_write_guard_blocked_clears_barrier(client, tmp_path):
    """Path B: Write Guard exception inside the COMPLETED branch."""

def test_finalize_failure_via_direct_stage_failed_clears_barrier(client, tmp_path):
    """Path C: direct run.transition(Event.STAGE_FAILED, ...) calls at orch:1596/2837/2872."""

def test_deep_enrichment_failure_clears_scope_enrichment_barrier(client, tmp_path):
    """Scope='enrichment' boundary check."""

def test_fast_sync_failure_clears_scope_sync_barrier(client, tmp_path):
    """Scope='sync' boundary check."""
```

The shared fixture style follows `tests/test_scoped_full_reset_selfheal_race.py` (TestClient + `_add_project` + `_idx_dir` helpers).

**Why five tests, not two:** because the v2 fix is a shared hook, we want every entry point covered. If a future refactor accidentally bypasses the hook on one path, this catches it.

### B2 — author the shared cleanup hook

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py` (~30 lines)

Sketch (precise diff at execution time):

```python
def _post_run_cleanup(self, run: "PipelineGroupStateMachine", terminal: str) -> None:
    """Single hook invoked on every terminal pipeline transition.

    Called from every callsite that puts a run into COMPLETED, FAILED,
    or CANCELLED. Centralizes cleanup that historically lived only on
    the success branch and silently leaked on failure — most notably
    the reset_barrier clear (Phase 145 Thread B).

    Args:
        run: the state machine for the just-ended pipeline group.
        terminal: "completed", "failed", or "cancelled".
    """
    # Phase 145 Thread B: clear the scoped reset barrier on EVERY terminal
    # transition, not just success. See
    # docs/Phase145_Pipeline-UI-Reliability/FINDING_reset-barrier-stuck-on-failed-finalize.md.
    try:
        from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
        maybe_clear_scoped_barrier(run.project_id, completed_group=run.group)
    except Exception:
        logger.debug(
            "maybe_clear_scoped_barrier failed (non-fatal) for %s [%s]",
            run.project_id, terminal, exc_info=True,
        )
    # Future cleanup belongs here too — any cleanup that should fire on
    # both success AND failure paths.
```

Then replace the three success-branch callsites (orch:2118, 2152, 2166) with a single call to `self._post_run_cleanup(run, "completed")`. Add the same call after every failure-transition site enumerated in DG3 (at minimum: orch:2673 Write Guard, orch:2737 FAILED branch, orch:1596, orch:2837, orch:2872).

**Scrutiny check before execution:** verify that calling `maybe_clear_scoped_barrier` multiple times with the wrong group is a safe no-op. Existing test `test_scoped_full_reset_selfheal_race.py` should already cover this; if it doesn't, add a unit test.

### B3 — smoke against the live Applifier deadlock

Same as v1. Restart daemon. Confirm `.reset_barrier` removed after a forced finalize failure. Re-run the dashboard's Run button on Applifier; confirm the previous `PIPELINE_UP_TO_DATE` toast either changes (because Thread C is also landed) or stays consistent (because B alone doesn't fix the toast, only the barrier).

### B4 — verify against existing barrier tests

```bash
.venv/bin/pytest tests/test_scoped_full_reset.py \
                 tests/test_scoped_full_reset_selfheal_race.py \
                 tests/test_rebuild_sync_scope_chain.py \
                 tests/test_phase145_barrier_clears_on_failure.py -v
```

All must pass.

### B5 — commit

```
fix(pipeline): factor terminal cleanup into shared hook; clear barrier on failure

Phase 145 Thread B. maybe_clear_scoped_barrier was only called from
_advance_pipeline's success branch; every failure path leaked the
.reset_barrier dotfile and selfheal was gated forever with "awaiting
genuine finalize". Refactors three success-branch callsites + five
failure-path callsites into a single _post_run_cleanup hook so future
terminal-transition sites inherit the cleanup automatically.

Tests: tests/test_phase145_barrier_clears_on_failure.py (5 cases —
on_build_transition FAILED, write-guard-blocked, direct STAGE_FAILED,
scope=enrichment, scope=sync).
```

---

## Thread C — resume detector must reject COMPLETE on empty outputs / stub manifests  *[evidence: partial, needs DG2]*

### C-pre — read DG2 output before authoring tests

This thread is shaped by DG2's writeup of `ResumeStrategy.detect_resume_point`'s actual decision tree. The shape below is a *hypothesis* based on the journal evidence + the manifest_store.py code we've already read. If DG2 reveals a different structure (e.g., per-stage overrides, an output-presence check that exists but is bypassed for one stage), the test design changes.

**Do not author tests until DG2's `EVIDENCE_resume-detector-decision-tree.md` is in the corpus.**

### C-hypothesis — what the fix probably looks like (subject to DG2)

Current behavior (per journal evidence):

```python
# Pseudo-code reconstruction from journal:
# {"stage": "enrichment", "decision": "COMPLETE", "manifest_size": 690}
def detect_resume_point(project_id, stages, ...) -> int:
    for stage in stages:
        manifest_path = manifest_store.provenance_path(stage)
        if not manifest_path.exists():
            return stage.index  # missing → resume here
        if manifest_path.stat().st_size == 0:
            return stage.index  # empty manifest → resume here
        # COMPLETE: manifest exists with size > 0
    return len(stages)  # all_complete
```

Proposed behavior (under hypothesis — verify against DG2 first):

```python
def detect_resume_point(project_id, stages, ...) -> int:
    for stage in stages:
        manifest_path = manifest_store.provenance_path(stage)
        if not manifest_path.exists() or manifest_path.stat().st_size == 0:
            return stage.index
        # NEW: reject stub manifests as proof of completion (Phase 72C
        # restored manifests don't prove the stage ran)
        if manifest_store.is_stub_manifest(stage):
            return stage.index
        # NEW: for output-bearing stages, also verify the output file
        # has nonzero content. A manifest without output is not COMPLETE.
        output_path = STAGE_OUTPUT_FILE.get(stage)
        if output_path and not _output_has_content(idx_dir / output_path):
            return stage.index
    return len(stages)
```

`STAGE_OUTPUT_FILE` is a new constant mapping each stage to its output file (e.g., `EPISTEMIC → "trace_epistemic.jsonl"`, `CLUSTERING → "trace_modules.jsonl"`). Stages without a distinct output file (e.g., `STRUCTURAL`, which writes inline into the manifest) skip the output check.

### C1–C5 — TDD tasks (to be authored after DG2)

Sketch only. Full code blocks deferred until DG2 lands.

- **C1:** Write `tests/test_phase145_resume_detector_empty_output.py` with cases per stage (enrichment, clustering, deepening, deep_knowledge) for: manifest-present-output-missing, manifest-present-output-empty, manifest-is-stub, manifest-and-output-both-present.
- **C2:** Add the `STAGE_OUTPUT_FILE` constant and the output-check logic to `src/prep/services/pipeline/resume.py`. Skip the check for stages where output ≡ manifest.
- **C3:** Run C1 tests; confirm PASS.
- **C4:** Run existing pipeline tests (`tests/test_*resume*.py`, `tests/test_*pipeline*.py`) to confirm no regression — especially `test_scoped_full_reset_selfheal_race.py` which already exercises post-reset resume points.
- **C5:** Live smoke against Applifier: post-fix, `POST /pipeline/deep` should return `started=true` (not `PIPELINE_UP_TO_DATE`) when `trace_epistemic.jsonl` is empty.

### C6 — commit

```
fix(pipeline): resume detector rejects COMPLETE on empty outputs / stub manifests

Phase 145 Thread C. _detect_resume_point treated any manifest with
size > 0 as COMPLETE, which let Applifier sit in a state where every
deep_enrichment manifest existed (690 bytes) but the corresponding
trace_epistemic.jsonl was 0 bytes. The user clicked Run, the backend
returned PIPELINE_UP_TO_DATE, and the UI correctly showed "Not run"
— but the toast and the rendered rows contradicted each other.

Adds two predicates to detect_resume_point:
- reject Phase 72C stub manifests (already detectable via
  manifest_store.is_stub_manifest)
- require nonzero output file for stages that have one

Tests: tests/test_phase145_resume_detector_empty_output.py.
```

---

## Thread D — UI safety chip: "complete-per-manifest but produced 0 output"  *[evidence: solid, independent]*

This is a defense-in-depth net for a future regression of Thread C. It doesn't depend on B or C. It can ship alone, independently, even if neither B nor C ever lands.

### D1 — wire vitest into packages/ui

**Files:**
- Modify: `packages/ui/package.json`
- Modify: `turbo.json`
- Create: `packages/ui/vitest.config.ts`

```bash
cd packages/ui
npm install --save-dev vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom
```

Add `"test": "vitest run"` and `"test:watch": "vitest"` to `packages/ui/package.json` scripts. Add a `test` task to `turbo.json`:

```json
"test": {
  "dependsOn": ["^build"]
}
```

Then run `npx vitest run packages/ui/src/components/trace/__tests__/pipelineRollup.test.ts` and confirm the EXISTING dormant tests pass. If they don't, fix them before adding new tests (an old test failure shouldn't be smuggled in under a new task).

### D2 — failing test for the warning chip

**Files:**
- Create: `packages/ui/src/components/trace/__tests__/StageWarningChip.test.tsx`

The chip behavior:

- If `stage.provenance.state == "match"` AND the stage's data-presence count is 0 (e.g., `enrichment.enriched_nodes == 0`, `clustering.module_count == 0`), render a small amber chip labeled `"complete-per-manifest, 0 output"` with a tooltip linking the user to support docs.
- Otherwise render nothing.

The chip is purely informational. It does not change the row's primary state — that still comes from the existing `compute*State` helpers (which correctly render `'not_built'` when count is zero). The chip is an additional adornment.

### D3 — implement the chip

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (small addition near the row renderer, ~15 lines)

Define a `<StageWarningChip>` component locally or in `packages/ui/src/components/trace/StageWarningChip.tsx`. Add it to the row template wherever existing chips (provenance chip, model chip) live.

### D4 — visual smoke

Reload the dashboard against Applifier (assuming Thread C hasn't landed yet — Applifier is still in the broken state). Confirm the new chip appears next to each Deep Enrichment row.

### D5 — commit

```
feat(ui): add "complete-but-empty" warning chip to enrichment rows

Phase 145 Thread D. Defense-in-depth surface for the case where a
stage's manifest is on disk and the model matches
(provenance.state == "match") but the output count is zero. Today
this state is mostly invisible: the row shows "Not run" because
compute*State correctly checks output count, but the user can be
confused by a Run button that returns PIPELINE_UP_TO_DATE.

Wires up vitest for packages/ui along the way.

Tests: packages/ui/src/components/trace/__tests__/StageWarningChip.test.tsx.
```

---

## Risk register (read before scrutiny)

| # | Risk | Mitigation in this proposal |
|---|---|---|
| R1 | The shared `_post_run_cleanup` hook is called multiple times for the same run (e.g., once from `_advance_pipeline` and once from `_on_build_transition`). | `maybe_clear_scoped_barrier` is already idempotent (returns False if barrier scope doesn't match). Verified, and B1 test 5 will pin it. |
| R2 | Thread C's output-presence check makes `_detect_resume_point` slow because it stats output files for every stage on every call. | The check is cheap (a stat + size read). For pathological projects with very large outputs, this is still O(stages) syscalls — negligible. Worst case is sub-millisecond. |
| R3 | Thread C accidentally treats legitimately-empty outputs as "needs resume" — e.g., a tiny project where deep_enrichment really did produce zero rows because there's nothing to enrich. | The output-presence check should be "*if* the stage has an `output_file` AND the count of input candidates was > 0, *then* require nonzero output." This needs to be designed precisely in DG2's followup. Listed as an open question on the C-hypothesis stub above. |
| R4 | Thread D's chip is noisy — appears on legitimately-complete-but-empty rows. | Same as R3. The chip's trigger should match Thread C's check so they agree. If Thread C lands first, Thread D should only trigger when Thread C's resume detector also rejects COMPLETE on that stage — i.e., the chip surfaces *real* problems, not legitimate emptiness. |
| R5 | Refactoring three callsites into one hook (B2) accidentally drops a side-effect the original three callsites had. | Each of the three original callsites is just `try: maybe_clear_scoped_barrier(...); except Exception: logger.debug(...)`. Strict copy. R5 is "we should diff carefully" — low risk. |
| R6 | The vitest setup in D1 destabilizes an existing build because of conflicting dependency versions. | Install with `--save-dev` in `packages/ui` only; don't add to the root. Test in CI before merging. |
| R7 | DG2's evidence reveals that the resume detector has per-stage logic we don't yet know about, and Thread C's design needs a substantial revision. | Don't author Thread C tests/code until DG2 is in. Stop at C-hypothesis until then. |

---

## Open questions for the scrutiny pass

These are the questions the scrutiny step should explicitly answer before this v2 proposal is marked "ready":

1. Is `_post_run_cleanup` the right name for the new shared hook, or does it overlap with an existing pattern (`_finalize_run_metadata`)? Should we just *extend* `_finalize_run_metadata` and make it the canonical post-run hook for both success and failure?
2. Is the v2 v1-test parity correct? B1 should still cover everything B1 in v1 covered (scope=all + scope=enrichment), now with three more cases (Write Guard, direct STAGE_FAILED, scope=sync).
3. Does Thread C's `STAGE_OUTPUT_FILE` mapping have a natural home in `src/prep/services/pipeline/stages.py` (alongside `STAGE_BUILD_TYPE` and `STAGE_TASK_ID`), or somewhere else?
4. Does Thread D's chip belong inline in `GraphEnrichmentPipeline.tsx` or in its own component file? Existing trace chips (`ProvenanceChip.tsx`) live in their own files — match that pattern.
5. Should D1's vitest setup target `packages/ui` only, or should it be a workspace-wide thing in `turbo.json`? (Probably scoped — `src/prep/dashboard` already uses Vite and could benefit later, but that's not Phase 145 scope.)
6. Is the proposed sequencing (B → C → D) right, or should D ship first as a fast user-visible safety net while C waits for DG2?

---

## How to scrutinize this proposal

When a reviewer picks this up:

1. Verify R1–R7 are still accurate. Add anything missed.
2. Read DG2's `EVIDENCE_resume-detector-decision-tree.md` if it's landed; revise Thread C against its actual structure.
3. Read DG3's `EVIDENCE_failure-path-inventory.md` if it's landed; revise Thread B's failure-path list if a sixth path emerges.
4. Run each task's `Files: Create/Modify` line through `prep_impact` to confirm the file is what we think it is and the change radius is what we think it is.
5. For every command in the smoke sections, validate that the URL / port / project ID is still current.
6. If new defects are found, record them as D6, D7, … in a fresh banner at the top, and write v3.

The scrutiny output goes into the v2 file itself (as a `## Scrutiny pass — YYYY-MM-DD` section appended near the top) or into a separate `SCRUTINY_v2_threads-B-and-C.md` if the analysis is too large.

---

## Cross-references

- v1 (superseded): `PROPOSAL_threads-B-and-C-v1-barrier-and-rollup.md`
- Findings: `FINDING_reset-barrier-stuck-on-failed-finalize.md`, `FINDING_concurrency-undershoot-and-cross-project-work-loss.md`
- Diagnostic (prerequisite for Thread C): `DIAGNOSTIC_2026-06-15_resume-point-and-failure-paths.md`
- Code: `src/prep/services/pipeline/orchestrator.py:1596, 2080, 2118, 2152, 2166, 2673, 2737, 2837, 2872, 4787`; `src/prep/services/pipeline/resume.py`; `src/prep/services/pipeline_provenance.py:160-205`; `src/prep/services/pipeline/state_machine.py:112-191`; `src/prep/api/routers/pipeline.py:600-660`; `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505-600`.
