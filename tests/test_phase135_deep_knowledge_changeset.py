"""Phase 135 — stage 10 (deep_knowledge) consults the Changeset.

Stage 5 (is_deep=False) is unaffected — same code path, but the worker
only sets `use_changeset=True` on the deep call.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from prep.core.knowledge import KnowledgeIndex
from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def idx(tmp_path: Path) -> KnowledgeIndex:
    embedder = MagicMock()
    embedder.model = "test-embed"
    embedder.embed.return_value = MagicMock(vector=[0.0] * 8)
    return KnowledgeIndex(index_dir=tmp_path, embedder=embedder, project_id="p1")


def test_index_inherits_worker(idx: KnowledgeIndex) -> None:
    from prep.services.pipeline.workers.base import Worker
    assert isinstance(idx, Worker)


def test_index_has_changeset_attribute(idx: KnowledgeIndex) -> None:
    assert idx.changeset is None
    assert idx.use_changeset is False  # default = stage 5 behavior


def test_should_process_routes_through_changeset(idx: KnowledgeIndex) -> None:
    idx.changeset = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert idx.should_process("a.py") is True
    assert idx.should_process("d.py") is False


def test_file_path_extraction_from_doc_id() -> None:
    """The helper that maps know:aug:file:foo.py → foo.py and similar."""
    extract = KnowledgeIndex._file_path_for_doc_id
    assert extract("know:aug:file:foo.py") == "foo.py"
    assert extract("know:epistemic:file:bar/baz.py") == "bar/baz.py"
    # Module docs are not file-backed
    assert extract("know:module:my_module") == ""
    # Defensive: unrecognized prefix
    assert extract("garbage") == ""


def test_deep_path_reuse_map_omits_content_hash(idx: KnowledgeIndex) -> None:
    """When use_changeset=True, _load_previous_for_reuse returns
    {doc_id: vector} (a plain np.ndarray value, not a (hash, vec) tuple)."""
    docs = [{"id": "know:aug:file:foo.py", "content": "x"}]
    idx.docs_path.parent.mkdir(parents=True, exist_ok=True)
    idx.docs_path.write_text(json.dumps(docs))
    np.save(idx.emb_path, np.array([[0.0] * 8], dtype=np.float32))

    idx.use_changeset = True
    reuse_map = idx._load_previous_for_reuse()
    val = reuse_map["know:aug:file:foo.py"]
    # Plain ndarray value — not a 2-tuple of (content_hash, ndarray)
    assert isinstance(val, np.ndarray)


def test_stage5_reuse_map_keeps_content_hash(idx: KnowledgeIndex) -> None:
    """When use_changeset=False (default = stage 5), reuse_map values
    are (hash, vector) tuples — legacy path is preserved."""
    docs = [{"id": "know:aug:file:foo.py", "content": "hello"}]
    idx.docs_path.parent.mkdir(parents=True, exist_ok=True)
    idx.docs_path.write_text(json.dumps(docs))
    np.save(idx.emb_path, np.array([[0.0] * 8], dtype=np.float32))

    assert idx.use_changeset is False
    reuse_map = idx._load_previous_for_reuse()
    val = reuse_map["know:aug:file:foo.py"]
    assert isinstance(val, tuple)
    assert len(val) == 2
    assert isinstance(val[0], str)  # content hash


def test_cached_instance_use_changeset_resets_for_stage5(tmp_path: Path) -> None:
    """Regression: build_manager caches KnowledgeIndex per project. After
    stage 10 sets use_changeset=True on the cached instance, the next
    run's stage 5 must reset it back to False — otherwise stage 5
    silently switches to changeset mode with a stale changeset.

    Invokes _knowledge_worker twice on the SAME cached idx (is_deep=True
    then is_deep=False) and verifies the flag toggles correctly.
    """
    from unittest.mock import patch
    from prep.services.pipeline.workers.factory import WorkerFactory

    # One cached KnowledgeIndex instance, used by both calls.
    embedder = MagicMock()
    embedder.model = "test-embed"
    cached_idx = KnowledgeIndex(index_dir=tmp_path, embedder=embedder, project_id="p1")
    cached_idx.build = MagicMock(return_value={"count": 0, "status": "empty"})

    fake_proj = MagicMock()
    fake_proj.id = "p1"
    fake_proj.name = "p"
    fake_proj.config = {}
    fake_proj.path = str(tmp_path)

    cs1 = Changeset(
        added=frozenset(), modified=frozenset({"b.py"}),
        deleted=frozenset(), unchanged=frozenset({"a.py"}),
        run_id="r1", base_run_id=None,
    )

    common_patches = [
        patch(
            "prep.services.pipeline.workers.WorkerFactory._get_project_and_config",
            return_value=(fake_proj, {}, [], [], 0, 0, 0, 0, 0),
        ),
        patch(
            "prep.services.build_manager.build_manager.get_project_knowledge_index",
            return_value=cached_idx,
        ),
    ]

    # Call 1: stage 10. Worker should set use_changeset=True.
    for p in common_patches:
        p.start()
    try:
        worker_fn = WorkerFactory._knowledge_worker("p1", is_deep=True)
        worker_fn.changeset = cs1  # simulate _build_worker injection
        worker_fn(MagicMock(cancel_token=None), lambda *a, **kw: None)
        assert cached_idx.use_changeset is True
        assert cached_idx.changeset is cs1
    finally:
        patch.stopall()

    # Call 2: stage 5 on the SAME cached instance. Worker MUST reset.
    for p in common_patches:
        p.start()
    try:
        worker_fn = WorkerFactory._knowledge_worker("p1", is_deep=False)
        worker_fn.changeset = cs1  # injection still happens, but should be ignored
        worker_fn(MagicMock(cancel_token=None), lambda *a, **kw: None)
        assert cached_idx.use_changeset is False, "stage 5 inherited stale flag from prior stage 10"
        assert cached_idx.changeset is None, "stage 5 inherited stale changeset"
    finally:
        patch.stopall()
