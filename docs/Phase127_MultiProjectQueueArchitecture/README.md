# Phase 124 -- Multi-Project Queue & Priority Architecture

> **Scope:** Unify the priority, queueing, and swarm-window mechanisms in
> the pipeline scheduler so multi-project workloads are predictable,
> fair, and free of the bugs Phase 119 surfaced (cooldown blocking,
> swarm-state mismatches, ambiguous priority-vs-swarm interactions).
> **Prior art:** Phase 72B (multi-project priority), Phase 82 (latency-
> aware concurrency), Phase 91 (swarm window mechanic), Phase 119 (swarm
> coordinator quality), Phase 119+ (swarm window authority correction
> in commit `9c9eb037`).
> **Status:** Design approved by user, implementation plan pending
> **Date:** 2026-05-03

---

## 0. Getting started (next agent, read this first)

This phase is a **scheduler refactor** with strict no-regression
requirements. Single-project pipelines are working end-to-end as of
Phase 119; this work must not break that.

### Recommended first session

1. **Read §1 (Problem Statement) and §2 (Design Principles)** to
   understand what we're correcting.
2. **Read §3-§7** for the mechanism details. They describe the
   *behavior*; implementation choices come later.
3. **Read §13 (Regression Risk Assessment)** before touching code.
   The single-project flow must continue to work after every commit.
4. **Read §16 (Rollout Strategy)** — work is sequenced into 5 phases.
   Implement them in order; each ships independently.
5. Build the **soft-hold primitive first** (Rollout Phase 1). It's
   the shared mechanism between exclusive and swarm-drain. Get it
   right and tested with a single-project no-op case before extending
   to multi-project.

### What's already known good

- Phase 119 routing fix (`fe8a144e`): coord calls land on the right
  scheduler slot via endpoint_id propagation.
- Phase 119 timeouts (`1e99311b`): cloud coord 180s, synth 240s.
- Phase 119+ swarm window authority (`9c9eb037`): `is_swarm` is now
  driven by `window_matches OR role_tagged_call`, not `live_workers >= 2`.
- Phase 119+ scrutiny pass (`a2eaaf32`): atlas timeout, dropped the
  `-1` reservation, AIMD soft-MD test.

### What this phase explicitly does NOT do

- Touch the LLM client or worker dispatch logic beyond adding a
  soft-hold check.
- Change the AI Gateway endpoint configuration.
- Modify priority levels or weighted-share math (already correct).
- Address UI rendering — coordinate with the other agent's UI
  truthfulness work; this phase only ensures backend produces the
  data the UI needs.
- Cross-machine coordination (out of scope; see §15).

### Glossary

- **Slot**: a `ComputeSlot` representing a compute node (e.g.,
  `cloud:default_ollama`). Tracks `current_load`, `dynamic_capacity`,
  `active_stages` (per-project).
- **Endpoint**: a saved configuration entry mapping a model + URL +
  provider. Identified by `endpoint_id`. Multiple endpoints can map
  to a single scheduler slot (e.g., the OpenRouter endpoint maps to
  `cloud:ep_…`).
- **Swarm window**: a globally-exclusive marker held by a
  `SwarmOrchestrator`-driven stage. Blocks others on conflicting
  endpoints.
- **Soft-hold**: a per-(project, endpoint) signal that says "no new
  LLM dispatches; let in-flight finish; checkpoint and pause."
- **Drain**: the natural reduction of in-flight calls to zero on a
  given slot, as worker dispatches stop and existing calls complete.

---

## 1. Problem statement

The scheduler accumulated three priority/concurrency mechanisms in
separate phases, each with overlapping responsibilities and unclear
interaction rules:

1. **Phase 72B priority levels** (`none`, `boost`, `exclusive`) at
   `scheduler.py:42`, weighted into the fair-share split formula at
   `scheduler.py:1869`.
2. **Phase 82 latency-aware concurrency** (AIMD, multi-cloud-node
   capacity discovery).
3. **Phase 91 swarm window** (`scheduler.py:1408`), a globally
   exclusive marker for stages requiring full budget.

Each was correct in its own scope but their interactions were
underspecified. Concrete bugs surfaced in Phase 119:

- **Cooldown blocking**: the `_swarm_cooldown_seconds: 45.0` between
  consecutive swarm windows blocked the next stage even on the same
  project (atlas → concepts ran with SwarmOrchestrator active but the
  scheduler window was blocked, creating a false UI state).
