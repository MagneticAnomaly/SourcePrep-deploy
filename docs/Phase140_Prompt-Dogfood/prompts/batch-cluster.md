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
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-cluster/powermate-reborn.json`](../snapshots/2026-05-17_baseline/outputs/batch-cluster/powermate-reborn.json) — 24 clusters analyzed by `kimi-k2.6:cloud`, 187.3s wall

## Iterations

### 2026-05-19: B2 — snapshot gap + prompt structural review

**Type:** analysis-only (snapshot incomplete for direct prompt audit; structural review of prompt copy + recommendation to widen capture)

**Read materials:**
- `BATCHED_CLUSTER_SYSTEM` + `build_batched_cluster_prompt` (`batch_prompts.py:313-358`).
- Captured snapshot: [`../snapshots/2026-05-17_baseline/outputs/batch-cluster/powermate-reborn.json`](../snapshots/2026-05-17_baseline/outputs/batch-cluster/powermate-reborn.json) — a single JSON object describing the **meta-synthesis** (`stage: "cluster_synthesis_swarm"`) across 24 clusters.

**Finding #0 — snapshot is at the wrong layer to audit this prompt directly.** The site's target prompt is `build_batched_cluster_prompt` — a per-cluster (batched) call that emits a `name`, `summary`, `architecture_layers`, etc. for each cluster. The captured file is the **downstream synthesis-of-clusters** output (`naming_consistency`, `cross_cluster_deps`, `architectural_layering`, `redundancy_flags`, `key_insight`) — that's a different prompt. The per-cluster `{name, summary, architecture_layers, ...}` records that `build_batched_cluster_prompt` actually produces are not in the snapshot.

Cross-cluster names visible in `cross_cluster_deps` (`core-orchestration`, `build-and-distribution`, `display-control`, `hardware-abstraction-core`, `user-interface-feedback`) are **kebab-case cluster IDs**, not the title-case `name` field. The schema asks for `"name": "Descriptive Module Name"` (line 349); we don't see actual outputs of that field in the snapshot.

**Recommendation #1 — extend snapshot to capture per-cluster outputs.** Update `snapshots/2026-05-17_baseline/capture-notes.md` to (a) flag the gap, (b) document the path to the per-cluster artifacts when next captured. The per-cluster outputs likely live in the daemon's per-project index dir (`<data_dir>/projects/<powermate_id>/` — under cluster-related JSON or in `pipeline_run_metadata.json`'s stage outputs). Without these, we can't audit name length, summary lead pattern adherence ("Lead with WHAT the subsystem does"), or architecture_layer accuracy.

**Finding #1 — meta-synthesis output is high quality (incidentally validates the cluster prompt produced workable inputs).** The synthesis identifies concrete architectural issues — "star-topology architecture", "release pipeline fragmentation across 5 clusters", "research vs implementation duplication". These observations would only be possible if the per-cluster outputs were coherent and named clearly enough to be comparable. So the per-cluster prompt is probably doing well — but "probably" is a vibe, not a verdict.

**Finding #2 — `BATCHED_CLUSTER_SYSTEM` is thin compared to peer batched prompts.** It's a single sentence: "You are a software architect synthesizing module-level summaries from file clusters." Compare to `BATCHED_EPISTEMIC_CODE_SYSTEM`: "You are a senior software architect performing deep epistemic analysis of source code files." Both are persona-only system prompts. Per grounding §6 (persona prompting), the published evidence is mixed-to-skeptical on persona impact for objective tasks. The persona line is probably doing no harm, but it's also probably doing no work.

The substantive work lives in the user-prompt's NAMING RULES and SUMMARY RULES (lines 336-346) and in the JSON schema (lines 347-356). Those are well-constructed:

- NAMING RULES include positive examples ("LLM Concurrency Scheduler", "Trace Graph Builder") AND negative examples ("UI Subsystem", "Config Module", "Pipeline #2") AND a hard rule ("Never use generic labels, numbered clones, or single-word names"). This is grounding §1's "show concrete contrast" pattern executed correctly.
- SUMMARY RULES use the same positive/negative shape: "Lead with WHAT the subsystem does, not what files it contains."

**Finding #3 — the prompt lacks anti-padding/empty-output discipline.** Unlike `SYNTH_SYSTEM_PROMPT` ("EMPTY OUTPUT IS ACCEPTABLE — PADDING IS A FAILURE MODE") and the inferred-edges prompt ("empty array if none found"), batch-cluster has no clause permitting empty/sparse output. Every cluster gets a `name + summary + layers + status + dependencies + tech_debt_summary` record regardless of how thin the underlying file group is. If a cluster has 2 unrelated files, the prompt still requires a `name` and a `summary` — the model will invent both.

This is a structural property of the schema (all fields required) and a downstream issue (a 24-cluster output is mandatory, even though some clusters might be noise). Two reads:
- The clustering step upstream (anchor-overlap) is supposed to suppress noise clusters before they reach this prompt — i.e., the prompt assumes its inputs are pre-vetted.
- If upstream noise still leaks through, the prompt has no defense.

**Finding #4 — no "do not echo file names into name" instruction.** A common failure mode for cluster naming is the model just titlecasing the most common filename ("`MIDI Controller`" cluster name when the cluster contains `MIDIController.swift`). The NAMING RULES say "specific and descriptive" but don't explicitly forbid filename echoing. Without the per-cluster outputs we can't measure how often this happens; flagging as a known watchpoint.

**Verdict:** `analysis (no edit)`. Three deferred actions:

1. **Capture per-cluster outputs in the next snapshot** — without them, this site's audit is permanently structural-only.
2. **Once captured**, audit (a) name length distribution (target: 2-4 words per the prompt's own NAMING RULES; measure actual), (b) summary lead-with-WHAT compliance (parse first 5 words; count "Contains N files" / "A directory of" failures), (c) architecture_layer choice consistency across clusters with similar member files.
3. **Consider** adding an "EMPTY-OK" clause and a "do not echo filenames" clause to the prompt, both pending the audit in step 2.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (Anthropic best practices: show concrete contrast in examples) — current NAMING/SUMMARY RULES execute this well.
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §5 (Geng et al. 2025 schema overhead) — schema fully-required-fields shape may force the model to invent content for shallow clusters.
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §6 (persona prompting: published evidence mixed) — the "You are a software architect" opener is weak signal; safe to keep, no reason to invest in expanding it.

**Cross-references:** Sibling: [batch-file.md](./batch-file.md), [batch-symbol.md](./batch-symbol.md) (the upstream summaries that feed batch-cluster — if those are noisy, batch-cluster compounds). Phase 22 epistemic enrichment parent.

## Open questions
- What's the right cluster-name length for atlas readability? Current outputs (per `prep` results) suggest 4-7 words; could shorter be better?
- Should integration_points be the same vocabulary as audit-architecture findings?

## Cross-references
- Sibling: [batch-file](./batch-file.md), [batch-symbol](./batch-symbol.md)
- Memory: `project_concept_promotion_strategy.md`
- Phase 22 — Epistemic enrichment (parent architecture)
