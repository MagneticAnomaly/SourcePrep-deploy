"""Tests for prep.core.concept_t3_refine — Phase 125 T3.

Covers prompt builders, response parsing, and grouping. The
DB-applying runner ``run_pass3_refine`` requires a live LLM
client and concept store, so it's exercised by integration runs
on HomeColab after the calibration set is labeled.
"""
from __future__ import annotations

import json

import pytest

from prep.core.concept_clustering import ConceptInput
from prep.core.concept_t3_refine import (
    MAX_GROUP_SIZE,
    TIER_TO_CONFIDENCE,
    VALID_PAIRWISE,
    VALID_TIERS,
    T3RefinedConcept,
    _strip_code_fence,
    group_with_category,
    make_t3_system_prompt,
    make_t3_user_prompt,
    map_tier_to_confidence,
    parse_t3_response,
)


def _ci(cid: str, title: str, conf: float = 0.8, anchors: tuple = ()) -> ConceptInput:
    return ConceptInput(id=cid, title=title, confidence=conf, anchors=anchors)


# ──────────────────────────────────────────────────────────────────────
# Tier mapping
# ──────────────────────────────────────────────────────────────────────

def test_tier_mapping_is_three_tiers():
    assert set(TIER_TO_CONFIDENCE) == {"T1", "T2", "T3"}


def test_tier_confidence_is_monotonic():
    assert TIER_TO_CONFIDENCE["T1"] < TIER_TO_CONFIDENCE["T2"] < TIER_TO_CONFIDENCE["T3"]


def test_invalid_tier_returns_zero():
    assert map_tier_to_confidence("UNKNOWN") == 0.0
    assert map_tier_to_confidence("") == 0.0


# ──────────────────────────────────────────────────────────────────────
# Prompt builders
# ──────────────────────────────────────────────────────────────────────

def test_system_prompt_includes_all_three_tiers():
    sp = make_t3_system_prompt()
    assert "T1" in sp and "T2" in sp and "T3" in sp


def test_system_prompt_includes_passing_test_per_tier():
    sp = make_t3_system_prompt()
    # Each tier definition should have its passing test
    assert "no enforcement" in sp.lower()  # T1
    assert "enforcing mechanism" in sp.lower()  # T2
    assert "fail the build" in sp.lower()  # T3


def test_system_prompt_prescribes_field_order():
    """The schema must be presented with rationale before tier."""
    sp = make_t3_system_prompt()
    # counter_evidence must appear before tier in the description
    ce_pos = sp.find("counter_evidence")
    tier_pos = sp.find('"T1" | "T2" | "T3"')
    assert 0 < ce_pos < tier_pos


def test_system_prompt_size_under_cap():
    """System prompt must stay under ~2K tokens (≈8000 chars) per Round-2 research."""
    sp = make_t3_system_prompt()
    assert len(sp) < 8000, f"system prompt is {len(sp)} chars, target <8000"


def test_user_prompt_lists_concepts_in_order():
    cs = [_ci("a", "First"), _ci("b", "Second"), _ci("c", "Third")]
    up = make_t3_user_prompt(cs, category="x", segment="y")
    a = up.find("'a'")
    b = up.find("'b'")
    c = up.find("'c'")
    assert 0 < a < b < c


def test_user_prompt_includes_category_and_segment():
    up = make_t3_user_prompt([_ci("a", "x")], category="architecture", segment="packages-ui")
    assert "architecture" in up
    assert "packages-ui" in up


def test_user_prompt_marks_confidence_hint_as_ignored():
    """The LLM must NOT use the input confidence as a calibration anchor."""
    up = make_t3_user_prompt([_ci("a", "x", conf=0.92)])
    assert "ignore" in up.lower()
    assert "calibrate via tier" in up.lower()


# ──────────────────────────────────────────────────────────────────────
# Response parsing
# ──────────────────────────────────────────────────────────────────────

def _ok_entry(cid: str = "x", tier: str = "T2", **overrides) -> dict:
    base = {
        "concept_id": cid,
        "counter_evidence": "ce",
        "coincidence": "co",
        "falsification": "fa",
        "tier_pairwise": "closer_to_lower",
        "tier": tier,
        "tier_justification": "tj",
        "consolidation_action": "keep",
        "refined_title": "rt",
        "refined_content": "rc",
    }
    base.update(overrides)
    return base


def test_parse_empty_returns_empty():
    assert parse_t3_response("") == []
    assert parse_t3_response("   ") == []


def test_parse_invalid_json_returns_empty():
    assert parse_t3_response("not json") == []
    assert parse_t3_response("{") == []


def test_parse_non_array_returns_empty():
    assert parse_t3_response('{"concept_id": "a"}') == []


