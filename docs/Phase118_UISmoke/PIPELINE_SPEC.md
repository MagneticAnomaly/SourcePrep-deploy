# Pipeline Behavioral Spec — Phase 118 finalization

This is the canonical "how the trace-graph enrichment pipeline SHOULD
behave" reference for Phase 118 UI smoke testing. It is the merge of
existing scattered specs (Phase 89 state machine, Phase 114 pipeline
safety, Phase 117 RepairUX scoped endpoints, the `pipeline-testing` skill
references) into one document an autonomous test agent can read and
proceed without ambiguity.

Anywhere this spec disagrees with code, `PIPELINE_REFERENCE.md` (which
cites code line-by-line) wins. Anywhere this spec is silent and code is
also silent, that is an explicit gap recorded in §7.

---

## 1. The 15 stages and 3 groups

Stage IDs are stable (used in API, manifests, and DOM `data-stage-id`).

| Group | # | Stage ID | Outputs |
|---|---|---|---|
| Fast Sync | 1 | `structural` | `manifest.json`, `documents.json`, `embeddings.npy` |
| | 2 | `inferred_edges` | `trace_inferred_hashes.json`, `trace_edges.jsonl` |
| | 3 | `catalogue` | `trace_augmented.jsonl`, `trace_augment_manifest.json` |
| | 4 | `validation` | (validates catalogue; updates trace_augmented in-place) |
| | 5 | `knowledge` | `knowledge_documents.json`, `knowledge_embeddings.npy`, `knowledge_manifest.json` |
| Deep Enrichment | 6 | `enrichment` | `trace_epistemic.jsonl`, `trace_epistemic_manifest.json` |
| | 7 | `group_reasoning` | `group_reasoning_manifest.json` |
| | 8 | `clustering` | (cluster artifacts in `audit/`) |
| | 9 | `deepening` | `deepening_manifest.json` |
| | 10 | `deep_knowledge` | `deep_knowledge_manifest.json` |
| Finalize | 11 | `atlas` | `atlas.json`, `atlas_manifest.json`, `atlas_roles/` |
| | 12 | `rules` | `rules_manifest.json` |
| | 13 | `concepts` | `concepts_manifest.json` |
| | 14 | `audit` | `audit/`, `audit_manifest.json` |
| | 15 | `antibodies` | `antibodies_manifest.json` |

Swarm-capable (5 of 15): `group_reasoning`, `clustering`, `atlas`,
`concepts`, `audit` (`scheduler.py:53`).

## 2. State machine (per group)

Ten states; transitions enforced by `_TRANSITIONS` table at
`state_machine.py:130-192`. Invalid transitions are rejected and logged,
not raised — so callers must check return value of `transition()`.

```
                  ┌─────────────────┐
                  │      IDLE       │◀─────────RESET───────────┐
                  └─────────────────┘                          │
                          │                                    │
              START / ENQUEUE / CRASH_DETECTED                 │
                          ▼                                    │
            ┌────────┐ ┌────────┐ ┌────────────┐               │
            │QUEUED  │ │RUNNING │ │ RECOVERING │               │
            └────────┘ └────────┘ └────────────┘               │
              │  │       │  │  │         │                     │
       CAP    │  │PAUSE  │  │  │CANCEL   │RECOVERY_*          │
              ▼  ▼       ▼  ▼  ▼         ▼                     │
         RUNNING  PAUSING   CANCELLING                          │
                    │           │                              │
            STAGE_FLUSHED  STAGE_STOPPED                        │
                    ▼           ▼                              │
                  PAUSED    CANCELLED  ────────────────────────┤
                    │                                          │
              RESUME / ALL_DONE / CANCEL                       │
                    ▼                                          │
                  RUNNING / COMPLETED / CANCELLED              │
                                  │                            │
                                  │FAILED                      │
                                  ▼                            │
                                FAILED ─────────────────────────┘
```

Source: `state_machine.py:130-200` (full table in `PIPELINE_REFERENCE.md`).

## 3. The "ambiguous paused" pattern (THIS phase's central clarification)

