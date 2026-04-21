# Pipeline UI Smoke Driver — Design

**Date:** 2026-04-16
**Phase:** 96D.5 (from `docs/Phase96-fix-pipeline/02_UI_SYNC_DIAGNOSTIC.md`)
**Goal:** Catch UI↔backend desyncs in the dashboard pipeline panel across initial/incremental/rebuild cycles. Runnable over and over against the local daemon.

## Scope

Build `tools/playwright_smoke.py` — a sync Playwright driver that:
1. Drives the dashboard against a chosen project (default: PowerMateReborn).
2. Exercises three pipeline modes: `initial` (from-scratch), `incremental` (touch-a-file), `rebuild` (Danger Zone).
3. Polls `/projects/{id}/pipeline/status` and scrapes the pipeline panel DOM in parallel.
4. Emits screenshots + JSON events whenever API and DOM disagree on stage/phase/progress, and at every stage transition.

Out of scope (v2): active-state toggle testing, queue panel assertions, multi-project orchestration.

## CLI

```
python -m tools.playwright_smoke \
  [--project-id 2e356d01-beaa-4559-8b5f-ceadb14b7203] \
  [--modes initial,incremental,rebuild] \
  [--iterations 1] \
  [--headed] \
  [--dashboard-url http://localhost:5174] \
  [--api-url http://localhost:8400] \
  [--out-root tests/eval/ui_smoke]
```

## Modes

| Mode | Precondition | Trigger | Done when |
|---|---|---|---|
| `initial` | any prior index is destroyed first | `POST /projects/{id}/pipeline/all` | `finalize.phase == "completed"` or all 15 `stages[*].exists == true` and no group is `running` |
| `incremental` | project has a complete index | write `.prep_smoke_tick.py` with timestamp into the repo; wait ≥5s debounce | pipeline returns to idle; delete tick file after |
| `rebuild` | project has a complete index | click Danger Zone → Rebuild in UI; fall back to `POST /pipeline/rebuild` if selector missing | pipeline returns to idle |

## Watch loop (every 2s while any mode is active)

1. Fetch `/projects/{id}/pipeline/status` → authoritative.
2. Read dashboard DOM: stage rows by `data-testid="pipeline-stage-row-{id}"`, read `data-stage-state` and `data-stage-progress`.
3. Compare — desync if any of these disagree for the same `stage_id`:
   - `running` API group vs `running` DOM state
   - `progress` integer within ±1 (rounding tolerance)
4. On desync: log event `{type:"desync", stage, api, dom, ts}` and snap `desync_<ts>.png`.
5. On stage transition (API-driven): log `{type:"stage-start"|"stage-end", stage, ts}` and snap `<mode>_<seq>_<stage>_<state>.png`.

## Output

```
tests/eval/ui_smoke/run_<UTC-ISO>/
├── report.md               # human roll-up across modes
├── initial/
│   ├── events.jsonl
│   ├── summary.json        # { mode, duration_s, stages_observed, desync_count, pass }
│   └── *.png
├── incremental/...
└── rebuild/...
```

Exit code: `0` if every mode passed (no desyncs, no API failures); `1` otherwise.

## Frontend patch

Add `data-testid` + `data-stage-state` + `data-stage-progress` attrs to `StageRow` in `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`. Zero behavior change; selectors only. Also tag the three group headers (Fast Sync / Deep Enrichment / Finalize) with `data-testid="pipeline-group-{id}"` and the Rebuild button when we find it.

## Risks

- **Stage-state label mapping.** API group phases (`running`/`paused`/`completed`/`cancelled`) vs DOM stage states (`running`/`rerunning`/`complete`/`queued`/`disabled`/`stale`/`warning`/`not_built`) aren't 1:1. Driver maps both to a canonical `{pending, running, complete, failed}` set before comparing; surfaces unmapped values as desyncs with a `reason` field rather than crashing.
- **Incremental trigger noise.** Writing into the repo mutates user-visible files. Tick file is prefixed `.prep_smoke_` and cleaned up in a `finally`; restore step logs its action.
- **Rebuild confirmation dialog.** If Danger Zone gates behind a text-match confirm, driver types the project name. If that fails, falls back to the API.
- **Daemon restart mid-run.** Driver detects by comparing a run `started_at` to the previous poll; logs `daemon-restart` event and resumes polling.

## Verification

Run end-to-end locally against PowerMateReborn with each mode in isolation first, then combined. Any desync findings become either (a) a real Phase 96D bug to fix or (b) a driver mapping gap to patch.
