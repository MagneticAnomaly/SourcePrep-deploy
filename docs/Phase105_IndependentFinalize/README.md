# Phase 105 — Independent Finalize Stages

> **Core reframe.** CoDRAG has been treated as two groups (Sync 1–5, Enrich 6–10) that must run sequentially, plus a Finalize group (11–15) that also runs sequentially. Phase 105 makes it **three groups of five**, where the Finalize five are **independent post-pipeline learners** — each triggerable on its own with full queue/history/state parity with the other pipeline stages. The group-level "Run Finalize" trigger stays as today (queues all five in order). Individual stages become cheap, targeted reruns.

This is the root-cause fix for the symptoms observed after Phase 104 shipped: pressing the Atlas "Regenerate" button updated the atlas card in isolation — no queue entry, no pipeline journal update, no last-run-date bump, no stage-state transition in the pipeline panel. The cause is that `/atlas/regenerate` is an in-process `atlas.generate_segmented()` call that completely bypasses the orchestrator. Phase 105 removes the bypass and generalizes the fix to every finalize stage that already has a UI trigger.

## The three-pipeline mental model

```
Group 1: Sync         (stages 1–5)    — sequential, group-only trigger
Group 2: Enrich       (stages 6–10)   — sequential, group-only trigger
Group 3: Finalize     (stages 11–15)  — INDEPENDENT LEARNERS + group trigger

                 Atlas     Rules     Concepts     Audit     Antibodies
                 [solo]    [solo]    [solo]       [solo]    [solo]
                 └─────────────── run_finalize (all 5, ordered) ───────────┘
```

The five finalize learners:

1. **Atlas** — synthesizes module-level codebase map from trace graph.
2. **Rules** — generates AGENTS.md / CLAUDE.md / IDE rule files from atlas + concepts.
3. **Concepts** — LLM-seeds concept candidates (knowledge entries).
4. **Audit** — structural analysis + optional LLM-summarized findings.
5. **Antibodies** — derives runtime checkers from constraint/architecture concepts.

Each learner has a legitimate use case for solo rerun:

- Atlas: modules haven't changed but you want a fresh module-level summary with a different model or after adjusting epistemic weights.
- Rules: you updated a template or added a new IDE target (Cursor, Windsurf, Zed), regenerate rules without re-running anything upstream.
- Concepts: a new code area merged; seed fresh concept candidates for it without touching atlas.
- Audit: you fixed a reported issue and want to confirm it's gone.
- Antibodies: you just promoted a seed concept to active with a new assertion — rebuild immune system without touching anything else.

None of these depend on one another at the data level except:
- Rules reads atlas content (if atlas is dirty, rules is stale).
- Antibodies reads concepts (if concepts is dirty, antibodies may be stale).

Dependency invalidation is the orchestrator's job, not the UI's. Fresh → stale cascades remain, but each stage is independently re-runnable.

## Problem statement (what's broken today)

`POST /projects/{id}/atlas/regenerate` (and `onRunAudit` on the audit panel) invoke stage work directly in the FastAPI request handler. The four symptoms observed after Phase 104:

1. **No queue entry.** The left-panel queue never shows the regenerate as pending/running/done.
2. **No pipeline-panel update.** Stage-level state flags remain at their old values; "last run" dates don't move.
3. **No journal/history update.** `pipeline_history` never records the run.
4. **Downstream stale flags don't flip.** Segments keep their "stale" badge because the pipeline's stage-completion tracker (separate from `atlas.is_stale()`) wasn't touched.

All four collapse into one cause: **bypassing the orchestrator**. Every fix converges on the same remedy — route the regenerate through the orchestrator the same way `run_finalize` does, but for a single stage.

## In scope (this phase)

### Backend

1. **Orchestrator support for single-stage runs.** New method `run_single_stage(project_id, stage_id)` that:
   - Validates `stage_id` is in `FINALIZE_STAGES`.
   - Enqueues a one-stage group through the existing `_start_group` machinery.
   - Integrates with the existing queue, journal, history, and event emission.
   - Respects the existing pause/cancel/resume semantics.
   - Refuses if an enrich/sync run is active (same guard as `run_finalize` today).
