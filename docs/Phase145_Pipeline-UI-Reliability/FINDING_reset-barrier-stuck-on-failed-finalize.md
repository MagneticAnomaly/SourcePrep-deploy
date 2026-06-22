# Phase 145 Finding — Reset barrier never clears when finalize fails (Applifier deadlock; user-visible only via UI drift + Force-Reset toast)

**Status:** Open. Root cause **pinned to a specific code path**.
**Found:** 2026-06-15, follow-on to §2k (`FINDING_concurrency-undershoot-and-cross-project-work-loss.md`). Screenshot confirms the toast wording — see §1.
**Severity:** Medium-High. The user is not strictly trapped (Force Reset clears the barrier as a side effect of `clear_reset_barrier()`), but the auto-clear contract is broken and the surfaced toast asks the user to trust the daemon over what the dashboard renders.
**Repro project:** Applifier (`7cdea5e4-c94d-4612-be67-81597da3d6ec`, `/Volumes/Thunderbolt/AI/ApplicationBrowser`).

---

## 1. Symptom (corrected against screenshot)

After the concurrency/work-loss incident from §2k, the user opened Applifier and saw every Deep Enrichment row rendered as "Not run" / "Waiting for enrichment" with empty circle icons. Overall Health: 33% (5/15). Finalize rows show similar — Atlas "671 files" but no check, Rules "Generated" but no check, Concept Seeding / Structural Audit / Immune System all "Not run".

Clicking **Run** on Deep Enrichment surfaces this toast (screenshot 2026-06-15 18:09):

> ⚠ Deep Enrichment detected all stages as complete. If stages appear incomplete in the UI, try 'Force Reset' then 'Run' again.

**The toast is NOT the soft-hold or barrier error.** It is `409 PIPELINE_UP_TO_DATE` from `src/prep/api/routers/pipeline.py:271-278`, raised when `pipeline_orchestrator.run_deep_enrichment()` returns `started=false` and the diagnostic falls through to "Case 3: All stages detected as complete." The daemon is correctly observing that the deep_enrichment manifests are on-disk with `provenance.state="match"` — the bug is that the dashboard rolls those rows up as "Not run" anyway. That's the §2b UI-drift shape, manifested on a new specific path.

The barrier-deadlock root cause documented in §2-§5 below remains valid and is a separate, real bug. It happens not to be what surfaces this particular toast, but selfheal logs every ~10 min prove the barrier is still stuck:
```
{"event": "selfheal", "data": {"action": "barrier_active",
 "detail": "Selfheal skipped: reset barrier active — awaiting genuine finalize",
 "stages": ["enrichment","group_reasoning","clustering","deepening","deep_knowledge"]}}
```

Disk evidence at time of repro (40 minutes after the failure):

- `.sourceprep/.reset_barrier` is still present:
  ```
  ts=1781559563.731238  reason=full_reset  scope=all
  ```
- `.sourceprep/.pipeline_last_success` is `1781559765.398314` — **~200 s AFTER the barrier was written.** A run completed *something* successfully after the barrier was set but the barrier was not cleared.
- `/projects/<id>/pipeline/status` returns `barrier.active=true, age_seconds=2404.5, reason="full_reset", scope="all"`.
- `finalize.phase = "failed"`, error:
  ```
  Stage concepts failed: Dispatch paused on soft-hold
  (project='7cdea5e4-...', endpoint='cloud:default_ollama')
  ```
- Selfheal repeats every ~10 minutes with the same skip:
  ```
  Selfheal skipped: reset barrier active — awaiting genuine finalize
  stages: [enrichment, group_reasoning, clustering, deepening, deep_knowledge]
  ```

## 2. Root cause — pinned

`maybe_clear_scoped_barrier()` (`src/prep/services/pipeline/recovery.py:320`) is **only called from the success branch** of each pipeline group's completion handler in `orchestrator.py`. From a fresh read of the orchestrator:

| Group | Auto-clear callsite | Branch |
|---|---|---|
| `fast_sync` | `src/prep/services/pipeline/orchestrator.py:2169` | success only |
| `deep_enrichment` | `src/prep/services/pipeline/orchestrator.py:2121` | success only |
| `finalize` | `src/prep/services/pipeline/orchestrator.py:2158` | success only |

When the group **fails** (the `_run_failed` path), the orchestrator never invokes `maybe_clear_scoped_barrier`. With `scope="all"`, the barrier's auto-clear boundary is `finalize`. A failed finalize → barrier persists indefinitely.

