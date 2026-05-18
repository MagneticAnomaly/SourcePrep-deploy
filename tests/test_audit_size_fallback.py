"""Phase 136 Part 10 regression — audit consumers handle the
Phase-134/135 file-node schema where `metadata.size` is missing.

The shared `effective_file_size` helper falls back to
`metadata.line_count * 40` so analyzers and the synthesizer prompt
keep working post-cutover.  Without this, LargeFileAnalyzer silently
emitted zero findings and AuditDocs rendered "~0 lines" for every
file in the inventory prompt.
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from prep.core.audit.analyzers.large_files import LargeFileAnalyzer
from prep.core.audit.models import AuditContext, effective_file_size


def _file_node(nid: str, file_path: str, **meta: Any) -> Dict[str, Any]:
    return {
        "id": nid,
        "kind": "file",
        "file_path": file_path,
        "language": "python",
        "metadata": meta,
    }


def _ctx(*nodes: Dict[str, Any]) -> AuditContext:
    return AuditContext(nodes={n["id"]: n for n in nodes})


class TestEffectiveFileSize:
    """Helper unit tests — the central choke point for the fallback."""

    def test_size_field_wins_when_present(self):
        node = {"metadata": {"size": 8000, "line_count": 1}}
        # size is authoritative when present; line_count is fallback only.
        assert effective_file_size(node) == 8000

    def test_line_count_fallback_when_size_missing(self):
        node = {"metadata": {"line_count": 200}}
        # 200 lines * 40 chars/line = 8000
        assert effective_file_size(node) == 8000

    def test_returns_zero_for_empty_metadata(self):
        assert effective_file_size({"metadata": {}}) == 0

    def test_returns_zero_when_no_metadata_key(self):
        assert effective_file_size({}) == 0

    def test_zero_size_with_line_count_falls_back(self):
        # size=0 is treated as "not present" by the truthy check
        node = {"metadata": {"size": 0, "line_count": 100}}
        # Falls through to line_count * 40
        assert effective_file_size(node) == 4000

    def test_none_metadata_safe(self):
        # AuditContext sometimes carries nodes with metadata=None.
        node = {"metadata": None}
        assert effective_file_size(node) == 0


class TestLargeFileAnalyzerSchemaFallback:
    """Regression: LargeFileAnalyzer must surface findings under both
    the legacy (`size`) and current (`line_count`) file-node schemas."""

    def test_emits_finding_for_large_file_via_line_count(self):
        # 2500 lines * 40 = 100_000 bytes — above CRITICAL_BYTES (80_000)
        ctx = _ctx(_file_node("file:big.py", "big.py", line_count=2500))
        findings = LargeFileAnalyzer().analyze(ctx)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "big.py" in findings[0].file_paths

    def test_emits_finding_for_large_file_via_legacy_size(self):
        ctx = _ctx(_file_node("file:big.py", "big.py", size=100_000))
        findings = LargeFileAnalyzer().analyze(ctx)
        assert len(findings) == 1
        assert findings[0].severity == "critical"

    def test_warning_threshold_line_count(self):
        # 1100 lines * 40 = 44_000 bytes — above WARNING_BYTES (40_000),
        # below CRITICAL_BYTES (80_000)
        ctx = _ctx(_file_node("file:medium.py", "medium.py", line_count=1100))
        findings = LargeFileAnalyzer().analyze(ctx)
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_skips_small_files(self):
        # 500 lines * 40 = 20_000 bytes — below WARNING_BYTES (40_000)
        ctx = _ctx(_file_node("file:small.py", "small.py", line_count=500))
        findings = LargeFileAnalyzer().analyze(ctx)
        assert findings == []

    def test_skips_files_with_no_size_signal(self):
        # No size, no line_count → genuinely no signal, skip
        ctx = _ctx(_file_node("file:meta.py", "meta.py"))
        findings = LargeFileAnalyzer().analyze(ctx)
        assert findings == []

    def test_skips_expected_large_lockfile(self):
        # package-lock.json is in EXPECTED_LARGE_BASENAMES — never flagged
        ctx = _ctx(_file_node("file:p.json", "package-lock.json", line_count=5000))
        findings = LargeFileAnalyzer().analyze(ctx)
        assert findings == []
