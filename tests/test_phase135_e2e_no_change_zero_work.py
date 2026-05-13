"""Phase 135 — E2E: on a rebuild where stage 1 emits an all-unchanged
changeset, stages 7/8/10 reuse 100% and call the LLM zero times.

This is the goal of the entire phase: 'nothing becomes stale mid-process,
so just run the pipeline.'"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def all_unchanged_changeset() -> Changeset:
    return Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset({"foo.py", "bar.py"}),
        run_id="r2",
        base_run_id="r1",
    )


def test_group_reasoning_zero_work_on_no_change(
    all_unchanged_changeset: Changeset, tmp_path: Path
) -> None:
    """All-unchanged changeset → every group reused → zero LLM calls
    needed via the staleness gate (`_group_is_stale` returns False)."""
    from prep.core.group_reasoning import GroupReasoningEngine

    llm = MagicMock()
    llm.model = "test"
    llm.provider = "test"

    engine = GroupReasoningEngine(llm=llm, index_dir=tmp_path, project_id="p1")
    engine.changeset = all_unchanged_changeset

    members = ["file:foo.py", "file:bar.py"]
    assert engine._group_is_stale(members) is False


def test_cluster_zero_work_on_no_change(
    all_unchanged_changeset: Changeset, tmp_path: Path
) -> None:
    """All-unchanged changeset → every cluster reused → zero LLM calls."""
    from prep.core.cluster import ClusterSynthesizer

    llm = MagicMock()
    llm.model = "test"
    llm.provider = "test"

    synth = ClusterSynthesizer(
        llm=llm, index_dir=tmp_path, batch_profile=None, project_id="p1",
    )
    synth.changeset = all_unchanged_changeset

    assert synth._cluster_is_stale(["file:foo.py", "file:bar.py"]) is False


def test_deep_knowledge_zero_work_on_no_change(
    all_unchanged_changeset: Changeset, tmp_path: Path
) -> None:
    """All-unchanged changeset → every doc reused, no embedder calls.

    Stages the on-disk state, sets use_changeset=True, and confirms
    embedder.embed is never called during build()."""
    import json
    import numpy as np
    from prep.core.knowledge import KnowledgeIndex

    embedder = MagicMock()
    embedder.model = "test-embed"
    embedder.embed.return_value = MagicMock(vector=[0.0] * 8)

    idx = KnowledgeIndex(index_dir=tmp_path, embedder=embedder, project_id="p1")
    docs = [
        {"id": "know:aug:file:foo.py", "type": "catalogue", "source_id": "file:foo.py",
         "content": "summary of foo", "metadata": {}},
        {"id": "know:aug:file:bar.py", "type": "catalogue", "source_id": "file:bar.py",
         "content": "summary of bar", "metadata": {}},
    ]
    idx.docs_path.write_text(json.dumps(docs))
    np.save(idx.emb_path, np.zeros((2, 8), dtype=np.float32))
    idx._load()  # reload from disk

    idx.use_changeset = True
    idx.changeset = all_unchanged_changeset

    # Place a trace_augmented.jsonl so build() finds inputs:
    aug_path = tmp_path / "trace_augmented.jsonl"
    aug_path.write_text(
        json.dumps({"node_id": "file:foo.py", "role": "code", "summary": "summary of foo"}) + "\n" +
        json.dumps({"node_id": "file:bar.py", "role": "code", "summary": "summary of bar"}) + "\n"
    )

    with patch.object(idx, "_embedder_model", return_value="test-embed"):
        result = idx.build(progress_callback=None)

    embedder.embed.assert_not_called()
    assert result.get("count", 0) == 2
