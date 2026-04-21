# Phase 96F: Swarm-enable Concepts and Audit Workers

**Date:** 2026-04-11
**Goal:** Make CONCEPTS and AUDIT stages use the SwarmOrchestrator pattern so each LLM stage can monopolize the full configured worker budget (10 on Ollama cloud, ~9x throughput vs sequential).

---

## Why this matters

Wave parallelism with shared budget is **slower** than sequential with swarm:

| Stage | Sequential, no swarm | Wave-parallel (5w each) | Sequential, swarm (10w) |
|---|---|---|---|
| concepts | 60s | 180s | 6s |
| audit | 60s | 180s | 6s |

Single biggest win in Phase 96 is making concepts and audit use swarm. The infrastructure is already wired through `_advance_pipeline` (verified in Phase 96E) — only the worker implementations need refactoring.

---

## Design: Concepts swarm decomposition

### Decomposition unit: per-module

Each module from `trace_modules.jsonl` becomes one WorkItem. Workers generate concepts scoped to that module. Synthesizer merges + extracts cross-module invariants.

**Why per-module:**
- `trace_modules.jsonl` is already produced by the clustering stage with rich per-module metadata (member_files, summary, dependencies)
- Modules represent natural "subsystems" — concepts derived from a module have clean anchors
- Typical fan-out: 5-20 modules → fills the 10-worker budget well
- Each worker prompt is small and focused → fast per-worker → better parallelism
- Cross-module invariants surface in synthesis phase

### Worker context (per-module)

Each worker receives a context dict:
```json
{
  "module_name": "Pipeline Stage Orchestrator",
  "module_summary": "Manages 15-stage pipeline execution...",
  "domain_tags": ["pipeline", "orchestration"],
  "file_count": 12,
  "member_files": [
    {"path": "src/prep/services/pipeline/orchestrator.py", "summary": "Main orchestrator class"},
    ...
  ],
  "internal_dependencies": ["scheduler", "state_machine"],
  "external_dependencies": ["llm_client", "build_orchestrator"]
}
```

### Worker prompt

Each worker generates 3-8 concepts scoped to its module:
```
You are analyzing the "{module_name}" subsystem of the codebase.

Module context:
{full_context_json}

Your analysis angle: {assignment.analysis_angle}
Priority concerns: {assignment.priority_concerns}

Generate 3-8 concept seeds about WHY this subsystem is structured the way it is.
Focus on: design rationale, trade-offs, hidden constraints, business decisions.

Each concept should be specific to this subsystem (not generic statements).
Anchor concepts to specific files in member_files.

Output JSON:
{
  "concepts": [
    {
      "title": "...",
      "content": "2-4 sentences",
      "category": "architecture|domain|...",
      "confidence": 0.5-1.0,
      "anchors": ["file1.py", "file2.py"],
      "tags": ["tag1"]
    }
  ]
}
```

### Coordinator prompt

The coordinator decomposes the modules and assigns analysis angles to each worker:
```
You are coordinating concept extraction across {n} subsystems of a codebase.

Subsystems:
{group_summaries}

For each subsystem, choose an analysis_angle that suits its nature:
- Pipeline/orchestration → "control flow and coordination"
- Data/storage → "data model and persistence boundaries"
- API/router → "interface contracts and validation"
- Worker/processor → "input transformation and side effects"
- Config/settings → "constraint propagation and defaults"
- Test/eval → "guarantees being verified"

Respond with JSON:
{
  "assignments": [
    {
      "item_id": "module:...",
      "analysis_angle": "...",
      "priority_concerns": ["...", "..."]
    }
  ]
}
```

### Synthesis prompt

The synthesizer merges per-module concepts + extracts cross-module invariants:
```
Below are concepts extracted from {n} parallel subsystem analyses.

{worker_outputs}

Your task:
1. Deduplicate concepts (merge any with similar title or overlapping content)
2. Identify CROSS-MODULE patterns (concepts that span multiple subsystems)
3. Generate 3-5 GLOBAL invariants — concepts that describe the codebase as a whole
4. Generate 3-8 clarifying questions about areas where the "why" is unclear

Output JSON:
{
  "concepts": [
    {
      "title": "...",
      "content": "...",
      "category": "...",
      "confidence": 0.5-1.0,
      "anchors": ["..."],
      "tags": ["..."],
      "scope": "module|cross-module|global"
    }
  ],
  "questions": [
    {
      "question": "...",
      "context": "...",
      "suggested_category": "..."
    }
  ]
}
```

### Fallback to sequential

`seed_concepts_swarm()` falls back to `seed_concepts()` (sequential single-call) when:
- Fewer than 3 modules with ≥ MIN_MODULE_FILES files exist (insufficient fan-out)
- The configured model doesn't support swarm (`is_swarm_active_for_stage` returns False)
- The scheduler returns `full_budget_for_swarm() < 3` (low-resource guard)
- Any error during swarm setup

---

## Design: Audit Tier 2 swarm decomposition

### Decomposition unit: per-finding-category

Audit Tier 1 already produces categorized findings. Decompose Tier 2 LLM synthesis by category:
- coupling
- complexity
- testability
- architecture
- security
- performance

