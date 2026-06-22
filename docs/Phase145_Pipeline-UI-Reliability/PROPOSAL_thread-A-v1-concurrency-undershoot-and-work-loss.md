# PROPOSAL v1 — Thread A: Concurrency undershoot + cross-project work loss on second-start

> **STATUS: DRAFT v1 — awaiting scrutiny — 2026-06-16.** Do not execute as-is. Thread A is the largest, least-pinned thread in Phase 145 — six hypotheses (H1–H6, see [`FINDING_concurrency-undershoot-and-cross-project-work-loss.md`](FINDING_concurrency-undershoot-and-cross-project-work-loss.md) §3) and no live evidence capture yet. This proposal structures the work as a diagnostic sub-thread (A.1) that must run first, and six independent fix sub-threads (A.2–A.7) gated on what A.1 surfaces. Each fix task is labeled `[evidence: solid]`, `[evidence: partial, needs DG-Ax]`, or `[evidence: hypothesis only, do not author tests yet]`.

**Goal:** When this proposal is ready to execute, the user-visible result is: (i) the user's manually-configured `llm_concurrency_deep` is honored as a floor, not silently capped to a discovered lower value; (ii) starting a second project does not cancel work-in-flight on the first; (iii) any genuine cancellation surfaces as a visible failure with a reason, not as silent disappearance; (iv) the in-flight worker count for a running stage scales up *and* down with `capacity_changed`, not just down.

**Architecture:** Six independent fixes plus one shared diagnostic. The fixes touch `src/prep/services/pipeline/scheduler.py` (worker budget + capacity broadcast), `src/prep/services/build_orchestrator.py` (semaphore lifecycle), and the per-stage batch engines (`src/prep/core/epistemic_enrichment.py`, `augmenter.py`, etc.) that own the in-flight worker semaphores. Each sub-thread can ship alone; sequencing recommended below is by evidence strength, not by code dependency.

**Tech stack:** Python 3.11 + pytest. No UI changes in Thread A (a "drain_timeout surfaced as visible failure" UI affordance is mentioned as a stretch but lives in Thread D-shape, not here).

