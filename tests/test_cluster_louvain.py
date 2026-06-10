"""Sanity tests for the Louvain community-detection path in cluster.py.

A graph with two obvious dense communities and one weak bridge edge
must produce at least two distinct clusters with the community-A and
community-B files landing in disjoint clusters. The exact algorithm
(Leiden or Louvain) is an implementation detail; this test must pass
with either, and locks the swap from Leiden→Louvain made 2026-06-10.

Covers both public entry points:
- ``build_clusters_leiden`` — tag-aware path used after enrichment
- ``build_clusters_structural`` — LLM-free path used pre-enrichment
"""
from prep.core.cluster import (
    EpistemicEntry,
    build_clusters_leiden,
    build_clusters_structural,
)


def _entry(node_id: str, tags: list[str]) -> EpistemicEntry:
    return EpistemicEntry(
        node_id=node_id,
        extended_summary="",
        domain_tags=tags,
        architecture_layer="impl",
    )


def _edge(src: str, tgt: str, conf: float) -> dict:
    return {
        "source": src,
        "target": tgt,
        "kind": "imports",
        "metadata": {"confidence": conf},
    }


def _two_triangle_edges(files_a: list[str], files_b: list[str]) -> list[dict]:
    """Build edges for two dense triangles joined by one weak bridge."""
    edges = []
    for i, src in enumerate(files_a):
        for tgt in files_a[i + 1:]:
            edges.append(_edge(src, tgt, 1.0))
    for i, src in enumerate(files_b):
        for tgt in files_b[i + 1:]:
            edges.append(_edge(src, tgt, 1.0))
    edges.append(_edge(files_a[0], files_b[0], 0.1))
    return edges


def _cluster_lookup(clusters):
    return {nid: c.cluster_id for c in clusters for nid in c.member_node_ids}


def test_build_clusters_leiden_separates_two_communities():
    files_a = [f"file:src/a{i}.py" for i in (1, 2, 3)]
    files_b = [f"file:src/b{i}.py" for i in (1, 2, 3)]
    entries = {f: _entry(f, ["impl"]) for f in files_a + files_b}
    edges = _two_triangle_edges(files_a, files_b)

    clusters = build_clusters_leiden(
        entries,
        edges,
        min_cluster_size=1,
        resolution=1.0,
    )

    assert len(clusters) >= 2, f"expected ≥2 clusters, got {len(clusters)}"

    lookup = _cluster_lookup(clusters)
    a_clusters = {lookup[f] for f in files_a}
    b_clusters = {lookup[f] for f in files_b}

    assert a_clusters.isdisjoint(b_clusters), (
        f"A and B share a cluster: A={a_clusters}, B={b_clusters}"
    )


def test_build_clusters_structural_separates_two_communities():
    files_a = [f"file:src/a{i}.py" for i in (1, 2, 3)]
    files_b = [f"file:src/b{i}.py" for i in (1, 2, 3)]
    file_paths = [f[5:] for f in files_a + files_b]
    edges = _two_triangle_edges(files_a, files_b)

    clusters = build_clusters_structural(
        file_paths,
        edges,
        min_cluster_size=1,
        resolution=0.8,
    )

    assert len(clusters) >= 2, f"expected ≥2 clusters, got {len(clusters)}"

    lookup = _cluster_lookup(clusters)
    a_clusters = {lookup[f] for f in files_a}
    b_clusters = {lookup[f] for f in files_b}

    assert a_clusters.isdisjoint(b_clusters), (
        f"A and B share a cluster: A={a_clusters}, B={b_clusters}"
    )