A `phase=paused` snapshot is **not necessarily** the result of a user
pause. The recovery path constructs a synthetic PAUSED snapshot at
daemon startup whenever disk inspection finds an incomplete-but-flushed
group. The construction at `recovery.py:999-1012` does:

```
sm.transition(START)            # sets started_at = now()
sm.current_stage_index = resume # advances index in-memory
sm.transition(PAUSE)            # IDLE→...→PAUSING
sm.transition(STAGE_FLUSHED)    # PAUSING → PAUSED, sets finished_at = now()
```

All four happen in the same microsecond, producing the fingerprint:

```
phase: "paused"
is_paused: true
started_at:  T   ┐
finished_at: T+ε ┘  ε ≈ 0.0001s
journal_run_id: null  (state machine does not set; orchestrator does — and on hydration the orchestrator is bypassed)
stage_results: { … reflecting on-disk completed stages … }
```

This is NOT corruption. It is the recovery code's way of saying "the
disk is partially built, treat the in-memory state as a paused run so
the user can resume or cancel it." The bug is **the UI conflating it
with a user-pause**, since the user never clicked pause. From a testing
perspective:

1. Always begin a smoke run with `DELETE /index/destroy` (resets to
   IDLE/no-snapshot) to avoid inheriting a synthetic-paused snapshot
   from a prior session.
2. If a synthetic-paused snapshot is observed mid-test, that is a
   regression worth filing — the recovery path is firing during a run,
   not just at startup.

A real (user-triggered) pause has:

```
journal_run_id:  <uuid>           (orchestrator set on START)
finished_at - started_at:  > 1s   (real elapsed work)
.checkpoints/<stage>/  exists     (worker flushed actual state)
```

## 4. Multi-pipeline concurrency contract

This is the contract the Phase 118 harness MUST preserve so multi-project
support is not regressed.

- The scheduler maintains **per-node FIFO queues** (`scheduler.py:218-219`).
  There is no global queue.
- Two projects on **different compute nodes** can run pipelines in
  parallel (e.g. one on local Ollama, one on a cloud node).
- Two projects targeting the **same node** serialize via the per-node
  FIFO. Priority projects appendleft (`scheduler.py:1230`); normal
  projects append (`scheduler.py:1237`).
- A swarm window blocks other projects on the same node for the
  duration of the window plus the cooldown (`scheduler.py:865-921`,
  `981-990`).
- All `/pipeline/*` endpoints are **per-project**: `{project_id}` in
  the path. The harness must always pass the target `project_id` and
  must never assume the smoke project is the only one running.
