"""Phase 113 Step 1 — codrag.core.paths.data_dir() resolution.

Pre-fix state: there was no single path helper. Several callers
(server.py, config_manager.py, build_manager.py) defaulted to
`./codrag_data` while project_registry.codrag_data_dir() returned
`~/.local/share/codrag/`. Post-fix, every caller routes through
`paths.data_dir()`.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from prep.core.paths import data_dir, legacy_cwd_data_dir


def test_env_var_overrides_default() -> None:
    """CODRAG_DATA_DIR (absolute) takes precedence over ~/.local/share/codrag."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        with patch.dict(os.environ, {"CODRAG_DATA_DIR": str(td_path)}):
            resolved = data_dir()
        assert resolved == td_path


def test_env_var_must_be_absolute() -> None:
    """A relative CODRAG_DATA_DIR must raise — we refuse CWD-drift."""
    with patch.dict(os.environ, {"CODRAG_DATA_DIR": "relative/path"}):
        with pytest.raises(ValueError, match="absolute"):
            data_dir()


def test_default_is_xdg() -> None:
    """With no env var, default is ~/.local/share/codrag."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CODRAG_DATA_DIR", None)
        resolved = data_dir()
    assert resolved == Path.home() / ".local" / "share" / "codrag"


def test_env_var_path_is_created() -> None:
    """data_dir() must create the directory if absent (parents=True)."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve() / "nested" / "codrag"
        assert not td_path.exists()
        with patch.dict(os.environ, {"CODRAG_DATA_DIR": str(td_path)}):
            resolved = data_dir()
        assert resolved.is_dir()
        assert resolved == td_path


def test_env_var_expanduser() -> None:
    """Tilde in the env var is expanded before the absolute-path check."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        # Simulate ~-prefixed value by pointing HOME at td
        with patch.dict(os.environ, {"HOME": str(td_path), "CODRAG_DATA_DIR": "~/codrag"}):
            resolved = data_dir()
        assert resolved == td_path / "codrag"


def test_legacy_cwd_data_dir_is_relative_to_arg() -> None:
    """legacy_cwd_data_dir(cwd=...) uses the given CWD, not the process CWD."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        assert legacy_cwd_data_dir(td_path) == td_path / "codrag_data"


def test_empty_env_var_falls_through_to_default() -> None:
    """An empty CODRAG_DATA_DIR is treated as unset."""
    with patch.dict(os.environ, {"CODRAG_DATA_DIR": "  "}):
        resolved = data_dir()
    assert resolved == Path.home() / ".local" / "share" / "codrag"
