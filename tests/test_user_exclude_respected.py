"""Phase 115 Step 10 — user-exclude must ADD to defaults, never REPLACE.

Architectural contract (see docs/Phase115_filter-universality/01_TARGET_DESIGN.md):
a user who adds an `exclude_globs` entry in `repo_policy.json` or sets
`project.config.trace.ignore_patterns` expects their pattern to apply
**on top of** the built-in defaults. Replacing defaults silently
re-opens the self-ingestion / build-artifact leaks we just closed.

These tests prove that `effective_excludes()` is union-semantics and
that the per-project policy auto-merges L1 back in on every load.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from prep.core.repo_policy import (
    effective_excludes,
    ensure_repo_policy,
    policy_path_for_index,
    write_repo_policy,
)
from prep.core.repo_profile import (
    CODRAG_OUTPUT_FILE_GLOBS,
    DEFAULT_EXCLUDE_DIR_NAMES,
    DEFAULT_EXCLUDE_FILE_GLOBS,
)


def _scaffold_repo(tmpdir: Path) -> tuple[Path, Path]:
    repo_root = tmpdir
    index_dir = repo_root / ".codrag"
    index_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / "main.py").write_text("print('x')\n")
    return repo_root, index_dir


def test_effective_excludes_unions_all_three_layers() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo_root, index_dir = _scaffold_repo(Path(td))

        # User sets L3 runtime patterns.
        l3 = ["**/*.secret.ts", "**/my_generated/**"]
        # Plus an explicit caller pattern.
        explicit = ["**/scratch.md"]

        result = effective_excludes(
            index_dir=index_dir,
            repo_root=repo_root,
            trace_ignore_patterns=l3,
            explicit_excludes=explicit,
        )

        assert "**/.codrag/**" in result, "L1 self-ingestion guard must be present"
        assert "**/codrag_data/**" in result, "L1 self-ingestion guard must be present"
        assert "**/storybook-static/**" in result, "L1 leak culprit must be present"
        assert "**/*.d.ts" in result, "L1 build-artifact glob must be present"
        assert "**/*.secret.ts" in result, "L3 runtime pattern must be merged"
        assert "**/my_generated/**" in result, "L3 runtime pattern must be merged"
        assert "**/scratch.md" in result, "explicit caller pattern must be merged"


def test_user_excludes_added_to_existing_policy_survive_auto_migration() -> None:
    """Simulate: user added custom `**/*.lock` / `**/.DS_Store`. Later
    CoDRAG adds new defaults (e.g. `**/storybook-static/**`). The
    user's additions must survive; the new defaults must appear.
    """
    with tempfile.TemporaryDirectory() as td:
        repo_root, index_dir = _scaffold_repo(Path(td))

        stub_policy = {
            "version": "1.0",
            "repo_root": str(repo_root.resolve()),
            "include_globs": ["**/*.py"],
            # Sparse: only the user's customizations + a couple of old defaults.
            "exclude_globs": ["**/*.lock", "**/.DS_Store", "**/node_modules/**"],
            "role_weights": {},
            "path_weights": {},
            "path_roles": [],
            "detected_languages": [],
            "marker_files": [],
        }
        write_repo_policy(policy_path_for_index(index_dir), stub_policy)

        merged = ensure_repo_policy(index_dir, repo_root)
        excludes = set(merged.get("exclude_globs") or [])

        # User customisations preserved.
        assert "**/*.lock" in excludes
        assert "**/.DS_Store" in excludes

        # L1 self-ingestion guards back-filled.
        assert "**/.codrag/**" in excludes
        assert "**/codrag_data/**" in excludes

        # L1 build-artifact globs back-filled.
        assert "**/storybook-static/**" in excludes
        assert "**/*.d.ts" in excludes

        # Written back to disk — watcher / other consumers see the merged set.
        on_disk = json.loads(policy_path_for_index(index_dir).read_text())
        assert "**/*.lock" in on_disk["exclude_globs"]
        assert "**/storybook-static/**" in on_disk["exclude_globs"]


def test_user_cannot_silently_remove_codrag_output_guard() -> None:
    """Direct edit of `repo_policy.json` removing `**/.codrag/**` gets
    re-added on the next load. Self-ingestion is a hard invariant.
    """
    with tempfile.TemporaryDirectory() as td:
        repo_root, index_dir = _scaffold_repo(Path(td))

        # User edits the file and deletes the self-ingestion guard.
        sabotaged = {
            "version": "1.0",
            "repo_root": str(repo_root.resolve()),
            "include_globs": ["**/*.py"],
            "exclude_globs": ["**/*.log"],  # user-only, no defaults
            "role_weights": {},
            "path_weights": {},
            "path_roles": [],
            "detected_languages": [],
            "marker_files": [],
        }
        write_repo_policy(policy_path_for_index(index_dir), sabotaged)

        reloaded = ensure_repo_policy(index_dir, repo_root)
        excludes = set(reloaded.get("exclude_globs") or [])

        # Guard is back.
        assert "**/.codrag/**" in excludes
        assert "**/codrag_data/**" in excludes
        # User's custom entry still there.
        assert "**/*.log" in excludes


def test_codrag_output_file_globs_all_in_defaults() -> None:
    """Sanity: every CODRAG_OUTPUT_FILE_GLOBS entry is in
    DEFAULT_EXCLUDE_FILE_GLOBS. Registry is the source of truth.
    """
    for glob in CODRAG_OUTPUT_FILE_GLOBS:
        assert glob in DEFAULT_EXCLUDE_FILE_GLOBS, (
            f"{glob} is in CODRAG_OUTPUT_FILE_GLOBS but not in DEFAULT_EXCLUDE_FILE_GLOBS"
        )
