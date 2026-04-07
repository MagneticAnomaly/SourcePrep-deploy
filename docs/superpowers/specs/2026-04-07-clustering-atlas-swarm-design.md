# Clustering & Atlas Swarm Integration — Design Spec

> Date: 2026-04-07
> Phase: 79 (Swarm Expansion)
> Status: Approved
> Depends on: Phase 79 core (SwarmOrchestrator, SwarmRegistry, Group Reasoning integration — all complete)

## Goal

Add swarm orchestration to two additional pipeline stages:
- **Stage 8: Clustering (Module Synthesis)** — Medium swarm benefit
- **Stage 9: Atlas Generation** — Medium swarm benefit

Both reuse the existing `SwarmOrchestrator` (coordinator → fan-out → synthesis). Only stage-specific prompts and wiring are needed.

Additionally, leave a TODO marker for the future **Dual-Model Swarm** optimization (coordinator uses `large` model slot, workers use `small` slot).

## Non-Goals

- Dual-model swarm implementation (future work)
- Epistemic Enrichment swarm (decided against — low benefit)
- MCP tool swarm (tools are lightweight lookups, no LLM fan-out)

---

## Stage 8: Clustering Swarm

### Current Behavior

`cluster.py` processes clusters via `synthesize_cluster()` — each cluster gets an independent LLM call with `MODULE_SYNTHESIS_PROMPT` containing member summaries and external dependencies. Runs concurrent or batched depending on profile.

### Swarm Additions

**WorkItem construction:**
- `id`: cluster_id (e.g., `"cluster:auth"`)
- `summary`: `"{primary_tag}: {file_list_truncated} ({N} files)"`
- `full_context`: JSON with `member_summaries`, `external_deps`, `domain_tags`, `file_count`

**Coordinator prompt:**
Asks the coordinator to examine all clusters and assign per-cluster:
- `naming_guidance`: Suggest a module name direction based on the cluster's apparent role
- `analysis_angle`: What to focus on (e.g., "data access patterns" vs. "API contract surface")
- `naming_constraints`: Names to avoid (prevents overlap with other clusters)

**Worker function:**
Calls a new `synthesize_cluster_with_angle()` method that:
1. Builds the standard `MODULE_SYNTHESIS_PROMPT`
2. Appends coordinator guidance (naming direction, analysis angle)
3. Calls LLM with same settings as `synthesize_cluster()`
4. Returns `ModuleEntry`

**Synthesis prompt:**
Aggregates all worker outputs and looks for:
- Naming consistency (are module names coherent as a set?)
- Cross-cluster dependencies (do clusters reference each other's files?)
- Architectural layering (do clusters map cleanly to layers?)
- Redundancy (are two clusters essentially the same module?)

**Synthesis artifact:** Written to `trace_cluster_swarm_synthesis.json`.

**Threshold:** 3+ clusters to activate swarm.

**Fallback:** If coordinator fails, falls through to existing concurrent/batched path.

### Files Modified

| File | Change |
|------|--------|
| `src/codrag/core/cluster.py` | Add `_run_swarm()`, `synthesize_cluster_with_angle()`, `_get_swarm_enabled()`, `_write_cluster_synthesis()`, swarm decision branch in `run()` |

---

## Stage 9: Atlas Swarm

### Current Behavior

`atlas/generator.py` has `generate_segmented()` which:
1. Discovers workspace segments via `compute_segments()`
2. Generates per-segment atlases via `_generate_segment_atlas()` (parallel with ThreadPoolExecutor)
3. Generates root atlas via `_generate_root_atlas()` using all segment results

### Swarm Additions

Swarm replaces step 2 (per-segment generation) with coordinator-scoped parallel workers and adds a synthesis step that feeds into step 3 (root atlas).

**WorkItem construction:**
- `id`: segment_id (e.g., `"seg:packages/ui"`)
- `summary`: `"{dir_path} ({file_count} files, domains: {domain_tags})"`
- `full_context`: JSON with `module_ids`, `key_files`, `domain_tags`, `file_count`, `dir_path`

**Coordinator prompt:**
Asks the coordinator to examine all segments and assign per-segment:
- `analysis_focus`: What aspect to emphasize (e.g., "component architecture" vs. "data pipeline flow")
- `cross_segment_hints`: Which other segments this one likely connects to
- `priority_files`: Which key files deserve the most attention

**Worker function:**
Calls a new `_generate_segment_atlas_with_angle()` method that:
1. Builds the standard `SEGMENT_ATLAS_PROMPT`
2. Appends coordinator guidance (focus, cross-segment hints)
3. Calls LLM with same settings as `_generate_segment_atlas()`
4. Returns `SegmentDocument`

**Synthesis prompt:**
Aggregates all segment atlases and produces:
- Cross-segment data flow chains
- Shared dependency patterns
- Architectural coherence assessment
- Key cross-cutting concerns

**Synthesis output:** Injected into the root atlas generation prompt as additional context, improving the quality of the final atlas. Also written to `atlas_swarm_synthesis.json`.

**Threshold:** 3+ segments to activate swarm.

**Fallback:** If coordinator fails, falls through to existing `generate_segmented()` parallel path.

### Files Modified

| File | Change |
|------|--------|
| `src/codrag/core/atlas/generator.py` | Add `_run_swarm()`, `_generate_segment_atlas_with_angle()`, `_get_swarm_enabled()`, `_write_atlas_synthesis()`, swarm decision branch in `generate_segmented()` |

---

## Dual-Model Swarm TODO

Both stages should include a TODO comment at the SwarmOrchestrator instantiation point:

```python
# TODO(Phase79-DualModel): When dual-model swarm is implemented,
# use large_llm for coordinator/synthesis, small_llm for workers.
# For now, single model handles all three phases.
orch = SwarmOrchestrator(llm=self.llm, concurrency=concurrency)
```

The future dual-model design is documented in `docs/Phase79_Swarm/05_Dual_Model_Swarm_Plan.md`. The key insight from today's discussion: dual-model can simply map to existing `large` (thinking) and `small` (fast) model slots rather than requiring complex pairing logic. A model assignment toggle in the UI will let users override the defaults.

---

## Shared Patterns

Both stages follow the same pattern established in Group Reasoning:

1. **Swarm decision** in `run()`/`generate_segmented()`: check `get_swarm_tier()`, `_get_swarm_enabled()`, item count >= threshold
2. **WorkItem construction**: stage data → `WorkItem(id, summary, full_context)`
3. **Coordinator prompt**: stage-specific template with `{group_summaries}` placeholder
4. **Worker function**: bridges `SwarmOrchestrator` callback to stage-specific analysis method
5. **Synthesis prompt**: stage-specific template with `{worker_outputs}` placeholder
6. **Result conversion**: `WorkerResult` → stage-specific entry objects
7. **Fallback**: coordinator failure → standard concurrent path

## Testing Strategy

Each stage gets:
- **Decision tests**: swarm activates when eligible, skips when model unsuitable / disabled / below threshold
- **Integration test**: full swarm path with mocked LLM

Test files:
- `tests/test_cluster_swarm.py`
- `tests/test_atlas_swarm.py`

## Cost Impact

Per the earlier analysis, adding swarm to Stages 8+9 adds ~$0.10–0.15 per pipeline run in coordinator/synthesis overhead, but the quality improvement in naming consistency and cross-segment coherence justifies it. With dual-model (future), worker costs drop 5-6x.