Once the barrier is stuck on `scope="all"`, `_SCOPE_BLOCKS["all"]` blocks reuse for every group (`recovery.py:300+`). Any restart attempt goes through paths that see the barrier and refuse — manifested either as the soft-hold error path on the LLM dispatch side (Phase 127, `src/prep/services/pipeline/holds.py:103`, `raise_hold_paused_for_llm`) or the resume-path refusal (`src/prep/services/pipeline/resume.py:205+`, "Stub manifest detected with reset_barrier"). The selfheal log shows the exact reason: `"awaiting genuine finalize"`.

## 3. How Applifier got here (sequence of events)

Reconstructed from the run log `.sourceprep/logs/pipeline_20260615_214245.log`:

1. **17:39:23** — User triggers a `full_reset` on Applifier. `.reset_barrier` written: `ts=…563.7, reason=full_reset, scope=all`.
2. **17:39:27** — `fast_sync` run starts (`run-0699d012df7e`), completes ok at 17:42:30.
3. **17:42:30** — `deep_enrichment` run starts (`run-b1dd09f64145`), completes ok at 17:42:45. Stages 6–10 succeed on disk. `maybe_clear_scoped_barrier(deep_enrichment)` is called but the barrier's scope is `all` so the boundary check returns false → no clear.
4. **17:42:45** — `finalize` run starts (`run-3544b4c24ccc`). Atlas + Rules complete.
5. **17:42:46** — Stage `concepts` raises `HoldPausedError: Dispatch paused on soft-hold (project=7cdea5e4, endpoint=cloud:default_ollama)`. Run fails. State machine: `running → failed`.
6. **`maybe_clear_scoped_barrier(finalize)` is never reached** because that call lives in the success branch.
7. **17:42:46 onward** — Every 10 minutes the watcher/selfheal probes the project and emits `Selfheal skipped: reset barrier active — awaiting genuine finalize`. No further runs can succeed because every restart path either hits the soft-hold immediately or is refused by the barrier-aware reuse check.

