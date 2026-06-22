# Phase 145 Finding — Concurrency undershoot + cross-project work loss on a second start

**Status:** Open. Symptom observed live during a two-project dogfooding session. Not yet pinned to a scheduler path.
**Found:** 2026-06-15, dashboard, two simultaneous deep runs.
**Severity:** High. Includes apparent **work loss** on a running, non-conflicting project — see §1.3. Distinct from the UI-drift focus of the rest of Phase 145; this is a backend scheduler/allocator bug that surfaces as concurrency under-allocation.

---

## 1. Symptom

User context: Ollama Cloud (Pro) configured with **manual `llm_concurrency_deep = 10`** in settings. Two local projects: `ApplicationBrowser` running first, `SkyPath-Restart` started second. Both observed during the `enrichment` stage (UI label "Deep Reasoning", Stage 6 / Epistemic Enrichment per `docs/Phase79_Swarm/06_Pipeline_Stage_Execution_Profiles.md`).

### 1.1 Solo project under-allocated (no contention)

- `ApplicationBrowser` was running alone before the second project started.
- Observed only **2–4 concurrent LLM calls**, not the configured 10.
- Stage 6 (Epistemic Enrichment) is `llm_concurrency_deep`-budgeted, non-swarm. With one active project, fair-share should give the project the **full budget** (per `Phase91_QueueRefinement/01_Resource_Allocation_Design.md` §Tier 4: "Equal share of worker budget among all active projects" → with N=1, share = budget).

### 1.2 Second project under-allocated (contention started)

- User clicked Start on `SkyPath-Restart` while `ApplicationBrowser` was mid-run.
- The second project also saw only **2–4 concurrent calls**, not the boost/fair-share expected.
- With 1 boost (★) + 1 normal at budget=10 (Phase 91 §Tier 3 weighted formula): boost should get **floor(10 × 2/3) + remainder ≈ 7**, normal should get **floor(10 × 1/3) = 3**. Observed split was roughly 2–4 each, total ≤ 8, well under the 10 the user configured.

### 1.3 First project work loss (the worst part)

- After the second project started, `ApplicationBrowser`'s active run **shut off mid-stage** and appears to have lost the in-flight enrichment work (the user observed the run progressing for a few minutes after second-start, then disappearing).
- This violates the design invariant. Per `Phase91_QueueRefinement/01_Resource_Allocation_Design.md`:
  - Normal-mode contention should **resize**, not **cancel** (§Capacity Change Broadcast: "all projects get recalculated fair-share"). Stages register a `capacity_changed` callback and adjust their semaphore.
  - Even **swarm activation** by the second project does not justify canceling the first — it should drain via the 10-minute timeout (§Drain Timeout Mechanism), and only on timeout does the first stage get force-cancelled to `failed` with reason `"drain_timeout"`. The user reported no failure surfaced; work simply stopped and was not re-emitted.
- The "star + circle" (swarm queued) icon is the user's mental model for the swarm-pending state: a queued swarm stage should sit in the queue without dispossessing a running non-swarm stage of work it has already produced.

## 2. Why this matters

Whatever the cause, the user-visible behavior is:

> "I started a second project and the first one lost the work it had already done."

That's worse than the UI drifts cataloged elsewhere in Phase 145 because it consumes real LLM spend on partial work that gets discarded. The longer the first project had been running, the more wasted cost. Also: a user who has paid for higher concurrency (Ollama Pro, manual 10) is seeing 2–4 — the configuration is silently ignored.

## 3. Where to look (hypothesis list, unverified)

