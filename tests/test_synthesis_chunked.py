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
    # Phase 136 Part 09 Step 2 follow-up: kill switch defaults to off
    # so the bypass-__init__ tests exercise the chunked path as before.
    orch.synthesis_chunk_disable = False
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


# ── Per-chunk + meta failure handling ──────────────────────────────


def test_chunked_some_chunks_fail_meta_gets_survivors():
    """2 of 4 chunks parse-fail.  Meta is called with the 2 survivors;
    result.synthesis is the meta dict; meta_failed is False.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(798)  # 4 chunks

    # 4 chunk calls return alternating success/failure; 5th call (meta)
    # returns success.  Failure shape = unparseable text.
    chunk_returns = iter([
        ('{"concepts": [{"title": "C1"}], "questions": []}', 50),   # chunk 1 OK
        ("not-json-reasoning-blob",                          30),    # chunk 2 fail
        ('{"concepts": [{"title": "C3"}], "questions": []}', 50),   # chunk 3 OK
        ("more-reasoning-blob",                              30),    # chunk 4 fail
        ('{"concepts": [{"title": "MetaConsolidated"}], "questions": []}', 100),  # meta
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call) as mock_llm:
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert mock_llm.call_count == 5, (
        f"Even with 2 chunks failing, meta call still fires; "
        f"expected 5 LLM calls, got {mock_llm.call_count}"
    )

    # Meta input prompt should contain C1 and C3 (survivors) but NOT
    # any of the failure blobs.
    meta_call_prompt = mock_llm.call_args_list[-1].kwargs.get("prompt", "")
    assert "C1" in meta_call_prompt, "Meta must receive surviving chunk 1's parsed JSON"
    assert "C3" in meta_call_prompt, "Meta must receive surviving chunk 3's parsed JSON"

    # Meta succeeded → use its output, meta_failed False.
    assert parsed == {"concepts": [{"title": "MetaConsolidated"}], "questions": []}
    assert meta_failed is False


def test_chunked_all_chunks_fail_returns_none():
    """All 4 chunks fail to parse; meta is NOT called; result is
    (None, sum_tokens, None, max_prompt_chars, False).
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(798)  # 4 chunks

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=("garbage non-json", 25)) as mock_llm:
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # Only the 4 per-chunk calls — meta is skipped.
    assert mock_llm.call_count == 4, (
        f"All-chunks-fail must skip meta; expected 4 LLM calls, got "
        f"{mock_llm.call_count}"
    )
    assert parsed is None
    assert raw_text is None, (
        "Per-chunk raw text is NOT bubbled to SwarmResult on the "
        "chunked_all_failed path; operators consult the swarm event log "
        "for per-chunk evidence"
    )
    assert tokens == 4 * 25, "Tokens summed across all 4 chunk calls"
    assert meta_failed is False, (
        "All chunks failed → meta never ran → meta_failed remains False"
    )


