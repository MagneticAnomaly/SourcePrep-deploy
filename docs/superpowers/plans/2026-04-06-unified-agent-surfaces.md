# Unified Agent Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Prep a clean frontend story: Prep dashboard is config-only, Paperclip plugin is the rich agent surface, and a push enrichment pipeline connects engine findings to Paperclip issues with structural intelligence.

**Architecture:** Four phases. Phase 1 adds backend capabilities (consensus scoring, structural enrichment, significance classification, push settings). Phase 2 simplifies the Prep dashboard to config-only. Phase 3 enhances the Paperclip plugin UI slots. Phase 4 wires engine runs to the push pipeline. Each phase produces independently testable, committable work.

**Tech Stack:** Python 3.11 (FastAPI, SQLite, Pydantic, pytest asyncio), TypeScript/React (Tailwind, Tremor, Lucide icons), Paperclip Plugin SDK (`@paperclipai/plugin-sdk`).

**Spec:** `docs/superpowers/specs/2026-04-06-unified-agent-surfaces-design.md`
**Backend enrichment spec:** `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/emergence_and_p3_design.md`

**Status:** IMPLEMENTED — 19 commits, 27 tests. See spec Section 13 for implementation status and deferred roadmap.

---

## File Structure

**New files (10):**

| File | Responsibility |
|---|---|
| `tests/test_consensus_scoring.py` | Unit tests for `get_consensus_scores()` on ObservationStore |
| `tests/test_structural_enrichment.py` | Unit tests for `StructuralContext` + complexity tiers + PushEngine enrichment |
| `tests/test_significance.py` | Unit tests for significance classification on engine findings |
| `tests/test_push_settings_api.py` | Tests for push settings + consensus REST endpoints |
| `tests/test_delta_push.py` | Tests for `push_significant_delta()` on PushEngine |
| `packages/ui/src/components/agents/PushSettings.tsx` | Push config form: auto-push toggle, significance threshold, Paperclip project |
| `packages/paperclip-plugin-prep/src/ui/CodebaseHealthWidget.tsx` | Enhanced dashboard widget: pipeline status, push summary, consensus, delta |
| `packages/paperclip-plugin-prep/src/ui/KnowledgeScopeTab.tsx` | Read-only scope display with claims overlay |
| `packages/paperclip-plugin-prep/src/ui/IssueContextTab.tsx` | Structural context for Prep-pushed issues + on-demand enrichment |
| `packages/paperclip-plugin-prep/src/ui/SettingsPage.tsx` | Enhanced settings with health check + push settings link |

**Modified files (13):**

| File | Changes |
|---|---|
| `src/prep/services/observation_store.py` | Add `get_consensus_scores()` method (~30 lines) |
| `src/prep/adapters/pm_models.py` | Add `StructuralContext` dataclass + `structural_context` on `PMIssue` + `significance` on `PMIssue` (~40 lines) |
| `src/prep/adapters/push_engine.py` | Add `snapshot_store` param, `_enrich_with_structural_context()`, `push_significant_delta()`, consensus enrichment in `_push_group()` (~100 lines) |
| `src/prep/api/routers/collaboration.py` | Add consensus endpoint + push summary endpoint + push settings endpoints (~60 lines) |
| `src/prep/api/routers/agents.py` | Add `push` query param to generate/run endpoints (~20 lines) |
| `src/prep/mcp/collaboration_handlers.py` | Add consensus hotspots to `format_delta_resource()`, claims steps to prompts (~20 lines) |
| `packages/ui/src/components/agents/AgentOpsPanel.tsx` | Redesign: engine control rows + PushSettings section (rewrite ~140 lines) |
| `packages/ui/src/components/agents/index.ts` | Update exports — add PushSettings, remove dashboard-only re-exports |
| `packages/ui/src/config/panelRegistry.ts` | Update `agent-ops` description |
| `packages/paperclip-plugin-prep/src/worker/index.ts` | Extend `codebase-health` provider, fix `agent-knowledge-scope`, add `consensus-hotspots` + `push-summary` providers, add `enrich-issue` action (~80 lines) |
| `packages/paperclip-plugin-prep/src/manifest.ts` | No structural changes (data providers/actions are registered dynamically in worker) |
| `src/prep/dashboard/src/hooks/useAgentOps.ts` | Update to match redesigned AgentOpsPanel props |
| `src/prep/dashboard/src/hooks/useDashboardPanels.tsx` | Update agent-ops panel rendering |

---

## Phase 1: Backend Push Enrichment

### Task 1: Consensus Scoring on ObservationStore

**Files:**
- Modify: `src/prep/services/observation_store.py:480-496` (after `get_all_attributed`)
- Test: `tests/test_consensus_scoring.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_consensus_scoring.py
"""Tests for consensus scoring on ObservationStore."""
import tempfile
from pathlib import Path

import pytest

from prep.services.observation_store import ObservationStore


@pytest.fixture
def store(tmp_path):
    s = ObservationStore()
    s.init(tmp_path / "test.db")
    yield s
    s.close()


def test_no_observations_returns_empty(store):
    results = store.get_consensus_scores("proj-1")
    assert results == []


def test_single_agent_per_file_returns_empty(store):
    store.save("proj-1", "Auth uses JWT", file_path="src/auth.py", created_by="researcher")
    store.save("proj-1", "Config loads env", file_path="src/config.py", created_by="researcher")
    results = store.get_consensus_scores("proj-1", min_agents=2)
    assert results == []


def test_two_agents_same_file_returns_consensus(store):
    store.save("proj-1", "Auth JWT pattern", file_path="src/auth.py", created_by="researcher")
    store.save("proj-1", "Auth dead code", file_path="src/auth.py", created_by="custodian")
    results = store.get_consensus_scores("proj-1", min_agents=2)
    assert len(results) == 1
    assert results[0]["file_path"] == "src/auth.py"
    assert results[0]["agent_count"] == 2
    assert set(results[0]["agents"]) == {"researcher", "custodian"}
    assert results[0]["consensus_score"] == pytest.approx(1.0)  # 2/2 active agents


def test_stale_observations_excluded(store):
    store.save("proj-1", "Auth JWT", file_path="src/auth.py", created_by="researcher")
    store.save("proj-1", "Auth dead", file_path="src/auth.py", created_by="custodian")
    store.mark_stale_batch("proj-1", ["src/auth.py"], "file modified")
    results = store.get_consensus_scores("proj-1", min_agents=2)
    assert results == []


def test_since_days_filter(store):
    import time
    # Save an old observation (fake timestamp by direct SQL)
    store.save("proj-1", "Old obs", file_path="src/auth.py", created_by="researcher")
    store.save("proj-1", "New obs", file_path="src/auth.py", created_by="custodian")
    # With default since_days=30, both should be included
    results = store.get_consensus_scores("proj-1", min_agents=2, since_days=30)
    assert len(results) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_consensus_scoring.py -v`
Expected: FAIL — `ObservationStore` has no `get_consensus_scores` method.

- [ ] **Step 3: Implement `get_consensus_scores()`**

In `src/prep/services/observation_store.py`, after `get_all_attributed()` (around line 496), add:

```python
    def get_consensus_scores(
        self,
        project_id: str,
        min_agents: int = 2,
        since_days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Group attributed observations by file_path, count distinct agents.

        Returns files flagged by min_agents or more distinct agents,
        with consensus_score = agent_count / total_active_agents.
        """
        conn = self._require_conn()
        cutoff = time.time() - since_days * 86400

        with self._lock:
            # Count total distinct active agents
            total_row = conn.execute(
                """SELECT COUNT(DISTINCT created_by) AS cnt
                   FROM observations
                   WHERE project_id = ? AND created_by IS NOT NULL
                   AND created_at > ?""",
                (project_id, cutoff),
            ).fetchone()
            total_active = total_row["cnt"] if total_row else 0

            if total_active < min_agents:
                return []

            rows = conn.execute(
                """SELECT file_path,
                          GROUP_CONCAT(DISTINCT created_by) AS agents,
                          COUNT(DISTINCT created_by) AS agent_count,
                          MAX(created_at) AS latest_at
                   FROM observations
                   WHERE project_id = ?
                     AND created_by IS NOT NULL
                     AND file_path IS NOT NULL
                     AND stale = 0
                     AND created_at > ?
                   GROUP BY file_path
                   HAVING COUNT(DISTINCT created_by) >= ?
                   ORDER BY agent_count DESC, latest_at DESC""",
                (project_id, cutoff, min_agents),
            ).fetchall()

        return [
            {
                "file_path": row["file_path"],
                "agents": row["agents"].split(","),
                "agent_count": row["agent_count"],
                "total_active_agents": total_active,
                "consensus_score": round(
                    row["agent_count"] / total_active, 2,
                ),
                "latest_observation_at": row["latest_at"],
            }
            for row in rows
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_consensus_scoring.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/observation_store.py tests/test_consensus_scoring.py
git commit -m "feat(collab): add consensus scoring to ObservationStore"
```

