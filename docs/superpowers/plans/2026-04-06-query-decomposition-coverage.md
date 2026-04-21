# Query Decomposition + Coverage Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add query decomposition (extract structural signals and route to graph before semantic search) and query coverage indicators (show which query terms matched) to Prep's search pipeline, completing Phase 73.5.

**Architecture:** Query decomposition adds a pre-search analysis step in `CodeIndex.search()` that extracts file names, symbol names, and module references from the query, looks them up via the trace graph, and injects them as priority results before semantic search runs. Query coverage adds a `matched_terms` dict to the search response so agents can see which terms drove the results. Both features are additive — no changes to existing search behavior when queries have no structural signals.

**Tech Stack:** Python 3.11, regex, existing TraceIndex, existing CodeIndex.search()

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/prep/core/query_analyzer.py` | **Create** | Extract structural signals from queries (file names, symbols, modules) |
| `src/prep/core/index.py` | **Modify** | Call query analyzer, inject graph hits, add coverage to response |
| `src/prep/api/routers/projects/search.py` | **Modify** | Forward coverage metadata in context response |
| `src/prep/mcp/server.py` | **Modify** | Include coverage in MCP search markdown output |
| `tests/test_query_analyzer.py` | **Create** | Tests for query analysis + coverage |

---

### Task 1: Create QueryAnalyzer

**Files:**
- Create: `src/prep/core/query_analyzer.py`
- Create: `tests/test_query_analyzer.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_query_analyzer.py
"""Tests for query structural signal extraction."""
from __future__ import annotations

import pytest

from prep.core.query_analyzer import QueryAnalyzer, QuerySignals


