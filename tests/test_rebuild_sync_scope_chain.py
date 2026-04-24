"""Phase 117 integration — Rebuild Sync force-starts stages 1-5 and auto-clears barrier.

Full-chain integration test for the Rebuild Sync seam. Per the project's
"test full import chain" rule (F-117), this test does NOT mock the seam under
test. The seam is:

    POST /pipeline/fast {"force_from_start": True}
      → real write_reset_barrier(pid, reason="rebuild", scope="sync")
      → landed on the real project index dir
      → visible to real read_reset_barrier() + GET /pipeline/status
      → real maybe_clear_scoped_barrier(pid, "fast_sync")
        (the same function the orchestrator calls at the fast_sync boundary)
      → barrier file removed, /pipeline/status reflects cleared state.

We invoke ``maybe_clear_scoped_barrier`` directly instead of waiting for the
real orchestrator to finish all 5 stages: fast_sync stage 5 (KNOWLEDGE) runs
real embeddings and would need an ONNX/Ollama model, a journal, a branch
backup, and a file watcher — infrastructure that isn't guaranteed in the test
environment and would make the test slow and flaky. Invoking the exact
production boundary function is NOT a mock — it is the same code the
orchestrator runs at fast_sync completion (orchestrator.py:1915-1916).

Layers exercised end-to-end WITHOUT mocks:
  * FastAPI router (`/pipeline/fast`) — request model + force_from_start dispatch
  * ``prep.services.pipeline.recovery.write_reset_barrier`` — real file write
  * ``_resolve_idx_dir`` via real ProjectRegistry → real embedded idx_dir
  * ``/pipeline/status`` endpoint's barrier payload (uses real read_reset_barrier)
  * ``maybe_clear_scoped_barrier`` — real scope-boundary check + unlink
"""
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
    """Isolated TestClient with a fresh registry rooted at tmp_path.

    Matches the pattern in ``tests/test_pipeline_barrier_clear.py`` — swap out
    the module-level registry handles so each test gets a clean projects DB.
    """
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    yield TestClient(app)
    # Clean up any orchestrator state leaked by this test so subsequent tests
    # (including in the same process) don't see a stale fast_sync run. The
    # singleton ``pipeline_orchestrator`` holds a ``_runs`` dict across tests.
    try:
        from prep.services.pipeline_orchestrator import pipeline_orchestrator
        # Best-effort cancel for every (pid, group) this test may have started.
        active_keys = list(pipeline_orchestrator._runs.keys())
        for pid, _group in active_keys:
            try:
                pipeline_orchestrator.cancel_fast_sync(pid)
            except Exception:
                pass
        pipeline_orchestrator._runs.clear()
    except Exception:
        pass


def _add_embedded(client: TestClient, repo: Path) -> str:
    """Create an embedded project and return its id.

    ``embedded`` mode puts the index dir at ``<repo>/.sourceprep`` so
    ``_resolve_idx_dir`` resolves against real tmp_path disk.
    """
    res = client.post(
        "/projects",
        json={"path": str(repo), "name": "phase117-sync-chain", "mode": "embedded"},
    )
    assert res.status_code == 200, res.text
    return str(res.json()["data"]["project"]["id"])


