# Tier-Adaptive Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Prep's 14 context control mechanisms tier-aware so Tier 1 (50K), Tier 2 (30K), and Tier 2.5 (20K) clients each get optimally compressed context instead of one-size-fits-all.

**Architecture:** Add a `ContextTier` enum (1, 2, 3) that flows from MCP client detection → API request → LOD assignment, hub selection, neighbor fidelity, and module formatting. Each mechanism adapts its behavior based on the tier. No new dependencies. Pure parameter tuning on existing infrastructure.

**Tech Stack:** Python (FastAPI, Pydantic), existing LOD extractor, existing MCP server

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/prep/core/context_tier.py` | **Create** | `ContextTier` enum + tier detection from budget |
| `src/prep/core/lod_extractor.py` | **Modify** | Tier-aware `assign_lod()` + new LOD 2.5 level |
| `src/prep/api/routers/projects/models.py` | **Modify** | Add `context_tier` field to `ContextRequest` |
| `src/prep/api/routers/projects/search.py` | **Modify** | Tier-aware hub/neighbor/module assembly |
| `src/prep/mcp/server.py` | **Modify** | Compute tier + pass to backend |
| `tests/test_context_tier.py` | **Create** | Tests for tier detection + integration |
| `tests/test_lod_extractor.py` | **Modify** | Tests for tier-aware assign_lod + LOD 2.5 |
| `tests/test_compressor.py` | **Modify** | Update real-file tests for LOD 2.5 |

---

### Task 1: Create ContextTier Enum

**Files:**
- Create: `src/prep/core/context_tier.py`
- Create: `tests/test_context_tier.py`

- [ ] **Step 1: Write the test file**

```python
# tests/test_context_tier.py
"""Tests for ContextTier enum and tier detection."""
from prep.core.context_tier import ContextTier, tier_from_budget


class TestContextTier:
    def test_tier_values(self) -> None:
        assert ContextTier.TIER_1.value == 1
        assert ContextTier.TIER_2.value == 2
        assert ContextTier.TIER_2_5.value == 3

    def test_tier_1_from_high_budget(self) -> None:
        assert tier_from_budget(50_000) == ContextTier.TIER_1
        assert tier_from_budget(75_000) == ContextTier.TIER_1

    def test_tier_2_from_mid_budget(self) -> None:
        assert tier_from_budget(30_000) == ContextTier.TIER_2
        assert tier_from_budget(24_000) == ContextTier.TIER_2

    def test_tier_2_5_from_low_budget(self) -> None:
        assert tier_from_budget(20_000) == ContextTier.TIER_2_5
        assert tier_from_budget(15_000) == ContextTier.TIER_2_5
        assert tier_from_budget(6_000) == ContextTier.TIER_2_5

    def test_tier_properties(self) -> None:
        t1 = ContextTier.TIER_1
        assert t1.hub_count == 10
        assert t1.hub_lod == 0
        assert t1.neighbor_lod == 1
        assert t1.min_score == 0.15
        assert t1.hub_budget_pct == 0.55
        assert t1.neighbor_budget_pct == 0.25
        assert t1.trace_max_chars == 6000

        t2 = ContextTier.TIER_2
        assert t2.hub_count == 6
        assert t2.hub_lod == 0
        assert t2.neighbor_lod == 2
        assert t2.min_score == 0.20
        assert t2.trace_max_chars == 4000

        t25 = ContextTier.TIER_2_5
        assert t25.hub_count == 4
        assert t25.hub_lod == 2
        assert t25.neighbor_lod == 4
        assert t25.min_score == 0.25
        assert t25.trace_max_chars == 2000

    def test_module_display_tiers(self) -> None:
        t1 = ContextTier.TIER_1
        assert t1.module_min_files_significant == 5
        assert t1.module_show_small is True
        assert t1.module_show_tiny is True

        t25 = ContextTier.TIER_2_5
        assert t25.module_min_files_significant == 5
        assert t25.module_show_small is False
        assert t25.module_show_tiny is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_context_tier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prep.core.context_tier'`

- [ ] **Step 3: Implement ContextTier**

