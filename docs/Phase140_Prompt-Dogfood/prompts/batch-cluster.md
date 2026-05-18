# Batch — Cluster summary

**File:** `src/prep/core/batch_prompts.py:313-358`
**Symbols:** `BATCHED_CLUSTER_SYSTEM`, `build_batched_cluster_prompt`
**Invoked by:** Clustering worker — once per cluster of related files
**Pipeline stage:** deep (clustering)
**Output schema:** structured JSON — module-level summary (cluster purpose, member files, primary responsibility, integration points)
**Status:** baseline

## Purpose
Produces module-level summaries from co-located file clusters. Drives the "Modules in scope" section of the atlas-style overview that `prep` returns to agents.

## Grounding (inputs)
- A cluster of related files (with file roles from batch-file)
- Their summaries from upstream prompts
- The cluster's graph subgraph (internal vs external edges)

## Output schema
JSON: `{cluster_name, purpose, member_files[], primary_responsibility, integration_points[]}`.

## Known issues / hypotheses
- **Cluster-name quality is load-bearing**. The cluster name is what shows up in `prep` output as the user-facing module label (e.g., "Dashboard React Hook Ecosystem"). Hypothesis: current names are over-long and over-novelized. Try "Plain noun phrase, max 4 words" instruction.
- **Cascade dependency on upstream summaries**: if batch-file or batch-symbol summaries are noisy, batch-cluster compounds the noise. Worth testing batch-cluster in isolation with hand-crafted clean inputs to isolate prompt quality from upstream quality.
- **Number of clusters** (memory: `project_concept_promotion_strategy.md`). Anchor-overlap clustering is the lever for concept dedup — similar issue applies to file clusters. If we have too many clusters, the atlas degrades.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured: TBD

## Iterations

_(none yet)_

## Open questions
- What's the right cluster-name length for atlas readability? Current outputs (per `prep` results) suggest 4-7 words; could shorter be better?
- Should integration_points be the same vocabulary as audit-architecture findings?

## Cross-references
- Sibling: [batch-file](./batch-file.md), [batch-symbol](./batch-symbol.md)
- Memory: `project_concept_promotion_strategy.md`
- Phase 22 — Epistemic enrichment (parent architecture)
