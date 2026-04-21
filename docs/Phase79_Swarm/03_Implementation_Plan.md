# Agent Swarm Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add agent swarm orchestration to Prep's Group Reasoning stage — a coordinator decomposes work, parallel workers execute with scoped roles, and a synthesis step finds cross-cutting patterns.

**Architecture:** Stage-level wrapper pattern (Approach A). New `SwarmOrchestrator` class handles the three-phase flow generically. Group Reasoning opts in when the model is in a finite supported list and there are 3+ groups. All existing pipeline code paths remain untouched when swarm is inactive.

**Tech Stack:** Python 3.11+, `concurrent.futures.ThreadPoolExecutor` (matches existing Group Reasoning concurrency), `LLMClient.generate()` for all LLM calls, `SettingsStore` for the toggle, JSON for the model registry.

**Spec:** `docs/Phase79_Swarm/02_Swarm_Integration_Design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/prep/data/swarm_models.json` | Create | Finite list of swarm-capable models |
| `src/prep/core/swarm_registry.py` | Create | Load JSON, expose `get_swarm_tier()` |
| `src/prep/core/swarm_orchestrator.py` | Create | Three-phase swarm executor (coordinator → fan-out → synthesis) |
| `src/prep/core/group_reasoning.py` | Modify | Add `_run_swarm()` method, decision branch in `run()` |
| `tests/test_swarm_registry.py` | Create | Registry lookup tests |
| `tests/test_swarm_orchestrator.py` | Create | Three-phase flow tests with mocked LLM |
| `tests/test_group_reasoning_swarm.py` | Create | Integration test for swarm path in Group Reasoning |

---

### Task 1: Swarm Model Registry

**Files:**
- Create: `src/prep/data/swarm_models.json`
- Create: `src/prep/core/swarm_registry.py`
- Create: `tests/test_swarm_registry.py`

- [ ] **Step 1: Create the data directory and JSON registry**

```bash
mkdir -p src/prep/data
```

Write `src/prep/data/swarm_models.json`:

```json
{
  "version": "0.1.0",
  "last_reviewed": "2026-04-07",
  "min_groups_threshold": 3,
  "models": [
    {
      "id": "kimi-k2.5",
      "providers": ["ollama"],
      "contains": "kimi",
      "tier": "both",
      "notes": "Primary supported model. Designed for agent swarm."
    },
    {
      "id": "claude-sonnet-4",
      "providers": ["anthropic", "openai-compatible"],
      "contains": "sonnet",
      "tier": "both",
      "notes": "Best cost/quality ratio."
    },
    {
      "id": "claude-opus-4",
      "providers": ["anthropic", "openai-compatible"],
      "contains": "opus",
      "tier": "coordinator",
      "notes": "Best synthesis quality."
    },
    {
      "id": "gpt-5.4",
      "providers": ["openai", "openai-compatible"],
      "contains": "gpt-5",
      "tier": "both",
      "notes": "Structured outputs. Outstanding agentic evals."
    },
    {
      "id": "gemini-pro",
      "providers": ["openai-compatible", "ollama"],
      "contains": "gemini",
      "tier": "coordinator",
      "notes": "Best long-context coordination."
    },
    {
      "id": "grok-4",
      "providers": ["openai-compatible"],
      "contains": "grok",
      "tier": "both",
      "notes": "Strong contextual awareness."
    }
  ],
  "default_tier": "unsuitable"
}
```

- [ ] **Step 2: Write the failing tests for swarm_registry**

Write `tests/test_swarm_registry.py`:

```python
"""Tests for swarm model registry."""
import pytest
from prep.core.swarm_registry import SwarmTier, get_swarm_tier, get_min_groups_threshold


class TestSwarmTier:
    def test_coordinator_can_coordinate(self):
        assert SwarmTier.COORDINATOR.can_coordinate is True

    def test_both_can_coordinate(self):
        assert SwarmTier.BOTH.can_coordinate is True

    def test_worker_cannot_coordinate(self):
        assert SwarmTier.WORKER.can_coordinate is False

    def test_unsuitable_cannot_coordinate(self):
        assert SwarmTier.UNSUITABLE.can_coordinate is False


class TestGetSwarmTier:
    def test_kimi_via_ollama(self):
        assert get_swarm_tier("ollama", "kimi-k2.5:cloud") == SwarmTier.BOTH

    def test_kimi_case_insensitive(self):
        assert get_swarm_tier("ollama", "Kimi-K2.5") == SwarmTier.BOTH

    def test_claude_sonnet_anthropic(self):
        assert get_swarm_tier("anthropic", "claude-sonnet-4.6") == SwarmTier.BOTH

    def test_claude_sonnet_openai_compatible(self):
        assert get_swarm_tier("openai-compatible", "claude-sonnet-4.6") == SwarmTier.BOTH

    def test_claude_opus_is_coordinator(self):
        assert get_swarm_tier("anthropic", "claude-opus-4.6") == SwarmTier.COORDINATOR

    def test_gpt5_via_openai(self):
        assert get_swarm_tier("openai", "gpt-5.4") == SwarmTier.BOTH

    def test_gemini_pro_is_coordinator(self):
        assert get_swarm_tier("openai-compatible", "gemini-3.1-pro") == SwarmTier.COORDINATOR

    def test_grok_via_compatible(self):
        assert get_swarm_tier("openai-compatible", "grok-4.20") == SwarmTier.BOTH

    def test_unknown_model_is_unsuitable(self):
        assert get_swarm_tier("ollama", "llama3.3:70b") == SwarmTier.UNSUITABLE

    def test_unknown_provider_is_unsuitable(self):
        assert get_swarm_tier("lm-studio", "kimi-k2.5") == SwarmTier.UNSUITABLE

    def test_qwen_local_is_unsuitable(self):
        assert get_swarm_tier("ollama", "qwen3:32b") == SwarmTier.UNSUITABLE


class TestThreshold:
    def test_default_threshold_is_3(self):
        assert get_min_groups_threshold() == 3
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_swarm_registry.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prep.core.swarm_registry'`

