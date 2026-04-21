# Phase 79: Agent Swarm Integration — Design Spec

> Date: 2026-04-07  
> Status: Design approved, pending implementation plan  
> Approach: Stage-level swarm wrapper (Approach A)  
> First target: Group Reasoning (Stage 7)

## Summary

When Prep detects a swarm-capable model, it upgrades specific pipeline stages from "concurrent independent calls" to a three-phase swarm pattern: **coordinator → parallel fan-out → synthesis**. This produces higher-quality architectural analysis by giving each parallel worker a scoped role and adding a cross-cutting synthesis step that standard concurrent batching cannot provide.

The swarm is invisible to users by default — it silently improves results. A settings toggle lets users disable it to save tokens.

## Design Principles

1. **Pipeline safety first.** The pipeline is delicate. Swarm is a wrapper around existing stage logic, not a replacement. When swarm is off or the model is ineligible, the existing code path runs unchanged.
2. **Finite model list.** Swarm capability is not auto-detected. A short curated list of validated models gates the feature. Default is unsuitable.
3. **Same outputs.** Swarm produces the same `GroupReasoningEntry` objects and the same `trace_group_reasoning.jsonl` format. Downstream stages don't know swarm was used. The synthesis is an additive bonus artifact.
4. **Respect concurrency budget.** Workers use the existing `llm_concurrency_deep` slots. The coordinator and synthesis calls are single sequential calls that don't compete for slots.

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `src/prep/core/swarm_registry.py` | Swarm tier lookup — finite list of supported models |
| `src/prep/core/swarm_orchestrator.py` | Three-phase swarm executor (coordinator → fan-out → synthesis) |
| `src/prep/data/swarm_models.json` | External model list for easy updates |

### Modified Files

| File | Change |
|------|--------|
| `src/prep/core/group_reasoning.py` | Add `_run_swarm()` method; decision branch in `run()` |
| Pipeline settings (DB/API) | Add `swarm_enabled` boolean |

### Unchanged Files

Everything else in the pipeline remains untouched:
- `PipelineOrchestrator`, `PipelineScheduler`, `WorkerFactory`
- `BuildOrchestrator` state machine
- `LLMClient` (swarm orchestrator calls `generate()` normally)
- `batch_profiles.py`, `model_awareness.py`, `model_readiness.py`
- All other pipeline stages

---

## Component 1: Swarm Registry

### `src/prep/data/swarm_models.json`

A flat JSON file with the validated model list. No regex — just exact model family strings matched with simple `startswith`/`contains` checks.

```json
{
  "version": "0.1.0",
  "last_reviewed": "2026-04-07",
  "min_groups_threshold": 3,
  "models": [
    {
      "id": "kimi-k2.5",
      "match": { "provider": ["ollama"], "contains": "kimi" },
      "tier": "both",
      "notes": "Primary supported model. Designed for agent swarm."
    },
    {
      "id": "claude-sonnet-4",
      "match": { "provider": ["anthropic", "openai-compatible"], "contains": "sonnet" },
      "tier": "both",
      "notes": "Best cost/quality ratio."
    },
    {
      "id": "claude-opus-4",
      "match": { "provider": ["anthropic", "openai-compatible"], "contains": "opus" },
      "tier": "coordinator",
      "notes": "Best synthesis quality. Expensive."
    },
    {
      "id": "gpt-5.4",
      "match": { "provider": ["openai", "openai-compatible"], "contains": "gpt-5" },
      "tier": "both",
      "notes": "Structured outputs. Outstanding agentic evals."
    },
    {
      "id": "gemini-pro",
      "match": { "provider": ["openai-compatible", "ollama"], "contains": "gemini" },
      "tier": "coordinator",
      "notes": "Best long-context coordination. 1M effective."
    },
    {
      "id": "grok-4",
      "match": { "provider": ["openai-compatible"], "contains": "grok" },
      "tier": "both",
      "notes": "Strong contextual awareness."
    }
  ],
  "default_tier": "unsuitable"
}
```

### `src/prep/core/swarm_registry.py`