The soft-hold itself was set during the §2k contention (almost certainly by Phase 127's pause logic when SkyPath-Restart took over the cloud endpoint), and it was never cleared on its own either — see §5 for the open question on hold lifecycle.

## 4. Why this is its own bug (separable from §2k, and from the UI drift in §1)

There are **three separable threads** colliding on Applifier right now:

| # | Thread | Where it lives |
|---|---|---|
| A | Concurrency undershoot + work loss on second-start | Scheduler / capacity broadcast — §2k |
| B | **Reset barrier never auto-clears on failed finalize** (this finding) | `orchestrator.py:2121, 2158, 2169` — success-only branches |
| C | UI rollup shows "Not run" while backend says `match` | `GraphEnrichmentPipeline.tsx` rollup — §2b shape |

Thread A is what *put* Applifier into a failed-finalize state in the first place.
Thread B is what's keeping `.reset_barrier` on disk now and skipping every selfheal pass.
Thread C is what makes the user click Run, see the toast, and read it as "refusing to start."

Fixing A narrows how often the trap is sprung. Fixing B removes the trap. Fixing C makes the trap visible to the user (today they see "Not run" rows and a toast that contradicts them — neither tells them about the barrier). All three should be fixed; this finding is scoped to B.

Per Phase 117 (CLAUDE.md): "the barrier is scoped (`sync` / `enrichment` / `all`) and auto-clears at the appropriate group boundary." The contract says nothing about success — but the implementation requires it.

## 5. Open questions

1. **Should a failed terminal group clear the barrier, or just allow manual override?**
   - Argument for clearing: the barrier's job is to gate selfheal/reuse during the in-progress reset. Once the run ends (success or failure), the gating is moot.
   - Argument for keeping: leaving the barrier might prevent selfheal from "resurrecting" half-written manifests from a partial failure (which is exactly the §2.10 `.reset_barrier` rationale in recovery.py).
   - Likely answer: **clear on terminal failure, but only after the orchestrator has flushed any in-progress writes.** Also expose a UI affordance to clear the barrier explicitly.
2. **What set the soft-hold, and why didn't it clear?**
   - `raise_hold_paused_for_llm` is invoked when the per-project/per-endpoint hold flag is set. Need to find: who writes that hold during the §2k contention? Is it written by the swarm/scheduler when the boost project takes over, and is there a release path that didn't fire?
   - Code starting point: `src/prep/services/pipeline/holds.py` and the swarm orchestrator's soft-hold mechanism at `src/prep/core/swarm_orchestrator.py:105`.
3. **Is the toast surfacing the right error?** (answered: no, and that's a separate UI bug)
   - The toast is `PIPELINE_UP_TO_DATE` from `pipeline.py:271-278`. The daemon is telling the truth — the stages are complete on disk. The dashboard is the one rendering them as "Not run." From the user's seat, the toast contradicts what they see in the UI and they have to take the daemon's word for it. This is the §2b UI-drift shape, not a wrong toast — but the right fix is to make the UI rollup match disk state so the toast never needs to "win" against the rendered rows.
   - Note: clicking Force Reset incidentally calls `clear_reset_barrier()` (`pipeline.py:244-247`), which is why the user can recover even with this bug unfixed. That side-effect is the only thing preventing this finding from being severity Critical.
4. **Should `maybe_clear_scoped_barrier` be in a `finally` block?**
   - Mechanically the simplest fix. Both success and failure branches would run it. The orchestrator pattern around line 2080+ already has try/except scaffolding — promote the existing call out of the success branch and into a post-run `finally`.

## 6. Evidence to capture next (concrete next step)

Re-run the §2k repro with verbose logging enabled. Look specifically for:

```bash
# Did the post-run handler run for the failed finalize?
grep -E "maybe_clear_scoped_barrier|_run_failed|_run_completed|finalize.*failed" \
  /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/logs/pipeline_<latest>.log

# When was the soft-hold set? By whom?
grep -E "soft.hold|HoldPaused|raise_hold|hold_set|hold_release" \
  /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/logs/pipeline_<latest>.log

# Did Phase 127's swarm orchestrator path detect a hold and emit a pause event?
grep -E "Phase 127|swarm.*paused|swarm_paused" \
  /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/logs/pipeline_<latest>.log

# Confirm the barrier file is still on disk and check its content
cat /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/.reset_barrier
ls -la /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/.reset_barrier
```

If the user gets the daemon into this state again before any fix lands, the **manual unstick** is:

```bash
rm /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/.reset_barrier
# then restart finalize via dashboard or:
curl -s -X POST http://localhost:8400/projects/<PID>/pipeline/finalize
```

(This is documented here as a *recovery procedure*, not as a fix — the daemon should not need a user to delete a file to recover from a failed run.)

## 7. Design invariants this bug violates

1. **Terminal state ⇒ barrier cleared.** Phase 117 contract: barrier auto-clears at its group boundary. The contract does not condition on the run *succeeding*. A failed terminal group is still a terminal state.
2. **Failure must not be permanently unrecoverable from the UI.** A failed pipeline should always be re-runnable. Today, `scope=all` + failed finalize → permanently blocked, with no UI affordance to clear.
3. **Errors must explain the next user action.** The toast (whatever it says) needs to tell the user *what to click* to unstick. Today the user has to learn about `.reset_barrier` from documentation.
4. **A soft-hold from contention must release when contention ends.** §2k's second project (SkyPath-Restart) finished cleanly hours ago. The hold on `cloud:default_ollama` that traps Applifier should have lifted with it.

## 8. Recommended fix shape (no code yet — confirms scope before implementation)

Three layers, in order of safety/scope:

1. **Backend (smallest, safest):** move the `maybe_clear_scoped_barrier` calls in `orchestrator.py` (lines 2121, 2158, 2169) out of the success-only branches and into the post-run `finally` block. Add a regression test: trigger a `full_reset`, force-fail finalize, assert `.reset_barrier` no longer exists when the run handler returns.
2. **Backend (separable):** audit the soft-hold lifecycle — confirm every `set_hold` has a paired release, and add a TTL/watchdog so a hold older than N minutes is force-released with a warning log. (Pin via §6 evidence first.)
3. **UI (independent of backend):** add an "Unstick / clear reset barrier" action under the failed-run badge with confirmation. When `/pipeline/status` reports `barrier.active=true AND finalize.phase=="failed"`, surface a contextual recovery toast instead of an opaque error.

## Cross-references

- §2k / `FINDING_concurrency-undershoot-and-cross-project-work-loss.md` — the upstream cause that triggered the failed finalize on Applifier.
- Phase 117 (CLAUDE.md) — the scoped barrier contract.
- Phase 127 — soft-hold mechanism (`src/prep/core/swarm_orchestrator.py:105`, `src/prep/services/pipeline/holds.py`).
- `src/prep/services/pipeline/recovery.py:320` — `maybe_clear_scoped_barrier`.
- `src/prep/services/pipeline/orchestrator.py:2121,2158,2169` — the three success-only callsites.