Each worker synthesizes high-level observations for its category. Synthesizer produces the final audit narrative.

### Worker context (per-category)

```json
{
  "category": "coupling",
  "finding_count": 14,
  "findings": [
    {"title": "...", "severity": "warning", "files": ["..."], "details": "..."},
    ...
  ]
}
```

### Worker prompt

```
You are synthesizing audit findings for the "{category}" category.

Findings ({finding_count}):
{full_context_json}

Generate 1-3 high-level observations about this category:
- What pattern do these findings reveal?
- What's the underlying root cause?
- What action would address the most findings at once?

Output JSON:
{
  "observations": [
    {
      "category": "{category}",
      "headline": "Short summary",
      "narrative": "2-4 sentences",
      "root_cause": "...",
      "recommended_action": "...",
      "affected_files_sample": ["..."],
      "severity": "info|warning|critical"
    }
  ]
}
```

### Synthesizer prompt

```
Below are observations from {n} parallel category analyses.

{worker_outputs}

Synthesize the overall audit:
- Top 3-5 highest-priority observations across all categories
- Cross-cutting patterns (themes that appear in multiple categories)
- Overall codebase health assessment

Output JSON:
{
  "top_priorities": [...],
  "cross_cutting_patterns": [...],
  "overall_health": "good|moderate|concerning",
  "summary": "..."
}
```

### Fallback to sequential

Falls back to current single-call Tier 2 synthesis when:
- Fewer than 3 categories have findings
- Model doesn't support swarm
- Scheduler budget < 3

---

## Implementation plan

### 96F.1 — concept_seeder swarm refactor
**File:** `src/prep/core/concept_seeder.py`
**Changes:**
1. Keep existing `seed_concepts()` as the sequential path (rename internally to `_seed_concepts_sequential()` if needed)
2. Add `seed_concepts_swarm()` with the per-module decomposition above
3. Add public `seed_concepts(project_id, *, prefer_swarm=True)` wrapper that:
   - Tries swarm if `prefer_swarm` and conditions met
   - Falls back to sequential otherwise
4. Helper functions:
   - `_load_modules_for_swarm(index_dir)` — loads modules with ≥3 file count
   - `_build_module_context(module, index_dir)` — builds focused per-module dict
   - `_dedupe_concepts(concept_lists)` — merges by title similarity
**Tests:**
- Unit test `seed_concepts_swarm` with mocked SwarmOrchestrator
- Integration test confirms swarm path produces concepts and they're saved
- Fallback test confirms sequential path runs when modules < 3

### 96F.2 — audit Tier 2 swarm refactor
**File:** `src/prep/core/audit/runner.py`
**Changes:**
1. Locate the existing Tier 2 LLM synthesis call
2. Refactor into `_synthesize_tier2_swarm()` and `_synthesize_tier2_sequential()`
3. Router logic in `run_audit(..., tier2=True)`:
   - If categories ≥ 3 and swarm available → swarm
   - Else → sequential
4. Helper: `_group_findings_by_category(findings)`
**Tests:**
- Unit test swarm path with mocked SwarmOrchestrator
- Integration test on real findings fixture

### 96F.3 — Register stages in SWARM_CAPABLE_STAGES
**File:** `src/prep/services/pipeline/scheduler.py`
**Change:**
```python
SWARM_CAPABLE_STAGES: Set[str] = {
    "group_reasoning", "clustering", "atlas",
    "concepts", "audit",  # Phase 96F
}
```
**Tests:**
- Update `test_is_swarm_active_for_stage` to cover concepts and audit
- Verify the swarm window opens for concepts/audit during finalize runs

### 96F.4 — Workers wire-up
**File:** `src/prep/services/pipeline/workers.py`
**Changes:**
- `_concepts_worker`: call `seed_concepts(prefer_swarm=True)` (no-op change since the wrapper handles routing)
- `_audit_worker`: pass `swarm=True` to `run_audit` for Tier 2

### 96F.5 — Live validation
- Run rebuild on rust_repo via Playwright driver
- Verify log shows `[Swarm] Coordinator planned N assignments` for concepts and audit
- Verify wall-clock improvement vs the 96E baseline run
- Verify dashboard shows the stages running with full budget

---

## Success criteria

- [ ] `seed_concepts_swarm` works with mocked SwarmOrchestrator
- [ ] `seed_concepts_swarm` falls back to sequential when conditions not met
- [ ] Audit Tier 2 swarm works with mocked SwarmOrchestrator
- [ ] CONCEPTS and AUDIT in SWARM_CAPABLE_STAGES
- [ ] All 202 existing pipeline tests still pass
- [ ] Live rebuild on rust_repo shows `[Swarm]` log lines for concepts and audit
- [ ] Wall-clock improvement measured

---

## Out of scope for 96F

- Tier 1 audit analyzer parallelism (CPU-bound, separate optimization)
- Wave parallelism for finalize (deferred to 96G if ever needed)
- Frontend display of "concepts running with 10 workers" (Phase 97 dashboard work)
- Per-cluster concept decomposition (instead of per-module) — would duplicate clustering effort
