"""Phase 125c T2b — tests for per-worker payload + prompt assembly.

Pure functions, no LLM. Validates that:
- WorkerPayload is composed correctly from shared Grounding + per-scope filter
- (system, user) prompts include the scope context, planning-doc tiers,
  in-scope rationale, and the cross-cutting grounding artifacts
"""
from __future__ import annotations

from prep.core.concept_generate_grounding import (
    WorkerScope,
    build_worker_scopes,
)
from prep.core.concept_generate_prompt import (
    WorkerPayload,
    build_generate_system_prompt,
    build_generate_user_prompt,
    build_worker_payload,
    build_worker_prompt,
)
from prep.core.concept_synthesizer import Grounding
from prep.core.docs_grounding import DiscoveredDoc, DocsGrounding


# ── Fixtures ────────────────────────────────────────────────────────


def _grounding() -> Grounding:
    return Grounding(
        project_name="testproj",
        atlas_summary="One-paragraph atlas summary.",
        segments=[{"name": "core", "file_count": 42, "domain_tags": ["py"]}],
        audit_findings=[
            {"title": "circular import", "severity": "warning",
             "file_paths": ["src/a.py", "src/b.py"]},
        ],
        spaghetti_hotspots=[
            {"file_path": "src/big.py", "score": 9.2,
             "severity": "warning", "in_circular": True},
        ],
        antibody_patterns=[
            {"name": "no-cloud-llm-without-license", "severity": "warn"},
        ],
        rationale_clusters=[
            {"title": "auth flow", "category": "security",
             "anchors": ["src/auth.py"], "content": "JWT validates..."},
            {"title": "css system", "category": "brand",
             "anchors": ["packages/ui/src/theme.ts"], "content": "..."},
            {"title": "ADR-42", "category": "decision",
             "anchors": ["docs/adr/0042.md"], "content": "Why X over Y..."},
            {"title": "react usage", "category": "technical",
             "anchors": ["packages/ui/src/x.tsx"], "content": "..."},
        ],
        top_md_docs=[],  # not used by 125c (replaced by docs grounding)
    )


def _docs() -> DocsGrounding:
    return DocsGrounding(
        version=1, generated_at=0,
        docs=[
            DiscoveredDoc(
                path="ARCHITECTURE.md", score=0.9,
                signals=("convention_match",), in_link_count=20,
                size_bytes=2000, excerpt="The system is split into...",
                headings=("Architecture", "Components"),
            ),
            DiscoveredDoc(
                path="docs/Phase125c/README.md", score=0.7,
                signals=("convention_match",), in_link_count=10,
                size_bytes=5000, excerpt="Phase 125c plans...",
                headings=("Scope",),
            ),
            DiscoveredDoc(
                path="docs/notes.md", score=0.4,
                signals=("folder_concentration",), in_link_count=2,
                size_bytes=500, excerpt="...", headings=("Notes",),
            ),
            DiscoveredDoc(
                path="random.md", score=0.1,
                signals=(), in_link_count=0,
                size_bytes=100, excerpt="...", headings=(),
            ),
        ],
        total_candidates_considered=4, selected_count=4,
    )


# ── build_worker_payload ────────────────────────────────────────────


def test_payload_filters_rationale_to_scope_categories():
    """A 3-axis 'rules' worker only sees security/constraint/decision rationale."""
    rules_scope = next(
        s for s in build_worker_scopes(3) if s.label == "rules"
    )
    payload = build_worker_payload(
        rules_scope, grounding=_grounding(), docs=_docs(),
    )
    in_scope_titles = {r["title"] for r in payload.rationale_in_scope}
    assert "auth flow" in in_scope_titles       # security
    assert "ADR-42" in in_scope_titles           # decision
    assert "css system" not in in_scope_titles   # brand → out
    assert "react usage" not in in_scope_titles  # technical → out


def test_payload_tiers_docs_by_score():
    """Default thresholds: full ≥ 0.5, headings 0.3-0.5, drop < 0.3."""
    scope = build_worker_scopes(1)[0]
    payload = build_worker_payload(
        scope, grounding=_grounding(), docs=_docs(),
    )
    full_paths = {d.path for d in payload.full_doc_excerpts}
    headings_paths = {d.path for d in payload.doc_headings_only}
    assert full_paths == {"ARCHITECTURE.md", "docs/Phase125c/README.md"}
    assert headings_paths == {"docs/notes.md"}
    # random.md (score=0.1) dropped


def test_payload_passes_through_shared_grounding_unchanged():
    """Atlas/audit/spaghetti/antibodies are global — every worker sees them."""
    scope = build_worker_scopes(1)[0]
    payload = build_worker_payload(
        scope, grounding=_grounding(), docs=_docs(),
    )
    assert payload.project_name == "testproj"
    assert payload.atlas_summary.startswith("One-paragraph atlas")
    assert len(payload.atlas_segments) == 1
    assert len(payload.audit_findings) == 1
    assert len(payload.spaghetti_hotspots) == 1
    assert len(payload.antibody_patterns) == 1


