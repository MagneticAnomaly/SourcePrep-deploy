# Phase 145 — Pipeline UI Reliability + Browser-Driven Diagnostics

**Status:** Open. Investigation + planning. No code changes proposed in this document yet.
**Owner:** Eric (created 2026-06-10, handoff-ready for an agent picking up cold)
**Predecessor:** `docs/superpowers/plans/2026-06-08-pipeline-reliability-ux-fixes.md` (P1–P6, all landed)
**Related code:** `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`, `src/prep/services/pipeline/`, `src/prep/api/routers/`

---

## 1. Why this phase exists

The 2026-06-08 plan (P1–P6) closed every single backend bug we traced from the original cross-project contamination incident. The orchestrator, scheduler, write guard, selfheal, and embedder all do the right thing now, and pipeline runs complete end-to-end.

**The UI does not consistently reflect that.** Three incidents in three days where:

- 2026-06-08: skipped stages displayed as `0% Running` indefinitely.
- 2026-06-09: the dashboard locked — clicks didn't register, the whole tab needed a refresh.
- 2026-06-10: every project shows `Deep Reasoning` (stage `enrichment`) stuck in an incomplete-looking state, and the UI is "extremely sluggish."

Each of these has a different proximate cause (uncommitted helper, broken PUT endpoint, state-rollup mismatch). The pattern is: **the UI's idea of pipeline state drifts from the daemon's reality, and the user can't tell why.**

Phase 145's job is to **stop firefighting individual UI bugs and produce a single source of truth for what the UI should display in every state**, plus a browser-driven test harness that pins it.

## 2. Symptom catalog (every observed bad behavior)

### 2a. Phase shows "incomplete" / "0% Running" when the stage actually finished

- **2026-06-08 form:** freshness-skipped stages emit `stage_start` + a `log` event, no `stage_end`. UI keeps the initial `"pending"` from `create_run_metadata` and renders "Iteration 0/?" / "Enriching…" forever.
- **Fix that landed:** `mark_stage_skipped` added to `pipeline_metadata.py` (P2, commit `1a04e097`).
- **Status:** verified live for new runs; **legacy projects whose metadata was written pre-fix still show the bug.**

### 2b. Deep Reasoning stuck across all projects (open, 2026-06-10)

- Every project's `enrichment` stage row shows incomplete in the panel.
- Probe of one project (SourcePrep) via `/projects/{id}/pipeline/status` shows `stages.enrichment.provenance.state == "match"` — i.e. **the backend says the stage is current**.
- `deep_enrichment` group is `null` (no active or recent run record).
- Hypothesis: the UI rollup in `GraphEnrichmentPipeline.tsx` derives stage state from a different source than `provenance.state` and they disagree.
- **Unverified.** See §6 Investigation Plan.

### 2c. Dashboard sluggish / unresponsive (open, 2026-06-09 and 2026-06-10)

- Whole-tab freeze where clicks queue but never fire.
- 2026-06-09 was traced (partially) to `PUT /global/config` returning 500 on every save because of a broken `_deep_merge` import — fixed in `883158db`.
- **The 2026-06-10 sluggishness persists after that fix**, so there's at least one more cause.
- Hypothesis: SSE event volume during long stages + React re-render storms on `/projects` list updates.
- **Unverified.**

### 2d. Cross-project surprise triggers

- Original 2026-06-08 incident: flipping a single project's auto toggle dispatched runs for every active trace-enabled project via a fan-out thread in the settings router.
- **Fixed** by P1 (`11033fc2`). Regression-pinned by `tests/test_settings_pipeline_config_no_fanout.py`.
- **Still worth verifying** that no other "global toggle → multi-project effect" paths exist (e.g., `crud.py:_activate_project`, `server.py:_startup_auto_run`).

### 2e. Process Logs panel hides the actual error

- The UI panel shows each log line as one row. When uvicorn writes `[uvicorn.error] Exception in ASGI application` followed by a 6–10 line Python traceback, the user sees one red row with a generic message and the traceback rows look like normal text below it. The actual exception class + message + file path are invisible at a glance.
- **Real symptom: the user couldn't tell what the daemon was failing at without dropping to the browser Network tab.**
- No fix landed for this yet.

