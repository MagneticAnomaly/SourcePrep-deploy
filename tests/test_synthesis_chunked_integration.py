"""Phase 136 Part 09 Step 2 Follow-up B — C1 integration test.

Drives ``seed_concepts_swarm`` end-to-end with a hand-crafted
``SwarmResult`` returned by a stubbed orchestrator, then asserts which
telemetry event (``concepts_synthesis_failed`` vs.
``concepts_chunked_meta_failed``) fires for each outcome shape.

This catches the C1 routing bug:  before the fix, when chunked meta
fails AND ``_dedup_chunk_union`` produces an empty-concepts dict (every
chunk emitted only ``questions`` — the Phase 123 worker fingerprint
when synthesis fails), the existing ``if synthesis_was_empty …``
branch fires the wrong event and overwrites chunk-survivor questions
with raw-worker fallback dedup.

Seam:  ``prep.core.swarm_orchestrator.SwarmOrchestrator`` is patched
with a stub whose ``execute()`` returns the parametrized
``SwarmResult``.  Persistence (``concept_store.save_many`` /
``save_question``) is also stubbed so the test isolates the routing
decision.  ``record_event`` is captured via ``monkeypatch`` at
``prep.services.pipeline_telemetry.record_event``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from prep.core.swarm_orchestrator import SwarmResult, WorkerResult


# ── Fixtures ──────────────────────────────────────────────────────


def _ok_worker(item_id: str, concept_title: str = "x") -> WorkerResult:
    """Successful worker with one parsed concept."""
    return WorkerResult(
        item_id=item_id,
        raw_output="ok",
        parsed={"concepts": [{"title": concept_title}], "questions": []},
        success=True,
    )


def _question_only_worker(item_id: str, q_text: str) -> WorkerResult:
    """Successful worker that emitted ONLY a clarifying question — the
    Phase 123 fingerprint when downstream synthesis fails.
    """
    return WorkerResult(
        item_id=item_id,
        raw_output="ok",
        parsed={
            "concepts": [],
            "questions": [{"question": q_text, "target_module": item_id}],
        },
        success=True,
    )


def _module(name: str, file_count: int = 5) -> dict:
    return {
        "module_id": name.lower(),
        "name": name,
        "file_count": file_count,
        "member_files": [f"src/{name}/f{i}.py" for i in range(file_count)],
        "summary": f"The {name} subsystem",
        "domain_tags": ["test"],
        "internal_dependencies": [],
        "external_dependencies": [],
    }


# ── Parametrized routing harness ──────────────────────────────────


def _build_result_for_case(case: str) -> SwarmResult:
    """Build the hand-crafted SwarmResult for each parametrize case.

    Cases mirror the docstring at the top of this file:
      (i)   single-call success
      (ii)  single-call parsed_but_empty
      (iii) chunked meta success
      (iv)  chunked meta failed with non-empty union
      (v)   chunked meta failed with empty-concepts union (the C1 bug)
    """
    workers = [_ok_worker(f"m{i}") for i in range(5)]

    if case == "single_call_success":
        return SwarmResult(
            worker_results=workers,
            synthesis={
                "concepts": [{"title": "GoodSynthesis"}],
                "questions": [],
            },
            raw_synthesis_text="ok",
            synthesis_prompt_chars=50_000,
            synthesis_chunk_count=1,
            synthesis_meta_failed=False,
        )

    if case == "single_call_parsed_but_empty":
        return SwarmResult(
            worker_results=workers,
            synthesis={"concepts": [], "questions": []},
            raw_synthesis_text="{}",
            synthesis_prompt_chars=50_000,
            synthesis_chunk_count=1,
            synthesis_meta_failed=False,
        )

    if case == "chunked_meta_success":
        return SwarmResult(
            worker_results=workers,
            synthesis={
                "concepts": [{"title": "MetaConsolidated"}],
                "questions": [],
            },
            raw_synthesis_text="ok",
            synthesis_prompt_chars=400_000,
            synthesis_chunk_count=4,
            synthesis_meta_failed=False,
        )

    if case == "chunked_meta_failed_non_empty_union":
        return SwarmResult(
            worker_results=workers,
            synthesis={
                "concepts": [
                    {"title": "C1"},
                    {"title": "C2"},
                ],
                "questions": [{"question": "Q1", "target_module": "m0"}],
            },
            raw_synthesis_text="unparseable-meta-failure",
            synthesis_prompt_chars=400_000,
            synthesis_chunk_count=4,
            synthesis_meta_failed=True,
        )

    if case == "chunked_meta_failed_empty_concepts_union":
        # The C1 bug case: every chunk emitted only questions (Phase 123
        # fingerprint), so _dedup_chunk_union returned empty concepts.
        # Workers themselves are also question-only so the raw-worker
        # fallback (if it incorrectly fires) is observably distinct
        # from the chunk-survivor union we want preserved.
        q_workers = [
            _question_only_worker("m0", "Worker question 1"),
            _question_only_worker("m1", "Worker question 2"),
        ]
        return SwarmResult(
            worker_results=q_workers,
            synthesis={
                "concepts": [],
                "questions": [
                    {"question": "Chunk-survivor question 1",
                     "target_module": "m0"},
                ],
            },
            raw_synthesis_text="unparseable-meta-failure",
            synthesis_prompt_chars=400_000,
            synthesis_chunk_count=4,
            synthesis_meta_failed=True,
        )

    raise AssertionError(f"unknown case: {case}")


@pytest.mark.parametrize(
    "case,expected_events,expected_failure_mode",
    [
        ("single_call_success", set(), None),
        ("single_call_parsed_but_empty",
         {"concepts_synthesis_failed"}, "parsed_but_empty"),
        ("chunked_meta_success", set(), None),
        ("chunked_meta_failed_non_empty_union",
         {"concepts_chunked_meta_failed"}, "chunked_meta_failed"),
        # ── C1 regression ──
        # Empty-concepts union + meta_failed must still route to
        # concepts_chunked_meta_failed (NOT concepts_synthesis_failed).
        ("chunked_meta_failed_empty_concepts_union",
         {"concepts_chunked_meta_failed"}, "chunked_meta_failed"),
    ],
)
def test_seed_concepts_swarm_routes_telemetry_by_outcome_shape(
    case, expected_events, expected_failure_mode, tmp_path, monkeypatch,
):
    """Assert that ``seed_concepts_swarm`` fires the correct telemetry
    event for each outcome shape.

    Case (v) is the C1 regression test:  empty-concepts union with
    ``meta_failed=True`` must fire ``concepts_chunked_meta_failed`` and
    NOT ``concepts_synthesis_failed`` (the raw-worker fallback path).
    Before the fix this case wrongly fires ``concepts_synthesis_failed``
    because ``synthesis_was_empty`` is True and the IF branch is
    checked before the ELIF.
    """
    from prep.core import concept_seeder as cs

    swarm_result = _build_result_for_case(case)

    # ── Capture telemetry ──
    captured: list[dict[str, Any]] = []

    def _capture(idx_dir, event, payload=None, **kwargs):
        captured.append({
            "event": event,
            "payload": payload or {},
            "kwargs": kwargs,
        })

    import prep.services.pipeline_telemetry as telemetry_mod
    monkeypatch.setattr(telemetry_mod, "record_event", _capture)

    # ── Stub orchestrator ──
    class _StubOrchestrator:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def execute(self, **kwargs):
            return swarm_result

    # ── Stub LLM ──
    llm = MagicMock()
    llm.provider = "ollama"
    llm.model = "gpt-oss:120b-cloud"

    # ── Stub modules + project ──
    modules = [_module(f"m{i}", 5) for i in range(5)]
    project = MagicMock()
    project.id = "proj-test"
    project.name = "TestProj"
    project.path = str(tmp_path)

    # ── Stub concept_store so persistence does not fail the test ──
    fake_store = MagicMock()
    fake_store.save_many.return_value = (0, 0)
    fake_store.save_question.return_value = None

    with patch(
        "prep.core.swarm_orchestrator.SwarmOrchestrator", _StubOrchestrator,
    ), patch.object(
        cs, "_load_modules_for_swarm", return_value=modules,
    ), patch(
        "prep.core.llm_client._is_cloud_endpoint", return_value=True,
    ), patch.object(
        cs, "_get_seeder_llm", return_value=llm,
    ), patch(
        "prep.services.pipeline.scheduler.pipeline_scheduler.full_budget_for_swarm",
        return_value=10,
    ), patch(
        "prep.services.pipeline.scheduler.is_swarm_active_for_stage",
        return_value=True,
    ), patch(
        "prep.services.pipeline.workers.WorkerFactory._get_coordinator_llm_client",
        return_value=MagicMock(),
    ), patch(
        "prep.services.project_helpers.require_project", return_value=project,
    ), patch(
        "prep.core.project_registry.project_index_dir", return_value=tmp_path,
    ), patch(
        "prep.services.concept_store.concept_store", fake_store,
    ):
        result = cs.seed_concepts_swarm("proj-test")

    # ── Assertion 1:  exactly the expected event(s) fired ──
    routing_events = {
        c["event"] for c in captured
        if c["event"] in {
            "concepts_synthesis_failed",
            "concepts_chunked_meta_failed",
        }
    }
    assert routing_events == expected_events, (
        f"[{case}] expected {expected_events}, got {routing_events}. "
        f"All captured events: {[c['event'] for c in captured]}"
    )

    # ── Assertion 2:  failure_mode in payload matches ──
    if expected_failure_mode is not None:
        # Find the routing event payload.
        routing = [
            c for c in captured
            if c["event"] in expected_events
        ]
        assert len(routing) == 1, (
            f"[{case}] expected exactly one routing event, got {len(routing)}"
        )
        payload = routing[0]["payload"]
        assert payload.get("failure_mode") == expected_failure_mode, (
            f"[{case}] expected failure_mode={expected_failure_mode!r}, "
            f"got payload={payload!r}"
        )

    # ── Assertion 3 (C1 regression):  concepts_synthesis_failed must
    #     NOT fire on the empty-concepts-union meta-failed case. ──
    if case == "chunked_meta_failed_empty_concepts_union":
        names = [c["event"] for c in captured]
        assert "concepts_synthesis_failed" not in names, (
            "C1 regression: empty-concepts union with synthesis_meta_failed=True "
            "must route to concepts_chunked_meta_failed, NOT the raw-worker "
            "fallback path. Captured events: " + repr(names)
        )

    # Sanity: result dict is well-formed (status or summary present)
    assert isinstance(result, dict)
