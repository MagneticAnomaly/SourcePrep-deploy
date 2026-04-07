# Phase 80: MemPalace-Inspired Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adapt three patterns from the MemPalace project to make CoDRAG a better product: module-scoped retrieval (L2 memory layer), temporal validity on concepts/observations, and structural compression for swarm communication. Also fix the `compression_level` bug discovered during research.

**Architecture:** Four independent tracks that can be implemented in any order. Track 0 is a bugfix. Tracks 1-3 each add a new capability by extending existing abstractions (`ObservationStore`, `ConceptStore`, `ContextCompressor`) without breaking current behavior. All changes are backward-compatible — existing databases auto-migrate via `ALTER TABLE ADD COLUMN`, and the `NoopCompressor` remains the default.

**Tech Stack:** Python 3.11+, SQLite (WAL mode), FTS5, pytest (asyncio_mode=auto), existing CoDRAG singleton stores.

**Research:** See `docs/Phase80_mempalace/01_MemPalace_Integration_Research_Strategy.md` and `docs/Phase80_mempalace/02_MemPalace_Integration_Findings.md` for full analysis of the MemPalace repo and integration mapping.

---

## File Map

| Track | File | Action | Responsibility |
|-------|------|--------|----------------|
| 0 | `src/codrag/mcp/server.py` | Modify (~L889) | Fix undefined `compression_level` variable |
| 1 | `src/codrag/services/observation_store.py` | Modify | Add `get_for_directory()` method |
| 1 | `src/codrag/services/concept_store.py` | Modify | Add `get_for_anchors_directory()` method |
| 1 | `src/codrag/mcp/server.py` | Modify | Wire L2 scoped retrieval into `tool_context()` |
| 1 | `src/codrag/mcp_tools.py` | Modify | Add `working_dir` param to `codrag` and `codrag_search` tools |
| 1 | `tests/test_observation_store_directory.py` | Create | Tests for directory-scoped observation retrieval |
| 1 | `tests/test_concept_store_directory.py` | Create | Tests for directory-scoped concept retrieval |
| 2 | `src/codrag/services/concept_store.py` | Modify | Add `valid_from`/`valid_to` columns, `as_of` queries |
| 2 | `src/codrag/services/observation_store.py` | Modify | Add `valid_from`/`valid_to` columns, `as_of` queries |
| 2 | `src/codrag/mcp_tools.py` | Modify | Add `as_of` param to `codrag_observe` and `codrag_concepts` |
| 2 | `src/codrag/mcp/server.py` | Modify | Pass `as_of` through to store queries |
| 2 | `tests/test_temporal_validity.py` | Create | Tests for temporal knowledge lifecycle |
| 3 | `src/codrag/core/compression/symbol_registry.py` | Create | Short-code registry built from trace graph |
| 3 | `src/codrag/core/compressor.py` | Modify | Add `StructuralCompressor` subclass |
| 3 | `tests/test_structural_compressor.py` | Create | Tests for structural compression |

---

## Task 0: Fix `compression_level` Bug

**Context:** `codrag_search` MCP tool is currently broken. In `src/codrag/mcp/server.py` at line ~889, the variable `compression_level` is referenced but never defined. The function signature has a `compression` parameter (valid values: `"none"`, `"lod"`), but a stale validation block references `compression_level` which doesn't exist, causing a `NameError` on every search call.

**Files:**
- Modify: `src/codrag/mcp/server.py:885-895`
- Test: manual — call `codrag_search` via MCP and verify it no longer errors

- [ ] **Step 1: Read the buggy code block**

Open `src/codrag/mcp/server.py` and find the `tool_search` method (starts ~line 854). Locate the validation block around lines 885-895. You'll see:

```python
# Around line 885-892:
if compression not in ("none", "lod"):
    raise InvalidParamsError("compression must be 'none' or 'lod'")

if compression_level not in ("light", "standard", "aggressive"):
    raise InvalidParamsError(
        "compression_level must be 'light', 'standard', or 'aggressive'"
    )
```

The `compression` validation is correct. The `compression_level` block references a variable that doesn't exist in the function signature and isn't extracted from any payload.

- [ ] **Step 2: Remove the dead validation block**

Delete the `compression_level` validation block (the `if compression_level not in ...` block). This was likely left over from a prior refactor where `compression_level` was a separate parameter. The `compression` parameter already covers the valid modes.

```python
# AFTER fix — only the valid compression check remains:
if compression not in ("none", "lod"):
    raise InvalidParamsError("compression must be 'none' or 'lod'")
```

- [ ] **Step 3: Verify the fix**

Start the CoDRAG daemon and call `codrag_search` via MCP with any query. Confirm it returns results instead of a `NameError`.

```bash
# Quick smoke test via the daemon API:
curl -s http://localhost:8400/projects/<project_id>/context \
  -H 'Content-Type: application/json' \
  -d '{"query": "observation store", "max_chars": 5000}' | python3 -m json.tool | head -20
```

- [ ] **Step 4: Commit**

```bash
git add src/codrag/mcp/server.py
git commit -m "fix(mcp): remove undefined compression_level variable from tool_search

Stale validation block referenced compression_level which was never
defined in the function signature, causing NameError on every
codrag_search call."
```

---

## Task 1: L2 Module-Scoped Retrieval

