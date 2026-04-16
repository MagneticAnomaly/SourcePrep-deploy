---
name: pipeline-testing
description: Use when testing, debugging, or regression-checking the CoDRAG graph enrichment pipeline — especially pause/resume, daemon restart, or reset workflows. Encodes the 15-stage state machine, observation primitives, and known failure modes (F-66/67/69/75/76/78) so agents do not improvise.
---

# Pipeline Testing Runbook

The CoDRAG graph enrichment pipeline has 15 stages in 3 groups, a 10-state per-group state machine, two scoped reset endpoints, a swarm fan-out path for 5 of the stages, and a recovery manager that hydrates paused/crashed runs on daemon start. It is not a black box. Testing it by clicking "Rebuild" and watching the bars is not sufficient — the failure modes are in the transitions, not the happy path.

This skill is a **runbook**, not a harness. Follow it; do not automate it away.

## 0. Before you start

1. **Restart the daemon** if you have not already since the last code change. The dashboard silently falls back to disk-manifest reads when `/pipeline/status` returns 500, so stale bugs can look like UI bugs. Restart first, rule it out.
2. **Pick a project** — note its `project_id`. Testing always targets a specific project; there are no global pipeline controls.
3. **Baseline disk state** — run `ls <idx_dir>` once before starting. You will compare against it after every reset/restart/pause scenario.
4. **Open three windows**: dashboard, daemon logs (`tail -f`), and a terminal for `curl`/`sqlite3` probes.

## 1. The 15 stages (exact names)

Full table with queue types and swarm-capability: [references/stages.md](references/stages.md)

| Group | Stages (stage_id in code) |
|---|---|
| Fast Sync (1–5) | `structural`, `inferred_edges`, `catalogue`, `validation`, `knowledge` |
| Deep Enrichment (6–10) | `enrichment`, `group_reasoning`, `clustering`, `deepening`, `deep_knowledge` |
| Finalize (11–15) | `atlas`, `rules`, `concepts`, `audit`, `antibodies` |

**Swarm-capable** (5 of 15): `group_reasoning`, `clustering`, `atlas`, `concepts`, `audit` — see `src/codrag/services/pipeline/scheduler.py:53`.

## 2. State machine

Full transition table: [references/state-machine.md](references/state-machine.md). Defined in `src/codrag/services/pipeline/state_machine.py:94-200`.

Ten per-group states. Key ones to watch during testing:

- `idle` → `queued` → `running` → `completed` (happy path)
- `running` → `pausing` → `paused` (user pause, checkpoint saved)
- `paused` → `running` (resume, re-reads LLM config — model can change between pause and resume)
- `running` → `recovering` → `running` (daemon restart mid-stage)
- `paused + cancel` → `cancelling` → `cancelled` (pause+cancel chain)
- any → `failed` (stage error; recovery behavior depends on stage)

**Invariant under test:** a state transition must have an on-disk effect (manifest written, checkpoint saved, barrier dropped) OR an in-memory effect that survives the next `/pipeline/status` poll. If the UI shows a state that disk does not reflect, the state machine and hydration code disagree.

## 3. Observation primitives

Full endpoint list: [references/endpoints.md](references/endpoints.md).

**During a test, you will only need these five:**

```bash
# Live pipeline state (cached 2–3s per project)
curl -s localhost:8400/projects/$PID/pipeline/status | jq

# Start a run
curl -X POST localhost:8400/projects/$PID/pipeline/rebuild  # full reset + run all 15

# Pause / resume a group
curl -X POST localhost:8400/projects/$PID/pipeline/pause  -d '{"group":"deep_enrichment"}' -H 'Content-Type: application/json'
curl -X POST localhost:8400/projects/$PID/pipeline/resume -d '{"group":"deep_enrichment"}' -H 'Content-Type: application/json'

# Scoped reset (stages 6–15 only; fast sync survives)
curl -X DELETE localhost:8400/projects/$PID/enrichment/full-reset
```

**Disk probes** (run from `<idx_dir>`):

