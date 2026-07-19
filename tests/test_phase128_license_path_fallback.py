"""License path resolves to ~/.sourceprep/license.json (no legacy fallback).

The .runprep legacy fallback was removed 2026-07-19: the codrag/RunPrep
product names are dead with no surviving licensed installs, so there is
no legacy license file to discover. Reads and writes both target the
canonical ~/.sourceprep location. A stray ~/.runprep/license.json left
on disk is ignored (the name is dead), not honored.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_resolves_sourceprep_when_present(tmp_path: Path) -> None:
    from prep.core.feature_gate import _resolve_license_path

    new_dir = tmp_path / ".sourceprep"
    new_dir.mkdir()
    (new_dir / "license.json").write_text("{}")
    legacy_dir = tmp_path / ".runprep"
    legacy_dir.mkdir()
    (legacy_dir / "license.json").write_text("{}")

    with patch("prep.core.feature_gate.Path.home", return_value=tmp_path):
        assert _resolve_license_path() == new_dir / "license.json"


def test_ignores_dead_runprep_when_sourceprep_missing(tmp_path: Path) -> None:
    """A stray ~/.runprep/license.json is NOT honored — the name is dead."""
    from prep.core.feature_gate import _resolve_license_path

    legacy_dir = tmp_path / ".runprep"
    legacy_dir.mkdir()
    (legacy_dir / "license.json").write_text("{}")

    with patch("prep.core.feature_gate.Path.home", return_value=tmp_path):
        result = _resolve_license_path()
        # Returns the canonical .sourceprep path even though it does not exist
        # yet (writes target it), NOT the dead .runprep path.
        assert result.parent.name == ".sourceprep"
        assert result.name == "license.json"
        assert result == tmp_path / ".sourceprep" / "license.json"


def test_returns_sourceprep_path_for_new_writes_when_neither_exists(tmp_path: Path) -> None:
    """When no license file exists yet, point to the new path so writes go there."""
    from prep.core.feature_gate import _resolve_license_path

    with patch("prep.core.feature_gate.Path.home", return_value=tmp_path):
        result = _resolve_license_path()
        assert result.parent.name == ".sourceprep"
        assert result.name == "license.json"
