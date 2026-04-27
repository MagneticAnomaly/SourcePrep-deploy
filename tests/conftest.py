"""
Pytest configuration and shared fixtures for Prep tests.

Fixtures defined here are automatically available to all test files.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Generator

import pytest


import os

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture(autouse=True)
def _unlock_all_features(monkeypatch):
    """Set PREP_TIER=pro for all tests so feature gates don't block integration tests."""
    monkeypatch.setenv("PREP_TIER", "pro")
    monkeypatch.setenv("PREP_DEV_MODE", "1")
    from prep.core.feature_gate import clear_license_cache
    clear_license_cache()
    yield
    clear_license_cache()

@pytest.fixture(autouse=True)
def _init_global_stores(tmp_path: Path):
    """Automatically initialize required background SQLite stores for all tests."""
    from prep.services.settings_store import settings
    from prep.services.token_telemetry import telemetry

    db_path = tmp_path / "global_test_db.sqlite"
    settings.init(db_path)
    telemetry.init(db_path)

    yield

    settings.close()
    telemetry.close()


@pytest.fixture(autouse=True)
def _isolate_concurrency_store(tmp_path_factory, monkeypatch):
    """Phase 82: isolate ConcurrencyStore per test.

    The store is a process-level singleton that reads data_dir() lazily.
    Without isolation, tests would read the real user's persisted AIMD
    ceilings at ~/.local/share/runprep/concurrency_store.db, polluting
    scheduler tests that expect fresh cloud-slot seeds (current_limit=5).
    """
    from prep.services.pipeline import concurrency_store as _cs_mod
    from prep.core import paths as _paths_mod

    test_data_dir = tmp_path_factory.mktemp("prep_test_data")
    monkeypatch.setattr(_paths_mod, "data_dir", lambda: test_data_dir)
    monkeypatch.setattr(_cs_mod, "_store", None)
    yield
    # monkeypatch auto-restores singleton and data_dir after each test.

@pytest.fixture
def tmp_settings(tmp_path):
    """Swap the settings_store singleton's SQLite file to a tmp_path-backed copy.

    Note: _init_global_stores (autouse) already initialises the settings
    singleton against a per-test tmp_path DB.  This fixture re-initialises
    it against a *second* isolated DB so that tests using tmp_settings get a
    completely clean slate that is not shared with other fixtures.
    """
    from prep.services import settings_store as ss

    db = tmp_path / "settings.db"
    # Close any existing connection first (autouse fixture may have opened one)
    ss.settings.close()
    # Point the singleton at the new isolated DB and open a fresh connection
    ss.settings._db_path = None
    ss.settings._conn = None
    ss.settings.init(db)
    yield ss.settings
    ss.settings.close()
    ss.settings._conn = None


@pytest.fixture
def dummy_project(tmp_path, monkeypatch):
    from prep.core.project_registry import Project
    proj = Project(
        id="proj-test",
        name="Test",
        path=str(tmp_path),
        mode="standalone",
        config={"included_paths": []},
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    from prep.services import project_helpers as ph
    monkeypatch.setattr(ph, "require_project", lambda pid: proj)
    return proj


class _FakeRegistry:
    def __init__(self, proj):
        self._proj = proj

    def get_project(self, project_id):
        return self._proj if project_id == self._proj.id else None

    def mutate_config(self, project_id, mutator, *, touch: bool = True):
        if project_id != self._proj.id:
            return self._proj
        new_cfg = mutator(self._proj.config or {}) or {}
        # Project is frozen=True; use object.__setattr__ to bypass the guard.
        object.__setattr__(self._proj, "config", new_cfg)
        return self._proj


@pytest.fixture
def dummy_project_in_registry(dummy_project, monkeypatch):
    """Like dummy_project but also patches the get_registry() singleton so that
    mutate_global_scope (which calls get_registry().mutate_config / get_project)
    works against an in-memory registry instead of a real SQLite DB."""
    from prep.services import project_helpers as ph
    fake = _FakeRegistry(dummy_project)
    monkeypatch.setattr(ph, "_registry", fake)
    return dummy_project


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """
    Create a minimal test repository with deterministic content.
    
    Contains:
    - main.py: Hello world + greet function
    - utils.py: add + multiply functions
    - README.md: Basic documentation
    
    Usage:
        def test_something(mini_repo: Path):
            # mini_repo is a Path to a temp directory with test files
            server = DirectMCPServer(repo_root=mini_repo)
    """
    repo = tmp_path / "test_repo"
    repo.mkdir()

    (repo / "main.py").write_text(
        '''"""Main module for the application."""

def main() -> str:
    """Return hello world."""
    return "hello world"

def greet(name: str) -> str:
    """Greet a user by name."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(main())
'''
    )

    (repo / "utils.py").write_text(
        '''"""Utility functions."""

def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
'''
    )

    (repo / "README.md").write_text(
        """# Test Repository

This is a minimal test repository for integration testing.

## Features

- Hello world greeting
- Basic math utilities
"""
    )

    return repo


@pytest.fixture
def fake_embedder():
    """
    Provide a FakeEmbedder for testing without Ollama dependency.
    
    Usage:
        def test_something(fake_embedder):
            idx = CodeIndex(index_dir=..., embedder=fake_embedder)
    """
    from prep.core import FakeEmbedder
    return FakeEmbedder(model="test-embed", dim=384)


@pytest.fixture
def clean_codrag_dir(mini_repo: Path) -> Generator[Path, None, None]:
    """
    Ensure .prep directory is clean before and after test.
    
    Usage:
        def test_something(clean_codrag_dir):
            repo = clean_codrag_dir  # .prep is guaranteed clean
    """
    prep_dir = mini_repo / ".sourceprep"
    if prep_dir.exists():
        shutil.rmtree(prep_dir)
    
    yield mini_repo
    
    # Cleanup after test
    if prep_dir.exists():
        shutil.rmtree(prep_dir)
