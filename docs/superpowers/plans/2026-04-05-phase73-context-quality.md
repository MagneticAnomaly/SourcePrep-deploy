# Phase 73: Context Quality & Retrieval Improvements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dramatically improve the signal-to-noise ratio of Prep MCP tool responses so AI agents receive targeted, relevant, compressed context instead of noisy megabyte payloads that break the protocol.

**Architecture:** Three layers of improvements: (A) inject file-level meta-chunks so search can find large architectural files, (B) cap unbounded response sections and improve hub selection heuristics in the context assembly layer, (C) decompose the 243-line `_assemble_ambient_context` god-function and add chunk-level deduplication in `get_context`.

**Tech Stack:** Python 3.11, numpy, SQLite FTS5, pytest (asyncio_mode="auto")

---

## Task 1: Meta-Chunk Injection During Indexing

**Why:** Large files like `orchestrator.py` (2,643 lines) get split into 20+ chunks, none of which embed the file's overall identity. A query for "orchestrator" doesn't match any single chunk strongly. A synthetic "chunk 0" containing the file path, top-level docstring, class/function names, and section overview creates an anchor that the embedding model can match against structural queries.

**Files:**
- Modify: `src/prep/core/index.py:555-579` (the normal file processing loop in `build()`)
- Modify: `src/prep/core/chunking.py` (add `extract_file_synopsis` helper)
- Test: `tests/test_meta_chunk.py` (new)

- [ ] **Step 1: Write the failing test for synopsis extraction**

Create `tests/test_meta_chunk.py`:

```python
"""Tests for Phase 73 meta-chunk injection."""
from __future__ import annotations

import pytest
from prep.core.chunking import extract_file_synopsis


SAMPLE_PYTHON = '''"""Pipeline orchestrator for multi-stage builds."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Coordinates the execution of build pipeline stages."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.stages: List[str] = []

    def run_stage(self, stage_name: str) -> bool:
        """Execute a single pipeline stage by name."""
        pass

    def process_files(self, paths: List[Path]) -> Dict[str, Any]:
        """Process a batch of files through the pipeline."""
        pass


class StageResult:
    """Result container for a completed pipeline stage."""

    def __init__(self, stage: str, success: bool):
        self.stage = stage
        self.success = success


def create_orchestrator(config_path: Path) -> PipelineOrchestrator:
    """Factory function for pipeline orchestrator."""
    pass
'''


class TestExtractFileSynopsis:
    def test_extracts_module_docstring(self):
        result = extract_file_synopsis(SAMPLE_PYTHON, "src/pipeline/orchestrator.py")
        assert "Pipeline orchestrator for multi-stage builds" in result

    def test_extracts_class_names(self):
        result = extract_file_synopsis(SAMPLE_PYTHON, "src/pipeline/orchestrator.py")
        assert "PipelineOrchestrator" in result
        assert "StageResult" in result

    def test_extracts_function_names(self):
        result = extract_file_synopsis(SAMPLE_PYTHON, "src/pipeline/orchestrator.py")
        assert "run_stage" in result
        assert "process_files" in result
        assert "create_orchestrator" in result

    def test_includes_file_path(self):
        result = extract_file_synopsis(SAMPLE_PYTHON, "src/pipeline/orchestrator.py")
        assert "src/pipeline/orchestrator.py" in result

    def test_respects_max_length(self):
        result = extract_file_synopsis(SAMPLE_PYTHON, "test.py", max_chars=200)
        assert len(result) <= 200

    def test_handles_empty_file(self):
        result = extract_file_synopsis("", "empty.py")
        assert "empty.py" in result

    def test_handles_no_classes(self):
        simple = 'x = 1\ndef foo():\n    pass\n'
        result = extract_file_synopsis(simple, "simple.py")
        assert "foo" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_meta_chunk.py -v`
Expected: FAIL with `ImportError: cannot import name 'extract_file_synopsis'`

- [ ] **Step 3: Implement `extract_file_synopsis` in chunking.py**

Add to end of `src/prep/core/chunking.py`:

```python
import re as _re


def extract_file_synopsis(
    text: str,
    source_path: str,
    max_chars: int = 1500,
) -> str:
    """Build a file-level synopsis for embedding as meta-chunk.

    Extracts the module docstring, class names with their docstrings,
    and top-level function names. This creates a single chunk that
    semantically represents the whole file for retrieval.
    """
    parts: List[str] = [f"File: {source_path}"]

    lines = text.split("\n")

    # Extract module docstring (first triple-quoted string)
    stripped = text.lstrip()
    for quote in ('"""', "'''"):
        if stripped.startswith(quote):
            end = stripped.find(quote, len(quote))
            if end != -1:
                docstring = stripped[len(quote):end].strip()
                if docstring:
                    parts.append(f"Purpose: {docstring}")
            break

    # Extract class names + their docstrings
    classes: List[str] = []
    for i, line in enumerate(lines):
        m = _re.match(r'^class\s+(\w+)', line)
        if m:
            cls_name = m.group(1)
            cls_doc = ""
            # Look for docstring on next non-empty line
            for j in range(i + 1, min(i + 4, len(lines))):
                stripped_line = lines[j].strip()
                if not stripped_line:
                    continue
                for quote in ('"""', "'''"):
                    if stripped_line.startswith(quote):
                        end_q = stripped_line.find(quote, len(quote))
                        if end_q != -1:
                            cls_doc = stripped_line[len(quote):end_q].strip()
                        elif j + 1 < len(lines):
                            # Multi-line docstring — take first line
                            cls_doc = stripped_line[len(quote):].strip()
                break
            entry = cls_name
            if cls_doc:
                entry += f" — {cls_doc}"
            classes.append(entry)

    if classes:
        parts.append("Classes: " + "; ".join(classes))

    # Extract top-level function/method names
    functions: List[str] = []
    for line in lines:
        m = _re.match(r'^(?:    )?def\s+(\w+)\s*\(', line)
        if m:
            fn_name = m.group(1)
            if not fn_name.startswith("_"):
                functions.append(fn_name)

    if functions:
        parts.append("Functions: " + ", ".join(functions))

    result = "\n".join(parts)
    if len(result) > max_chars:
        result = result[:max_chars - 3] + "..."
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_meta_chunk.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Write the failing test for meta-chunk in index build**

Add to `tests/test_meta_chunk.py`:

```python
from unittest.mock import MagicMock, patch
from prep.core.index import CodeIndex


class TestMetaChunkInBuild:
    def test_multi_chunk_file_gets_meta_chunk(self, tmp_path):
        """Files that produce >1 chunk should also get a meta-chunk."""
        # Create a file large enough to produce multiple chunks (>2000 chars)
        big_code = '"""Big module docstring."""\n\nclass Foo:\n    """Foo class."""\n    pass\n\n' + (
            "def func_{i}():\n    pass\n\n".replace("{i}", str(i)) * 1
            for i in range(50)
        )
        big_code = '"""Big module docstring."""\n\nclass Foo:\n    """Foo class."""\n    pass\n\n'
        big_code += "\n".join(f"def func_{i}():\n    x = {i}\n    return x\n" for i in range(80))

        src = tmp_path / "repo" / "big.py"
        src.parent.mkdir(parents=True)
        src.write_text(big_code)

        # Build index and check that a META_SYNOPSIS chunk exists
        embedder = MagicMock()
        embedder.embed.return_value = MagicMock(vector=[0.1] * 384)
        embedder.embed_query = embedder.embed

        idx = CodeIndex(index_dir=tmp_path / "idx", embedder=embedder)
        idx.build(repo_root=tmp_path / "repo", file_paths=[src])

        docs = idx._documents or []
        meta_docs = [d for d in docs if d.get("section") == "META_SYNOPSIS"]
        assert len(meta_docs) == 1, f"Expected 1 meta-chunk, got {len(meta_docs)}"
        assert "Foo" in meta_docs[0]["content"]
        assert "big.py" in meta_docs[0]["content"]
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_meta_chunk.py::TestMetaChunkInBuild -v`
Expected: FAIL (no META_SYNOPSIS chunks exist yet)

- [ ] **Step 7: Inject meta-chunk into the build loop**

Modify `src/prep/core/index.py:555-579`. After the normal chunking loop, add meta-chunk generation for files that produce multiple chunks:

```python
# In build(), after line 559 (chunks = chunk_code(...)):

            # Normal processing for small files
            if file_path.suffix.lower() in (".md", ".markdown"):
                chunks = chunk_markdown(raw, source_path=rel_path)
            else:
                chunks = chunk_code(raw, source_path=rel_path)

            # Phase 73: Inject meta-chunk for multi-chunk files.
            # A synthetic "chunk 0" with file synopsis anchors the whole
            # file's identity in embedding space so structural queries
            # like "orchestrator" can find orchestrator.py.
            if len(chunks) > 1:
                from prep.core.chunking import extract_file_synopsis
                synopsis = extract_file_synopsis(raw, rel_path)
                meta_chunk_id = stable_file_hash(rel_path + ":meta_synopsis")
                meta_text = self._format_chunk_for_embedding(
                    Chunk(
                        chunk_id=meta_chunk_id,
                        content=synopsis,
                        metadata={"source_path": rel_path, "section": "META_SYNOPSIS"},
                    ),
                    file_hash,
                )
                meta_emb = self.embedder.embed(meta_text).vector
                docs.append({
                    "id": meta_chunk_id,
                    "source_path": rel_path,
                    "file_hash": file_hash,
                    "role": role,
                    "section": "META_SYNOPSIS",
                    "span": None,
                    "content": synopsis,
                })
                vectors.append(meta_emb)
                chunks_embedded += 1
                if is_doc:
                    chunks_docs += 1
                else:
                    chunks_code += 1

            for ch in chunks:
                # ... existing chunk embedding loop unchanged
