# Part 13 — Swarm resource contention: two SwarmOrchestrators racing

> **Status:** **FIXED 2026-05-18** — 9 regression tests landed, plus
> 2 updated existing tests.
> **Trigger:** 2026-05-18 dogfood — Thinking endpoint showed three
> concurrent loads on a single project rebuild plus a cross-project
> stage running through the supposed swarm reservation.
> **Work order:** insert after Part 12 (resource correctness, contained
> Python fix).

## Dogfood evidence

User screenshot 2026-05-18 captured the LLM activity strip:

```
Thinking 11×  kimi-k2.6:cloud
  ↺ Module Synthesis  4× Swarm  on SourcePrep
  ↺ Deep Reasoning             on SkyPath-Restart
  ↺ Group Reasoning   6×       on SourcePrep
```

By design, when a SwarmOrchestrator opens on an endpoint it should be
the SOLE consumer — that's the entire point of opening a swarm
window. Instead the endpoint was hosting:

- 4 Module Synthesis workers (the "official" swarm)
- 6 Group Reasoning workers (a SECOND swarm on the same project)
- 1 Deep Reasoning worker on a different project (SkyPath-Restart)

## Two distinct gaps

### Gap #1 — Stage workers don't consult scheduler ownership

`src/prep/core/cluster.py:1988-1992` and
`src/prep/core/group_reasoning.py:893-897` decided `use_swarm`
locally:

```python
use_swarm = (
    swarm_tier.can_coordinate
    and swarm_enabled
    and len(to_synthesize) >= min_threshold
)
```

The orchestrator (`services/pipeline/orchestrator.py:2324-2331`)
calls `pipeline_scheduler.open_swarm_window(...)` before the stage
runs. When that returns False (another window is already open), the
orchestrator logs `"# stage runs with normal (non-swarm) budget —
fine"` — **but the stage never finds out**. It walks straight into
`_run_swarm()` and spawns its own SwarmOrchestrator.

That's how SourcePrep ended up with two SwarmOrchestrators at once:
Module Synthesis opened the scheduler's single window first; Group
Reasoning's `open_swarm_window` returned False; both stages fired
their own swarm orchestration regardless.

### Gap #2 — New arrivals after window-open aren't held

`scheduler.py:open_swarm_window` snapshots `slot.active_stages` at
the moment it opens and stamps soft-holds on those projects:

```python
for pid in slot.active_stages:
    if pid == project_id:
        continue
    drain_targets[pid] = now
    self._holds[HoldKey(project_id=pid, endpoint_id=ep)] = ...
```

A project that becomes active AFTER the window opens isn't in
`active_stages`, so no hold is stamped for it. The stage-level
`acquire()` returned False (correct), but in-flight workers and any
worker that goes through `acquire_request` (LLM-call slot) without
a corresponding `is_held` check kept dispatching.

## Fix delivered

### Gap #1 — `pipeline_scheduler.is_my_swarm_window(project_id, stage)`

New helper at `scheduler.py`. Returns True iff the active window is
owned by `(project_id, stage)`. Accepts `None` stage to match "any
stage of this project," and accepts both `StageId` enum values and
raw strings.

Wired into both stage workers:

- `cluster.py` (~line 1996): when `use_swarm` is True, additionally
  check `is_my_swarm_window(self.project_id, StageId.CLUSTERING)`.
  If False, log + flip `use_swarm = False` → falls through to the
  existing batched/sequential dispatch path.
- `group_reasoning.py` (~line 901): same pattern with
  `StageId.GROUP_REASONING`.

Both files have existing non-swarm paths (cluster has batched /
sequential; group_reasoning has sequential), so the fallback is
free — no new dispatch code needed.

### Gap #2 — Stamp soft-hold on swarm-blocked acquire

`scheduler.py:acquire()` now stamps a hold when `_is_blocked_by_swarm`
returns True:

```python
if self._is_blocked_by_swarm(project_id, resolved):
    owner = self._swarm_window.get("project_id") if self._swarm_window else None
    if owner and owner != project_id:
        self._holds[
            HoldKey(project_id=project_id, endpoint_id=resolved)
        ] = HoldEntry(reason="swarm", set_by_project=owner)
    return False
```

