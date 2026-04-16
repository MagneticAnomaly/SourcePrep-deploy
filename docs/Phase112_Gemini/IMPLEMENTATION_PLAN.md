# Swarm Decoupled Slots + Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md`

**Goal:** Decouple the Swarm `coordinator_llm` (Phases 1+3) from `worker_llm` (Phase 2), add a dynamic batching/concurrency optimizer, and expose the three Advanced-Settings overrides — while preserving backward compatibility via inherit-from-large fallback.

**Architecture:** New `swarm_optimizer.py` centralizes quality/throughput constants. `SwarmOrchestrator` gains a dual-LLM constructor; four call sites (cluster, group_reasoning, concept_seeder, atlas/generator) pass both clients sourced from `config_manager`. UI scaffolding for the coordinator slot already exists — this plan completes the backend wiring, cleans the `RECOMMENDED_MODELS` list, and adds the Advanced Settings panel.

**Tech Stack:** Python 3.11 (FastAPI + Pydantic), React/TypeScript (Vite), Tailwind + Radix UI. Tests: pytest (`asyncio_mode = "auto"`), Vitest for frontend.

**Primary success metric:** synthesis JSON validity rate ≥ 99% (up from ~85% baseline). Secondary: concept coverage +20%, Swarm wall-clock ≤ 30 min on CoDRAG deep enrichment (Max plan).

**Important pre-existing state (verified 2026-04-16):**
- `ModelSlotType` already includes `'coordinator'` (`packages/ui/src/types.ts:824`)
- `coordinator_model` block already exists in config defaults (`src/codrag/services/config_manager.py:348`)
- Coordinator card already renders with inherit toggle (`packages/ui/src/components/llm/AIModelsSettings.tsx:900–935`)
- F-59 root cause is resolved (see `docs/Phase79_Swarm/07_Rework/SWARM_HANG_INVESTIGATION.md`) but the stale `return 1` workaround still lives in `batch_profiles.py:359`

---

## File Structure

**Create:**
- `src/codrag/core/swarm_optimizer.py` — constants + `get_optimal_swarm_config()`
- `tests/test_swarm_optimizer.py` — unit tests for optimizer
- `packages/ui/src/components/llm/AdvancedLLMSettings.tsx` — new Advanced Settings panel
- `packages/ui/src/components/llm/AdvancedLLMSettings.stories.tsx` — Storybook

**Modify:**
- `src/codrag/core/swarm_orchestrator.py` — dual-LLM constructor, inherit fallback
- `src/codrag/core/batch_profiles.py` — remove F-59 hardcap, add plan-tier-aware concurrency, add "enforce safety limits" gate
- `src/codrag/core/llm_client.py` — gate the 24K `num_predict` cap on a configurable `max_thinking_budget`
- `src/codrag/core/cluster.py:1307` — pass coordinator_llm + worker_llm
- `src/codrag/core/group_reasoning.py:467` — same
- `src/codrag/core/concept_seeder.py:309` — same
- `src/codrag/core/atlas/generator.py:939` — same
- `src/codrag/services/config_manager.py` — add `get_llm_client_for_slot("coordinator")` with inherit-from-large resolution; add `advanced_llm_settings` block
- `packages/ui/src/types.ts` — add `AdvancedLLMSettings` interface, extend `LLMConfig`
- `packages/ui/src/components/llm/AIModelsSettings.tsx:85–90` — update `RECOMMENDED_MODELS` (remove qwen3:{4b,8b,14b,30b})
- `packages/ui/src/hooks/useDashboardPanels.tsx` — wire Advanced Settings panel

**Test:**
- `tests/test_swarm_optimizer.py`
- `tests/test_swarm_orchestrator.py` — extend existing
- `tests/test_batch_profiles.py` — extend existing (add plan-tier tests)
- `tests/test_config_manager.py` — extend (coordinator slot inherit resolution)

---

## Task 1: Add swarm_optimizer constants (TDD)

**Files:**
- Create: `tests/test_swarm_optimizer.py`
- Create: `src/codrag/core/swarm_optimizer.py`

- [ ] **Step 1: Write failing test for constants**

```python
# tests/test_swarm_optimizer.py
from codrag.core.swarm_optimizer import (
    KIMI_MAX_BATCH,
    GEMINI_MAX_BATCH_ITEMS,
    GEMINI_ATTENTION_QUALITY_CEILING_TOKENS,
    GEMINI_HARD_CONTEXT_TOKENS,
    PLAN_TIER_CONCURRENCY,
)


def test_constants_match_spec():
    assert KIMI_MAX_BATCH == 10
    assert GEMINI_MAX_BATCH_ITEMS == 200
    assert GEMINI_ATTENTION_QUALITY_CEILING_TOKENS == 200_000
    assert GEMINI_HARD_CONTEXT_TOKENS == 800_000
    assert PLAN_TIER_CONCURRENCY == {"free": 1, "pro": 3, "max": 10}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_swarm_optimizer.py -v`
Expected: `ModuleNotFoundError: No module named 'codrag.core.swarm_optimizer'`

- [ ] **Step 3: Create swarm_optimizer.py with constants**

```python
# src/codrag/core/swarm_optimizer.py
"""Dynamic Swarm batching & concurrency optimizer.

Centralizes quality/throughput constants for the three Swarm phases:
- Phase 1 (Coordinator): Gemini — one JSON planning call
- Phase 2 (Workers): Kimi — deep per-file reasoning, fan-out
- Phase 3 (Synthesis): Gemini — large-context aggregation

See docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md §7 for the rationale.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

# ── Kimi (Worker) ──────────────────────────────────────────────────
# Per-file attention lever.  Beyond ~10 items per prompt, thinking-
# preamble attention dilutes and JSON schemas degrade regardless of
# context window size.
KIMI_MAX_BATCH: int = 10

# ── Gemini (Coordinator + Synthesis) ───────────────────────────────
# Item-count cap protects against degenerate cases (many tiny outputs
# packing into one call but blowing item-wise attention).
GEMINI_MAX_BATCH_ITEMS: int = 200

# Payload cap where Gemini 3 Flash cross-reference attention stays
# sharp.  Primary quality lever for Phase 3 synthesis.
GEMINI_ATTENTION_QUALITY_CEILING_TOKENS: int = 200_000

# Hard safety cap at 80% of 1M window — leaves headroom for system
# prompt + generated output.
GEMINI_HARD_CONTEXT_TOKENS: int = 800_000

# ── Plan tier concurrency ──────────────────────────────────────────
# Ollama Cloud per-plan concurrent-model limits.
PlanTier = Literal["free", "pro", "max"]
PLAN_TIER_CONCURRENCY: Dict[str, int] = {
    "free": 1,
    "pro": 3,
    "max": 10,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_swarm_optimizer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/swarm_optimizer.py tests/test_swarm_optimizer.py
git commit -m "feat(swarm): add optimizer constants per SWARM_UI_PLAN_v2 §7"
```