| # | Hypothesis | First place to instrument |
|---|---|---|
| H1 | The effective `llm_concurrency_deep` is being capped below the configured 10 by Phase 82 latency-aware discovery, or by an AIMD step-down, before the user's manual value is honored. The manual override should clamp **up** to the user's value, not be replaced by discovery. | `src/prep/services/pipeline/scheduler.py` around AIMD `current_limit`; cross-check `concurrency observability` Phase 136 Part 15 events. |
| H2 | The weighted fair-share computation is using the wrong `budget` (e.g., the post-reserve `dynamic_capacity - 1` plus a stale low-resource guardrail triggering when capacity ≤ 3 — see §Low-Resource Guardrails). If the scheduler thinks capacity is ≤3, it disables boost weighting and minimum-3-workers guards apply. | `scheduler.py:_weighted_share` (`grep -n _weighted_share src/prep/services/pipeline/scheduler.py`); log the inputs to the share computation when a project starts. |
| H3 | `capacity_changed` broadcast (Phase 91 §Capacity Change Broadcast) is firing on the running stage but with `new_budget=0` or with a `reason` that triggers cancellation rather than resize. The orchestrator's recovery path then drops the in-flight work instead of resuming. | `scheduler.on_capacity_change` registration in the augmenter/enrichment batch engine; the callback path in `orchestrator.py`. |
| H4 | The second project's start path is taking an exclusive code path (e.g., `_activate_project` sets a flag that demotes other running stages) — analogous to the original 2026-06-08 fan-out incident (§2d in the README), but on a different code path. | `src/prep/api/routers/projects/build.py`, `src/prep/services/pipeline/orchestrator.py` `_activate_project` and friends. |
| H5 | First project's stage is being treated as draining and silently force-cancelled (§Drain Timeout: marks `failed` with reason `"drain_timeout"`), but the failure event is being swallowed by the UI rather than surfaced — making it look like "lost work" without an error. | Search journal/event log for `drain_timeout`, `cancel`, `force_cancel` around the timestamp; confirm via `.sourceprep/logs/pipeline_*.log` for both projects. |
| H6 | `ApplicationBrowser`'s stage was using `llm_concurrency_deep` but the *effective* in-flight worker count was bounded by a batch-engine semaphore created with a stale snapshot of the budget at stage-start (before the user manually raised concurrency or before AIMD ramped up). | `src/prep/core/epistemic_enrichment.py` semaphore init; check whether it subscribes to `capacity_changed`. |

H1 and H6 together can explain §1.1 (solo undershoot). H3/H5 explain §1.3 (work loss). H2/H3 explain §1.2 (contention undershoot).

## 4. Repro / evidence to capture next

When the symptom is live or re-triggered, capture:

```bash
# 1. Confirm the configured value the scheduler sees
curl -s http://localhost:8400/settings/pipeline-config | python3 -m json.tool

# 2. Observability snapshot during a single-project run
curl -s http://localhost:8400/projects/<APPBROWSER_PID>/pipeline/status | python3 -m json.tool

# 3. Concurrency observability (Phase 136 Part 15)
grep -i "concurren\|capacity_changed\|aimd\|fair.share\|_weighted_share\|drain_timeout" \
  /Volumes/<path>/<project>/.sourceprep/logs/pipeline_<latest>.log

# 4. After starting the second project, watch both event streams
timeout 30 curl -sN http://localhost:8400/events | grep -E "capacity_changed|cancel|drain|swarm"

# 5. Confirm whether the first project's stage was marked failed/cancelled
cat /Volumes/<path>/<APPBROWSER>/.sourceprep/pipeline_run_metadata.json | python3 -m json.tool | grep -A2 enrichment
```

If H3 or H5 is confirmed, the journal will show a `failed` transition with reason `drain_timeout` or `cancel` on `ApplicationBrowser`'s enrichment stage shortly after `SkyPath-Restart` started, even though no UI error surfaced.

## 5. Design invariants this bug violates

These are the contract pieces the fix must restore, lifted from `Phase91_QueueRefinement/01_Resource_Allocation_Design.md`:

