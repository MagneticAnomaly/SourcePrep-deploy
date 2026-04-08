# Phase 82: Swarm UI Accuracy + AIMD Gap Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the UI accurately show swarm vs concurrent mode by checking model capability, and fill AIMD throughput reporting gaps in Azure/Gemini providers.

**Architecture:** Add `SWARM_CAPABLE_STAGES` constant and `is_swarm_active_for_stage()` helper to the scheduler module. Add `resolve_model_for_stage()` to a shared helper. Update `concurrent_workers_for_project()` to return the full swarm budget for swarm-active stages. Patch both API routers to use model-aware logic. Add `_record_throughput()` to Azure/Gemini LLM providers.

**Tech Stack:** Python 3.11, FastAPI, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/codrag/services/pipeline/scheduler.py` | Modify | Add `SWARM_CAPABLE_STAGES`, `is_swarm_active_for_stage()`, update `concurrent_workers_for_project()`, update `status()` |
| `src/codrag/api/routers/_llm_helpers.py` | Create | `resolve_model_for_stage()` — shared provider/model resolution |
| `src/codrag/api/routers/queue.py` | Modify | Model-aware `is_swarm` flag |
| `src/codrag/api/routers/llm.py` | Modify | Model-aware `is_swarm` flag, pass `stage` to scheduler, fix telemetry tasks |
| `src/codrag/core/llm_client.py` | Modify | Add `_record_throughput()` to Azure OpenAI and Google Gemini providers |
| `tests/test_pipeline_scheduler.py` | Modify | Tests for `is_swarm_active_for_stage()` and swarm-aware `concurrent_workers_for_project()` |
| `tests/test_llm_helpers.py` | Create | Tests for `resolve_model_for_stage()` |
| `tests/test_llm_client_throughput.py` | Create | Tests for Azure/Gemini throughput recording |

---

### Task 1: Shared Constant + Swarm Helper in Scheduler

**Files:**
- Modify: `src/codrag/services/pipeline/scheduler.py:44-48` (module-level, after imports)
- Modify: `src/codrag/services/pipeline/scheduler.py:849-863` (concurrent_workers_for_project)
- Test: `tests/test_pipeline_scheduler.py`

- [ ] **Step 1: Write failing tests for `is_swarm_active_for_stage()`**

Add to `tests/test_pipeline_scheduler.py`:

```python
from codrag.services.pipeline.scheduler import (
    SWARM_CAPABLE_STAGES,
    is_swarm_active_for_stage,
)


class TestSwarmCapableStages:

    def test_group_reasoning_in_set(self):
        assert "group_reasoning" in SWARM_CAPABLE_STAGES

    def test_clustering_in_set(self):
        assert "clustering" in SWARM_CAPABLE_STAGES

    def test_atlas_in_set(self):
        assert "atlas" in SWARM_CAPABLE_STAGES

    def test_enrichment_not_in_set(self):
        assert "enrichment" not in SWARM_CAPABLE_STAGES

    def test_catalogue_not_in_set(self):
        assert "catalogue" not in SWARM_CAPABLE_STAGES


