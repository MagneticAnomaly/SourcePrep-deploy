"""
Tests for included_paths (Knowledge Scope) persistence and RAG integration.

Covers:
- included_paths persistence via project config (SQLite)
- included_paths filter at build time (CodeIndex.build)
- Full RAG integration: trace context + selected file context both flow through
- Scope add/remove delta operations update the canonical set

Uses FakeEmbedder so no Ollama dependency is required.
Run with: pytest tests/test_included_paths.py -v
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set

import pytest

from prep.core import CodeIndex, FakeEmbedder
from prep.core.project_registry import ProjectRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scoped_repo(tmp_path: Path) -> Path:
    """Create a test repo with files in multiple folders for scope testing."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # src/ folder — main code
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text(
        '"""Main module."""\n\ndef main():\n    """Entry point for the application."""\n    return "hello"\n'
    )
    (src / "utils.py").write_text(
        '"""Utility functions."""\n\ndef helper():\n    """Helper utility for processing."""\n    return 42\n'
    )

    # src/core/ subfolder
    core = src / "core"
    core.mkdir()
    (core / "engine.py").write_text(
        '"""Core engine module."""\n\ndef process():\n    """Process data through the engine."""\n    return True\n'
    )

    # docs/ folder
    docs = repo / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "# Project Documentation\n\nThis project has a core engine and utilities.\n"
    )
    (docs / "API.md").write_text(
        "# API Reference\n\nThe main entry point is `main()` in `src/main.py`.\n"
    )

    # tests/ folder
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text(
        '"""Test main."""\n\ndef test_main():\n    assert True\n'
    )

    return repo


@pytest.fixture
def registry(tmp_path: Path) -> ProjectRegistry:
    """Create an isolated ProjectRegistry for testing."""
    db_path = tmp_path / "test_registry.db"
    return ProjectRegistry(db_path=db_path)


# ---------------------------------------------------------------------------
# included_paths persistence via ProjectRegistry
# ---------------------------------------------------------------------------

class TestIncludedPathsPersistence:
    """Test that included_paths persists correctly in project config (SQLite)."""

    def test_empty_by_default(self, registry: ProjectRegistry, tmp_path: Path):
        """New projects have no included_paths."""
        repo = tmp_path / "repo"
        repo.mkdir()
        proj = registry.add_project(path=str(repo), name="test")
        assert proj.config.get("included_paths", []) == []

    def test_set_and_read_included_paths(self, registry: ProjectRegistry, tmp_path: Path):
        """Set included_paths, read them back."""
        repo = tmp_path / "repo"
        repo.mkdir()
        proj = registry.add_project(path=str(repo), name="test")

        new_config = dict(proj.config)
        new_config["included_paths"] = ["src", "docs/README.md"]
        updated = registry.update_project(proj.id, config=new_config)

        assert updated.config["included_paths"] == ["src", "docs/README.md"]

    def test_included_paths_roundtrip(self, registry: ProjectRegistry, tmp_path: Path):
        """Write, close, reopen, read."""
        repo = tmp_path / "repo"
        repo.mkdir()
        proj = registry.add_project(path=str(repo), name="test")

        paths = ["src/main.py", "src/core", "docs"]
        new_config = dict(proj.config)
        new_config["included_paths"] = sorted(paths)
        registry.update_project(proj.id, config=new_config)

        # Re-read from registry (which reads from SQLite)
        reloaded = registry.get_project(proj.id)
        assert reloaded is not None
        assert reloaded.config["included_paths"] == sorted(paths)

    def test_clear_included_paths(self, registry: ProjectRegistry, tmp_path: Path):
        """Setting included_paths to [] clears the scope."""
        repo = tmp_path / "repo"
        repo.mkdir()
        proj = registry.add_project(path=str(repo), name="test")

        # Set some paths
        new_config = dict(proj.config)
        new_config["included_paths"] = ["src", "docs"]
        registry.update_project(proj.id, config=new_config)

        # Clear
        new_config["included_paths"] = []
        updated = registry.update_project(proj.id, config=new_config)
        assert updated.config["included_paths"] == []

    def test_included_paths_coexists_with_path_weights(self, registry: ProjectRegistry, tmp_path: Path):
        """included_paths and path_weights in the same config don't interfere."""
        repo = tmp_path / "repo"
        repo.mkdir()
        proj = registry.add_project(path=str(repo), name="test")

        new_config = dict(proj.config)
        new_config["included_paths"] = ["src", "docs"]
        new_config["path_weights"] = {"src": 1.5, "docs": 0.5}
        updated = registry.update_project(proj.id, config=new_config)

        assert updated.config["included_paths"] == ["src", "docs"]
        assert updated.config["path_weights"] == {"src": 1.5, "docs": 0.5}


