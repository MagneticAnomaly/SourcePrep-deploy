# Recovery Flow

Entry point: `RecoveryManager.startup_recovery()` — called once on daemon start.

Source: `src/prep/services/pipeline/recovery.py:736`.

## Startup phases

### Phase 1 — Journal crash detection

`journal.recover_crashed_runs()` scans `prep_pipeline_journal.db` for runs with status `running` that did not transition to `completed`/`failed`/`paused` before the previous shutdown.

For each, `verify_trace_files()` checks whether expected output files exist:

- If all expected outputs exist → mark `completed` (journal was never updated)
- If partial outputs → mark `recovering`, call `auto_heal()`
- If no outputs → mark `failed`

### Phase 98 — Startup selfheal

`startup_selfheal_all()` — scans projects for orphan output files whose manifests are missing (F-67: manifest is deleted at stage start, worker writes data, then re-writes manifest at end; daemon crash between leaves orphan data).

For each orphan: writes a **stub manifest marked incomplete** if the output is shared with prior stages (so the next run knows to re-do it), otherwise claims it.

### Phase 2 — Hydrate paused runs from disk

`hydrate_paused_runs_from_disk()` — scans projects for checkpoints in `.checkpoints/`. For each:

- Creates a PAUSED state machine at the checkpoint's stage
- Skips projects marked deactivated/frozen (F-69)
- Skips projects with clean shutdown marker (F-65)

### Phase 61B — Auto-recovery for auto-mode projects

`auto_recover_stale_pipelines()` — for projects with auto-mode enabled, restarts `deep_enrichment` if incomplete.

Use with caution in testing: if you are testing pause/resume and the project is auto-mode, it may resume itself before you can observe the paused state.

## What restores cleanly

- ✅ Journal run rows (project_id, group_name, stage_index, chain flags)
- ✅ Paused runs with checkpoints in `.checkpoints/`
- ✅ Completed manifests (always read from disk)
- ✅ Orphan outputs via stub manifests (marked incomplete)

## What does NOT restore cleanly

- ❌ Partially-written stage outputs **without** any manifest (F-67 edge: manifest deleted, worker crashes before writing data — output file is zero-byte or missing; selfheal cannot tell the stage ran at all)
- ❌ Progress baseline counts across restarts — unless F-66 manifest persistence is implemented for the stage
- ❌ KnowledgeIndex runtime count (F-76: needs manifest fallback)
- ❌ Swarm fan-out worker state across restarts — active swarm is dropped, stage re-runs sequentially

## Testing tips

1. **Simulate graceful restart** — `SIGTERM` gives Python time to flush checkpoints. Use this to test the paused-run hydration path.
2. **Simulate hard crash** — `kill -9` bypasses cleanup. Use this to test selfheal and orphan-output paths.
3. **Always check `.reset_barrier` after a crash** — if a barrier was in place before the crash, it must still be present. Selfheal must not resurrect stages behind an active barrier.
4. **Inspect the journal after restart** — the `status` column tells you what Phase 1 decided. If it says `completed` but outputs are missing, journal/disk disagree.

## Related concept files

When investigating recovery bugs, also check:

- `.branch_snapshots/` — branch-switch snapshots (a separate persistence path, used by full-reset)
- `.checkpoints/_golden/` — golden-state snapshots used during Finalize for selfheal resurrection (F-78 territory)
- `prep_pipeline_history.db` vs `prep_pipeline_journal.db` — history is completed runs only; journal is live state