```python
# src/prep/core/context_tier.py
"""Context tier definitions for adaptive compression.

Phase 73.3b: Maps MCP client budgets to tier-specific parameters
that control LOD thresholds, hub selection, neighbor fidelity,
and module display across 3 client tiers.

Research basis:
  - Context Rot (Chroma 2025): less curated context > more noisy context
  - Lost in the Middle (Liu 2023): position in window matters
  - LongCodeZip (Shi 2025): structural compression validated for code
"""
from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class _TierParams(NamedTuple):
    """Parameters for a context tier."""
    # Hub files
    hub_count: int
    hub_lod: int             # LOD level for hub file content
    hub_budget_pct: float    # fraction of remaining budget for hubs
    # Neighbors
    neighbor_lod: int        # LOD level for neighbor files
    neighbor_budget_pct: float
    # Search
    min_score: float         # minimum relevance score to include
    trace_max_chars: int     # budget for trace expansion
    # LOD score thresholds (score → LOD level)
    lod_full: float          # score ≥ this → LOD 0 (full source)
    lod_sig: float           # score ≥ this → LOD 2 (signatures)
    lod_names: float         # score ≥ this → LOD 4 (names)
    # Module display
    module_min_files_significant: int
    module_show_small: bool  # show 2-4 file modules
    module_show_tiny: bool   # show <2 file modules


# Tier 1: Claude Code, Gemini CLI (50K budget, 1M windows)
_T1 = _TierParams(
    hub_count=10, hub_lod=0, hub_budget_pct=0.55,
    neighbor_lod=1, neighbor_budget_pct=0.25,
    min_score=0.15, trace_max_chars=6000,
    lod_full=0.40, lod_sig=0.25, lod_names=0.15,
    module_min_files_significant=5,
    module_show_small=True, module_show_tiny=True,
)

# Tier 2: Cursor, Windsurf, Copilot, Qwen (24-30K budget, 200-250K windows)
_T2 = _TierParams(
    hub_count=6, hub_lod=0, hub_budget_pct=0.50,
    neighbor_lod=2, neighbor_budget_pct=0.25,
    min_score=0.20, trace_max_chars=4000,
    lod_full=0.50, lod_sig=0.35, lod_names=0.20,
    module_min_files_significant=5,
    module_show_small=True, module_show_tiny=False,
)

# Tier 2.5: Cline, Roo, Continue / local models (20K budget, 250K+ windows)
_T2_5 = _TierParams(
    hub_count=4, hub_lod=2, hub_budget_pct=0.45,
    neighbor_lod=4, neighbor_budget_pct=0.20,
    min_score=0.25, trace_max_chars=2000,
    lod_full=0.60, lod_sig=0.40, lod_names=0.25,
    module_min_files_significant=5,
    module_show_small=False, module_show_tiny=False,
)


class ContextTier(Enum):
    """Client context tier with associated parameters.

    Access parameters as properties: tier.hub_count, tier.min_score, etc.
    """
    TIER_1 = 1
    TIER_2 = 2
    TIER_2_5 = 3

    @property
    def _params(self) -> _TierParams:
        return {
            ContextTier.TIER_1: _T1,
            ContextTier.TIER_2: _T2,
            ContextTier.TIER_2_5: _T2_5,
        }[self]

    # Hub properties
    @property
    def hub_count(self) -> int:
        return self._params.hub_count

    @property
    def hub_lod(self) -> int:
        return self._params.hub_lod

    @property
    def hub_budget_pct(self) -> float:
        return self._params.hub_budget_pct

    # Neighbor properties
    @property
    def neighbor_lod(self) -> int:
        return self._params.neighbor_lod

    @property
    def neighbor_budget_pct(self) -> float:
        return self._params.neighbor_budget_pct

    # Search properties
    @property
    def min_score(self) -> float:
        return self._params.min_score

    @property
    def trace_max_chars(self) -> int:
        return self._params.trace_max_chars

    # LOD threshold properties
    @property
    def lod_full(self) -> float:
        return self._params.lod_full

    @property
    def lod_sig(self) -> float:
        return self._params.lod_sig

    @property
    def lod_names(self) -> float:
        return self._params.lod_names

    # Module display properties
    @property
    def module_min_files_significant(self) -> int:
        return self._params.module_min_files_significant

    @property
    def module_show_small(self) -> bool:
        return self._params.module_show_small

    @property
    def module_show_tiny(self) -> bool:
        return self._params.module_show_tiny


# Budget thresholds for tier detection
_TIER_1_MIN_BUDGET = 40_000
_TIER_2_MIN_BUDGET = 22_000


def tier_from_budget(max_chars: int) -> ContextTier:
    """Detect context tier from the max_chars budget.

    Thresholds:
      ≥ 40K → Tier 1 (Claude/Gemini, 1M windows)
      22K-39K → Tier 2 (IDE integrations, 200-250K windows)
      < 22K → Tier 2.5 (local models, 250K+ but constrained)
    """
    if max_chars >= _TIER_1_MIN_BUDGET:
        return ContextTier.TIER_1
    if max_chars >= _TIER_2_MIN_BUDGET:
        return ContextTier.TIER_2
    return ContextTier.TIER_2_5
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_context_tier.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/context_tier.py tests/test_context_tier.py
git commit -m "feat(context): add ContextTier enum with per-tier compression parameters"
```

