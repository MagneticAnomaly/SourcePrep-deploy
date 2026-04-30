"""GroupReasoningEngine.load_existing respects the reset barrier."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _seed_existing(idx_dir: Path, n: int) -> None:
    """Seed trace_group_reasoning.jsonl with N entries."""
    idx_dir.mkdir(parents=True, exist_ok=True)
    path = idx_dir / "trace_group_reasoning.jsonl"
    with open(path, "w") as f:
        for i in range(n):
            f.write(json.dumps({
                "group_id": f"group:{i}",
                "member_node_ids": [f"file:a{i}.py", f"file:b{i}.py"],
                "pattern": "Repository Pattern",
                "data_flow": "A -> B",
                "coupling_risks": [],
                "blast_radius": [],
                "architectural_insight": "...",
                "confidence": 0.7,
                "analyzed_at": "2026-01-01T00:00:00Z",
                "model": "test-model",
                "member_fingerprint": f"fp{i}",
            }) + "\n")


def test_load_existing_returns_empty_when_barrier_blocks(tmp_path: Path) -> None:
    from prep.core.group_reasoning import GroupReasoningEngine
    _seed_existing(tmp_path, 3)

    engine = GroupReasoningEngine.__new__(GroupReasoningEngine)
    engine.output_path = tmp_path / "trace_group_reasoning.jsonl"
    engine.index_dir = tmp_path
    engine.project_id = "proj-X"

    with patch("prep.core.group_reasoning.is_reuse_blocked", return_value=True):
        result = engine.load_existing()

    assert result == {}


def test_load_existing_returns_data_when_barrier_clear(tmp_path: Path) -> None:
    from prep.core.group_reasoning import GroupReasoningEngine
    _seed_existing(tmp_path, 2)

    engine = GroupReasoningEngine.__new__(GroupReasoningEngine)
    engine.output_path = tmp_path / "trace_group_reasoning.jsonl"
    engine.index_dir = tmp_path
    engine.project_id = "proj-Y"

    with patch("prep.core.group_reasoning.is_reuse_blocked", return_value=False):
        result = engine.load_existing()

    assert len(result) == 2


def test_constructor_accepts_project_id_kwarg(tmp_path: Path) -> None:
    from prep.core.group_reasoning import GroupReasoningEngine
    llm = MagicMock()
    engine = GroupReasoningEngine(llm=llm, index_dir=tmp_path, project_id="proj-Z")
    assert engine.project_id == "proj-Z"