class TestIsSwarmActiveForStage:

    def test_kimi_on_ollama_group_reasoning(self):
        assert is_swarm_active_for_stage("group_reasoning", "ollama", "kimi-k2.5:cloud") is True

    def test_kimi_on_ollama_clustering(self):
        assert is_swarm_active_for_stage("clustering", "ollama", "kimi-k2.5:cloud") is True

    def test_kimi_on_ollama_atlas(self):
        assert is_swarm_active_for_stage("atlas", "ollama", "kimi-k2.5:cloud") is True

    def test_kimi_on_ollama_non_swarm_stage(self):
        assert is_swarm_active_for_stage("enrichment", "ollama", "kimi-k2.5:cloud") is False

    def test_unsuitable_model_returns_false(self):
        assert is_swarm_active_for_stage("group_reasoning", "ollama", "llama3.3:70b") is False

    def test_claude_sonnet_on_anthropic(self):
        assert is_swarm_active_for_stage("group_reasoning", "anthropic", "claude-sonnet-4.6") is True

    def test_unknown_provider_returns_false(self):
        assert is_swarm_active_for_stage("group_reasoning", "lm-studio", "kimi-k2.5") is False

    def test_swarm_disabled_setting(self, monkeypatch):
        """When swarm_enabled=False in settings, always returns False."""
        from codrag.services import settings_store
        original_get = settings_store.settings.get

        def mock_get(key, default=None):
            if key == "swarm_enabled":
                return False
            return original_get(key, default)

        monkeypatch.setattr(settings_store.settings, "get", mock_get)
        assert is_swarm_active_for_stage("group_reasoning", "ollama", "kimi-k2.5:cloud") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py::TestSwarmCapableStages -v && .venv/bin/pytest tests/test_pipeline_scheduler.py::TestIsSwarmActiveForStage -v`
Expected: ImportError — `SWARM_CAPABLE_STAGES` and `is_swarm_active_for_stage` don't exist yet.

- [ ] **Step 3: Implement `SWARM_CAPABLE_STAGES` and `is_swarm_active_for_stage()`**

In `src/codrag/services/pipeline/scheduler.py`, add after the existing imports (around line 44, after `logger = logging.getLogger(__name__)`):

```python
# Stages that can use swarm orchestration (coordinator → fan-out → synthesis).
# Shared constant — imported by queue.py and llm.py routers to avoid duplication.
SWARM_CAPABLE_STAGES: frozenset = frozenset({"group_reasoning", "clustering", "atlas"})


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

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py::TestSwarmCapableStages tests/test_pipeline_scheduler.py::TestIsSwarmActiveForStage -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline/scheduler.py tests/test_pipeline_scheduler.py
git commit -m "feat(scheduler): add SWARM_CAPABLE_STAGES constant and is_swarm_active_for_stage() helper

Phase 82: Shared swarm decision logic for API endpoints to check
model capability via the swarm registry, instead of just checking
stage names."
```

---

### Task 2: `resolve_model_for_stage()` Shared Helper

**Files:**
- Create: `src/codrag/api/routers/_llm_helpers.py`
- Create: `tests/test_llm_helpers.py`

- [ ] **Step 1: Write failing test for `resolve_model_for_stage()`**

Create `tests/test_llm_helpers.py`:

```python
"""Tests for shared LLM router helpers."""
import pytest
from unittest.mock import patch, MagicMock


