from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def project(tmp_path, tmp_settings, monkeypatch):
    """A minimal in-memory Project for API tests."""
    from prep.core.project_registry import Project

    proj = Project(
        id="proj-test",
        name="Test",
        path=str(tmp_path),
        mode="standalone",
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
        config={"included_paths": []},
    )

    from prep.services import project_helpers as ph

    class _FakeReg:
        def __init__(self, p):
            self._proj = p

        def get_project(self, pid: str):
            return self._proj if pid == self._proj.id else None

        def list_projects(self):
            return [self._proj]

        def mutate_config(self, project_id: str, fn):
            if project_id != self._proj.id:
                return self._proj
            new_cfg = fn(self._proj.config or {}) or {}
            object.__setattr__(self._proj, "config", new_cfg)
            return self._proj

    monkeypatch.setattr(ph, "_registry", _FakeReg(proj))
    return proj


@pytest.fixture
def client(project):  # noqa: ARG001  (project installs the fake registry)
    """TestClient against prep.server.app with a fake project registry."""
    from prep.server import app

    return TestClient(app)
