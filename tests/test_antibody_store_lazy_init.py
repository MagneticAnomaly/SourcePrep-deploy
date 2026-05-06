"""
Tests for AntibodyStore lazy-init.

Regression coverage for the 2026-05-06 dogfood bug — see
docs/Phase124_FinalizeChainEpistemicAudit/MCP_DOGFOOD_FEEDBACK_2026-05-05_SCRUTINY.md
item #3. The MCP server runs in a separate process from the FastAPI
daemon, so server.py's startup init() never reaches the MCP-side
singleton, and every prep_audit(action="antibodies") call threw
"AntibodyStore not initialized."
"""
from __future__ import annotations

import pytest

from prep.core.antibodies import (
    Antibody,
    Response,
    ResponseType,
    Severity,
    Trigger,
    TriggerType,
)
from prep.services.antibody_store import antibody_store


@pytest.fixture
def fresh_antibody_store(tmp_path, monkeypatch):
    """Reset the global singleton and point its lazy-init at tmp_path."""
    # Force the lazy-init to use the test tmp_path as the data dir
    monkeypatch.setenv("PREP_DATA_DIR", str(tmp_path))
    # Clear any existing connection from prior tests
    if antibody_store._conn is not None:
        antibody_store.close()
    antibody_store._conn = None
    yield antibody_store
    # Restore
    if antibody_store._conn is not None:
        antibody_store.close()
    antibody_store._conn = None


def test_lazy_init_when_uninitialized(fresh_antibody_store, tmp_path):
    """list_antibodies on an uninitialized store should auto-init from data_dir
    instead of throwing the historical 'AntibodyStore not initialized' error."""
    # Should not raise — this was the actual bug from 2026-05-05 dogfood.
    result = fresh_antibody_store.list_antibodies("test-project")
    assert result == []
    # The connection should now be live
    assert fresh_antibody_store._conn is not None


def test_lazy_init_then_save_and_list(fresh_antibody_store, tmp_path):
    """After lazy-init, normal save/list operations should work."""
    ab = Antibody(
        id="test-ab-1",
        name="Test Antibody",
        source_concept_id="c1",
        trigger=Trigger(type=TriggerType.FILE_MODIFIED, target="src/foo.py"),
        response=Response(type=ResponseType.AMBIENT_INJECT, message="Test trigger fired"),
        severity=Severity.WARN,
        status="testing",
    )
    fresh_antibody_store.save("proj-1", ab)
    listed = fresh_antibody_store.list_antibodies("proj-1")
    assert len(listed) == 1
    assert listed[0].id == "test-ab-1"


def test_explicit_init_still_works(tmp_path):
    """Explicit init() (the daemon startup path) should remain idempotent
    and override the lazy path."""
    if antibody_store._conn is not None:
        antibody_store.close()
    antibody_store._conn = None
    explicit_path = tmp_path / "custom_antibodies.db"
    try:
        antibody_store.init(explicit_path)
        assert antibody_store._conn is not None
        # Second init should be a no-op (the existing _conn is preserved)
        antibody_store.init(explicit_path)
        assert antibody_store._conn is not None
        # The file is at the explicit path, not derived from data_dir
        assert explicit_path.exists()
    finally:
        antibody_store.close()
        antibody_store._conn = None


def test_concept_store_lazy_init(tmp_path, monkeypatch):
    """ConceptStore got the same defensive lazy-init treatment as
    AntibodyStore on 2026-05-06 — verify it self-bootstraps from data_dir."""
    from prep.services.concept_store import concept_store
    monkeypatch.setenv("PREP_DATA_DIR", str(tmp_path))
    if concept_store._conn is not None:
        concept_store.close()
    concept_store._conn = None
    try:
        # Should not raise — was the original failure mode
        result = concept_store.list_concepts("test-project")
        assert result == []
        assert concept_store._conn is not None
    finally:
        concept_store.close()
        concept_store._conn = None


def test_observation_store_lazy_init(tmp_path, monkeypatch):
    """ObservationStore got the same defensive lazy-init treatment."""
    from prep.services.observation_store import observation_store
    monkeypatch.setenv("PREP_DATA_DIR", str(tmp_path))
    if observation_store._conn is not None:
        observation_store.close()
    observation_store._conn = None
    try:
        # Should not raise
        result = observation_store.get_recent("test-project", limit=10)
        assert result == []
        assert observation_store._conn is not None
    finally:
        observation_store.close()
        observation_store._conn = None
