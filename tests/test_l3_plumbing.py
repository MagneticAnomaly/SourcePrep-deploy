"""Phase 115 audit follow-up — L3 reaches loaders & watcher via project pointer.

Pre-fix: `project.config.trace.ignore_patterns` was plumbed only
through the pipeline worker (`services/pipeline/workers.py:174-179`).
Loaders and the filesystem watcher read the policy directly and never
saw runtime ignore patterns, so the watcher could trigger rebuilds
on files the user had explicitly asked to ignore.

Fix: `project_registry.project_for_index_dir()` + `trace_ignore_patterns_for_index()`
reverse-look up the Project via `<index_dir>/project.json` and expose
L3. `load_filtered_trace_nodes` and `AutoRebuildWatcher._load_policy_globs`
auto-resolve when no patterns are passed explicitly.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from codrag.core.project_registry import (
    Project,
    _POINTER_FILENAME,
    trace_ignore_patterns_for_index,
)


def _stub_project(idx_dir: Path, project_id: str, patterns: list[str]) -> Project:
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / _POINTER_FILENAME).write_text(json.dumps({"id": project_id}))
    return Project(
        id=project_id,
        name="test",
        path="/tmp/fake",
        mode="embedded",
        config={"trace": {"ignore_patterns": patterns}},
        created_at="2026-04-17T00:00:00Z",
        updated_at="2026-04-17T00:00:00Z",
    )


def test_trace_ignore_patterns_resolved_via_pointer() -> None:
    with tempfile.TemporaryDirectory() as td:
        idx_dir = Path(td) / ".codrag"
        proj = _stub_project(idx_dir, "proj-abc", ["**/*.secret.ts", "**/private/**"])

        with patch(
            "codrag.core.project_registry.ProjectRegistry.get_project",
            return_value=proj,
        ):
            patterns = trace_ignore_patterns_for_index(idx_dir)

        assert patterns == ["**/*.secret.ts", "**/private/**"]


def test_trace_ignore_patterns_empty_when_pointer_missing() -> None:
    with tempfile.TemporaryDirectory() as td:
        idx_dir = Path(td) / ".codrag"
        idx_dir.mkdir(parents=True)
        # No project.json written.
        assert trace_ignore_patterns_for_index(idx_dir) == []


def test_trace_ignore_patterns_empty_when_project_not_in_registry() -> None:
    with tempfile.TemporaryDirectory() as td:
        idx_dir = Path(td) / ".codrag"
        idx_dir.mkdir(parents=True)
        (idx_dir / _POINTER_FILENAME).write_text(json.dumps({"id": "missing-id"}))

        with patch(
            "codrag.core.project_registry.ProjectRegistry.get_project",
            return_value=None,
        ):
            assert trace_ignore_patterns_for_index(idx_dir) == []


def test_loader_auto_resolves_l3() -> None:
    """load_filtered_trace_nodes filters a leaked path that is only in L3."""
    from codrag.core.repo_policy import ensure_repo_policy
    from codrag.core.trace.loaders import load_filtered_trace_nodes

    with tempfile.TemporaryDirectory() as td:
        repo_root = Path(td).resolve()
        idx_dir = repo_root / ".codrag"
        idx_dir.mkdir(parents=True)

        # Fresh policy so L1+L2 don't happen to cover the L3 pattern.
        ensure_repo_policy(idx_dir, repo_root)

        # trace_nodes.jsonl with one file node that only L3 will kill.
        nodes_jsonl = idx_dir / "trace_nodes.jsonl"
        nodes_jsonl.write_text(
            json.dumps({"node_id": "file:src/keep.py", "path": "src/keep.py"}) + "\n"
            + json.dumps({"node_id": "file:src/secret.data", "path": "src/secret.data"}) + "\n"
        )

        proj = _stub_project(idx_dir, "proj-xyz", ["**/*.data"])

        with patch(
            "codrag.core.project_registry.ProjectRegistry.get_project",
            return_value=proj,
        ):
            nodes = load_filtered_trace_nodes(
                index_dir=idx_dir, repo_root=repo_root,
            )

        paths = {n.get("path") for n in nodes}
        assert "src/keep.py" in paths, "Legit file should survive"
        assert "src/secret.data" not in paths, (
            "L3 pattern '**/*.data' should have been auto-resolved and applied"
        )


def test_loader_explicit_empty_opt_out() -> None:
    """Passing an empty list (not None) skips the registry lookup."""
    from codrag.core.repo_policy import ensure_repo_policy
    from codrag.core.trace.loaders import load_filtered_trace_nodes

    with tempfile.TemporaryDirectory() as td:
        repo_root = Path(td).resolve()
        idx_dir = repo_root / ".codrag"
        idx_dir.mkdir(parents=True)
        ensure_repo_policy(idx_dir, repo_root)

        nodes_jsonl = idx_dir / "trace_nodes.jsonl"
        nodes_jsonl.write_text(
            json.dumps({"node_id": "file:src/a.py", "path": "src/a.py"}) + "\n"
        )

        # ProjectRegistry.get_project should NOT be called when caller
        # passes trace_ignore_patterns=[] explicitly.
        with patch(
            "codrag.core.project_registry.ProjectRegistry.get_project"
        ) as mock_get:
            nodes = load_filtered_trace_nodes(
                index_dir=idx_dir,
                repo_root=repo_root,
                trace_ignore_patterns=[],
            )
            assert not mock_get.called, (
                "Explicit empty list must opt out of L3 auto-resolve"
            )

        assert len(nodes) == 1
