# Phase 82: Swarm UI Accuracy + AIMD Gap Fixes

> Design spec
> Date: 2026-04-07
> Builds on: 01_Latency_Aware_Discovery.md, Phase 79 Swarm Orchestration
> Revised after codebase audit — AIMD core is already implemented

## Overview

The codebase audit revealed that **AIMD latency-aware discovery is already fully implemented** in the scheduler and LLM client for Ollama, OpenAI, and Anthropic providers. What remains are:

1. **Swarm UI accuracy** — API endpoints report `is_swarm` based on actual model capability, not just stage name. Worker counts reflect swarm's full budget during swarm-active stages.
2. **AIMD provider gaps** — Azure OpenAI and Google Gemini providers lack throughput recording.
3. **Duplicated constants** — `_SWARM_STAGES` defined independently in 2 files.
4. **Scheduler status API** — Expose AIMD state for observability.

### What Already Works (No Changes Needed)

| Component | Location | Status |
|-----------|----------|--------|
| `ComputeSlot` AIMD fields | `scheduler.py:50-89` | 7 fields, 3 properties, `__post_init__` |
| `dynamic_capacity` property | `scheduler.py:72-74` | `min(max_concurrent, current_limit)` |
| `has_capacity` uses `dynamic_capacity` | `scheduler.py:76-78` | Correct |
| `_record_throughput_for_slot()` | `scheduler.py:290-343` | Full AIMD: MD, AI, jumpstart, congestion avoidance, cooldown |
| `record_throughput()` | `scheduler.py:248-263` | Public node-based wrapper |
| `record_throughput_for_provider()` | `scheduler.py:265-288` | Provider→node routing |
| `_weighted_share()` headroom | `scheduler.py:649-651` | `max(1, slot.dynamic_capacity - 1)` |
| `full_budget_for_swarm()` | `scheduler.py:793-847` | Uses `slot.dynamic_capacity` at lines 820, 840 |
| `LLMClient._record_throughput()` | `llm_client.py:424-436` | Wrapper calling scheduler |
| Ollama timing extraction | `llm_client.py:619-698` | eval/prompt/load durations, queue_time_ms |
| OpenAI rate-limit headers | `llm_client.py:734-796` | `x-ratelimit-remaining-requests` |
| Anthropic rate-limit headers | `llm_client.py:815-864` | `anthropic-ratelimit-requests-remaining` |

---

## Part 1: Swarm UI Accuracy

### Problem

The `is_swarm` flag in both API endpoints is wrong:

**`llm.py:610`**: Sets `is_swarm` based solely on stage name in `_SWARM_STAGES`. Never checks model capability or swarm_enabled setting. Reports swarm for UNSUITABLE-tier models.

**`queue.py:88-93`**: Checks stage name + `swarm_enabled` setting, but never checks model capability. Also lacks access to provider/model info entirely.

**`concurrent_workers_for_project()` (scheduler.py:849-863)**: Always returns `_weighted_share()`, even during active swarm. The actual swarm uses `full_budget_for_swarm()` which returns the full undivided budget. So the UI shows a lower worker count than reality.

**`llm.py:627-636`**: Telemetry-tracked requests (agent_ops) get no `is_swarm` enrichment at all.

**Result**: UI shows blue "concurrent" badges when swarm is active, or shows "swarm" when the model isn't swarm-capable.

### Solution

#### 1.1 Shared constant: `SWARM_CAPABLE_STAGES`

Extract from duplicated string literals into the scheduler module, then import in both API routers.

```python
# scheduler.py (module-level)
SWARM_CAPABLE_STAGES: frozenset[str] = frozenset({"group_reasoning", "clustering", "atlas"})
```

Remove the local `_SWARM_STAGES` definitions in `llm.py:602` and `queue.py:89`.

#### 1.2 Shared helper: `is_swarm_active_for_stage()`

Location: `src/codrag/services/pipeline/scheduler.py`