---

### Task 2: Tier-Aware assign_lod()

**Files:**
- Modify: `src/prep/core/lod_extractor.py:366-384`
- Modify: `tests/test_lod_extractor.py` (TestAssignLOD class)

- [ ] **Step 1: Add tier-aware tests to test_lod_extractor.py**

Add these tests to the existing `TestAssignLOD` class:

```python
class TestAssignLODTierAware:
    """Tier-aware LOD assignment (Phase 73.3b)."""

    def test_tier1_more_generous(self) -> None:
        """Tier 1 gives LOD 0 at lower scores (0.40 vs 0.50)."""
        from prep.core.context_tier import ContextTier
        # Score 0.45: Tier 1 → LOD 0, Tier 2 → LOD 2
        assert assign_lod(0.45, tier=ContextTier.TIER_1) == 0
        assert assign_lod(0.45, tier=ContextTier.TIER_2) == 2

    def test_tier2_5_more_aggressive(self) -> None:
        """Tier 2.5 requires higher scores for LOD 0."""
        from prep.core.context_tier import ContextTier
        # Score 0.55: Tier 2 → LOD 0, Tier 2.5 → LOD 2
        assert assign_lod(0.55, tier=ContextTier.TIER_2) == 0
        assert assign_lod(0.55, tier=ContextTier.TIER_2_5) == 2

    def test_tier1_boundaries(self) -> None:
        from prep.core.context_tier import ContextTier
        t = ContextTier.TIER_1
        assert assign_lod(0.40, tier=t) == 0
        assert assign_lod(0.39, tier=t) == 2
        assert assign_lod(0.25, tier=t) == 2
        assert assign_lod(0.24, tier=t) == 4
        assert assign_lod(0.15, tier=t) == 4
        assert assign_lod(0.14, tier=t) == 5

    def test_tier2_5_boundaries(self) -> None:
        from prep.core.context_tier import ContextTier
        t = ContextTier.TIER_2_5
        assert assign_lod(0.60, tier=t) == 0
        assert assign_lod(0.59, tier=t) == 2
        assert assign_lod(0.40, tier=t) == 2
        assert assign_lod(0.39, tier=t) == 4
        assert assign_lod(0.25, tier=t) == 4
        assert assign_lod(0.24, tier=t) == 5

    def test_no_tier_uses_tier2_defaults(self) -> None:
        """Backward compatibility: no tier arg = Tier 2 thresholds."""
        assert assign_lod(0.50) == 0
        assert assign_lod(0.49) == 2
        assert assign_lod(0.35) == 2
        assert assign_lod(0.34) == 4

    def test_trace_expanded_ignores_tier(self) -> None:
        from prep.core.context_tier import ContextTier
        assert assign_lod(0.80, is_trace_expanded=True, tier=ContextTier.TIER_1) == 4
        assert assign_lod(0.80, is_trace_expanded=True, tier=ContextTier.TIER_2_5) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_lod_extractor.py::TestAssignLODTierAware -v`
Expected: FAIL — `TypeError: assign_lod() got an unexpected keyword argument 'tier'`

- [ ] **Step 3: Update assign_lod() in lod_extractor.py**

Replace the module-level `assign_lod` function at line 366-384:

```python
def assign_lod(
    score: float,
    *,
    is_trace_expanded: bool = False,
    tier: Optional["ContextTier"] = None,
) -> int:
    """Map a search score to an LOD level.

    Phase 73.3b: Tier-aware thresholds — Tier 1 (generous) gives full
    source at lower scores, Tier 2.5 (aggressive) requires higher scores.
    When tier is None, uses Tier 2 defaults for backward compatibility.

    Research basis:
      - Context Rot (Chroma 2025): less context > more noise
      - LongCodeZip (Shi 2025): structural extraction validated for code
    """
    if is_trace_expanded:
        return 4

    # Get tier-specific thresholds (default to Tier 2 for backward compat)
    if tier is not None:
        lod_full = tier.lod_full
        lod_sig = tier.lod_sig
        lod_names = tier.lod_names
    else:
        # Tier 2 defaults (unchanged from original thresholds)
        lod_full = 0.50
        lod_sig = 0.35
        lod_names = 0.20

    if score >= lod_full:
        return 0
    if score >= lod_sig:
        return 2
    if score >= lod_names:
        return 4
    return 5
```

Also add the import at the top of the file (after existing imports):

```python
from typing import Any, Dict, List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from prep.core.context_tier import ContextTier
```

And update the `LODExtractor.assign_lod` static method (line 515-533) to match:

