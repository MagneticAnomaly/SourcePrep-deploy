"""ClusterSynthesizer.load_existing_modules respects the reset barrier."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _seed_modules_file(idx_dir: Path, n: int) -> None:
    idx_dir.mkdir(parents=True, exist_ok=True)
    path = idx_dir / "trace_modules.jsonl"
    with open(path, "w") as f:
        for i in range(n):
            f.write(json.dumps({
                "module_id": f"m{i}",
                "name": f"module_{i}",
                "summary": "x",
                "domain_tags": [],
                "architecture_layers": [],
                "component_status": "unknown",
                "member_files": [],
            }) + "\n")


def test_load_existing_modules_returns_empty_when_barrier_blocks(tmp_path: Path) -> None:
    from prep.core.cluster import ClusterSynthesizer
    _seed_modules_file(tmp_path, 5)

    synth = ClusterSynthesizer.__new__(ClusterSynthesizer)
    synth.modules_path = tmp_path / "trace_modules.jsonl"
    synth.index_dir = tmp_path
    synth.project_id = "proj-X"

    with patch("prep.core.cluster.is_reuse_blocked", return_value=True):
        result = synth.load_existing_modules()

    assert result == {}


def test_load_existing_modules_returns_data_when_barrier_clear(tmp_path: Path) -> None:
    from prep.core.cluster import ClusterSynthesizer
    _seed_modules_file(tmp_path, 3)

    synth = ClusterSynthesizer.__new__(ClusterSynthesizer)
    synth.modules_path = tmp_path / "trace_modules.jsonl"
    synth.index_dir = tmp_path
    synth.project_id = "proj-Y"

    with patch("prep.core.cluster.is_reuse_blocked", return_value=False):
        result = synth.load_existing_modules()

    assert len(result) == 3


def test_constructor_accepts_project_id_kwarg(tmp_path: Path) -> None:
    """ClusterSynthesizer must accept project_id so callers can thread it through."""
    from prep.core.cluster import ClusterSynthesizer
    llm = MagicMock()
    synth = ClusterSynthesizer(llm=llm, index_dir=tmp_path, project_id="proj-Z")
    assert synth.project_id == "proj-Z"