```python
class SwarmTier(str, Enum):
    COORDINATOR = "coordinator"
    BOTH = "both"
    WORKER = "worker"
    UNSUITABLE = "unsuitable"

    @property
    def can_coordinate(self) -> bool:
        return self in (SwarmTier.COORDINATOR, SwarmTier.BOTH)


def get_swarm_tier(provider: str, model: str) -> SwarmTier:
    """Look up swarm tier for a model. Returns UNSUITABLE if not in list."""
    # Load swarm_models.json (cached after first load)
    # Match provider + model name against each entry
    # First match wins
    # Default: UNSUITABLE
```

**Matching logic:** For each entry in `models`, check:
1. `provider` is in the entry's provider list
2. Model name contains the entry's `contains` string (case-insensitive)

Matches are intentionally broad per model family (e.g., `"contains": "kimi"` matches `kimi-k2.5`, `kimi-k3`, any future Kimi model). This is by design — when a new version of a supported family ships, it's assumed swarm-capable until proven otherwise. To exclude a specific model, add it to the list with tier `unsuitable` before the family entry (first match wins).

No regex. Simple string matching. Easy to reason about, easy to update.

---

## Component 2: Swarm Orchestrator

### `src/prep/core/swarm_orchestrator.py`

Generic three-phase executor. Knows nothing about Group Reasoning or any specific stage.

### Data Model

```python
@dataclass
class WorkItem:
    """A unit of work for the swarm."""
    id: str
    summary: str        # Short description for coordinator (what is this group?)
    full_context: str   # Full details for worker (epistemic data, edges, etc.)

@dataclass
class CoordinatorPlan:
    """Output of Phase 1 — how to scope each worker."""
    assignments: List[WorkerAssignment]

@dataclass  
class WorkerAssignment:
    """Scoped instructions for one worker."""
    item_id: str
    analysis_angle: str   # e.g. "Focus on API contract stability"
    priority_concerns: List[str]  # What to look for specifically

@dataclass
class WorkerResult:
    """Output of one worker sub-agent."""
    item_id: str
    raw_output: str       # The JSON response from the LLM
    success: bool

@dataclass
class SwarmResult:
    """Complete swarm output."""
    worker_results: List[WorkerResult]
    synthesis: Optional[str]   # Cross-cutting synthesis JSON
    coordinator_plan: CoordinatorPlan
    stats: SwarmStats

@dataclass
class SwarmStats:
    """Telemetry for the swarm run."""
    total_items: int
    workers_succeeded: int
    workers_failed: int
    coordinator_tokens: int
    worker_tokens: int
    synthesis_tokens: int
    wall_clock_seconds: float
```

### Three-Phase Execution

```
Phase 1: COORDINATE
  Input:  List of WorkItem summaries (NOT full context — keep coordinator prompt small)
  Prompt: Stage-specific coordinator prompt
  Output: CoordinatorPlan — one WorkerAssignment per item
  Calls:  1 LLM call (sequential, outside concurrency budget)
  
  If coordinator fails → FALLBACK to standard concurrent (no swarm)

Phase 2: FAN-OUT
  Input:  WorkItems + their WorkerAssignments
  Prompt: Stage-specific worker prompt template, injected with:
          - The item's full_context
          - The coordinator's analysis_angle and priority_concerns
  Output: List[WorkerResult]
  Calls:  N LLM calls, limited by llm_concurrency_deep
  
  If individual workers fail → proceed with partial results (existing behavior)

Phase 3: SYNTHESIZE
  Input:  All successful WorkerResults
  Prompt: Stage-specific synthesis prompt
  Output: Cross-cutting synthesis JSON
  Calls:  1 LLM call (sequential, outside concurrency budget)
  
  If synthesis fails → return worker results without synthesis (still better than no swarm)
```

### Concurrency Model

```
Existing concurrency budget: llm_concurrency_deep (e.g. 10)

Timeline with swarm (20 groups, concurrency=10):
  [coordinator: 1 call]
  [workers batch 1: 10 parallel] → [workers batch 2: 10 parallel]
  [synthesis: 1 call]

Timeline without swarm (20 groups, concurrency=10):
  [batch 1: 10 parallel] → [batch 2: 10 parallel]

Delta: +2 sequential LLM calls (coordinator + synthesis)
       ~same wall-clock for the parallel portion
```

