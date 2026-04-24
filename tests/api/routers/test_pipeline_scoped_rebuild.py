"""Phase 117: scoped-rebuild body params on /pipeline/fast and /pipeline/deep."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from prep.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_project(monkeypatch):
    def _noop(_pid):
        return None
    monkeypatch.setattr(
        "prep.services.project_helpers.require_project_writable", _noop
    )
    return "proj-test"


def test_pipeline_fast_with_force_from_start_writes_sync_barrier(
    client, fake_project, monkeypatch
):
    from prep.services.pipeline import recovery

    writes: list[tuple[str, str, str]] = []

    def fake_write(pid, reason, scope="all"):
        writes.append((pid, reason, scope))
        return True

    monkeypatch.setattr(recovery, "write_reset_barrier", fake_write)

    started = MagicMock(return_value=True)
    orch = MagicMock()
    orch.run_fast_sync = started
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(
        f"/projects/{fake_project}/pipeline/fast",
        json={"force_from_start": True},
    )
    assert resp.status_code == 200
    assert writes == [(fake_project, "rebuild", "sync")]
    orch.run_fast_sync.assert_called_once_with(fake_project, force_from_start=True)


def test_pipeline_deep_with_force_from_start_writes_enrichment_barrier(
    client, fake_project, monkeypatch
):
    from prep.services.pipeline import recovery
    writes: list[tuple[str, str, str]] = []

    def fake_write(pid, reason, scope="all"):
        writes.append((pid, reason, scope))
        return True

    monkeypatch.setattr(recovery, "write_reset_barrier", fake_write)

    orch = MagicMock()
    orch.run_deep_enrichment = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(
        f"/projects/{fake_project}/pipeline/deep",
        json={"force_from_start": True},
    )
    assert resp.status_code == 200
    assert writes == [(fake_project, "rebuild", "enrichment")]
    orch.run_deep_enrichment.assert_called_once_with(fake_project, force_from_start=True)


def test_pipeline_fast_without_force_from_start_does_not_write_barrier(
    client, fake_project, monkeypatch
):
    from prep.services.pipeline import recovery
    writes: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        recovery, "write_reset_barrier",
        lambda pid, reason, scope="all": writes.append((pid, reason, scope)) or True,
    )

    orch = MagicMock()
    orch.run_fast_sync = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(f"/projects/{fake_project}/pipeline/fast", json={})
    assert resp.status_code == 200
    assert writes == []
    orch.run_fast_sync.assert_called_once_with(fake_project, force_from_start=False)


def test_pipeline_fast_clears_barrier_when_orchestrator_refuses(
    client, fake_project, monkeypatch
):
    """When force=True but orchestrator returns False, barrier should not linger."""
    from prep.services.pipeline import recovery

    write_calls: list[tuple] = []
    clear_calls: list[str] = []

    def fake_write(pid, reason, scope="all"):
        write_calls.append((pid, reason, scope))
        return True

    def fake_clear(pid):
        clear_calls.append(pid)
        return True

    monkeypatch.setattr(recovery, "write_reset_barrier", fake_write)
    monkeypatch.setattr(recovery, "clear_reset_barrier", fake_clear)

    orch = MagicMock()
    orch.run_fast_sync = MagicMock(return_value=False)  # orchestrator refuses
    orch.status = MagicMock(return_value={})
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(
        f"/projects/{fake_project}/pipeline/fast",
        json={"force_from_start": True},
    )
    assert resp.status_code == 409
    assert write_calls == [(fake_project, "rebuild", "sync")]
    assert clear_calls == [fake_project]


def test_pipeline_deep_clears_barrier_when_orchestrator_refuses(
    client, fake_project, monkeypatch
):
    """When force=True but orchestrator returns False, barrier should not linger."""
    from prep.services.pipeline import recovery

    write_calls: list[tuple] = []
    clear_calls: list[str] = []

    def fake_write(pid, reason, scope="all"):
        write_calls.append((pid, reason, scope))
        return True

    def fake_clear(pid):
        clear_calls.append(pid)
        return True

    monkeypatch.setattr(recovery, "write_reset_barrier", fake_write)
    monkeypatch.setattr(recovery, "clear_reset_barrier", fake_clear)

    orch = MagicMock()
    orch.run_deep_enrichment = MagicMock(return_value=False)
    orch.status = MagicMock(return_value={})
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(
        f"/projects/{fake_project}/pipeline/deep",
        json={"force_from_start": True},
    )
    assert resp.status_code == 409
    assert write_calls == [(fake_project, "rebuild", "enrichment")]
    assert clear_calls == [fake_project]