- **`is_swarm` detection mismatch**: `is_swarm` required
  `live_workers >= 2`, which failed during coord and synth phases
  (intrinsically 1-worker by design). Patched in `9c9eb037` by adding
  the role-tag fallback signal.
- **Ambiguous priority-vs-swarm interaction**: nowhere documented
  what happens when a user clicks Exclusive on Project A while
  Project B has a swarm in progress.
- **No project-level "hold" indicator**: when one project blocks
  another, there's no visible held state for the user.
- **Drain semantics unclear**: today other projects' active stages
  drain "naturally" with a 10-min timeout; new stages can keep
  starting on those projects, piling up work that delays the swarm.

This phase resolves these by defining three **orthogonal mechanisms**
with explicit interaction rules.

---

## 2. Design principles

| Principle | Application |
|---|---|
| **Orthogonality** | Boost, Exclusive, and Swarm are independent state. A project can be `boost` AND on a swarm stage. Interactions are explicit, not emergent. |
| **No regressions on single-project flow** | Single-project pipeline is the canonical path. Multi-project logic must be *additive*: when only one project runs, behavior is identical to today. |
| **Anti-thrash by construction** | Don't add timer-based cooldowns. Order of operations and queue semantics should naturally prevent ping-pong. |
| **Soft-block over hard-pause** | Held projects let in-flight calls finish naturally. Workers stop *dispatching* new calls; they don't kill threads. |
| **One mechanism, one purpose** | Soft-hold is a single primitive shared by exclusive's preempt and swarm's drain. Not two separate state machines. |
| **Explicit user intent wins** | If the user opts into Exclusive, the system honors it even at the cost of progress on other projects. |
| **The UI must reflect reality** | Every backend state (held, queued, draining, exclusive-blocked, swarm-active) needs a distinct UI surface. |

---

## 3. The three mechanisms

The scheduler tracks three independent kinds of priority/exclusivity:

### 3.1 Boost

| Property | Value |
|---|---|
| Scope | Project-wide |
| Effect | 2× weight in `_weighted_share()` formula (`scheduler.py:1869`). |
| Concurrency | Multiple projects can hold `boost` simultaneously. |
| Lifetime | Set/unset via UI/API. Persists across daemon restarts. |
| Interaction with swarm | Boost projects skip ahead in the swarm-waiter queue (boost-weighted FIFO). |
| Interaction with exclusive | Boost is irrelevant when another project is exclusive. |
| Behavior under no-conflict | Just splits resources proportionally. |

### 3.2 Exclusive

| Property | Value |
|---|---|
| Scope | Project-wide |
| Effect | Full cloud budget. Other projects' in-flight stages soft-held. New acquires by other projects are blocked. |
| Concurrency | Only ONE exclusive at a time globally. Setting exclusive on a new project demotes existing exclusive holders to `boost`. |
| Lifetime | **Manual only** — set/unset by user click. No auto-clear. (Per Q4-A in brainstorm.) Persists across daemon restarts. |
| Interaction with swarm | Exclusive blocks new swarm windows on conflicting endpoints. Existing swarm window in progress when exclusive is set: that swarm is soft-held mid-stage, resumes when exclusive lifts. |
| UI indicator | Held projects must show distinct "Held — exclusive on Project X" status (Q2 requirement). |

### 3.3 Swarm window

| Property | Value |
|---|---|
| Scope | Stage-level (one swarm-capable stage of one project). |
| Effect | Globally exclusive marker. All other projects' active stages on conflicting endpoints get soft-held. The swarm gets full budget for the stage's duration (coord + fanout + synth). |
| Concurrency | Only ONE swarm window globally at a time. |
| Lifetime | Open at stage start, close at stage end. **No cooldown** (Q6-E). |
| Interaction with priority | Swarm window auto-claims exclusivity for that stage. Doesn't change the project's `boost`/`exclusive` field. |
| Interaction with exclusive | If exclusive is held by a different project, swarm waiter is blocked. (Exclusive wins.) |
| Queue position when blocked | Boost-weighted FIFO (Q5-B). |

---

## 4. Default concurrency model (no swarm, no exclusive)

When no swarm window is open and no project is exclusive, multiple
projects' pipelines run **simultaneously**. The cloud node's capacity
is split via the existing `_weighted_share()` formula:

- 2 boost projects + 2 normal projects on a cap=10 node:
  - boost weight 2, normal weight 1; total weight 6.
  - Each boost gets `floor(10 * 2/6) = 3` workers.
  - Each normal gets `floor(10 * 1/6) = 1` worker.
  - Remainder distributed to boost projects (so 3+1+3+1=8, plus 2 to
    boost: 4+1+4+1=10).
- 1 boost + 0 others: boost gets full budget (single-project path).

There's **no queue** for normal pipeline stages. They share concurrency
directly via `acquire_request_ctx` against the AIMD gate. The gate
hands out tokens by current capacity; weighted-share already accounts
for priority via project's allocation.

Anti-thrash is implicit: workers acquire tokens, run, release. Stage
boundaries don't trigger "yield to queue" decisions because there's
no queue to yield to.

---

## 5. Swarm window lifecycle

### 5.1 Open phase

```
Pipeline orchestrator: "stage X is swarm-capable; trying to open window"
  ↓
scheduler.open_swarm_window(project_id, stage)
  ↓
Check 1: Is another project exclusive? → if yes, BLOCK (return False).
Check 2: Is another swarm window already open? → if yes, BLOCK.
Check 3: Pass → mark window open, identify drain targets.
  ↓
Drain targets = {pid: started_at for pid in slot.active_stages if pid != project_id}
  ↓
For each drain target: scheduler signals "soft-block dispatches on conflicting endpoints"
  ↓
Window state recorded: {project_id, stage, started_at, drain_targets, endpoints}
```

### 5.2 Drain phase

The drain phase is the new soft-block-driven semantic (Q7-C):

- For each drain-target project, the scheduler sets a per-(project,
  endpoint) soft-hold flag.
- Drain-target workers check this flag before each LLM dispatch. If
  set, the worker:
  - Lets in-flight LLM calls finish naturally.
  - Stops dispatching new calls.
  - Saves a checkpoint (worker checkpoints at item granularity for
    augmenter/epistemic; phase boundary for SwarmOrchestrator).
  - Enters "soft-held" state.
- The scheduler watches `slot.in_flight_requests` for each drain target.
  When all conflicting in-flight calls have completed, the swarm
  proceeds.
- During the drain, the swarm's coord call CAN run if its endpoint
  doesn't conflict with the drain targets (e.g., coord on OpenRouter
  while workers drain on Ollama Cloud). This minimizes wall-clock
  delay.

### 5.3 Run phase (coord → fanout → synth)

The swarm runs all three phases under the same window. The window
persists across phase transitions. `is_swarm` stays true throughout
(per `9c9eb037` — the role-tag fallback ensures detection survives
phase boundaries).

### 5.4 Close phase

```
SwarmOrchestrator.run() returns (synth complete)
  ↓
Pipeline orchestrator: stage X complete → release()
  ↓
release() detects: this project owns the swarm window
  ↓
scheduler.close_swarm_window()
  ↓
Window state cleared. NO COOLDOWN.
  ↓
Soft-hold flags for drain targets are cleared.
  ↓
If swarm-waiter queue is non-empty:
   next entry (by boost-weighted FIFO) opens its swarm window immediately.
Else:
   Same project's next swarm-capable stage can immediately open its window
   if the orchestrator advances to one.
```

### 5.5 `is_swarm` authority signal

The scheduler-side window is the bureaucratic signal. The runtime
truth is telemetry's `swarm_role` tag (set by `set_swarm_role()`
ContextVar in `swarm_orchestrator.py:256, 432`). Either source flips
`is_swarm` to true:

```python
is_swarm = window_matches OR (any active call has swarm_role tagged)
```

This dual signal handles edge cases where the SwarmOrchestrator runs
without an open scheduler window (the bug Phase 119+ caught).

---

## 6. Exclusive priority lifecycle

### 6.1 Set

```
User clicks Exclusive on Project A in UI
  ↓
scheduler.set_priority(A, "exclusive")
  ↓
For each other project P with active stages on conflicting endpoints:
   Set soft-hold flag for (P, endpoint).
  ↓
A's pipeline acquires get full budget via _weighted_share (proj_level == "exclusive" branch).
```

### 6.2 During exclusive

