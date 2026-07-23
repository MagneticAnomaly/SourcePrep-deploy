# Phase 145 Finding — `force_from_start` rebuild hangs *pre-registration*, orphaning an `all`-scope barrier with no watchdog and no captured stderr (silent rebuild death)

**Status:** Open. Root cause pinned to a specific code window; the exact blocking call within that window is narrowed but not yet confirmed by thread dump (needs root `py-spy`, see §8).
**Found:** 2026-07-22, live on the SourcePrep dogfood daemon.
**Severity:** High. Once triggered, **every subsequent rebuild on the project silently no-ops** (the orphaned `all`-scope barrier blocks reuse via the subsumption check), self-heal stays off, and the dashboard shows no error — just the stale "last built" timestamp forever. Has been latent on the dogfood daemon since it started 2026-07-12; the last successful build was 2026-07-11 under the *previous* daemon.
**Repro project:** SourcePrep dogfood (`f1636374-abc6-410d-99ee-822120379e79`, `/Volumes/4TB-BAD/HumanAI/CoDRAG`).
**Related findings:** `FINDING_reset-barrier-stuck-on-failed-finalize.md` (barrier not cleared on *failure* — success-only callsites), `FINDING_daemon-stall-and-frontend-lockup.md`. This one is distinct: the stall is *pre-run-registration*, so there is no run to fail and no journal row to time out.
**Storage ruled out:** The 4TB-BAD drive is **not** the cause (confirmed with Eric 2026-07-22). Do not pursue storage/USB theories for this finding.

---

## 1. Symptom (what the user sees)

User clicks **Rebuild** on the dashboard (or triggers `force_from_start`). The dashboard's "last built" timestamp does not advance — it stays at the previous successful build (here: 2026-07-11, ~11 days / "2 weeks ago"). No error toast, no failed-stage chip, no crashed-run indicator. Repeated rebuild clicks also appear to do nothing.

Under the hood, three things are wrong and all are invisible to the user:
1. A `pipeline_*.log` file is written with exactly **3 launch-decision events**, then goes silent forever.
2. **No `pipeline_runs` journal row is ever created** for the attempt.
3. An `all`-scope `.reset_barrier` is left active and never clears — which then silently blocks every later rebuild.

## 2. Root cause — pinned (the launch sequence)

The rebuild endpoint is a **synchronous** `def` (`api/routers/pipeline.py:396`), so FastAPI runs the entire launch on one request-threadpool worker, in this order:

| Step | File:line | What happens | In our evidence? |
|---|---|---|---|
| 0 | `api/routers/pipeline.py:414-415` | `write_reset_barrier(project_id, reason="rebuild", scope="all")` — **before** anything starts | `.reset_barrier` stamped at run start |
| 1 | `services/pipeline/orchestrator.py:645` | `pfl.decision("mode_selection", "force_from_start", group="fast_sync")` | log event 1 ✅ |
| 2 | `services/pipeline/orchestrator.py:3353` | `pfl.decision("rebuild_cache_wipe", "deferred", scope="fast_sync")` | log event 2 ✅ |
| 3 | `services/pipeline/orchestrator.py:674` | `pfl.decision("rebuild_changed_paths_cleared", "ok", "force_from_start: full scan")` | log event 3 ✅ |
| **3.5** | **`orchestrator.py:691` then `:706`** | **`watcher.clear_pending_state("force_from_start_rebuild")` then `gap = self.check_coverage_gap(project_id, include_paths=True)`** | **log goes silent here** ❌ |
| 4 | `orchestrator.py:711` | `pfl.decision("rebuild_gap_check", ...)` | never emitted ❌ |
| 5 | `orchestrator.py:986` → `_start_group` (`:1944`) → `:2043` registers run, `:2048` `pfl.start_run`, `:2053` `journal.start_run` (creates the `pipeline_runs` row) | never reached ❌ |
| 6 | `build_orchestrator.py:225-232` | spawn daemon worker thread | never reached ❌ |

The request thread **hangs at step 3.5** — inside `watcher.clear_pending_state()` (`core/watcher.py:198`, which acquires `watcher._lock`) or `check_coverage_gap()` (delegates to `ResumeStrategy.check_coverage_gap`, scans the index). Both calls sit inside `try/except Exception:` blocks (`orchestrator.py:687-695`, `:706-735`). A *raise* would be caught and flow would continue to emit event 4 at `:711`. **Event 4 never appeared → this is not an exception, it is a true block** — a held lock or an I/O syscall that never returns. This matches the observed CPU signature: brief ~30% CPU (the call did some work) then idle ~0.1% (the thread is blocked asleep).

