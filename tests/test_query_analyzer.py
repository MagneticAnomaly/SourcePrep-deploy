"""Tests for QueryAnalyzer structural signal extraction."""

from __future__ import annotations

from prep.core.query_analyzer import QueryAnalyzer, QuerySignals


class TestFileNameExtraction:
    def test_extracts_file_name(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does orchestrator.py handle stages")
        assert "orchestrator.py" in signals.file_names

    def test_does_not_extract_name_from_path(self) -> None:
        signals = QueryAnalyzer.extract_signals("look at src/codrag/mcp/server.py")
        # server.py is part of a path, should not also appear as a bare name
        assert "server.py" not in signals.file_names


class TestFilePathExtraction:
    def test_extracts_file_path(self) -> None:
        signals = QueryAnalyzer.extract_signals("look at src/codrag/mcp/server.py")
        assert "src/codrag/mcp/server.py" in signals.file_paths

    def test_path_with_various_extensions(self) -> None:
        signals = QueryAnalyzer.extract_signals("check engine/crates/codrag-walker/src/lib.rs")
        assert any(p.endswith(".rs") for p in signals.file_paths)


class TestSymbolExtraction:
    def test_camel_case_symbol(self) -> None:
        signals = QueryAnalyzer.extract_signals("what does PipelineOrchestrator do")
        assert "PipelineOrchestrator" in signals.symbols

    def test_snake_case_symbol(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does assign_lod work")
        assert "assign_lod" in signals.symbols

    def test_symbol_not_from_file_path(self) -> None:
        signals = QueryAnalyzer.extract_signals(
            "how does CodeIndex.search in src/codrag/core/index.py handle scoring"
        )
        assert "src/codrag/core/index.py" in signals.file_paths
        assert "CodeIndex" in signals.symbols


class TestNoSignalsFromPlainQuery:
    def test_plain_query(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does authentication work")
        assert signals.file_names == []
        assert signals.file_paths == []
        assert signals.symbols == []


class TestMixedQuery:
    def test_path_and_symbol(self) -> None:
        signals = QueryAnalyzer.extract_signals(
            "how does CodeIndex.search in src/codrag/core/index.py handle scoring"
        )
        assert "src/codrag/core/index.py" in signals.file_paths
        assert "CodeIndex" in signals.symbols


class TestKeywords:
    def test_keywords_extracted(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does authentication work")
        assert "authentication" in signals.keywords

    def test_stop_words_excluded(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does the function handle errors")
        for stop in ("how", "does", "the", "function", "handle"):
            assert stop not in signals.keywords
        assert "errors" in signals.keywords


class TestHasStructuralSignals:
    def test_true_with_file_name(self) -> None:
        signals = QuerySignals(file_names=["foo.py"])
        assert signals.has_structural_signals is True

    def test_true_with_symbol(self) -> None:
        signals = QuerySignals(symbols=["FooBar"])
        assert signals.has_structural_signals is True

    def test_false_when_empty(self) -> None:
        signals = QuerySignals(keywords=["auth"])
        assert signals.has_structural_signals is False


class TestCoverage:
    def test_compute_coverage(self) -> None:
        signals = QuerySignals(keywords=["auth", "token", "missing"])
        content = "This handles auth and token validation"
        cov = signals.compute_coverage(content)
        assert cov["auth"] is True
        assert cov["token"] is True
        assert cov["missing"] is False

    def test_coverage_ratio(self) -> None:
        signals = QuerySignals(keywords=["auth", "token", "missing"])
        content = "This handles auth and token validation"
        assert abs(signals.coverage_ratio(content) - 2 / 3) < 1e-9

    def test_coverage_ratio_no_keywords(self) -> None:
        signals = QuerySignals()
        assert signals.coverage_ratio("anything") == 1.0


class TestGraphInjection:
    def test_file_path_signal_boosts_matching_docs(self) -> None:
        from prep.core.query_analyzer import QueryAnalyzer
        from prep.core.index import _structural_boosts
        signals = QueryAnalyzer.extract_signals("look at src/codrag/mcp/server.py")
        docs = [
            {"source_path": "src/codrag/mcp/server.py", "id": "1"},
            {"source_path": "src/codrag/core/index.py", "id": "2"},
        ]
        boosts = _structural_boosts(signals, docs)
        assert boosts[0] > 0.0
        assert boosts[1] == 0.0

    def test_file_name_signal_boosts_basename_match(self) -> None:
        from prep.core.query_analyzer import QueryAnalyzer
        from prep.core.index import _structural_boosts
        signals = QueryAnalyzer.extract_signals("explain orchestrator.py")
        docs = [
            {"source_path": "src/codrag/services/pipeline/orchestrator.py", "id": "1"},
            {"source_path": "src/codrag/core/index.py", "id": "2"},
        ]
        boosts = _structural_boosts(signals, docs)
        assert boosts[0] > 0.0

    def test_symbol_signal_boosts_content_match(self) -> None:
        from prep.core.query_analyzer import QueryAnalyzer
        from prep.core.index import _structural_boosts
        signals = QueryAnalyzer.extract_signals("what does PipelineOrchestrator do")
        docs = [
            {"source_path": "orchestrator.py", "id": "1", "content": "class PipelineOrchestrator:"},
            {"source_path": "utils.py", "id": "2", "content": "def helper(): pass"},
        ]
        boosts = _structural_boosts(signals, docs)
        assert boosts[0] > 0.0
        assert boosts[1] == 0.0

    def test_no_signals_no_boosts(self) -> None:
        from prep.core.query_analyzer import QueryAnalyzer
        from prep.core.index import _structural_boosts
        signals = QueryAnalyzer.extract_signals("how does auth work")
        docs = [{"source_path": "auth.py", "id": "1"}]
        boosts = _structural_boosts(signals, docs)
        assert boosts[0] == 0.0