### 2f. Sidebar queue shows stale state

- 2026-06-08 X-button heuristic (P3, `75dc3c9a` + `cf2d6874`) added toast-on-cancel + repeat-click escalation.
- **New symptom 2026-06-10:** Deep-Live-Cam shows `phase=queued, active=True` in `/projects/{id}/pipeline/status`, but `/system/pipeline-queue` returns empty. Two endpoints disagree about whether the project is queued.

### 2g. ImportError 500s on endpoints that aren't called at startup

- 2026-06-09: `PUT /global/config` 500'd for **weeks** without anyone noticing, because the broken `_deep_merge` import was inside the function body. Startup-time syntax/import checks didn't catch it.
- **Fixed by `883158db`** (the specific symbol) plus a regression test pinning the import path.
- **Class of bug worth auditing:** every other `from prep.server import ...` inside a function body could have the same latent break.

### 2h. Multiple "config" endpoints that look similar but behave differently

- `/global/config` (GET/PUT) — UI config blob.
- `/settings/pipeline-config` (GET/POST) — pipeline mode flags.
- `/mcp/config?ide=...` (GET) — MCP server snippet per IDE.
- `/projects/{id}/pm/config` (GET) — Paperclip plugin config.
- `/settings/advanced-config` (GET/POST) — advanced settings.
- `/admin/actions/approve-config` (POST) — admin gate.
- **No single API contract documents what state each endpoint owns**, leading to the dashboard PUTting partial updates to `/global/config` for things that probably belong elsewhere.

### 2i. Changeset never reports content edits — daemon-wide (FIXED, 2026-06-15)

- Edited source files (confirmed via `git diff`) were classified `changeset.unchanged` and never re-enriched or finalized — no error, no UI signal. Verified across **all 13 local projects**: every one had `hash_algo: None` and `modified=0`.
- **Root cause (one writer):** `ManifestStore.write_provenance` (STRUCTURAL branch) merged the stage provenance into `trace_manifest.json` preserving only `("file_hashes","config","file_errors")`, **dropping `hash_algo` and `built_at`**. Untagged → `_emit_changeset` always took Case 3 ("trust prior") → Case 2 (real diff) was dead → edits never `modified`. The dropped `built_at` is *also* the §earlier "always 0 stale" staleness bug. One writer, both symptoms.
- **Fix:** add `hash_algo` + `built_at` to `preserved_keys`. `_emit_changeset` is deliberately left alone (an untagged manifest is ambiguous vs a genuine pre-Phase-133 one, and already-swallowed edits have a poisoned baseline). Existing backlogs clear with a one-time force-rebuild.
- This is a **backend correctness** bug (distinct from the UI-drift focus of this phase, but surfaces as "the pipeline says up-to-date when it isn't").
- **Full root-cause + evidence:** [`FINDING_changeset-swallowed-edits.md`](FINDING_changeset-swallowed-edits.md). Tests: `test_phase145_provenance_preserves_hash_algo.py`, `test_phase145_changeset_swallow.py`, `test_phase145_finalize_incremental_hatch.py`.
- Related item, also fixed: Finalize never auto-chained on incremental runs (missing Phase 89 hatch in `run_finalize`).

### 2j. Stage `progress` regresses at sub-stage boundaries (open, 2026-06-15)

- Observed live: Group Reasoning's progress bar regressed mid-run (visible as bright-orange shrinkage under the old 3-slab incremental renderer). `progress_baseline` is frozen per stage (verified), so the regression is in `progress_current / progress_total`.
- Suspected cause: a stage worker with multiple internal phases reports each phase's progress as its own 0→N against the shared `progress_total`, so `current` snaps backward at phase boundaries. First place to look: `src/prep/core/epistemic_enrichment.py:842`.
- Visual symptom suppressed (not fixed) by the 3→2 slab collapse in `StageProgressBar` 'incremental' variant on 2026-06-15. Under the new renderer the green slab itself will visibly shrink if `progress` regresses — still wrong.
- **Full notes + recommended follow-up:** [`FINDING_stage-progress-non-monotonic.md`](FINDING_stage-progress-non-monotonic.md). Two layers: frontend monotonic guard (cheap, defensive) + backend stage-worker audit (correct).

