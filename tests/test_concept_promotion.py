import pytest
from prep.core.concept_promotion import suggest_promotion, PromotionSuggestion, build_concept_from_observation


def _make_observation(content, category="decision", file_path="src/server.py"):
    return {"id": "obs-1", "content": content, "category": category, "file_path": file_path}


def test_decision_suggests_promotion():
    obs = _make_observation("We decided to use SQLite for portability", category="decision")
    suggestion = suggest_promotion(obs)
    assert suggestion is not None
    assert suggestion.reason is not None


def test_note_does_not_suggest():
    obs = _make_observation("Looked at the code today", category="note")
    assert suggest_promotion(obs) is None


def test_pattern_suggests_promotion():
    obs = _make_observation("All MCP handlers follow dispatch pattern", category="pattern")
    assert suggest_promotion(obs) is not None


def test_bug_does_not_suggest():
    obs = _make_observation("Found a null pointer issue", category="bug")
    assert suggest_promotion(obs) is None


def test_build_concept_from_observation():
    obs = _make_observation(
        "We decided to use SQLite for portability",
        category="decision",
        file_path="src/codrag/core/project_registry.py",
    )
    concept = build_concept_from_observation(obs)
    assert concept["title"] != ""
    assert concept["content"] == obs["content"]
    assert "src/codrag/core/project_registry.py" in concept["anchors"]
    assert concept["status"] == "proposed"
    assert concept["assertion"] == ""


def test_build_concept_preserves_observation_ref():
    obs = _make_observation("Pattern: all handlers validate before dispatch", category="pattern")
    concept = build_concept_from_observation(obs)
    assert concept["source"] == "obs-1"
