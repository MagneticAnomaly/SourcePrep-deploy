# Phase 145 Proposal — Fix the `force_from_start` pre-registration hang, orphaned `all`-barrier, and silent-stall visibility gaps (v1)

**Status:** Draft, awaiting sign-off.
**Companion finding:** `FINDING_force-from-start-rebuild-hangs-pre-registration-orphans-all-barrier.md` (root cause pinned, evidence, §11 corollaries, §12 recovery sequence).
**Scope:** Core pipeline rebuild path — `api/routers/pipeline.py`, `services/pipeline/orchestrator.py`, `services/pipeline/recovery.py`, `services/pipeline_journal.py`, `services/build_orchestrator.py`, `services/pipeline_logger.py`, `core/watcher.py`, `server.py`, `cli.py`.
**Severity driver:** A `force_from_start` rebuild can hang *before* registering its run, orphan an `all`-scope reset barrier that survives restart, and silently block every subsequent rebuild on the project — with no error surfaced, no `crashed_runs` entry, no telemetry, and no captured traceback. Confirmed live on the dogfood daemon (two days, two wedged daemons). Validated: when a run completes, the barrier auto-clears correctly, so the bug is isolated to the pre-registration hang + the missing failure-side clear (not the success-path clear logic).

---

## Goals

1. **A `force_from_start` rebuild can never produce a permanent silent outage.** If the run dies before registering, the barrier is released and the user gets a real error.
2. **A blocking call in the rebuild launch path raises instead of wedging.** `clear_pending_state` / `check_coverage_gap` (and the `/rebuild/stop` cancel chain) are bounded by a timeout.
3. **No rebuild death is silent.** The daemon captures its own stderr to a log file; broad-swallow `try/except` blocks in the launch path log exceptions instead of eating them.
4. **A stuck run is detected while the daemon lives,** not only at startup. A during-lifetime heartbeat watchdog marks stale runs crashed and surfaces them.
5. **The dashboard surfaces the failure** (out of scope for this proposal's code, but the backend must return a real error code/body the UI can render — see §6).

## Non-goals

- Reworking the barrier scope semantics (`_SCOPE_BOUNDARY`) — the `all`→`finalize` boundary is correct; only the acquisition/clear ordering is broken.
- The dashboard error-rendering work itself (tracked separately; this proposal only guarantees the backend emits a non-2xx with a useful body).
- Fixing the *trigger* of the `check_coverage_gap`/`clear_pending_state` hang (likely a `_lock`-held-across-I/O deadlock, §11.4 of the finding). The timeout (#2) converts it from a permanent wedge into a raise; the deeper lock hygiene is flagged as follow-up.
- Changing auto-heal cadence or self-heal behavior beyond the barrier interaction.

---

## Fix areas

Each area: **Problem → Approach (file:line) → Test → Acceptance → Risk.** Areas are independently shippable and ordered by leverage/risk.

### A1. Barrier safety — acquire after registration, and clear on failure  *(cheap, low-risk, highest leverage)*

**Problem.** `pipeline.py:414-415` writes the `all`-scope barrier **before** `run_all` (`:419-420`). If the run hangs/dies before `_start_group` registers it (`orchestrator.py:2043`) and creates the journal row (`:2053`), nothing ever clears the barrier. The full-rebuild endpoint (`:422-427`) raises 409 on `not started` **without** clearing the barrier — unlike the fast (`:167-171`) and deep (`:243-247`) endpoints, which clear on failure. The `/rebuild/stop` endpoint (`:1105`) clears the barrier at `:1146` *after* a cancel chain that can itself hang (`:1138-1142`), so a cancel hang prevents the clear.

**Approach.**
1. Move the `write_reset_barrier` call from `pipeline.py:414` to **inside** `_start_group` (`orchestrator.py:~2043`), *after* `self._runs[key]=sm` and `journal.start_run` succeed. The barrier then exists only once a run it protects actually exists. Pass the scope through `run_all`→`run_fast_sync`→`_start_group` (or write it from the endpoint after `started=True` is known). Keep the `scope="all"` semantics for the full-rebuild path.
2. Add a failure-side `clear_reset_barrier(project_id)` to the `/rebuild` endpoint's `not started` branch (`:422-427`), mirroring fast/deep. Wrap in `try/except` + `logger.exception`.
3. In `/rebuild/stop` (`:1105`), move `recovery.clear_reset_barrier(project_id)` (`:1146`) into a `try/finally` so a cancel-chain hang (`:1138-1142`) cannot prevent the clear. Cancel remains best-effort (already wrapped in `try/except`).

**Test.** `tests/test_phase145_barrier_safety.py`:
- (a) A rebuild whose `run_all` returns `started=False` (mock a PAUSED occupant) leaves **no** `.reset_barrier` file.
- (b) A `_start_group` that raises before registration leaves no barrier (move-then-fail clears).
- (c) `/rebuild/stop` clears the barrier even when `cancel_*` raises (inject a raising cancel).
**Acceptance.** No code path can leave an orphaned `all`-barrier after a failed/non-started rebuild or a failed stop.
**Risk.** Low. Moving the write is a sequencing change; the barrier still suppresses self-heal for the full duration (registration happens within milliseconds of the decision events). The failure-side clears mirror existing fast/deep behavior.

### A2. Bound the blocking launch calls with a timeout  *(medium risk — must pick a sane timeout)*

**Problem.** `watcher.clear_pending_state` (`core/watcher.py:198`, acquires `watcher._lock`) and `check_coverage_gap` (`orchestrator.py:706` → `ResumeStrategy.check_coverage_gap`) can block indefinitely. Both sit inside `try/except Exception` (`orchestrator.py:687-695`, `:706-735`), which catches *raises* but not *hangs* — so a true block orphans the barrier and wedges the request thread. The `/rebuild/stop` cancel chain has the same shape.

**Approach.**
1. Wrap `clear_pending_state` and `check_coverage_gap` calls in the launch path with a bounded async/thread timeout (e.g. `anyio.fail_after` / `asyncio.wait_for` adapted for the sync threadpool, or a `concurrent.futures`-based deadline). On timeout, raise a `PipelineLaunchTimeout` that the existing `try/except` catches → logs → releases the barrier (A1's failure-side clear) → returns a 503 to the client.
2. Apply the same timeout to the `cancel_*` calls in `/rebuild/stop` (`:1138-1142`).
3. Timeout value: start conservative (60s for the launch scan, 15s for cancel) and make it configurable via `PREP_LAUNCH_TIMEOUT_S` / `PREP_CANCEL_TIMEOUT_S` env vars.

**Test.** `tests/test_phase145_launch_timeout.py`:
- (a) A `check_coverage_gap` that blocks (mock with an event never set) raises `PipelineLaunchTimeout` within the deadline, the endpoint returns 503, the barrier is cleared.
- (b) `/rebuild/stop` with a hanging `cancel_fast_sync` still clears the barrier within the cancel deadline.
**Acceptance.** A hung launch/stop call returns an error within the deadline instead of hanging the request thread forever; no orphaned barrier.
**Risk.** Medium. A too-aggressive timeout could abort a legitimately-slow scan on a huge repo. Mitigation: conservative default + env override + the deadline only bounds the *launch pre-amble* (the scan that decides resume point), not the structural build itself. Validate against the dogfood repo (this one) and a large repo (HomeColab) before landing the default.

### A3. Capture daemon stderr to a log file by default  *(cheap, low-risk, high visibility)*

**Problem.** `prep serve` is started detached with no `--log-file`; `server.py:62` is `logging.basicConfig(level=logging.INFO)` → stderr only. So a swallowed/raised traceback in the run task vanishes. This is the single biggest visibility gap and the cheapest fix.

**Approach.**
1. In `serve` startup (`cli.py` serve command / `server.py`), add a `RotatingFileHandler` writing to `$PREP_DATA_DIR/daemon.log` (or `.sourceprep/logs/daemon.log` for embedded mode) by default, in addition to stderr. Respect an explicit `--log-file` override.
2. Enable `faulthandler` (`faulthandler.enable()` + `faulthandler.register(signal.SIGUSR1)`) so `kill -USR1 <pid>` dumps all thread tracebacks to the log — a non-root alternative to `py-spy` for the §11.4 lock-deadlock investigation.
3. Document the log location in `CLAUDE.md` (Daemon State Location table) and the finding.

**Test.** `tests/test_phase145_daemon_logging.py`: starting `serve` writes a `daemon.log`; a logged `logger.exception` appears in the file; `kill -USR1` produces a traceback in the log.
**Acceptance.** Any future swallowed exception in the run task is recoverable from `daemon.log`; thread dumps are obtainable without root.
**Risk.** Low. File-handler rotation must not interfere with the embedder/CoreML threads. Use a separate logger, not the root, if rotation causes issues. Verify log rotation on the USB-Thunderbolt drive (DELETE mode is already used for SQLite per the WAL memory; log append is safe).

### A4. Stop broad-swallowing in the launch path; log exceptions  *(cheap, low-risk)*

**Problem.** The `try/except Exception:` around `clear_pending_state` (`orchestrator.py:687-695`) and `check_coverage_gap` (`:706-735`) swallow errors with at most a debug log. Even with A3's stderr capture, these would hide the cause.

**Approach.** Replace bare `except Exception: pass`/debug with `except Exception: logger.exception("...")` so the traceback hits the log (A3). Do **not** change control flow (still continue to the next step) — visibility only, to avoid changing behavior.

**Test.** Extend the A2 timeout test to assert the exception is logged.
**Acceptance.** A raise in `clear_pending_state`/`check_coverage_gap` appears in `daemon.log` with a full traceback.
**Risk.** Low. Logging-only change.

### A5. Register the run / journal row before the blocking calls  *(medium risk — ordering change)*

**Problem.** The journal row (`pipeline_runs`) is created at `orchestrator.py:2053`, *after* the blocking `clear_pending_state`/`check_coverage_gap` (`:691`/`:706`). A hang there leaves no row → invisible to `any_running`, `crashed_runs`, and the (future) watchdog.

**Approach.** Insert a `pipeline_runs` row with `status='starting'` (new status) before `clear_pending_state`/`check_coverage_gap`, then transition to `running` at `_start_group`. This makes a pre-registration hang visible as a stuck `starting` row the watchdog (A6) can time out. Coordinate with the existing `is_active`/`is_paused` checks at `_start_group:1971-1978` so a `starting` row doesn't falsely trip the "already running" guard.

**Test.** `tests/test_phase145_early_registration.py`: a hang injected in `check_coverage_gap` leaves a `starting` row; the watchdog (A6) marks it crashed after the deadline.
**Acceptance.** A pre-registration hang is observable in `pipeline_runs` and recoverable by the watchdog/restart.
**Risk.** Medium. New status value must be handled everywhere `status` is read (status API, `crashed_runs` filter, dashboard). Mitigation: treat `starting` as active-for-watchdog but not active-for-block-reuse.

### A6. During-lifetime heartbeat watchdog  *(deeper — new background task)*

**Problem.** Heartbeats are written (`orchestrator.py:3736`, `pipeline_journal.py:257`) but staleness is checked **only at startup** (`pipeline_metadata.py:329` from `recovery.py:1562`). `force_reset_stale_runs` (`orchestrator.py:1660`) is not on a timer — only manual endpoints invoke it. So a stuck run goes undetected while the daemon lives.

**Approach.** Add a periodic background task (every `PREP_WATCHDOG_INTERVAL_S`, default 120s) that calls `force_reset_stale_runs` / `check_heartbeat_stale` for all projects with a heartbeat older than `PREP_RUN_STALE_S` (default 300s), marks the run `crashed` with `error="heartbeat stale (watchdog)"`, and clears an orphaned barrier whose run is no longer active. Start the task in `serve` startup; cancel on shutdown. Guard it so it never runs concurrently with itself.

**Test.** `tests/test_phase145_watchdog.py`: a run whose heartbeat is faked old gets marked crashed within one interval; an orphaned barrier with no active run gets cleared.
**Acceptance.** A wedged run is detected and surfaced within ~5 min while the daemon is up, not only after a restart.
**Risk.** Medium. A too-aggressive watchdog could mark a long-but-legitimate LLM stage (deep_enrichment can run 10+ min between heartbeats?) crashed. Mitigation: confirm the heartbeat is actually written mid-stage (it should be — `pipeline_journal.py:257` thread); set the stale threshold well above the longest inter-heartbeat gap observed in the dogfood rebuild telemetry.

### A7. (Follow-up, not in v1) `_lock`-across-blocking-I/O hygiene  *(research)*

**Problem.** §11.4: the hang recurs on an hours-old daemon but not on a fresh one → the trigger is a `_lock`-held-across-blocking-I/O deadlock that accumulates. A1/A2 make it non-fatal, but the underlying lock hygiene (likely `orchestrator._lock` or `watcher._lock` held across a blocking scan) should be audited so the daemon doesn't slowly accumulate stuck state.

**Approach (v1 leaves this as flagged follow-up).** Audit `orchestrator._lock` and `watcher._lock` holders; ensure no blocking I/O is performed while holding the lock (acquire → copy state → release → do I/O). Use the A3 `kill -USR1` thread dump on a deliberately-wedged daemon to confirm which lock/thread before refactoring.
**Risk.** Higher; deferred to a v2 proposal with its own design pass.

---

## Sequencing

```
A3 (stderr capture)  ─┐
A4 (log exceptions)  ─┼─→ A1 (barrier safety) ─→ A2 (timeout) ─→ A5 (early reg) ─→ A6 (watchdog)
                     │
                     └─ (A3 enables A4/A6 diagnostics)
```

- **A3 + A4 first** — unblock all diagnosis; cheapest.
- **A1** — ends the permanent silent outage; ships independently and is the highest user-visible leverage.
- **A2** — converts the hang from permanent to recoverable; needs the A1 failure-side clear to release the barrier on timeout.
- **A5 + A6** — make a hang *visible* and *auto-recovered*; depend on A3/A4 for diagnostics and A1 for barrier semantics.

Each area ships as its own commit with its own test, per the Phase 136/145 per-Part methodology.

## Validation (the Phase 145 dogfood method)

For each area, a before/after probe against the running daemon (Layer 2):

- **A1:** trigger a rebuild that returns `not started` (PAUSED occupant) → assert no `.reset_barrier` remains. Then a normal rebuild → assert barrier appears at registration and clears on finalize.
- **A2:** (synthetic) inject a blocking `check_coverage_gap` → assert 503 within the deadline and barrier cleared. Then a real rebuild on this repo and on HomeColab → assert the launch scan completes well under the 60s default.
- **A3/A4:** force a swallowed exception in the launch path → assert it appears in `daemon.log` with a traceback.
- **A5/A6:** inject a hang → assert a `starting`/`running` row appears and is marked crashed within `PREP_RUN_STALE_S`.

Layer 1 (pytest) per area as specified above. Layer 3: update `99_Scorecard.md` (or the Phase 145 scorecard) with the before/after for the rebuild-reliability rubric.

## Acceptance for the whole proposal

1. No sequence of rebuild failures can leave an orphaned `all`-barrier that survives restart (A1).
2. A hung launch/stop returns an error within a bounded deadline and releases the barrier (A2 + A1).
3. Every swallowed launch exception is recoverable from `daemon.log`; thread dumps available without root (A3 + A4).
4. A wedged run is detected and marked crashed within ~5 min while the daemon is up, and an orphaned barrier with no active run is auto-cleared (A6).
5. The full dogfood rebuild (this repo) completes end-to-end with the new code, barrier clears on finalize, and `last_success` advances — replicating the 2026-07-22 23:02 successful run, but with the safety net in place.

## Risks summary

| Area | Risk | Mitigation |
|---|---|---|
| A1 | Move-write changes timing | Barrier exists within ms of decisions; behavior unchanged on success |
| A2 | Too-aggressive timeout aborts legit scans | Conservative default + env override; validate on dogfood + HomeColab |
| A3 | File-handler interacts with embedder threads | Separate logger; verify on the USB-Thunderbolt drive |
| A5 | New `starting` status read sites | Treat as active-for-watchdog, not active-for-block-reuse |
| A6 | Watchdog marks legit long stages crashed | Confirm inter-heartbeat gap; threshold above it |
| A7 | Lock refactor | Deferred to v2; A3 `kill -USR1` diagnostics first |

## Out of scope (tracked elsewhere)

- Dashboard error rendering for 503/409 (separate UI work).
- The `_lock`-across-I/O refactor (A7, v2 proposal).
- Barrier scope semantics (`_SCOPE_BOUNDARY`) — correct as-is.
- Self-heal cadence changes.

## Cross-references

- `FINDING_force-from-start-rebuild-hangs-pre-registration-orphans-all-barrier.md` — root cause, §7 fix areas, §11 corollaries, §12 recovery sequence.
- `FINDING_reset-barrier-stuck-on-failed-finalize.md` — barrier not cleared on finalize *failure* (success-only callsites); A1's failure-side clear complements this.
- `FINDING_daemon-stall-and-frontend-lockup.md` — related stall class.
- `REFERENCE_canonical-pipeline-behavior.md` — the 15-stage / 3-group model this proposal preserves.