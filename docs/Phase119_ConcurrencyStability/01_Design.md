# Phase 119 — Concurrency Discovery Stability (CDS)

> Design spec
> Date: 2026-04-25
> Builds on: Phase 82 (Latency-Aware Discovery), F-28 (idle recovery), Phase 91 (queue refinement)
> Related: docs/Phase82_CloudPipelineConcurrency/, docs/Phase96-fix-pipeline/05_FINDINGS_AND_BUGS_REGISTRY.md (F-28)

## Problem

Live observation (Apr 25, 2026 sweep on `tests/eval/sample_repos/generated/rust_repo`):

```
Scheduler: Node cloud:default_ollama idle recovery 53 -> 54 (max=1, floor=1)  # 22:16:48
Scheduler: Node cloud:default_ollama idle recovery 54 -> 55 (max=1, floor=1)  # 22:17:24
Scheduler: Node cloud:default_ollama idle recovery 55 -> 56 (max=1, floor=1)  # 22:20:41
Scheduler: Node cloud:default_ollama idle recovery 56 -> 57 (max=1, floor=1)  # 22:21:14
```

UI rendering: `cloud:default_ollama  2 / 58 (max 1)`. Persisted ceiling: 60.

Three failures combine:

1. **Random-walk growth.** F-28's `_maybe_idle_recover()` adds +1 to `current_limit` every 30 s on every `acquire()`, regardless of whether the gate was binding. Cloud has no `max_concurrent` clamp (Phase 82 is "unbounded"), so it walks upward forever without ever proving the ceiling. The 60+ persisted value is not a measurement — it's just elapsed time × 30 s.
2. **Backoff cliff.** `_record_throughput_for_slot` halves to `max(min_limit, min(current_limit//2, in_flight_requests))`. With 67 grown via idle recovery but only 3 requests in flight, a single transient timeout collapses 67 → 3. Then idle recovery starts climbing again. This is the whiplash.
3. **No ceiling lock-in.** Even when AIMD does observe a real backoff edge, nothing remembers "we backed off at L+1, hold L." The next idle recovery tick walks back to L+1 and retries the failure ad infinitum.

Plus a UI-layer issue: the panel shows three uncorrelated numbers (`in_flight / current_limit (max max_concurrent)`), and `max=1` is visibly nonsensical when `current_limit=58`. The `max_concurrent=1` value comes from a saved-endpoint config where `cloud_concurrency` was never persisted; a fallback path used `1`.

## Goals

1. **Stable discovery.** The reported ceiling should change ≤ once per backoff edge under stable load, not drift continuously.
2. **Grounded probes.** Growth happens only when the gate has been binding (real demand); otherwise no growth.
3. **Locked ceiling with TTL.** Once an edge is observed (success at L, failure at L+1), persist L as the discovered ceiling and hold it for a TTL (default 24 h). Re-probe one step after TTL.
4. **Honest UI.** One number — the discovered limit — plus a state badge (`probing | locked | backing off | recovering`).
5. **Sensible Ollama seed.** New cloud-via-Ollama slots seed at a probed value (Ollama `/api/ps` or `OLLAMA_NUM_PARALLEL`), not the literal `5` from Phase 82, and never at the legacy `1` fallback.

## Non-Goals

- Replacing AIMD with a different congestion-control family. We keep BBR-inspired AIMD; we just stabilize it.
- Per-model-family ceilings. The persisted store key is `(node_id, "__default__")` today; per-model splitting is a future phase if Kimi vs Gemini diverge.
- Removing user-visible `cloud_concurrency` settings. Users can still cap a node manually; the cap acts as a soft upper bound on AIMD growth.
- Changing local (VRAM) slot behavior. Local stays clamped at `max_concurrent`.

## Standards & Prior Art

The design is grounded in three lines of production work:

- **TCP BBR (Cardwell et al., 2016):** Probes bandwidth in cycles, then drains to clear queue. Lesson: **periodic, time-bounded probing**, not continuous growth.
- **AIMD with floor (RFC 5681 Reno; AWS Adaptive Retry):** MD on explicit failure signals (429/5xx/timeout), AI on confirmed success batches, with a floor preventing collapse to zero. Phase 82 already follows this. Lesson: **failure signals are primary; latency thresholds are unreliable** (Netflix concurrency-limits, Envoy adaptive_concurrency).
- **Bounded discovery / Hill climbing (Linkerd, Envoy circuit breakers):** Once a working operating point is found under load, **hold it** until conditions change. Don't continuously hunt. Lesson: **lock-in beats continuous probing**.

The Phase 82 design followed (1) and (2) but skipped (3). F-28's idle recovery is a workaround that makes (3) worse by growing without demand.

## Design

### Change 1 — Demand-gated growth