def test_chunked_meta_fails_returns_deduped_union():
    """Chunks succeed; meta fails; result.synthesis is the deduped
    union of chunk parsed results; meta_failed is True.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(400)  # 2 chunks

    # Chunk 1 and chunk 2 each return concepts with overlapping titles.
    chunk_returns = iter([
        ('{"concepts": [{"title": "Shared"}, {"title": "OnlyInChunk1"}], "questions": []}', 50),
        ('{"concepts": [{"title": "Shared"}, {"title": "OnlyInChunk2"}], "questions": []}', 50),
        ("unparseable-meta-failure", 75),
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert meta_failed is True, (
        "Meta failure after chunk successes must set meta_failed=True"
    )
    assert parsed is not None and "concepts" in parsed
    titles = {c["title"] for c in parsed["concepts"]}
    assert titles == {"Shared", "OnlyInChunk1", "OnlyInChunk2"}, (
        f"Union must dedupe 'Shared' but keep 'OnlyInChunk1' and "
        f"'OnlyInChunk2'; got {titles}"
    )
    # raw_synthesis_text carries the meta response text — operators see
    # what the failed meta call actually produced.
    assert raw_text == "unparseable-meta-failure"


def test_chunked_meta_fail_union_skips_entries_with_empty_titles():
    """The manual dedup mirrors concept_seeder.py:889-909 defensiveness:
    entries with empty/missing titles are skipped; questions with empty
    text are skipped.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(400)  # 2 chunks

    chunk_returns = iter([
        (json.dumps({
            "concepts": [
                {"title": "Real"},
                {"title": ""},  # empty title — must be dropped
                {"title": "  "},  # whitespace only — must be dropped
                {"description": "missing title field"},  # missing — must be dropped
            ],
            "questions": [
                {"question": "Real q", "target_module": "m"},
                {"question": "", "target_module": "m"},  # empty — dropped
                {"target_module": "m"},  # missing question — dropped
            ],
        }), 50),
        (json.dumps({"concepts": [{"title": "Another"}], "questions": []}), 50),
        ("unparseable-meta", 75),
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert meta_failed is True
    titles = {c["title"] for c in parsed["concepts"]}
    assert titles == {"Real", "Another"}, (
        f"Empty/missing-title entries must be skipped; got {titles}"
    )
    q_texts = {q["question"] for q in parsed["questions"]}
    assert q_texts == {"Real q"}, (
        f"Empty/missing-question entries must be skipped; got {q_texts}"
    )


# ── Soft-hold (HoldPausedError) propagation ────────────────────────


def test_chunked_pause_between_chunks_propagates_hold_paused():
    """Mock _hold_paused to return True after chunk 1 completes; the
    chunked path must raise HoldPausedError; chunks 2-4 and meta must
    NOT dispatch.
    """
    from prep.services.pipeline.holds import HoldPausedError

    orch = _make_orch(chunk_max=200)
    orch.project_id = "proj-test"
    workers = _many_ok_workers(798)  # 4 chunks

    # Each chunk call returns valid JSON; meta would too if reached.
    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    # _hold_paused is only polled at the between-chunks check (line 909
    # of swarm_orchestrator.py) — _synthesize_single itself does NOT
    # poll.  So the first poll IS the post-chunk-1 check; return True
    # there to fire the pause before chunk 2 dispatches.
    def _fake_hold():
        return True

    # _raise_hold_paused must raise — patch with the real-ish behavior.
    def _fake_raise():
        raise HoldPausedError(
            project_id="proj-test", endpoint_id="cloud:test",
        )

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 50)) as mock_llm:
        with patch.object(SwarmOrchestrator, "_hold_paused",
                           side_effect=_fake_hold):
            with patch.object(SwarmOrchestrator, "_raise_hold_paused",
                               side_effect=_fake_raise):
                with pytest.raises(HoldPausedError):
                    orch._synthesize(
                        workers,
                        synthesis_prompt="prefix {worker_outputs} suffix",
                        event_log=None,
                    )

    # Only chunk 1 dispatched before the pause was raised.
    assert mock_llm.call_count == 1, (
        f"Pause between chunks must stop dispatch; expected 1 LLM call, "
        f"got {mock_llm.call_count}"
    )


def test_chunked_pause_before_meta_propagates_hold_paused():
    """All chunks succeed; _hold_paused returns True at the pre-meta
    check; HoldPausedError raises; meta does NOT dispatch.
    """
    from prep.services.pipeline.holds import HoldPausedError

    orch = _make_orch(chunk_max=200)
    orch.project_id = "proj-test"
    workers = _many_ok_workers(400)  # 2 chunks

    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    # _hold_paused: False after chunk 1 (between-chunks check), True
    # before meta dispatch.
    hold_returns = iter([False, True])
    def _fake_hold():
        return next(hold_returns)

    def _fake_raise():
        raise HoldPausedError(
            project_id="proj-test", endpoint_id="cloud:test",
        )

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 50)) as mock_llm:
        with patch.object(SwarmOrchestrator, "_hold_paused",
                           side_effect=_fake_hold):
            with patch.object(SwarmOrchestrator, "_raise_hold_paused",
                               side_effect=_fake_raise):
                with pytest.raises(HoldPausedError):
                    orch._synthesize(
                        workers,
                        synthesis_prompt="prefix {worker_outputs} suffix",
                        event_log=None,
                    )

    # Both chunks dispatched; meta did NOT.
    assert mock_llm.call_count == 2, (
        f"Both chunks must dispatch before the pre-meta hold check "
        f"fires; meta must NOT dispatch; expected 2 LLM calls, got "
        f"{mock_llm.call_count}"
    )


