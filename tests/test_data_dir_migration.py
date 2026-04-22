"""Phase 113 Step 3 — one-time legacy-codrag_data migration.

Pre-fix: the daemon's state was split between ./codrag_data/ (CWD) and
~/.local/share/runprep/ (XDG) with no migration path. Users who moved
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

from prep.core.data_dir_migration import (
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


def test_sqlite_sidecars_move_with_db() -> None:
    """`-wal` / `-shm` sidecars must travel with the `.db` or we lose WAL-only data."""
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()

        (legacy / "codrag_antibodies.db").write_bytes(b"main")
        (legacy / "codrag_antibodies.db-wal").write_bytes(b"uncommitted-pages")
        (legacy / "codrag_antibodies.db-shm").write_bytes(b"shm-index")

        dest = Path(dest_td).resolve()
        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        assert result.ran is True
        assert "codrag_antibodies.db" in result.moved
        assert "codrag_antibodies.db-wal" in result.moved
        assert "codrag_antibodies.db-shm" in result.moved
        assert (dest / "codrag_antibodies.db-wal").read_bytes() == b"uncommitted-pages"
        assert (dest / "codrag_antibodies.db-shm").read_bytes() == b"shm-index"
        assert not (legacy / "codrag_antibodies.db-wal").exists()
        assert not (legacy / "codrag_antibodies.db-shm").exists()


def test_non_sqlite_has_no_sidecar_handling() -> None:
    """`ui_config.json` has no sidecars; nothing odd should happen."""
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()
        (legacy / "ui_config.json").write_text('{"a": 1}')

        dest = Path(dest_td).resolve()
        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        assert result.moved == ["ui_config.json"]  # no phantom sidecar entries


def test_sidecar_conflict_preserved_with_db() -> None:
    """When dest wins a conflict, legacy `-wal`/`-shm` are preserved as -wal/-shm conflict copies."""
    with tempfile.TemporaryDirectory() as cwd_td, tempfile.TemporaryDirectory() as dest_td:
        cwd = Path(cwd_td).resolve()
        legacy = cwd / "codrag_data"
        legacy.mkdir()
        dest = Path(dest_td).resolve()

        # Dest wins (bigger), legacy has a WAL we must preserve.
        (legacy / "codrag_antibodies.db").write_bytes(b"small")
        (legacy / "codrag_antibodies.db-wal").write_bytes(b"legacy-wal-data")
        (dest / "codrag_antibodies.db").write_bytes(b"bigger-winning-file")

        result = migrate_legacy_data_dir(cwd=cwd, data_dir_override=dest)

        # Main-file conflict backup AND wal-suffix conflict backup both exist.
        main_conflicts = list(dest.glob("codrag_antibodies.db.migration-conflict.*"))
        # Exactly one is the main .db backup; any others are sidecar backups.
        plain_main = [p for p in main_conflicts if not p.name.endswith(("-wal", "-shm"))]
        wal_side = [p for p in main_conflicts if p.name.endswith("-wal")]
        assert len(plain_main) == 1
        assert len(wal_side) == 1
        assert wal_side[0].read_bytes() == b"legacy-wal-data"
        # Legacy side is drained.
        assert not (legacy / "codrag_antibodies.db-wal").exists()


# ---------------------------------------------------------------------------
# Task 3B: codrag XDG dir -> prep XDG dir migration (D4)
# ---------------------------------------------------------------------------

def test_migrate_from_legacy_codrag_dir(tmp_path, monkeypatch):
    """First prep-serve run migrates ~/.local/share/codrag to ~/.local/share/sourceprep."""
    fake_home = tmp_path / "home"
    legacy = fake_home / ".local" / "share" / "codrag"
    target = fake_home / ".local" / "share" / "sourceprep"
    legacy.mkdir(parents=True)
    (legacy / "prep_settings.db").write_bytes(b"SQLITE payload")
    (legacy / "projects").mkdir()
    # Patch Path.home() directly for macOS compatibility (HOME env var
    # is not always respected by Path.home() on macOS/Python).
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.delenv("PREP_DATA_DIR", raising=False)

    from prep.core.data_dir_migration import migrate_from_legacy_codrag
    migrated = migrate_from_legacy_codrag()

    assert migrated is True
    assert target.exists()
    assert (target / "prep_settings.db").read_bytes() == b"SQLITE payload"
    assert (target / ".migrated_from_codrag").exists()
    assert not legacy.exists()


def test_migrate_from_legacy_codrag_is_idempotent(tmp_path, monkeypatch):
    """Sentinel file prevents re-migration."""
    fake_home = tmp_path / "home"
    target = fake_home / ".local" / "share" / "sourceprep"
    target.mkdir(parents=True)
    (target / ".migrated_from_codrag").write_text("2026-04-21T00:00:00Z\n")
    legacy = fake_home / ".local" / "share" / "codrag"
    legacy.mkdir(parents=True)
    (legacy / "prep_settings.db").write_bytes(b"should_not_migrate")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.delenv("PREP_DATA_DIR", raising=False)

    from prep.core.data_dir_migration import migrate_from_legacy_codrag
    migrated = migrate_from_legacy_codrag()

    assert migrated is False
    assert legacy.exists()  # untouched
    assert not (target / "prep_settings.db").exists()


def test_migrate_from_legacy_codrag_conflict_preserves_both(tmp_path, monkeypatch):
    """Both dirs non-empty: target wins; legacy saved as conflict suffix."""
    fake_home = tmp_path / "home"
    legacy = fake_home / ".local" / "share" / "codrag"
    target = fake_home / ".local" / "share" / "sourceprep"
    legacy.mkdir(parents=True)
    target.mkdir(parents=True)
    (legacy / "prep_settings.db").write_bytes(b"legacy_data")
    (target / "prep_settings.db").write_bytes(b"newer_data")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.delenv("PREP_DATA_DIR", raising=False)

    from prep.core.data_dir_migration import migrate_from_legacy_codrag
    result = migrate_from_legacy_codrag()

    assert result is True
    assert (target / "prep_settings.db").read_bytes() == b"newer_data"
    conflicts = list(fake_home.glob(".local/share/codrag.migration-conflict.*"))
    assert len(conflicts) == 1
    assert (conflicts[0] / "prep_settings.db").read_bytes() == b"legacy_data"


# ---------------------------------------------------------------------------
# Task 3B: embedded .codrag -> .prep migration (D5)
# ---------------------------------------------------------------------------

def test_migrate_embedded_codrag_dir(tmp_path):
    """Embedded .codrag/ chains all the way to .sourceprep/ via Task 1.4 migration."""
    from prep.core.paths import _migrate_embedded_dir
    project = tmp_path / "myproj"
    (project / ".codrag").mkdir(parents=True)
    (project / ".codrag" / "index.json").write_text("{}")

    _migrate_embedded_dir(project)

    assert (project / ".sourceprep").exists()
    assert (project / ".sourceprep" / "index.json").read_text() == "{}"
    assert not (project / ".codrag").exists()
    assert not (project / ".runprep").exists()


# ---------------------------------------------------------------------------
# Task 1.1: runprep XDG dir -> sourceprep XDG dir migration (SourcePrep rebrand)
# ---------------------------------------------------------------------------


def test_migrate_from_legacy_runprep_moves_xdg_dir(tmp_path, monkeypatch):
    """~/.local/share/runprep/ -> ~/.local/share/sourceprep/ when sentinel absent."""
    from prep.core.data_dir_migration import migrate_from_legacy_runprep

    fake_home = tmp_path / "home"
    legacy = fake_home / ".local" / "share" / "runprep"
    legacy.mkdir(parents=True)
    (legacy / "prep_settings.db").write_text("legacy-db")

    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    # Also override the default XDG target derivation inside migration
    monkeypatch.setenv("PREP_DATA_DIR", str(fake_home / ".local" / "share" / "sourceprep"))

    assert migrate_from_legacy_runprep() is True

    target = fake_home / ".local" / "share" / "sourceprep"
    assert (target / "prep_settings.db").read_text() == "legacy-db"
    assert (target / ".migrated_from_runprep").exists()
    assert not legacy.exists()


def test_migrate_from_legacy_runprep_idempotent(tmp_path, monkeypatch):
    """Second call is a no-op after sentinel is written."""
    from prep.core.data_dir_migration import migrate_from_legacy_runprep

    fake_home = tmp_path / "home"
    target = fake_home / ".local" / "share" / "sourceprep"
    target.mkdir(parents=True)
    (target / ".migrated_from_runprep").touch()

    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("PREP_DATA_DIR", str(target))

    assert migrate_from_legacy_runprep() is False