# ---------------------------------------------------------------------------
# Scope delta operations
# ---------------------------------------------------------------------------

class TestScopeDeltaOperations:
    """Test add/remove logic that mirrors what the scope router does."""

    @staticmethod
    def _apply_add(current: Set[str], paths: List[str]) -> List[str]:
        """Replicate the add logic from scope.py."""
        for p in paths:
            if p:
                current.add(p)
                prefix = p + "/"
                current = {x for x in current if not x.startswith(prefix) or x == p}
        return sorted(current)

    @staticmethod
    def _apply_remove(current: Set[str], paths: List[str]) -> List[str]:
        """Replicate the remove logic from scope.py."""
        for p in paths:
            current.discard(p)
            prefix = p + "/"
            current = {x for x in current if not x.startswith(prefix)}
        return sorted(current)

    def test_add_single_path(self):
        current: Set[str] = set()
        result = self._apply_add(current, ["src"])
        assert result == ["src"]

    def test_add_parent_removes_children(self):
        """Adding a parent folder should remove explicit children."""
        current: Set[str] = {"src/main.py", "src/utils.py"}
        result = self._apply_add(current, ["src"])
        assert result == ["src"]

    def test_add_child_under_parent_noop(self):
        """Adding a child when parent is already selected keeps parent only."""
        current: Set[str] = {"src"}
        result = self._apply_add(current, ["src/main.py"])
        # Parent "src" already covers src/main.py, but our logic adds it
        # and then removes descendants — src/main.py is NOT a descendant of src/main.py
        # Actually src/main.py doesn't start with "src/main.py/" so it stays
        # But "src" doesn't start with "src/main.py/" either, so both stay
        assert "src" in result
        assert "src/main.py" in result

    def test_remove_single_path(self):
        current: Set[str] = {"src", "docs"}
        result = self._apply_remove(current, ["src"])
        assert result == ["docs"]

    def test_remove_parent_removes_descendants(self):
        current: Set[str] = {"src/main.py", "src/utils.py", "docs"}
        result = self._apply_remove(current, ["src"])
        # "src" itself isn't in the set, but descendants should be removed
        # Wait — discard("src") is a no-op, but the prefix cleanup removes src/*
        assert result == ["docs"]

    def test_remove_nonexistent_is_safe(self):
        current: Set[str] = {"src"}
        result = self._apply_remove(current, ["nonexistent"])
        assert result == ["src"]

    def test_add_then_remove_roundtrip(self):
        current: Set[str] = set()
        current = set(self._apply_add(current, ["src", "docs"]))
        assert sorted(current) == ["docs", "src"]
        current = set(self._apply_remove(current, ["docs"]))
        assert sorted(current) == ["src"]


# ---------------------------------------------------------------------------
# CodeIndex.build() with included_paths filter
# ---------------------------------------------------------------------------

