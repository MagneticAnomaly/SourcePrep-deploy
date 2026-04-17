"""Phase 114 follow-up: checkpoint GC at daemon startup.

Happy-path prune runs after every successful run_completed, but projects
stuck in a crash loop never hit that hook, so .checkpoints/run-* grows
without bound. The startup prune pass establishes a ceiling regardless
of run outcome.
"""
from __future__ import annotations
import time
from pathlib import Path

from codrag.services.pipeline_checkpoint import (
    prune_old_checkpoints,
    prune_checkpoints_all_projects,
)


def _make_checkpoint_dir(cp_root: Path, name: str, mtime_offset: float = 0.0) -> Path:
    d = cp_root / name
    d.mkdir(parents=True, exist_ok=True)
    # Put a sentinel file in so rmtree has something to remove
    (d / "marker").write_text(name)
    if mtime_offset:
        target = time.time() + mtime_offset
        import os
        os.utime(d, (target, target))
    return d


def test_prune_old_checkpoints_respects_keep(tmp_path: Path):
    cp_root = tmp_path / ".checkpoints"
    # 5 runs with ascending mtimes — oldest first
    for i in range(5):
        _make_checkpoint_dir(cp_root, f"run-{i:04x}", mtime_offset=float(i))

    removed = prune_old_checkpoints(tmp_path, keep=3)
    assert removed == 2
    remaining = sorted(p.name for p in cp_root.iterdir())
    # Three newest kept (run-0002, run-0003, run-0004)
    assert remaining == ["run-0002", "run-0003", "run-0004"]


def test_prune_old_checkpoints_never_touches_golden(tmp_path: Path):
    cp_root = tmp_path / ".checkpoints"
    # Golden + 5 run dirs
    golden = _make_checkpoint_dir(cp_root, "_golden", mtime_offset=-1000)
    for i in range(5):
        _make_checkpoint_dir(cp_root, f"run-{i:04x}", mtime_offset=float(i))

    removed = prune_old_checkpoints(tmp_path, keep=3)
    assert removed == 2
    assert golden.exists(), "Golden checkpoint must survive prune"


def test_prune_old_checkpoints_noop_when_under_limit(tmp_path: Path):
    cp_root = tmp_path / ".checkpoints"
    _make_checkpoint_dir(cp_root, "run-0000")
    _make_checkpoint_dir(cp_root, "run-0001")

    removed = prune_old_checkpoints(tmp_path, keep=3)
    assert removed == 0
    assert sorted(p.name for p in cp_root.iterdir()) == ["run-0000", "run-0001"]


def test_prune_old_checkpoints_missing_dir(tmp_path: Path):
    # No .checkpoints dir at all — must not raise
    assert prune_old_checkpoints(tmp_path, keep=3) == 0


def test_prune_checkpoints_all_projects_swallows_registry_failures(
    tmp_path: Path, monkeypatch
):
    """Startup prune must never wedge the daemon if the registry is unhappy."""
    def _boom():
        raise RuntimeError("registry offline")

    class _FakeReg:
        def list_projects(self):
            _boom()

    import codrag.services.pipeline_checkpoint as mod
    monkeypatch.setattr(
        "codrag.services.project_helpers.get_registry",
        lambda: _FakeReg(),
    )

    # Should return an empty dict, not raise
    result = mod.prune_checkpoints_all_projects(keep=3)
    assert result == {}


def test_prune_checkpoints_all_projects_per_project_errors_isolated(
    tmp_path: Path, monkeypatch
):
    """A single bad project must not prevent others from being pruned."""
    # Two project index dirs
    good_idx = tmp_path / "good"
    good_idx.mkdir()
    for i in range(5):
        _make_checkpoint_dir(good_idx / ".checkpoints", f"run-{i:04x}", mtime_offset=float(i))

    bad_idx = tmp_path / "does_not_exist"  # index_dir returns a non-existent path

    class _P:
        def __init__(self, pid, idx):
            self.id = pid
            self._idx = idx

    projects = [_P("p-good", good_idx), _P("p-bad", bad_idx)]

    class _FakeReg:
        def list_projects(self):
            return projects

    monkeypatch.setattr(
        "codrag.services.project_helpers.get_registry",
        lambda: _FakeReg(),
    )
    monkeypatch.setattr(
        "codrag.core.project_registry.project_index_dir",
        lambda p: str(p._idx),
    )

    result = prune_checkpoints_all_projects(keep=3)
    # good project pruned (5 -> 3, so 2 removed), bad project skipped silently
    assert result == {"p-good": 2}
    remaining = sorted(p.name for p in (good_idx / ".checkpoints").iterdir())
    assert remaining == ["run-0002", "run-0003", "run-0004"]
