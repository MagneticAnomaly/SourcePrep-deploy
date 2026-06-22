# Phase 145 Finding — `HoldPausedError` mis-classified as hard fail + exclusive-toggle leaks inbound swarm holds

**Status:** Open. **Both root causes pinned to file:line.** Partially answers OQ#2 of `FINDING_reset-barrier-stuck-on-failed-finalize.md`.
**Found:** 2026-06-22, session-end handoff. Live repro on Applifier (`7cdea5e4-c94d-4612-be67-81597da3d6ec`).
**Severity:** Medium-High. Two independent gaps in the Phase 127 soft-hold lifecycle. Together they explain why a transient swarm contention silently fails a stage and why the user-facing "exclusive" priority toggle does not actually drain stale holds.
**Repro project:** Applifier, same conditions as parent finding — three projects (SourcePrep, Deep-Live-Cam, Applifier) running deep_enrichment concurrently, one of them opening a swarm window during another's `group_reasoning`.

---

## 1. What this finding adds

`FINDING_reset-barrier-stuck-on-failed-finalize.md` pinned the **downstream** root cause (barrier never auto-clears when the terminal group fails) and left OQ#2 open:

> *"What set the soft-hold, and why didn't it clear?"*

This finding answers OQ#2 with two distinct root causes:

| ID | Root cause | Code location | What it explains |
|---|---|---|---|
| **HC-1** | `HoldPausedError` falls into the generic `except Exception` and is marked `BuildPhase.FAILED` | `src/prep/services/build_orchestrator.py:402-426` | Why a transient soft-hold (which the docstring says is "pause, checkpoint, retry") becomes a permanent stage failure that locks the state machine into `running → failed`. |
| **HC-2** | Setting a project to `exclusive` priority clears only its own *outbound* exclusive holds; inbound holds (set BY a sibling, reason=`swarm` or `exclusive`) targeting the newly-exclusive project are NOT cleared | `src/prep/services/pipeline/scheduler.py:692-706` | Why the user's "I made it exclusive in the queue and it didn't actually become exclusive" symptom is real: the toggle leaves orphan swarm-holds ON the project that the toggle is supposed to liberate. |

These are independent. HC-1 turns a transient signal into a hard failure regardless of why the hold was set. HC-2 explains how a hold can persist on a project even after the user has explicitly elevated it.

## 2. Root cause HC-1 — `HoldPausedError` misclassified

### 2.1 The contract (per `holds.py:47-61`)

```python
class HoldPausedError(Exception):
    """Raised when an LLM dispatch is paused due to a soft-hold.

    Callers should catch this at a run-loop boundary and treat it as
    'pause, checkpoint, retry on next run' — NOT as a permanent failure.
    """
```

The Phase 127 contract is explicit: this is a transient signal, not a failure mode. It is raised when a project tries to dispatch against a (project, endpoint) pair that another project has soft-held (swarm window owner, exclusive-priority owner, or admin manual hold).

### 2.2 The implementation (`build_orchestrator.py:402-426`)

```python
try:
    result = worker(slot, progress_cb)
    ...
except PipelinePausedError:
    # → handled as paused (resumable)
    slot.phase = BuildPhase.FAILED  # repurposed; cancel_token.is_pause distinguishes
    slot.error = "Paused by user"

except PipelineCancelledError:
    # → handled as cancelled (no further work)
    ...

except Exception as e:
    # → HARD FAIL. HoldPausedError lands here.
    logger.exception("Build failed: %s/%s", project_id, build_type.value)
    slot.phase = BuildPhase.FAILED
    slot.error = str(e)
    self._notify(...)
```

There is no `except HoldPausedError` branch. The exception inherits from `Exception`, so it falls through to the catch-all. The state machine then transitions `running → failed` (per `state_machine.py:94-200`) and the run is considered terminal.

### 2.3 Why this is the right diagnosis (live repro from this session)

From `.sourceprep/logs/pipeline_20260612_182813.log`:

```
14:28:49 WARNING acquire failed on cloud:default_ollama with no other contenders;
                  forcing slot reset to break stall
14:28:49 ERROR   acquire still failing after force-reset;
                  node cloud:default_ollama may be misconfigured
14:28:49 INFO    Group reasoning: scheduler did not grant swarm window
                  (another stage owns it or it failed to open) —
                  falling back to sequential dispatch
14:28:50 ERROR   Build failed: 7cdea5e4-…/group_reasoning
    raise HoldPausedError(project_id or "<unset>", endpoint_id)
prep.services.pipeline.holds.HoldPausedError: Dispatch paused on soft-hold
    (project='7cdea5e4-…', endpoint='cloud:default_ollama')
14:28:50 INFO    Pipeline 7cdea5e4-…/deep_enrichment: running → failed
                  (event=stage_failed, stage_idx=1)
```

The exception originates from `holds.py:103` (`raise_hold_paused_for_llm`). The orchestrator catches it via the generic handler at `build_orchestrator.py:417` and marks the stage FAILED.

Independent evidence: this is the **same** error already cited in §3 step 5 of `FINDING_reset-barrier-stuck-on-failed-finalize.md` (2026-06-15 incident, stage `concepts` instead of `group_reasoning`). Repeated across stages and weeks against the same project — not a fluke.

### 2.4 Correct behavior

Per the docstring, the error should be:
1. Caught explicitly (not in `except Exception`)
2. Treated more like `PipelinePausedError` than like a real failure — checkpoint state, mark the run for retry-on-next-tick, don't transition `running → failed`
3. Logged at INFO/WARNING (not as a stack-trace exception) — it's a backpressure signal, not a bug

This is a 4–6 line patch. Belongs in a `PROPOSAL_` only after the broader question of "how does the orchestrator distinguish transient backpressure from permanent failure" is settled — that question reaches into §2o and §2p as well.

## 3. Root cause HC-2 — Exclusive-toggle doesn't clear inbound holds

### 3.1 The current implementation (`scheduler.py:692-706`)

```python
if level == "exclusive":
    # Clear any stale exclusive holds we previously set (e.g.
    # from a prior exclusive window) so the new set is canonical.
    self._clear_holds_set_by_with_reason(project_id, "exclusive")
    for nid, slot in self._slots.items():
        if nid == self._EMBEDDING_NODE_ID:
            continue
        for other_pid in slot.active_stages:
            if other_pid != project_id:
                self._holds[
                    HoldKey(project_id=other_pid, endpoint_id=nid)
                ] = HoldEntry(
                    reason="exclusive",
                    set_by_project=project_id,
                )
```

The clear filter is **`set_by_project == project_id AND reason == "exclusive"`** — i.e. only holds *this project itself stamped previously while exclusive*. It does NOT clear:

- Inbound holds where `set_by_project == sibling AND reason == "swarm"` targeting `project_id`
- Inbound holds where `set_by_project == sibling AND reason == "exclusive"` targeting `project_id`

### 3.2 Why this is wrong (the user's stated symptom)

User report this session:

> *"the current bug you are tracking is related to me changing the setting on the exclusive in the queue and it not really being exclusive"*

Concrete sequence:
1. SourcePrep is running its `group_reasoning` stage. The scheduler opens a swarm window owned by SourcePrep.
2. The window-open path (`scheduler.py:1858`) stamps a hold on every other active project for every endpoint in the window's endpoint_set. Applifier gets `HoldKey(project_id=7cdea5e4, endpoint_id=cloud:default_ollama)` with `set_by_project=SourcePrep, reason=swarm`.
3. SourcePrep's window closes. The `close_swarm_window` path (`scheduler.py:1894-1896`) calls `_clear_holds_set_by_with_reason(SourcePrep, "swarm")` — clears the hold correctly.

But if step 3 either *doesn't fire cleanly* or *the user toggles Applifier to exclusive in the gap between step 2 and step 3*, the hold persists. The user's intuition that "making it exclusive should liberate it" is correct in spirit. The code does not implement that.

### 3.3 The contract gap

A project at `exclusive` priority is, by user-facing definition, the project that should be *un-held* on every endpoint. The implementation only stamps holds outbound (correct) and clears its own past outbound holds (correct), but never sweeps inbound holds targeting itself (gap).