### Failure Handling

Every phase has a fallback:

| Phase | Failure | Fallback |
|-------|---------|----------|
| Coordinator | LLM error, bad JSON, timeout | Skip swarm entirely → run standard concurrent path |
| Worker N | LLM error, bad JSON | Mark failed, continue with other workers (existing partial-result behavior) |
| Synthesis | LLM error, bad JSON | Return worker results without synthesis (still have per-group entries) |

No retries within the orchestrator. The existing `LLMClient` retry logic and `CloudRateLimitError` handling still apply to each individual call.

---

## Component 3: Group Reasoning Integration

### Changes to `GroupReasoningEngine`

The `run()` method (line ~404) gets a decision branch where it currently chooses concurrent vs sequential (line ~493):

```python
def run(self, progress_callback=None, cancel_token=None):
    # ... existing: load epistemic, edges, build groups, check staleness ...
    
    # NEW: Check swarm eligibility
    swarm_tier = get_swarm_tier(self.llm.provider, self.llm.model)
    swarm_enabled = self._get_swarm_setting()  # from pipeline settings
    use_swarm = (
        swarm_tier.can_coordinate
        and swarm_enabled
        and len(to_analyze) >= MIN_GROUPS_THRESHOLD  # 3
    )
    
    if use_swarm:
        results.update(self._run_swarm(to_analyze, epistemic, edges, 
                                        progress_callback, cancel_token))
    elif concurrency > 1 and len(to_analyze) > 1:
        # EXISTING concurrent path — completely unchanged
        ...
    else:
        # EXISTING sequential path — completely unchanged
        ...
```

### Coordinator Prompt (Group Reasoning)

```
You are a senior software architect planning a parallel codebase analysis.

Below are {n} file groups from a codebase. Each group is a cluster of 
files connected by imports, calls, or data flow.

## Groups:
{for each group: id, member file paths, architecture layers, domain tags}

## Task:
For each group, assign a SPECIFIC analysis angle based on what you see. 
Don't give generic instructions — tailor each to the group's apparent role.

Examples of good angles:
- "This looks like a request pipeline — focus on middleware ordering and error propagation"
- "This is a data access layer — focus on query patterns, N+1 risks, and transaction boundaries"
- "This group bridges UI and API — focus on contract stability and serialization boundaries"

Respond with JSON:
{
  "assignments": [
    {
      "item_id": "group:abc123",
      "analysis_angle": "specific focus for this group",
      "priority_concerns": ["specific thing 1", "specific thing 2"]
    }
  ]
}
```

### Worker Prompt (Group Reasoning)

The existing `GROUP_REASONING_PROMPT` (line 100) with an added section:

```
## Coordinator Guidance:
Analysis angle: {assignment.analysis_angle}
Priority concerns: {assignment.priority_concerns}

Pay special attention to the above. Your analysis should be shaped by 
this guidance while still covering the standard architectural assessment.
```

Everything else in the existing prompt stays the same — the worker still produces the same JSON schema (`pattern`, `data_flow`, `coupling_risks`, `blast_radius`, `architectural_insight`, `confidence`).

### Synthesis Prompt (Group Reasoning)

```
You are a senior software architect synthesizing architectural findings 
from {n} parallel group analyses of the same codebase.

## Group Analysis Results:
{for each group: id, pattern, data_flow, coupling_risks, blast_radius, insight}

## Task:
Look ACROSS these groups for:
1. Shared patterns — do multiple groups use the same architectural pattern?
2. Cross-group coupling — do groups reference each other's blast radius?
3. Data flow chains — does data flow from one group into another?
4. Systemic risks — are the same coupling risks appearing in multiple groups?
5. Architectural coherence — is the overall architecture consistent or fragmented?

Respond with JSON:
{
  "cross_group_patterns": ["pattern seen across multiple groups"],
  "shared_coupling_risks": ["risks that span group boundaries"],
  "data_flow_chains": ["group A → group B → group C via X"],
  "systemic_risks": ["risks appearing in 2+ groups"],
  "architectural_coherence": "1-2 sentence assessment",
  "key_insight": "The single most important finding from this cross-group analysis"
}
```

