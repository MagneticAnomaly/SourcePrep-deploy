"""Tests for swarm orchestration in Atlas Generation (Stage 9)."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from prep.core.atlas.generator import CodebaseAtlas
from prep.core.atlas.models import Segment, AtlasDocument, SegmentDocument
from prep.core.swarm_orchestrator import SwarmResult, SwarmStats
from prep.core.swarm_registry import SwarmTier


def _make_segments(n: int) -> list[Segment]:
    """Create n segments with some files each."""
    segments = []
    for i in range(n):
        segments.append(Segment(
            id=f"seg:pkg{i}",
            name=f"Package {i}",
            dir_path=f"packages/pkg{i}",
            file_paths=[f"packages/pkg{i}/file{j}.py" for j in range(5)],
            module_ids=[f"module:pkg{i}:0"],
            domain_tags=[f"domain_{i}"],
            file_count=5,
        ))
    return segments


def _make_mock_llm():
    mock = MagicMock()
    mock.provider = "ollama"
    mock.model = "kimi-k2.5:cloud"
    mock.generate.return_value = (
        "SEGMENT: Test (test/, 5 files)\nROLE: Test segment.\nKEY FILES: file0.py: main entry.",
        200,
    )
    return mock


def _make_root_doc():
    return AtlasDocument(
        content="IDENTITY: Test project.\nSTACK: Python.",
        generated_at="2026-04-07T00:00:00Z",
        model="test",
        file_count=50,
        module_count=4,
        char_count=38,
        mode="segmented",
        segment_ids=["seg:pkg0", "seg:pkg1", "seg:pkg2", "seg:pkg3"],
    )


class TestAtlasSwarmDecision:
    @patch("prep.core.atlas.generator.get_swarm_tier")
    @patch("prep.core.atlas.generator.compute_segments")
    def test_swarm_activated_when_eligible(self, mock_segments, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        segments = _make_segments(4)
        mock_segments.return_value = segments

        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)

        # Return non-empty docs so the success path (early return) is tested
        mock_docs = [
            SegmentDocument(
                content="SEGMENT: test", generated_at="2026-04-07", model="test",
                file_count=5, segment_id=f"seg:pkg{i}",
                segment_name=f"Package {i}", dir_path=f"packages/pkg{i}",
                char_count=13, mode="llm",
            )
            for i in range(4)
        ]
        mock_result = SwarmResult(stats=SwarmStats(total_items=4, workers_succeeded=4))

        with patch.object(atlas, "_run_swarm", return_value=(mock_docs, mock_result)) as mock_swarm:
            with patch.object(atlas, "_get_swarm_enabled", return_value=True):
                with patch.object(atlas, "_load_modules", return_value=[]):
                    with patch.object(atlas, "_load_epistemic_summary", return_value={}):
                        with patch.object(atlas, "_load_graph_stats", return_value={"file_count": 50}):
                            with patch.object(atlas, "_identify_hubs", return_value=[]):
                                with patch.object(atlas, "_generate_root_atlas", return_value=_make_root_doc()):
                                    root_doc, seg_docs = atlas.generate_segmented()
                                    mock_swarm.assert_called_once()
                                    assert len(seg_docs) == 4  # swarm docs returned

    @patch("prep.core.atlas.generator.get_swarm_tier")
    @patch("prep.core.atlas.generator.compute_segments")
    def test_swarm_skipped_when_model_unsuitable(self, mock_segments, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.UNSUITABLE
        segments = _make_segments(4)
        mock_segments.return_value = segments

        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)

        with patch.object(atlas, "_run_swarm") as mock_swarm:
            with patch.object(atlas, "_get_swarm_enabled", return_value=True):
                with patch.object(atlas, "_load_modules", return_value=[]):
                    with patch.object(atlas, "_load_epistemic_summary", return_value={}):
                        with patch.object(atlas, "_load_graph_stats", return_value={"file_count": 50}):
                            with patch.object(atlas, "_identify_hubs", return_value=[]):
                                with patch.object(atlas, "_generate_root_atlas", return_value=_make_root_doc()):
                                    with patch.object(atlas, "_generate_segment_atlas") as mock_seg:
                                        mock_seg.return_value = SegmentDocument(
                                            content="test", generated_at="2026-04-07", model="test",
                                            file_count=5, segment_id="seg:pkg0",
                                            dir_path="packages/pkg0", segment_name="Package 0",
                                            char_count=4, mode="llm",
                                        )
                                        atlas.generate_segmented()
                                        mock_swarm.assert_not_called()

    @patch("prep.core.atlas.generator.get_swarm_tier")
    @patch("prep.core.atlas.generator.compute_segments")
    def test_swarm_skipped_when_disabled(self, mock_segments, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        segments = _make_segments(4)
        mock_segments.return_value = segments

        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)

        with patch.object(atlas, "_run_swarm") as mock_swarm:
            with patch.object(atlas, "_get_swarm_enabled", return_value=False):
                with patch.object(atlas, "_load_modules", return_value=[]):
                    with patch.object(atlas, "_load_epistemic_summary", return_value={}):
                        with patch.object(atlas, "_load_graph_stats", return_value={"file_count": 50}):
                            with patch.object(atlas, "_identify_hubs", return_value=[]):
                                with patch.object(atlas, "_generate_root_atlas", return_value=_make_root_doc()):
                                    with patch.object(atlas, "_generate_segment_atlas") as mock_seg:
                                        mock_seg.return_value = SegmentDocument(
                                            content="test", generated_at="2026-04-07", model="test",
                                            file_count=5, segment_id="seg:pkg0",
                                            dir_path="packages/pkg0", segment_name="Package 0",
                                            char_count=4, mode="llm",
                                        )
                                        atlas.generate_segmented()
                                        mock_swarm.assert_not_called()

    @patch("prep.core.atlas.generator.get_swarm_tier")
    @patch("prep.core.atlas.generator.compute_segments")
    def test_swarm_skipped_below_threshold(self, mock_segments, mock_tier, tmp_path):
        mock_tier.return_value = SwarmTier.BOTH
        segments = _make_segments(2)  # Below threshold of 3
        mock_segments.return_value = segments

        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)

        with patch.object(atlas, "_run_swarm") as mock_swarm:
            with patch.object(atlas, "_get_swarm_enabled", return_value=True):
                with patch.object(atlas, "_load_modules", return_value=[]):
                    with patch.object(atlas, "_load_epistemic_summary", return_value={}):
                        with patch.object(atlas, "_load_graph_stats", return_value={"file_count": 50}):
                            with patch.object(atlas, "_identify_hubs", return_value=[]):
                                with patch.object(atlas, "_generate_root_atlas", return_value=_make_root_doc()):
                                    with patch.object(atlas, "_generate_segment_atlas") as mock_seg:
                                        mock_seg.return_value = SegmentDocument(
                                            content="test", generated_at="2026-04-07", model="test",
                                            file_count=5, segment_id="seg:pkg0",
                                            dir_path="packages/pkg0", segment_name="Package 0",
                                            char_count=4, mode="llm",
                                        )
                                        atlas.generate_segmented()
                                        mock_swarm.assert_not_called()

    def test_get_swarm_enabled_defaults_true(self, tmp_path):
        mock_llm = _make_mock_llm()
        atlas = CodebaseAtlas(index_dir=tmp_path, llm=mock_llm)
        assert atlas._get_swarm_enabled() is True
