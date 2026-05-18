"""Tests for swarm orchestration in Clustering (Stage 8)."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from prep.core.cluster import ClusterSynthesizer, Cluster, ModuleEntry
from prep.core.swarm_registry import SwarmTier


def _make_clusters(n: int) -> list[Cluster]:
    """Create n clusters with 3 files each."""
    clusters = []
    for i in range(n):
        clusters.append(Cluster(
            cluster_id=f"cluster:mod{i}:0",
            primary_tag=f"module_{i}",
            member_node_ids=[
                f"file:src/mod{i}/file{j}.py" for j in range(3)
            ],
            all_tags={f"module_{i}", "python"},
        ))
    return clusters


def _make_epistemic(clusters: list[Cluster]) -> dict:
    """Build minimal epistemic entries for all cluster members."""
    from prep.core.epistemic_score import EpistemicEntry
    entries = {}
    for cluster in clusters:
        for nid in cluster.member_node_ids:
            fp = nid.replace("file:", "", 1)
            entries[nid] = EpistemicEntry(
                node_id=nid,
                extended_summary=f"Module file at {fp}",
                architecture_layer="service",
                domain_tags=[cluster.primary_tag],
                tech_debt=[],
                epistemic_confidence=0.8,
                model="test-model",
                enriched_at="2026-04-07T00:00:00Z",
            )
    return entries


def _make_mock_llm():
    mock = MagicMock()
    mock.provider = "ollama"
    mock.model = "kimi-k2.5:cloud"
    mock.generate.return_value = (
        json.dumps({
            "name": "Test Module",
            "summary": "A test module.",
            "component_status": "complete",
            "data_flow": "A -> B",
            "dependencies": [],
            "tech_debt_summary": None,
        }),
        200,
    )
    return mock


class TestClusterSwarmDecision:
    @patch("prep.core.cluster.get_swarm_tier")
    def test_swarm_activated_when_eligible(self, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)

        clusters = _make_clusters(4)
        epistemic = _make_epistemic(clusters)

        with patch.object(synth, "_run_swarm", return_value={}) as mock_swarm:
            with patch.object(synth, "_get_swarm_enabled", return_value=True):
                with patch.object(synth, "load_epistemic", return_value=epistemic):
                    with patch.object(synth, "load_edges", return_value=[]):
                        with patch("prep.core.cluster.build_clusters", return_value=clusters):
                            # Phase 136 Part 13: simulate scheduler granting
                            # the swarm window — without this patch the new
                            # `is_my_swarm_window` gate falls the synth
                            # back to non-swarm dispatch.
                            with patch(
                                "prep.services.pipeline.scheduler.pipeline_scheduler.is_my_swarm_window",
                                return_value=True,
                            ):
                                synth.run()
                                mock_swarm.assert_called_once()

    @patch("prep.core.cluster.get_swarm_tier")
    def test_swarm_skipped_when_model_unsuitable(self, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.UNSUITABLE
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)

        clusters = _make_clusters(4)
        epistemic = _make_epistemic(clusters)

        with patch.object(synth, "_run_swarm") as mock_swarm:
            with patch.object(synth, "_get_swarm_enabled", return_value=True):
                with patch.object(synth, "load_epistemic", return_value=epistemic):
                    with patch.object(synth, "load_edges", return_value=[]):
                        with patch("prep.core.cluster.build_clusters", return_value=clusters):
                            synth.run()
                            mock_swarm.assert_not_called()

    @patch("prep.core.cluster.get_swarm_tier")
    def test_swarm_skipped_when_disabled(self, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)

        clusters = _make_clusters(4)
        epistemic = _make_epistemic(clusters)

        with patch.object(synth, "_run_swarm") as mock_swarm:
            with patch.object(synth, "_get_swarm_enabled", return_value=False):
                with patch.object(synth, "load_epistemic", return_value=epistemic):
                    with patch.object(synth, "load_edges", return_value=[]):
                        with patch("prep.core.cluster.build_clusters", return_value=clusters):
                            synth.run()
                            mock_swarm.assert_not_called()

    @patch("prep.core.cluster.get_swarm_tier")
    def test_swarm_skipped_below_threshold(self, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)

        clusters = _make_clusters(2)  # Below threshold of 3
        epistemic = _make_epistemic(clusters)

        with patch.object(synth, "_run_swarm") as mock_swarm:
            with patch.object(synth, "_get_swarm_enabled", return_value=True):
                with patch.object(synth, "load_epistemic", return_value=epistemic):
                    with patch.object(synth, "load_edges", return_value=[]):
                        with patch("prep.core.cluster.build_clusters", return_value=clusters):
                            synth.run()
                            mock_swarm.assert_not_called()

    def test_get_swarm_enabled_defaults_true(self, tmp_path):
        mock_llm = _make_mock_llm()
        synth = ClusterSynthesizer(llm=mock_llm, index_dir=tmp_path)
        assert synth._get_swarm_enabled() is True