class TestExtractSignals:
    def test_file_name_extraction(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does orchestrator.py handle stages")
        assert "orchestrator.py" in signals.file_names

    def test_file_path_extraction(self) -> None:
        signals = QueryAnalyzer.extract_signals("look at src/prep/mcp/server.py")
        assert "src/prep/mcp/server.py" in signals.file_paths

    def test_symbol_extraction_camelcase(self) -> None:
        signals = QueryAnalyzer.extract_signals("what does PipelineOrchestrator do")
        assert "PipelineOrchestrator" in signals.symbols

    def test_symbol_extraction_snake_case_function(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does assign_lod work")
        assert "assign_lod" in signals.symbols

    def test_module_extraction(self) -> None:
        signals = QueryAnalyzer.extract_signals("explain the MCP server module")
        assert any("mcp" in kw for kw in signals.keywords)

    def test_no_signals_from_plain_query(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does authentication work")
        assert len(signals.file_names) == 0
        assert len(signals.file_paths) == 0
        assert len(signals.symbols) == 0

    def test_mixed_query(self) -> None:
        signals = QueryAnalyzer.extract_signals(
            "how does CodeIndex.search in src/prep/core/index.py handle scoring"
        )
        assert "src/prep/core/index.py" in signals.file_paths
        assert "CodeIndex" in signals.symbols

    def test_keywords_extracted(self) -> None:
        signals = QueryAnalyzer.extract_signals("pipeline orchestrator stage processing")
        assert "pipeline" in signals.keywords
        assert "orchestrator" in signals.keywords
        assert "stage" in signals.keywords

    def test_stop_words_excluded(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does the function work")
        assert "how" not in signals.keywords
        assert "does" not in signals.keywords
        assert "the" not in signals.keywords

    def test_has_structural_signals(self) -> None:
        assert QueryAnalyzer.extract_signals("look at server.py").has_structural_signals
        assert QueryAnalyzer.extract_signals("what does MyClass do").has_structural_signals
        assert not QueryAnalyzer.extract_signals("how does auth work").has_structural_signals


class TestQueryCoverage:
    def test_compute_coverage(self) -> None:
        signals = QueryAnalyzer.extract_signals("pipeline orchestrator stage")
        content = "The pipeline orchestrator processes build stages"
        coverage = signals.compute_coverage(content)
        assert coverage["pipeline"] is True
        assert coverage["orchestrator"] is True
        assert coverage["stage"] is True

    def test_partial_coverage(self) -> None:
        signals = QueryAnalyzer.extract_signals("pipeline auth MCP")
        content = "The pipeline processes files"
        coverage = signals.compute_coverage(content)
        assert coverage["pipeline"] is True
        assert coverage.get("auth") is False or coverage.get("auth") is None
        assert coverage.get("mcp") is False or coverage.get("mcp") is None

    def test_coverage_ratio(self) -> None:
        signals = QueryAnalyzer.extract_signals("pipeline orchestrator auth")
        content = "The pipeline orchestrator runs"
        ratio = signals.coverage_ratio(content)
        assert ratio == pytest.approx(2 / 3, abs=0.01)

    def test_empty_signals(self) -> None:
        signals = QueryAnalyzer.extract_signals("how does it work")
        ratio = signals.coverage_ratio("some content")
        assert ratio == 1.0  # no keywords = fully covered by default
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_query_analyzer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement QueryAnalyzer**

```python
# src/prep/core/query_analyzer.py
"""Query structural signal extraction for search decomposition.

Phase 73.5: Extracts file names, file paths, symbol names, and keywords
from search queries so the search pipeline can route structural queries
to the trace graph before falling back to semantic search.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set


# File extensions we recognize
_FILE_EXT_RE = re.compile(
    r"\b([\w/.-]+\.(?:py|ts|tsx|js|jsx|rs|go|java|kt|swift|cs|cpp|c|rb|php|md|json|toml|yaml|yml))\b"
)

# CamelCase symbols (class names, type names)
_CAMEL_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")

# snake_case identifiers with at least one underscore (function/variable names)
_SNAKE_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")

# Words that should not be treated as keywords
_STOP_WORDS = frozenset({
    "the", "how", "does", "what", "where", "when", "why", "which",
    "this", "that", "with", "from", "have", "has", "are", "was",
    "were", "been", "being", "for", "and", "not", "but", "all",
    "can", "will", "just", "about", "into", "file", "files",
    "code", "function", "class", "method", "work", "works",
    "look", "explain", "show", "find", "get", "use", "uses",
    "does", "handle", "handles", "module", "modules",
})


@dataclass
class QuerySignals:
    """Structural signals extracted from a search query."""

    file_names: List[str] = field(default_factory=list)   # e.g. ["server.py"]
    file_paths: List[str] = field(default_factory=list)    # e.g. ["src/prep/mcp/server.py"]
    symbols: List[str] = field(default_factory=list)       # e.g. ["PipelineOrchestrator"]
    keywords: List[str] = field(default_factory=list)      # e.g. ["pipeline", "orchestrator"]

    @property
    def has_structural_signals(self) -> bool:
        """True if the query contains file names, paths, or symbol references."""
        return bool(self.file_names or self.file_paths or self.symbols)

    def compute_coverage(self, content: str) -> Dict[str, bool]:
        """Check which keywords appear in the given content."""
        if not self.keywords:
            return {}
        content_lower = content.lower()
        return {kw: kw.lower() in content_lower for kw in self.keywords}

    def coverage_ratio(self, content: str) -> float:
        """Fraction of keywords found in content (0.0-1.0). Returns 1.0 if no keywords."""
        if not self.keywords:
            return 1.0
        coverage = self.compute_coverage(content)
        matched = sum(1 for v in coverage.values() if v)
        return matched / len(coverage)


class QueryAnalyzer:
    """Extract structural signals from search queries."""

    @staticmethod
    def extract_signals(query: str) -> QuerySignals:
        """Parse a query for file names, paths, symbol names, and keywords.

        Examples:
            "how does orchestrator.py handle stages"
              → file_names=["orchestrator.py"], keywords=["orchestrator", "stages"]

            "look at src/prep/mcp/server.py"
              → file_paths=["src/prep/mcp/server.py"]

            "what does PipelineOrchestrator do"
              → symbols=["PipelineOrchestrator"], keywords=["pipeline", "orchestrator"]
        """
        file_paths: List[str] = []
        file_names: List[str] = []
        symbols: List[str] = []

        # Extract file paths and names
        for match in _FILE_EXT_RE.finditer(query):
            path = match.group(1)
            if "/" in path:
                file_paths.append(path)
            else:
                file_names.append(path)

        # Extract CamelCase symbols
        for match in _CAMEL_RE.finditer(query):
            sym = match.group(1)
            # Skip if it's part of a file path we already extracted
            if not any(sym in fp for fp in file_paths + file_names):
                symbols.append(sym)

        # Extract snake_case symbols
        for match in _SNAKE_RE.finditer(query):
            sym = match.group(1)
            if not any(sym in fp for fp in file_paths + file_names):
                symbols.append(sym)

        # Extract keywords (non-stop words, 3+ chars)
        raw_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", query.lower())
        keywords = [t for t in raw_tokens if t not in _STOP_WORDS]
        # Deduplicate while preserving order
        seen: Set[str] = set()
        deduped: List[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                deduped.append(kw)

        return QuerySignals(
            file_names=file_names,
            file_paths=file_paths,
            symbols=symbols,
            keywords=deduped,
        )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_query_analyzer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/query_analyzer.py tests/test_query_analyzer.py
git commit -m "feat(search): add QueryAnalyzer for structural signal extraction from queries"
```

---

### Task 2: Integrate Query Decomposition into CodeIndex.search()

**Files:**
- Modify: `src/prep/core/index.py:980-1102` (the `search` method)
- Modify: `tests/test_query_analyzer.py` (add integration-level tests)

- [ ] **Step 1: Add integration tests**

Add to `tests/test_query_analyzer.py`:

```python
class TestGraphInjection:
    """Test that structural signals produce graph-based score boosts."""

    def test_file_path_signal_boosts_matching_docs(self) -> None:
        from prep.core.query_analyzer import QueryAnalyzer
        signals = QueryAnalyzer.extract_signals("look at src/prep/mcp/server.py")
        # The injection function returns a boost array
        from prep.core.index import _structural_boosts
        docs = [
            {"source_path": "src/prep/mcp/server.py", "id": "1"},
            {"source_path": "src/prep/core/index.py", "id": "2"},
            {"source_path": "src/prep/api/routers/search.py", "id": "3"},
        ]
        boosts = _structural_boosts(signals, docs)
        assert boosts[0] > 0.0   # server.py gets boost
        assert boosts[1] == 0.0  # index.py does not
        assert boosts[2] == 0.0  # search.py does not

    def test_file_name_signal_boosts_basename_match(self) -> None:
        from prep.core.query_analyzer import QueryAnalyzer
        signals = QueryAnalyzer.extract_signals("explain orchestrator.py")
        from prep.core.index import _structural_boosts
        docs = [
            {"source_path": "src/prep/services/pipeline/orchestrator.py", "id": "1"},
            {"source_path": "src/prep/core/index.py", "id": "2"},
        ]
        boosts = _structural_boosts(signals, docs)
        assert boosts[0] > 0.0  # orchestrator.py matches

    def test_symbol_signal_boosts_content_match(self) -> None:
        from prep.core.query_analyzer import QueryAnalyzer
        signals = QueryAnalyzer.extract_signals("what does PipelineOrchestrator do")
        from prep.core.index import _structural_boosts
        docs = [
            {"source_path": "orchestrator.py", "id": "1", "content": "class PipelineOrchestrator:"},
            {"source_path": "utils.py", "id": "2", "content": "def helper(): pass"},
        ]
        boosts = _structural_boosts(signals, docs)
        assert boosts[0] > 0.0  # PipelineOrchestrator in content

    def test_no_signals_no_boosts(self) -> None:
        from prep.core.query_analyzer import QueryAnalyzer
        signals = QueryAnalyzer.extract_signals("how does auth work")
        from prep.core.index import _structural_boosts
        docs = [{"source_path": "auth.py", "id": "1"}]
        boosts = _structural_boosts(signals, docs)
        assert boosts[0] == 0.0  # no structural signals
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_query_analyzer.py::TestGraphInjection -v`
Expected: FAIL — `cannot import name '_structural_boosts'`

- [ ] **Step 3: Implement _structural_boosts in index.py**

Add this function near the other boost functions (after `_fts_boosts`, around line 2009):

```python
def _structural_boosts(
    signals: "QuerySignals",
    docs: List[Dict[str, Any]],
) -> "np.ndarray":
    """Compute score boosts from structural query signals (Phase 73.5).

    File path matches get a strong boost (0.35) — the user explicitly
    named a file. File name matches get a moderate boost (0.25) — basename
    match. Symbol matches in content get a smaller boost (0.15).
    """
    import numpy as np
    boosts = np.zeros(len(docs), dtype=np.float32)

    if not signals.has_structural_signals:
        return boosts

    for i, d in enumerate(docs):
        sp = str(d.get("source_path") or "")
        content = str(d.get("content") or "")
        boost = 0.0

        # Exact file path match (strongest signal)
        for fp in signals.file_paths:
            if sp == fp:
                boost = max(boost, 0.35)
            elif sp.endswith("/" + fp) or sp == fp:
                boost = max(boost, 0.35)

        # Basename match
        if sp:
            basename = sp.rsplit("/", 1)[-1]
            for fn in signals.file_names:
                if basename == fn:
                    boost = max(boost, 0.25)

        # Symbol in content
        for sym in signals.symbols:
            if sym in content:
                boost = max(boost, 0.15)

        boosts[i] = boost

    return boosts
```

Make this a module-level function (not a method) so it's importable for testing. Add the import at the top of the file:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from prep.core.query_analyzer import QuerySignals
```

- [ ] **Step 4: Wire into CodeIndex.search()**

In the `search` method, after the existing boost lines (around line 1030-1031):

```python
        sims = sims + self._keyword_boosts(query, docs)
        sims = sims + self._fts_boosts(query, docs, limit=max(10, k * 4))
```

Add structural boosts:

```python
        # Phase 73.5: Structural query decomposition — boost files/symbols named in query
        from prep.core.query_analyzer import QueryAnalyzer
        _query_signals = QueryAnalyzer.extract_signals(query)
        sims = sims + _structural_boosts(_query_signals, docs)
```

Store `_query_signals` as an attribute so `get_context_structured` can access it later for coverage:

```python
        self._last_query_signals = _query_signals
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_query_analyzer.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/prep/core/index.py tests/test_query_analyzer.py
git commit -m "feat(search): structural query decomposition — boost files/symbols named in queries"
```

---

### Task 3: Add Query Coverage to Search Response

**Files:**
- Modify: `src/prep/core/index.py:1274-1370` (`get_context_structured`)
- Modify: `src/prep/api/routers/projects/search.py` (forward coverage)
- Modify: `src/prep/mcp/server.py:915-928` (include in markdown)

- [ ] **Step 1: Add coverage computation to get_context_structured**

In `get_context_structured` (around line 1274), after the results are assembled, add coverage computation before the return. Find the return statement and add coverage metadata:

```python
        # Phase 73.5: Query coverage — show which terms matched
        query_coverage = None
        signals = getattr(self, "_last_query_signals", None)
        if signals and signals.keywords:
            all_content = " ".join(
                str(d.get("content") or "") + " " + str(d.get("source_path") or "")
                for d in [r.doc for r in results]
            )
            coverage = signals.compute_coverage(all_content)
            matched = sum(1 for v in coverage.values() if v)
            query_coverage = {
                "terms": coverage,
                "matched": matched,
                "total": len(coverage),
                "ratio": round(matched / len(coverage), 2) if coverage else 1.0,
            }
```

Add `query_coverage` to the returned dict. Find where the return dict is built and add:

```python
        if query_coverage:
            result["query_coverage"] = query_coverage
```

- [ ] **Step 2: Forward coverage in search.py context response**

In `src/prep/api/routers/projects/search.py`, in the `context_project` function, after the LOD compression result is built (around line 1022-1040), add:

```python
        # Phase 73.5: Forward query coverage metadata
        if isinstance(result, dict) and "query_coverage" in result:
            resp_data["query_coverage"] = result["query_coverage"]
```

- [ ] **Step 3: Include coverage in MCP search markdown**

In `src/prep/mcp/server.py`, in `tool_search` (around line 915-928 where the confidence line is built), add coverage info after the confidence line:

```python
            # Phase 73.5: Query coverage indicator
            if isinstance(data, dict):
                qcov = data.get("query_coverage")
                if qcov and isinstance(qcov, dict):
                    terms = qcov.get("terms", {})
                    if terms:
                        matched = [k for k, v in terms.items() if v]
                        missed = [k for k, v in terms.items() if not v]
                        parts = []
                        if matched:
                            parts.append(" ".join(f"{t}\u2713" for t in matched))
                        if missed:
                            parts.append(" ".join(f"{t}\u2717" for t in missed))
                        coverage_line = f"[query terms: {' | '.join(parts)}]\n"
                        context_str = context_str.rstrip() + "\n" + coverage_line
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/pytest tests/test_query_analyzer.py tests/test_context_tier.py tests/test_lod_extractor.py tests/test_compressor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/index.py src/prep/api/routers/projects/search.py src/prep/mcp/server.py
git commit -m "feat(search): add query coverage indicator — show which terms matched in results"
```

---

### Task 4: Export + Final Integration

**Files:**
- Modify: `src/prep/core/__init__.py`

- [ ] **Step 1: Add exports**

```python
from .query_analyzer import QueryAnalyzer, QuerySignals
```

Add to `__all__`:

```python
    "QueryAnalyzer",
    "QuerySignals",
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/pytest tests/test_query_analyzer.py tests/test_context_tier.py tests/test_lod_extractor.py tests/test_compressor.py -v --tb=short`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/prep/core/__init__.py
git commit -m "feat(core): export QueryAnalyzer and QuerySignals"
```

---

## Verification

1. **Query decomposition works:** A query like "explain orchestrator.py" boosts `orchestrator.py` chunks by +0.25 via structural signals, on top of existing keyword and BM25 boosts.
2. **Coverage indicator works:** Search response includes `query_coverage: {terms: {pipeline: true, auth: false}, matched: 1, total: 2, ratio: 0.5}`.
3. **MCP output shows coverage:** Search markdown includes `[query terms: pipeline✓ | auth✗]`.
4. **Backward compatible:** Queries without structural signals get zero structural boost — existing behavior unchanged.
5. **All existing tests pass:** No regressions in LOD, tier, or compressor tests.