```python
    @staticmethod
    def assign_lod(
        score: float,
        *,
        is_trace_expanded: bool = False,
        tier: Optional["ContextTier"] = None,
    ) -> int:
        """Map a search score to an LOD level. Delegates to module-level assign_lod."""
        return assign_lod(score, is_trace_expanded=is_trace_expanded, tier=tier)
```

- [ ] **Step 4: Run all LOD tests to verify nothing broke**

Run: `.venv/bin/pytest tests/test_lod_extractor.py -v`
Expected: All PASS (original tests use no tier arg → Tier 2 defaults → same thresholds)

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/lod_extractor.py tests/test_lod_extractor.py
git commit -m "feat(lod): tier-aware assign_lod with per-tier score thresholds"
```

---

### Task 3: Add context_tier to ContextRequest

**Files:**
- Modify: `src/prep/api/routers/projects/models.py:44-62`

- [ ] **Step 1: Add the field to ContextRequest**

Add after the existing `compression_timeout_s` field (line 60):

```python
    context_tier: Optional[int] = None  # Phase 73.3b: 1=Tier1, 2=Tier2, 3=Tier2.5. None=auto from max_chars.
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `.venv/bin/pytest tests/ -k "context" --co -q 2>&1 | head -20`
Expected: No import errors

- [ ] **Step 3: Commit**

```bash
git add src/prep/api/routers/projects/models.py
git commit -m "feat(api): add context_tier field to ContextRequest model"
```

---

### Task 4: Tier-Aware Hub Selection + LOD

**Files:**
- Modify: `src/prep/api/routers/projects/search.py:459-484` (`_resolve_hub_files`)
- Modify: `src/prep/api/routers/projects/search.py:487-577` (`_assemble_ambient_context`)

- [ ] **Step 1: Write integration test**

Add to `tests/test_compressor.py`:

```python
class TestTierAwareAmbient:
    """Verify tier parameters are respected in ambient context assembly."""

    def test_tier_from_budget_import(self) -> None:
        from prep.core.context_tier import ContextTier, tier_from_budget
        assert tier_from_budget(50_000) == ContextTier.TIER_1
        assert tier_from_budget(30_000) == ContextTier.TIER_2
        assert tier_from_budget(20_000) == ContextTier.TIER_2_5

    def test_tier_hub_counts_are_ordered(self) -> None:
        from prep.core.context_tier import ContextTier
        assert ContextTier.TIER_1.hub_count > ContextTier.TIER_2.hub_count
        assert ContextTier.TIER_2.hub_count > ContextTier.TIER_2_5.hub_count

    def test_tier_neighbor_lods_are_ordered(self) -> None:
        from prep.core.context_tier import ContextTier
        # Higher tier number = more aggressive compression = higher LOD number
        assert ContextTier.TIER_2_5.neighbor_lod > ContextTier.TIER_2.neighbor_lod
        assert ContextTier.TIER_2.neighbor_lod > ContextTier.TIER_1.neighbor_lod
```

- [ ] **Step 2: Run tests to verify they pass** (these are just property checks)

Run: `.venv/bin/pytest tests/test_compressor.py::TestTierAwareAmbient -v`

- [ ] **Step 3: Update _resolve_hub_files to accept hub_count**

In `search.py`, modify `_resolve_hub_files` (line 459) to accept a `hub_count` parameter:

```python
def _resolve_hub_files(
    trace_idx: Any,
    idx: Any,
    included_paths: List[str],
    hub_count: int = 8,
) -> List[Tuple[str, int]]:
    """Resolve hub files from trace index with fallbacks."""
    hub_files: List[Tuple[str, int]] = []
    if trace_idx is not None and trace_idx.is_loaded():
        scope_set = set(included_paths) if included_paths else None
        hub_files = trace_idx.get_hub_files(scope_paths=scope_set, k=hub_count)
    if not hub_files and included_paths:
        indexed_docs = getattr(idx, '_documents', None) or []
        for ip in included_paths:
            prefix = ip.rstrip("/") + "/"
            for d in indexed_docs:
                sp = str(d.get("source_path") or "")
                if sp == ip or sp.startswith(prefix):
                    hub_files.append((sp, 0))
                    if len(hub_files) >= hub_count:
                        break
            if len(hub_files) >= hub_count:
                break
    if not hub_files:
        if trace_idx is not None and trace_idx.is_loaded():
            hub_files = trace_idx.get_hub_files(k=hub_count)
    return hub_files
```

- [ ] **Step 4: Update _assemble_ambient_context to use tier**

Modify the function signature at line 487 to accept `context_tier`:

```python
def _assemble_ambient_context(
    proj,
    project_id: str,
    idx,
    trace_idx,
    included_paths: List[str],
    max_chars: int = 6000,
    context_tier: Optional[int] = None,
) -> Dict[str, Any]:
```

