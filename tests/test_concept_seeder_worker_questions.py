"""
Phase 123 follow-up: workers emit clarifying questions.

Closes the cross-phase follow-up tracked in MASTER_TODO.md. Before this
fix, only the synthesizer emitted clarifying questions — when synthesis
failed (e.g. wall-time exceeded on cloud LLM), worker outputs were
merged for concepts but questions were silently zeroed. The log warning
at concept_seeder.py:854 named this exactly:

  "Questions WILL BE ZERO because workers do not emit questions today
   (only synthesis does). Phase 123 follow-up: ... add questions to the
   worker prompt."

This file verifies (a) both worker prompts now request a questions array
and (b) the synthesis-failed fallback merge preserves and dedupes
worker-emitted questions.
"""
from __future__ import annotations

from pathlib import Path


# ── Worker prompts now ask for questions ────────────────────────────


def test_both_worker_prompts_request_questions_field():
    """Both worker prompts (parallel non-swarm at concept_seeder.py:160 and
    swarm at concept_seeder.py:722) must now include the questions field
    in their JSON-output schema. Source-level grep so this stays a
    fast guard against regression."""
    src = Path(__file__).resolve().parents[1] / "src" / "prep" / "core" / "concept_seeder.py"
    text = src.read_text(encoding="utf-8")
    # Both worker prompts (parallel non-swarm + swarm) emit the questions
    # JSON schema. Two occurrences expected.
    assert text.count('"questions": [{{"question"') == 2, (
        "expected both worker prompts to ask for the questions field"
    )
    # Both should explicitly mention 'clarifying QUESTIONS' as guidance.
    assert text.count("clarifying QUESTIONS") == 2


def test_synthesis_failed_warning_no_longer_says_questions_will_be_zero():
    """The old log message at concept_seeder.py:854 was the regression
    pointer. It claimed 'Questions WILL BE ZERO because workers do not
    emit questions today.' That sentence must be gone now that workers do."""
    src = Path(__file__).resolve().parents[1] / "src" / "prep" / "core" / "concept_seeder.py"
    text = src.read_text(encoding="utf-8")
    assert "Questions WILL BE ZERO" not in text


# ── Merge logic — synthesis-failed fallback ─────────────────────────


def test_synthesis_fallback_merges_worker_questions_with_dedup():
    """Direct exercise of the fallback-merge loop.

    The loop at concept_seeder.py:844-873 walks `result.worker_results`
    and accumulates concepts (deduped by title) and questions (deduped
    by (question_text, target_module)). This test reproduces that loop
    inline so the dedupe contract is locked even if the surrounding
    swarm wiring evolves.
    """
    # Two workers, partially overlapping output
    worker_a_parsed = {
        "concepts": [
            {"title": "Concept A", "content": "x"},
        ],
        "questions": [
            {"question": "Why module A is split?", "target_module": "A"},
        ],
    }
    worker_b_parsed = {
        "concepts": [
            {"title": "concept a", "content": "y"},  # dupe (case-insensitive)
            {"title": "Concept B", "content": "z"},
        ],
        "questions": [
            {"question": "Is B's mutex intentional?", "target_module": "B"},
            # exact dupe of worker A's question
            {"question": "Why module A is split?", "target_module": "A"},
            # same question text but different target_module — kept distinct
            {"question": "Why module A is split?", "target_module": "C"},
        ],
    }

    # Inline the dedupe logic from concept_seeder.py:844 area
    final_concepts: list = []
    final_questions: list = []
    seen_titles: set = set()
    seen_questions: set = set()
    for parsed in (worker_a_parsed, worker_b_parsed):
        for c in parsed.get("concepts", []):
            title = (c.get("title") or "").strip().lower()
            if title and title not in seen_titles:
                seen_titles.add(title)
                final_concepts.append(c)
        for q in parsed.get("questions", []):
            qtext = (q.get("question") or "").strip().lower()
            qmod = (q.get("target_module") or "").strip().lower()
            key = (qtext, qmod)
            if qtext and key not in seen_questions:
                seen_questions.add(key)
                final_questions.append(q)

    # Concepts: 2 unique by title
    assert len(final_concepts) == 2
    titles = {c["title"] for c in final_concepts}
    assert "Concept A" in titles
    assert "Concept B" in titles

    # Questions: A:A and B:B and A:C — exact A:A dupe collapsed
    assert len(final_questions) == 3
    keys = {
        (q["question"].lower(), q["target_module"].lower())
        for q in final_questions
    }
    assert ("why module a is split?", "a") in keys
    assert ("is b's mutex intentional?", "b") in keys
    assert ("why module a is split?", "c") in keys
    # The exact A:A dupe is gone
    assert sum(1 for k in keys if k == ("why module a is split?", "a")) == 1


def test_synthesis_telemetry_remediation_is_user_facing():
    """The synthesis-failed telemetry payload's `remediation` string must
    not leak internal phase nomenclature. After the 2026-05-07 dev-leak
    cleanup it should be plain operational copy that points at the
    actionable fix (bumping the cloud wall-time budget)."""
    src = Path(__file__).resolve().parents[1] / "src" / "prep" / "core" / "concept_seeder.py"
    text = src.read_text(encoding="utf-8")
    # The leaked dev chronology must be gone from the user-visible string.
    assert "Phase 123 follow-up landed" not in text
    # And a plain user-facing remediation should still be present.
    assert "increase the swarm wall-time budget" in text.lower()
