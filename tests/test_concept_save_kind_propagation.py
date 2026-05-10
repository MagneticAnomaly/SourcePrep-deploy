"""Regression tests for the AI-save / synthesizer auto-acceptance path.

Two bugs the Phase 125b two-layer split exposed:

1. AI-direct saves via prep_concepts dropped the kind discriminator,
   so concepts written by AI agents landed in kind='module_rationale'
   and were invisible to the default prep_concepts(action='get')
   filter (which returns kind='concept'). The save looked silently
   rejected — "auto-accept not working".

2. concept_store.save() / save_many() UPDATE branches omitted the
   status column. A synthesizer re-run that promoted a concept from
   T1 (seed) to T2 (active) silently kept the old seed status when
   a same-titled row already existed.
"""
from __future__ import annotations

import pytest

from prep.services.concept_store import ConceptStore


@pytest.fixture
def store(tmp_path):
    s = ConceptStore()
    s.init(tmp_path / "save_kind.db")
    yield s
    s.close()


# ── Fix 1: kind='concept' default for explicit save() ───────────────


def test_save_with_explicit_concept_kind_is_visible_in_default_list(store):
    """A concept saved with kind='concept' shows up in the default
    list_concepts() (which filters to kind='concept')."""
    store.save(
        project_id="proj-1",
        title="License check precedes cloud LLM",
        content="Constraint enforced by decorator. See license_gate.py.",
        category="constraint",
        status="active",
        kind="concept",
    )
    items = store.list_concepts("proj-1")  # default kind='concept'
    assert len(items) == 1
    assert items[0].kind == "concept"
    assert items[0].status == "active"


def test_save_default_kind_is_module_rationale_for_seeders(store):
    """Default kind stays 'module_rationale' so seeder callsites that
    omit kind continue to land in the rationale layer (the seeder is
    the largest legitimate caller of save() and existing code
    relies on this default)."""
    store.save(
        project_id="proj-1",
        title="Module pdf_chunker centralizes PDF extraction",
        content="...",
        status="seed",
    )
    rationale = store.list_concepts("proj-1", kind="module_rationale")
    assert len(rationale) == 1
    concepts = store.list_concepts("proj-1")  # kind='concept'
    assert len(concepts) == 0


# ── Fix 2: UPDATE preserves status promotion ────────────────────────


def test_save_update_promotes_seed_to_active(store):
    """save() UPDATE branch: when a same-titled row exists at status='seed'
    and we re-save with status='active', the row should be promoted."""
    store.save(
        project_id="proj-1",
        title="Same title concept",
        content="initial",
        status="seed",
        kind="concept",
    )
    # Simulate a re-synthesis where the LLM upgraded the tier T1 → T2.
    store.save(
        project_id="proj-1",
        title="Same title concept",
        content="refined",
        status="active",
        kind="concept",
    )
    items = store.list_concepts("proj-1", kind="concept")
    assert len(items) == 1
    assert items[0].status == "active", (
        "UPDATE should reflect the new status, not silently keep the old seed"
    )
    assert items[0].content == "refined"


def test_save_many_update_promotes_seed_to_active(store):
    """save_many() UPDATE branch: same promotion behavior in the batch path
    used by the synthesizer."""
    store.save_many("proj-1", [{
        "title": "Batch same title",
        "content": "initial",
        "status": "seed",
        "kind": "concept",
    }])
    store.save_many("proj-1", [{
        "title": "Batch same title",
        "content": "refined",
        "status": "active",
        "kind": "concept",
    }])
    items = store.list_concepts("proj-1", kind="concept")
    assert len(items) == 1
    assert items[0].status == "active"
    assert items[0].content == "refined"


# ── API request model carries kind ──────────────────────────────────


def test_save_concept_request_defaults_kind_to_concept():
    """Pydantic SaveConceptRequest defaults the kind field to 'concept'
    so AI/user saves through the HTTP API land in the curated layer
    even when callers don't pass kind explicitly."""
    from prep.api.routers.concepts import SaveConceptRequest

    body = SaveConceptRequest(title="t", content="c")
    assert body.kind == "concept"