- A's pipeline runs at full capacity per its own concurrency.
- Other projects' active stages soft-hold; their workers stop
  dispatching new calls. Existing in-flight finishes.
- New project pipelines that try to start (via `acquire()`) get
  blocked at `scheduler.py:1671`. They enter the queue.

### 6.3 Unset

```
User clicks Exclusive off in UI
  ↓
scheduler.set_priority(A, "none")
  ↓
Soft-hold flags for all other projects cleared.
  ↓
Held workers detect cleared flag → resume dispatch loop from checkpoint.
  ↓
Queued projects (if any) drain via existing release()/dequeue_next() path.
```

### 6.4 Lifecycle invariants

- Exclusive **never auto-clears** (Q4-A). User must explicitly unset.
- Persists across daemon restarts (priority state is saved in settings).
- If exclusive is set on an idle project, it has no immediate effect
  — but blocks any other project from starting. UI should warn after
  >5 min of idle exclusive.

---

## 7. Queue semantics

The scheduler maintains a queue (per-node) ONLY for two specific
blocking conditions:

### 7.1 Cases requiring queue

1. **Swarm-window waiters**: a project tries to `open_swarm_window`
   but another project has an open window. The waiter is enqueued.
2. **Exclusive-blocked acquires**: a project's pipeline tries to
   `acquire()` a slot but another project is exclusive. The waiter
   is enqueued.

### 7.2 Cases NOT requiring queue

- Two projects running non-swarm stages simultaneously: handled by
  weighted-share, no queue.
- A project's stage completing and starting the next stage on the
  same project: chains via `acquire()`/`release()`, no queue ordering.
- Same-tier projects coexisting: weighted-share handles concurrency.

### 7.3 Ordering rules

| Case | Order |
|---|---|
| Multiple swarm waiters | Boost-weighted FIFO (Q5-B): boost projects ahead of normal; FIFO within tier. |
| Multiple exclusive-blocked projects | Order doesn't matter — they all wait until exclusive lifts, then they all unblock. The first to acquire wins by AIMD timing. |
| Mixed (some swarm waiters + some exclusive-blocked) | Exclusive-blocked clears when exclusive lifts (a separate event). Swarm waiters clear when current swarm closes. The two conditions are independent. |

### 7.4 Cooldown removal

The `_swarm_cooldown_seconds = 45.0` is **removed**. Anti-thrash comes
from queue ordering, not from a timer. Concretely:

- If queue has waiters when a swarm closes → next waiter immediately
  opens. No 45s wait.
- If queue is empty when a swarm closes → same project's next
  swarm-capable stage can immediately open, with no cooldown.

The queue itself is the anti-thrash mechanism: a project that just
finished swarm yields to anyone waiting before reclaiming a window.

---

## 8. Soft-hold mechanism (the shared primitive)

Both **exclusive's preempt** and **swarm-drain's soft-block** use the
same primitive, parameterized by trigger:

### 8.1 Data model

```
soft_holds: Dict[(project_id, endpoint_id), HoldReason]

HoldReason: literal "exclusive_set" | "swarm_window" | "drain_target"
```

### 8.2 Worker-side check

Worker dispatch loop (epistemic enricher, augmenter, swarm orchestrator
fan-out) calls a single function before each dispatch:

```python
should_dispatch(project_id, endpoint_id) -> bool:
    return scheduler.is_held(project_id, endpoint_id) is False
```

If False, the worker:

1. Lets in-flight LLM calls finish naturally (no thread-kill).
2. Saves a checkpoint at item boundary.
3. Pauses dispatch loop, polling `should_dispatch` periodically (e.g.,
   1s).
4. When `should_dispatch` returns True again, resumes from checkpoint.

### 8.3 Scheduler-side signal

`scheduler.set_hold(project_id, endpoint_id, reason)` and
`scheduler.clear_hold(project_id, endpoint_id)` are the two operations.

Triggers:

| Trigger | Effect |
|---|---|
| `set_priority(P, "exclusive")` for project P | Set hold for all OTHER projects on all conflicting endpoints |
| `set_priority(P, "none")` (clearing exclusive) | Clear all holds set by exclusive |
| `open_swarm_window(P)` | Set hold for all OTHER projects on conflicting endpoints |
| `close_swarm_window(P)` | Clear all holds set by that swarm window |

### 8.4 Drain detection