Add tier detection at the start of the function (after `idx_dir = ...`):

```python
    from prep.core.context_tier import ContextTier, tier_from_budget
    tier = (
        ContextTier(context_tier) if context_tier is not None
        else tier_from_budget(max_chars)
    )
```

Replace the hub file resolution call (line 516):

```python
    hub_files = _resolve_hub_files(trace_idx, idx, included_paths, hub_count=tier.hub_count)
```

Replace the budget split (lines 544-546):

```python
    chars_budget = max_chars - total_chars
    hub_budget = int(chars_budget * tier.hub_budget_pct)
    neighbor_budget = int(chars_budget * tier.neighbor_budget_pct)
```

- [ ] **Step 5: Update hub content LOD**

In the hub content assembly loop (starting ~line 548), when `tier.hub_lod > 0`, use LOD extraction instead of raw content. Replace the block from `hub_chars = 0` through the hub loop ending ~line 586:

```python
    hub_chars = 0
    seen_hub_paths: set = set()
    hub_lod_extractor = None
    if tier.hub_lod > 0:
        try:
            from prep.core.lod_extractor import LODExtractor
            hub_lod_extractor = LODExtractor(index_dir=idx_dir)
        except Exception:
            pass

    repo_root_path = Path(proj.path) if proj.path else None

    for fp, deg in hub_files:
        if hub_chars >= hub_budget:
            break
        if fp in seen_hub_paths:
            continue
        seen_hub_paths.add(fp)

        # Tier-aware hub LOD: Tier 2.5 uses LOD 2 (signatures), others use LOD 0
        content = None
        if tier.hub_lod > 0 and hub_lod_extractor is not None and repo_root_path is not None:
            try:
                trace_nodes_for_hub = []
                if trace_idx is not None and trace_idx.is_loaded():
                    for nid_key in list(getattr(trace_idx, '_nodes', {}).keys()):
                        n = trace_idx.get_node(nid_key)
                        if n and n.get("file_path") == fp:
                            trace_nodes_for_hub.append(n)
                lod_result = hub_lod_extractor.extract(
                    fp, lod=tier.hub_lod, trace_nodes=trace_nodes_for_hub,
                    repo_root=repo_root_path,
                )
                if lod_result and lod_result.content and not lod_result.error:
                    content = lod_result.content
            except Exception:
                pass

        if content is None:
            # Fallback to document chunks (original behavior)
            file_docs = doc_by_path.get(fp, [])
            if not file_docs:
                continue
            best_doc = None
            for d in file_docs:
                if d.get("section") == "META_SYNOPSIS":
                    best_doc = d
                    break
            if best_doc is None:
                by_span = sorted(file_docs, key=lambda d: (d.get("span") or {}).get("start_line", 9999))
                best_doc = by_span[0]
            content = str(best_doc.get("content") or "")

        if hub_chars + len(content) > hub_budget and hub_chars > 0:
            continue
        section = ""
        header = f"[hub | in-degree:{deg} | @{fp}"
        if tier.hub_lod > 0:
            header += f" | lod={tier.hub_lod}"
        header += "]"
        block = f"{header}\n{content}"
        parts.append(block)
        chunks.append({
            "source_path": fp,
            "section": section,
            "score": 1.0,
            "truncated": False,
            "ambient_role": "hub",
        })
        hub_chars += len(block)
        total_chars += len(block)
```

- [ ] **Step 6: Update neighbor LOD to use tier**

In the neighbor assembly loop (~line 589-658), replace the hardcoded `lod=2` with `tier.neighbor_lod`. Change line 624:

```python
                lod_result = lod_extractor.extract(nfp, lod=tier.neighbor_lod, trace_nodes=trace_nodes, repo_root=repo_root)
```

- [ ] **Step 7: Run full test suite**

Run: `.venv/bin/pytest tests/test_compressor.py tests/test_context_tier.py tests/test_lod_extractor.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/prep/api/routers/projects/search.py tests/test_compressor.py
git commit -m "feat(context): tier-aware hub count, hub LOD, neighbor LOD, and budget split"
```

---

### Task 5: Tier-Aware Module Display

**Files:**
- Modify: `src/prep/api/routers/projects/search.py:432-456` (`_format_module_tiers`)

- [ ] **Step 1: Update _format_module_tiers to accept tier**