## 3. What we know about the data flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE COMPLETION SIGNALS — multiple sources, must agree              │
├──────────────────────────────────────────────────────────────────────┤
│ 1. pipeline_run_metadata.json    ← canonical: who finished what when │
│    stage_metadata[].status         pending|running|completed|failed|skipped │
│ 2. <stage>_manifest.json         ← provenance: did the stage write?  │
│    .provenance.state               match|drift|missing|self_healed   │
│ 3. PipelineGroupStateMachine     ← in-memory: is anything active now │
│    .stage_results[stage]           running|completed|failed|skipped  │
│ 4. ManifestStore.age_summary()   ← mtime-derived: how stale?         │
└──────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ DASHBOARD READS                                                       │
├──────────────────────────────────────────────────────────────────────┤
│ /projects/{id}/pipeline/status — combines (1)+(2)+(3) into one blob   │
│   data.fast_sync / deep_enrichment / finalize  ← from (3)             │
│   data.stages.<stage>                          ← from (2)+manifest    │
│ /events SSE                     — pipeline_status push updates        │
│ /system/pipeline-queue           — orchestrator's queue snapshot       │
└──────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ GraphEnrichmentPipeline.tsx → derives per-row state from many props  │
│   enrichmentState, fastKnowledgeState, ...                           │
│   promoteForRebuild(...) → 'complete' | 'running' | 'not_built' | … │
└──────────────────────────────────────────────────────────────────────┘
```

**Drift surfaces** (places where (1)/(2)/(3)/(4) disagree → UI confusion):

| Drift | Observed symptom |
|---|---|
| (1) says `pending`, (3) says `skipped` | Stage shows "Running 0%" forever (the 2026-06-08 bug; partially fixed by P2) |
| (2) says `match`, (3) says no run | Stage shows "complete" but rollup says "incomplete" (suspected 2026-06-10 bug) |
| `/projects/{id}/pipeline/status.deep_enrichment` is `null` but `/system/pipeline-queue` says queued | Cross-endpoint disagreement (open) |
| `/queue` 404 but UI still calls it | Dead endpoint (the `/queue` → `/system/pipeline-queue` migration left stale callers) |

## 4. UI behavior contract (the source-of-truth this phase produces)

Goal: **the next agent should know what the UI should show for any pipeline state without having to reverse-engineer it from React props.**

### 4a. Stage row states (every row in every group)

| State | When | What the row should show | What it must NOT show |
|---|---|---|---|
| `disabled` | Stage is configured off | Greyed-out icon, label, no progress, hint "Disabled" | A progress bar, a percent, a spinner |
| `not_built` | First run never happened OR stage was reset | Label + "Not built" | A spinner, a 0% bar, "Pending" |
| `running` | Stage actively in-flight | Spinner, label, % progress (or indeterminate bar if `progress_total` unknown), live stat ("12/47 nodes…") | Stale stat from a prior run |
| `complete` | Stage finished, manifest matches, no newer inputs | Green check, label, last-run stat, age chip | A spinner, "Running…" |
| `complete_stale` | Stage finished but downstream inputs newer | Green check + amber stale chip | A green check with no chip |
| `failed` | Stage raised | Red icon, label, error tooltip | Silent success |
| `skipped` | Freshness check determined nothing to do | Grey check + "skipped: <reason>" tooltip | "Running 0%", "Iteration 0/?" |
| `paused` | User clicked pause | Pause icon, "Paused at stage N" | Spinner |
| `queued` | Stage acquired but waiting for slot | Hourglass, "Queued behind <other-project>" | Spinner |
| `recovering` | Selfheal is filling in a missing manifest | Spinner + "Self-healing…" | Plain "Running" |

### 4b. Group rollup states (Fast Sync / Deep Enrichment / Finalize headers)

A group's header state is the **lowest-priority terminal state across its stages**:

| Group state | When |
|---|---|
| `complete` | Every stage is `complete` or `skipped` |
| `complete_stale` | Every stage is `complete`/`skipped`, ≥1 stage's inputs newer than outputs |
| `running` | ≥1 stage is `running` or `queued` |
| `failed` | ≥1 stage is `failed` |
| `paused` | ≥1 stage is `paused` |
| `not_built` | ≥1 stage is `not_built` AND no stage is `running`/`failed` |

### 4c. Invariants the UI MUST hold

1. **Status-on-disk is truth.** When `pipeline_run_metadata.json:stage_metadata[X].status == "skipped"`, the panel for stage X must show `skipped`, not `running`. (P2 closed the *writer* side of this; we still need a UI test that exercises the *reader* side.)
2. **No `null` group → "stuck" rollup.** If `/projects/{id}/pipeline/status.deep_enrichment` is `null`, the group header should derive from stages, not show "incomplete by default."
3. **No conflicting `is_active`/`phase`.** `is_active: true` ↔ `phase ∈ {running, queued, paused}`. If we ever see `is_active: false, phase: running`, that's a state machine bug to surface, not a UI bug to paper over.
4. **No silent endpoint failure.** A 500 from a polled endpoint should produce a visible degraded-state indicator, not propagate as `undefined` into React props that then render as "stuck."
5. **No cross-project state.** Setting any flag on project A must not change what's displayed for project B.
6. **Refresh fixes everything.** A hard browser refresh must bring the UI back to a known-good state. If it doesn't, that's a daemon-side state bug, not a UI bug.

## 5. Diagnostic toolkit (the next agent runs these to interrogate live state)

```bash
# Daemon health + which process is serving
curl -s http://localhost:8400/health
ps aux | grep "prep.cli serve" | grep -v grep

