"""Selfheal cannot resurrect cleared data while the barrier is active.
Reset is idempotent under partial cleanup failure."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """TestClient + initialized store singletons (same as zombies fixture)."""
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


def _idx_dir(client: TestClient, pid: str) -> Path:  # noqa: ARG001
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project
    return Path(project_index_dir(require_project(pid)))


def test_enrichment_reset_writes_barrier_with_enrichment_scope(client, tmp_path):
    pid = _add_project(client, tmp_path / "repo")
    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    from prep.services.pipeline.recovery import reset_barrier_active, read_reset_barrier
    assert reset_barrier_active(pid)
    info = read_reset_barrier(pid)
    assert info is not None
    assert info["scope"] == "enrichment"


def test_finalize_reset_writes_barrier_with_finalize_scope(client, tmp_path):
    pid = _add_project(client, tmp_path / "repo")
    res = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res.status_code in (200, 207)

    from prep.services.pipeline.recovery import reset_barrier_active, read_reset_barrier
    assert reset_barrier_active(pid)
    info = read_reset_barrier(pid)
    assert info is not None
    assert info["scope"] == "finalize"


def test_barrier_blocks_reuse_after_reset(client, tmp_path):
    """After reset, is_reuse_blocked returns True for the relevant stage groups."""
    pid = _add_project(client, tmp_path / "repo")
    client.delete(f"/projects/{pid}/enrichment/full-reset")

    from prep.services.pipeline.recovery import is_reuse_blocked
    # enrichment-scope barrier subsumes both deep_enrichment and finalize
    assert is_reuse_blocked(pid, stage_group="deep_enrichment") is True
    assert is_reuse_blocked(pid, stage_group="finalize") is True


def test_reset_idempotent_under_partial_failure(client, tmp_path, monkeypatch):
    """If a cleanup step (concept_store) fails, the endpoint returns 500 and
    the barrier remains active. A second reset attempt completes cleanly."""
    pid = _add_project(client, tmp_path / "repo")

    from prep.services import concept_store as cs_mod
    real_clear = cs_mod.concept_store.clear_project
    calls = {"n": 0}

    def flaky(project_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated DB lock contention")
        return real_clear(project_id)

    monkeypatch.setattr(cs_mod.concept_store, "clear_project", flaky)

    # First call: cleanup raises → 500, barrier persists
    res1 = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res1.status_code == 500

    from prep.services.pipeline.recovery import reset_barrier_active
    assert reset_barrier_active(pid), "barrier must persist after partial failure"

    # Second call: succeeds (calls["n"] is now 2, real_clear runs)
    res2 = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res2.status_code in (200, 207)


def test_disk_artifacts_wiped_post_reset(client, tmp_path):
    """End-to-end: seed disk + store data, reset, confirm both gone."""
    pid = _add_project(client, tmp_path / "repo")
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Seed enrichment outputs
    (idx_dir / "trace_epistemic.jsonl").write_text("{}\n")
    (idx_dir / "trace_modules.jsonl").write_text("{}\n")
    (idx_dir / "atlas.json").write_text("{}")
    # Seed an unknown future stage output
    (idx_dir / "future_stage.jsonl").write_text("{}")
    # Seed fast-sync output (must survive)
    (idx_dir / "trace_nodes.jsonl").write_text("{}\n")

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    # Wiped
    assert not (idx_dir / "trace_epistemic.jsonl").exists()
    assert not (idx_dir / "trace_modules.jsonl").exists()
    assert not (idx_dir / "atlas.json").exists()
    assert not (idx_dir / "future_stage.jsonl").exists()
    # Survived
    assert (idx_dir / "trace_nodes.jsonl").is_file()

    # Barrier is active
    from prep.services.pipeline.recovery import reset_barrier_active
    assert reset_barrier_active(pid)