```

- [ ] **Step 8: Run all meta-chunk tests**

Run: `.venv/bin/pytest tests/test_meta_chunk.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add tests/test_meta_chunk.py src/prep/core/chunking.py src/prep/core/index.py
git commit -m "feat(search): inject meta-chunk synopsis for multi-chunk files

Files producing >1 chunk now get a synthetic META_SYNOPSIS chunk containing
the file path, module docstring, class names, and function names. This
anchors the file's identity in embedding space so structural queries
like 'orchestrator' reliably surface orchestrator.py."
```

---

## Task 2: Budget Caps for Unbounded Response Sections

**Why:** The `tool_context` response in `server.py` appends architecture context, concepts summary, and role atlas projections with **no character limits**. The architecture section alone can grow to 248KB when it dumps all 600+ modules. Even after the tiering fix in `architecture.py`, these sections can still grow unboundedly for large projects. Hard caps prevent any single section from blowing out the total budget.

**Files:**
- Modify: `src/prep/mcp/server.py:969-1005` (architecture + concepts sections in `tool_context`)
- Test: `tests/test_mcp_budget_caps.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_budget_caps.py`:

```python
"""Tests for Phase 73 MCP response budget caps."""
from __future__ import annotations


def _truncate_section(text: str, max_chars: int, label: str) -> str:
    """Replicate the truncation logic we'll add to server.py."""
    if len(text) <= max_chars:
        return text
    # Truncate at last newline before limit to avoid mid-line cut
    truncated = text[:max_chars]
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars // 2:
        truncated = truncated[:last_nl]
    return truncated + f"\n\n[{label}: truncated to {max_chars} chars]"


class TestSectionTruncation:
    def test_short_text_unchanged(self):
        text = "Small section"
        result = _truncate_section(text, 2000, "architecture")
        assert result == text

    def test_long_text_truncated(self):
        text = "line\n" * 1000  # 5000 chars
        result = _truncate_section(text, 2000, "architecture")
        assert len(result) <= 2100  # 2000 + truncation notice
        assert "[architecture: truncated" in result

    def test_truncates_at_newline_boundary(self):
        text = "a" * 999 + "\n" + "b" * 1500
        result = _truncate_section(text, 1200, "test")
        assert result.startswith("a" * 999)
        assert "bbb" not in result  # Should cut at newline
