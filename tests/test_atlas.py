"""
Tests for CoDRAG Codebase Atlas (Phase 29).

Tests cover:
- AtlasDocument serialization
- Adaptive budget computation
- Structural Atlas generation (no LLM)
- LLM Atlas generation (mocked)
- Staleness detection (fingerprint, hub hashes, file count)
- Persistence (save, load, rotation)
- Edge cases (empty project, tiny project, missing files)
"""
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

# Import directly to avoid heavy __init__.py chain
import importlib
_atlas = importlib.import_module("codrag.core.atlas")
CodebaseAtlas = _atlas.CodebaseAtlas
AtlasDocument = _atlas.AtlasDocument
Segment = _atlas.Segment
SegmentDocument = _atlas.SegmentDocument
compute_atlas_budget = _atlas.compute_atlas_budget
compute_segments = _atlas.compute_segments
MIN_FILES_FOR_ATLAS = _atlas.MIN_FILES_FOR_ATLAS


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_index_dir(tmp_path):
    """Create a temporary index directory with sample enrichment data."""
    idx = tmp_path / "index"
    idx.mkdir()
    return idx


def _write_modules(idx_dir: Path, modules: List[Dict[str, Any]]) -> None:
    """Write trace_modules.jsonl."""
    with open(idx_dir / "trace_modules.jsonl", "w") as f:
        for m in modules:
            f.write(json.dumps(m) + "\n")


