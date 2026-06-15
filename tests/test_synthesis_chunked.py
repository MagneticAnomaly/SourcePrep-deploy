"""Phase 136 Part 09 Step 2 — chunked synthesis.

Tests the new chunked path in SwarmOrchestrator + the corresponding
telemetry surface in concept_seeder.

Spec: docs/Phase136_Dogfood-fixes/Part09_SynthesizerWallTimeRegression/STEP2_CHUNKED_SYNTHESIS_DESIGN.md
"""
from __future__ import annotations

import json
import os
from dataclasses import is_dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from prep.core.swarm_orchestrator import (
    SwarmOrchestrator,
    SwarmResult,
    WorkerResult,
)


# ── SwarmResult contract ───────────────────────────────────────────


def test_swarm_result_synthesis_chunk_count_default_is_1():
    """Backward compat: existing callers see chunk_count == 1."""
    r = SwarmResult()
    assert hasattr(r, "synthesis_chunk_count"), (
        "SwarmResult must carry synthesis_chunk_count so concept_seeder's "
        "diagnostic classifier can distinguish chunked from single-call paths"
    )
    assert r.synthesis_chunk_count == 1


def test_swarm_result_synthesis_meta_failed_default_is_false():
    """Backward compat: existing callers see meta_failed is False."""
    r = SwarmResult()
    assert hasattr(r, "synthesis_meta_failed"), (
        "SwarmResult must expose synthesis_meta_failed so the diagnostic "
        "classifier can fire chunked_meta_failed without re-deriving"
    )
    assert r.synthesis_meta_failed is False


# ── Config ─────────────────────────────────────────────────────────


def test_env_var_overrides_default_threshold(monkeypatch):
    """PREP_SYNTHESIS_CHUNK_MAX_WORKERS env var sets the threshold at
    init time.  Tests use a small value (e.g. 10) so they don't need
    to construct 200+ fake workers.
    """
    monkeypatch.setenv("PREP_SYNTHESIS_CHUNK_MAX_WORKERS", "10")

    # Build a fresh orchestrator AFTER the env is set (env is read in
    # __init__).  Bypass __init__'s LLM-client requirement by passing
    # a sentinel coordinator/worker pair that satisfies the type but
    # is never called in this test.
    class _StubLLM:
        model = "stub"
        def _resolve_scheduler_node_id(self):
            return ""

    stub = _StubLLM()
    orch = SwarmOrchestrator(
        coordinator_llm=stub,
        worker_llm=stub,
        concurrency=1,
    )
    assert orch.synthesis_chunk_max_workers == 10


def test_default_chunk_max_workers_is_200_when_env_unset(monkeypatch):
    """Default threshold matches the work-order's '~200 workers' guidance."""
    monkeypatch.delenv("PREP_SYNTHESIS_CHUNK_MAX_WORKERS", raising=False)

    class _StubLLM:
        model = "stub"
        def _resolve_scheduler_node_id(self):
            return ""

    stub = _StubLLM()
    orch = SwarmOrchestrator(
        coordinator_llm=stub,
        worker_llm=stub,
        concurrency=1,
    )
    assert orch.synthesis_chunk_max_workers == 200
