# Known Gaps (F-XX series)

These are tracked issues in pipeline resume/recovery. Grep the codebase for each tag to find current status. Update this file when a gap is closed or a new one is opened.

## F-65 — Skip projects with clean shutdown marker

**State:** implemented (hydrate skips)
**Symptom if regressed:** graceful-restart resumes completed runs that should stay dormant
**Where:** `services/pipeline/recovery.py` hydrate phase

## F-66 — Progress baseline persistence

**State:** partially implemented
**Symptom if regressed:** after daemon restart, 2-tone progress bar resets to 0/N instead of showing prior progress as baseline
**Where:** per-stage manifest must persist `progress_baseline`; recovery reads it back into status endpoint
**Test:** start a run, let it reach 50% on stage 7, SIGTERM, restart, observe `progress_baseline` in `/pipeline/status` for stage 7

## F-67 — Manifest-delete-before-worker orphan outputs

**State:** implemented (selfheal stubs)
**Symptom if regressed:** hard-crash during a stage leaves orphan output that either (a) never runs again because selfheal claims it complete, or (b) selfheal deletes useful data
**Where:** `orchestrator.py` stage-start cleanup; `startup_selfheal_all()`
**Test:** start stage 7, `kill -9` daemon mid-stage, restart, verify stage 7 re-runs (not skipped)

## F-68 — Incremental resume vs full restart distinction

**State:** partially implemented
**Symptom if regressed:** daemon restart loses incremental progress and appears to start over
**Where:** hydrate path vs crash-recovery path in `recovery.py`
**Test:** see S1 in the main skill

## F-69 — Skip deactivated/frozen projects on hydrate

**State:** implemented
**Symptom if regressed:** deactivated project resumes on daemon restart
**Where:** `hydrate_paused_runs_from_disk()` — checks project frozen flag
**Test:** deactivate a paused project, restart daemon, verify it does not resume

## F-75 — Interrupted-run recovery gap

**State:** partially implemented
**Symptom if regressed:** certain crash patterns leave a run that neither resumes nor is marked failed
**Where:** `RecoveryManager.resume_crashed_run`
**Test:** induce a crash during swarm fan-out (multi-worker stage), inspect journal after restart

## F-76 — KnowledgeIndex manifest fallback

**State:** partially implemented
**Symptom if regressed:** `/pipeline/status` reports `item_count: 0` for stage 5 (knowledge) after restart, despite manifests indicating complete
**Where:** `recovery.py` / `knowledge` stage — runtime count needs manifest fallback
**Test:** complete stage 5, restart daemon, observe stage 5 count in status

## F-78 — Full reset completeness

**State:** implemented (see `tests/test_scoped_full_reset.py`)
**Symptom if regressed:** after a scoped reset, old data reappears on next finalize completion (selfheal resurrects from `.checkpoints/_golden/`)
**Where:** `_golden/` must be wiped by reset; `.reset_barrier` blocks selfheal until next finalize
**Test:** `_seed_checkpoint()` pattern in `test_scoped_full_reset.py`

## Relationship map

```
Daemon start
  ├── F-65 (skip clean-shutdown projects)
  ├── F-69 (skip deactivated projects)
  ├── F-67 (selfheal orphan outputs)
  ├── F-75 (resume crashed runs from journal)
  └── hydrate paused runs
      ├── F-66 (restore baseline counts)
      └── F-76 (restore knowledge count)

User triggers reset
  └── F-78 (wipe checkpoints/_golden + write barrier)
```

## Adding a new gap

If you find a new bug during testing:

1. Reserve the next F-number (F-79, F-80, ...).
2. Add an entry above with: state, symptom, location, repro test.
3. Link it from the symptom table in `../SKILL.md` §7.
4. If the gap maps to a bug that persists across restarts, add to the map in this file.
