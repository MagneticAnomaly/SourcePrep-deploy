"""Tests for Phase 119 lock-with-TTL extension to ConcurrencyStore.

Schema migration adds two columns:
  - locked_until: float — unix seconds; ceiling is locked until this time.
  - edge_observed_at: float — when the backoff edge that established
    the ceiling was observed.

Both default to 0 for legacy rows so a fresh-install boot sees them
as "unlocked" (i.e. probing) until a real edge fires.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from prep.services.pipeline.concurrency_store import ConcurrencyStore


@pytest.fixture
def store(tmp_path: Path) -> ConcurrencyStore:
    return ConcurrencyStore(tmp_path / "concurrency.db")


def test_load_full_returns_ceiling_lock_edge(store: ConcurrencyStore) -> None:
    now = time.time()
    store.save_edge("cloud:ep-1", "__default__", ceiling=12, locked_until=now + 3600, edge_observed_at=now)
    record = store.load_full("cloud:ep-1", "__default__")
    assert record is not None
    assert record["ceiling"] == 12
    assert abs(record["locked_until"] - (now + 3600)) < 1.0
    assert abs(record["edge_observed_at"] - now) < 1.0


def test_load_full_missing_returns_none(store: ConcurrencyStore) -> None:
    assert store.load_full("cloud:none", "__default__") is None


def test_save_edge_overwrites_in_place(store: ConcurrencyStore) -> None:
    now = time.time()
    store.save_edge("cloud:ep-1", "__default__", ceiling=12, locked_until=now + 3600, edge_observed_at=now)
    store.save_edge("cloud:ep-1", "__default__", ceiling=14, locked_until=now + 7200, edge_observed_at=now + 10)
    record = store.load_full("cloud:ep-1", "__default__")
    assert record is not None
    assert record["ceiling"] == 14
    assert abs(record["locked_until"] - (now + 7200)) < 1.0


def test_legacy_save_still_works_and_reads_back_with_zero_lock(store: ConcurrencyStore) -> None:
    """Pre-Phase-119 callers using the original save() must keep working."""
    store.save("cloud:ep-1", "__default__", ceiling=20)
    assert store.load("cloud:ep-1", "__default__") == 20
    record = store.load_full("cloud:ep-1", "__default__")
    assert record is not None
    assert record["ceiling"] == 20
    assert record["locked_until"] == 0.0
    assert record["edge_observed_at"] == 0.0


def test_migration_from_legacy_schema(tmp_path: Path) -> None:
    """A pre-Phase-119 DB with only (node_id, model_family, ceiling, updated_at)
    must migrate to the new schema on first connect, preserving existing rows.
    """
    db_path = tmp_path / "concurrency.db"
    legacy_schema = """
        CREATE TABLE discovered_ceilings (
            node_id TEXT NOT NULL,
            model_family TEXT NOT NULL,
            ceiling INTEGER NOT NULL,
            updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (node_id, model_family)
        )
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(legacy_schema)
        conn.execute(
            "INSERT INTO discovered_ceilings (node_id, model_family, ceiling) VALUES (?, ?, ?)",
            ("cloud:legacy", "__default__", 30),
        )
        conn.commit()
    finally:
        conn.close()

    # Opening the store triggers migration.
    store = ConcurrencyStore(db_path)
    record = store.load_full("cloud:legacy", "__default__")
    assert record is not None
    assert record["ceiling"] == 30
    assert record["locked_until"] == 0.0
    assert record["edge_observed_at"] == 0.0


def test_clear_removes_lock_too(store: ConcurrencyStore) -> None:
    now = time.time()
    store.save_edge("cloud:ep-1", "__default__", ceiling=12, locked_until=now + 3600, edge_observed_at=now)
    store.clear("cloud:ep-1", "__default__")
    assert store.load_full("cloud:ep-1", "__default__") is None


def test_save_edge_rejects_bad_ceiling(store: ConcurrencyStore) -> None:
    with pytest.raises(ValueError):
        store.save_edge("cloud:ep-1", "__default__", ceiling=0, locked_until=0, edge_observed_at=0)


def test_save_edge_rejects_lock_before_edge(store: ConcurrencyStore) -> None:
    """If locked_until is set, it must not precede the edge it locks."""
    with pytest.raises(ValueError):
        store.save_edge(
            "cloud:ep-1", "__default__",
            ceiling=10, locked_until=100.0, edge_observed_at=200.0,
        )


def test_save_edge_allows_zero_locked_until(store: ConcurrencyStore) -> None:
    """locked_until=0 means 'no lock yet' — permitted even with non-zero edge."""
    store.save_edge(
        "cloud:ep-1", "__default__",
        ceiling=10, locked_until=0.0, edge_observed_at=12345.0,
    )
    record = store.load_full("cloud:ep-1", "__default__")
    assert record is not None
    assert record["locked_until"] == 0.0
    assert record["edge_observed_at"] == 12345.0