# ── Prompt builders ─────────────────────────────────────────────────


def test_system_prompt_mentions_assigned_scope():
    scope = next(s for s in build_worker_scopes(3) if s.label == "intent")
    sys_prompt = build_generate_system_prompt(scope)
    assert "ASSIGNED DIMENSION: intent" in sys_prompt
    assert "architecture" in sys_prompt   # category in scope
    # Sanity: still contains the T3 rubric inherited from SYNTH_SYSTEM_PROMPT
    assert "T3" in sys_prompt
    assert "BANNED OUTPUTS" in sys_prompt


def test_user_prompt_lists_scope_categories_in_emit_block():
    scope = next(s for s in build_worker_scopes(3) if s.label == "rules")
    payload = build_worker_payload(
        scope, grounding=_grounding(), docs=_docs(),
    )
    user_prompt = build_generate_user_prompt(payload)
    # The EMIT block instructs the worker to limit categories
    assert "category in your scope" in user_prompt
    assert "security" in user_prompt
    assert "constraint" in user_prompt
    assert "decision" in user_prompt


def test_user_prompt_includes_full_doc_excerpts():
    scope = build_worker_scopes(1)[0]
    payload = build_worker_payload(
        scope, grounding=_grounding(), docs=_docs(),
    )
    user_prompt = build_generate_user_prompt(payload)
    assert "PLANNING DOCS — FULL EXCERPTS" in user_prompt
    assert "ARCHITECTURE.md" in user_prompt
    assert "The system is split into" in user_prompt   # excerpt body present


def test_user_prompt_has_headings_only_section_for_borderline_tier():
    scope = build_worker_scopes(1)[0]
    payload = build_worker_payload(
        scope, grounding=_grounding(), docs=_docs(),
    )
    user_prompt = build_generate_user_prompt(payload)
    assert "PLANNING DOCS — HEADINGS ONLY" in user_prompt
    assert "docs/notes.md" in user_prompt
    # The borderline doc's excerpt body should NOT be in the prompt
    # (only headings + path); excerpt is "..." in the fixture so this
    # is a weak check but locks in the section structure.
    assert "Notes" in user_prompt   # the heading


def test_user_prompt_includes_rationale_filtered_by_scope():
    scope = next(s for s in build_worker_scopes(3) if s.label == "rules")
    payload = build_worker_payload(
        scope, grounding=_grounding(), docs=_docs(),
    )
    user_prompt = build_generate_user_prompt(payload)
    assert "MODULE RATIONALE IN YOUR DIMENSION" in user_prompt
    assert "auth flow" in user_prompt           # security in scope
    assert "ADR-42" in user_prompt              # decision in scope
    assert "css system" not in user_prompt      # brand out of scope


def test_build_worker_prompt_returns_system_user_pair():
    scope = build_worker_scopes(1)[0]
    payload = build_worker_payload(
        scope, grounding=_grounding(), docs=_docs(),
    )
    sys_prompt, user_prompt = build_worker_prompt(payload)
    assert "T3" in sys_prompt
    assert "PROJECT: testproj" in user_prompt


def test_empty_grounding_does_not_crash():
    """A fresh project may have no audit/spaghetti/rationale yet — the
    prompt builder must handle empty fields gracefully."""
    scope = build_worker_scopes(1)[0]
    payload = build_worker_payload(
        scope,
        grounding=Grounding(project_name="empty"),
        docs=DocsGrounding(),
    )
    sys_prompt, user_prompt = build_worker_prompt(payload)
    assert "PROJECT: empty" in user_prompt
    assert "EMIT JSON ARRAY ONLY" in user_prompt


def test_swarm_size_3_produces_three_distinct_prompts():
    """Smoke test: feeding the same grounding to all 3 axis-3 scopes
    produces 3 prompts that each emphasize a different dimension."""
    g = _grounding()
    d = _docs()
    prompts: dict[str, tuple[str, str]] = {}
    for scope in build_worker_scopes(3):
        payload = build_worker_payload(scope, grounding=g, docs=d)
        prompts[scope.label] = build_worker_prompt(payload)
    assert set(prompts.keys()) == {"intent", "rules", "implementation"}
    # Each system prompt names its own dimension
    assert "ASSIGNED DIMENSION: intent" in prompts["intent"][0]
    assert "ASSIGNED DIMENSION: rules" in prompts["rules"][0]
    assert "ASSIGNED DIMENSION: implementation" in prompts["implementation"][0]
    # And each user prompt's rationale section reflects the scope filter
    assert "auth flow" in prompts["rules"][1]
    assert "auth flow" not in prompts["intent"][1]
