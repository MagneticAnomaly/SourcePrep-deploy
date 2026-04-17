"""Phase 113 Step 3 — one-time legacy-codrag_data migration.

Pre-fix: the daemon's state was split between ./codrag_data/ (CWD) and
~/.local/share/codrag/ (XDG) with no migration path. Users who moved
between versions, or who changed the directory they launched from,
silently ended up with fragmented state.

Post-fix: `migrate_legacy_data_dir()` runs once on daemon startup,
moves recognized files, resolves both-non-empty conflicts with an
auditable `.migration-conflict.<ts>` backup, and writes a sentinel so
subsequent runs are no-ops.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from codrag.core.data_dir_migration import (
    _SENTINEL_NAME,
    MigrationResult,
    migrate_legacy_data_dir,
)


def _seed_sqlite(path: Path, rows: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)")
    for i in range(rows):
        conn.execute(
            "INSERT OR REPLACE INTO settings (k, v) VALUES (?, ?)",
            (f"k{i}", f"v{i}"),
        )
    conn.commit()
    conn.close()


def test_noop_when_no_legacy_dir() -> None:
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()  # no codrag_data/ inside
        dest = Path(dest_td).resolve()
        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

    assert result.ran is False
    assert result.moved == []
    assert not (dest / _SENTINEL_NAME).exists()


def test_noop_when_legacy_only_has_unrecognized_files() -> None:
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()
        (legacy / "projects.db").write_bytes(b"\x00" * 100)  # legacy, skipped
        (legacy / "codrag_settings.db.corrupt.bak").write_bytes(b"\x00")

        dest = Path(dest_td).resolve()
        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

    assert result.ran is False
    assert not (dest / _SENTINEL_NAME).exists()


def test_moves_recognized_files_when_dest_empty() -> None:
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()

        (legacy / "codrag_antibodies.db").write_bytes(b"payload-a")
        (legacy / "ui_config.json").write_text('{"ver": 20}')
        _seed_sqlite(legacy / "codrag_settings.db", rows=3)

        dest = Path(dest_td).resolve()
        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        assert result.ran is True
        assert set(result.moved) == {
            "codrag_antibodies.db", "ui_config.json", "codrag_settings.db"
        }
        assert result.conflicts == []

        assert (dest / "codrag_antibodies.db").read_bytes() == b"payload-a"
        assert (dest / "ui_config.json").read_text() == '{"ver": 20}'
        assert (dest / "codrag_settings.db").is_file()

        assert not (legacy / "codrag_antibodies.db").exists()
        assert not (legacy / "ui_config.json").exists()

        sentinel = dest / _SENTINEL_NAME
        assert sentinel.is_file()
        payload = json.loads(sentinel.read_text())
        assert payload["legacy_path"] == str(legacy)
        assert "codrag_antibodies.db" in payload["moved"]


def test_conflict_both_non_empty_larger_wins() -> None:
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()

        dest = Path(dest_td).resolve()

        # Generic non-sqlite store (falls through to size heuristic).
        # Dest has MORE data → dest wins, legacy copied to .migration-conflict.
        (legacy / "codrag_antibodies.db").write_bytes(b"small-legacy")
        (dest / "codrag_antibodies.db").write_bytes(b"bigger-existing-destination-file-wins")

        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        assert result.ran is True
        assert "codrag_antibodies.db" not in result.moved  # dest won, no swap
        assert any(c.startswith("codrag_antibodies.db.migration-conflict.") for c in result.conflicts)

        assert (dest / "codrag_antibodies.db").read_bytes() == b"bigger-existing-destination-file-wins"
        conflict_copies = list(dest.glob("codrag_antibodies.db.migration-conflict.*"))
        assert len(conflict_copies) == 1
        assert conflict_copies[0].read_bytes() == b"small-legacy"


def test_conflict_settings_row_count_tiebreak() -> None:
    """codrag_settings.db uses row-count, not size, for picking winner."""
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()
        dest = Path(dest_td).resolve()

        # Dest file is physically LARGER (padded) but has FEWER rows.
        _seed_sqlite(dest / "codrag_settings.db", rows=1)
        with open(dest / "codrag_settings.db", "ab") as f:
            f.write(b"\x00" * 100_000)  # bloat without adding rows

        _seed_sqlite(legacy / "codrag_settings.db", rows=10)

        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        assert result.ran is True
        assert "codrag_settings.db" in result.moved  # legacy won on row-count
        # Losing dest copy is preserved
        conflict_copies = list(dest.glob("codrag_settings.db.migration-conflict.*"))
        assert len(conflict_copies) == 1

        # Post-migration dest is the 10-row legacy file
        conn = sqlite3.connect(dest / "codrag_settings.db")
        count = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
        conn.close()
        assert count == 10


def test_sentinel_present_means_noop() -> None:
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()
        (legacy / "codrag_antibodies.db").write_bytes(b"would-move")

        dest = Path(dest_td).resolve()
        (dest / _SENTINEL_NAME).write_text("{}")

        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        assert result.ran is False
        assert result.moved == []
        assert (legacy / "codrag_antibodies.db").read_bytes() == b"would-move"


def test_partial_crash_resumes_on_next_run() -> None:
    """If the process dies before sentinel is written, re-running picks up remaining files."""
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()
        (legacy / "codrag_antibodies.db").write_bytes(b"a")
        (legacy / "codrag_concepts.db").write_bytes(b"c")
        dest = Path(dest_td).resolve()

        # Simulate a prior partial run that moved antibodies but didn't write sentinel.
        (dest / "codrag_antibodies.db").write_bytes(b"a")
        (legacy / "codrag_antibodies.db").unlink()

        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        assert result.ran is True
        assert result.moved == ["codrag_concepts.db"]
        assert (dest / "codrag_concepts.db").read_bytes() == b"c"
        assert (dest / _SENTINEL_NAME).exists()


def test_skipped_files_recorded_not_moved() -> None:
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()
        (legacy / "codrag_antibodies.db").write_bytes(b"a")
        (legacy / "projects.db").write_bytes(b"legacy-stale")
        (legacy / "registry.db").write_bytes(b"")
        dest = Path(dest_td).resolve()

        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        assert "projects.db" in result.skipped
        assert "registry.db" in result.skipped
        assert not (dest / "projects.db").exists()
        assert not (dest / "registry.db").exists()
        assert (legacy / "projects.db").exists()


def test_returns_migration_result_on_all_paths() -> None:
    """The function must always return a MigrationResult (never None/raise)."""
    with tempfile.TemporaryDirectory() as dest_td:
        result = migrate_legacy_data_dir(
            cwd=Path("/nonexistent/no-legacy-here-xyz"),
            data_dir_override=Path(dest_td).resolve(),
        )
        assert isinstance(result, MigrationResult)
        assert result.ran is False
