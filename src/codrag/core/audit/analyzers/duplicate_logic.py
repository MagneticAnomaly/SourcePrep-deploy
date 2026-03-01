"""Duplicate logic analyzer — finds files with suspiciously similar augmentation summaries."""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from ..models import AuditContext, Finding
from . import BaseAnalyzer


# Jaccard similarity threshold for flagging
SIMILARITY_THRESHOLD = 0.65


class DuplicateLogicAnalyzer(BaseAnalyzer):
    name = "duplicate_logic"
    category = "quality"

    def __init__(self, similarity_threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = similarity_threshold

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        if not ctx.augmentations:
            return findings

        # Collect file-level augmentations with summaries
        file_summaries: List[Tuple[str, str, Set[str]]] = []
        for nid, aug in ctx.augmentations.items():
            node = ctx.nodes.get(nid, {})
            if node.get("kind") != "file":
                continue
            summary = aug.get("summary", "")
            if not summary or len(summary) < 20:
                continue
            file_path = node.get("file_path", "")
            if not file_path:
                continue
            tokens = _tokenize(summary)
            if len(tokens) < 3:
                continue
            file_summaries.append((file_path, summary, tokens))

        # Pairwise Jaccard similarity (only O(n²/2), manageable for <5000 files)
        seen_pairs: Set[Tuple[str, str]] = set()
        for i in range(len(file_summaries)):
            for j in range(i + 1, len(file_summaries)):
                path_a, sum_a, tok_a = file_summaries[i]
                path_b, sum_b, tok_b = file_summaries[j]

                # Skip if in the same directory (siblings are often similar by design)
                dir_a = path_a.rsplit("/", 1)[0] if "/" in path_a else ""
                dir_b = path_b.rsplit("/", 1)[0] if "/" in path_b else ""
                if dir_a == dir_b:
                    continue

                sim = _jaccard(tok_a, tok_b)
                if sim < self.threshold:
                    continue

                pair_key = (min(path_a, path_b), max(path_a, path_b))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                severity = "warning" if sim >= 0.80 else "info"

                findings.append(Finding(
                    analyzer=self.name,
                    severity=severity,
                    category=self.category,
                    title=f"Similar logic: {path_a} ↔ {path_b} ({sim:.0%})",
                    description=(
                        f"These files have highly similar augmentation summaries "
                        f"(Jaccard similarity {sim:.0%}), suggesting duplicated "
                        f"or overlapping responsibilities.\n"
                        f"  A: {sum_a[:120]}\n"
                        f"  B: {sum_b[:120]}"
                    ),
                    file_paths=[path_a, path_b],
                    evidence={
                        "similarity": round(sim, 3),
                        "summary_a": sum_a[:200],
                        "summary_b": sum_b[:200],
                    },
                    suggested_action=(
                        "Review for consolidation. These files may contain "
                        "duplicated logic that should be extracted into a shared module."
                    ),
                ))

        findings.sort(key=lambda f: -f.evidence.get("similarity", 0))
        return findings[:50]  # Cap to avoid flooding


def _tokenize(text: str) -> Set[str]:
    """Simple word tokenization for Jaccard similarity."""
    import re
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text.lower())
    # Filter out very common stopwords
    stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
            "has", "have", "had", "do", "does", "did", "will", "would",
            "can", "could", "should", "may", "might", "this", "that",
            "it", "its", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "from", "by", "as", "not", "no"}
    return {w for w in words if w not in stop and len(w) > 2}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0