# ── Reproducibility ────────────────────────────────────────────────


def test_chunk_results_deterministic_by_item_id():
    """Workers passed in shuffled order produce the same chunk
    boundaries as sorted-by-item_id workers.  Critical for production
    debugging — a chunk's contents must be reproducible from the input
    list.
    """
    import random

    orch = _make_orch(chunk_max=100)
    sorted_workers = _many_ok_workers(250)  # 3 chunks of 100, 100, 50
    shuffled = sorted_workers.copy()
    random.Random(42).shuffle(shuffled)

    fake_text = '{"concepts": [{"title": "OK"}], "questions": []}'

    sorted_prompts = []
    shuffled_prompts = []

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 10)) as mock_llm:
        orch._synthesize(
            sorted_workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )
        # First 3 calls = per-chunk; 4th = meta.
        for call in mock_llm.call_args_list[:3]:
            sorted_prompts.append(call.kwargs.get("prompt", ""))

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 10)) as mock_llm:
        orch._synthesize(
            shuffled,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )
        for call in mock_llm.call_args_list[:3]:
            shuffled_prompts.append(call.kwargs.get("prompt", ""))

    assert sorted_prompts == shuffled_prompts, (
        "Chunk boundaries (and therefore per-chunk prompts) must be "
        "identical regardless of input worker order — _synthesize_chunked "
        "sorts by item_id before slicing"
    )


# ── Diagnostic classifier — chunked failure modes ──────────────────


from prep.core.concept_seeder import _synthesis_diagnostic_fields


def test_diagnostic_failure_mode_chunked_all_failed():
    """SwarmResult with synthesis_chunk_count > 1, synthesis=None,
    raw_text=None, prompt_chars>0 → failure_mode = chunked_all_failed.
    """
    r = SwarmResult(
        worker_results=[
            WorkerResult(item_id=f"m{i}", raw_output="", parsed=None,
                          success=False)
            for i in range(5)
        ],
        synthesis=None,
        raw_synthesis_text=None,
        synthesis_prompt_chars=500_000,  # non-zero — chunks were dispatched
        synthesis_chunk_count=4,
        synthesis_meta_failed=False,
    )

    out = _synthesis_diagnostic_fields(r)

    assert out["failure_mode"] == "chunked_all_failed"
    assert out["raw_synthesis_chars"] == 0


def test_diagnostic_failure_mode_chunked_meta_failed():
    """SwarmResult with synthesis_chunk_count > 1, synthesis (non-empty
    union), synthesis_meta_failed=True → failure_mode = chunked_meta_failed.
    """
    survivors_union = {
        "concepts": [{"title": "C1"}, {"title": "C2"}],
        "questions": [],
    }
    r = SwarmResult(
        worker_results=[
            WorkerResult(item_id=f"m{i}", raw_output="r",
                          parsed={"concepts": [{"title": "x"}]},
                          success=True)
            for i in range(5)
        ],
        synthesis=survivors_union,
        raw_synthesis_text="meta call failed with this response text",
        synthesis_prompt_chars=400_000,
        synthesis_chunk_count=4,
        synthesis_meta_failed=True,
    )

    out = _synthesis_diagnostic_fields(r)

    assert out["failure_mode"] == "chunked_meta_failed"


# ── concepts_chunked_meta_failed event emission ────────────────────


