"""Phase 135 — stage 7 (group_reasoning) consults the Changeset.

A group is stale iff any member file is in changeset.modified | deleted.
No fingerprint computation. No member_fingerprint field on entries.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.core.group_reasoning import GroupReasoningEngine, GroupReasoningEntry
from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def engine(tmp_path: Path) -> GroupReasoningEngine:
    llm = MagicMock()
    llm.model = "test-model"
    llm.provider = "test"
    return GroupReasoningEngine(llm=llm, index_dir=tmp_path, project_id="p1")


def test_engine_inherits_worker(engine: GroupReasoningEngine) -> None:
    from prep.services.pipeline.workers.base import Worker
    assert isinstance(engine, Worker)


def test_engine_has_changeset_attribute(engine: GroupReasoningEngine) -> None:
    # Worker base class default
    assert engine.changeset is None


def test_should_process_routes_through_changeset(engine: GroupReasoningEngine) -> None:
    engine.changeset = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert engine.should_process("a.py") is True
    assert engine.should_process("b.py") is True
    assert engine.should_process("c.py") is False  # deleted
    assert engine.should_process("d.py") is False  # unchanged


def test_member_fingerprint_field_removed() -> None:
    """GroupReasoningEntry no longer carries member_fingerprint."""
    fields = {f for f in GroupReasoningEntry.__dataclass_fields__}
    assert "member_fingerprint" not in fields


def test_compute_group_fingerprint_deleted() -> None:
    """The fingerprint helper is gone."""
    import prep.core.group_reasoning as gr_mod
    assert not hasattr(gr_mod, "compute_group_fingerprint")


def test_group_is_stale_uses_changeset(engine: GroupReasoningEngine) -> None:
    """A group is stale iff any member file is in modified|deleted."""
    engine.changeset = Changeset(
        added=frozenset(),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py", "e.py"}),
        run_id="r1",
        base_run_id=None,
    )
    # All unchanged → not stale
    assert engine._group_is_stale(["file:d.py", "file:e.py"]) is False
    # Any modified → stale
    assert engine._group_is_stale(["file:d.py", "file:b.py"]) is True
    # Any deleted → stale
    assert engine._group_is_stale(["file:e.py", "file:c.py"]) is True


def test_group_is_stale_none_changeset_returns_true(engine: GroupReasoningEngine) -> None:
    """Defensive: no changeset → conservative 'all stale'."""
    engine.changeset = None
    assert engine._group_is_stale(["file:foo.py"]) is True
