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

    fake = _FakeReg(proj)
    monkeypatch.setattr(ph, "_registry", fake)
    monkeypatch.setattr(ph, "get_registry", lambda: fake)
    return proj


@pytest.fixture
def client(project):  # noqa: ARG001  (project installs the fake registry)
    """TestClient against prep.server.app with a fake project registry."""
    from prep.server import app

    return TestClient(app)


@pytest.fixture
def mock_orchestrator(monkeypatch):
    """Replace the scope_orchestrator singleton with a recorder.

    Tests can assert against `.added` and `.removed` lists. Avoids the
    real orchestrator's debounce timing (which has a known flaky test
    on this branch — see docs/Phase120_NamedScopes/PRE_EXISTING_ISSUES.md).
    """

    class M:
        def __init__(self) -> None:
            self.added: list[tuple[str, list[str]]] = []
            self.removed: list[tuple[str, list[str]]] = []

        def on_files_added(self, pid: str, paths: list[str]) -> None:
            self.added.append((pid, list(paths)))

        def on_files_removed(self, pid: str, paths: list[str]) -> None:
            self.removed.append((pid, list(paths)))

        def status(self, pid: str) -> dict:
            return {"state": "idle"}

        def register_build_fn(self, pid: str, fn) -> None:  # noqa: ARG002
            pass

    inst = M()
    from prep.services import scope_orchestrator as so

    monkeypatch.setattr(so, "scope_orchestrator", inst)
    return inst
