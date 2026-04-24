"""Tests for the Phase 117 reset-barrier scope extension."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from prep.services.pipeline.recovery import (
    _RESET_BARRIER_FILENAME,
    clear_reset_barrier,
    read_reset_barrier,
    write_reset_barrier,
)


@pytest.fixture
def project_with_idx(tmp_path, monkeypatch):
    """Patch _resolve_idx_dir so recovery helpers write to tmp_path."""
    from prep.services.pipeline import recovery

    monkeypatch.setattr(recovery, "_resolve_idx_dir", lambda _pid: tmp_path)
    return "proj-test", tmp_path


def test_write_barrier_default_scope_is_all(project_with_idx):
    project_id, idx_dir = project_with_idx
    assert write_reset_barrier(project_id, reason="rebuild") is True

    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["reason"] == "rebuild"
    assert info["scope"] == "all"


def test_write_barrier_sync_scope_roundtrips(project_with_idx):
    project_id, _ = project_with_idx
    assert write_reset_barrier(project_id, reason="rebuild", scope="sync") is True

    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["scope"] == "sync"


def test_write_barrier_enrichment_scope_roundtrips(project_with_idx):
    project_id, _ = project_with_idx
    assert write_reset_barrier(project_id, reason="rebuild", scope="enrichment") is True

    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["scope"] == "enrichment"


def test_read_legacy_two_line_barrier_defaults_scope_all(project_with_idx):
    """A barrier written by pre-phase-117 code (no scope line) reads as scope=all."""
    project_id, idx_dir = project_with_idx
    (idx_dir / _RESET_BARRIER_FILENAME).write_text("1776000000.0\nrebuild\n")

    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["reason"] == "rebuild"
    assert info["scope"] == "all"


def test_invalid_scope_rejected(project_with_idx):
    project_id, _ = project_with_idx
    with pytest.raises(ValueError):
        write_reset_barrier(project_id, reason="rebuild", scope="bogus")


def test_clear_barrier(project_with_idx):
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="sync")
    assert clear_reset_barrier(project_id) is True

    info = read_reset_barrier(project_id)
    assert info is None
