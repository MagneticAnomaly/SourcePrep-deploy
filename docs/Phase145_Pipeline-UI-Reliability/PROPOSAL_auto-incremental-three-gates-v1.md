# Phase 145 Proposal — Fix the three gates that silently block auto-incremental fast_sync (v1)

**Status:** Draft, awaiting scrutiny.
**Companion findings:**
- `FINDING_auto-incremental-never-fired-despite-stale-files.md` (§2q — root cause now pinned, see §1 below)
- `FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md` (§2s — paired symptom, same root cause for the auto-refuses half)
- `FINDING_stage15-antibodies-never-complete.md` (§2n — the upstream bug that turns RC#3 into a permanent block)
- `FINDING_manual-update-click-triggers-ui-cluster.md` (§2u — meta-pattern; fixing §2q removes the cascade trigger)
**Scope:** `src/prep/core/watcher.py`, `src/prep/api/routers/projects/watch.py`, `src/prep/services/pipeline/orchestrator.py`, `src/prep/services/pipeline/resume.py`, `src/prep/core/trace/coverage.py`. No UI changes required (though §6 proposes a defensive UI signal as a non-goal of this proposal).
**Severity driver:** A project on Auto mode with legitimate untraced source files will **never** auto-run fast_sync. The user must manually click Rebuild per-project, per-occurrence. The bug is silent — no error, no log at INFO, no UI badge. Confirmed live on two dogfood projects (Applifier §2q, SourcePrep §2s) over multiple days. The manual Rebuild workaround is a sledgehammer (`force_from_start=True`) that throws away all stage data and rebuilds from scratch — far more expensive than the incremental run the watcher should have done.

---

## 1. The issue, verbosely

### 1.1 What the user observes

A project is configured with `auto_config.fastSync = true` (and typically `deepEnrichment = "auto"` and `finalize = "auto"` as well — the "Auto" toggle is on for all three groups in the Graph Enrichment panel). The Graph Scope card shows:

- `N / M files traced · 99.x%` — coverage is high but not 100%.
- A queue of **untraced files** with ages ranging from minutes to **hours** (observed: up to 7h).
- `Last updated: <hours> ago` — no fast_sync has completed in that window.

The user expects: with Auto on and untraced files aging, the watcher should have fired an incremental fast_sync many times over by now. It has not. No error is surfaced. No log entry at INFO level explains why. The only recovery is to manually click "Rebuild" (or "Update") in the dashboard, which works because it bypasses the gates described below — but it's a full `force_from_start` rebuild, not the cheap incremental the watcher should have done.

### 1.2 The two auto-trigger paths

The `AutoRebuildWatcher` (`src/prep/core/watcher.py`) has two independent paths that should trigger an incremental fast_sync:

1. **Filesystem event path** — watchdog's `Observer` detects a file change/create, calls `on_event` → `_queue_path` → after a 5s debounce, `_on_debounce_fire` → `trigger_build(paths)` callback → `pipeline_orchestrator.run_fast_sync(proj.id)`. This is the primary path for files that change *after* the watcher started.

2. **Periodic coverage check** — every 5 minutes (`_COVERAGE_CHECK_INTERVAL = 300.0`), `_on_coverage_check` runs independently of filesystem events. It's the **backstop** for files the event path misses: files that existed before the watcher started, files from a bulk `git pull` that overwhelmed FSEvents, files on a volume where FSEvents is unreliable, etc. It calls `check_coverage_gap(project_id)` and triggers a rebuild if `needs_rebuild` is true.

**Both paths are broken.** A third gate in the orchestrator blocks the actual build start regardless of which path fired.

### 1.3 Root cause #1 — "Close enough" gate defeats the coverage-check backstop

`watcher.py:596-616` (the fallback path, which is the only path used in production — see §1.3.1):

```python
if gap.get("needs_rebuild"):
    if (stale == 0
            and coverage_pct >= self._COVERAGE_GAP_OK_PCT   # 95.0
            and untraced <= self._COVERAGE_GAP_OK_MAX_FILES): # 20
        logger.info(
            "Watcher coverage check for %s: %d untraced + %d stale "
            "files (%.1f%% coverage) — close enough, skipping",
            self.project_id, untraced, stale, coverage_pct,
        )
    else:
        # ... trigger rebuild
```

The Applifier scenario: **9 untraced files, 99.1% coverage, 0 stale** → `stale == 0` ✓, `coverage_pct >= 95.0` ✓, `untraced <= 20` ✓ → "close enough, skipping." Every 5 minutes. Forever.

The gate's comment says "Those files are likely binary, generated, or excluded." But the untraced files in the observed cases are **legitimate source**: `Packages/DetectionEngine/JS/tests/lab*.js`, `design/AppIcon/generate_icon.py`, `docs/Phase34_multivendor_qa/*.md`. The gate makes an assumption about *file character* (binary/generated/excluded) using only *aggregate counts* (coverage % and untraced count) — it has no information about what the untraced files actually are. A repo at 99% coverage with 9 untraced `.py`/`.swift`/`.md` files is in a fundamentally different state than a repo at 99% coverage with 9 untraced `.png`/`.lock`/`.min.js` files, but the gate treats them identically.

#### 1.3.1 The `on_coverage_gap` callback is never set in production

The watcher constructor accepts an `on_coverage_gap` callback (`watcher.py:47`) which, if set, is the "preferred path" (`watcher.py:580-585`) — it delegates to the caller and **does not apply the "close enough" gate**. But the production construction at `src/prep/api/routers/projects/watch.py:224-233` does **not** pass `on_coverage_gap`:

```python
watcher = AutoRebuildWatcher(
    repo_root=Path(proj.path),
    index_dir=idx.index_dir,
    on_trigger_build=trigger_build,
    is_building=is_building,
    debounce_ms=debounce_ms,
    min_rebuild_gap_ms=min_gap_ms,
    project_id=proj.id,
    on_files_changed=on_files_changed,
    # NOTE: no on_coverage_gap= — so the fallback path with the gate is always used
)
```

So the gated fallback path is the only one that runs. Contrast this with the **startup auto-run** path in `server.py:1182-1194`, which calls `check_coverage_gap` and checks `needs_rebuild` directly with **no "close enough" gate** — which is why a daemon restart temporarily fixes the problem (the 9 untraced files trigger a fast_sync on startup), but once the daemon is running, the periodic coverage check re-engages the gate and the cycle resumes.

### 1.4 Root cause #2 — `trigger_build` always returns `True`, masking silent skips

`src/prep/api/routers/projects/watch.py:160-166`:

```python
started = pipeline_orchestrator.run_fast_sync(proj.id)
logger.info(
    "Watcher: incremental fast_sync for %s — started=%s "
    "(deep auto-chains if per-project deepEnrichment=auto)",
    proj.id, started,
)
return True   # ← ALWAYS True, regardless of `started`
```

The `trigger_build` callback captures `run_fast_sync`'s return value in `started` (and even logs it!), but then **returns `True` unconditionally** at line 166. The watcher's `_on_debounce_fire` (`watcher.py:368-396`) checks `started = bool(self._on_trigger_build(paths))`:

```python
started = False
try:
    started = bool(self._on_trigger_build(paths))
except Exception:
    started = False

if not started:
    # re-queue and re-debounce
    ...
    return

with self._lock:
    self._state = "building"
    self._last_trigger_at_epoch = time.time()

t = threading.Thread(target=self._wait_for_build_complete, daemon=True)
t.start()
```

Because `trigger_build` always returns `True`, the watcher:
1. Has already cleared `_pending_paths` (line 312, before the call).
2. Transitions to `"building"` state.
3. Starts `_wait_for_build_complete`, which polls `_is_building()` — finds nothing running (because `run_fast_sync` returned `False` without starting anything) — exits immediately.
4. Transitions back to `"idle"` and clears `stale_since` (line 429).

**The untraced files are silently dropped from the watcher's pending set.** No build ever ran. The watcher believes it successfully handed off the work. The `started=False` from `run_fast_sync` is logged but never acted on — the log line is the only trace, and it's at INFO level with no flag that it indicates a problem.

This means: even when the filesystem event path *does* fire correctly (watchdog saw the new file, debounce expired, `trigger_build` was called), if `run_fast_sync` returns `False` (which it does, per RC#3 below), the watcher eats the event and resets to idle. The file stays untraced. The next file event re-queues it, re-debounces, re-calls `trigger_build`, re-gets `True`, re-eats it. Indefinitely.

### 1.5 Root cause #3 — Downstream-partial guard blocks `run_fast_sync` when finalize is incomplete

`src/prep/services/pipeline/orchestrator.py:737-822` — when all 5 fast sync stages are already complete (`resume == len(FAST_SYNC_STAGES) == 5`), `run_fast_sync` checks whether downstream groups are partially complete before allowing an incremental re-run:

```python
deep_resume = self._detect_resume_point(
    project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
)
finalize_resume = self._detect_resume_point(
    project_id, FINALIZE_STAGES, skip_mtime_cascade=True,
)
deep_partial = 0 < deep_resume < len(DEEP_ENRICHMENT_STAGES)      # 0 < x < 5
finalize_partial = 0 < finalize_resume < len(FINALIZE_STAGES)      # 0 < x < 5
downstream_partial = deep_partial or finalize_partial

if downstream_partial or blocking_run is not None:
    logger.info(
        "[%s] Skipping incremental fast_sync — downstream partial or busy: %s. "
        "Run will be re-attempted after the downstream group settles.",
        project_id, reason,
    )
    return False
```

`FINALIZE_STAGES` includes `ANTIBODIES` (stage 15) — `src/prep/services/pipeline/stages.py:72-78`:

```python
FINALIZE_STAGES: List[StageId] = [
    StageId.ATLAS,       # 11
    StageId.RULES,       # 12
    StageId.CONCEPTS,    # 13
    StageId.AUDIT,       # 14
    StageId.ANTIBODIES,  # 15
]
```

Per §2n (`FINDING_stage15-antibodies-never-complete.md`), the Immune System stage **never completes** — it's always rendered as "Not run" regardless of whether the worker ran, failed, or returned zero derivables. This means `finalize_resume = 4` (4 of 5 finalize stages have provenance manifests; `ANTIBODIES` does not), so `finalize_partial = True`, so `downstream_partial = True`, so `run_fast_sync` **always returns `False`** for any incremental trigger on a project in this state.

The guard's intent (per the comment at `orchestrator.py:738-752`) is to prevent selfheal from manufacturing stub manifests from *partial* on-disk data that downstream stages would then consume as real outputs. That's a legitimate concern for the `0 < resume < total` case. But the guard doesn't distinguish:
- **"Stage genuinely incomplete"** — the stage ran, partially wrote data, and selfheal would extrapolate garbage. (The concern the guard was built for.)
- **"Stage never produced derivable outputs"** — the stage ran to completion but its output is empty (zero antibodies derivable from the current concept set). This is §2n's exact shape. There's no partial data to extrapolate; the "incompleteness" is a UI/rendering artifact, not a data-integrity risk.

Only `force_from_start=True` bypasses this guard — it sets `resume = 0` at `orchestrator.py:631-633`, so the `if resume >= len(FAST_SYNC_STAGES)` block (where the guard lives) is never entered. This is why the manual "Rebuild" button works: it calls `run_all(project_id, force_from_start=True)` (`api/routers/pipeline.py:419-420`), which bypasses all three gates.

### 1.6 The vicious cycle

```
§2n: Immune System (stage 15) never completes
  → finalize_resume = 4, finalize_partial = True         (RC#3)
  → run_fast_sync() returns False for ALL auto-trigger paths
  → trigger_build() returns True anyway                  (RC#2)
  → watcher clears pending paths, transitions building→idle
  → untraced files silently dropped from pending set
  → coverage check backstop also skips via "close enough" gate (RC#1)
  → files pile up indefinitely
  → user must manually click Rebuild (force_from_start=True, bypasses RC#3)
  → full rebuild from scratch — expensive, and the cycle restarts once §2n re-triggers
```

The three root causes are **independent but compounding**:
- RC#3 alone (with §2n) would block all auto-triggers, but the watcher would correctly re-queue and retry (pending paths preserved) — the user would see a perpetual "stale" badge, which is at least a signal.
- RC#2 alone (return True regardless) would cause silent drops, but only when `run_fast_sync` actually returns False — which, without RC#3, would be rare.
- RC#1 alone (close-enough gate) would suppress the coverage backstop for high-coverage repos, but the filesystem event path would still catch new files — until RC#2+RC#3 eat those events too.

Together, they produce a **completely silent** failure: no error, no log at WARNING, no UI badge, no re-queue. The user's only signal is "Last updated: N hours ago" in the Graph Scope card, which is easy to miss and gives no indication of *why*.

### 1.7 What this is NOT

- **NOT a watcher-not-started bug (§2q H-Q1).** The watcher is started by `watch.py:234` and registered in `_srv()._project_watchers`. The `is_building` callback at `watch.py:185-214` is functional. The watcher is running; it's the gates downstream of it that block.
- **NOT an FSEvents-not-delivering bug (§2q H-Q2).** Even when FSEvents *does* deliver (confirmed by the `started=False` log lines — `trigger_build` was called), the event is eaten by RC#2. And the coverage-check backstop (RC#1) doesn't depend on FSEvents at all.
- **NOT a glob-filter bug (§2q H-Q5).** The untraced files appear in the Graph Scope's "Untraced" list, which uses the same `compute_trace_coverage` that the coverage check uses. If they're visible in the UI, they're not filtered.
- **NOT a swarm-queue bug (§2p).** The §2s capture shows `cloud:default_ollama: 0/10` — no swarm is holding the slots. The work never got to the scheduler.
- **NOT a reset-barrier bug (§2l).** No `.reset_barrier` file is present in the observed cases. The barrier is a different stall mechanism.

### 1.8 Relationship to §2s (Edge Discovery stuck Pending)

§2s's "auto-incremental refuses to fire" half is **the same bug** as §2q — RC#1/RC#2/RC#3 all apply. §2s's "Edge Discovery renders spinning but is actually Pending" half is a **separate** UI-rendering bug (the `compute*State` family, §2r/§2a) — the row spinner says "running" but the queue widget says "Pending" because the UI's row-state derivation doesn't read S1 (the state machine). The §2s recurrence on 2026-06-19 (manual Rebuild All, 8h stall at 93%) is a **third** bug — a worker hang without timeout (H-S2/H-S6/H-S7), which needs the T4 worker-watchdog proposal, not this one.

This proposal addresses the **auto-refuses-to-fire** half of §2s and all of §2q. It does not address the UI-rendering half of §2s (that's the state-machine re-centering proposal, `PROPOSAL_state-machine-re-centering-v1.md`) or the worker-hang half (T4, not yet proposed).

---

## 2. Goals

1. **An auto-triggered fast_sync actually starts when there is legitimate work to do.** No gate silently returns `False` when `check_coverage_gap` says `needs_rebuild=True` and the files are real source.
2. **The watcher's pending set is not silently dropped.** If `run_fast_sync` returns `False`, the watcher re-queues and retries (with backoff), and the decision is logged at WARNING with the reason.
3. **The "close enough" coverage gate does not suppress legitimate source files.** The gate either (a) inspects the character of the untraced files (source vs binary/generated) before suppressing, or (b) is removed in favor of letting `run_fast_sync`'s own freshness check decide, or (c) is tightened to only suppress when the untraced files are all non-source.
4. **The downstream-partial guard does not permanently block on a stage that completed-with-empty-output.** The guard distinguishes "partial data on disk" (the real risk) from "stage ran but produced zero derivables" (§2n's shape — no data-integrity risk).
5. **Every silent skip is logged at INFO with a machine-parseable reason** so the user (and the dashboard) can see *why* the watcher decided not to act. (Per §2q design question #1.)

## 3. Non-goals

- **Fixing §2n (Immune System never completes).** That's a separate finding with its own root cause (UI count-gate + narrow derivation filter). This proposal makes RC#3 not depend on §2n being fixed, but §2n should still be fixed independently — it causes its own UI confusion and makes `finalize_resume` permanently 4/5.
- **The state-machine re-centering (T1) or worker-watchdog (T4).** Those address the UI-rendering half of §2s and the worker-hang half of §2s-recurrence, respectively. This proposal is orthogonal.
- **Changing the coverage-check interval (5 min) or cooldown (30 min).** Those are reasonable defaults. The bug is that the gate suppresses *legitimate* work, not that it fires too rarely.
- **Adding a "stale" badge to the Graph Scope card.** That's a defensive UI signal (§2q design question #4) and is valuable, but it's a UI change — track separately. This proposal ensures the backend stops silently dropping work; the UI can layer on top.
- **Reworking the `on_coverage_gap` callback contract.** The callback is never set in production; wiring it up is one option for RC#1 but not the only one (see §4.1 options).

---

## 4. Fix areas

Each area: **Problem → Approach (file:line) → Options → Test → Acceptance → Risk.** Areas are independently shippable and ordered by leverage/risk. **A1 is the smallest fix that breaks the vicious cycle; A2+A3 make the auto-trigger robust independently of §2n.**

### A1. Make `trigger_build` return the actual `started` value *(cheap, low-risk, highest leverage)*

**Problem.** `src/prep/api/routers/projects/watch.py:160-166` — `trigger_build` captures `started = pipeline_orchestrator.run_fast_sync(proj.id)` but returns `True` unconditionally. The watcher's `_on_debounce_fire` (`watcher.py:368-389`) checks the return value: if `False`, it re-queues the paths and re-debounces. Because the callback always returns `True`, the watcher eats the event and clears its pending set even when no build started.

**Approach.** Return `started` instead of `True`. The `except Exception` fallback at `:167-170` already returns `True` (legacy fallback path) — leave that as-is (the legacy build did start), but the primary path should reflect `run_fast_sync`'s result.

```python
# watch.py:160-166, before:
started = pipeline_orchestrator.run_fast_sync(proj.id)
logger.info(
    "Watcher: incremental fast_sync for %s — started=%s "
    "(deep auto-chains if per-project deepEnrichment=auto)",
    proj.id, started,
)
return True

# after:
started = pipeline_orchestrator.run_fast_sync(proj.id)
logger.info(
    "Watcher: incremental fast_sync for %s — started=%s "
    "(deep auto-chains if per-project deepEnrichment=auto)",
    proj.id, started,
)
return bool(started)
```

**Options considered:**
- (a) **Return `started` directly** (chosen). Smallest change. The watcher's existing `if not started: re-queue` path handles the `False` case correctly — it re-queues and re-debounces after `debounce_ms`. ✓
- (b) **Return `started` and also surface the reason.** `run_fast_sync` returns only `bool`; the reason for `False` is logged inside `run_fast_sync` but not returned. Enriching the return type to `(bool, str)` would let the watcher log the specific gate. More invasive — the `run_fast_sync` signature is used in many places. Defer to A4 (log visibility) instead.
- (c) **Keep returning `True` but have the watcher poll `_is_building()` after the call.** The watcher already does this via `_wait_for_build_complete` — but that thread starts *after* the `started=True` branch, so it never runs in the `False` case. Fixing this is equivalent to (a) with more steps.

**Test.** `tests/test_phase145_auto_trigger_return.py`:
- (a) Mock `run_fast_sync` to return `False`; assert `trigger_build` returns `False`; assert the watcher's `_pending_paths` is preserved (not cleared) and a new debounce timer is scheduled.
- (b) Mock `run_fast_sync` to return `True`; assert `trigger_build` returns `True`; assert the watcher transitions to `building` and starts `_wait_for_build_complete`.
- (c) Mock `run_fast_sync` to raise; assert `trigger_build` returns `True` (legacy fallback) — preserves existing behavior for the exception path.

**Acceptance.** When `run_fast_sync` returns `False`, the watcher re-queues the pending paths and re-debounces instead of silently dropping them. The untraced files remain in the pending set and are retried.

**Risk.** Low. The watcher's `if not started` branch (`watcher.py:374-389`) already exists and is well-tested — it re-queues and re-debounces. The only behavior change is that this branch now actually executes in the `run_fast_sync-returns-False` case. The re-debounce uses `debounce_ms` (default 5s), so a permanently-`False` `run_fast_sync` would re-debounce every 5s — which is noisy but not harmful (no build starts). A4 adds a backoff cap to prevent log spam. The `min_rebuild_gap_ms` throttle (`watcher.py:354-366`) also applies, limiting the retry rate.

### A2. Relax the "close enough" coverage gate for source files *(medium risk — changes when coverage check triggers)*

**Problem.** `src/prep/core/watcher.py:596-616` — the "close enough" gate suppresses the coverage-check trigger when `stale == 0 and coverage_pct >= 95.0 and untraced <= 20`, regardless of whether the untraced files are source or binary/generated/excluded. This defeats the backstop for high-coverage repos with a small number of legitimate untraced source files — exactly the §2q scenario.

**Approach.** The gate should inspect the *character* of the untraced files before suppressing. `check_coverage_gap` already returns the untraced file list when `include_paths=True` (`resume.py:885-891`); the watcher's fallback path doesn't pass `include_paths=True` today. Two options:

**Option (a) — tighten the gate to only suppress non-source untraced files (chosen).**

```python
# watcher.py, _on_coverage_check fallback path, before:
if gap.get("needs_rebuild"):
    if (stale == 0
            and coverage_pct >= self._COVERAGE_GAP_OK_PCT
            and untraced <= self._COVERAGE_GAP_OK_MAX_FILES):
        logger.info("... close enough, skipping")
    else:
        # trigger rebuild

# after:
if gap.get("needs_rebuild"):
    # Fetch the untraced file list to inspect their character.
    # The "close enough" gate is only safe when the untraced files are
    # all non-source (binary, generated, excluded). If any untraced
    # file is a source language the project cares about, trigger.
    should_suppress = False
    if stale == 0 and coverage_pct >= self._COVERAGE_GAP_OK_PCT and untraced <= self._COVERAGE_GAP_OK_MAX_FILES:
        # Re-check with include_paths to see what the untraced files are.
        gap_with_paths = pipeline_orchestrator.check_coverage_gap(
            self.project_id, include_paths=True
        )
        changed = gap_with_paths.get("changed_paths") or set()
        # A file is "source" if it matches the default include_globs
        # (the same set compute_trace_coverage uses). If any untraced
        # file is source, don't suppress.
        source_extensions = {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs",
            ".java", ".c", ".cpp", ".cc", ".h", ".hpp", ".swift",
            ".md", ".markdown",
        }
        has_source = any(
            Path(p).suffix.lower() in source_extensions
            for p in changed
        )
        if not has_source:
            should_suppress = True

    if should_suppress:
        logger.info(
            "Watcher coverage check for %s: %d untraced + %d stale "
            "files (%.1f%% coverage) — all non-source, close enough, skipping",
            self.project_id, untraced, stale, coverage_pct,
        )
    else:
        # trigger rebuild (unchanged)
```

**Option (b) — remove the gate entirely and let `run_fast_sync`'s freshness check decide.**

`run_fast_sync` already calls `check_coverage_gap` internally (`orchestrator.py:826`) and skips with `"up to date"` if `stale == 0 and untraced == 0` (`:892-903`). So the coverage check would trigger `run_fast_sync`, which would do its own gap check and skip if there's truly nothing to do. The cost is one extra `run_fast_sync` call per coverage-check cycle that immediately returns `False` — but that's cheap (one `check_coverage_gap` call, no stage work). The benefit is no duplicated gating logic.

Risk of (b): if `run_fast_sync`'s gap check and the watcher's gap check diverge (they use the same `check_coverage_gap`, so they shouldn't — but the watcher's `_on_coverage_check` also checks `_is_building` and cooldown, which `run_fast_sync` doesn't), the watcher might trigger more often than necessary. The cooldown (`_COVERAGE_COOLDOWN_SECONDS = 1800`) still applies, limiting the rate.

**Option (c) — wire up the `on_coverage_gap` callback in production.**

The "preferred path" (`watcher.py:580-585`) delegates to the caller and doesn't apply the gate. Wiring it up in `watch.py:224-233` would bypass the gate entirely. But the callback contract is underspecified — the caller would need to reimplement the cooldown, the `_is_building` check, and the trigger logic. More moving parts than (a) or (b).

**Chosen: (a).** It's the smallest change that preserves the gate's intent (suppress for binary/generated/excluded files) while fixing the false-suppress for source files. (b) is appealing for simplicity but changes the trigger frequency more than necessary; (c) is the most invasive.

**Test.** `tests/test_phase145_coverage_gate_source.py`:
- (a) 9 untraced `.py`/`.md` files, 99.1% coverage, 0 stale → gate does **not** suppress → rebuild triggered.
- (b) 9 untraced `.png`/`.lock` files, 99.1% coverage, 0 stale → gate suppresses (close enough).
- (c) 25 untraced `.py` files, 99.1% coverage → gate does **not** suppress (untraced > 20, fails the count check before the source check).
- (d) 9 untraced `.py` files, 94.0% coverage → gate does **not** suppress (coverage < 95, fails the pct check).
- (e) 5 stale + 9 untraced `.png` files, 99.1% coverage → gate does **not** suppress (stale > 0 — stale files are always worth re-running).

**Acceptance.** The coverage-check backstop triggers a rebuild when there are untraced **source** files, regardless of coverage % or count. It continues to suppress for non-source files at high coverage.

**Risk.** Medium. The gate was added for a reason (prevent infinite rebuild loops from binary/generated files that the walker sees but the tracer can't handle). Option (a) preserves that protection — it only relaxes the gate for source files, which the tracer *can* handle. The source-extension list mirrors `compute_trace_coverage`'s default `include_globs` (`coverage.py:69-75`), so the definition of "source" is consistent. The risk is a project with a custom `include_globs` that adds a non-default extension (e.g. `.rb`) — the gate's source-extension list wouldn't include it, so `.rb` files would be suppressed. Mitigation: read the project's `include_globs` from config instead of hardcoding (but that adds a config-read dependency to the gate — defer to scrutiny).

### A3. Distinguish "partial data" from "completed-with-empty-output" in the downstream-partial guard *(medium risk — changes when incremental fast_sync is allowed)*

**Problem.** `src/prep/services/pipeline/orchestrator.py:771-822` — the downstream-partial guard blocks incremental fast_sync when `0 < deep_resume < 5` or `0 < finalize_resume < 5`. With §2n (Immune System never completes), `finalize_resume = 4` permanently, so the guard blocks **all** incremental fast_sync. The guard doesn't distinguish:
- **"Stage has partial data on disk"** (the real risk — selfheal would extrapolate garbage). This is the `0 < resume < total` case where the stage *started but didn't finish*.
- **"Stage ran to completion but produced zero outputs"** (§2n's shape — no data-integrity risk). The stage's provenance manifest is absent not because it didn't run, but because it ran and had nothing to write (or wrote an empty manifest that's not detected as "complete").

**Approach.** The guard should check whether the incomplete stage has **partial on-disk data** (stage-specific output files exist but no provenance manifest) vs **no data at all** (no output files, no manifest — the stage either didn't run or ran and produced nothing). Only the former is a selfheal-extrapolation risk.

```python
# orchestrator.py:771-779, before:
deep_resume = self._detect_resume_point(
    project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
)
finalize_resume = self._detect_resume_point(
    project_id, FINALIZE_STAGES, skip_mtime_cascade=True,
)
deep_partial = 0 < deep_resume < len(DEEP_ENRICHMENT_STAGES)
finalize_partial = 0 < finalize_resume < len(FINALIZE_STAGES)
downstream_partial = deep_partial or finalize_partial

# after:
deep_resume = self._detect_resume_point(
    project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
)
finalize_resume = self._detect_resume_point(
    project_id, FINALIZE_STAGES, skip_mtime_cascade=True,
)
deep_partial = 0 < deep_resume < len(DEEP_ENRICHMENT_STAGES)
finalize_partial = 0 < finalize_resume < len(FINALIZE_STAGES)

# Phase 145 §2q/RC#3: distinguish "partial data on disk" (selfheal
# extrapolation risk — the original concern) from "stage ran but
# produced no derivable outputs" (§2n shape — no data-integrity risk).
# A stage is only a *blocking* partial if it has output files on disk
# but no provenance manifest. A stage with no output files and no
# manifest either didn't run or ran and produced nothing — neither
# creates a selfheal-extrapolation risk.
if deep_partial or finalize_partial:
    from prep.services.pipeline_integrity import STAGE_DATA_FILES
    store = ManifestStore(idx_dir)  # idx_dir resolved above
    def _has_partial_data(stages, resume_count):
        # Check only the stages past the resume point — those are
        # the "incomplete" ones the guard is worried about.
        for stage in stages[resume_count:]:
            if not store.provenance_exists(stage):
                data_files = STAGE_DATA_FILES.get(stage.value, [])
                if any((idx_dir / f).exists() for f in data_files):
                    return True  # partial data — blocking
        return False  # no partial data — not blocking

    # Need idx_dir — resolve it here (it's available in the enclosing
    # scope via the check_coverage_gap call below, but that's in a
    # try/except; resolve explicitly for clarity).
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project
    _proj = require_project(project_id)
    _idx_dir = Path(project_index_dir(_proj))

    deep_blocking = _has_partial_data(DEEP_ENRICHMENT_STAGES, deep_resume) if deep_partial else False
    finalize_blocking = _has_partial_data(FINALIZE_STAGES, finalize_resume) if finalize_partial else False
    downstream_partial = deep_blocking or finalize_blocking
else:
    downstream_partial = False
```

**Options considered:**
- (a) **Check for partial on-disk data** (chosen). Directly addresses the guard's stated concern (selfheal extrapolation from partial data). A stage with no output files has nothing for selfheal to extrapolate, so it's not blocking.
- (b) **Special-case `ANTIBODIES`** — exclude it from the `finalize_resume` count. Fragile — hardcodes a §2n assumption into the guard. If §2n is fixed, the special-case becomes dead code; if another stage develops a "never-complete" bug, it's not covered.
- (c) **Remove the guard entirely** and rely on selfheal's own safety checks. Too aggressive — the guard exists because selfheal *did* extrapolate garbage in the past (the Phase 98 comment at `:738-752`). The guard is a defense-in-depth layer; weakening it to "trust selfheal" removes the layer.

**Chosen: (a).** It's the most principled — it checks the actual condition the guard is worried about (partial data on disk) rather than a proxy (resume count). It works regardless of which stage is the "never-complete" one, so it's robust to §2n being fixed or not.

**Test.** `tests/test_phase145_downstream_partial_guard.py`:
- (a) `finalize_resume = 4` (ANTIBODIES missing), no ANTIBODIES output files on disk → guard does **not** block → incremental fast_sync proceeds. (The §2q/§2n scenario.)
- (b) `finalize_resume = 4` (ANTIBODIES missing), ANTIBODIES output files exist on disk (partial write) → guard **blocks** → incremental fast_sync skipped with reason. (The original Phase 98 concern.)
- (c) `deep_resume = 3` (DEEPENING + DEEP_KNOWLEDGE missing), no output files for either → guard does **not** block.
- (d) `deep_resume = 3`, DEEPENING output files exist but no provenance → guard **blocks**.
- (e) `deep_resume = 0` (no deep stages complete) → `deep_partial = False` → guard does **not** block (the all-zero case, already handled by the comment at `:762-770`).

**Acceptance.** Incremental fast_sync is only blocked when a downstream stage has **partial data on disk** (output files without a provenance manifest). A stage that ran but produced no outputs (§2n) does not block.

**Risk.** Medium. The guard is defense-in-depth against selfheal extrapolation. Option (a) preserves the defense for the case it was built for (partial data) while relaxing it for the case it wasn't (no data). The risk is a stage that writes output files *and* has zero derivable outputs — in that case, the output files would exist (maybe empty, maybe a header-only stub) and the guard would still block. This is a narrower case than §2n (which has *no* output files) and is acceptable — if a stage writes files, selfheal *might* extrapolate, so blocking is conservative-correct. Scrutiny should verify: does `ANTIBODIES` write any output files even when it produces zero derivables? If yes, (a) doesn't fully fix RC#3 and we need (b) as a fallback.

### A4. Log every silent-skip decision at INFO with a machine-parseable reason *(cheap, low-risk, visibility)*

**Problem.** Per §2q design question #1: today many of the watcher's "I tried to fire but bailed" decisions are DEBUG or unlogged. A user with Auto mode on has no way to know the watcher *did* see the file change but decided not to act. The `run_fast_sync` skip at `orchestrator.py:805-809` logs at INFO but with a generic message; the coverage-check suppress at `watcher.py:603-607` logs at INFO but doesn't say *why* it's "close enough" (no file-character breakdown). And the `trigger_build` return-`True`-always (A1) means the watcher doesn't even know a skip happened.

**Approach.**
1. After A1, the watcher's `if not started` branch (`watcher.py:374-389`) executes on `run_fast_sync-returns-False`. Add a `logger.info` there with the reason (if available — see A1 option (b) for enriching the return type; if not, log "run_fast_sync returned False — see orchestrator log for reason").
2. After A2, the coverage-check gate's suppress/trigger decision is already logged at INFO — ensure the log includes the file-character breakdown (how many source vs non-source untraced).
3. After A3, the downstream-partial guard's block decision at `orchestrator.py:805-809` is already logged at INFO — ensure it includes whether the block is due to partial data (blocking) or empty-output (not blocking, per A3).
4. Add a backoff cap to the watcher's re-debounce (A1's `if not started` branch) to prevent log spam if `run_fast_sync` permanently returns `False`: after N consecutive `False` returns, increase the debounce delay (e.g. `min(debounce_ms * 2^N, 300_000)` — cap at 5 min) and log at WARNING once per backoff step. Reset on the next `True`.

**Test.** Extend A1/A2/A3 tests to assert the log lines are emitted at INFO with the expected reason strings. Add a test for the backoff: N consecutive `False` returns → debounce delay increases → WARNING logged once per step.

**Acceptance.** Every silent-skip decision is recoverable from the daemon log at INFO. A user (or a future dashboard "watcher status" panel) can see *why* the watcher didn't act.

**Risk.** Low. Logging-only change. The backoff cap is a behavior change (re-debounce slows down on permanent `False`) but it's strictly better than the current behavior (silent drop — A1 fixes the drop, A4 prevents the re-debounce from spamming).

---

## 5. Implementation order and dependencies

```
A1 (return started)  ──────────────→  breaks the silent-drop (RC#2)
                                         │
                                         ├── standalone: watcher re-queues on False
                                         │   but if RC#3 still returns False, it re-debounces forever
                                         │   (A4 backoff prevents spam)
                                         │
A3 (partial-data guard)  ──────────→  breaks the permanent-block (RC#3)
                                         │
                                         ├── standalone: run_fast_sync returns True for §2n projects
                                         │   but if RC#2 still returns True-always, the watcher
                                         │   doesn't know it should re-queue (it thinks it succeeded)
                                         │
A1 + A3 together  ─────────────────→  the auto-trigger works for §2n projects
                                         │
A2 (source-file gate)  ────────────→  breaks the backstop suppress (RC#1)
                                         │
                                         ├── standalone: coverage check triggers for source files
                                         │   but if RC#2+RC#3 still eat the trigger, no build starts
                                         │
A1 + A2 + A3 together  ────────────→  all three root causes fixed
                                         │
A4 (logging + backoff)  ───────────→  visibility for any future silent-skip
```

**Recommended ship order:** A1 first (smallest, breaks the silent-drop, immediately improves UX even before A3). Then A3 (breaks the permanent-block — this is the one that depends on §2n's shape). Then A2 (breaks the backstop suppress — defense-in-depth for files the event path misses). Then A4 (visibility). Each is independently shippable and testable.

**Dependency on §2n:** A3 makes RC#3 not depend on §2n being fixed, but §2n should still be fixed independently — it causes `finalize_resume = 4` permanently, which means the `_check_incomplete_deep_enrichment` self-heal (`watcher.py:690-756`) will keep trying to auto-start deep enrichment (which is already complete), and the finalize group will never reach "all complete." Fixing §2n is a separate proposal.

---

## 6. Risk register

| ID | Risk | Mitigation |
|---|---|---|
| R1 | A1's re-debounce on `False` creates a tight retry loop (every 5s) if `run_fast_sync` permanently returns `False`. | A4's backoff cap (exponential up to 5 min). Also, the `min_rebuild_gap_ms` throttle (`watcher.py:354-366`) applies. |
| R2 | A2's source-extension list diverges from a project's custom `include_globs` — non-default source extensions (`.rb`, `.kt`) are suppressed. | Read the project's `include_globs` from config instead of hardcoding. Defer to scrutiny — the hardcoded list mirrors `compute_trace_coverage`'s default, so it's consistent for default-config projects. |
| R3 | A3's `_has_partial_data` check misses a stage that writes empty/stub output files even when it produces zero derivables. | Scrutiny must verify: does `ANTIBODIES` (or any finalize stage) write output files when it produces zero derivables? If yes, A3 doesn't fully fix RC#3 — need A3 option (b) (special-case) as a fallback. |
| R4 | A3 weakens the downstream-partial guard, which is defense-in-depth against selfheal extrapolation. | A3 only relaxes the guard for the no-partial-data case. The partial-data case (the original concern) still blocks. The guard remains defense-in-depth for its stated purpose. |
| R5 | A2's extra `check_coverage_gap(include_paths=True)` call adds latency to the coverage check (every 5 min). | `check_coverage_gap` is a disk walk + changeset read — typically <1s for repos <10k files. The call only happens when the gate *would* suppress (high coverage, few untraced), which is the common steady-state case. Acceptable. |
| R6 | The fixes don't address the `on_coverage_gap` callback being unset in production (§1.3.1). | Not a goal — the fallback path (with A2's fix) is sufficient. Wiring the callback is option (c) in A2, deferred. |
| R7 | A1 changes `trigger_build`'s return contract — other callers (if any) might depend on `True`. | `trigger_build` is a closure local to `watch.py:90` — it's only passed to `AutoRebuildWatcher` as `on_trigger_build`. No other callers. Verified by grep. |
| R8 | The three fixes don't address the §2s UI-rendering half (spinner vs Pending). | Non-goal — that's the state-machine re-centering proposal (`PROPOSAL_state-machine-re-centering-v1.md`). This proposal fixes the backend auto-trigger; the UI proposal fixes the rendering. |
| R9 | A3's `_has_partial_data` reads from disk on every `run_fast_sync` call (when `resume == 5`). | The check only runs in the `resume >= len(FAST_SYNC_STAGES)` branch (all fast sync stages complete), which is the incremental case. The disk reads are `Path.exists()` calls — cheap. |
| R10 | Fixing RC#3 (A3) without fixing §2n means `_check_incomplete_deep_enrichment` (`watcher.py:690-756`) will keep auto-starting deep enrichment that's already complete. | `_check_incomplete_deep_enrichment` checks `store.provenance_exists(stage)` for each deep stage (`watcher.py:727-730`) — if all deep stages have provenance, it returns early (`:731-732`). §2n is a *finalize* stage, not deep, so this self-heal doesn't trigger for it. No interaction. |

---

## 7. Open questions for scrutiny

| ID | Question |
|---|---|
| OQ1 | Does `ANTIBODIES` (or any finalize stage) write output files to disk when it produces zero derivable outputs? If yes, A3's `_has_partial_data` check would still see "partial data" and block — A3 doesn't fully fix RC#3. Need to inspect the ANTIBODIES worker's output behavior. (Determines whether A3 option (a) suffices or option (b) is needed.) |
| OQ2 | Should A2 read the project's `include_globs` from config instead of hardcoding the source-extension list? (R2.) The hardcoded list mirrors `compute_trace_coverage`'s default, but a project with custom `include_globs` adding `.rb` would have `.rb` files suppressed by the gate. |
| OQ3 | Should A1 also enrich `run_fast_sync`'s return type to `(bool, str)` so the watcher can log the specific gate that caused `False`? More invasive (signature change) but better visibility. Alternatively, A4's "see orchestrator log for reason" is sufficient if the orchestrator log is reliable. |
| OQ4 | Is the `min_rebuild_gap_ms` throttle (`watcher.py:354-366`) sufficient to prevent A1's re-debounce from spinning too fast, or is A4's backoff cap needed too? The throttle defaults to 2000ms — so re-debounce is at most every 2s. A4's backoff would slow this to 5 min on permanent `False`. Is 2s-forever acceptable, or do we need the backoff? |
| OQ5 | Should the "close enough" gate (A2) be removed entirely (option (b)) instead of tightened (option (a))? Option (b) is simpler (no source-extension list, no extra `check_coverage_gap` call) and relies on `run_fast_sync`'s own gap check to skip when there's truly nothing to do. The cost is one extra `run_fast_sync` call per coverage-check cycle that immediately returns `False`. Is that acceptable? |
| OQ6 | Does A3's `_has_partial_data` check need to handle the case where a stage's output files exist from a *previous* run (stale data from before a reset)? If a reset wiped the provenance manifest but left the output files, the guard would see "partial data" and block — but the data is stale, not partial. Need to check whether reset wipes output files or just manifests. |
| OQ7 | Should A4's backoff cap also reset the watcher's `stale_since` marker after N consecutive `False` returns, so the UI's "stale" badge doesn't stay on forever? Or should `stale_since` persist as a signal that the watcher is failing? (UI behavior — coordinate with the state-machine re-centering proposal.) |
| OQ8 | Is there a test that covers the full vicious cycle (§1.6) end-to-end? A1+A2+A3 each have unit tests, but the cycle is an integration behavior. Should there be an integration test that sets up §2n's state (ANTIBODIES never completes) and verifies the auto-trigger fires? |

---

## 8. TDD steps (summary — expand before execution)

1. **A1:** Write `tests/test_phase145_auto_trigger_return.py` with cases (a)/(b)/(c) from §4.A1. Run — expect (a) to fail (current code returns `True`, watcher clears pending). Apply A1 fix. Run — expect all pass.
2. **A2:** Write `tests/test_phase145_coverage_gate_source.py` with cases (a)-(e) from §4.A2. Run — expect (a) to fail (current code suppresses). Apply A2 fix. Run — expect all pass.
3. **A3:** Write `tests/test_phase145_downstream_partial_guard.py` with cases (a)-(e) from §4.A3. Run — expect (a) to fail (current code blocks). Apply A3 fix. Run — expect all pass. **Gate on OQ1** — if ANTIBODIES writes output files on zero derivables, (a) still fails after A3; need A3 option (b).
4. **A4:** Extend A1's test with backoff assertions. Apply A4 fix. Run — expect pass.
5. **Integration:** Write `tests/test_phase145_vicious_cycle_integration.py` — set up a project with §2n state (ANTIBODIES missing, no ANTIBODIES output files), add untraced source files, run the watcher's coverage check, verify `run_fast_sync` is called and returns `True`. (OQ8.)

---

## 9. Cross-references

- **§2q finding:** `FINDING_auto-incremental-never-fired-despite-stale-files.md` — root cause now pinned (RC#1/RC#2/RC#3 above). Hypotheses H-Q3 (debounce gated → actually `run_fast_sync` gated, RC#3) and H-Q6 (`_check_incomplete_deep_enrichment` stuck on §2n → actually the downstream-partial guard in `run_fast_sync` stuck on §2n, RC#3) are confirmed. H-Q1 (watcher not started), H-Q2 (FSEvents missed), H-Q5 (glob filter) are ruled out (§1.7).
- **§2s finding:** `FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md` — the "auto-refuses to fire" half is the same bug (RC#1/RC#2/RC#3). The "spinner vs Pending" half is the state-machine re-centering proposal. The 2026-06-19 recurrence (worker hang at 93%) is T4 (worker watchdog), not this proposal.
- **§2n finding:** `FINDING_stage15-antibodies-never-complete.md` — the upstream bug that turns RC#3 into a permanent block. This proposal makes RC#3 not depend on §2n, but §2n should still be fixed.
- **§2u finding:** `FINDING_manual-update-click-triggers-ui-cluster.md` — the meta-pattern. Fixing §2q (this proposal) removes the cascade trigger (the manual Update click workaround), and the UI cluster evaporates.
- **State-machine re-centering proposal:** `PROPOSAL_state-machine-re-centering-v1.md` — addresses the UI-rendering half of §2s and the broader S1-drift family. Orthogonal to this proposal.
- **Rebuild pre-registration proposal:** `PROPOSAL_rebuild-pre-registration-hang-and-barrier-safety-v1.md` — addresses the `force_from_start` hang and barrier safety. Orthogonal (different code path — the manual Rebuild button, not the auto-watcher).
- **Code pointers:**
  - `src/prep/core/watcher.py` — `AutoRebuildWatcher`, `_on_debounce_fire` (RC#2 consumer), `_on_coverage_check` (RC#1), `_check_incomplete_deep_enrichment`.
  - `src/prep/api/routers/projects/watch.py` — `trigger_build` closure (RC#2 source), watcher construction (§1.3.1 — `on_coverage_gap` not set).
  - `src/prep/services/pipeline/orchestrator.py` — `run_fast_sync` (RC#3 source), `_is_fast_sync_auto`, downstream-partial guard at `:771-822`.
  - `src/prep/services/pipeline/resume.py` — `check_coverage_gap` (the gap computation both paths use).
  - `src/prep/core/trace/coverage.py` — `compute_trace_coverage` (untraced/stale categorization, default `include_globs`).
  - `src/prep/services/pipeline/stages.py` — `FINALIZE_STAGES` (includes `ANTIBODIES`), `STAGE_DATA_FILES` (for A3's partial-data check).
  - `src/prep/server.py:1182-1194` — startup auto-run (no "close enough" gate — the contrast that confirms RC#1).
