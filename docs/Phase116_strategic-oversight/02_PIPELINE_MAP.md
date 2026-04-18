# 02 — Current Pipeline Map

Ground truth as of 2026-04-17. Stages 1–10 are the enrichment pipeline; 11–15
are the finalize group. Phase 116 primarily focuses on 1–10 but the finalize
stages are documented here because several candidate checkpoints touch them.

## Stages 1–10 (enrichment)

| # | Name | Ingests | Produces | LLMs | Entry point |
|---|---|---|---|---|---|
| 1 | STRUCTURAL | Source files | `trace_nodes.jsonl`, `trace_edges.jsonl` | None (Rust) | `src/codrag/services/pipeline/workers.py:117` |
| 2 | INFERRED_EDGES | Nodes + snippets | `trace_inferred_edges.jsonl` | Kimi | `workers.py:121` |
| 3 | CATALOGUE | Augmented nodes | `trace_augmented.jsonl` | Gemini Flash | `workers.py:123` |
| 4 | VALIDATION | Edges + inferred | Status (no file) | None (Rust) | `workers.py:125` |
| 5 | KNOWLEDGE | Augmented nodes | Embeddings (no JSONL) | Ollama (ONNX/CoreML) | `workers.py:127` |
| 6 | ENRICHMENT | Augmented | `trace_epistemic.jsonl` | Opus | `workers.py:129` |
| 7 | GROUP_REASONING | Epistemic | `trace_group_reasoning.jsonl` | Opus + Kimi Swarm | `workers.py:131` |
| 8 | CLUSTERING | Epistemic | `trace_modules.jsonl` | Opus | `workers.py:133` |
| 9 | DEEPENING | Epistemic + modules | `trace_epistemic.jsonl` (updated) | Opus | `workers.py:137` |
| 10 | DEEP_KNOWLEDGE | Epistemic + modules | Embeddings (no JSONL) | Ollama | `workers.py:127` (shared) |

## Stages 11–15 (finalize group)

| # | Name | Output | LLMs |
|---|---|---|---|
| 11 | ATLAS | Atlas + role projections | Opus |
| 12 | CONCEPTS | Promoted concepts | Opus (via audit swarm) |
| 13 | RULES | Rule files (AGENTS.md etc.) | None |
| 14 | AUDIT | 5 markdown reports (summary, arch, gap, inventory, tech-debt) | Opus |
| 15 | ANTIBODIES | Immune-system rules derived from concepts | None (template-based) |

## Swarm architecture (Stage 7 detail)

Stage 7 is the prototypical swarm stage. `src/codrag/core/swarm_orchestrator.py:70-250`
runs the pattern:

```
coordinator (Opus-style) plans groups
    └── for each group:
        └── fan out to N workers (Kimi, DEFAULT_WORKER_TIMEOUT_S=180s)
            ├── each worker analyzes the group independently
            └── returns confidence + blast-radius + coupling risks
        └── synthesis (Opus) merges worker outputs into one GroupReasoningEntry
```

**Observable state today:** `SwarmResult.worker_results` exposes all N worker
outputs. Synthesis consumes them but does not surface *disagreement* —
conflicting blast-radius / coupling assessments are averaged into a single
confidence field silently.

## Confidence fields across stages

Observed inconsistency (noted in dogfooding feedback — see `08_`):

| Stage | Confidence field | Semantics |
|---|---|---|
| INFERRED_EDGES | `confidence` (0–1) | Per-edge |
| CATALOGUE | `confidence` (0–1) | Per-node |
| ENRICHMENT | `epistemic_confidence` (0–1) | Per-file |
| GROUP_REASONING | `confidence` (0–1) | Per-group (no per-member) |
| CLUSTERING | — (none) | No confidence exposed |
| DEEPENING | `epistemic_confidence` (0–1) | Per-file (second pass) |

This inconsistency is an obstacle to a unified overseer: the gate logic has
to normalize across different semantics.

## Known weirdness / regressions

Documented in code comments and in `PHASES.md`:

- **Phase 76 / 89 / 91 / 92 state-machine regressions.** State machine
  (`src/codrag/services/pipeline/state_machine.py:25`) comments reference
  lost stage advancement. Transitions are defined (RUNNING → RUNNING on
  STAGE_COMPLETED) but incrementing `current_stage_index` is not obvious
  from a cold read. Audit before layering overseer gates on top.
- **Swarm worker timeout is silent.** Workers that exceed 180s are marked
  `failed` in `worker_results` but synthesis still runs with the surviving
  subset. No warning when failure rate > threshold.
- **Knowledge stages produce no artifact.** Stages 5 and 10 are
  embedding-only passes with `STAGE_OUTPUT_FILE=None`. Fine functionally
  but manifest doesn't distinguish "no-output stage" from "failed stage."
- **Hub-file information is computed but unused downstream.** `codrag_impact`
  knows blast radius; stages 6–8 do not receive it as input. A hub file
  gets the same treatment as a leaf during enrichment and clustering.
- **Audit reports are independent.** `AuditSynthesizer` parallelizes 5
  report generators with no cross-consistency check. ARCHITECTURE_ANALYSIS
  can claim "monolithic" while COMPONENT_INVENTORY claims "microservices"
  and nothing surfaces the contradiction.

## Implications for Phase 116

These aren't all overseer problems, but they shape the design space:

1. The **state-machine advancement** work needs to happen first (or in
   parallel) — you can't gate a stage transition that isn't cleanly defined.
2. **Confidence normalization** is prerequisite plumbing. A uniform
   `quality_score` across stages makes gating policies portable.
3. **Hub-file propagation** would make hub-aware gating trivial. Today we'd
   have to re-derive blast radius at overseer-call time.
4. **Swarm worker-disagreement exposure** is the lowest-cost signal we
   could surface — it already exists in `worker_results`, just isn't
   summarized.
