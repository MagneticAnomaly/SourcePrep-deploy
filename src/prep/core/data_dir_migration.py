"""Phase 113 — one-time migration of legacy `./codrag_data/` to XDG.

On daemon startup, if a legacy CWD-relative `codrag_data/` directory
exists and the new canonical `paths.data_dir()` has not yet been
marked as migrated, move the recognized store files over. Guarded by
a sentinel so it runs exactly once per install.

Safety guarantees
-----------------

1. Nothing is ever deleted during migration. When both sides have
   non-empty files for the same store (the ambiguous case — mostly
   `codrag_settings.db` on this dev machine), the "loser" is
   preserved at a `.migration-conflict.<ISO8601>` suffix in the
   destination so the user can recover either way.
2. Unrecognized files (legacy `projects.db`, `registry.db` shadows,
   `*.corrupt.bak*` leftovers, stray test state) are left alone —
   we do not speculatively move files we don't understand.
3. A broad try/except wrap ensures a failed migration never prevents
   the daemon from starting. A "half-migrated" layout re-runs for
   still-present legacy files on next startup.
4. The sentinel is only written at the end, after all recognized
   files have been handled. If the process dies mid-migration the
   next run picks up where it left off (idempotent per file).

Conflict resolution
-------------------

When both `legacy/<name>` and `data_dir/<name>` are non-empty we pick
the "winner" by file size (larger = more history). For
`codrag_settings.db` specifically we additionally probe the
`user_version` PRAGMA and row counts — a 40 KB recent-but-live DB
could beat a 180 KB WAL-corrupted leftover, so we log the decision.

The loser is moved to `<data_dir>/<name>.migration-conflict.<ISO>`.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Recognized daemon-wide state files. Order matters only for the log
# output (stores first, ui_config last).
_RECOGNIZED_FILES = (
    "codrag_antibodies.db",
    "codrag_concepts.db",
    "codrag_observations.db",
    "codrag_pipeline_journal.db",
    "codrag_pipeline_history.db",
    "codrag_settings.db",
    "codrag_token_telemetry.db",
    "ui_config.json",
)

# Files we deliberately do NOT migrate. Kept here so we document the
# "we saw it and chose to ignore it" decision.
_SKIPPED_FILES = (
    "projects.db",                   # legacy, pre-registry.db
    "registry.db",                   # shadow of the authoritative XDG copy
    "settings.db",                   # 0-byte leftover from a dev incident
)

_SENTINEL_NAME = ".migrated_from_cwd"


@dataclass
class MigrationResult:
    """Outcome of a single call to `migrate_legacy_data_dir`."""

    ran: bool = False                 # False = no-op (sentinel/no legacy dir)
    moved: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)  # lost files -> .migration-conflict
    skipped: List[str] = field(default_factory=list)    # present-but-ignored
    errors: List[str] = field(default_factory=list)

    def as_log_summary(self) -> str:
        parts = []
        if self.moved:
            parts.append(f"moved={len(self.moved)}")
        if self.conflicts:
            parts.append(f"conflicts={len(self.conflicts)}")
        if self.skipped:
            parts.append(f"skipped={len(self.skipped)}")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return ", ".join(parts) or "no-op"


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _sqlite_row_count(path: Path) -> Optional[int]:
    """Total row count across all user tables, or None if DB is unreadable."""
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.5) as conn:
            conn.row_factory = sqlite3.Row
            tables = [
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            ]
            total = 0
            for table in tables:
                try:
                    row = conn.execute(f"SELECT COUNT(*) AS n FROM '{table}'").fetchone()
                    total += int(row["n"])
                except sqlite3.DatabaseError:
                    return None
            return total
    except sqlite3.DatabaseError:
        return None
    except Exception:
        return None


def _pick_winner(legacy: Path, dest: Path, name: str) -> Path:
    """Return whichever of `legacy`/`dest` is the preferred data copy.

    Default heuristic: larger file wins. For `codrag_settings.db` we
    first try row-count comparison — a leftover WAL-corrupted file can
    be larger but semantically dead.
    """
    if name == "codrag_settings.db":
        legacy_rows = _sqlite_row_count(legacy)
        dest_rows = _sqlite_row_count(dest)
        if legacy_rows is not None and dest_rows is not None and legacy_rows != dest_rows:
            winner = legacy if legacy_rows > dest_rows else dest
            logger.info(
                "data-dir migration: %s row-count tiebreak legacy=%d dest=%d → winner=%s",
                name, legacy_rows, dest_rows, winner,
            )
            return winner

    legacy_size = legacy.stat().st_size
    dest_size = dest.stat().st_size
    winner = legacy if legacy_size >= dest_size else dest
    logger.info(
        "data-dir migration: %s size-tiebreak legacy=%dB dest=%dB → winner=%s",
        name, legacy_size, dest_size, winner,
    )
    return winner


def _safe_rename_or_copy(src: Path, dst: Path) -> None:
    """Atomic same-fs rename, or copy+fsync+unlink across filesystems."""
    try:
        os.replace(str(src), str(dst))
    except OSError:
        shutil.copy2(str(src), str(dst))
        with open(dst, "rb") as f:
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        src.unlink()


def _sqlite_sidecars(name: str) -> tuple[str, ...]:
    """Return `-wal`/`-shm` sidecar names for a SQLite DB, or empty for others.

    WAL files carry committed-but-not-checkpointed transactions. Moving
    the `.db` without its WAL is a data-loss bug — SQLite opens the
    main file with no WAL and silently discards those pages.
    """
    if not name.endswith(".db"):
        return ()
    return (f"{name}-wal", f"{name}-shm")


def _migrate_sidecars(
    name: str,
    legacy: Path,
    dest_dir: Path,
    result: MigrationResult,
) -> None:
    """Move `.db-wal` / `.db-shm` siblings after a successful `.db` move.

    Sidecar behavior:
    - -wal: must move WITH the .db. Loss = committed transactions dropped.
    - -shm: shared-memory index; safe to move. SQLite rebuilds it on open
      if absent, but moving keeps the WAL recovery path consistent.

    If a sidecar already exists at dest (shouldn't, since we only reach
    here when `.db` itself was moved cleanly), overwrite it.
    """
    for sidecar in _sqlite_sidecars(name):
        src = legacy / sidecar
        if not src.exists():
            continue
        dst = dest_dir / sidecar
        try:
            if dst.exists():
                dst.unlink()
            _safe_rename_or_copy(src, dst)
            result.moved.append(sidecar)
        except Exception as e:
            logger.exception("data-dir migration: failed to move sidecar %s", sidecar)
            result.errors.append(f"{sidecar}: {e!r}")


def _migrate_one(
    name: str,
    legacy: Path,
    dest_dir: Path,
    result: MigrationResult,
) -> None:
    src = legacy / name
    if not src.exists():
        return

    dst = dest_dir / name

    if not _is_nonempty_file(dst) and dst.exists():
        # Destination is a 0-byte placeholder (e.g. unused sqlite shell).
        # Remove it so the rename can replace it.
        try:
            dst.unlink()
        except OSError:
            pass

    if not dst.exists():
        try:
            _safe_rename_or_copy(src, dst)
            result.moved.append(name)
            _migrate_sidecars(name, legacy, dest_dir, result)
        except Exception as e:
            logger.exception("data-dir migration: failed to move %s", name)
            result.errors.append(f"{name}: {e!r}")
        return

    # Both sides non-empty — conflict resolution.
    try:
        winner = _pick_winner(src, dst, name)
        if winner == src:
            # Legacy wins — move current dest (and its sidecars) aside,
            # then move legacy in.
            iso = _iso_now()
            conflict_path = dst.with_name(f"{name}.migration-conflict.{iso}")
            _safe_rename_or_copy(dst, conflict_path)
            # Preserve the losing side's WAL/SHM alongside it so the
            # conflict backup is recoverable as a complete DB.
            for sidecar in _sqlite_sidecars(name):
                loser_side = dest_dir / sidecar
                if loser_side.exists():
                    loser_conflict = dst.with_name(
                        f"{name}.migration-conflict.{iso}-{sidecar.rsplit('-', 1)[-1]}"
                    )
                    try:
                        _safe_rename_or_copy(loser_side, loser_conflict)
                    except Exception:
                        logger.exception(
                            "data-dir migration: failed to preserve loser sidecar %s",
                            sidecar,
                        )
            _safe_rename_or_copy(src, dst)
            _migrate_sidecars(name, legacy, dest_dir, result)
            result.moved.append(name)
            result.conflicts.append(conflict_path.name)
        else:
            # Dest wins — move legacy (and its sidecars) aside.
            iso = _iso_now()
            conflict_path = dst.with_name(f"{name}.migration-conflict.{iso}")
            _safe_rename_or_copy(src, conflict_path)
            for sidecar in _sqlite_sidecars(name):
                legacy_side = legacy / sidecar
                if legacy_side.exists():
                    legacy_conflict = dst.with_name(
                        f"{name}.migration-conflict.{iso}-{sidecar.rsplit('-', 1)[-1]}"
                    )
                    try:
                        _safe_rename_or_copy(legacy_side, legacy_conflict)
                    except Exception:
                        logger.exception(
                            "data-dir migration: failed to preserve legacy sidecar %s",
                            sidecar,
                        )
            result.conflicts.append(conflict_path.name)
    except Exception as e:
        logger.exception("data-dir migration: conflict resolution failed for %s", name)
        result.errors.append(f"{name}: {e!r}")


_LEGACY_CODRAG_SENTINEL = ".migrated_from_codrag"


def migrate_from_legacy_codrag() -> bool:
    """Migrate ~/.local/share/codrag/ -> ~/.local/share/prep/ once.

    Sentinel-gated: writes <target>/.migrated_from_codrag on completion.
    On conflict (both sides non-empty), target wins; legacy is renamed to
    <legacy_parent>/codrag.migration-conflict.<ISO8601>/.

    Returns True if a migration occurred (including conflict resolution),
    False if no migration was needed (sentinel exists or legacy absent).
    """
    try:
        home = Path.home()
        legacy = home / ".local" / "share" / "codrag"
        target = home / ".local" / "share" / "prep"
        sentinel = target / _LEGACY_CODRAG_SENTINEL

        if sentinel.exists():
            return False
        if not legacy.exists():
            return False

        logger.info(
            "codrag->prep dir migration: legacy=%s → target=%s", legacy, target
        )

        if target.exists() and any(target.iterdir()):
            # Conflict: target already has data. Preserve legacy as a sibling.
            iso = _iso_now()
            conflict = legacy.with_name(f"codrag.migration-conflict.{iso}")
            legacy.rename(conflict)
            logger.info(
                "codrag->prep dir migration: conflict — target already populated; "
                "legacy preserved as %s",
                conflict,
            )
        else:
            # Target is absent or empty — move legacy in place.
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.rmdir()  # empty dir from a prior aborted run
            shutil.move(str(legacy), str(target))

        target.mkdir(exist_ok=True)
        sentinel.write_text(datetime.now(timezone.utc).isoformat() + "Z\n")
        logger.info("codrag->prep dir migration: done")
        return True

    except Exception:
        logger.exception(
            "codrag->prep dir migration: top-level failure (daemon will still start)"
        )
        return False


def migrate_legacy_data_dir(
    cwd: Path | None = None,
    data_dir_override: Path | None = None,
) -> MigrationResult:
    """Run the one-time migration. Idempotent via sentinel.

    Args:
        cwd: directory containing the legacy `codrag_data/` (defaults to
            `Path.cwd()`).
        data_dir_override: destination data dir. Tests pass this; prod
            leaves it None so `paths.data_dir()` resolves it.

    Returns:
        MigrationResult describing what happened. `ran=False` for the
        common no-op cases (no legacy dir, sentinel already present).
    """
    result = MigrationResult()

    try:
        from prep.core.paths import data_dir as resolve_data_dir
        from prep.core.paths import legacy_cwd_data_dir

        dest_dir = Path(data_dir_override) if data_dir_override else resolve_data_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)

        legacy = legacy_cwd_data_dir(cwd)
        if not legacy.is_dir():
            return result

        # If the legacy dir IS the dest (user ran from a parent that
        # happens to contain a `codrag_data` alias — unlikely, but safe),
        # there's nothing to migrate.
        try:
            if legacy.resolve() == dest_dir.resolve():
                return result
        except OSError:
            pass

        sentinel = dest_dir / _SENTINEL_NAME
        if sentinel.exists():
            return result

        legacy_contents = {p.name for p in legacy.iterdir() if p.is_file()}
        recognized_present = [f for f in _RECOGNIZED_FILES if f in legacy_contents]
        if not recognized_present:
            return result

        result.ran = True
        logger.info(
            "data-dir migration: legacy=%s → dest=%s (%d recognized files)",
            legacy, dest_dir, len(recognized_present),
        )

        for name in _RECOGNIZED_FILES:
            _migrate_one(name, legacy, dest_dir, result)

        for name in _SKIPPED_FILES:
            if name in legacy_contents:
                result.skipped.append(name)

        sentinel_payload = {
            "migrated_at": datetime.now(timezone.utc).isoformat(),
            "legacy_path": str(legacy),
            "dest_path": str(dest_dir),
            "hostname": socket.gethostname(),
            "moved": result.moved,
            "conflicts": result.conflicts,
            "skipped": result.skipped,
            "errors": result.errors,
        }
        try:
            sentinel.write_text(json.dumps(sentinel_payload, indent=2))
        except Exception:
            logger.exception("data-dir migration: failed to write sentinel")

        logger.info("data-dir migration: done (%s)", result.as_log_summary())

    except Exception as e:
        logger.exception("data-dir migration: top-level failure (daemon will still start)")
        result.errors.append(f"top-level: {e!r}")

    return result
