"""Phase 125c T3a — tests for the Validate worker prompt + verdict parsing.

Pure functions; no LLM. Validates that:
- Per-concept user prompt includes candidate + grounding sections
- System prompt encodes the T3 / T2 / T1 / REJECT rubric
- Verdict parser handles JSON with optional fence + invalid verdict labels
- Reconciliation rule produces the expected (tier, status) pairs
"""
from __future__ import annotations

import json

from prep.core.concept_synthesizer import SynthesizedConcept
from prep.core.concept_validate_prompt import (
    VALIDATE_SYSTEM_PROMPT,
    ValidationVerdict,
    build_validate_prompt,
    build_validate_user_prompt,
    parse_verdict_response,
    reconcile_tier,
)


# ── Fixtures ────────────────────────────────────────────────────────


def _candidate(
    title: str = "License gate", tier: str = "T2",
    anchors: tuple[str, ...] = ("src/llm/gate.py",),
) -> SynthesizedConcept:
    return SynthesizedConcept(
        title=title,
        content="License verification must precede cloud LLM calls.",
        category="constraint",
        tier=tier,
        tier_pairwise="closer_to_lower",
        anchors=anchors,
        counter_evidence="see src/test/no_decorator.py",
        falsification="grep '@licensed' against LLMClient.generate sites",
    )


# ── User prompt content ─────────────────────────────────────────────


def test_user_prompt_includes_candidate_fields():
    p = build_validate_user_prompt(candidate=_candidate())
    assert "License gate" in p
    assert "self-rated tier (Generate): T2" in p
    assert "src/llm/gate.py" in p
    assert "License verification" in p
    assert "EMIT JSON OBJECT ONLY" in p


def test_user_prompt_lists_related_rationale_when_present():
    rationale = [
        {"title": "auth flow", "category": "security",
         "anchors": ["src/auth.py"], "content": "JWT validates..."},
    ]
    p = build_validate_user_prompt(
        candidate=_candidate(), related_rationale=rationale,
    )
    assert "RELATED MODULE RATIONALE" in p
    assert "auth flow" in p
    assert "JWT validates" in p


def test_user_prompt_lists_doc_excerpts_when_present():
    docs = [{
        "path": "ARCHITECTURE.md",
        "excerpt": "All LLM calls go through the gate.",
    }]
    p = build_validate_user_prompt(
        candidate=_candidate(), related_doc_excerpts=docs,
    )
    assert "RELATED PLANNING DOCS" in p
    assert "ARCHITECTURE.md" in p
    assert "All LLM calls go through the gate." in p


def test_user_prompt_warns_on_empty_grounding():
    p = build_validate_user_prompt(candidate=_candidate())
    assert "GROUNDING — (NONE" in p
    assert "T1 or REJECT" in p   # nudge the worker to be skeptical


def test_build_validate_prompt_returns_system_user_pair():
    sys_p, user_p = build_validate_prompt(candidate=_candidate())
    assert sys_p == VALIDATE_SYSTEM_PROMPT
    assert "License gate" in user_p


# ── System prompt encodes the rubric ────────────────────────────────


def test_system_prompt_encodes_full_tier_rubric():
    assert "T3 — Codified" in VALIDATE_SYSTEM_PROMPT
    assert "T2 — Documented decision" in VALIDATE_SYSTEM_PROMPT
    assert "T1 — Pattern observed" in VALIDATE_SYSTEM_PROMPT
    assert "REJECT" in VALIDATE_SYSTEM_PROMPT
    # Field order is the calibration-research-derived anti-bias rule
    assert "counter_evidence FIRST" in VALIDATE_SYSTEM_PROMPT
    assert "tier LAST" in VALIDATE_SYSTEM_PROMPT


# ── Verdict parsing ─────────────────────────────────────────────────


def test_parse_verdict_basic_t3():
    text = json.dumps({
        "counter_evidence": "no callers of LLMClient.generate without @licensed",
        "falsification": "grep returns zero hits",
        "rationale": "anchored decorator + CI lint enforce",
        "verdict": "T3",
    })
    v = parse_verdict_response(text)
    assert v is not None
    assert v.verdict == "T3"
    assert v.counter_evidence.startswith("no callers")


def test_parse_verdict_handles_markdown_fence():
    raw = "```json\n" + json.dumps({
        "counter_evidence": "x", "falsification": "y",
        "rationale": "z", "verdict": "T1",
    }) + "\n```"
    v = parse_verdict_response(raw)
    assert v is not None
    assert v.verdict == "T1"


def test_parse_verdict_rejects_invalid_label():
    text = json.dumps({
        "counter_evidence": "x", "falsification": "y",
        "rationale": "z", "verdict": "VERY_HIGH",
    })
    assert parse_verdict_response(text) is None


def test_parse_verdict_returns_none_on_empty():
    assert parse_verdict_response("") is None
    assert parse_verdict_response("   ") is None


def test_parse_verdict_returns_none_on_unparsable():
    assert parse_verdict_response("{not json") is None
    assert parse_verdict_response("[not an object]") is None


def test_parse_verdict_rejects_non_object_root():
    """Verdict must be a JSON object, not an array."""
    assert parse_verdict_response('[{"verdict": "T2"}]') is None


def test_parse_verdict_uppercases_lowercase_input():
    text = json.dumps({"verdict": "t2", "counter_evidence": "",
                       "falsification": "", "rationale": ""})
    v = parse_verdict_response(text)
    assert v is not None
    assert v.verdict == "T2"


# ── Reconciliation ──────────────────────────────────────────────────


def test_reconcile_reject_wins_over_any_generate_tier():
    """Hostile reviewer says REJECT; tier doesn't matter — archive."""
    for gen_tier in ("T1", "T2", "T3"):
        tier, status = reconcile_tier(gen_tier, "REJECT")
        assert tier == "REJECT"
        assert status == "archived"


def test_reconcile_t3_validate_yields_active():
    tier, status = reconcile_tier("T2", "T3")
    assert tier == "T3"
    assert status == "active"


def test_reconcile_t2_validate_yields_active():
    tier, status = reconcile_tier("T2", "T2")
    assert tier == "T2"
    assert status == "active"


def test_reconcile_t1_validate_yields_triage():
    tier, status = reconcile_tier("T2", "T1")
    assert tier == "T1"
    assert status == "triage_pending"


def test_reconcile_validate_downgrade_always_wins():
    """Generate said T3, Validate said T1 → T1 wins (status=triage)."""
    tier, status = reconcile_tier("T3", "T1")
    assert tier == "T1"
    assert status == "triage_pending"


def test_reconcile_big_upgrade_meets_in_middle():
    """Generate said T1, Validate said T3 → suspicious → T2 (meet in middle)."""
    tier, status = reconcile_tier("T1", "T3")
    assert tier == "T2"
    assert status == "active"


def test_reconcile_small_upgrade_accepted_as_is():
    """T1 → T2 or T2 → T3 (distance 1) is accepted directly."""
    assert reconcile_tier("T1", "T2") == ("T2", "active")
    assert reconcile_tier("T2", "T3") == ("T3", "active")


def test_reconcile_equal_tiers_pass_through():
    """No disagreement — Validate's tier wins (it's strict reviewer)."""
    for t in ("T1", "T2", "T3"):
        gen_tier, status = reconcile_tier(t, t)
        assert gen_tier == t
        # Status mapping
        if t == "T1":
            assert status == "triage_pending"
        else:
            assert status == "active"