def test_chunked_meta_failed_event_fires_alongside_no_concepts_synthesis_failed(
    monkeypatch,
):
    """When SwarmResult has synthesis_meta_failed=True AND non-empty
    synthesis.concepts, concept_seeder must emit
    concepts_chunked_meta_failed event AND NOT emit
    concepts_synthesis_failed.

    We exercise the emission helper directly by simulating the gating
    logic concept_seeder uses: if meta_failed → fire the new event;
    if final_concepts empty → fire the existing event.  This is a
    contract test for the new emission site behavior.
    """
    # Test fixture: build the result + call the helper that emits.
    # Since seed_concepts_swarm is a 700-LoC function with heavy fixtures,
    # we factor out the emission helper as `_emit_chunked_meta_failed_event`
    # and test it directly (implementation step adds the helper).
    from prep.core.concept_seeder import _emit_chunked_meta_failed_event

    survivors_union = {
        "concepts": [{"title": "C1"}, {"title": "C2"}],
        "questions": [{"question": "Q1"}],
    }
    r = SwarmResult(
        worker_results=[
            WorkerResult(item_id=f"m{i}", raw_output="r",
                          parsed={"concepts": [{"title": "x"}]},
                          success=True)
            for i in range(5)
        ],
        synthesis=survivors_union,
        raw_synthesis_text="meta call failed",
        synthesis_prompt_chars=400_000,
        synthesis_chunk_count=4,
        synthesis_meta_failed=True,
    )

    captured: List[Dict[str, Any]] = []

    def _capture(index_dir, event_name, payload, **kwargs):
        captured.append({
            "event_name": event_name,
            "payload": payload,
            "kwargs": kwargs,
        })

    # Patch record_event at its import site within concept_seeder.
    import prep.services.pipeline_telemetry as telemetry_mod
    monkeypatch.setattr(telemetry_mod, "record_event", _capture)

    _emit_chunked_meta_failed_event(
        result=r,
        index_dir="/tmp/fake-index",
        project_id="proj-test",
        final_concepts=survivors_union["concepts"],
        final_questions=survivors_union["questions"],
    )

    assert len(captured) == 1
    assert captured[0]["event_name"] == "concepts_chunked_meta_failed"
    payload = captured[0]["payload"]
    # New event carries the diagnostic-fields surface PLUS the success
    # counters (concepts_returned + questions_returned).
    assert payload["failure_mode"] == "chunked_meta_failed"
    assert payload["concepts_returned"] == 2
    assert payload["questions_returned"] == 1
    assert payload["worker_count"] == 5
    assert payload["raw_synthesis_chars"] == len("meta call failed")


# ── 1-survivor short-circuit (Phase 136 Part 09 Step 2 follow-up) ────


