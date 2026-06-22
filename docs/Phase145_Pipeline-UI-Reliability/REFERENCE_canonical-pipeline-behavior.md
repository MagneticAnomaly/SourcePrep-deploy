# Phase 145 Reference — Canonical pipeline behavior (the source of truth Fable should align against)

**Status:** Living draft — 2026-06-18. **Subject to scrutiny like any other Phase 145 corpus doc.** Authored from the evidence in [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md) + [`EVIDENCE_findings-replayed-against-pure-s1.md`](EVIDENCE_findings-replayed-against-pure-s1.md). Where it documents what *is*, it cites code. Where it documents what *should be* (after re-centering), it labels the section "(target)."
**Purpose:** Give Fable (and any future human reviewer) one document that answers "what should every layer be in, for every user action and system event, at every state." This is the input the eventual Playwright invariant suite will assert against and the standard the re-centering proposal will be checked against.
**Companion:** [`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md) is the implementation proposal that *executes* the target rows of this reference.

---

## 0. How to read this document

- **§1–§3 describe what is.** State machine vocabulary, transitions, state stores. Cited to code.
- **§4 describes the canonical rule for "which store owns which question."** This is the architectural contract the re-centering proposal restores.
- **§5 is the (user action × current state) matrix.** What should happen, per layer, for every UI button click.
- **§6 is the (system event × current state) matrix.** Same for daemon-internal events (worker completion, watcher fire, scheduler capacity change, daemon restart).
- **§7 is the UI rendering contract.** Per-row state, per-group rollup, per-panel composition — formalized from README §4a and reconciled with this evidence.
- **§8 is the Playwright invariant catalog.** A list of assertions a future test suite can express, each tied back to a §5/§6/§7 cell.
- **§9 is the open question list.** Things the next scrutiny pass must answer before the proposal is marked ready.

---

## 1. The state machine vocabulary (what is, cited)

From `src/prep/services/pipeline/state_machine.py:94–110`:

```
PipelineState (10 states):
    IDLE         No run in progress
    QUEUED       Waiting for compute capacity (LLM slot)
    RUNNING      Actively executing stages
    PAUSING      Pause signal sent, waiting for stage to flush
    PAUSED       Stopped cleanly, checkpoint saved, can resume
    CANCELLING   Cancel signal sent, waiting for stage to stop
    CANCELLED    Cancelled by user
    COMPLETED    All stages finished successfully
    FAILED       A stage failed (actual error, not pause/cancel)
    RECOVERING   Crash detected, restoring from checkpoint
```

From `state_machine.py:112–125`:

```
Event (15 events):
    START
    ENQUEUE                  CAPACITY_AVAILABLE
    STAGE_COMPLETED          ALL_STAGES_DONE
    STAGE_FAILED
    PAUSE                    STAGE_FLUSHED       RESUME
    CANCEL                   STAGE_STOPPED
    CRASH_DETECTED           RECOVERY_SUCCEEDED  RECOVERY_FAILED
    RESET
```

From `state_machine.py:195–203`:

```
TERMINAL_STATES = {COMPLETED, FAILED, CANCELLED}
ACTIVE_STATES   = {RUNNING, PAUSING, PAUSED, CANCELLING, RECOVERING}
```

**Stage-result vocabulary** (the per-stage `stage_results: Dict[str, str]` dict S1 owns at `state_machine.py:268`):

```
"completed"           Worker ran to completion AND fired STAGE_COMPLETED
"failed"              Worker raised AND fired STAGE_FAILED
"user_stopped"        User-initiated pause/cancel (line 2735)
"restored_from_backup" Recovery stub (recovery.py:814)
```

Plus the implicit value `<absent>` (key never set) meaning "not yet reached."

**Gap surfaced by evidence:** S1's vocabulary has no `"skipped"` distinct from `"completed"`. The orchestrator's freshness skip fires `STAGE_COMPLETED` which writes `"completed"`. The skip reason is recorded separately in S3 (`pipeline_run_metadata.json`) via `mark_stage_skipped`. **The re-centering proposal must decide whether S1 should grow a `"skipped"` value or whether the UI should keep reading S3 for the skip nuance.**

---

## 2. The valid transition table (what is, cited)

From `state_machine.py:130–191`. Each `(state, event) → new_state` pair:

| From | Event | To |
|---|---|---|
| IDLE | START | RUNNING |
| IDLE | ENQUEUE | QUEUED |
| IDLE | CRASH_DETECTED | RECOVERING |
| QUEUED | CAPACITY_AVAILABLE | RUNNING |
| QUEUED | CANCEL | CANCELLED |
| QUEUED | STAGE_COMPLETED | RUNNING |
| QUEUED | ALL_STAGES_DONE | COMPLETED |
| QUEUED | STAGE_FAILED | FAILED |
| RUNNING | STAGE_COMPLETED | RUNNING *(advance stage)* |
| RUNNING | ALL_STAGES_DONE | COMPLETED |
| RUNNING | STAGE_FAILED | FAILED |
| RUNNING | PAUSE | PAUSING |
| RUNNING | ENQUEUE | QUEUED *(re-enqueue)* |
| RUNNING | CANCEL | CANCELLING |
| PAUSING | STAGE_FLUSHED | PAUSED |
| PAUSING | STAGE_FAILED | FAILED |
| PAUSING | CANCEL | CANCELLING |
| PAUSED | RESUME | RUNNING |
| PAUSED | ALL_STAGES_DONE | COMPLETED |
| PAUSED | CANCEL | CANCELLED |
| CANCELLING | STAGE_STOPPED | CANCELLED |
| RECOVERING | RECOVERY_SUCCEEDED | RUNNING |
| RECOVERING | RECOVERY_FAILED | FAILED |
| COMPLETED | RESET | IDLE |
| FAILED | RESET | IDLE |
| CANCELLED | RESET | IDLE |
| PAUSED | RESET | IDLE |
| QUEUED | RESET | IDLE |

Anything not in the table raises (per `state_machine.py:238+`). The transition table is the formal contract S1 exposes.

---

## 3. The state-store inventory (what is, cited)

Recap of [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md) §3. Nine independent representations:

| # | Store | Where | What it actually knows today |
|---|---|---|---|
| **S1** | `PipelineGroupStateMachine` | `state_machine.py` | Run-level state + per-stage terminal status (`stage_results`) |
| S2 | `BuildOrchestrator` slot phase | `build_orchestrator.py` | Per build-type slot phase (RUNNING/COMPLETED/FAILED) |
| S3 | `pipeline_run_metadata.json` | `.sourceprep/` | Durable per-run metadata, with `mark_stage_skipped` carrying the skip reason |
| S4 | `<stage>_manifest.json` | `.sourceprep/` | Per-stage provenance: model used, hashes, quality, output stats |
| S5 | `provenance.state` (derived) | `pipeline_provenance.py:160–205` | `match` / `drift` / `missing` / `recovered_soft` / `recovered_stub` — *model comparison only*, not output presence |
| S6 | Disk flags | `.sourceprep/` (`.reset_barrier`, `.guard_rejections.json`, soft-holds, `.checkpoints/`) | Recovery + integrity signals |
| S7 | Scheduler per-node load | `scheduler.py` | `ComputeSlot.active_stages`, `current_limit`, AIMD state |
| S8 | UI `compute*State` derivations | `GraphEnrichmentPipeline.tsx:505+` | Per-row state for the dashboard panels |
| S9 | `AutoRebuildWatcher` state | `watcher.py` | `_enabled`, `_state` ∈ {`disabled`, `idle`, `pending`} |

S1 was *supposed* to be the single owner per Phase 25B. Today it's one signal among nine. The proposal's job is to decide what each store *should* own, given that decoupling them entirely is impractical (S4 and S6 are durable / disk-backed for good reasons).

---

## 4. The canonical ownership rule (target — to be ratified by scrutiny)

The architectural rule the re-centering proposal restores:

> **For each pipeline question, exactly one store is canonical. Other stores are derived views or caches. When two stores disagree, the canonical one wins.**

The proposed ownership per question:

| Question | Canonical store | Other stores derive from / mirror it |
|---|---|---|
| Is the run active? | S1 (`state in ACTIVE_STATES`) | S2 slot phase mirrors |
| Which stage is current? | S1 (`current_stage_index`) | S2 slot's build_type derives |
| Did stage X finish? | S1 (`stage_results[X]` ∈ `{completed, failed, skipped}`) | S4 manifest existence is a downstream artifact |
| Why did stage X end? | S1 + S4 (S1 for terminal status, S4 for `quality`/error detail) | S3 metadata mirrors |
| What model was used? | S4 (`manifest.model`) | S5 `provenance.state` derives by comparing to current config |
| Is the on-disk artifact current? | S5 derived from S4 + current config + S6 reset_barrier | (purely derived) |
| Is a reset in progress? | S6 (`.reset_barrier`) | S1 stays in IDLE during reset; rehydrated after |
| Is a stage's output queued for compute? | S7 (`ComputeSlot.queued`) | S1 should mirror via `Event.ENQUEUE` → QUEUED |
| Is the watcher waiting on debounce? | S9 (`_state == "pending"`) | (not currently surfaced; should be exposed read-only via `/projects/<id>/watch/status`) |
| What ran in the last finished run? | S3 (`pipeline_run_metadata.json`) | Durable mirror of S1 at run-end |

**Key target invariant — the "compute*State must consult S1 first" rule:**

> The UI's per-row state derivation MUST consult `stage_results[X]` from S1 first. Cold-state checks (count gates, manifest existence) are fallback for stages S1 has no opinion on (`<absent>` in `stage_results`).

This is the smallest intervention that closes 6 of the open findings per the IQ2 analysis.

---

## 5. (User action × current state) matrix (target)

For each user action a UI exposes, the table records:
- What event fires on S1
- What other stores are written (and by whom)
- What the UI should render
- What it must NOT render

States across the top are *group-level* (`fast_sync` / `deep_enrichment` / `finalize` are each their own S1 state machine).

### 5.1 Click **Run** on a group

| Current state | Event | Other writes | UI renders | UI must NOT render |
|---|---|---|---|---|
| IDLE | `START` if capacity, else `ENQUEUE` then `START` later | S2 slot acquire; S3 metadata created; S6 barrier check; S7 acquire (or enqueue) | "Started" toast; group goes Running; current stage gets spinner | Silent — nothing visible |
| QUEUED | (already queued; no-op) | (none) | "Already queued behind X" toast | Re-enqueue or duplicate-queue badge |
| RUNNING | (no-op) | (none) | "Already running" toast | Second spinner / second-run badge |
| PAUSED | `RESUME` | S6 clears pause marker | "Resumed" toast; group returns to Running | "Started fresh" toast |
| COMPLETED | (decision: `RESET` then `START` OR PIPELINE_UP_TO_DATE 409) | If RESET-then-START: full event chain | Per §4 ownership rule: if S5 says match AND S1 says completed, return 409 with the existing toast text and the row should render `complete`. Today this is inconsistent (§2l) | Conflicting toast vs row state (the §2l symptom) |
| FAILED | `RESET` then `START` (force_from_start) | S6 barrier cleared (Thread B target) | "Restarting after failure" toast; row goes from red to spinner | Silent failure surface |
| CANCELLED | `RESET` then `START` | (same as FAILED) | "Restarting after cancel" toast | "Already cancelled" without ability to restart |
| RECOVERING | (rejected; no-op) | (none) | "Recovery in progress" toast | Allow start-during-recovery |

### 5.2 Click **Pause**

| Current state | Event | Other writes | UI renders |
|---|---|---|---|
| RUNNING | `PAUSE` | S6 pause marker; S4 checkpoint | Pause icon, "Pausing…" |
| PAUSING | (no-op) | (none) | Continue showing "Pausing…" |
| PAUSED | (no-op) | (none) | "Already paused" toast |
| QUEUED | `CANCEL` (treated as remove from queue) | S7 remove from queue | Confirm "Remove from queue?" |
| Other | (rejected) | (none) | "Cannot pause" toast |

### 5.3 Click **Cancel** (the X button on the queue widget)

| Current state | Event | Other writes | UI renders |
|---|---|---|---|
| QUEUED | `CANCEL` | S7 dequeue | "Cancelled" toast; row leaves queue |
| RUNNING | `CANCEL` | S7 release on cancellation completion | Pause icon, "Cancelling…" then "Cancelled" |
| PAUSING / PAUSED | `CANCEL` | S7 release | "Cancelled from pause" |
| COMPLETED / FAILED / CANCELLED | (no-op) | (none) | "Already in terminal state" toast |

### 5.4 Click **Force Reset**

| Current state | Event | Other writes | UI renders |
|---|---|---|---|
| Any | `RESET` | S6 `.reset_barrier` written; manifests wiped per scope; S6 cleared at boundary (per [`PROPOSAL_threads-B-and-C-v2`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md) Thread B target) | Confirm dialog → "Reset queued; will rebuild from scratch" toast | Silent — user can't tell barrier wrote |

### 5.5 Click **Update** (Graph Scope card)

| Current state of fast_sync group | Event | UI renders |
|---|---|---|
| IDLE + untraced files exist | `START` (incremental) | "Update started" + spinner |
| IDLE + no untraced files | (no-op) | "Already current" toast |
| RUNNING / QUEUED | (no-op or `ENQUEUE` per current rules) | Per §5.1 |
| (Today: silent stuck "Updating…" — §2p) | — | Per the target rules, never silent |

### 5.6 Toggle **Auto ↔ Manual** on a group header

| Side effect | Notes |
|---|---|
| Update `auto_config.<group>` in project config | Pure config write; does not fire S1 events |
| Watcher (S9) consults `auto_config` on its next debounce fire | Asymmetric: switching to Auto doesn't fire a rebuild immediately |
| UI re-renders the toggle | No row-state changes |

### 5.7 Toggle **Star** (boost)

| Side effect |
|---|
| Persist `priority_level == "boost"` in project config |
| Scheduler (S7) reads new value on next allocation decision |
| Does NOT fire S1 events |
| UI re-renders star icon |

### 5.8 Click **Stop** on the active run from the queue widget

Equivalent to §5.3 Cancel.

---

## 6. (System event × current state) matrix (target)

Daemon-internal events. The UI is a passive observer that re-renders from `/events` SSE or from polled status.

### 6.1 Worker finishes a stage successfully

| Current state | Event fired by orchestrator | Result |
|---|---|---|
| RUNNING with `current_stage_index < len(stages)-1` | `STAGE_COMPLETED` | `stage_results[current_stage] = "completed"`; `current_stage_index += 1`; state stays RUNNING; next stage starts |
| RUNNING with `current_stage_index == len(stages)-1` | `STAGE_COMPLETED` then `ALL_STAGES_DONE` | state → COMPLETED; `_finalize_run_metadata` writes S3; cleanup hook runs (per [`PROPOSAL_threads-B-and-C-v2`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md) Thread B); maybe_clear_scoped_barrier called |
| Other states | (would not be called — event rejected) | (n/a) |

### 6.2 Worker raises during a stage

| Current state | Event fired by orchestrator | Result |
|---|---|---|
| RUNNING | `STAGE_FAILED` | `stage_results[current_stage] = "failed"`; state → FAILED; cleanup hook runs (must include barrier-clear per Thread B target) |
| PAUSING | `STAGE_FAILED` (line 179 transition table) | state → FAILED |
| Any other ACTIVE state | (depends on event path) | (must always release scheduler slot; must always surface to UI) |

### 6.3 Freshness check skips a stage

| Current state | Today | Target |
|---|---|---|
| RUNNING | `STAGE_COMPLETED` fired → `stage_results[X] = "completed"`; S3 `mark_stage_skipped` separately records `"skipped"` with reason | Either: (a) S1 grows `"skipped"` value and skip reason is stored on S1; OR (b) UI reads S3 for skip context when S1 says `"completed"` AND S3 says `"skipped"` |

The proposal must pick (a) or (b). (a) is cleaner but a vocabulary change to S1; (b) preserves backward compatibility but keeps the dual-source duplication.

### 6.4 Scheduler `capacity_changed` broadcast (e.g., on swarm window open/close)

| Current state | Target |
|---|---|
| RUNNING | Subscribers (worker semaphores) resize. **NEVER cancel work in flight.** S1 stays RUNNING with no event fire. |
| QUEUED | If `new_budget > 0`, `CAPACITY_AVAILABLE` fires → state → RUNNING |
| QUEUED | If `new_budget == 0`, stay QUEUED |
| (Today: §2k's work loss suggests capacity_changed sometimes results in cancellation rather than resize — the target is "never cancel from a capacity change") | — |

### 6.5 Watcher fires a debounce trigger

| Current state | Target |
|---|---|
| IDLE + auto_config enabled + no barrier | `START` fires; same as §5.1 |
| IDLE + auto_config enabled + reset_barrier active | Skip with `selfheal_skipped` event surfaced to S9's debug log AND surfaced through `/projects/<id>/watch/status` as `last_decision: "barrier_active"` |
| Any non-IDLE | Skip with `selfheal_skipped` event surfaced as `last_decision: "already_running"` |
| Watcher disabled | (no fire) |

**Target invariant — watcher visibility:** every watcher fire decision (fire / skip-because-X / debounce-coalesced) must be queryable via `/projects/<id>/watch/status` with the last 10 decisions + timestamps. (Today none are surfaced — that's §2q.)

### 6.6 Daemon restart with paused/in-flight runs

| Disk state | Target |
|---|---|
| `pipeline_run_metadata.json` present with `status: "paused"` + `.pause_marker` flag | `hydrate_paused_runs_from_disk` reconstructs S1 in PAUSED state. **Must cross-check S4 manifests** (per evidence §8 — today the cross-check is missing). If S3 says paused-at-stage-5 but S4 shows manifests 1–3 missing, the cross-check should refuse hydration and either route to RECOVERING or write a `.startup_hydration_error` flag visible in the UI. |
| `pipeline_run_metadata.json` present with `status: "running"` (no clean shutdown) | `auto_recover_stale_pipelines` decides whether to auto-trigger a new run. **Must not silently mark a stage as restored if the actual data file is absent** — current bug source for §2o. |
| No metadata or clean shutdown marker | No recovery action; S1 starts IDLE on first request. |

### 6.7 Crash detected mid-run

| Current state | Target |
|---|---|
| RUNNING | `CRASH_DETECTED` → RECOVERING; orchestrator restores from S4 checkpoint; on success `RECOVERY_SUCCEEDED` → RUNNING; on failure `RECOVERY_FAILED` → FAILED. UI shows "Recovering…" badge throughout. |

---

## 7. UI rendering contract (target — formalized from README §4a)

Per-row state derivation, post-re-centering:

```
row_state(stage_X, run_state_machine S1, status_payload):
    # T1 (Thread T1 in proposal): consult S1 first
    if stage_X in S1.stage_results:
        match S1.stage_results[stage_X]:
            "completed"    -> 'complete'
            "failed"       -> 'failed'
            "skipped"      -> 'skipped'         (after T1 vocabulary decision)
            "user_stopped" -> 'paused'
            "restored_from_backup" -> 'recovering'
    # S1 has no opinion on this stage yet:
    if S1.state in ACTIVE_STATES and S1.current_stage == stage_X:
        return 'running'
    if S1.state in ACTIVE_STATES and stage_X.index < S1.current_stage_index:
        return 'complete'   # downstream of current — implicitly done
    if S1.state in ACTIVE_STATES and stage_X.index > S1.current_stage_index:
        return 'not_yet_reached'
    if S1.state == IDLE:
        # Fall back to cold-state checks against S4 manifests
        return cold_state_from_S4(stage_X, status_payload)
    if S1.state == QUEUED:
        return 'queued'
    if S1.state == PAUSED:
        return 'paused'
    # ... etc.
```

### 7.1 Per-row state table (formalized)

| State | Trigger | Row should show | Row must NOT show |
|---|---|---|---|
| `not_built` | S1 IDLE AND no manifest | Label + "Not built" | Spinner, 0% bar, "Pending" |
| `not_yet_reached` | S1 RUNNING, this stage's index > current_stage_index | Dim label, no spinner | Spinner, % bar (this stage hasn't started) |
| `running` | S1 RUNNING AND current_stage == this | Spinner + label + live % from S2 slot progress | Stale stat from prior run |
| `complete` | S1 `stage_results[X] == "completed"` OR (idle AND manifest exists AND fresh) | Green check + label + last-run stat + age chip | Spinner |
| `complete_stale` | S5 `provenance.state == "drift"` | Green check + amber stale chip | Just a check (no chip) |
| `skipped` | S1 `stage_results[X] == "skipped"` (post-T1) OR (S1 says "completed" + S3 says skipped) | Grey check + skip-reason tooltip | "Running 0%" forever |
| `failed` | S1 `stage_results[X] == "failed"` | Red icon + error tooltip | Silent success |
| `paused` | S1 PAUSED OR `stage_results[X] == "user_stopped"` | Pause icon + "Paused at stage N" | Spinner |
| `queued` | S1 QUEUED OR S7 says this project's stage is in queue | Hourglass + "Queued behind <X>" | Empty (the §2p, §2f symptom) |
| `recovering` | S1 RECOVERING OR `stage_results[X] == "restored_from_backup"` | Spinner + "Self-healing…" | Plain "Running" |
| `disabled` | Stage configured off (auto_config or manual disable) | Greyed label + "Disabled" | Spinner, % bar |

### 7.2 Group rollup (lowest-priority terminal state across stages — unchanged from README §4b, restated)

| Group state | When |
|---|---|
| `complete` | Every stage `complete` or `skipped` |
| `complete_stale` | Every stage `complete`/`skipped`, ≥1 stage's inputs newer |
| `running` | ≥1 stage `running` or `queued` |
| `failed` | ≥1 stage `failed` |
| `paused` | ≥1 stage `paused` |
| `recovering` | ≥1 stage `recovering` |
| `not_built` | ≥1 stage `not_built` AND none `running`/`failed`/`recovering` |

### 7.3 UI invariants the rendering contract enforces

The following must hold for any single SSE snapshot or polled status response:

1. **Exactly one row per group renders `running`.** Per §6.1: only `current_stage` is running. Closes §2r entirely.
2. **No row renders `running` with stale metadata** ("yesterday" / "1384 chunks embedded" while spinning).
3. **No row renders `complete` while S1 says the stage hasn't been reached yet** (`stage_X.index > current_stage_index`). Closes §2r (downstream fake-complete) and the upstream-spinner half of it.
4. **A `queued` group must appear somewhere visible to the user.** Either in the queue widget OR with a per-row hourglass on its first stage. Closes §2f and §2p UI sides.
5. **Force Reset's confirmation toast must indicate the barrier was written.** Closes the silent-barrier half of §2l Thread B.
6. **Any terminal state (`failed`/`cancelled`/`completed`) must persist across page refresh.** Closes the "refresh fixes nothing" anti-pattern.
7. **A status field's source store must be discoverable** — either by naming convention (`stages.<stage>.from_S1` vs `from_S4`) OR by documenting per-field provenance in the API contract.

---

## 8. Playwright invariant catalog (for Fable to drive eventually)

Each invariant is a single assertion the test suite can express against a known-state daemon. Citations point to the §5/§6/§7 cell that justifies the invariant.

| # | Invariant | From | Closes finding(s) |
|---|---|---|---|
| **I1** | For any group at any moment, exactly one row in that group has `data-state="running"`. | §7.3 #1 | §2r |
| **I2** | No row with `data-state="running"` also displays a `last_run` chip from a prior run timestamp (the chip is hidden during run). | §7.3 #2 | §2r |
| **I3** | No row at index > `current_stage_index` has `data-state="complete"`. | §7.3 #3 | §2r |
| **I4** | When `/system/pipeline-queue` shows a project queued AND `/projects/<id>/pipeline/status.<group>.phase == "queued"`, the sidebar queue widget contains the project. | §7.3 #4 | §2f, §2p |
| **I5** | After Force Reset, `.reset_barrier` is on disk AND the toast text contains "Reset queued" within 500 ms. | §7.3 #5 | §2l Thread B |
| **I6** | After a failed terminal group, `.reset_barrier` is NOT on disk (per Thread B fix). | §6.2 | §2l Thread B |
| **I7** | After a fast_sync run that processed N files, the Knowledge Embedding row's stat reads exactly N chunks within 2 s of `STAGE_COMPLETED`. | §7 reading contract | §2j |
| **I8** | The Update button click on a group with no untraced files results in a "Already current" toast within 500 ms (not silent). | §5.5 | §2p |
| **I9** | After 60 s of `auto_config.fastSync == true` AND ≥1 untraced file with mtime > debounce-window, either `/projects/<id>/pipeline/status.fast_sync.is_active == true` OR `/projects/<id>/watch/status.last_decision` was emitted explaining why. | §6.5 | §2q |
| **I10** | `compute*State` invocation against any `(S1, status_payload)` pair always produces the row state defined in §7.1. | §7.1 | §2a, §2l Thread A, §2n |
| **I11** | After a stage worker raises, the row's `data-state == "failed"` AND the error text contains the worker's exception class within 500 ms (no silent failure). | §6.2 | §2k partially (work loss surface) |
| **I12** | After a `capacity_changed` event with `new_budget < current_in_flight`, in-flight count drops to `new_budget` via natural completion only — `run.state` stays in its current state, no `STAGE_FAILED` fires. | §6.4 | §2k |

These twelve cover most of the UI-visible Phase 145 findings. Adding more would target backend-only invariants (resume detector correctness, watcher decisions, swarm window semantics) that don't need Playwright but could be pytest-asserted from the daemon directly.

---

## 9. Open questions for the scrutiny pass (NEEDS user/Fable input)

These must be answered before this reference doc is marked "ratified" and before the proposal is marked "ready":

### OQ1 — S1 vocabulary: should `"skipped"` be a first-class `stage_results` value?

Two options. **Option A** grows S1 to own the skip distinction — cleanest single-source-of-truth model, but a vocabulary breaking change (anything that reads `stage_results` must handle the new value). **Option B** leaves S1 conflating skip and completion and the UI reads S3 for skip context — preserves compatibility, perpetuates duplication. **Recommended:** Option A, but verify nothing critical reads `stage_results == "completed"` as a strict equality without also accepting `"skipped"`.

### OQ2 — Resume detector: should it read S1?

Today the resume detector ignores S1 entirely. Should it cross-check S1 against S4 (its current source) and refuse to mark a stage COMPLETE if S1 disagrees? This is a layering question — making S1 a *reader-side authority* for resume could prevent §2o, but it also turns S1 into a dependency for a code path that currently has no S1 dependency. **Recommended for scrutiny:** investigate whether the resume detector should *consult* S1 as a sanity check OR whether S1 should *be derived from* resume detector output (the opposite direction).

### OQ3 — Watcher (S9) visibility: surfaced via API or also reflected in S1?

Today S9 is invisible to the UI. Two surfacing options. **Option A** expose S9 through `/projects/<id>/watch/status` only — UI consumes the new endpoint, S1 unchanged. **Option B** make watcher fires/skips emit S1 events (e.g., a new `Event.WATCHER_SKIPPED`) so they appear in S1's transition history. **Recommended:** Option A. Watcher is an *initiator*, not part of the run lifecycle; folding it into S1 inflates the state machine.

### OQ4 — Scheduler (S7) ↔ S1: how tight?

`capacity_changed` events today don't fire S1 events. Should they (e.g., `CAPACITY_AVAILABLE` already exists; add `CAPACITY_RESCINDED`)? Or should they remain entirely separate, with S1 just exposing the scheduler's view as a read-only field in `to_dict()`? **Recommended for scrutiny:** keep S1 and S7 separate; have S7's `capacity_changed` resize semaphores directly and never cancel runs; surface S7's per-project status through the existing `scheduler` block in the API response.

### OQ5 — Status endpoint: per-field source labeling?

Today `/projects/<id>/pipeline/status` silently merges S1 + S4 + S5 + S7 + S6 into the same response. Should each field be tagged with its source store (e.g., `{"phase": "running", "_source": "S1"}`)? Useful for debugging + lets the UI pick deliberately. **Recommended:** add a `_provenance` sub-object to the response listing source per field; UI can ignore initially, debugging tools immediately benefit.

### OQ6 — Daemon startup cross-check: should S3↔S4 mismatch refuse hydration?

Today S1 hydrates from S3 even if S4 contradicts. Should hydration refuse to proceed if cross-check fails, leaving the project in a visible "recovery_needed" state until the user clicks Force Reset? This is the architectural question behind §2o. **Recommended for scrutiny:** YES with a soft fallback (refuse → set state to RECOVERING → auto-trigger a clean rebuild OR surface to user).

### OQ7 — When this reference doc is wrong, who updates it?

The doc encodes the target behavior. If a future Phase introduces a new state or a new event, this doc must update. Should the project's `CLAUDE.md` reference it as a "must-update when changing the pipeline" file?

### OQ8 — Playwright invariants: which run in CI vs which are exploratory?

The 12 invariants in §8 are aspirational. Some are stable contracts (I1, I2, I3 — purely UI rules) and could run as CI gates. Others (I9 — depends on FSEvents timing) may be flaky. The scrutiny pass should triage: which 6–8 are CI-grade vs which are diagnostic.

---

## 10. Cross-references

- [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md) — the hypothesis.
- [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md) — what is.
- [`EVIDENCE_findings-replayed-against-pure-s1.md`](EVIDENCE_findings-replayed-against-pure-s1.md) — what would change if T1 lands.
- [`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md) — the implementation plan that *executes* the target rows of this reference.
- All open Phase 145 findings: README §2a–§2r.
- Prior precedent of "extract canonical registry": prep concept "Canonical registry extracted to break triple-source duplication after audit finding" (`packages/ui/src/config/mcpSetup.ts`).
- Phase 25B state machine introduction: `src/prep/services/pipeline/state_machine.py` (docstring).
- Phase 118 U2 prior re-centering: `src/prep/services/pipeline/orchestrator.py:2713–2740`.
- Phase 91 Resource Allocation contract: `docs/Phase91_QueueRefinement/01_Resource_Allocation_Design.md`.
- Phase 117 scoped barriers: documented in `CLAUDE.md`.
- Phase 134 changeset-driven pipeline (precedent for ~600-line cleanup of per-stage staleness): prep concept "Changeset-driven pipeline eliminates per-stage staleness derivation."