```python
def _format_module_tiers(
    scope_modules: List[Dict[str, Any]],
    context_tier: Optional["ContextTier"] = None,
) -> str:
    """Format modules into tiered display: significant, small, tiny.

    Phase 73.3b: Tier 2.5 shows only significant modules.
    Tier 2 shows significant + small. Tier 1 shows all.
    """
    from prep.core.context_tier import ContextTier, tier_from_budget
    tier = context_tier or ContextTier.TIER_2

    if not scope_modules:
        return ""
    significant = [m for m in scope_modules if m.get("file_count", 0) >= tier.module_min_files_significant]
    small = [m for m in scope_modules if 2 <= m.get("file_count", 0) < tier.module_min_files_significant]
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
            line += f" \u2192 {deps}"
        mod_header += line + "\n"

    if tier.module_show_small and small:
        mod_header += f"\n*Plus {len(small)} smaller modules (2-{tier.module_min_files_significant - 1} files each)*\n"

    if tier.module_show_tiny and tiny:
        mod_header += f"*Plus {len(tiny)} single-file modules*\n"
    elif not tier.module_show_small and (small or tiny):
        omitted = len(small) + len(tiny)
        mod_header += f"\n*Plus {omitted} smaller modules*\n"

    return mod_header
```

- [ ] **Step 2: Update the call site in _assemble_ambient_context**

Replace the call at ~line 510:

```python
    mod_text = _format_module_tiers(scope_modules, context_tier=tier)
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_context_tier.py tests/test_compressor.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/prep/api/routers/projects/search.py
git commit -m "feat(context): tier-aware module display — T2.5 shows significant only"
```

---

### Task 6: Wire Tier Through MCP Server

**Files:**
- Modify: `src/prep/mcp/server.py:165-189` (`_get_context_budget`)
- Modify: `src/prep/mcp/server.py:902-967` (`tool_context`)

- [ ] **Step 1: Add _get_context_tier method**

Add after `_get_context_budget` (after line 189):

```python
    def _get_context_tier(self) -> int:
        """Return the context tier int for the current client.

        Phase 73.3b: Flows the tier to the backend so LOD thresholds,
        hub selection, and module display adapt per client.
        """
        from prep.core.context_tier import tier_from_budget
        # Use the base budget (without orientation boost) to determine tier
        client_lower = self._client_name.lower()
        base = self._DEFAULT_BUDGET
        for pattern, budget in self._CLIENT_BUDGETS.items():
            if pattern in client_lower:
                base = budget
                break
        return tier_from_budget(base).value
```

- [ ] **Step 2: Pass tier in tool_context payload**

In `tool_context` (line 940), add `context_tier` to the payload:

```python
        payload: Dict[str, Any] = {
            "query": "",
            "max_chars": max_chars,
            "include_atlas": not has_rules,
            "context_tier": self._get_context_tier(),
        }
```

- [ ] **Step 3: Pass tier in tool_search payload**

In `tool_search` (~line 813), add context_tier to the payload:

```python
        payload: Dict[str, Any] = {
            "query": query,
            "k": k,
            "max_chars": max_chars,
            "include_sources": True,
            "include_scores": True,
            "structured": True,
            "trace_expand": bool(trace_expand),
            "context_tier": self._get_context_tier(),
        }
```

- [ ] **Step 4: Run compressor and tier tests**

Run: `.venv/bin/pytest tests/test_context_tier.py tests/test_compressor.py tests/test_lod_extractor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/mcp/server.py
git commit -m "feat(mcp): compute and forward context_tier to backend API"
```

---

### Task 7: Wire Tier Into Search Compression Path

**Files:**
- Modify: `src/prep/api/routers/projects/search.py:252-357` (`_apply_lod_compression`)
- Modify: `src/prep/api/routers/projects/search.py:1016-1040` (compression routing)

- [ ] **Step 1: Update _apply_lod_compression to accept tier**

Add `context_tier` parameter to the function signature (line 252):

```python
def _apply_lod_compression(
    chunks: List[Dict[str, Any]],
    proj: Any,
    query: str,
    max_chars: int,
    context_tier: Optional[int] = None,
) -> Dict[str, Any]:
```

Add tier detection at the top of the function:

```python
    from prep.core.context_tier import ContextTier, tier_from_budget
    tier = (
        ContextTier(context_tier) if context_tier is not None
        else tier_from_budget(max_chars)
    )
```

Replace the `assign_lod` call (line 286) with tier-aware version:

```python
        lod = assign_lod(score, is_trace_expanded=is_expanded, tier=tier)
```

- [ ] **Step 2: Update the call site at line 1019**

```python
            lod_result = _apply_lod_compression(
                result.get("chunks", []), proj, req.query, req.max_chars,
                context_tier=req.context_tier,
            )
```

- [ ] **Step 3: Update _assemble_ambient_context call site**

Find where `_assemble_ambient_context` is called (search for the function name in search.py) and pass through `context_tier=req.context_tier`. It's called around line 862-870 in the ambient context path:

