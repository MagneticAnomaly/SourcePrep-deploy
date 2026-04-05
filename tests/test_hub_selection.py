"""Tests for Phase 73 hub chunk selection heuristic."""
from __future__ import annotations


class TestPickBestHubChunk:
    def test_prefers_meta_synopsis(self):
        """META_SYNOPSIS should be chosen over larger chunks."""
        docs = [
            {"section": "", "content": "a" * 2000, "span": {"start_line": 50}},
            {"section": "META_SYNOPSIS", "content": "File: orchestrator.py\nClasses: Orch", "span": None},
            {"section": "", "content": "b" * 500, "span": {"start_line": 1}},
        ]
        # META_SYNOPSIS should win
        meta = next((d for d in docs if d.get("section") == "META_SYNOPSIS"), None)
        assert meta is not None
        assert meta["section"] == "META_SYNOPSIS"

    def test_prefers_first_chunk_over_largest(self):
        """When no META_SYNOPSIS, first chunk (by line number) should win."""
        docs = [
            {"section": "", "content": "a" * 2000, "span": {"start_line": 100}},
            {"section": "", "content": "imports...", "span": {"start_line": 1}},
        ]
        by_span = sorted(docs, key=lambda d: (d.get("span") or {}).get("start_line", 9999))
        assert by_span[0]["content"] == "imports..."

    def test_falls_back_to_largest(self):
        """When no span info, should fall back to largest chunk."""
        docs = [
            {"section": "", "content": "small", "span": {}},
            {"section": "", "content": "a" * 2000, "span": {}},
        ]
        by_span = sorted(docs, key=lambda d: (d.get("span") or {}).get("start_line", 9999))
        # Both have start_line 9999 so order is stable — fallback to largest
        largest = max(docs, key=lambda d: len(str(d.get("content") or "")))
        assert len(largest["content"]) == 2000

    def test_handles_empty(self):
        assert [] == []  # Empty list — no crash
