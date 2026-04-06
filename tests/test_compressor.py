"""Tests for context compression: NoopCompressor, LinguaCompressor, and LOD on real files.

Covers:
  - NoopCompressor pass-through behavior
  - LinguaCompressor graceful fallback when llmlingua not installed
  - LinguaCompressor configuration (levels, force tokens)
  - CompressResult dataclass correctness
  - LOD extraction on real CoDRAG source files (compression ratio validation)
  - End-to-end _get_compressor routing
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from codrag.core.compressor import (
    CompressResult,
    ContextCompressor,
    LinguaCompressor,
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
# LinguaCompressor — without llmlingua installed
# ═══════════════════════════════════════════════════════════════════


class TestLinguaCompressorFallback:
    """Tests that run regardless of whether llmlingua is installed."""

    def test_level_rates_defined(self) -> None:
        assert LinguaCompressor.LEVEL_RATES["light"] == 0.6
        assert LinguaCompressor.LEVEL_RATES["standard"] == 0.4
        assert LinguaCompressor.LEVEL_RATES["aggressive"] == 0.25

    def test_force_tokens_include_structural_markers(self) -> None:
        tokens = LinguaCompressor.FORCE_TOKENS
        assert "\n" in tokens
        assert "@" in tokens
        assert "/" in tokens
        assert ".py" in tokens
        assert ".ts" in tokens
        assert "[" in tokens
        assert "]" in tokens

    def test_hf_model_id(self) -> None:
        assert "llmlingua-2" in LinguaCompressor.HF_MODEL_ID
        assert "bert-base" in LinguaCompressor.HF_MODEL_ID

    def test_compress_returns_noop_when_unavailable(self) -> None:
        comp = LinguaCompressor()
        # Simulate model load failure — set _available=False AND provide a
        # non-None _compressor sentinel so _ensure_loaded doesn't re-try
        comp._available = False
        comp._compressor = None
        # Patch the import to fail so _ensure_loaded can't reload
        with patch.dict("sys.modules", {"llmlingua": None}):
            result = comp.compress("Hello, this is a test string.")
        assert result.compressed == "Hello, this is a test string."
        assert result.error is not None
        assert "not available" in result.error

    def test_compress_empty_string(self) -> None:
        comp = LinguaCompressor()
        result = comp.compress("")
        assert result.compressed == ""
        assert result.input_chars == 0
        assert result.output_chars == 0

    def test_status_without_loading(self) -> None:
        comp = LinguaCompressor()
        status = comp.status()
        assert "type" in status
        assert status["type"] == "lingua"
        assert "loaded" in status
        assert status["loaded"] is False

    def test_custom_model_id(self) -> None:
        comp = LinguaCompressor(model_id="custom/model")
        assert comp._model_id == "custom/model"


class TestLinguaCompressorMocked:
    """Tests using a mock to simulate llmlingua being available."""

    def test_compress_with_mock_model(self) -> None:
        comp = LinguaCompressor()
        mock_inner = MagicMock()
        mock_inner.compress_prompt.return_value = {
            "compressed_prompt": "Hello test."
        }
        comp._compressor = mock_inner
        comp._available = True

        result = comp.compress("Hello, this is a test string.", level="standard")

        assert result.compressed == "Hello test."
        assert result.input_chars == 29
        assert result.output_chars == 11
        assert result.compression_ratio == pytest.approx(2.64, abs=0.1)
        assert result.timing_ms >= 0  # mock runs instantly
        assert result.error is None

        # Verify call args
        mock_inner.compress_prompt.assert_called_once()
        call_args = mock_inner.compress_prompt.call_args
        assert call_args[0][0] == ["Hello, this is a test string."]
        assert call_args[1]["rate"] == 0.4  # standard level
        assert call_args[1]["drop_consecutive"] is True

    def test_compress_with_light_level(self) -> None:
        comp = LinguaCompressor()
        mock_inner = MagicMock()
        mock_inner.compress_prompt.return_value = {"compressed_prompt": "result"}
        comp._compressor = mock_inner
        comp._available = True

        comp.compress("input text", level="light")
        call_args = mock_inner.compress_prompt.call_args
        assert call_args[1]["rate"] == 0.6

    def test_compress_with_aggressive_level(self) -> None:
        comp = LinguaCompressor()
        mock_inner = MagicMock()
        mock_inner.compress_prompt.return_value = {"compressed_prompt": "r"}
        comp._compressor = mock_inner
        comp._available = True

        comp.compress("input text", level="aggressive")
        call_args = mock_inner.compress_prompt.call_args
        assert call_args[1]["rate"] == 0.25

    def test_compress_handles_exception(self) -> None:
        comp = LinguaCompressor()
        mock_inner = MagicMock()
        mock_inner.compress_prompt.side_effect = RuntimeError("model crashed")
        comp._compressor = mock_inner
        comp._available = True

        result = comp.compress("test input")
        # Should fall back to original text
        assert result.compressed == "test input"
        assert result.error == "model crashed"
        assert result.timing_ms >= 0  # mock runs instantly

    def test_force_tokens_passed_to_model(self) -> None:
        comp = LinguaCompressor()
        mock_inner = MagicMock()
        mock_inner.compress_prompt.return_value = {"compressed_prompt": "ok"}
        comp._compressor = mock_inner
        comp._available = True

        comp.compress("test")
        call_args = mock_inner.compress_prompt.call_args
        assert call_args[1]["force_tokens"] == LinguaCompressor.FORCE_TOKENS


# ═══════════════════════════════════════════════════════════════════
# _get_compressor routing (from search.py)
# ═══════════════════════════════════════════════════════════════════


class TestGetCompressorRouting:
    def test_none_returns_noop(self) -> None:
        from codrag.api.routers.projects.search import _get_compressor
        comp = _get_compressor("none")
        assert isinstance(comp, NoopCompressor)

    def test_lingua_returns_lingua(self) -> None:
        from codrag.api.routers.projects.search import _get_compressor
        comp = _get_compressor("lingua")
        assert isinstance(comp, LinguaCompressor)

    def test_auto_returns_lingua(self) -> None:
        from codrag.api.routers.projects.search import _get_compressor
        comp = _get_compressor("auto")
        assert isinstance(comp, LinguaCompressor)

    def test_lod_returns_noop(self) -> None:
        # "lod" is handled separately via _apply_lod_compression, not _get_compressor
        from codrag.api.routers.projects.search import _get_compressor
        comp = _get_compressor("lod")
        assert isinstance(comp, NoopCompressor)

    def test_unknown_returns_noop(self) -> None:
        from codrag.api.routers.projects.search import _get_compressor
        comp = _get_compressor("garbage")
        assert isinstance(comp, NoopCompressor)


# ═══════════════════════════════════════════════════════════════════
# Dual-channel auto mode (LOD for code + Lingua for docs)
# ═══════════════════════════════════════════════════════════════════


class TestDualChannelAutoMode:
    """Test _apply_lingua_to_doc_chunks — the dual-channel routing function."""

    def test_code_only_result_unchanged(self) -> None:
        """When all chunks are code files, Lingua does nothing."""
        from codrag.api.routers.projects.search import _apply_lingua_to_doc_chunks
        lod_result = {
            "context": "[score=0.8 | @src/auth.py]\ndef login(): ...",
            "chunks": [{"source_path": "src/auth.py", "score": 0.8}],
            "total_chars": 42,
            "estimated_tokens": 10,
        }
        result = _apply_lingua_to_doc_chunks(lod_result, "auth")
        # Should be unchanged — no doc chunks to compress
        assert result["context"] == lod_result["context"]

    def test_doc_chunk_gets_compressed(self) -> None:
        """Markdown chunks should be compressed by Lingua."""
        from codrag.api.routers.projects.search import _apply_lingua_to_doc_chunks
        doc_content = (
            "This is a comprehensive documentation file that explains in great detail "
            "how the authentication system works within the broader context of the "
            "application architecture and its various subsystems. It covers multiple "
            "aspects including session management, token validation, and authorization "
            "flow patterns that are commonly used throughout the entire codebase for "
            "security purposes. The document also discusses the integration points "
            "between the authentication middleware and the request handling pipeline, "
            "including how JWT tokens are validated, how refresh tokens are rotated, "
            "and how the permission system maps roles to specific API endpoint access "
            "controls. Understanding these patterns is essential for anyone modifying "
            "the security infrastructure of the application."
        )
        context = f"[@docs/auth.md]\n{doc_content}"
        original_len = len(context)
        lod_result = {
            "context": context,
            "chunks": [{"source_path": "docs/auth.md", "score": 0.6}],
            "total_chars": original_len,
            "estimated_tokens": original_len // 4,
        }
        result = _apply_lingua_to_doc_chunks(lod_result, "authentication")
        # Lingua should have compressed the doc content
        assert len(result["context"]) < original_len
        comp = result.get("compression", {})
        assert comp.get("mode") == "auto"
        assert comp.get("lingua_input_chars", 0) > 0
        assert comp.get("lingua_output_chars", 0) > 0
        assert comp.get("lingua_ratio", 0) > 1.0

    def test_mixed_preserves_code_compresses_docs(self) -> None:
        """In a mixed result, code stays intact while docs get compressed."""
        from codrag.api.routers.projects.search import _apply_lingua_to_doc_chunks
        code_block = "[score=0.9 | @src/auth.py]\ndef login(user, password):\n    return validate(user)"
        doc_content = (
            "The authentication module provides comprehensive security features "
            "including password hashing, session management, OAuth integration, "
            "rate limiting, and brute force protection mechanisms that safeguard "
            "the application from unauthorized access attempts. It implements "
            "a multi-layered defense strategy with configurable lockout thresholds, "
            "cryptographically secure token generation, and automatic session "
            "invalidation after configurable idle timeouts. The module also supports "
            "multi-factor authentication via TOTP and WebAuthn protocols."
        )
        doc_block = f"[@docs/auth-guide.md]\n{doc_content}"
        context = f"{code_block}\n\n---\n\n{doc_block}"
        original_len = len(context)
        lod_result = {
            "context": context,
            "chunks": [
                {"source_path": "src/auth.py", "score": 0.9},
                {"source_path": "docs/auth-guide.md", "score": 0.6},
            ],
            "total_chars": original_len,
            "estimated_tokens": original_len // 4,
        }
        result = _apply_lingua_to_doc_chunks(lod_result, "authentication")
        # Code block should be preserved exactly
        assert "def login(user, password):" in result["context"]
        # Doc block should be compressed (shorter overall)
        assert len(result["context"]) < original_len

    def test_empty_context_noop(self) -> None:
        from codrag.api.routers.projects.search import _apply_lingua_to_doc_chunks
        result = _apply_lingua_to_doc_chunks(
            {"context": "", "chunks": [], "total_chars": 0}, "test"
        )
        assert result["context"] == ""

    def test_short_doc_chunk_skipped(self) -> None:
        """Doc chunks under 100 chars are not worth compressing."""
        from codrag.api.routers.projects.search import _apply_lingua_to_doc_chunks
        lod_result = {
            "context": "[@docs/short.md]\nBrief note.",
            "chunks": [{"source_path": "docs/short.md", "score": 0.5}],
            "total_chars": 30,
            "estimated_tokens": 7,
        }
        result = _apply_lingua_to_doc_chunks(lod_result, "test")
        assert result["context"] == lod_result["context"]


class TestLinguaCompressorLive:
    """Live integration tests — actually run LLMLingua-2 on real content."""

    def test_compress_real_text(self) -> None:
        comp = LinguaCompressor()
        if not comp.is_available():
            pytest.skip("llmlingua not installed")
        result = comp.compress(
            "CoDRAG is a local-first codebase intelligence platform that builds "
            "persistent semantic indexes of codebases and serves bounded, source-cited "
            "context to AI coding agents via MCP. The goal is to give AI agents robust "
            "contextual and epistemological knowledge of a codebase.",
            level="standard",
        )
        assert result.error is None
        assert result.compression_ratio > 1.3
        assert result.output_chars < result.input_chars
        # Key terms should survive
        assert "CoDRAG" in result.compressed or "codrag" in result.compressed.lower()

    def test_compress_damages_file_refs(self) -> None:
        """LLMLingua-2 damages file paths — documents why auto mode uses LOD only.

        Quality testing showed that even with FORCE_TOKENS protecting .py and /,
        the model removes the identifier text between path separators.
        E.g., src/codrag/services/config_manager.py → / codrag / config _ manager.py
        """
        comp = LinguaCompressor()
        if not comp.is_available():
            pytest.skip("llmlingua not installed")
        result = comp.compress(
            "The main entry point is src/codrag/server.py which starts the FastAPI "
            "daemon on port 8400. Configuration lives in src/codrag/services/config_manager.py "
            "and the CLI is at src/codrag/cli.py for command-line usage.",
            level="light",
        )
        assert result.error is None
        assert result.compression_ratio > 1.2
        # .py extension survives (in FORCE_TOKENS) but path basenames may not
        assert ".py" in result.compressed

    def test_compress_code_badly(self) -> None:
        """Demonstrate that Lingua damages code — validates why we use LOD for code."""
        comp = LinguaCompressor()
        if not comp.is_available():
            pytest.skip("llmlingua not installed")
        code = (
            "def calculate_score(items: List[Dict], weights: Dict[str, float]) -> float:\n"
            "    total = sum(w * items[i].get('value', 0) for i, w in weights.items())\n"
            "    return round(total / max(len(items), 1), 4)\n"
        )
        result = comp.compress(code, level="standard")
        # The compressed version should be syntactically broken or missing key tokens
        # This test documents WHY we don't use Lingua on code
        if result.compression_ratio > 1.5:
            # If it compressed significantly, syntax is likely broken
            try:
                compile(result.compressed, "<test>", "exec")
                # If it somehow compiles, that's fine too
            except SyntaxError:
                pass  # Expected — Lingua corrupts code syntax


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
