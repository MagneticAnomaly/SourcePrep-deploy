"""Regression test for concept_store init after data-dir rename.

Reproduces the post brand-rename (codrag -> prep -> runprep) state where
prep_settings.db exists but has no concepts table, and prep_concepts.db
is missing. Before the fix, configure()'s migration branch skipped
concept_store.init() in this case, leaving the store uninitialized and
causing concepts-stage failures with "ConceptStore not initialized".
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from prep import server
from prep.services.concept_store import concept_store


def _make_bare_settings_db(path: Path) -> None:
    """Create a prep_settings.db with only settings/settings_meta tables."""
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE settings (
                namespace TEXT NOT NULL DEFAULT 'global',
                key       TEXT NOT NULL,
                value     TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, key)
            );
            CREATE TABLE settings_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_configure_initializes_concept_store_when_settings_has_no_concepts_table(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "runprep_data"
    data_dir.mkdir()
    _make_bare_settings_db(data_dir / "prep_settings.db")
    assert not (data_dir / "prep_concepts.db").exists()

    # Ensure a clean starting state — other tests may have initialized
    # the singleton already.
    concept_store.close()

    try:
        server.configure(index_dir=str(data_dir))
        assert concept_store._conn is not None, (
            "concept_store.init() should have been called during configure(); "
            "migration branch skipped it when settings.db had no concepts table"
        )
        assert (data_dir / "prep_concepts.db").exists(), (
            "Dedicated prep_concepts.db should be created on init"
        )
    finally:
        concept_store.close()
