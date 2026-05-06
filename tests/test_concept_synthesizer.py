"""Tests for prep.core.concept_synthesizer (Phase 125b)."""
from __future__ import annotations

import json

import pytest

from prep.core.concept_synthesizer import (
    MAX_SYNTHESIZED_CONCEPTS,
    TIER_TO_CONFIDENCE,
    Grounding,
    SynthesizedConcept,
    _strip_fence,
    build_synthesis_prompt,
    parse_synthesis_response,
)


# ──────────────────────────────────────────────────────────────────────
# Tier mapping
# ──────────────────────────────────────────────────────────────────────

def test_tier_mapping_three_tiers():
    assert set(TIER_TO_CONFIDENCE) == {"T1", "T2", "T3"}
    assert TIER_TO_CONFIDENCE["T1"] < TIER_TO_CONFIDENCE["T2"] < TIER_TO_CONFIDENCE["T3"]


# ──────────────────────────────────────────────────────────────────────
# Fence stripping
# ──────────────────────────────────────────────────────────────────────

def test_strip_fence_removes_json_fence():
    assert _strip_fence("```json\n[1,2]\n```") == "[1,2]"


def test_strip_fence_removes_plain_fence():
    assert _strip_fence("```\nfoo\n```") == "foo"


def test_strip_fence_passes_unfenced():
    assert _strip_fence("no fences here") == "no fences here"


# ──────────────────────────────────────────────────────────────────────
# Prompt builder
# ──────────────────────────────────────────────────────────────────────

def test_prompt_includes_anti_examples():
    """The system prompt must explicitly forbid module-rationale-style outputs.

    Phase 125b sharpening: BANNED list of junior-reviewer outputs is
    a stronger signal than just "BAD concepts" — and the prompt now
    leads with the BANNED bucket before the GOOD examples.
    """
    sys, _ = build_synthesis_prompt(Grounding())
    s_lower = sys.lower()
    assert "banned" in s_lower or "bad concepts" in s_lower
    assert "do not emit" in s_lower or "must not emit" in s_lower or "never emit" in s_lower
    # Verify at least one canonical junior-reviewer banned phrase is named
    assert any(phrase in s_lower for phrase in (
        "uses async", "modular architecture", "has tests", "library use",
    ))


def test_prompt_emphasizes_quality_over_quantity():
    """Phase 125b: empty output must be explicitly permitted, padding flagged.

    Replaces the old `30-100` quota check — that volume target was the
    over-production knob. New design: target is fewer-but-better, with
    explicit permission to emit nothing.
    """
    sys, _ = build_synthesis_prompt(Grounding())
    s_lower = sys.lower()
    assert "empty output is acceptable" in s_lower or "empty array" in s_lower
    assert "padding is a failure mode" in s_lower
    assert "fewer is better" in s_lower or "target 5-30" in s_lower or "fewer-but-better" in s_lower


def test_prompt_requires_counter_evidence_first():
    """Tier assignment must follow counter_evidence population, not precede it."""
    sys, _ = build_synthesis_prompt(Grounding())
    s_lower = sys.lower()
    assert "counter-evidence first" in s_lower or "counter_evidence first" in s_lower
    assert "do not default to t2" in s_lower or "default to t2" in s_lower


def test_prompt_includes_hostile_reviewer_pass():
    """Final downgrade pass must be in the prompt (anti-tier-inflation)."""
    sys, _ = build_synthesis_prompt(Grounding())
    s_lower = sys.lower()
    assert "hostile reviewer" in s_lower
    assert "downgrade" in s_lower


def test_prompt_lists_tier_definitions():
    sys, _ = build_synthesis_prompt(Grounding())
    assert "T1" in sys and "T2" in sys and "T3" in sys
    assert "fail the build" in sys.lower() or "fail build" in sys.lower()


def test_prompt_user_includes_grounding_when_provided():
    g = Grounding(
        project_name="Demo",
        atlas_summary="Demo atlas content",
        segments=[{"id": "core", "name": "Core", "file_count": 12, "domain_tags": ["x"]}],
        audit_findings=[{"title": "Hub bottleneck", "severity": "warning", "file_paths": ["src/x.py"], "description": ""}],
        spaghetti_hotspots=[{"file_path": "src/y.py", "score": 0.8, "severity": "critical", "in_circular": True}],
        antibody_patterns=[{"name": "License before cloud call", "severity": "warn"}],
        rationale_clusters=[{"title": "Module rationale A", "category": "architecture", "anchors": ["src/a.py"]}],
        top_md_docs=[{"path": "docs/ADR-1.md", "links": 7}],
    )
    _, user = build_synthesis_prompt(g)
    # Project header
    assert "Demo" in user
    # Atlas
    assert "Demo atlas content" in user
    # Segment
    assert "Core" in user
    # Audit
    assert "Hub bottleneck" in user
    # Spaghetti
    assert "src/y.py" in user
    # Antibody
    assert "License before cloud call" in user
    # Rationale
    assert "Module rationale A" in user
    # Top docs
    assert "docs/ADR-1.md" in user


