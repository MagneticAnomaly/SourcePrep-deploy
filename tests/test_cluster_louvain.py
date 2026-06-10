"""Sanity tests for build_clusters_leiden after Leiden→Louvain swap.

The test asserts behavioral parity: a graph with two obvious dense
communities and one weak bridge edge must produce at least two
distinct clusters. The exact algorithm (Leiden or Louvain) is an
implementation detail; this test must pass with either.
"""
from prep.core.cluster import build_clusters_leiden
from prep.core.cluster import EpistemicEntry


def _entry(node_id: str, tags: list[str]) -> EpistemicEntry:
    return EpistemicEntry(
        node_id=node_id,
        extended_summary="",
        domain_tags=tags,
        architecture_layer="impl",
    )


def test_two_obvious_communities_separate():
    # Two dense triangles connected by one weak bridge edge.
    # Community A: files a1, a2, a3 (dense interconnects, weight 1.0)
    # Community B: files b1, b2, b3 (dense interconnects, weight 1.0)
    # Bridge: a1 ↔ b1 with weight 0.1
    files_a = [f"file:src/a{i}.py" for i in (1, 2, 3)]
    files_b = [f"file:src/b{i}.py" for i in (1, 2, 3)]
    all_files = files_a + files_b

    entries = {f: _entry(f, ["impl"]) for f in all_files}

    def edge(src: str, tgt: str, conf: float) -> dict:
        return {
            "source": src,
            "target": tgt,
            "kind": "imports",
            "metadata": {"confidence": conf},
        }

    edges = []
    # Dense within A
    for i, src in enumerate(files_a):
        for tgt in files_a[i + 1:]:
            edges.append(edge(src, tgt, 1.0))
    # Dense within B
    for i, src in enumerate(files_b):
        for tgt in files_b[i + 1:]:
            edges.append(edge(src, tgt, 1.0))
    # Weak bridge
    edges.append(edge(files_a[0], files_b[0], 0.1))

    clusters = build_clusters_leiden(
        entries,
        edges,
        min_cluster_size=1,
        resolution=1.0,
    )

    # Expect at least two clusters; the A-files should not all share a
    # cluster with the B-files.
    assert len(clusters) >= 2, f"expected ≥2 clusters, got {len(clusters)}"

    # Find which cluster each file landed in
    file_to_cluster = {}
    for c in clusters:
        for nid in c.member_node_ids:
            file_to_cluster[nid] = c.cluster_id

    a_clusters = {file_to_cluster[f] for f in files_a if f in file_to_cluster}
    b_clusters = {file_to_cluster[f] for f in files_b if f in file_to_cluster}

    # Community A and B should not be the same single cluster
    assert a_clusters != b_clusters or len(a_clusters | b_clusters) >= 2, \
        f"A and B collapsed into the same cluster: A={a_clusters}, B={b_clusters}"
