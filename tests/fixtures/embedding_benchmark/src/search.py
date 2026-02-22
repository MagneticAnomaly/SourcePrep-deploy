"""Full-text search engine with indexing and ranking."""

import re
import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple


class SearchIndex:
    """Inverted index for full-text search with TF-IDF ranking."""

    def __init__(self):
        self._index: Dict[str, Dict[str, List[int]]] = defaultdict(dict)
        self._doc_lengths: Dict[str, int] = {}
        self._doc_count = 0

    def add_document(self, doc_id: str, text: str):
        """Index a document for full-text search."""
        tokens = self._tokenize(text)
        self._doc_lengths[doc_id] = len(tokens)
        self._doc_count += 1
        for pos, token in enumerate(tokens):
            if doc_id not in self._index[token]:
                self._index[token][doc_id] = []
            self._index[token][doc_id].append(pos)

    def search(self, query: str, limit: int = 10) -> List[Tuple[str, float]]:
        """Search documents using TF-IDF scoring."""
        query_tokens = self._tokenize(query)
        scores: Dict[str, float] = Counter()
        for token in query_tokens:
            if token not in self._index:
                continue
            idf = math.log(self._doc_count / len(self._index[token]))
            for doc_id, positions in self._index[token].items():
                tf = len(positions) / max(self._doc_lengths[doc_id], 1)
                scores[doc_id] += tf * idf
        return sorted(scores.items(), key=lambda x: -x[1])[:limit]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Split text into lowercase tokens."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def highlight(self, text: str, query: str, tag: str = "**") -> str:
        """Highlight matching query terms in text."""
        query_tokens = set(self._tokenize(query))
        words = text.split()
        result = []
        for word in words:
            if word.lower().strip(".,!?;:") in query_tokens:
                result.append(f"{tag}{word}{tag}")
            else:
                result.append(word)
        return " ".join(result)