---

### Task 2: StructuralContext Dataclass + Complexity Tiers

**Files:**
- Modify: `src/prep/adapters/pm_models.py:56-57` (add field to PMIssue) and after `PMPushConfig` (add new dataclass)
- Test: `tests/test_structural_enrichment.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_structural_enrichment.py
"""Tests for StructuralContext and complexity tier computation."""
import pytest

from prep.adapters.pm_models import StructuralContext, compute_complexity_tier


def test_empty_context_is_lightweight():
    ctx = StructuralContext()
    assert compute_complexity_tier(ctx) == "lightweight"


def test_one_hub_is_standard():
    ctx = StructuralContext(
        hub_files_involved=["src/gateway.py"],
        hub_count=1,
        total_dependents=10,
    )
    assert compute_complexity_tier(ctx) == "standard"


def test_two_hubs_is_heavyweight():
    ctx = StructuralContext(
        hub_files_involved=["src/gateway.py", "src/config.py"],
        hub_count=2,
        total_dependents=30,
    )
    assert compute_complexity_tier(ctx) == "heavyweight"


def test_cross_module_is_heavyweight():
    ctx = StructuralContext(
        modules_spanned=["api_gateway", "core_config", "auth"],
        cross_module=True,
        hub_count=0,
        total_dependents=3,
    )
    assert compute_complexity_tier(ctx) == "heavyweight"


def test_high_dependents_is_heavyweight():
    ctx = StructuralContext(
        hub_count=1,
        total_dependents=25,
    )
    assert compute_complexity_tier(ctx) == "heavyweight"


def test_low_dependents_no_hubs_is_lightweight():
    ctx = StructuralContext(
        hub_count=0,
        total_dependents=2,
        modules_spanned=["core"],
        cross_module=False,
    )
    assert compute_complexity_tier(ctx) == "lightweight"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_structural_enrichment.py -v`
Expected: FAIL — `StructuralContext` and `compute_complexity_tier` don't exist.

- [ ] **Step 3: Add StructuralContext and compute_complexity_tier to pm_models.py**

In `src/prep/adapters/pm_models.py`, after the `PMPushConfig` class (end of file), add:

```python
# ── Structural Enrichment (Phase 73.5 Emergence) ───────────────────


@dataclass
class StructuralContext:
    """Structural intelligence attached to a PM issue.

    Prep-only data that helps Paperclip route work.
    """
    hub_files_involved: List[str] = field(default_factory=list)
    hub_count: int = 0
    total_dependents: int = 0
    modules_spanned: List[str] = field(default_factory=list)
    cross_module: bool = False
    complexity_tier: str = "lightweight"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hub_files": self.hub_files_involved,
            "hub_count": self.hub_count,
            "total_dependents": self.total_dependents,
            "modules_spanned": self.modules_spanned,
            "cross_module": self.cross_module,
            "complexity_tier": self.complexity_tier,
        }


def compute_complexity_tier(ctx: StructuralContext) -> str:
    """Classify structural complexity: lightweight / standard / heavyweight."""
    if ctx.hub_count >= 2 or ctx.total_dependents > 20 or ctx.cross_module:
        return "heavyweight"
    if ctx.hub_count >= 1 or ctx.total_dependents > 5:
        return "standard"
    return "lightweight"
```

Also add `structural_context` and `significance` fields to `PMIssue` (after `prep_item_ids`, around line 56):

```python
    # Structural enrichment (Phase 73.5 Emergence)
    structural_context: Optional["StructuralContext"] = None
    significance: str = "recommended"   # "mandatory" | "recommended" | "informational"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_structural_enrichment.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/adapters/pm_models.py tests/test_structural_enrichment.py
git commit -m "feat(push): add StructuralContext dataclass and complexity tiers"
```

---

### Task 3: PushEngine Structural Enrichment

**Files:**
- Modify: `src/prep/adapters/push_engine.py:44-50` (add `snapshot_store` param) and `175-260` (enrich in `_push_group`)
- Test: extend `tests/test_structural_enrichment.py`

- [ ] **Step 1: Write the failing test for enrichment**

Append to `tests/test_structural_enrichment.py`:

```python
from unittest.mock import MagicMock
from prep.adapters.push_engine import PushEngine
from prep.services.collaboration.snapshots import GraphSnapshot


def _make_snapshot(hubs, modules):
    return GraphSnapshot(
        id="snap-1", project_id="proj-1",
        hubs=hubs, modules=modules,
        created_at=1000.0,
    )


def test_enrich_no_snapshot_returns_none():
    adapter = MagicMock()
    engine = PushEngine(adapter)
    ctx = engine._enrich_with_structural_context(
        affected_files=["src/foo.py"],
        project_id="proj-1",
    )
    assert ctx is None


def test_enrich_with_hub_files():
    adapter = MagicMock()
    snapshot_store = MagicMock()
    snapshot_store.get_latest.return_value = _make_snapshot(
        hubs=[
            {"path": "src/gateway.py", "dependents_count": 14, "rank": 2},
            {"path": "src/config.py", "dependents_count": 18, "rank": 3},
        ],
        modules=[
            {"name": "api_gateway", "files": ["src/gateway.py", "src/routes.py"]},
            {"name": "core_config", "files": ["src/config.py"]},
        ],
    )
    engine = PushEngine(adapter, snapshot_store=snapshot_store)
    ctx = engine._enrich_with_structural_context(
        affected_files=["src/gateway.py", "src/config.py"],
        project_id="proj-1",
    )
    assert ctx is not None
    assert ctx.hub_count == 2
    assert ctx.total_dependents == 32
    assert ctx.cross_module is True
    assert ctx.complexity_tier == "heavyweight"


def test_enrich_leaf_files_only():
    adapter = MagicMock()
    snapshot_store = MagicMock()
    snapshot_store.get_latest.return_value = _make_snapshot(
        hubs=[{"path": "src/gateway.py", "dependents_count": 14, "rank": 2}],
        modules=[{"name": "utils", "files": ["src/utils.py", "src/helpers.py"]}],
    )
    engine = PushEngine(adapter, snapshot_store=snapshot_store)
    ctx = engine._enrich_with_structural_context(
        affected_files=["src/utils.py"],
        project_id="proj-1",
    )
    assert ctx is not None
    assert ctx.hub_count == 0
    assert ctx.complexity_tier == "lightweight"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_structural_enrichment.py::test_enrich_no_snapshot_returns_none -v`
Expected: FAIL — `PushEngine` doesn't accept `snapshot_store` or have `_enrich_with_structural_context`.

- [ ] **Step 3: Add `snapshot_store` param and `_enrich_with_structural_context` to PushEngine**

In `src/prep/adapters/push_engine.py`, modify `__init__` (line 44):

```python
    def __init__(
        self,
        adapter: PMAdapter,
        consolidator: Optional[Consolidator] = None,
        conflict_detector: Optional[Any] = None,
        conflict_store: Optional[Any] = None,
        snapshot_store: Optional[Any] = None,
    ) -> None:
        self.adapter = adapter
        self.consolidator = consolidator or Consolidator()
        self._conflict_detector = conflict_detector
        self._conflict_store = conflict_store
        self._snapshot_store = snapshot_store
```