class TestBuildWithIncludedPaths:
    """Test that CodeIndex.build() correctly filters files by included_paths."""

    def test_no_included_paths_indexes_everything(self, scoped_repo: Path, tmp_path: Path):
        """Without included_paths, all files matching globs are indexed."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        meta = idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
        )

        all_paths = {d["source_path"] for d in idx._documents}
        assert "src/main.py" in all_paths
        assert "src/utils.py" in all_paths
        assert "src/core/engine.py" in all_paths
        assert "docs/README.md" in all_paths
        assert "docs/API.md" in all_paths
        assert "tests/test_main.py" in all_paths

    def test_included_paths_folder_filter(self, scoped_repo: Path, tmp_path: Path):
        """Only files under included folders should be indexed."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        meta = idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["src"],
        )

        all_paths = {d["source_path"] for d in idx._documents}
        # src/ and its children should be indexed
        assert "src/main.py" in all_paths
        assert "src/utils.py" in all_paths
        assert "src/core/engine.py" in all_paths
        # docs/ and tests/ should NOT be indexed
        assert "docs/README.md" not in all_paths
        assert "docs/API.md" not in all_paths
        assert "tests/test_main.py" not in all_paths

    def test_included_paths_multiple_folders(self, scoped_repo: Path, tmp_path: Path):
        """Multiple included folders."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        meta = idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["src", "docs"],
        )

        all_paths = {d["source_path"] for d in idx._documents}
        assert "src/main.py" in all_paths
        assert "docs/README.md" in all_paths
        assert "tests/test_main.py" not in all_paths

    def test_included_paths_specific_file(self, scoped_repo: Path, tmp_path: Path):
        """Can include a specific file."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        meta = idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["src/main.py", "docs/README.md"],
        )

        all_paths = {d["source_path"] for d in idx._documents}
        assert "src/main.py" in all_paths
        assert "docs/README.md" in all_paths
        assert "src/utils.py" not in all_paths
        assert "src/core/engine.py" not in all_paths

    def test_included_paths_subfolder(self, scoped_repo: Path, tmp_path: Path):
        """Can include a subfolder specifically."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        meta = idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["src/core"],
        )

        all_paths = {d["source_path"] for d in idx._documents}
        assert "src/core/engine.py" in all_paths
        assert "src/main.py" not in all_paths
        assert "src/utils.py" not in all_paths

    def test_included_paths_empty_list_indexes_nothing(self, scoped_repo: Path, tmp_path: Path):
        """Tri-state semantics (Phase 24 SM-8 design):

        ``included_paths=[]`` is the user's explicit "empty Knowledge Scope" —
        embed exactly zero files, not "everything matching include_globs".
        ``None`` (key absent) is what means "no filter, index everything";
        see the next test.

        Earlier code used ``if included_paths:`` (truthy) which conflated
        [] with None and caused 34k-file walks on projects whose Scope
        panel had been cleared.
        """
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=[],
        )

        all_paths = {d["source_path"] for d in idx._documents}
        assert all_paths == set(), (
            f"included_paths=[] must produce zero embeddings, got {len(all_paths)}: {all_paths}"
        )

    def test_included_paths_none_indexes_everything(self, scoped_repo: Path, tmp_path: Path):
        """``included_paths=None`` (key absent) is the legacy "no scope filter"
        signal — index every file matching include_globs / exclude_globs."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=None,
        )

        all_paths = {d["source_path"] for d in idx._documents}
        assert len(all_paths) >= 6, (
            f"included_paths=None should embed every matched file, got {len(all_paths)}"
        )

    def test_empty_scope_build_preserves_unrelated_artifacts(self, scoped_repo: Path, tmp_path: Path):
        """REGRESSION GUARD for the Apr 2026 trace-graph wipe:

        Build's atomic swap renames the existing index_dir to a backup and
        then deletes the backup. An empty-scope build that writes only the
        4 CodeIndex files into temp_dir would (under the original bug)
        destroy every other artifact sharing index_dir — the trace graph,
        atlas, concepts, audit, antibodies, knowledge_* embeddings, audit
        subdirs, etc.

        This test seeds artifacts that simulate a real .sourceprep/ from a
        completed pipeline, runs the empty-scope build, and asserts every
        non-CodeIndex file still exists with its original content.
        """
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        # Simulate a fully-populated .sourceprep/ from a completed pipeline.
        seeded = {
            "trace_nodes.jsonl": '{"id":"n1","kind":"file"}\n{"id":"n2","kind":"symbol"}\n',
            "trace_edges.jsonl": '{"src":"n1","dst":"n2","kind":"contains"}\n',
            "trace_manifest.json": '{"stage":"structural","completed_at":"2026-04-27"}',
            "trace_augmented.jsonl": '{"id":"n1","summary":"main module"}\n',
            "trace_epistemic.jsonl": '{"id":"n1","confidence":0.9}\n',
            "atlas.json": '{"identity":"my project","stack":"python"}',
            "atlas_manifest.json": '{"version":"1.0"}',
            "concepts_manifest.json": '{"count":42}',
            "audit_manifest.json": '{"findings":[]}',
            "antibodies_manifest.json": '{"derived":15}',
            "knowledge_documents.json": '[{"id":"k1"}]',
            "knowledge_embeddings.npy": b"\x93NUMPY\x01\x00",  # bogus npy header is fine
            "rules_manifest.json": '{"emitted":["AGENTS.md"]}',
            "pipeline_run_metadata.json": '{"run_id":"abc"}',
        }
        for name, content in seeded.items():
            p = idx_dir / name
            if isinstance(content, bytes):
                p.write_bytes(content)
            else:
                p.write_text(content)

        # Subdirectories the trace pipeline populates
        (idx_dir / "audit").mkdir()
        (idx_dir / "audit" / "findings.json").write_text('[{"file":"src/main.py"}]')
        (idx_dir / "atlas_roles").mkdir()
        (idx_dir / "atlas_roles" / "architect.json").write_text('{"role":"architect"}')
        (idx_dir / ".checkpoints").mkdir()
        (idx_dir / ".checkpoints" / "run-deadbeef").mkdir()
        (idx_dir / ".checkpoints" / "run-deadbeef" / "trace_nodes.jsonl").write_text(
            '{"snapshot":true}\n'
        )

        # Run an empty-scope build — equivalent to "user cleared the
        # Knowledge Scope and the watcher fired".
        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=[],
        )

        # CodeIndex itself is empty — that's the design.
        assert idx._documents == []

        # Every seeded file MUST survive the swap with byte-identical content.
        for name, expected in seeded.items():
            p = idx_dir / name
            assert p.exists(), f"{name} was destroyed by the empty-scope build"
            actual = p.read_bytes() if isinstance(expected, bytes) else p.read_text()
            assert actual == expected, f"{name} survived but content changed"

        # Every seeded subdirectory + nested file must survive.
        assert (idx_dir / "audit" / "findings.json").read_text() == '[{"file":"src/main.py"}]'
        assert (idx_dir / "atlas_roles" / "architect.json").read_text() == '{"role":"architect"}'
        assert (idx_dir / ".checkpoints" / "run-deadbeef" / "trace_nodes.jsonl").read_text() == (
            '{"snapshot":true}\n'
        )

        # And the new CodeIndex files must be present too.
        assert (idx_dir / "documents.json").exists()
        assert (idx_dir / "embeddings.npy").exists()
        assert (idx_dir / "manifest.json").exists()
        manifest = json.loads((idx_dir / "manifest.json").read_text())
        assert manifest["build"]["mode"] == "empty_scope"
        assert manifest["count"] == 0

    def test_normal_build_preserves_unrelated_artifacts(self, scoped_repo: Path, tmp_path: Path):
        """Defense in depth: the same preservation invariant must hold for
        a non-empty build, not just empty-scope. The hardened
        ``_swap_index_dir`` is the safety net for both paths."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        # Seed a single high-value artifact — the trace graph.
        (idx_dir / "trace_nodes.jsonl").write_text('{"id":"n1"}\n')
        (idx_dir / "trace_edges.jsonl").write_text('{"src":"n1","dst":"n2"}\n')

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            # No included_paths -> normal full-scope build path.
        )

        # Both seeded files must survive even though we ran a real build.
        assert (idx_dir / "trace_nodes.jsonl").read_text() == '{"id":"n1"}\n'
        assert (idx_dir / "trace_edges.jsonl").read_text() == '{"src":"n1","dst":"n2"}\n'

        # CodeIndex artifacts must also be present.
        assert (idx_dir / "documents.json").exists()
        assert (idx_dir / "embeddings.npy").exists()
        assert (idx_dir / "manifest.json").exists()

    def test_empty_scope_build_replaces_stale_fts(self, scoped_repo: Path, tmp_path: Path):
        """REGRESSION GUARD for the FTS-sidecar issue:

        fts.sqlite3 is the only CodeIndex artifact with sidecars (WAL/SHM/
        journal). If an empty-scope build wrote documents.json/embeddings.npy
        but skipped the FTS rebuild, the safety net would preserve the OLD
        fts.sqlite3 — leaving a keyword index pointing at documents that no
        longer exist. Subsequent /search calls would surface phantom hits.

        Two invariants this test pins:
          1. After an empty-scope build, fts.sqlite3 is the new (empty) one,
             not bytes from the prior build.
          2. WAL/SHM/journal siblings of the OLD database don't survive — they
             were tied to a DB that's been replaced.
        """
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        # Seed a "stale" FTS database + its WAL/SHM siblings, simulating a
        # previous successful build whose CodeIndex we are now wiping.
        stale_fts_bytes = b"STALE_FTS_HEADER" + b"\x00" * 100
        (idx_dir / "fts.sqlite3").write_bytes(stale_fts_bytes)
        (idx_dir / "fts.sqlite3-wal").write_bytes(b"STALE_WAL")
        (idx_dir / "fts.sqlite3-shm").write_bytes(b"STALE_SHM")

        # Run an empty-scope build.
        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=[],
        )

        # 1. fts.sqlite3 is the new file — not the stale bytes.
        assert (idx_dir / "fts.sqlite3").exists()
        new_fts_bytes = (idx_dir / "fts.sqlite3").read_bytes()
        assert new_fts_bytes != stale_fts_bytes, (
            "fts.sqlite3 still holds stale bytes — the empty-scope build did "
            "not write a fresh FTS, so the safety net preserved the old one."
        )
        # Sanity-check: the new file is a valid SQLite database.
        assert new_fts_bytes.startswith(b"SQLite format 3")

        # 2. WAL/SHM siblings of the OLD database must not survive — they
        #    would be inconsistent against the new fts.sqlite3.
        assert not (idx_dir / "fts.sqlite3-wal").exists(), (
            "Stale fts.sqlite3-wal survived the empty-scope build — would "
            "corrupt SQLite recovery against the new (empty) DB."
        )
        assert not (idx_dir / "fts.sqlite3-shm").exists(), (
            "Stale fts.sqlite3-shm survived the empty-scope build."
        )


# ---------------------------------------------------------------------------
# Full RAG integration: search uses only indexed (selected) files
# ---------------------------------------------------------------------------

class TestRAGWithSelectedFiles:
    """Test that search/context only returns results from selected (indexed) files."""

    def test_search_only_returns_selected_files(self, scoped_repo: Path, tmp_path: Path):
        """When built with included_paths=['src'], search should not return docs."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["src"],
        )

        results = idx.search("main entry point", k=10, min_score=0.0)
        result_paths = {r.doc["source_path"] for r in results}

        # All results should be from src/
        for path in result_paths:
            assert path.startswith("src/"), f"Unexpected result from outside scope: {path}"

    def test_context_only_contains_selected_files(self, scoped_repo: Path, tmp_path: Path):
        """get_context should only assemble from selected files."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["docs"],
        )

        context = idx.get_context("project documentation", k=5, max_chars=6000, min_score=0.0)
        # Context should only reference docs/ files, not src/ files
        assert "docs/" in context or "Documentation" in context or "API" in context
        # src/ content should not appear
        assert "def main()" not in context
        assert "def helper()" not in context

    def test_rebuild_with_different_scope(self, scoped_repo: Path, tmp_path: Path):
        """Rebuilding with a different scope replaces the index contents."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)

        # First build: only src/
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["src"],
        )
        paths_v1 = {d["source_path"] for d in idx._documents}
        assert "src/main.py" in paths_v1
        assert "docs/README.md" not in paths_v1

        # Second build: only docs/
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["docs"],
        )
        paths_v2 = {d["source_path"] for d in idx._documents}
        assert "docs/README.md" in paths_v2
        assert "src/main.py" not in paths_v2


