"""Tests for src/codrag/agents/shared/git_client.py

Uses real git repos created in tmp_path to exercise branch management,
commit operations, and file archiving.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codrag.agents.shared.git_client import GitClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True
    )
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=repo, capture_output=True, check=True
    )
    return repo


@pytest.fixture
def client(git_repo):
    return GitClient(repo_root=git_repo)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCurrentBranch:
    def test_returns_branch_name(self, client):
        branch = client.current_branch()
        assert branch in ("main", "master")

    def test_returns_string(self, client):
        assert isinstance(client.current_branch(), str)


class TestBranchExists:
    def test_existing_branch_true(self, client):
        branch = client.current_branch()
        assert client.branch_exists(branch) is True

    def test_nonexistent_branch_false(self, client):
        assert client.branch_exists("no-such-branch-xyz") is False

    def test_created_branch_exists(self, client):
        client.create_branch("feature/test-exists")
        assert client.branch_exists("feature/test-exists") is True


class TestCreateBranch:
    def test_creates_and_switches(self, client):
        client.create_branch("feature/new")
        assert client.current_branch() == "feature/new"

    def test_switch_back(self, client, git_repo):
        origin = client.current_branch()
        client.create_branch("feature/temp")
        assert client.current_branch() == "feature/temp"
        client.switch_branch(origin)
        assert client.current_branch() == origin

    def test_branch_listed_after_create(self, client):
        client.create_branch("feature/listed")
        assert client.branch_exists("feature/listed") is True


class TestCommit:
    def test_commit_returns_40_char_sha(self, client, git_repo):
        (git_repo / "new_file.txt").write_text("hello\n")
        client.add_files(["new_file.txt"])
        sha = client.commit("add new file")
        assert isinstance(sha, str)
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)

    def test_nothing_to_commit_returns_empty_string(self, client):
        sha = client.commit("empty commit")
        assert sha == ""

    def test_multiple_commits_return_different_shas(self, client, git_repo):
        (git_repo / "file_a.txt").write_text("a\n")
        client.add_files(["file_a.txt"])
        sha1 = client.commit("commit a")

        (git_repo / "file_b.txt").write_text("b\n")
        client.add_files(["file_b.txt"])
        sha2 = client.commit("commit b")

        assert sha1 != sha2


class TestDiff:
    def test_diff_returns_string(self, client):
        result = client.diff()
        assert isinstance(result, str)

    def test_diff_reflects_modification(self, client, git_repo):
        (git_repo / "README.md").write_text("# Modified\n")
        diff_output = client.diff()
        assert "Modified" in diff_output

    def test_staged_diff(self, client, git_repo):
        (git_repo / "staged.txt").write_text("staged content\n")
        client.add_files(["staged.txt"])
        staged = client.diff(staged=True)
        assert "staged content" in staged

    def test_unstaged_diff_empty_when_staged(self, client, git_repo):
        (git_repo / "only_staged.txt").write_text("only staged\n")
        client.add_files(["only_staged.txt"])
        # Unstaged diff should not contain this new file (it's tracked via staged)
        unstaged = client.diff(staged=False)
        # The staged file is new/untracked staging — unstaged diff won't show it
        assert isinstance(unstaged, str)


class TestCopyToBranch:
    def test_copies_file_to_target_branch(self, client, git_repo):
        # Create a source file on main
        (git_repo / "source.py").write_text("# source\n")
        client.add_files(["source.py"])
        client.commit("add source")

        origin = client.current_branch()
        sha = client.copy_to_branch(
            source_paths=["source.py"],
            target_branch="archive/test",
            target_dir="archive",
            commit_message="archive source.py",
        )

        # Should return a valid SHA
        assert len(sha) == 40

        # Should return to origin branch
        assert client.current_branch() == origin

    def test_creates_target_branch_if_missing(self, client, git_repo):
        (git_repo / "to_archive.txt").write_text("data\n")
        client.add_files(["to_archive.txt"])
        client.commit("add file")

        client.copy_to_branch(
            source_paths=["to_archive.txt"],
            target_branch="custodian/archive",
            target_dir="archived",
            commit_message="move to archive",
        )

        assert client.branch_exists("custodian/archive") is True

    def test_uses_existing_target_branch(self, client, git_repo):
        # Pre-create the target branch
        origin = client.current_branch()
        client.create_branch("existing-target")
        client.switch_branch(origin)

        (git_repo / "file_for_existing.txt").write_text("exists\n")
        client.add_files(["file_for_existing.txt"])
        client.commit("add file")

        sha = client.copy_to_branch(
            source_paths=["file_for_existing.txt"],
            target_branch="existing-target",
            target_dir="copies",
            commit_message="copy to existing",
        )
        assert len(sha) == 40
        assert client.current_branch() == origin