The fix conceptually: when `project_id` is set to `exclusive`, in addition to the existing outbound-stamp loop, also:

```python
# Clear any hold whose KEY targets us, regardless of who set it.
# We are now exclusive — no other project's claim over us is valid.
to_clear = [
    k for k in self._holds.keys()
    if k.project_id == project_id
]
for k in to_clear:
    del self._holds[k]
```

5 lines, placed between line 695 (existing canonical-reset of own outbound exclusive holds) and line 696 (outbound-stamp loop).

### 3.4 Why `sweep_stale_holds` doesn't save us today

`scheduler.py:871-915` has a `sweep_stale_holds(grace_s=300)` that clears orphan holds whose backing state is gone AND whose age exceeds `drain_timeout_seconds + grace_s` (= 900 s default). This is a safety net for the case where `close_swarm_window` never fires. It is NOT a substitute for HC-2's missing semantics — the user expects the exclusive toggle to be immediate, not "eventual within 15 minutes." Also, `sweep_stale_holds` is not wired to any background scheduler; it relies on callers invoking it (e.g., during slot acquire). The sweep path is opportunistic, not periodic.

## 4. How this answers OQ#2 of FINDING_reset-barrier-stuck-on-failed-finalize.md

> *"What set the soft-hold, and why didn't it clear?"*

**Set by:** A sibling project's swarm window opening (`scheduler.py:1858`) when that sibling's `group_reasoning` / `clustering` / `atlas` / `concepts` / `audit` stage acquired the swarm node. Holds are stamped on every *other* active project on every endpoint in `endpoint_set`.

**Why it didn't clear:** Two failure modes, both real:
- **Path A** — The owning swarm window never called `close_swarm_window` cleanly (e.g., daemon stalled, crashed, or the owner project itself failed). Sweep_stale_holds would eventually catch it but only after 900 s and only if a slot-acquire happens to invoke it.
- **Path B** — The user toggled the held project to `exclusive` expecting that to liberate it (HC-2). It did not. The hold persisted, the next stage tried to acquire, hit the hold, raised `HoldPausedError`, was caught by the generic catch-all (HC-1), and the stage was marked failed.

This converts OQ#2 from open hypothesis to pinned cause-pair. The remaining question is **Path A's** root cause: when *exactly* does `close_swarm_window` not fire? That ties to §2k (concurrency undershoot) and is a separable thread.

## 5. Concrete fixes (sketches, not yet proposals)

Both fixes are small and independent. Both should land in a coordinated pass (Fable scope) rather than whack-a-mole, per the phase's working principles.

### HC-1 patch sketch (build_orchestrator.py)

Insert between line 412 (existing `PipelineCancelledError` handler) and line 417 (catch-all):

```python
except HoldPausedError as e:
    # Phase 127 contract: transient backpressure, not a hard failure.
    # Mark the run as soft-paused so it can be retried on next tick
    # rather than being recorded as a permanent stage failure.
    logger.info(
        "Build held by soft-hold: %s/%s (%s) — will retry",
        project_id, build_type.value, e,
    )
    with self._lock:
        if slot.phase == BuildPhase.FAILED:
            return
        old_phase = slot.phase
        slot.phase = BuildPhase.HELD  # or reuse PAUSED — see open question
        slot.finished_at = time.time()
        slot.error = None  # not an error
    self._notify(project_id, build_type, old_phase, slot.phase)
```

**Open question:** introduce a new `BuildPhase.HELD`, or reuse `BuildPhase.PAUSED` (which already has a non-error semantic)? `HELD` makes the cause visible to the UI; `PAUSED` is one fewer concept. Slight preference for `HELD` because the user-facing surface should distinguish "user paused" from "system back-pressured."

### HC-2 patch sketch (scheduler.py)

Insert at line 696 (immediately after the existing `_clear_holds_set_by_with_reason(project_id, "exclusive")` line):

```python
# Phase 127: when a project becomes exclusive, no other project's
# claim over it is valid. Sweep ANY hold whose key targets us,
# regardless of set_by_project / reason. Without this, a swarm
# hold stamped on us moments before we became exclusive will
# silently block our next dispatch — surfacing as the user
# symptom "exclusive doesn't actually become exclusive."
inbound_to_clear = [
    k for k in self._holds.keys()
    if k.project_id == project_id
]
for k in inbound_to_clear:
    del self._holds[k]
```

