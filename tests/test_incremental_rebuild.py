"""
Tests for incremental rebuild (S-03.2).

Covers:
- file_hashes stored in manifest
- Cold-start incremental (daemon restart reuses unchanged chunks)
- Deleted file detection (removed files don't carry over)
- Noop detection (nothing changed → mode="noop")

Uses FakeEmbedder so no Ollama/ONNX dependency required.
Run with: pytest tests/test_incremental_rebuild.py -v
"""

import json
from pathlib import Path

import pytest

from prep.core import CodeIndex, FakeEmbedder
from prep.core.manifest import read_manifest


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a test repo with a few files."""
    repo = tmp_path / "repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text('def main():\n    return "hello"\n')
    (src / "utils.py").write_text('def helper():\n    return 42\n')

    docs = repo / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# My Project\n\nThis is the readme.\n")

    return repo


class TestFileHashesInManifest:
    def test_manifest_contains_file_hashes(self, repo: Path, tmp_path: Path):
        """Build should store per-file hashes in manifest."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo)

        manifest = read_manifest(idx_dir / "manifest.json")
        assert "file_hashes" in manifest
        fh = manifest["file_hashes"]
        assert isinstance(fh, dict)
        assert len(fh) > 0

        # Should have entries for our files
        assert "src/main.py" in fh
        assert "src/utils.py" in fh
        assert "docs/README.md" in fh

        # Hashes should be non-empty strings
        for path, h in fh.items():
            assert isinstance(h, str)
            assert len(h) > 0

    def test_file_hashes_change_on_content_change(self, repo: Path, tmp_path: Path):
        """File hash should change when content changes."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo)

        manifest1 = read_manifest(idx_dir / "manifest.json")
        hash1 = manifest1["file_hashes"]["src/main.py"]

        # Modify a file
        (repo / "src" / "main.py").write_text('def main():\n    return "world"\n')
        idx.build(repo_root=repo)

        manifest2 = read_manifest(idx_dir / "manifest.json")
        hash2 = manifest2["file_hashes"]["src/main.py"]

        assert hash1 != hash2, "Hash should change when file content changes"

        # Unchanged file should keep same hash
        assert manifest1["file_hashes"]["src/utils.py"] == manifest2["file_hashes"]["src/utils.py"]


class TestIncrementalBuild:
    def test_incremental_reuses_unchanged_files(self, repo: Path, tmp_path: Path):
        """Second build with one changed file should reuse unchanged chunks."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        manifest1 = idx.build(repo_root=repo)

        # Modify one file
        (repo / "src" / "main.py").write_text('def main():\n    return "modified"\n')
        manifest2 = idx.build(repo_root=repo)

        build = manifest2.get("build", {})
        assert build["mode"] == "incremental"
        assert build["files_reused"] > 0, "Should reuse unchanged files"
        assert build["files_embedded"] > 0, "Should re-embed changed file"

    def test_noop_when_nothing_changed(self, repo: Path, tmp_path: Path):
        """Rebuild with no changes should report mode='noop'."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo)

        # Rebuild without changes
        manifest2 = idx.build(repo_root=repo)
        build = manifest2.get("build", {})
        assert build["mode"] == "noop", "No changes should yield noop mode"
        assert build["files_reused"] == build["files_total"]
        assert build["files_embedded"] == 0


class TestColdStartIncremental:
    def test_cold_start_reuses_unchanged_chunks(self, repo: Path, tmp_path: Path):
        """After loading a fresh CodeIndex (simulating restart), incremental should still work."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo)

        # Simulate daemon restart: create new CodeIndex, only load manifest (not full docs)
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        # Don't call idx2.load() — just read the manifest
        manifest_path = idx_dir / "manifest.json"
        assert manifest_path.exists()
        idx2._manifest = read_manifest(manifest_path)

        # Modify one file
        (repo / "src" / "main.py").write_text('def main():\n    return "cold-start-modified"\n')

        # Build should detect unchanged files via manifest file_hashes
        manifest2 = idx2.build(repo_root=repo)
        build = manifest2.get("build", {})
        assert build["files_reused"] > 0, "Cold-start should reuse unchanged files"
        assert build["files_embedded"] > 0, "Changed file should be re-embedded"
        assert build["mode"] == "incremental"


class TestDeletedFileDetection:
    def test_deleted_file_not_carried_over(self, repo: Path, tmp_path: Path):
        """Chunks from deleted files should not appear in rebuilt index."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo)

        # Verify utils.py is indexed (check documents directly, not search similarity)
        docs1 = idx._documents or []
        has_utils = any("utils.py" in str(d.get("source_path", "")) for d in docs1)
        assert has_utils, "utils.py should be in the index"

        # Delete the file
        (repo / "src" / "utils.py").unlink()

        # Rebuild
        manifest2 = idx.build(repo_root=repo)
        build = manifest2.get("build", {})
        assert build["files_deleted"] >= 1, "Should detect deleted file"

        # Verify utils.py chunks are gone (check documents directly)
        docs2 = idx._documents or []
        has_utils_after = any("utils.py" in str(d.get("source_path", "")) for d in docs2)
        assert not has_utils_after, "Deleted file chunks should not be in rebuilt index"

        # File hashes should not include deleted file
        fh = manifest2.get("file_hashes", {})
        assert "src/utils.py" not in fh

    def test_deleted_file_count_accurate(self, repo: Path, tmp_path: Path):
        """files_deleted should accurately count removed files."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo)

        # Delete two files
        (repo / "src" / "main.py").unlink()
        (repo / "src" / "utils.py").unlink()

        manifest2 = idx.build(repo_root=repo)
        build = manifest2.get("build", {})
        assert build["files_deleted"] == 2
