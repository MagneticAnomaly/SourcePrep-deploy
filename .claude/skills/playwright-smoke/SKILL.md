---
name: playwright-smoke
description: Use when validating that the dashboard UI matches backend reality during a pipeline run — especially after touching pipeline status endpoints, panel state, barrier handling, or recovery flows. Wraps tools/playwright_smoke.py to drive the dashboard headlessly while polling /pipeline/status and flagging any UI↔API disagreement as a desync event with screenshot.
---

# Playwright Pipeline Smoke

The pipeline-testing skill is a runbook for poking the backend by hand. This one is for **catching the bugs that only show when the dashboard is in the loop** — desyncs between what `/pipeline/status` says and what the UI renders. Phase 96D existed because the UI claimed "Analyzed" while a stage was still running. The smoke driver was written to make that class of bug detectable in a single command.

This skill is a **harness wrapper**, not a runbook. The harness does the polling + screenshotting; you set up the project, pick the scenario, and read the report.

## 0. When to reach for this

Use this skill when:

- You changed anything that feeds the pipeline panel: `/pipeline/status`, `/pipeline/health`, `/pipeline/reset-barrier`, `useEnrichment`, `usePipelineHealth`, `GraphEnrichmentPipeline.tsx`, `RecoverStagePanel`, `BarrierIndicator`.
- You changed status caching, hydration, or recovery — anything where the API can lie briefly because of stale state.
- You are about to land a Phase 114 follow-up (T15/T16/T17) and want a regression net.
- Manual click-through "looks fine" but you want a paper trail before merging.

Use the `pipeline-testing` skill instead when:

- The bug is purely backend (state-machine transition, journal entry, manifest write).
- You need disk/journal probes that don't have a UI surface.
- The dashboard isn't running or is broken — the harness needs `:5174` up.

The two skills are complementary. The runbook tells you **what** to test; this skill tells you **how to verify the UI agreed**.

## 1. Pre-flight

Both must be up before invoking the harness — it has no boot logic of its own.

```bash
# 1. Daemon at :8400
curl -s localhost:8400/health | jq .status   # expect "ok"

# 2. Dashboard at :5174
curl -sI localhost:5174 | head -1            # expect 200 OK

# 3. Pick a project_id (any project that has a working repo path on disk)
curl -s localhost:8400/projects | jq '.data[] | {id, name, path}'
```

If you don't have both servers, run `scripts/dev.sh` from the repo root — it brings up the daemon, dashboard, and storybook. The harness will fail fast with a clear error if either is missing.

## 2. The three modes

| Mode | What it does | When to use |
|---|---|---|
| `initial` | `DELETE /index/destroy` then `POST /pipeline/all` | Full cold start; exercises hydrate-from-empty, all 15 stages, every group transition |
| `incremental` | Writes `codrag_smoke_tick.py` to the repo, waits, then `POST /pipeline/all` | Watcher path; only affected stages should re-run; baseline must come from manifest (F-66) |
| `rebuild` | `POST /pipeline/rebuild` (Danger Zone equivalent) | Full reset+run via the UI button path; exercises `.reset_barrier` lifecycle |

Default is all three sequentially. They can take 30+ minutes per project if Deep Enrichment is enabled, so on a small project this is fine; on `swift_repo` consider running one mode at a time.

## 3. Invoke