def test_rebuild_sync_sets_barrier_and_clears_at_fast_sync_boundary(
    client: TestClient, tmp_path: Path
) -> None:
    """The full seam: /pipeline/fast force=True → barrier(scope=sync) → boundary clear.

    Asserts at every layer:
      1. API returns 200 with ``started=True, force_from_start=True``.
      2. Real barrier file exists on disk (via ``read_reset_barrier``).
      3. Barrier has ``reason="rebuild"``, ``scope="sync"``.
      4. GET ``/pipeline/status`` reports ``barrier.active=True``.
      5. After the fast_sync boundary clear, barrier is gone on disk.
      6. GET ``/pipeline/status`` reports ``barrier.active=False``.
    """
    from prep.services.pipeline.recovery import (
        maybe_clear_scoped_barrier,
        read_reset_barrier,
    )

    # Build a minimal source tree — the force_from_start path writes the
    # barrier BEFORE the orchestrator starts, so even if the pipeline
    # ultimately fails to embed (no model), the barrier lands on disk.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "hello.py").write_text("def hello():\n    return 1\n")

    pid = _add_embedded(client, repo)

    # ── Step 1: Rebuild Sync ──────────────────────────────────────────
    res = client.post(f"/projects/{pid}/pipeline/fast", json={"force_from_start": True})
    # 200 → orchestrator accepted the start. The test targets the barrier
    # seam, not end-to-end stage execution, so a 200 response is enough to
    # prove the force path wrote the barrier and dispatched.
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["started"] is True
    assert data["group"] == "fast_sync"
    assert data["force_from_start"] is True

    # ── Step 2: Real barrier on real disk with scope=sync ─────────────
    info = read_reset_barrier(pid)
    assert info is not None, "barrier should exist after force_from_start=True"
    assert info["reason"] == "rebuild"
    assert info["scope"] == "sync"
    assert info["age_seconds"] >= 0.0

    # ── Step 3: /pipeline/status reflects barrier active ──────────────
    # The status payload's barrier sub-object doesn't expose `scope` today
    # (see pipeline.py ~line 855 — scope is intentionally omitted). We
    # assert only on `active` here; scope is covered via the direct read
    # above, which is the source of truth.
    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    status = res.json()["data"]
    assert status.get("barrier", {}).get("active") is True

    # ── Step 4: Simulate fast_sync completion boundary ────────────────
    # The orchestrator calls this exact function at fast_sync completion
    # (orchestrator.py:1915-1916). Invoking it directly here chains the
    # barrier-write seam to the barrier-clear seam using the same
    # production code the orchestrator uses. This is NOT a mock — it is
    # the actual boundary clear under test.
    cleared = maybe_clear_scoped_barrier(pid, completed_group="fast_sync")
    assert cleared is True, "scope=sync barrier must clear at fast_sync boundary"

    # ── Step 5: Real barrier file removed ─────────────────────────────
    assert read_reset_barrier(pid) is None

    # ── Step 6: /pipeline/status reflects cleared state ───────────────
    # The status endpoint has a 3s stale-while-refresh cache (pipeline.py
    # ~line 62-64). Invalidate it explicitly so the next read reflects the
    # just-cleared barrier — production has a dedicated cache-bust path
    # (pipeline.py:1193-1194) for exactly this scenario.
    from prep.api.routers import pipeline as pipeline_router
    with pipeline_router._status_cache_lock:
        pipeline_router._status_cache.pop(pid, None)

    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    status = res.json()["data"]
    assert status.get("barrier", {}).get("active") is False


def test_rebuild_sync_barrier_only_clears_at_sync_boundary_not_deep(
    client: TestClient, tmp_path: Path
) -> None:
    """scope=sync must NOT clear when deep_enrichment / finalize finishes.

    Locks the scope boundary semantics for the fast_sync rebuild scope so a
    future refactor can't accidentally clear the barrier on a wrong group's
    completion (which would re-enable selfheal mid-run and let stale stubs
    leak into downstream stages).
    """
    from prep.services.pipeline.recovery import (
        maybe_clear_scoped_barrier,
        read_reset_barrier,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "m.py").write_text("x = 1\n")
    pid = _add_embedded(client, repo)

    res = client.post(f"/projects/{pid}/pipeline/fast", json={"force_from_start": True})
    assert res.status_code == 200, res.text

    assert read_reset_barrier(pid) is not None

    # Wrong boundaries must NOT clear scope=sync
    assert maybe_clear_scoped_barrier(pid, completed_group="deep_enrichment") is False
    assert maybe_clear_scoped_barrier(pid, completed_group="finalize") is False
    # Still there
    info = read_reset_barrier(pid)
    assert info is not None
    assert info["scope"] == "sync"

    # Right boundary clears it
    assert maybe_clear_scoped_barrier(pid, completed_group="fast_sync") is True
    assert read_reset_barrier(pid) is None
