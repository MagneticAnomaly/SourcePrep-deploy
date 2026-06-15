"""Phase 136 Part 09 — diagnostic surface for synthesis failures.

The 2026-05-17 incident showed `concepts_synthesis_failed` firing with
~1795 fallback concepts / ~1334 questions on a 798-worker rebuild,
recurring on 5/18 and 5/28 with the same fingerprint.  The README's
revised diagnosis says wall-time is NOT the failure mode: synthesis is
returning empty or unparseable output on the consolidation prompt,
and the operator has no visibility into the raw response.

Step 1 of the recovery plan: capture the raw LLM synthesis response
on every parse path and surface it through ``SwarmResult`` so the
concept_seeder fallback can include it in the telemetry payload.  This
test pins the contract.

No behavior change other than the new diagnostic field surface.
"""
from __future__ import annotations

import json
from dataclasses import is_dataclass
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

from prep.core.swarm_orchestrator import (
    SwarmOrchestrator,
    SwarmResult,
    WorkerResult,
)


# ── SwarmResult contract ───────────────────────────────────────────


def test_swarm_result_has_raw_synthesis_text_field_default_none():
    """SwarmResult must expose ``raw_synthesis_text`` with default
    ``None`` so existing callers that ignore it stay green."""
    r = SwarmResult()
    assert hasattr(r, "raw_synthesis_text"), (
        "SwarmResult must carry the raw synthesis LLM response so "
        "concept_seeder can include head/tail in the diagnostic payload"
    )
    assert r.raw_synthesis_text is None


def test_swarm_result_has_synthesis_prompt_chars_field_default_zero():
    """``synthesis_prompt_chars`` defaults to 0 so callers that never
    ran synthesis report zero, not a misleading None."""
    r = SwarmResult()
    assert hasattr(r, "synthesis_prompt_chars"), (
        "SwarmResult must carry the synthesis prompt size so the "
        "consolidation-prompt-too-large hypothesis can be tested in "
        "production telemetry"
    )
    assert r.synthesis_prompt_chars == 0


def test_swarm_result_is_still_a_dataclass():
    """Defensive: the new fields must not break the dataclass shape."""
    assert is_dataclass(SwarmResult)


# ── _synthesize return contract ────────────────────────────────────


def _make_orch() -> SwarmOrchestrator:
    """Construct a SwarmOrchestrator suitable for unit-testing
    _synthesize.  We bypass __init__ because LLM clients aren't needed
    for the paths under test — _llm_call_with_timeout is monkey-patched.
    """
    orch = SwarmOrchestrator.__new__(SwarmOrchestrator)
    orch.synthesis_timeout_s = 60.0
    orch.coordinator_llm = None
    orch.worker_llm = None
    orch.project_id = None
    return orch


def _ok_worker(item_id: str = "m1") -> WorkerResult:
    """Worker result with parsed JSON — enough to feed _synthesize."""
    return WorkerResult(
        item_id=item_id,
        raw_output="ignored",
        parsed={"concepts": [{"title": "t"}], "questions": []},
        success=True,
    )


def test_synthesize_returns_raw_text_on_success():
    """Successful parse path returns (parsed_dict, tokens, raw_text, prompt_chars, meta_failed).

    raw_text must equal the LLM response so callers can checkpoint it
    even on success — useful for later quality auditing.
    """
    orch = _make_orch()
    workers = [_ok_worker("m1")]
    fake_text = '{"concepts": [{"title": "Synthesized"}], "questions": []}'

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(fake_text, 100)):
        out = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert len(out) == 5, (
        f"_synthesize must return (parsed, tokens, raw_text, prompt_chars, "
        f"meta_failed); got tuple of length {len(out)}"
    )
    parsed, tokens, raw_text, prompt_chars, meta_failed = out
    assert parsed == {"concepts": [{"title": "Synthesized"}], "questions": []}
    assert tokens == 100
    assert raw_text == fake_text, "raw_text must echo the LLM response on success"
    assert prompt_chars > 0, "prompt_chars must record the prompt size sent"
    assert meta_failed is False, (
        "_synthesize_single never has a meta phase — meta_failed must be False"
    )


