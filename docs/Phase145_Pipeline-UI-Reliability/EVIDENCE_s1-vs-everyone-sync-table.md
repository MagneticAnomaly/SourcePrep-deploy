# Phase 145 Evidence — S1 (PipelineGroupStateMachine) sync coverage vs the other eight state stores

**Status:** Static evidence capture — 2026-06-18.
**Source:** Direct code reading (Bash/Read/Grep) by a dedicated research agent over the Phase 25B state machine and every system that interacts with it. Every claim is cited file:line. **No code changes from this pass.**
**Companion:** Answers IQ1 of [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md).

---

## 0. Headline finding (read this first)

**The Phase 25B state machine (S1) is no longer the canonical signal for "what is the pipeline doing."** Empirically:

- **15** orchestrator-initiated `run.transition(Event.*)` callsites, but **4 distinct write paths bypass `Event.*` entirely** and mutate `stage_results` directly.
- **0** of the UI's `compute*State` functions read `run.stage_results` from S1 — they all read S4 manifest-derived fields instead.
- **0** references to `run.state` or `run.stage_results` in `scheduler.py` (S7) or `watcher.py` (S9). Both subsystems are entirely independent.
- The `/projects/{id}/pipeline/status` endpoint **silently merges** S1 fields with S4 manifest fields into the same response payload, hiding the duplication.
- Daemon startup recovery **trusts S3 (metadata JSON) blindly** when rehydrating S1 — if S3 and S4 disagree, S1 is set to S3's resume point and the mismatch is left for the resume detector to find at run-time.

Each subsection below cites the evidence for one of these claims.

---

## 1. S1 writer coverage — every `run.transition(Event.*)` callsite

15 callsites total, all in `src/prep/services/pipeline/orchestrator.py` and `src/prep/services/pipeline/recovery.py`. None outside `services/pipeline/`. The table below lists each callsite + which other stores (S2 BuildPhase, S3 metadata, S4 manifests, S6 disk flags, S7 scheduler) get written *in the same code path*.

### 1.1 orchestrator.py

| Line | Event | Context | S2 | S3 | S4 | S6 | S7 |
|---:|---|---|:--:|:--:|:--:|:--:|:--:|
| 1509 | `RESUME` | User-initiated PAUSED→RUNNING | — | — | — | clears pause marker | release lock |
| 1596 | `STAGE_FAILED` | Force-reset: worker crashed (slot idle >600s) | slot.phase read | — | — | — | — |
| 1928 | `START` | Pipeline run init; guards check project active | slot acquired | metadata created | — | barrier written | `acquire()` |
| 2044 | `ALL_STAGES_DONE` | All stages done (current_stage_index ≥ len) | — | `_finalize_run_metadata` | — | — | release |
| 2339 | `ENQUEUE` | No compute capacity on node | slot status read | — | — | — | `enqueue()` |
| 2607 | `STAGE_COMPLETED` | Worker finished; BuildPhase=COMPLETED | slot.phase read | `write_stage_manifest_and_update_run` | provenance written | — | — |
| 2673 | `STAGE_FAILED` | **Write guard blocked** (S4 integrity failure) | — | `_journal_run_failed` | integrity checked | — | release |
| 2737 | `STAGE_FAILED` | Worker error (Phase 118 U2 non-user) | slot.error read | `_journal_stage_failed` | — | — | release |
| 2836 | `STAGE_FAILED` | Post-structural sanity (0 nodes, files exist) | — | `pfl.end_run()` | manifest validated | — | — |
| 2871 | `STAGE_FAILED` | `_advance_pipeline` exception handler | — | `pfl.end_run()` | — | — | — |
| 2913 | `CANCEL` | User cancel from RUNNING/PAUSED | `orchestrator.cancel()` | `_journal_run_cancelled` | — | clear pause marker | release |
| 2923 | `STAGE_STOPPED` | Complete CANCEL (CANCELLING→CANCELLED) | — | — | — | — | — |
| 3437 | `PAUSE` | User pause; RUNNING→PAUSING | `orchestrator.pause()` | `write_user_pause_marker` | checkpoint created | pause marker | release |
| 3486 | `STAGE_FLUSHED` | Complete PAUSE (PAUSING→PAUSED) | slot active checked | pause marker | checkpoint | pause marker | release |
| 3760 | `CAPACITY_AVAILABLE` | Scheduler released slot; QUEUED→RUNNING | — | — | — | — | `release()` |
| 3783 | `ENQUEUE` | Re-enqueue after advance failure | — | — | — | — | `enqueue()` |

