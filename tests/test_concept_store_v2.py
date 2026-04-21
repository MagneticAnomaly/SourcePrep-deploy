import pytest
from prep.services.concept_store import ConceptStore, Concept
import json


@pytest.fixture
def store(tmp_path):
    s = ConceptStore()
    s.init(tmp_path / "test_concepts.db")
    yield s
    s.close()


def test_concept_has_assertion_field():
    c = Concept(
        id="test-1", project_id="proj-1", title="Zero-LLM Pi Agent",
        content="Pi Agent must never import LLM libraries",
        assertion="pi_agent.py does not import llm_client, openai, or anthropic",
        category="constraint", status="active",
    )
    assert c.assertion == "pi_agent.py does not import llm_client, openai, or anthropic"


def test_concept_has_doc_links_field():
    c = Concept(
        id="test-2", project_id="proj-1", title="Design System",
        content="Component library architecture",
        doc_links=[
            {"path": "packages/ui/src/components/", "label": "Component root", "type": "source"},
        ],
        category="architecture", status="active",
    )
    assert len(c.doc_links) == 1
    assert c.doc_links[0]["path"] == "packages/ui/src/components/"


def test_concept_has_superseded_by_field():
    c = Concept(
        id="test-3", project_id="proj-1", title="Old auth approach",
        content="Use JWT tokens",
        status="superseded", superseded_by="test-4",
        category="architecture",
    )
    assert c.superseded_by == "test-4"


def test_concept_defaults_new_fields_to_empty():
    c = Concept(
        id="test-5", project_id="proj-1", title="Basic concept",
        content="Just a note", category="technical", status="seed",
    )
    assert c.assertion == ""
    assert c.doc_links == []
    assert c.superseded_by is None


def test_save_and_retrieve_with_new_fields(store):
    concept_id = store.save(
        project_id="proj-1",
        title="Zero-LLM Pi Agent",
        content="Pi Agent must never import LLM libraries",
        assertion="pi_agent.py does not import llm_client",
        doc_links=[{"path": "src/pi_agent.py", "label": "Pi Agent", "type": "source"}],
        category="constraint",
        status="active",
    )
    assert concept_id is not None
    retrieved = store.get(concept_id)
    assert retrieved is not None
    assert retrieved.assertion == "pi_agent.py does not import llm_client"
    assert len(retrieved.doc_links) == 1
    assert retrieved.doc_links[0]["path"] == "src/pi_agent.py"


def test_supersede_concept(store):
    old_id = store.save(
        project_id="proj-1", title="Old approach",
        content="Use JWT", category="architecture",
    )
    new_id = store.save(
        project_id="proj-1", title="New approach",
        content="Use session tokens", category="architecture",
    )
    store.supersede(old_id, new_id)
    old = store.get(old_id)
    assert old.status == "superseded"
    assert old.superseded_by == new_id


def test_backward_compat_concepts_without_new_fields(store):
    concept_id = store.save(
        project_id="proj-1", title="Legacy concept",
        content="Just a note", category="technical",
    )
    retrieved = store.get(concept_id)
    assert retrieved.assertion == ""
    assert retrieved.doc_links == []
    assert retrieved.superseded_by is None
