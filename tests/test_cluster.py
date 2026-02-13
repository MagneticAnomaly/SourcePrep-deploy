"""Tests for cluster synthesis (Pass 3)."""
import pytest

from codrag.core.cluster import (
    Cluster,
    ModuleEntry,
    build_clusters,
    _connected_components,
    _merge_small_clusters,
)
from codrag.core.epistemic_score import EpistemicEntry


def make_entry(node_id: str, tags: list, subsystem: str = None) -> EpistemicEntry:
    return EpistemicEntry(
        node_id=node_id,
        extended_summary=f"Summary for {node_id}",
        domain_tags=tags,
        architecture_layer="business_logic",
        subsystem=subsystem,
        epistemic_confidence=0.85,
    )


class TestBuildClusters:
    def test_groups_by_primary_tag(self):
        """Files with the same primary domain_tag cluster together."""
        entries = {
            "file:src/ad_manager.py": make_entry("file:src/ad_manager.py", ["monetization", "ads"]),
            "file:src/ad_banner.py": make_entry("file:src/ad_banner.py", ["monetization", "ui"]),
            "file:src/auth.py": make_entry("file:src/auth.py", ["auth", "security"]),
        }
        edges = [
            {"source": "file:src/ad_manager.py", "target": "file:src/ad_banner.py", "kind": "imports"},
        ]
        clusters = build_clusters(entries, edges, min_cluster_size=1)

        # Should have 2 clusters: monetization (2 files) and auth (1 file)
        tags = {c.primary_tag for c in clusters}
        assert "monetization" in tags
        assert "auth" in tags

        monetization = next(c for c in clusters if c.primary_tag == "monetization")
        assert len(monetization.member_node_ids) == 2

    def test_splits_disconnected_groups(self):
        """Same tag but disconnected files should split into separate clusters."""
        entries = {
            "file:src/a.py": make_entry("file:src/a.py", ["core"]),
            "file:src/b.py": make_entry("file:src/b.py", ["core"]),
            "file:src/c.py": make_entry("file:src/c.py", ["core"]),
        }
        # a↔b connected, c isolated
        edges = [
            {"source": "file:src/a.py", "target": "file:src/b.py", "kind": "imports"},
        ]
        clusters = build_clusters(entries, edges, min_cluster_size=1)

        core_clusters = [c for c in clusters if c.primary_tag == "core"]
        assert len(core_clusters) == 2  # {a,b} and {c}

    def test_merges_small_clusters(self):
        """Clusters smaller than min_cluster_size get merged."""
        entries = {
            "file:src/a.py": make_entry("file:src/a.py", ["core"]),
            "file:src/b.py": make_entry("file:src/b.py", ["core"]),
            "file:src/c.py": make_entry("file:src/c.py", ["util"]),  # lone file
        }
        edges = [
            {"source": "file:src/a.py", "target": "file:src/b.py", "kind": "imports"},
            {"source": "file:src/c.py", "target": "file:src/a.py", "kind": "imports"},
        ]
        clusters = build_clusters(entries, edges, min_cluster_size=2)

        # "util" cluster (1 file) should merge into "core" cluster (2 files)
        assert len(clusters) == 1
        assert len(clusters[0].member_node_ids) == 3

    def test_empty_entries(self):
        clusters = build_clusters({}, [], min_cluster_size=2)
        assert clusters == []

    def test_no_tags_uses_uncategorized(self):
        """Entries with empty domain_tags get grouped as 'uncategorized'."""
        entries = {
            "file:src/x.py": make_entry("file:src/x.py", []),
        }
        clusters = build_clusters(entries, [], min_cluster_size=1)
        assert len(clusters) == 1
        assert clusters[0].primary_tag == "uncategorized"


class TestConnectedComponents:
    def test_single_component(self):
        adjacency = {
            "a": {"b"},
            "b": {"a", "c"},
            "c": {"b"},
        }
        components = _connected_components(["a", "b", "c"], adjacency)
        assert len(components) == 1
        assert set(components[0]) == {"a", "b", "c"}

    def test_two_components(self):
        adjacency = {
            "a": {"b"},
            "b": {"a"},
            "c": {"d"},
            "d": {"c"},
        }
        components = _connected_components(["a", "b", "c", "d"], adjacency)
        assert len(components) == 2

    def test_no_edges(self):
        components = _connected_components(["a", "b", "c"], {})
        assert len(components) == 3


class TestModuleEntry:
    def test_roundtrip(self):
        entry = ModuleEntry(
            module_id="module:monetization",
            name="Ad Framework",
            summary="Handles all ad-related functionality",
            member_files=["src/ad_manager.py", "src/ad_banner.py"],
            domain_tags=["monetization", "ads"],
            architecture_layers=["business_logic", "presentation"],
            component_status="partial",
            data_flow="AdManager → BannerView → UI",
            dependencies=["auth"],
            tech_debt_summary="Several stubs for backend integration",
            file_count=2,
            avg_epistemic_confidence=0.87,
            synthesized_at="2026-02-13T00:00:00Z",
            model="qwen2.5:14b",
        )
        d = entry.to_dict()
        restored = ModuleEntry.from_dict(d)
        assert restored.module_id == entry.module_id
        assert restored.name == entry.name
        assert restored.member_files == entry.member_files
        assert restored.component_status == entry.component_status
        assert restored.file_count == 2