### 1.2 recovery.py

| Line | Event | Context |
|---:|---|---|
| 1475 | `START` | Hydrate paused run from disk; create new SM |
| 1485 | `PAUSE` | Auto-pause for hydrated PAUSED state |
| 1486 | `STAGE_FLUSHED` | Complete recovery pause |

### 1.3 Notable single-finding

**`Event.STAGE_FAILED` is fired from FIVE distinct callsites** (orch:1596, 2673, 2737, 2836, 2871) covering different failure modes (worker crash, write guard, worker error, post-structural sanity, exception). They share the state machine transition but **not the cleanup path** — for example, only line 2737 reaches the `_on_build_transition` FAILED branch that the parked [`PROPOSAL_threads-B-and-C-v1`](PROPOSAL_threads-B-and-C-v1-barrier-and-rollup.md) tried to fix. This is the empirical confirmation of v1's defect D3.

---

## 2. `stage_results[...]` writer divergences — S1 doesn't actually own it

Phase 25B's docstring says S1 owns `stage_results`. In practice, **4 of the 6 writers bypass the `Event.*` system**:

| File:Line | Writer | State Assigned | Event Fired? | Sync? |
|---|---|---|:--:|:--:|
| `state_machine.py:395` | `transition(Event.STAGE_COMPLETED)` | `"completed"` | YES | ✓ |
| `state_machine.py:407` | `transition(Event.STAGE_FAILED)` | `"failed"` | YES | ✓ |
| `orchestrator.py:2735` | `_on_build_transition` (user-initiated stop branch) | `"user_stopped"` | **NO** | **DIVERGENT** |
| `orchestrator.py:2742` | `_on_build_transition` (overwrites with detail string) | `"failed: {slot.error}"` | yes (line 2737) | ⚠ overwrites canonical value |
| `orchestrator.py:1951` | `start_run` (resume path, prior stages) | `"completed"` for each prior stage | **NO** | **DIVERGENT** |
| `recovery.py:814` | `auto_recover_stale_pipelines` | `"restored_from_backup"` | **NO** | **DIVERGENT** |
| `recovery.py:1484` | `hydrate_paused_runs_from_disk` (prior stages) | `"completed"` for each prior stage | **NO** | **DIVERGENT** |

**Implication:** S1's `stage_results` is touched by direct dict mutation as often as by state-machine events. Any future code that subscribes to `_on_transition` callbacks to detect stage completion will miss these four paths. The docstring claim "the state machine OWNS `stage_results`" is aspirational, not actual.

---

## 3. Resume detector & freshness checks — never read S1

`ResumeStrategy.detect_resume_point` (`src/prep/services/pipeline/resume.py:85–400+`) is consulted at the start of every run and every selfheal pass to decide what to skip. Its sources:

| Source | Lines | What it reads |
|---|---|---|
| S4 manifests | 134–190 | `provenance_exists`, `read_provenance`, `finished_at` |
| S6 reset_barrier | 124–130, 215–239 | `read_reset_barrier`, barrier_floor for rebuild detection |
| S3 metadata | 293–319 | `is_stage_pending_in_interrupted_run` |
| S4 output files | 270–290 | `STAGE_OUTPUT_FILE` existence + size checks |
| **S1** | — | **Never reads `run.stage_results` or `run.state`** |

