"""Tests for swarm integration in GroupReasoningEngine."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.core.group_reasoning import GroupReasoningEngine, GroupReasoningEntry
from prep.core.swarm_registry import SwarmTier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_epistemic_line(node_id: str, layer: str = "service") -> str:
    """Build a single trace_epistemic.jsonl line."""
    return json.dumps({
        "node_id": node_id,
        "extended_summary": f"Summary for {node_id}",
        "architecture_layer": layer,
        "domain_tags": ["core"],
        "tech_debt": [],
        "epistemic_confidence": 0.8,
        "model": "test-model",
        "enriched_at": "2026-01-01T00:00:00Z",
    })


def _make_edge_line(source: str, target: str, kind: str = "import") -> str:
    """Build a single trace_edges.jsonl line."""
    return json.dumps({"source": source, "target": target, "kind": kind})


@pytest.fixture()
def tmp_index_dir(tmp_path: Path):
    """Create index dir with enough epistemic + edge data for 4 groups of 3 files.

    Groups are isolated from each other (no cross-group edges), so
    build_dependency_groups will produce 4 separate connected components.
    """
    # 4 groups, 3 files each => 12 files
    epistemic_lines = []
    edge_lines = []
    for g in range(4):
        files = [f"file:mod{g}/f{i}.py" for i in range(3)]
        for f in files:
            epistemic_lines.append(_make_epistemic_line(f))
        # Chain edges within each group: f0->f1, f1->f2
        edge_lines.append(_make_edge_line(files[0], files[1]))
        edge_lines.append(_make_edge_line(files[1], files[2]))

    (tmp_path / "trace_epistemic.jsonl").write_text(
        "\n".join(epistemic_lines) + "\n", encoding="utf-8",
    )
    (tmp_path / "trace_edges.jsonl").write_text(
        "\n".join(edge_lines) + "\n", encoding="utf-8",
    )
    return tmp_path


def _build_engine(index_dir: Path) -> GroupReasoningEngine:
    """Create an engine with a mock LLM."""
    llm = MagicMock()
    llm.provider = "anthropic"
    llm.model = "claude-sonnet-4-20250514"
    return GroupReasoningEngine(llm=llm, index_dir=index_dir)


# ---------------------------------------------------------------------------
# TestGroupReasoningSwarmDecision
# ---------------------------------------------------------------------------

class TestGroupReasoningSwarmDecision:
    """Verify the swarm vs. standard-path decision branch in run()."""

    @patch("prep.core.group_reasoning.get_swarm_tier")
    def test_swarm_activated_when_eligible(
        self, mock_tier, tmp_index_dir,
    ):
        """If tier=BOTH, swarm enabled, and groups >= threshold => _run_swarm called."""
        mock_tier.return_value = SwarmTier.BOTH
        engine = _build_engine(tmp_index_dir)

        # Stub _run_swarm to return fake entries so run() takes the swarm path
        fake_entry = GroupReasoningEntry(
            group_id="g1",
            member_node_ids=["a"],
            pattern="test",
            data_flow="",
            coupling_risks=[],
            blast_radius=[],
            architectural_insight="",
        )
        with patch.object(engine, "_run_swarm", return_value={"g1": fake_entry}) as mock_run:
            with patch.object(engine, "_get_swarm_enabled", return_value=True):
                result = engine.run()

        mock_run.assert_called_once()
        assert result.get("swarm") is True

    @patch("prep.core.group_reasoning.get_swarm_tier")
    def test_swarm_skipped_when_model_unsuitable(
        self, mock_tier, tmp_index_dir,
    ):
        """If tier=UNSUITABLE => _run_swarm NOT called, standard path used."""
        mock_tier.return_value = SwarmTier.UNSUITABLE
        engine = _build_engine(tmp_index_dir)

        # Mock the standard analyze_group to avoid real LLM calls
        with patch.object(engine, "_run_swarm") as mock_run:
            with patch.object(engine, "analyze_group", return_value=None):
                with patch("prep.core.batch_profiles.get_batch_concurrency", return_value=1):
                    engine.run()

        mock_run.assert_not_called()

    @patch("prep.core.group_reasoning.get_swarm_tier")
    def test_swarm_skipped_when_disabled_by_user(
        self, mock_tier, tmp_index_dir,
    ):
        """If swarm_enabled=False => _run_swarm NOT called even with BOTH tier."""
        mock_tier.return_value = SwarmTier.BOTH
        engine = _build_engine(tmp_index_dir)

        with patch.object(engine, "_run_swarm") as mock_run:
            with patch.object(engine, "_get_swarm_enabled", return_value=False):
                with patch.object(engine, "analyze_group", return_value=None):
                    with patch("prep.core.batch_profiles.get_batch_concurrency", return_value=1):
                        engine.run()

        mock_run.assert_not_called()

    @patch("prep.core.group_reasoning.get_swarm_tier")
    def test_swarm_skipped_below_threshold(
        self, mock_tier, tmp_path,
    ):
        """If fewer groups than min_groups_threshold => _run_swarm NOT called."""
        mock_tier.return_value = SwarmTier.BOTH

        # Only 2 groups (below default threshold of 3)
        epistemic_lines = []
        edge_lines = []
        for g in range(2):
            files = [f"file:mod{g}/f{i}.py" for i in range(3)]
            for f in files:
                epistemic_lines.append(_make_epistemic_line(f))
            edge_lines.append(_make_edge_line(files[0], files[1]))
            edge_lines.append(_make_edge_line(files[1], files[2]))

        (tmp_path / "trace_epistemic.jsonl").write_text(
            "\n".join(epistemic_lines) + "\n", encoding="utf-8",
        )
        (tmp_path / "trace_edges.jsonl").write_text(
            "\n".join(edge_lines) + "\n", encoding="utf-8",
        )

        engine = _build_engine(tmp_path)

        with patch.object(engine, "_run_swarm") as mock_run:
            with patch.object(engine, "_get_swarm_enabled", return_value=True):
                # Threshold is 3, we have 2 groups to analyze
                with patch("prep.core.group_reasoning.get_min_groups_threshold", return_value=3):
                    with patch.object(engine, "analyze_group", return_value=None):
                        with patch("prep.core.batch_profiles.get_batch_concurrency", return_value=1):
                            engine.run()

        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# TestSwarmSetting
# ---------------------------------------------------------------------------

class TestSwarmSetting:
    """Tests for _get_swarm_enabled helper."""

    def test_get_swarm_enabled_defaults_true(self, tmp_path):
        """When settings store isn't initialised, default is True."""
        engine = _build_engine(tmp_path)
        # Patch the import inside the method to raise, simulating uninitialised store
        with patch.dict("sys.modules", {"prep.services.settings_store": None}):
            result = engine._get_swarm_enabled()
        assert result is True