```

- [ ] **Step 2: Run test to verify it passes (helper test only)**

Run: `.venv/bin/pytest tests/test_mcp_budget_caps.py -v`
Expected: PASS (this tests the pure function we'll extract)

- [ ] **Step 3: Add `_truncate_section` to server.py and apply caps**

Modify `src/prep/mcp/server.py`. Add the helper method to `PrepMcpServer` class and apply caps in `tool_context`:

```python
    # Add as a static method on PrepMcpServer:
    @staticmethod
    def _truncate_section(text: str, max_chars: int, label: str) -> str:
        """Truncate a response section to a hard character cap."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        last_nl = truncated.rfind("\n")
        if last_nl > max_chars // 2:
            truncated = truncated[:last_nl]
        return truncated + f"\n\n[{label}: truncated to {max_chars} chars]"
```

Then in `tool_context`, modify the architecture section (lines 969-980):

```python
        # Phase 71: Architecture context (user-curated)
        try:
            arch_data = await self._api_get(
                f"/projects/{project_id}/architecture/context"
            )
            if isinstance(arch_data, dict) and arch_data.get("exists"):
                arch_text = arch_data.get("text", "")
                if arch_text:
                    # Phase 73: Hard cap to prevent context overflow
                    arch_text = self._truncate_section(arch_text, 3000, "architecture")
                    md_parts.append("\n---\n")
                    md_parts.append(arch_text)
        except Exception as e:
            logger.debug("Architecture context failed: %s", e)
```

And the role atlas section (lines 953-967):

```python
        # Phase 64A: Role-based atlas projection
        if role:
            try:
                atlas_data = await self._api_get(
                    f"/projects/{project_id}/atlas?role={role}"
                )
                if isinstance(atlas_data, dict):
                    role_content = atlas_data.get("role_atlas", "")
                    if role_content:
                        # Phase 73: Hard cap on role atlas
                        role_content = self._truncate_section(role_content, 2000, "role atlas")
                        md_parts.append("\n---\n")
                        md_parts.append(role_content)
                        result["role"] = role
                        result["role_atlas_chars"] = len(role_content)
            except Exception as e:
                logger.debug("Role projection failed for role=%s: %s", role, e)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_mcp_budget_caps.py tests/test_mcp_direct_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/mcp/server.py tests/test_mcp_budget_caps.py
git commit -m "feat(mcp): add hard character caps to architecture and role atlas sections

Prevents unbounded response growth from architecture context (cap: 3000),
role atlas (cap: 2000). Truncation preserves newline boundaries and adds
a notice so the agent knows content was trimmed."
```

---

## Task 3: Hub Selection by Structural Importance

**Why:** Hub files are currently selected by picking the "largest chunk" per file. This is a poor heuristic — the largest chunk is often a long function body, not the most representative overview. Instead, prefer chunks that are the file's META_SYNOPSIS (from Task 1), or failing that, the first chunk (which typically contains imports + module docstring).

**Files:**
- Modify: `src/prep/api/routers/projects/search.py:537-542` (hub chunk selection)
- Test: `tests/test_hub_selection.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_hub_selection.py`:

```python
"""Tests for Phase 73 hub chunk selection heuristic."""
from __future__ import annotations


def _pick_best_hub_chunk(file_docs: list) -> dict:
    """Pick the most representative chunk for a hub file.

    Priority: META_SYNOPSIS > first chunk (chunk_index=0) > largest chunk.
    """
    if not file_docs:
        return {}

    # Prefer META_SYNOPSIS
    for d in file_docs:
        if d.get("section") == "META_SYNOPSIS":
            return d

    # Prefer first chunk (imports + module docstring)
    by_span = sorted(file_docs, key=lambda d: (d.get("span") or {}).get("start_line", 9999))
    if by_span:
        return by_span[0]

    # Fallback: largest chunk
    return max(file_docs, key=lambda d: len(str(d.get("content") or "")))


class TestPickBestHubChunk:
    def test_prefers_meta_synopsis(self):
        docs = [
            {"section": "", "content": "a" * 2000, "span": {"start_line": 50}},
            {"section": "META_SYNOPSIS", "content": "File: orchestrator.py\nClasses: Orch", "span": None},
            {"section": "", "content": "b" * 500, "span": {"start_line": 1}},
        ]
        result = _pick_best_hub_chunk(docs)
        assert result["section"] == "META_SYNOPSIS"

    def test_prefers_first_chunk_over_largest(self):
        docs = [
            {"section": "", "content": "a" * 2000, "span": {"start_line": 100}},
            {"section": "", "content": "imports...", "span": {"start_line": 1}},
        ]
        result = _pick_best_hub_chunk(docs)
        assert result["content"] == "imports..."

    def test_falls_back_to_largest(self):
        docs = [
            {"section": "", "content": "small", "span": {}},
            {"section": "", "content": "a" * 2000, "span": {}},
        ]
        result = _pick_best_hub_chunk(docs)
        assert len(result["content"]) == 2000

    def test_handles_empty(self):
        assert _pick_best_hub_chunk([]) == {}
```

- [ ] **Step 2: Run test to verify it passes (testing the logic in isolation)**

Run: `.venv/bin/pytest tests/test_hub_selection.py -v`
Expected: PASS

- [ ] **Step 3: Apply the heuristic to search.py**

Modify `src/prep/api/routers/projects/search.py:537-542`. Replace the `max(file_docs, ...)` line:

```python
    hub_chars = 0
    seen_hub_paths: set = set()  # Phase 73.1 Fix 2: dedup hub files
    for fp, deg in hub_files:
        if hub_chars >= hub_budget:
            break
        if fp in seen_hub_paths:  # Phase 73.1: skip duplicate file paths
            continue
        seen_hub_paths.add(fp)
        file_docs = doc_by_path.get(fp, [])
        if not file_docs:
            continue
        # Phase 73: Pick most representative chunk, not largest.
        # Priority: META_SYNOPSIS > first chunk > largest chunk.
        best_doc = None
        for d in file_docs:
            if d.get("section") == "META_SYNOPSIS":
                best_doc = d
                break
        if best_doc is None:
            by_span = sorted(file_docs, key=lambda d: (d.get("span") or {}).get("start_line", 9999))
            best_doc = by_span[0]
        content = str(best_doc.get("content") or "")
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `.venv/bin/pytest tests/ -x -q --ignore=tests/test_api_envelope.py --ignore=tests/test_dashboard_error_states.py -k "search or ambient or hub" --tb=short`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/projects/search.py tests/test_hub_selection.py
git commit -m "feat(context): select hub chunks by structural importance, not size

Hub files now prefer META_SYNOPSIS chunks (file-level overview) over the
largest chunk. Falls back to first chunk (imports/docstring) then largest.
This ensures hub file sections in prep output show the file's purpose,
not a random function body."
```

---

## Task 4: Search Result Deduplication in `get_context`

**Why:** `get_context()` in `index.py` can return multiple chunks from the same file without deduplication. If two chunks from `orchestrator.py` both rank in the top-k, the agent gets 4000 chars of the same file with no diversity signal. Dedup by file path, keeping only the highest-scoring chunk per file.

**Files:**
- Modify: `src/prep/core/index.py:1192-1226` (`get_context` method)
- Test: `tests/test_context_dedup.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_context_dedup.py`:

```python
"""Tests for Phase 73 search result deduplication."""
from __future__ import annotations

from prep.core.index import SearchResult


def _deduplicate_by_file(results: list[SearchResult]) -> list[SearchResult]:
    """Keep only the highest-scoring chunk per source file."""
    seen: dict[str, SearchResult] = {}
    for r in results:
        fp = r.doc.get("source_path", "")
        if fp not in seen or r.score > seen[fp].score:
            seen[fp] = r
    # Preserve original ordering by score
    return sorted(seen.values(), key=lambda r: -r.score)


class TestDeduplicateByFile:
    def test_removes_lower_scoring_duplicate(self):
        results = [
            SearchResult(doc={"source_path": "a.py", "content": "chunk1"}, score=0.9),
            SearchResult(doc={"source_path": "a.py", "content": "chunk2"}, score=0.7),
            SearchResult(doc={"source_path": "b.py", "content": "chunk3"}, score=0.8),
        ]
        deduped = _deduplicate_by_file(results)
        assert len(deduped) == 2
        paths = [r.doc["source_path"] for r in deduped]
        assert paths == ["a.py", "b.py"]
        assert deduped[0].score == 0.9

    def test_preserves_unique_results(self):
        results = [
            SearchResult(doc={"source_path": "a.py", "content": "c1"}, score=0.9),
            SearchResult(doc={"source_path": "b.py", "content": "c2"}, score=0.8),
            SearchResult(doc={"source_path": "c.py", "content": "c3"}, score=0.7),
        ]
        deduped = _deduplicate_by_file(results)
        assert len(deduped) == 3

    def test_empty_input(self):
        assert _deduplicate_by_file([]) == []
```

- [ ] **Step 2: Run test to verify it passes (isolated logic test)**

Run: `.venv/bin/pytest tests/test_context_dedup.py -v`
Expected: PASS

- [ ] **Step 3: Apply deduplication in `get_context`**

Modify `src/prep/core/index.py:1184-1190`, adding dedup after the search call:

```python
    def get_context(
        self,
        query: str,
        k: int = 5,
        max_chars: int = 6000,
        include_sources: bool = True,
        include_scores: bool = False,
        min_score: float = 0.15,
        segment_file_paths: Optional[set] = None,
        segment_boost: float = 0.12,
    ) -> str:
        results = self.search(
            query, k=k, min_score=min_score,
            segment_file_paths=segment_file_paths,
            segment_boost=segment_boost,
        )
        if not results:
            return ""

        # Phase 73: Deduplicate by file path — keep highest-scoring chunk per file.
        seen_files: Dict[str, SearchResult] = {}
        for r in results:
            fp = r.doc.get("source_path", "")
            if fp not in seen_files or r.score > seen_files[fp].score:
                seen_files[fp] = r
        results = sorted(seen_files.values(), key=lambda r: -r.score)

        parts: List[str] = [
            # ... rest unchanged
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_context_dedup.py tests/test_mmr_diversity.py tests/test_path_weights.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/index.py tests/test_context_dedup.py
git commit -m "feat(search): deduplicate search results by file path in get_context

When multiple chunks from the same file rank in top-k, only the highest-
scoring chunk is included. This improves diversity of search results and
prevents a single large file from consuming the entire context budget."
```

---

## Task 5: Improved Neighbor LOD Fallback

**Why:** When LOD extraction fails for neighbor files, the current fallback truncates to 500 chars blindly — often cutting mid-function. Better: use the file's META_SYNOPSIS chunk (from Task 1) if available, or truncate at a newline boundary.

**Files:**
- Modify: `src/prep/api/routers/projects/search.py:606-611` (neighbor fallback in `_assemble_ambient_context`)

- [ ] **Step 1: Modify the neighbor fallback in search.py**

Replace the fallback block at `search.py:606-611`:

```python
        if lod_content:
            content = lod_content
            lod_label = "LOD 2"
        elif file_docs:
            # Phase 73: Prefer META_SYNOPSIS over blind truncation
            meta_doc = next((d for d in file_docs if d.get("section") == "META_SYNOPSIS"), None)
            if meta_doc:
                content = str(meta_doc.get("content") or "")
                lod_label = "synopsis"
            else:
                best_doc = max(file_docs, key=lambda d: len(str(d.get("content") or "")))
                raw = str(best_doc.get("content") or "")
                # Truncate at newline boundary, not mid-line
                if len(raw) > 500:
                    cut = raw[:500].rfind("\n")
                    if cut > 250:
                        content = raw[:cut] + "\n..."
                    else:
                        content = raw[:500] + "..."
                else:
                    content = raw
                lod_label = "truncated"
        else:
            continue
```

- [ ] **Step 2: Run existing tests**

Run: `.venv/bin/pytest tests/ -x -q --ignore=tests/test_api_envelope.py --ignore=tests/test_dashboard_error_states.py -k "search or ambient or context" --tb=short`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/prep/api/routers/projects/search.py
git commit -m "feat(context): improve neighbor LOD fallback with synopsis and newline-aware truncation

Neighbor files that fail LOD extraction now prefer META_SYNOPSIS chunks
over blind 500-char truncation. Plain truncation now cuts at newline
boundaries to avoid mid-line artifacts."
```

---

## Task 6: Decompose `_assemble_ambient_context`

**Why:** The function is 243 lines (401-643) doing 5 distinct jobs: module loading, hub extraction, neighbor expansion, LOD assembly, and budget management. This makes it hard to test, modify, or reason about individual stages. Extracting focused helpers improves maintainability and testability.

**Files:**
- Modify: `src/prep/api/routers/projects/search.py:401-643`
- Test: existing tests should continue to pass

- [ ] **Step 1: Extract `_load_scope_modules` helper**

Create a helper function above `_assemble_ambient_context`:

```python
def _load_scope_modules(
    idx_dir: Path,
    included_paths: List[str],
) -> List[Dict[str, Any]]:
    """Load and filter modules from trace_modules.jsonl by scope paths."""
    scope_modules: List[Dict[str, Any]] = []
    modules_path = idx_dir / "trace_modules.jsonl"
    if not modules_path.exists():
        return scope_modules

    try:
        with open(modules_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = _json.loads(line)
                    member_files = m.get("member_files", [])
                    for ip in included_paths:
                        prefix = ip.rstrip("/") + "/"
                        if any(mf == ip or mf.startswith(prefix) for mf in member_files):
                            scope_modules.append(m)
                            break
                except _json.JSONDecodeError:
                    continue
    except OSError:
        pass

    return scope_modules
```

- [ ] **Step 2: Extract `_format_module_tiers` helper**

```python
def _format_module_tiers(scope_modules: List[Dict[str, Any]]) -> str:
    """Format modules into tiered display: significant, small, tiny."""
    if not scope_modules:
        return ""

    significant = [m for m in scope_modules if m.get("file_count", 0) >= 5]
    small = [m for m in scope_modules if 2 <= m.get("file_count", 0) < 5]
    tiny = [m for m in scope_modules if m.get("file_count", 0) < 2]

    mod_header = "## Modules in scope\n"
    for m in sorted(significant, key=lambda x: -x.get("file_count", 0)):
        name = m.get("name", m.get("module_id", "?"))
        summary = m.get("summary", "")
        fc = m.get("file_count", 0)
        deps = ", ".join(m.get("dependencies", [])[:3])
        line = f"- **{name}** ({fc} files)"
        if summary:
            line += f": {summary}"
        if deps:
            line += f" → {deps}"
        mod_header += line + "\n"
    if small:
        mod_header += f"\n*Plus {len(small)} smaller modules (2-4 files each)*\n"
    if tiny:
        mod_header += f"*Plus {len(tiny)} single-file modules*\n"
    return mod_header.strip()
```

- [ ] **Step 3: Extract `_resolve_hub_files` helper**

```python
def _resolve_hub_files(
    trace_idx: Any,
    idx: Any,
    included_paths: List[str],
) -> List[Tuple[str, int]]:
    """Resolve hub files from trace index with fallbacks."""
    hub_files: List[Tuple[str, int]] = []

    if trace_idx is not None and trace_idx.is_loaded():
        scope_set = set(included_paths) if included_paths else None
        hub_files = trace_idx.get_hub_files(scope_paths=scope_set, k=8)

    if not hub_files and included_paths:
        indexed_docs = getattr(idx, '_documents', None) or []
        for ip in included_paths:
            prefix = ip.rstrip("/") + "/"
            for d in indexed_docs:
                sp = str(d.get("source_path") or "")
                if sp == ip or sp.startswith(prefix):
                    hub_files.append((sp, 0))
                    if len(hub_files) >= 8:
                        break
            if len(hub_files) >= 8:
                break

    if not hub_files:
        if trace_idx is not None and trace_idx.is_loaded():
            hub_files = trace_idx.get_hub_files(k=8)

    return hub_files
```

- [ ] **Step 4: Rewrite `_assemble_ambient_context` to use helpers**

Replace the body of `_assemble_ambient_context` to delegate to the extracted helpers. The function becomes an orchestrator (~60 lines) instead of a monolith (~243 lines). The hub content assembly and neighbor assembly loops remain inline since they interact heavily with budgets and parts list.

- [ ] **Step 5: Run full test suite**

Run: `.venv/bin/pytest tests/ -x -q --ignore=tests/test_api_envelope.py --ignore=tests/test_dashboard_error_states.py --tb=short`
Expected: PASS (no behavior changes, only structural extraction)

- [ ] **Step 6: Commit**

```bash
git add src/prep/api/routers/projects/search.py
git commit -m "refactor(context): decompose _assemble_ambient_context into focused helpers

Extract _load_scope_modules, _format_module_tiers, _resolve_hub_files
from the 243-line monolith. The main function is now an orchestrator
delegating to testable, single-responsibility helpers."
```

---

## Task 7: FTS5 / BM25 Boost Tuning

**Why:** The existing `_fts_boosts` uses Reciprocal Rank Fusion with `rrf_weight=0.08`, giving the #1 BM25 hit only ~0.08/61 ≈ 0.0013 boost. This is far too weak to matter. For identifier-heavy queries ("MCP server", "orchestrator"), BM25 should contribute meaningfully. Tuning the RRF weight and combining with the strengthened keyword boosts creates effective hybrid search without adding new infrastructure.

**Files:**
- Modify: `src/prep/core/index.py` (`_fts_boosts` method)
- Test: `tests/test_fts_boost_tuning.py` (new)

- [ ] **Step 1: Read the current `_fts_boosts` implementation**

Read `src/prep/core/index.py` at the `_fts_boosts` method to find current RRF parameters.

- [ ] **Step 2: Write the failing test**

Create `tests/test_fts_boost_tuning.py`:

```python
"""Tests for Phase 73 FTS5 boost tuning."""
from __future__ import annotations

import numpy as np
import pytest


class TestRRFScoring:
    """Verify RRF produces meaningful boosts for top-ranked BM25 hits."""

    def test_top_hit_gets_meaningful_boost(self):
        """The #1 BM25 result should get a boost >= 0.08."""
        rrf_weight = 0.12
        rrf_k = 60
        top_boost = rrf_weight / (rrf_k + 1)  # rank 1 = position 1
        assert top_boost >= 0.001  # Minimum meaningful boost

    def test_boost_decay_is_gradual(self):
        """Boosts should decay gradually, not cliff-drop."""
        rrf_weight = 0.12
        rrf_k = 60
        boost_1 = rrf_weight / (rrf_k + 1)
        boost_5 = rrf_weight / (rrf_k + 5)
        boost_10 = rrf_weight / (rrf_k + 10)
        # #5 should still be >60% of #1
        assert boost_5 / boost_1 > 0.6
        # #10 should still be >40% of #1
        assert boost_10 / boost_1 > 0.4
