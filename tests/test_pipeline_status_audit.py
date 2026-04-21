"""Regression test for /pipeline/status stages.audit completion signal.

The audit stage (core/audit/runner.py) writes:
  - {idx_dir}/audit_manifest.json         (orchestrator top-level manifest)
  - {idx_dir}/audit/findings.json         (raw findings dict: {findings: [...]})
  - {idx_dir}/audit/audit_manifest.json   (runner's own manifest)

A prior revision of pipeline_status() checked for `audit_findings.json`,
a filename no writer produces — so every completed audit read as
exists=False ("Not run") in the dashboard. This test locks the correct
contract: manifest present ⇒ exists=True regardless of finding count.
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
    return TestClient(app)


def _add_embedded_project(client: TestClient, repo_root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(repo_root), "name": "test", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def _idx_dir(client: TestClient, pid: str) -> Path:
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project
    return Path(project_index_dir(require_project(pid)))


def _audit(client: TestClient, pid: str) -> dict:
    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    return res.json()["data"]["stages"]["audit"]


def test_audit_exists_false_when_no_manifest(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    _idx_dir(client, pid)  # ensure idx_dir is materialized
    audit = _audit(client, pid)
    assert audit["exists"] is False
    assert audit["finding_count"] == 0


def test_audit_exists_true_when_manifest_only(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / "audit_manifest.json").write_text("{}")

    audit = _audit(client, pid)
    assert audit["exists"] is True
    assert audit["finding_count"] == 0


def test_audit_finding_count_from_findings_json(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / "audit_manifest.json").write_text("{}")
    (idx_dir / "audit").mkdir()
    (idx_dir / "audit" / "findings.json").write_text(
        '{"findings": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "finding_count": 3}'
    )

    audit = _audit(client, pid)
    assert audit["exists"] is True
    assert audit["finding_count"] == 3


def test_audit_finding_count_falls_back_to_len_when_count_missing(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / "audit_manifest.json").write_text("{}")
    (idx_dir / "audit").mkdir()
    (idx_dir / "audit" / "findings.json").write_text(
        '{"findings": [{"id": "a"}, {"id": "b"}]}'
    )

    audit = _audit(client, pid)
    assert audit["exists"] is True
    assert audit["finding_count"] == 2