Freshness checks in `orchestrator.py:2300+` delegate to `ResumeStrategy.should_skip_stage_freshness`, also S4-only. `_integrity_check_after_stage` reads S4 manifest validity. `_sync_downstream_manifest_mtimes` touches S4 manifests to cascade staleness.

**Critical:** A stage marked `"completed"` in S1's `stage_results` but missing from S4 will trigger a re-run. A stage marked incomplete in S3 (`pending`) but present in S4 (stale manifest) will be re-run even if S1 says completed. The resume detector treats S1 as if it doesn't exist.

This is the direct cause of [`FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md`](FINDING_incremental-run-shows-50pct-work-after-interrupted-rebuild.md) (§2o) and the upstream root cause behind [`PROPOSAL_threads-B-and-C-v2`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md) Thread C.

---

## 4. Status endpoint — silent multi-source merge

`/projects/{id}/pipeline/status` handler in `src/prep/api/routers/pipeline.py:432–960` composes the response payload from at least four stores:

| Response field | Source store | Code |
|---|:--:|---|
| `fast_sync.phase`, `.current_stage`, `.current_stage_index`, `.started_at`, `.finished_at`, `.error` | S1 | `run.to_dict()` → `state_machine.py:462–480` |
| `fast_sync.stage_results` | S1 | `run.to_dict()["stage_results"]` → `state_machine.py:475` |
| `stages.<stage>.exists`, `.enabled`, `.counts` | S4 | manifest reads, pipeline.py:598–640 |
| `stages.<stage>.running` | S2 or S1 snapshots | slot_progress (BuildSlot) OR stage_snapshots — pipeline.py:843–872 |
| `stages.<stage>.progress_current`, `.progress_total` | S2 or S1 | slot_progress OR stage_snapshots — pipeline.py:845–867 |
| `stages.<stage>.provenance.state` | S5 (derived from S4 + current config) | `compute_stage_provenance` — pipeline.py:944 |
| `scheduler.*` | S7 | `pipeline_scheduler.status()` |
| `barrier.*` | S6 | `read_reset_barrier` |

**The same payload contains S1's `stage_results["enrichment"] = "completed"` next to `stages.enrichment.exists = false` (S4) next to `stages.enrichment.provenance.state = "match"` (S5).** When these disagree, the client sees all three values and has no contract telling it which to trust. The UI has chosen S4-derived fields as its primary signal (see §5).

---

## 5. UI `compute*State` source map — **0 of 6 functions consult S1**

`packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505+`. Every per-stage state-deriver:

| Function | Line | Inputs consulted | Reads S1's `stage_results`? |
|---|---:|---|:--:|
| `computeEpistemicState` | 505 | `trace.exists`, `aug.enabled`, `ep.enabled`, `ep.enriched_nodes`, `ep.avg_confidence`, `running`, SSE flags | **NO** |
| `computeModuleState` | 535 | `ep.enriched_nodes`, `mod.enabled`, `mod.module_count`, `running`, SSE flags | **NO** |
| `computeAtlasState` | 554 | `ep`, `mod`, `atlas.exists`, `atlas.stale`, `deep.total_scored`, `running` | **NO** |
| `computeDeepeningState` | 580 | `ep`, `deep.total_scored`, `deep.settled_ratio`, `running` | **NO** |
| `computeFastKnowledgeState` | 613 | `trace.exists`, `know.enabled`, `know.chunks_embedded`, `building`, `aug` | **NO** |
| `computeDeepKnowledgeState` | 647 | `ep.enriched_nodes`, `ep.running`, `mod`, `deep`, `know.deep_chunks_embedded`, `building` | **NO** |

**Yes/no question per finding's IQ2 prompt: does any compute*State function read S1? Answer: NO. None.**

Every helper reads S4-derived fields (epistemic_status, module_status, atlas_status, deepening_status, knowledge_status) which the status endpoint computes from the on-disk manifests, plus the per-stage `running` boolean (from S2's slot_progress when active, S1's stage_snapshot when idle).

