"""Per-stage reuse gates respect the barrier scope subsumption matrix.

Sister test to test_reset_barrier_is_reuse_blocked.py — that one tests
the helper in isolation; this one verifies that calling the reset
endpoint actually puts the helper into a state that blocks reuse for
the right stage groups."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app
from prep.services.pipeline.recovery import is_reuse_blocked


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """TestClient + initialized store singletons."""
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    with server._project_build_lock:
        server._project_build_threads.clear()
        server._project_last_build_result.clear()
        server._project_last_build_error.clear()
    with server._project_trace_build_lock:
        server._project_trace_build_threads.clear()

    from prep.services.pipeline_journal import journal
    from prep.services.concept_store import concept_store
    from prep.services.antibody_store import antibody_store
    from prep.services.observation_store import observation_store

    journal._conn = None
    concept_store._conn = None
    antibody_store._conn = None
    observation_store._conn = None

    journal.init(tmp_path / "journal.db")
    concept_store.init(tmp_path / "concepts.db")
    antibody_store.init(tmp_path / "antibodies.db")
    observation_store.init(tmp_path / "observations.db")

    yield TestClient(app)

    journal.close()
    concept_store.close()
    antibody_store.close()
    observation_store.close()
    journal._conn = None
    concept_store._conn = None
    antibody_store._conn = None
    observation_store._conn = None


def _add_project(client: TestClient, root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    res = client.post(
        "/projects",
        json={"path": str(root), "name": "t", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def test_no_barrier_no_block(client, tmp_path):
    """Fresh project with no barrier — reuse allowed for all groups."""
    pid = _add_project(client, tmp_path / "repo")
    assert is_reuse_blocked(pid, stage_group="fast_sync") is False
    assert is_reuse_blocked(pid, stage_group="deep_enrichment") is False
    assert is_reuse_blocked(pid, stage_group="finalize") is False


def test_enrichment_reset_blocks_deep_enrichment_and_finalize(client, tmp_path):
    """Reset 6-15 → barrier scope=enrichment subsumes both groups."""
    pid = _add_project(client, tmp_path / "repo")
    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    assert is_reuse_blocked(pid, stage_group="deep_enrichment") is True
    assert is_reuse_blocked(pid, stage_group="finalize") is True
    # fast_sync NOT blocked — its outputs are preserved by the reset
    assert is_reuse_blocked(pid, stage_group="fast_sync") is False


def test_finalize_reset_blocks_only_finalize(client, tmp_path):
    """Reset 11-15 → barrier scope=finalize blocks only finalize.

    Critical asymmetry: deep_enrichment outputs survived a finalize-only
    reset, so deep_enrichment reuse (clustering fingerprint match,
    group_reasoning fingerprint cache) must NOT be blocked."""
    pid = _add_project(client, tmp_path / "repo")
    res = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res.status_code in (200, 207)

    assert is_reuse_blocked(pid, stage_group="finalize") is True
    # The asymmetry: enrichment reuse is still allowed
    assert is_reuse_blocked(pid, stage_group="deep_enrichment") is False
    assert is_reuse_blocked(pid, stage_group="fast_sync") is False


def test_barrier_clears_with_external_call(client, tmp_path):
    """Sanity: clearing the barrier explicitly releases the gate.

    Mirrors what the orchestrator does at finalize-completion boundary.
    """
    pid = _add_project(client, tmp_path / "repo")
    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    assert is_reuse_blocked(pid, stage_group="deep_enrichment") is True

    from prep.services.pipeline.recovery import clear_reset_barrier
    cleared = clear_reset_barrier(pid)
    assert cleared is True

    assert is_reuse_blocked(pid, stage_group="deep_enrichment") is False
    assert is_reuse_blocked(pid, stage_group="finalize") is False


def test_double_reset_replaces_scope(client, tmp_path):
    """If user resets enrichment, then resets finalize, the barrier scope
    becomes finalize (the latest write wins). After the second reset,
    deep_enrichment reuse is no longer blocked."""
    pid = _add_project(client, tmp_path / "repo")

    # First reset: enrichment scope
    res1 = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res1.status_code in (200, 207)
    assert is_reuse_blocked(pid, stage_group="deep_enrichment") is True

    # Second reset: finalize scope (narrower)
    res2 = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res2.status_code in (200, 207)

    # Now only finalize is blocked, enrichment reuse opens up
    assert is_reuse_blocked(pid, stage_group="finalize") is True
    assert is_reuse_blocked(pid, stage_group="deep_enrichment") is False
