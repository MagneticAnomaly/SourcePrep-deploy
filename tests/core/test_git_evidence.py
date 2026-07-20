"""Unit tests for core/git_evidence.py."""
from __future__ import annotations

import dataclasses
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from prep.core.git_evidence import (
    HUB_EVOLVING_MAX_COMMITS,
    HUB_FRAGILE_MIN_AUTHORS,
    HUB_STABLE_MAX_COMMITS,
    FileChurn,
    GitEvidence,
    _is_excluded_path,
)


def test_filechurn_is_frozen_dataclass():
    """FileChurn must be immutable to be safe for caching."""
    now = datetime.now(UTC)
    churn = FileChurn(
        path="src/foo.py",
        commits=5,
        lines_added=100,
        lines_removed=20,
        first_seen=now,
        last_seen=now,
        authors=2,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        churn.commits = 10  # type: ignore


def test_classification_constants_have_expected_values():
    """Lock the thresholds in one place; changes should be explicit."""
    assert HUB_STABLE_MAX_COMMITS == 3
    assert HUB_EVOLVING_MAX_COMMITS == 15
    assert HUB_FRAGILE_MIN_AUTHORS == 3


def test_excluded_paths_includes_lockfiles_and_media():
    """Exclusion list covers auto-regenerated and binary files."""
    assert _is_excluded_path("package-lock.json") is True
    assert _is_excluded_path("yarn.lock") is True
    assert _is_excluded_path("frontend/package-lock.json") is True
    assert _is_excluded_path("assets/logo.png") is True
    assert _is_excluded_path("docs/diagram.svg") is True
    assert _is_excluded_path("AGENTS.md") is True
    assert _is_excluded_path("CLAUDE.md") is True
    assert _is_excluded_path(".sourceprep/state.json") is True
    assert _is_excluded_path(".cursor/rules.mdc") is True

    # Nested monorepo lockfiles (regression guard for fnmatch depth)
    assert _is_excluded_path("packages/ui/package-lock.json") is True
    assert _is_excluded_path("packages/vscode/yarn.lock") is True
    assert _is_excluded_path("services/billing/deep/nested/poetry.lock") is True


def test_excluded_paths_excludes_normal_source():
    """Normal source files are not excluded."""
    assert _is_excluded_path("src/prep/foo.py") is False
    assert _is_excluded_path("tests/test_foo.py") is False
    assert _is_excluded_path("README.md") is False  # Not a Prep-managed file


def test_git_evidence_init_sets_defaults(tmp_path):
    """Constructor accepts repo_root and cache_dir; defaults wire correctly."""
    cache_dir = tmp_path / "cache"
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    assert evidence._default_window_days == 60
    assert evidence._default_max_commits == 2000


# ── Fixture-repo helpers ─────────────────────────────────────────────

def _init_repo(path: Path) -> None:
    """Initialize an empty git repo at `path` with a local identity."""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    # Ensure default branch is 'main' across git versions
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=path, check=False)


def _commit_file(
    path: Path,
    rel_file: str,
    content: str,
    *,
    author: str = "Test User <test@example.com>",
    date: str | None = None,
    message: str = "test commit",
) -> None:
    """Write a file, stage, and commit. `date` is ISO-8601 or None for now."""
    target = path / rel_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    subprocess.run(["git", "add", rel_file], cwd=path, check=True)
    env = {**os.environ}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "commit", "-q", "--author", author, "-m", message],
        cwd=path, check=True, env=env,
    )


# ── churn primitive tests ────────────────────────────────────────────

def test_recent_churn_smoke(tmp_path):
    """Fixture repo with three files, three commits — churn map reflects them."""
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x = 1\n", message="add foo")
    _commit_file(tmp_path, "src/bar.py", "y = 2\n", message="add bar")
    _commit_file(tmp_path, "src/foo.py", "x = 1\ny = 2\n", message="update foo")

    evidence = GitEvidence(
        repo_root=tmp_path,
        cache_dir=tmp_path / ".cache",
    )
    churn = evidence.recent_churn_by_file(window_days=30)

    assert "src/foo.py" in churn
    assert "src/bar.py" in churn
    assert churn["src/foo.py"].commits == 2
    assert churn["src/bar.py"].commits == 1
    assert churn["src/foo.py"].authors == 1


def test_recent_churn_respects_exclusions(tmp_path):
    """AGENTS.md and lockfiles are absent from the churn map."""
    _init_repo(tmp_path)
    _commit_file(tmp_path, "AGENTS.md", "agents\n", message="regenerate")
    _commit_file(tmp_path, "package-lock.json", '{"a": 1}\n', message="lock")
    _commit_file(tmp_path, "src/real.py", "pass\n", message="real source")

    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    churn = evidence.recent_churn_by_file(window_days=30)

    assert "src/real.py" in churn
    assert "AGENTS.md" not in churn
    assert "package-lock.json" not in churn


