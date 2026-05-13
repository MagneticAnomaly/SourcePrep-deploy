"""Phase 135.5 — stage 2 (inferred_edges) consults the Changeset.

The InferredEdgesAnalyzer is a Worker subclass; staleness routes through
self.should_process. The legacy trace_inferred_hashes.json manifest is gone.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.core.inferred_edges import InferredEdgesAnalyzer
from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def analyzer(tmp_path: Path) -> InferredEdgesAnalyzer:
    repo = tmp_path / "repo"
    repo.mkdir()
    idx = tmp_path / "idx"
    idx.mkdir()
    llm = MagicMock()
    llm.model = "test-model"
    llm.provider = "test"
    return InferredEdgesAnalyzer(
        index_dir=idx, repo_root=repo, llm_client=llm, batch_profile=None,
    )


def test_analyzer_inherits_worker(analyzer: InferredEdgesAnalyzer) -> None:
    from prep.services.pipeline.workers.base import Worker
    assert isinstance(analyzer, Worker)


def test_analyzer_has_changeset_attribute(analyzer: InferredEdgesAnalyzer) -> None:
    assert analyzer.changeset is None


def test_should_process_routes_through_changeset(analyzer: InferredEdgesAnalyzer) -> None:
    analyzer.changeset = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert analyzer.should_process("a.py") is True
    assert analyzer.should_process("b.py") is True
    assert analyzer.should_process("c.py") is False  # deleted
    assert analyzer.should_process("d.py") is False  # unchanged


def test_manifest_path_attribute_removed(analyzer: InferredEdgesAnalyzer) -> None:
    """The trace_inferred_hashes.json manifest is gone in Phase 135.5."""
    assert not hasattr(analyzer, "manifest_path")


def test_load_save_manifest_helpers_removed() -> None:
    """The legacy hash-manifest helpers are gone."""
    assert not hasattr(InferredEdgesAnalyzer, "_load_manifest")
    assert not hasattr(InferredEdgesAnalyzer, "_save_manifest")
    assert not hasattr(InferredEdgesAnalyzer, "_migrate_old_manifest")
