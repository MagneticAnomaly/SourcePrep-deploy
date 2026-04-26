# Pipeline Code Reference — Phase 118

Code-grounded reference. Every claim has a `file:line` citation.
This is the source of truth when `PIPELINE_SPEC.md` is silent or
ambiguous.

## State machine — `src/prep/services/pipeline/state_machine.py`

### Valid transitions (`_TRANSITIONS` table at `state_machine.py:130-192`)

The table is enforced — invalid transitions are **rejected and logged**
at `state_machine.py:351-366`, returning `False` rather than raising.
Callers that ignore the return value can silently no-op.

```
IDLE       → START                     → RUNNING
IDLE       → ENQUEUE                   → QUEUED
IDLE       → CRASH_DETECTED            → RECOVERING

QUEUED     → CAPACITY_AVAILABLE        → RUNNING
QUEUED     → CANCEL                    → CANCELLED
QUEUED     → STAGE_COMPLETED           → RUNNING   (Phase 48-F8 edge)
QUEUED     → ALL_STAGES_DONE           → RUNNING   (Phase 48-F8 edge)

RUNNING    → STAGE_COMPLETED           → RUNNING   (loop)
RUNNING    → ALL_STAGES_DONE           → COMPLETED
RUNNING    → ENQUEUE                   → QUEUED    (between-stage re-queue)
RUNNING    → PAUSE                     → PAUSING
RUNNING    → CANCEL                    → CANCELLING
RUNNING    → STAGE_FAILED              → FAILED

PAUSING    → STAGE_FLUSHED             → PAUSED
PAUSING    → CANCEL                    → CANCELLING
PAUSING    → STAGE_FAILED              → FAILED

PAUSED     → RESUME                    → RUNNING
PAUSED     → ALL_STAGES_DONE           → COMPLETED   (Phase 25, line 169)
PAUSED     → CANCEL                    → CANCELLED

CANCELLING → STAGE_STOPPED             → CANCELLED

RECOVERING → RECOVERY_SUCCEEDED        → RUNNING
RECOVERING → RECOVERY_FAILED           → FAILED

(any terminal) → RESET                 → IDLE
```

### Snapshot fields written by transitions

- `START`: sets `started_at` (`state_machine.py:387`); does NOT set
  `journal_run_id`.
- `STAGE_FLUSHED` (PAUSING → PAUSED): sets `finished_at`
  (`state_machine.py:402`).
- `RESUME`: clears `finished_at` and `error` (`state_machine.py:416-418`).
- `STAGE_COMPLETED`: appends to `stage_results`.

### Why `journal_run_id` is null for synthetic snapshots

`journal_run_id` is set by the **orchestrator** (not the state
machine) at the start of a real run. The recovery path
(`recovery.py:999-1012`) constructs the state machine and drives
`START → PAUSE → STAGE_FLUSHED` directly without going through the
orchestrator, so `journal_run_id` remains its initial `None`.

## The "ambiguous paused" smoking gun — `recovery.py:999-1012`

```python
sm = PipelineGroupStateMachine(
    project_id=pid,
    group=group,
    stages=[s.value for s in stages],
)
sm.add_guard(default_guard)

# Transition: IDLE -> RUNNING -> PAUSING -> PAUSED
sm.transition(Event.START)
sm.current_stage_index = resume
for i in range(resume):
    sm.stage_results[stages[i].value] = "completed"
sm.transition(Event.PAUSE)
sm.transition(Event.STAGE_FLUSHED)
```

Called from `hydrate_paused_runs_from_disk()` (`recovery.py:927-1025`)
during daemon startup. Detects partially-built groups on disk and
materializes a synthetic PAUSED snapshot to expose them to the UI.

The four transitions execute in the same microsecond, producing the
diagnostic fingerprint:

```
phase: paused
is_paused: true
started_at:    T
finished_at:   T + ~0.0001
journal_run_id: null
stage_results: { …existing-on-disk completed stages… }
```

This snapshot exposes the user to a "Resume / Cancel" UI. Resume
will re-run from `current_stage_index`. Cancel will mark
`CANCELLED` (terminal).

## Scheduler — `src/prep/services/pipeline/scheduler.py`

### Queue architecture

Per-node FIFO queue (`scheduler.py:218-219`):

```python
self._queues: Dict[str, Deque[QueueEntry]] = {}  # node_id → FIFO
```

There is **no global queue.** Multiple projects on different nodes
can run concurrently.

### Concurrent execution

- One project per slot per node (`scheduler.py:171`).
- Two projects on different nodes: parallel.
- Two projects on the same node: serialized via FIFO.
- Concurrent `POST /pipeline/all` on different projects: both run if
  capacity exists; no global lock taken.

### Dequeue policy (`scheduler.py:1141-1203`)

1. On slot release, scan queue for next acquirable entry
   (`scheduler.py:1188-1198`).
2. Priority projects appendleft (`scheduler.py:1230`); normal
   projects append (`scheduler.py:1237`).
3. Swarm-blocked projects skipped (`scheduler.py:1189-1192`).
4. Dequeued entry's `resume()` callback fired by orchestrator.

### Swarm window (`scheduler.py:865-954`)

- `open_swarm_window()` (`scheduler.py:865-921`): blocks other
  projects from acquiring on the same node.
- `is_blocked_by_swarm()` (`scheduler.py:981-990`): checked in
  `can_start()` and `acquire()`.
- Drain timeout (`scheduler.py:956-979`): force-cancel waiting
  projects after 10 minutes.

## Endpoints — `src/prep/api/routers/`

