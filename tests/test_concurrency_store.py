"""Tests for ConcurrencyStore — persisted AIMD ceilings.

Phase 82 completion: on daemon restart, the scheduler should
re-hydrate the discovered ceiling per (endpoint, model_family)
instead of replaying jumpstart from seed=5 every boot. The
mode/streak/backoff-time state deliberately does NOT survive
restart — only the ceiling carries forward.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from prep.services.pipeline.concurrency_store import ConcurrencyStore


@pytest.fixture
def store(tmp_path: Path) -> ConcurrencyStore:
    return ConcurrencyStore(tmp_path / "concurrency.db")


def test_load_missing_returns_none(store: ConcurrencyStore) -> None:
    assert store.load("cloud:ep-1", "qwen3-coder") is None


def test_save_then_load_roundtrip(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=40)
    assert store.load("cloud:ep-1", "qwen3-coder") == 40


def test_save_overwrites(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=20)
    store.save("cloud:ep-1", "qwen3-coder", ceiling=80)
    assert store.load("cloud:ep-1", "qwen3-coder") == 80


def test_distinct_model_families_are_independent(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=40)
    store.save("cloud:ep-1", "gemini-2.5-flash", ceiling=10)
    assert store.load("cloud:ep-1", "qwen3-coder") == 40
    assert store.load("cloud:ep-1", "gemini-2.5-flash") == 10


def test_distinct_endpoints_are_independent(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=40)
    store.save("cloud:ep-2", "qwen3-coder", ceiling=80)
    assert store.load("cloud:ep-1", "qwen3-coder") == 40
    assert store.load("cloud:ep-2", "qwen3-coder") == 80


def test_clear_removes_entry(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=40)
    store.clear("cloud:ep-1", "qwen3-coder")
    assert store.load("cloud:ep-1", "qwen3-coder") is None


def test_minimum_ceiling_is_rejected(store: ConcurrencyStore) -> None:
    """Ceiling must be a positive integer; zero/negative can't mean concurrency."""
    with pytest.raises(ValueError):
        store.save("cloud:ep-1", "qwen3-coder", ceiling=0)
    with pytest.raises(ValueError):
        store.save("cloud:ep-1", "qwen3-coder", ceiling=-1)


def test_uses_delete_journal_mode(tmp_path: Path) -> None:
    """Per project policy: WAL is unreliable on USB, use DELETE journal mode.

    Robust test: seed the DB file with WAL mode externally, then prove
    that ConcurrencyStore actively resets it back to DELETE. A weaker
    test (inspecting the default mode of a fresh file) would pass even
    if the PRAGMA line were deleted from _connect(), because DELETE is
    SQLite's default.
    """
    import sqlite3

    db_path = tmp_path / "concurrency.db"
    # Seed WAL mode externally, before the store ever touches the file.
    seed = sqlite3.connect(db_path)
    try:
        seed.execute("PRAGMA journal_mode = WAL")
        seed.commit()
        assert seed.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        seed.close()

    # Opening through ConcurrencyStore should reset the mode to DELETE.
    store = ConcurrencyStore(db_path)
    store.save("cloud:ep-1", "qwen3-coder", ceiling=10)

    # Verify from a fresh external connection (no PRAGMA on this one).
    verify = sqlite3.connect(db_path)
    try:
        mode = verify.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        verify.close()
    assert mode.lower() == "delete", f"Store did not enforce DELETE mode (got {mode!r})"


def test_default_store_uses_data_dir(monkeypatch, tmp_path: Path) -> None:
    """The module-level singleton reads from `data_dir() / concurrency_store.db`."""
    from prep.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from prep.services.pipeline import concurrency_store as mod

    # Force re-init by calling the accessor
    mod._store = None  # type: ignore[attr-defined]
    s = mod.concurrency_store()
    s.save("cloud:ep-1", "test-model", ceiling=10)
    assert (tmp_path / "concurrency_store.db").exists()
    assert s.load("cloud:ep-1", "test-model") == 10
