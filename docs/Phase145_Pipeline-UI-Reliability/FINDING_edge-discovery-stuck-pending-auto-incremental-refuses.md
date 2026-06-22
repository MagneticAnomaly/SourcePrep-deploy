# Phase 145 Finding — Edge Discovery (Stage 2) renders as spinning but is actually `Pending`; auto-incremental refuses to fire despite untraced files; refresh doesn't recover

**Status:** Open. Live screenshot 2026-06-18 23:38 EDT. Limited inline notes per Eric's "we can't write too much about this" preference.
**Found:** 2026-06-18, on SourcePrep project (`f1636374-abc6-410d-99ee-822120379e79`).
**Severity:** Medium-High. UI-vs-reality desync that's *refresh-resistant* — distinguishes this from the broader frontend-hang family.
**Linked symptom in README:** §2s.

---

## 1. Symptom

Project: **SourcePrep** (self, the repo we're working in).

What the panels show:

- **Graph Scope:** `2090/2098 files traced · 99.9%`. **8 untraced markdown files** in queue, ages 37m–1h (the docs/Phase145_* files I've been writing today).
- **Graph Enrichment → Fast Sync → Edge Discovery (Stage 2):** spinner icon ON, label `Discovering edges…`. Looks like it's running.
- **Sidebar queue widget:** `SourcePrep · Pending · Fast Sync · Edge Discovery`. The `Pending` badge is the ground truth — the scheduler hasn't actually started this stage.
- **`cloud:default_ollama: 0/10`** — confirms zero LLM activity. Edge Discovery uses the cloud Fast model.
- **AI Gateway:** `1 active · Code Model · Inferred Edge Discovery on SourcePrep` — claims it IS running (with the spinner glyph). Contradicts the queue widget's `Pending`.
- **Browser refresh does NOT change any of the above.** This isn't a stale-frontend-state issue.

What it should be doing: with `Auto` enabled on Fast Sync and 8 untraced files aging up to 1h, the watcher should have fired and Edge Discovery should have actually progressed (or completed already — these are small markdown files).

## 2. What this is NOT

To save the next reader investigation cycles, ruling out the wrong attributions before listing the right hypotheses:

- **NOT a daemon stall (§2m).** Other projects' state is current; the daemon is responding to status polls (the queue widget itself is being polled fine). The user has confirmed similar 22:38 incidents were frontend hangs, but **refresh doesn't fix this one** — so it's not a pure frontend hang either.
- **NOT a swarm-window block (§2k / §2p).** Cloud:0/10 means no project holds the slots. SourcePrep is the only thing in the queue.
- **NOT a reset_barrier deadlock (§2l Thread B).** No barrier on disk for SourcePrep (verify with `ls /Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/.reset_barrier` — file shouldn't exist).
- **NOT a UI rollup race (§2r).** §2r is "multiple rows running"; this is "one row claiming running while backend says Pending." Different shape.

## 3. Hypotheses (unverified, ordered by likelihood)

### H-S1 — Worker was dispatched but raised silently, leaving SM state inconsistent

Per [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md) §2: there are at least 5 callsites that fire `Event.STAGE_FAILED` from different failure modes. If one of those fires without surfacing to the UI (silent failure swallowed by an `except Exception: pass`), the SM transitions to FAILED but the queue widget still shows `Pending` (it was enqueued before the failure) and the row spinner stays on (UI doesn't know to clear it).

### H-S2 — Stage entered the run but the worker thread is blocked / hung

If the Edge Discovery worker started, registered with the scheduler (slot acquired), then hung in a synchronous call before producing any output — the slot would release (no progress callback fires `release()`) but the SM state would be stuck. The queue still shows `Pending` because the *next* item is pending; the row spinner stays on because the worker hasn't transitioned to a terminal state.

### H-S3 — Watcher fired and enqueued correctly, but the orchestrator's `_advance_pipeline` hit a guard that returns without starting AND without surfacing

`_check_incomplete_deep_enrichment` (`src/prep/core/watcher.py:664`) and similar gates can cause the auto-trigger to short-circuit. If the gate returned True (some downstream stage thinks it's incomplete), the run might be enqueued but never started. **Note: §2q H-Q6 covers this exact pattern — likely the same bug surfacing differently.**

### H-S4 — Stage 2 result is being treated as cached/stale and the new untraced files were never re-scoped

The 8 untraced files appeared in Graph Scope's "Untraced" list (so the file scanner *can* see them) but the orchestrator's input fingerprinting may not have picked them up for the next run. If `_emit_changeset` (per §2i, where `hash_algo`/`built_at` preservation was fixed 2026-06-15) is broken in a *new* way for this project, the input change might not be detected.

### H-S5 — Auto-trigger fired but is silently deduplicated against an already-Pending entry

The queue widget shows `SourcePrep · Pending`. If a prior watcher fire enqueued the run and it never started (per H-S1/H-S2/H-S3), subsequent watcher fires see "already in queue" and silently no-op. The 8 untraced files keep accumulating; no second fire happens because the first one is still pending.

## 4. Diagnostic commands (capture next time the symptom is live)

```bash
PID=f1636374-abc6-410d-99ee-822120379e79   # SourcePrep
REPO=/Volumes/4TB-BAD/HumanAI/CoDRAG

# 1. What does the pipeline status actually say?
curl -s http://localhost:8400/projects/$PID/pipeline/status | python3 -m json.tool > /tmp/dgS_status.json
# Look at: fast_sync.phase, fast_sync.is_active, fast_sync.is_queued,
#          fast_sync.stage_results.inferred_edges,
#          stages.inferred_edges.running, stages.inferred_edges.provenance.state

# 2. What does the queue snapshot say?
curl -s http://localhost:8400/system/pipeline-queue | python3 -m json.tool > /tmp/dgS_queue.json

# 3. What does the watcher say?
curl -s http://localhost:8400/projects/$PID/watch/status | python3 -m json.tool

# 4. Tail the latest pipeline log
LATEST=$(ls -t $REPO/.sourceprep/logs/pipeline_*.log | head -1)
tail -100 "$LATEST"

# 5. Specifically look for stage-start / stage-end / failure events on inferred_edges
grep -E "inferred_edges|edge.discovery|STAGE_FAILED|STAGE_COMPLETED|stage_start|stage_end" "$LATEST" | tail -30

# 6. Confirm no barrier / guard rejections
ls -la $REPO/.sourceprep/.reset_barrier $REPO/.sourceprep/.guard_rejections.json 2>/dev/null

# 7. Is the orchestrator's in-memory run state visible?
curl -s http://localhost:8400/system/orchestrator-state 2>/dev/null  # may or may not exist
```

The discriminator between H-S1 (silent failure) and H-S3 (gate short-circuit): does the journal show a `STAGE_FAILED` event for inferred_edges? If yes, H-S1. If no, H-S3 or H-S5.

## 5. Relationship to other open findings

- **§2q (auto-incremental never fired):** very likely the same underlying bug. §2q's H-Q3 (debounce gated) and H-Q4 (silently enqueued behind §2p) overlap directly with this finding's H-S5.
- **§2r (multiple rows running):** different specific failure but same compute*State family. The proposed T1 re-centering would help here too — if the helper read `stage_results["inferred_edges"]`, it would render `not_yet_reached` (S1 says no opinion) instead of spinning.
- **§2p / §2q reattribution retraction:** this finding strengthens the case that §2p/§2q are real bugs, not §2m manifestations. Auto-incremental refusing to fire while the daemon is otherwise healthy is exactly the pattern §2q first described.

## 6. What the proposal does and doesn't address

- **T1 (UI re-centering)** would fix the spinner — Edge Discovery's row would render `not_yet_reached` (S1's `current_stage_index` hasn't reached it OR `stage_results` is empty). The row state and the queue widget would agree.
- **T1 does NOT address the underlying "watcher fires but stage never starts" backend bug.** That's a §2q / new §2s investigation.
- **T2.b (scheduler ↔ S1 sync)** indirectly relevant if the run is enqueued but never dispatched.

## 8. Recurrence 2026-06-19 07:13 — manual Rebuild All on same project, 8h stall, progress reached 93% then froze

Same project (SourcePrep). Different trigger this time — **explicit Manual Rebuild All click**, not the auto-watcher. Captured ~8 hours after the click. Refresh doesn't recover.

What's different from the §1 capture:

- **Header reads:** `Rebuilding All stage 2/15: Edge Discovery · 93%`. The 93% is the per-stage progress bar for Edge Discovery itself.
- **Stage 1 (Structural Graph) completed today in 4s** — proving the rebuild actually started and at least one stage ran.
- **Edge Discovery worker started, reached 93% progress, then stalled.** Has been at 93% for ~8 hours.
- **All downstream stages (Stages 3–15) still show their *prior* run timestamps** ("today 2m 49s", "today 8m 30s", "today 41s", "yesterday 1m 51s"). They were not re-run yet because the rebuild is stuck on stage 2 — and their UI still shows the data from the previous successful run.
- Everything else matches §1: queue widget `Pending`, `cloud:default_ollama: 0/10`, browser refresh no help, "Last updated: 9h ago" in Graph Scope.

What this tells us about the hypotheses:

- **H-S2 (worker thread hung mid-execution) is now the strongest.** The worker DID start, made it to 93%, then stopped. Not a gate-before-start issue.
- **H-S3 (orchestrator guard short-circuited) is ruled out for this capture.** The worker reached 93% — it definitely started.
- **H-S1 (silent failure swallowed) refines to "silent failure DURING execution, not before."** The worker was making progress, then either raised silently OR hung in a non-raising blocking call.
- **H-S4 (changeset fingerprint missed files) is ruled out.** This was a manual Rebuild All — the user explicitly told the orchestrator to ignore freshness and rebuild everything. If the rebuild started and progressed to 93%, fingerprint detection was fine.
- **H-S5 (silent dedup against already-Pending entry) is also ruled out** for the same reason — manual click should bypass dedup logic.

What this adds to the hypothesis space:

- **H-S6 — Worker hung in an LLM call that never returned, and `cloud:default_ollama: 0/10` reflects the slot being released by a heartbeat-style cleanup but the worker still believing it's holding the slot.** Different shape from §2m's CoreML hang because this is a cloud LLM call (Edge Discovery uses gemini-3-flash-preview per the screenshot), not an embedder. But same family: synchronous blocking call without timeout, scheduler eventually frees the slot, worker doesn't know.
- **H-S7 — Worker hung on a non-LLM operation (file write, semaphore wait, batch coordination).** Edge Discovery dispatches batches to the cloud Fast model — a coordination deadlock between the dispatcher and one or more in-flight batches could leave the dispatcher hung while the LLM slots are free.

### 8.1 Diagnostic priorities (given the 8h evidence)

If the symptom is still live (which it has been for 8 hours and probably continues):

```bash
# Get a py-spy stack trace of the daemon's worker thread for this project
# This is the single most valuable capture for H-S2/H-S6/H-S7 discrimination
DAEMON_PID=$(pgrep -f "prep.cli serve" | head -1)
py-spy dump --pid $DAEMON_PID > /tmp/dgS8_daemon_pyspy_$(date +%s).txt
# Look for: anything on a worker thread blocked in a recv() / read() / lock acquire()
#          that's been there for hours

# Confirm the journal shows the stage start but no stage_end
LATEST=$(ls -t /Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/logs/pipeline_*.log | head -1)
grep -E '"stage": ?"inferred_edges"|inferred_edges.*stage_start|inferred_edges.*stage_end|inferred_edges.*STAGE_FAILED' "$LATEST"

# What was the last batch dispatched to the cloud LLM for Edge Discovery?
grep -E "inferred_edges.*batch|inferred_edges.*request|cloud.*inferred_edges" "$LATEST" | tail -20
```

The py-spy dump answers the H-S2 vs H-S6 vs H-S7 question definitively.

### 8.1.5 Daemon-restart cleared the 8h hang (strong supporting evidence for H-S2/H-S6/H-S7)

After ~8h of the stall, Eric restarted the daemon. **The dashboard came back at `Rebuilding All stage 5/15: Knowledge Embedding · 87%`** — the rebuild had advanced through stages 2, 3, 4, and was actively progressing on stage 5. So the daemon-restart killed whatever was hanging and the orchestrator either resumed the run or restarted it cleanly from a checkpoint.

**Implication:** the hung condition was in-process state (a Python thread blocked on a syscall, an unsignalled semaphore, an unreleased lock, etc.) — exactly the shape of H-S2 / H-S6 / H-S7. A SIGTERM clears it because the OS forcibly tears down the process. This is direct evidence that **a watchdog-with-timeout (proposed T4) would have converted the 8h silent hang into a `STAGE_FAILED` and a re-dispatch hours earlier**, with no daemon restart needed.

This also rules out hypotheses where the hang would survive a restart (e.g. a permanently-corrupt manifest blocking the resume detector). The hang is process-lifetime-scoped.

### 8.2 What this implies for the proposal stack

- **T1 (UI re-centering) still applies and is still the smallest valuable intervention** — the UI's "93% spinner" is wrong because S1 has no `stage_results["inferred_edges"]` entry yet. Reading from S1, the row would render `running` legitimately, but a separate "stuck > N seconds" warning chip (in T3 / Thread D family) would be a new defense-in-depth addition.
- **The worker-hang-without-timeout pattern is independent of S1's drift.** No re-centering of S1 fixes a worker that won't return. This needs a separate sub-thread — call it **T4 — Worker-side watchdog**: every batch-dispatching worker should have a wall-clock timeout that converts a hang into `Event.STAGE_FAILED` so S1 transitions and the UI surfaces it. Worth adding to the v2 proposal.
- This finding now spans both (a) the UI's compute*State row-state derivation problem AND (b) a backend worker-hang-without-timeout problem. They're independent fixes.

## 9. Cross-references

- Probable shared cause: [`FINDING_auto-incremental-never-fired-despite-stale-files.md`](FINDING_auto-incremental-never-fired-despite-stale-files.md) H-Q3, H-Q4.
- UI rendering family: [`FINDING_multiple-stages-show-running-simultaneously.md`](FINDING_multiple-stages-show-running-simultaneously.md).
- Code pointers: `src/prep/services/pipeline/orchestrator.py` `_advance_pipeline` + `_on_build_transition`, `src/prep/core/watcher.py` `_on_debounce_fire` + `_check_incomplete_deep_enrichment`, `src/prep/services/pipeline/scheduler.py` `acquire`/`enqueue`.