# Per-project status (the dashboard's main poll target)
curl -s http://localhost:8400/projects/<PID>/pipeline/status | python3 -m json.tool | less

# Queue snapshot (note: NOT /queue — that path is dead, see §2f)
curl -s http://localhost:8400/system/pipeline-queue | python3 -m json.tool | head -30

# What manifest state actually says on disk
ls -la /Volumes/<path>/<project>/.sourceprep/*_manifest.json
cat /Volumes/<path>/<project>/.sourceprep/pipeline_run_metadata.json | python3 -m json.tool

# Tail the most recent run's structured event log
ls -lat /Volumes/<path>/<project>/.sourceprep/logs/pipeline_*.log | head -3
tail -50 /Volumes/<path>/<project>/.sourceprep/logs/pipeline_<latest>.log

# Streaming events the dashboard receives
timeout 5 curl -sN http://localhost:8400/events

# Test that PUT /global/config doesn't 500 (regression-prone area)
curl -s -X PUT http://localhost:8400/global/config -H "Content-Type: application/json" -d '{}' -w "\nHTTP: %{http_code}\n"

# Audit all `from prep.server import` inside function bodies (potential latent breaks like §2g)
grep -rn "from prep.server import" src/prep/ --include="*.py" | grep -v "def __init__" | head -20
```

## 6. Investigation plan (staged, for the next agent)

### Phase 145.1 — Browser-driven diagnostic harness (Playwright)

**Goal:** capture the symptom *while it's happening*, not via post-mortem.

#### Setup (one-time)

```bash
# Node 20+ required (matches the .nvmrc)
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
npm install --save-dev @playwright/test
npx playwright install chromium webkit
mkdir -p tools/playwright/pipeline-uat
```

#### Harness script: `tools/playwright/pipeline-uat/probe-pipeline.ts`

The script should:

1. Boot a Chromium context with **console + network capture** enabled.
2. Navigate to `http://localhost:5174` (Vite dev) or `http://localhost:8400` (built dashboard served by daemon).
3. Snapshot the network requests during dashboard load: status codes, URLs, sizes. Flag any 4xx/5xx.
4. Snapshot the browser console: errors, warnings.
5. Wait until the Graph Enrichment panel is rendered.
6. For each panel row (Deep Reasoning, Group Reasoning, Module Synthesis, Continuous Deepening, Deep Knowledge), read the rendered text and the icon's `data-state` attribute (or compute it from CSS class).
7. Cross-reference each row's state against `/projects/{id}/pipeline/status.stages.<stage>` fetched directly.
8. Write a report to `tools/playwright/pipeline-uat/reports/<timestamp>.json` listing:
   - Network errors (URL, status, response body)
   - Console errors (message, stack)
   - State drifts (UI row says X, API says Y, for each row)
9. Take a full-page screenshot in light + dark mode.
10. Optionally: simulate a click on the X button in the queue and verify the toast fires + the cancel endpoint is called with `reason: "user_action"`.

#### Wiring it as a watcher (the user's actual ask)

```bash
# Run once
npx playwright test tools/playwright/pipeline-uat/probe-pipeline.ts

# Run every 30 seconds (Playwright doesn't have built-in watching;
# wrap in a shell loop or use the Monitor pattern from elsewhere in this repo)
while sleep 30; do
  npx playwright test tools/playwright/pipeline-uat/probe-pipeline.ts \
    --reporter=line || echo "DRIFT DETECTED at $(date)"
done
```

#### What this proves

- **If the harness can NOT reproduce the "Deep Reasoning stuck" symptom**, it's an environment-specific issue (browser cache, localStorage, etc.) and we add a "clear state" step.
- **If it can reproduce**, the report JSON will show *exactly* which signal (network call, prop, state-rollup) is producing the wrong rendered state. That collapses 2026-06-10's "sluggish + stuck" reports into a specific drift to fix.

### Phase 145.2 — State reconciliation audit

Inventory every place stage status is read, written, or derived:

- **Writers:** `pipeline_metadata.mark_stage_*`, `ManifestStore.write_*`, `PipelineGroupStateMachine.transition`.
- **Readers:** `/projects/{id}/pipeline/status` handler, `/projects/{id}/status` handler, the SSE event emitters in `orchestrator.py`.
- **Deriver:** the rollup logic at `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1391+` (the `deepStages` array) and the equivalent in `fastStages` / `finalizeStages`.

Build a state-flow diagram. Identify each pair where the writer and reader use different field names or different state vocabularies. (For example: `stage_metadata.status` uses `"skipped"`, but `stage_results` uses `"skipped"` too — good. `provenance.state` uses `"match" | "drift" | "missing"`, which doesn't translate 1:1 to a row state — possible drift source.)

### Phase 145.3 — UI invariant tests

For each row in §4a, write a Playwright test that:

1. Mocks the daemon's `/projects/{id}/pipeline/status` response to a specific shape.
2. Asserts the corresponding panel row renders the expected state per §4a.

Coverage targets:
- All 9 row states across all 15 stages.
- The 6 invariants in §4c.
- The known drift cases in §3.

### Phase 145.4 — Performance audit (the "sluggish" symptom)

1. Capture a Chrome DevTools Performance trace during a 60-second window where the dashboard is "sluggish."
2. Identify the main-thread blockers — the typical suspects:
   - SSE event handler doing sync work on every event (look for handlers in `state/enrichmentReducer.ts`, `hooks/useEnrichment.ts`).
   - Large list renders without virtualization (the Concepts panel after 1700+ concepts; the Audit panel after 2000+ findings).
   - Toast queue accumulating without cleanup (P3's `cf2d6874` fixed the timer leak; verify it's still fixed in dist).
3. For each blocker, propose a fix (memoization, virtualization, debouncing) but **do not implement in this phase** — produce the audit report only.

### Phase 145.5 — Latent-broken-import audit

Class of bug from §2g. Grep every `from prep.server import` inside function bodies and verify each symbol still exists in `prep.server`.

```bash
grep -rn "from prep.server import" src/prep/ --include="*.py" -A 3 | grep -B 1 -A 3 "def "
```

For each hit, run `python -c "from prep.server import <symbol>"` to verify it imports. Fix any others like `_deep_merge`.

## 7. Open questions (the next agent should answer these before proposing code changes)

1. **Why does `Deep Reasoning` show stuck across all projects on 2026-06-10 when SourcePrep's `enrichment.provenance.state == "match"`?**
   - Hypothesis A: the panel reads from a different field (e.g., `epistemic.enriched_nodes` count) and a recent change reset that field without restoring it.
   - Hypothesis B: the panel reads from `stage_results` in the in-memory state machine, but the daemon was restarted and the state machine doesn't rehydrate this signal.
   - Hypothesis C: `promoteForRebuild()` is being called with a stale rebuild scope marker.
2. **Why is `/system/pipeline-queue` empty but `Deep-Live-Cam` shows `phase=queued, active=True`?**
   - These two endpoints must derive from the same source. If they don't, that's the bug.
3. **What is the dashboard saving via `PUT /global/config` on load?** The 231-byte payload from the 2026-06-09 Network tab is the question. If it's saving a partial UI preference, the writer should be moved to a per-project endpoint.
4. **How many ASGI-Exception 500s land per dashboard load today?** The 2026-06-09 screenshot showed ≥7 in the first minute. Whitelisting "expected startup races" (e.g., `__embedding__` slot probe before slots are init'd) vs. surfacing real bugs requires counting them.
5. **Does the `_check_incomplete_deep_enrichment` watcher (`src/prep/core/watcher.py:664`) fire across projects on file events?** Per the P1 contract it should be per-project — but the symptom "every project stuck" hints at a cross-project trigger we haven't found.
6. **What's the actual cause of the 2026-06-10 sluggishness now that the PUT /global/config 500 is fixed?** Requires Phase 145.4 perf trace.

## 8. What we already fixed (do not redo)

| Commit | Fix |
|---|---|
| `cac65709` | Phase 136 Part 15 concurrency observability + SWARM_CAPABLE gating |
| `bb27f152` | Projects router: tri-state `included_paths` + watcher parity |
| `bfdabc55` | Reset: added 9 missing files to TRACE_FILES |
| `5adba8ed` | mcp_direct: prep no-arg routes to tool_hi |
| `11033fc2` + `b3c6f45f` | **P1: killed settings router cross-project fan-out** |
| `1a04e097` | **P2: added missing mark_stage_skipped helper** |
| `beba167e` + `a06caae2` | **P3a: cancel endpoint accepts `reason` field** |
| `75dc3c9a` + `cf2d6874` | **P3b: X-button toast + repeat-click escalation** |
| `f88c6b8c` + `01774ea2` | **P4: Write Guard 10% baseline shrink tolerance** |
| `62a6bb59` + `554666ae` | **P5: selfheal defers Write-Guard-rejected stages** |
| `7c9d01c2` + `e1bf3360` | **P6: scoped close_shared_embedders** |
| `f214fd39` | Auto_config deep-merge (fixes Switch-to-Manual clobber) |
| `551ad579` | Watcher clears guard markers for all stage groups |
| `f0f6af2d` | `.guard_rejections.json` added to RECOVERY_MARKERS |
| `883158db` | **`PUT /global/config` 500 — `_deep_merge` import fix (UI hang root cause)** |
| `2c6fb8a1` | **`useToast` non-throwing no-op default + Storybook wrap** |

## 9. Files the next agent should know

### Backend hotspots

| File | Why |
|---|---|
| `src/prep/services/pipeline/orchestrator.py` | Stage transitions, write guard recovery, journal writes |
| `src/prep/services/pipeline_metadata.py` | `mark_stage_started/completed/failed/skipped`, the source of UI state |
| `src/prep/services/pipeline/recovery.py` | Selfheal + guard rejection markers |
| `src/prep/api/routers/projects/watch.py` | Watcher trigger, debounce, `_check_incomplete_deep_enrichment` parallel |
| `src/prep/api/routers/projects/build.py` | Build trigger |
| `src/prep/api/routers/system.py` | `/global/config` GET + PUT, validation |
| `src/prep/api/routers/queue.py` | `/system/pipeline-queue` snapshot |
| `src/prep/server.py` | Startup auto-run, SSE setup, registry hydration |
| `src/prep/core/watcher.py` | `AutoRebuildWatcher`, file-event handling, `_on_debounce_fire` |

### Frontend hotspots

| File | Why |
|---|---|
| `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | The panel that displays Deep Reasoning + all stage rows. Rollup logic at lines 1391+. |
| `packages/ui/src/components/trace/pipelineRollup.ts` | Group rollup computation (`computeGroupRollup`) |
| `packages/ui/src/components/trace/rebuildProgress.ts` | Rebuild progress + scope handling |
| `src/prep/dashboard/src/hooks/useEnrichment.ts` | SSE reaction + polling + state machine |
| `src/prep/dashboard/src/state/enrichmentReducer.ts` | Reducer for the enrichment state tree |
| `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` | Queue widget, X-button cancel flow, toast wiring |
| `packages/ui/src/components/primitives/Toast.tsx` | Toast provider, useToast, no-op default |
| `packages/ui/src/components/console/LogConsole.tsx` | Process Logs panel (§2e — needs traceback grouping) |
| `packages/ui/src/api/client.ts` | Daemon HTTP wrapper, `/global/config` GET/PUT (line 1037 was the 2026-06-09 culprit) |

### Tests that pin current contracts

```
tests/test_settings_pipeline_config_no_fanout.py   ← P1 contract
tests/test_freshness_skip_metadata.py              ← P2 contract (end-to-end)
tests/test_pipeline_metadata_skip.py               (does not exist; user wrote test_freshness_skip_metadata.py instead)
tests/test_pipeline_cancel_reason.py               ← P3a contract
tests/test_write_guard_clustering_shrink.py        ← P4 contract
tests/test_orphan_clustering_recovery.py           ← P5 contract
tests/test_close_shared_embedders_scope.py         ← P6 contract
tests/test_project_update_auto_config_merge.py     ← auto_config deep-merge contract
tests/test_recovery_markers_destroy.py             ← guard markers destroy contract
tests/test_global_config_put_import.py             ← PUT /global/config import contract
```

## 10. Handoff instructions for the next agent

You're picking up an investigation, not a code task. Read this document end-to-end before doing anything. Then:

1. **Do not start coding fixes.** Phase 145.1 (Playwright harness) and 145.2 (state reconciliation audit) are diagnostic phases that produce evidence. Phases 145.3+ propose fixes based on what 145.1/145.2 surface.
2. **Run the diagnostic toolkit in §5 first.** Capture the current state. Compare to the user's reports (§2b, §2c) to verify the symptoms are still active.
3. **Build the Playwright harness from §6.1.** That's the user's actual ask: "use Playwright to actually watch the browser and see its behavior." Don't skip it for shortcuts.
4. **For each open question in §7, write a short hypothesis-and-test document** in this phase folder (`docs/Phase145_Pipeline-UI-Reliability/Q1-deep-reasoning-stuck.md`, etc.) before proposing a fix.
5. **Treat the UI invariants in §4c as a contract.** Any proposed code change must preserve them.
6. **Daemon restart is required** any time you touch `src/prep/**`. `prep serve` has no hot-reload.

### Anti-patterns from this session

- **Dismissing user reports because the backend says it's fine.** I did this on 2026-06-09 ("the pipeline completed, you must be confused") — the user was right and the UI was hung. Believe the user's reported experience; the backend's `result: "completed"` doesn't help if the UI never reflects it.
- **Fixing symptoms one at a time.** The plan that landed (P1–P6) closed real bugs but left the broader UI-state-contract gap unexamined. Don't fix the next single "stuck" report; produce the contract first.
- **Skipping daemon restart before live validation.** Multiple times this session I "fixed" something and the user kept hitting the bug because the daemon was running pre-fix code.

### When you're done

- Phase 145.1 lands a working harness + report format.
- Phase 145.2 lands a state-reconciliation audit document.
- §7 open questions each have an answer (with evidence) recorded.
- §4 invariants have at least one Playwright test each.
- This phase doc gets a "Status: closed" line at the top, dated.