2. **HTTP endpoints.** `POST /projects/{id}/pipeline/stages/{stage_id}/run` — thin router wrapper. Returns 409 if another run is active or the stage is already up-to-date.
3. **Deprecate the direct-call paths.** `POST /projects/{id}/atlas/regenerate` becomes an alias for `POST /pipeline/stages/atlas/run` (301/302 or in-code redirect, TBD during implementation). Same for the audit run button once verified.
4. **Dependency invalidation.** When atlas runs solo, rules gets marked stale (since rules embeds atlas content). When concepts runs solo, antibodies gets marked stale. The orchestrator already has stage-readiness checks — extend them to invalidate downstream siblings.
5. **Post-run hooks preserved.** The atlas regenerate currently invalidates the role-atlas cache (our Phase 104 work). This behavior must be preserved in the orchestrator path.

### Frontend

1. **Match existing pipeline stage UI.** The Graph Enrichment Pipeline panel renders stages with per-stage status (idle / running / complete / stale / error), last-run timestamps, and per-stage Run buttons where provided. The atlas regenerate button and audit run button should look and behave like these — no bespoke "Regenerate" pill.
2. **Only wire UI for stages that already have triggers.** Atlas and Audit (and the group-level Run Finalize). Rules, Concepts, and Antibodies get **no new UI surface** in Phase 105. Their backend trigger endpoints exist for MCP/agent callers but aren't exposed as buttons.
3. **AtlasLensPanel regenerate button rewrite.** Points at `/pipeline/stages/atlas/run` instead of `/atlas/regenerate`. Shows orchestrator-reported state (running, queued, last-run) pulled from the pipeline status endpoint rather than computing it locally.
4. **Audit panel `onRunAudit` rewrite.** Same treatment — points at `/pipeline/stages/audit/run`.

### Prompt-cache optimization (Phase 105.5, captured here)

Between consecutive LLM finalize stages (atlas → concepts → audit-summary), the shared prompt prefix (~20–30KB of trace graph + module summaries) is identical. Enable Anthropic's prompt caching on this prefix so the second and third calls pay only for their unique suffix. Achieves ~90% of a full "fuse all three into one swarm call" optimization without the coupling penalty.

Implementation: add `cache_control: {type: "ephemeral"}` at the end of the shared prefix block when the LLM client is Anthropic. Other providers (Ollama, OpenAI) — no-op.

This lands as a follow-up commit after Phase 105 core, not blocking.

## Out of scope

- **No fusion into a single LLM call.** Considered and rejected. Tradeoffs documented in "Optimizations considered" below.
- **No concurrency between finalize stages.** Stages remain sequential within a group run. Solo runs are inherently single-stage, so the question doesn't arise. Concurrent runs of different solo stages (e.g., audit while atlas is running) — rejected for v1 to keep the state machine simple.
- **No new UI triggers for Rules / Concepts / Antibodies.** Backend-only for these. UI for them is a Phase 106 question.
- **No agent-ownership model.** The idea that a specific agent (e.g., "Scholar") owns a stage and receives the trigger hand-off is noted as Phase 106+ and shapes the orchestrator API (`run_single_stage` returns a run-id that an agent could claim), but no agent wiring happens this phase.
- **No swarm-fanout per stage.** Each solo call remains single-worker today. Swarm parallelism is separately tracked in Phase 79 work and is orthogonal.

## Optimizations considered

### 1. Fuse Atlas + Concepts + Audit-LLM into one swarm call

**Benefit:** 20–30KB shared prefix evaluated once instead of three times. Atomic consistency across the three outputs. Lower latency.

**Rejected because:**
- Contradicts the "independently triggerable" requirement. All-or-nothing coupling.
- Response-budget ceiling: atlas (~4–8KB) + concepts (~2–3KB) + audit summary (~2–4KB) crowds model output window.
- Blast radius: one failed section kills three stages.
- Temperature/model-config mismatch: atlas wants deterministic thinking; concept seeding benefits from variance.
- Breaks agent-ownership model (no obvious owner for a fused call).

### 2. Prompt-cache the shared prefix across sequential stages

**Benefit:** ~90% of the fusion cache benefit without coupling. Works even when only one stage is dirty. Anthropic-native, small code change.

**Accepted.** Lands as Phase 105.5 follow-up.

### 3. Concurrent solo runs

**Benefit:** Audit and atlas don't depend on each other; running them in parallel cuts wall-clock time.

**Deferred.** Orchestrator's current state machine assumes one group-run at a time. Supporting concurrent solo runs requires rework of the queue/journal/lock structure. Phase 106+ if measurably valuable.

## Design questions to resolve in the implementation plan

1. **`run_single_stage` reuse of `_start_group`.** Does `_start_group` cleanly accept a single-element stage list, or does it make assumptions about group identity (`"finalize"`, `"fast_sync"`, etc.)? May need a new "solo" group identity or generalization of the group concept.