### Why "Path 2" (`_start_group` returns False) is ruled out

An alternate silent path exists: `_start_group` could return False at `orchestrator.py:1978` if a hydrated PAUSED fast_sync run already occupies the `(project_id, "fast_sync")` slot (and `run_fast_sync` does not pop synthetic-paused snapshots before calling `_start_group`, unlike `run_deep_enrichment` at `:1017-1023`). That would also leave no journal row and orphan the barrier. **But** event 4 (`rebuild_gap_check`, `:711`) is emitted *before* `_start_group` (`:986`), so Path 2 would still log event 4. Our log has exactly 3 events → **Path 2 is ruled out; step 3.5 hang is the actual path.**

## 3. Why it is totally silent (three independent visibility gaps)

1. **Barrier written pre-registration.** `write_reset_barrier` runs at step 0, before the run exists. When the thread hangs at step 3.5, no run was registered → `maybe_clear_scoped_barrier` (`recovery.py:320-332`) never runs → the `all`-scope barrier (boundary = `finalize`, `recovery.py:282`) is orphaned indefinitely. Compounding this: the full-rebuild endpoint (`pipeline.py:422-427`) is the **only** rebuild path with **no failure-side `clear_reset_barrier`** — the fast (`:167-171`) and deep (`:243-247`) endpoints clear the barrier on failure; the full-rebuild endpoint does not. So even a *detected* failure here would orphan the barrier.
2. **No during-lifetime watchdog.** Heartbeats are *written* (`orchestrator.py:3736` 60s timer; `pipeline_journal.py:257` journal heartbeat thread) but the staleness check (`pipeline_metadata.py:329` `check_heartbeat_stale`) runs **only at daemon startup** (`recovery.py:1562`). The lone "stuck-run" detector, `force_reset_stale_runs` (`orchestrator.py:1660`), is not on a timer — it is invoked only from manual endpoints (`api/routers/projects/watch.py:204`, `api/routers/pipeline.py:1282`). `BuildOrchestrator._check_zombie` (`build_orchestrator.py:365-376`) transitions a dead-thread slot to FAILED but only **lazily**, on the next `status()`/`is_active()` poll of that slot — and here no slot was ever created (the run was never registered), so there is nothing to poll. **A run that hangs before registration is invisible to every detector.**
3. **Daemon stderr is not captured.** `prep serve` is started as `python -m prep.cli serve --port 8400` detached, stdin from `/dev/null`, **no `--log-file`**, and `server.py:62` is just `logging.basicConfig(level=logging.INFO)` → stderr. So if the hang *had* raised, the traceback would have gone to a detached terminal that no longer exists. The per-run `pipeline_*.log` only captures `pfl` decision/stage events, not Python tracebacks.

## 4. The reset barrier — design intent vs. the bug

The reset barrier (`recovery.py:176-189`) exists to **suppress self-heal during a rebuild** so self-heal does not resurrect stale data mid-rebuild. It is a 3-line file: timestamp, reason, **scope**. Scope sets the auto-clear boundary:

```
_SCOPE_BOUNDARY = {"sync": "fast_sync", "enrichment": "deep_enrichment",
                   "finalize": "finalize", "all": "finalize"}   # recovery.py:278-283
```