def test_chunked_with_1_survivor_skips_meta_dispatch():
    """When only 1 chunk survives parsing, the meta-synthesis call must
    NOT be dispatched.  A degenerate meta call over a single chunk-parsed
    dict has no cross-chunk benefit, costs wall-time, and risks silent
    data loss if the LLM returns schema-valid-but-empty JSON.

    Two chunks: chunk 1 fails to parse, chunk 2 succeeds.  Total LLM
    dispatches must be exactly 2 (one per chunk) — NOT 3 (chunk1 fail +
    chunk2 ok + meta).
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(400)  # 2 chunks

    chunk_returns = iter([
        ("not-json-reasoning-blob", 30),  # chunk 1 fails to parse
        ('{"concepts": [{"title": "OnlyOne"}], "questions": []}', 50),  # chunk 2 ok
        # A third return would be consumed iff meta dispatched — but it
        # must NOT.  Leaving the iterator with no further values means
        # any meta dispatch would raise StopIteration, which the test
        # catches via the call-count assertion below.
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call) as mock_llm:
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    # Exactly 2 LLM calls (one per chunk) — meta is short-circuited.
    assert mock_llm.call_count == 2, (
        f"1-survivor short-circuit must skip meta dispatch; "
        f"expected 2 LLM calls (per-chunk only), got {mock_llm.call_count}"
    )


def test_chunked_with_1_survivor_preserves_survivor_data():
    """The lone survivor's concepts must flow through (via dedup union
    passthrough) — NOT be replaced by an empty meta-synthesis result.
    Silent data loss prevention.
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(400)  # 2 chunks

    chunk_returns = iter([
        ("garbage", 30),  # chunk 1 fail
        (json.dumps({
            "concepts": [{"title": "OnlyOne"}],
            "questions": [{"question": "Q1", "target_module": "m"}],
        }), 50),  # chunk 2 ok — the lone survivor
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert parsed is not None, (
        "1-survivor path must return the survivor's data, NOT None"
    )
    titles = {c["title"] for c in parsed.get("concepts", [])}
    assert titles == {"OnlyOne"}, (
        f"Survivor's concept must be preserved verbatim; got {titles}"
    )
    q_texts = {q["question"] for q in parsed.get("questions", [])}
    assert q_texts == {"Q1"}, (
        f"Survivor's question must be preserved verbatim; got {q_texts}"
    )


def test_chunked_with_1_survivor_sets_meta_failed_true():
    """The short-circuit must set meta_failed=True so the caller emits
    concepts_chunked_meta_failed — operators see the partial-recovery
    signal exactly as if meta had failed (which is morally equivalent:
    meta did not run and did not consolidate cross-chunk).
    """
    orch = _make_orch(chunk_max=200)
    workers = _many_ok_workers(400)  # 2 chunks

    chunk_returns = iter([
        ("garbage", 30),  # chunk 1 fail
        ('{"concepts": [{"title": "OnlyOne"}], "questions": []}', 50),  # chunk 2 ok
    ])
    def _fake_call(**kwargs):
        return next(chunk_returns)

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       side_effect=_fake_call):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert meta_failed is True, (
        "1-survivor short-circuit must set meta_failed=True so the "
        "telemetry event fires; got meta_failed=False"
    )


# ── PREP_SYNTHESIS_CHUNK_DISABLE kill-switch ───────────────────────


def test_chunk_disable_env_forces_single_call(monkeypatch):
    """When PREP_SYNTHESIS_CHUNK_DISABLE=1, _synthesize takes the
    single-call path even with worker count above chunk_max_workers.

    Operator rollback path: with the kill switch on, large workloads
    (798/805/741 workers in production) hit the documented merge gate
    (single-call concepts_synthesis_failed with parsed_but_empty)
    instead of falling through to chunked recovery.
    """
    monkeypatch.setenv("PREP_SYNTHESIS_CHUNK_DISABLE", "1")

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
    # Use a small chunk_max so we don't have to fabricate 200+ workers
    # — the dispatcher reads chunk_max_workers and chunk_disable
    # independently.
    orch.synthesis_chunk_max_workers = 10
    workers = _many_ok_workers(50)  # 50 > 10 → would chunk if not disabled
    fake_text = '{"concepts": [{"title": "Single"}], "questions": []}'

    with patch.object(
        SwarmOrchestrator, "_synthesize_single",
        return_value=({"concepts": [{"title": "Single"}], "questions": []},
                      100, fake_text, 500, False),
    ) as mock_single, patch.object(
        SwarmOrchestrator, "_synthesize_chunked",
    ) as mock_chunked:
        out = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert mock_single.call_count == 1, (
        f"Kill switch on → _synthesize_single must be called exactly once; "
        f"got {mock_single.call_count}"
    )
    assert mock_chunked.call_count == 0, (
        f"Kill switch on → _synthesize_chunked must NOT be called; "
        f"got {mock_chunked.call_count}"
    )
    parsed, _, _, _, meta_failed = out
    assert parsed == {"concepts": [{"title": "Single"}], "questions": []}
    assert meta_failed is False


def test_chunk_disable_unset_uses_chunking(monkeypatch):
    """When PREP_SYNTHESIS_CHUNK_DISABLE unset (default), worker count
    above chunk_max_workers takes the chunked path — confirming the
    kill switch is genuinely opt-in.
    """
    monkeypatch.delenv("PREP_SYNTHESIS_CHUNK_DISABLE", raising=False)

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
    orch.synthesis_chunk_max_workers = 10
    workers = _many_ok_workers(50)  # 50 > 10 → chunked

    with patch.object(
        SwarmOrchestrator, "_synthesize_chunked",
        return_value=({"concepts": [{"title": "Meta"}], "questions": []},
                      200, "meta-raw", 800, False),
    ) as mock_chunked, patch.object(
        SwarmOrchestrator, "_synthesize_single",
        return_value=({"concepts": [{"title": "Single"}], "questions": []},
                      50, "single-raw", 100, False),
    ) as mock_single:
        orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert mock_chunked.call_count == 1, (
        f"Default (kill switch unset) + 50 workers > chunk_max=10 → "
        f"_synthesize_chunked must be called; got {mock_chunked.call_count}"
    )
    # _synthesize_single may also be patched but our dispatcher does not
    # call it directly at the top level when the chunked path is taken
    # (the chunked path calls _synthesize_single internally, but we've
    # patched the chunked path to short-circuit, so single must not be
    # invoked from the dispatcher).
    assert mock_single.call_count == 0, (
        f"Dispatcher routed to chunked path; _synthesize_single must not "
        f"be called directly; got {mock_single.call_count}"
    )
