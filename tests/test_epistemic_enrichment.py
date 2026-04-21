"""Tests for epistemic enrichment engine (topological sort, enricher)."""
import pytest

from prep.core.epistemic_enrichment import topological_sort_files


class TestTopologicalSort:
    def test_leaves_first(self):
        """Files with no dependencies should come first."""
        nodes = [
            {"id": "file:src/app.py", "kind": "file"},
            {"id": "file:src/utils.py", "kind": "file"},
            {"id": "file:src/config.py", "kind": "file"},
        ]
        edges = [
            {"source": "file:src/app.py", "target": "file:src/utils.py", "kind": "imports"},
            {"source": "file:src/app.py", "target": "file:src/config.py", "kind": "imports"},
        ]
        result = topological_sort_files(nodes, edges)
        ids = [n["id"] for n in result]
        # utils and config have no dependencies, should come before app
        assert ids.index("file:src/utils.py") < ids.index("file:src/app.py")
        assert ids.index("file:src/config.py") < ids.index("file:src/app.py")

    def test_chain(self):
        """A → B → C should produce C, B, A."""
        nodes = [
            {"id": "file:a.py", "kind": "file"},
            {"id": "file:b.py", "kind": "file"},
            {"id": "file:c.py", "kind": "file"},
        ]
        edges = [
            {"source": "file:a.py", "target": "file:b.py", "kind": "imports"},
            {"source": "file:b.py", "target": "file:c.py", "kind": "imports"},
        ]
        result = topological_sort_files(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids.index("file:c.py") < ids.index("file:b.py")
        assert ids.index("file:b.py") < ids.index("file:a.py")

    def test_no_edges(self):
        """With no edges, all nodes are leaves — order preserved."""
        nodes = [
            {"id": "file:a.py", "kind": "file"},
            {"id": "file:b.py", "kind": "file"},
        ]
        result = topological_sort_files(nodes, [])
        assert len(result) == 2

    def test_cycle_handled(self):
        """Cycles should not cause infinite loops — cyclic nodes added at end."""
        nodes = [
            {"id": "file:a.py", "kind": "file"},
            {"id": "file:b.py", "kind": "file"},
            {"id": "file:c.py", "kind": "file"},  # leaf
        ]
        edges = [
            {"source": "file:a.py", "target": "file:b.py", "kind": "imports"},
            {"source": "file:b.py", "target": "file:a.py", "kind": "imports"},  # cycle
        ]
        result = topological_sort_files(nodes, edges)
        assert len(result) == 3
        # c.py (no deps) should be first
        ids = [n["id"] for n in result]
        assert ids[0] == "file:c.py"

    def test_ignores_non_file_edges(self):
        """Edges between non-file nodes (e.g. contains) should be ignored."""
        nodes = [
            {"id": "file:a.py", "kind": "file"},
            {"id": "file:b.py", "kind": "file"},
        ]
        edges = [
            {"source": "file:a.py", "target": "sym:foo@a.py:1", "kind": "contains"},
        ]
        result = topological_sort_files(nodes, edges)
        assert len(result) == 2

    def test_inferred_edges_count(self):
        """Inferred edges should affect topological order."""
        nodes = [
            {"id": "file:doc.md", "kind": "file"},
            {"id": "file:src/main.py", "kind": "file"},
        ]
        edges = [
            {"source": "file:doc.md", "target": "file:src/main.py", "kind": "inferred"},
        ]
        result = topological_sort_files(nodes, edges)
        ids = [n["id"] for n in result]
        # main.py is a leaf (no outbound deps), should come first
        assert ids.index("file:src/main.py") < ids.index("file:doc.md")