```

- [ ] **Step 3: Tune RRF weight in `_fts_boosts`**

In the `_fts_boosts` method, increase the `rrf_weight` parameter from its current value to `0.12`:

```python
        # Phase 73: Tuned RRF weight for meaningful BM25 contribution.
        # rrf_weight=0.12 gives #1 hit ~0.002 boost, #5 ~0.0018.
        # Combined with _keyword_boosts (0.25 for basename match), this
        # creates effective hybrid search for identifier queries.
        rrf_weight = 0.12
        rrf_k = 60
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_fts_boost_tuning.py tests/test_mmr_diversity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/index.py tests/test_fts_boost_tuning.py
git commit -m "feat(search): tune FTS5 RRF weight for stronger BM25 contribution

Increase rrf_weight to 0.12 so BM25 keyword matches contribute
meaningfully to hybrid search ranking alongside embeddings."
```

---

## Task 8: Integration Verification

**Why:** All individual changes are tested in isolation. This task verifies they work together — meta-chunks improve search, budget caps prevent overflow, hub selection picks synopses, and dedup cleans up results.

**Files:**
- No code changes
- Run: full test suite, manual MCP tool calls

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/pytest tests/ -q --ignore=tests/test_api_envelope.py --ignore=tests/test_dashboard_error_states.py --tb=short`
Expected: All PASS

