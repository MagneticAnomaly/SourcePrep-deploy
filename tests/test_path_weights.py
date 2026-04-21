"""
Tests for user-defined path weights feature.

Covers:
- _normalize_path_weights validation and clamping
- _resolve_path_weight hierarchical lookup
- path_weights persisted in repo_policy.json
- path_weights stored in manifest config during build
- path_weights applied at search time (score multiplier)

Uses FakeEmbedder so no Ollama dependency is required.
Run with: pytest tests/test_path_weights.py -v
"""

import json
import tempfile
from pathlib import Path

import pytest

from prep.core import CodeIndex, FakeEmbedder
from prep.core.index import CodeIndex as _CI
from prep.core.repo_policy import (
    _normalize_path_weights,
    ensure_repo_policy,
    load_repo_policy,
    policy_path_for_index,
    write_repo_policy,
)


# ---------------------------------------------------------------------------
# _normalize_path_weights
# ---------------------------------------------------------------------------

class TestNormalizePathWeights:
    def test_empty_dict(self):
        assert _normalize_path_weights({}) == {}

    def test_none_returns_empty(self):
        assert _normalize_path_weights(None) == {}

    def test_non_dict_returns_empty(self):
        assert _normalize_path_weights("bad") == {}
        assert _normalize_path_weights([1, 2]) == {}

    def test_valid_entries(self):
        result = _normalize_path_weights({"src": 1.5, "docs": 0.5})
        assert result == {"src": 1.5, "docs": 0.5}

    def test_clamps_to_range(self):
        result = _normalize_path_weights({"a": -0.5, "b": 3.0})
        assert result["a"] == 0.0
        assert result["b"] == 2.0

    def test_strips_slashes(self):
        result = _normalize_path_weights({"/src/core/": 1.2})
        assert "src/core" in result

    def test_strips_whitespace_keys(self):
        result = _normalize_path_weights({"  docs  ": 0.8})
        assert "docs" in result

    def test_skips_empty_keys(self):
        result = _normalize_path_weights({"": 1.0, "  ": 0.5})
        assert result == {}

    def test_skips_non_string_keys(self):
        result = _normalize_path_weights({123: 1.0, None: 0.5})
        assert result == {}

    def test_skips_non_numeric_values(self):
        result = _normalize_path_weights({"src": "bad", "docs": 0.5})
        assert result == {"docs": 0.5}

    def test_rounds_to_2_decimal(self):
        result = _normalize_path_weights({"src": 1.123456})
        assert result["src"] == 1.12


# ---------------------------------------------------------------------------
# _resolve_path_weight (static method on CodeIndex)
# ---------------------------------------------------------------------------

class TestResolvePathWeight:
    resolve = staticmethod(_CI._resolve_path_weight)

    def test_exact_file_match(self):
        pw = {"src/main.py": 0.5}
        assert self.resolve("src/main.py", pw) == 0.5

    def test_folder_propagates(self):
        pw = {"src": 1.5}
        assert self.resolve("src/main.py", pw) == 1.5
        assert self.resolve("src/core/index.py", pw) == 1.5

    def test_child_overrides_parent(self):
        pw = {"src": 0.5, "src/core": 1.8}
        assert self.resolve("src/utils.py", pw) == 0.5
        assert self.resolve("src/core/index.py", pw) == 1.8

    def test_file_overrides_folder(self):
        pw = {"docs": 0.5, "docs/ARCHITECTURE.md": 1.2}
        assert self.resolve("docs/API.md", pw) == 0.5
        assert self.resolve("docs/ARCHITECTURE.md", pw) == 1.2

    def test_no_match_returns_1(self):
        pw = {"src": 0.5}
        assert self.resolve("tests/test_foo.py", pw) == 1.0

    def test_empty_weights_returns_1(self):
        assert self.resolve("src/main.py", {}) == 1.0

    def test_deep_nesting(self):
        pw = {"a": 0.3}
        assert self.resolve("a/b/c/d/e.py", pw) == 0.3

    def test_most_specific_wins(self):
        pw = {"a": 0.1, "a/b": 0.5, "a/b/c": 0.9}
        assert self.resolve("a/b/c/d.py", pw) == 0.9
        assert self.resolve("a/b/x.py", pw) == 0.5
        assert self.resolve("a/y.py", pw) == 0.1


# ---------------------------------------------------------------------------
# Policy persistence
# ---------------------------------------------------------------------------