2. **Stage identity for `run_single_stage(project_id, stage_id)`.** What does the journal/history record as the "group" for a solo run? Options:
   - Use the stage_id as the group name (`group="atlas"`).
   - Reuse `"finalize"` but flag the run as `solo=True`.
   - New `"solo"` group identity with stage recorded in metadata.

3. **Dependency invalidation cascade.** When atlas runs solo, rules is stale. Mechanism:
   - Orchestrator emits a stage-complete event; rules-stage freshness check reads it.
   - Direct mutation of a stage-state table.
   - Implicit via `STAGE_INPUT_FILES` (rules reads atlas output file; if mtime advances, rules is stale). *This may already work* — verify.

4. **UI event subscription.** The Graph Enrichment Pipeline panel polls or listens for status changes. Does solo-run status reach it through the same channel, or does it need a new event type?

5. **Deprecation path for `/atlas/regenerate`.** Options:
   - HTTP redirect (`307 Temporary Redirect → /pipeline/stages/atlas/run`).
   - In-handler forward (same process, same response).
   - Remove immediately and update UI in the same commit (UI client is internal, no external consumers).
   
   Same question applies to the direct-call audit run if present.

6. **MCP surface.** Should there be an MCP tool for triggering solo stages from agents? (`codrag_run(stage="atlas")`?) Phase 106 question but shape now informs endpoint design.

7. **Regenerate button UX when the stage is already queued.** What does the button show? Disabled + "queued"? "Cancel"? Needs the same treatment the existing pipeline stage buttons have — verify what they do.

## Success criteria

- Pressing the atlas regenerate button results in a queue entry visible in the left panel within ~200ms.
- `pipeline_history` records the run with start/end timestamps and `group="atlas"` (or whichever group identity is chosen).
- The pipeline panel's "last run" timestamp for the atlas stage advances.
- Segments' stale flags flip to fresh after the run completes.
- Running audit solo and atlas solo in sequence produces two journal entries, two history rows, two UI stage-state transitions.
- `run_finalize` group run still produces exactly one history entry with all five stages inside (no regression).
- `codrag_audit` dashboard tools / Phase 79 swarm tools work unchanged.

## Relevant code

### Orchestrator + stages
- `src/codrag/services/pipeline/orchestrator.py` — `run_finalize`, `_start_group`, `_find_finalize_resume_point`, journal integration.
- `src/codrag/services/pipeline/stages.py` — `StageId`, `FINALIZE_STAGES`, `STAGE_INPUT_FILES`, `STAGE_OUTPUT_FILES`.
- `src/codrag/services/pipeline/workers.py` — per-stage worker implementations including atlas, rules, concepts, audit, antibodies.
- `src/codrag/services/pipeline_history.py` — history persistence.
- `src/codrag/services/pipeline_journal.py` — journal persistence.

### HTTP
- `src/codrag/api/routers/pipeline.py` — existing `POST /pipeline/finalize`, `POST /pipeline/fast`, etc. Target location for new `/pipeline/stages/{stage_id}/run`.
- `src/codrag/api/routers/projects/atlas_endpoints.py` — current `regenerate_atlas` (to be deprecated/forwarded).

### UI
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — per-stage Run buttons pattern to match.
- `packages/ui/src/components/trace/AtlasLensPanel/StatusStrip.tsx` — regenerate button to rewire.
- `packages/ui/src/components/audit/AuditPanel.tsx`, `HealthScannerPanel.tsx` — audit run button.
- `src/codrag/dashboard/src/hooks/useAtlasLens.ts` — `regenerate()` implementation to rewire.

### Phase 96 reorg context
- `docs/Phase96-fix-pipeline/UI+tweaks/PIPELINE_15_STAGE_REORGANIZATION.md` — original 3×5 reorg plan.

## Implementation sequence (sketch, not final)

1. Orchestrator `run_single_stage` + tests.
2. HTTP endpoint `POST /pipeline/stages/{stage_id}/run` + tests.
3. Dependency invalidation wiring (atlas → rules stale; concepts → antibodies stale) + tests.
4. UI: atlas regenerate button rewired to new endpoint; status derived from pipeline state, not local.
5. UI: audit run button rewired to new endpoint.
6. Deprecate `/atlas/regenerate` (decide in-flight whether to redirect or remove).
7. Phase 105.5 prompt-cache follow-up.

Each step ends at a checkpoint where the dev server still runs and tests pass.