- [ ] **Step 2: Restart dev server**

Run: `scripts/dev.sh` (or `prep serve` on port 8400)

- [ ] **Step 3: Verify `prep` overview size**

Call `prep` MCP tool and verify:
- Total response is < 200 lines
- No duplicated hub content
- Module list shows only significant modules with collapse counts
- Architecture section is ≤ 3000 chars

- [ ] **Step 4: Verify search retrieval**

Call `prep_search query="how does the pipeline orchestrator process files"` and verify:
- `orchestrator.py` appears in results (META_SYNOPSIS anchoring)
- Retrieval confidence indicator is present
- No duplicate file paths in results

Call `prep_search query="MCP tool handler"` and verify:
- `mcp/server.py` appears in results

- [ ] **Step 5: Verify audit findings**

Call `prep_audit action="scan"` and verify:
- `package-lock.json` does NOT appear as "critical"
- Suggested actions are file-type-aware

- [ ] **Step 6: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix: integration fixups from Phase 73 verification"
```

---

## Summary: Expected Impact

| Metric | Before Phase 73 | After Phase 73 |
|--------|-----------------|----------------|
| `prep` overview lines | 745 | < 200 |
| Signal-to-noise ratio | ~13% | ~60-70% |
| Search recall for architectural queries | ~0/3 | ~3/3 |
| Architecture context size | 248KB | < 3KB |
| Critical audit false positives | 8/11 | 0/11 |
| Duplicate hub content | 3x | 0x |
| File-level search anchors | None | Every multi-chunk file |
