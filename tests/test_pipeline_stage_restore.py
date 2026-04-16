from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry
from codrag.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    return TestClient(app)


def _add_embedded(client: TestClient, repo: Path) -> str:
    res = client.post("/projects", json={"path": str(repo), "name": "t", "mode": "embedded"})
    return str(res.json()["data"]["project"]["id"])


def _seed_golden(idx_dir: Path, stage_manifest: str, content: str):
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    (golden / stage_manifest).write_text(content)


def test_restore_golden_replaces_active_manifest(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project
    idx_dir = project_index_dir(require_project(pid))

    # Active manifest = stub; golden = good
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / "atlas_manifest.json").write_text('{"status":"stub","provenance":"selfheal_stub"}')
    _seed_golden(idx_dir, "atlas_manifest.json", '{"status":"complete","provenance":"run"}')

    res = client.post(
        f"/projects/{pid}/pipeline/stages/atlas/restore",
        json={"snapshot_id": "golden"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["data"]["restored"] is True
    assert body["data"]["stage_id"] == "atlas"
    assert body["data"]["snapshot_id"] == "golden"
    assert "atlas_manifest.json" in body["data"]["files_restored"]

    # Active manifest should now match golden
    assert '"status":"complete"' in (idx_dir / "atlas_manifest.json").read_text()


def test_restore_rejects_unknown_stage(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.post(
        f"/projects/{pid}/pipeline/stages/not-a-stage/restore",
        json={"snapshot_id": "golden"},
    )
    assert res.status_code == 404


def test_restore_rejects_missing_snapshot(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.post(
        f"/projects/{pid}/pipeline/stages/atlas/restore",
        json={"snapshot_id": "golden"},
    )
    assert res.status_code == 404
    assert "snapshot" in res.json()["error"]["message"].lower()


def test_restore_copies_output_jsonl_for_stage_with_output(client, tmp_path):
    """Stages with a non-None STAGE_OUTPUT_FILE must restore both files."""
    pid = _add_embedded(client, tmp_path)
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project
    idx_dir = project_index_dir(require_project(pid))
    idx_dir.mkdir(parents=True, exist_ok=True)

    # structural → manifest=trace_manifest.json, output=trace_nodes.jsonl
    (idx_dir / "trace_manifest.json").write_text('{"status":"stub"}')
    (idx_dir / "trace_nodes.jsonl").write_text('{"id":"stub"}\n')
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    (golden / "trace_manifest.json").write_text('{"status":"complete"}')
    (golden / "trace_nodes.jsonl").write_text('{"id":"good-1"}\n{"id":"good-2"}\n')

    res = client.post(
        f"/projects/{pid}/pipeline/stages/structural/restore",
        json={"snapshot_id": "golden"},
    )
    assert res.status_code == 200, res.text
    files_restored = res.json()["data"]["files_restored"]
    assert "trace_manifest.json" in files_restored
    assert "trace_nodes.jsonl" in files_restored
    assert '"status":"complete"' in (idx_dir / "trace_manifest.json").read_text()
    assert "good-1" in (idx_dir / "trace_nodes.jsonl").read_text()


def test_restore_does_not_touch_other_stages(client, tmp_path):
    """Restoring atlas must NOT modify validation's manifest."""
    pid = _add_embedded(client, tmp_path)
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project
    idx_dir = project_index_dir(require_project(pid))
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Active state: both stages have a sentinel
    (idx_dir / "atlas_manifest.json").write_text('{"stage":"atlas","v":"active"}')
    (idx_dir / "validation_manifest.json").write_text('{"stage":"validation","v":"active"}')

    # Golden has BOTH but with different content — restore should only pull atlas
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    (golden / "atlas_manifest.json").write_text('{"stage":"atlas","v":"golden"}')
    (golden / "validation_manifest.json").write_text('{"stage":"validation","v":"golden"}')

    res = client.post(
        f"/projects/{pid}/pipeline/stages/atlas/restore",
        json={"snapshot_id": "golden"},
    )
    assert res.status_code == 200, res.text

    # Atlas overwritten, validation untouched
    assert '"v":"golden"' in (idx_dir / "atlas_manifest.json").read_text()
    assert '"v":"active"' in (idx_dir / "validation_manifest.json").read_text()


def test_restore_rejects_path_traversal_in_snapshot_id(client, tmp_path):
    """snapshot_id with '..' must be blocked even if a directory exists at the resolved path."""
    pid = _add_embedded(client, tmp_path)
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project
    idx_dir = project_index_dir(require_project(pid))
    idx_dir.mkdir(parents=True, exist_ok=True)
    # Seed a real golden so the traversal target physically exists
    (idx_dir / ".checkpoints" / "_golden").mkdir(parents=True, exist_ok=True)
    (idx_dir / ".checkpoints" / "_golden" / "atlas_manifest.json").write_text('{}')

    # ".branch_snapshots/../.checkpoints/_golden" resolves to a real dir
    res = client.post(
        f"/projects/{pid}/pipeline/stages/atlas/restore",
        json={"snapshot_id": "../.checkpoints/_golden"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PATH"
