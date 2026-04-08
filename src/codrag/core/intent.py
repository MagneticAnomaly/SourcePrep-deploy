"""Rule-based intent classifier for CoDRAG search queries.

Zero-latency, deterministic classification of search queries into
one of 7 intents, each routing to a different retrieval strategy.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Tuple


class SearchIntent(Enum):
    LOCATE = "locate"
    EXPLAIN = "explain"
    RATIONALE = "rationale"
    TRACE = "trace"
    EXAMPLE = "example"
    COMPARE = "compare"
    DISCOVER = "discover"


def classify_intent(query: str) -> Tuple[SearchIntent, str]:
    """Classify a search query into an intent.

    Returns (intent, confidence) where confidence is "high" if multiple
    signal words match, "low" if falling back to default.

    Priority order: RATIONALE > TRACE > COMPARE > EXAMPLE > EXPLAIN > LOCATE > DISCOVER
    """
    q = query.lower().strip()

    # TRACE — asking about relationships (check early, specific patterns)
    if re.search(r"\b(what calls|who (calls|imports|uses)|dependents|dependencies|callers|importers|imported by)\b", q):
        return SearchIntent.TRACE, "high"

    # RATIONALE — asking why (high priority)
    if re.match(r"(why|reason|rationale|motivation|decision behind)\b", q):
        return SearchIntent.RATIONALE, "high"
    if re.search(r"\b(instead of|rather than|chose|decision|trade.?off)\b", q):
        return SearchIntent.RATIONALE, "medium"

    # COMPARE — asking about differences
    if re.search(r"\b(difference|compare|vs\.?|versus)\b", q) or re.search(r"\bbetween .+ and\b", q):
        return SearchIntent.COMPARE, "high"

    # EXAMPLE — asking for usage
    if re.search(r"\b(example|usage|how to use|how do I use|call sites|who uses|show me how)\b", q):
        return SearchIntent.EXAMPLE, "high"

    # DISCOVER — asking for overview/browsing
    if re.search(r"\b(what'?s in|overview|modules|list all|browse|contents of|what files)\b", q):
        return SearchIntent.DISCOVER, "high"

    # LOCATE — asking for a position/definition
    if re.match(r"(where|find|locate|which file|path to|definition of|show me)\b", q):
        return SearchIntent.LOCATE, "high"
    if re.search(r"\b(find|locate|where is|definition)\b", q) and not re.search(r"\b(how|why|explain)\b", q):
        return SearchIntent.LOCATE, "medium"

    # EXPLAIN — asking how (broad category)
    if re.search(r"\b(how does|what does|explain|walk me through|tell me about|describe)\b", q):
        return SearchIntent.EXPLAIN, "high"

    # Default: EXPLAIN (safest fallback — semantic search)
    return SearchIntent.EXPLAIN, "low"


def rewrite_query(query: str, intent: SearchIntent) -> str:
    """Strip signal words from query before passing to retrieval pipeline.

    Removes intent-classification prefixes that add noise to search.
    """
    q = query.strip()

    patterns = {
        SearchIntent.LOCATE: [
            r"^(where is|find|locate|which file has|path to|definition of|show me)\s+",
        ],
        SearchIntent.EXPLAIN: [
            r"^(how does|what does|explain|walk me through|tell me about|describe)\s+",
        ],
        SearchIntent.RATIONALE: [
            r"^(why does|why is|why do|reason for|rationale for|motivation for)\s+",
        ],
        SearchIntent.TRACE: [
            r"^(what calls|who calls|who imports|who uses)\s+",
        ],
        SearchIntent.EXAMPLE: [
            r"^(how to use|how do I use|example of|usage of|show me how to use)\s+",
        ],
        SearchIntent.COMPARE: [
            r"^(compare|difference between)\s+",
        ],
        SearchIntent.DISCOVER: [
            r"^(what'?s in|overview of|list all|contents of)\s+",
        ],
    }

    for pattern in patterns.get(intent, []):
        q = re.sub(pattern, "", q, flags=re.IGNORECASE)

    return q.strip() or query.strip()