Arrival is now symmetric with the open-time snapshot. Any worker for
the arriving project that polls `is_held(project_id, endpoint_id)`
will pause via the existing soft-hold contract.

## Tests

`tests/test_swarm_ownership_gate.py` — 9 new tests:

- `TestIsMySwarmWindow` (6): no window, owner+stage match, different
  project, different stage same project, None stage matches any
  stage, string stage accepted.
- `TestArrivalHoldOnSwarmActive` (3): arrival during swarm stamps
  hold, owner acquire doesn't self-hold, no hold without window.

Plus existing test updates in `test_group_reasoning_swarm.py` and
`test_cluster_swarm.py` — the `test_swarm_activated_when_eligible`
tests now patch `is_my_swarm_window → True` to simulate the
scheduler granting the window.

**31 passing across all swarm/group tests** (9 new + 22 existing).

## Expected behavior post-fix

When Module Synthesis opens the swarm window:
1. Module Synthesis: spawns its SwarmOrchestrator (granted).
2. Group Reasoning (same project, different stage): asks
   `is_my_swarm_window(SourcePrep, GROUP_REASONING)` → False (owner
   is CLUSTERING) → falls back to sequential dispatch.
3. SkyPath-Restart's stage tries to acquire on the same endpoint:
   stage-level `acquire()` returns False AND stamps a soft-hold →
   the stage queues; any in-flight workers see `is_held` True and
   pause.

Net effect on the Thinking endpoint: ONE SwarmOrchestrator at a
time, full capacity reservation honored.

## Deferred to follow-ups (NOT fixed in this Part)

### Part 13b — Cluster ID stability (parallel to Part 12)

`src/prep/core/cluster.py` uses `cluster_id = f"cluster:{tag}:{idx}"`
where `idx` is a sequential counter assigned during a single run.
If the count of clusters with the same tag shifts between runs, all
those indices renumber → similar cache-invalidation pattern to the
group_reasoning bug Part 12 fixed.

Less hash-sensitive than group_reasoning (the tag is semantic and
stable, the index is the volatile bit), but still real. Needs its
own investigation + Jaccard-style overlap fallback.

### Part 13c — Same-project stage drain (design question)

The CURRENT design lets the owning project's OTHER stages run
concurrently with its own swarm window — see `_is_blocked_by_swarm`:
`if window["project_id"] == project_id: return False`. Combined with
the Gap #1 fix, this means same-project stages fall back to
sequential dispatch but still consume some endpoint capacity.

The user's mental model is "swarm owns ALL resources." If we want to
match that intent strictly, owner-project stages should also drain
during the window. This is an ARCHITECTURAL question because:

- It could deadlock pipelines where stage N depends on stage N-1's
  output and N-1 is the swarm-owning stage (rare but possible).
- It changes throughput characteristics — most projects today
  benefit from same-project concurrent stages.

Tracked as a future design pass. The Gap #1 fix already addresses
the worst case (two swarms racing); this would just tighten further.

### Part 13d — `acquire_request` doesn't take project_id

The request-level slot acquire (`acquire_request` /
`acquire_request_ctx`) is the entry point for individual LLM-call
in-flight slots. It doesn't know which project it's for, so it can't
consult `_is_blocked_by_swarm`. Workers that go through this path
without ALSO polling `is_held` could bypass the hold contract.

Fix shape: thread `project_id` through `acquire_request` (and its
callers) so the request-level gate can also respect swarm
ownership. Moderate-sized change — touches every LLM-call call site.

Tracked for later.

## Cross-refs

- `docs/Phase82_MCP-Dogfooding/` — methodology baseline
- Phase 91 swarm window (the original design)
- Phase 127 soft-hold primitive (`services/pipeline/holds.py`)
- Phase 136 Part 12 (group_reasoning cache invalidation — sibling
  finding, also surfaced by the 2026-05-18 dogfood pass)
- User dogfood screenshot 2026-05-18 (LLM activity strip)
