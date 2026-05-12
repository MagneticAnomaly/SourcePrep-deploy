"""Phase 135 — stage 8 (clustering) consults the Changeset.

A cluster is stale iff any member file is in changeset.modified | deleted.
No fingerprint computation. _cluster_fingerprint method is gone.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.core.cluster import ClusterSynthesizer
from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def synth(tmp_path: Path) -> ClusterSynthesizer:
    llm = MagicMock()
    llm.model = "test-model"
    llm.provider = "test"
    return ClusterSynthesizer(
        llm=llm,
        index_dir=tmp_path,
        batch_profile=None,
        project_id="p1",
    )


def test_synthesizer_inherits_worker(synth: ClusterSynthesizer) -> None:
    from prep.services.pipeline.workers.base import Worker
    assert isinstance(synth, Worker)


def test_synthesizer_has_changeset_attribute(synth: ClusterSynthesizer) -> None:
    assert synth.changeset is None


def test_should_process_routes_through_changeset(synth: ClusterSynthesizer) -> None:
    synth.changeset = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert synth.should_process("a.py") is True
    assert synth.should_process("b.py") is True
    assert synth.should_process("c.py") is False
    assert synth.should_process("d.py") is False


def test_cluster_fingerprint_method_deleted() -> None:
    """ClusterSynthesizer._cluster_fingerprint is gone."""
    assert not hasattr(ClusterSynthesizer, "_cluster_fingerprint")


def test_cluster_is_stale_uses_changeset(synth: ClusterSynthesizer) -> None:
    synth.changeset = Changeset(
        added=frozenset(),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py", "e.py"}),
        run_id="r1",
        base_run_id=None,
    )
    # All unchanged → not stale
    assert synth._cluster_is_stale(["file:d.py", "file:e.py"]) is False
    # Any modified → stale
    assert synth._cluster_is_stale(["file:d.py", "file:b.py"]) is True
    # Any deleted → stale
    assert synth._cluster_is_stale(["file:e.py", "file:c.py"]) is True


def test_cluster_is_stale_none_changeset_returns_true(synth: ClusterSynthesizer) -> None:
    """Defensive: no changeset → conservative 'all stale'."""
    synth.changeset = None
    assert synth._cluster_is_stale(["file:foo.py"]) is True