This sits AFTER the outbound-clear (existing line 695) so the symmetry reads cleanly: "first, drop any exclusive holds we previously set; second, drop any holds targeting us; third, stamp new holds on the projects we're now exclusive over."

## 6. Test coverage required before either patch ships

Per phase principles, both fixes need TDD coverage. Sketch:

- **HC-1 test** — drive `build_orchestrator._run_worker` with a worker that raises `HoldPausedError`. Assert phase transitions to HELD (or PAUSED), not FAILED. Assert error is None. Assert the listener is notified with the held phase.
- **HC-2 test** — pre-populate `_holds` with a swarm-set hold targeting project X. Call `set_priority(X, "exclusive")`. Assert the inbound hold is gone. Add a second hold set by a DIFFERENT project still targeting X; assert that's also gone. Add an outbound hold set BY X for reason swarm; assert that is NOT clobbered (it lives on the OTHER project's key and should remain).

## 7. Cross-references

- **Parent finding** — `FINDING_reset-barrier-stuck-on-failed-finalize.md` §5 OQ#2 ("What set the soft-hold, and why didn't it clear?") — this finding answers Path B of that question.
- **Sibling finding** — `FINDING_two-project-incremental-blocked-during-swarm.md` §2p — likely shares root cause HC-1 (the held second project's eventual `HoldPausedError` is misclassified). Confirm by checking the failure mode logged at the second project's stage termination.
- **Sibling finding** — `FINDING_concurrency-undershoot-and-cross-project-work-loss.md` §2k — the contention scenario that produces the swarm-window-set hold in the first place. Fixing §2k would reduce frequency but not eliminate either HC-1 or HC-2.
- **Phase 127 design** — `src/prep/services/pipeline/holds.py:1-13` is the canonical statement of the soft-hold contract. HC-1 and HC-2 are both violations of that contract.
- **Live evidence** — `pipeline_20260612_182813.log` lines documenting the 14:28:49 → 14:28:50 acquire-fail → force-reset → HoldPausedError → stage_failed chain.

## 8. Severity / blast radius

- **User-visible:** The failed stage triggers the parent finding's downstream behavior (barrier never auto-clears, UI rollup misleads, Force Reset is the only recovery). Visible weekly per the session log.
- **Data integrity:** No corruption. Stages that hit this are no-ops (hold raised before any disk write).
- **Coupled fixes:** HC-1 is independent. HC-2 partially depends on the broader question of whether `set_priority` should be the canonical authority for hold clearance, or whether `sweep_stale_holds` should be periodically scheduled instead. Both make the system more robust; the right choice depends on whether we want "user toggle is immediate" or "system self-heals eventually."

## 9. Session handoff context

This finding was authored 2026-06-22 at session end. The conversation that produced it began as a "why isn't my rebuild rebuilding?" diagnosis on Applifier, traced through:

- Daemon-wide orchestrator-lock wedge on `/pipeline/rebuild` and `/pipeline/rebuild/stop` (status endpoint still responded due to 2-3 s cache) — likely the same daemon-stall symptom as `FINDING_daemon-stall-and-frontend-lockup.md` §2m, not separately documented here.
- Per-project pipeline log `.sourceprep/logs/pipeline_<ts>.log` is the authoritative source — `~/.local/share/sourceprep/logs/` does NOT contain a daemon-wide application log, only the `swarm/` subdirectory. Future diagnosis should always read the per-project log first.
- 13 stale `.f67_pending` files on Applifier index, dating Jun 10–11, with no auto-cleanup hook on successful stage completion. Worth a separate finding if not already filed.
- `knowledge_manifest.json` had only a `.f67_pending` and no live counterpart — possible F-67 gap, also worth a separate finding.

Both `.f67_pending` observations may already be subsumed by §2x findings in this directory — quick scan suggests no, but did not exhaustively check. The 25-finding corpus is mature and well-indexed; consult README.md §2 catalog first.
