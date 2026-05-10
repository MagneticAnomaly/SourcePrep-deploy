"""Phase 125c T3b — tests for the Validate swarm runner.

LLM is mocked. Validates that:
- Each candidate gets its own LLM call
- related_rationale / related_docs / related_audit are filtered to
  anchors-overlapping rows only
- Verdicts are reconciled with Generate's tier
- save_many is called with the reconciled status
- Parse failures default to archive (conservative)
- A single worker's exception doesn't sink the swarm
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.core.concept_synthesizer import Grounding, SynthesizedConcept
from prep.core.concept_validate_swarm import (
    ValidateSwarmReport,
    validate_concepts_swarm,
)
from prep.core.docs_grounding import DiscoveredDoc, DocsGrounding


# ── Fixtures ────────────────────────────────────────────────────────


def _candidate(title: str, tier: str, anchors: tuple[str, ...]) -> SynthesizedConcept:
    return SynthesizedConcept(
        title=title, content=f"{title} content",
        category="constraint", tier=tier,
        tier_pairwise="closer_to_lower", anchors=anchors,
    )


def _grounding() -> Grounding:
    """Grounding with rationale anchored to specific files for overlap tests."""
    return Grounding(
        project_name="test",
        rationale_clusters=[
            {"title": "auth flow", "category": "security",
             "anchors": ["src/auth.py"], "content": "JWT validates..."},
            {"title": "ui theme", "category": "brand",
             "anchors": ["packages/ui/theme.ts"], "content": "css..."},
        ],
        audit_findings=[
            {"title": "auth audit", "severity": "warning",
             "file_paths": ["src/auth.py"]},
            {"title": "unrelated", "severity": "info",
             "file_paths": ["src/other.py"]},
        ],
    )


def _docs() -> DocsGrounding:
    return DocsGrounding(
        version=1, generated_at=0,
        docs=[
            DiscoveredDoc(
                path="src/auth.py", score=0.9, signals=("convention_match",),
                in_link_count=10, size_bytes=500,
                excerpt="auth excerpt", headings=("Auth",),
            ),
            DiscoveredDoc(
                path="docs/unrelated.md", score=0.5, signals=(),
                in_link_count=0, size_bytes=100,
                excerpt="other", headings=(),
            ),
        ],
    )


def _verdict_json(verdict: str, **fields) -> str:
    return json.dumps({
        "counter_evidence": fields.get("counter_evidence", "ce"),
        "falsification": fields.get("falsification", "fa"),
        "rationale": fields.get("rationale", "r"),
        "verdict": verdict,
    })


# ── Empty input ─────────────────────────────────────────────────────


def test_empty_candidates_returns_zero_report():
    llm = MagicMock()
    report = validate_concepts_swarm(
        "p1", candidates=[], llm=llm,
        grounding=_grounding(), docs=_docs(),
    )
    assert isinstance(report, ValidateSwarmReport)
    assert report.input_count == 0
    assert report.saved == 0
    llm.generate.assert_not_called()


# ── Per-candidate LLM call ──────────────────────────────────────────


def test_each_candidate_gets_one_llm_call(tmp_path):
    candidates = [
        _candidate("A", "T2", ("src/auth.py",)),
        _candidate("B", "T1", ("packages/ui/theme.ts",)),
    ]
    llm = MagicMock()
    llm.generate = MagicMock(return_value=(_verdict_json("T2"), 100))

    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (2, 0)
        report = validate_concepts_swarm(
            "p1", candidates=candidates, llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
        )
    assert llm.generate.call_count == 2
    assert report.input_count == 2


# ── Anchor-overlap filter ───────────────────────────────────────────


def test_related_rationale_filtered_by_anchor_overlap(tmp_path):
    """A candidate anchored to src/auth.py should have its prompt include
    'auth flow' rationale (anchored same) but NOT 'ui theme'."""
    cand = _candidate("Auth gate", "T2", ("src/auth.py",))
    captured_prompts: list[str] = []
    def _gen(prompt: str, system: str, **_):
        captured_prompts.append(prompt)
        return (_verdict_json("T2"), 100)
    llm = MagicMock()
    llm.generate = _gen

    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (1, 0)
        validate_concepts_swarm(
            "p1", candidates=[cand], llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
        )
    user_prompt = captured_prompts[0]
    assert "auth flow" in user_prompt           # anchors share src/auth.py
    assert "ui theme" not in user_prompt        # anchors don't overlap
    assert "auth audit" in user_prompt          # audit finding overlaps
    assert "unrelated" not in user_prompt       # finding doesn't overlap


def test_related_docs_filtered_to_anchor_paths(tmp_path):
    """Docs whose `path` is in candidate.anchors get included; others don't."""
    cand = _candidate("Auth gate", "T2", ("src/auth.py",))
    captured_prompts: list[str] = []
    def _gen(prompt: str, system: str, **_):
        captured_prompts.append(prompt)
        return (_verdict_json("T2"), 100)
    llm = MagicMock()
    llm.generate = _gen

    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (1, 0)
        validate_concepts_swarm(
            "p1", candidates=[cand], llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
        )
    user_prompt = captured_prompts[0]
    assert "src/auth.py" in user_prompt          # anchor doc present
    assert "auth excerpt" in user_prompt         # excerpt body included
    assert "docs/unrelated.md" not in user_prompt   # not an anchor


# ── Verdict reconciliation drives save_many status ──────────────────