**Independence:** Sub-threads A.2–A.7 are all independent of each other and independent of Threads B/C/D. A.1 (diagnostic) must finish before A.3–A.7 can have their tests authored; A.2 has solid evidence already (the user's screenshot + settings configuration) and can be authored against without DG-A.

**Out of scope (still):** §2l (Threads B/C/D — separate proposal). Phase 91 design itself (we're restoring its contract, not redesigning). LLM provider rate limit discovery itself (Phase 82 — we're not touching the AIMD probe, only how its result interacts with the manual override).

---

## Pre-flight: What we know vs hypothesize

| Category | Status |
|---|---|
| **Symptom** | User had Ollama Pro with manual `llm_concurrency_deep = 10`. Project A (Applifier/ApplicationBrowser) running alone on Deep Reasoning (Stage 6) showed only 2–4 concurrent calls instead of 10. Starting Project B (SkyPath-Restart) mid-run: Project B also got 2–4 calls; Project A's work shut off mid-stage with apparent work loss. No surfaced failure event. **Solid — user screenshot + config + observation.** |
| **Design contract** | Phase 91 (`docs/Phase91_QueueRefinement/01_Resource_Allocation_Design.md`) specifies: N=1 → share = budget; boost+normal → 7/3 split at budget=10; `capacity_changed` resizes running stages; cancellation only via `drain_timeout` (default 600 s) with visible `failed` state and reason. **Solid — design doc + implementation cites the rules.** |
| **Code citations** | `src/prep/services/pipeline/scheduler.py:_weighted_share` (`grep -n _weighted_share`), `capacity_changed` event in same file, Phase 79 swarm bypass at `scheduler.py:2587` (logs "Full budget for project X on node Y: 10 (bypassing fair-share)"). **Solid — visible in logs and code.** |
| **What ran on Applifier per logs** | Deep enrichment ran in 15 s after fast_sync completed — the log shows scheduler acquiring/releasing slots correctly during atlas/rules but then the concepts stage hit a soft-hold and the run failed. **Solid — `pipeline_20260615_214245.log`.** |
| **Hypotheses for the under-count** | Six (H1–H6 in FINDING §3). **Hypothesis only — no instrumentation has yet pinned which one(s) are firing.** |
| **Hypothesis for the work loss** | H5: stage force-cancelled via `drain_timeout` (10 min) and the failure event was swallowed by the UI; or H3: `capacity_changed` fired with `new_budget=0` and the callback path did a cancel instead of a resize. **Hypothesis — needs DG-A evidence.** |

These splits matter because A.1 (diagnostic) becomes the *source of truth* for A.3–A.7. A.2 is the only sub-thread with strong enough evidence to author tests + code against today.

---

## Sub-thread map

```
A.1 — Diagnostic (DG-A1 ... DG-A6)           [solid: this is just running commands]
   │
   ▼  produces EVIDENCE_* files which are inputs to:
   ├── A.2 — Manual concurrency is a floor      [solid: user config + screenshot]
   ├── A.3 — Fair-share budget audit            [partial: needs DG-A2 + DG-A3]
   ├── A.4 — capacity_changed resize-not-cancel [partial: needs DG-A3 + DG-A4]
   ├── A.5 — Project-start cross-effects audit  [partial: needs DG-A5]
   ├── A.6 — Drain-timeout surfaced as failure  [partial: needs DG-A4]
   └── A.7 — Dynamic semaphore for stage workers [partial: needs DG-A3 + DG-A6]
```

Sub-thread A.2 can ship today. A.3–A.7 wait on A.1.

---

## A.1 — Diagnostic sub-thread (prerequisite for A.3–A.7)

This is a focused reproduction of the §2k incident with maximum instrumentation. The commands are lifted (lightly expanded) from `FINDING_concurrency-undershoot-and-cross-project-work-loss.md` §4. **No code changes** — purely capture.

### DG-A1 — settings snapshot

Confirm the daemon sees the user's manual `llm_concurrency_deep = 10`.

```bash
curl -s http://localhost:8400/settings/pipeline-config | python3 -m json.tool > /tmp/dgA1_settings.json
```

Save to `docs/Phase145_Pipeline-UI-Reliability/EVIDENCE_dgA1_pipeline-config.json`. Verify `llm_concurrency_deep == 10` (or the user's current configured value) in the captured JSON.

### DG-A2 — scheduler nodes snapshot (single-project baseline)

With Project A (Applifier) running alone on a deep-enrichment stage, capture:

```bash
PID=7cdea5e4-c94d-4612-be67-81597da3d6ec
curl -s http://localhost:8400/projects/$PID/pipeline/status \
  | python3 -m json.tool \
  > /tmp/dgA2_solo_$(date +%s).json
```

The interesting fields for analysis: `scheduler.nodes."cloud:default_ollama".max_concurrent`, `dynamic_capacity`, `current_load`, `current_limit`, `discovered_ceiling`. Save and label "solo baseline."

### DG-A3 — concurrency observability stream

Phase 136 Part 15 (commit `cac65709`) added concurrency observability. Tail the journal during the same run:

```bash
LOG=$(ls -t /Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/logs/pipeline_*.log | head -1)
grep -E "concurrency|capacity_changed|aimd|fair.share|_weighted_share|swarm|acquired slot|released slot" "$LOG" \
  > /tmp/dgA3_concurrency_events.log
```

Save as `EVIDENCE_dgA3_concurrency-events.log`. This is the *primary* evidence for whether AIMD is stepping the limit down (H1), whether `_weighted_share` is computing the wrong budget (H2), and whether capacity broadcasts fire on cross-project starts (H3).

### DG-A4 — second-project start, side-by-side capture

While Project A is mid-stage (under DG-A2's solo baseline), start Project B:

```bash
PID_B=bfbe8ab2-7adc-4c6c-983c-03edeac767e8  # SkyPath-Restart
curl -s -X POST http://localhost:8400/projects/$PID_B/pipeline/deep \
  -w "\nHTTP: %{http_code}\n" \
  > /tmp/dgA4_start_B.txt

# Simultaneously stream events for 60 s
timeout 60 curl -sN http://localhost:8400/events \
  | tee /tmp/dgA4_events_during_contention.log

# Re-capture both projects' status after 30 s of contention
sleep 30
curl -s http://localhost:8400/projects/$PID/pipeline/status \
  > /tmp/dgA4_A_during_contention.json
curl -s http://localhost:8400/projects/$PID_B/pipeline/status \
  > /tmp/dgA4_B_during_contention.json
```

Save all four files. The events stream is the discriminator between H3 (`capacity_changed` reason field), H4 (`_activate_project` cross-effect), and H5 (`drain_timeout` firing).

### DG-A5 — project-start path audit (static)

Read the project-start code paths for any "demotes others" side-effect:

```bash
grep -n "_activate_project\|all_projects\|other_runs\|for.*runs.items" \
  src/prep/api/routers/projects/build.py \
  src/prep/services/pipeline/orchestrator.py \
  src/prep/services/pipeline/scheduler.py | head -30
```

Write a short writeup (`EVIDENCE_dgA5_project-start-paths.md`) listing every place a "start project B" action could affect Project A's running stages. Cite line numbers.

### DG-A6 — semaphore lifecycle audit (static)

Read each batch engine's semaphore creation + capacity-changed subscription:

```bash
grep -rn "Semaphore\|asyncio.Semaphore\|on_capacity_change\|capacity_callback\|scheduler.on_capacity" \
  src/prep/core/epistemic_enrichment.py \
  src/prep/core/group_reasoning.py \
  src/prep/core/clustering.py \
  src/prep/core/deepening.py \
  src/prep/services/pipeline/workers/ | head -30
```

For each stage, document: when is the semaphore created (stage start? batch start?), what value is it initialized to (current `dynamic_capacity`? cached at start?), and is there a `capacity_changed` subscription that resizes it? Save as `EVIDENCE_dgA6_semaphore-lifecycle.md`.

### DG-A7 — synthesis

Write `SYNTHESIS_2026-06-16_thread-A-concurrency.md` consolidating DG-A1 through DG-A6 into: (i) which of H1–H6 are confirmed firing, (ii) which can be ruled out, (iii) which remain ambiguous. This synthesis is the input the next plan reads from.

---

## A.2 — Manual concurrency is a floor, not a ceiling for AIMD  *[evidence: solid]*

This sub-thread can ship today; it doesn't depend on A.1.

**Premise:** Phase 82's AIMD discovery (`docs/Phase82_CloudPipelineConcurrency/02_Design_Spec.md`) discovers an effective concurrency ceiling per cloud node. The user-facing setting `llm_concurrency_deep` is *user intent*. When the user manually sets it to 10, AIMD should treat 10 as the *floor it must reach* (probing up to that value); it should not lower the effective limit below 10 unless it has direct evidence of throttling (429 / timeout).

**Hypothesis the symptom invalidates:** the user sees 2–4 concurrent calls while solo. Either AIMD is stepping down without explicit throttling evidence (bug), OR the manual value isn't being read into the scheduler's `max_concurrent` at all (bug).

### A.2.1 — failing test  *(authored at execution time)*

**Files:**
- Create: `tests/test_phase145_manual_concurrency_floor.py`

Test cases (sketches):

```python
def test_manual_override_sets_max_concurrent_on_scheduler():
    """When settings.pipeline-config sets llm_concurrency_deep=10,
    the scheduler's cloud:default_ollama node max_concurrent is 10."""

def test_aimd_does_not_drop_below_manual_override_without_throttle_evidence():
    """If no 429/timeout has been observed, AIMD's current_limit
    must equal or exceed the manual override."""

def test_aimd_steps_back_up_to_manual_override_after_clean_window():
    """If AIMD stepped down due to a transient 429, it must return
    to the manual override floor when the throttle pressure clears."""
```

### A.2.2 — code change candidate

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py` (`_weighted_share`, AIMD step methods)

The fix is one of two shapes (decide at execution time based on the code):

- **Option A — Floor in AIMD step-down:** `current_limit = max(manual_override, computed_step_down)`. Single condition added to the step-down code path.
- **Option B — Discovery seeds AIMD with manual as starting `current_limit`:** the AIMD probe starts at `max_concurrent = manual_override` instead of 1; AIMD only steps up from there.

Both restore the invariant. Option A is more conservative; Option B is more aggressive. Pick at execution time after reading the existing AIMD step code.

### A.2.3 — smoke

After the fix, restart the daemon. Trigger a deep-enrichment run on Applifier solo. Capture the same fields as DG-A2 and confirm `current_limit == 10` from the first stage onward.

### A.2.4 — commit

```
fix(scheduler): manual llm_concurrency override is a floor, not a ceiling

Phase 145 Thread A.2. AIMD discovery was overriding the user's manual
concurrency setting on cloud nodes, capping effective in-flight
requests at 2–4 even when the user had configured 10 (Ollama Pro).
Restores the Phase 82 + Phase 91 contract: manual override is a floor;
AIMD steps down only with direct throttle evidence and steps back up
to the floor when pressure clears.

Tests: tests/test_phase145_manual_concurrency_floor.py.
```

---

## A.3 — Fair-share budget audit  *[evidence: partial, needs DG-A2 + DG-A3]*

**Premise:** Per Phase 91 §Tier 3 / §Tier 4: with 1 boost + 1 normal at budget=10 the split should be 7/3 (floor + remainder). User observed 2–4 / 2–4. Either the budget passed to `_weighted_share` is wrong (e.g., a low-resource guardrail is firing because `dynamic_capacity ≤ 3` triggers, even when the manual is 10), or the boost weighting is off, or the split is right but the *consumer-side* semaphore caps it lower (which is A.7's territory).

### A.3 tasks — wait for DG-A2 + DG-A3

Do not author tests or code for A.3 until DG-A2 + DG-A3 are in the corpus. The shape of the test depends on what `_weighted_share`'s inputs actually were during the user's incident.

**Probable fix shape** (subject to evidence):

- **If DG-A3 shows `_weighted_share` was called with `budget < 10` while manual was 10:** the budget computation reads from `dynamic_capacity` instead of `max_concurrent`. Fix: route `_weighted_share` through the manual-floor logic from A.2 (this is why A.2 ships first — A.3 may piggyback on it).
- **If DG-A3 shows the budget was 10 but the per-project share was 2–3:** the weighted formula is misapplied. Read the actual formula vs Phase 91 §Tier 3 example and reconcile.
- **If DG-A3 shows the low-resource guardrail (capacity ≤ 3) was triggered:** find why — `dynamic_capacity` is being computed lower than `max_concurrent` somehow. Likely related to AIMD step-down (A.2 territory).

### A.3 commit shape

```
fix(scheduler): _weighted_share budget honors manual concurrency floor

Phase 145 Thread A.3. <pinned cause from DG-A3>. Was producing 2–4
per project under boost+normal contention where the design called
for a 7/3 split at budget=10.

Tests: tests/test_phase145_fair_share_budget.py.
```

---

## A.4 — `capacity_changed` resizes; never cancels  *[evidence: partial, needs DG-A3 + DG-A4]*

**Premise:** Phase 91 §Capacity Change Broadcast defines `capacity_changed` events with `new_budget` and `reason` fields. Subscribers (the batch engines) register a callback that **adjusts the stage's `asyncio.Semaphore` or thread pool size**. The contract is *resize* — not *cancel*. The user's reported work loss (Project A shut off mid-stage with no surfaced failure) suggests the broadcast on Project B's swarm-window start is being interpreted as a stop signal somewhere.

### A.4 tasks — wait for DG-A3 + DG-A4

Don't author until evidence lands. The discriminator in DG-A3/A4: does `capacity_changed` ever fire with `new_budget == 0`? Does any subscriber call `.cancel()` instead of `.set_value(new_budget)`?

**Probable fix shape:**

- **If DG-A3 shows `capacity_changed` firing with `new_budget=0`:** find why — `_weighted_share` returned 0 for the running project after the broadcast input changed. Fix: clamp to `min_workers_per_active_project = 1` (or whatever the design specifies).
- **If DG-A4 shows a subscriber doing `.cancel()`:** the callback is wrong — should be resize, not cancel. Fix per-stage callback.
- **If both are clean:** look at H4 (cross-project effect on project start). The work loss must come from somewhere; if not from `capacity_changed`, it's from a different code path.

### A.4 commit shape

```
fix(scheduler): capacity_changed broadcasts resize stage workers, never cancel

Phase 145 Thread A.4. A second project starting was triggering a
capacity_changed event that <DG-A3-confirmed mechanism> caused the
first project's in-flight workers to drop to zero with no surfaced
failure. Restores the Phase 91 §Capacity Change Broadcast contract:
the event is a resize signal, not a stop signal.

Tests: tests/test_phase145_capacity_changed_resize_not_cancel.py.
```

---

## A.5 — Project-start path cross-effects audit  *[evidence: partial, needs DG-A5]*

**Premise:** The 2026-06-08 incident traced a cross-project fan-out in the settings router (`P1: 11033fc2`). Could there be another such path on the project-start endpoint?

### A.5 task — wait for DG-A5

Read `EVIDENCE_dgA5_project-start-paths.md` first. If no cross-project side effects exist, A.5 is closed without code change (just a regression test that pins the absence). If a side effect is found, fix it at the source.

### A.5 commit shape

```
fix(pipeline): project-start path has no cross-project side effects

Phase 145 Thread A.5. <evidence: cross-project trigger found / no
cross-project trigger found>. Adds regression test analogous to
test_settings_pipeline_config_no_fanout.py.

Tests: tests/test_phase145_project_start_no_cross_effect.py.
```

---

## A.6 — Drain-timeout surfaced as visible failure  *[evidence: partial, needs DG-A4]*

**Premise:** Phase 91 §Drain Timeout: when swarm or exclusive needs other projects' stages to drain, after 10 min the draining stage is force-cancelled with reason `"drain_timeout"`. The user reported NO surfaced failure when Project A's work disappeared. So either (a) drain_timeout fired and the event was swallowed, or (b) it didn't fire (other mechanism caused the loss).

### A.6 task — wait for DG-A4 events stream

If DG-A4's `/events` capture shows a `drain_timeout` event, the bug is in the UI's event handling (it's not surfacing). If no `drain_timeout` event, A.6 is closed; the work loss came from elsewhere (A.4).

### A.6 commit shape — UI thread

```
fix(ui): drain_timeout cancellations surface as visible failed state

Phase 145 Thread A.6. drain_timeout cancellations were correctly
firing on the backend per the journal but never appeared in the
dashboard, so the user saw work "disappear" with no error. Adds
event handling for the drain_timeout SSE event + a failed-state
badge with reason="Cancelled to make room for higher-priority work".

Tests: packages/ui/src/components/.../__tests__/DrainTimeoutBadge.test.tsx.
```

Vitest prerequisite same as Thread D in the B/C v2 proposal — if D1 (vitest setup) hasn't shipped, do it here first.

---

## A.7 — Stage workers dynamically resize via capacity_changed subscription  *[evidence: partial, needs DG-A3 + DG-A6]*

**Premise:** Per Phase 91 §Capacity Change Broadcast subscription contract: batch engines register a callback when they start; the callback resizes the stage's semaphore. The user's symptom — solo project still capped at 2–4 even when budget should be 10 — could be a stale semaphore created at stage-start with a value that AIMD has since raised.

### A.7 task — wait for DG-A3 + DG-A6

The `EVIDENCE_dgA6_semaphore-lifecycle.md` audit will reveal which batch engines actually subscribe and which ones cache a stale value. For each engine that doesn't subscribe, the fix is to add a `scheduler.on_capacity_change()` call at engine startup that resizes its `asyncio.Semaphore` value when fired.

### A.7 commit shape

```
fix(workers): epistemic_enrichment + group_reasoning subscribe to capacity_changed

Phase 145 Thread A.7. Stage worker semaphores were created at
stage-start with a snapshot of dynamic_capacity and never resized;
when AIMD or fair-share later raised the limit, in-flight concurrency
stayed pinned at the old value. Adds capacity-change subscriptions
per Phase 91 §Capacity Change Broadcast contract.

Tests: tests/test_phase145_stage_workers_capacity_subscribe.py.
```

---

## Cross-cutting invariants this whole thread must restore

Five contracts lifted from `FINDING_concurrency-undershoot-and-cross-project-work-loss.md` §5. Every sub-thread must preserve all five:

1. **Manual concurrency override is a floor for the user, not a ceiling for discovery.** AIMD steps down only with direct throttle evidence; the floor is the configured `llm_concurrency_deep`.
2. **Sole active project gets the full budget.** N=1 → share = budget (Phase 91 §Tier 4).
3. **Boost weighting is 2:1.** 1 boost + 1 normal at budget=10 → 7/3 split.
4. **Contention resizes; it does not destroy work.** `capacity_changed` resizes the running stage's semaphore; cancellation only on `drain_timeout` (default 600 s) with visible reason.
5. **Queued swarm does not dispossess.** A second project's queued swarm stage doesn't preempt the first project's in-flight non-swarm work.

A scrutiny pass should verify every sub-thread preserves every invariant.

---

## Risk register

| # | Risk | Mitigation in this proposal |
|---|---|---|
| RA1 | A.2 ships first; if A.2's "manual is a floor" change happens to mask a deeper bug A.3 was supposed to find, we lose the diagnostic signal. | Run DG-A1 + DG-A2 + DG-A3 *before* A.2. Capture solo-baseline + concurrency events *first* so A.3 still has evidence. Then A.2 ships. Then re-capture for A.3. |
| RA2 | The "manual is a floor" fix (A.2) accidentally disables AIMD's ability to throttle down on real 429s, leading to thrashing. | A.2.1's third test (`test_aimd_steps_back_up_to_manual_override_after_clean_window`) implies AIMD CAN step down on throttle evidence. The "floor" only applies when *no throttle evidence has been observed*. Tighten the test before authoring code. |
| RA3 | A.7's "subscribe to capacity_changed" wiring per stage is mechanical but error-prone (six batch engines, six places to add a subscription). | Refactor: add a `ScalingSemaphore` helper in `src/prep/services/pipeline/scheduler.py` that wraps `asyncio.Semaphore` and subscribes itself. Every batch engine uses the helper instead of `asyncio.Semaphore` directly. One place to test, six places to import. |
| RA4 | A.4's resize-not-cancel fix could be in an `await` path where dropping references causes the semaphore to actually shrink in-flight work via task cancellation (Python semantics, not bug). | Test with high parallelism so the difference is visible. If RA4 manifests, the fix is `new_size = max(in_flight, new_budget)` — never shrink below in-flight; let natural completion drain. |
| RA5 | Drain-timeout (A.6) UI fix lands but the backend was wrong about firing it; user sees a "drain_timeout" badge for something that wasn't actually drained. | A.6 is gated on DG-A4 showing the event actually fires. If DG-A4 doesn't show it, A.6 doesn't ship — A.4 handles the work-loss root cause. |
| RA6 | Diagnostic A.1 needs both projects in a specific state to reproduce; if Applifier has been Force-Reset to clear the §2l deadlock, the §2k reproduction may be harder. | Use any two large-enough projects; the bug is structural to the scheduler, not Applifier-specific. SkyPath-Restart + a fresh local repo should suffice. |
| RA7 | This proposal touches the scheduler (a hub file by `prep_impact`). A regression here breaks every project's pipeline. | Heavy reliance on `tests/test_scheduler_*` regression tests (audit which exist via `ls tests/test_scheduler_*.py`). Before any A.2 commit, run the full pipeline test suite. After A.4 and A.7 commits, run live smokes on at least three projects. |

---

## Open questions for the scrutiny pass

1. Is the A.1 → A.2 ordering safe given RA1? Should A.2 wait for *all* of A.1, or only DG-A1–A3?
2. Is the proposed `ScalingSemaphore` helper (RA3) the right abstraction, or does it overlap with something the scheduler already has (read `scheduler.py` for existing semaphore wrappers before adding a new one)?
3. Should A.6 (drain-timeout surfacing) be reframed as a Thread D-style independent UI defense rather than gated on DG-A4? It's defense-in-depth either way.
4. The "Option A vs Option B" choice in A.2.2 (AIMD step-down floor vs starting limit) — which is more consistent with how Phase 82 and Phase 119 documented AIMD's intended behavior?
5. Does Phase 91's "swarm cooldown" interact with A.4? If a swarm window closes and another opens within 45 s, does `capacity_changed` fire twice with potentially contradictory `new_budget` values? Worth a unit test even if not user-observed yet.
6. Is the `dynamic_capacity` field in the scheduler's per-node status (visible in DG-A2 output) the right signal for A.3's audit, or is there a more authoritative budget signal we should read instead?

---

## How to scrutinize this proposal

Same workflow as the v2 B/C proposal:

1. Verify RA1–RA7 are still accurate. Add anything missed.
2. Cross-check each sub-thread's `[evidence: …]` label against what's actually in the corpus.
3. Confirm A.2 can really ship without DG-A1–A3 running first (RA1 says it shouldn't).
4. Run `prep_impact` on `src/prep/services/pipeline/scheduler.py` and `src/prep/services/build_orchestrator.py` to confirm the change-radius is what we think it is.
5. For each curl in A.1, validate that the URL / port / project ID is still current.
6. If new defects are found, record them as DA1, DA2, … in a fresh banner at the top, and write v2.

Scrutiny output goes inline as a `## Scrutiny pass — YYYY-MM-DD` section near the top of this file, or as a separate `SCRUTINY_v1_thread-A.md` if the analysis is large.

---

## What this proposal does NOT propose

These are deliberate omissions so the scrutiny pass can confirm they belong out-of-scope:

- **No redesign of Phase 91.** We're restoring its contract, not changing it. If Phase 91's contract itself is wrong (e.g., the 7/3 split is the wrong policy), that's a separate phase.
- **No changes to AIMD probe behavior.** Only the *interaction* of AIMD's result with the manual override is in scope.
- **No drain-timeout config UI.** The drain timeout stays at 600 s default; making it configurable per-project is post-MVP work.
- **No swarm policy changes.** Whether stage X *should* swarm under Y conditions is Phase 79 territory.
- **No new event types.** A.6 surfaces an existing `drain_timeout` event in the UI; it doesn't invent new events.

---

## Cross-references

- Finding: `FINDING_concurrency-undershoot-and-cross-project-work-loss.md` (root, §3 hypotheses H1–H6, §4 evidence commands, §5 design invariants).
- Phase 91 design: `docs/Phase91_QueueRefinement/01_Resource_Allocation_Design.md` (canonical contract).
- Phase 82 (AIMD discovery): `docs/Phase82_CloudPipelineConcurrency/02_Design_Spec.md`, `docs/Phase82_CloudPipelineConcurrency/01_Latency_Aware_Discovery.md`.
- Phase 79 (swarm): `docs/Phase79_Swarm/02_Swarm_Integration_Design.md`, `docs/Phase79_Swarm/06_Pipeline_Stage_Execution_Profiles.md` (line 110 — "Swarm: full slot budget (bypasses fair-share)").
- Phase 119 (concurrency stability): `docs/Phase119_ConcurrencyStability/02_Implementation_Plan.md`.
- Phase 121 (Ollama concurrency UX): `docs/Phase121_OllamaConcurrencyUX/`.
- Phase 136 Part 15 (observability instrumentation, commit `cac65709`): `docs/Phase136_Dogfood-fixes/`.
- Prior cross-project fan-out fix: commit `11033fc2` (P1, settings router).
- Code: `src/prep/services/pipeline/scheduler.py`, `src/prep/services/build_orchestrator.py`, `src/prep/core/epistemic_enrichment.py`, `src/prep/core/group_reasoning.py`, `src/prep/services/pipeline/workers/`, `src/prep/api/routers/projects/build.py`, `src/prep/api/routers/system.py`.