The state machine's `stage_results` field — the dict Phase 25B specifically said S1 owned — is **never** read by the UI for row-state derivation. It travels in the status payload (per §4 above) and gets ignored.

---

## 6. Scheduler (S7) ↔ S1 — **fully independent**

`src/prep/services/pipeline/scheduler.py`. Searched for any reference to `run.state`, `run.transition`, `run.stage_results`, `PipelineGroupStateMachine`, `PipelineState`, `Event.`:

| Component | References S1? |
|---|:--:|
| `PipelineScheduler.acquire()` | NO |
| `PipelineScheduler.release()` | NO |
| `PipelineScheduler.enqueue()` | NO |
| `PipelineScheduler.can_start()` | NO |
| `PipelineScheduler.dequeue_next()` | NO |
| `_weighted_share`, AIMD step methods | NO |
| `capacity_changed` event emit | NO (event consumers exist; producer doesn't read S1) |

The scheduler operates on S7 (`ComputeSlot`, `active_stages`, `current_limit`) without ever consulting S1. The integration loop is one-way: **orchestrator → scheduler** via `acquire/release/enqueue` calls. The scheduler is not aware which `PipelineState` a run is in — only which slot is held.

This is the structural reason [`FINDING_concurrency-undershoot-and-cross-project-work-loss.md`](FINDING_concurrency-undershoot-and-cross-project-work-loss.md) (§2k) and [`FINDING_two-project-incremental-blocked-during-swarm.md`](FINDING_two-project-incremental-blocked-during-swarm.md) (§2p) can both exist: when the scheduler decides allocation, it has no insight into S1; when the UI surfaces queue state, it reads S7's view which doesn't know S1's view, and they drift.

---

## 7. Watcher (S9) ↔ S1 — also fully independent

`src/prep/core/watcher.py`. Same search: zero references to `run.state`, `run.transition`, `run.stage_results`.

| Component | References S1? |
|---|:--:|
| `AutoRebuildWatcher.__init__` | NO (takes callbacks `on_trigger_build`, `is_building`) |
| `AutoRebuildWatcher.start/stop` | NO |
| `_on_debounce_fire` | NO (calls `on_trigger_build` callback) |
| `_on_coverage_check` | NO (reads disk file counts) |
| `_check_incomplete_deep_enrichment` | NO (reads manifests + mtimes) |

The watcher owns its own state — `_enabled`, `_state` ("disabled" / "idle" / "pending") — entirely in-memory and disconnected from S1. The integration point is the `is_building` callback the watcher receives at construction time, which the orchestrator implements by checking S1 state. **The watcher does NOT read S1 before firing a debounce trigger.**

This is the structural reason [`FINDING_auto-incremental-never-fired-despite-stale-files.md`](FINDING_auto-incremental-never-fired-despite-stale-files.md) (§2q) has no UI signal: the watcher's state is not in the status endpoint, not in S1, not in any panel. It can only be queried via `/projects/{id}/watch/status`, and the dashboard does not consume that endpoint.

---

## 8. Daemon startup recovery — S1 trusts S3 blindly

Two startup paths, both in `src/prep/services/pipeline/recovery.py`:

### 8.1 `hydrate_paused_runs_from_disk` (line 1370–1500)

When the daemon starts with a paused run on disk:

1. Reads S3 (`pipeline_run_metadata.json`) to find paused runs — lines 1410–1420.
2. Reads S6 (`.pause_marker`) for user-initiated pause intent — lines 1400+.
3. Reconstructs S1 — lines 1470–1487:
   - `PipelineGroupStateMachine(...)` (line 1470)
   - `Event.START` (line 1475)
   - **Manually sets `current_stage_index = resume`** (line 1482) — bypasses any STAGE_COMPLETED for prior stages
   - **Manually populates `stage_results` for prior completed stages** (line 1484) — direct dict write, no event
   - `Event.PAUSE` (line 1485)
   - `Event.STAGE_FLUSHED` (line 1486)

**Trust model: S3 is authoritative for what stage to resume from. S1 is reconstructed from S3's decision. S4 manifests are not consulted at hydration time.**

### 8.2 `auto_recover_stale_pipelines` (line 1502–1900)

**Does not touch S1.** It:

1. Scans S3 for stale runs (`check_heartbeat_stale`, line 1562).
2. Reads S4 manifests + S6 markers to decide whether to auto-trigger deep enrichment (lines 1618–1790).
3. Creates **stub manifests** in S4 if data files exist but manifest is missing (lines 1768–1774) — does NOT touch S1.
4. Fires `orchestrator.run_deep_enrichment(project_id)` if needed (line 1850+) — which creates a fresh S1 via `Event.START`.

### 8.3 The combined trust path

```
startup_recovery()
  ├── hydrate_paused_runs_from_disk()
  │     └── trusts S3 to reconstruct S1; S4 not consulted at hydration
  └── auto_recover_stale_pipelines()
        └── reads S3 + S4 + S6 to decide whether to trigger a NEW run
            └── new run creates fresh S1 via Event.START (no rehydration)
```

**If S3 and S4 disagree at startup, S1 is hydrated from S3 and the mismatch surfaces later in `_advance_pipeline` when `ResumeStrategy.detect_resume_point` reads S3+S4 (not S1) and decides what to actually run.** The state machine is downstream of disk truth, not the canonical record of it.

---

## 9. What this means for the proposal

Each row below maps an evidence section to which thread of a future re-centering proposal it informs. (No fix proposed here.)

| Evidence | Informs proposal thread |
|---|---|
| §1 (writer coverage), §2 (`stage_results` divergences) | Shape of "make S1 actually own what its docstring claims" — close the four direct-write paths |
| §3 (resume detector ignores S1) | Decide: should the resume detector consult S1 too, or should S1 be downstream of the manifests it currently mirrors? |
| §4 (status endpoint multi-source) | Decide: should the endpoint label each field with its source store so the UI can pick deliberately, or should it normalize to S1's view? |
| §5 (UI consults nothing from S1) | The smallest high-value intervention — `compute*State` reads `stage_results` first, falls back to S4 fields only when S1 has no opinion |
| §6 (scheduler independence) | Decide: should `capacity_changed` events also fire S1 events (e.g., a new `Event.CAPACITY_CHANGED`), or should they stay independent and S1 just expose them as a view? |
| §7 (watcher independence) | Decide: should the watcher's state be surfaced through `/projects/<id>/pipeline/status` next to S1's view, even if the watcher doesn't write into S1? |
| §8 (recovery trust model) | Decide: at hydration, should we cross-check S3 against S4 and refuse to hydrate S1 from a state that S4 contradicts? |

These decisions are the open questions a future scrutiny pass on the re-centering proposal must explicitly answer.

---

## 10. Cross-references

- The hypothesis: [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md).
- IQ2's companion: [`EVIDENCE_findings-replayed-against-pure-s1.md`](EVIDENCE_findings-replayed-against-pure-s1.md).
- Code: `src/prep/services/pipeline/state_machine.py` (Phase 25B canonical), `src/prep/services/pipeline/orchestrator.py` (15 transitions + 4 divergences), `src/prep/services/pipeline/resume.py` (resume detector), `src/prep/services/pipeline/scheduler.py` (S7), `src/prep/core/watcher.py` (S9), `src/prep/services/pipeline/recovery.py` (startup hydration), `src/prep/api/routers/pipeline.py:432–960` (status endpoint), `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505–680` (compute*State family).
- Prior pattern this confirms: prep concept "Canonical registry extracted to break triple-source duplication after audit finding" (`packages/ui/src/config/mcpSetup.ts`) — the team has done this kind of re-centering before, for a different subsystem.
