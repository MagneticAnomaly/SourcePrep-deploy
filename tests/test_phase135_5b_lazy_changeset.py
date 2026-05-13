"""Phase 135.5b — engines lazy-load changeset from disk when not
explicitly injected. Fixes the regression where API endpoints,
headless_runner, and post-flight actions hit the defensive `all stale`
fallback because they don't go through WorkerFactory."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.services.pipeline.changeset import Changeset, write_changeset
from prep.services.pipeline.workers.base import Worker


@pytest.fixture
def cs_on_disk(tmp_path: Path) -> Changeset:
    """Pre-seed a changeset.json in tmp_path."""
    cs = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"c.py"}),
        run_id="r1",
        base_run_id=None,
    )
    write_changeset(tmp_path, cs)
    return cs


def test_worker_resolves_changeset_from_disk_when_not_injected(tmp_path: Path, cs_on_disk: Changeset) -> None:
    """A Worker with an index_dir but no explicit injection should
    lazy-load the changeset from disk."""
    class _TestWorker(Worker):
        def __init__(self, index_dir: Path):
            self.index_dir = index_dir

    w = _TestWorker(tmp_path)
    assert w.changeset is None  # no explicit injection
    resolved = w._resolve_changeset()
    assert resolved is not None
    assert resolved.run_id == "r1"
    # Caches: now self.changeset is set
    assert w.changeset is resolved


def test_worker_resolve_returns_none_when_no_index_dir() -> None:
    """Worker without index_dir → cannot lazy-load → returns None."""
    class _TestWorker(Worker):
        pass

    w = _TestWorker()
    assert w._resolve_changeset() is None


def test_worker_resolve_prefers_explicit_injection(tmp_path: Path, cs_on_disk: Changeset) -> None:
    """Explicit injection wins over on-disk."""
    class _TestWorker(Worker):
        def __init__(self, index_dir: Path):
            self.index_dir = index_dir

    other_cs = Changeset(
        added=frozenset({"z.py"}),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="DIFFERENT",
        base_run_id=None,
    )
    w = _TestWorker(tmp_path)
    w.changeset = other_cs
    resolved = w._resolve_changeset()
    assert resolved is other_cs
    assert resolved.run_id == "DIFFERENT"


def test_should_process_lazy_loads(tmp_path: Path, cs_on_disk: Changeset) -> None:
    """should_process picks up on-disk changeset without explicit injection."""
    class _TestWorker(Worker):
        def __init__(self, index_dir: Path):
            self.index_dir = index_dir

    w = _TestWorker(tmp_path)
    assert w.should_process("a.py") is True   # added
    assert w.should_process("b.py") is True   # modified
    assert w.should_process("c.py") is False  # unchanged


def test_atlas_is_stale_lazy_loads(tmp_path: Path, cs_on_disk: Changeset) -> None:
    """CodebaseAtlas.is_stale lazy-loads — fixes /pipeline/status regression."""
    from prep.core.atlas.generator import CodebaseAtlas

    # Pre-seed an on-disk atlas so exists()=True
    atlas = CodebaseAtlas(tmp_path)
    atlas.atlas_path.write_text('{"content": "stub"}')

    # All-unchanged changeset on disk (override cs_on_disk's modified)
    cs = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset({"foo.py"}),
        run_id="r2",
        base_run_id="r1",
    )
    write_changeset(tmp_path, cs)

    # No explicit injection — lazy-load should kick in
    assert atlas.changeset is None
    assert atlas.is_stale() is False, (
        "atlas.is_stale() should lazy-load the on-disk changeset and "
        "report False (no churn). Pre-Phase-135.5b this returned True "
        "because the API endpoint never injects the changeset."
    )


def test_atlas_is_stale_no_changeset_on_disk_is_defensive(tmp_path: Path) -> None:
    """No changeset on disk anywhere → defensive return True."""
    from prep.core.atlas.generator import CodebaseAtlas
    atlas = CodebaseAtlas(tmp_path)
    atlas.atlas_path.write_text('{"content": "stub"}')
    # No changeset.json written
    assert atlas.is_stale() is True


def test_group_reasoning_is_stale_lazy_loads(tmp_path: Path, cs_on_disk: Changeset) -> None:
    """GroupReasoningEngine._group_is_stale lazy-loads."""
    from prep.core.group_reasoning import GroupReasoningEngine

    llm = MagicMock()
    llm.model = "test"
    llm.provider = "test"
    engine = GroupReasoningEngine(llm=llm, index_dir=tmp_path, project_id="p1")
    # No explicit injection
    assert engine.changeset is None
    # cs_on_disk has b.py in modified; group with member file:b.py is stale
    assert engine._group_is_stale(["file:b.py"]) is True
    # c.py is unchanged
    assert engine._group_is_stale(["file:c.py"]) is False


def test_cluster_is_stale_lazy_loads(tmp_path: Path, cs_on_disk: Changeset) -> None:
    """ClusterSynthesizer._cluster_is_stale lazy-loads."""
    from prep.core.cluster import ClusterSynthesizer

    llm = MagicMock()
    llm.model = "test"
    llm.provider = "test"
    synth = ClusterSynthesizer(
        llm=llm, index_dir=tmp_path, batch_profile=None, project_id="p1",
    )
    assert synth.changeset is None
    assert synth._cluster_is_stale(["file:b.py"]) is True
    assert synth._cluster_is_stale(["file:c.py"]) is False