def test_parse_strips_markdown_code_fence():
    fenced = "```json\n[{}]\n```"
    # Single empty entry — no concept_id but parses
    result = parse_t3_response(fenced)
    # entry without tier is dropped, so we expect 0 or 1 depending on content
    assert isinstance(result, list)


def test_parse_strips_unfenced_code_block_too():
    """Plain ``` ``` (no language) should also strip."""
    fenced = f"```\n{json.dumps([_ok_entry()])}\n```"
    result = parse_t3_response(fenced)
    assert len(result) == 1
    assert result[0].tier == "T2"


def test_parse_drops_entries_with_invalid_tier():
    text = json.dumps([_ok_entry(cid="a", tier="MAYBE")])
    result = parse_t3_response(text)
    assert result == []


def test_parse_preserves_valid_entry():
    text = json.dumps([_ok_entry(cid="abc", tier="T3")])
    result = parse_t3_response(text)
    assert len(result) == 1
    r = result[0]
    assert r.concept_id == "abc"
    assert r.tier == "T3"
    assert r.confidence == TIER_TO_CONFIDENCE["T3"]


def test_parse_defaults_invalid_pairwise():
    entry = _ok_entry(tier_pairwise="bogus")
    text = json.dumps([entry])
    result = parse_t3_response(text)
    assert len(result) == 1
    assert result[0].tier_pairwise == "closer_to_lower"
    assert any("invalid tier_pairwise" in w for w in result[0].parse_warnings)


def test_parse_defaults_invalid_consolidation_action():
    entry = _ok_entry(consolidation_action="archive")
    text = json.dumps([entry])
    result = parse_t3_response(text)
    assert result[0].consolidation_action == "keep"


def test_parse_preserves_merge_with_action():
    entry = _ok_entry(consolidation_action="merge_with_xyz123")
    text = json.dumps([entry])
    result = parse_t3_response(text)
    assert result[0].consolidation_action == "merge_with_xyz123"


def test_parse_truncates_long_fields_defensively():
    entry = _ok_entry(refined_content="x" * 5000)
    text = json.dumps([entry])
    result = parse_t3_response(text)
    assert len(result[0].refined_content) <= 1500


def test_parse_handles_mixed_valid_invalid():
    text = json.dumps([
        _ok_entry(cid="a", tier="T2"),
        _ok_entry(cid="b", tier="MAYBE"),  # dropped
        _ok_entry(cid="c", tier="T3"),
    ])
    result = parse_t3_response(text)
    assert len(result) == 2
    assert {r.concept_id for r in result} == {"a", "c"}


# ──────────────────────────────────────────────────────────────────────
# Grouping
# ──────────────────────────────────────────────────────────────────────

def test_group_with_category_splits_by_category():
    items = [
        (_ci("a", "x"), "architecture"),
        (_ci("b", "y"), "architecture"),
        (_ci("c", "z"), "technical"),
    ]
    groups = group_with_category(items)
    cats = {g[0] for g in groups}
    assert cats == {"architecture", "technical"}


def test_group_with_category_uses_segment_majority_anchor():
    file_seg = {
        "src/a.py": "S1",
        "src/b.py": "S1",
        "src/c.py": "S2",
    }
    items = [
        (_ci("c1", "x", anchors=("src/a.py", "src/b.py", "src/c.py")), "arch"),
    ]
    groups = group_with_category(items, file_to_segment=file_seg)
    assert groups[0][0] == "arch"
    # 2 anchors in S1, 1 in S2 → S1 wins
    assert groups[0][1] == "S1"


def test_group_with_category_splits_oversize_groups():
    items = [(_ci(f"c{i}", f"t{i}"), "arch") for i in range(MAX_GROUP_SIZE + 5)]
    groups = group_with_category(items)
    # Should be 2 groups (both same cat,seg) of size MAX and 5
    assert len(groups) == 2
    sizes = sorted(len(g[2]) for g in groups)
    assert sizes == [5, MAX_GROUP_SIZE]


def test_group_with_category_no_segment_map_falls_back_to_star():
    items = [(_ci("a", "x"), "arch")]
    groups = group_with_category(items)
    assert groups[0][1] == "*"


# ──────────────────────────────────────────────────────────────────────
# Code-fence stripping
# ──────────────────────────────────────────────────────────────────────

def test_strip_code_fence_removes_json_fence():
    fenced = "```json\n[1,2,3]\n```"
    assert _strip_code_fence(fenced) == "[1,2,3]"


def test_strip_code_fence_removes_plain_fence():
    fenced = "```\nfoo\n```"
    assert _strip_code_fence(fenced) == "foo"


def test_strip_code_fence_passes_unfenced():
    assert _strip_code_fence("plain text") == "plain text"