class TestPolicyPersistence:
    def test_path_weights_in_new_policy(self, tmp_path: Path):
        """ensure_repo_policy includes path_weights key (empty for new repos)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("x = 1\n")

        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        policy = ensure_repo_policy(idx_dir, repo, force=True)
        assert "path_weights" in policy
        assert isinstance(policy["path_weights"], dict)

    def test_path_weights_roundtrip(self, tmp_path: Path):
        """Write path_weights to policy, reload, verify they survive."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("x = 1\n")

        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        policy = ensure_repo_policy(idx_dir, repo, force=True)
        policy["path_weights"] = {"src": 0.5, "docs": 1.5}

        pp = policy_path_for_index(idx_dir)
        write_repo_policy(pp, policy)

        reloaded = load_repo_policy(pp)
        assert reloaded is not None
        assert reloaded["path_weights"] == {"src": 0.5, "docs": 1.5}

    def test_ensure_normalizes_existing_path_weights(self, tmp_path: Path):
        """ensure_repo_policy normalizes path_weights on existing policy."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("x = 1\n")

        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        # Create initial policy
        policy = ensure_repo_policy(idx_dir, repo, force=True)
        # Manually write bad path_weights
        policy["path_weights"] = {"/src/": 3.0, "": 1.0, "docs": "bad"}
        pp = policy_path_for_index(idx_dir)
        write_repo_policy(pp, policy)

        # Reload — should normalize
        reloaded = ensure_repo_policy(idx_dir, repo, force=False)
        pw = reloaded["path_weights"]
        assert "src" in pw
        assert pw["src"] == 2.0  # clamped
        assert "" not in pw  # empty key dropped
        assert "docs" not in pw  # non-numeric dropped


# ---------------------------------------------------------------------------
# Build + Search integration
# ---------------------------------------------------------------------------

@pytest.fixture
def weighted_repo(tmp_path: Path) -> Path:
    """Create a test repo with files in different folders."""
    repo = tmp_path / "repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text(
        'def main():\n    """Main entry point for the application."""\n    return "hello"\n'
    )
    (src / "utils.py").write_text(
        'def helper():\n    """Helper utility function."""\n    return 42\n'
    )

    docs = repo / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "# Documentation\n\nThis is the main documentation for the project.\n"
    )

    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text(
        'def test_main():\n    """Test main function."""\n    assert True\n'
    )

    return repo


class TestBuildStoresPathWeights:
    def test_manifest_contains_path_weights(self, weighted_repo: Path, tmp_path: Path):
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        # Set path_weights in policy before build
        policy = ensure_repo_policy(idx_dir, weighted_repo, force=True)
        policy["path_weights"] = {"docs": 0.5, "src": 1.5}
        write_repo_policy(policy_path_for_index(idx_dir), policy)

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=weighted_repo)

        manifest = idx._manifest
        assert manifest is not None
        config = manifest.get("config", {})
        assert config.get("path_weights") == {"docs": 0.5, "src": 1.5}


class TestSearchAppliesPathWeights:
    def test_boosted_folder_ranks_higher(self, weighted_repo: Path, tmp_path: Path):
        """Files in a boosted folder should score higher than equivalent files."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        # Build without weights first
        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=weighted_repo)

        # Get baseline scores
        baseline_results = idx.search("main entry point", k=10, min_score=0.0)
        baseline_by_path = {r.doc["source_path"]: r.score for r in baseline_results}

        # Now set path_weights: boost src, de-emphasize docs
        config = idx._manifest.get("config", {})
        config["path_weights"] = {"src": 1.8, "docs": 0.3}

        # Re-search with weights
        weighted_results = idx.search("main entry point", k=10, min_score=0.0)
        weighted_by_path = {r.doc["source_path"]: r.score for r in weighted_results}

        # src files should be boosted relative to baseline
        for path, score in weighted_by_path.items():
            baseline_score = baseline_by_path.get(path, 0.0)
            if path.startswith("src/"):
                assert score >= baseline_score * 1.5, \
                    f"src file {path} should be boosted: {score} vs baseline {baseline_score}"
            elif path.startswith("docs/"):
                assert score <= baseline_score * 0.5, \
                    f"docs file {path} should be de-emphasized: {score} vs baseline {baseline_score}"

    def test_zero_weight_effectively_excludes(self, weighted_repo: Path, tmp_path: Path):
        """A weight of 0.0 should zero out the score, effectively excluding results."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=weighted_repo)

        # Zero out tests folder
        config = idx._manifest.get("config", {})
        config["path_weights"] = {"tests": 0.0}

        results = idx.search("test main", k=10, min_score=0.01)
        test_results = [r for r in results if r.doc["source_path"].startswith("tests/")]
        assert all(r.score < 0.01 for r in test_results), \
            "test files with weight 0.0 should have near-zero scores"
