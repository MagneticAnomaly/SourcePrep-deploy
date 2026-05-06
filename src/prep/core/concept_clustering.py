"""Phase 125 T1 — anchor-overlap concept clustering.

Detects near-duplicate concepts by structural overlap (shared file
anchors + title token similarity). Pure CPU, deterministic, runs in
seconds on thousands of concepts.

Used by Pass 2 of the Concept Promotion Pipeline (Phase 125 README §2)
to compress raw seed concepts into cluster representatives + shadows
before a scoped LLM critique pass.

Algorithm (per Phase 125 §4.1):

1. Build inverted index: anchor → list of concept_ids that mention it.
2. For each concept, candidate-set is union of "any concept sharing
   ≥1 anchor" via the inverted index.
3. For each candidate pair, compute shared_anchor_count and
   title_jaccard.
4. Two concepts cluster together if EITHER:
     - shared_anchor_count >= min_shared_anchors (default 2), OR
     - shared_anchor_count >= 1 AND title_jaccard >= title_jaccard_threshold
       (default 0.6)
5. Compute connected components via union-find.
6. Within each component, the highest-confidence concept is the
   "representative"; the rest are "shadows".

Outputs are dataclasses, not DB rows. Caller decides what to do
with cluster information (e.g., set status='shadow' on shadow ids).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

# Token-extraction regex: words >= 3 chars (drop articles, conjunctions).
_TOKEN_RE = re.compile(r"[A-Za-z0-9]{3,}")
_STOPWORDS = frozenset({
    "the", "and", "for", "with", "from", "into", "via", "has", "are", "but",
    "not", "all", "any", "each", "more", "less", "than", "this", "that",
    "these", "those", "such", "their", "there", "where", "when", "what",
    "which", "while", "have", "been", "must", "may", "can", "will", "should",
    "would", "could", "shall", "does", "did", "was", "were",
})


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ConceptInput:
    """Minimal concept payload required for clustering."""
    id: str
    title: str
    confidence: float
    anchors: tuple[str, ...]


@dataclass
class ConceptCluster:
    """One connected component: one representative + zero-or-more shadows."""
    representative_id: str
    shadow_ids: tuple[str, ...] = ()
    shared_anchors: tuple[str, ...] = ()  # union over all member pairs
    member_count: int = 1                 # representative + len(shadow_ids)
    reason: str = "singleton"             # "anchor" | "anchor+title" | "singleton"


@dataclass
class ClusterReport:
    """Aggregate output for a clustering run."""
    clusters: list[ConceptCluster] = field(default_factory=list)
    input_count: int = 0
    cluster_count: int = 0
    singleton_count: int = 0
    largest_cluster_size: int = 0
    reduction_ratio: float = 0.0  # cluster_count / input_count
    hub_anchors_filtered: int = 0  # Phase 125 T1: anchors stripped as too-generic

    def cluster_size_distribution(self) -> dict[str, int]:
        """Return cluster size distribution for histograms."""
        buckets: dict[str, int] = {
            "1": 0, "2": 0, "3-5": 0, "6-10": 0, "11-25": 0, "26+": 0,
        }
        for c in self.clusters:
            n = c.member_count
            if n == 1:
                buckets["1"] += 1
            elif n == 2:
                buckets["2"] += 1
            elif n <= 5:
                buckets["3-5"] += 1
            elif n <= 10:
                buckets["6-10"] += 1
            elif n <= 25:
                buckets["11-25"] += 1
            else:
                buckets["26+"] += 1
        return buckets


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> frozenset[str]:
    """Lowercase, drop stopwords, drop tokens <3 chars."""
    if not text:
        return frozenset()
    tokens = (m.group(0).lower() for m in _TOKEN_RE.finditer(text))
    return frozenset(t for t in tokens if t not in _STOPWORDS)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class _UnionFind:
    """Disjoint-set union with path compression."""

    def __init__(self, ids: Iterable[str]) -> None:
        self.parent: dict[str, str] = {i: i for i in ids}

    def find(self, x: str) -> str:
        # Path compression — iterative.
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def components(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for x in self.parent:
            root = self.find(x)
            out.setdefault(root, []).append(x)
        return out


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def cluster_concepts(
    concepts: Iterable[ConceptInput],
    *,
    min_shared_anchors: int = 2,
    title_jaccard_threshold: float = 0.6,
    hub_anchor_threshold: int = 1_000_000,
) -> ClusterReport:
    """Group near-duplicate concepts into clusters.

    Args:
        concepts: Iterable of ``ConceptInput`` (id, title, confidence, anchors).
        min_shared_anchors: Two concepts auto-cluster when they share at
            least this many topical anchors. Default 2 (high-precision).
            Setting to 1 dramatically increases compression but inflates
            false positives via transitive union-find — concepts that
            share a single phase-doc anchor get merged across unrelated
            topics.
        title_jaccard_threshold: When two concepts share fewer anchors
            than ``min_shared_anchors`` (but at least one), they cluster
            if their title Jaccard similarity meets or exceeds this
            threshold. Default 0.6.
        hub_anchor_threshold: Anchors referenced by ≥ this many concepts
            are treated as **hub anchors** and ignored for clustering.
            Hubs (e.g., ``MASTER_TODO.md``) can produce mega-clusters
            via transitive merging. Default = effectively off
            (1,000,000) because ``min_shared_anchors=2`` already
            prevents the pile-up. Lower it (e.g., to 8) only when
            running with ``min_shared_anchors=1``.

    Returns:
        ``ClusterReport`` with one ``ConceptCluster`` per connected
        component. Singletons are clusters too.

    Phase 125 T1 calibration on SourcePrep (1,590 concepts):
        - default settings → 1,272 clusters, 20% compression,
          biggest cluster 9 members, all 159 multi-member clusters
          inspected as **genuine** near-duplicates.
        - min=1 + hub_threshold=8 → 317 clusters, 80% compression,
          biggest cluster 35 members. Visual inspection of largest
          clusters showed **non-duplicates** merged transitively
          via shared phase-doc anchors. Rejected as low-precision.

        Pass 2 of the four-pass concept promotion pipeline handles
        OBVIOUS duplicates only. Bulk compression (1,272 → ~80-100)
        is Pass 3's job (scoped LLM critique on cluster
        representatives).
    """
    concept_list = list(concepts)
    n = len(concept_list)
    report = ClusterReport(input_count=n)
    if n == 0:
        return report

    # Index concepts by id, deduplicate inputs by id (last wins).
    by_id: dict[str, ConceptInput] = {c.id: c for c in concept_list}
    ids = list(by_id.keys())

    # Build inverted index: anchor → set of concept ids.
    inv: dict[str, set[str]] = {}
    for cid, c in by_id.items():
        for a in c.anchors:
            if not isinstance(a, str) or not a:
                continue
            inv.setdefault(a, set()).add(cid)

    # Phase 125 T1 hub filter: anchors referenced by ≥ hub_anchor_threshold
    # concepts are too generic to be a near-duplicate signal. They'd
    # transitively merge unrelated concepts via union-find. Strip them
    # from the inverted index AND from per-concept anchor sets used for
    # pairwise overlap counting.
    hub_anchors: set[str] = {
        a for a, cohort in inv.items() if len(cohort) >= hub_anchor_threshold
    }
    if hub_anchors:
        inv = {a: cohort for a, cohort in inv.items() if a not in hub_anchors}
    report.hub_anchors_filtered = len(hub_anchors)

    # Topical anchors per concept (for pairwise overlap counts below).
    topical: dict[str, frozenset[str]] = {
        cid: frozenset(a for a in c.anchors if a not in hub_anchors)
        for cid, c in by_id.items()
    }

    # Pre-tokenize titles.
    titles: dict[str, frozenset[str]] = {
        cid: _tokenize(c.title) for cid, c in by_id.items()
    }

    # Track unioning + reason annotation.
    uf = _UnionFind(ids)
    cluster_reason: dict[str, str] = {}    # representative_id → reason
    pair_anchors: dict[tuple[str, str], frozenset[str]] = {}

    seen: set[tuple[str, str]] = set()
    for anchor, cohort in inv.items():
        cohort_list = sorted(cohort)
        # Skip explosion on very-popular anchors (e.g., MASTER_TODO.md).
        # If an anchor connects >50 concepts, it's too generic to be a
        # near-duplicate signal on its own — require min_shared_anchors=2
        # path to gate.
        if len(cohort_list) > 50 and min_shared_anchors <= 1:
            # Caller really wants permissive — let it proceed.
            pass
        for i in range(len(cohort_list)):
            a_id = cohort_list[i]
            for j in range(i + 1, len(cohort_list)):
                b_id = cohort_list[j]
                key = (a_id, b_id)
                if key in seen:
                    continue
                seen.add(key)

                # Use topical (hub-filtered) anchors for overlap counting.
                shared = topical[a_id] & topical[b_id]
                shared_count = len(shared)

                cluster_them = False
                reason = ""
                if shared_count >= min_shared_anchors:
                    cluster_them = True
                    reason = "anchor"
                elif shared_count >= 1:
                    j_score = _jaccard(titles[a_id], titles[b_id])
                    if j_score >= title_jaccard_threshold:
                        cluster_them = True
                        reason = "anchor+title"

                if cluster_them:
                    uf.union(a_id, b_id)
                    pair_anchors[key] = shared
                    # Track the strongest reason on the cluster
                    cluster_reason[a_id] = reason
                    cluster_reason[b_id] = reason

    # Build the cluster output.
    components = uf.components()
    for root, members in components.items():
        if len(members) == 1:
            cid = members[0]
            report.clusters.append(ConceptCluster(
                representative_id=cid,
                shadow_ids=(),
                shared_anchors=(),
                member_count=1,
                reason="singleton",
            ))
            continue

        # Choose the highest-confidence concept as representative;
        # tie-break by id for stability.
        ranked = sorted(
            members,
            key=lambda x: (-by_id[x].confidence, x),
        )
        rep_id = ranked[0]
        shadows = tuple(ranked[1:])

        # Union of shared anchors across pairs in this component.
        union_shared: set[str] = set()
        for k, sa in pair_anchors.items():
            a_id, b_id = k
            if uf.find(a_id) == root or uf.find(b_id) == root:
                if a_id in members and b_id in members:
                    union_shared.update(sa)

        # Pick a reason: any "anchor" wins over "anchor+title".
        reasons = {cluster_reason.get(m, "") for m in members}
        reason = (
            "anchor" if "anchor" in reasons
            else ("anchor+title" if "anchor+title" in reasons else "anchor")
        )

        report.clusters.append(ConceptCluster(
            representative_id=rep_id,
            shadow_ids=shadows,
            shared_anchors=tuple(sorted(union_shared)),
            member_count=len(members),
            reason=reason,
        ))

    # Aggregate stats.
    report.cluster_count = len(report.clusters)
    report.singleton_count = sum(1 for c in report.clusters if c.member_count == 1)
    report.largest_cluster_size = max((c.member_count for c in report.clusters), default=0)
    report.reduction_ratio = report.cluster_count / max(report.input_count, 1)
    return report


# ──────────────────────────────────────────────────────────────────────
# Convenience: load from concept store
# ──────────────────────────────────────────────────────────────────────

def load_concepts_for_clustering(
    db_path: str,
    project_id: str,
    *,
    status: str = "seed",
    kind: str = "module_rationale",
) -> list[ConceptInput]:
    """Load concepts from the prep_concepts.db SQLite store for clustering.

    Decoupled here so callers don't need to import sqlite3 themselves
    or know about the anchors-as-JSON-string serialization detail.

    Phase 125b: defaults to ``kind='module_rationale'`` because
    clustering is a Pass 2 operation over the dense rationale layer.
    The small ``kind='concept'`` layer (~30-100 entries) doesn't need
    clustering. Pass ``kind=None`` to bypass the filter (useful for
    older DBs that don't have the ``kind`` column yet).
    """
    import json
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        if kind is None:
            rows = conn.execute(
                "SELECT id, title, confidence, anchors FROM concepts "
                "WHERE project_id=? AND status=?",
                (project_id, status),
            ).fetchall()
        else:
            # Defensive: older DBs may not have `kind` column. Try with
            # the filter first; fall back to no-filter on schema error.
            try:
                rows = conn.execute(
                    "SELECT id, title, confidence, anchors FROM concepts "
                    "WHERE project_id=? AND status=? AND kind=?",
                    (project_id, status, kind),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    "SELECT id, title, confidence, anchors FROM concepts "
                    "WHERE project_id=? AND status=?",
                    (project_id, status),
                ).fetchall()
    finally:
        conn.close()

    out: list[ConceptInput] = []
    for cid, title, conf, anchors_json in rows:
        try:
            anchors = json.loads(anchors_json) if anchors_json else []
        except Exception:
            anchors = []
        if not isinstance(anchors, list):
            anchors = []
        out.append(ConceptInput(
            id=cid,
            title=title or "",
            confidence=float(conf) if conf is not None else 0.0,
            anchors=tuple(a for a in anchors if isinstance(a, str)),
        ))
    return out