class TestResolveModelForStage:

    def test_non_llm_stage_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "structural") is None

    def test_knowledge_stage_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "knowledge") is None

    def test_invalid_stage_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "bogus_stage") is None

    def test_resolves_large_slot_model(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "large_model": {
                "endpoint_id": "ep-1",
                "model": "kimi-k2.5:cloud",
            },
            "saved_endpoints": [
                {"id": "ep-1", "provider": "ollama"},
            ],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "group_reasoning")
            assert result == ("ollama", "kimi-k2.5:cloud")

    def test_resolves_small_slot_model(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "small_model": {
                "endpoint_id": "ep-2",
                "model": "gpt-5.1-mini",
            },
            "saved_endpoints": [
                {"id": "ep-2", "provider": "openai"},
            ],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "catalogue")
            assert result == ("openai", "gpt-5.1-mini")

    def test_missing_endpoint_id_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "large_model": {"model": "kimi-k2.5:cloud"},
            "saved_endpoints": [],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            assert resolve_model_for_stage("proj-1", "group_reasoning") is None

    def test_missing_model_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "large_model": {"endpoint_id": "ep-1"},
            "saved_endpoints": [{"id": "ep-1", "provider": "ollama"}],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            assert resolve_model_for_stage("proj-1", "group_reasoning") is None

    def test_defaults_provider_to_ollama(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "large_model": {
                "endpoint_id": "ep-1",
                "model": "kimi-k2.5:cloud",
            },
            "saved_endpoints": [
                {"id": "ep-1"},  # no provider field
            ],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "group_reasoning")
            assert result == ("ollama", "kimi-k2.5:cloud")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_llm_helpers.py -v`
Expected: ImportError — module doesn't exist yet.

- [ ] **Step 3: Implement `resolve_model_for_stage()`**

Create `src/codrag/api/routers/_llm_helpers.py`:

```python
"""Shared helpers for LLM-related API routers.

Phase 82: Provides model resolution so queue.py and llm.py can
determine provider/model for a project's current pipeline stage
without duplicating the slot → endpoint → provider resolution chain.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy import — avoids circular dependency at module load
_settings = None


def _get_settings():
    global _settings
    if _settings is None:
        from codrag.services.settings_store import settings as _s
        _settings = _s
    return _settings


# Make patchable for tests
try:
    from codrag.services.settings_store import settings
except ImportError:
    settings = None  # type: ignore[assignment]


def resolve_model_for_stage(
    project_id: str,
    stage: str,
) -> Optional[Tuple[str, str]]:
    """Resolve (provider, model) for a project's current pipeline stage.

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_llm_helpers.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/api/routers/_llm_helpers.py tests/test_llm_helpers.py
git commit -m "feat(api): add resolve_model_for_stage() helper

Phase 82: Shared helper for queue.py and llm.py routers to resolve
stage → model slot → endpoint → provider/model without duplicating
the resolution chain."
```

---

### Task 3: Swarm-Aware `concurrent_workers_for_project()`

**Files:**
- Modify: `src/codrag/services/pipeline/scheduler.py:849-863`
- Test: `tests/test_pipeline_scheduler.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_pipeline_scheduler.py`:

```python
from unittest.mock import patch