- [ ] **Step 4: Implement swarm_registry.py**

Write `src/prep/core/swarm_registry.py`:

```python
"""Swarm model registry — finite list of validated swarm-capable models.

Loads swarm_models.json and exposes get_swarm_tier() for the pipeline
to check if the current model supports agent swarm orchestration.

The list is intentionally small and curated. Models not in the list
default to UNSUITABLE and use standard concurrent batching.
"""

import enum
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_REGISTRY_PATH = _DATA_DIR / "swarm_models.json"


class SwarmTier(str, enum.Enum):
    """Swarm capability tier for a model."""
    COORDINATOR = "coordinator"
    BOTH = "both"
    WORKER = "worker"
    UNSUITABLE = "unsuitable"

    @property
    def can_coordinate(self) -> bool:
        """Can this model act as a swarm coordinator?"""
        return self in (SwarmTier.COORDINATOR, SwarmTier.BOTH)


def _load_registry() -> Dict[str, Any]:
    """Load the swarm model registry from JSON."""
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load swarm registry from %s: %s", _REGISTRY_PATH, exc)
        return {"models": [], "default_tier": "unsuitable", "min_groups_threshold": 3}


@lru_cache(maxsize=1)
def _cached_registry() -> Dict[str, Any]:
    return _load_registry()


def get_swarm_tier(provider: str, model: str) -> SwarmTier:
    """Look up swarm tier for a model. Returns UNSUITABLE if not in list.

    Matching: provider must be in the entry's providers list, and the
    model name must contain the entry's 'contains' string (case-insensitive).
    First match wins.
    """
    registry = _cached_registry()
    provider_lower = provider.lower().strip()
    model_lower = model.lower().strip()

    for entry in registry.get("models", []):
        providers: List[str] = entry.get("providers", [])
        contains: str = entry.get("contains", "")

        if provider_lower in [p.lower() for p in providers] and contains.lower() in model_lower:
            tier_str = entry.get("tier", "unsuitable")
            try:
                return SwarmTier(tier_str)
            except ValueError:
                logger.warning("Unknown swarm tier '%s' for model %s", tier_str, entry.get("id"))
                return SwarmTier.UNSUITABLE

    return SwarmTier(registry.get("default_tier", "unsuitable"))


def get_min_groups_threshold() -> int:
    """Minimum number of groups required to activate swarm."""
    registry = _cached_registry()
    return int(registry.get("min_groups_threshold", 3))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_swarm_registry.py -v
```

Expected: All 13 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prep/data/swarm_models.json src/prep/core/swarm_registry.py tests/test_swarm_registry.py
git commit -m "feat(swarm): add swarm model registry with finite supported model list

Phase 79 — Agent Swarm Integration. Curated JSON registry of 6 validated
swarm-capable model families (Kimi K2.5, Claude Sonnet/Opus, GPT-5.4,
Gemini Pro, Grok). Simple contains-matching, first match wins."
```

---

### Task 2: Swarm Orchestrator — Data Model & Phase 1 (Coordinator)

**Files:**
- Create: `src/prep/core/swarm_orchestrator.py`
- Create: `tests/test_swarm_orchestrator.py`

- [ ] **Step 1: Write failing tests for data model and coordinator phase**

Write `tests/test_swarm_orchestrator.py`:

```python
"""Tests for swarm orchestrator — three-phase swarm execution."""
import json
import pytest
from unittest.mock import MagicMock, patch
from prep.core.swarm_orchestrator import (
    SwarmOrchestrator,
    WorkItem,
    CoordinatorPlan,
    WorkerAssignment,
    WorkerResult,
    SwarmResult,
    SwarmStats,
)


def _make_items(n: int) -> list[WorkItem]:
    return [
        WorkItem(
            id=f"group:{i}",
            summary=f"Group {i}: files about module_{i}",
            full_context=f"Full epistemic details for group {i}...",
        )
        for i in range(n)
    ]


def _mock_coordinator_response(items: list[WorkItem]) -> str:
    """Build a valid coordinator JSON response."""
    assignments = [
        {
            "item_id": item.id,
            "analysis_angle": f"Focus on coupling in {item.id}",
            "priority_concerns": ["data flow", "error handling"],
        }
        for item in items
    ]
    return json.dumps({"assignments": assignments})


def _mock_worker_response(item_id: str) -> str:
    """Build a valid worker JSON response."""
    return json.dumps({
        "pattern": "Request Pipeline",
        "data_flow": "A calls B calls C",
        "coupling_risks": ["tight coupling via shared state"],
        "blast_radius": ["file_a.py", "file_b.py"],
        "architectural_insight": "Well-structured but tightly coupled.",
        "confidence": 0.8,
    })


def _mock_synthesis_response() -> str:
    """Build a valid synthesis JSON response."""
    return json.dumps({
        "cross_group_patterns": ["Multiple groups use Repository Pattern"],
        "shared_coupling_risks": ["Shared config dependency"],
        "data_flow_chains": ["group:0 → group:1 via events"],
        "systemic_risks": ["Config coupling in 3 groups"],
        "architectural_coherence": "Mostly consistent, some drift in data layer.",
        "key_insight": "Event bus is an implicit dependency across all groups.",
    })