def test_synthesize_returns_raw_text_on_parse_failure():
    """When the parser rejects the LLM response, the raw text must
    still come back so we can log first/last 500 chars.  This is the
    actual diagnostic surface Part 09 needs.
    """
    orch = _make_orch()
    workers = [_ok_worker("m1")]
    unparseable = "I'm a reasoning model still thinking... <think>foo</think>"

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(unparseable, 50)):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert parsed is None, "unparseable response must return parsed=None"
    assert raw_text == unparseable, (
        "raw_text must survive parse failure — that's the entire point of "
        "the diagnostic surface"
    )
    assert prompt_chars > 0
    assert meta_failed is False, (
        "_synthesize_single never has a meta phase — meta_failed must be False"
    )


def test_synthesize_returns_none_text_on_llm_timeout():
    """When the LLM call returns (None, 0) (timeout/error), raw_text
    must be None — there's nothing to log — and prompt_chars must
    still reflect the prompt that was sent."""
    orch = _make_orch()
    workers = [_ok_worker("m1")]

    with patch.object(SwarmOrchestrator, "_llm_call_with_timeout",
                       return_value=(None, 0)):
        parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
            workers,
            synthesis_prompt="prefix {worker_outputs} suffix",
            event_log=None,
        )

    assert parsed is None
    assert raw_text is None, "LLM timeout has no text to surface"
    assert prompt_chars > 0, (
        "prompt_chars must record the prompt that WAS sent even when "
        "the response timed out — the consolidation-prompt-too-large "
        "hypothesis is what we're trying to test"
    )
    assert meta_failed is False, (
        "_synthesize_single never has a meta phase — meta_failed must be False"
    )


def test_synthesize_returns_zero_prompt_chars_when_no_workers():
    """No successful workers → no LLM call made → prompt_chars = 0."""
    orch = _make_orch()
    failed = WorkerResult(
        item_id="x", raw_output="", parsed=None, success=False,
    )

    parsed, tokens, raw_text, prompt_chars, meta_failed = orch._synthesize(
        [failed],
        synthesis_prompt="prefix {worker_outputs} suffix",
        event_log=None,
    )

    assert parsed is None
    assert raw_text is None
    assert prompt_chars == 0
    assert tokens == 0
    assert meta_failed is False, (
        "_synthesize_single never has a meta phase — meta_failed must be False"
    )


# ── concept_seeder diagnostic-fields helper ────────────────────────


from prep.core.concept_seeder import _synthesis_diagnostic_fields


def _result(
    *,
    raw_text: Optional[str] = None,
    prompt_chars: int = 0,
    synthesis: Optional[Dict[str, Any]] = None,
    workers: Optional[List[WorkerResult]] = None,
) -> SwarmResult:
    """Build a SwarmResult shaped for the helper under test."""
    return SwarmResult(
        worker_results=workers or [],
        synthesis=synthesis,
        raw_synthesis_text=raw_text,
        synthesis_prompt_chars=prompt_chars,
    )


def test_diagnostic_failure_mode_no_workers_when_synthesis_skipped():
    """When no successful workers had parseable output, ``_synthesize``
    returns prompt_chars=0 (it never ran).  failure_mode = 'no_workers'.
    """
    r = _result(raw_text=None, prompt_chars=0, synthesis=None,
                workers=[WorkerResult(item_id="x", raw_output="", success=False)])

    out = _synthesis_diagnostic_fields(r)

    assert out["failure_mode"] == "no_workers"
    assert out["raw_synthesis_chars"] == 0
    assert out["raw_synthesis_head"] == ""
    assert out["raw_synthesis_tail"] == ""
    assert out["synthesis_prompt_chars"] == 0