After `_push_conflict_to_pm` (around line 301), add:

```python
    # ── Structural Enrichment ──────────────────────────────────

    def _enrich_with_structural_context(
        self,
        affected_files: List[str],
        project_id: str,
    ) -> Optional["StructuralContext"]:
        """Compute structural context for a set of affected files.

        Uses the latest graph snapshot to check hub involvement
        and module membership. Returns None if no snapshot available.
        """
        if not self._snapshot_store:
            return None

        from prep.adapters.pm_models import StructuralContext, compute_complexity_tier

        latest = self._snapshot_store.get_latest(project_id)
        if not latest:
            return None

        hub_paths = {h["path"]: h for h in latest.hubs}
        hub_files = [f for f in affected_files if f in hub_paths]
        total_deps = sum(
            hub_paths[f].get("dependents_count", 0) for f in hub_files
        )

        # Module detection from snapshot
        file_to_module: Dict[str, str] = {}
        for mod in latest.modules:
            for f in mod.get("files", []):
                file_to_module[f] = mod["name"]
        modules = list(set(
            file_to_module.get(f, "unknown") for f in affected_files
        ))

        ctx = StructuralContext(
            hub_files_involved=hub_files,
            hub_count=len(hub_files),
            total_dependents=total_deps,
            modules_spanned=modules,
            cross_module=len(modules) > 1,
        )
        ctx.complexity_tier = compute_complexity_tier(ctx)
        return ctx
```

Add the missing import at the top of push_engine.py:

```python
from typing import Any, Dict, List, Optional
```

(This import already exists — just verify `Dict` is included.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_structural_enrichment.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/adapters/push_engine.py tests/test_structural_enrichment.py
git commit -m "feat(push): add structural enrichment to PushEngine"
```

---

### Task 4: Delta Push to Paperclip

**Files:**
- Modify: `src/prep/adapters/push_engine.py` (add `push_significant_delta` after `_enrich_with_structural_context`)
- Test: `tests/test_delta_push.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_delta_push.py
"""Tests for push_significant_delta on PushEngine."""
from unittest.mock import MagicMock, call

import pytest

from prep.adapters.push_engine import PushEngine
from prep.services.collaboration.snapshots import StructuralDelta


def test_empty_delta_pushes_nothing():
    adapter = MagicMock()
    engine = PushEngine(adapter)
    delta = StructuralDelta(since=0, until=1000)
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 0
    adapter.create_issue.assert_not_called()


def test_rank_change_only_pushes_nothing():
    adapter = MagicMock()
    engine = PushEngine(adapter)
    delta = StructuralDelta(
        since=0, until=1000,
        hub_changes=[{"path": "src/foo.py", "change": "rank_changed", "old_rank": 3, "new_rank": 1}],
    )
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 0


def test_new_hub_creates_issue():
    adapter = MagicMock()
    adapter.find_issue_by_prep_address.return_value = None
    engine = PushEngine(adapter)
    delta = StructuralDelta(
        since=0, until=1000,
        hub_changes=[{"path": "src/gateway.py", "change": "new", "dependents_count": 14, "rank": 2}],
    )
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 1
    adapter.create_issue.assert_called_once()
    issue = adapter.create_issue.call_args[0][0]
    assert "src/gateway.py" in issue.title
    assert "new hub" in issue.title.lower() or "New hub" in issue.description


def test_dedup_same_delta_twice():
    adapter = MagicMock()
    adapter.find_issue_by_prep_address.return_value = "existing-id"
    engine = PushEngine(adapter)
    delta = StructuralDelta(
        since=0, until=1000,
        hub_changes=[{"path": "src/gateway.py", "change": "new", "dependents_count": 14, "rank": 2}],
    )
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 0
    adapter.create_issue.assert_not_called()


def test_mixed_delta_creates_multiple_issues():
    adapter = MagicMock()
    adapter.find_issue_by_prep_address.return_value = None
    engine = PushEngine(adapter)
    delta = StructuralDelta(
        since=0, until=1000,
        hub_changes=[{"path": "src/gw.py", "change": "new", "dependents_count": 10, "rank": 3}],
        module_changes=[{"name": "auth_v2", "change": "new", "file_count": 8}],
    )
    count = engine.push_significant_delta(delta, "proj-1")
    assert count == 2
    assert adapter.create_issue.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_delta_push.py -v`
Expected: FAIL — `PushEngine` has no `push_significant_delta` method.

- [ ] **Step 3: Implement `push_significant_delta`**

In `src/prep/adapters/push_engine.py`, after `_enrich_with_structural_context`, add:

```python
    def push_significant_delta(
        self,
        delta: Any,
        project_id: str,
    ) -> int:
        """Push significant structural changes to Paperclip as issues.

        Only pushes new/removed hubs and modules. Rank changes and
        size changes are informational and stay in the MCP delta resource.

        Returns the number of issues created.
        """
        from prep.adapters.pm_models import PMIssue

        significant = []
        for h in delta.hub_changes:
            if h.get("change") in ("new", "removed"):
                significant.append({**h, "type": "hub"})
        for m in delta.module_changes:
            if m.get("change") in ("new", "removed"):
                significant.append({**m, "type": "module"})

        if not significant:
            return 0

        created = 0
        for change in significant:
            change_type = change["type"]
            change_action = change["change"]

            if change_type == "hub":
                path = change.get("path", "unknown")
                address = f"prep://{project_id}/DELTA-hub-{hash(path) & 0xFFFFFFFF:08x}"
                if change_action == "new":
                    deps = change.get("dependents_count", 0)
                    rank = change.get("rank", "?")
                    title = f"Structural Change: {path} is a new hub ({deps} dependents)"
                    desc = (
                        f"A new hub file was detected after pipeline rebuild.\n\n"
                        f"**File:** {path}\n"
                        f"**Dependents:** {deps}\n"
                        f"**Rank:** #{rank}\n\n"
                        f"Hub files are central dependencies — many other files import from them. "
                        f"Changes to hub files have high blast radius.\n\n"
                        f"---\n"
                        f"<!-- prep-address:{address} -->\n"
                        f"<!-- prep-delta:true -->"
                    )
                else:
                    title = f"Structural Change: {path} is no longer a hub"
                    desc = (
                        f"A hub file was removed from the hub list after pipeline rebuild.\n\n"
                        f"**File:** {path}\n\n"
                        f"This file no longer has enough dependents to be a hub.\n\n"
                        f"---\n"
                        f"<!-- prep-address:{address} -->\n"
                        f"<!-- prep-delta:true -->"
                    )
            else:
                name = change.get("name", "unknown")
                address = f"prep://{project_id}/DELTA-module-{hash(name) & 0xFFFFFFFF:08x}"
                if change_action == "new":
                    file_count = change.get("file_count", 0)
                    title = f"Structural Change: new module '{name}' ({file_count} files)"
                    desc = (
                        f"A new module was detected after pipeline rebuild.\n\n"
                        f"**Module:** {name}\n"
                        f"**Files:** {file_count}\n\n"
                        f"---\n"
                        f"<!-- prep-address:{address} -->\n"
                        f"<!-- prep-delta:true -->"
                    )
                else:
                    title = f"Structural Change: module '{name}' removed"
                    desc = (
                        f"A module was removed after pipeline rebuild.\n\n"
                        f"**Module:** {name}\n\n"
                        f"---\n"
                        f"<!-- prep-address:{address} -->\n"
                        f"<!-- prep-delta:true -->"
                    )

            # Dedup check
            existing = self.adapter.find_issue_by_prep_address(address)
            if existing:
                continue

            try:
                issue = PMIssue(
                    title=title,
                    description=desc,
                    priority="P3",
                    category="architecture",
                    prep_address=address,
                )
                self.adapter.create_issue(issue)
                created += 1
            except Exception:
                logger.debug("Failed to push delta issue (non-fatal)", exc_info=True)

        return created
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_delta_push.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/adapters/push_engine.py tests/test_delta_push.py
git commit -m "feat(push): add delta push to Paperclip for significant structural changes"
```

---

### Task 5: Consensus Hotspots in Delta Resource + Claims in Prompts

**Files:**
- Modify: `src/prep/mcp/collaboration_handlers.py:145-198` (extend `format_delta_resource`) and `234-280` (extend prompts)

- [ ] **Step 1: Add consensus hotspots to delta resource formatter**

In `src/prep/mcp/collaboration_handlers.py`, modify `format_delta_resource()` — after the module changes section (before the final `return`), add:

```python
    # Consensus hotspots (if provided)
    consensus = delta.get("consensus_hotspots", [])
    if consensus:
        lines.append("")
        lines.append("### Consensus Hotspots (files flagged by 2+ agents)")
        lines.append("")
        lines.append("| File | Agents | Score |")
        lines.append("|---|---|---|")
        for entry in consensus:
            agents_str = ", ".join(entry.get("agents", []))
            score = entry.get("consensus_score", 0)
            lines.append(
                f"| {entry.get('file_path', '?')} "
                f"| {agents_str} | {score:.2f} |"
            )
```

- [ ] **Step 2: Add claims steps to prompts**

In the same file, modify the `prep-enrich` prompt text (in `get_collaboration_prompts()` or `format_prompt_messages()`). Find the prompt message list for `prep-enrich` and append:

```python
# In the enrich prompt messages, add after existing steps:
"7. Check active file claims: which files are currently claimed by agents? "
"Findings on claimed files should note the claim — the claiming agent "
"may already be addressing the issue."
```

And in the `prep-handoff` prompt messages, add:

```python
"5. Check active claims: does the from-agent have any active file claims? "
"The receiving agent should be aware of claimed areas and either "
"respect or release those claims."
```

- [ ] **Step 3: Run existing collaboration tests**

Run: `.venv/bin/pytest tests/test_collab_resources.py -v`
Expected: PASS (existing tests should still pass; the new content is additive).

- [ ] **Step 4: Commit**

```bash
git add src/prep/mcp/collaboration_handlers.py
git commit -m "feat(collab): add consensus hotspots to delta resource, claims to prompts"
```

---

### Task 6: Consensus + Push Summary REST Endpoints

**Files:**
- Modify: `src/prep/api/routers/collaboration.py` (add 3 endpoints after existing claims endpoints)
- Test: `tests/test_push_settings_api.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_push_settings_api.py
"""Tests for consensus and push settings API endpoints."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create a test FastAPI app with collaboration router."""
    from fastapi import FastAPI
    from prep.api.routers.collaboration import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_consensus_endpoint_returns_scores(client):
    mock_store = MagicMock()
    mock_store.get_consensus_scores.return_value = [
        {
            "file_path": "src/auth.py",
            "agents": ["researcher", "custodian"],
            "agent_count": 2,
            "total_active_agents": 3,
            "consensus_score": 0.67,
            "latest_observation_at": 1000.0,
        }
    ]

    with patch(
        "prep.api.routers.collaboration._get_obs_store",
        return_value=mock_store,
    ):
        resp = client.get("/projects/proj-1/collaboration/consensus")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["scores"]) == 1
    assert data["scores"][0]["file_path"] == "src/auth.py"


