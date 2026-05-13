"""Phase 135 — stage 5 (knowledge, is_deep=False) must keep its
legacy content-hash reuse behavior. Stage 10 overwrites stage 5's
output anyway; rearchitecting stage 5 would add risk for no benefit."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from prep.core.knowledge import KnowledgeIndex


@pytest.fixture
def idx(tmp_path: Path) -> KnowledgeIndex:
    embedder = MagicMock()
    embedder.model = "test-embed"
    embedder.embed.return_value = MagicMock(vector=[0.0] * 8)
    return KnowledgeIndex(index_dir=tmp_path, embedder=embedder, project_id="p1")


def test_default_use_changeset_is_false(idx: KnowledgeIndex) -> None:
    """Stage 5 callers don't touch use_changeset — must default False."""
    assert idx.use_changeset is False


def test_stage5_reuse_map_uses_content_hash(idx: KnowledgeIndex) -> None:
    """With use_changeset=False, reuse_map values must be (hash, vector) tuples."""
    docs = [{"id": "know:aug:file:foo.py", "content": "hello"}]
    idx.docs_path.parent.mkdir(parents=True, exist_ok=True)
    idx.docs_path.write_text(json.dumps(docs))
    np.save(idx.emb_path, np.array([[0.0] * 8], dtype=np.float32))

    assert idx.use_changeset is False
    reuse_map = idx._load_previous_for_reuse()
    val = reuse_map.get("know:aug:file:foo.py")
    assert isinstance(val, tuple)
    assert len(val) == 2
    assert isinstance(val[0], str)  # the content hash