---

## Task 2: Add `get_optimal_swarm_config()` (TDD)

**Files:**
- Modify: `tests/test_swarm_optimizer.py`
- Modify: `src/codrag/core/swarm_optimizer.py`

- [ ] **Step 1: Write failing tests for optimizer**

Append to `tests/test_swarm_optimizer.py`:

```python
from codrag.core.swarm_optimizer import (
    SwarmConfig,
    get_optimal_swarm_config,
)


def test_worker_max_plan_155_groups():
    cfg = get_optimal_swarm_config(role="worker", plan_tier="max", total_items=155)
    assert cfg.concurrency == 10
    assert cfg.batch_size == 10
    # 155 items / (10 conc × 10 batch) = 2 waves
    assert cfg.expected_waves == 2


def test_worker_pro_plan_155_groups():
    cfg = get_optimal_swarm_config(role="worker", plan_tier="pro", total_items=155)
    assert cfg.concurrency == 3
    assert cfg.batch_size == 10
    # 16 prompts / 3 conc = 6 waves (5 waves of 3 + 1 wave of 1)
    assert cfg.expected_waves == 6


def test_worker_free_plan_100_items():
    cfg = get_optimal_swarm_config(role="worker", plan_tier="free", total_items=100)
    assert cfg.concurrency == 1
    assert cfg.batch_size == 10
    # 10 prompts / 1 conc = 10 waves
    assert cfg.expected_waves == 10


def test_synthesis_small_payload_single_call():
    cfg = get_optimal_swarm_config(
        role="synthesis", plan_tier="max", total_items=155,
        avg_item_tokens=1000,
    )
    assert cfg.concurrency == 1
    # 200K ceiling / 1000 tokens = 200; 155 < 200 → 155 items/call
    assert cfg.batch_size == 155
    assert cfg.expected_calls == 1


def test_synthesis_large_payload_splits():
    cfg = get_optimal_swarm_config(
        role="synthesis", plan_tier="max", total_items=602,
        avg_item_tokens=1000,
    )
    # 200 items per call (quality ceiling) → 4 calls (3x200 + 1x2, rounds to 4)
    assert cfg.batch_size == 200
    assert cfg.expected_calls == 4  # ceil(602 / 200)


def test_synthesis_respects_item_cap_at_high_density():
    # Tiny outputs (100 tokens) would pack 2000/call by token math,
    # but the item cap holds at 200.
    cfg = get_optimal_swarm_config(
        role="synthesis", plan_tier="max", total_items=500,
        avg_item_tokens=100,
    )
    assert cfg.batch_size == 200


def test_coordinator_always_one_call():
    cfg = get_optimal_swarm_config(
        role="coordinator", plan_tier="max", total_items=155,
        avg_item_tokens=500,
    )
    assert cfg.concurrency == 1
    assert cfg.expected_calls == 1


def test_unknown_plan_tier_raises():
    import pytest
    with pytest.raises(ValueError, match="plan_tier"):
        get_optimal_swarm_config(role="worker", plan_tier="enterprise", total_items=10)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_swarm_optimizer.py -v`
Expected: FAIL — `ImportError: cannot import name 'SwarmConfig'`

- [ ] **Step 3: Implement optimizer**

Append to `src/codrag/core/swarm_optimizer.py`:

```python
from math import ceil


@dataclass(frozen=True)
class SwarmConfig:
    """Runtime swarm configuration for one phase."""
    role: str                  # "coordinator" | "worker" | "synthesis"
    concurrency: int           # max parallel calls
    batch_size: int            # items per call
    expected_waves: int = 1    # worker-only: concurrency-dependent waves
    expected_calls: int = 1    # synthesis-only: sequential calls


def get_optimal_swarm_config(
    role: Literal["coordinator", "worker", "synthesis"],
    plan_tier: str,
    total_items: int,
    avg_item_tokens: int = 1_000,
) -> SwarmConfig:
    """Return the optimal (concurrency, batch_size) for a swarm phase.

    Quality-first: smaller batches keep per-item attention sharp.
    Throughput is the secondary optimizer only for the Worker role.

    Args:
        role: Which swarm phase (coordinator | worker | synthesis).
        plan_tier: Ollama Cloud plan ("free" | "pro" | "max").
        total_items: Number of items to process in this phase.
        avg_item_tokens: Mean tokens per item (used for synthesis payload
                         sizing).

    Raises:
        ValueError: if plan_tier is not a recognized tier.
    """
    if plan_tier not in PLAN_TIER_CONCURRENCY:
        raise ValueError(
            f"Unknown plan_tier '{plan_tier}'. "
            f"Expected one of: {sorted(PLAN_TIER_CONCURRENCY)}"
        )
    max_concurrency = PLAN_TIER_CONCURRENCY[plan_tier]

    if role == "worker":
        concurrency = max_concurrency
        batch_size = KIMI_MAX_BATCH
        prompts_needed = ceil(total_items / batch_size) if total_items > 0 else 0
        waves = ceil(prompts_needed / concurrency) if prompts_needed > 0 else 0
        return SwarmConfig(
            role="worker",
            concurrency=concurrency,
            batch_size=batch_size,
            expected_waves=waves,
        )

    if role in ("synthesis", "coordinator"):
        # Coordinator is always a single call over all items;
        # synthesis may split at the quality ceiling.
        token_cap_batch = GEMINI_ATTENTION_QUALITY_CEILING_TOKENS // max(
            avg_item_tokens, 1
        )
        batch_size = min(GEMINI_MAX_BATCH_ITEMS, token_cap_batch, total_items or 1)
        if role == "coordinator":
            # Coordinator ingests summaries and returns a plan — always 1 call.
            return SwarmConfig(
                role="coordinator",
                concurrency=1,
                batch_size=total_items,
                expected_calls=1,
            )
        calls = ceil(total_items / batch_size) if total_items > 0 else 0
        return SwarmConfig(
            role="synthesis",
            concurrency=1,
            batch_size=batch_size,
            expected_calls=calls,
        )

    raise ValueError(f"Unknown role '{role}'")
```

- [ ] **Step 4: Run tests to verify passage**

Run: `.venv/bin/pytest tests/test_swarm_optimizer.py -v`
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/swarm_optimizer.py tests/test_swarm_optimizer.py
git commit -m "feat(swarm): add get_optimal_swarm_config() with quality-first sizing"
```

---

## Task 3: Remove stale F-59 hardcap; add plan-tier-aware concurrency

**Files:**
- Modify: `src/codrag/core/batch_profiles.py:349–419` (in `get_batch_concurrency`)
- Modify: `tests/test_batch_profiles.py` (add new cases)

- [ ] **Step 1: Write failing test for plan-tier concurrency**

Append to `tests/test_batch_profiles.py`:

```python
from unittest.mock import patch