```bash
ls *.jsonl *.json           # presence of per-stage outputs/manifests
cat .reset_barrier 2>/dev/null   # "enrichment_reset" or "finalize_reset" if a scoped reset is active
ls .checkpoints/             # pause checkpoints
ls .branch_snapshots/        # branch-switch snapshots (full-reset path)
```

**Journal DB** (crash recovery source of truth):

```bash
sqlite3 codrag_data/codrag_pipeline_journal.db \
  "SELECT run_id, project_id, group_name, stage_index, status FROM pipeline_runs ORDER BY started_at DESC LIMIT 5"
```

## 4. Workflow test matrix

Run each scenario on a clean project. Reset between runs (`DELETE /enrichment/full-reset` is usually enough; `/pipeline/rebuild` if you want stages 1–5 rebuilt too).

| # | Scenario | How to trigger | What to verify |
|---|---|---|---|
| W1 | Fresh index (empty `.codrag/`) | `POST /pipeline/rebuild` on a never-built project | Stages progress 1→15 in order; each group transitions `idle→queued→running→completed`; all 15 manifests written |
| W2 | Incremental rebuild | Edit one source file, wait for watcher, observe | Only affected stages re-run; baseline progress counts come from manifest (F-66) not zero |
| W3 | Scoped enrichment reset | `DELETE /enrichment/full-reset` on a fully built project, then `POST /rebuild` | Fast sync (1–5) files survive the DELETE; stages 6–15 wiped; `.reset_barrier` present; selfheal does not resurrect |
| W4 | Scoped finalize reset | `DELETE /finalize/full-reset` | Stages 1–10 survive; 11–15 wiped; `.reset_barrier` = `finalize_reset` |
| W5 | Swarm-capable stage | Run to `group_reasoning` (stage 7) with capacity > 3 and cloud model | Log shows `swarm_window_opened`; fan-out workers visible; synthesis stage completes |
| W6 | Swarm fallback | Same but cap compute to `max_concurrent:1` (apple_silicon profile does this) | Log shows swarm skipped; stage runs sequentially with `cloud_concurrency` cap (currently 10) |

**Known blocker for W5/W6 today:** apple_silicon profile seeds `max_concurrent:1`, capacity ≤3, so swarm path never opens. Pending investigation — see task #18.

## 5. Pause-state test matrix

Pause is where bugs hide. Test at three boundaries.

| # | Scenario | How to trigger | What to verify |
|---|---|---|---|
| P1 | Pause mid-stage | While `running`, `POST /pipeline/pause` with group name | State transitions `running→pausing→paused`; checkpoint file in `.checkpoints/`; no partial manifest written for the interrupted stage |
| P2 | Pause between stages | Time the pause to land during a stage transition | Lands on a clean stage boundary; resume re-enters at next stage, not mid-stage |
| P3 | Pause during swarm fan-out | Pause while a swarm-capable stage has active fan-out workers | All workers finish or cancel cleanly; no orphaned worker state in journal |
| P4 | Resume after pause | `POST /pipeline/resume` | State `paused→running`; stage count continues from checkpoint (not from 0); LLM config re-read (model can be swapped between pause and resume — test this) |
| P5 | Pause during Finalize | Pause during stages 11–15 | No half-written atlas/rules/concepts/audit/antibodies manifests; resume completes cleanly |
| P6 | Pause + cancel | Pause, then cancel | State `paused→cancelling→cancelled`; checkpoint removed; can start fresh run |

**What to check in the journal after each P#:**

```bash
sqlite3 codrag_data/codrag_pipeline_journal.db \
  "SELECT stage_index, status, stage_state_json FROM pipeline_runs WHERE run_id='<run_id>'"
```

The `status` column must match the on-disk state machine snapshot. If it does not, hydration on next daemon start will misbehave.

## 6. Shutdown / restart test matrix

Full recovery flow documented in [references/recovery.md](references/recovery.md).