```python
            ambient_result = _assemble_ambient_context(
                proj, project_id, idx, trace_idx, included_paths,
                max_chars=req.max_chars,
                context_tier=req.context_tier,
            )
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/pytest tests/test_compressor.py tests/test_context_tier.py tests/test_lod_extractor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/projects/search.py
git commit -m "feat(search): wire context_tier through LOD compression and ambient assembly"
```

---

### Task 8: Add LOD 2.5 (Strip Module-Level Constants)

**Files:**
- Modify: `src/prep/core/lod_extractor.py:186-289` (add `_build_lod25`)
- Modify: `src/prep/core/lod_extractor.py:458-480` (LODExtractor.extract)
- Modify: `tests/test_lod_extractor.py` (new TestLOD25 class)
- Modify: `tests/test_compressor.py` (real-file LOD 2.5 tests)

- [ ] **Step 1: Write tests for LOD 2.5**

Add to `tests/test_lod_extractor.py`:

```python
class TestLOD25:
    """LOD 2.5: signatures + docstrings only (strip module-level constants)."""

    def test_retains_function_signatures(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        # LOD 2.5 is requested as lod=25 internally, mapped from the half-level
        result = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert "def standalone_function" in result.content
        assert "class MyClass" in result.content

    def test_strips_module_level_constants(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert "CONSTANT = 42" not in result.content

    def test_retains_imports(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        result = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert "import os" in result.content
        assert "from pathlib import Path" in result.content

    def test_better_ratio_than_lod2(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        r2 = extractor.extract("src/example.py", 2, nodes, tmp_repo)
        r25 = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        assert r25.output_chars <= r2.output_chars

    def test_larger_than_lod4(self, extractor: LODExtractor, tmp_repo: Path) -> None:
        nodes = _make_python_trace_nodes()
        r25 = extractor.extract("src/example.py", 25, nodes, tmp_repo)
        r4 = extractor.extract("src/example.py", 4, nodes, tmp_repo)
        assert r25.output_chars >= r4.output_chars
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_lod_extractor.py::TestLOD25 -v`
Expected: FAIL (LOD 25 not handled)

- [ ] **Step 3: Implement _build_lod25 in lod_extractor.py**

Add after `_build_lod23` (after line 289):

```python
def _build_lod25(
    lines: List[str],
    symbols: List[Dict[str, Any]],
    language: str,
) -> str:
    """LOD 2.5: signatures + docstrings, strip module-level constants.

    Like LOD 2 but also removes lines outside any symbol span that are
    not imports. This handles the constant-heavy file problem where LOD 2
    only achieves ~1.3x because module-level dicts/regexes/constants
    pass through unchanged.
    """
    import_pat = _IMPORT_RE.get(language)

    # First, build the LOD 2 skeleton
    lod2 = _build_lod23(lines, symbols, language, lod3=False)
    lod2_lines = lod2.splitlines()

    # Identify lines that are inside symbol spans
    n = len(lines)
    in_symbol = [False] * (n + 1)  # 1-indexed
    for sym in symbols:
        span = sym.get("span") or {}
        start = span.get("start_line", 0)
        end = span.get("end_line", 0)
        if start and end:
            for ln in range(start, min(end + 1, n + 1)):
                in_symbol[ln] = True

    # Rebuild: keep imports + lines inside symbols, skip module-level code
    out: List[str] = []
    for i, line in enumerate(lines, 1):
        if in_symbol[i]:
            continue  # handled by LOD 2 skeleton
        stripped = line.strip()
        if not stripped:
            continue
        # Keep import lines
        if import_pat and import_pat.match(line):
            out.append(line)
            continue
        # Skip module-level constants, assignments, decorators outside symbols
        # (these are the lines LOD 2 keeps but LOD 2.5 strips)

    # Now merge: imports from raw scan + LOD 2 skeleton for symbols
    # Simpler approach: take LOD 2 output, remove non-import non-symbol lines
    result_lines: List[str] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            # Keep blank lines between symbols for readability
            if result_lines and result_lines[-1].strip():
                result_lines.append("")
            continue
        if import_pat and import_pat.match(line):
            result_lines.append(line)
            continue
        if in_symbol[i]:
            # This line is inside a symbol — use LOD 2 logic
            result_lines.append(line)
            continue
        # Module-level code outside symbols → skip

    # Now apply LOD 2 body compression to the symbol lines
    # Re-run _build_lod23 but only on lines that survived
    # Actually, simpler: just run _build_lod23 on full source, then filter
    # out module-level non-import non-symbol lines from the LOD 2 output

    # Simplest correct approach: mark which original lines are in the LOD 2 output,
    # then remove those that are module-level non-import non-symbol
    out = []
    for orig_line in lod2_lines:
        # Find this line in original source to check if it's module-level
        # This is approximate but works because LOD 2 preserves original lines
        stripped = orig_line.strip()
        if not stripped:
            if out and out[-1].strip():
                out.append(orig_line)
            continue

        # Check if it's a placeholder
        placeholder = _PLACEHOLDER.get(language, _DEFAULT_PLACEHOLDER)
        if stripped == placeholder.strip():
            out.append(orig_line)
            continue

        # Check if it's an import
        if import_pat and import_pat.match(orig_line):
            out.append(orig_line)
            continue

        # Check if this line is inside any symbol span
        # We need to find the line number in original source
        is_in_sym = False
        for ln_idx in range(1, n + 1):
            if lines[ln_idx - 1] == orig_line and in_symbol[ln_idx]:
                is_in_sym = True
                break
        if is_in_sym:
            out.append(orig_line)
            continue

        # Module-level non-import non-symbol line → skip

    while out and not out[-1].strip():
        out.pop()

    return "\n".join(out)
```

