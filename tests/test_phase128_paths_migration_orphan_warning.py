"""Phase 128 Task 1: warn when legacy .runprep/.codrag dirs coexist with .sourceprep/.

The migration in paths._migrate_embedded_dir runs once per project open. When
a user wipes-and-rebuilds (creating .sourceprep/ from scratch), the
runprep→sourceprep rename branch silently no-ops because the target already
exists, leaving .runprep/ as a silent orphan. This test verifies a one-time
warning is logged so operators can clean up explicitly.
"""
from __future__ import annotations

import logging
from pathlib import Path


def test_warns_when_runprep_and_sourceprep_coexist(tmp_path: Path, caplog) -> None:
    from prep.core.paths import _migrate_embedded_dir

    (tmp_path / ".runprep").mkdir()
    (tmp_path / ".sourceprep").mkdir()
    # Marker file inside legacy dir to make the warning actionable
    (tmp_path / ".runprep" / ".pipeline_clean_shutdown").write_text("123")

    with caplog.at_level(logging.WARNING, logger="prep.core.paths"):
        _migrate_embedded_dir(tmp_path)

    msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(".runprep" in m for m in msgs), f"no warning about .runprep orphan: {msgs}"
    assert any("orphan" in m.lower() for m in msgs)


def test_no_warning_when_only_sourceprep_exists(tmp_path: Path, caplog) -> None:
    from prep.core.paths import _migrate_embedded_dir

    (tmp_path / ".sourceprep").mkdir()
    with caplog.at_level(logging.WARNING, logger="prep.core.paths"):
        _migrate_embedded_dir(tmp_path)

    msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert not any("orphan" in m.lower() for m in msgs)


def test_warning_lists_all_legacy_dirs(tmp_path: Path, caplog) -> None:
    from prep.core.paths import _migrate_embedded_dir

    (tmp_path / ".codrag").mkdir()
    (tmp_path / ".runprep").mkdir()
    (tmp_path / ".sourceprep").mkdir()

    with caplog.at_level(logging.WARNING, logger="prep.core.paths"):
        _migrate_embedded_dir(tmp_path)

    msgs = " ".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
    assert ".codrag" in msgs
    assert ".runprep" in msgs


def test_no_warning_when_no_sourceprep_exists(tmp_path: Path, caplog) -> None:
    """If only legacy dirs exist, the migration RENAMES; no warning needed."""
    from prep.core.paths import _migrate_embedded_dir

    (tmp_path / ".runprep").mkdir()
    # No .sourceprep — migration should rename, not warn

    with caplog.at_level(logging.WARNING, logger="prep.core.paths"):
        _migrate_embedded_dir(tmp_path)

    msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert not any("orphan" in m.lower() for m in msgs)
    # And the rename should have happened
    assert (tmp_path / ".sourceprep").exists()
    assert not (tmp_path / ".runprep").exists()
