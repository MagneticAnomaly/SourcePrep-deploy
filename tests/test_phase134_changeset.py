"""Phase 134 — Changeset dataclass and persistence."""
from __future__ import annotations

import json
from pathlib import Path

from prep.services.pipeline.changeset import (
    Changeset,
    read_changeset,
    write_changeset,
)


def test_changeset_should_process_added():
    cs = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset({"b.py"}),
        run_id="run-1",
        base_run_id=None,
    )
    assert cs.should_process("a.py") is True


def test_changeset_should_process_modified():
    cs = Changeset(
        added=frozenset(),
        modified=frozenset({"b.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"a.py"}),
        run_id="run-1",
        base_run_id="run-0",
    )
    assert cs.should_process("b.py") is True


def test_changeset_should_not_process_unchanged():
    cs = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset({"a.py"}),
        run_id="run-1",
        base_run_id="run-0",
    )
    assert cs.should_process("a.py") is False


def test_changeset_should_not_process_deleted():
    cs = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset({"old.py"}),
        unchanged=frozenset(),
        run_id="run-1",
        base_run_id="run-0",
    )
    assert cs.should_process("old.py") is False


def test_changeset_should_not_process_unknown():
    cs = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="run-1",
        base_run_id=None,
    )
    assert cs.should_process("never-seen.py") is False


def test_changeset_all_known_excludes_deleted():
    cs = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset({"gone.py"}),
        unchanged=frozenset({"same.py"}),
        run_id="run-1",
        base_run_id="run-0",
    )
    assert cs.all_known() == frozenset({"new.py", "changed.py", "same.py"})
    assert "gone.py" not in cs.all_known()


def test_write_and_read_round_trip(tmp_path: Path):
    idx = tmp_path / "index"
    idx.mkdir()
    cs = Changeset(
        added=frozenset({"a.py", "b.py"}),
        modified=frozenset({"c.py"}),
        deleted=frozenset({"old.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="run-abc123",
        base_run_id="run-def456",
    )
    write_changeset(idx, cs)
    loaded = read_changeset(idx)
    assert loaded == cs


def test_read_changeset_returns_none_when_absent(tmp_path: Path):
    idx = tmp_path / "index"
    idx.mkdir()
    assert read_changeset(idx) is None


def test_read_changeset_returns_none_when_malformed(tmp_path: Path):
    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "changeset.json").write_text("not valid json{{{")
    assert read_changeset(idx) is None


def test_write_changeset_atomic_via_tempfile(tmp_path: Path):
    """Atomic write: a crash mid-write must leave the prior changeset intact."""
    idx = tmp_path / "index"
    idx.mkdir()
    cs1 = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="run-1",
        base_run_id=None,
    )
    write_changeset(idx, cs1)
    cs2 = Changeset(
        added=frozenset(),
        modified=frozenset({"a.py"}),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="run-2",
        base_run_id="run-1",
    )
    write_changeset(idx, cs2)
    loaded = read_changeset(idx)
    assert loaded.run_id == "run-2"


def test_serialized_format_uses_sorted_lists(tmp_path: Path):
    """Sets serialize to sorted lists for deterministic JSON output
    (helps with diffing changeset.json across runs in test fixtures
    and in debugging)."""
    idx = tmp_path / "index"
    idx.mkdir()
    cs = Changeset(
        added=frozenset({"z.py", "a.py", "m.py"}),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="run-1",
        base_run_id=None,
    )
    write_changeset(idx, cs)
    raw = json.loads((idx / "changeset.json").read_text())
    assert raw["added"] == ["a.py", "m.py", "z.py"]
