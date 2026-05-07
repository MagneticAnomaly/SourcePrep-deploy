"""
Determinism guard for atlas + module-list emission.

Closes Task #5 from the 2026-05-05 dogfood scrutiny pass — see
docs/Phase124_FinalizeChainEpistemicAudit/MCP_DOGFOOD_FEEDBACK_2026-05-05_SCRUTINY.md
item #5. Module file counts drifted between consecutive prep calls 3
days apart on the same project. The drift could come from any of:

1. Module clustering (upstream of these tests — Leiden + heuristics).
2. Atlas structural rendering reading the modules.
3. Module-list emission in the ambient context.

This file pins **(2) and (3)** — the deterministic-by-design layers.
The LLM atlas path is intentionally non-deterministic (temperature 0.3
in generator.py:558) and is NOT covered here. The clustering layer is
out of scope for this guard; if the upstream JSONL is identical, every
downstream consumer must produce identical output.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from prep.api.routers.projects.search import _format_module_tiers
from prep.core.atlas.role_resolver import resolve_role
from prep.core.context_tier import ContextTier

_atlas = importlib.import_module("prep.core.atlas")
CodebaseAtlas = _atlas.CodebaseAtlas


@pytest.fixture
def populated_index(tmp_path):
    """Mirror the minimal _populate_index helper from test_atlas.py without
    coupling this file to that test's private fixtures."""
    idx = tmp_path / "idx"
    idx.mkdir()

    modules: List[Dict[str, Any]] = [
        {
            "module_id": "module:core:0",
            "name": "Core Engine",
            "summary": "Indexing and search engine.",
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
            "summary": "React dashboard.",
            "member_files": ["ui/App.tsx", "ui/Search.tsx"],
            "domain_tags": ["ui", "dashboard"],
            "architecture_layers": ["presentation"],
            "component_status": "partial",
            "file_count": 2,
            "dependencies": ["core"],
        },
    ]
    nodes = [
        {"node_id": f"file:{p}", "file_path": p}
        for p in ["src/index.py", "src/search.py", "src/embedder.py",
                  "ui/App.tsx", "ui/Search.tsx"]
    ]
    edges = [
        {"source": "file:src/search.py", "target": "file:src/index.py", "kind": "imports"},
        {"source": "file:ui/App.tsx", "target": "file:src/index.py", "kind": "imports"},
    ]

    with open(idx / "trace_modules.jsonl", "w") as f:
        for m in modules:
            f.write(json.dumps(m) + "\n")
    with open(idx / "trace_nodes.jsonl", "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")
    with open(idx / "trace_edges.jsonl", "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")
    with open(idx / "trace_manifest.json", "w") as f:
        json.dump({"stats": {"files_indexed": 5}}, f)
    return idx


# ── Module list emission determinism ─────────────────────────────────


def test_format_module_tiers_is_deterministic_no_role():
    """Same module list -> same output text. Pure-function determinism."""
    modules = [
        {"name": "Auth", "module_id": "auth", "summary": "x", "file_count": 30,
         "domain_tags": ["security"], "dependencies": []},
        {"name": "UI", "module_id": "ui", "summary": "y", "file_count": 25,
         "domain_tags": ["ui"], "dependencies": []},
    ]
    out_a = _format_module_tiers(modules, context_tier=ContextTier.TIER_2, role=None)
    out_b = _format_module_tiers(modules, context_tier=ContextTier.TIER_2, role=None)
    assert out_a == out_b


def test_format_module_tiers_is_deterministic_with_role():
    """Role-weighted ranking must also be deterministic — role lens must
    not introduce non-determinism via dict-iteration or set-iteration."""
    modules = [
        {"name": "A", "module_id": "a", "summary": "", "file_count": 30,
         "domain_tags": ["security"], "dependencies": []},
        {"name": "B", "module_id": "b", "summary": "", "file_count": 30,
         "domain_tags": ["security"], "dependencies": []},
        {"name": "C", "module_id": "c", "summary": "", "file_count": 30,
         "domain_tags": ["marketing"], "dependencies": []},
    ]
    role = resolve_role("security")
    outs = [
        _format_module_tiers(modules, context_tier=ContextTier.TIER_2, role=role)
        for _ in range(5)
    ]
    assert all(o == outs[0] for o in outs)


# ── Structural atlas determinism (no LLM) ────────────────────────────


def test_structural_atlas_is_deterministic(populated_index):
    """The structural atlas path (no LLM) must produce identical output
    on identical input. If this regresses, expect drift symptoms like
    those reported in the 2026-05-02/05 dogfood pass."""
    atlas_a = CodebaseAtlas(populated_index, llm=None).generate_structural()
    atlas_b = CodebaseAtlas(populated_index, llm=None).generate_structural()
    # Content + structural counts must match. generated_at can differ.
    assert atlas_a.content == atlas_b.content
    assert atlas_a.module_count == atlas_b.module_count
    assert atlas_a.file_count == atlas_b.file_count
    assert atlas_a.fingerprint == atlas_b.fingerprint
    assert atlas_a.mode == atlas_b.mode == "structural"


def test_structural_atlas_fingerprint_stable_across_loads(populated_index):
    """Fingerprint must be a pure function of inputs — independent of how
    many times the atlas is generated/saved/reloaded."""
    atlas = CodebaseAtlas(populated_index, llm=None)
    doc1 = atlas.generate_structural()
    fp1 = doc1.fingerprint

    # Reload + regenerate — fingerprint should still match
    atlas2 = CodebaseAtlas(populated_index, llm=None)
    doc2 = atlas2.generate_structural()
    assert doc2.fingerprint == fp1
