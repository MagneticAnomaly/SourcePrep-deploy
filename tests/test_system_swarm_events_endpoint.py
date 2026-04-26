"""Tests for ``GET /system/swarm-events`` (Phase 119 verbose-logging API).

The recent-swarm-logs UI panel relies on this endpoint to enumerate the
JSONL files written by ``SwarmEventLogger`` and to read individual logs
on demand.  This module pins the response shapes the UI consumes plus
the path-traversal guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prep.core.swarm_event_logger import SwarmEventLogger
from prep.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def swarm_log_dir(tmp_path_factory, monkeypatch) -> Path:
    """Point ``data_dir()`` at an isolated temp dir for the duration of the test.

    The endpoint resolves the swarm log directory as
    ``data_dir() / "logs" / "swarm"``; the autouse
    ``_isolate_concurrency_store`` conftest fixture already redirects
    ``data_dir`` for this scope, but we mirror that here so this test
    is robust if the autouse fixture is ever scoped down.
    """
    from prep.core import paths as _paths_mod

    dest = tmp_path_factory.mktemp("swarm_events_test_data")
    monkeypatch.setattr(_paths_mod, "data_dir", lambda: dest)
    return dest / "logs" / "swarm"


def _seed(log_dir: Path, run_id: str, stage: str) -> Path:
    log = SwarmEventLogger(
        run_id=run_id,
        stage=stage,
        project_id="proj-test",
        log_dir=log_dir,
    )
    log.phase_start("coordinator", model="m", n_items=1)
    log.worker_dispatch("w-0", "item-0", "m", prompt_chars=10)
    log.worker_complete("w-0", success=True, duration_s=0.5,
                         response_chars=20, parse_ok=True)
    log.phase_end("coordinator", success=True, duration_s=0.5, tokens=10)
    log.session_end(success=True, summary={"total_items": 1})
    assert log.path is not None
    return log.path


def test_list_mode_empty(client: TestClient, swarm_log_dir: Path) -> None:
    """No log dir → ok with empty file list and ``events: None``."""
    resp = client.get("/system/swarm-events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["files"] == []
    assert body["events"] is None
    assert "log_dir" in body


def test_list_mode_returns_files(client: TestClient, swarm_log_dir: Path) -> None:
    """List mode returns ``{name,size,mtime}`` rows newest-first."""
    p1 = _seed(swarm_log_dir, "abcdef000001", "concept_seeding")
    p2 = _seed(swarm_log_dir, "abcdef000002", "group_reasoning")

    resp = client.get("/system/swarm-events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["events"] is None
    names = [f["name"] for f in body["files"]]
    assert p1.name in names
    assert p2.name in names

    for f in body["files"]:
        # Schema the UI consumes.
        assert "name" in f and isinstance(f["name"], str)
        assert "size" in f and isinstance(f["size"], int)
        assert "mtime" in f and isinstance(f["mtime"], (int, float))
        assert f["size"] > 0


def test_read_mode_returns_events(client: TestClient, swarm_log_dir: Path) -> None:
    """``?file=<basename>`` returns parsed JSONL events."""
    p = _seed(swarm_log_dir, "abcdef111111", "audit_swarm")

    resp = client.get(f"/system/swarm-events?file={p.name}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["file"] == p.name
    assert body["events"] is not None
    kinds = [ev["kind"] for ev in body["events"]]
    # session_start (auto on construction), then phases/workers, then session_end.
    assert kinds[0] == "session_start"
    assert kinds[-1] == "session_end"
    assert "phase_start" in kinds
    assert "worker_complete" in kinds
    # Every event has the elapsed_s + ts fields the UI relies on.
    for ev in body["events"]:
        assert "ts" in ev
        assert "elapsed_s" in ev
        assert "kind" in ev


def test_read_mode_path_traversal_rejected(
    client: TestClient, swarm_log_dir: Path
) -> None:
    """Forward-slash paths must be rejected with 4xx, not 500."""
    resp = client.get("/system/swarm-events?file=../../../etc/passwd")
    assert resp.status_code == 400
    body = resp.json()
    # ApiException renders into the standard error envelope.
    assert body.get("ok") is False or "error" in body or "detail" in body


def test_read_mode_backslash_traversal_rejected(
    client: TestClient, swarm_log_dir: Path
) -> None:
    resp = client.get("/system/swarm-events?file=..\\evil.jsonl")
    assert resp.status_code == 400


def test_read_mode_missing_file_returns_404(
    client: TestClient, swarm_log_dir: Path
) -> None:
    """Plain basename for a file that doesn't exist → 404 (not 500)."""
    swarm_log_dir.mkdir(parents=True, exist_ok=True)
    resp = client.get("/system/swarm-events?file=does_not_exist.jsonl")
    assert resp.status_code == 404


def test_filename_layout_for_ui_label(
    client: TestClient, swarm_log_dir: Path
) -> None:
    """The UI label-parser splits on underscores and expects
    ``swarm_<date>_<time>_<stage>_<runid>.jsonl``.  Confirm the file
    SwarmEventLogger writes follows that layout."""
    p = _seed(swarm_log_dir, "deadbeefcafe", "concept_seeding")
    parts = p.stem.split("_")
    assert parts[0] == "swarm"
    # date (YYYYMMDD), time (HHMMSS), stage..., runid
    assert len(parts[1]) == 8 and parts[1].isdigit()
    assert len(parts[2]) == 6 and parts[2].isdigit()
    # Last token is the short run_id (8 hex chars).
    assert parts[-1] == "deadbeef"


def test_list_mode_includes_log_dir_for_copy_button(
    client: TestClient, swarm_log_dir: Path
) -> None:
    """The UI's ``Open`` button copies ``log_dir / name`` to the clipboard;
    pin that the endpoint always exposes a non-empty ``log_dir`` field."""
    resp = client.get("/system/swarm-events")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("log_dir"), str) and body["log_dir"]


def test_list_mode_response_shape(
    client: TestClient, swarm_log_dir: Path
) -> None:
    """Pin the exact top-level keys the UI's TypeScript types expect."""
    _seed(swarm_log_dir, "00000001", "atlas_swarm")
    resp = client.get("/system/swarm-events")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {"ok", "log_dir", "files", "events"}
    assert expected_keys.issubset(set(body.keys()))
    assert body["events"] is None  # list mode never embeds events
    assert isinstance(body["files"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