The scheduler watches `slot.in_flight_requests` per slot. Held projects'
in-flight count drops naturally as their workers stop dispatching.
When `slot.in_flight_requests == 0` for a held (project, endpoint) pair,
the drain is complete for that pair.

The swarm window's "ready" check waits for all conflicting drain
targets to reach in-flight == 0.

### 8.5 UI indicator (mandatory per Q2)

Every held project surfaces a distinct UI state:

- **"Held — Exclusive on Project X"** (when held by exclusive)
- **"Held — Swarm window for Project X"** (when held by drain)
- **"Held — Draining (in-flight: N)"** (intermediate state during drain)

This is **separate from "Queued"** (waiting in line for a swarm window
to open) and **separate from "Idle"** (no work to do).

---

## 9. Endpoint-disjoint exception clause

When a project is exclusive OR has an open swarm window, only OTHER
projects with conflicting endpoints are held. If an other project's
pipeline only needs DIFFERENT endpoints, it can proceed.

### 9.1 Examples

| Exclusive holder | Other project's active stage | Result |
|---|---|---|
| A on `cloud:ollama` (Kimi) + `cloud:openrouter` (Qwen coord) | B on `__embedding__` (HuggingFace local) | B proceeds — no conflict |
| A on `cloud:ollama` | B on `cloud:openrouter` (Qwen-only stage) | B proceeds — no conflict |
| A on `cloud:ollama` | B on `cloud:ollama` | B held |
| Swarm on A using `cloud:ollama` + `cloud:openrouter` | B on `cloud:openrouter` | B held (overlap) |

### 9.2 Practical relevance

Currently the AI Gateway sets endpoints **globally** for all projects.
So all projects share the same coord/worker endpoints. The
disjoint-exception clause is a no-op for typical setups.

It exists for **future power-user configurations** where endpoints
might be configurable per project, or where a project explicitly skips
certain stages (e.g., embedding-only re-index runs).

The exception clause is also forward-compatible with **per-project AI
Gateway settings** (a possible future feature). Documenting now so the
mechanism is in place when needed.

---

## 10. UI indicators

This phase produces the **backend signals** for these states. The UI
implementation is the other agent's territory (see Phase 121 for the
overall UI truthfulness work). This section enumerates what the
backend MUST surface so the UI has truthful data to render.

### 10.1 Per-project status fields

Add to running_tasks / queue API response:

| Field | Values |
|---|---|
| `state` | `running` / `held` / `queued` / `idle` / `swarm_active` / `swarm_waiting` |
| `held_reason` | `null` / `"exclusive_on_<project_id>"` / `"swarm_window_for_<project_id>"` / `"draining"` |
| `held_since` | ISO timestamp of when hold was applied |
| `priority_level` | `none` / `boost` / `exclusive` |
| `swarm_role` (if running) | `null` / `coordinator` / `worker` / `synthesizer` |

### 10.2 Global scheduler status fields

Add to `/compute/scheduler` response:

| Field | Values |
|---|---|
| `swarm_window` | `null` or `{project_id, stage, started_at, drain_status: "draining" | "running" | "closing"}` |
| `exclusive_project` | `null` or `project_id` |
| `held_projects` | `[{project_id, held_since, reason}]` |
| `swarm_queue` | `[{project_id, stage, queued_at, priority}]` (boost-weighted FIFO order) |

### 10.3 Anti-stale guarantees

- All states are computed from live scheduler state on each API call —
  no caching that could lag behind reality.
- The "draining" sub-state surfaces during the brief window between
  swarm window opening and all conflicting in-flight calls completing.
  Critical for the UI to show "X is held while N calls finish" instead
  of just appearing frozen.

---

## 11. Edge cases