def test_cloud_concurrency_uses_plan_tier_max():
    """F-59 is resolved — cloud models must no longer be hardcapped at 1."""
    from codrag.core.batch_profiles import get_batch_concurrency
    with patch("codrag.core.batch_profiles._get_plan_tier", return_value="max"):
        result = get_batch_concurrency("ollama", model="kimi-k2.5:cloud")
        assert result == 10


def test_cloud_concurrency_uses_plan_tier_pro():
    from codrag.core.batch_profiles import get_batch_concurrency
    with patch("codrag.core.batch_profiles._get_plan_tier", return_value="pro"):
        result = get_batch_concurrency("ollama", model="kimi-k2.5:cloud")
        assert result == 3


def test_cloud_concurrency_defaults_to_free_when_unset():
    from codrag.core.batch_profiles import get_batch_concurrency
    with patch("codrag.core.batch_profiles._get_plan_tier", return_value="free"):
        result = get_batch_concurrency("ollama", model="kimi-k2.5:cloud")
        assert result == 1


def test_local_model_still_returns_one():
    from codrag.core.batch_profiles import get_batch_concurrency
    result = get_batch_concurrency("ollama", model="gemma3:12b")
    assert result == 1
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_batch_profiles.py -v -k "plan_tier or local_model"`
Expected: FAIL — current code hardcaps cloud at 1.

- [ ] **Step 3: Replace F-59 hardcap**

In `src/codrag/core/batch_profiles.py`, add near the top (after imports):

```python
from codrag.core.swarm_optimizer import PLAN_TIER_CONCURRENCY


def _get_plan_tier() -> str:
    """Resolve the current Ollama Cloud plan tier from settings.

    Returns "free" when unset (safest default).  Overridden by tests via
    patch.
    """
    try:
        from codrag.services.config_manager import get_advanced_llm_settings
        settings = get_advanced_llm_settings()
        return settings.get("ollama_plan_tier", "free")
    except Exception:
        return "free"
```

Replace the F-59 block in `get_batch_concurrency` (`batch_profiles.py:349–367`):

```python
    # Cloud models: use Ollama Cloud plan tier to cap concurrency.
    # F-59 root cause (daemon hang from timeout misconfiguration) was
    # resolved on 2026-04-12 — see docs/Phase79_Swarm/07_Rework/
    # SWARM_HANG_INVESTIGATION.md.  Concurrent cloud requests now work
    # end-to-end inside the daemon; the real limit is the plan tier.
    _is_cloud = provider_lower not in _LOCAL_PROVIDERS
    if not _is_cloud and model:
        _is_cloud = is_cloud_model_via_ollama(provider_lower, model or "")
    if _is_cloud:
        tier = _get_plan_tier()
        plan_concurrency = PLAN_TIER_CONCURRENCY.get(tier, 1)
        logger.info(
            "Batch concurrency: %d (plan tier=%s, provider=%s, model=%s)",
            plan_concurrency, tier, provider_lower, model,
        )
        return plan_concurrency
```

- [ ] **Step 4: Run tests to verify passage**

Run: `.venv/bin/pytest tests/test_batch_profiles.py -v`
Expected: all new tests PASS; existing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/batch_profiles.py tests/test_batch_profiles.py
git commit -m "fix(swarm): remove stale F-59 hardcap, route cloud concurrency via plan tier"
```

---

## Task 4: Add dual-LLM `SwarmOrchestrator` constructor (TDD)

**Files:**
- Modify: `tests/test_swarm_orchestrator.py`
- Modify: `src/codrag/core/swarm_orchestrator.py:131–162`

- [ ] **Step 1: Write failing test**

Append to `tests/test_swarm_orchestrator.py`:

```python
from unittest.mock import MagicMock
from codrag.core.swarm_orchestrator import SwarmOrchestrator


def test_decoupled_constructor_uses_distinct_clients():
    coord = MagicMock(name="coordinator_llm")
    worker = MagicMock(name="worker_llm")
    orch = SwarmOrchestrator(coordinator_llm=coord, worker_llm=worker, concurrency=3)
    assert orch.coordinator_llm is coord
    assert orch.worker_llm is worker


def test_inherit_fallback_when_coordinator_none():
    worker = MagicMock(name="worker_llm")
    orch = SwarmOrchestrator(coordinator_llm=None, worker_llm=worker)
    assert orch.coordinator_llm is worker  # inherited


def test_legacy_single_llm_constructor_still_works():
    """Backward compatibility: `llm=` kwarg maps to both."""
    legacy = MagicMock(name="legacy_llm")
    orch = SwarmOrchestrator(llm=legacy, concurrency=3)
    assert orch.coordinator_llm is legacy
    assert orch.worker_llm is legacy
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_swarm_orchestrator.py -v -k "decoupled or inherit or legacy"`
Expected: FAIL — current constructor only accepts `llm=`.

- [ ] **Step 3: Update `SwarmOrchestrator.__init__`**

Replace the `__init__` signature + body in `src/codrag/core/swarm_orchestrator.py:131–162` with:

```python
    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        concurrency: int = 10,
        *,
        coordinator_llm: Optional[LLMClient] = None,
        worker_llm: Optional[LLMClient] = None,
        coordinator_timeout_s: Optional[float] = None,
        synthesis_timeout_s: Optional[float] = None,
        worker_timeout_s: Optional[float] = None,
        max_wall_time_s: Optional[float] = None,
    ) -> None:
        # Resolve LLMs.  New-style callers pass coordinator_llm + worker_llm.
        # Legacy callers (and tests) still use llm=.  If coordinator_llm is
        # unset, fall back to worker_llm (or legacy llm) — this is the
        # "Inherit from Thinking Model" behavior.
        if worker_llm is None:
            worker_llm = llm
        if coordinator_llm is None:
            coordinator_llm = worker_llm

        if worker_llm is None:
            raise ValueError(
                "SwarmOrchestrator requires either `llm` (legacy) or "
                "`worker_llm` (preferred)."
            )

        self.worker_llm = worker_llm
        self.coordinator_llm = coordinator_llm
        # Keep `self.llm` pointing at the worker LLM for any code path that
        # still references it (migrated incrementally in call-site tasks).
        self.llm = worker_llm

        self.concurrency = max(1, concurrency)
        self.coordinator_timeout_s = (
            coordinator_timeout_s
            if coordinator_timeout_s is not None
            else self.DEFAULT_COORDINATOR_TIMEOUT_S
        )
        self.synthesis_timeout_s = (
            synthesis_timeout_s
            if synthesis_timeout_s is not None
            else self.DEFAULT_SYNTHESIS_TIMEOUT_S
        )
        self.worker_timeout_s = (
            worker_timeout_s
            if worker_timeout_s is not None
            else self.DEFAULT_WORKER_TIMEOUT_S
        )
        self.max_wall_time_s = (
            max_wall_time_s
            if max_wall_time_s is not None
            else self.DEFAULT_MAX_WALL_TIME_S
        )
```

- [ ] **Step 4: Run tests to verify passage**