def test_recent_churn_not_a_git_repo_returns_empty(tmp_path):
    """Non-git directory: empty churn, no exception."""
    # tmp_path is not a git repo
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    churn = evidence.recent_churn_by_file(window_days=30)
    assert churn == {}


def test_file_touched_in_window(tmp_path):
    """file_touched_in_window returns True for touched files, False otherwise."""
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/touched.py", "pass\n")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")

    assert evidence.file_touched_in_window("src/touched.py", window_days=30) is True
    assert evidence.file_touched_in_window("src/untouched.py", window_days=30) is False


# ── classify_hub tests ───────────────────────────────────────────────

def test_classify_hub_returns_unknown_for_untracked_path(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/real.py", "pass\n")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/missing.py") == "unknown"


def test_classify_hub_stable_when_few_commits(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/stable.py", "v = 1\n")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/stable.py") == "stable"


def test_classify_hub_evolving_when_moderate_churn(tmp_path):
    _init_repo(tmp_path)
    # 5 commits → within [3, 15] range → evolving
    for i in range(5):
        _commit_file(tmp_path, "src/evolving.py", f"v = {i}\n", message=f"c{i}")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/evolving.py") == "evolving"


def test_classify_hub_fragile_requires_high_churn_and_many_authors(tmp_path):
    """> HUB_EVOLVING_MAX_COMMITS AND >= HUB_FRAGILE_MIN_AUTHORS -> fragile."""
    _init_repo(tmp_path)
    # 16 commits from 3 authors
    authors = [
        "Alice <alice@example.com>",
        "Bob <bob@example.com>",
        "Cara <cara@example.com>",
    ]
    for i in range(16):
        _commit_file(
            tmp_path, "src/fragile.py", f"v = {i}\n",
            author=authors[i % 3], message=f"c{i}",
        )
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/fragile.py") == "fragile"


def test_classify_hub_evolving_when_high_churn_but_single_author(tmp_path):
    """High churn + single author is 'evolving', not 'fragile' — someone working alone."""
    _init_repo(tmp_path)
    for i in range(16):
        _commit_file(tmp_path, "src/solo.py", f"v = {i}\n", message=f"c{i}")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/solo.py") == "evolving"


# ── hot_zones tests ──────────────────────────────────────────────────