| # | Scenario | Expected behavior |
|---|---|---|
| 1 | Two projects' pipelines hit a swarm-capable stage simultaneously | First to call `open_swarm_window` wins. Second is enqueued. On first's close (no cooldown), second immediately opens. |
| 2 | User clicks Exclusive on A while B's swarm is in progress | Exclusive triggers soft-hold on B. B's swarm pauses mid-phase. B's swarm session resumes from checkpoint when exclusive lifts. |
| 3 | User clicks Exclusive on A while B's pipeline is just starting fast_sync | B's stages soft-block. B's progress is preserved. |
| 4 | Exclusive set on a project that's idle | No-op for held state (nothing to hold). When user later starts pipeline on that project, it gets full budget. UI warns after 5 min idle. |
| 5 | Daemon crashes mid-swarm | See §12 (durability). Pipeline orchestrator's state machine recovers from journal; scheduler state recomputes from live priority + active-pipelines. |
| 6 | Two projects both hold `boost`, both running non-swarm stages | They share resources via weighted-share. Each gets equal share. No queue, no handoff. |
| 7 | Pipeline crash on exclusive project | Exclusive does NOT auto-clear (Q4-A). Other projects remain held until user manually un-sets. UI warns. |
| 8 | Swarm window opens while previous swarm's soft-blocked workers are still draining | Drains are project-keyed; the new swarm only soft-blocks its own conflicts. Existing soft-blocks for the closing window are released as that window closes. |
| 9 | Multiple projects all blocked by exclusive | All soft-held. When exclusive lifts, they all unblock. AIMD gate handles fairness via natural acquire timing. |
| 10 | Exclusive set, then unset rapidly (mistake click) | Held projects resume from checkpoint. No data loss (workers don't kill threads on hold). |
| 11 | A project's worker doesn't honor the soft-hold flag (bug or legacy code) | Detection is via `slot.in_flight_requests` reaching 0. If a project never drains, swarm never opens. Watchdog logs a warning after 60s of stuck drain. Future: force-release after 10 min timeout (matches existing drain-timeout for swarm window). |
| 12 | Endpoint goes unreachable during a held state | Held workers are paused; they won't notice. When endpoint recovers, they resume from checkpoint. Independent of hold state. |
| 13 | Swarm window blocked by exclusive, swarm-capable stage falls back to non-swarm | Acceptable salvage. Stage runs sequentially or in fan-out parallelism without coord. Result is correct but lower quality. |

---

## 12. State durability across daemon restart

Per user's chunk-2 request: state must persist across restart. **Not
all state, however** — some is reasonable to recompute.

| State | Persistence | Restore behavior |
|---|---|---|
| Priority levels (`_priority_projects`) | **Persist to settings store** on every change | Restored on daemon start |
| Swarm window (`_swarm_window`) | In-memory only — discarded on restart | Pipeline orchestrator's journal records "stage X started"; on restart, if X is in_progress, the orchestrator re-opens the swarm window via the standard open-window-on-stage-start path |
| Soft-hold state per (project, endpoint) | In-memory only — recomputed on restart | After restart, scheduler re-derives holds from current priority + swarm state |
| Queue (`_queues`) | In-memory only | Empty on restart. Pipelines that were queued must re-attempt acquire. Their orchestrators retry naturally. |
| Drain checkpoints | Already persisted by worker (existing pipeline checkpoint) | Held workers resume from last checkpoint on restart |

### 12.1 Phasing

User explicitly noted durability is **patchable later**. Initial
implementation can:

1. Persist priority levels (already partially implemented via settings
   store — extend tests).
2. Document swarm window + queue + holds as "in-memory; recovered from
   pipeline orchestrator journal on restart."
3. Add a separate phase later for full durability (swarm window
   journal, queue persistence) if needed.

### 12.2 Test requirements

Each phase ships with at least one test that:
1. Sets state (priority, opens swarm window, holds another project).
2. Simulates daemon restart (re-instantiates scheduler from saved
   settings + journal).
3. Asserts state is correct: priority restored, holds re-derived,
   swarm window re-opened by orchestrator path.

---

## 13. Regression risk assessment

The single-project pipeline is the canonical happy path. Phase 119
verified end-to-end. **This phase must not regress that.**

### 13.1 Risk matrix

| Area | Risk | Mitigation |
|---|---|---|
| Single-project flow | Soft-hold logic accidentally fires on the only running project | Worker's soft-hold check requires a SIGNAL from scheduler. If scheduler never sets the signal (single project case), worker dispatches normally. **Test**: run single project end-to-end before touching multi-project paths. |
| Cooldown removal | Hidden assumption elsewhere relies on the cooldown | grep for `_swarm_cooldown` and `swarm_cooldown_until` — only used by `open_swarm_window` per current inspection (`scheduler.py:1426`). **Test**: confirm `_swarm_cooldown_seconds` symbol has no remaining references after removal. |
| Boost-weighted FIFO | Today queue is plain FIFO. Switching could starve normal projects if boost projects keep arriving | Add a maximum-wait counter per queue entry. After N minutes a normal project ages into "boost-equivalent" priority. **Future enhancement**, not v1. |
| Soft-hold worker check overhead | Each LLM dispatch now checks "should I dispatch?" | Negligible — single bool read, no lock. **Benchmark**: dispatch loop overhead < 100µs per call. |
| `is_swarm` UI badge regression | Already shipped in Phase 119+ (`9c9eb037`). Stays as-is. | None — explicitly preserved. |
| `_summarize_swarm_phases` schema | Existing tests assume current shape. New `held_reason` field is additive. | Tests pass unchanged; new tests cover new field. |
| Telemetry's `swarm_role` ContextVar propagation | ThreadPoolExecutor child threads may not inherit ContextVar in older Python | Already worked around in Phase 119 via `_fallback_ctx`. No new risk. |
| Pipeline orchestrator's stage state machine | Adding "soft-held" state may interact with existing pause/resume logic | **Test**: hold then unhold a stage, verify it resumes from checkpoint with no stage_state corruption. |

### 13.2 Hard requirements

Every commit in this phase must:

1. Run the existing single-project end-to-end test (`tests/test_pipeline_*` covering full 1-15 flow).
2. Run the swarm-window/role-tag tests (`test_swarm_window_authority.py`, `test_swarm_slot_attribution.py`).
3. Run the priority/queue tests (extended in this phase).
4. Pass `mypy` and `ruff`.

### 13.3 Rollback plan

If a regression is detected, revert the specific commit. The phasing
strategy (§16) ensures each phase is independently revertible without
affecting prior phases' value.

---

## 14. Code touchpoints

Files this phase will modify (or add):

| File | Section | Changes |
|---|---|---|
| `src/prep/services/pipeline/scheduler.py` | Priority + queue + swarm window | Add soft-hold state machine; remove cooldown; add boost-weighted FIFO; expand swarm window to track endpoints |
| `src/prep/services/pipeline/scheduler.py` | `_resolve_node_for_stage` | Possibly extend to multi-node tracking (per Phase 124 Phase 3) |
| `src/prep/api/routers/queue.py` | Status reporting | Add `held` / `state` / `held_reason` fields to queue items |
| `src/prep/api/routers/llm.py` | `/llm/slots/status` | Add `held_projects` and `swarm_queue` fields |
| `src/prep/services/pipeline/workers.py` | Worker dispatch loops | Add `should_dispatch()` check before each LLM call |
| `src/prep/core/swarm_orchestrator.py` | Coord/worker/synth phase logic | Honor soft-hold within phase boundaries |
| `src/prep/core/epistemic_enrichment.py` | Worker dispatch | Same as workers.py |
| `src/prep/core/augmenter.py` | Batched augmentation | Same |
| `src/prep/services/settings_store.py` | Priority persistence | Already present; extend tests |
| `tests/test_multi_project_queue.py` | New test file | All new behavior tests |
| `tests/test_soft_hold_primitive.py` | New test file | Soft-hold mechanism tests |
| `packages/ui/src/types.ts` | Type definitions | Add `held_reason`, `held_since`, etc. (coordinate with UI agent) |

---

## 15. Out-of-scope (future phases)

Documented for future revision; **not addressed in this phase**.

### 15.1 Cross-machine coordination (Teams / Enterprise)

Current design assumes:
- Single daemon process
- Single machine
- All scheduler state is in one Python process's memory

For Teams/Enterprise, multi-daemon coordination requires:
- Shared priority state (Redis / Postgres)
- Distributed swarm window lock (consensus protocol or DB row lock)
- Cross-daemon queue (stable ordering with multiple writers)
- Cross-daemon soft-hold signaling (pub/sub)

**Plan for revision**: when multi-machine becomes real, this phase's
design will need adaptation. Specifically:
- Priority state moves from settings_store to shared store.
- Swarm window becomes a distributed lock with TTL (timeout-based
  release if daemon dies).
- Queue becomes a shared ordered list with optimistic concurrency.
- Soft-hold signals via pub/sub (each daemon subscribes to a topic
  per project_id; scheduler publishes hold/unhold events).

**Backward compatibility**: this phase's data model should be a strict
subset of the future distributed model. Avoid scheduler API choices
that are intrinsically single-machine-only.

### 15.2 Other deferred items

- **Per-project resource limits** (e.g., "Project X never gets more
  than 4 workers"). Out of scope.
- **Time-of-day scheduling** ("boost off-peak only"). Out of scope.
- **Cost-aware scheduling** ("prefer cheaper endpoint when load is
  low"). Out of scope.
- **Dynamic priority** ("auto-promote to boost after 10 min in queue").
  Future enhancement.
- **Project-level cancellation cascade** ("cancel project A → also
  cancel all its pipelines"). Already handled by orchestrator.

---

## 16. Rollout strategy

This phase ships in **5 sub-phases**, each independently revertible.

### Phase 124.1 — Soft-hold primitive

Build the worker-side `should_dispatch()` check + scheduler-side
`set_hold` / `clear_hold` API. **No callers yet.** Test with
single-project (no-op). Then test with two projects + manual
priority changes.

**Goal**: get the primitive correct before any users (callers).

### Phase 124.2 — Cooldown removal + queue refactor

Remove `_swarm_cooldown_seconds`. Replace with queue-driven ordering.
Implement boost-weighted FIFO. Update tests.

**Risk**: this phase touches the swarm window's most active code path.
Test thoroughly with single-project + multi-project + same-project
back-to-back swarm.

### Phase 124.3 — Endpoint-disjoint exception clause

Track endpoint sets in swarm window + exclusive state. Allow
non-conflicting acquires through. Mostly bookkeeping; small risk.

### Phase 124.4 — UI signal integration

Surface `held_reason` / `state` / `swarm_queue` in API responses.
Coordinate with UI agent to render. No backend behavior change.

### Phase 124.5 — Durability hardening

Persist priority + swarm window state. Restore on daemon restart.
Add restart-recovery tests. (Optional extension per user's "patch
later" note.)

### 16.1 Each sub-phase ships with

- Updated tests (regression + new behavior)
- Documentation update if behavior visibly changes
- Single-project full pipeline regression test passing
- Multi-project soak test (manual or automated): two pipelines running
  simultaneously, verify no deadlocks/starvation/wrong holds

### 16.2 Sequencing rationale

- Soft-hold primitive first (no callers means safe to iterate)
- Cooldown removal next (uses primitive, but standalone-testable)
- Endpoint-disjoint after (enhances 124.2's queue logic)
- UI signals last (depends on stable backend behavior)
- Durability is a separate slice with its own tests

---

## 17. Open questions for reviewers

These were not fully resolved in brainstorming and should be flagged
during plan review:

1. **Maximum drain wait**: today swarm window has a 10-min drain
   timeout. With soft-hold being faster (no new dispatches), do we
   keep the 10-min timeout, reduce it, or remove it? Default
   recommendation: reduce to 5 min, log a warning, and fail-fast
   if drain stuck.
2. **UI warning threshold for idle exclusive**: is 5 min the right
   threshold? Configurable?
3. **Boost-weighted FIFO starvation guarantee**: should we add an
   age-based promotion (normal → effective-boost after N minutes)
   to prevent starvation? Default: NO; user discipline expected,
   add if observed.
4. **Soft-hold polling cadence**: workers check `should_dispatch`
   on every loop iteration. If a worker is idle (waiting on an LLM
   call), how does it learn the flag changed? Default: check at
   call boundaries; for long calls, the flag check happens after
   call completion, before next dispatch. Adequate for typical
   30-180s LLM calls.

---

## 18. Cross-references

- Phase 72B (multi-project priority): `scheduler.py:286, 532, 1869`
- Phase 82 (latency-aware concurrency): `scheduler.py:608` and AIMD doc
- Phase 91 (swarm window): `scheduler.py:1408, 1466`
- Phase 119 (swarm coordinator quality): commits `fe8a144e` …
  `a2eaaf32`
- Phase 119+ (swarm window authority): commit `9c9eb037`
- Phase 121 (Ollama concurrency UX): `docs/Phase121_OllamaConcurrencyUX/`
- Phase 122 (feature utilization audit): `docs/Phase122_FeatureUtilizationAudit/`
- Brainstorm transcript: this README is the spec emitted by the
  brainstorming session 2026-05-03

---

## Approval

Design approved by user 2026-05-03 (multi-step Q&A in chat).
Ready for implementation plan via `superpowers:writing-plans`.
