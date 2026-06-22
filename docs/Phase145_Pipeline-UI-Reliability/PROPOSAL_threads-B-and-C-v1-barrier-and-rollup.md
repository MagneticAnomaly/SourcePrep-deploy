# PROPOSAL v1 — Threads B (barrier auto-clear) + C (UI rollup drift)  *(superseded by v2)*

> **STATUS: DRAFT v1 — superseded by [`PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md) on 2026-06-15.** Kept in the Phase 145 corpus for context. The scrutiny pass that exposed defects D1–D5 is reproduced in this banner; the v2 proposal takes those into account. Read this v1 if you want to understand *what was wrong with the first attempt* — the defects teach the next reviewer what to verify before assuming. The evidence to fully validate v2's Thread C is being gathered in [`DIAGNOSTIC_2026-06-15_resume-point-and-failure-paths.md`](DIAGNOSTIC_2026-06-15_resume-point-and-failure-paths.md).
>
> **Why the parked plan is still worth reading** for an orchestrator picking this up: the *diagnosis* of the barrier-deadlock root cause is correct, the existing barrier-test pattern (`tests/test_phase145_*.py`) it cites is correct, and the daemon-restart smoke procedure carries over to the revised plan. The *implementation details* are what broke. Specifically:
>
> - **D1 — Thread C is misdiagnosed.** `provenance.state == "match"` only compares model names, not output presence (`src/prep/services/pipeline_provenance.py:184-191`). The UI rendering "Not run" on Applifier is honest — the real bug is upstream in `_detect_resume_point`, which treats `manifest_size > 0` as COMPLETE regardless of whether the stage produced output.
> - **D2 — Thread B test uses non-existent enums.** `Event.PIPELINE_STARTED` and `Event.STAGE_STARTED` don't exist; the real enum has `Event.START`, `Event.STAGE_COMPLETED`, `Event.STAGE_FAILED`. The test would `ImportError` on its first line.
> - **D3 — Thread B fix is too narrow.** `_on_build_transition`'s FAILED branch is one of at least four failure paths in `orchestrator.py` (also lines 1596, 2673 Write-Guard-Blocked, 2837, 2872). The Write-Guard path bypasses the FAILED branch entirely.
> - **D4 — packages/ui has no test runner wired.** No vitest in `package.json`, no `test` task in `turbo.json`. Thread C's TDD path would need vitest install + script + turbo task before the first test could run.
> - **D5 — `enabled: false` is computed from output count** (`src/prep/api/routers/pipeline.py:623, 652`), not config. The plan's framing of "UI reading the wrong field" is wrong; the field is honest.
>
> Do not delete this file. The defects are part of the Phase 145 corpus — they teach the next planner what to verify before assuming.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop a failed finalize from leaving `.reset_barrier` on disk forever (Thread B), and stop the Deep Enrichment rows from rendering "Not run" when the backend's per-stage `provenance.state == "match"` (Thread C). Net user effect: Applifier (and any future project in the same state) recovers from a failed finalize without manual `rm` of dotfiles or clicking Force Reset, and the UI stops contradicting the daemon.

**Architecture:** Two surgical, independent fixes plus their tests. Thread B is a Python orchestrator change — promote three existing `maybe_clear_scoped_barrier` calls out of success-only branches into the unified failure path at `_on_build_transition`. Thread C is a TypeScript change in `GraphEnrichmentPipeline.tsx` — when the backend says `provenance.state == "match"` for a stage, the per-stage `compute*State` functions must NOT return `'not_built'`. We pin both behaviors with regression tests before changing code, per the existing Phase 145 test convention (`tests/test_phase145_*.py`, `packages/ui/src/components/trace/__tests__/*.test.ts*`).

**Tech Stack:** Python 3.11 + pytest (backend), TypeScript + vitest (frontend, via the existing `__tests__` directory next to the component). Both editing existing files only — no new modules.

**Out of scope:** Thread A (concurrency undershoot + work loss on second start, §2k). That thread is a hypothesis list, not a pinned cause; it needs live evidence capture per `FINDING_concurrency-undershoot-and-cross-project-work-loss.md` §4 before a plan can be written. Land Threads B and C first; they reduce the blast radius of A (the trap is gone, the UI contradiction is gone) so when A's evidence comes in we can scope a clean fix without worrying about cascading failures.

---

## Scope check

Threads B and C are independent subsystems (Python orchestrator vs React component). Per the writing-plans skill they could be two plans. I'm keeping them in one document because:

1. Both come from the same user incident (Applifier on 2026-06-15). Splitting them risks one half landing without the other and leaving the user still confused.
2. Each thread is small (one file change + one test file) — a single plan stays readable.
3. The tasks are sequenced (B first because it's lower-risk and unblocks the user's immediate recovery flow). The plan reflects that order.

If the executing agent decides to break this into two PRs, that's fine — the tasks are labeled by thread.

---

## File structure

### Thread B — files

| File | Status | Responsibility |
|---|---|---|
| `src/prep/services/pipeline/orchestrator.py` | Modify (~30 lines) | Add a single barrier-clear call in the FAILED branch at `_on_build_transition` (around line 2772). Optionally factor the three existing success-branch calls into one helper. |
| `tests/test_phase145_barrier_clears_on_failure.py` | Create (~140 lines) | Regression test: simulate failed-finalize via the recovery primitives + the existing TestClient fixture pattern; assert `.reset_barrier` is removed when the run handler returns. |

### Thread C — files

| File | Status | Responsibility |
|---|---|---|
| `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | Modify (~5 small edits at `computeEpistemicState`, `computeModuleState`, `computeAtlasState`, `computeDeepeningState`, `computeDeepKnowledgeState`) | Add a "trust on-disk provenance" gate: when the API reports `provenance.state == "match"` for the stage, return `'complete'` instead of `'not_built'` from the cold-state checks. |
| `packages/ui/src/components/trace/__tests__/computeStageStates.test.ts` | Create (~120 lines) | Unit tests pinning the new behavior: a stage with `provenance.state == "match"` and `enabled: false` renders as `'complete'`, not `'not_built'`. |

---

## Sequencing rationale (read before starting tasks)

Thread B comes first because it's safer (one server-side change, well-pinned, has an established test pattern next to it). Thread C is a UI rollup change that needs care to avoid regressing the §2b "Deep Reasoning stuck" symptom — we want to make rows MORE accurate, not just "show complete more often." That's why Thread C's test fixture explicitly includes negative cases (`provenance.state == "drift"` must still render `'not_built'`) and runs after Thread B is merged.

Do not interleave the threads. Finish B, commit, run its test. Then start C.

---

## Thread B — Tasks

### Task B1: Lock down the existing barrier-clear behavior with a regression test

**Files:**
- Create: `tests/test_phase145_barrier_clears_on_failure.py`

This task only writes the failing test for the new behavior. We're not changing code yet. The test must FAIL on `main` and PASS after Task B2.

- [ ] **Step B1.1: Read the existing barrier test for the fixture/import pattern**

Read `tests/test_scoped_full_reset_selfheal_race.py` lines 1-100 to understand the `client`, `_add_project`, and `_idx_dir` helpers. The new test will reuse the same fixture style.

Note from the file: it uses `tests/conftest.py`'s `client` fixture (FastAPI TestClient) and a per-test `tmp_path`. It imports `read_reset_barrier`, `reset_barrier_active`, and `clear_reset_barrier` from `prep.services.pipeline.recovery`. The same conftest fixture is correct for this new test.

- [ ] **Step B1.2: Write the failing test**

Create `tests/test_phase145_barrier_clears_on_failure.py` with this content:

```python
"""Phase 145 Thread B regression — `.reset_barrier` must be cleared when a
group's terminal run ends in FAILED, not only on COMPLETED.

Before the fix, ``maybe_clear_scoped_barrier`` was only called from the
success branch of ``_advance_pipeline`` (orchestrator.py:2118, 2152,
2166). A finalize run that ended in FAILED — e.g. Applifier on
2026-06-15, ``Stage concepts failed: Dispatch paused on soft-hold`` —
left the barrier on disk indefinitely. Selfheal logged
``Selfheal skipped: reset barrier active — awaiting genuine finalize``
every ~10 minutes forever.

This test simulates the failed-finalize sequence directly via the
orchestrator's _on_build_transition (BuildPhase.FAILED) without
spinning up a real LLM. It asserts the barrier is gone when the
handler returns.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _add_project(client, repo_path: Path) -> str:
    """Match the helper pattern in test_scoped_full_reset_selfheal_race.py."""
    repo_path.mkdir(parents=True, exist_ok=True)
    (repo_path / "a.py").write_text("def f():\n    return 1\n")
    res = client.post("/projects", json={"name": "barrier-test", "path": str(repo_path)})
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]["project"]["id"]


def _idx_dir(client, project_id: str) -> Path:
    res = client.get(f"/projects/{project_id}")
    payload = res.json()["data"]["project"]
    return Path(payload["path"]) / ".sourceprep"


def test_finalize_failure_clears_reset_barrier(client, tmp_path):
    """A failed finalize must clear .reset_barrier (scope=all) before returning.

    Sequence:
      1. Write a scope=all barrier (simulates a full-reset in progress).
      2. Drive a finalize run to FAILED via the orchestrator's transition handler.
      3. Assert .reset_barrier no longer exists.
    """
    from prep.services.pipeline.recovery import (
        write_reset_barrier,
        reset_barrier_active,
    )

    pid = _add_project(client, tmp_path / "repo")
    idx = _idx_dir(client, pid)
    idx.mkdir(parents=True, exist_ok=True)

    # 1. Simulate a full-reset barrier — same shape as the Applifier dotfile.
    write_reset_barrier(pid, reason="full_reset", scope="all")
    assert reset_barrier_active(pid), "precondition: barrier must be active"
    barrier_path = idx / ".reset_barrier"
    assert barrier_path.is_file()

    # 2. Drive finalize to FAILED. The orchestrator's _on_build_transition
    #    is the unified post-run handler for both COMPLETED and FAILED.
    from prep.services.pipeline_orchestrator import pipeline_orchestrator
    from prep.services.pipeline.state_machine import (
        PipelineGroupStateMachine,
        Event,
    )
    from prep.services.build_orchestrator import BuildPhase, BuildType

    # Construct a finalize run that's about to fail on stage `concepts`.
    run = PipelineGroupStateMachine(
        project_id=pid,
        group="finalize",
        stages=["atlas", "rules", "concepts", "audit", "antibodies"],
    )
    # Advance state machine to RUNNING on `concepts` (the failing stage).
    run.transition(Event.PIPELINE_STARTED)
    run.transition(Event.STAGE_STARTED)  # atlas
    run.transition(Event.STAGE_COMPLETED)
    run.transition(Event.STAGE_STARTED)  # rules
    run.transition(Event.STAGE_COMPLETED)
    run.transition(Event.STAGE_STARTED)  # concepts
    # Register the run so _on_build_transition can find it
    with pipeline_orchestrator._lock:
        pipeline_orchestrator._runs[(pid, "finalize")] = run

    # 3. Dispatch a FAILED transition for concepts. This is the codepath
    #    that, before the fix, did not call maybe_clear_scoped_barrier.
    try:
        pipeline_orchestrator._on_build_transition(
            project_id=pid,
            build_type=BuildType.CONCEPTS,
            old_phase=BuildPhase.RUNNING,
            new_phase=BuildPhase.FAILED,
        )
    finally:
        with pipeline_orchestrator._lock:
            pipeline_orchestrator._runs.pop((pid, "finalize"), None)

    # 4. The fix: barrier MUST be cleared after a failed terminal group.
    assert not reset_barrier_active(pid), (
        ".reset_barrier should be cleared after a failed finalize; "
        f"file still exists at {barrier_path}"
    )
    assert not barrier_path.exists()


def test_deep_enrichment_failure_clears_scope_enrichment_barrier(client, tmp_path):
    """Mirror of the above for scope='enrichment' on a failed deep_enrichment."""
    from prep.services.pipeline.recovery import (
        write_reset_barrier,
        reset_barrier_active,
    )

    pid = _add_project(client, tmp_path / "repo")
    idx = _idx_dir(client, pid)
    idx.mkdir(parents=True, exist_ok=True)

    write_reset_barrier(pid, reason="enrichment_reset", scope="enrichment")
    assert reset_barrier_active(pid)

    from prep.services.pipeline_orchestrator import pipeline_orchestrator
    from prep.services.pipeline.state_machine import (
        PipelineGroupStateMachine,
        Event,
    )
    from prep.services.build_orchestrator import BuildPhase, BuildType

    run = PipelineGroupStateMachine(
        project_id=pid,
        group="deep_enrichment",
        stages=["enrichment", "group_reasoning", "clustering", "deepening", "deep_knowledge"],
    )
    run.transition(Event.PIPELINE_STARTED)
    run.transition(Event.STAGE_STARTED)  # enrichment

    with pipeline_orchestrator._lock:
        pipeline_orchestrator._runs[(pid, "deep_enrichment")] = run

    try:
        pipeline_orchestrator._on_build_transition(
            project_id=pid,
            build_type=BuildType.EPISTEMIC,
            old_phase=BuildPhase.RUNNING,
            new_phase=BuildPhase.FAILED,
        )
    finally:
        with pipeline_orchestrator._lock:
            pipeline_orchestrator._runs.pop((pid, "deep_enrichment"), None)

    assert not reset_barrier_active(pid), (
        ".reset_barrier scope=enrichment should be cleared after a failed "
        "deep_enrichment run; file still exists"
    )
```

- [ ] **Step B1.3: Run the new test and confirm it FAILS**

Run:
```bash
.venv/bin/pytest tests/test_phase145_barrier_clears_on_failure.py -v
```

Expected: both tests FAIL with an `AssertionError` like:
```
AssertionError: .reset_barrier should be cleared after a failed finalize; file still exists at /tmp/.../.sourceprep/.reset_barrier
```

If the test passes accidentally on `main`, something has changed since this plan was written (or the test setup isn't routing through the failure branch). Stop and investigate — do not skip to Task B2.

If the test errors out with `ImportError` on `BuildType.CONCEPTS` or similar, fix the import (the codepath may have moved). Concrete imports to verify:

```bash
.venv/bin/python -c "from prep.services.build_orchestrator import BuildType, BuildPhase; print([t.value for t in BuildType])"
.venv/bin/python -c "from prep.services.pipeline.state_machine import PipelineGroupStateMachine, Event; print(Event.__members__)"
.venv/bin/python -c "from prep.services.pipeline_orchestrator import pipeline_orchestrator; print(type(pipeline_orchestrator))"
```

Use whatever `BuildType` enum value maps to the concepts stage in this code's `STAGE_BUILD_TYPE` table — read `src/prep/services/pipeline/orchestrator.py` near `STAGE_BUILD_TYPE` if `CONCEPTS` is named differently.

- [ ] **Step B1.4: Commit the failing test**

```bash
git add tests/test_phase145_barrier_clears_on_failure.py
git commit -m "test(phase145): pin reset_barrier auto-clear on failed terminal group

Failing test reproducing Applifier 2026-06-15 deadlock: a failed
finalize leaves .reset_barrier on disk indefinitely because
maybe_clear_scoped_barrier is only called from the success branch.
Fix in next commit."
```

### Task B2: Add the barrier-clear call to the FAILED branch

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py` (one insertion at the FAILED-cleanup block, ~lines 2765-2774)

The success branch already has three callsites (lines 2118, 2152, 2166) that pass the correct `completed_group` argument. The cleanest fix is to add a single call in the FAILED cleanup block that passes the failed run's group. `maybe_clear_scoped_barrier` is already a no-op when the boundary doesn't match the barrier's scope, so over-calling is safe.

- [ ] **Step B2.1: Read the current FAILED branch to confirm the exact location**

```bash
sed -n '2760,2780p' src/prep/services/pipeline/orchestrator.py
```

You should see (modulo whitespace):

```python
            pfl = self._get_file_logger(project_id)
            if pfl:
                pfl.stage_end(stage.value, "failed", error=slot.error, data={
                    "duration": slot.duration_seconds,
                })
                pfl.end_run("failed", error=slot.error)
            self._journal_stage_failed(matching_run, stage, slot.error or "Unknown error")
            self._stop_heartbeat_timer(matching_run)
            self._release_group_models_via_sm(matching_run)
            return
```

If the lines have drifted, find them by searching for `pfl.end_run("failed"` — that anchor is unique to the FAILED block in this file.

- [ ] **Step B2.2: Insert the barrier-clear call before `return`**

Use Edit to replace the FAILED-cleanup block. The new block adds a Phase-145-tagged `maybe_clear_scoped_barrier` call after `_release_group_models_via_sm` and before `return`:

```python
            pfl = self._get_file_logger(project_id)
            if pfl:
                pfl.stage_end(stage.value, "failed", error=slot.error, data={
                    "duration": slot.duration_seconds,
                })
                pfl.end_run("failed", error=slot.error)
            self._journal_stage_failed(matching_run, stage, slot.error or "Unknown error")
            self._stop_heartbeat_timer(matching_run)
            self._release_group_models_via_sm(matching_run)

            # Phase 145 Thread B: clear the reset barrier on a failed terminal
            # group, same as the success branch does at _advance_pipeline.
            # Without this, .reset_barrier persists indefinitely and selfheal
            # is permanently gated ("awaiting genuine finalize") — see
            # docs/Phase145_Pipeline-UI-Reliability/FINDING_reset-barrier-stuck-on-failed-finalize.md.
            try:
                from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
                maybe_clear_scoped_barrier(project_id, completed_group=matching_run.group)
            except Exception:
                logger.debug(
                    "maybe_clear_scoped_barrier (failed-path) failed (non-fatal) for %s",
                    project_id, exc_info=True,
                )
            return
```

- [ ] **Step B2.3: Run the regression test and confirm it PASSES**

```bash
.venv/bin/pytest tests/test_phase145_barrier_clears_on_failure.py -v
```

Expected: both tests PASS.

- [ ] **Step B2.4: Run the existing barrier tests to confirm no regression**

```bash
.venv/bin/pytest tests/test_scoped_full_reset.py tests/test_scoped_full_reset_selfheal_race.py tests/test_rebuild_sync_scope_chain.py -v
```

Expected: all PASS. If anything fails, the new call is over-clearing — read the failure carefully. `maybe_clear_scoped_barrier(pid, completed_group=X)` is already guarded internally (it returns False without clearing if `X` doesn't match the barrier's scope boundary), so the only way to regress is if a test was relying on a barrier persisting through an UNRELATED group's failure. Examine the failing test before changing the production code.

- [ ] **Step B2.5: Commit the fix**

```bash
git add src/prep/services/pipeline/orchestrator.py
git commit -m "fix(pipeline): clear reset_barrier on failed terminal group, not only success

Phase 145 Thread B. maybe_clear_scoped_barrier was only called from the
success branch of _advance_pipeline; a failed finalize left
.reset_barrier on disk indefinitely and selfheal was gated forever with
'awaiting genuine finalize'. Adds the same call to _on_build_transition's
FAILED branch. Test: tests/test_phase145_barrier_clears_on_failure.py."
```

### Task B3: Smoke against the real Applifier deadlock

Manual verification that the fix actually unsticks the user's current Applifier state.

- [ ] **Step B3.1: Restart the daemon to load the new code**

`prep serve` has no hot-reload (see memory `feedback_restart_daemon_before_live_validation.md`).

```bash
scripts/dev.sh --kill
scripts/dev.sh
# wait for ":8400 ready" in the log
```

- [ ] **Step B3.2: Confirm `.reset_barrier` is still on disk before the smoke**

```bash
ls -la /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/.reset_barrier
cat /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/.reset_barrier
```

Expected: file exists, contents are `<ts>\nfull_reset\nall`.

- [ ] **Step B3.3: Trigger a finalize run that will fail the same way**

```bash
curl -s -X POST http://localhost:8400/projects/7cdea5e4-c94d-4612-be67-81597da3d6ec/pipeline/finalize -w "\nHTTP: %{http_code}\n"
```

Expected: a 200 with `started: true`, then within ~5 s the run fails the same way as before (soft-hold or whatever the current state surfaces).

- [ ] **Step B3.4: Confirm the barrier is now gone**

```bash
ls -la /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/.reset_barrier
```

Expected: `No such file or directory`. The fix worked end-to-end.

- [ ] **Step B3.5: Confirm the dashboard's Run button no longer hits the soft-hold trap**

Click Run on Deep Enrichment in the dashboard. The toast should change (or the run should actually start). If it's still `PIPELINE_UP_TO_DATE`, that's Thread C, not Thread B — proceed to Thread C with this state.

If something other than expected happens, capture the daemon log and revisit; do not commit anything new until B3 passes cleanly.

---

## Thread C — Tasks

Thread C is more subtle than B. The bug is that `computeEpistemicState` (and its siblings for `module`, `atlas`, `deepening`, `deep_knowledge`) decide between `'complete'` and `'not_built'` from per-stage `enabled` + `enriched_nodes` flags. When the manifest is on disk and current (`provenance.state == "match"`) but the runtime fields are 0 (e.g., after a `full_reset` that cleared transient counters but left the manifests), the UI returns `'not_built'`. We need to add a "trust on-disk truth" check.

### Task C1: Lock down `computeEpistemicState` (and siblings) behavior with a unit test

**Files:**
- Create: `packages/ui/src/components/trace/__tests__/computeStageStates.test.ts`

The functions `computeEpistemicState`, `computeModuleState`, `computeAtlasState`, `computeDeepeningState`, and `computeDeepKnowledgeState` (the latter likely exists with a similar name — read the file to confirm) are not currently exported. Step C1.1 below adds named exports so the test can import them directly. This is the minimum surface change.

- [ ] **Step C1.1: Export the per-stage compute functions**

Find the function declarations in `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`. Their current form is `function computeEpistemicState(...)`. Prepend `export ` to each of these five functions:

- `function computeEpistemicState` (~line 505)
- `function computeModuleState` (~line 535)
- `function computeAtlasState` (~line 554)
- `function computeDeepeningState` (~line 580)
- `function computeDeepKnowledgeState` (or whatever the deep_knowledge function is named — find by grep `grep -n "function compute" packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`).

For each, replace `function computeXxxState(` with `export function computeXxxState(` using Edit's old_string / new_string. Do not change anything else.

- [ ] **Step C1.2: Write the failing test**

Create `packages/ui/src/components/trace/__tests__/computeStageStates.test.ts` with this content:

```typescript
/**
 * Phase 145 Thread C regression — UI rollup must trust on-disk truth.
 *
 * Bug: on Applifier (2026-06-15), all five deep_enrichment rows rendered
 * as "Not run" while /projects/<id>/pipeline/status reported
 * provenance.state == "match" for every one of them. Cause: the
 * cold-state branches in compute*State return 'not_built' from
 * (!ep.enabled || ep.enriched_nodes === 0) without considering
 * provenance.state.
 *
 * Fix: when provenance.state === 'match', return 'complete' from the
 * cold-state branch. When provenance.state === 'drift', keep the
 * existing logic (the on-disk manifest is stale relative to inputs).
 * When provenance.state === 'missing', the manifest doesn't exist yet,
 * so 'not_built' is correct.
 */

import { describe, expect, it } from 'vitest';

import {
  computeEpistemicState,
  computeModuleState,
  computeAtlasState,
  computeDeepeningState,
} from '../GraphEnrichmentPipeline';

const TRACE_PRESENT = { exists: true, enabled: true } as const;
const CATALOGUE_DONE = { enabled: true, augmented_nodes: 100 } as any;
const PROVENANCE_MATCH = { state: 'match' } as any;
const PROVENANCE_DRIFT = { state: 'drift' } as any;
const PROVENANCE_MISSING = { state: 'missing' } as any;

describe('computeEpistemicState — Phase 145 Thread C', () => {
  it("returns 'complete' when provenance.state is 'match' even if runtime counters are zero", () => {
    const ep = {
      enabled: false,
      enriched_nodes: 0,
      avg_confidence: 0,
      provenance: PROVENANCE_MATCH,
    } as any;
    const state = computeEpistemicState(TRACE_PRESENT as any, CATALOGUE_DONE, ep);
    expect(state).toBe('complete');
  });

  it("returns 'not_built' when provenance.state is 'missing' (manifest absent)", () => {
    const ep = {
      enabled: false,
      enriched_nodes: 0,
      avg_confidence: 0,
      provenance: PROVENANCE_MISSING,
    } as any;
    const state = computeEpistemicState(TRACE_PRESENT as any, CATALOGUE_DONE, ep);
    expect(state).toBe('not_built');
  });

  it("keeps 'not_built' when provenance.state is 'drift' and runtime is zero", () => {
    // Drift means the manifest exists but inputs changed. Pre-fix this
    // would also be 'not_built' from the same branch. We preserve that.
    const ep = {
      enabled: false,
      enriched_nodes: 0,
      avg_confidence: 0,
      provenance: PROVENANCE_DRIFT,
    } as any;
    const state = computeEpistemicState(TRACE_PRESENT as any, CATALOGUE_DONE, ep);
    expect(state).toBe('not_built');
  });

  it("returns 'running' when the running flag is set, regardless of provenance", () => {
    const ep = {
      enabled: true,
      enriched_nodes: 0,
      avg_confidence: 0,
      provenance: PROVENANCE_MATCH,
    } as any;
    const state = computeEpistemicState(TRACE_PRESENT as any, CATALOGUE_DONE, ep, true);
    expect(state).toBe('running');
  });
});

describe('computeModuleState — Phase 145 Thread C', () => {
  it("returns 'complete' when provenance.state is 'match' even if module_count is zero", () => {
    const ep = { enabled: true, enriched_nodes: 100 } as any;
    const mod = {
      enabled: true,
      module_count: 0,
      running: false,
      provenance: PROVENANCE_MATCH,
    } as any;
    expect(computeModuleState(ep, mod)).toBe('complete');
  });

  it("returns 'not_built' when provenance.state is 'missing'", () => {
    const ep = { enabled: true, enriched_nodes: 100 } as any;
    const mod = { enabled: true, module_count: 0, provenance: PROVENANCE_MISSING } as any;
    expect(computeModuleState(ep, mod)).toBe('not_built');
  });
});

describe('computeAtlasState — Phase 145 Thread C', () => {
  it("returns 'complete' when provenance.state is 'match' even if atlas.exists is false in runtime view", () => {
    const ep = { enabled: true, enriched_nodes: 100 } as any;
    const mod = { enabled: true, module_count: 28 } as any;
    const atlas = { exists: false, provenance: PROVENANCE_MATCH } as any;
    expect(computeAtlasState(ep, mod, atlas)).toBe('complete');
  });
});

describe('computeDeepeningState — Phase 145 Thread C', () => {
  it("returns 'complete' when provenance.state is 'match' even if total_scored is zero", () => {
    const ep = { enabled: true, enriched_nodes: 100 } as any;
    const deep = {
      running: false,
      total_scored: 0,
      provenance: PROVENANCE_MATCH,
    } as any;
    expect(computeDeepeningState(ep, deep)).toBe('complete');
  });
});
```

- [ ] **Step C1.3: Run the test and confirm it FAILS**

```bash
cd packages/ui
npx vitest run src/components/trace/__tests__/computeStageStates.test.ts
```

Expected: most tests fail with `expected 'not_built' to be 'complete'` or similar. The `running` test should pass on its own (it's a control case).

If the test file errors with `Cannot find module './GraphEnrichmentPipeline'` or similar, fix the import path. If it errors with `computeEpistemicState is not a function`, you missed the `export` keyword in Step C1.1.

If vitest itself isn't wired up in `packages/ui` (check `package.json` for a `test` script — note that as of writing the package.json has no `test` script), add one before running:

```bash
# In packages/ui/package.json, under "scripts", add:
#   "test": "vitest run",
#   "test:watch": "vitest"
# Then ensure vitest is installed:
npm install --save-dev vitest @vitest/ui
```

(If the existing `__tests__/pipelineRollup.test.ts` already runs under some test command, prefer reusing that setup — read its top of file for the import shape and re-run with the same command. Don't introduce a second test runner.)

- [ ] **Step C1.4: Commit the failing test + exports**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx \
        packages/ui/src/components/trace/__tests__/computeStageStates.test.ts \
        packages/ui/package.json  # only if you added the test script
git commit -m "test(phase145-ui): pin compute*State 'trust provenance.match' contract

Failing test reproducing Applifier 2026-06-15 drift: deep_enrichment
rows render as 'Not run' while backend's provenance.state == 'match'.
Exports the compute*State helpers from GraphEnrichmentPipeline.tsx so
they can be tested directly. Fix in next commit."
```

### Task C2: Make the compute*State functions trust `provenance.state == "match"`

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`

For each of the five `compute*State` functions, add a short circuit: before the existing cold-state branches that return `'not_built'`/`'disabled'`, check whether the per-stage status payload carries `provenance.state === 'match'`. If so, return `'complete'`. The functions already accept the per-stage status objects as parameters (the test in C1 confirmed this).

- [ ] **Step C2.1: Add a small helper at the top of GraphEnrichmentPipeline.tsx**

Find the existing helper section near the top of the file (just above `computeEpistemicState`, around line 500). Insert:

```typescript
/**
 * Phase 145 Thread C: trust on-disk truth.
 *
 * When the backend reports provenance.state === 'match', the manifest
 * for this stage is on disk and current with the input fingerprint.
 * That's a stronger signal than runtime counters (which can be 0 right
 * after a daemon restart, after a full_reset that cleared transient
 * state, or during a partial reset). Return true to short-circuit the
 * cold-state branches that would otherwise render 'not_built'.
 */
function provenanceSaysComplete(stage: { provenance?: { state?: string } } | undefined): boolean {
  return stage?.provenance?.state === 'match';
}
```

- [ ] **Step C2.2: Use the helper in computeEpistemicState**

In `computeEpistemicState` (around line 505), insert the provenance check immediately after the running-flag checks and before the `if (!trace.exists) return 'disabled';` line. Existing code:

```typescript
  // SSE flags as forward-progression hint (only when API doesn't claim this stage is running)
  if (clusterRunning || atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete';
  // Cold state checks
  if (!trace.exists) return 'disabled';
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';
  if (!ep || !ep.enabled) return 'not_built';
  if (ep.enriched_nodes === 0) return 'not_built';
```

New code (one inserted line, marked):

```typescript
  // SSE flags as forward-progression hint (only when API doesn't claim this stage is running)
  if (clusterRunning || atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete';
  // Phase 145 Thread C: trust on-disk truth before falling into cold-state branches.
  if (provenanceSaysComplete(ep)) return 'complete';
  // Cold state checks
  if (!trace.exists) return 'disabled';
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';
  if (!ep || !ep.enabled) return 'not_built';
  if (ep.enriched_nodes === 0) return 'not_built';
```

- [ ] **Step C2.3: Apply the same pattern to computeModuleState**

In `computeModuleState` (around line 535), insert after the running-flag checks:

```typescript
  if (atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete';
  // Phase 145 Thread C: trust on-disk truth.
  if (provenanceSaysComplete(mod)) return 'complete';
  // Cold state checks
  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
```

- [ ] **Step C2.4: Apply to computeAtlasState**

In `computeAtlasState` (around line 554), insert after the running-flag checks:

```typescript
  if (deepeningRunning || deepKnowledgeBuilding) return 'complete';
  // Phase 145 Thread C: trust on-disk truth.
  if (provenanceSaysComplete(atlas)) return 'complete';
  // Cold state checks
  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
```

- [ ] **Step C2.5: Apply to computeDeepeningState**

In `computeDeepeningState` (around line 580), insert after the running-flag checks:

```typescript
  if (deepKnowledgeBuilding) return 'complete';
  // Phase 145 Thread C: trust on-disk truth.
  if (provenanceSaysComplete(deep)) return 'complete';
```

- [ ] **Step C2.6: Apply to computeDeepKnowledgeState (or whichever function handles deep_knowledge)**

Find the function with grep:
```bash
grep -n "function compute" packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
```

Find the one that returns the state for the `deep_knowledge` stage. Insert the same pattern: after running-flag checks, before cold-state branches:

```typescript
  // Phase 145 Thread C: trust on-disk truth.
  if (provenanceSaysComplete(dk)) return 'complete';
```

(replace `dk` with whatever the function's parameter name is for the deep_knowledge status object.)

- [ ] **Step C2.7: Run the C1 test and confirm PASS**

```bash
cd packages/ui
npx vitest run src/components/trace/__tests__/computeStageStates.test.ts
```

Expected: all tests PASS.

- [ ] **Step C2.8: Run the existing UI tests to confirm no regression**

```bash
cd packages/ui
npx vitest run
```

Expected: all existing tests in `__tests__/` pass (BarrierIndicator, ProvenanceChip, RebuildDropdown, RebuildingRow, RecoverStagePanel, pipelineRollup, rebuildProgress). Pay particular attention to `pipelineRollup.test.ts` — the group rollup reads per-stage `state`, so any per-stage compute change can shift a group's rollup.

If `pipelineRollup` regresses, read the failing case carefully: is the test asserting a behavior that the user actually wants to keep? (E.g. "all stages disabled → group disabled" — yes, keep.) Or is it pinning a stale assumption that this fix is correcting? (E.g. "stage with no runtime counters → not_built" — that's exactly the assumption we're loosening.) Update those tests to match the new, more-correct behavior, citing this plan in the commit message.

- [ ] **Step C2.9: Typecheck**

```bash
cd packages/ui
npm run typecheck
```

Expected: no errors. If TypeScript complains that `provenance` is not on the stage status type, widen the helper's type signature (it already uses `?.` chaining, so the runtime is fine — this is purely a type-side fix).

- [ ] **Step C2.10: Commit the fix**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "fix(ui-pipeline): per-stage rollup trusts provenance.state=='match'

Phase 145 Thread C. compute*State helpers in GraphEnrichmentPipeline
returned 'not_built' when runtime counters were zero, even when the
backend reported provenance.state == 'match' (manifest on disk and
current). Adds a provenanceSaysComplete() short-circuit before each
function's cold-state branches. Fixes the Applifier 2026-06-15 toast
where Deep Enrichment rows rendered 'Not run' while the daemon refused
to start a run because all stages were complete on disk. Test:
packages/ui/src/components/trace/__tests__/computeStageStates.test.ts."
```

### Task C3: Smoke against the dashboard

- [ ] **Step C3.1: Rebuild the UI bundle**

```bash
cd packages/ui
npm run build
```

Expected: clean build. If the dashboard imports `@prep/ui` from the workspace package, the rebuild will pick up the new behavior; if it imports from source via Vite alias (check `src/prep/dashboard/vite.config.ts`), no rebuild needed.

- [ ] **Step C3.2: Reload the dashboard and visit Applifier**

In Chrome, hard-refresh `http://localhost:5174`. Click into Applifier. Read each Deep Enrichment row's state.

Expected: rows that the backend reports as `provenance.state == "match"` now render with the green check / "complete" state, not "Not run" / empty circle. Overall Health should reflect more than 5/15 complete (the exact number depends on how many stages on disk are `match`).

- [ ] **Step C3.3: Click Run on Deep Enrichment**

Expected: one of two things.
- If the orchestrator's `run_deep_enrichment()` returns the same `started=false → PIPELINE_UP_TO_DATE`, the toast still fires but is now CONSISTENT with the UI (which now shows complete). The user is no longer confused; they're being told "nothing to do, the rows you see all-green are correct."
- If we want the Run button to do something user-visible even when stages are up-to-date (e.g., trigger a force-rebuild), that's a separate UX decision — out of scope for this plan. File a follow-up issue if you think it's worth doing.

- [ ] **Step C3.4: Drift control — confirm 'drift' rows still render correctly**

Find a project whose backend reports `provenance.state == "drift"` on at least one stage (look for `"chip_text"` non-null in `/projects/<id>/pipeline/status`). Reload that project's panel. Confirm the drifted stage does NOT render as `'complete'` — it should be `'not_built'`, `'stale'`, or whichever state matches its actual runtime data. The fix should only apply to `'match'`, not `'drift'` or `'missing'`.

If no project currently has a drift stage, skip C3.4 and document it as "not exercised on this smoke — covered by the C1 unit test `keeps 'not_built' when provenance.state is 'drift'`."

---

## Self-review (run before declaring the plan complete)

**Spec coverage check:**

| Spec requirement | Task | Note |
|---|---|---|
| Move `maybe_clear_scoped_barrier` out of success-only branch (Thread B) | B2 | Promoted to FAILED branch via `_on_build_transition`. |
| Pin behavior with regression test (Thread B) | B1 | Two tests: scope=all + scope=enrichment. |
| Confirm fix end-to-end against real Applifier (Thread B) | B3 | Manual smoke; the daemon restart is gated. |
| Audit soft-hold lifecycle (Thread B item 2 in finding) | — | **NOT in this plan.** Soft-hold audit is open work in §5 of the finding; needs evidence from §6 first. |
| "Unstick" UI affordance (Thread B item 3 in finding) | — | **NOT in this plan.** Force Reset already calls `clear_reset_barrier` (`pipeline.py:244-247`); with Thread B landed it's redundant. A more discoverable affordance can be a follow-up. |
| UI rollup reads `provenance.state` (Thread C) | C1, C2 | Five `compute*State` helpers updated; helper isolated for clarity. |
| Pin UI behavior with unit test (Thread C) | C1 | Vitest, exports added as the minimum touchpoint. |
| Confirm fix in real dashboard (Thread C) | C3 | Smoke + drift control. |
| Concurrency undershoot + work loss (Thread A) | — | **NOT in this plan, by design.** §2k is hypothesis-only; needs evidence capture first. |

**Placeholder scan:** No "TODO", "TBD", "implement later", "similar to Task N". Every code step contains the actual code.

**Type consistency:** All five `compute*State` functions use the same helper `provenanceSaysComplete()`. The helper's parameter is the stage status object (whatever the per-function name — `ep`, `mod`, `atlas`, `deep`, `dk`) which all already have an optional `provenance.state` field per the API response. Tests in C1 import the functions directly from `GraphEnrichmentPipeline.tsx`, matching the exports added in C1.1.

**Sequence:** B before C. Within B: B1 (red) → B2 (green) → B3 (smoke). Within C: C1 (red) → C2 (green) → C3 (smoke). Commits between every test/fix pair, matching the writing-plans skill's frequent-commits guidance.

---

## Execution Handoff

Plan complete and saved to `docs/Phase145_Pipeline-UI-Reliability/PLAN_threads-B-and-C-barrier-and-rollup.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Best for this plan because Thread B and Thread C are independent reviewable units.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints. Best if you want to watch the implementation happen and intervene quickly between B and C.

Which approach?