| # | Scenario | How to trigger | What to verify |
|---|---|---|---|
| S1 | Graceful daemon restart mid-pipeline | `codrag serve` → start run → SIGTERM → `codrag serve` | Journal has incomplete run; `RecoveryManager.startup_recovery()` picks it up; resumes at correct stage (F-66 baseline preserved) |
| S2 | Browser refresh while running | Refresh dashboard while stage 7 is running | UI reconciles from `/pipeline/status`, not stale disk read. (If status endpoint returns 500, dashboard falls back to disk and shows wrong state — this was the bug fixed in 7512669e.) |
| S3 | Hard crash (kill -9) | `kill -9 <pid>` mid-stage | On restart: `auto_heal()` runs; selfheal resurrects orphan outputs as stub manifests marked incomplete (F-67); incomplete stage is re-run |
| S4 | Shutdown during Finalize | Kill during stages 11–15 | Atlas/rules/concepts/audit/antibodies manifests either fully written or absent (no half-state); selfheal resurrects via `.checkpoints/_golden/` (F-78) |
| S5 | Restart on deactivated project | Deactivate project, restart daemon | Hydrate skips deactivated/frozen projects (F-69) — no runs resurrected for them |
| S6 | Restart with clean shutdown marker | Graceful stop + restart | Clean marker prevents re-resuming completed runs (F-65) |

## 7. Known failure modes (what symptom → what bug)

Full gap list: [references/known-gaps.md](references/known-gaps.md).

| Symptom observed during testing | Likely bug | Where to look |
|---|---|---|
| After daemon restart, progress bar resets to 0/N instead of resuming at previous count | **F-66** — manifest baseline not persisted | `services/pipeline/recovery.py` baseline fields |
| After hard crash, selfheal resurrects a stage that should re-run | **F-67** — manifest-delete-before-worker pattern creates orphan outputs | `orchestrator.py` stage-start cleanup |
| Deactivated project resumes on daemon restart | **F-69** — hydrate does not skip frozen projects | `recovery.py:hydrate_paused_runs_from_disk` |
| Interrupted-run recovery drops state | **F-75** — no journal entry for interrupted run | `recovery.py:resume_crashed_run` |
| KnowledgeIndex count reads 0 after restart | **F-76** — manifest fallback missing | `recovery.py` / `knowledge` stage |
| After full reset, old data comes back on next finalize | **F-78** — `index_destroy_project` missed stores | `_golden/` resurrection path |
| Group Reasoning shows "Analyzed" while clearly running | pipeline_status 500 → dashboard falls back to disk | already fixed in `7512669e`; restart daemon |
| `pipeline_ui` config not persisting | config_manager whitelist | already fixed in `f0b98911`; restart daemon |

## 8. Red flags that mean STOP and investigate

- `/pipeline/status` returns 500 — do not diagnose UI bugs until this is fixed.
- State machine and journal disagree on `status` — hydration will misbehave; do not proceed with pause/resume tests.
- Selfheal log says "resurrecting orphan" on a stage that just completed successfully — the cleanup invariant is broken.
- Baseline progress count is smaller after restart than before the restart — F-66 regression.
- Swarm window opens but no fan-out workers log — capacity calculation wrong or cooldown not honored.

## 9. When adding new tests

1. Pick a scenario from §4–6 and **reproduce the happy path first**. If the happy path is broken, do not test the failure injection.
2. Add an entry to the relevant matrix in this skill file when you find a new gap.
3. Prefer observable-from-HTTP-endpoints checks over DB introspection. DB checks are for bug diagnosis, not regression coverage.
4. Do not add pipeline pytest fixtures that mock the scheduler, the journal, or the recovery manager. Those are exactly what we are testing. Use real `TestClient(app)` (see `tests/test_scoped_full_reset.py` for the pattern).

## 10. Referenced commits and fixes

- `7512669e` — fixed `pipeline_status` NameError for `modules_path` / `deep_has_run`
- `f0b98911` — added `pipeline_ui` to config_manager whitelist
- `a37cf3e0` — introduced the deep_knowledge_status refactor that caused 7512669e

Both fixes need a daemon restart to take effect. If either symptom reappears after restart, the fix regressed.