class TestCoordinatorPhase:
    def test_coordinator_produces_plan(self):
        items = _make_items(4)
        mock_llm = MagicMock()
        mock_llm.generate.return_value = (_mock_coordinator_response(items), 500)
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        plan = orch._coordinate(items, "Analyze these groups: {group_summaries}")

        assert plan is not None
        assert len(plan.assignments) == 4
        assert plan.assignments[0].item_id == "group:0"
        assert "coupling" in plan.assignments[0].analysis_angle.lower()

    def test_coordinator_failure_returns_none(self):
        items = _make_items(4)
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = Exception("LLM timeout")
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        plan = orch._coordinate(items, "Analyze: {group_summaries}")

        assert plan is None

    def test_coordinator_bad_json_returns_none(self):
        items = _make_items(4)
        mock_llm = MagicMock()
        mock_llm.generate.return_value = ("not valid json at all", 100)
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        plan = orch._coordinate(items, "Analyze: {group_summaries}")

        assert plan is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_swarm_orchestrator.py::TestCoordinatorPhase -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'prep.core.swarm_orchestrator'`

- [ ] **Step 3: Implement data model and coordinator phase**

Write `src/prep/core/swarm_orchestrator.py`:

```python
"""Swarm Orchestrator — three-phase coordinator → fan-out → synthesis.

Generic swarm executor that any pipeline stage can use. The orchestrator
knows nothing about specific stages — each stage provides its own prompts.

Phase 1 (Coordinate): One LLM call decomposes work into scoped assignments.
Phase 2 (Fan-out): N parallel worker calls with scoped roles.
Phase 3 (Synthesize): One LLM call aggregates worker results.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .llm_client import LLMClient, _parse_json_response

logger = logging.getLogger(__name__)


# ── Data Model ──────────────────────────────────────────────────

@dataclass
class WorkItem:
    """A unit of work for the swarm."""
    id: str
    summary: str
    full_context: str


@dataclass
class WorkerAssignment:
    """Scoped instructions for one worker, produced by coordinator."""
    item_id: str
    analysis_angle: str
    priority_concerns: List[str] = field(default_factory=list)


@dataclass
class CoordinatorPlan:
    """Output of Phase 1 — how to scope each worker."""
    assignments: List[WorkerAssignment] = field(default_factory=list)

    def get_assignment(self, item_id: str) -> Optional[WorkerAssignment]:
        """Get assignment for a specific item."""
        for a in self.assignments:
            if a.item_id == item_id:
                return a
        return None


@dataclass
class WorkerResult:
    """Output of one worker sub-agent."""
    item_id: str
    raw_output: str
    parsed: Optional[Dict[str, Any]] = None
    success: bool = True


@dataclass
class SwarmStats:
    """Telemetry for the swarm run."""
    total_items: int = 0
    workers_succeeded: int = 0
    workers_failed: int = 0
    coordinator_tokens: int = 0
    worker_tokens: int = 0
    synthesis_tokens: int = 0
    wall_clock_seconds: float = 0.0


@dataclass
class SwarmResult:
    """Complete swarm output."""
    worker_results: List[WorkerResult] = field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    coordinator_plan: Optional[CoordinatorPlan] = None
    stats: SwarmStats = field(default_factory=SwarmStats)


# ── Orchestrator ────────────────────────────────────────────────

COORDINATOR_SYSTEM = (
    "You are a senior software architect planning a parallel codebase analysis. "
    "Respond with valid JSON only. No markdown, no explanation outside the JSON."
)

SYNTHESIS_SYSTEM = (
    "You are a senior software architect synthesizing findings from parallel "
    "codebase analyses. Respond with valid JSON only."
)


class SwarmOrchestrator:
    """Three-phase swarm executor.

    Usage:
        orch = SwarmOrchestrator(llm=llm_client, concurrency=10)
        result = orch.execute(
            items=work_items,
            coordinator_prompt="...",
            worker_fn=my_worker_function,
            synthesis_prompt="...",
        )
    """

    def __init__(self, llm: LLMClient, concurrency: int = 10):
        self.llm = llm
        self.concurrency = max(1, concurrency)

    # ── Phase 1: Coordinate ─────────────────────────────────────

    def _coordinate(
        self,
        items: List[WorkItem],
        coordinator_prompt: str,
    ) -> Optional[CoordinatorPlan]:
        """Run coordinator to decompose work into scoped assignments.

        The coordinator_prompt should contain {group_summaries} placeholder.
        Returns None on failure (caller should fall back to non-swarm).
        """
        summaries = "\n".join(
            f"- **{item.id}**: {item.summary}" for item in items
        )
        prompt = coordinator_prompt.replace("{group_summaries}", summaries)

        try:
            text, tokens = self.llm.generate(
                prompt,
                system=COORDINATOR_SYSTEM,
                json_mode=True,
                temperature=0.4,
            )
        except Exception as exc:
            logger.warning("[Swarm] Coordinator LLM call failed: %s", exc)
            return None

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning("[Swarm] Coordinator returned unparseable JSON: %.200s", text)
            return None

        assignments = []
        for a in parsed.get("assignments", []):
            assignments.append(WorkerAssignment(
                item_id=str(a.get("item_id", "")),
                analysis_angle=str(a.get("analysis_angle", "")),
                priority_concerns=[str(p) for p in a.get("priority_concerns", [])],
            ))

        if not assignments:
            logger.warning("[Swarm] Coordinator produced empty assignments")
            return None

        logger.info(
            "[Swarm] Coordinator planned %d assignments (%d tokens)",
            len(assignments), tokens,
        )
        return CoordinatorPlan(assignments=assignments)

    # ── Phase 2: Fan-out ────────────────────────────────────────

    def _fan_out(
        self,
        items: List[WorkItem],
        plan: CoordinatorPlan,
        worker_fn: Callable[[WorkItem, WorkerAssignment], Optional[str]],
        progress_fn: Optional[Callable[[int, int], None]] = None,
    ) -> List[WorkerResult]:
        """Run workers in parallel with scoped assignments.

        worker_fn receives a WorkItem and its WorkerAssignment, returns
        the raw LLM response string or None on failure.
        """
        results: List[WorkerResult] = []
        done_count = 0

        def _run_one(item: WorkItem) -> WorkerResult:
            assignment = plan.get_assignment(item.id)
            if assignment is None:
                # Coordinator didn't assign this item — use generic assignment
                assignment = WorkerAssignment(
                    item_id=item.id,
                    analysis_angle="Perform standard architectural analysis",
                    priority_concerns=[],
                )

            try:
                raw = worker_fn(item, assignment)
                if raw is None:
                    return WorkerResult(item_id=item.id, raw_output="", success=False)
                parsed = _parse_json_response(raw)
                return WorkerResult(
                    item_id=item.id, raw_output=raw, parsed=parsed, success=True,
                )
            except Exception as exc:
                logger.warning("[Swarm] Worker failed for %s: %s", item.id, exc)
                return WorkerResult(item_id=item.id, raw_output="", success=False)

        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(items))) as pool:
            futures = {pool.submit(_run_one, item): item for item in items}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                done_count += 1
                if progress_fn:
                    progress_fn(done_count, len(items))

        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded
        logger.info("[Swarm] Fan-out complete: %d succeeded, %d failed", succeeded, failed)
        return results

    # ── Phase 3: Synthesize ─────────────────────────────────────

    def _synthesize(
        self,
        worker_results: List[WorkerResult],
        synthesis_prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Run synthesis to find cross-cutting patterns across worker results.

        The synthesis_prompt should contain {worker_outputs} placeholder.
        Returns None on failure (worker results are still usable without it).
        """
        successful = [r for r in worker_results if r.success and r.parsed]
        if not successful:
            logger.warning("[Swarm] No successful worker results to synthesize")
            return None

        outputs = "\n\n".join(
            f"### {r.item_id}\n```json\n{json.dumps(r.parsed, indent=2)}\n```"
            for r in successful
        )
        prompt = synthesis_prompt.replace("{worker_outputs}", outputs)

        try:
            text, tokens = self.llm.generate(
                prompt,
                system=SYNTHESIS_SYSTEM,
                json_mode=True,
                temperature=0.5,
            )
        except Exception as exc:
            logger.warning("[Swarm] Synthesis LLM call failed: %s", exc)
            return None

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning("[Swarm] Synthesis returned unparseable JSON: %.200s", text)
            return None

        logger.info("[Swarm] Synthesis complete (%d tokens)", tokens)
        return parsed

    # ── Full execution ──────────────────────────────────────────

    def execute(
        self,
        items: List[WorkItem],
        coordinator_prompt: str,
        worker_fn: Callable[[WorkItem, WorkerAssignment], Optional[str]],
        synthesis_prompt: str,
        progress_fn: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[SwarmResult]:
        """Execute the full three-phase swarm.

        Returns None if coordinator fails (caller should fall back to
        standard concurrent execution). If workers or synthesis fail
        partially, returns whatever succeeded.
        """
        start = time.monotonic()
        stats = SwarmStats(total_items=len(items))

        # Phase 1: Coordinate
        plan = self._coordinate(items, coordinator_prompt)
        if plan is None:
            logger.info("[Swarm] Coordinator failed — falling back to standard path")
            return None

        # Phase 2: Fan-out
        worker_results = self._fan_out(items, plan, worker_fn, progress_fn)
        stats.workers_succeeded = sum(1 for r in worker_results if r.success)
        stats.workers_failed = len(worker_results) - stats.workers_succeeded

        # Phase 3: Synthesize
        synthesis = self._synthesize(worker_results, synthesis_prompt)

        stats.wall_clock_seconds = time.monotonic() - start
        logger.info(
            "[Swarm] Complete in %.1fs: %d/%d workers succeeded, synthesis=%s",
            stats.wall_clock_seconds, stats.workers_succeeded,
            stats.total_items, "yes" if synthesis else "no",
        )

        return SwarmResult(
            worker_results=worker_results,
            synthesis=synthesis,
            coordinator_plan=plan,
            stats=stats,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_swarm_orchestrator.py::TestCoordinatorPhase -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/swarm_orchestrator.py tests/test_swarm_orchestrator.py
git commit -m "feat(swarm): add SwarmOrchestrator with coordinator phase

Three-phase swarm executor: coordinator → fan-out → synthesis.
Generic — stages provide their own prompts via worker_fn callback.
Coordinator failure returns None for graceful fallback."
```

---

### Task 3: Swarm Orchestrator — Phase 2 (Fan-out) & Phase 3 (Synthesis) Tests

**Files:**
- Modify: `tests/test_swarm_orchestrator.py`

- [ ] **Step 1: Add fan-out and synthesis tests**

Append to `tests/test_swarm_orchestrator.py`:

```python
class TestFanOutPhase:
    def test_fan_out_runs_all_workers(self):
        items = _make_items(4)
        mock_llm = MagicMock()
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        plan = CoordinatorPlan(assignments=[
            WorkerAssignment(item_id=f"group:{i}", analysis_angle=f"Analyze group {i}")
            for i in range(4)
        ])

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        results = orch._fan_out(items, plan, worker_fn)

        assert len(results) == 4
        assert all(r.success for r in results)
        assert all(r.parsed is not None for r in results)

    def test_fan_out_handles_worker_failure(self):
        items = _make_items(4)
        mock_llm = MagicMock()
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        plan = CoordinatorPlan(assignments=[
            WorkerAssignment(item_id=f"group:{i}", analysis_angle=f"Analyze group {i}")
            for i in range(4)
        ])

        call_count = 0
        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            nonlocal call_count
            call_count += 1
            if item.id == "group:2":
                raise Exception("Worker crashed")
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        results = orch._fan_out(items, plan, worker_fn)

        assert len(results) == 4
        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        assert len(succeeded) == 3
        assert len(failed) == 1

    def test_fan_out_missing_assignment_uses_generic(self):
        items = _make_items(2)
        mock_llm = MagicMock()
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        # Only assign group:0, leave group:1 unassigned
        plan = CoordinatorPlan(assignments=[
            WorkerAssignment(item_id="group:0", analysis_angle="Specific angle"),
        ])

        received_assignments = {}
        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            received_assignments[item.id] = assignment.analysis_angle
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        orch._fan_out(items, plan, worker_fn)

        assert received_assignments["group:0"] == "Specific angle"
        assert "standard" in received_assignments["group:1"].lower()

    def test_fan_out_reports_progress(self):
        items = _make_items(3)
        mock_llm = MagicMock()
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        plan = CoordinatorPlan(assignments=[
            WorkerAssignment(item_id=f"group:{i}", analysis_angle=f"Analyze {i}")
            for i in range(3)
        ])

        progress_calls = []
        def progress_fn(done: int, total: int):
            progress_calls.append((done, total))

        def worker_fn(item, assignment):
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        orch._fan_out(items, plan, worker_fn, progress_fn=progress_fn)

        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)


class TestSynthesisPhase:
    def test_synthesis_produces_cross_group_insights(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = (_mock_synthesis_response(), 300)
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        worker_results = [
            WorkerResult(
                item_id=f"group:{i}",
                raw_output=_mock_worker_response(f"group:{i}"),
                parsed=json.loads(_mock_worker_response(f"group:{i}")),
                success=True,
            )
            for i in range(4)
        ]

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        synthesis = orch._synthesize(worker_results, "Synthesize: {worker_outputs}")

        assert synthesis is not None
        assert "cross_group_patterns" in synthesis
        assert "key_insight" in synthesis

    def test_synthesis_failure_returns_none(self):
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = Exception("LLM error")
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        worker_results = [
            WorkerResult(item_id="group:0", raw_output="{}", parsed={}, success=True),
        ]

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        synthesis = orch._synthesize(worker_results, "Synthesize: {worker_outputs}")

        assert synthesis is None

    def test_synthesis_skipped_when_no_successful_workers(self):
        mock_llm = MagicMock()
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        worker_results = [
            WorkerResult(item_id="group:0", raw_output="", success=False),
        ]

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        synthesis = orch._synthesize(worker_results, "Synthesize: {worker_outputs}")

        assert synthesis is None
        mock_llm.generate.assert_not_called()


class TestFullExecution:
    def test_full_swarm_happy_path(self):
        items = _make_items(4)
        mock_llm = MagicMock()
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        # Coordinator returns assignments
        mock_llm.generate.side_effect = [
            (_mock_coordinator_response(items), 500),  # coordinator
            (_mock_synthesis_response(), 300),          # synthesis
        ]

        def worker_fn(item, assignment):
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        result = orch.execute(
            items=items,
            coordinator_prompt="Plan: {group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synthesize: {worker_outputs}",
        )

        assert result is not None
        assert result.coordinator_plan is not None
        assert len(result.worker_results) == 4
        assert result.stats.workers_succeeded == 4
        assert result.stats.workers_failed == 0
        assert result.synthesis is not None
        assert result.stats.wall_clock_seconds > 0

    def test_coordinator_failure_returns_none(self):
        items = _make_items(4)
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = Exception("LLM down")
        mock_llm.provider = "ollama"
        mock_llm.model = "kimi-k2.5:cloud"

        orch = SwarmOrchestrator(llm=mock_llm, concurrency=10)
        result = orch.execute(
            items=items,
            coordinator_prompt="Plan: {group_summaries}",
            worker_fn=lambda i, a: "{}",
            synthesis_prompt="Synth: {worker_outputs}",
        )

        assert result is None  # Caller should fall back to standard path
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_swarm_orchestrator.py -v
```

Expected: All 14 tests PASS (3 coordinator + 4 fan-out + 3 synthesis + 2 full + 2 existing).

- [ ] **Step 3: Commit**

```bash
git add tests/test_swarm_orchestrator.py
git commit -m "test(swarm): add fan-out, synthesis, and full execution tests

Covers: partial worker failure, missing assignments fallback, progress
reporting, synthesis skip on no results, coordinator failure fallback."
```

---

### Task 4: Group Reasoning Swarm Integration

**Files:**
- Modify: `src/prep/core/group_reasoning.py:404-550` (the `run()` method)
- Create: `tests/test_group_reasoning_swarm.py`

- [ ] **Step 1: Write failing integration test**

Write `tests/test_group_reasoning_swarm.py`:

```python
"""Integration test: Group Reasoning using swarm orchestration."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from prep.core.group_reasoning import GroupReasoningEngine, GroupReasoningEntry
from prep.core.swarm_registry import SwarmTier


@pytest.fixture
def tmp_index_dir(tmp_path):
    """Create a minimal index directory with epistemic + edge data."""
    # 4 groups of 3 files each = 12 files, triggers swarm (>= 3 groups)
    epistemic_entries = []
    for g in range(4):
        for f in range(3):
            node_id = f"file:src/group{g}/file{f}.py"
            epistemic_entries.append({
                "node_id": node_id,
                "extended_summary": f"Module in group {g}, file {f}",
                "architecture_layer": "service",
                "domain_tags": [f"group{g}"],
                "tech_debt": [],
                "confidence": 0.8,
                "model": "test-model",
                "analyzed_at": "2026-04-07T00:00:00Z",
            })

    with open(tmp_path / "trace_epistemic.jsonl", "w") as f:
        for entry in epistemic_entries:
            f.write(json.dumps(entry) + "\n")

    # Edges connecting files within each group
    edges = []
    for g in range(4):
        for f in range(2):
            edges.append({
                "source": f"file:src/group{g}/file{f}.py",
                "target": f"file:src/group{g}/file{f+1}.py",
                "kind": "imports",
            })

    with open(tmp_path / "trace_edges.jsonl", "w") as f:
        for edge in edges:
            f.write(json.dumps(edge) + "\n")

    return tmp_path


def _make_mock_llm(coordinator_response: str, synthesis_response: str):
    """Create mock LLM that returns coordinator then synthesis responses."""
    mock = MagicMock()
    mock.provider = "ollama"
    mock.model = "kimi-k2.5:cloud"
    # generate() is called for coordinator, each worker, and synthesis
    # Worker calls go through analyze_group which also calls generate()
    mock.generate.return_value = (
        json.dumps({
            "pattern": "Service Layer",
            "data_flow": "A → B → C",
            "coupling_risks": ["shared state"],
            "blast_radius": ["file0.py"],
            "architectural_insight": "Clean separation.",
            "confidence": 0.85,
        }),
        200,
    )
    return mock


class TestGroupReasoningSwarmDecision:
    @patch("prep.core.group_reasoning.get_swarm_tier")
    def test_swarm_activated_when_eligible(self, mock_tier, tmp_index_dir):
        mock_tier.return_value = SwarmTier.BOTH
        mock_llm = _make_mock_llm("{}", "{}")

        engine = GroupReasoningEngine(llm=mock_llm, index_dir=tmp_index_dir)

        with patch.object(engine, "_run_swarm", return_value={}) as mock_swarm:
            with patch.object(engine, "_get_swarm_enabled", return_value=True):
                engine.run()
                mock_swarm.assert_called_once()

    @patch("prep.core.group_reasoning.get_swarm_tier")
    def test_swarm_skipped_when_model_unsuitable(self, mock_tier, tmp_index_dir):
        mock_tier.return_value = SwarmTier.UNSUITABLE
        mock_llm = _make_mock_llm("{}", "{}")

        engine = GroupReasoningEngine(llm=mock_llm, index_dir=tmp_index_dir)

        with patch.object(engine, "_run_swarm") as mock_swarm:
            with patch.object(engine, "_get_swarm_enabled", return_value=True):
                engine.run()
                mock_swarm.assert_not_called()

    @patch("prep.core.group_reasoning.get_swarm_tier")
    def test_swarm_skipped_when_disabled_by_user(self, mock_tier, tmp_index_dir):
        mock_tier.return_value = SwarmTier.BOTH
        mock_llm = _make_mock_llm("{}", "{}")

        engine = GroupReasoningEngine(llm=mock_llm, index_dir=tmp_index_dir)

        with patch.object(engine, "_run_swarm") as mock_swarm:
            with patch.object(engine, "_get_swarm_enabled", return_value=False):
                engine.run()
                mock_swarm.assert_not_called()

    @patch("prep.core.group_reasoning.get_swarm_tier")
    def test_swarm_skipped_below_threshold(self, mock_tier, tmp_path):
        """With only 2 groups (below threshold of 3), swarm should not activate."""
        mock_tier.return_value = SwarmTier.BOTH

        # Create only 2 groups of 2 files
        epistemic_entries = []
        for g in range(2):
            for f in range(2):
                node_id = f"file:src/g{g}/f{f}.py"
                epistemic_entries.append({
                    "node_id": node_id,
                    "extended_summary": f"File {f} in group {g}",
                    "architecture_layer": "service",
                    "domain_tags": [],
                    "tech_debt": [],
                    "confidence": 0.8,
                    "model": "test",
                    "analyzed_at": "2026-04-07T00:00:00Z",
                })

        with open(tmp_path / "trace_epistemic.jsonl", "w") as fp:
            for entry in epistemic_entries:
                fp.write(json.dumps(entry) + "\n")

        edges = []
        for g in range(2):
            edges.append({
                "source": f"file:src/g{g}/f0.py",
                "target": f"file:src/g{g}/f1.py",
                "kind": "imports",
            })
        with open(tmp_path / "trace_edges.jsonl", "w") as fp:
            for edge in edges:
                fp.write(json.dumps(edge) + "\n")

        mock_llm = _make_mock_llm("{}", "{}")
        engine = GroupReasoningEngine(llm=mock_llm, index_dir=tmp_path)

        with patch.object(engine, "_run_swarm") as mock_swarm:
            with patch.object(engine, "_get_swarm_enabled", return_value=True):
                engine.run()
                mock_swarm.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_group_reasoning_swarm.py -v
```

Expected: FAIL — `AttributeError: 'GroupReasoningEngine' object has no attribute '_run_swarm'`

- [ ] **Step 3: Add swarm integration to GroupReasoningEngine**

Modify `src/prep/core/group_reasoning.py`. Add imports near the top (after existing imports):

```python
from .swarm_registry import SwarmTier, get_swarm_tier, get_min_groups_threshold
from .swarm_orchestrator import SwarmOrchestrator, WorkItem, WorkerAssignment, SwarmResult
```

Add three new methods to `GroupReasoningEngine` (after `_build_internal_edges`, before `analyze_group`):

```python
    def _get_swarm_enabled(self) -> bool:
        """Check if swarm is enabled in pipeline settings."""
        try:
            from prep.services.settings_store import settings
            return bool(settings.get("swarm_enabled", True))
        except Exception:
            return True  # Default to enabled

    def _run_swarm(
        self,
        to_analyze: List[Tuple[str, List[str]]],
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
        progress_callback: Optional[Callable[..., None]] = None,
        cancel_token: Optional[Any] = None,
    ) -> Dict[str, GroupReasoningEntry]:
        """Run group reasoning using swarm orchestration.

        Phase 1: Coordinator scopes each group's analysis angle.
        Phase 2: Workers analyze groups with scoped prompts.
        Phase 3: Synthesis finds cross-group patterns.
        """
        from prep.core.batch_profiles import get_batch_concurrency

        try:
            concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
        except Exception:
            concurrency = 1

        orch = SwarmOrchestrator(llm=self.llm, concurrency=concurrency)

        # Build work items
        items = []
        for gid, members in to_analyze:
            summary_parts = []
            for nid in members[:5]:  # Cap summary at 5 files
                entry = epistemic.get(nid)
                if entry:
                    fp = nid.replace("file:", "", 1)
                    summary_parts.append(f"{fp} ({entry.architecture_layer})")
            summary = ", ".join(summary_parts)
            if len(members) > 5:
                summary += f" (+{len(members) - 5} more)"

            items.append(WorkItem(
                id=gid,
                summary=summary,
                full_context=json.dumps({
                    "member_details": self._build_member_details(members, epistemic),
                    "internal_edges": self._build_internal_edges(members, edges),
                    "member_count": len(members),
                }),
            ))

        coordinator_prompt = (
            "You are planning a parallel architectural analysis of {n} file groups "
            "from a codebase. Each group is a cluster of files connected by imports "
            "or data flow.\n\n"
            "## Groups:\n{group_summaries}\n\n"
            "For each group, assign a SPECIFIC analysis angle based on what you see. "
            "Don't give generic instructions — tailor each to the group's apparent role.\n\n"
            "Respond with JSON:\n"
            '{{"assignments": [{{"item_id": "group:xxx", '
            '"analysis_angle": "specific focus", '
            '"priority_concerns": ["concern1", "concern2"]}}]}}'
        ).replace("{n}", str(len(items)))

        synthesis_prompt = (
            "You are synthesizing architectural findings from {n} parallel group "
            "analyses of the same codebase.\n\n"
            "## Group Analysis Results:\n{worker_outputs}\n\n"
            "Look ACROSS these groups for:\n"
            "1. Shared patterns — do multiple groups use the same architecture?\n"
            "2. Cross-group coupling — do groups reference each other's files?\n"
            "3. Data flow chains — does data flow from one group into another?\n"
            "4. Systemic risks — same coupling risks in multiple groups?\n\n"
            "Respond with JSON:\n"
            '{{"cross_group_patterns": [], "shared_coupling_risks": [], '
            '"data_flow_chains": [], "systemic_risks": [], '
            '"architectural_coherence": "", "key_insight": ""}}'
        ).replace("{n}", str(len(items)))

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
            ctx = json.loads(item.full_context)
            gid = item.id
            members = [
                gid_m for gid_m, _ in to_analyze if True  # we need the member list
            ]
            # Find the member list for this group
            member_ids = None
            for g_id, g_members in to_analyze:
                if g_id == gid:
                    member_ids = g_members
                    break
            if member_ids is None:
                return None

            entry = self.analyze_group_with_angle(
                gid, member_ids, epistemic, edges,
                assignment.analysis_angle, assignment.priority_concerns,
            )
            if entry is None:
                return None
            return json.dumps(entry.to_dict())

        def progress_fn(done: int, total: int) -> None:
            if progress_callback:
                progress_callback("group_reasoning", done, len(to_analyze), 0)

        result = orch.execute(
            items=items,
            coordinator_prompt=coordinator_prompt,
            worker_fn=worker_fn,
            synthesis_prompt=synthesis_prompt,
            progress_fn=progress_fn,
        )

        if result is None:
            # Coordinator failed — fall back to standard path
            return {}

        # Convert worker results to GroupReasoningEntry objects
        entries: Dict[str, GroupReasoningEntry] = {}
        for wr in result.worker_results:
            if wr.success and wr.parsed:
                try:
                    entry = GroupReasoningEntry.from_dict(wr.parsed)
                    entries[entry.group_id] = entry
                except (KeyError, TypeError):
                    pass

        # Write synthesis artifact
        if result.synthesis:
            self._write_synthesis(result)

        return entries

    def analyze_group_with_angle(
        self,
        group_id: str,
        member_ids: List[str],
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
        analysis_angle: str,
        priority_concerns: List[str],
    ) -> Optional[GroupReasoningEntry]:
        """Analyze a single group with coordinator-assigned scoping."""
        member_details = self._build_member_details(member_ids, epistemic)
        internal_edges = self._build_internal_edges(member_ids, edges)

        concerns_str = ", ".join(priority_concerns) if priority_concerns else "general architecture"

        prompt = GROUP_REASONING_PROMPT.format(
            file_count=len(member_ids),
            member_details=member_details,
            internal_edges=internal_edges,
        )
        prompt += (
            f"\n\n## Coordinator Guidance:\n"
            f"Analysis angle: {analysis_angle}\n"
            f"Priority concerns: {concerns_str}\n\n"
            f"Pay special attention to the above. Your analysis should be "
            f"shaped by this guidance while still covering the standard "
            f"architectural assessment."
        )

        import time as _time
        from prep.core.context_config import PipelineTask, compute_optimal_settings
        from prep.core.llm_client import TASK_MAX_CHARS

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.GROUP_REASONING,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=True,
        )

        try:
            text, tokens = self.llm.generate(
                prompt,
                system=GROUP_REASONING_SYSTEM,
                num_predict=num_predict,
                num_ctx=num_ctx,
                json_mode=True,
                temperature=0.6,
                think=True,
                max_chars=TASK_MAX_CHARS["group_reasoning"],
            )
        except Exception as e:
            logger.warning("[GroupReasoning/Swarm] Worker failed for %s: %s", group_id, e)
            return None

        parsed = _parse_json_response(text)
        if parsed is None:
            return None

        fingerprint = compute_group_fingerprint(member_ids, epistemic)
        return GroupReasoningEntry(
            group_id=group_id,
            member_node_ids=member_ids,
            pattern=str(parsed.get("pattern", "unknown"))[:200],
            data_flow=str(parsed.get("data_flow", ""))[:500],
            coupling_risks=[str(r) for r in parsed.get("coupling_risks", [])][:10],
            blast_radius=[str(r) for r in parsed.get("blast_radius", [])][:20],
            architectural_insight=str(parsed.get("architectural_insight", ""))[:500],
            confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.7)))),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            member_fingerprint=fingerprint,
        )

    def _write_synthesis(self, result: SwarmResult) -> None:
        """Write swarm synthesis artifact to disk."""
        synthesis_path = self.index_dir / "trace_swarm_synthesis.json"
        data = {
            "stage": "group_reasoning",
            "model": self.llm.model,
            "groups_analyzed": result.stats.total_items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "synthesis": result.synthesis,
            "stats": {
                "workers_succeeded": result.stats.workers_succeeded,
                "workers_failed": result.stats.workers_failed,
                "wall_clock_seconds": round(result.stats.wall_clock_seconds, 1),
            },
        }
        with open(synthesis_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("[Swarm] Synthesis written to %s", synthesis_path)
```

Modify the `run()` method — insert the swarm decision branch at line ~478 (after `results` dict is initialized, before the existing concurrency check):

```python
        # ── Swarm decision ──────────────────────────────────────────
        swarm_tier = get_swarm_tier(self.llm.provider, self.llm.model)
        swarm_enabled = self._get_swarm_enabled()
        min_threshold = get_min_groups_threshold()
        use_swarm = (
            swarm_tier.can_coordinate
            and swarm_enabled
            and len(to_analyze) >= min_threshold
        )

        if use_swarm:
            logger.info(
                "Group reasoning: using SWARM orchestration (%s, %d groups, tier=%s)",
                self.llm.model, len(to_analyze), swarm_tier.value,
            )
            swarm_entries = self._run_swarm(
                to_analyze, epistemic, edges, progress_callback, cancel_token,
            )
            if swarm_entries:
                # Swarm succeeded — use its results
                results.update(swarm_entries)
                analyzed = len(swarm_entries)
                self._write_results(results)
                elapsed = time.monotonic() - start
                return {
                    "total_groups": total_groups,
                    "analyzed": analyzed,
                    "reused": len(reuse),
                    "failed": len(to_analyze) - analyzed,
                    "elapsed_seconds": round(elapsed, 1),
                    "swarm": True,
                }
            else:
                logger.info("Swarm coordinator failed — falling back to standard path")
                # Fall through to existing concurrent/sequential logic below
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_group_reasoning_swarm.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Run existing tests to verify no regression**

```bash
.venv/bin/pytest tests/ -k "group_reasoning" -v
```

Expected: All existing + new tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prep/core/group_reasoning.py tests/test_group_reasoning_swarm.py
git commit -m "feat(swarm): integrate swarm orchestration into Group Reasoning

Stage 7 now uses coordinator → fan-out → synthesis when:
- Model is in the swarm-capable list (Kimi K2.5, Claude, GPT-5, Gemini, Grok)
- User hasn't disabled swarm in settings
- There are 3+ groups to analyze

Falls back to standard concurrent path if coordinator fails.
Produces additive trace_swarm_synthesis.json with cross-group insights."
```

---

### Task 5: Settings Toggle

**Files:**
- Modify: `src/prep/core/group_reasoning.py` (already has `_get_swarm_enabled`)
- No new files — uses existing `SettingsStore.get()`/`set()`

- [ ] **Step 1: Verify the setting works with existing SettingsStore**

The `_get_swarm_enabled()` method added in Task 4 reads from `settings.get("swarm_enabled", True)`. The setting defaults to `True` (swarm on) and can be toggled off via the API:

```python
# To disable: settings.set("swarm_enabled", False)
# To re-enable: settings.set("swarm_enabled", True)
# To check: settings.get("swarm_enabled", True)
```

No new API route is needed — the existing `PUT /api/settings` endpoint handles arbitrary key-value settings. The dashboard can add a toggle that writes this key.

- [ ] **Step 2: Write a quick test**

Add to `tests/test_group_reasoning_swarm.py`:

```python
class TestSwarmSetting:
    def test_get_swarm_enabled_defaults_true(self):
        """When settings store isn't initialized, default to True."""
        mock_llm = MagicMock()
        mock_llm.provider = "ollama"
        mock_llm.model = "test"
        engine = GroupReasoningEngine(llm=mock_llm, index_dir=Path("/tmp"))
        assert engine._get_swarm_enabled() is True
```

- [ ] **Step 3: Run test**

```bash
.venv/bin/pytest tests/test_group_reasoning_swarm.py::TestSwarmSetting -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_group_reasoning_swarm.py
git commit -m "test(swarm): verify swarm_enabled setting defaults to true"
```

---

### Task 6: Final Integration Test & Cleanup

**Files:**
- All swarm files for a full end-to-end run

- [ ] **Step 1: Run full test suite**

```bash
.venv/bin/pytest tests/test_swarm_registry.py tests/test_swarm_orchestrator.py tests/test_group_reasoning_swarm.py -v
```

Expected: All tests PASS.

- [ ] **Step 2: Run linting**

```bash
.venv/bin/ruff check src/prep/core/swarm_registry.py src/prep/core/swarm_orchestrator.py src/prep/core/group_reasoning.py
```

Expected: No errors. Fix any issues.

- [ ] **Step 3: Run type checking**

```bash
.venv/bin/mypy src/prep/core/swarm_registry.py src/prep/core/swarm_orchestrator.py
```

Expected: No errors. Fix any issues.

- [ ] **Step 4: Commit any lint/type fixes**

```bash
git add -A
git commit -m "chore(swarm): fix lint and type check issues"
```

- [ ] **Step 5: Final commit with all Phase 79 docs**

```bash
git add docs/Phase79_Swarm/
git commit -m "docs(swarm): Phase 79 research, design spec, and implementation plan"
```

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 1 | Swarm model registry | `swarm_registry.py`, `swarm_models.json` | 13 tests |
| 2 | Orchestrator: data model + coordinator | `swarm_orchestrator.py` | 3 tests |
| 3 | Orchestrator: fan-out + synthesis | `swarm_orchestrator.py` (tests only) | 9 tests |
| 4 | Group Reasoning integration | `group_reasoning.py` | 4 tests |
| 5 | Settings toggle | Uses existing SettingsStore | 1 test |
| 6 | Integration & cleanup | All files | Full suite |

**Total: ~30 tests, 3 new files, 1 modified file, 1 JSON data file.**