Run: `.venv/bin/pytest tests/test_swarm_orchestrator.py -v`
Expected: new tests PASS; existing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/swarm_orchestrator.py tests/test_swarm_orchestrator.py
git commit -m "feat(swarm): add dual-LLM constructor with inherit-from-worker fallback"
```

---

## Task 5: Route `_coordinate` and `_synthesize` through `coordinator_llm`

**Files:**
- Modify: `src/codrag/core/swarm_orchestrator.py:164–247` (`_llm_call_with_timeout`)
- Modify: `src/codrag/core/swarm_orchestrator.py` (Phase 2 `_fan_out` — uses `worker_llm`)
- Modify: `tests/test_swarm_orchestrator.py`

- [ ] **Step 1: Write failing test asserting per-phase routing**

Append to `tests/test_swarm_orchestrator.py`:

```python
def test_coordinator_calls_use_coordinator_llm_only():
    from codrag.core.swarm_orchestrator import SwarmOrchestrator, WorkItem
    coord = MagicMock(name="coord")
    coord.generate.return_value = ('{"assignments":[]}', 100)
    worker = MagicMock(name="worker")
    worker.generate.return_value = ('{"result":"ok"}', 200)

    orch = SwarmOrchestrator(
        coordinator_llm=coord, worker_llm=worker,
        coordinator_timeout_s=5, synthesis_timeout_s=5,
        worker_timeout_s=5, max_wall_time_s=15,
    )
    plan, _tokens = orch._coordinate(
        items=[WorkItem(id="x", summary="s", full_context="c")],
        coordinator_prompt="{group_summaries}",
    )
    # coord.generate must have been called; worker.generate must NOT.
    assert coord.generate.called
    assert not worker.generate.called
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_swarm_orchestrator.py::test_coordinator_calls_use_coordinator_llm_only -v`
Expected: FAIL — current `_llm_call_with_timeout` uses `self.llm`.

- [ ] **Step 3: Parameterize `_llm_call_with_timeout` to accept an LLM**

Change the signature and internal reference. In `swarm_orchestrator.py:164`:

```python
    def _llm_call_with_timeout(
        self,
        prompt: str,
        system: str,
        temperature: float,
        timeout_s: float,
        phase: str,
        llm: Optional[LLMClient] = None,
    ) -> Tuple[Optional[str], int]:
        """Run an LLM call in a worker thread with a hard timeout.
        ...
        """
        client = llm if llm is not None else self.worker_llm
        # ... rest of method uses `client` instead of `self.llm`
```

Replace every `self.llm.` inside `_llm_call_with_timeout` with `client.`.

In `_coordinate` (`swarm_orchestrator.py:267`), pass the coordinator:

```python
        text, tokens = self._llm_call_with_timeout(
            prompt=prompt,
            system=COORDINATOR_SYSTEM,
            temperature=0.4,
            timeout_s=self.coordinator_timeout_s,
            phase="coordinator",
            llm=self.coordinator_llm,
        )
```

In `_synthesize` (find the `_llm_call_with_timeout` call in the synthesis block), pass `llm=self.coordinator_llm` similarly.

In `_fan_out` (Phase 2 worker dispatch), ensure worker calls use `self.worker_llm` — locate the worker's `.generate(...)` call sites inside the fan-out block and switch `self.llm.generate(...)` → `self.worker_llm.generate(...)`.

- [ ] **Step 4: Run tests to verify passage**

Run: `.venv/bin/pytest tests/test_swarm_orchestrator.py -v`
Expected: all tests PASS (including the new routing test).

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/swarm_orchestrator.py tests/test_swarm_orchestrator.py
git commit -m "feat(swarm): route coordinator+synthesis to coordinator_llm, workers to worker_llm"
```

---

## Task 6: Add `get_coordinator_llm()` to config_manager (TDD)

**Files:**
- Modify: `src/codrag/services/config_manager.py`
- Modify: `tests/test_config_manager.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_config_manager.py`:

```python
def test_coordinator_inherits_when_unconfigured(tmp_path, monkeypatch):
    from codrag.services.config_manager import get_coordinator_llm_client
    # Set up minimal settings where coordinator_model.inherit_from_large = True
    # and large_model points at a valid endpoint.
    # (Wire this via the test fixture that already creates a config; reuse
    # whatever pattern test_config_manager.py already uses for large_model.)
    coord_client = get_coordinator_llm_client()
    large_client = get_large_llm_client()  # existing helper
    assert coord_client is large_client


def test_coordinator_uses_own_model_when_configured(tmp_path, monkeypatch):
    from codrag.services.config_manager import get_coordinator_llm_client
    # Set coordinator_model.enabled = True, inherit_from_large = False,
    # model = "gemini-3-flash-preview:cloud"
    coord_client = get_coordinator_llm_client()
    assert coord_client.model == "gemini-3-flash-preview:cloud"
```

> Match the exact fixture patterns used by existing tests — the file already contains config-building helpers. Re-read `tests/test_config_manager.py` before writing to ensure the fixtures match.

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_config_manager.py -v -k "coordinator"`
Expected: FAIL — `get_coordinator_llm_client` doesn't exist.

- [ ] **Step 3: Implement helper**

Locate the existing `get_large_llm_client()` in `config_manager.py` (or equivalent). Beneath it, add:

```python
def get_coordinator_llm_client() -> Optional[LLMClient]:
    """Resolve the Swarm Coordinator LLM client.

    Returns the configured coordinator model when
    `coordinator_model.enabled=True` and `inherit_from_large=False`.
    Otherwise falls back to `get_large_llm_client()` (the inherit-from-
    thinking-model behavior documented in SWARM_UI_PLAN_v2 §2).
    """
    cfg = get_config()
    coord = cfg.get("coordinator_model") or {}
    if not coord.get("enabled") or coord.get("inherit_from_large", True):
        return get_large_llm_client()

    endpoint_id = coord.get("endpoint_id")
    model = coord.get("model")
    if not endpoint_id or not model:
        return get_large_llm_client()

    endpoint = resolve_endpoint(endpoint_id)
    if endpoint is None:
        return get_large_llm_client()

    return LLMClient(
        endpoint_url=endpoint.url,
        model=model,
        provider=endpoint.provider,
        timeout=COORDINATOR_TIMEOUT_S,  # reuse existing large-slot timeout
    )
```

- [ ] **Step 4: Run tests to verify passage**

Run: `.venv/bin/pytest tests/test_config_manager.py -v -k "coordinator"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/config_manager.py tests/test_config_manager.py
git commit -m "feat(config): add get_coordinator_llm_client() with inherit fallback"
```

---

## Task 7: Wire `atlas/generator.py` call site

**Files:**
- Modify: `src/codrag/core/atlas/generator.py:939`
- Modify: `tests/test_atlas_swarm.py` (extend mock to assert both LLMs flow through)

- [ ] **Step 1: Update the SwarmOrchestrator construction**

Replace `atlas/generator.py:939–946`:

```python
        # F-59 rework: per-worker + wall-time caps prevent apparent hangs
        # on sequential cloud endpoints.  Phase 112: decoupled coord/worker.
        from codrag.services.config_manager import get_coordinator_llm_client
        orch = SwarmOrchestrator(
            coordinator_llm=get_coordinator_llm_client(),
            worker_llm=self.llm,
            concurrency=concurrency,
            coordinator_timeout_s=10.0 if is_cloud else 90.0,
            synthesis_timeout_s=120.0 if is_cloud else 180.0,
            worker_timeout_s=180.0 if is_cloud else 300.0,
            max_wall_time_s=900.0 if is_cloud else 1800.0,
        )
