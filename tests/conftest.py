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
    ceilings at ~/.local/share/prep/concurrency_store.db, polluting
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
    prep_dir = mini_repo / ".prep"
    if prep_dir.exists():
        shutil.rmtree(prep_dir)
    
    yield mini_repo
    
    # Cleanup after test
    if prep_dir.exists():
        shutil.rmtree(prep_dir)