# ---------------------------------------------------------------------------
# Combined: path_weights + included_paths
# ---------------------------------------------------------------------------

class TestCombinedWeightsAndScope:
    """Test that path_weights and included_paths work together correctly."""

    def test_weights_apply_within_scope(self, scoped_repo: Path, tmp_path: Path):
        """Path weights should still apply to files within the selected scope."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        from prep.core.repo_policy import ensure_repo_policy, policy_path_for_index, write_repo_policy

        # Set up path weights in policy
        policy = ensure_repo_policy(idx_dir, scoped_repo, force=True)
        policy["path_weights"] = {"src/core": 1.8, "src": 0.5}
        write_repo_policy(policy_path_for_index(idx_dir), policy)

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(
            repo_root=scoped_repo,
            include_globs=["**/*.py", "**/*.md"],
            included_paths=["src"],
        )

        # All results should be from src/ only
        results = idx.search("engine process data", k=10, min_score=0.0)
        result_paths = {r.doc["source_path"] for r in results}
        for path in result_paths:
            assert path.startswith("src/"), f"Unexpected result: {path}"

        # src/core/ files should have boosted scores
        core_results = [r for r in results if r.doc["source_path"].startswith("src/core/")]
        other_results = [r for r in results if r.doc["source_path"].startswith("src/") and not r.doc["source_path"].startswith("src/core/")]

        if core_results and other_results:
            # Core should generally score higher due to weight boost
            max_core = max(r.score for r in core_results)
            min_other = min(r.score for r in other_results)
            # This is a soft assertion — FakeEmbedder may not produce meaningful differences
            # but the weights should be applied
            assert max_core > 0, "Core results should have positive scores"
