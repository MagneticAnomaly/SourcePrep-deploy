"""Tests for directory-scoped observation retrieval."""
from pathlib import Path

import pytest

from prep.services.observation_store import ObservationStore


@pytest.fixture
def store(tmp_path: Path) -> ObservationStore:
    s = ObservationStore()
    s.init(tmp_path / "test.db")
    yield s
    s.close()


def test_get_for_directory_returns_matching_observations(store: ObservationStore) -> None:
    store.save("proj-1", "Auth uses JWT", file_path="src/auth/login.py")
    store.save("proj-1", "Auth rate limiting", file_path="src/auth/middleware.py")
    store.save("proj-1", "DB migration note", file_path="src/db/migrate.py")

    results = store.get_for_directory("proj-1", "src/auth")
    assert len(results) == 2
    paths = {r.file_path for r in results}
    assert paths == {"src/auth/login.py", "src/auth/middleware.py"}


def test_get_for_directory_excludes_stale_when_requested(store: ObservationStore) -> None:
    store.save("proj-1", "Old note", file_path="src/auth/old.py")
    store.mark_stale_batch("proj-1", ["src/auth/old.py"], "file deleted")
    store.save("proj-1", "Fresh note", file_path="src/auth/new.py")

    results = store.get_for_directory("proj-1", "src/auth", include_stale=False)
    assert len(results) == 1
    assert results[0].file_path == "src/auth/new.py"


def test_get_for_directory_empty_for_no_match(store: ObservationStore) -> None:
    store.save("proj-1", "Unrelated", file_path="src/db/schema.py")

    results = store.get_for_directory("proj-1", "src/auth")
    assert results == []


def test_get_for_directory_excludes_null_file_paths(store: ObservationStore) -> None:
    store.save("proj-1", "General note")

    results = store.get_for_directory("proj-1", "src")
    assert results == []


def test_get_for_directory_respects_limit(store: ObservationStore) -> None:
    for i in range(10):
        store.save("proj-1", f"Note {i}", file_path=f"src/auth/file{i}.py")

    results = store.get_for_directory("proj-1", "src/auth", limit=3)
    assert len(results) == 3


def test_get_for_directory_trailing_slash_normalization(store: ObservationStore) -> None:
    store.save("proj-1", "Note", file_path="src/auth/login.py")

    results_no_slash = store.get_for_directory("proj-1", "src/auth")
    results_slash = store.get_for_directory("proj-1", "src/auth/")
    assert len(results_no_slash) == len(results_slash) == 1
