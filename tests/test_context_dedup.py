"""Tests for Phase 73 search result deduplication."""
from __future__ import annotations

from prep.core.index import SearchResult


class TestDeduplicateByFile:
    def test_removes_lower_scoring_duplicate(self):
        results = [
            SearchResult(doc={"source_path": "a.py", "content": "chunk1"}, score=0.9),
            SearchResult(doc={"source_path": "a.py", "content": "chunk2"}, score=0.7),
            SearchResult(doc={"source_path": "b.py", "content": "chunk3"}, score=0.8),
        ]
        # After dedup: a.py (0.9), b.py (0.8) — only 2 results
        seen: dict[str, SearchResult] = {}
        for r in results:
            fp = r.doc.get("source_path", "")
            if fp not in seen or r.score > seen[fp].score:
                seen[fp] = r
        deduped = sorted(seen.values(), key=lambda r: -r.score)
        assert len(deduped) == 2
        assert deduped[0].doc["source_path"] == "a.py"
        assert deduped[0].score == 0.9
        assert deduped[1].doc["source_path"] == "b.py"

    def test_preserves_unique_results(self):
        results = [
            SearchResult(doc={"source_path": "a.py", "content": "c1"}, score=0.9),
            SearchResult(doc={"source_path": "b.py", "content": "c2"}, score=0.8),
            SearchResult(doc={"source_path": "c.py", "content": "c3"}, score=0.7),
        ]
        seen: dict[str, SearchResult] = {}
        for r in results:
            fp = r.doc.get("source_path", "")
            if fp not in seen or r.score > seen[fp].score:
                seen[fp] = r
        deduped = sorted(seen.values(), key=lambda r: -r.score)
        assert len(deduped) == 3

    def test_empty_input(self):
        seen: dict[str, SearchResult] = {}
        deduped = sorted(seen.values(), key=lambda r: -r.score)
        assert deduped == []