def _write_epistemic(idx_dir: Path, entries: List[Dict[str, Any]]) -> None:
    """Write trace_epistemic.jsonl."""
    with open(idx_dir / "trace_epistemic.jsonl", "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _write_nodes(idx_dir: Path, nodes: List[Dict[str, Any]]) -> None:
    """Write trace_nodes.jsonl."""
    with open(idx_dir / "trace_nodes.jsonl", "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")


def _write_edges(idx_dir: Path, edges: List[Dict[str, Any]]) -> None:
    """Write trace_edges.jsonl."""
    with open(idx_dir / "trace_edges.jsonl", "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")


def _write_manifest(idx_dir: Path, stats: Dict[str, Any], file_hashes: Optional[Dict] = None) -> None:
    """Write trace_manifest.json."""
    manifest = {"stats": stats}
    if file_hashes:
        manifest["file_hashes"] = file_hashes
    with open(idx_dir / "trace_manifest.json", "w") as f:
        json.dump(manifest, f)


def _sample_modules() -> List[Dict[str, Any]]:
    return [
        {
            "module_id": "module:core:0",
            "name": "Core Engine",
            "summary": "Main indexing and search engine. Handles embedding, chunking, and semantic search.",
            "member_files": ["src/index.py", "src/search.py", "src/embedder.py"],
            "domain_tags": ["core", "search"],
            "architecture_layers": ["data"],
            "component_status": "complete",
            "file_count": 3,
            "dependencies": ["utils"],
        },
        {
            "module_id": "module:ui:0",
            "name": "Dashboard UI",
            "summary": "React dashboard for project management and search visualization.",
            "member_files": ["ui/App.tsx", "ui/Search.tsx"],
            "domain_tags": ["ui", "dashboard"],
            "architecture_layers": ["presentation"],
            "component_status": "partial",
            "file_count": 2,
            "dependencies": ["core"],
            "tech_debt_summary": "Missing error boundaries",
        },
    ]


def _sample_epistemic() -> List[Dict[str, Any]]:
    return [
        {
            "node_id": "file:src/index.py",
            "architecture_layer": "data",
            "domain_tags": ["core", "search"],
            "epistemic_confidence": 0.85,
        },
        {
            "node_id": "file:src/search.py",
            "architecture_layer": "data",
            "domain_tags": ["core"],
            "epistemic_confidence": 0.90,
        },
        {
            "node_id": "file:ui/App.tsx",
            "architecture_layer": "presentation",
            "domain_tags": ["ui"],
            "epistemic_confidence": 0.75,
        },
    ]


def _sample_nodes() -> List[Dict[str, Any]]:
    return [
        {"node_id": "file:src/index.py", "file_path": "src/index.py"},
        {"node_id": "file:src/search.py", "file_path": "src/search.py"},
        {"node_id": "file:src/embedder.py", "file_path": "src/embedder.py"},
        {"node_id": "file:ui/App.tsx", "file_path": "ui/App.tsx"},
        {"node_id": "file:ui/Search.tsx", "file_path": "ui/Search.tsx"},
    ] + [
        {"node_id": f"file:src/utils/util_{i}.py", "file_path": f"src/utils/util_{i}.py"}
        for i in range(15)
    ]


def _sample_edges() -> List[Dict[str, Any]]:
    return [
        {"source": "file:src/search.py", "target": "file:src/index.py", "kind": "imports"},
        {"source": "file:src/embedder.py", "target": "file:src/index.py", "kind": "imports"},
        {"source": "file:ui/App.tsx", "target": "file:src/index.py", "kind": "imports"},
        {"source": "file:ui/Search.tsx", "target": "file:src/search.py", "kind": "imports"},
        {"source": "file:ui/Search.tsx", "target": "file:src/index.py", "kind": "imports"},
    ]


def _populate_index(idx_dir: Path) -> None:
    """Populate an index directory with all sample data."""
    _write_modules(idx_dir, _sample_modules())
    _write_epistemic(idx_dir, _sample_epistemic())
    _write_nodes(idx_dir, _sample_nodes())
    _write_edges(idx_dir, _sample_edges())
    _write_manifest(idx_dir, {"files_indexed": 20}, {
        "src/index.py": "abc123",
        "src/search.py": "def456",
    })


# ── AtlasDocument Tests ──────────────────────────────────────────────

class TestAtlasDocument:
    def test_roundtrip(self):
        doc = AtlasDocument(
            content="Test atlas content",
            generated_at="2026-02-19T00:00:00Z",
            model="test-model",
            fingerprint="abc123",
            file_count=100,
            module_count=5,
            char_count=18,
            mode="llm",
            hub_file_hashes={"src/index.py": "hash1"},
        )
        d = doc.to_dict()
        restored = AtlasDocument.from_dict(d)
        assert restored.content == doc.content
        assert restored.model == doc.model
        assert restored.fingerprint == doc.fingerprint
        assert restored.file_count == doc.file_count
        assert restored.module_count == doc.module_count
        assert restored.mode == doc.mode
        assert restored.hub_file_hashes == doc.hub_file_hashes

    def test_from_dict_defaults(self):
        doc = AtlasDocument.from_dict({"content": "test"})
        assert doc.content == "test"
        assert doc.model == "unknown"
        assert doc.mode == "structural"
        assert doc.hub_file_hashes == {}
        assert doc.version == 1


# ── Budget Tests ─────────────────────────────────────────────────────

class TestAdaptiveBudget:
    def test_tiny_project_no_atlas(self):
        assert compute_atlas_budget(0) == 0
        assert compute_atlas_budget(1) == 0

    def test_small_project(self):
        budget = compute_atlas_budget(50)
        assert budget == 1200  # minimum meaningful atlas

    def test_medium_project(self):
        budget = compute_atlas_budget(500)
        assert 2500 <= budget <= 2600  # 2100 + (500-200)*1.5 = 2550

    def test_large_project(self):
        budget = compute_atlas_budget(2000)
        assert 3600 <= budget <= 3700  # 3300 + (2000-1000)*0.35 = 3650

    def test_huge_project_capped(self):
        budget = compute_atlas_budget(10000)
        assert budget == 4000  # capped at MAX

    def test_threshold_boundary(self):
        assert compute_atlas_budget(MIN_FILES_FOR_ATLAS - 1) == 0
        assert compute_atlas_budget(MIN_FILES_FOR_ATLAS) > 0


# ── Structural Atlas Tests ───────────────────────────────────────────

class TestStructuralAtlas:
    def test_generates_content(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        doc = atlas.generate_structural()

        assert doc.mode == "structural"
        assert doc.model == "structural"
        assert doc.content  # non-empty
        assert doc.file_count == 20
        assert doc.module_count == 2
        assert doc.fingerprint
        assert doc.generated_at

    def test_mentions_languages(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        doc = atlas.generate_structural()
        assert ".py" in doc.content or "py" in doc.content.lower()

    def test_mentions_modules(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        doc = atlas.generate_structural()
        assert "Core Engine" in doc.content or "module" in doc.content.lower()

    def test_mentions_hub_files(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        doc = atlas.generate_structural()
        assert "index.py" in doc.content

    def test_empty_project(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        doc = atlas.generate_structural()
        assert doc.content == ""  # below MIN_FILES_FOR_ATLAS

    def test_saves_to_disk(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        doc = atlas.generate_structural()

        assert atlas.atlas_path.exists()
        loaded = atlas.load()
        assert loaded is not None
        assert loaded.content == doc.content
        assert loaded.fingerprint == doc.fingerprint


# ── LLM Atlas Tests (Mocked) ────────────────────────────────────────

class TestLLMAtlas:
    def test_generate_with_mock_llm(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        mock_llm = MagicMock()
        mock_llm.model = "test-14b"
        mock_llm.generate.return_value = (
            "IDENTITY: Python RAG toolkit for semantic code search.\n\n"
            "STACK: Python 3.11, React (dashboard), ONNX Runtime (embeddings), Ollama (LLM).\n\n"
            "ARCHITECTURE: Core Engine (src/index.py, src/search.py, src/embedder.py) handles indexing, "
            "chunking, and semantic search. Dashboard UI (ui/App.tsx, ui/Search.tsx) provides project "
            "management and search visualization over a REST API.\n\n"
            "SUBSYSTEMS:\n"
            "Core Engine: src/index.py, src/search.py, src/embedder.py\n"
            "Dashboard UI: ui/App.tsx, ui/Search.tsx\n\n"
            "FLOW: User query enters via ui/Search.tsx, dispatched to src/search.py which calls "
            "src/embedder.py for vector similarity, then src/index.py for chunk retrieval. Results "
            "rendered in ui/App.tsx.\n\n"
            "PATTERNS: Dashboard depends on Core via REST. Embedding model loaded once at startup.\n\n"
            "RISKS: Missing error boundaries in Dashboard UI.",
            500,
        )

        atlas = CodebaseAtlas(tmp_index_dir, llm=mock_llm)
        doc = atlas.generate()

        assert doc.mode == "llm"
        assert doc.model == "test-14b"
        assert "Core Engine" in doc.content
        assert doc.module_count == 2
        assert doc.file_count == 20
        mock_llm.generate.assert_called_once()

    def test_fallback_to_structural_on_llm_error(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        mock_llm = MagicMock()
        mock_llm.model = "test-14b"
        mock_llm.generate.side_effect = RuntimeError("Connection refused")

        atlas = CodebaseAtlas(tmp_index_dir, llm=mock_llm)
        doc = atlas.generate()

        assert doc.mode == "structural"
        assert doc.content  # structural fallback should still produce content

    def test_fallback_when_no_llm(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir, llm=None)
        doc = atlas.generate()
        assert doc.mode == "structural"

    def test_fallback_when_no_modules(self, tmp_index_dir):
        # Only write nodes/edges, no modules
        _write_nodes(tmp_index_dir, _sample_nodes())
        _write_edges(tmp_index_dir, _sample_edges())
        _write_manifest(tmp_index_dir, {"files_indexed": 20})

        mock_llm = MagicMock()
        atlas = CodebaseAtlas(tmp_index_dir, llm=mock_llm)
        doc = atlas.generate()

        assert doc.mode == "structural"
        mock_llm.generate.assert_not_called()

    def test_prompt_includes_modules(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        mock_llm = MagicMock()
        mock_llm.model = "test-14b"
        # Return long enough content to pass the quality gate (MIN_ATLAS_CHARS // 2 = 600)
        mock_llm.generate.return_value = (
            "IDENTITY: Python RAG toolkit. STACK: Python, React. "
            "ARCHITECTURE: Core Engine handles indexing and search. Dashboard UI provides visualization. "
            "SUBSYSTEMS: Core Engine: src/index.py, src/search.py. Dashboard UI: ui/App.tsx. "
            "FLOW: Query enters Search.tsx, dispatches to search.py, calls embedder.py, returns via index.py. "
            "PATTERNS: REST API between UI and Core. RISKS: Missing error boundaries in UI. "
            + "Additional context to meet minimum length. " * 8,
            100,
        )

        atlas = CodebaseAtlas(tmp_index_dir, llm=mock_llm)
        atlas.generate()

        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0]
        assert "Core Engine" in prompt
        assert "Dashboard UI" in prompt


# ── Staleness Tests ──────────────────────────────────────────────────

class TestStaleness:
    def test_stale_when_no_cached(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        assert atlas.is_stale() is True

    def test_not_stale_after_generate(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas.generate_structural()
        assert atlas.is_stale() is False

    def test_stale_when_module_changes(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas.generate_structural()
        assert atlas.is_stale() is False

        # Change a module summary
        modules = _sample_modules()
        modules[0]["summary"] = "Completely different summary now"
        _write_modules(tmp_index_dir, modules)

        assert atlas.is_stale() is True

    def test_stale_when_module_added(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas.generate_structural()

        # Add a new module
        modules = _sample_modules()
        modules.append({
            "module_id": "module:api:0",
            "name": "API Layer",
            "summary": "New API layer",
            "member_files": ["src/api.py"],
            "domain_tags": ["api"],
            "architecture_layers": ["service"],
            "component_status": "complete",
            "file_count": 1,
        })
        _write_modules(tmp_index_dir, modules)

        assert atlas.is_stale() is True

    def test_stale_when_hub_hash_changes(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas.generate_structural()
        assert atlas.is_stale() is False

        # Change a hub file hash in the manifest
        _write_manifest(tmp_index_dir, {"files_indexed": 20}, {
            "src/index.py": "CHANGED_HASH",
            "src/search.py": "def456",
        })
        assert atlas.is_stale() is True

    def test_stale_when_file_count_grows_20pct(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas.generate_structural()
        assert atlas.is_stale() is False

        # Increase file count by 25%
        _write_manifest(tmp_index_dir, {"files_indexed": 25})

        assert atlas.is_stale() is True

    def test_not_stale_when_nothing_changes(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas.generate_structural()

        # Same modules, same manifest, same hub hashes — NOT stale
        assert atlas.is_stale() is False


# ── Persistence Tests ────────────────────────────────────────────────

class TestPersistence:
    def test_load_returns_none_when_missing(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        assert atlas.load() is None

    def test_exists_false_when_missing(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        assert atlas.exists() is False

    def test_exists_true_after_generate(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas.generate_structural()
        assert atlas.exists() is True

    def test_rotation_preserves_previous(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)

        # Generate first version
        doc1 = atlas.generate_structural()
        assert atlas.load_previous() is None  # no previous yet

        # Modify and regenerate
        modules = _sample_modules()
        modules[0]["summary"] = "Updated summary for rotation test"
        _write_modules(tmp_index_dir, modules)

        doc2 = atlas.generate_structural()

        # Previous should be doc1
        prev = atlas.load_previous()
        assert prev is not None
        assert prev.content == doc1.content
        assert prev.fingerprint != doc2.fingerprint

    def test_load_handles_corrupt_json(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas.atlas_path.parent.mkdir(parents=True, exist_ok=True)
        with open(atlas.atlas_path, "w") as f:
            f.write("not json {{{")
        assert atlas.load() is None


# ── Fingerprint Tests ────────────────────────────────────────────────

class TestFingerprint:
    def test_deterministic(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        modules = atlas._load_modules()
        stats = atlas._load_graph_stats()
        fp1 = atlas._compute_fingerprint(modules, stats)
        fp2 = atlas._compute_fingerprint(modules, stats)
        assert fp1 == fp2

    def test_changes_with_module_content(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)

        modules1 = atlas._load_modules()
        stats = atlas._load_graph_stats()
        fp1 = atlas._compute_fingerprint(modules1, stats)

        modules1[0]["summary"] = "Different content"
        fp2 = atlas._compute_fingerprint(modules1, stats)
        assert fp1 != fp2

    def test_changes_with_file_count(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)

        modules = atlas._load_modules()
        stats1 = {"file_count": 100}
        stats2 = {"file_count": 200}

        fp1 = atlas._compute_fingerprint(modules, stats1)
        fp2 = atlas._compute_fingerprint(modules, stats2)
        assert fp1 != fp2


# ── Graph Stats Loading Tests ────────────────────────────────────────

class TestGraphStats:
    def test_loads_manifest_stats(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        stats = atlas._load_graph_stats()
        assert stats["file_count"] == 20

    def test_counts_nodes(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        stats = atlas._load_graph_stats()
        assert stats["node_count"] == 20  # 5 named + 15 utils

    def test_counts_edges(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        stats = atlas._load_graph_stats()
        assert stats["edge_count"] == 5

    def test_detects_languages(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        stats = atlas._load_graph_stats()
        langs = stats["languages"]
        assert ".py" in langs
        assert ".tsx" in langs

    def test_identifies_hub_files(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        stats = atlas._load_graph_stats()
        hubs = atlas._identify_hubs(stats)
        # index.py should be the top hub (3 incoming edges)
        assert len(hubs) > 0
        assert hubs[0][0] == "src/index.py"
        assert hubs[0][1] >= 3


# ── Progress Callback Tests ──────────────────────────────────────────

class TestProgressCallback:
    def test_structural_no_callback(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        atlas = CodebaseAtlas(tmp_index_dir)
        doc = atlas.generate_structural()
        assert doc.content  # works without callback

    def test_llm_with_callback(self, tmp_index_dir):
        _populate_index(tmp_index_dir)
        mock_llm = MagicMock()
        mock_llm.model = "test"
        mock_llm.generate.return_value = (
            "IDENTITY: Python RAG toolkit. STACK: Python, React. "
            "ARCHITECTURE: Core Engine handles indexing. Dashboard UI provides visualization. "
            "SUBSYSTEMS: Core: src/index.py, src/search.py. UI: ui/App.tsx. "
            "FLOW: Query enters Search.tsx, dispatches to search.py, returns via index.py. "
            "PATTERNS: REST API. RISKS: Missing error boundaries. "
            + "Padding content for quality gate. " * 10,
            100,
        )

        progress_calls = []

        def cb(stage, current, total):
            progress_calls.append((stage, current, total))

        atlas = CodebaseAtlas(tmp_index_dir, llm=mock_llm)
        atlas.generate(progress_callback=cb)

        assert len(progress_calls) >= 3
        assert progress_calls[0][0] == "atlas_generation"
        assert progress_calls[-1][0] == "atlas_complete"


# ── Segmented Atlas Tests ─────────────────────────────────────────────

def _write_nodes_with_paths(idx_dir: Path, file_paths: List[str]) -> None:
    """Write trace_nodes.jsonl with specific file paths."""
    with open(idx_dir / "trace_nodes.jsonl", "w") as f:
        for fp in file_paths:
            f.write(json.dumps({"file_path": fp}) + "\n")


def _write_modules_with_files(idx_dir: Path, modules: List[Dict[str, Any]]) -> None:
    """Write trace_modules.jsonl with member_files."""
    with open(idx_dir / "trace_modules.jsonl", "w") as f:
        for m in modules:
            f.write(json.dumps(m) + "\n")


class TestSegmentDiscovery:
    """Tests for compute_segments() and directory grouping."""

    def test_empty_index(self, tmp_index_dir):
        segments = compute_segments(tmp_index_dir)
        assert segments == []

    def test_groups_by_top_level_dir(self, tmp_index_dir):
        # Need >=10 files per group to survive MIN_SEGMENT_FILES merge
        files = [f"src/codrag/core/file{i}.py" for i in range(12)]
        files += [f"tests/test_{i}.py" for i in range(12)]
        _write_nodes_with_paths(tmp_index_dir, files)
        _write_manifest(tmp_index_dir, {"files_indexed": 24})

        segments = compute_segments(tmp_index_dir)
        assert len(segments) >= 2

        # Should have src/codrag segments (deep dirs)
        seg_dirs = {s.dir_path for s in segments}
        assert any("codrag" in d for d in seg_dirs)

    def test_deep_dir_uses_depth_2(self, tmp_index_dir):
        files = [f"src/core/file{i}.py" for i in range(12)]
        files += [f"src/api/file{i}.py" for i in range(12)]
        _write_nodes_with_paths(tmp_index_dir, files)

        segments = compute_segments(tmp_index_dir)
        seg_dirs = {s.dir_path for s in segments}
        # src/ should be split into src/core and src/api
        assert "src/core" in seg_dirs
        assert "src/api" in seg_dirs

    def test_merges_tiny_groups(self, tmp_index_dir):
        files = [f"src/core/file{i}.py" for i in range(12)]
        files += ["README.md", "LICENSE"]  # tiny root group (<10 files)
        _write_nodes_with_paths(tmp_index_dir, files)

        segments = compute_segments(tmp_index_dir)
        # Root files should be merged since <10 files
        total_files = sum(s.file_count for s in segments)
        assert total_files == 14

    def test_annotates_with_module_tags(self, tmp_index_dir):
        files = [f"src/core/file{i}.py" for i in range(12)]
        _write_nodes_with_paths(tmp_index_dir, files)
        _write_modules_with_files(tmp_index_dir, [
            {
                "module_id": "mod_1",
                "name": "Core Engine",
                "summary": "Core indexing engine",
                "member_files": ["src/core/file0.py", "src/core/file1.py"],
                "domain_tags": ["search", "indexing"],
                "file_count": 2,
            },
        ])

        segments = compute_segments(tmp_index_dir)
        assert len(segments) >= 1
        seg = segments[0]
        assert "mod_1" in seg.module_ids
        assert "search" in seg.domain_tags

    def test_caps_at_max_segments(self, tmp_index_dir):
        # Create many top-level dirs
        files = []
        for i in range(20):
            for j in range(6):
                files.append(f"dir{i}/file{j}.py")
        _write_nodes_with_paths(tmp_index_dir, files)

        segments = compute_segments(tmp_index_dir)
        assert len(segments) <= 15  # MAX_SEGMENTS


class TestSegmentDataclass:
    """Tests for Segment and SegmentDocument serialization."""

    def test_segment_roundtrip(self):
        seg = Segment(
            id="src-core",
            name="Core",
            dir_path="src/core",
            file_paths=["src/core/a.py", "src/core/b.py"],
            module_ids=["mod_1"],
            domain_tags=["search"],
            file_count=2,
        )
        d = seg.to_dict()
        restored = Segment.from_dict(d)
        assert restored.id == seg.id
        assert restored.file_paths == seg.file_paths
        assert restored.file_count == 2

    def test_segment_document_roundtrip(self):
        doc = SegmentDocument(
            content="SEGMENT: Core Engine...",
            generated_at="2026-02-20T00:00:00Z",
            model="mistral:14b",
            fingerprint="abc123",
            segment_id="src-core",
            segment_name="Core",
            dir_path="src/core",
            file_count=10,
            char_count=25,
            mode="llm",
        )
        d = doc.to_dict()
        restored = SegmentDocument.from_dict(d)
        assert restored.segment_id == "src-core"
        assert restored.content == doc.content
        assert restored.file_count == 10


class TestSegmentPersistence:
    """Tests for segment save/load."""

    def test_save_and_load_segment(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        doc = SegmentDocument(
            content="SEGMENT content",
            generated_at="2026-02-20T00:00:00Z",
            model="test",
            fingerprint="fp1",
            segment_id="src-core",
            segment_name="Core",
            dir_path="src/core",
            file_count=10,
            char_count=15,
            mode="llm",
        )
        atlas._save_segment(doc)

        loaded = atlas._load_segment("src-core")
        assert loaded is not None
        assert loaded.content == "SEGMENT content"
        assert loaded.segment_id == "src-core"

    def test_load_missing_segment(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        assert atlas._load_segment("nonexistent") is None

    def test_load_all_segments(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        for i in range(3):
            doc = SegmentDocument(
                content=f"Segment {i}",
                generated_at="2026-02-20T00:00:00Z",
                model="test",
                fingerprint=f"fp{i}",
                segment_id=f"seg-{i}",
                segment_name=f"Seg {i}",
                dir_path=f"dir{i}",
                file_count=5,
                char_count=9,
                mode="llm",
            )
            atlas._save_segment(doc)

        all_segs = atlas.load_segments()
        assert len(all_segs) == 3

    def test_segment_manifest(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        segments = [
            Segment(id="a", name="A", dir_path="a/", file_paths=["a/1.py"], file_count=1),
            Segment(id="b", name="B", dir_path="b/", file_paths=["b/1.py", "b/2.py"], file_count=2),
        ]
        atlas._save_segment_manifest(segments)

        loaded = atlas._load_segment_manifest()
        assert len(loaded) == 2
        assert loaded[0]["id"] == "a"
        assert loaded[1]["file_count"] == 2

    def test_has_segments(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        assert not atlas.has_segments()

        # Save manifest + create segments dir
        atlas._save_segment_manifest([
            Segment(id="a", name="A", dir_path="a/", file_count=1),
        ])
        atlas.segments_dir.mkdir(parents=True, exist_ok=True)
        assert atlas.has_segments()


class TestSegmentSelection:
    """Tests for query-time segment selection."""

    def test_select_segments_by_path(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)

        # Set up manifest
        segments = [
            Segment(
                id="src-core",
                name="Core",
                dir_path="src/core",
                file_paths=["src/core/index.py", "src/core/trace.py", "src/core/search.py"],
                file_count=3,
            ),
            Segment(
                id="src-api",
                name="Api",
                dir_path="src/api",
                file_paths=["src/api/router.py", "src/api/models.py"],
                file_count=2,
            ),
        ]
        atlas._save_segment_manifest(segments)
        atlas.segments_dir.mkdir(parents=True, exist_ok=True)

        # Save segment docs
        for seg in segments:
            doc = SegmentDocument(
                content=f"Content for {seg.name}",
                generated_at="2026-02-20T00:00:00Z",
                model="test",
                fingerprint="fp",
                segment_id=seg.id,
                segment_name=seg.name,
                dir_path=seg.dir_path,
                file_count=seg.file_count,
                char_count=20,
                mode="llm",
            )
            atlas._save_segment(doc)

        # Query with paths touching core
        result = atlas.select_segments(["src/core/index.py", "src/core/trace.py"])
        assert len(result) == 1
        assert result[0].segment_id == "src-core"

    def test_select_multiple_segments(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)

        segments = [
            Segment(id="a", name="A", dir_path="a/",
                    file_paths=["a/1.py", "a/2.py"], file_count=2),
            Segment(id="b", name="B", dir_path="b/",
                    file_paths=["b/1.py"], file_count=1),
        ]
        atlas._save_segment_manifest(segments)
        atlas.segments_dir.mkdir(parents=True, exist_ok=True)

        for seg in segments:
            atlas._save_segment(SegmentDocument(
                content=f"Seg {seg.name}" * 10,
                generated_at="2026-02-20T00:00:00Z",
                model="test", fingerprint="fp",
                segment_id=seg.id, segment_name=seg.name,
                dir_path=seg.dir_path, file_count=seg.file_count,
                char_count=40, mode="llm",
            ))

        # Query touching both segments
        result = atlas.select_segments(["a/1.py", "a/2.py", "b/1.py"])
        assert len(result) == 2

    def test_select_no_match(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas._save_segment_manifest([
            Segment(id="a", name="A", dir_path="a/",
                    file_paths=["a/1.py"], file_count=1),
        ])

        result = atlas.select_segments(["unrelated/file.py"])
        assert len(result) == 0

    def test_build_file_to_segment_index(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        atlas._save_segment_manifest([
            Segment(id="core", name="Core", dir_path="src/core",
                    file_paths=["src/core/a.py", "src/core/b.py"], file_count=2),
            Segment(id="api", name="API", dir_path="src/api",
                    file_paths=["src/api/r.py"], file_count=1),
        ])

        idx = atlas.build_file_to_segment_index()
        assert idx["src/core/a.py"] == "core"
        assert idx["src/core/b.py"] == "core"
        assert idx["src/api/r.py"] == "api"


class TestSegmentedGeneration:
    """Tests for generate_segmented() with mocked LLM."""

    def test_generate_segmented_full(self, tmp_index_dir):
        # Create enough files for 2+ segments (>=10 each for MIN_SEGMENT_FILES)
        files = [f"src/core/file{i}.py" for i in range(12)]
        files += [f"src/api/file{i}.py" for i in range(12)]
        _write_nodes_with_paths(tmp_index_dir, files)
        _write_modules_with_files(tmp_index_dir, [
            {
                "module_id": f"mod_{i}",
                "name": f"Module {i}",
                "summary": f"Summary for module {i}",
                "member_files": [f"src/core/file{i}.py"],
                "domain_tags": ["search"],
                "file_count": 1,
            }
            for i in range(12)
        ])
        _write_manifest(tmp_index_dir, {"files_indexed": 24})
        _write_edges(tmp_index_dir, [])

        mock_llm = MagicMock()
        mock_llm.model = "test-14b"
        # Return long enough content for each call
        mock_llm.generate.return_value = (
            "IDENTITY: Test project. STACK: Python. "
            "WORKSPACE MAP: Core (src/core, 8 files): search engine. "
            "API (src/api, 7 files): REST endpoints. "
            "CROSS-CUTTING: Core serves API. "
            + "Context padding to meet length requirements. " * 10,
            100,
        )

        atlas = CodebaseAtlas(tmp_index_dir, llm=mock_llm)
        root_doc, seg_docs = atlas.generate_segmented()

        assert root_doc.content
        assert root_doc.mode == "llm"
        assert len(seg_docs) >= 2
        for seg_doc in seg_docs:
            assert seg_doc.content
            assert seg_doc.segment_id
            assert seg_doc.mode == "llm"

        # Verify manifest was saved
        assert atlas.has_segments()
        manifest = atlas._load_segment_manifest()
        assert len(manifest) >= 2

    def test_fallback_to_single_when_few_segments(self, tmp_index_dir):
        # Only one directory group — should fall back to single atlas
        files = [f"src/core/file{i}.py" for i in range(15)]
        _write_nodes_with_paths(tmp_index_dir, files)
        _write_modules_with_files(tmp_index_dir, [
            {
                "module_id": "mod_0",
                "name": "Core",
                "summary": "Core engine with search and indexing",
                "member_files": files,
                "domain_tags": ["search"],
                "file_count": 15,
            }
        ])
        _write_manifest(tmp_index_dir, {"files_indexed": 15})
        _write_edges(tmp_index_dir, [])

        mock_llm = MagicMock()
        mock_llm.model = "test-14b"
        mock_llm.generate.return_value = (
            "IDENTITY: Test project. STACK: Python. "
            "ARCHITECTURE: Single core engine. "
            "SUBSYSTEMS: Core: src/core/file0.py, src/core/file1.py. "
            "FLOW: Request enters file0, dispatches to file1. "
            "PATTERNS: REST API. RISKS: (none flagged). "
            + "Additional context for quality gate. " * 10,
            100,
        )

        atlas = CodebaseAtlas(tmp_index_dir, llm=mock_llm)
        root_doc, seg_docs = atlas.generate_segmented()

        # Should fall back to single atlas (no segments)
        assert seg_docs == []
        assert root_doc.content

    def test_no_llm_falls_back(self, tmp_index_dir):
        files = [f"src/core/file{i}.py" for i in range(12)]
        files += [f"src/api/file{i}.py" for i in range(12)]
        _write_nodes_with_paths(tmp_index_dir, files)
        _write_manifest(tmp_index_dir, {"files_indexed": 24})
        _write_edges(tmp_index_dir, [])

        atlas = CodebaseAtlas(tmp_index_dir, llm=None)
        root_doc, seg_docs = atlas.generate_segmented()

        assert seg_docs == []
        assert root_doc.mode == "structural"


class TestAdaptiveRootBudget:
    """Tests for compute_root_atlas_budget()."""

    def test_small_project(self):
        # 50 files → full budget 1200, root = max(1200, 1200*0.55=660) = 1200
        from codrag.core.atlas import compute_root_atlas_budget
        assert compute_root_atlas_budget(50) == 1200

    def test_medium_project(self):
        # 500 files → full budget 2550, root = max(1200, 2550*0.55=1402) = 1402
        from codrag.core.atlas import compute_root_atlas_budget
        assert compute_root_atlas_budget(500) == 1402

    def test_large_project(self):
        # 2028 files → full budget min(4000, 3300+(2028-1000)*0.35) = min(4000,3659) = 3659
        # root = max(1200, min(2500, 3659*0.55=2012)) = 2012
        from codrag.core.atlas import compute_root_atlas_budget
        assert compute_root_atlas_budget(2028) == 2012

    def test_very_large_project(self):
        # 5000 files → full budget 4000, root = max(1200, min(2500, 4000*0.55=2200)) = 2200
        from codrag.core.atlas import compute_root_atlas_budget
        assert compute_root_atlas_budget(5000) == 2200

    def test_tiny_project_no_budget(self):
        from codrag.core.atlas import compute_root_atlas_budget
        assert compute_root_atlas_budget(1) == 0


class TestDisplayContent:
    """Tests for get_display_content() dashboard concatenation."""

    def test_no_segments_returns_root(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        # Save a root atlas
        doc = AtlasDocument(
            content="Root atlas content only",
            generated_at="2026-02-20T00:00:00Z",
            model="test", fingerprint="fp",
            file_count=100, module_count=5, char_count=23,
            mode="llm",
        )
        atlas._save(doc)

        content, chars = atlas.get_display_content()
        assert content == "Root atlas content only"
        assert chars == 23

    def test_concatenates_root_and_segments(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)

        # Save root atlas
        doc = AtlasDocument(
            content="IDENTITY: Test project.",
            generated_at="2026-02-20T00:00:00Z",
            model="test", fingerprint="fp",
            file_count=100, module_count=5, char_count=23,
            mode="llm",
        )
        atlas._save(doc)

        # Save segments + manifest
        segs = [
            Segment(id="core", name="Core", dir_path="src/core",
                    file_paths=["src/core/a.py"], file_count=1),
            Segment(id="api", name="Api", dir_path="src/api",
                    file_paths=["src/api/b.py"], file_count=1),
        ]
        atlas._save_segment_manifest(segs)
        atlas.segments_dir.mkdir(parents=True, exist_ok=True)

        for seg in segs:
            atlas._save_segment(SegmentDocument(
                content=f"Details for {seg.name}",
                generated_at="2026-02-20T00:00:00Z",
                model="test", fingerprint="fp",
                segment_id=seg.id, segment_name=seg.name,
                dir_path=seg.dir_path, file_count=seg.file_count,
                char_count=17, mode="llm",
            ))

        content, chars = atlas.get_display_content()
        assert "IDENTITY: Test project." in content
        assert "[CORE] (src/core)" in content
        assert "[API] (src/api)" in content
        assert "Details for Core" in content
        assert "Details for Api" in content
        assert chars > 23  # longer than root alone

    def test_no_atlas_returns_empty(self, tmp_index_dir):
        atlas = CodebaseAtlas(tmp_index_dir)
        content, chars = atlas.get_display_content()
        assert content == ""
        assert chars == 0


# ── Routing Tests ────────────────────────────────────────────────────

SegmentDescriptor = _atlas.SegmentDescriptor
build_routing_descriptors = _atlas.build_routing_descriptors
route_query = _atlas.route_query
ROUTING_MIN_SCORE = _atlas.ROUTING_MIN_SCORE
ROUTING_SEGMENT_BOOST = _atlas.ROUTING_SEGMENT_BOOST
MIN_FILES_FOR_ROUTING = _atlas.MIN_FILES_FOR_ROUTING


def _make_segment_data(idx_dir: Path, num_segments: int = 3, files_per: int = 60):
    """Create trace data that produces multiple segments."""
    nodes = []
    edges = []
    epistemic = []
    modules = []

    prefixes = ["src/core", "src/api", "src/ui", "tests", "scripts"][:num_segments]

    for seg_idx, prefix in enumerate(prefixes):
        seg_files = []
        for i in range(files_per):
            fp = f"{prefix}/file_{i}.py"
            seg_files.append(fp)
            nodes.append({"file_path": fp})
            epistemic.append({
                "node_id": f"file:{fp}",
                "architecture_layer": "core" if seg_idx == 0 else "other",
                "domain_tags": [f"domain_{seg_idx}", f"tag_{seg_idx}_{i % 5}"],
                "epistemic_confidence": 0.8,
            })
            # Add edges within segment
            if i > 0:
                prev_fp = f"{prefix}/file_{i - 1}.py"
                edges.append({"source": f"file:{prev_fp}", "target": f"file:{fp}"})

        modules.append({
            "module_id": f"module:seg{seg_idx}",
            "name": f"Segment {seg_idx} Module",
            "summary": f"Module for {prefix}",
            "member_files": seg_files,
            "domain_tags": [f"domain_{seg_idx}"],
            "architecture_layers": [],
            "component_status": "complete",
            "file_count": len(seg_files),
        })

    # Cross-segment edges
    if num_segments >= 2:
        edges.append({"source": f"file:{prefixes[0]}/file_0.py", "target": f"file:{prefixes[1]}/file_0.py"})

    _write_nodes(idx_dir, nodes)
    _write_edges(idx_dir, edges)
    _write_epistemic(idx_dir, epistemic)
    _write_modules(idx_dir, modules)
    _write_manifest(idx_dir, {"files_indexed": num_segments * files_per})


class TestSegmentDescriptor:

    def test_roundtrip(self):
        desc = SegmentDescriptor(
            segment_id="src-core",
            dir_path="src/core",
            name="Core Engine",
            covers="Covers: indexing search trace graph embedding",
            key_files=["src/core/index.py", "src/core/trace.py"],
            boundaries=["→ src-api (12 edges)"],
            file_paths=["src/core/index.py", "src/core/trace.py"],
            file_count=2,
            fingerprint="abc123",
            generated_at="2026-02-20T00:00:00Z",
        )
        d = desc.to_dict()
        restored = SegmentDescriptor.from_dict(d)
        assert restored.segment_id == "src-core"
        assert restored.covers == desc.covers
        assert restored.key_files == desc.key_files
        assert restored.boundaries == desc.boundaries
        assert restored.file_count == 2

    def test_from_dict_defaults(self):
        desc = SegmentDescriptor.from_dict({"segment_id": "test"})
        assert desc.segment_id == "test"
        assert desc.covers == ""
        assert desc.key_files == []
        assert desc.file_count == 0


class TestBuildRoutingDescriptors:

    def test_empty_segments(self):
        assert build_routing_descriptors([], Path("/nonexistent")) == []

    def test_builds_descriptors_from_pipeline_data(self, tmp_path):
        idx = tmp_path / "index"
        idx.mkdir()
        _make_segment_data(idx, num_segments=3, files_per=10)

        segments = compute_segments(idx)
        assert len(segments) >= 2

        descriptors = build_routing_descriptors(segments, idx)
        assert len(descriptors) == len(segments)

        for desc in descriptors:
            assert desc.segment_id
            assert desc.covers  # Non-empty COVERS text
            assert desc.file_count > 0
            assert desc.fingerprint
            assert len(desc.file_paths) > 0

    def test_covers_contains_domain_tags(self, tmp_path):
        idx = tmp_path / "index"
        idx.mkdir()
        _make_segment_data(idx, num_segments=2, files_per=10)

        segments = compute_segments(idx)
        descriptors = build_routing_descriptors(segments, idx)

        # COVERS should contain domain vocabulary from epistemic tags
        for desc in descriptors:
            assert "Covers:" in desc.covers or "Segment:" in desc.covers

    def test_key_files_from_hub_detection(self, tmp_path):
        idx = tmp_path / "index"
        idx.mkdir()
        _make_segment_data(idx, num_segments=2, files_per=10)

        segments = compute_segments(idx)
        descriptors = build_routing_descriptors(segments, idx)

        # At least some descriptors should have key files (from edge in-degree)
        has_key_files = any(len(d.key_files) > 0 for d in descriptors)
        assert has_key_files

    def test_boundaries_detected(self, tmp_path):
        idx = tmp_path / "index"
        idx.mkdir()
        _make_segment_data(idx, num_segments=2, files_per=10)

        segments = compute_segments(idx)
        descriptors = build_routing_descriptors(segments, idx)

        # Cross-segment edges exist in test data
        has_boundaries = any(len(d.boundaries) > 0 for d in descriptors)
        assert has_boundaries


class TestRouteQuery:

    def _make_embeddings(self, n_descriptors: int, dim: int = 768):
        """Create synthetic descriptor embeddings."""
        import numpy as np
        rng = np.random.RandomState(42)
        return rng.randn(n_descriptors, dim).astype(np.float32)

    def _make_descriptors(self, n: int) -> list:
        return [
            SegmentDescriptor(
                segment_id=f"seg-{i}",
                dir_path=f"src/seg{i}",
                name=f"Segment {i}",
                covers=f"domain_{i} tag_{i}",
                key_files=[f"src/seg{i}/main.py"],
                boundaries=[],
                file_paths=[f"src/seg{i}/f{j}.py" for j in range(10)],
                file_count=10,
                fingerprint=f"fp{i}",
            )
            for i in range(n)
        ]

    def test_empty_inputs(self):
        import numpy as np
        assert route_query(np.zeros(768), None, []) == []
        assert route_query(np.zeros(768), np.zeros((0, 768)), []) == []

    def test_routes_to_most_similar(self):
        import numpy as np

        descs = self._make_descriptors(3)
        # Make descriptor 1 very similar to query
        dim = 768
        query = np.random.RandomState(99).randn(dim).astype(np.float32)
        embeddings = np.random.RandomState(42).randn(3, dim).astype(np.float32)
        embeddings[1] = query + np.random.RandomState(0).randn(dim).astype(np.float32) * 0.1

        results = route_query(query, embeddings, descs, min_score=0.0, max_segments=3)
        assert len(results) >= 1
        # Best match should be segment 1 (closest to query)
        assert results[0][0].segment_id == "seg-1"
        assert results[0][1] > results[-1][1]  # Sorted by score

    def test_min_score_filtering(self):
        import numpy as np
        descs = self._make_descriptors(3)
        embeddings = np.random.RandomState(42).randn(3, 768).astype(np.float32)
        query = np.random.RandomState(99).randn(768).astype(np.float32)

        # With very high min_score, nothing should match
        results = route_query(query, embeddings, descs, min_score=0.99)
        assert len(results) == 0

    def test_max_segments_cap(self):
        import numpy as np
        descs = self._make_descriptors(5)
        query = np.ones(768, dtype=np.float32)
        embeddings = np.ones((5, 768), dtype=np.float32)  # All similar

        results = route_query(query, embeddings, descs, min_score=0.0, max_segments=2)
        assert len(results) <= 2


class TestCodebaseAtlasRouting:

    def test_has_routing_false_initially(self, tmp_path):
        idx = tmp_path / "index"
        idx.mkdir()
        atlas = CodebaseAtlas(idx)
        assert atlas.has_routing() is False

    def test_load_routing_empty(self, tmp_path):
        idx = tmp_path / "index"
        idx.mkdir()
        atlas = CodebaseAtlas(idx)
        descs, emb = atlas.load_routing()
        assert descs == []
        assert emb is None

    def test_save_and_load_routing(self, tmp_path):
        import numpy as np

        idx = tmp_path / "index"
        idx.mkdir()
        atlas = CodebaseAtlas(idx)

        descs = [
            SegmentDescriptor(
                segment_id="seg-0", dir_path="src/core", name="Core",
                covers="indexing search", key_files=["src/core/index.py"],
                boundaries=[], file_paths=["src/core/index.py"],
                file_count=1, fingerprint="fp0",
            ),
            SegmentDescriptor(
                segment_id="seg-1", dir_path="src/api", name="API",
                covers="api endpoints", key_files=["src/api/server.py"],
                boundaries=[], file_paths=["src/api/server.py"],
                file_count=1, fingerprint="fp1",
            ),
        ]
        embeddings = np.random.randn(2, 768).astype(np.float32)

        atlas._save_routing(descs, embeddings, "test-model")

        assert atlas.has_routing()
        loaded_descs, loaded_emb = atlas.load_routing()
        assert len(loaded_descs) == 2
        assert loaded_descs[0].segment_id == "seg-0"
        assert loaded_descs[1].covers == "api endpoints"
        assert loaded_emb.shape == (2, 768)
        np.testing.assert_array_almost_equal(loaded_emb, embeddings)

    def test_get_routed_file_paths(self, tmp_path):
        idx = tmp_path / "index"
        idx.mkdir()
        atlas = CodebaseAtlas(idx)

        desc_a = SegmentDescriptor(
            segment_id="a", dir_path="src/a", name="A",
            covers="", key_files=[], boundaries=[],
            file_paths=["src/a/f1.py", "src/a/f2.py"],
            file_count=2, fingerprint="fp",
        )
        desc_b = SegmentDescriptor(
            segment_id="b", dir_path="src/b", name="B",
            covers="", key_files=[], boundaries=[],
            file_paths=["src/b/g1.py"],
            file_count=1, fingerprint="fp",
        )
        selected = [(desc_a, 0.9), (desc_b, 0.7)]
        paths = atlas.get_routed_file_paths(selected)
        assert paths == {"src/a/f1.py", "src/a/f2.py", "src/b/g1.py"}

    def test_generate_routing_below_threshold(self, tmp_path):
        idx = tmp_path / "index"
        idx.mkdir()
        # Tiny project — should not generate routing
        _write_nodes(idx, [{"file_path": f"f{i}.py"} for i in range(10)])
        _write_manifest(idx, {"files_indexed": 10})

        mock_embedder = MagicMock()
        atlas = CodebaseAtlas(idx)
        result = atlas.generate_routing(mock_embedder)
        assert result == []
        assert atlas.has_routing() is False