```python
def is_swarm_active_for_stage(stage: str, provider: str, model: str) -> bool:
    """Check if a stage would use swarm orchestration with the given model.

    Mirrors the decision in GroupReasoningEngine.run(), ClusterSynthesizer,
    and AtlasGenerator — minus the min_groups check (not available at query time).
    """
    if stage not in SWARM_CAPABLE_STAGES:
        return False
    try:
        from codrag.core.swarm_registry import get_swarm_tier
        from codrag.services.settings_store import settings
        tier = get_swarm_tier(provider, model)
        return tier.can_coordinate and bool(settings.get("swarm_enabled", True))
    except Exception:
        return False
```

#### 1.3 Model resolution helper: `_resolve_model_for_stage()`

Both API endpoints need to resolve stage → provider + model. This logic already exists in the orchestrator's `_resolve_node_for_stage()` (orchestrator.py:1014-1048). Extract the provider/model resolution into a reusable helper:

```python
def _resolve_model_for_stage(project_id: str, stage: str) -> tuple[str, str] | None:
    """Resolve (provider, model) for a project's current stage.

    Walks: stage → model_slot → llm_config["{slot}_model"] → endpoint → provider.
    Returns None if resolution fails (no config, non-LLM stage, etc).
    """
    from codrag.services.pipeline.stages import STAGE_MODEL_SLOT, StageId
    try:
        stage_id = StageId(stage)
    except ValueError:
        return None
    slot_name = STAGE_MODEL_SLOT.get(stage_id)
    if not slot_name:
        return None
    try:
        from codrag.services.settings_store import settings
        llm_config = settings.get("llm_config") or {}
    except Exception:
        return None
    slot_config = llm_config.get(f"{slot_name}_model", {})
    endpoint_id = slot_config.get("endpoint_id")
    model = slot_config.get("model", "")
    if not endpoint_id or not model:
        return None
    provider = "ollama"
    for ep in llm_config.get("saved_endpoints", []):
        if ep.get("id") == endpoint_id:
            provider = ep.get("provider", "ollama")
            break
    return provider, model
```

Location: `src/codrag/api/routers/_llm_helpers.py` (new small module) or inline in the scheduler. Since both `llm.py` and `queue.py` need it, a shared location is cleaner.

#### 1.4 `concurrent_workers_for_project()` — swarm-aware

Add optional `stage` parameter. When stage is swarm-capable AND model is swarm-capable, return the full swarm budget instead of fair-share.

```python
def concurrent_workers_for_project(
    self, project_id: str, stage: str | None = None,
) -> Tuple[int, Optional[str]]:
    with self._lock:
        for nid, slot in self._slots.items():
            if project_id not in slot.active_stages:
                continue
            # Check if this is an active swarm stage
            if stage and stage in SWARM_CAPABLE_STAGES:
                resolved = _resolve_model_for_stage(project_id, stage)
                if resolved:
                    provider, model = resolved
                    if is_swarm_active_for_stage(stage, provider, model):
                        budget = max(1, slot.dynamic_capacity - 1)
                        return budget, nid
            return self._weighted_share(slot, project_id), nid
    return 1, None
```

#### 1.5 API endpoint fixes

**`llm.py:599-612`** — Pass stage, use model-aware swarm check:

```python
from codrag.services.pipeline.scheduler import (
    pipeline_scheduler, SWARM_CAPABLE_STAGES, is_swarm_active_for_stage,
)
for rt in running_tasks:
    workers, node_id = pipeline_scheduler.concurrent_workers_for_project(
        rt["project_id"], stage=rt.get("stage"),
    )
    rt["concurrent_workers"] = workers
    rt["compute_node"] = node_id
    # Model-aware swarm flag
    rt["is_swarm"] = False
    stage = rt.get("stage", "")
    if stage in SWARM_CAPABLE_STAGES:
        resolved = _resolve_model_for_stage(rt["project_id"], stage)
        if resolved:
            rt["is_swarm"] = is_swarm_active_for_stage(stage, *resolved)
```

**`queue.py:88-93`** — Same pattern:

```python
is_swarm = False
if current_stage and current_stage in SWARM_CAPABLE_STAGES:
    resolved = _resolve_model_for_stage(project_id, current_stage)
    if resolved:
        is_swarm = is_swarm_active_for_stage(current_stage, *resolved)
```

**`llm.py:627-636`** — Telemetry tasks: add `"is_swarm": False` to the dict. These are agent_ops tasks, never swarm stages.

#### 1.6 Files changed

| File | Change |
|------|--------|
| `src/codrag/services/pipeline/scheduler.py` | Add `SWARM_CAPABLE_STAGES`, `is_swarm_active_for_stage()`, update `concurrent_workers_for_project()` |
| `src/codrag/api/routers/llm.py` | Import shared constant, pass stage, model-aware `is_swarm`, fix telemetry tasks |
| `src/codrag/api/routers/queue.py` | Import shared constant, model-aware `is_swarm` |
| `src/codrag/api/routers/_llm_helpers.py` | New: `_resolve_model_for_stage()` helper |

No UI changes needed — the existing purple/blue badge logic is correct, it just needs accurate data from the API.

---

## Part 2: AIMD Provider Gaps

### Problem

Azure OpenAI (`llm_client.py:884-932`) and Google Gemini (`llm_client.py:934-976`) providers are missing:
- Wall-time capture (`time.monotonic()` before/after request)
- Rate-limit header extraction
- `_record_throughput()` calls on success and failure

Without these, AIMD cannot discover the concurrency ceiling for these providers. They fall back to the static `max_concurrent` from settings.

### Solution

Add the same timing/reporting pattern that Ollama, OpenAI, and Anthropic already use.

#### 2.1 Azure OpenAI (`llm_client.py:884-932`)

```python
t0 = time.monotonic()
try:
    resp = requests.post(url, json=payload, headers=headers, params=params, timeout=self.timeout)
    t1 = time.monotonic()
    wall_time_ms = (t1 - t0) * 1000.0

    # Azure uses same headers as OpenAI
    rate_limit_remaining = None
    srem = resp.headers.get("x-ratelimit-remaining-requests")
    if srem and srem.isdigit():
        rate_limit_remaining = int(srem)

    if resp.status_code == 429:
        self._record_throughput(is_429_or_timeout=True)
        # ... existing retry logic
    else:
        resp.raise_for_status()
        self._record_throughput(
            queue_time_ms=wall_time_ms,
            rate_limit_remaining=rate_limit_remaining,
        )
except (requests.Timeout, requests.ConnectionError):
    self._record_throughput(is_429_or_timeout=True)
    raise
```

#### 2.2 Google Gemini (`llm_client.py:934-976`)

```python
t0 = time.monotonic()
try:
    resp = requests.post(url, json=payload, params=params, timeout=self.timeout)
    t1 = time.monotonic()
    wall_time_ms = (t1 - t0) * 1000.0

    if resp.status_code == 429:
        self._record_throughput(is_429_or_timeout=True)
        # ... existing retry logic
    else:
        resp.raise_for_status()
        self._record_throughput(queue_time_ms=wall_time_ms)
except (requests.Timeout, requests.ConnectionError):
    self._record_throughput(is_429_or_timeout=True)
    raise
```

Note: Google Gemini API doesn't expose `x-ratelimit-remaining` headers in the same way. We rely on wall-time and 429 detection only.

#### 2.3 Files changed

| File | Change |
|------|--------|
| `src/codrag/core/llm_client.py` | Add timing + `_record_throughput()` to Azure OpenAI and Google Gemini providers |

---

## Part 3: Scheduler Status API Enhancement

### Problem

The scheduler `status()` method (line 865) exposes `max_concurrent` and `current_load` but not the AIMD state. Operators and the dashboard can't see whether discovery is in jumpstart or congestion avoidance, what the current discovered limit is, or recent queue times.

### Solution

Add AIMD fields to the status dict:

```python
nodes[nid] = {
    "max_concurrent": slot.max_concurrent,
    "dynamic_capacity": slot.dynamic_capacity,
    "aimd_mode": slot.mode,
    "current_limit": slot.current_limit,
    "recent_queue_ms": round(slot.last_queue_time_ms, 1),
    "current_load": slot.current_load,
    "active": dict(slot.active_stages),
    "queued": [...],
}
```

#### Files changed

| File | Change |
|------|--------|
| `src/codrag/services/pipeline/scheduler.py` | Add AIMD fields to `status()` dict |

---

## Integration: How It All Connects

```
LLMClient call completes (ALREADY WORKING for Ollama/OpenAI/Anthropic)
    │
    ├── Ollama: queue_time_ms from eval/prompt/load durations
    ├── OpenAI: x-ratelimit-remaining-requests header
    ├── Anthropic: anthropic-ratelimit-requests-remaining header
    ├── Azure: x-ratelimit-remaining-requests header (NEW)
    ├── Gemini: wall-time + 429 detection (NEW)
    │
    ▼
scheduler.record_throughput_for_provider() → _record_throughput_for_slot()
    │
    ▼
AIMD adjusts slot.current_limit → dynamic_capacity changes
    │
    ├── _weighted_share() reads dynamic_capacity (batch stages)
    ├── full_budget_for_swarm() reads dynamic_capacity (swarm stages)
    │
    ▼
API endpoints (FIXED):
    ├── concurrent_workers_for_project(stage=...) → swarm budget when appropriate
    ├── is_swarm = is_swarm_active_for_stage() → checks model registry
    │
    ▼
UI renders correctly:
    ├── Purple "N×Swarm" for swarm-capable model on swarm stage
    ├── Blue "N×" for concurrent stages
    ├── No badge when workers=1
```

---

## Summary of All Changes

| # | File | What | Lines |
|---|------|------|-------|
| 1 | `scheduler.py` | `SWARM_CAPABLE_STAGES` constant | new, module-level |
| 2 | `scheduler.py` | `is_swarm_active_for_stage()` helper | new function |
| 3 | `scheduler.py` | `concurrent_workers_for_project()` accepts `stage`, returns swarm budget | modify ~849-863 |
| 4 | `scheduler.py` | `status()` exposes AIMD fields | modify ~865-890 |
| 5 | `_llm_helpers.py` | `_resolve_model_for_stage()` helper | new file (~40 lines) |
| 6 | `llm.py` | Import shared constant, model-aware `is_swarm`, fix telemetry tasks | modify ~599-636 |
| 7 | `queue.py` | Import shared constant, model-aware `is_swarm` | modify ~85-95 |
| 8 | `llm_client.py` | Azure OpenAI: timing + `_record_throughput()` | modify ~884-932 |
| 9 | `llm_client.py` | Google Gemini: timing + `_record_throughput()` | modify ~934-976 |

**Total**: ~4 files modified, 1 small file created. No UI changes. No new dependencies.

---

## Testing Strategy

1. **Unit: `is_swarm_active_for_stage()`** — test with kimi/ollama (→ True), unknown-model/ollama (→ False), kimi/ollama + swarm_enabled=False (→ False), non-swarm stage (→ False)
2. **Unit: `concurrent_workers_for_project(stage=...)`** — verify swarm stage returns full budget, non-swarm returns weighted share
3. **Unit: `_resolve_model_for_stage()`** — test with valid config, missing endpoint, non-LLM stage
4. **Unit: Azure/Gemini throughput recording** — mock responses, verify `_record_throughput()` called with correct args
5. **Manual: Run pipeline with kimi2.5:cloud** — verify purple "N×Swarm" badge appears at group_reasoning, blue "N×" at catalogue

---

## Out of Scope

- UI changes to display AIMD state (future: show discovery progress in AI Gateway)
- Dashboard node detail panel showing AIMD metrics
- min_groups_threshold check in API (would require knowing item count — not available at query time)
- LM Studio provider throughput recording (low priority, similar pattern)