Replace `_maybe_idle_recover()` with a function that grows `current_limit` only when:

- The gate has been **binding** recently (`in_flight_requests >= current_limit - headroom` observed within the last `_DEMAND_WINDOW_S = 60 s`), AND
- The backoff cooldown has passed (`now - _last_backoff_time >= _BACKOFF_COOLDOWN_S = 30 s`), AND
- The recovery interval has passed (`now - _last_recovery_time >= _IDLE_RECOVERY_INTERVAL_S = 30 s`), AND
- `current_limit < discovered_ceiling` (if a ceiling is locked) OR no ceiling locked.

Mechanism:
- Add `slot._gate_binding_until: float = 0.0` — set by `acquire_request` when it observes `in_flight_requests >= current_limit` (or `>= current_limit - 1` if `current_limit > 5`). Value is `time.time() + _DEMAND_WINDOW_S`.
- `_maybe_demand_recover()` checks `now < slot._gate_binding_until` instead of unconditionally growing.

This addresses F-28's original symptom (post-backoff stuck-low) without F-28's pathology: when something is actually waiting, recovery fires; when the system is idle, it does not.

The original AIMD additive-increase path (`success_streak >= batch_size` → `+1` in congestion-avoidance, `*2` in jumpstart) is unchanged. That path already requires real success, so it's already demand-gated by definition.

### Change 2 — Ceiling lock with TTL

Extend `ConcurrencyStore` schema:

```sql
ALTER TABLE discovered_ceilings ADD COLUMN locked_until REAL NOT NULL DEFAULT 0;
ALTER TABLE discovered_ceilings ADD COLUMN edge_observed_at REAL NOT NULL DEFAULT 0;
```

(Done as `CREATE TABLE … IF NOT EXISTS` with an in-place `PRAGMA table_info` migration to add columns when the existing schema is older.)

Lifecycle:

- `mode = "jumpstart"` (initial): doubles on success batches as today. **No lock written.**
- First MD event causes `mode = "congestion_avoidance"` + records the **edge**: `edge_observed_at = now`, `discovered_ceiling = new_limit` (the post-MD value), `locked_until = now + 24h`.
- While locked: AI does not grow `current_limit` above `discovered_ceiling`. Backoff still works (collapses `current_limit`, but the ceiling stays at L; recovery climbs back to L, not above).
- Idle/demand recovery while locked: grows back toward `discovered_ceiling`, never above.
- After `now > locked_until`: a single +1 probe is allowed. If it survives a `success_streak >= batch_size` window with no backoff, the lock extends for another 24 h at the new ceiling. If it backs off, lock goes back to the old ceiling (we just observed a confirming edge).

Defaults & overrides:
- TTL default: `24 * 3600` seconds. Configurable via `settings.get("concurrency_lock_ttl_s")` for power users.
- Admin endpoint `POST /compute/concurrency/clear?node_id=...` invalidates a lock for re-detection.

### Change 3 — UI semantics

The current panel shows `in_flight / current_limit (max max_concurrent)` with `max=1` rendered when discovery has run. Replace with a single primary number plus a state pill.

API change in `GET /queue/status` `node_summary`:

```json
{
  "max_concurrent": 1,                // configured upper bound (soft, may be 0 = "unset")
  "current_load": 0,                  // active stages (count)
  "in_flight_requests": 2,            // live LLM requests
  "current_limit": 58,                // AIMD live (current operating point)
  "discovered_ceiling": 12,           // locked ceiling, or null if probing
  "locked_until": 1777170000.0,       // unix seconds, or null
  "aimd_mode": "congestion_avoidance",
  "state": "locked"                   // probing | locked | backing_off | recovering
}
```

State derivation:
- `backing_off` if `now - _last_backoff_time < _BACKOFF_COOLDOWN_S`.
- `locked` if `discovered_ceiling != null` and `now < locked_until`.
- `recovering` if `discovered_ceiling != null` and `now >= locked_until`.
- `probing` otherwise (jumpstart or first runs in congestion_avoidance pre-edge).

Frontend (`SidebarPipelineQueue.tsx`):

```
cloud:default_ollama   2 / 12  ⏸ locked     ← when discovered_ceiling=12, in_flight=2
cloud:default_ollama   3 / 8   📈 probing   ← jumpstart or pre-edge
cloud:default_ollama   1 / 6   🔻 backing off
```

Drops the misleading `(max 1)` annotation. If the user has explicitly configured a soft cap below `discovered_ceiling`, show it: `2 / 8 (cap 8)`.

### Change 4 — Sensible Ollama seed

When configuring a new `cloud:` slot for an Ollama-proxied endpoint with no persisted ceiling, probe before seeding:

```python
def _probe_ollama_concurrency(host: str) -> int:
    """Best-effort probe of Ollama's parallel-request capacity.

    Order:
      1. Read OLLAMA_NUM_PARALLEL from the daemon's environment if reachable.
      2. Fall back to GET /api/ps and count returned slots.
      3. Fall back to the Phase 82 default (5).
    """
    ...
```

Specifically, this seeds `current_limit = probe_result` with `mode = "jumpstart"`. Doubling still happens — the probe just gives us a smarter starting point.

Why this matters for the user's complaint: their saved endpoint stored `cloud_concurrency=None`, which fell through to `1`. With the probe, a fresh Ollama Cloud Max plan will seed at ~10–12 instead, and AIMD will quickly find the real edge from there.

## Implementation Map

| File | Change |
|------|--------|
| `src/prep/services/pipeline/concurrency_store.py` | Schema migration: add `locked_until`, `edge_observed_at`. New `load_full()`, `save_edge()`, `clear()` already present. |
| `src/prep/services/pipeline/scheduler.py` | Replace `_maybe_idle_recover` with `_maybe_demand_recover`. Add ceiling-aware AI clamp. Add `state` derivation in `status()`. Add `_record_edge()` helper called from MD path. Track `_gate_binding_until`. |
| `src/prep/services/pipeline/ollama_probe.py` (NEW) | `_probe_ollama_concurrency(host)` — calls `/api/version`, `/api/ps`; reads `OLLAMA_*` env. |
| `src/prep/api/routers/queue.py` | Add `discovered_ceiling`, `locked_until`, `aimd_mode`, `state` to `node_summary`. |
| `src/prep/api/routers/compute.py` | New `POST /compute/concurrency/clear` admin endpoint. |
| `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` | Replace `(max N)` with state badge; show `discovered_ceiling` when locked. |
| `tests/test_concurrency_store_lock.py` (NEW) | Lock TTL roundtrip, edge persistence, migration. |
| `tests/test_scheduler_demand_recovery.py` (NEW) | Demand-gated recovery + ceiling lock-in behavioral tests. |
| `tests/test_ollama_probe.py` (NEW) | Probe ordering: env → /api/ps → default. |
| `tests/test_queue_status_state.py` (NEW) | API surface for `state` field. |

## Migration & Compatibility

- **Persisted ceilings**: existing rows in `concurrency_store.db` are honored as discovered ceilings with `locked_until = now + TTL` on first daemon startup after the migration. Rationale: those are the values the user has been seeing; lock them in.
- **Settings**: no settings schema changes. The endpoint's `cloud_concurrency` continues to act as a soft cap if set; its absence falls back to the Ollama probe.
- **API**: `node_summary` gains fields; the existing `current_limit` and `max_concurrent` fields keep their meanings, so old clients keep rendering (just with the misleading `(max 1)` annotation, which the frontend will drop in Change 3).

## Verification Plan

1. **Unit**: each new helper has a focused test (store migration, demand-gate trigger, lock TTL roll-over).
2. **Integration**: `tests/test_scheduler_demand_recovery.py` runs a 60 s simulated workload with mocked clock, asserts `current_limit` stops growing once binding ceases, then verifies a backoff edge persists and re-grows recovery clamps at ceiling.
3. **Live smoke**: re-run the same `rust_repo` sweep that exposed the bug; tail `pipeline_*.log`, expect:
   - No `idle recovery N -> N+1` lines while no requests are queued.
   - One `discovered ceiling locked at N` line per real backoff edge.
   - UI shows a stable number across stages, with `🔒 locked` badge after the first edge.
4. **Restart**: stop daemon, restart, confirm `current_limit` hydrates to the locked ceiling (not the Phase 82 jumpstart of 5).

## Failure Modes Considered

- **Lock too tight under bursty load.** TTL=24h sounds long but a `clear` endpoint exists, and any real backoff still drops `current_limit` (just not the ceiling). The lock is on growth, not on responsiveness.
- **Probe of `/api/ps` returns wrong number.** Falls back to `5`. Tested in `test_ollama_probe.py`.
- **Migration on USB drive.** ALTER TABLE is small; SQLite uses DELETE journal mode per project policy. Tested in `test_concurrency_store_lock.py::test_migration_from_legacy_schema`.
- **Multiple endpoints to same Ollama host.** Each `cloud:<endpoint_id>` is independently locked; the persisted ceilings are per-endpoint by design.

## Out of Scope

- Per-(endpoint, model) ceiling discrimination (would require expanding the persisted `model_family` key beyond `__default__`).
- Removing F-28 retroactively from history — the function existed and shipped, this design supersedes it.
- Replacing the user's `cloud_concurrency` setting with a "soft cap" UI control. The soft-cap interpretation is automatic; no UI change required.
