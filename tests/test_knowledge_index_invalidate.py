"""KnowledgeIndex.invalidate() clears in-memory state."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from prep.core.knowledge import KnowledgeIndex


@pytest.fixture()
def index(tmp_path: Path) -> KnowledgeIndex:
    embedder = MagicMock()
    embedder.model_name = "test-embedder"
    return KnowledgeIndex(tmp_path, embedder)


def test_invalidate_clears_in_memory_state(index: KnowledgeIndex) -> None:
    index._documents = [{"id": "a"}, {"id": "b"}]
    index._embeddings = np.zeros((2, 4), dtype=np.float32)
    index._manifest = {"count": 2}

    index.invalidate()

    assert index._documents is None
    assert index._embeddings is None
    assert index._manifest == {}
