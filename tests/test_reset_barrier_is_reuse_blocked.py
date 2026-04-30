"""is_reuse_blocked() correctly subsumes scopes."""
from __future__ import annotations

from pathlib import Path

import pytest

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.services.pipeline.recovery import (
    write_reset_barrier, clear_reset_barrier, is_reuse_blocked,
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


def test_no_barrier_reuse_allowed(project_id: str) -> None:
    assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is False
    assert is_reuse_blocked(project_id, stage_group="finalize") is False


def test_enrichment_barrier_blocks_both_groups(project_id: str) -> None:
    write_reset_barrier(project_id, reason="enrichment_reset", scope="enrichment")
    try:
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is True
        assert is_reuse_blocked(project_id, stage_group="finalize") is True
    finally:
        clear_reset_barrier(project_id)


def test_finalize_barrier_blocks_only_finalize(project_id: str) -> None:
    write_reset_barrier(project_id, reason="finalize_reset", scope="finalize")
    try:
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is False
        assert is_reuse_blocked(project_id, stage_group="finalize") is True
    finally:
        clear_reset_barrier(project_id)


def test_all_scope_blocks_everything(project_id: str) -> None:
    write_reset_barrier(project_id, reason="rebuild_all", scope="all")
    try:
        assert is_reuse_blocked(project_id, stage_group="fast_sync") is True
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is True
        assert is_reuse_blocked(project_id, stage_group="finalize") is True
    finally:
        clear_reset_barrier(project_id)


def test_sync_barrier_blocks_only_fast_sync(project_id: str) -> None:
    write_reset_barrier(project_id, reason="sync_rebuild", scope="sync")
    try:
        assert is_reuse_blocked(project_id, stage_group="fast_sync") is True
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is False
        assert is_reuse_blocked(project_id, stage_group="finalize") is False
    finally:
        clear_reset_barrier(project_id)
