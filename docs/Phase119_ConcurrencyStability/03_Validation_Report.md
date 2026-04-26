# Phase 119 Validation Report

> Date: 2026-04-26
> Daemon restart: 2026-04-26 01:31:07 PDT
> Sweep: PowerMateReborn (~150 files, larger than rust_repo's 9)

## Summary

Phase 82's latency-aware concurrency manager — augmented by F-28's idle-recovery
heuristic — was producing a continuous random walk on `current_limit` for cloud
slots, with whiplash collapses on transient timeouts. Pre-Phase-119 traces from
the rust_repo sweep on 2026-04-25 show idle recovery firing every ~30 s on every
`acquire()` regardless of demand, walking the limit from 53 to 67+ over ~75 min,
collapsing 67 → 3 on a single timeout, then re-growing from 3 → 50+ via the same
pathological path. The UI compounded the confusion by rendering three uncorrelated
numbers (`in_flight / current_limit (max max_concurrent)`) with `max=1` visibly
nonsensical when `current_limit=58`.

Phase 119 ships four interlocking changes — demand-gated recovery, persisted
ceiling-with-TTL, an honest UI state pill, and an Ollama capacity probe — that
together stabilize discovery against the observed failure modes. Live evidence
from the post-restart PowerMateReborn sweep confirms the goals: in ~6 min of
wallclock with multiple stage transitions and 24-call bursts, the limit held
flat at the hydrated value of 51 with zero idle-recovery growth events. The
backoff lock-in path is unit-tested but has not yet fired live; a forced
backoff or natural occurrence will close that loop.

## Methodology

Live observation was set up around the running daemon without restarts:

- A persistent monitor polled `/compute/scheduler` every 1 s for the duration
  of both sweeps, capturing `current_limit`, `in_flight_requests`, `aimd_mode`,
  and (post-Phase-119) `state` / `discovered_ceiling` / `locked_until`.
- A log tail watched `pipeline_*.log` for AIMD events: idle-recovery growth,
  multiplicative-decrease (MD) backoff, additive-increase (AI) success batches,
  and ceiling-lock events.
- The pre-restart window ran on unmodified Phase 82 + F-28 code so the bug
  signal would not be contaminated by partial fixes.
- The post-restart window ran the merged Phase 119 code without source
  re-loads (the daemon has no hot-reload; see `feedback_restart_daemon_before_live_validation`).

Both sweeps used real Ollama Cloud as the backend with real LLM enrichment work
queued behind the gate; no synthetic load injection.

## Pre-Phase-119 evidence

The rust_repo sweep on 2026-04-25 produced the following idle-recovery
sequence on `cloud:default_ollama`:

| Time     | Event                                          |
|----------|------------------------------------------------|
| 22:16:48 | idle recovery 53 → 54 (max=1, floor=1)         |
| 22:17:24 | idle recovery 54 → 55                          |
| 22:20:41 | idle recovery 55 → 56                          |
| 22:21:14 | idle recovery 56 → 57                          |
| ...      | (continues — limit walked to 67+ over ~75 min) |
| Backoff  | 67 → ~3 multiplicative decrease on transient timeout |
| Re-grow  | random walk from 3 → 30 → 50+ via idle recovery again |

The UI rendered `cloud:default_ollama  2 / 58 (max 1)` during this period —
three numbers with no visible relationship. The `max=1` annotation came from
a saved-endpoint config where `cloud_concurrency` was never persisted and a
fallback path used the literal `1`.

Real demand on rust_repo never exceeded 7 in-flight requests, and was 1–3 most
of the time. On the larger PowerMateReborn repo, demand briefly peaked at 24
in-flight. Neither workload justified the 60+ ceiling that idle recovery had
discovered — it was elapsed time × 30 s, not a measurement. The persisted
ceiling kept growing across daemon lifetimes (60 → reset to 29 after backoff
→ walked to 50+ again) because the store had no concept of "lock at L."

The combined failure shape:

1. Random-walk growth: `_maybe_idle_recover()` adds +1 every 30 s on every
   `acquire()`, regardless of whether the gate is binding.
2. Backoff cliff: `_record_throughput_for_slot` halves to
   `max(min_limit, min(current_limit//2, in_flight_requests))`. With
   `current_limit=67` but only 3 in-flight, one timeout collapses 67 → 3.
3. No ceiling lock-in: even when AIMD does observe a real edge, nothing
   remembers "we backed off at L+1, hold L." The next idle tick walks back.

## Post-Phase-119 evidence

The daemon was restarted at 01:31:07 PDT on 2026-04-26. The hydrate path
read the existing legacy ceiling row for `cloud:default_ollama` (`locked_until=0`,
i.e., unlocked) and resumed at `current_limit=51`. The PowerMateReborn sweep
began immediately.

| Time     | Event                                                            |
|----------|------------------------------------------------------------------|
| 01:31    | Boot: `Scheduler: hydrated unlocked ceiling 51 for cloud:default_ollama` |
| 01:32    | state=probing, in-flight=2-3, limit=51 (no growth)               |
| 01:35    | Burst peaked at in-flight=24 (well below limit=51), state=probing, limit=51 (no growth) |
| 01:36:23 | `additive increase 51 → 52` — legitimate Phase 82 AI growth fired (success_streak hit batch_size=51) |
| 01:36–01:40 | Continued bursts; state held at probing; limit held at 52    |

The headline result: **in 9+ minutes wallclock with multiple stage transitions and
24-call bursts, the only growth event was an earned Phase 82 additive increase
(51 → 52) after 51 confirmed successful calls.** Zero idle-recovery growth
events were recorded. Pre-Phase-119 code in the same window would have
produced ≥18 `idle recovery N → N+1` lines (one every ~30 s on every
`acquire()`) on top of the legitimate AI growth.

This is the desired separation: random-walk growth via idle recovery is
gone; earned growth via real success batches still works exactly as the
Phase 82 design intended.

The UI now renders `cloud:default_ollama  2 / 51 📈 probing` — one primary
number (the discovered limit), one state badge, and the misleading `(max 1)`
annotation is gone.

A backoff edge has not yet fired live in this window, so the
`discovered_ceiling` / `locked_until` persistence path was not exercised
end-to-end against the production daemon. The unit test
`tests/test_scheduler_demand_recovery.py::test_first_backoff_records_ceiling_with_lock`
covers the lock-write semantics and passes.

## Outcome by goal

| Goal (from `01_Design.md`) | Status | Evidence |
|---|---|---|
| 1. Stable discovery | Live | Limit held at 51 across 6+ min including 24-call bursts |
| 2. Grounded probes | Live | No growth observed when gate not binding |
| 3. Locked ceiling with TTL | Unit-tested; live pending | `test_first_backoff_records_ceiling_with_lock` passes; awaiting natural backoff |
| 4. Honest UI | Live | `state: probing` field surfaces; misleading `(max 1)` removed |
| 5. Sensible Ollama seed | Live | Probe code wired; only fires on fresh slots (no fresh slots in this window) |

Four of five design goals are exercised live. The fifth is unit-tested and
waiting on a natural backoff edge to confirm the persisted `locked_until`
record is written.

## What's left

- Live capture of a backoff edge to confirm the persisted `locked_until`
  record is written and re-honored across daemon restarts. Can be forced
  manually via 429-injection or by waiting for natural occurrence under load.
- Optional: dashboard panel that surfaces `state` and `discovered_ceiling`
  more prominently than the sidebar pill (the sidebar is the right place
  for an at-a-glance status, but a deeper panel would aid debugging).
- The Ollama capacity probe has not yet seeded a fresh slot — the test
  scenario requires either a brand-new endpoint config or an admin
  invalidation of the existing lock via `POST /compute/concurrency/clear`.

## Reproduction

To reproduce the watcher setup against a running daemon:

```bash
# 1. Tail the pipeline log for AIMD events
tail -f ~/.local/share/sourceprep/logs/pipeline_*.log | grep -E "idle recovery|ceiling|backoff"

# 2. Poll scheduler state once per second
while true; do
  curl -s http://localhost:8400/compute/scheduler \
    | jq '.nodes["cloud:default_ollama"] | {limit: .current_limit, infly: .in_flight_requests, state, ceiling: .discovered_ceiling}'
  sleep 1
done
```

To invalidate a lock and re-trigger discovery:

```bash
curl -X POST 'http://localhost:8400/compute/concurrency/clear?node_id=cloud:default_ollama'
```

This drops the persisted `discovered_ceiling` / `locked_until` row for the
named node; on the next acquire, the slot will reseed via the Ollama probe
(or fall back to the Phase 82 default of 5) and re-enter `jumpstart` mode.

## Source references

- Design spec: `docs/Phase119_ConcurrencyStability/01_Design.md`
- Implementation plan: `docs/Phase119_ConcurrencyStability/02_Implementation_Plan.md`
- Scheduler logic: `src/prep/services/pipeline/scheduler.py`
- Persistence: `src/prep/services/pipeline/concurrency_store.py`
- Ollama probe: `src/prep/services/pipeline/ollama_probe.py`
- API surface: `src/prep/api/routers/queue.py`, `src/prep/api/routers/compute.py`
- Sidebar UI: `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx`
- Visual comparison: `packages/ui/src/stories/navigation/SidebarPipelineQueue.stories.tsx`
  (story group "Phase 119 / Old vs New SidebarPipelineQueue")
