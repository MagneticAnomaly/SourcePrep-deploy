"""Verify the reset barrier accepts the new 'finalize' scope value."""
from __future__ import annotations

from pathlib import Path

import pytest

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.services.pipeline.recovery import (
    write_reset_barrier, read_reset_barrier, clear_reset_barrier,
)


@pytest.fixture()
def project_id(tmp_path: Path) -> str:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    repo = tmp_path / "repo"
    repo.mkdir()
    proj = reg.add_project(name="t", path=str(repo), mode="embedded")
    return proj.id


def test_finalize_scope_accepted(project_id: str) -> None:
    assert write_reset_barrier(project_id, reason="finalize_reset", scope="finalize")
    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["scope"] == "finalize"
    clear_reset_barrier(project_id)


def test_invalid_scope_rejected(project_id: str) -> None:
    with pytest.raises(ValueError, match="invalid barrier scope"):
        write_reset_barrier(project_id, reason="bogus", scope="bogus_scope")