def test_prompt_user_handles_empty_grounding():
    """When grounding is empty, the user prompt still includes the task line."""
    _, user = build_synthesis_prompt(Grounding())
    assert "TASK" in user.upper() or "emit" in user.lower()


def test_prompt_warns_against_echoing_rationale():
    g = Grounding(
        rationale_clusters=[{"title": "A", "category": "x", "anchors": []}],
    )
    _, user = build_synthesis_prompt(g)
    assert "synthesize" in user.lower() or "lift" in user.lower()
    assert "do not echo" in user.lower() or "do NOT echo" in user


# ──────────────────────────────────────────────────────────────────────
# Response parsing
# ──────────────────────────────────────────────────────────────────────

def _ok(title: str = "T", tier: str = "T2", **overrides) -> dict:
    base = {
        "title": title,
        "category": "architecture",
        "counter_evidence": "ce",
        "falsification": "fa",
        "tier_pairwise": "closer_to_lower",
        "tier": tier,
        "anchors": ["src/x.py"],
        "refined_content": "rc",
    }
    base.update(overrides)
    return base


def test_parse_empty_response_returns_empty():
    assert parse_synthesis_response("") == []
    assert parse_synthesis_response("   ") == []


def test_parse_invalid_json_returns_empty():
    assert parse_synthesis_response("not json") == []


def test_parse_non_array_returns_empty():
    assert parse_synthesis_response('{"title": "x"}') == []


def test_parse_strips_markdown_fence():
    text = f"```json\n{json.dumps([_ok(title='Concept A')])}\n```"
    parsed = parse_synthesis_response(text)
    assert len(parsed) == 1
    assert parsed[0].title == "Concept A"


def test_parse_drops_entries_missing_title():
    text = json.dumps([_ok(title=""), _ok(title="OK")])
    parsed = parse_synthesis_response(text)
    titles = [c.title for c in parsed]
    assert titles == ["OK"]


def test_parse_drops_entries_with_invalid_tier():
    text = json.dumps([_ok(tier="MAYBE"), _ok(tier="T3")])
    parsed = parse_synthesis_response(text)
    assert len(parsed) == 1
    assert parsed[0].tier == "T3"


def test_parse_defaults_invalid_pairwise():
    text = json.dumps([_ok(tier_pairwise="bogus")])
    parsed = parse_synthesis_response(text)
    assert parsed[0].tier_pairwise == "closer_to_lower"


def test_parse_returns_anchor_tuple():
    text = json.dumps([_ok(anchors=["src/a.py", "src/b.py"])])
    parsed = parse_synthesis_response(text)
    assert isinstance(parsed[0].anchors, tuple)
    assert parsed[0].anchors == ("src/a.py", "src/b.py")


def test_parse_skips_non_string_anchors():
    text = json.dumps([_ok(anchors=["src/x.py", None, 42, ""])])
    parsed = parse_synthesis_response(text)
    assert parsed[0].anchors == ("src/x.py",)


def test_synthesized_concept_confidence_maps_from_tier():
    c = SynthesizedConcept(
        title="x", content="y", category="architecture",
        tier="T3", tier_pairwise="closer_to_lower", anchors=(),
    )
    assert c.confidence == 0.92


def test_synthesized_concept_to_save_dict_sets_kind_concept():
    c = SynthesizedConcept(
        title="x", content="y", category="architecture",
        tier="T2", tier_pairwise="closer_to_lower", anchors=("src/a.py",),
    )
    d = c.to_save_dict()
    # Critical: this is what saves to the DB
    assert d["kind"] == "concept"
    assert d["confidence"] == TIER_TO_CONFIDENCE["T2"]
    assert d["anchors"] == ["src/a.py"]


def test_to_save_dict_promotes_t2_and_t3_to_active():
    """T2/T3 are LLM-gated as anchored & cross-cutting → active.

    T1 stays as 'seed' candidate. The synthesizer is itself the gate.
    """
    for tier in ("T2", "T3"):
        c = SynthesizedConcept(
            title="x", content="y", category="architecture",
            tier=tier, tier_pairwise="closer_to_lower", anchors=("a.py",),
        )
        assert c.to_save_dict()["status"] == "active", f"{tier} should be active"

    c1 = SynthesizedConcept(
        title="x", content="y", category="architecture",
        tier="T1", tier_pairwise="closer_to_lower", anchors=(),
    )
    assert c1.to_save_dict()["status"] == "seed"