| Method | Path | Handler file:line | Description |
|---|---|---|---|
| GET | `/projects/{id}/pipeline/status` | `pipeline.py:420-959` | Full 15-stage status, scheduler status, crashed runs, barrier. Cached 3s, stale-while-refresh 30s. |
| POST | `/projects/{id}/pipeline/all` | `pipeline.py:359-380` | Chain Fast→Deep→Finalize. |
| POST | `/projects/{id}/pipeline/fast` | `pipeline.py:120-193` | Run Fast Sync only. `force_from_start=true` writes barrier scope=`sync`. |
| POST | `/projects/{id}/pipeline/deep` | `pipeline.py:196-268` | Run Deep Enrichment only. `force_from_start=true` writes barrier scope=`enrichment`. |
| POST | `/projects/{id}/pipeline/rebuild` | `pipeline.py:383-417` | Rebuild all 15. Writes barrier scope=`all` at `pipeline.py:403`. Cleared on stage 15 completion. |
| POST | `/projects/{id}/pipeline/pause` | `pipeline.py:1054-1097` | Pause running group. Triggers `STAGE_FLUSHED` after worker drains. |
| POST | `/projects/{id}/pipeline/resume` | `pipeline.py:1100-1120` | Resume paused group. Re-reads LLM config (model can swap). |
| POST | `/projects/{id}/pipeline/rebuild/stop` | (Phase 117) | Atomically cancel active rebuild + clear barrier. |
| DELETE | `/projects/{id}/pipeline/reset-barrier` | `pipeline.py:1173-1195` | Clear barrier manually. Invalidates status cache. |
| DELETE | `/projects/{id}/enrichment/full-reset` | `enrichment.py:1101-1119` | Reset stages 6-15. Wipes manifests + concept/antibody stores. Barrier reason=`enrichment_reset`. |
| DELETE | `/projects/{id}/finalize/full-reset` | `enrichment.py:1122-1138` | Reset stages 11-15. Barrier reason=`finalize_reset`. |
| DELETE | `/projects/{id}/index/destroy` | `enrichment.py:1141-1335` | Nuclear reset. All disk state, all stores, watcher stopped. Writes barrier. |
| GET | `/system/pipeline-queue` | `queue.py:29` | Global queue state (runs + scheduler dump). |
| POST | `/system/pipeline-queue/priority` | `queue.py` | Set project priority (queue-jump). |
| POST | `/system/pipeline-queue/purge-ghosts` | `queue.py` | Manual ghost-lock purge. |
| GET | `/compute/scheduler` | `compute.py:238-242` | Full scheduler diagnostic. |
| GET | `/compute/scheduler-status` | `settings.py:523-527` | Slim scheduler status (active slots, queues per node). |
| GET | `/pipeline/crashed` | `pipeline.py:1200-1209` | All crashed runs (journal-based). Optional `project_id` filter. |
| POST | `/pipeline/resume` | `pipeline.py:1212-1223` | Resume a crashed run from journal entry. |
| POST | `/pipeline/discard` | `pipeline.py:1226-1237` | Mark crashed run as discarded. |

### Reset barrier

- Path: `<project_idx_dir>/.reset_barrier`
- Format: `written_at\nreason\nscope`
- Read API: `recovery.py:127-166` returns dict with `written_at`,
  `reason`, `scope`, `age_seconds`.
- Active blocks: selfheal_group (`recovery.py:519`), per-stage
  backup restore (`recovery.py:418`).
- Cleared automatically: on scope-group completion
  (`recovery.py:176-188`).
- Cleared manually: `DELETE /pipeline/reset-barrier`.

### Self-heal — `recovery.py:489-694`

Avoids resurrecting after a reset:

1. Checks `reset_barrier_active()` first (`recovery.py:519`).
2. If active, returns `skipped_reset_barrier` — no resurrection paths
   considered.
3. Otherwise scans in priority order: golden checkpoint → run
   checkpoints → branch snapshot.
4. Writes `selfheal` stub provenance (`recovery.py:37-44`) with
   source label.

### Phase 117 scoped barriers

- `POST /pipeline/fast` + `force_from_start=true` → barrier
  `scope=sync` written at `pipeline.py:135-139`. Cleared at stage 5
  completion.
- `POST /pipeline/deep` + `force_from_start=true` → barrier
  `scope=enrichment` written at `pipeline.py:213-214`. Cleared at
  stage 10 completion.
- `POST /pipeline/rebuild` → barrier `scope=all` (covers full 15).
  Cleared at stage 15 completion.

## Observation primitives

```bash
# Live status (cached)
curl -s localhost:8400/projects/$PID/pipeline/status | jq

# Queue dump (all projects)
curl -s localhost:8400/system/pipeline-queue | jq

# Per-node scheduler diagnostic
curl -s localhost:8400/compute/scheduler | jq

# Disk barrier
cat <idx_dir>/.reset_barrier 2>/dev/null

# Journal (source of truth for crash recovery)
sqlite3 <data_dir>/prep_pipeline_journal.db \
  "SELECT run_id, project_id, group_name, stage_index, status \
   FROM pipeline_runs WHERE project_id='$PID' \
   ORDER BY started_at DESC LIMIT 5"
```

## Key invariants the harness must verify

1. After `DELETE /index/destroy`: no manifests, no `.checkpoints/`,
   no `.branch_snapshots/`, watcher stopped, all in-memory caches
   empty.
2. After `DELETE /enrichment/full-reset`: stages 6-15 manifests gone
   AND `concept_store` + `antibody_store` SQLite tables empty AND
   `_golden/` checkpoint dir wiped.
3. After scoped rebuild: barrier scope matches request scope; cleared
   on the correct stage's completion.
4. UI `data-stage-state` for any stage matches the API's reported
   state at every poll, with at most one tick of lag.
5. The queue dump for the target `project_id` matches the per-project
   `/pipeline/status` snapshot's barrier and phase fields.
