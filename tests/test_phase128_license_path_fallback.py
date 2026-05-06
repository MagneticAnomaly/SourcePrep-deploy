"""Phase 128 Task 2: license path resolves .sourceprep first, .runprep as legacy fallback.

After the RunPrep→SourcePrep brand split, license files moved from
~/.runprep/license.json to ~/.sourceprep/license.json. To avoid breaking
existing licensed installs through the rename, the resolver reads .sourceprep
first and falls back to .runprep when only the legacy file exists. New
license writes go to .sourceprep.
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


def test_falls_back_to_runprep_when_sourceprep_missing(tmp_path: Path) -> None:
    from prep.core.feature_gate import _resolve_license_path

    legacy_dir = tmp_path / ".runprep"
    legacy_dir.mkdir()
    (legacy_dir / "license.json").write_text("{}")

    with patch("prep.core.feature_gate.Path.home", return_value=tmp_path):
        assert _resolve_license_path() == legacy_dir / "license.json"


def test_returns_sourceprep_path_for_new_writes_when_neither_exists(tmp_path: Path) -> None:
    """When no license file exists yet, point to the new path so writes go there."""
    from prep.core.feature_gate import _resolve_license_path

    with patch("prep.core.feature_gate.Path.home", return_value=tmp_path):
        result = _resolve_license_path()
        assert result.parent.name == ".sourceprep"
        assert result.name == "license.json"