class TestConcurrentWorkersSwarmAware:

    def test_swarm_stage_returns_full_budget(self):
        """When stage is swarm-capable and model supports swarm,
        return full dynamic_capacity - 1, not weighted share."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 12)
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")

        mock_config = {
            "large_model": {"endpoint_id": "ep-1", "model": "kimi-k2.5:cloud"},
            "saved_endpoints": [{"id": "ep-1", "provider": "ollama"}],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            workers, node_id = sched.concurrent_workers_for_project(
                "proj-a", stage="group_reasoning",
            )
        assert node_id == "cloud:ep-1"
        # full budget = dynamic_capacity - 1 = 12 - 1 = 11
        assert workers == 11

    def test_non_swarm_stage_returns_weighted_share(self):
        """Non-swarm stages still use weighted share."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")

        workers, node_id = sched.concurrent_workers_for_project(
            "proj-a", stage="enrichment",
        )
        assert node_id == "cloud:ep-1"
        # Single project: weighted share = dynamic_capacity - 1 = min(10, 5) - 1 = 4
        # (AIMD starts at current_limit=5, so dynamic_capacity = min(10, 5) = 5)
        assert workers >= 1

    def test_no_stage_returns_weighted_share(self):
        """When stage is None (backward compat), use weighted share."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.CATALOGUE, "cloud:ep-1")

        workers, _ = sched.concurrent_workers_for_project("proj-a")
        assert workers >= 1

    def test_unsuitable_model_on_swarm_stage_returns_weighted_share(self):
        """Swarm stage with unsuitable model falls back to weighted share."""
        sched = PipelineScheduler()
        sched.configure_node("local:ep-1", 1)
        sched.acquire("proj-a", StageId.GROUP_REASONING, "local:ep-1")

        mock_config = {
            "large_model": {"endpoint_id": "ep-1", "model": "llama3.3:70b"},
            "saved_endpoints": [{"id": "ep-1", "provider": "ollama"}],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            workers, _ = sched.concurrent_workers_for_project(
                "proj-a", stage="group_reasoning",
            )
        # Unsuitable model → weighted share, not swarm budget
        assert workers == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py::TestConcurrentWorkersSwarmAware -v`
Expected: FAIL — `concurrent_workers_for_project` doesn't accept `stage` parameter.

- [ ] **Step 3: Update `concurrent_workers_for_project()`**

In `src/codrag/services/pipeline/scheduler.py`, replace lines 849-863:

```python
    def concurrent_workers_for_project(
        self, project_id: str, stage: Optional[str] = None,
    ) -> Tuple[int, Optional[str]]:
        """Return (concurrent_worker_count, node_id) for a project.

        Used by the AI Gateway UI to display how many parallel LLM
        calls a stage is making.  Returns (1, None) if the project
        isn't found in any active slot.

        Phase 82: When ``stage`` is a swarm-capable stage and the
        model supports swarm, returns the full undivided budget
        instead of the weighted fair-share.
        """
        with self._lock:
            for nid, slot in self._slots.items():
                if project_id not in slot.active_stages:
                    continue
                # Phase 82: Check if this is an active swarm stage
                if stage and stage in SWARM_CAPABLE_STAGES:
                    try:
                        from codrag.api.routers._llm_helpers import resolve_model_for_stage
                        resolved = resolve_model_for_stage(project_id, stage)
                        if resolved and is_swarm_active_for_stage(stage, *resolved):
                            budget = max(1, slot.dynamic_capacity - 1)
                            return budget, nid
                    except Exception:
                        pass  # Fall through to weighted share
                return self._weighted_share(slot, project_id), nid
        return 1, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py::TestConcurrentWorkersSwarmAware -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline/scheduler.py tests/test_pipeline_scheduler.py
git commit -m "feat(scheduler): swarm-aware concurrent_workers_for_project()

Phase 82: Returns full undivided budget for swarm-capable stages
when the model supports swarm, instead of always returning the
weighted fair-share."
```

---

### Task 4: Fix `queue.py` — Model-Aware `is_swarm`

**Files:**
- Modify: `src/codrag/api/routers/queue.py:82-95`

- [ ] **Step 1: Update `_build_queue_item()` in queue.py**

Replace lines 82-95 of `src/codrag/api/routers/queue.py`:

```python
    priority = pipeline_scheduler.get_priority(project_id)
    workers, node_id = pipeline_scheduler.concurrent_workers_for_project(
        project_id, stage=current_stage,
    )

    # Phase 82: Determine swarm mode from actual model capability,
    # not just stage name.
    is_swarm = False
    if current_stage:
        try:
            from codrag.services.pipeline.scheduler import SWARM_CAPABLE_STAGES, is_swarm_active_for_stage
            from codrag.api.routers._llm_helpers import resolve_model_for_stage
            if current_stage in SWARM_CAPABLE_STAGES:
                resolved = resolve_model_for_stage(project_id, current_stage)
                if resolved:
                    is_swarm = is_swarm_active_for_stage(current_stage, *resolved)
        except Exception:
            pass
```

This replaces the old code that defined a local `_SWARM_STAGES` and only checked `settings.get("swarm_enabled")`.

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `.venv/bin/pytest tests/ -k "queue" -v --timeout=30`
Expected: All existing tests still PASS.

- [ ] **Step 3: Commit**

```bash
git add src/codrag/api/routers/queue.py
git commit -m "fix(queue): model-aware is_swarm flag

Phase 82: Queue API now checks the swarm registry for model
capability instead of assuming all swarm-capable stages are swarming."
```

---

### Task 5: Fix `llm.py` — Model-Aware `is_swarm` + Telemetry Fix

**Files:**
- Modify: `src/codrag/api/routers/llm.py:599-636`

- [ ] **Step 1: Update running_tasks enrichment in llm.py**

Replace lines 599-636 of `src/codrag/api/routers/llm.py`:

```python
        # Enrich running tasks with concurrent worker count from scheduler
        try:
            from codrag.services.pipeline.scheduler import (
                pipeline_scheduler, SWARM_CAPABLE_STAGES, is_swarm_active_for_stage,
            )
            from codrag.api.routers._llm_helpers import resolve_model_for_stage
            for rt in running_tasks:
                workers, node_id = pipeline_scheduler.concurrent_workers_for_project(
                    rt["project_id"], stage=rt.get("stage"),
                )
                rt["concurrent_workers"] = workers
                rt["compute_node"] = node_id
                # Phase 82: Model-aware swarm flag
                rt["is_swarm"] = False
                stage = rt.get("stage", "")
                if stage in SWARM_CAPABLE_STAGES:
                    resolved = resolve_model_for_stage(rt["project_id"], stage)
                    if resolved:
                        rt["is_swarm"] = is_swarm_active_for_stage(stage, *resolved)
        except Exception:
            pass  # Scheduler not available — leave defaults

        # [Goal 3] Merge live telemetry active requests that bypass the orchestrator
        from codrag.services.token_telemetry import telemetry
        for req in telemetry.get_active_requests():
            # Skip if already tracked by orchestrator logic
            if any(rt["project_id"] == req["project_id"] and rt.get("task_id") == req["task_id"] for rt in running_tasks):
                continue
            proj_name = req["project_id"]
            try:
                p = registry.get_project(req["project_id"])
                if p:
                    proj_name = p.name
            except Exception:
                pass
            running_tasks.append({
                "task_id": req["task_id"] or "agent_call",
                "project_id": req["project_id"],
                "project_name": proj_name,
                "group": "agent_ops",
                "stage": req["task_id"],
                "model_slot": req["model_slot"] or "large_model",
                "concurrent_workers": 1,
                "compute_node": "local",
                "is_swarm": False,
            })
```

Key changes:
- Imports `SWARM_CAPABLE_STAGES` and `is_swarm_active_for_stage` from scheduler
- Passes `stage=rt.get("stage")` to `concurrent_workers_for_project()`
- Uses `resolve_model_for_stage()` + `is_swarm_active_for_stage()` for the flag
- Adds `"is_swarm": False` to telemetry tasks (they're never swarm)

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `.venv/bin/pytest tests/ -k "llm" -v --timeout=30`
Expected: All existing tests still PASS.

- [ ] **Step 3: Commit**

```bash
git add src/codrag/api/routers/llm.py
git commit -m "fix(llm): model-aware is_swarm flag + telemetry task fix

Phase 82: LLM slots API now checks swarm registry for model capability.
Telemetry-tracked tasks now include is_swarm: false."
```

---

### Task 6: Scheduler `status()` — Expose AIMD State

**Files:**
- Modify: `src/codrag/services/pipeline/scheduler.py:865-891`
- Test: `tests/test_pipeline_scheduler.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_pipeline_scheduler.py`:

```python
class TestSchedulerStatusAIMD:

    def test_status_includes_aimd_fields(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        status = sched.status()
        node = status["nodes"]["cloud:ep-1"]
        assert "aimd_mode" in node
        assert "current_limit" in node
        assert "last_queue_time_ms" in node
        assert node["aimd_mode"] == "jumpstart"
        assert node["current_limit"] == 5  # default
        assert node["last_queue_time_ms"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py::TestSchedulerStatusAIMD -v`
Expected: FAIL — `aimd_mode` not in node dict.

- [ ] **Step 3: Update `status()` method**

In `src/codrag/services/pipeline/scheduler.py`, replace the node dict construction inside `status()` (lines 871-884):

```python
                nodes[nid] = {
                    "max_concurrent": slot.max_concurrent,
                    "dynamic_capacity": slot.dynamic_capacity,
                    "current_load": slot.current_load,
                    "aimd_mode": slot.mode,
                    "current_limit": slot.current_limit,
                    "last_queue_time_ms": round(slot.last_queue_time_ms, 1) if hasattr(slot, 'last_queue_time_ms') else 0.0,
                    "active": dict(slot.active_stages),
                    "queued": [
                        {
                            "project_id": e.project_id,
                            "stage": e.stage.value,
                            "waiting_seconds": round(time.time() - e.enqueued_at, 1),
                        }
                        for e in queue
                    ],
                }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py::TestSchedulerStatusAIMD -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline/scheduler.py tests/test_pipeline_scheduler.py
git commit -m "feat(scheduler): expose AIMD state in status() API

Phase 82: Status endpoint now includes aimd_mode, current_limit,
and last_queue_time_ms for each compute node."
```

---

### Task 7: Azure OpenAI — Throughput Recording

**Files:**
- Modify: `src/codrag/core/llm_client.py:884-932` (azure-openai provider block)
- Test: `tests/test_llm_client_throughput.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_llm_client_throughput.py`:

```python
"""Tests for LLM client throughput recording (Phase 82 provider gaps)."""
import pytest
import time
from unittest.mock import patch, MagicMock

from codrag.core.llm_client import LLMClient


class TestAzureOpenAIThroughput:

    def _make_client(self):
        return LLMClient(
            provider="azure-openai",
            endpoint_url="https://test.openai.azure.com",
            model="gpt-4o",
            api_key="test-key",
        )

    @patch("codrag.core.llm_client.requests.post")
    def test_records_throughput_on_success(self, mock_post):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"x-ratelimit-remaining-requests": "42"}
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_post.return_value = mock_resp

        with patch.object(client, "_record_throughput") as mock_record:
            client.generate("test prompt")
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            # Should have queue_time_ms and rate_limit_remaining
            assert "queue_time_ms" in call_kwargs.kwargs or len(call_kwargs.args) > 0
            assert call_kwargs.kwargs.get("rate_limit_remaining") == 42

    @patch("codrag.core.llm_client.requests.post")
    def test_records_429_on_rate_limit(self, mock_post):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        mock_resp.json.return_value = {"error": {"message": "rate limited"}}
        mock_resp.raise_for_status.side_effect = Exception("429")
        mock_post.return_value = mock_resp

        with patch.object(client, "_record_throughput") as mock_record:
            with pytest.raises(Exception):
                client.generate("test prompt")
            # Should have recorded the 429
            assert any(
                c.kwargs.get("is_429_or_timeout") is True
                for c in mock_record.call_args_list
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_llm_client_throughput.py::TestAzureOpenAIThroughput -v`
Expected: FAIL — `_record_throughput` never called (no timing code in azure block).

- [ ] **Step 3: Add throughput recording to Azure OpenAI provider**

In `src/codrag/core/llm_client.py`, replace lines 914-916 (the `requests.post` + `raise_for_status` + `json` block inside the azure-openai branch):

```python
            t0 = time.monotonic()
            try:
                resp = requests.post(url, json=payload, headers=headers, params=params, timeout=self.timeout)
                t1 = time.monotonic()
                wall_time_ms = (t1 - t0) * 1000.0

                # Parse rate-limit headers (Azure uses same as OpenAI)
                rate_limit_remaining = None
                srem = resp.headers.get("x-ratelimit-remaining-requests")
                if srem and srem.isdigit():
                    rate_limit_remaining = int(srem)

                if resp.status_code == 429:
                    self._record_throughput(is_429_or_timeout=True)
                    resp.raise_for_status()

                resp.raise_for_status()
                self._record_throughput(
                    queue_time_ms=wall_time_ms,
                    rate_limit_remaining=rate_limit_remaining,
                )
            except (requests.Timeout, requests.ConnectionError):
                self._record_throughput(is_429_or_timeout=True)
                raise

            data = resp.json()
```

Also add `import time` at the top of the file if not already present (it is — verify at line ~10).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_llm_client_throughput.py::TestAzureOpenAIThroughput -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/llm_client.py tests/test_llm_client_throughput.py
git commit -m "feat(llm): add throughput recording to Azure OpenAI provider

Phase 82: Azure OpenAI now reports wall-time, rate-limit headers,
and 429/timeout events to the AIMD scheduler."
```

---

### Task 8: Google Gemini — Throughput Recording

**Files:**
- Modify: `src/codrag/core/llm_client.py:958-960` (google provider block)
- Test: `tests/test_llm_client_throughput.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_llm_client_throughput.py`:

```python
class TestGoogleGeminiThroughput:

    def _make_client(self):
        return LLMClient(
            provider="google",
            endpoint_url="https://generativelanguage.googleapis.com",
            model="gemini-2.5-pro",
            api_key="test-key",
        )

    @patch("codrag.core.llm_client.requests.post")
    def test_records_throughput_on_success(self, mock_post):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "hello"}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }
        mock_post.return_value = mock_resp

        with patch.object(client, "_record_throughput") as mock_record:
            client.generate("test prompt")
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert "queue_time_ms" in call_kwargs.kwargs or len(call_kwargs.args) > 0

    @patch("codrag.core.llm_client.requests.post")
    def test_records_429_on_rate_limit(self, mock_post):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        mock_resp.raise_for_status.side_effect = Exception("429")
        mock_post.return_value = mock_resp

        with patch.object(client, "_record_throughput") as mock_record:
            with pytest.raises(Exception):
                client.generate("test prompt")
            assert any(
                c.kwargs.get("is_429_or_timeout") is True
                for c in mock_record.call_args_list
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_llm_client_throughput.py::TestGoogleGeminiThroughput -v`
Expected: FAIL — `_record_throughput` never called.

- [ ] **Step 3: Add throughput recording to Google Gemini provider**

In `src/codrag/core/llm_client.py`, replace lines 958-960 (the `requests.post` + `raise_for_status` + `json` block inside the google branch):

```python
            t0 = time.monotonic()
            try:
                resp = requests.post(url, json=payload, params=params, timeout=self.timeout)
                t1 = time.monotonic()
                wall_time_ms = (t1 - t0) * 1000.0

                if resp.status_code == 429:
                    self._record_throughput(is_429_or_timeout=True)
                    resp.raise_for_status()

                resp.raise_for_status()
                self._record_throughput(queue_time_ms=wall_time_ms)
            except (requests.Timeout, requests.ConnectionError):
                self._record_throughput(is_429_or_timeout=True)
                raise

            data = resp.json()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_llm_client_throughput.py::TestGoogleGeminiThroughput -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/llm_client.py tests/test_llm_client_throughput.py
git commit -m "feat(llm): add throughput recording to Google Gemini provider

Phase 82: Gemini now reports wall-time and 429/timeout events
to the AIMD scheduler."
```

---

### Task 9: Full Test Suite + Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py tests/test_llm_helpers.py tests/test_llm_client_throughput.py tests/test_swarm_registry.py -v`
Expected: All PASS.

- [ ] **Step 2: Run broader regression check**

Run: `.venv/bin/pytest tests/ -x --timeout=60 -q`
Expected: No regressions.

- [ ] **Step 3: Final commit with all changes**

```bash
git add -A
git status
# If any unstaged changes remain, commit them:
git commit -m "chore: Phase 82 — swarm UI accuracy + AIMD provider gaps

- SWARM_CAPABLE_STAGES shared constant (eliminates duplication)
- is_swarm_active_for_stage() checks model registry
- concurrent_workers_for_project(stage=) returns swarm budget
- queue.py + llm.py use model-aware is_swarm flag
- Azure OpenAI + Google Gemini throughput recording
- Scheduler status() exposes AIMD state"
```