- The harness queue observer (Task #10) MUST iterate the queue dump and
  filter by `project_id`. It MUST NOT fail if other projects are in the
  queue. It MUST NOT issue any pause/cancel/reset against another
  project.

## 5. Trigger-path behavioral specs

The 6 paths covered by Phase 118. For each: backend invariant, disk
invariant, UI invariant, queue invariant.

### 5.1 Cold initial build (T1)

- **Backend.** `DELETE /index/destroy` → `POST /pipeline/all`. Each of
  3 groups: `IDLE → QUEUED → RUNNING → COMPLETED`. Auto-chains
  Fast→Deep→Finalize (`orchestrator.py` chaining condition).
- **Disk.** All 15 manifests present afterward. No
  `.reset_barrier`. `.checkpoints/` empty.
- **UI.** All 15 stage rows visible from the start. Single-tone
  progress bars 0→100. Group header transitions
  `running` → `completed`. No two-tone bars (no baseline to show).
- **Queue.** Single project entry while running; entry removed on
  group completion. No barrier in dump.

### 5.2 Incremental rebuild (T2)

- **Backend.** Watcher fires `POST /pipeline/all` after a file change.
  `incremental=True` flag set. `_detect_resume_point` finds highest
  completed stage. Affected stages re-run; unaffected skip via
  manifest freshness check.
- **Disk.** Manifests updated in-place via temp + atomic rename
  (`augmenter.py:1899-1908`). No new `.checkpoints/` entries.
- **UI.** **Two-tone progress bars** on affected stages (darker
  baseline = prior count, lighter = new). Unaffected stages stay at
  100% green. Baseline number visible in the bar tooltip.
- **Queue.** Same as T1 but typically short-lived.

### 5.3 Rebuild all (T3 — Danger Zone scope=all)

- **Backend.** `POST /pipeline/rebuild`. Writes barrier
  `scope=all` BEFORE dispatch (`pipeline.py:403`). All 15 stages
  re-run with `force_from_start=True`. Barrier cleared automatically
  on stage 15 completion (`recovery.py:176-188`).
- **Disk.** All manifests overwritten via atomic swap. Old
  manifests transiently visible until swap (zero-downtime intent).
- **UI.** Single-tone bars 0→100 (no baseline). Barrier indicator
  visible throughout the run; clears at end. Stage rows do NOT
  reset visually mid-run (only at start).
- **Queue.** Project entry + barrier=all in dump.

### 5.4 Rebuild sync (T4 — Danger Zone scope=sync)

- **Backend.** `POST /pipeline/fast` with `force_from_start=true`
  (Phase 117). Barrier `scope=sync` written. Stages 1–5 re-run.
  Stages 6–15 manifests untouched. Barrier cleared on stage 5
  completion.
- **Disk.** Stages 1–5 manifests overwritten. Stages 6–15 manifests
  unchanged (mtime preserved). `.reset_barrier` present with
  `scope=sync` for the duration.
- **UI.** Only stages 1–5 animate. Stages 6–15 stay in their
  pre-rebuild state (typically green). Scoped progress style
  matches scope (the bar grouping shows "1/5 → 5/5", not "1/15").
- **Queue.** Project entry + barrier=sync.

### 5.5 Rebuild enrichment (T5 — Danger Zone scope=enrichment)

- Same as T4 but for stages 6–10 via `POST /pipeline/deep`.
- Note: T5 implicitly depends on stages 1–5 being complete (deep
  enrichment reads from `knowledge_documents.json`). The harness
  must verify pre-conditions or kick off T1 first.

### 5.6 Reset all (T6 — Danger Zone Reset scope=all)

- **Backend.** `DELETE /index/destroy` (`enrichment.py:1141-1335`).
  Wipes `ALL_DATA_FILES`, `.checkpoints/`, `.branch_snapshots/`,
  `audit/`, `atlas_roles/`, `git_evidence/`. Clears in-memory caches
  and SQLite stores (concepts, observations, pipeline_history,
  antibodies). Stops file watcher. Writes reset barrier.
- **Disk.** `.sourceprep/` reduced to its empty-project form
  (just `project.json` + `.reset_barrier`).
- **UI.** Pipeline panel transitions to pristine "never built"
  state IMMEDIATELY. No stale stage rows showing prior progress.
- **Queue.** No project entry; the destroy stops the watcher.

### 5.7 Reset enrichment (T7 — Danger Zone Reset scope=enrichment)

- **Backend.** `DELETE /enrichment/full-reset`
  (`enrichment.py:1101-1119`). Deletes stages 6–15 manifests +
  outputs. Clears `concept_store` and `antibody_store`. Writes
  barrier `reason=enrichment_reset`.
- **Disk.** Stages 1–5 manifests/outputs survive. Stages 6–15
  files removed. `_golden/` checkpoint dir wiped (F-78 fix path).
- **UI.** Stages 6–15 transition to "not built" badge.
  Stages 1–5 keep their green/completed state.
- **Queue.** Project entry shows scoped reset barrier.

### 5.8 Reset finalize (T8 — Danger Zone Reset scope=finalize)

- Same as T7 but only stages 11–15.
- Barrier `reason=finalize_reset`. Stages 1–10 unaffected.

## 6. UI selector contract (data-testids the harness depends on)

This phase ADDS the following testids. Selector contract — break this
and the harness goes blind:

| Where | testid | Purpose |
|---|---|---|
| Pipeline panel container | `pipeline-panel` | Existing — DO NOT change |
| Each stage row | `pipeline-stage-row-<stage_id>` | Existing — DO NOT change |
| Stage row data attrs | `data-stage-id`, `data-stage-state`, `data-stage-progress` | Existing canonicalisation tables (`tools/playwright_smoke.py`) |
| Settings overlay open button | `settings-overlay-open` | NEW (Task #9) — opens the settings drawer |
| Settings nav: Danger Zone | `settings-nav-danger-zone` | NEW |
| Rebuild scope select | `pipeline-danger-rebuild-scope-select` | NEW |
| Rebuild submit button | `pipeline-danger-rebuild-button` | NEW |
| Reset scope select | `pipeline-danger-reset-scope-select` | NEW |
| Reset submit button | `pipeline-danger-reset-button` | NEW |
| Confirm dialog container | `pipeline-danger-confirm-dialog` | NEW |
| Typed-confirm input (rebuild) | `pipeline-danger-confirm-typed-name-input` | NEW |
| Confirm submit button | `pipeline-danger-confirm-submit` | NEW |
| Barrier indicator | `pipeline-barrier-indicator` | NEW (or existing; verify) |

Harness-side canonicalisation lives in `tools/playwright_smoke.py`'s
`DOM_STATE_TO_CANON` map (see `playwright-smoke` skill §7). State
vocab today: `running`, `rerunning`, `queued`, `not_built`, `disabled`,
`paused`, `complete`, `stale`, `warning`, `error`. If a new state is
added, both the panel and the canonicalisation table must update in
the same commit.

## 7. Open questions — explicitly NOT resolved by this phase

These remain documented gaps. The harness should record but not
diagnose:

1. **Swarm cooldown timer start.** When does the 45s cooldown begin —
   on swarm window close, on stage end, on first non-swarm dequeue?
   `scheduler.py:865-990` is silent; only the duration is documented.
2. **Auto-recover stale pipelines.** `recovery.py:33-35` mentions an
   auto-recover for auto-mode projects but staleness threshold and
   trigger cadence are undocumented.
3. **`PipelineHealth.stuck_runs` threshold.** Phase 114 spec defines
   the field but not the threshold or whether it's configurable.
4. **Progress baseline on full rebuild.** Phase 89_05:71-74 flags that
   `progress_baseline > 0` may persist into a rebuild from prior run
   state. Should rebuild explicitly zero the baseline? Code path
   currently inherits.
5. **Manifest `provenance` field write timing.** Phase 114 defines the
   values but not when they're written. Test path will record what we
   observe.
6. **Model-swap-on-resume semantics across stages 7→8.** If pause
   lands at stage 7 and resume changes model, does stage 7 re-run
   with the new model? `state-machine.md:45` is ambiguous.
7. **Journal grain.** Per-stage row vs per-group row vs per-run row.
   `recovery.py:40-44` and `pipeline-testing/SKILL.md:80` disagree.
8. **Synthetic-paused detection in UI.** Should the dashboard
   distinguish synthetic-paused (hydration) from user-paused? Today
   the API exposes the same `phase=paused` for both. Tests will
   document the symptom; fix is out of scope.

## 8. Stop conditions for autonomous test runs

The harness should halt and surface the failure (rather than continue)
when:

- `/pipeline/status` returns 500 — the dashboard's disk-fallback path
  will mask state machine bugs as UI bugs (see `pipeline-testing/SKILL.md` §8).
- A `desync` event is logged within the **first 15s** of a mode
  (startup grace window). This indicates the harness setup itself is
  broken, not the panel.
- The journal and the state machine snapshot disagree on `status` for
  the project under test. Hydration on next restart will misbehave.
- Selfheal log says "resurrecting orphan" on a stage that just
  completed successfully in this run. The cleanup invariant is broken.
- Baseline progress count is smaller after a daemon restart than
  before — F-66 regression.
- Any other project's pipeline state appears to mutate as a side
  effect of the test. Multi-project contract violated.

When halted, the harness writes the failure cause to `events.jsonl`
and exits non-zero. RESULTS.md should record the file path of the
events log so the next agent can pick up triage.
