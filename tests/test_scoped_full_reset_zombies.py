"""Reset 6-15 and Reset 11-15 must purge derived stores: concepts,
antibodies, journal rows for the relevant groups. Observations are
intentionally preserved (user-authored).

Regression coverage for the empirical bug found 2026-04-29 where 200
concepts and 373 antibodies survived multiple resets.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """TestClient + initialized store singletons.

    The store singletons normally get initialized by `prep serve` startup;
    in tests we have to init them by hand so the reset endpoint actually
    has something to clear.
    """
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

    # Init stores (each gets its own SQLite file in tmp_path).
    from prep.services.pipeline_journal import journal
    from prep.services.concept_store import concept_store
    from prep.services.antibody_store import antibody_store
    from prep.services.observation_store import observation_store

    # Reset _conn to None so init() will run fresh (singletons are
    # module-level and may already be initialized by prior tests).
    journal._conn = None
    concept_store._conn = None
    antibody_store._conn = None
    observation_store._conn = None

    journal.init(tmp_path / "journal.db")
    concept_store.init(tmp_path / "concepts.db")
    antibody_store.init(tmp_path / "antibodies.db")
    observation_store.init(tmp_path / "observations.db")

    yield TestClient(app)

    # Teardown: close the per-test SQLite handles so the next test fixture
    # opens fresh files.
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


def _seed_concepts(project_id: str, n: int) -> None:
    from prep.services.concept_store import concept_store
    for i in range(n):
        concept_store.save(
            project_id=project_id,
            title=f"concept-{i}",
            content="...",
            category="technical",
            confidence=0.5,
            anchors=[],
            tags=[],
        )


def _seed_antibodies(project_id: str, n: int) -> None:
    """Insert antibodies via raw SQL (sidesteps the Antibody dataclass)."""
    from prep.services.antibody_store import antibody_store
    conn = antibody_store._conn
    assert conn is not None
    for i in range(n):
        conn.execute(
            "INSERT INTO antibodies (id, project_id, name, source_concept_id, "
            "trigger_json, response_json, severity, status, created_at, "
            "last_triggered, trigger_count, dismiss_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"ab-{i}", project_id, f"ab-{i}", "", "{}", "{}", "warn", "testing", time.time(), None, 0, 0),
        )
    conn.commit()


def _seed_journal_runs(project_id: str) -> None:
    from prep.services.pipeline_journal import journal
    conn = journal._conn
    assert conn is not None
    now = time.time()
    for run_id, group in [
        ("r-fs", "fast_sync"),
        ("r-de", "deep_enrichment"),
        ("r-fn", "finalize"),
    ]:
        conn.execute(
            "INSERT INTO pipeline_runs (run_id, project_id, group_name, status, "
            "stages, current_stage_index, created_at) "
            "VALUES (?, ?, ?, 'completed', '[]', 0, ?)",
            (run_id, project_id, group, now),
        )
    conn.commit()


@pytest.mark.parametrize("endpoint", [
    "enrichment/full-reset",
    "finalize/full-reset",
])
def test_concepts_purged(client, tmp_path, endpoint):
    pid = _add_project(client, tmp_path / "repo")
    _seed_concepts(pid, 5)

    from prep.services.concept_store import concept_store
    conn = concept_store._conn
    assert conn is not None
    pre = conn.execute(
        "SELECT COUNT(*) FROM concepts WHERE project_id = ?", (pid,)
    ).fetchone()[0]
    # We seeded 5 concepts; project creation may add system concepts on top.
    assert pre >= 5

    res = client.delete(f"/projects/{pid}/{endpoint}")
    assert res.status_code in (200, 207)

    post = conn.execute(
        "SELECT COUNT(*) FROM concepts WHERE project_id = ?", (pid,)
    ).fetchone()[0]
    assert post == 0


@pytest.mark.parametrize("endpoint", [
    "enrichment/full-reset",
    "finalize/full-reset",
])
def test_antibodies_purged(client, tmp_path, endpoint):
    pid = _add_project(client, tmp_path / "repo")
    _seed_antibodies(pid, 5)

    from prep.services.antibody_store import antibody_store
    conn = antibody_store._conn
    assert conn is not None
    pre = conn.execute(
        "SELECT COUNT(*) FROM antibodies WHERE project_id = ?", (pid,)
    ).fetchone()[0]
    assert pre == 5

    res = client.delete(f"/projects/{pid}/{endpoint}")
    assert res.status_code in (200, 207)

    post = conn.execute(
        "SELECT COUNT(*) FROM antibodies WHERE project_id = ?", (pid,)
    ).fetchone()[0]
    assert post == 0


def test_enrichment_reset_purges_de_and_finalize_journal_rows(client, tmp_path):
    pid = _add_project(client, tmp_path / "repo")
    _seed_journal_runs(pid)

    from prep.services.pipeline_journal import journal
    conn = journal._conn
    assert conn is not None
    pre = conn.execute(
        "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
    ).fetchall()
    assert len(pre) == 3

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    post = [r["group_name"] for r in conn.execute(
        "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
    ).fetchall()]
    assert sorted(post) == ["fast_sync"]


def test_finalize_reset_purges_only_finalize_journal_rows(client, tmp_path):
    pid = _add_project(client, tmp_path / "repo")
    _seed_journal_runs(pid)

    res = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res.status_code in (200, 207)

    from prep.services.pipeline_journal import journal
    conn = journal._conn
    assert conn is not None
    post = [r["group_name"] for r in conn.execute(
        "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
    ).fetchall()]
    assert sorted(post) == ["deep_enrichment", "fast_sync"]


def test_observations_NOT_purged(client, tmp_path):
    """Observations are user-authored and intentionally survive reset."""
    pid = _add_project(client, tmp_path / "repo")
    from prep.services.observation_store import observation_store
    obs_id = observation_store.save(
        project_id=pid,
        content="user-authored note",
        category="note",
    )
    assert obs_id

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    conn = observation_store._conn
    assert conn is not None
    post = conn.execute(
        "SELECT COUNT(*) FROM observations WHERE project_id = ?", (pid,)
    ).fetchone()[0]
    assert post == 1