Always use the project venv (this repo's `.venv/bin/python` — see auto-memory).

```bash
# Headless, all three modes, single iteration
.venv/bin/python -m tools.playwright_smoke \
  --project-id 1d6f0b35-45cb-427b-ae9d-aac3c6371a4b \
  --modes initial,incremental,rebuild

# Headed (watch the browser drive itself — useful when debugging selectors)
.venv/bin/python -m tools.playwright_smoke \
  --project-id <pid> \
  --modes rebuild \
  --headed

# Quick triage of a single mode
.venv/bin/python -m tools.playwright_smoke --project-id <pid> --modes incremental
```

Outputs land in `tests/eval/ui_smoke/run_<UTC-timestamp>/<mode>/`:

- `summary.json` — pass/fail, duration, stages observed, desync count, error count
- `events.jsonl` — one event per line: `stage-start`, `stage-end`, `desync`, `error`, `note`
- `*.png` — screenshots tagged by event (e.g. `desync_clustering_progress_gap.png`)
- Top-level `report.md` summarises all modes for the run

Exit code is **non-zero if any desync or error was observed**. Wire it into CI / `make test-ui` when ready.

## 4. What counts as a desync

The harness only flags **confident** disagreements (it deliberately does not guess during idle). See [references/desync-rules.md](references/desync-rules.md) for the full canonicalisation table.

| Kind | Meaning | Likely cause |
|---|---|---|
| `api_running_dom_not_running` | API says stage X is running; DOM shows pending/complete/failed | Stale dashboard state, missed SSE/poll, or the panel was hidden when the event fired |
| `api_complete_dom_still_running` | API says stage X finished this run; DOM still spinning | Reducer/hook didn't consume the completion event |
| `progress_gap` | API and DOM both say running, but progress numbers differ by >5% | Two different progress sources (manifest vs in-memory) |
| `dom_claims_running_while_api_idle` | No group is running per API; DOM claims something is | The 96D symptom — UI is showing a stale pre-restart state |

Each (stage, kind) pair is logged **at most once per transition**. Same disagreement re-detected 2s later is suppressed; the screenshot you have is the one you need.

## 5. Phase 114 hooks (what to verify when touching panel/barrier code)

These are not built into the harness today; they are **add-ons you should invoke alongside** the standard modes when the relevant code path changed. See [references/phase114-hooks.md](references/phase114-hooks.md) for the curl/DOM assertions to splice in.

| Code path you touched | Add-on check | Why |
|---|---|---|
| `BarrierIndicator.tsx` / `clearBarrier` flow | After mode runs, `POST /pipeline/reset-barrier` then immediately `GET /pipeline/status` and verify `barrier.active=false` (cache-invalidation regression — fixed in commit hardening the DELETE handler) | Status cache TTL is 3s; if the DELETE doesn't pop the cache the indicator looks stuck |
| `RecoverStagePanel.tsx` aria/labels | Run with `--headed`, tab through panel — every action has a label | A11y regression net |
| `useEnrichment` / `usePipelineHealth` panelVisible gate (T15) | Toggle the trace-pipeline panel hidden in dashboard layout, run `incremental`, then check daemon logs for `/pipeline/health` requests during the run — should be **zero** | The hooks must stop polling when the panel is hidden |
| `pipeline_checkpoint.prune_*` (T37 startup GC) | Before run: count `<idx>/.checkpoints/run-*` dirs. Restart daemon. Re-count. Should cap at `keep=3` per project; `_golden` survives | Startup prune is silent; this is the only way to verify it ran |

When you add a new Phase 114 hook to this list, also add the corresponding assertion snippet to `references/phase114-hooks.md` so the next agent has a copy-paste recipe.

## 6. Interpreting a failed run

```bash
# 1. Open the report
cat tests/eval/ui_smoke/run_<ts>/report.md

# 2. For any failed mode, read its event log
jq -c '.' tests/eval/ui_smoke/run_<ts>/<mode>/events.jsonl | grep -E 'desync|error'

# 3. Look at the screenshot named in the desync event
open tests/eval/ui_smoke/run_<ts>/<mode>/<seq>_desync_<stage>_<kind>.png
```

The screenshot is the ground truth — it is what the user would have seen at the moment of the desync. Cross-reference with daemon logs at the same wall-clock time (events are ISO timestamps).

**Common false positives:**

- Desync within the first 15s (`startup_grace_seconds`). Already filtered by the harness, but if you tightened the grace window and now see noise here, restore it.
- `dom_claims_running_while_api_idle` flagged immediately after a `complete` transition — could be a 1-tick lag rather than a real bug. Check the next event.
- `progress_gap` between Deep Enrichment manifest count and in-memory count when the manifest is being written piecewise. Tolerate up to 5%; harness already does.

If a desync survives those filters, it is real — open a ticket.

## 7. Selector contract (don't break this)

The harness scrapes the DOM via `data-testid` and `data-stage-*` attributes:

- `[data-testid="pipeline-panel"]` — the GraphEnrichmentPipeline container (used as "panel hydrated" signal)
- `[data-testid^="pipeline-stage-row-"]` — one per stage row
- `data-stage-id="<stage_id>"` — must match the canonical 15 stage IDs (see §1 of pipeline-testing skill)
- `data-stage-state="<state>"` — one of: `running`, `rerunning`, `queued`, `not_built`, `disabled`, `paused`, `complete`, `stale`, `warning`, `error`
- `data-stage-progress="<0-100 or empty>"` — numeric percent or empty string

If you rename or remove any of these, the harness goes blind and silently passes everything as "DOM not rendered." Update the canonicalisation tables in `tools/playwright_smoke.py` (`DOM_STATE_TO_CANON` map, `scrape_pipeline_dom` evaluator) in the same PR, and update `references/desync-rules.md`.

The state vocabulary has grown twice without the harness being updated — `disabled` and `paused` were added later. Treat the canon table as part of the panel's public contract.

## 8. When to extend the harness vs add an assertion in this skill

- **One-off verification** of a specific Phase N regression → add a curl/DOM snippet to `references/phaseN-hooks.md`.
- **Pattern that will recur** across modes → add a new `--check <name>` flag to `tools/playwright_smoke.py` and document it here.
- **New observation primitive** (e.g. WebSocket/SSE traffic) → first prove the use case manually, then promote to the harness with a flag.

YAGNI applies; don't add flags that won't be used by the next agent.

## 9. Cross-references

- `pipeline-testing` skill — the runbook this complements
- `tools/playwright_smoke.py` — the harness itself; read it before extending
- `archive/scripts/eval-oneoff/playwright_ui_smoke.py` — older variant; do not resurrect, kept for reference only
- Phase 96D commit `59c9d770` — original motivation (UI/API desync class of bugs)
- `docs/Phase106_ReviewRecent/MASTER_TODO.md` — Phase 114 follow-up list this skill helps execute (T17 in particular)