1. **Manual concurrency override is a floor for the user, not a ceiling for discovery.** A user who configured `llm_concurrency_deep = 10` should never see 2–4 unless AIMD has explicitly stepped down with logged 429/timeout pressure.
2. **Sole active project gets the full budget.** N=1 → share = budget (Tier 4: Normal Mode).
3. **Boost weighting is 2:1.** 1 boost + 1 normal at budget=10 → 7/3 split (with remainder to boost), not 2-4 / 2-4. The star icon means "this project gets ~2/3 of available slots."
4. **Contention resizes; it does not destroy work.** A `capacity_changed` event resizes the running stage's semaphore. Work already done is preserved. Cancellation only happens on `drain_timeout` (default 600s), and even then it surfaces as a visible `failed` state with reason — not silent disappearance.
5. **Queued swarm does not dispossess.** A second project's swarm-capable stage in the queue (the "star with a circle" state) waits its turn or activates only after cooldown/drain rules; it does not preempt and discard the first project's in-flight non-swarm work.

## 6. Recommended path forward

This finding pairs naturally with §6 (Investigation Plan) of the Phase 145 README, but the diagnostic is **backend-first** and does **not** require the Playwright harness. Capture §4 evidence on a fresh two-project repro, then walk H1→H6 against the observed event ordering. Do not propose code changes until the journal evidence pins the exact transition that drops `ApplicationBrowser`'s work.

Related prior fixes worth re-reading first:

- `cac65709` — Phase 136 Part 15 concurrency observability + SWARM_CAPABLE gating.
- `11033fc2` / `b3c6f45f` — P1 settings router cross-project fan-out (different code path, same shape).
- `Phase91_QueueRefinement/01_Resource_Allocation_Design.md` — the authoritative resource-allocation contract.
- `Phase82_CloudPipelineConcurrency/02_Design_Spec.md` — latency-aware discovery and how it interacts with the configured limit.

## 7. Scope clarification 2026-06-19 — swarm code path confirmed working; concerns are about NON-SWARM fair-share only

Captured 2026-06-19 ~08:14 on Applifier: AI Gateway widget shows `Thinking [10×] · kimi-k2.6:cloud · Group Reasoning [10×Swarm] on Applifier`. When Applifier's deep_enrichment run reached the swarm-capable Group Reasoning stage (Stage 7), it correctly acquired the full 10-slot swarm budget per Phase 91 §Tier 1 / Phase 79 §6 Stage 7. **The swarm code path is intact.**

This narrows §2k's scope. The hypotheses H1–H6 in §3 are about **non-swarm stages** specifically — Epistemic Enrichment (Stage 6, "Deep Reasoning" in UI), Catalogue (Stage 3), Module Synthesis (Stage 8, currently non-swarm per Phase 79), etc. These use `llm_concurrency_deep` with `BatchProfile`-driven batching, NOT the swarm orchestrator. The user's original §1 evidence ("2–4 calls instead of 10") was during Deep Reasoning — a non-swarm stage.

**Adjacent datapoint, 2026-06-19 08:13:** Applifier in Deep Reasoning (non-swarm Stage 6) showed `cloud:default_ollama: 1/10` while SourcePrep was simultaneously on Knowledge Embedding (embedder slot, doesn't compete for `cloud:default_ollama`). With Applifier alone on the cloud LLM slot and boost-priority, the design expects ~7 in-flight requests. **Observed: 1.** Consistent with §1's original "undershoot" report. This is NOT a swarm bug; the swarm code path verified working a minute later on Stage 7. The undershoot lives in either:

- `BatchProfile` for the Epistemic Enrichment stage (it may emit batches one-at-a-time rather than fanning out)
- `_weighted_share` returning the wrong budget when N=1 (should be `full budget` per Phase 91 §Tier 4, not `1`)
- AIMD stepping down to 1 without observed throttle pressure (covered by `PROPOSAL_thread-A-v1` sub-thread A.2)

**Update to `PROPOSAL_thread-A-v1` v2:** the threads inventory remains valid, but the swarm-vs-non-swarm distinction should be explicit. A.2 (manual concurrency floor) and A.3 (fair-share budget audit) are non-swarm concerns; the swarm-bypass path doesn't need touching.