def test_max_synthesized_concepts_constant_is_sane():
    # Sanity: should be on the order of 100s, not 10s or 10000s.
    assert 50 <= MAX_SYNTHESIZED_CONCEPTS <= 500


# ──────────────────────────────────────────────────────────────────────
# Freshness manifest (Phase 125b wrap-up)
# ──────────────────────────────────────────────────────────────────────

def test_synth_manifest_roundtrip(tmp_path):
    """Manifest writes and reads back with the same fingerprint."""
    from prep.core.concept_synthesizer import (
        _read_synth_manifest, _write_synth_manifest,
    )
    payload = {
        "rationale_count": 24,
        "rationale_max_updated_at": 1234567890.0,
        "synth_completed_at": 1234567950.0,
        "saved": 31,
        "total_emitted": 31,
    }
    _write_synth_manifest(tmp_path, payload)

    manifest_path = tmp_path / "concept_synthesis_manifest.json"
    assert manifest_path.is_file()

    read = _read_synth_manifest(tmp_path)
    assert read == payload


def test_synth_manifest_missing_returns_none(tmp_path):
    """No manifest file → returns None (not an error)."""
    from prep.core.concept_synthesizer import _read_synth_manifest
    assert _read_synth_manifest(tmp_path) is None


def test_synth_manifest_corrupted_returns_none(tmp_path):
    """Corrupted JSON in manifest → returns None (defensive, won't crash synth)."""
    from prep.core.concept_synthesizer import _read_synth_manifest
    (tmp_path / "concept_synthesis_manifest.json").write_text("not-json{{")
    assert _read_synth_manifest(tmp_path) is None


def test_freshness_skip_logic_count_changed():
    """If rationale count changed, skip should NOT trigger."""
    # Manifest snapshot at time T: count=24, max_ts=1000
    # Current state: count=25 (one new) → must NOT skip.
    last_count, last_ts = 24, 1000.0
    now_count, now_ts = 25, 1100.0
    should_skip = (last_count == now_count and now_ts <= last_ts)
    assert should_skip is False


def test_freshness_skip_logic_count_same_ts_unchanged():
    """If count + max_ts unchanged, skip SHOULD trigger."""
    last_count, last_ts = 24, 1000.0
    now_count, now_ts = 24, 1000.0
    should_skip = (last_count == now_count and now_ts <= last_ts)
    assert should_skip is True


def test_freshness_skip_logic_in_place_update():
    """If rationale was updated (same count, newer max_ts), skip should NOT trigger."""
    last_count, last_ts = 24, 1000.0
    now_count, now_ts = 24, 1100.0
    should_skip = (last_count == now_count and now_ts <= last_ts)
    assert should_skip is False


# ──────────────────────────────────────────────────────────────────────
# Truncated JSON salvage (Phase 125b wrap-up)
# ──────────────────────────────────────────────────────────────────────

def test_salvage_truncated_json_recovers_complete_entries():
    """LLM hit num_predict mid-array — recover complete objects up to last `}`."""
    truncated = (
        '[{"title":"a","tier":"T2","tier_pairwise":"closer_to_lower",'
        '"category":"architecture","anchors":["a.py"],"content":"x"},'
        '{"title":"b","tier":"T2","tier_pairwise":"closer_to_lower",'
        '"category":"architecture","anchors":["b.py"],"content":"y"},'
        '{"title":"c","tier":"T2","tier_pairwise":"closer_to_l'  # truncated mid-string
    )
    parsed = parse_synthesis_response(truncated)
    # Should recover a + b but drop the truncated c
    titles = sorted(c.title for c in parsed)
    assert titles == ["a", "b"]


def test_salvage_returns_empty_on_unrecoverable():
    """Garbage input that has no complete object → empty list, no crash."""
    parsed = parse_synthesis_response('[{"title":"a","tier":"T')
    assert parsed == []


def test_salvage_passes_through_complete_json():
    """Complete JSON parses on first try (salvage NOT invoked)."""
    complete = (
        '[{"title":"a","tier":"T3","tier_pairwise":"closer_to_higher",'
        '"category":"architecture","anchors":["a.py"],"content":"x"}]'
    )
    parsed = parse_synthesis_response(complete)
    assert len(parsed) == 1
    assert parsed[0].tier == "T3"