`scope="all"` means "I am rebuilding the whole chain; keep self-heal off until `finalize` completes." `maybe_clear_scoped_barrier(completed_group)` clears it **iff** `completed_group == _SCOPE_BOUNDARY[scope]` (`recovery.py:329-332`). For `all`, only a completed `finalize` clears it; fast_sync/deep_enrichment completion do **not** (intentional — the chain isn't done).

**The bug is ordering, not the scope semantics.** The barrier is written at step 0, *before* the run is registered. A run that hangs/dies at step 3.5 — before `_start_group` (step 5) — never reaches any completion handler, so `maybe_clear_scoped_barrier` is never called, and the `all` barrier is orphaned. From that point on, the subsumption check (`orchestrator.py:4546` — refuses to start while a barrier with scope in `("all","sync","enrichment")` is active) blocks every new rebuild, and self-heal logs `"Selfheal skipped: reset barrier active — awaiting genuine finalize"` indefinitely (same log line as `FINDING_reset-barrier-stuck-on-failed-finalize.md`).

**Net:** the barrier is a reasonable mechanism for *protecting an in-flight rebuild from self-heal*, but it is unsafe as written because (a) it is acquired before the run it protects is known to exist, and (b) the full-rebuild endpoint has no failure-side release. A pre-registration hang turns a transient, recoverable stall into a permanent, silent outage.

## 5. Evidence (live, 2026-07-22)

- Run log `.sourceprep/logs/pipeline_20260722_112909.log` — exactly 3 lines, all `elapsed=0`, the three decision events from §2 steps 1-3; 680 bytes, frozen.
- `.sourceprep/.pipeline_last_success` = `1783784361.78` → 2026-07-11T15:39:21Z (last successful build; predates the current daemon, which started 2026-07-12 09:52).
- `pipeline_telemetry.jsonl` — last event 2026-07-11T15:39:21Z; **zero events today**.
- `pipeline_runs` journal (`~/.local/share/sourceprep/prep_pipeline_journal.db`): **zero rows since 2026-07-22 00:00** — no row was ever created for the 11:29 attempt.
- `/projects/<id>/pipeline/status`: `any_running=false`; `crashed_runs` contains only old May `deep_enrichment` runs (`error="Process terminated (cleaned on restart)"`); `barrier={active:true, age_seconds:196, reason:"rebuild", scope:"all"}`.
- Daemon process (PID 30710): started Sun Jul 12 09:52:38, up 9d 21h; CPU 0.1-0.2% (idle, state `S+` — not disk-blocked); responds to API; no child worker processes; `lsof` shows no run-related open files, only `audit_log.db` / `prep_pipeline_journal.db` / `registry.db`. Stderr goes nowhere (no log file open, no tty).
- The `structural` stage reports `enabled=False` in status — this is a **symptom, not a cause**: `structural.enabled` is a project-config flag (`api/routers/pipeline.py:467`) that the structural worker flips to True only on successful completion (`services/pipeline/workers/__init__.py:696-700`). It is still False because the structural worker never ran.

## 6. Stale-code hypothesis — disproven for this path

Tested because the daemon has been up 9+ days and `prep serve` has no hot-reload:

- `orchestrator.py` last *committed* 2026-06-25 (`82923651`); `recovery.py` 2026-06-09; `stages.py` 2026-05-06; `pipeline.py` 2026-06-09 — **all before the daemon's 2026-07-12 start**.
- On-disk `orchestrator.py` working-tree blob sha == HEAD blob sha → the 2026-07-18 mtime was a content-free touch (a git checkout/merge rewrote identical bytes), **not** a code change.
- Recent Phase 145 commits (`1de6deb6`, `0fbc762c`, `6a91e6fa`) touched only `tools/phase145_uat/`, `tests/`, `.claude/skills/`, `playwright_smoke.py` — the outer UAT harness, **not** core pipeline code the daemon imports.

**Conclusion:** the daemon's loaded pipeline code == current pipeline code. The stall reproduces on production code → this is a production issue, not a stale-daemon artifact. (Side note, separate from this finding: the daemon *is* stale on `feature_gate.py`/`lemon_squeezy.py`/`license.py`/`docs_grounding.py` from a 2026-07-19 scrub — those are not on the rebuild path.)

## 7. Recommended fix areas (for Phase 145 to scope; not a commitment)

1. **Move barrier acquisition to after run registration, or add failure-side release.** Either write the barrier inside `_start_group` *after* `self._runs[key]=sm` + `journal.start_run` succeed, or — minimally — add `clear_reset_barrier(project_id)` to the full-rebuild endpoint's failure/non-started branch (`pipeline.py:422-427`), matching the fast (`:167-171`) and deep (`:243-247`) endpoints. This alone prevents the permanent silent outage.
2. **Timeout the pre-registration blocking calls.** Wrap `watcher.clear_pending_state()` and `check_coverage_gap()` (and any other pre-`_start_group` call that can block) in a bounded timeout so a hang *raises* into the existing `try/except`, which then releases the barrier and returns a real error instead of hanging the request thread forever.
3. **Add a during-lifetime watchdog.** Run `check_heartbeat_stale` / `force_reset_stale_runs` on a periodic timer (not only at startup) so a stuck run is detected and surfaced while the daemon lives. Note: this catches a *registered* run that hangs, but **not** a pre-registration hang — so this is defense-in-depth, not a substitute for #1/#2.
4. **Capture daemon stderr.** `prep serve` should log to a file by default (add a `FileHandler` in `server.py:62`, or a default `--log-file` in the `serve` CLI), so a swallowed/raised traceback is never lost. This is the single biggest visibility win and the cheapest.
5. **Register the run / journal row earlier.** Insert the `pipeline_runs` row (status=`pending`/`starting`) *before* `clear_pending_state`/`check_coverage_gap`, so a hang in those calls is visible as a stuck run the watchdog (#3) can time out, rather than as nothing.
6. **Stop broad-swallowing in the launch path.** The `try/except Exception:` around `:691`/`:706` silently eats errors; at minimum log them (`logger.exception`) so a raise is not invisible even before #4 lands.

## 8. Confirming the exact blocking call (open — needs root)

The hang is narrowed to the window between `orchestrator.py:674` and `:711` — i.e. `watcher.clear_pending_state()` (`:691`, blocked on `watcher._lock`?) or `check_coverage_gap()` (`:706`, blocked on index I/O?). `py-spy` is installed in the venv but macOS requires root to attach (`py-spy dump --pid <daemon>` → "This program requires root on OSX"). Confirm with:

```
sudo .venv/bin/py-spy dump --pid 30710 2>&1 | grep -A8 -E "clear_pending_state|check_coverage_gap|_lock|watcher|ResumeStrategy"
```

The blocked frame decides whether the fix is a **lock deadlock** (watcher thread holding `_lock` in a stuck state) or an **I/O timeout** (index scan blocked on a syscall). Either way, fix #2 (bounded timeout) covers it.

## 9. Reproduction

1. Daemon: `prep serve` started 2026-07-12 (PID 30710), repo on `/Volumes/4TB-BAD/HumanAI/CoDRAG`, embedded `.sourceprep/`.
2. Trigger a `force_from_start` full rebuild (dashboard Rebuild, or `POST /projects/{id}/pipeline/rebuild` with `force_from_start=True`).
3. Observe: `pipeline_*.log` gains exactly 3 decision events then freezes; `pipeline_runs` gets no new row; `.reset_barrier` appears with `scope=all` and never clears; `/pipeline/status` shows `any_running=false`, `barrier.active=true`; daemon CPU idles; dashboard "last built" does not advance; no error surfaced.
4. Subsequent rebuilds: blocked by the subsumption check (`orchestrator.py:4546`) while the `all` barrier is active; also silent.

## 10. Immediate unblock (does not fix the bug)

The intended clear path is `POST /projects/{id}/pipeline/rebuild/stop` (`pipeline.py:1105`) — it unconditionally calls `recovery.clear_reset_barrier` (`pipeline.py:1146`) even with no active run. **However, see §11: in the wedged state this endpoint itself hangs, so the reliable unblock is `rm .sourceprep/.reset_barrier` immediately followed by a daemon restart** (the barrier file survives restart, so it must be removed first or the new daemon boots into the same blocked state).

## 11. Corollaries observed during recovery (2026-07-22 evening)

Live recovery attempts on the dogfood daemon surfaced four additional facts that sharpen the finding and the fix scope:

1. **`/rebuild/stop` also hangs — same bug class.** With an orphaned `all`-barrier present and no run active, `POST /pipeline/rebuild/stop` returned `HTTP 000` (no response) at both 10s and 60s timeouts; `GET` on the same path returned `405` (route exists, POST-only). The handler is a synchronous `def` (`pipeline.py:1106`) and, for `scope="all"`, runs an OR-chain of `cancel_fast_sync` / `cancel_deep_enrichment` / `cancel_finalize` (`pipeline.py:1138-1142`) **before** `clear_reset_barrier` (`:1146`). One of those cancel calls blocks (lock/I-O), so the barrier is never cleared and the request hangs. **The endpoint designed to unstick a stuck barrier is itself susceptible to the same stall.** Fix: the same bounded-timeout / lock-safety treatment as the rebuild path (§7 #2), plus `clear_reset_barrier` should run in a `finally` so a cancel hang can't prevent the clear.

2. **Manual `rm` of the barrier file is NOT a reliable clear while the daemon is wedged.** After `rm -f .sourceprep/.reset_barrier` (file confirmed gone), the status API still reported `barrier.active=true` with the *original* `written_at`, and `age_seconds` frozen at an identical value across calls (stale/cached, not recomputed). The file then reappeared minutes later with a fresh mtime but the old content `written_at` — i.e. something (a background path / backup manager referencing `.reset_barrier`, `branch_backup_manager.py:287`) rewrote it. So on a wedged daemon, neither the API nor `rm` clears the barrier reliably; **a restart is required**, and the file must be absent at boot.

3. **The barrier file survives restart — this is why "restart fixes everything" stopped working.** For months, restart cleared pipeline issues because they were in-memory (stuck threads/locks). The orphaned `all`-barrier is a **file**, so a restart boots into the same blocked state (self-heal refuses, subsumption blocks rebuilds). The user's reliable fix pattern broke the moment a run first died pre-registration and orphaned the file. This is the user-visible regression: not "restart got worse," but "a new failure mode produces a disk-resident blocker that restart can't reach." (Confirmed live: a restart with the barrier file still present booted straight back into `selfheal barrier_active` / `PRE_BARRIER_STALE` — see the 16:22 boot log.)

4. **The hang recurs on a restarted daemon but NOT on a truly fresh one — root trigger is accumulated daemon state, not the index.** A daemon restarted mid-day (12:22) was wedged again ~8h later (sync endpoints `000`, barrier flickering, status frozen). But a fresh daemon (33s uptime) with the barrier file removed accepted the rebuild immediately — `POST` returned `200 {"started":true}`, `run-637f524f22e9` registered, `structural` completed, advanced to `inferred_edges` (no step-3.5 hang). This means the blocking call (`check_coverage_gap` / `clear_pending_state`) hangs only after the daemon accumulates stuck state (a held lock that deadlocks over hours), not on first contact with the Jul-11 index. **Implication for the fix:** the bounded-timeout (§7 #2) is still essential (it converts the eventual hang into a raise instead of a permanent wedge), but the deeper lever is preventing the lock-deadlock accumulation — likely a background self-heal/heartbeat thread holding `orchestrator._lock` across a blocking I-O call. A `py-spy` thread dump of a wedged daemon (needs root: `sudo .venv/bin/py-spy dump --pid <pid>`) would confirm which thread holds `_lock` and in which call — left as the next diagnostic step.

## 12. Recovery sequence that worked (2026-07-22 21:18)

1. `rm -f .sourceprep/.reset_barrier` (file was still present post-restart with a recreated mtime).
2. Restart `prep serve` (fresh daemon, no barrier file → boots clean: `barrier.active=false`).
3. `POST /projects/{id}/pipeline/rebuild` → `200 {"started":true,"group":"all"}`; run registered, structural completed, advanced to inferred_edges. **No pre-registration hang on the fresh daemon.**

This sequence is the reliable unblock until the §7 fixes land. It does not fix the bug — the next long daemon uptime will re-wedge unless §7 #2 (timeout the blocking calls) and the `_lock`-across-I-O issue (§11.4) are addressed.

## 13. Completion validation (2026-07-22 23:02 EDT) — barrier clear-on-success is sound

After the §12 recovery, a full `force_from_start` rebuild ran to completion on the fresh daemon (PID 59431): fast_sync (5 stages) → deep_enrichment (5 stages) → finalize (5 stages), `run_end result=completed elapsed_seconds=822.74`. The `all`-scope barrier **auto-cleared exactly as designed** — `maybe_clear_scoped_barrier("finalize")` matched the `all`→`finalize` boundary and removed `.reset_barrier`; `.pipeline_last_success` advanced from Jul 11 (`1783784361`) to Jul 22 23:02 EDT (`1784775765`).

**Implication:** the barrier-clear-on-*success* logic is correct. The bug is isolated to (a) the pre-registration hang and (b) the missing failure-side clear on the full-rebuild/stop endpoints — *not* the scope-boundary mechanism. This narrows the fix (see `PROPOSAL_rebuild-pre-registration-hang-and-barrier-safety-v1.md`): A1 (barrier safety) + A2 (timeout) close the failure modes without touching `_SCOPE_BOUNDARY`.