"""Phase 117: /pipeline/last-rebuild-duration endpoint.

Returns the best-effort duration (in seconds) of the most recent
completed run per rebuild scope:

    sync         → group "fast_sync"
    enrichment   → group "deep_enrichment"
    all          → fast_sync + deep_enrichment + finalize (chained)

Unknown / missing runs yield ``null`` rather than 0.
"""
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
    # Endpoint only reads from history — no project-writable guard here —
    # but keep the pattern consistent with sibling tests.
    return "proj-test"


def _make_entry(group: str, status: str = "completed", elapsed: float | None = 120.0):
    """Build a minimal HistoryEntry-compatible mock."""
    entry = MagicMock()
    entry.group = group
    entry.status = status
    entry.elapsed_seconds = elapsed
    return entry


def test_empty_project_returns_all_null(client, fake_project, monkeypatch):
    """Project with no recorded runs → all scopes null."""
    from prep.services import pipeline_history as ph_mod

    history = MagicMock()
    history.get_latest_run = MagicMock(return_value=None)
    monkeypatch.setattr(ph_mod, "history", history)

    resp = client.get(f"/projects/{fake_project}/pipeline/last-rebuild-duration")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == {"sync": None, "enrichment": None, "all": None}


def test_sync_only_populated_when_fast_sync_completed(client, fake_project, monkeypatch):
    """One completed fast_sync run → sync populated, enrichment null,
    all = fast_sync duration (sum of the one part with data)."""
    from prep.services import pipeline_history as ph_mod

    def _latest(_pid, group=None):
        if group == "fast_sync":
            return _make_entry("fast_sync", "completed", 240.5)
        return None

    history = MagicMock()
    history.get_latest_run.side_effect = _latest
    monkeypatch.setattr(ph_mod, "history", history)

    resp = client.get(f"/projects/{fake_project}/pipeline/last-rebuild-duration")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sync"] == 240.5
    assert data["enrichment"] is None
    # "all" is the sum of whichever groups have data; here only fast_sync
    assert data["all"] == 240.5


def test_all_scopes_sum_all_three_groups(client, fake_project, monkeypatch):
    """All three groups completed → all = sync + enrichment + finalize."""
    from prep.services import pipeline_history as ph_mod

    durations = {"fast_sync": 100.0, "deep_enrichment": 200.0, "finalize": 50.0}

    def _latest(_pid, group=None):
        secs = durations.get(group or "")
        return _make_entry(group, "completed", secs) if secs else None

    history = MagicMock()
    history.get_latest_run.side_effect = _latest
    monkeypatch.setattr(ph_mod, "history", history)

    resp = client.get(f"/projects/{fake_project}/pipeline/last-rebuild-duration")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sync"] == 100.0
    assert data["enrichment"] == 200.0
    assert data["all"] == 350.0


def test_failed_run_excluded(client, fake_project, monkeypatch):
    """Failed run is not eligible — treated as null."""
    from prep.services import pipeline_history as ph_mod

    def _latest(_pid, group=None):
        if group == "fast_sync":
            return _make_entry("fast_sync", status="failed", elapsed=60.0)
        return None

    history = MagicMock()
    history.get_latest_run.side_effect = _latest
    monkeypatch.setattr(ph_mod, "history", history)

    resp = client.get(f"/projects/{fake_project}/pipeline/last-rebuild-duration")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sync"] is None
    assert data["all"] is None


def test_history_not_initialized_returns_nulls(client, fake_project, monkeypatch):
    """RuntimeError from an un-initialized history → graceful null payload."""
    from prep.services import pipeline_history as ph_mod

    history = MagicMock()
    history.get_latest_run.side_effect = RuntimeError("not initialized")
    monkeypatch.setattr(ph_mod, "history", history)

    resp = client.get(f"/projects/{fake_project}/pipeline/last-rebuild-duration")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"sync": None, "enrichment": None, "all": None}