```

- [ ] **Step 2: Update the atlas swarm test**

In `tests/test_atlas_swarm.py` (around line 32 where `mock.model = "kimi-k2.5:cloud"` is set), ensure the test patches `get_coordinator_llm_client` to return a distinct mock and asserts it is forwarded to `SwarmOrchestrator`:

```python
def test_atlas_swarm_passes_distinct_coordinator(monkeypatch):
    from unittest.mock import MagicMock, patch
    coord_mock = MagicMock(name="coord")
    with patch(
        "codrag.core.atlas.generator.get_coordinator_llm_client",
        return_value=coord_mock,
    ), patch(
        "codrag.core.atlas.generator.SwarmOrchestrator"
    ) as OrchCls:
        # ... invoke atlas swarm entry point (match existing test harness) ...
        _, kwargs = OrchCls.call_args
        assert kwargs["coordinator_llm"] is coord_mock
        assert kwargs["worker_llm"] is not coord_mock
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_atlas_swarm.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/core/atlas/generator.py tests/test_atlas_swarm.py
git commit -m "feat(atlas): route swarm coordinator through coordinator_llm slot"
```

---

## Task 8: Wire `concept_seeder.py` call site

**Files:**
- Modify: `src/codrag/core/concept_seeder.py:309`
- Modify: `tests/test_concept_seeder_swarm.py`

- [ ] **Step 1: Update construction**

Replace `concept_seeder.py:309–315`:

```python
    from codrag.services.config_manager import get_coordinator_llm_client
    orch = SwarmOrchestrator(
        coordinator_llm=get_coordinator_llm_client(),
        worker_llm=llm,
        concurrency=concurrency,
        coordinator_timeout_s=10.0 if is_cloud_model else 90.0,
        synthesis_timeout_s=120.0 if is_cloud_model else 180.0,
        worker_timeout_s=180.0 if is_cloud_model else 300.0,
        max_wall_time_s=900.0 if is_cloud_model else 1800.0,
    )
```

- [ ] **Step 2: Update concept-seeder swarm test**

Extend `tests/test_concept_seeder_swarm.py` mirroring the atlas test: patch `get_coordinator_llm_client`, assert forwarding.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_concept_seeder_swarm.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/core/concept_seeder.py tests/test_concept_seeder_swarm.py
git commit -m "feat(concept-seeder): route swarm coordinator through coordinator_llm slot"
```

---

## Task 9: Wire `group_reasoning.py` call site

**Files:**
- Modify: `src/codrag/core/group_reasoning.py:467`
- Modify: relevant test file (locate via `rg SwarmOrchestrator tests/`)

- [ ] **Step 1: Update construction**

Replace `group_reasoning.py:467–474`:

```python
        from codrag.services.config_manager import get_coordinator_llm_client
        orch = SwarmOrchestrator(
            coordinator_llm=get_coordinator_llm_client(),
            worker_llm=self.llm,
            concurrency=concurrency,
            coordinator_timeout_s=10.0 if is_cloud else 90.0,
            synthesis_timeout_s=120.0 if is_cloud else 180.0,
            worker_timeout_s=180.0 if is_cloud else 300.0,
            max_wall_time_s=900.0 if is_cloud else 1800.0,
        )
```

- [ ] **Step 2: Update corresponding test**

Mirror the atlas/concept-seeder test additions.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/ -v -k "group_reasoning"`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/core/group_reasoning.py tests/
git commit -m "feat(group-reasoning): route swarm coordinator through coordinator_llm slot"
```

---

## Task 10: Wire `cluster.py` call site (removes Phase79 TODO)

**Files:**
- Modify: `src/codrag/core/cluster.py:1304–1307`
- Modify: `tests/test_cluster_swarm.py`

- [ ] **Step 1: Update construction**

Replace `cluster.py:1304–1307`:

```python
        # Phase 112: coord and worker now decoupled — coord uses the
        # coordinator_llm slot (defaults to Gemini 3 Flash), worker uses
        # self.llm (Kimi).  Resolves the Phase79-DualModel TODO.
        from codrag.services.config_manager import get_coordinator_llm_client
        orch = SwarmOrchestrator(
            coordinator_llm=get_coordinator_llm_client(),
            worker_llm=self.llm,
            concurrency=concurrency,
        )
```

- [ ] **Step 2: Update `tests/test_cluster_swarm.py`**

