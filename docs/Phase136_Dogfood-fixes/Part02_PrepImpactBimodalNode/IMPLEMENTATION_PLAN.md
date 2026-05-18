# Part 02 — Implementation plan: `prep_impact` bimodal-node twins

> **Status:** Ready to execute
> **Authored:** 2026-05-17
> **Estimated effort:** ~150 LOC production + ~120 LOC test, 1 session

## Root cause confirmed

`TraceIndex.get_impact_graph(node_id, …)` at
`src/prep/core/trace/index.py:405-493` performs BFS reverse traversal
starting from **one** `node_id`. The graph carries two nodes for a
package-imported file:

- `file:src/prep/core/augmenter.py` — the file node, target of
  `contains` edges and `import`-by-file-path edges
- `prep.core.augmenter` (kind `external_module`, empty `file_path`) —
  target of `from prep.core.augmenter import X` import edges (the
  Python package resolver's actual landing point)

When MCP's `tool_impact` calls
`get_impact_graph("file:src/prep/core/augmenter.py")`, the BFS only
walks in-edges that point at the file-node. Every importer using
`from prep.core.X import Y` is invisible — its edge points at the
external_module twin, which the BFS never visits.

**Evidence (post-rebuild 2026-05-17 probe):**

```
prep_impact augmenter.py dependents → 14 direct dependents
  2 Python: __init__.py (re-export), epistemic_enrichment.py
  12 markdown: doc references
```

The two Python dependents are exactly the ones that survive: the
re-export (`src/prep/core/__init__.py`) is a file-to-file edge, and
`epistemic_enrichment.py` happens to use a path-style import that
binds to the file node. All `from prep.core.augmenter import X`
callers (`index.py`, `orchestrator.py`, worker factory, tests) are
missing because their edges land on the `external_module` twin.

## The fix at three layers

### Layer 1 — Trace index: seed BFS from both twins

`src/prep/core/trace/index.py`:

```python
def _find_node_twins(self, node_id: str) -> list[str]:
    """Return node_ids for all twins of `node_id` in the trace graph.

    A file may have two representations: a `file:<path>` node carrying
    structural edges, and an `external_module` node (e.g. `prep.core.X`
    with empty file_path) carrying package-import edges.  This helper
    returns both ids when they exist, deduped.

    Bimodal-node bug history: pre-2026-05-17, `get_impact_graph` only
    seeded BFS from the requested node_id, so package-import
    dependents were silently invisible (P122-D2, MASTER_TODO 2026-05-13).
    """
    twins: list[str] = [node_id]
    if not self._loaded:
        self.load()
    node = self._nodes.get(node_id) or {}

    # Case 1: file:X.py → find external_module with matching dotted name
    if node_id.startswith("file:"):
        rel_path = node_id[len("file:"):]
        dotted = self._path_to_dotted_module(rel_path)
        if dotted:
            for nid, n in self._nodes.items():
                if (n.get("kind") == "external_module"
                        and n.get("name") == dotted
                        and nid != node_id):
                    twins.append(nid)

    # Case 2: external_module → find file: node with matching path
    elif node.get("kind") == "external_module":
        dotted = node.get("name", "")
        rel_path = self._dotted_to_path(dotted)
        if rel_path:
            twin_id = f"file:{rel_path}"
            if twin_id in self._nodes and twin_id != node_id:
                twins.append(twin_id)

    return twins

def _path_to_dotted_module(self, rel_path: str) -> Optional[str]:
    """`src/prep/core/augmenter.py` → `prep.core.augmenter`.

    Walks up from the file stem, dropping `src/` prefix and `.py`
    suffix, joining components with `.`.  Returns None for non-Python
    files.  Result is exact-match keyed against external_module names
    in the graph.
    """
    if not rel_path.endswith(".py"):
        return None
    stem = rel_path[:-3]               # drop .py
    if stem.startswith("src/"):
        stem = stem[4:]                 # drop src/
    parts = [p for p in stem.split("/") if p and p != "__init__"]
    return ".".join(parts) if parts else None

def _dotted_to_path(self, dotted: str) -> Optional[str]:
    """`prep.core.augmenter` → `src/prep/core/augmenter.py` (best effort).

    Probes both `src/<path>.py` and `<path>.py`, returning whichever
    exists as a file: node in the graph.  Returns None if neither
    twin is indexed.
    """
    if not dotted:
        return None
    rel = "/".join(dotted.split("."))
    for candidate in (f"src/{rel}.py", f"{rel}.py", f"src/{rel}/__init__.py"):
        if f"file:{candidate}" in self._nodes:
            return candidate
    return None
```

Then modify `get_impact_graph`:

```python
def get_impact_graph(self, node_id, max_hops=2, max_nodes=30):
    if not self._loaded:
        self.load()

    # Bimodal-node aggregation: seed BFS from all twins of node_id.
    seeds = self._find_node_twins(node_id)
    target_node = self._nodes.get(node_id) or {}

    visited: Set[str] = set(seeds)        # don't re-visit any twin
    queue: List[Tuple[str, int]] = [(s, 0) for s in seeds]
    dependents: List[Dict[str, Any]] = []
    # Dedupe by file_path so the same file via two twins doesn't double-count.
    seen_files: set[str] = set()

    while queue and len(dependents) < max_nodes:
        # ... existing BFS body, but skip when dep.path in seen_files
        # ... add dep.path to seen_files after appending
```

**Key dedup decision:** dependents are deduped by `file_path` once
inside the result list. Two twin-target edges from the same file get
counted once. Edges where both source and target are twins of each
other (which would be a fluke) collapse naturally.

### Layer 2 — MCP server: keep the existing dispatch

`src/prep/mcp/server.py` `tool_impact` doesn't need changes — it
already calls `get_impact_graph(node_id)` via the API. The fix at
Layer 1 makes the API return the right answer regardless of which
twin the caller asked about. The P122-D3 empty-parens header cosmetic
fix (`server.py:1745-1747`) has **already landed** as part of this
session — verify the in-flight edit before merging.

### Layer 3 — Trace API surface

`src/prep/api/routers/projects/trace.py` (if exists) — verify the
HTTP endpoint that wraps `get_impact_graph` passes through the
`dependents` list unchanged. No filtering at the API layer that
would re-drop external_module nodes.

Check: `grep -rn 'get_impact_graph' src/prep/`.

## Test plan

### `tests/test_prep_impact_bimodal.py` (new)

```python
"""Regression test for the bimodal-node aggregation bug.

A Python file imported via `from pkg.X import Y` produces an
external_module twin in the trace graph.  Reverse-impact must
aggregate edges from BOTH twins, not just the file: node.

History: pre-2026-05-17, prep_impact silently returned 0 dependents
for any module consumed via package-import syntax — biasing the
Custodian LLM verifier toward `safe_to_delete`.
"""

from pathlib import Path
import tempfile
import textwrap

import pytest

from prep.core.trace.index import TraceIndex
# (use whichever fixture helper builds a small index in-process —
# see tests/test_*_smoke.py for the canonical pattern)


def _build_fixture(tmp_path: Path) -> Path:
    """Three-file fixture:

        pkg/a.py            — has a function `foo()`
        pkg/__init__.py     — re-exports a
        consumer.py         — does `from pkg.a import foo`
    """
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("def foo():\n    return 1\n")
    (tmp_path / "pkg" / "__init__.py").write_text("from .a import foo\n")
    (tmp_path / "consumer.py").write_text(
        textwrap.dedent("""
            from pkg.a import foo

            def use_it():
                return foo()
        """).strip() + "\n"
    )
    return tmp_path


@pytest.fixture
def fixture_index(tmp_path):
    project_root = _build_fixture(tmp_path)
    # Build a real trace index against the fixture — do NOT mock
    # the TraceIndex itself (per feedback_test_full_import_chain).
    idx = ... # build via the canonical index helper
    return idx


def test_dependents_aggregates_bimodal_twins(fixture_index):
    """`from pkg.a import foo` must be visible as a dependent of pkg/a.py."""
    result = fixture_index.get_impact_graph("file:pkg/a.py", max_hops=2)
    paths = {d["path"] for d in result["dependents"]}
    assert "consumer.py" in paths, (
        f"consumer.py imports from pkg.a, must appear as dependent; "
        f"got {paths}"
    )


def test_dependents_no_double_counting(fixture_index):
    """A dependent reachable via both twins must appear exactly once."""
    result = fixture_index.get_impact_graph("file:pkg/a.py", max_hops=2)
    paths = [d["path"] for d in result["dependents"]]
    assert len(paths) == len(set(paths)), (
        f"Duplicate dependents detected: {paths}"
    )


def test_dependents_zero_for_unimported_file(fixture_index):
    """Control case: a file no one imports must return 0 dependents."""
    (fixture_index.project_root / "pkg" / "unused.py").write_text("# nothing\n")
    # ... rebuild index
    result = fixture_index.get_impact_graph("file:pkg/unused.py", max_hops=2)
    assert result["total_dependents"] == 0


def test_dependents_external_module_seed(fixture_index):
    """Seeding BFS from the external_module twin gives same result as file:."""
    # The trace graph has both `file:pkg/a.py` and `pkg.a` (external_module).
    via_file = fixture_index.get_impact_graph("file:pkg/a.py", max_hops=2)
    via_module = fixture_index.get_impact_graph("pkg.a", max_hops=2)
    paths_file = {d["path"] for d in via_file["dependents"]}
    paths_module = {d["path"] for d in via_module["dependents"]}
    assert paths_file == paths_module
```

### `tests/test_prep_impact_not_indexed.py` (new — covers P122-D3)

```python
def test_not_indexed_path_returns_explicit_indicator():
    """An unindexed file_path must say so explicitly, not silently 0."""
    # Call MCP tool_impact handler with a path that doesn't exist in the graph.
    result = ...
    assert "node not found" in result["_to_markdown"].lower()
    assert "Impact analysis for:  ()" not in result["_to_markdown"]
```

## Acceptance

1. **Pytest:** `test_prep_impact_bimodal.py` and
   `test_prep_impact_not_indexed.py` pass. The bimodal aggregation
   test fails today (before this Part lands) — this is the
   regression-asserting test.

2. **Live MCP probe (2026-05-17 baseline → post-fix):**

   ```
   prep_impact(file_path="src/prep/core/augmenter.py", direction="dependents")
   ```

   Pre-fix (current): 14 direct dependents (2 Python + 12 markdown).
   Post-fix (target): 14+ Python dependents including `index.py`,
   `orchestrator.py`, `epistemic_enrichment.py`, plus tests under
   `tests/`. Markdown reference count unchanged.

3. **Custodian downstream verification:**
   `CustodianEngine._get_impact()` (`src/prep/agents/custodian/engine.py:51`)
   re-run against the SourcePrep repo no longer reports
   `dependent_count=0` for modules with package-import callers. No
   code change needed in custodian — it benefits transparently from
   Layer 1.

4. **P122-D3 cosmetic fix verified in MCP output:** "Impact analysis
   for:  ()" with empty parens no longer appears in any response.
   (Already landed at `server.py:1745-1761` in this session.)

## Risks and mitigations

- **Path-to-dotted heuristics break for monorepos.** `src/<pkg>/X.py`
  → `<pkg>.X` is fine for SourcePrep; arbitrary monorepos might use
  different layouts. Mitigation: the dotted-name resolver checks
  multiple candidate paths (`src/<rel>.py`, `<rel>.py`,
  `src/<rel>/__init__.py`); if none match the graph, no twin is
  returned and the BFS behaves exactly as today (no regression).

- **Twin discovery cost.** `_find_node_twins` iterates all nodes
  looking for external_module matches. For 28k-node graphs this is
  ~28k dict-item iterations per call — fast. If profiling reveals
  this as a hot path on hub files, add a `_external_module_index:
  dict[str, str]` cache keyed by dotted name, built once at load.

- **Edge dedup correctness.** If the same `consumer.py` file imports
  `pkg.a` AND `pkg.a.b` (sub-module), both edges land on different
  external_module twins. The file-path dedup keeps consumer.py once
  in the result; the underlying graph still shows both edges
  correctly. This is the right tradeoff for the impact summary.

- **Backward compatibility.** Callers that already received correct
  results (control case `workers.py` returned 2 dependents pre-fix,
  truth was 2) must continue to receive 2 dependents post-fix. The
  `seen_files` set guards against double-counting.

## Out of scope for Part 02

- **Unifying twins at index build time.** Collapsing the two nodes
  into one would be cleaner data-model-wise but changes every
  consumer of `external_module`-typed nodes. Bigger refactor; not
  needed to close the dogfood finding.
- **Same fix for `tool_trace_neighbors` / `direction="all"`.** The
  fix at Layer 1 is in `get_impact_graph`. If `tool_trace_neighbors`
  uses a different path (`get_neighbors`), audit separately. Add
  follow-up if scope confirmed broader.
- **Custodian's standalone test coverage.** Custodian gets the fix
  for free via the MCP/API. A Custodian-specific regression test
  could be added in a future Phase 122 follow-up.

## Cross-refs

- `docs/MASTER_TODO.md` — 2026-05-13 Phase 122 dogfood entry
- `docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md` Gap #2
- `docs/Phase136_Dogfood-fixes/00_Status_2026-05-17.md` — Probe 2
- `prep_observe` bug id `bd79badde4d2`
- Already-landed in this session: P122-D3 fix at
  `src/prep/mcp/server.py:1744-1761`
