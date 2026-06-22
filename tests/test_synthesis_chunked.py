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


# ── Helpers ────────────────────────────────────────────────────────


def _make_orch(chunk_max: int = 200) -> SwarmOrchestrator:
    """Construct an orchestrator suitable for unit-testing _synthesize_chunked.
    Bypasses __init__'s LLM-client setup; sets only the attributes the
    code paths under test touch.
    """
    orch = SwarmOrchestrator.__new__(SwarmOrchestrator)
    orch.synthesis_timeout_s = 60.0
    orch.coordinator_llm = None
    orch.worker_llm = None
    orch.project_id = None
    orch.synthesis_chunk_max_workers = chunk_max
    return orch


def _ok_worker(item_id: str = "m1", concept_title: str = "T") -> WorkerResult:
    """Worker result with parsed JSON — enough to feed _synthesize."""
    return WorkerResult(
        item_id=item_id,
        raw_output="ignored",
        parsed={"concepts": [{"title": concept_title}], "questions": []},
        success=True,
    )


def _many_ok_workers(n: int, prefix: str = "m") -> List[WorkerResult]:
    """Generate N workers with distinct item_ids for chunk-count tests."""
    return [_ok_worker(item_id=f"{prefix}{i:03d}", concept_title=f"T-{i}")
            for i in range(n)]


# ── Dispatcher: below/above threshold ──────────────────────────────


def test_below_threshold_uses_single_call():
    """At exactly the threshold (200 with default config), the dispatcher
    must NOT chunk — single-call runs once.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(200)
    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 100)) as mock_llm:
        out = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # _llm_call_with_timeout called exactly once → single-call path.
    assert mock_llm.call_count == 1, (
        f"At threshold (200 == 200), dispatcher must use single-call; "
        f"got {mock_llm.call_count} LLM calls (would indicate chunking)"
    )
    parsed, tokens, raw_text, prompt_chars, meta_failed = out
    assert parsed == {"concepts": [{"title": "OK"}], "questions": []}
    assert meta_failed is False


def test_above_threshold_dispatches_correct_chunk_count():
    """At 798 workers, threshold 200, the chunked path must split into
    chunks of 200 + 200 + 200 + 198 and dispatch 4 + 1 = 5 LLM calls
    (4 per-chunk + 1 meta).
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(798)
    # Every per-chunk call AND the meta call returns the same valid JSON;
    # we count call_count to assert chunk math.
    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 50)) as mock_llm:
        out = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # 4 chunks (200+200+200+198) + 1 meta = 5 LLM dispatches.
    assert mock_llm.call_count == 5, (
        f"798 workers at threshold 200 → 4 chunks + 1 meta = 5 LLM calls; "
        f"got {mock_llm.call_count}"
    )

    # Each chunk's prompt is one of the LLM call's positional args.
    # Verify the per-chunk prompts together contain all 798 workers'
    # item_ids (sanity check that chunking actually split the workload).
    prompts_sent = []
    for call in mock_llm.call_args_list[:4]:  # first 4 are per-chunk
        # _llm_call_with_timeout(prompt=..., system=..., ...)
        prompts_sent.append(call.kwargs.get("prompt", ""))

    for i in range(798):
        item_id = f"m{i:03d}"
        assert any(item_id in p for p in prompts_sent), (
            f"Worker {item_id} should appear in exactly one chunk prompt"
        )


def test_chunked_full_success_has_meta_dict_and_no_meta_failed():
    """All 4 chunks + meta succeed: result.synthesis is the meta dict,
    synthesis_meta_failed is False, synthesis_chunk_count == 4.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(798)
    fake_text = '{"concepts": [{"title": "MetaConsolidated"}], "questions": []}'

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 100)):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert parsed == {"concepts": [{"title": "MetaConsolidated"}], "questions": []}
    assert meta_failed is False, (
        "Full chunked success must NOT set meta_failed"
    )


def test_chunked_synthesis_tokens_sum_across_chunks_and_meta():
    """Total tokens returned is the sum of per-chunk LLM tokens plus
    meta tokens.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(600)  # 3 chunks of 200
    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    # Each LLM call returns a different token count so the sum is
    # distinguishable from "took the last call's count".
    token_seq = iter([100, 200, 300, 400])  # 3 chunks + 1 meta
    def _fake_call(**kwargs):
        return fake_text, next(token_seq)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert tokens == 100 + 200 + 300 + 400, (
        f"tokens must be sum of per-chunk + meta calls; got {tokens}"
    )


def test_chunked_synthesis_prompt_chars_is_max_single_prompt_size():
    """synthesis_prompt_chars is the LARGEST single prompt sent
    (per-chunk or meta), not the sum.  Operators read it as 'worst-case
    prompt the LLM saw'.
    """
    orch = _make_orch(chunk_max=200)

    # Build workers whose parsed content has varying sizes so the
    # per-chunk prompts differ.
    small = WorkerResult(item_id="m000", raw_output="r",
                         parsed={"concepts": [{"title": "x"}]}, success=True)
    large = WorkerResult(item_id="m001", raw_output="r",
                         parsed={"concepts": [{"title": "X" * 10_000}]},
                         success=True)
    # 201 workers → 2 chunks.  Put the large worker in chunk 1 (it sorts
    # to item_id "m001" → chunk starting at m000).
    workers = [small, large] + _many_ok_workers(199, prefix="m")
    # Re-sort by item_id since the chunked path sorts before splitting.
    # m000, m001, m000..m198 — duplicate m000 is fine for this test.

    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'
    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 10)):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # The chunk containing the 10K-char worker produces a much larger
    # prompt than the meta call (which only has 2 small partial syntheses).
    # prompt_chars must reflect the largest single prompt.
    assert prompt_chars >= 10_000, (
        f"prompt_chars must be the MAX single prompt size; got {prompt_chars} "
        f"which is smaller than the large worker's content (10K chars)"
    )