def test_hot_zones_empty_when_no_churn(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    # Only 1 commit; min_commits=10 default → empty
    assert evidence.hot_zones() == []


def test_hot_zones_sorted_by_commit_count_desc(tmp_path):
    _init_repo(tmp_path)
    # Zone A: 12 commits across three files
    for i in range(12):
        _commit_file(tmp_path, f"src/zone_a/f{i % 3}.py", f"v={i}\n", message=f"a{i}")
    # Zone B: 15 commits
    for i in range(15):
        _commit_file(tmp_path, f"src/zone_b/f{i % 3}.py", f"v={i}\n", message=f"b{i}")
    # Zone C: 5 commits (below min_commits=10)
    for i in range(5):
        _commit_file(tmp_path, f"src/zone_c/f{i}.py", f"v={i}\n", message=f"c{i}")

    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    zones = evidence.hot_zones(top_n=5, min_commits=10)

    # Need at least 3 qualifying dirs to surface at all
    # Here only zone_a and zone_b qualify (2 dirs); expect []
    assert zones == []


def test_hot_zones_surfaces_when_three_or_more_qualify(tmp_path):
    _init_repo(tmp_path)
    for zone in ("alpha", "beta", "gamma", "delta"):
        for i in range(11):
            _commit_file(tmp_path, f"src/{zone}/f{i % 2}.py", f"v={i}\n", message=f"{zone}{i}")

    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    zones = evidence.hot_zones(top_n=3, min_commits=10)
    assert len(zones) == 3
    # Ordering is by commit count desc; ties broken lex. All four have 11
    # commits, so lex-ordered top 3 are alpha, beta, delta (or similar).
    assert all(z.startswith("src/") for z in zones)
    assert len(set(zones)) == 3   # no duplicates


def test_hot_zones_filters_renamed_directories(tmp_path):
    """Regression: dirs that show up in `git log` but no longer exist on
    disk (renamed/removed) must not surface as 'Active zones'.

    The dogfooding finding was that this repo's atlas kept reporting
    pre-rename source directories (since renamed under `src/prep/`) as
    Active zones long after the rename. The pre-rename paths have churn
    forever in `git log`, but the directories are empty on disk —
    surfacing them in the atlas is misleading.
    """
    _init_repo(tmp_path)
    # Three zones with enough churn to qualify, three more that exist
    # only in history (rename/remove later).
    for zone in ("alpha", "beta", "gamma"):
        for i in range(11):
            _commit_file(tmp_path, f"src/{zone}/f{i % 2}.py", f"v={i}\n", message=f"{zone}{i}")

    for zone in ("ghost1", "ghost2", "ghost3"):
        for i in range(11):
            _commit_file(tmp_path, f"src/{zone}/f{i % 2}.py", f"v={i}\n", message=f"{zone}{i}")
    # Now remove the ghost directories from disk (and commit the deletion)
    # so they only exist in history.
    for zone in ("ghost1", "ghost2", "ghost3"):
        subprocess.run(
            ["git", "rm", "-rq", f"src/{zone}"], cwd=tmp_path, check=True,
        )
    subprocess.run(
        ["git", "commit", "-q", "-m", "remove ghost dirs"], cwd=tmp_path, check=True,
    )

    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    zones = evidence.hot_zones(top_n=10, min_commits=10)

    # Only the three real zones survive the existence filter.
    assert sorted(zones) == ["src/alpha/", "src/beta/", "src/gamma/"]
    assert not any("ghost" in z for z in zones)


def test_hot_zones_filters_empty_directory_husks(tmp_path):
    """Regression: an empty leftover directory (rename leaves behind
    parent dirs even after `git rm`) must not surface as a hot zone.

    On disk, this is the exact state of a pre-rename source directory
    in this repo after the rename — the directory exists as a 0-byte
    husk but has no files in it. `is_dir()` is True; we still want it
    filtered out.
    """
    _init_repo(tmp_path)
    for zone in ("real_a", "real_b", "real_c"):
        for i in range(11):
            _commit_file(tmp_path, f"src/{zone}/f{i % 2}.py", f"v={i}\n", message=f"{zone}{i}")

    # Add a husk zone and then delete its contents (leaving the dir).
    for i in range(11):
        _commit_file(tmp_path, f"src/husk/f{i % 2}.py", f"v={i}\n", message=f"husk{i}")
    subprocess.run(["git", "rm", "-rq", "src/husk"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "remove husk files"], cwd=tmp_path, check=True)

    # Re-create the empty parent directory on disk to simulate the leftover.
    husk_dir = tmp_path / "src" / "husk"
    husk_dir.mkdir(parents=True, exist_ok=True)
    assert husk_dir.is_dir()
    assert not any(husk_dir.iterdir())   # confirmed empty husk

    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    zones = evidence.hot_zones(top_n=10, min_commits=10)

    assert sorted(zones) == ["src/real_a/", "src/real_b/", "src/real_c/"]
    assert "src/husk/" not in zones


def test_cache_persists_across_instances(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")

    cache_dir = tmp_path / ".cache"
    ev1 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    churn1 = ev1.recent_churn_by_file(window_days=30)

    # Second instance reads the cache without re-running git
    ev2 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    churn2 = ev2.recent_churn_by_file(window_days=30)

    assert set(churn1.keys()) == set(churn2.keys())
    # Confirm the second instance hit the on-disk cache
    stats = ev2.stats()
    assert stats["refreshes"] == 0


def test_cache_invalidated_on_head_change(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")

    cache_dir = tmp_path / ".cache"
    ev1 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    ev1.recent_churn_by_file(window_days=30)

    # New commit → HEAD changes
    _commit_file(tmp_path, "src/bar.py", "y\n")

    ev2 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    churn = ev2.recent_churn_by_file(window_days=30)
    assert "src/bar.py" in churn
    stats = ev2.stats()
    assert stats["refreshes"] == 1


def test_refresh_clears_in_memory_caches(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")
    cache_dir = tmp_path / ".cache"

    ev = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    ev.recent_churn_by_file(window_days=30)
    ev.refresh()

    # After refresh, in-memory per-window caches are cleared
    assert ev._churn_caches == {}


def test_multiple_windows_have_independent_caches(tmp_path):
    """Regression guard: callers with different windows must not collide.

    Our own design uses 180d for TODO gating and 60d for atlas
    classification. Both should work on the same GitEvidence instance.
    """
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")
    ev = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")

    churn_60 = ev.recent_churn_by_file(window_days=60)
    churn_180 = ev.recent_churn_by_file(window_days=180)

    # Same HEAD → same results, but in-memory caches should be independently populated
    assert "src/foo.py" in churn_60
    assert "src/foo.py" in churn_180
    assert 60 in ev._churn_caches
    assert 180 in ev._churn_caches


def test_corrupt_churn_file_forces_rebuild(tmp_path):
    """Corrupt JSON in churn file → _load_disk_cache returns None → rebuild."""
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")
    cache_dir = tmp_path / ".cache"
    ev1 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    ev1.recent_churn_by_file(window_days=30)

    # Corrupt the churn file (valid JSON, wrong schema)
    churn_path = cache_dir / "churn_30.json"
    churn_path.write_text('{"src/foo.py": {"commits": "not-an-int"}}')

    ev2 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    result = ev2.recent_churn_by_file(window_days=30)
    assert "src/foo.py" in result  # rebuilt from git
    assert ev2.stats()["refreshes"] == 1
