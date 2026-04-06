"""Tests for context compression: NoopCompressor and LOD on real files.

Covers:
  - NoopCompressor pass-through behavior
  - CompressResult dataclass correctness
  - LOD extraction on real CoDRAG source files (compression ratio validation)
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, List

import pytest

from codrag.core.compressor import (
    CompressResult,
    ContextCompressor,
    NoopCompressor,
)
from codrag.core.lod_extractor import LODExtractor, LODResult, assign_lod


# ═══════════════════════════════════════════════════════════════════
# NoopCompressor
# ═══════════════════════════════════════════════════════════════════


class TestNoopCompressor:
    def test_returns_input_unchanged(self) -> None:
        comp = NoopCompressor()
        result = comp.compress("Hello, world!")
        assert result.compressed == "Hello, world!"

    def test_chars_match(self) -> None:
        comp = NoopCompressor()
        result = comp.compress("abcdef")
        assert result.input_chars == 6
        assert result.output_chars == 6

    def test_empty_string(self) -> None:
        comp = NoopCompressor()
        result = comp.compress("")
        assert result.compressed == ""
        assert result.input_chars == 0
        assert result.output_chars == 0

    def test_is_always_available(self) -> None:
        comp = NoopCompressor()
        assert comp.is_available() is True

    def test_ignores_all_parameters(self) -> None:
        comp = NoopCompressor()
        result = comp.compress(
            "test",
            query="foo",
            budget_chars=100,
            level="aggressive",
            timeout_s=1.0,
        )
        assert result.compressed == "test"


# ═══════════════════════════════════════════════════════════════════
# CompressResult
# ═══════════════════════════════════════════════════════════════════


class TestCompressResult:
    def test_fields(self) -> None:
        r = CompressResult(
            compressed="abc",
            input_chars=300,
            output_chars=100,
            compression_ratio=3.0,
            timing_ms=42.5,
        )
        assert r.compressed == "abc"
        assert r.input_chars == 300
        assert r.output_chars == 100
        assert r.compression_ratio == 3.0
        assert r.timing_ms == 42.5
        assert r.error is None

    def test_defaults(self) -> None:
        r = CompressResult(compressed="x", input_chars=1, output_chars=1)
        assert r.input_tokens == 0
        assert r.output_tokens == 0
        assert r.compression_ratio == 1.0
        assert r.timing_ms == 0.0
        assert r.error is None

    def test_error_field(self) -> None:
        r = CompressResult(
            compressed="x", input_chars=1, output_chars=1, error="boom"
        )
        assert r.error == "boom"

    def test_frozen(self) -> None:
        r = CompressResult(compressed="x", input_chars=1, output_chars=1)
        with pytest.raises(AttributeError):
            r.compressed = "y"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════
# LOD on real CoDRAG source files
# ═══════════════════════════════════════════════════════════════════

# Real project files to test against — these are known to exist
REPO_ROOT = Path("/Volumes/4TB-BAD/HumanAI/CoDRAG")
REAL_FILES = {
    "src/codrag/core/compressor.py": "python",
    "src/codrag/core/lod_extractor.py": "python",
    "src/codrag/core/feature_gate.py": "python",
    "src/codrag/mcp_tools.py": "python",
}


def _load_trace_nodes_for_file(file_path: str) -> List[Dict[str, Any]]:
    """Build minimal trace nodes from actual file content (no index needed)."""
    import re
    abs_path = REPO_ROOT / file_path
    if not abs_path.exists():
        return []

    source = abs_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    nodes: List[Dict[str, Any]] = []

    # Simple regex-based symbol extraction for Python
    class_re = re.compile(r"^class\s+(\w+)")
    func_re = re.compile(r"^(\s*)(async\s+)?def\s+(\w+)")
    current_class_start = None
    current_class_end = None
    current_class_name = None

    for i, line in enumerate(lines, 1):
        cm = class_re.match(line)
        if cm:
            # Close previous class
            if current_class_name:
                nodes.append({
                    "id": f"sym:{current_class_name}@{file_path}:{current_class_start}",
                    "kind": "symbol",
                    "name": current_class_name,
                    "file_path": file_path,
                    "span": {"start_line": current_class_start, "end_line": i - 1},
                    "language": "python",
                    "metadata": {"symbol_type": "class", "is_public": True},
                })
            current_class_name = cm.group(1)
            current_class_start = i
            current_class_end = None
            continue

        fm = func_re.match(line)
        if fm:
            indent = len(fm.group(1))
            name = fm.group(3)
            sym_type = "method" if indent > 0 else "function"
            # Find end of function (next line at same or less indent, or EOF)
            end = i
            for j in range(i + 1, min(i + 200, len(lines) + 1)):
                next_line = lines[j - 1]
                if next_line.strip() == "":
                    continue
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_indent <= indent and next_line.strip():
                    end = j - 1
                    break
                end = j
            nodes.append({
                "id": f"sym:{name}@{file_path}:{i}",
                "kind": "symbol",
                "name": name,
                "file_path": file_path,
                "span": {"start_line": i, "end_line": end},
                "language": "python",
                "metadata": {
                    "symbol_type": sym_type,
                    "is_public": not name.startswith("_"),
                },
            })

    # Close final class
    if current_class_name:
        nodes.append({
            "id": f"sym:{current_class_name}@{file_path}:{current_class_start}",
            "kind": "symbol",
            "name": current_class_name,
            "file_path": file_path,
            "span": {"start_line": current_class_start, "end_line": len(lines)},
            "language": "python",
            "metadata": {"symbol_type": "class", "is_public": True},
        })

    return nodes


@pytest.mark.skipif(
    not REPO_ROOT.exists(),
    reason="Real CoDRAG repo not available at expected path",
)
class TestLODOnRealFiles:
    """Validate LOD compression ratios on actual CoDRAG source files."""

    @pytest.fixture
    def extractor(self) -> LODExtractor:
        return LODExtractor()

    @pytest.mark.parametrize("file_path", list(REAL_FILES.keys()))
    def test_lod0_is_full_source(self, extractor: LODExtractor, file_path: str) -> None:
        abs_path = REPO_ROOT / file_path
        expected = abs_path.read_text(encoding="utf-8")
        nodes = _load_trace_nodes_for_file(file_path)
        result = extractor.extract(file_path, 0, nodes, REPO_ROOT)
        assert result.content == expected
        assert result.compression_ratio == pytest.approx(1.0, abs=0.05)

    @pytest.mark.parametrize("file_path", list(REAL_FILES.keys()))
    def test_lod2_achieves_compression(self, extractor: LODExtractor, file_path: str) -> None:
        """LOD 2 on real files should achieve at least 1.2x compression.

        Note: files with heavy module-level constants/dicts (compressor.py,
        lod_extractor.py) achieve only ~1.3-1.4x at LOD 2 because LOD only
        compresses function/method bodies. The 3-4x documented target applies
        to files where most code lives inside functions.
        """
        nodes = _load_trace_nodes_for_file(file_path)
        if not nodes:
            pytest.skip(f"No symbols extracted for {file_path}")
        result = extractor.extract(file_path, 2, nodes, REPO_ROOT)
        assert not result.fallback, f"LOD 2 fell back to LOD 0 for {file_path}"
        assert result.compression_ratio >= 1.2, (
            f"LOD 2 on {file_path}: only {result.compression_ratio:.2f}x "
            f"({result.input_chars} → {result.output_chars} chars)"
        )

    @pytest.mark.parametrize("file_path", list(REAL_FILES.keys()))
    def test_lod4_achieves_strong_compression(self, extractor: LODExtractor, file_path: str) -> None:
        """LOD 4 on real files should achieve at least 3x compression."""
        nodes = _load_trace_nodes_for_file(file_path)
        if not nodes:
            pytest.skip(f"No symbols extracted for {file_path}")
        result = extractor.extract(file_path, 4, nodes, REPO_ROOT)
        assert result.compression_ratio >= 3.0, (
            f"LOD 4 on {file_path}: only {result.compression_ratio:.2f}x "
            f"({result.input_chars} → {result.output_chars} chars)"
        )

    @pytest.mark.parametrize("file_path", list(REAL_FILES.keys()))
    def test_lod_monotonicity(self, extractor: LODExtractor, file_path: str) -> None:
        """Higher LOD levels should produce smaller output."""
        nodes = _load_trace_nodes_for_file(file_path)
        if not nodes:
            pytest.skip(f"No symbols extracted for {file_path}")
        sizes = {}
        for lod in (0, 2, 4, 5):
            r = extractor.extract(file_path, lod, nodes, REPO_ROOT)
            sizes[lod] = r.output_chars
        assert sizes[0] >= sizes[2], f"LOD0 ({sizes[0]}) < LOD2 ({sizes[2]})"
        assert sizes[2] >= sizes[4], f"LOD2 ({sizes[2]}) < LOD4 ({sizes[4]})"
        assert sizes[4] >= sizes[5], f"LOD4 ({sizes[4]}) < LOD5 ({sizes[5]})"

    @pytest.mark.parametrize("file_path", list(REAL_FILES.keys()))
    def test_lod2_retains_public_names(self, extractor: LODExtractor, file_path: str) -> None:
        """LOD 2 should retain all public class/function names."""
        nodes = _load_trace_nodes_for_file(file_path)
        if not nodes:
            pytest.skip(f"No symbols extracted for {file_path}")
        result = extractor.extract(file_path, 2, nodes, REPO_ROOT)

        public_names = [
            n["name"] for n in nodes
            if n.get("kind") == "symbol"
            and (n.get("metadata") or {}).get("is_public", True)
        ]
        if not public_names:
            pytest.skip(f"No public symbols in {file_path}")

        missing = [name for name in public_names if name not in result.content]
        retention = 1 - len(missing) / len(public_names)
        assert retention >= 0.90, (
            f"LOD 2 name retention {retention:.0%} < 90% for {file_path}. "
            f"Missing: {missing[:5]}"
        )

    @pytest.mark.parametrize("file_path", list(REAL_FILES.keys()))
    def test_lod25_better_than_lod2(self, extractor: LODExtractor, file_path: str) -> None:
        """LOD 2.5 should compress at least as much as LOD 2."""
        nodes = _load_trace_nodes_for_file(file_path)
        if not nodes:
            pytest.skip(f"No symbols extracted for {file_path}")
        r2 = extractor.extract(file_path, 2, nodes, REPO_ROOT)
        r25 = extractor.extract(file_path, 25, nodes, REPO_ROOT)
        assert r25.output_chars <= r2.output_chars, (
            f"LOD 2.5 ({r25.output_chars}) should be <= LOD 2 ({r2.output_chars}) for {file_path}"
        )

    def test_compression_ratio_summary(self, extractor: LODExtractor) -> None:
        """Print a summary table of compression ratios across all real files."""
        rows = []
        for file_path in REAL_FILES:
            nodes = _load_trace_nodes_for_file(file_path)
            if not nodes:
                continue
            abs_path = REPO_ROOT / file_path
            source_chars = len(abs_path.read_text(encoding="utf-8"))
            ratios = {}
            for lod in (0, 1, 2, 3, 4, 5):
                r = extractor.extract(file_path, lod, nodes, REPO_ROOT)
                ratios[lod] = r.compression_ratio
            rows.append((file_path, source_chars, ratios))

        # Just verify we got data — the parametrized tests check thresholds
        assert len(rows) > 0, "No real files could be processed"
        # Print summary for human review
        for fp, chars, ratios in rows:
            print(f"\n{fp} ({chars} chars):")
            for lod, ratio in sorted(ratios.items()):
                print(f"  LOD {lod}: {ratio:.1f}x")