def test_diagnostic_failure_mode_no_text_on_llm_timeout():
    """LLM call dispatched but timed out → raw_text=None and
    prompt_chars>0.  failure_mode = 'no_text'.
    """
    r = _result(raw_text=None, prompt_chars=8192, synthesis=None)

    out = _synthesis_diagnostic_fields(r)

    assert out["failure_mode"] == "no_text"
    assert out["raw_synthesis_chars"] == 0
    assert out["synthesis_prompt_chars"] == 8192


def test_diagnostic_failure_mode_parse_failed_on_unparseable_response():
    """LLM returned text but parser rejected it → raw_text non-None,
    synthesis=None.  failure_mode = 'parse_failed'.  This is the
    typical unclosed-think-tag / pure-prose failure shape.
    """
    unparseable = "<think>Let me reason about this... " + "x" * 200
    r = _result(raw_text=unparseable, prompt_chars=5000, synthesis=None)

    out = _synthesis_diagnostic_fields(r)

    assert out["failure_mode"] == "parse_failed"
    assert out["raw_synthesis_chars"] == len(unparseable)
    assert out["raw_synthesis_head"] == unparseable[:500]
    # Text is shorter than HEAD threshold → tail should stay empty
    # (no point duplicating).
    assert out["raw_synthesis_tail"] == ""


def test_diagnostic_failure_mode_parsed_but_empty_when_concepts_list_empty():
    """JSON parsed cleanly but concepts list was empty/missing — the
    most common 2026-05-17/18/28 telemetry fingerprint.
    failure_mode = 'parsed_but_empty'.
    """
    raw = '{"concepts": [], "questions": [{"question": "why?"}]}'
    parsed = {"concepts": [], "questions": [{"question": "why?"}]}
    r = _result(raw_text=raw, prompt_chars=2_000_000, synthesis=parsed)

    out = _synthesis_diagnostic_fields(r)

    assert out["failure_mode"] == "parsed_but_empty"
    assert out["synthesis_prompt_chars"] == 2_000_000


def test_diagnostic_head_and_tail_for_long_response():
    """When raw response is longer than head budget, both head and
    tail must be captured so operators see both ends of a truncated
    or repeating response.
    """
    body = "A" * 600 + "MIDDLE" + "B" * 600
    r = _result(raw_text=body, prompt_chars=1234, synthesis=None)

    out = _synthesis_diagnostic_fields(r)

    assert out["raw_synthesis_head"] == "A" * 500
    assert out["raw_synthesis_tail"] == "B" * 500
    assert out["raw_synthesis_chars"] == len(body)


def test_diagnostic_worker_outputs_chars_total_sums_parsed_workers():
    """worker_outputs_chars_total is the sum of len(json.dumps(parsed))
    over successful workers — gives operators a single number to
    diagnose 'consolidation prompt too large'.
    """
    workers = [
        WorkerResult(item_id="m1", raw_output="raw1",
                     parsed={"concepts": [{"title": "AAA" * 50}]}, success=True),
        WorkerResult(item_id="m2", raw_output="raw2",
                     parsed={"concepts": [{"title": "BBB" * 50}]}, success=True),
        WorkerResult(item_id="m3", raw_output="raw3", parsed=None, success=False),
    ]
    r = _result(raw_text="ok", prompt_chars=900, synthesis=None, workers=workers)

    out = _synthesis_diagnostic_fields(r)

    # Two successful workers — total must be the sum of their parsed sizes.
    expected = (
        len(json.dumps(workers[0].parsed, indent=2))
        + len(json.dumps(workers[1].parsed, indent=2))
    )
    assert out["worker_outputs_chars_total"] == expected


def test_diagnostic_fields_are_all_jsonable():
    """Telemetry serializes via record_event; every value must round-
    trip through json.dumps without raising.
    """
    r = _result(raw_text="text", prompt_chars=10,
                synthesis={"concepts": [], "questions": []})
    out = _synthesis_diagnostic_fields(r)
    # Must not raise.
    json.dumps(out)
