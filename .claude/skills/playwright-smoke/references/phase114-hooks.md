# Phase 114 Add-on Assertions

Snippets to splice in **alongside** a standard smoke run when the
corresponding code path changed. None of these are baked into
`tools/playwright_smoke.py` yet — they are copy-paste recipes.

## H1. Barrier indicator + cache invalidation

**Why:** `/pipeline/status` has a 3s `_STATUS_CACHE_TTL`. The DELETE
handler at `src/codrag/api/routers/pipeline.py` invalidates the cache
on success. If that invalidation regresses, the indicator appears stuck
on for ~3s after the user clicks Clear.

```bash
PID=<project_id>

# Force a barrier (any scoped reset writes one)
curl -sX DELETE localhost:8400/projects/$PID/enrichment/full-reset | jq

# Confirm it's visible to the API
curl -s localhost:8400/projects/$PID/pipeline/status \
  | jq '.data.barrier'   # expect { active: true, reason: "enrichment_reset", ... }

# Clear it
curl -sX DELETE localhost:8400/projects/$PID/pipeline/reset-barrier | jq

# IMMEDIATELY (not 3s later) re-check status — must already show inactive
curl -s localhost:8400/projects/$PID/pipeline/status \
  | jq '.data.barrier.active'    # expect false
```

If the second status check still shows `true`, the cache pop is broken.
Test: `tests/test_pipeline_barrier_clear.py::test_barrier_lifecycle_end_to_end`.

## H2. RecoverStagePanel a11y sweep

**Why:** Recover-stage actions are how a user unwedges a failed pipeline.
If labels are missing, screen-reader users cannot operate them.

Run smoke with `--headed`, then in the dashboard manually:

1. Trigger a failed stage (kill daemon mid-run, restart, observe failure surface).
2. Tab through the RecoverStagePanel — every actionable element must
   announce its purpose. Specifically:
   - "Retry stage <stage_id>" button
   - "Skip stage <stage_id>" button
   - "Reset stage <stage_id>" button
3. The panel container has `role="region"` and `aria-label="Recover stage"`.

If any label is missing or generic ("button"), open a regression ticket.

## H3. Panel-visibility polling gate (T15)

**Why:** `useEnrichment` and `usePipelineHealth` are gated on
`panelVisible`. If the gate regresses, the daemon takes 1 req/s
(`/pipeline/status`) and 1 req/10s (`/pipeline/health`) per project per
client, even when the user has the panel closed.

```bash
# Tail the daemon access log
tail -f ~/.local/share/codrag/logs/daemon.log | grep -E '/pipeline/(status|health)'

# In dashboard: hide the trace-pipeline panel via the layout drawer.
# Then trigger a run:
curl -sX POST localhost:8400/projects/$PID/pipeline/all

# Expected: ZERO /pipeline/health requests during the run.
# /pipeline/status requests should ALSO be zero from this client
# (the watcher loop in the harness will still poll, that's fine —
#  filter the log by user-agent if needed).
```

If you see steady polling while the panel is hidden, the prop didn't
thread end-to-end. Walk it: `App.tsx → useEnrichment` and
`App.tsx → useDashboardPanels → usePipelineHealth`.

## H4. Checkpoint GC at startup (T37)

**Why:** Happy-path prune runs only on `run_completed`. Crash-looping
projects accumulate `<idx>/.checkpoints/run-*` forever. The startup
prune in `server.py` caps at `keep=3` per project; `_golden` survives.

```bash
PID=<project_id>
IDX=$(curl -s localhost:8400/projects/$PID | jq -r '.data.index_dir')

# Count before
ls "$IDX/.checkpoints/" | grep -c '^run-'    # note the number

# Restart daemon
pkill -TERM -f 'codrag serve' && sleep 2 && codrag serve &

# Wait for /health
until curl -sf localhost:8400/health > /dev/null; do sleep 0.5; done

# Count after
ls "$IDX/.checkpoints/" | grep -c '^run-'    # expect min(before, 3)

# Golden must survive
ls "$IDX/.checkpoints/_golden/"              # expect non-empty
```

Test coverage: `tests/test_checkpoint_gc.py`.

## H5. (Future) Time-aware barrier stash (T16)

Pending decision on T16. When implemented, add an assertion that:

1. A barrier older than the configured TTL is auto-cleared on next
   `/pipeline/status`.
2. The cleared barrier reason is logged (not silently dropped).

Leave this section as a placeholder until the feature lands.