- [ ] **Step 4: Wire LOD 25 into LODExtractor.extract**

In `LODExtractor.extract` (~line 458), add handling for `lod == 25` after the `lod == 3` case:

```python
        elif lod == 25:
            lines = source.splitlines()
            content = _build_lod25(lines, file_symbols, language or "")
```

Also update the fallback check (line 447): change `if lod >= 2` to `if lod >= 2 and lod != 25` — actually, LOD 25 also needs symbols, so the existing check is fine. Just make sure LOD 25 falls back like LOD 2:

```python
        # Fall back to LOD 0 if no trace data and LOD > 0 requested
        if lod >= 2 and not file_symbols:
```

This already covers LOD 25 since 25 >= 2.

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_lod_extractor.py::TestLOD25 -v`
Expected: All PASS

- [ ] **Step 6: Add real-file LOD 2.5 tests**

Add to `tests/test_compressor.py` in `TestLODOnRealFiles`:

```python
    @pytest.mark.parametrize("file_path", list(REAL_FILES.keys()))
    def test_lod25_better_than_lod2(self, extractor: LODExtractor, file_path: str) -> None:
        """LOD 2.5 should compress more than LOD 2 on constant-heavy files."""
        nodes = _load_trace_nodes_for_file(file_path)
        if not nodes:
            pytest.skip(f"No symbols extracted for {file_path}")
        r2 = extractor.extract(file_path, 2, nodes, REPO_ROOT)
        r25 = extractor.extract(file_path, 25, nodes, REPO_ROOT)
        assert r25.output_chars <= r2.output_chars, (
            f"LOD 2.5 ({r25.output_chars}) should be <= LOD 2 ({r2.output_chars}) for {file_path}"
        )
```

- [ ] **Step 7: Run all tests**

Run: `.venv/bin/pytest tests/test_lod_extractor.py tests/test_compressor.py tests/test_context_tier.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/lod_extractor.py tests/test_lod_extractor.py tests/test_compressor.py
git commit -m "feat(lod): add LOD 2.5 — strip module-level constants for better compression"
```

---

### Task 9: Final Integration + Export

**Files:**
- Modify: `src/prep/core/__init__.py` (export ContextTier)

- [ ] **Step 1: Add exports to core __init__.py**

Add to the imports section (~line 70):

```python
from .context_tier import ContextTier, tier_from_budget
```

Add to `__all__` list:

```python
    "ContextTier",
    "tier_from_budget",
```

- [ ] **Step 2: Run the full test suite**

Run: `.venv/bin/pytest tests/test_context_tier.py tests/test_lod_extractor.py tests/test_compressor.py -v`
Expected: All PASS

- [ ] **Step 3: Run a broader smoke test**

Run: `.venv/bin/pytest tests/ -v --timeout=30 -x -q 2>&1 | tail -20`
Expected: No unexpected failures

- [ ] **Step 4: Commit**

```bash
git add src/prep/core/__init__.py
git commit -m "feat(core): export ContextTier and tier_from_budget"
```

---

## Verification

After all tasks complete, verify the full chain works:

1. **Unit tests:** `pytest tests/test_context_tier.py tests/test_lod_extractor.py tests/test_compressor.py -v` — all green
2. **LOD 2.5 real-file improvement:** The `test_lod25_better_than_lod2` tests confirm LOD 2.5 compresses more than LOD 2 on constant-heavy files
3. **Tier detection:** `tier_from_budget(50_000)` → Tier 1, `tier_from_budget(30_000)` → Tier 2, `tier_from_budget(20_000)` → Tier 2.5
4. **Backward compatibility:** All existing `assign_lod()` tests still pass (no tier arg = Tier 2 defaults = unchanged thresholds)
5. **MCP flow:** `tool_context` and `tool_search` both forward `context_tier` to the backend