def test_consensus_endpoint_empty(client):
    mock_store = MagicMock()
    mock_store.get_consensus_scores.return_value = []

    with patch(
        "prep.api.routers.collaboration._get_obs_store",
        return_value=mock_store,
    ):
        resp = client.get("/projects/proj-1/collaboration/consensus")

    assert resp.status_code == 200
    assert resp.json()["data"]["scores"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_push_settings_api.py -v`
Expected: FAIL — no `/collaboration/consensus` endpoint.

- [ ] **Step 3: Add endpoints to collaboration router**

In `src/prep/api/routers/collaboration.py`, after the claims endpoints (end of file), add:

```python
# ── Consensus ──────────────────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/consensus")
async def get_consensus(
    project_id: str,
    min_agents: int = Query(2, ge=2),
    since_days: int = Query(30, ge=1, le=365),
):
    store = _get_obs_store()
    scores = store.get_consensus_scores(
        project_id, min_agents=min_agents, since_days=since_days,
    )
    return ok({"scores": scores})


# ── Push Summary ───────────────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/push-summary")
async def get_push_summary(project_id: str):
    """Lightweight push summary from activity store."""
    hub = _get_hub()
    # Filter activity for push-related actions
    entries = hub.activity.get_recent(project_id, limit=50)
    push_entries = [
        e for e in entries
        if "push" in (e.action if hasattr(e, "action") else "").lower()
    ]
    return ok({
        "total_pushes": len(push_entries),
        "latest_push_at": push_entries[0].created_at if push_entries else None,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_push_settings_api.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/collaboration.py tests/test_push_settings_api.py
git commit -m "feat(api): add consensus scoring and push summary endpoints"
```

---

## Phase 2: Prep Dashboard Simplification

### Task 7: Redesign AgentOpsPanel to Config-Only

**Files:**
- Modify: `packages/ui/src/components/agents/AgentOpsPanel.tsx` (rewrite)
- Create: `packages/ui/src/components/agents/PushSettings.tsx` (new)
- Modify: `packages/ui/src/components/agents/index.ts` (update exports)

- [ ] **Step 1: Create PushSettings component**

```tsx
// packages/ui/src/components/agents/PushSettings.tsx
/**
 * PushSettings — Minimal push configuration form.
 *
 * Three fields: auto-push toggle, significance threshold, Paperclip project.
 * Reads/writes via callbacks — no internal API calls.
 */

export interface PushSettingsData {
  auto_push: boolean;
  min_significance: 'all' | 'recommended' | 'mandatory';
  paperclip_project: string;
}

export interface PushSettingsProps {
  settings: PushSettingsData | null;
  loading?: boolean;
  onUpdate?: (settings: PushSettingsData) => void;
  className?: string;
}

const SIGNIFICANCE_OPTIONS = [
  { value: 'all', label: 'All findings' },
  { value: 'recommended', label: 'Recommended+ only' },
  { value: 'mandatory', label: 'Mandatory only' },
] as const;

export function PushSettings({
  settings,
  loading = false,
  onUpdate,
  className = '',
}: PushSettingsProps) {
  if (loading || !settings) {
    return (
      <div className={`text-xs text-muted-foreground ${className}`}>
        {loading ? 'Loading push settings...' : ''}
      </div>
    );
  }

  const handleToggle = () => {
    onUpdate?.({ ...settings, auto_push: !settings.auto_push });
  };

  const handleThreshold = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onUpdate?.({
      ...settings,
      min_significance: e.target.value as PushSettingsData['min_significance'],
    });
  };

  const handleProject = (e: React.ChangeEvent<HTMLInputElement>) => {
    onUpdate?.({ ...settings, paperclip_project: e.target.value });
  };

  return (
    <div className={`space-y-2.5 ${className}`}>
      <h4 className="text-xs font-medium text-muted-foreground">Push Settings</h4>

      {/* Auto-push toggle */}
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={settings.auto_push}
          onChange={handleToggle}
          className="rounded border-border"
        />
        <span>Auto-push findings to Paperclip</span>
      </label>

      {/* Significance threshold */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground shrink-0">Threshold:</label>
        <select
          value={settings.min_significance}
          onChange={handleThreshold}
          className="flex-1 px-2 py-1 text-xs bg-surface border border-border rounded-md
                     focus:outline-none focus:ring-1 focus:ring-primary text-text"
        >
          {SIGNIFICANCE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Paperclip project */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground shrink-0">Project:</label>
        <input
          type="text"
          value={settings.paperclip_project}
          onChange={handleProject}
          placeholder="auto-detect"
          className="flex-1 px-2 py-1 text-xs bg-surface border border-border rounded-md
                     focus:outline-none focus:ring-1 focus:ring-primary text-text"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Rewrite AgentOpsPanel as config-only**

Replace the content of `packages/ui/src/components/agents/AgentOpsPanel.tsx`:

```tsx
/**
 * AgentOpsPanel — Config-only dashboard panel for Agent Operations.
 *
 * Shows engine control rows (Run/Generate/Scan with last-run + push count),
 * Paperclip connection status, and push settings.
 * No operational monitoring — that belongs in Paperclip.
 */
import { Users, Search, Trash2 } from 'lucide-react';
import { MCPConnectionCard, type MCPStatusData, type MCPInstallResult } from './MCPConnectionCard';
import { PushSettings, type PushSettingsData } from './PushSettings';

export interface EngineStatus {
  last_run: string | null;
  push_count: number;
}

export interface AgentOpsData {
  hr: EngineStatus;
  researcher: EngineStatus;
  custodian: EngineStatus;
}

export interface AgentOpsPanelProps {
  data: AgentOpsData | null;
  loading?: boolean;
  onHRGenerate?: () => void;
  onResearchRun?: () => void;
  onCustodianRun?: () => void;
  /** Paperclip skill status */
  mcpStatus?: MCPStatusData | null;
  mcpLoading?: boolean;
  onMCPInstall?: () => Promise<MCPInstallResult>;
  onMCPUninstall?: () => Promise<void>;
  onMCPRefresh?: () => void;
  /** Push settings */
  pushSettings?: PushSettingsData | null;
  pushSettingsLoading?: boolean;
  onPushSettingsUpdate?: (settings: PushSettingsData) => void;
  className?: string;
}

interface EngineRowProps {
  name: string;
  description: string;
  icon: React.ReactNode;
  status: EngineStatus | null;
  onAction?: () => void;
  actionLabel: string;
}

function EngineRow({ name, description, icon, status, onAction, actionLabel }: EngineRowProps) {
  return (
    <div className="flex items-center gap-3 py-2 px-2 rounded-md hover:bg-muted/30 transition-colors">
      <div className="text-muted-foreground shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{name}</div>
        <div className="text-xs text-muted-foreground truncate">{description}</div>
      </div>
      <div className="text-right shrink-0 mr-2">
        {status?.last_run ? (
          <div className="text-[10px] text-muted-foreground">
            {status.push_count > 0 && (
              <span className="text-primary">{status.push_count} pushed</span>
            )}
            {status.push_count > 0 && ' · '}
            {status.last_run}
          </div>
        ) : (
          <div className="text-[10px] text-muted-foreground italic">Not yet run</div>
        )}
      </div>
      {onAction && (
        <button
          onClick={onAction}
          className="shrink-0 px-2.5 py-1 text-xs font-medium rounded-md
                     bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function AgentOpsPanel({
  data,
  loading = false,
  onHRGenerate,
  onResearchRun,
  onCustodianRun,
  mcpStatus,
  mcpLoading = false,
  onMCPInstall,
  onMCPUninstall,
  onMCPRefresh,
  pushSettings,
  pushSettingsLoading = false,
  onPushSettingsUpdate,
  className = '',
}: AgentOpsPanelProps) {
  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 text-muted-foreground ${className}`}>
        Loading agent config...
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Engine Controls */}
      <div>
        <h4 className="text-xs font-medium text-muted-foreground mb-1">Engines</h4>
        <div className="divide-y divide-border/50">
          <EngineRow
            name="HR Agent"
            description="Generate and audit agent role definitions"
            icon={<Users size={14} />}
            status={data?.hr ?? null}
            onAction={onHRGenerate}
            actionLabel="Generate"
          />
          <EngineRow
            name="Researcher"
            description="Mine audit findings, formulate plans"
            icon={<Search size={14} />}
            status={data?.researcher ?? null}
            onAction={onResearchRun}
            actionLabel="Research"
          />
          <EngineRow
            name="Custodian"
            description="Detect dead code, plan cleanup"
            icon={<Trash2 size={14} />}
            status={data?.custodian ?? null}
            onAction={onCustodianRun}
            actionLabel="Scan"
          />
        </div>
      </div>

      {/* Paperclip Connection */}
      <MCPConnectionCard
        status={mcpStatus ?? null}
        loading={mcpLoading}
        onInstall={onMCPInstall}
        onUninstall={onMCPUninstall}
        onRefresh={onMCPRefresh}
      />

      {/* Push Settings */}
      <PushSettings
        settings={pushSettings ?? null}
        loading={pushSettingsLoading}
        onUpdate={onPushSettingsUpdate}
      />
    </div>
  );
}
```

- [ ] **Step 3: Update index.ts exports**

In `packages/ui/src/components/agents/index.ts`, replace the full file:

```typescript
// Agent Scope (Phase 67 — Knowledge Scope Editor)
export { AgentScopePanel } from './AgentScopePanel';
export type { AgentScopePanelProps, AutoPopulateResult } from './AgentScopePanel';

// MCP Connection (Phase 67 — Paperclip Integration)
export { MCPConnectionCard } from './MCPConnectionCard';
export type {
  MCPConnectionCardProps,
  MCPStatusData,
  MCPRuntimeStatus,
  MCPInstallResult,
} from './MCPConnectionCard';

// Agent Operations — Config-Only (Unified Surfaces)
export { AgentOpsPanel } from './AgentOpsPanel';
export type { AgentOpsData, AgentOpsPanelProps, EngineStatus } from './AgentOpsPanel';

// Push Settings (Unified Surfaces)
export { PushSettings } from './PushSettings';
export type { PushSettingsData, PushSettingsProps } from './PushSettings';

// ── Components kept for Storybook / future use but NOT rendered in dashboard ──
// AgentCard, AgentOpsDetail, EmployeeBadges, SystemAgentsTab,
// ManagedEmployeesTab, GenerateWizard, ResearchTopicList, CleanupPreview
// Import these directly from their files if needed outside the dashboard.
```

- [ ] **Step 4: Verify build**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck --workspace=packages/ui`
Expected: No type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/agents/AgentOpsPanel.tsx \
       packages/ui/src/components/agents/PushSettings.tsx \
       packages/ui/src/components/agents/index.ts
git commit -m "feat(ui): redesign AgentOpsPanel to config-only, add PushSettings"
```

---

### Task 8: Update Dashboard Hook and Panel Registry

**Files:**
- Modify: `src/prep/dashboard/src/hooks/useAgentOps.ts` (update to match new props)
- Modify: `packages/ui/src/config/panelRegistry.ts:345-354` (update description)

- [ ] **Step 1: Update panelRegistry description**

In `packages/ui/src/config/panelRegistry.ts`, change the `agent-ops` entry (lines 345-354):

```typescript
  {
    id: 'agent-ops',
    title: 'Agent Operations',
    description: 'Configure Prep agent engines (HR, Researcher, Custodian), Paperclip connection, and push settings.',
    icon: Bot,
    minHeight: 4,
    defaultHeight: 6,
    category: 'config',
    closeable: true,
    resizable: true,
  },
```

- [ ] **Step 2: Update useAgentOps hook**

In `src/prep/dashboard/src/hooks/useAgentOps.ts`, update the data shape to match the new `AgentOpsData` interface (with `EngineStatus` containing `last_run` and `push_count` instead of the previous operational counts). The hook should fetch from the existing `/agents/status` endpoint and reshape the response:

```typescript
// Map the API response to the config-only shape
const mapToEngineStatus = (
  apiData: any,
  engine: 'hr' | 'researcher' | 'custodian',
): EngineStatus => ({
  last_run: apiData?.[engine]?.latest_run ?? null,
  push_count: apiData?.[engine]?.push_count ?? 0,
});
```

- [ ] **Step 3: Verify typecheck**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck --workspace=@prep/dashboard`
Expected: No type errors.

- [ ] **Step 4: Commit**

```bash
git add src/prep/dashboard/src/hooks/useAgentOps.ts \
       packages/ui/src/config/panelRegistry.ts
git commit -m "feat(dashboard): update agent-ops hook and panel registry for config-only"
```

---

## Phase 3: Paperclip Plugin UI Enhancement

### Task 9: Enhanced Codebase Health Widget

**Files:**
- Create: `packages/paperclip-plugin-prep/src/ui/CodebaseHealthWidget.tsx` (rewrite)

- [ ] **Step 1: Write the enhanced widget**

```tsx
// packages/paperclip-plugin-prep/src/ui/CodebaseHealthWidget.tsx
/**
 * Codebase Health Widget — Paperclip dashboard widget.
 *
 * Shows: pipeline status, push summary, consensus hotspots, structural delta.
 * Data comes from the codebase-health data provider (extended in worker).
 */
import { usePluginData } from '@paperclipai/plugin-sdk/react';

interface ConsensusEntry {
  file_path: string;
  agents: string[];
  consensus_score: number;
}

interface HubChange {
  path: string;
  change: string;
  dependents_count?: number;
  rank?: number;
}

interface HealthData {
  status: {
    hr: { role_count: number };
    researcher: { run_count: number };
    custodian: { archive_count: number };
  } | null;
  readiness: { score: number } | null;
  push_summary: { total_pushes: number; latest_push_at: number | null } | null;
  consensus: ConsensusEntry[];
  delta: { hub_changes: HubChange[]; module_changes: any[]; is_empty: boolean } | null;
  error?: string;
}

export function CodebaseHealthWidget() {
  const { data, loading } = usePluginData<HealthData>('codebase-health');

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">Loading Prep status...</div>;
  }

  if (data?.error) {
    return (
      <div className="p-4">
        <div className="text-sm text-red-400">Prep daemon unavailable</div>
        <div className="text-xs text-gray-500 mt-1">{data.error}</div>
      </div>
    );
  }

  const pushSummary = data?.push_summary;
  const consensus = data?.consensus ?? [];
  const delta = data?.delta;

  return (
    <div className="p-4 space-y-3">
      <div className="text-sm font-medium">Prep Codebase Health</div>

      {/* Pipeline status */}
      <div className="text-xs text-gray-400">
        <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-1.5" />
        Pipeline healthy
        {data?.readiness && (
          <span className="ml-2">· Readiness: {(data.readiness.score * 100).toFixed(0)}%</span>
        )}
      </div>

      {/* Push summary */}
      {pushSummary && pushSummary.total_pushes > 0 && (
        <div className="text-xs">
          <div className="font-medium text-gray-300 mb-0.5">Recent Pushes</div>
          <div className="text-gray-400">
            {pushSummary.total_pushes} issues pushed
            {pushSummary.latest_push_at && (
              <span className="ml-1">
                · Last: {new Date(pushSummary.latest_push_at * 1000).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Consensus hotspots */}
      {consensus.length > 0 && (
        <div className="text-xs">
          <div className="font-medium text-gray-300 mb-0.5">Consensus Hotspots</div>
          {consensus.slice(0, 3).map((entry) => (
            <div key={entry.file_path} className="flex items-center justify-between py-0.5">
              <span className="text-gray-400 truncate mr-2">{entry.file_path}</span>
              <span className="text-amber-400 shrink-0">
                {entry.agents.length} agents · {entry.consensus_score.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Structural delta */}
      {delta && !delta.is_empty && (
        <div className="text-xs">
          <div className="font-medium text-gray-300 mb-0.5">Structural Delta</div>
          {delta.hub_changes
            .filter((h: HubChange) => h.change === 'new' || h.change === 'removed')
            .slice(0, 3)
            .map((h: HubChange) => (
              <div key={h.path} className="text-gray-400 py-0.5">
                {h.change === 'new' ? '+ New hub: ' : '- Removed hub: '}
                <span className="text-gray-300">{h.path}</span>
                {h.dependents_count != null && (
                  <span className="ml-1">({h.dependents_count} deps)</span>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/paperclip-plugin-prep/src/ui/CodebaseHealthWidget.tsx
git commit -m "feat(plugin): enhanced Codebase Health dashboard widget"
```

---

### Task 10: Enhanced Knowledge Scope Tab

**Files:**
- Create: `packages/paperclip-plugin-prep/src/ui/KnowledgeScopeTab.tsx` (rewrite)

- [ ] **Step 1: Write the enhanced tab**

```tsx
// packages/paperclip-plugin-prep/src/ui/KnowledgeScopeTab.tsx
/**
 * Knowledge Scope Tab — read-only agent scope view in Paperclip.
 *
 * Shows the Prep-configured file scope for this agent,
 * plus any active file claims. Editing happens in Prep dashboard only.
 */
import { usePluginData, useEntityContext } from '@paperclipai/plugin-sdk/react';

interface ScopeData {
  files: string[];
  role: string | null;
  error?: string;
}

interface Claim {
  id: string;
  agent_role: string;
  path: string;
  reason: string;
  expires_at: number;
}

interface ClaimsData {
  claims: Claim[];
  error?: string;
}

export function KnowledgeScopeTab() {
  const entity = useEntityContext();
  const { data: scopeData, loading: scopeLoading } = usePluginData<ScopeData>(
    'agent-knowledge-scope',
    { entityId: entity?.id },
  );
  const { data: claimsData } = usePluginData<ClaimsData>('agent-claims');

  if (scopeLoading) {
    return <div className="p-4 text-sm text-gray-500">Loading knowledge scope...</div>;
  }

  if (scopeData?.error) {
    return (
      <div className="p-4">
        <div className="text-sm text-yellow-400">{scopeData.error}</div>
        <div className="text-xs text-gray-500 mt-2">
          Configure agent scopes in the Prep dashboard (Agent Knowledge Scopes panel).
        </div>
      </div>
    );
  }

  const files = scopeData?.files ?? [];
  const role = scopeData?.role;

  // Filter claims relevant to this agent's scope
  const relevantClaims = (claimsData?.claims ?? []).filter((claim) =>
    files.some((f) => f.startsWith(claim.path) || claim.path.startsWith(f)),
  );

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">
          Knowledge Scope
          {role && <span className="text-gray-400 ml-1">({role})</span>}
        </div>
        <span className="text-xs text-gray-500">{files.length} files</span>
      </div>

      {/* File list */}
      {files.length > 0 ? (
        <div className="space-y-0.5 max-h-64 overflow-y-auto">
          {files.map((file) => (
            <div key={file} className="text-xs text-gray-400 py-0.5 font-mono truncate">
              {file}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-gray-500 italic">
          No files in scope. Configure in Prep dashboard.
        </div>
      )}

      {/* Active claims */}
      {relevantClaims.length > 0 && (
        <div>
          <div className="text-xs font-medium text-amber-400 mb-1">
            Active Claims ({relevantClaims.length})
          </div>
          {relevantClaims.map((claim) => (
            <div key={claim.id} className="text-xs text-gray-400 py-0.5">
              <span className="text-gray-300">{claim.agent_role}</span>
              {' → '}
              <span className="font-mono">{claim.path}</span>
              {claim.reason && (
                <span className="text-gray-500 ml-1">({claim.reason})</span>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="text-[10px] text-gray-600 border-t border-gray-800 pt-2">
        Scope is read-only here. Edit in Prep dashboard → Agent Knowledge Scopes.
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/paperclip-plugin-prep/src/ui/KnowledgeScopeTab.tsx
git commit -m "feat(plugin): enhanced Knowledge Scope tab with claims overlay"
```

---

### Task 11: Enhanced Issue Context Tab

**Files:**
- Create: `packages/paperclip-plugin-prep/src/ui/IssueContextTab.tsx` (rewrite)

- [ ] **Step 1: Write the enhanced tab**

```tsx
// packages/paperclip-plugin-prep/src/ui/IssueContextTab.tsx
/**
 * Issue Context Tab — structural context for Prep-pushed issues.
 *
 * For issues pushed from Prep (has prep-address in description):
 * shows structural complexity, hub involvement, consensus score.
 *
 * For other issues: offers on-demand enrichment.
 */
import { useState } from 'react';
import { useEntityContext, usePluginAction } from '@paperclipai/plugin-sdk/react';

interface IssueEntity {
  id: string;
  title: string;
  description: string;
}

function parsePrepMetadata(description: string): {
  address: string | null;
  isDelta: boolean;
  isConflict: boolean;
} {
  const addressMatch = description.match(/<!-- prep-address:(.*?) -->/);
  return {
    address: addressMatch?.[1] ?? null,
    isDelta: description.includes('<!-- prep-delta:true -->'),
    isConflict: description.includes('<!-- prep-conflict:true -->'),
  };
}

function parseStructuralContext(description: string): {
  complexity: string | null;
  hubFiles: string[];
  modulesSpanned: string[];
  blastRadius: string | null;
} | null {
  if (!description.includes('### Structural Context')) return null;

  const complexityMatch = description.match(/\*\*Complexity:\*\*\s*(\w+)/);
  const hubMatch = description.match(/\*\*Hub files:\*\*\s*(.+)/);
  const modulesMatch = description.match(/\*\*Modules spanned:\*\*\s*(.+)/);
  const blastMatch = description.match(/\*\*Blast radius:\*\*\s*(.+)/);

  return {
    complexity: complexityMatch?.[1] ?? null,
    hubFiles: hubMatch?.[1]?.split(',').map((s) => s.trim()) ?? [],
    modulesSpanned: modulesMatch?.[1]?.split(',').map((s) => s.trim()) ?? [],
    blastRadius: blastMatch?.[1] ?? null,
  };
}

export function IssueContextTab() {
  const entity = useEntityContext() as IssueEntity | null;
  const enrich = usePluginAction('enrich-issue');
  const [enriching, setEnriching] = useState(false);

  if (!entity) {
    return <div className="p-4 text-sm text-gray-500">No issue selected</div>;
  }

  const meta = parsePrepMetadata(entity.description);
  const structural = parseStructuralContext(entity.description);

  // Prep-pushed issue with structural context
  if (meta.address && structural) {
    const tierColor =
      structural.complexity === 'heavyweight' ? 'text-red-400' :
      structural.complexity === 'standard' ? 'text-amber-400' :
      'text-green-400';

    return (
      <div className="p-4 space-y-3">
        <div className="text-sm font-medium">Prep Structural Context</div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-500">Complexity:</span>
            <span className={`ml-1 font-medium ${tierColor}`}>
              {structural.complexity}
            </span>
          </div>
          {structural.blastRadius && (
            <div>
              <span className="text-gray-500">Blast radius:</span>
              <span className="ml-1 text-gray-300">{structural.blastRadius}</span>
            </div>
          )}
        </div>

        {structural.hubFiles.length > 0 && (
          <div className="text-xs">
            <div className="text-gray-500 mb-0.5">Hub files:</div>
            {structural.hubFiles.map((f) => (
              <div key={f} className="text-gray-400 font-mono pl-2">{f}</div>
            ))}
          </div>
        )}

        {structural.modulesSpanned.length > 1 && (
          <div className="text-xs">
            <span className="text-gray-500">Cross-module:</span>
            <span className="text-gray-400 ml-1">
              {structural.modulesSpanned.join(', ')}
            </span>
          </div>
        )}

        {meta.isDelta && (
          <div className="text-[10px] text-blue-400">Structural delta notification</div>
        )}
        {meta.isConflict && (
          <div className="text-[10px] text-amber-400">Agent conflict detected</div>
        )}
      </div>
    );
  }

  // Non-Prep issue — offer enrichment
  return (
    <div className="p-4 space-y-3">
      <div className="text-sm text-gray-500">
        No Prep context for this issue.
      </div>
      <button
        onClick={async () => {
          setEnriching(true);
          try {
            await enrich.run({ issueId: entity.id });
          } finally {
            setEnriching(false);
          }
        }}
        disabled={enriching}
        className="px-3 py-1.5 text-xs font-medium rounded-md
                   bg-blue-500/10 text-blue-400 hover:bg-blue-500/20
                   disabled:opacity-50 transition-colors"
      >
        {enriching ? 'Enriching...' : 'Add Structural Analysis'}
      </button>
      <div className="text-[10px] text-gray-600">
        Runs prep:impact on files mentioned in the issue description.
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/paperclip-plugin-prep/src/ui/IssueContextTab.tsx
git commit -m "feat(plugin): enhanced Issue Context tab with structural analysis"
```

---

### Task 12: Extend Plugin Worker — Data Providers + Actions

**Files:**
- Modify: `packages/paperclip-plugin-prep/src/worker/index.ts:249-304` (extend data providers, add new ones, add action)

- [ ] **Step 1: Extend `codebase-health` data provider**

In the worker's `setup()` function, replace the `codebase-health` data provider registration (around line 251):

```typescript
    ctx.data.register('codebase-health', async () => {
      try {
        const pid = await client.resolveProjectId(config);
        const [status, readiness, pushSummary, consensus, delta] = await Promise.all([
          client.request(`/projects/${pid}/agents/status`),
          client.request(`/projects/${pid}/agents/hr/readiness`),
          client.request(`/projects/${pid}/collaboration/push-summary`).catch(() => null),
          client.request(`/projects/${pid}/collaboration/consensus`).catch(() => ({ scores: [] })),
          client.request(`/projects/${pid}/collaboration/delta`).catch(() => null),
        ]);
        return {
          status,
          readiness,
          push_summary: pushSummary,
          consensus: (consensus as any)?.scores ?? [],
          delta,
        };
      } catch {
        return { status: null, readiness: null, push_summary: null, consensus: [], delta: null, error: 'Prep daemon unavailable' };
      }
    });
```

- [ ] **Step 2: Fix `agent-knowledge-scope` data provider**

Replace the existing `agent-knowledge-scope` registration (around line 264):

```typescript
    ctx.data.register('agent-knowledge-scope', async (input) => {
      try {
        const pid = await client.resolveProjectId(config);
        const agentId = (input as Record<string, unknown>)?.entityId as string;
        if (!agentId) return { files: [], role: null, error: 'No agent selected' };

        // Read role from agent's adapter config (set by Prep push_to_paperclip)
        const agent = await ctx.agents.get(agentId).catch(() => null);
        const roleSlug = (agent as any)?.adapterConfig?.prep_role
          ?? await ctx.state.get({
               scopeKind: 'agent', scopeId: agentId, stateKey: 'role_slug',
             });

        if (!roleSlug) return { files: [], role: null, error: 'No Prep role mapped for this agent' };

        const data = await client.request(`/projects/${pid}/agent-scope/${roleSlug}`);
        return { ...(data as object), role: roleSlug };
      } catch (err) {
        return { files: [], role: null, error: String(err) };
      }
    });
```

- [ ] **Step 3: Add new data providers**

After the existing `agent-claims` data provider (around line 304), add:

```typescript
    ctx.data.register('consensus-hotspots', async () => {
      try {
        const pid = await client.resolveProjectId(config);
        const data = await client.request(`/projects/${pid}/collaboration/consensus`);
        return data;
      } catch (err) {
        return { scores: [], error: String(err) };
      }
    });

    ctx.data.register('push-summary', async () => {
      try {
        const pid = await client.resolveProjectId(config);
        const data = await client.request(`/projects/${pid}/collaboration/push-summary`);
        return data;
      } catch (err) {
        return { total_pushes: 0, latest_push_at: null, error: String(err) };
      }
    });
```

- [ ] **Step 4: Add `enrich-issue` action**

After the existing `run-custodian` action (around line 324), add:

```typescript
    ctx.actions.register('enrich-issue', async (input) => {
      const pid = await client.resolveProjectId(config);
      const p = input as Record<string, unknown>;
      const issueId = p?.issueId as string;
      if (!issueId) return { error: 'No issue ID provided' };

      // Get the issue to extract file paths from description
      const issue = await ctx.issues.get(issueId).catch(() => null);
      if (!issue) return { error: 'Issue not found' };

      // Extract file paths from description (simple heuristic: find paths with extensions)
      const desc = (issue as any).description ?? '';
      const filePaths = desc.match(/[\w/.-]+\.\w{1,10}/g) ?? [];
      const uniquePaths = [...new Set(filePaths)].slice(0, 5);

      if (uniquePaths.length === 0) {
        return { error: 'No file paths found in issue description' };
      }

      // Get context + impact for each file
      const results = await Promise.all(
        uniquePaths.map((file: string) =>
          client.request(`/projects/${pid}/trace/impact`, {
            method: 'POST',
            body: { file },
          }).catch(() => null),
        ),
      );

      return {
        files_analyzed: uniquePaths,
        impact: results.filter(Boolean),
      };
    });
```

- [ ] **Step 5: Update init log**

Change the final log line (around line 356):

```typescript
    ctx.logger.info('Prep plugin initialized — 5 tools, 6 data providers, 3 actions, 1 job');
```

- [ ] **Step 6: Verify build**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep/packages/paperclip-plugin-prep && npm run build`
Expected: Build succeeds (or at minimum `tsc --noEmit` passes if no build script).

- [ ] **Step 7: Commit**

```bash
git add packages/paperclip-plugin-prep/src/worker/index.ts
git commit -m "feat(plugin): extend worker with consensus, push-summary providers and enrich action"
```

---

## Phase 4: Engine Push Wiring

### Task 13: Add `push` Query Param to Agent Endpoints

**Files:**
- Modify: `src/prep/api/routers/agents.py:102-139` (hr_generate), and researcher/custodian endpoints

- [ ] **Step 1: Add push param to HR generate**

In `src/prep/api/routers/agents.py`, modify the `HRGenerateRequest` model (line 45):

```python
class HRGenerateRequest(BaseModel):
    mode: str = "list"
    role_names: List[str] = []
    push: bool = False
```

At the end of `hr_generate()` (after the file collection loop), add:

```python
    # Push to Paperclip if requested
    push_count = 0
    if req.push:
        try:
            from prep.agents.hr.engine import StaffingEngine
            engine_fresh = StaffingEngine(core=core)
            engine_fresh.push_to_paperclip(llm_fn)
            push_count = len(roles)
        except Exception as e:
            logger.warning("[HR API] Push to Paperclip failed: %s", e)

    return ok({
        "mode": req.mode,
        "roles_generated": len(roles),
        "files": file_paths,
        "push_count": push_count,
    })
```

- [ ] **Step 2: Add push param to Researcher run**

Modify `ResearchRunRequest` (line 50):

```python
class ResearchRunRequest(BaseModel):
    max_topics: int = 3
    push: bool = False
```

At the end of the researcher run endpoint, after the research runs, add push logic following the same pattern.

- [ ] **Step 3: Add push param to Custodian run**

Modify `CustodianRunRequest` (line 54):

```python
class CustodianRunRequest(BaseModel):
    dry_run: bool = True
    max_candidates: int = 50
    max_files: int = 20
    push: bool = False
```

- [ ] **Step 4: Commit**

```bash
git add src/prep/api/routers/agents.py
git commit -m "feat(api): add push query param to agent engine endpoints"
```

---

### Task 14: Significance Classification in Engines

**Files:**
- Test: `tests/test_significance.py` (new)

- [ ] **Step 1: Write tests for significance classification**

```python
# tests/test_significance.py
"""Tests for significance classification helpers."""
import pytest

from prep.adapters.pm_models import classify_significance


def test_security_finding_is_mandatory():
    assert classify_significance(
        category="security", consensus_score=0.0, hub_count=0,
    ) == "mandatory"


def test_high_consensus_is_mandatory():
    assert classify_significance(
        category="quality", consensus_score=0.6, hub_count=0,
    ) == "mandatory"


def test_hub_finding_is_recommended():
    assert classify_significance(
        category="quality", consensus_score=0.0, hub_count=1,
    ) == "recommended"


def test_standard_finding_is_recommended():
    assert classify_significance(
        category="quality", consensus_score=0.0, hub_count=0,
    ) == "recommended"


def test_low_confidence_is_informational():
    assert classify_significance(
        category="quality", consensus_score=0.0, hub_count=0,
        confidence="low",
    ) == "informational"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_significance.py -v`
Expected: FAIL — `classify_significance` doesn't exist.

- [ ] **Step 3: Implement `classify_significance` in pm_models.py**

In `src/prep/adapters/pm_models.py`, after `compute_complexity_tier`, add:

```python
def classify_significance(
    category: str = "quality",
    consensus_score: float = 0.0,
    hub_count: int = 0,
    confidence: str = "normal",
) -> str:
    """Classify finding significance: mandatory / recommended / informational.

    Mandatory: security issues, high-consensus (3+ agents, score > 0.5).
    Recommended: standard findings, hub involvement.
    Informational: low-confidence, no structural backing.
    """
    if category == "security":
        return "mandatory"
    if consensus_score > 0.5:
        return "mandatory"
    if confidence == "low":
        return "informational"
    return "recommended"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_significance.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/adapters/pm_models.py tests/test_significance.py
git commit -m "feat(push): add significance classification for engine findings"
```

---

### Task 15: Integrate Enrichment into PushEngine._push_group

**Files:**
- Modify: `src/prep/adapters/push_engine.py:175-260` (enrich in `_push_group`)

- [ ] **Step 1: Add enrichment call in `_push_group`**

In `src/prep/adapters/push_engine.py`, in `_push_group()` (after building the `pm_issue` at line 241, before the dedup check at line 244), add:

```python
        # Structural enrichment (Phase 73.5 Emergence)
        structural_ctx = self._enrich_with_structural_context(
            affected_files=group.affected_files[:20],
            project_id=prep_project_id,
        )
        if structural_ctx:
            pm_issue.structural_context = structural_ctx
            # Append structural context to description
            pm_issue.description += (
                f"\n\n---\n### Structural Context (Prep)\n"
                f"- **Complexity:** {structural_ctx.complexity_tier}\n"
            )
            if structural_ctx.hub_files_involved:
                hub_list = ", ".join(structural_ctx.hub_files_involved[:5])
                pm_issue.description += (
                    f"- **Hub files:** {hub_list}\n"
                    f"- **Blast radius:** {structural_ctx.total_dependents} total dependents\n"
                )
            if structural_ctx.cross_module:
                mod_list = ", ".join(structural_ctx.modules_spanned[:5])
                pm_issue.description += f"- **Modules spanned:** {mod_list}\n"
```

- [ ] **Step 2: Add consensus enrichment**

After the structural enrichment block, add consensus enrichment:

```python
        # Consensus enrichment
        if prep_project_id:
            try:
                from prep.services.observation_store import observation_store
                consensus = observation_store.get_consensus_scores(
                    prep_project_id, min_agents=2, since_days=30,
                )
                # Check if any affected files are in consensus hotspots
                affected_set = set(group.affected_files)
                matching = [
                    c for c in consensus
                    if c["file_path"] in affected_set
                ]
                if matching:
                    best = max(matching, key=lambda c: c["consensus_score"])
                    agents_str = ", ".join(best["agents"])
                    pm_issue.description += (
                        f"\n**Consensus:** {best['agent_count']}/{best['total_active_agents']} "
                        f"agents independently flagged files in this area "
                        f"({agents_str})\n"
                    )
            except Exception:
                pass  # Consensus is best-effort
```

- [ ] **Step 3: Run all push-related tests**

Run: `.venv/bin/pytest tests/test_structural_enrichment.py tests/test_delta_push.py tests/test_consensus_scoring.py -v`
Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add src/prep/adapters/push_engine.py
git commit -m "feat(push): integrate structural + consensus enrichment into push pipeline"
```

---

## Summary

| Phase | Tasks | New files | Modified files | Tests |
|-------|-------|-----------|----------------|-------|
| 1: Backend | 1-6 | 5 test files | 4 Python files | ~25 |
| 2: Dashboard | 7-8 | 1 component | 4 files | typecheck |
| 3: Plugin UI | 9-12 | 3 components | 1 worker file | build check |
| 4: Wiring | 13-15 | 1 test file | 2 Python files | ~5 |

**Total: 15 tasks, 10 new files, 13 modified files, ~30 tests.**

Phases 1 and 2 are independent after Task 6 — they can run in parallel.
Phase 3 depends on Phase 1 (data providers need the new endpoints).
Phase 4 depends on Tasks 2-3 (significance classification and enrichment).