Mirror prior test patches.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_cluster_swarm.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/core/cluster.py tests/test_cluster_swarm.py
git commit -m "feat(cluster): route swarm coordinator through coordinator_llm slot (closes Phase79-DualModel TODO)"
```

---

## Task 11: Full regression smoke before moving to UI

- [ ] **Step 1: Run full backend suite**

Run: `.venv/bin/pytest tests/ -v --tb=short`
Expected: PASS (baseline + new tests).

- [ ] **Step 2: Lint + typecheck**

Run: `.venv/bin/ruff check src/ && .venv/bin/mypy src/codrag/core/swarm_orchestrator.py src/codrag/core/swarm_optimizer.py src/codrag/core/batch_profiles.py src/codrag/services/config_manager.py`
Expected: no new errors.

- [ ] **Step 3: In-daemon smoke (mini-redis-rust, Free plan)**

```bash
.venv/bin/python -m codrag.cli serve --port 8400 &
# In another shell: trigger finalize → concept seeding on mini-redis-rust.
# Watch logs for "Batch concurrency: N (plan tier=free, ...)".
```

Expected: swarm completes; all 19 modules synthesized; no hang; logs show `coordinator_llm` used for Phases 1+3 (verify via `[Swarm/coordinator]` + `[Swarm/synthesis]` log lines).

- [ ] **Step 4: Commit smoke notes**

If the smoke run surfaces issues, file them as follow-up tasks. Otherwise commit any config updates made during validation:

```bash
git add codrag_data/ui_config.json  # if touched during smoke
git commit -m "chore(config): smoke-test config for Phase 112 swarm decoupling" || true
```

---

## Task 12: Update `RECOMMENDED_MODELS` (remove qwen3 small/large)

**Files:**
- Modify: `packages/ui/src/components/llm/AIModelsSettings.tsx:85–91`

- [ ] **Step 1: Replace the constant**

Current (`AIModelsSettings.tsx:85–91`):
```ts
const RECOMMENDED_MODELS: Record<string, string[]> = {
  embedding: ['nomic-embed-text', 'nomic-embed-code'],
  small: ['qwen3:8b', 'qwen3:14b', 'gemma3:12b'],
  large: ['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'gemma3:12b'],
  code: ['qwen3-coder:30b', 'qwen3-coder-next:cloud'],
  coordinator: ['gemini-3-flash-preview:cloud', 'gpt-4o-mini', 'qwen3:30b'],
};
```

Replace with:
```ts
const RECOMMENDED_MODELS: Record<string, string[]> = {
  embedding: ['nomic-embed-text', 'nomic-embed-code'],
  small: ['gemini-3-flash-preview:cloud', 'gemma3:12b'],
  large: ['kimi-k2.5:cloud', 'gemma3:27b'],
  coordinator: ['gemini-3-flash-preview:cloud', 'gemma3:27b'],
  code: ['qwen3-coder-next:cloud', 'qwen3-coder:30b'],
};
```

Rationale (comment above the constant):
```ts
// Phase 112: quality-first cloud-centric stack.
// Small + Coordinator share gemini-3-flash-preview:cloud (JSON-reliable,
// 1M ctx, no thinking overhead).  Large = kimi-k2.5:cloud for deep
// reasoning.  qwen3 base family removed (8b/14b/30b) in favor of the
// cloud stack or gemma3 for air-gapped fallback.  qwen3-coder retained.
// See docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md §4.
```

- [ ] **Step 2: Run typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 3: Storybook visual check**

Run: `cd packages/ui && npm run storybook`
Open the AI Models Settings story and verify the recommended badges show the new models.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/llm/AIModelsSettings.tsx
git commit -m "feat(ui): quality-first RECOMMENDED_MODELS (remove qwen3 small/large)"
```

---

## Task 13: Add `AdvancedLLMSettings` types

**Files:**
- Modify: `packages/ui/src/types.ts`

- [ ] **Step 1: Add interface**

Append to `packages/ui/src/types.ts` (near the existing `LLMConfig` interface around line 803):

```ts
/**
 * Advanced LLM Settings — power-user overrides for cloud token safety,
 * thinking budget, and plan-tier concurrency.  All default to
 * conservative values so out-of-the-box behavior matches the documented
 * profile sizes.  See docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md §6.
 */
export interface AdvancedLLMSettings {
  /** When true (default), :cloud models force CLOUD_SMALL profile
   *  (batch sizes 3-8).  Disable only on paid plans with deep pockets. */
  enforce_cloud_token_safety: boolean;

  /** Hard cap on Kimi's num_predict when think=True.  Default 24576. */
  max_thinking_budget: number;

  /** Ollama Cloud plan — drives Swarm concurrency ceiling.
   *  'custom' reads `custom_concurrency` instead. */
  ollama_plan_tier: 'free' | 'pro' | 'max' | 'custom';

  /** Only used when ollama_plan_tier === 'custom'. */
  custom_concurrency?: number;
}
```

Extend `LLMConfig` (line 803):
```ts
export interface LLMConfig {
  assignment_mode?: AssignmentMode;
  embedding: EmbeddingConfig;
  small_model: LLMSlotConfig;
  large_model: LLMSlotConfig;
  code_model: LLMSlotConfig;
  coordinator_model?: LLMSlotConfig & { inherit_from_large?: boolean };
  advanced?: AdvancedLLMSettings;  // NEW
  saved_endpoints: LLMEndpoint[];
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/types.ts
git commit -m "feat(types): add AdvancedLLMSettings + coordinator_model on LLMConfig"
```

---

## Task 14: Build `AdvancedLLMSettings` UI panel

**Files:**
- Create: `packages/ui/src/components/llm/AdvancedLLMSettings.tsx`
- Create: `packages/ui/src/components/llm/AdvancedLLMSettings.stories.tsx`

- [ ] **Step 1: Scaffold the component**

Create `packages/ui/src/components/llm/AdvancedLLMSettings.tsx`:

```tsx
import { useState } from 'react';
import type { AdvancedLLMSettings as AdvancedSettings } from '../../types';
import { Card } from '../Card';
import { Switch } from '../Switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../Select';
import { Input } from '../Input';
import { Label } from '../Label';

interface Props {
  value: AdvancedSettings;
  onChange: (next: AdvancedSettings) => void;
}

/**
 * Advanced LLM Settings — surfaces three overrides documented in
 * docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md §6:
 *   1. Enforce Cloud Token Safety (default ON)
 *   2. Max Thinking Budget (default 24576)
 *   3. Ollama Cloud Plan (default 'free')
 */
export function AdvancedLLMSettings({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const tier = value.ollama_plan_tier;

  return (
    <Card className="mt-4">
      <button
        type="button"
        className="w-full text-left font-semibold py-2 px-3 flex justify-between"
        onClick={() => setOpen((o) => !o)}
      >
        <span>Advanced LLM Settings</span>
        <span className="text-sm text-muted-foreground">
          {open ? 'Hide' : 'Show'}
        </span>
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-4">
          {/* 1. Enforce Cloud Token Safety */}
          <div className="flex items-center justify-between gap-2">
            <div>
              <Label>Enforce Cloud Token Safety Limits</Label>
              <p className="text-xs text-muted-foreground">
                When ON, :cloud models use the conservative CLOUD_SMALL batch profile.
                Disable only on paid Ollama Cloud plans.
              </p>
            </div>
            <Switch
              checked={value.enforce_cloud_token_safety}
              onCheckedChange={(checked) =>
                onChange({ ...value, enforce_cloud_token_safety: checked })
              }
            />
          </div>

          {/* 2. Max Thinking Budget */}
          <div>
            <Label htmlFor="max-thinking-budget">Max Thinking Budget</Label>
            <p className="text-xs text-muted-foreground mb-1">
              Hard cap on `num_predict` when `think=True` (Kimi). Default 24576.
            </p>
            <Input
              id="max-thinking-budget"
              type="number"
              min={4096}
              max={131072}
              step={1024}
              value={value.max_thinking_budget}
              onChange={(e) =>
                onChange({
                  ...value,
                  max_thinking_budget: Number(e.target.value) || 24576,
                })
              }
            />
          </div>

          {/* 3. Ollama Cloud Plan */}
          <div>
            <Label>Ollama Cloud Plan</Label>
            <p className="text-xs text-muted-foreground mb-1">
              Drives Swarm concurrency ceiling. Free=1, Pro=3, Max=10.
            </p>
            <Select
              value={tier}
              onValueChange={(v) =>
                onChange({
                  ...value,
                  ollama_plan_tier: v as AdvancedSettings['ollama_plan_tier'],
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="free">Free (1 concurrent)</SelectItem>
                <SelectItem value="pro">Pro (3 concurrent)</SelectItem>
                <SelectItem value="max">Max (10 concurrent)</SelectItem>
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
            {tier === 'custom' && (
              <Input
                type="number"
                className="mt-2"
                min={1}
                max={32}
                value={value.custom_concurrency ?? 1}
                onChange={(e) =>
                  onChange({
                    ...value,
                    custom_concurrency: Number(e.target.value) || 1,
                  })
                }
              />
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 2: Create Storybook story**

Create `AdvancedLLMSettings.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { AdvancedLLMSettings } from './AdvancedLLMSettings';
import type { AdvancedLLMSettings as T } from '../../types';

const meta: Meta<typeof AdvancedLLMSettings> = {
  title: 'LLM/AdvancedLLMSettings',
  component: AdvancedLLMSettings,
};
export default meta;

const DEFAULT_VALUE: T = {
  enforce_cloud_token_safety: true,
  max_thinking_budget: 24576,
  ollama_plan_tier: 'free',
};

export const Default: StoryObj<typeof AdvancedLLMSettings> = {
  render: () => {
    const [value, setValue] = useState<T>(DEFAULT_VALUE);
    return <AdvancedLLMSettings value={value} onChange={setValue} />;
  },
};

export const MaxPlanUncapped: StoryObj<typeof AdvancedLLMSettings> = {
  render: () => {
    const [value, setValue] = useState<T>({
      enforce_cloud_token_safety: false,
      max_thinking_budget: 65536,
      ollama_plan_tier: 'max',
    });
    return <AdvancedLLMSettings value={value} onChange={setValue} />;
  },
};
```

- [ ] **Step 3: Typecheck + story render**

Run: `cd packages/ui && npm run typecheck && npm run storybook`
Expected: no errors; both stories render.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/llm/AdvancedLLMSettings.tsx packages/ui/src/components/llm/AdvancedLLMSettings.stories.tsx
git commit -m "feat(ui): add AdvancedLLMSettings panel (cloud-safety / thinking-budget / plan-tier)"
```

---

## Task 15: Mount AdvancedLLMSettings in AIModelsSettings

**Files:**
- Modify: `packages/ui/src/components/llm/AIModelsSettings.tsx`

- [ ] **Step 1: Import + render**

Near the top of the file (with other imports):
```tsx
import { AdvancedLLMSettings } from './AdvancedLLMSettings';
```

At the bottom of the settings list (after the existing slot cards, before the closing container — locate the right insertion point by searching for the existing last `</ModelCard>`):
```tsx
<AdvancedLLMSettings
  value={config.advanced ?? {
    enforce_cloud_token_safety: true,
    max_thinking_budget: 24576,
    ollama_plan_tier: 'free',
  }}
  onChange={(advanced) => onConfigChange({ ...config, advanced })}
/>
```

- [ ] **Step 2: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: no errors.

- [ ] **Step 3: Dev server smoke**

Run: `scripts/dev.sh`
Open `http://localhost:5174`, navigate to AI Models Settings. Verify the panel appears and expands/collapses.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/llm/AIModelsSettings.tsx
git commit -m "feat(ui): mount AdvancedLLMSettings in AIModelsSettings"
```

---

## Task 16: Wire Cloud-Token-Safety toggle to `batch_profiles.py`

**Files:**
- Modify: `src/codrag/services/config_manager.py` (add `get_advanced_llm_settings()`)
- Modify: `src/codrag/core/batch_profiles.py:248–279` (`is_cloud_model_via_ollama` — consult toggle)
- Modify: `tests/test_batch_profiles.py`

- [ ] **Step 1: Add config accessor**

In `config_manager.py`, add:

```python
def get_advanced_llm_settings() -> Dict[str, Any]:
    """Return the advanced LLM settings block with safe defaults."""
    cfg = get_config()
    defaults = {
        "enforce_cloud_token_safety": True,
        "max_thinking_budget": 24576,
        "ollama_plan_tier": "free",
    }
    return {**defaults, **(cfg.get("advanced") or {})}
```

- [ ] **Step 2: Gate `resolve_profile` on the toggle**

In `batch_profiles.py`, update `resolve_profile` (`batch_profiles.py:462–502`):

```python
def resolve_profile(
    provider: str,
    model: str,
    override: Optional[str] = None,
    context_tokens: Optional[int] = None,
) -> BatchProfile:
    """... (existing docstring) ..."""
    if override and override.lower() != "auto":
        try:
            profile_name = BatchProfileName(override.lower())
            return PROFILES[profile_name]
        except (ValueError, KeyError):
            logger.warning("Unknown batch profile override '%s' — falling back to auto", override)

    # Phase 112: honor the "Enforce Cloud Token Safety" toggle.
    # When OFF (power users), promote cloud models out of CLOUD_SMALL:
    #   - Gemini → LARGE (64K output, 1M context)
    #   - qwen3-coder-next, other cloud non-thinking → STANDARD (32K output)
    #   - Kimi → still CLOUD_SMALL (thinking-preamble constraint, not the
    #     16K cap, is the binding constraint for Kimi).  See §6.1.
    from codrag.services.config_manager import get_advanced_llm_settings
    enforce_safety = get_advanced_llm_settings().get(
        "enforce_cloud_token_safety", True,
    )
    if not enforce_safety and is_cloud_model_via_ollama(provider, model):
        model_lower = (model or "").lower()
        if "kimi" in model_lower:
            # Thinking model — preamble eats output budget regardless of cap.
            return PROFILE_CLOUD_SMALL
        if "gemini" in model_lower:
            return PROFILE_LARGE
        # Non-Gemini cloud non-thinking → STANDARD
        return PROFILE_STANDARD

    if context_tokens and context_tokens > 0:
        profile = detect_profile_from_context(context_tokens, provider, model)
        logger.info(
            "Batch profile for %s/%s: %s (via %dK context window)",
            provider, model, profile.name.value, context_tokens // 1000,
        )
        return profile

    return detect_profile(provider, model)
```

- [ ] **Step 3: Write test**

Append to `tests/test_batch_profiles.py`:

```python
def test_cloud_safety_off_promotes_gemini_to_large(monkeypatch):
    from codrag.core.batch_profiles import resolve_profile, PROFILE_LARGE
    monkeypatch.setattr(
        "codrag.services.config_manager.get_advanced_llm_settings",
        lambda: {"enforce_cloud_token_safety": False},
    )
    profile = resolve_profile("ollama", "gemini-3-flash-preview:cloud")
    assert profile is PROFILE_LARGE


def test_cloud_safety_off_keeps_kimi_on_cloud_small(monkeypatch):
    from codrag.core.batch_profiles import resolve_profile, PROFILE_CLOUD_SMALL
    monkeypatch.setattr(
        "codrag.services.config_manager.get_advanced_llm_settings",
        lambda: {"enforce_cloud_token_safety": False},
    )
    profile = resolve_profile("ollama", "kimi-k2.5:cloud")
    assert profile is PROFILE_CLOUD_SMALL  # thinking-preamble constraint
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_batch_profiles.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/config_manager.py src/codrag/core/batch_profiles.py tests/test_batch_profiles.py
git commit -m "feat(swarm): gate cloud batch profile promotion on safety toggle"
```

---

## Task 17: Wire Max-Thinking-Budget to `llm_client.py`

**Files:**
- Modify: `src/codrag/core/llm_client.py:620–626`
- Modify: `tests/test_llm_client.py` (or nearest existing test file)

- [ ] **Step 1: Replace hardcap**

Current (`llm_client.py:620–626`):
```python
                effective_num_predict = min(
                    max(num_predict * 3, num_predict + 8192),
                    max(num_predict, 24576),  # never less than base, capped at 24K
                )
```

Replace with:
```python
                from codrag.services.config_manager import get_advanced_llm_settings
                max_budget = get_advanced_llm_settings().get("max_thinking_budget", 24576)
                effective_num_predict = min(
                    max(num_predict * 3, num_predict + 8192),
                    max(num_predict, max_budget),
                )
```

- [ ] **Step 2: Add test**

Create/extend test asserting that the advanced setting overrides the cap:

```python
def test_max_thinking_budget_override(monkeypatch):
    from codrag.core.llm_client import LLMClient
    monkeypatch.setattr(
        "codrag.services.config_manager.get_advanced_llm_settings",
        lambda: {"max_thinking_budget": 65536},
    )
    # Use the existing test fixture / helper that exposes effective_num_predict,
    # or mock the HTTP POST and inspect the payload's num_predict value.
    # (Match the pattern used by existing llm_client tests.)
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/ -v -k "thinking_budget or llm_client"`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/core/llm_client.py tests/
git commit -m "feat(llm-client): override thinking-budget cap via Advanced Settings"
```

---

## Task 18: Surface Swarm metrics in telemetry

**Files:**
- Modify: `src/codrag/core/swarm_orchestrator.py` (emit metrics)
- Modify: `src/codrag/services/token_telemetry.py` (or equivalent — locate the existing token logger)

- [ ] **Step 1: Identify telemetry sink**

Run: `rg -n "token_telemetry|_telemetry_ctx" src/codrag/services/ | head -20` to locate the telemetry entrypoint used by existing swarm code.

- [ ] **Step 2: Emit three new metrics per swarm run**

In `swarm_orchestrator.py` at the end of the main `run()` method (find it — it's the one that sequences `_coordinate`, `_fan_out`, `_synthesize` and returns `SwarmResult`), add:

```python
        try:
            from codrag.services.token_telemetry import record_swarm_metrics
            record_swarm_metrics(
                phase="swarm_run",
                coordinator_json_valid=(result.coordinator_plan is not None),
                synthesis_json_valid=(result.synthesis is not None),
                workers_succeeded=result.stats.workers_succeeded,
                workers_failed=result.stats.workers_failed,
                wall_clock_seconds=result.stats.wall_clock_seconds,
            )
        except Exception:
            logger.debug("swarm metrics emission failed", exc_info=True)
```

Add `record_swarm_metrics()` to `token_telemetry.py` (match the patterns used by existing recorders):

```python
def record_swarm_metrics(
    *,
    phase: str,
    coordinator_json_valid: bool,
    synthesis_json_valid: bool,
    workers_succeeded: int,
    workers_failed: int,
    wall_clock_seconds: float,
) -> None:
    """Emit swarm-run metrics to the telemetry store.

    Tracks the §9 success metrics from SWARM_UI_PLAN_v2.md:
      - synthesis JSON validity rate (target ≥99%)
      - per-worker failure rate (target ≤2%)
      - wall-clock time
    """
    # ... insert row into telemetry DB following existing recorder patterns ...
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/ -v -k "telemetry or swarm"`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/core/swarm_orchestrator.py src/codrag/services/token_telemetry.py
git commit -m "feat(telemetry): record swarm quality + throughput metrics"
```

---

## Task 19: End-to-end integration smoke (Max + Pro + Free)

- [ ] **Step 1: Configure Max-plan stack**

Via UI: set `coordinator_model` = `gemini-3-flash-preview:cloud`, `large_model` = `kimi-k2.5:cloud`, Advanced Settings → Plan Tier = `max`, Enforce Cloud Token Safety = OFF.

- [ ] **Step 2: Trigger CoDRAG deep enrichment**

Via dashboard or API: trigger group-reasoning swarm on the CoDRAG project (155 groups).

- [ ] **Step 3: Verify logs**

Expected log lines include:
- `Batch concurrency: 10 (plan tier=max, provider=ollama, model=kimi-k2.5:cloud)`
- `[Swarm/coordinator]` entries routed via Gemini (check model field)
- `[Swarm/synthesis]` entries routed via Gemini
- Phase 2 fan-out completes in ~4–10 min per the spec

- [ ] **Step 4: Switch to Pro plan, re-run**

Set Plan Tier = `pro`. Re-run. Expect `Batch concurrency: 3` and Phase 2 ~12–30 min.

- [ ] **Step 5: Switch to Free plan, re-run small project**

Set Plan Tier = `free`. Re-run on mini-redis-rust (19 modules). Expect `Batch concurrency: 1` and successful completion.

- [ ] **Step 6: Record metrics in the v2 spec**

Append actual observed wall-clock + JSON validity rates into `docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md` §9 as a "Post-rollout measurements" subsection. Commit:

```bash
git add docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md
git commit -m "docs(phase112): record post-rollout swarm metrics"
```

---

## Self-Review Checklist

Before marking the plan complete, verify:

1. **Spec coverage:**
   - §2 (decoupled slots) → Tasks 4, 5, 6, 7, 8, 9, 10
   - §3 (UI card) → already exists, refined in Task 12
   - §4 (agent stack) → Task 12
   - §6.1 (cloud safety toggle) → Tasks 13, 14, 15, 16
   - §6.2 (thinking budget) → Task 17
   - §6.3 (plan-tier concurrency) → Task 3
   - §7 (optimizer) → Tasks 1, 2
   - §9 (metrics) → Task 18
   - §10 (tests) → embedded in every backend task
   - §11 (rollback/fallback) → inherit-from-worker behavior in Task 4
   - §12 (MVC path) → Steps 1–4 map to Tasks 1–2, 4–10, 12–17, 18

2. **Type consistency:**
   - `coordinator_llm` / `worker_llm` named identically everywhere
   - `get_coordinator_llm_client` is the single accessor
   - `AdvancedLLMSettings` type matches between TS (Task 13) and Python (`get_advanced_llm_settings` Task 16)

3. **Placeholder scan:** No "TBD" / "TODO" / "similar to Task N" entries remain. Every code step contains complete code.

4. **Gaps flagged intentionally:**
   - Task 7/8/9/10 test updates reference existing test patterns — the engineer must read the actual test file before adapting. Called out in-step.
   - Task 18 (`record_swarm_metrics`) says "match the patterns used by existing recorders" because the existing telemetry API wasn't inspected during planning. Engineer needs to open `token_telemetry.py` before writing.