def test_t3_verdict_with_t2_generate_lands_active(tmp_path):
    cand = _candidate("Auth gate", "T2", ("src/auth.py",))
    llm = MagicMock()
    llm.generate = MagicMock(return_value=(_verdict_json("T3"), 100))

    saved: list[dict] = []
    with patch("prep.services.concept_store.concept_store") as store:
        def _save(pid, dicts):
            saved.extend(dicts)
            return (len(dicts), 0)
        store.save_many.side_effect = _save
        report = validate_concepts_swarm(
            "p1", candidates=[cand], llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
        )
    assert report.activated == 1
    assert saved[0]["status"] == "active"
    assert saved[0]["confidence"] == pytest.approx(0.92)


def test_t1_verdict_lands_triage_pending(tmp_path):
    cand = _candidate("Auth gate", "T2", ("src/auth.py",))
    llm = MagicMock()
    llm.generate = MagicMock(return_value=(_verdict_json("T1"), 100))

    saved: list[dict] = []
    with patch("prep.services.concept_store.concept_store") as store:
        def _save(pid, dicts):
            saved.extend(dicts)
            return (len(dicts), 0)
        store.save_many.side_effect = _save
        report = validate_concepts_swarm(
            "p1", candidates=[cand], llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
        )
    assert report.triaged == 1
    assert saved[0]["status"] == "triage_pending"


def test_reject_verdict_lands_archived(tmp_path):
    cand = _candidate("Hallucinated", "T3", ("src/auth.py",))
    llm = MagicMock()
    llm.generate = MagicMock(return_value=(_verdict_json("REJECT"), 100))

    saved: list[dict] = []
    with patch("prep.services.concept_store.concept_store") as store:
        def _save(pid, dicts):
            saved.extend(dicts)
            return (len(dicts), 0)
        store.save_many.side_effect = _save
        report = validate_concepts_swarm(
            "p1", candidates=[cand], llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
        )
    assert report.archived == 1
    assert saved[0]["status"] == "archived"
    assert saved[0]["confidence"] == 0.0


def test_validate_uses_validate_evidence_when_present(tmp_path):
    """Validate's counter_evidence + falsification should override
    Generate's when Validate produced them (Validate is strict reviewer)."""
    cand = _candidate("Auth gate", "T2", ("src/auth.py",))
    cand = SynthesizedConcept(
        title=cand.title, content=cand.content, category=cand.category,
        tier=cand.tier, tier_pairwise=cand.tier_pairwise,
        anchors=cand.anchors,
        counter_evidence="generate_ce", falsification="generate_fa",
    )
    llm = MagicMock()
    llm.generate = MagicMock(return_value=(_verdict_json(
        "T2", counter_evidence="validate_ce", falsification="validate_fa",
    ), 100))

    saved: list[dict] = []
    with patch("prep.services.concept_store.concept_store") as store:
        def _save(pid, dicts):
            saved.extend(dicts)
            return (len(dicts), 0)
        store.save_many.side_effect = _save
        validate_concepts_swarm(
            "p1", candidates=[cand], llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
        )
    # `assertion` field carries the Validate-side falsification
    assert saved[0]["assertion"] == "validate_fa"


# ── Failure modes ───────────────────────────────────────────────────


def test_parse_failure_falls_back_to_archive(tmp_path):
    cand = _candidate("Auth gate", "T2", ("src/auth.py",))
    llm = MagicMock()
    # Return malformed JSON — parse_verdict_response returns None
    llm.generate = MagicMock(return_value=("{not valid", 50))

    saved: list[dict] = []
    with patch("prep.services.concept_store.concept_store") as store:
        def _save(pid, dicts):
            saved.extend(dicts)
            return (len(dicts), 0)
        store.save_many.side_effect = _save
        report = validate_concepts_swarm(
            "p1", candidates=[cand], llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
        )
    assert report.parse_failures == 1
    assert report.archived == 1
    # Conservative default: parse failure → archive
    assert saved[0]["status"] == "archived"


def test_worker_exception_does_not_sink_swarm(tmp_path):
    candidates = [
        _candidate("A", "T2", ("src/auth.py",)),
        _candidate("B", "T2", ("packages/ui/theme.ts",)),
    ]
    call_count = {"n": 0}
    def _gen(prompt: str, system: str, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated")
        return (_verdict_json("T2"), 100)
    llm = MagicMock()
    llm.generate = _gen

    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many.return_value = (2, 0)
        report = validate_concepts_swarm(
            "p1", candidates=candidates, llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
            max_workers=1,   # serialize so call order is deterministic
        )
    assert report.failed_workers == 1
    # The other one still went through
    assert report.activated == 1
    # The failed one defaults to archive
    assert report.archived == 1


# ── Dry run ─────────────────────────────────────────────────────────


def test_dry_run_skips_llm_and_save(tmp_path):
    cand = _candidate("Auth gate", "T2", ("src/auth.py",))
    llm = MagicMock()
    llm.generate = MagicMock(side_effect=AssertionError("LLM should not be called"))
    with patch("prep.services.concept_store.concept_store") as store:
        store.save_many = MagicMock(side_effect=AssertionError("save should not run"))
        report = validate_concepts_swarm(
            "p1", candidates=[cand], llm=llm,
            grounding=_grounding(), docs=_docs(), idx_dir=tmp_path,
            dry_run=True,
        )
    assert report.input_count == 1
    assert report.saved == 0
    llm.generate.assert_not_called()