### Output

**Per-group output** — identical to today. Same `GroupReasoningEntry`, same JSONL file. Workers produce the same schema. The coordinator's scoped guidance just makes each entry higher quality.

**Synthesis output** — new file `trace_swarm_synthesis.json`:

```json
{
  "stage": "group_reasoning",
  "model": "kimi-k2.5",
  "swarm_tier": "both",
  "groups_analyzed": 12,
  "timestamp": "2026-04-07T...",
  "synthesis": {
    "cross_group_patterns": [...],
    "shared_coupling_risks": [...],
    "data_flow_chains": [...],
    "systemic_risks": [...],
    "architectural_coherence": "...",
    "key_insight": "..."
  },
  "stats": {
    "coordinator_tokens": 1234,
    "worker_tokens": 15678,
    "synthesis_tokens": 890,
    "wall_clock_seconds": 23.4
  }
}
```

Downstream stages (Clustering, Atlas) can optionally read this for richer context, but are not required to. It's additive.

---

## Component 4: Settings

### New Setting

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `swarm_enabled` | bool | `true` | Enable Agent Swarm when model supports it. Disable to save tokens. |

### Where It Lives

Same settings storage as other pipeline config (`prep_settings.db`). Exposed through the existing settings API. The dashboard can add a toggle to the pipeline settings panel.

### Decision Logic

```
swarm_enabled (setting) = true
  AND get_swarm_tier(provider, model).can_coordinate = true
  AND len(groups_to_analyze) >= 3
  → use swarm

Otherwise → use existing concurrent/sequential path (unchanged)
```

---

## Token Cost Model

For a codebase with 20 dependency groups, concurrency=10:

| Phase | Calls | Est. Input Tokens | Est. Output Tokens |
|-------|-------|-------------------|-------------------|
| Coordinator | 1 | ~2K (group summaries) | ~1K (assignments) |
| Workers | 20 (10+10 parallel) | ~3K each = 60K total | ~500 each = 10K total |
| Synthesis | 1 | ~5K (all worker results) | ~1K |
| **Swarm total** | **22** | **~67K** | **~12K** |
| **Standard total** | **20** | **~60K** | **~10K** |
| **Delta** | **+2 calls** | **+~7K (~12%)** | **+~2K (~20%)** |

The overhead is ~2 extra calls and ~15% more tokens. The quality gain (scoped analysis + cross-group synthesis) is the justification.

---

## Future Expansion

Once the swarm orchestrator is proven on Group Reasoning, other stages can opt in by providing their own coordinator/worker/synthesis prompts:

| Stage | Swarm Opportunity | Priority |
|-------|-------------------|----------|
| Atlas Generation (Stage 9) | Workspace segments as independent workers | Medium |
| Epistemic Enrichment (Stage 6) | Per-file analysis with role-aware scoping | Low |
| Pi Agent scenarios | Independent scenarios as parallel workers | Low |

Each stage just needs to build `WorkItem` objects and provide three prompts. The `SwarmOrchestrator` is reusable.

---

## Testing Strategy

1. **Unit tests for SwarmOrchestrator** — mock LLMClient, verify three-phase flow, test all failure/fallback paths
2. **Unit tests for swarm_registry** — verify model matching, default tier, JSON loading
3. **Integration test for Group Reasoning swarm path** — small fixture codebase with 4+ groups, verify output format matches non-swarm path
4. **A/B quality comparison** — run same codebase with swarm on/off, compare group reasoning output (manual review initially, automated metrics later)

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|-----------|
| Same model for coordinator + workers? | Yes — single model for now. Simpler. |
| UI exposure? | Toggle only (swarm_enabled). No threshold, no model picker. |
| Which stages? | Group Reasoning first. Others later via same wrapper. |
| Model detection? | Finite curated list in JSON. No auto-detection. |
| Failure handling? | Graceful fallback at every phase. No swarm > broken swarm. |