**Context:** CoDRAG has two context layers today: the atlas (always-loaded structural overview, analogous to MemPalace's L0+L1) and semantic search (L3). There's no middle layer for "give me the observations and concepts relevant to the directory I'm working in" — a metadata-filtered recall that's cheaper than embedding similarity. This task adds that L2 layer.

### Task 1a: Add `get_for_directory()` to ObservationStore

**Files:**
- Modify: `src/codrag/services/observation_store.py`
- Create: `tests/test_observation_store_directory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_observation_store_directory.py`:

```python
"""Tests for directory-scoped observation retrieval."""
import tempfile
from pathlib import Path

import pytest

from codrag.services.observation_store import ObservationStore


@pytest.fixture
def store(tmp_path: Path) -> ObservationStore:
    s = ObservationStore()
    s.init(tmp_path / "test.db")
    yield s
    s.close()


def test_get_for_directory_returns_matching_observations(store: ObservationStore) -> None:
    """Observations with file_path under the directory are returned."""
    store.save("proj-1", "Auth uses JWT", file_path="src/auth/login.py")
    store.save("proj-1", "Auth rate limiting", file_path="src/auth/middleware.py")
    store.save("proj-1", "DB migration note", file_path="src/db/migrate.py")

    results = store.get_for_directory("proj-1", "src/auth")
    assert len(results) == 2
    paths = {r.file_path for r in results}
    assert paths == {"src/auth/login.py", "src/auth/middleware.py"}


def test_get_for_directory_excludes_stale_when_requested(store: ObservationStore) -> None:
    """Stale observations are excluded when include_stale=False."""
    store.save("proj-1", "Old note", file_path="src/auth/old.py")
    store.mark_stale_batch("proj-1", ["src/auth/old.py"], "file deleted")
    store.save("proj-1", "Fresh note", file_path="src/auth/new.py")

    results = store.get_for_directory("proj-1", "src/auth", include_stale=False)
    assert len(results) == 1
    assert results[0].file_path == "src/auth/new.py"


def test_get_for_directory_empty_for_no_match(store: ObservationStore) -> None:
    """Returns empty list when no observations match the directory."""
    store.save("proj-1", "Unrelated", file_path="src/db/schema.py")

    results = store.get_for_directory("proj-1", "src/auth")
    assert results == []


def test_get_for_directory_excludes_null_file_paths(store: ObservationStore) -> None:
    """Observations without a file_path are never returned."""
    store.save("proj-1", "General note")  # no file_path

    results = store.get_for_directory("proj-1", "src")
    assert results == []


def test_get_for_directory_respects_limit(store: ObservationStore) -> None:
    """Limit parameter caps the number of results."""
    for i in range(10):
        store.save("proj-1", f"Note {i}", file_path=f"src/auth/file{i}.py")

    results = store.get_for_directory("proj-1", "src/auth", limit=3)
    assert len(results) == 3


def test_get_for_directory_trailing_slash_normalization(store: ObservationStore) -> None:
    """Trailing slash on directory prefix doesn't affect results."""
    store.save("proj-1", "Note", file_path="src/auth/login.py")

    results_no_slash = store.get_for_directory("proj-1", "src/auth")
    results_slash = store.get_for_directory("proj-1", "src/auth/")
    assert len(results_no_slash) == len(results_slash) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_observation_store_directory.py -v
```

Expected: `AttributeError: 'ObservationStore' object has no attribute 'get_for_directory'`

- [ ] **Step 3: Implement `get_for_directory()`**

Add this method to the `ObservationStore` class in `src/codrag/services/observation_store.py`, after the `get_for_file()` method (after line ~364):

```python
def get_for_directory(
    self,
    project_id: str,
    directory: str,
    include_stale: bool = True,
    limit: int = 50,
) -> List[Observation]:
    """Get observations linked to files under a directory prefix.

    This is the L2 (on-demand scoped) retrieval layer — cheaper than
    semantic search, returns observations relevant to the working area.
    """
    conn = self._require_conn()
    # Normalize: ensure prefix ends with / for clean LIKE matching
    prefix = directory.rstrip("/") + "/"
    sql = """SELECT * FROM observations
             WHERE project_id = ? AND file_path IS NOT NULL
             AND file_path LIKE ?"""
    params: list = [project_id, f"{prefix}%"]
    if not include_stale:
        sql += " AND stale = 0"
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with self._lock:
        rows = conn.execute(sql, params).fetchall()
    return [Observation.from_row(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_observation_store_directory.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/observation_store.py tests/test_observation_store_directory.py
git commit -m "feat(observations): add get_for_directory() for L2 scoped retrieval

Enables retrieving observations by directory prefix instead of exact
file path. This is the 'L2 on-demand' memory layer — cheaper than
semantic search for working-area context."
```

---

### Task 1b: Add `get_for_anchors_directory()` to ConceptStore

**Files:**
- Modify: `src/codrag/services/concept_store.py`
- Create: `tests/test_concept_store_directory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_concept_store_directory.py`:

```python
"""Tests for directory-scoped concept retrieval."""
from pathlib import Path

import pytest

from codrag.services.concept_store import ConceptStore


@pytest.fixture
def store(tmp_path: Path) -> ConceptStore:
    s = ConceptStore()
    s.init(tmp_path / "test.db")
    yield s
    s.close()


def test_get_for_anchors_directory_returns_matching_concepts(store: ConceptStore) -> None:
    """Concepts anchored to files under the directory are returned."""
    store.save("proj-1", "JWT Auth", "We use JWT for auth", anchors=["src/auth/login.py"])
    store.save("proj-1", "Rate Limiting", "Rate limits on auth", anchors=["src/auth/middleware.py"])
    store.save("proj-1", "DB Schema", "Postgres schema design", anchors=["src/db/schema.py"])

    results = store.get_for_anchors_directory("proj-1", "src/auth")
    assert len(results) == 2
    titles = {c.title for c in results}
    assert titles == {"JWT Auth", "Rate Limiting"}


def test_get_for_anchors_directory_matches_any_anchor(store: ConceptStore) -> None:
    """A concept with multiple anchors matches if ANY anchor is under the directory."""
    store.save(
        "proj-1", "Cross-cutting",
        "Spans auth and db",
        anchors=["src/auth/login.py", "src/db/schema.py"],
    )

    results = store.get_for_anchors_directory("proj-1", "src/auth")
    assert len(results) == 1
    assert results[0].title == "Cross-cutting"


def test_get_for_anchors_directory_empty_for_no_match(store: ConceptStore) -> None:
    """Returns empty list when no concepts are anchored under the directory."""
    store.save("proj-1", "Unrelated", "Not anchored to auth", anchors=["src/db/schema.py"])

    results = store.get_for_anchors_directory("proj-1", "src/auth")
    assert results == []


def test_get_for_anchors_directory_excludes_archived(store: ConceptStore) -> None:
    """Archived concepts are excluded by default."""
    cid = store.save("proj-1", "Old Auth", "Deprecated", anchors=["src/auth/old.py"])
    store.update(cid, status="archived")

    results = store.get_for_anchors_directory("proj-1", "src/auth")
    assert results == []


def test_get_for_anchors_directory_respects_limit(store: ConceptStore) -> None:
    """Limit parameter caps the number of results."""
    for i in range(10):
        store.save("proj-1", f"Concept {i}", f"Content {i}", anchors=[f"src/auth/f{i}.py"])

    results = store.get_for_anchors_directory("proj-1", "src/auth", limit=3)
    assert len(results) == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_concept_store_directory.py -v
```

Expected: `AttributeError: 'ConceptStore' object has no attribute 'get_for_anchors_directory'`

- [ ] **Step 3: Implement `get_for_anchors_directory()`**

Add this method to the `ConceptStore` class in `src/codrag/services/concept_store.py`, after the `search()` method (after line ~630):

```python
def get_for_anchors_directory(
    self,
    project_id: str,
    directory: str,
    include_stale: bool = True,
    include_archived: bool = False,
    limit: int = 20,
) -> List[Concept]:
    """Get concepts anchored to files under a directory prefix.

    Scans the JSON anchors array for each concept and returns those
    with at least one anchor matching the directory prefix. This is
    the L2 (on-demand scoped) retrieval layer for concepts.
    """
    conn = self._require_conn()
    prefix = directory.rstrip("/") + "/"

    # SQLite JSON: use LIKE on the anchors text column to find
    # concepts with at least one anchor under the directory.
    # This works because anchors are stored as JSON arrays of paths.
    sql = """SELECT * FROM concepts
             WHERE project_id = ? AND anchors LIKE ?"""
    params: list = [project_id, f"%{prefix}%"]

    if not include_stale:
        sql += " AND stale = 0"
    if not include_archived:
        sql += " AND status != 'archived'"

    sql += """ ORDER BY
        CASE status WHEN 'active' THEN 0 WHEN 'seed' THEN 1 ELSE 2 END,
        created_at DESC
        LIMIT ?"""
    params.append(limit)

    with self._lock:
        rows = conn.execute(sql, params).fetchall()

    # Post-filter: verify at least one anchor actually starts with prefix
    # (the LIKE on JSON text can false-match on content or other anchors)
    results = []
    for row in rows:
        concept = Concept.from_row(row)
        if any(a.startswith(prefix) or a.rstrip("/") + "/" == prefix
               for a in concept.anchors):
            results.append(concept)

    return results[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_concept_store_directory.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/concept_store.py tests/test_concept_store_directory.py
git commit -m "feat(concepts): add get_for_anchors_directory() for L2 scoped retrieval

Retrieves concepts by directory prefix of their anchor file paths.
Post-filters JSON anchor arrays to prevent false matches."
```

---

### Task 1c: Add `working_dir` parameter to MCP tools

**Files:**
- Modify: `src/codrag/mcp_tools.py`

- [ ] **Step 1: Add `working_dir` property to `codrag` tool schema**

In `src/codrag/mcp_tools.py`, find the `codrag` tool definition (tool #1, starts around line 28). Add `working_dir` to its `properties` dict, after the `role` property:

```python
"working_dir": {
    "type": "string",
    "description": (
        "Directory you are currently working in (e.g. 'src/codrag/services'). "
        "When set, CoDRAG includes L2 scoped context: observations and concepts "
        "anchored to files in this directory. Improves relevance without a search query."
    ),
},
```

- [ ] **Step 2: Add `working_dir` property to `codrag_search` tool schema**

Find the `codrag_search` tool definition (tool #2, starts around line 58). Add the same `working_dir` property to its `properties` dict, after the `role` property:

```python
"working_dir": {
    "type": "string",
    "description": (
        "Directory you are currently working in (e.g. 'src/codrag/services'). "
        "When set, CoDRAG includes L2 scoped context: observations and concepts "
        "anchored to files in this directory."
    ),
},
```

- [ ] **Step 3: Commit**

```bash
git add src/codrag/mcp_tools.py
git commit -m "feat(mcp): add working_dir parameter to codrag and codrag_search tools

Enables agents to pass their current working directory so CoDRAG can
include L2 module-scoped observations and concepts in responses."
```

---

### Task 1d: Wire L2 retrieval into MCP server context assembly

**Files:**
- Modify: `src/codrag/mcp/server.py`

- [ ] **Step 1: Read the `tool_context()` method**

Open `src/codrag/mcp/server.py` and read the `tool_context()` method (starts ~line 1000). Identify where the concept augmentation block is (around lines 1176-1200). This is where L2 context will be injected.

- [ ] **Step 2: Accept `working_dir` in `tool_context()` and `tool_search()`**

Add `working_dir: Optional[str] = None` to both method signatures:

In `tool_context()` (~line 1000):
```python
async def tool_context(
    self,
    max_chars: int = 0,
    role: Optional[str] = None,
    working_dir: Optional[str] = None,  # NEW
    project_override: Optional[str] = None,
) -> Dict[str, Any]:
```

In `tool_search()` (~line 854):
```python
async def tool_search(
    self,
    query: str,
    k: int = 5,
    max_chars: int = 12000,
    trace_expand: bool = True,
    compression: str = "none",
    exclude_paths: Optional[List[str]] = None,
    role: Optional[str] = None,
    working_dir: Optional[str] = None,  # NEW
    project_override: Optional[str] = None,
) -> Dict[str, Any]:
```

- [ ] **Step 3: Add L2 context assembly helper**

Add a private method to the `MCPServer` class that assembles L2 scoped context from observations and concepts:

```python
def _assemble_l2_context(
    self,
    project_id: str,
    working_dir: str,
    max_items: int = 5,
) -> str:
    """Assemble L2 module-scoped context for a working directory.

    Returns a markdown section with observations and concepts anchored
    to files under the working directory. Returns empty string if
    nothing is found.
    """
    from codrag.services.observation_store import observation_store
    from codrag.services.concept_store import concept_store

    sections: list[str] = []

    # L2 observations
    try:
        observations = observation_store.get_for_directory(
            project_id, working_dir, include_stale=False, limit=max_items,
        )
        if observations:
            obs_lines = []
            for obs in observations:
                prefix = f"[{obs.category}]" if obs.category != "note" else ""
                file_hint = f" ({obs.file_path})" if obs.file_path else ""
                obs_lines.append(f"- {prefix}{obs.content}{file_hint}")
            sections.append(
                f"**Observations for `{working_dir}/`:**\n" + "\n".join(obs_lines)
            )
    except Exception:
        pass  # Store not initialized — skip gracefully

    # L2 concepts
    try:
        concepts = concept_store.get_for_anchors_directory(
            project_id, working_dir, include_stale=False, limit=max_items,
        )
        if concepts:
            con_lines = []
            for c in concepts:
                preview = c.content[:120] + "..." if len(c.content) > 120 else c.content
                con_lines.append(f"- **{c.title}** ({c.category}): {preview}")
            sections.append(
                f"**Concepts for `{working_dir}/`:**\n" + "\n".join(con_lines)
            )
    except Exception:
        pass  # Store not initialized — skip gracefully

    if not sections:
        return ""

    return "\n\n## Working Area Context\n\n" + "\n\n".join(sections) + "\n"
```

- [ ] **Step 4: Inject L2 context into `tool_context()` response**

In `tool_context()`, after the concepts summary block (~line 1200), add:

```python
# L2: Module-scoped context
if working_dir:
    l2_section = self._assemble_l2_context(project_id, working_dir)
    if l2_section:
        result["context"] += l2_section
        result["total_chars"] = len(result["context"])
```

- [ ] **Step 5: Inject L2 context into `tool_search()` response**

In `tool_search()`, after the concept augmentation block (~line 991), add the same pattern:

```python
# L2: Module-scoped context
if working_dir:
    l2_section = self._assemble_l2_context(project_id, working_dir)
    if l2_section:
        result["context"] += l2_section
        result["total_chars"] = len(result["context"])
```

- [ ] **Step 6: Wire `working_dir` through the dispatch**

Find the `handle_tools_call()` dispatch method in `server.py`. Locate where `tool_context` and `tool_search` are dispatched. Ensure `working_dir` is extracted from the tool arguments and passed through:

```python
# In the codrag dispatch block:
working_dir = args.get("working_dir")
# ... pass to tool_context(working_dir=working_dir)

# In the codrag_search dispatch block:
working_dir = args.get("working_dir")
# ... pass to tool_search(working_dir=working_dir)
```

- [ ] **Step 7: Commit**

```bash
git add src/codrag/mcp/server.py
git commit -m "feat(mcp): wire L2 module-scoped context into tool_context and tool_search

When working_dir is provided, CoDRAG appends a 'Working Area Context'
section with observations and concepts anchored to that directory.
This fills the gap between always-loaded atlas (L0/L1) and full
semantic search (L3)."
```

---

## Task 2: Temporal Validity on Knowledge

**Context:** CoDRAG currently uses a binary `stale` flag + `stale_reason` on observations and concepts. When things are marked stale, they can be pruned/evicted destructively. The MemPalace temporal pattern (`valid_from`/`valid_to`) preserves history — old knowledge is end-dated, never deleted. This enables "what was true 3 months ago?" queries and prevents irreversible knowledge loss.

### Task 2a: Add temporal columns to ConceptStore

**Files:**
- Modify: `src/codrag/services/concept_store.py`
- Create: `tests/test_temporal_validity.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_temporal_validity.py`:

```python
"""Tests for temporal validity on concepts and observations."""
import time
from pathlib import Path

import pytest

from codrag.services.concept_store import ConceptStore


@pytest.fixture
def store(tmp_path: Path) -> ConceptStore:
    s = ConceptStore()
    s.init(tmp_path / "test.db")
    yield s
    s.close()


def test_new_concept_has_valid_from_set(store: ConceptStore) -> None:
    """Saving a concept sets valid_from to creation time."""
    before = time.time()
    cid = store.save("proj-1", "Auth Design", "JWT-based auth")
    after = time.time()

    concept = store.get(cid)
    assert concept is not None
    assert concept.valid_from is not None
    assert before <= concept.valid_from <= after
    assert concept.valid_to is None  # Currently valid


def test_mark_stale_sets_valid_to(store: ConceptStore) -> None:
    """Marking a concept stale sets valid_to instead of just stale=1."""
    cid = store.save("proj-1", "Auth Design", "JWT-based auth", anchors=["src/auth.py"])

    store.mark_stale_batch("proj-1", ["src/auth.py"], "file modified")

    concept = store.get(cid)
    assert concept is not None
    assert concept.stale is True
    assert concept.valid_to is not None
    assert concept.valid_to >= concept.valid_from


def test_list_concepts_as_of_past(store: ConceptStore) -> None:
    """as_of parameter returns concepts that were valid at a past point in time."""
    t1 = time.time()
    cid = store.save("proj-1", "Old Design", "Monolith", anchors=["src/app.py"])
    time.sleep(0.05)
    t2 = time.time()

    # Invalidate the concept
    store.mark_stale_batch("proj-1", ["src/app.py"], "refactored")
    time.sleep(0.05)
    t3 = time.time()

    # Save a new concept
    store.save("proj-1", "New Design", "Microservices", anchors=["src/app.py"])

    # Query at t2: should see "Old Design" (still valid), not "New Design" (not yet created)
    results = store.list_concepts("proj-1", as_of=t2)
    titles = {c.title for c in results}
    assert "Old Design" in titles
    assert "New Design" not in titles

    # Query at t3: should see "New Design" only ("Old Design" is expired)
    results = store.list_concepts("proj-1", as_of=t3)
    titles = {c.title for c in results}
    assert "New Design" in titles
    assert "Old Design" not in titles


def test_list_concepts_default_shows_only_current(store: ConceptStore) -> None:
    """Without as_of, list_concepts returns only currently valid concepts."""
    store.save("proj-1", "Current", "Still valid")
    cid_old = store.save("proj-1", "Expired", "Was valid", anchors=["src/old.py"])
    store.mark_stale_batch("proj-1", ["src/old.py"], "deleted")

    results = store.list_concepts("proj-1", include_stale=False)
    titles = {c.title for c in results}
    assert "Current" in titles
    assert "Expired" not in titles
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_temporal_validity.py -v
```

Expected: Failures on `valid_from` / `valid_to` attribute access.

- [ ] **Step 3: Add `valid_from` and `valid_to` to the `Concept` dataclass**

In `src/codrag/services/concept_store.py`, update the `Concept` dataclass (around line 71):

```python
@dataclass
class Concept:
    """A single codebase concept."""
    id: str
    project_id: str
    title: str
    content: str
    category: str = "technical"
    status: str = "seed"
    confidence: float = 0.0
    anchors: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    cluster_id: Optional[str] = None
    created_at: float = 0.0
    updated_at: Optional[float] = None
    stale: bool = False
    stale_reason: Optional[str] = None
    valid_from: Optional[float] = None   # NEW: epoch when concept became valid
    valid_to: Optional[float] = None     # NEW: epoch when concept was invalidated (None = current)
```

Update `from_row()` to read the new columns:

```python
@staticmethod
def from_row(row: sqlite3.Row) -> Concept:
    keys = row.keys()
    anchors_raw = row["anchors"]
    tags_raw = row["tags"]
    return Concept(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        content=row["content"],
        category=row["category"],
        status=row["status"],
        confidence=row["confidence"],
        anchors=json.loads(anchors_raw) if anchors_raw else [],
        tags=json.loads(tags_raw) if tags_raw else [],
        cluster_id=row["cluster_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        stale=bool(row["stale"]),
        stale_reason=row["stale_reason"],
        valid_from=row["valid_from"] if "valid_from" in keys else None,
        valid_to=row["valid_to"] if "valid_to" in keys else None,
    )
```

Update `to_dict()` to include the new fields:

```python
def to_dict(self) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        # ... existing fields ...
    }
    # ... existing optional fields ...
    if self.valid_from is not None:
        d["valid_from"] = self.valid_from
    if self.valid_to is not None:
        d["valid_to"] = self.valid_to
    return d
```

- [ ] **Step 4: Add temporal columns to schema migration**

In `_create_tables()`, after the existing table creation, add the column migration (same pattern as the observation store's Phase 73.5 migration):

```python
# Phase 80: Add temporal validity columns (safe to run repeatedly)
for col in ("valid_from", "valid_to"):
    try:
        self._conn.execute(
            f"ALTER TABLE concepts ADD COLUMN {col} REAL DEFAULT NULL"
        )
        self._conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

# Backfill: set valid_from = created_at for existing rows
self._conn.execute(
    "UPDATE concepts SET valid_from = created_at WHERE valid_from IS NULL"
)
self._conn.commit()
```

- [ ] **Step 5: Set `valid_from` on save**

In the `save()` method, when inserting a new concept, set `valid_from = now`:

Update the INSERT statement to include `valid_from`:

```python
conn.execute(
    """INSERT INTO concepts
       (id, project_id, title, content, category, status,
        confidence, anchors, tags, cluster_id, created_at, stale, valid_from)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
    (concept_id, project_id, title, content, category, status,
     confidence, anchors_json, tags_json, cluster_id, now, now),
)
```

When updating an existing concept (the dedup path), also refresh `valid_from`:

```python
# In the existing-concept update block:
conn.execute(
    """UPDATE concepts
       SET content = ?, category = ?, confidence = ?,
           anchors = ?, tags = ?, cluster_id = ?,
           updated_at = ?, stale = 0, stale_reason = NULL,
           valid_from = ?, valid_to = NULL
       WHERE id = ?""",
    (content, category, confidence, anchors_json,
     tags_json, cluster_id, now, now, existing["id"]),
)
```

- [ ] **Step 6: Set `valid_to` in `mark_stale_batch()`**

In `mark_stale_batch()`, update the SQL to also set `valid_to`:

```python
conn.execute(
    """UPDATE concepts
       SET stale = 1, stale_reason = ?, updated_at = ?, valid_to = ?
       WHERE id = ?""",
    (reason, now, now, row["id"]),
)
```

- [ ] **Step 7: Add `as_of` parameter to `list_concepts()`**

Update the `list_concepts()` signature and add temporal filtering:

```python
def list_concepts(
    self,
    project_id: str,
    status: Optional[str] = None,
    category: Optional[str] = None,
    include_stale: bool = True,
    include_archived: bool = False,
    as_of: Optional[float] = None,  # NEW: point-in-time query
) -> List[Concept]:
    """List concepts for a project with optional filters.

    Args:
        as_of: If set, return concepts that were valid at this epoch time.
               A concept is valid at time T if: valid_from <= T AND
               (valid_to IS NULL OR valid_to > T).
    """
    conn = self._require_conn()
    sql = "SELECT * FROM concepts WHERE project_id = ?"
    params: list = [project_id]

    if as_of is not None:
        sql += " AND (valid_from IS NULL OR valid_from <= ?)"
        sql += " AND (valid_to IS NULL OR valid_to > ?)"
        params.extend([as_of, as_of])

    if status:
        sql += " AND status = ?"
        params.append(status)
    elif not include_archived:
        sql += " AND status != 'archived'"

    if category:
        sql += " AND category = ?"
        params.append(category)

    if not include_stale and as_of is None:
        sql += " AND stale = 0"

    sql += " ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'seed' THEN 1 ELSE 2 END, created_at DESC"

    with self._lock:
        rows = conn.execute(sql, params).fetchall()
    return [Concept.from_row(r) for r in rows]
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_temporal_validity.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 9: Commit**

```bash
git add src/codrag/services/concept_store.py tests/test_temporal_validity.py
git commit -m "feat(concepts): add temporal validity with valid_from/valid_to columns

Concepts now track when they became valid and when they were
invalidated. mark_stale_batch sets valid_to instead of just stale=1.
list_concepts accepts as_of for point-in-time queries.
Existing rows are backfilled with valid_from = created_at."
```

---

### Task 2b: Add temporal columns to ObservationStore

**Files:**
- Modify: `src/codrag/services/observation_store.py`
- Modify: `tests/test_temporal_validity.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_temporal_validity.py`:

```python
from codrag.services.observation_store import ObservationStore


@pytest.fixture
def obs_store(tmp_path: Path) -> ObservationStore:
    s = ObservationStore()
    s.init(tmp_path / "test_obs.db")
    yield s
    s.close()


def test_observation_has_valid_from_set(obs_store: ObservationStore) -> None:
    """Saving an observation sets valid_from to creation time."""
    before = time.time()
    obs_id = obs_store.save("proj-1", "Auth uses JWT", file_path="src/auth.py")
    after = time.time()

    results = obs_store.get_for_file("proj-1", "src/auth.py")
    assert len(results) == 1
    assert results[0].valid_from is not None
    assert before <= results[0].valid_from <= after
    assert results[0].valid_to is None


def test_observation_mark_stale_sets_valid_to(obs_store: ObservationStore) -> None:
    """Marking observations stale sets valid_to."""
    obs_store.save("proj-1", "Note about auth", file_path="src/auth.py")

    obs_store.mark_stale_batch("proj-1", ["src/auth.py"], "file changed")

    results = obs_store.get_for_file("proj-1", "src/auth.py")
    assert len(results) == 1
    assert results[0].stale is True
    assert results[0].valid_to is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_temporal_validity.py -v -k "observation"
```

Expected: `AttributeError: 'Observation' object has no attribute 'valid_from'`

- [ ] **Step 3: Add `valid_from` and `valid_to` to the `Observation` dataclass**

In `src/codrag/services/observation_store.py`, update the `Observation` dataclass:

```python
@dataclass
class Observation:
    """A single agent observation."""
    id: str
    project_id: str
    content: str
    file_path: Optional[str] = None
    symbol_fqn: Optional[str] = None
    trace_node_id: Optional[str] = None
    category: str = "note"
    created_at: float = 0.0
    updated_at: Optional[float] = None
    stale: bool = False
    stale_reason: Optional[str] = None
    created_by: Optional[str] = None
    visibility: str = "shared"
    valid_from: Optional[float] = None   # NEW
    valid_to: Optional[float] = None     # NEW
```

Update `from_row()`:

```python
@staticmethod
def from_row(row: sqlite3.Row) -> Observation:
    keys = row.keys()
    return Observation(
        id=row["id"],
        project_id=row["project_id"],
        content=row["content"],
        file_path=row["file_path"],
        symbol_fqn=row["symbol_fqn"],
        trace_node_id=row["trace_node_id"],
        category=row["category"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        stale=bool(row["stale"]),
        stale_reason=row["stale_reason"],
        created_by=row["created_by"] if "created_by" in keys else None,
        visibility=row["visibility"] if "visibility" in keys else "shared",
        valid_from=row["valid_from"] if "valid_from" in keys else None,
        valid_to=row["valid_to"] if "valid_to" in keys else None,
    )
```

- [ ] **Step 4: Add schema migration, set `valid_from` on save, set `valid_to` on stale**

In `_create_tables()`, add the migration after the Phase 73.5 block:

```python
# Phase 80: Add temporal validity columns (safe to run repeatedly)
for col in ("valid_from", "valid_to"):
    try:
        self._conn.execute(
            f"ALTER TABLE observations ADD COLUMN {col} REAL DEFAULT NULL"
        )
        self._conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

# Backfill: set valid_from = created_at for existing rows
self._conn.execute(
    "UPDATE observations SET valid_from = created_at WHERE valid_from IS NULL"
)
self._conn.commit()
```

In `save()`, update the INSERT to include `valid_from = now`:

```python
conn.execute(
    """INSERT INTO observations
       (id, project_id, content, file_path, symbol_fqn,
        trace_node_id, category, created_at, stale,
        created_by, visibility, valid_from)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
    (obs_id, project_id, content, file_path, symbol_fqn,
     trace_node_id, category, now, created_by, visibility, now),
)
```

In `mark_stale_batch()`, update the SQL to also set `valid_to`:

```python
cur = conn.execute(
    """UPDATE observations
       SET stale = 1, stale_reason = ?, updated_at = ?, valid_to = ?
       WHERE project_id = ? AND file_path = ? AND stale = 0""",
    (reason, now, now, project_id, fp),
)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_temporal_validity.py -v
```

Expected: All 6 tests pass (4 concept + 2 observation).

- [ ] **Step 6: Commit**

```bash
git add src/codrag/services/observation_store.py tests/test_temporal_validity.py
git commit -m "feat(observations): add temporal validity with valid_from/valid_to columns

Mirrors the concept store temporal pattern. Observations now track
when they became valid and when they were invalidated. Existing rows
are backfilled with valid_from = created_at."
```

---

### Task 2c: Expose `as_of` in MCP tools

**Files:**
- Modify: `src/codrag/mcp_tools.py`
- Modify: `src/codrag/mcp/server.py`

- [ ] **Step 1: Add `as_of` parameter to `codrag_observe` tool schema**

In `src/codrag/mcp_tools.py`, find the `codrag_observe` tool (tool #5). Add to its properties:

```python
"as_of": {
    "type": "number",
    "description": (
        "(get) Unix epoch timestamp for point-in-time queries. "
        "Returns observations that were valid at this time. "
        "Omit for current observations only."
    ),
},
```

- [ ] **Step 2: Add `as_of` parameter to `codrag_concepts` tool schema**

Find the `codrag_concepts` tool (tool #6). Add to its properties:

```python
"as_of": {
    "type": "number",
    "description": (
        "(get) Unix epoch timestamp for point-in-time queries. "
        "Returns concepts that were valid at this time. "
        "Omit for current concepts only."
    ),
},
```

- [ ] **Step 3: Wire `as_of` through the MCP server handlers**

In `src/codrag/mcp/server.py`, find the handler methods for `codrag_observe` (action=get) and `codrag_concepts` (action=get). Extract `as_of` from the tool arguments and pass it to the store queries:

For concepts (in the `codrag_concepts` get handler):
```python
as_of = args.get("as_of")
# Pass to list_concepts or search
results = concept_store.list_concepts(project_id, ..., as_of=as_of)
```

For observations, add `as_of` support to `get_for_query()` and `get_recent()` if the `as_of` parameter is present. This may require adding an `as_of` parameter to those methods using the same `valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)` pattern.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/mcp_tools.py src/codrag/mcp/server.py
git commit -m "feat(mcp): expose as_of temporal queries on codrag_observe and codrag_concepts

Agents can now pass as_of (epoch timestamp) to retrieve knowledge
that was valid at a specific point in time."
```

---

## Task 3: Structural Compression for Swarm Communication

**Context:** The swarm orchestrator (`src/codrag/core/swarm_orchestrator.py`) passes `WorkItem` objects between coordinator and workers. The coordinator sees summaries (file paths joined by semicolons), and workers see full JSON context with `member_details` and `internal_edges`. File paths and fully-qualified names are highly repetitive across items. Adapting MemPalace's AAAK pattern — short deterministic codes for structural entities — can reduce token usage 30-50% in these payloads.

The `ContextCompressor` ABC in `src/codrag/core/compressor.py` already exists with a `NoopCompressor` as the only implementation. This task fills that extension point.

### Task 3a: Build the Symbol Registry

**Files:**
- Create: `src/codrag/core/compression/symbol_registry.py`
- Create: `tests/test_structural_compressor.py` (partial — registry tests)

- [ ] **Step 1: Write failing tests for the registry**

Create `tests/test_structural_compressor.py`:

```python
"""Tests for structural compression: symbol registry and compressor."""
import pytest

from codrag.core.compression.symbol_registry import SymbolRegistry


def test_registry_generates_short_codes() -> None:
    """Paths get deterministic 3-4 char codes."""
    reg = SymbolRegistry()
    reg.register_paths([
        "src/codrag/core/swarm_orchestrator.py",
        "src/codrag/services/observation_store.py",
        "src/codrag/mcp/server.py",
    ])

    code = reg.get_code("src/codrag/core/swarm_orchestrator.py")
    assert code is not None
    assert 2 <= len(code) <= 5
    assert code == code.upper()  # Codes are uppercase


def test_registry_codes_are_unique() -> None:
    """No two paths get the same code."""
    reg = SymbolRegistry()
    paths = [f"src/module{i}/file{j}.py" for i in range(10) for j in range(5)]
    reg.register_paths(paths)

    codes = [reg.get_code(p) for p in paths]
    assert len(set(codes)) == len(codes), "Duplicate codes generated"


def test_registry_roundtrips() -> None:
    """Can resolve a code back to its path."""
    reg = SymbolRegistry()
    reg.register_paths(["src/auth/login.py"])

    code = reg.get_code("src/auth/login.py")
    resolved = reg.resolve(code)
    assert resolved == "src/auth/login.py"


def test_registry_generates_legend() -> None:
    """Legend is a compact string mapping codes to paths."""
    reg = SymbolRegistry()
    reg.register_paths(["src/auth/login.py", "src/db/schema.py"])

    legend = reg.legend()
    assert "src/auth/login.py" in legend
    assert "src/db/schema.py" in legend
    # Legend should be compact
    assert len(legend) < 200


def test_registry_compress_text_replaces_paths() -> None:
    """Paths in text are replaced with their short codes."""
    reg = SymbolRegistry()
    reg.register_paths(["src/auth/login.py"])

    code = reg.get_code("src/auth/login.py")
    text = "The file src/auth/login.py handles authentication."
    compressed = reg.compress_text(text)
    assert code in compressed
    assert "src/auth/login.py" not in compressed
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_structural_compressor.py -v -k "registry"
```

Expected: `ModuleNotFoundError: No module named 'codrag.core.compression.symbol_registry'`

- [ ] **Step 3: Ensure `__init__.py` exists for the compression package**

Check if `src/codrag/core/compression/__init__.py` exists. If not, create it as an empty file:

```bash
ls src/codrag/core/compression/__init__.py 2>/dev/null || touch src/codrag/core/compression/__init__.py
```

- [ ] **Step 4: Implement the SymbolRegistry**

Create `src/codrag/core/compression/symbol_registry.py`:

```python
"""
Symbol Registry — deterministic short codes for file paths.

Inspired by MemPalace's AAAK dialect: replaces repetitive file paths
and FQNs with 3-5 character uppercase codes. No decoder needed — a
legend block is prepended to the output so any LLM can read it.

Codes are derived from the filename (not the full path) to be
human-guessable: src/codrag/core/swarm_orchestrator.py → SWO.
Collisions are resolved by appending digits.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional


def _stem_code(path: str, length: int = 3) -> str:
    """Derive a short code from a file path's stem.

    Takes the uppercase initials of underscore/camelCase segments.
    Falls back to first N chars of filename if segments are too short.
    """
    # Extract filename without extension
    name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]

    # Split on underscores and camelCase boundaries
    parts = re.split(r"[_\-]", name)
    if len(parts) >= length:
        code = "".join(p[0] for p in parts[:length] if p).upper()
        if len(code) >= 2:
            return code

    # Fallback: first N uppercase chars of the filename
    return name[:length].upper()


class SymbolRegistry:
    """Maps file paths to short uppercase codes and back."""

    def __init__(self) -> None:
        self._path_to_code: Dict[str, str] = {}
        self._code_to_path: Dict[str, str] = {}

    def register_paths(self, paths: List[str]) -> None:
        """Register a batch of file paths, generating unique codes."""
        for path in paths:
            if path in self._path_to_code:
                continue

            base_code = _stem_code(path)
            code = base_code

            # Resolve collisions by appending digits
            suffix = 2
            while code in self._code_to_path:
                code = f"{base_code}{suffix}"
                suffix += 1

            self._path_to_code[path] = code
            self._code_to_path[code] = path

    def get_code(self, path: str) -> Optional[str]:
        """Get the short code for a path, or None if not registered."""
        return self._path_to_code.get(path)

    def resolve(self, code: str) -> Optional[str]:
        """Resolve a short code back to its full path."""
        return self._code_to_path.get(code)

    def legend(self) -> str:
        """Return a compact legend string mapping codes to paths."""
        if not self._path_to_code:
            return ""
        lines = [f"{code}={path}" for path, code in
                 sorted(self._path_to_code.items(), key=lambda x: x[1])]
        return "LEGEND: " + " | ".join(lines)

    def compress_text(self, text: str) -> str:
        """Replace all registered paths in text with their short codes."""
        result = text
        # Sort by path length descending to avoid partial replacements
        for path in sorted(self._path_to_code.keys(), key=len, reverse=True):
            code = self._path_to_code[path]
            result = result.replace(path, code)
        return result

    def __len__(self) -> int:
        return len(self._path_to_code)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_structural_compressor.py -v -k "registry"
```

Expected: All 5 registry tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/core/compression/symbol_registry.py src/codrag/core/compression/__init__.py tests/test_structural_compressor.py
git commit -m "feat(compression): add SymbolRegistry for deterministic path short codes

Maps file paths to 3-5 char uppercase codes (e.g. swarm_orchestrator.py
-> SWO). Generates legend strings and compresses text by replacing paths
with codes. Collision-free via suffix digits."
```

---

### Task 3b: Implement StructuralCompressor

**Files:**
- Modify: `src/codrag/core/compressor.py`
- Modify: `tests/test_structural_compressor.py`

- [ ] **Step 1: Write failing tests for the compressor**

Append to `tests/test_structural_compressor.py`:

```python
from codrag.core.compressor import StructuralCompressor


def test_structural_compressor_compresses_paths() -> None:
    """StructuralCompressor replaces paths and prepends a legend."""
    comp = StructuralCompressor(
        paths=["src/auth/login.py", "src/db/schema.py"]
    )

    text = (
        "The file src/auth/login.py imports from src/db/schema.py. "
        "Changes to src/auth/login.py will affect authentication."
    )
    result = comp.compress(text)
    assert result.compression_ratio > 1.0
    assert result.output_chars < result.input_chars
    assert "LEGEND:" in result.compressed
    # Paths should be replaced
    assert "src/auth/login.py" not in result.compressed
    assert "src/db/schema.py" not in result.compressed


def test_structural_compressor_is_available() -> None:
    """Always available (no external service needed)."""
    comp = StructuralCompressor(paths=[])
    assert comp.is_available() is True


def test_structural_compressor_passthrough_when_no_paths() -> None:
    """With no registered paths, acts like NoopCompressor."""
    comp = StructuralCompressor(paths=[])
    result = comp.compress("Hello world")
    assert result.compressed == "Hello world"
    assert result.compression_ratio == 1.0


def test_structural_compressor_respects_budget() -> None:
    """When budget_chars is set, output is truncated."""
    comp = StructuralCompressor(
        paths=["src/auth/login.py"]
    )
    long_text = "src/auth/login.py " * 500
    result = comp.compress(long_text, budget_chars=200)
    assert result.output_chars <= 250  # Allow some slack for legend
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_structural_compressor.py -v -k "structural_compressor"
```

Expected: `ImportError: cannot import name 'StructuralCompressor' from 'codrag.core.compressor'`

- [ ] **Step 3: Implement `StructuralCompressor`**

Add to `src/codrag/core/compressor.py`, after the `NoopCompressor` class:

```python
import time as _time
from typing import List

from codrag.core.compression.symbol_registry import SymbolRegistry


class StructuralCompressor(ContextCompressor):
    """Compresses context by replacing file paths with short codes.

    Inspired by MemPalace's AAAK dialect. Builds a symbol registry from
    a list of file paths and replaces occurrences in text with 3-5 char
    uppercase codes. A legend is prepended so any LLM can read it.

    This compressor requires no external service — it's pure string
    replacement. Typical compression ratio: 1.3-2.0x for path-heavy
    context (swarm payloads, dependency lists, impact analysis).
    """

    def __init__(self, paths: List[str]) -> None:
        self._registry = SymbolRegistry()
        self._registry.register_paths(paths)

    def compress(
        self,
        text: str,
        *,
        query: str = "",
        budget_chars: int = 0,
        level: str = "standard",
        timeout_s: float = 30.0,
    ) -> CompressResult:
        t0 = _time.monotonic()
        input_chars = len(text)

        if len(self._registry) == 0:
            return CompressResult(
                compressed=text,
                input_chars=input_chars,
                output_chars=input_chars,
            )

        compressed = self._registry.compress_text(text)
        legend = self._registry.legend()

        if legend:
            compressed = legend + "\n\n" + compressed

        # Apply budget truncation if requested
        if budget_chars > 0 and len(compressed) > budget_chars:
            # Keep the legend intact, truncate the body
            legend_end = compressed.index("\n\n") + 2 if "\n\n" in compressed else 0
            available = budget_chars - legend_end
            if available > 0:
                compressed = compressed[:legend_end] + compressed[legend_end:legend_end + available]
            else:
                compressed = compressed[:budget_chars]

        output_chars = len(compressed)
        ratio = input_chars / output_chars if output_chars > 0 else 1.0
        elapsed = (_time.monotonic() - t0) * 1000

        return CompressResult(
            compressed=compressed,
            input_chars=input_chars,
            output_chars=output_chars,
            compression_ratio=round(ratio, 2),
            timing_ms=round(elapsed, 1),
        )

    def is_available(self) -> bool:
        return True

    def status(self) -> Dict[str, Any]:
        return {
            "available": True,
            "type": "structural",
            "registered_paths": len(self._registry),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_structural_compressor.py -v
```

Expected: All 9 tests pass (5 registry + 4 compressor).

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/compressor.py tests/test_structural_compressor.py
git commit -m "feat(compression): add StructuralCompressor using path short codes

Fills the ContextCompressor extension point with a concrete
implementation that replaces file paths with 3-5 char codes and
prepends a legend. No external service needed. Typical ratio 1.3-2.0x
for path-heavy payloads like swarm communication."
```

---

## Verification

After all tasks are complete, run the full test suite to ensure no regressions:

```bash
.venv/bin/pytest tests/test_observation_store_directory.py tests/test_concept_store_directory.py tests/test_temporal_validity.py tests/test_structural_compressor.py -v
```

Then smoke-test the MCP tools:

```bash
# Start daemon
codrag serve &

# Test codrag_search no longer crashes
# (use your MCP client or curl to the daemon API)

# Test L2 context by passing working_dir
# Test as_of queries on concepts/observations
```

---

## Summary

| Task | What | Files Changed | New Files | Tests |
|------|------|---------------|-----------|-------|
| 0 | Fix `compression_level` bug | server.py | - | Manual smoke test |
| 1a | `get_for_directory()` on observations | observation_store.py | test_observation_store_directory.py | 6 |
| 1b | `get_for_anchors_directory()` on concepts | concept_store.py | test_concept_store_directory.py | 5 |
| 1c | `working_dir` MCP param | mcp_tools.py | - | - |
| 1d | Wire L2 into context assembly | server.py | - | - |
| 2a | Temporal columns on concepts | concept_store.py | test_temporal_validity.py | 4 |
| 2b | Temporal columns on observations | observation_store.py | test_temporal_validity.py | 2 |
| 2c | `as_of` in MCP tools | mcp_tools.py, server.py | - | - |
| 3a | Symbol registry | symbol_registry.py | test_structural_compressor.py | 5 |
| 3b | StructuralCompressor | compressor.py | test_structural_compressor.py | 4 |
| **Total** | | **6 modified** | **5 created** | **26 tests** |
