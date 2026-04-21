# Agent Collaboration Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Prep's agents (Pi, Researcher, Custodian, Staffing) awareness of each other's work and coordination primitives to avoid stepping on each other, exposed as MCP resources and prompts.

**Architecture:** New `src/prep/services/collaboration/` package with 5 modules behind a `CollaborationHub` facade. The hub lives in the daemon (FastAPI side) with direct SQLite access. New FastAPI routes expose collaboration data via REST. The MCP server accesses collaboration data via HTTP proxy (same pattern as all existing MCP resource handlers). Agent engines access the hub through `AgentCore.collab`.

**Tech Stack:** Python 3.11, SQLite (WAL mode, shared `prep_settings.db`), FastAPI, Pydantic, pytest (asyncio_mode="auto"), httpx (MCP server HTTP proxy).

**Spec:** `docs/superpowers/specs/2026-04-06-agent-collaboration-infrastructure-design.md`
**Issues to fix from scrutiny:** `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/next_steps.md` (Section 2)

---

## File Structure

**New files (16):**

| File | Responsibility |
|---|---|
| `src/prep/services/collaboration/__init__.py` | `CollaborationHub` facade — composes all sub-stores, single init with db_path |
| `src/prep/services/collaboration/activity.py` | `ActivityStore` + `ActivityEntry` — append-only agent action log, time-range queries, auto-prune |
| `src/prep/services/collaboration/snapshots.py` | `GraphSnapshotStore` + `GraphSnapshot` + `StructuralDelta` — persist graph state, diff two snapshots (hubs + modules only, no cycles/cross-cutting per Issue 1+2) |
| `src/prep/services/collaboration/conflicts.py` | `ConflictStore` + `ConflictDetector` + `AgentConflict` — two detection strategies: observation-level (same file, different agents) and push-level (contradictory ActionItem categories) per Issue 8 |
| `src/prep/services/collaboration/claims.py` | `ClaimStore` + `SoftClaim` — soft file claims with TTL, prefix matching, lazy expiry cleanup |
| `src/prep/api/routers/collaboration.py` | FastAPI routes for collaboration data — activity, delta, conflicts, claims, observations-by-agent (per Issue 6: daemon owns all data) |
| `src/prep/mcp/collaboration_handlers.py` | MCP resource content generators + prompt handlers — calls daemon via `server._api_get()` (per Issue 6) |
| `tests/test_activity_store.py` | Unit tests for ActivityStore |
| `tests/test_graph_snapshots.py` | Unit tests for GraphSnapshotStore + delta computation |
| `tests/test_conflict_store.py` | Unit tests for ConflictStore + ConflictDetector |
| `tests/test_claim_store.py` | Unit tests for ClaimStore |
| `tests/test_observation_attribution.py` | Tests for created_by + visibility in ObservationStore |
| `tests/test_collaboration_hub.py` | Integration tests for CollaborationHub |
| `tests/test_collab_api.py` | Tests for FastAPI collaboration routes |
| `tests/test_collab_resources.py` | Tests for MCP resource content generators |
| `tests/test_collab_prompts.py` | Tests for MCP prompt handlers |

**Modified files (11):**

| File | Changes |
|---|---|
| `src/prep/services/observation_store.py` | Add `created_by` + `visibility` columns, extend `save()`, add `get_by_agent()`, schema migration |
| `src/prep/agents/shared/prep_data.py:237-259` | Add `created_by` + `visibility` params to `save_observation()` (Issue 9) |
| `src/prep/agents/core.py:38-44,97-114` | Add `collab_hub` param to `__init__`, add `created_by` to `save_observation()` |
| `src/prep/services/pi_agent.py:60-68,1118-1145` | Add `collab_hub` param to `__init__`+`init_pi_agent()` (Issue 3), add `scenario` to `_save_observation()`, add activity logging |
| `src/prep/agents/researcher/engine.py:38-54` | Pass `created_by="researcher"` via `self._core`, add activity logging, add claim creation |
| `src/prep/agents/custodian/engine.py:28-47` | Pass `created_by="custodian"` via `self._core`, add activity logging, add claim checking |
| `src/prep/adapters/push_engine.py:35-51,280-295` | Add `conflict_detector`+`conflict_store` params (Issue 4), add detection in `push()` |
| `src/prep/adapters/pm_models.py:84-96` | Add `conflicts` field to `PushResult` |
| `src/prep/mcp_tools.py:698-736` | Add `created_by` to `prep_save_observation` schema |
| `src/prep/mcp/server.py:2092-2184,2360-2400` | 4 thin integration points: extend resource list, delegate resource read, extend prompt list, delegate prompt get |
| `src/prep/server.py:549-590` | Import + register collaboration router, init CollaborationHub |

---

## Phase A: Foundation

### Task 1: Observation Store — Add `created_by` + `visibility` Columns

**Files:**
- Modify: `src/prep/services/observation_store.py`
- Test: `tests/test_observation_attribution.py`

- [ ] **Step 1: Write the failing test for `save()` with `created_by`**

```python
# tests/test_observation_attribution.py
"""Tests for observation attribution (created_by + visibility)."""
import sqlite3
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


def test_save_with_created_by(store):
    obs_id = store.save("proj-1", "Auth uses JWT", created_by="researcher")
    obs = store.get_for_query("proj-1", "JWT")
    assert len(obs) >= 1
    match = [o for o in obs if o.id == obs_id]
    assert len(match) == 1
    assert match[0].created_by == "researcher"


def test_save_without_created_by_defaults_to_none(store):
    obs_id = store.save("proj-1", "Legacy observation")
    obs = store.get_for_query("proj-1", "Legacy")
    match = [o for o in obs if o.id == obs_id]
    assert len(match) == 1
    assert match[0].created_by is None


def test_save_with_visibility(store):
    obs_id = store.save("proj-1", "Private note", created_by="researcher", visibility="private")
    obs = store.get_for_query("proj-1", "Private")
    match = [o for o in obs if o.id == obs_id]
    assert len(match) == 1
    assert match[0].visibility == "private"


def test_visibility_defaults_to_shared(store):
    obs_id = store.save("proj-1", "Default visibility")
    obs = store.get_for_query("proj-1", "Default visibility")
    match = [o for o in obs if o.id == obs_id]
    assert len(match) == 1
    assert match[0].visibility == "shared"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_observation_attribution.py -v`
Expected: FAIL — `save()` doesn't accept `created_by` or `visibility` params, `Observation` has no `created_by` attribute.

- [ ] **Step 3: Add columns to Observation dataclass and schema**

In `src/prep/services/observation_store.py`, add to the `Observation` dataclass (after `stale_reason` field, around line 65):

```python
    created_by: Optional[str] = None
    visibility: str = "shared"
```

In `_create_tables()` (after line 172, after `conn.commit()`), add migration:

```python
        # Phase 73.5: Add collaboration columns (safe to run repeatedly)
        for col, default in [("created_by", "NULL"), ("visibility", "'shared'")]:
            try:
                self._conn.execute(
                    f"ALTER TABLE observations ADD COLUMN {col} TEXT DEFAULT {default}"
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists
```

In `from_row()` (around line 89), add with fallback for rows without the new columns:

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
        )
```

- [ ] **Step 4: Extend `save()` to accept new params**

In `save()` (around line 183), add params to signature:

```python
    def save(
        self,
        project_id: str,
        content: str,
        file_path: Optional[str] = None,
        symbol_fqn: Optional[str] = None,
        trace_node_id: Optional[str] = None,
        category: str = "note",
        created_by: Optional[str] = None,
        visibility: str = "shared",
    ) -> str:
```

Update the INSERT statement (around line 230):

```python
            conn.execute(
                """INSERT INTO observations
                   (id, project_id, content, file_path, symbol_fqn,
                    trace_node_id, category, created_at, stale,
                    created_by, visibility)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (obs_id, project_id, content, file_path, symbol_fqn,
                 trace_node_id, category, now, created_by, visibility),
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_observation_attribution.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/observation_store.py tests/test_observation_attribution.py
git commit -m "feat(collab): add created_by + visibility columns to observation store"
```

---

### Task 2: Observation Store — Add `get_by_agent()` Query Method

**Files:**
- Modify: `src/prep/services/observation_store.py`
- Test: `tests/test_observation_attribution.py`

- [ ] **Step 1: Write failing tests for `get_by_agent()`**

Append to `tests/test_observation_attribution.py`:

```python
def test_get_by_agent_filters_by_created_by(store):
    store.save("proj-1", "Researcher note 1", created_by="researcher")
    store.save("proj-1", "Custodian note 1", created_by="custodian")
    store.save("proj-1", "Researcher note 2", created_by="researcher")

    results = store.get_by_agent("proj-1", "researcher")
    assert len(results) == 2
    assert all(o.created_by == "researcher" for o in results)


def test_get_by_agent_excludes_stale_by_default(store):
    obs_id = store.save("proj-1", "Stale note", created_by="researcher")
    store.mark_stale_batch("proj-1", [None], reason="test")  # marks all
    # Save a fresh one
    store.save("proj-1", "Fresh note", created_by="researcher")

    results = store.get_by_agent("proj-1", "researcher", include_stale=False)
    assert all(not o.stale for o in results)


def test_get_by_agent_visibility_filter(store):
    store.save("proj-1", "Shared note", created_by="researcher", visibility="shared")
    store.save("proj-1", "Private note", created_by="researcher", visibility="private")

    shared = store.get_by_agent("proj-1", "researcher", visibility_filter="shared")
    assert len(shared) == 1
    assert shared[0].content == "Shared note"


def test_get_by_agent_respects_limit(store):
    for i in range(10):
        store.save("proj-1", f"Note {i}", created_by="researcher")

    results = store.get_by_agent("proj-1", "researcher", limit=3)
    assert len(results) == 3


def test_get_by_agent_empty_for_unknown_agent(store):
    store.save("proj-1", "Some note", created_by="researcher")
    results = store.get_by_agent("proj-1", "unknown_agent")
    assert len(results) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_observation_attribution.py::test_get_by_agent_filters_by_created_by -v`
Expected: FAIL — `get_by_agent` doesn't exist.

- [ ] **Step 3: Implement `get_by_agent()`**

Add to `ObservationStore` class (after `get_for_query`, around line 300):

```python
    def get_by_agent(
        self,
        project_id: str,
        created_by: str,
        include_stale: bool = False,
        visibility_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[Observation]:
        """Return observations created by a specific agent role.

        Args:
            project_id: Project ID.
            created_by: Agent role identifier (e.g. "researcher", "pi/watchdog").
            include_stale: If False (default), exclude stale observations.
            visibility_filter: If set, only return observations with this visibility.
            limit: Maximum results.
        """
        conn = self._require_conn()
        conditions = ["project_id = ?", "created_by = ?"]
        params: list = [project_id, created_by]

        if not include_stale:
            conditions.append("stale = 0")

        if visibility_filter:
            conditions.append("visibility = ?")
            params.append(visibility_filter)

        where = " AND ".join(conditions)
        params.append(limit)

        with self._lock:
            rows = conn.execute(
                f"SELECT * FROM observations WHERE {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [Observation.from_row(r) for r in rows]
```

- [ ] **Step 4: Run all attribution tests**

Run: `.venv/bin/pytest tests/test_observation_attribution.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/observation_store.py tests/test_observation_attribution.py
git commit -m "feat(collab): add get_by_agent() query method to observation store"
```

---

### Task 3: Wire `created_by` Through PrepDataAccess and AgentCore

**Files:**
- Modify: `src/prep/agents/shared/prep_data.py:237-259`
- Modify: `src/prep/agents/core.py:97-114`

This task fixes Issue 9 — the intermediate layer that drops `created_by`.

- [ ] **Step 1: Update `PrepDataAccess.save_observation()`**

In `src/prep/agents/shared/prep_data.py`, update the `save_observation` method (around line 237):

```python
    def save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        category: str = "note",
        created_by: Optional[str] = None,
        visibility: str = "shared",
    ) -> str:
        """Persist an agent observation and return its ID.

        Args:
            content: Observation text (max 2000 chars, will be truncated).
            file_path: Optional source file this observation relates to.
            category: One of ``note``, ``decision``, ``bug``, ``pattern``,
                ``assumption``.
            created_by: Agent role identifier (e.g. 'researcher', 'pi/watchdog').
            visibility: 'shared', 'private', or 'internal'.

        Returns:
            Observation UUID string.
        """
        return self._observation_store.save(
            self._project_id,
            content,
            file_path=file_path,
            category=category,
            created_by=created_by,
            visibility=visibility,
        )
```

- [ ] **Step 2: Update `AgentCore.save_observation()`**

In `src/prep/agents/core.py`, update the `save_observation` method (around line 97):

```python
    def save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        category: str = "note",
        created_by: Optional[str] = None,
        visibility: str = "shared",
    ) -> str:
        """Persist an agent observation and return its ID.

        Args:
            content: Observation text.
            file_path: Optional source file this observation relates to.
            category: One of ``note``, ``decision``, ``bug``, ``pattern``,
                ``assumption``.
            created_by: Agent role identifier (e.g. 'researcher', 'pi/watchdog').
            visibility: 'shared', 'private', or 'internal'.

        Returns:
            Observation UUID string.
        """
        return self._data.save_observation(
            content, file_path=file_path, category=category,
            created_by=created_by, visibility=visibility,
        )
```

- [ ] **Step 3: Add `collab` attribute to AgentCore**

In `src/prep/agents/core.py`, update `__init__` (around line 38):

```python
    def __init__(
        self,
        project_id: str,
        index_dir: Path,
        project_root: Optional[Path] = None,
        pm_config: Optional[PMPushConfig] = None,
        collab_hub: Optional[Any] = None,
    ) -> None:
        self.project_id = project_id
        self._data = PrepDataAccess(index_dir, project_root, project_id)
        self._paperclip = PaperclipClient(pm_config) if pm_config and pm_config.enabled else None
        self._git = GitClient(project_root) if project_root else None
        self.collab = collab_hub
```

- [ ] **Step 4: Run existing tests to confirm no regressions**

Run: `.venv/bin/pytest tests/ -k "observation" -v --timeout=30`
Expected: All existing observation tests still pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/agents/shared/prep_data.py src/prep/agents/core.py
git commit -m "feat(collab): wire created_by + visibility through PrepDataAccess and AgentCore"
```

---

### Task 4: ActivityStore

**Files:**
- Create: `src/prep/services/collaboration/__init__.py`
- Create: `src/prep/services/collaboration/activity.py`
- Test: `tests/test_activity_store.py`

- [ ] **Step 1: Create the package `__init__.py`**

```python
# src/prep/services/collaboration/__init__.py
"""Agent Collaboration Infrastructure — Phase 73.5.

Provides cross-agent awareness, coordination, and conflict detection.
All stores share the prep_settings.db SQLite database.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


class CollaborationHub:
    """Single entry point for all collaboration infrastructure.

    Initialized once by the daemon. Agent engines, API routers,
    and MCP handlers access collaboration features through this hub.
    """

    def __init__(self, db_path: Path) -> None:
        from prep.services.collaboration.activity import ActivityStore

        self.activity = ActivityStore(db_path)
```

- [ ] **Step 2: Write failing tests for ActivityStore**

```python
# tests/test_activity_store.py
"""Tests for ActivityStore — append-only agent action log."""
import time

import pytest

from prep.services.collaboration.activity import ActivityStore, ActivityEntry


@pytest.fixture
def store(tmp_path):
    s = ActivityStore(tmp_path / "test.db")
    yield s
    s.close()


def test_log_returns_id(store):
    entry_id = store.log("proj-1", "pi/watchdog", "delta_scan", "3 new findings")
    assert isinstance(entry_id, str)
    assert len(entry_id) > 0


def test_get_recent_returns_logged_entries(store):
    store.log("proj-1", "pi/watchdog", "delta_scan", "3 new findings")
    store.log("proj-1", "researcher", "topic_selection", "Selected auth topic")

    entries = store.get_recent("proj-1")
    assert len(entries) == 2
    assert entries[0].agent_role in ("pi/watchdog", "researcher")


def test_get_recent_ordered_by_time_desc(store):
    store.log("proj-1", "pi/watchdog", "scan_1", "First")
    time.sleep(0.01)
    store.log("proj-1", "researcher", "scan_2", "Second")

    entries = store.get_recent("proj-1")
    assert entries[0].summary == "Second"
    assert entries[1].summary == "First"


def test_get_recent_respects_limit(store):
    for i in range(10):
        store.log("proj-1", "pi/watchdog", f"scan_{i}", f"Entry {i}")

    entries = store.get_recent("proj-1", limit=3)
    assert len(entries) == 3


def test_get_recent_since_filters_by_time(store):
    store.log("proj-1", "pi/watchdog", "old_scan", "Old entry")
    cutoff = time.time()
    time.sleep(0.01)
    store.log("proj-1", "pi/watchdog", "new_scan", "New entry")

    entries = store.get_recent("proj-1", since=cutoff)
    assert len(entries) == 1
    assert entries[0].summary == "New entry"


def test_get_recent_isolates_projects(store):
    store.log("proj-1", "pi/watchdog", "scan", "Project 1")
    store.log("proj-2", "pi/watchdog", "scan", "Project 2")

    entries = store.get_recent("proj-1")
    assert len(entries) == 1
    assert entries[0].summary == "Project 1"


def test_log_with_details(store):
    store.log("proj-1", "pi/watchdog", "delta_scan", "Summary",
              details={"new": 3, "resolved": 1})

    entries = store.get_recent("proj-1")
    assert entries[0].details == {"new": 3, "resolved": 1}


def test_prune_removes_old_entries(store):
    # Log an entry, then prune with max_age_days=0 to remove it
    store.log("proj-1", "pi/watchdog", "scan", "Old entry")
    time.sleep(0.01)

    pruned = store.prune("proj-1", max_age_days=0)
    assert pruned >= 1

    entries = store.get_recent("proj-1")
    assert len(entries) == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_activity_store.py -v`
Expected: FAIL — module `prep.services.collaboration.activity` does not exist.

- [ ] **Step 4: Implement ActivityStore**

```python
# src/prep/services/collaboration/activity.py
"""ActivityStore — append-only agent action log.

Records what agents do and when. Queryable by time range.
Auto-prunes entries older than 30 days.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_ENTRIES_BEFORE_PRUNE = 1000


@dataclass
class ActivityEntry:
    """A single agent action record."""

    id: str
    project_id: str
    agent_role: str
    action: str
    summary: str
    details: Optional[Dict[str, Any]] = None
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "project_id": self.project_id,
            "agent_role": self.agent_role,
            "action": self.action,
            "summary": self.summary,
            "created_at": self.created_at,
        }
        if self.details:
            d["details"] = self.details
        return d


class ActivityStore:
    """SQLite-backed append-only agent activity log."""

    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False, isolation_level="DEFERRED",
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_activity (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                action TEXT NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_activity_project_time
                ON agent_activity(project_id, created_at DESC);
        """)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def log(
        self,
        project_id: str,
        agent_role: str,
        action: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Append an activity entry. Returns the entry ID."""
        entry_id = uuid.uuid4().hex[:12]
        now = time.time()
        details_json = json.dumps(details) if details else None

        with self._lock:
            self._conn.execute(
                """INSERT INTO agent_activity
                   (id, project_id, agent_role, action, summary, details_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (entry_id, project_id, agent_role, action, summary, details_json, now),
            )
            self._conn.commit()

            # Lazy prune when table gets large
            count = self._conn.execute(
                "SELECT COUNT(*) FROM agent_activity WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            if count > MAX_ENTRIES_BEFORE_PRUNE:
                self._prune_locked(project_id, max_age_days=30)

        return entry_id

    def get_recent(
        self,
        project_id: str,
        limit: int = 50,
        since: Optional[float] = None,
    ) -> List[ActivityEntry]:
        """Return recent activity entries, newest first."""
        conditions = ["project_id = ?"]
        params: list = [project_id]

        if since is not None:
            conditions.append("created_at > ?")
            params.append(since)

        where = " AND ".join(conditions)
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM agent_activity WHERE {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._row_to_entry(r) for r in rows]

    def prune(self, project_id: str, max_age_days: int = 30) -> int:
        """Remove entries older than max_age_days. Returns count deleted."""
        with self._lock:
            return self._prune_locked(project_id, max_age_days)

    def _prune_locked(self, project_id: str, max_age_days: int) -> int:
        cutoff = time.time() - (max_age_days * 86400)
        cur = self._conn.execute(
            "DELETE FROM agent_activity WHERE project_id = ? AND created_at < ?",
            (project_id, cutoff),
        )
        self._conn.commit()
        return cur.rowcount

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> ActivityEntry:
        details = None
        if row["details_json"]:
            try:
                details = json.loads(row["details_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        return ActivityEntry(
            id=row["id"],
            project_id=row["project_id"],
            agent_role=row["agent_role"],
            action=row["action"],
            summary=row["summary"],
            details=details,
            created_at=row["created_at"],
        )
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_activity_store.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/collaboration/__init__.py src/prep/services/collaboration/activity.py tests/test_activity_store.py
git commit -m "feat(collab): add ActivityStore — append-only agent action log"
```

---

### Task 5: ClaimStore

**Files:**
- Create: `src/prep/services/collaboration/claims.py`
- Test: `tests/test_claim_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_claim_store.py
"""Tests for ClaimStore — soft file claims with auto-expiry."""
import time

import pytest

from prep.services.collaboration.claims import ClaimStore, SoftClaim


@pytest.fixture
def store(tmp_path):
    s = ClaimStore(tmp_path / "test.db")
    yield s
    s.close()


def test_claim_returns_id(store):
    claim_id = store.claim("proj-1", "researcher", "src/auth/login.py", "Researching auth")
    assert isinstance(claim_id, str)
    assert len(claim_id) > 0


def test_is_claimed_exact_path(store):
    store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    assert store.is_claimed("proj-1", "src/auth/login.py") is True
    assert store.is_claimed("proj-1", "src/other.py") is False


def test_is_claimed_directory_prefix(store):
    store.claim("proj-1", "researcher", "src/auth/", "Research")
    assert store.is_claimed("proj-1", "src/auth/login.py") is True
    assert store.is_claimed("proj-1", "src/auth/session.py") is True
    assert store.is_claimed("proj-1", "src/other.py") is False


def test_is_claimed_exclude_agent(store):
    store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    assert store.is_claimed("proj-1", "src/auth/login.py", exclude_agent="researcher") is False
    assert store.is_claimed("proj-1", "src/auth/login.py", exclude_agent="custodian") is True


def test_release_claim(store):
    claim_id = store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    assert store.is_claimed("proj-1", "src/auth/login.py") is True

    result = store.release(claim_id)
    assert result is True
    assert store.is_claimed("proj-1", "src/auth/login.py") is False


def test_expired_claims_not_active(store):
    store.claim("proj-1", "researcher", "src/auth/login.py", "Research", ttl=0.0)
    time.sleep(0.01)

    assert store.is_claimed("proj-1", "src/auth/login.py") is False


def test_get_active_excludes_expired(store):
    store.claim("proj-1", "researcher", "src/old.py", "Old", ttl=0.0)
    time.sleep(0.01)
    store.claim("proj-1", "researcher", "src/new.py", "New", ttl=86400)

    active = store.get_active("proj-1")
    paths = [c.path for c in active]
    assert "src/new.py" in paths
    assert "src/old.py" not in paths


def test_cleanup_expired(store):
    store.claim("proj-1", "researcher", "src/old.py", "Old", ttl=0.0)
    time.sleep(0.01)

    cleaned = store.cleanup_expired("proj-1")
    assert cleaned >= 1


def test_get_claims_for_path(store):
    store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    store.claim("proj-1", "custodian", "src/auth/login.py", "Cleanup check")

    claims = store.get_claims_for_path("proj-1", "src/auth/login.py")
    assert len(claims) == 2
    roles = {c.agent_role for c in claims}
    assert roles == {"researcher", "custodian"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_claim_store.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement ClaimStore**

```python
# src/prep/services/collaboration/claims.py
"""ClaimStore — soft file claims with auto-expiry.

Agents declare active interest in files/directories. Other agents
check claims before modifying the same area. Claims auto-expire
after a configurable TTL (default 24 hours).
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SoftClaim:
    """An agent's deprep-compresstion of active interest in a file or directory."""

    id: str
    project_id: str
    agent_role: str
    path: str
    reason: str
    claimed_at: float
    expires_at: float


class ClaimStore:
    """SQLite-backed soft claim store with lazy expiry cleanup."""

    DEFAULT_TTL = 86400.0  # 24 hours

    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False, isolation_level="DEFERRED",
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS soft_claims (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                path TEXT NOT NULL,
                reason TEXT,
                claimed_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_claims_project_path
                ON soft_claims(project_id, path);
        """)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def claim(
        self,
        project_id: str,
        agent_role: str,
        path: str,
        reason: str,
        ttl: float = DEFAULT_TTL,
    ) -> str:
        """Create a soft claim on a file or directory. Returns claim ID."""
        claim_id = uuid.uuid4().hex[:12]
        now = time.time()
        expires_at = now + ttl

        with self._lock:
            # Lazy cleanup
            self._cleanup_expired_locked(project_id)

            self._conn.execute(
                """INSERT INTO soft_claims
                   (id, project_id, agent_role, path, reason, claimed_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (claim_id, project_id, agent_role, path, reason, now, expires_at),
            )
            self._conn.commit()

        return claim_id

    def release(self, claim_id: str) -> bool:
        """Release a claim. Returns True if it existed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM soft_claims WHERE id = ?", (claim_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def is_claimed(
        self,
        project_id: str,
        path: str,
        exclude_agent: Optional[str] = None,
    ) -> bool:
        """Check if a path is claimed (exact match or directory prefix)."""
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                """SELECT agent_role, path FROM soft_claims
                   WHERE project_id = ? AND expires_at > ?""",
                (project_id, now),
            ).fetchall()

        for row in rows:
            if exclude_agent and row["agent_role"] == exclude_agent:
                continue
            claim_path = row["path"]
            # Exact match
            if claim_path == path:
                return True
            # Directory prefix: claim on "src/auth/" covers "src/auth/login.py"
            if claim_path.endswith("/") and path.startswith(claim_path):
                return True
        return False

    def get_claims_for_path(
        self, project_id: str, path: str,
    ) -> List[SoftClaim]:
        """Get all active claims that cover a specific path."""
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM soft_claims
                   WHERE project_id = ? AND expires_at > ?""",
                (project_id, now),
            ).fetchall()

        results = []
        for row in rows:
            claim_path = row["path"]
            if claim_path == path or (claim_path.endswith("/") and path.startswith(claim_path)):
                results.append(self._row_to_claim(row))
        return results

    def get_active(self, project_id: str) -> List[SoftClaim]:
        """Get all active (non-expired) claims for a project."""
        now = time.time()
        with self._lock:
            self._cleanup_expired_locked(project_id)
            rows = self._conn.execute(
                """SELECT * FROM soft_claims
                   WHERE project_id = ? AND expires_at > ?
                   ORDER BY claimed_at DESC""",
                (project_id, now),
            ).fetchall()

        return [self._row_to_claim(r) for r in rows]

    def cleanup_expired(self, project_id: str) -> int:
        """Remove expired claims. Returns count deleted."""
        with self._lock:
            return self._cleanup_expired_locked(project_id)

    def _cleanup_expired_locked(self, project_id: str) -> int:
        now = time.time()
        cur = self._conn.execute(
            "DELETE FROM soft_claims WHERE project_id = ? AND expires_at <= ?",
            (project_id, now),
        )
        self._conn.commit()
        return cur.rowcount

    @staticmethod
    def _row_to_claim(row: sqlite3.Row) -> SoftClaim:
        return SoftClaim(
            id=row["id"],
            project_id=row["project_id"],
            agent_role=row["agent_role"],
            path=row["path"],
            reason=row["reason"],
            claimed_at=row["claimed_at"],
            expires_at=row["expires_at"],
        )
```

- [ ] **Step 4: Update `CollaborationHub` to include ClaimStore**

In `src/prep/services/collaboration/__init__.py`, update:

```python
class CollaborationHub:
    """Single entry point for all collaboration infrastructure."""

    def __init__(self, db_path: Path) -> None:
        from prep.services.collaboration.activity import ActivityStore
        from prep.services.collaboration.claims import ClaimStore

        self.activity = ActivityStore(db_path)
        self.claims = ClaimStore(db_path)
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_claim_store.py -v`
Expected: All 10 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/collaboration/claims.py src/prep/services/collaboration/__init__.py tests/test_claim_store.py
git commit -m "feat(collab): add ClaimStore — soft file claims with auto-expiry"
```

---

### Task 6: GraphSnapshotStore

**Files:**
- Create: `src/prep/services/collaboration/snapshots.py`
- Test: `tests/test_graph_snapshots.py`

Note: Per Issues 1+2, this captures **hubs + modules only** — no cycles or cross-cutting data (no structured source exists).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_graph_snapshots.py
"""Tests for GraphSnapshotStore — persist + diff graph state."""
import time

import pytest

from prep.services.collaboration.snapshots import (
    GraphSnapshotStore, GraphSnapshot, StructuralDelta,
)


@pytest.fixture
def store(tmp_path):
    s = GraphSnapshotStore(tmp_path / "test.db")
    yield s
    s.close()


HUBS_V1 = [
    {"path": "src/config.py", "dependents_count": 20, "rank": 1},
    {"path": "src/utils.py", "dependents_count": 15, "rank": 2},
    {"path": "src/auth.py", "dependents_count": 10, "rank": 3},
]

MODULES_V1 = [
    {"name": "core", "file_count": 12, "domain_tags": ["backend", "api"]},
    {"name": "auth", "file_count": 5, "domain_tags": ["security"]},
]

HUBS_V2 = [
    {"path": "src/config.py", "dependents_count": 22, "rank": 1},
    {"path": "src/gateway.py", "dependents_count": 18, "rank": 2},  # NEW
    {"path": "src/utils.py", "dependents_count": 15, "rank": 3},    # rank changed
    # src/auth.py REMOVED from hubs
]

MODULES_V2 = [
    {"name": "core", "file_count": 12, "domain_tags": ["backend", "api"]},
    {"name": "auth", "file_count": 3, "domain_tags": ["security"]},  # size changed
    {"name": "gateway", "file_count": 4, "domain_tags": ["api"]},     # NEW
]


def test_capture_returns_id(store):
    snap_id = store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    assert isinstance(snap_id, str)


def test_get_latest_returns_most_recent(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V2, modules=MODULES_V2)

    latest = store.get_latest("proj-1")
    assert latest is not None
    assert len(latest.hubs) == len(HUBS_V2)


def test_get_latest_returns_none_when_empty(store):
    assert store.get_latest("proj-1") is None


def test_compute_delta_detects_new_hub(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    before = time.time()
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V2, modules=MODULES_V2)

    delta = store.compute_delta("proj-1", since=before)
    new_hubs = [h for h in delta.hub_changes if h["change"] == "new"]
    assert any(h["path"] == "src/gateway.py" for h in new_hubs)


def test_compute_delta_detects_removed_hub(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    before = time.time()
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V2, modules=MODULES_V2)

    delta = store.compute_delta("proj-1", since=before)
    removed = [h for h in delta.hub_changes if h["change"] == "removed"]
    assert any(h["path"] == "src/auth.py" for h in removed)


def test_compute_delta_detects_new_module(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    before = time.time()
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V2, modules=MODULES_V2)

    delta = store.compute_delta("proj-1", since=before)
    new_mods = [m for m in delta.module_changes if m["change"] == "new"]
    assert any(m["name"] == "gateway" for m in new_mods)


def test_compute_delta_empty_when_no_changes(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    before = time.time()
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)

    delta = store.compute_delta("proj-1", since=before)
    assert delta.is_empty


def test_compute_delta_no_snapshots(store):
    delta = store.compute_delta("proj-1", since=0.0)
    assert delta.is_empty


def test_prune_keeps_recent(store):
    for i in range(15):
        store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
        time.sleep(0.01)

    pruned = store.prune("proj-1", keep=5)
    assert pruned == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_graph_snapshots.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement GraphSnapshotStore**

```python
# src/prep/services/collaboration/snapshots.py
"""GraphSnapshotStore — persist graph state and compute structural deltas.

Captures hub files and module structure at index rebuild time.
Diffs two snapshots to produce a StructuralDelta showing what changed.

Note: Cycles and cross-cutting concerns are NOT captured — no structured
data source exists for these yet (see Issue 1+2 in next_steps.md).
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GraphSnapshot:
    """Lightweight graph state for delta computation."""

    id: str
    project_id: str
    hubs: List[Dict[str, Any]]
    modules: List[Dict[str, Any]]
    created_at: float


@dataclass
class StructuralDelta:
    """Result of diffing two graph snapshots."""

    since: float
    until: float
    hub_changes: List[Dict[str, Any]] = field(default_factory=list)
    module_changes: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.hub_changes and not self.module_changes


class GraphSnapshotStore:
    """SQLite-backed graph snapshot store."""

    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False, isolation_level="DEFERRED",
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS graph_snapshots (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshot_project_time
                ON graph_snapshots(project_id, created_at DESC);
        """)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def capture(
        self,
        project_id: str,
        hubs: List[Dict[str, Any]],
        modules: List[Dict[str, Any]],
    ) -> str:
        """Capture current graph state. Returns snapshot ID."""
        snap_id = uuid.uuid4().hex[:12]
        now = time.time()
        payload = json.dumps({"hubs": hubs, "modules": modules})

        with self._lock:
            self._conn.execute(
                """INSERT INTO graph_snapshots (id, project_id, snapshot_json, created_at)
                   VALUES (?, ?, ?, ?)""",
                (snap_id, project_id, payload, now),
            )
            self._conn.commit()

        return snap_id

    def get_latest(self, project_id: str) -> Optional[GraphSnapshot]:
        """Return the most recent snapshot, or None."""
        with self._lock:
            row = self._conn.execute(
                """SELECT * FROM graph_snapshots
                   WHERE project_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id,),
            ).fetchone()

        if not row:
            return None
        return self._row_to_snapshot(row)

    def compute_delta(self, project_id: str, since: float) -> StructuralDelta:
        """Diff the snapshot closest to `since` against the latest snapshot."""
        with self._lock:
            # Find snapshot closest to (but before or at) `since`
            old_row = self._conn.execute(
                """SELECT * FROM graph_snapshots
                   WHERE project_id = ? AND created_at <= ?
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id, since),
            ).fetchone()

            # Latest snapshot
            new_row = self._conn.execute(
                """SELECT * FROM graph_snapshots
                   WHERE project_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id,),
            ).fetchone()

        if not old_row or not new_row:
            return StructuralDelta(since=since, until=time.time())

        old_snap = self._row_to_snapshot(old_row)
        new_snap = self._row_to_snapshot(new_row)

        # Same snapshot — no delta
        if old_snap.id == new_snap.id:
            return StructuralDelta(since=since, until=new_snap.created_at)

        hub_changes = self._diff_hubs(old_snap.hubs, new_snap.hubs)
        module_changes = self._diff_modules(old_snap.modules, new_snap.modules)

        return StructuralDelta(
            since=old_snap.created_at,
            until=new_snap.created_at,
            hub_changes=hub_changes,
            module_changes=module_changes,
        )

    def prune(self, project_id: str, keep: int = 10) -> int:
        """Keep only the N most recent snapshots. Returns count deleted."""
        with self._lock:
            # Find the created_at of the Nth most recent
            row = self._conn.execute(
                """SELECT created_at FROM graph_snapshots
                   WHERE project_id = ?
                   ORDER BY created_at DESC
                   LIMIT 1 OFFSET ?""",
                (project_id, keep),
            ).fetchone()

            if not row:
                return 0

            cutoff = row["created_at"]
            cur = self._conn.execute(
                """DELETE FROM graph_snapshots
                   WHERE project_id = ? AND created_at < ?""",
                (project_id, cutoff),
            )
            self._conn.commit()
            return cur.rowcount

    @staticmethod
    def _diff_hubs(
        old_hubs: List[Dict[str, Any]],
        new_hubs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        old_by_path = {h["path"]: h for h in old_hubs}
        new_by_path = {h["path"]: h for h in new_hubs}
        changes: List[Dict[str, Any]] = []

        # New hubs
        for path in new_by_path:
            if path not in old_by_path:
                h = new_by_path[path]
                changes.append({
                    "path": path, "change": "new",
                    "dependents_count": h.get("dependents_count", 0),
                    "rank": h.get("rank", 0),
                })

        # Removed hubs
        for path in old_by_path:
            if path not in new_by_path:
                changes.append({"path": path, "change": "removed"})

        # Rank changes (>1 position shift)
        for path in new_by_path:
            if path in old_by_path:
                old_rank = old_by_path[path].get("rank", 0)
                new_rank = new_by_path[path].get("rank", 0)
                if abs(old_rank - new_rank) > 1:
                    changes.append({
                        "path": path, "change": "rank_changed",
                        "old_rank": old_rank, "new_rank": new_rank,
                    })

        return changes

    @staticmethod
    def _diff_modules(
        old_modules: List[Dict[str, Any]],
        new_modules: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        old_by_name = {m["name"]: m for m in old_modules}
        new_by_name = {m["name"]: m for m in new_modules}
        changes: List[Dict[str, Any]] = []

        for name in new_by_name:
            if name not in old_by_name:
                m = new_by_name[name]
                changes.append({
                    "name": name, "change": "new",
                    "file_count": m.get("file_count", 0),
                })

        for name in old_by_name:
            if name not in new_by_name:
                changes.append({"name": name, "change": "removed"})

        for name in new_by_name:
            if name in old_by_name:
                old_count = old_by_name[name].get("file_count", 0)
                new_count = new_by_name[name].get("file_count", 0)
                if old_count > 0 and abs(new_count - old_count) / old_count > 0.2:
                    changes.append({
                        "name": name, "change": "size_changed",
                        "old_file_count": old_count, "new_file_count": new_count,
                    })

        return changes

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> GraphSnapshot:
        data = json.loads(row["snapshot_json"])
        return GraphSnapshot(
            id=row["id"],
            project_id=row["project_id"],
            hubs=data.get("hubs", []),
            modules=data.get("modules", []),
            created_at=row["created_at"],
        )
```

- [ ] **Step 4: Update CollaborationHub**

In `src/prep/services/collaboration/__init__.py`:

```python
class CollaborationHub:
    """Single entry point for all collaboration infrastructure."""

    def __init__(self, db_path: Path) -> None:
        from prep.services.collaboration.activity import ActivityStore
        from prep.services.collaboration.claims import ClaimStore
        from prep.services.collaboration.snapshots import GraphSnapshotStore

        self.activity = ActivityStore(db_path)
        self.claims = ClaimStore(db_path)
        self.snapshots = GraphSnapshotStore(db_path)
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_graph_snapshots.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/collaboration/snapshots.py src/prep/services/collaboration/__init__.py tests/test_graph_snapshots.py
git commit -m "feat(collab): add GraphSnapshotStore — persist graph state + compute structural deltas"
```

---

### Task 7: ConflictStore + ConflictDetector

**Files:**
- Create: `src/prep/services/collaboration/conflicts.py`
- Test: `tests/test_conflict_store.py`

Per Issue 8: two detection strategies — observation-level (same file, different agents) and push-level (contradictory ActionItem categories).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_conflict_store.py
"""Tests for ConflictStore + ConflictDetector."""
import time

import pytest

from prep.services.collaboration.conflicts import (
    AgentConflict, ConflictDetector, ConflictStore,
)


@pytest.fixture
def store(tmp_path):
    s = ConflictStore(tmp_path / "test.db")
    yield s
    s.close()


def test_save_and_get_active(store):
    conflict = AgentConflict(
        id="c1", project_id="proj-1", file_path="src/auth.py",
        agent_a="researcher", agent_a_assessment="Important pattern",
        agent_b="custodian", agent_b_assessment="Dead code",
        conflict_type="contradictory", detected_at=time.time(),
    )
    store.save(conflict)

    active = store.get_active("proj-1")
    assert len(active) == 1
    assert active[0].file_path == "src/auth.py"
    assert active[0].resolution == "deferred"


def test_resolve_conflict(store):
    conflict = AgentConflict(
        id="c1", project_id="proj-1", file_path="src/auth.py",
        agent_a="researcher", agent_a_assessment="Important",
        agent_b="custodian", agent_b_assessment="Dead code",
        detected_at=time.time(),
    )
    store.save(conflict)

    result = store.resolve("c1", "agent_a_wins")
    assert result is True

    active = store.get_active("proj-1")
    assert len(active) == 0


def test_get_active_excludes_resolved(store):
    for i, res in enumerate(["deferred", "agent_a_wins", "deferred"]):
        c = AgentConflict(
            id=f"c{i}", project_id="proj-1", file_path=f"src/file{i}.py",
            agent_a="researcher", agent_a_assessment="A",
            agent_b="custodian", agent_b_assessment="B",
            resolution=res, detected_at=time.time(),
        )
        store.save(c)

    active = store.get_active("proj-1")
    assert len(active) == 2


# ── ConflictDetector tests ──────────────────────────────────────

def test_detect_from_observations_same_file_different_agents():
    from prep.services.observation_store import Observation

    obs_list = [
        Observation(id="o1", project_id="proj-1", content="Important pattern",
                    file_path="src/auth.py", created_by="researcher", created_at=1.0),
        Observation(id="o2", project_id="proj-1", content="Dead code candidate",
                    file_path="src/auth.py", created_by="custodian", created_at=2.0),
        Observation(id="o3", project_id="proj-1", content="Unrelated",
                    file_path="src/other.py", created_by="researcher", created_at=3.0),
    ]

    detector = ConflictDetector()
    conflicts = detector.detect_from_observations("proj-1", obs_list)

    assert len(conflicts) == 1
    assert conflicts[0].file_path == "src/auth.py"
    assert {conflicts[0].agent_a, conflicts[0].agent_b} == {"researcher", "custodian"}


def test_detect_no_conflict_same_agent():
    from prep.services.observation_store import Observation

    obs_list = [
        Observation(id="o1", project_id="proj-1", content="Note 1",
                    file_path="src/auth.py", created_by="researcher", created_at=1.0),
        Observation(id="o2", project_id="proj-1", content="Note 2",
                    file_path="src/auth.py", created_by="researcher", created_at=2.0),
    ]

    detector = ConflictDetector()
    conflicts = detector.detect_from_observations("proj-1", obs_list)
    assert len(conflicts) == 0


def test_detect_no_conflict_no_file_path():
    from prep.services.observation_store import Observation

    obs_list = [
        Observation(id="o1", project_id="proj-1", content="Note 1",
                    created_by="researcher", created_at=1.0),
        Observation(id="o2", project_id="proj-1", content="Note 2",
                    created_by="custodian", created_at=2.0),
    ]

    detector = ConflictDetector()
    conflicts = detector.detect_from_observations("proj-1", obs_list)
    assert len(conflicts) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_conflict_store.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement ConflictStore + ConflictDetector**

```python
# src/prep/services/collaboration/conflicts.py
"""ConflictStore + ConflictDetector — cross-agent disagreement detection.

Two detection strategies:
1. Observation-level: Same file_path, different created_by agents (proximity signal).
2. Push-level: Same root_file in ConsolidatedGroups with contradictory ActionItem
   categories (semantic signal). Push-level is called from PushEngine.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from prep.services.observation_store import Observation

logger = logging.getLogger(__name__)


@dataclass
class AgentConflict:
    """A disagreement between two agents about the same file."""

    id: str
    project_id: str
    file_path: str
    agent_a: str
    agent_a_assessment: str
    agent_b: str
    agent_b_assessment: str
    conflict_type: str = "contradictory"
    resolution: str = "deferred"
    detected_at: float = 0.0
    resolved_at: Optional[float] = None


class ConflictStore:
    """SQLite-backed conflict store."""

    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False, isolation_level="DEFERRED",
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_conflicts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                agent_a TEXT NOT NULL,
                agent_a_assessment TEXT NOT NULL,
                agent_b TEXT NOT NULL,
                agent_b_assessment TEXT NOT NULL,
                conflict_type TEXT NOT NULL DEFAULT 'contradictory',
                resolution TEXT DEFAULT 'deferred',
                detected_at REAL NOT NULL,
                resolved_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_conflicts_project
                ON agent_conflicts(project_id, resolution);
        """)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def save(self, conflict: AgentConflict) -> str:
        """Persist a conflict. Returns the conflict ID."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO agent_conflicts
                   (id, project_id, file_path, agent_a, agent_a_assessment,
                    agent_b, agent_b_assessment, conflict_type, resolution,
                    detected_at, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (conflict.id, conflict.project_id, conflict.file_path,
                 conflict.agent_a, conflict.agent_a_assessment,
                 conflict.agent_b, conflict.agent_b_assessment,
                 conflict.conflict_type, conflict.resolution,
                 conflict.detected_at, conflict.resolved_at),
            )
            self._conn.commit()
        return conflict.id

    def get_active(self, project_id: str) -> List[AgentConflict]:
        """Return unresolved conflicts."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM agent_conflicts
                   WHERE project_id = ? AND resolution = 'deferred'
                   ORDER BY detected_at DESC""",
                (project_id,),
            ).fetchall()
        return [self._row_to_conflict(r) for r in rows]

    def resolve(self, conflict_id: str, resolution: str) -> bool:
        """Resolve a conflict. Returns True if it existed."""
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                """UPDATE agent_conflicts
                   SET resolution = ?, resolved_at = ?
                   WHERE id = ?""",
                (resolution, now, conflict_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    @staticmethod
    def _row_to_conflict(row: sqlite3.Row) -> AgentConflict:
        return AgentConflict(
            id=row["id"],
            project_id=row["project_id"],
            file_path=row["file_path"],
            agent_a=row["agent_a"],
            agent_a_assessment=row["agent_a_assessment"],
            agent_b=row["agent_b"],
            agent_b_assessment=row["agent_b_assessment"],
            conflict_type=row["conflict_type"],
            resolution=row["resolution"],
            detected_at=row["detected_at"],
            resolved_at=row["resolved_at"],
        )


class ConflictDetector:
    """Detects contradictions between agent observations about the same files.

    Observation-level strategy: Two different agents with observations on the
    same file_path is a potential conflict (proximity signal). The content of
    both observations is surfaced for human review.
    """

    def detect_from_observations(
        self, project_id: str, observations: List[Observation],
    ) -> List[AgentConflict]:
        """Detect conflicts from attributed observations.

        Groups observations by file_path. If two or more distinct agents have
        observations on the same file, that's a potential conflict.
        """
        # Group by file_path
        by_file: Dict[str, Dict[str, List[Observation]]] = defaultdict(lambda: defaultdict(list))
        for obs in observations:
            if obs.file_path and obs.created_by:
                by_file[obs.file_path][obs.created_by].append(obs)

        conflicts: List[AgentConflict] = []
        for file_path, agents in by_file.items():
            agent_names = list(agents.keys())
            if len(agent_names) < 2:
                continue

            # Create a conflict for each pair of agents on the same file
            for i in range(len(agent_names)):
                for j in range(i + 1, len(agent_names)):
                    a_name = agent_names[i]
                    b_name = agent_names[j]
                    a_obs = agents[a_name][-1]  # most recent
                    b_obs = agents[b_name][-1]

                    conflicts.append(AgentConflict(
                        id=uuid.uuid4().hex[:12],
                        project_id=project_id,
                        file_path=file_path,
                        agent_a=a_name,
                        agent_a_assessment=a_obs.content[:200],
                        agent_b=b_name,
                        agent_b_assessment=b_obs.content[:200],
                        conflict_type="contradictory",
                        detected_at=time.time(),
                    ))

        return conflicts
```

- [ ] **Step 4: Update CollaborationHub**

In `src/prep/services/collaboration/__init__.py`:

```python
class CollaborationHub:
    """Single entry point for all collaboration infrastructure."""

    def __init__(self, db_path: Path) -> None:
        from prep.services.collaboration.activity import ActivityStore
        from prep.services.collaboration.claims import ClaimStore
        from prep.services.collaboration.conflicts import ConflictStore
        from prep.services.collaboration.snapshots import GraphSnapshotStore

        self.activity = ActivityStore(db_path)
        self.claims = ClaimStore(db_path)
        self.conflicts = ConflictStore(db_path)
        self.snapshots = GraphSnapshotStore(db_path)
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_conflict_store.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/collaboration/conflicts.py src/prep/services/collaboration/__init__.py tests/test_conflict_store.py
git commit -m "feat(collab): add ConflictStore + ConflictDetector — cross-agent disagreement detection"
```

---

### Task 8: CollaborationHub Integration Test

**Files:**
- Test: `tests/test_collaboration_hub.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_collaboration_hub.py
"""Integration tests for CollaborationHub — cross-store workflows."""
import time

import pytest

from prep.services.collaboration import CollaborationHub


@pytest.fixture
def hub(tmp_path):
    h = CollaborationHub(tmp_path / "test.db")
    yield h


def test_hub_initializes_all_stores(hub):
    assert hub.activity is not None
    assert hub.claims is not None
    assert hub.conflicts is not None
    assert hub.snapshots is not None


def test_claim_then_detect_conflict_workflow(hub):
    """Researcher claims a file, custodian observes on same file = conflict potential."""
    # Researcher claims
    hub.claims.claim("proj-1", "researcher", "src/auth.py", "Researching auth")

    # Custodian checks claim
    assert hub.claims.is_claimed("proj-1", "src/auth.py", exclude_agent="custodian")

    # Log the custodian's check as activity
    hub.activity.log("proj-1", "custodian", "claim_check",
                     "Skipped src/auth.py — claimed by researcher")

    entries = hub.activity.get_recent("proj-1")
    assert len(entries) == 1
    assert "claimed by researcher" in entries[0].summary


def test_snapshot_then_delta_workflow(hub):
    """Capture two snapshots, compute delta."""
    hubs_v1 = [{"path": "src/a.py", "dependents_count": 10, "rank": 1}]
    mods_v1 = [{"name": "core", "file_count": 5, "domain_tags": []}]

    hub.snapshots.capture("proj-1", hubs=hubs_v1, modules=mods_v1)
    before = time.time()
    time.sleep(0.01)

    hubs_v2 = [
        {"path": "src/a.py", "dependents_count": 10, "rank": 1},
        {"path": "src/b.py", "dependents_count": 8, "rank": 2},
    ]
    hub.snapshots.capture("proj-1", hubs=hubs_v2, modules=mods_v1)

    delta = hub.snapshots.compute_delta("proj-1", since=before)
    assert not delta.is_empty
    new_hubs = [h for h in delta.hub_changes if h["change"] == "new"]
    assert any(h["path"] == "src/b.py" for h in new_hubs)
```

- [ ] **Step 2: Run integration tests**

Run: `.venv/bin/pytest tests/test_collaboration_hub.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_collaboration_hub.py
git commit -m "test(collab): add integration tests for CollaborationHub cross-store workflows"
```

---

## Phase B: Awareness Resources + MCP Integration

### Task 9: FastAPI Collaboration Router

**Files:**
- Create: `src/prep/api/routers/collaboration.py`
- Test: `tests/test_collab_api.py`

This is the daemon-side REST API (Issue 6 fix). The MCP server will call these endpoints.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_collab_api.py
"""Tests for FastAPI collaboration routes."""
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI

from prep.api.routers.collaboration import router, _get_hub, _get_obs_store


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app, tmp_path):
    from prep.services.collaboration import CollaborationHub
    from prep.services.observation_store import ObservationStore

    hub = CollaborationHub(tmp_path / "test.db")
    obs = ObservationStore()
    obs.init(tmp_path / "test.db")

    app.dependency_overrides[_get_hub] = lambda: hub
    app.dependency_overrides[_get_obs_store] = lambda: obs

    with TestClient(app) as c:
        yield c, hub, obs

    obs.close()


def test_get_activity_empty(client):
    c, hub, obs = client
    resp = c.get("/projects/proj-1/collaboration/activity")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["entries"] == []


def test_get_activity_with_entries(client):
    c, hub, obs = client
    hub.activity.log("proj-1", "pi/watchdog", "scan", "Test scan")

    resp = c.get("/projects/proj-1/collaboration/activity")
    assert resp.status_code == 200
    entries = resp.json()["data"]["entries"]
    assert len(entries) == 1
    assert entries[0]["agent_role"] == "pi/watchdog"


def test_get_observations_by_agent(client):
    c, hub, obs = client
    obs.save("proj-1", "Researcher note", created_by="researcher")
    obs.save("proj-1", "Custodian note", created_by="custodian")

    resp = c.get("/projects/proj-1/collaboration/observations?created_by=researcher")
    assert resp.status_code == 200
    entries = resp.json()["data"]["observations"]
    assert len(entries) == 1
    assert entries[0]["created_by"] == "researcher"


def test_get_delta_no_snapshots(client):
    c, hub, obs = client
    resp = c.get("/projects/proj-1/collaboration/delta")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_empty"] is True


def test_get_conflicts_empty(client):
    c, hub, obs = client
    resp = c.get("/projects/proj-1/collaboration/conflicts")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["conflicts"] == []


def test_get_claims_empty(client):
    c, hub, obs = client
    resp = c.get("/projects/proj-1/collaboration/claims")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["claims"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_collab_api.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the router**

```python
# src/prep/api/routers/collaboration.py
"""FastAPI routes for agent collaboration data.

Exposes activity, delta, conflicts, claims, and agent-filtered observations.
The MCP server calls these endpoints via HTTP proxy.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query

from prep.api.envelope import ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["collaboration"])


def _get_hub():
    """Dependency: get the CollaborationHub singleton."""
    from prep.services.collaboration import get_collaboration_hub
    hub = get_collaboration_hub()
    if hub is None:
        from prep.api.envelope import ApiException
        raise ApiException(503, "COLLAB_NOT_READY", "Collaboration hub not initialized")
    return hub


def _get_obs_store():
    """Dependency: get the observation store singleton."""
    from prep.services.observation_store import observation_store
    return observation_store


@router.get("/projects/{project_id}/collaboration/activity")
async def get_activity(
    project_id: str,
    limit: int = Query(50, le=200),
    since: Optional[float] = None,
    hub=Depends(_get_hub),
):
    entries = hub.activity.get_recent(project_id, limit=limit, since=since)
    return ok({"entries": [e.to_dict() for e in entries]})


@router.get("/projects/{project_id}/collaboration/observations")
async def get_observations_by_agent(
    project_id: str,
    created_by: str = Query(...),
    limit: int = Query(50, le=200),
    visibility: Optional[str] = None,
    obs_store=Depends(_get_obs_store),
):
    results = obs_store.get_by_agent(
        project_id, created_by,
        visibility_filter=visibility,
        limit=limit,
    )
    return ok({"observations": [o.to_dict() for o in results]})


@router.get("/projects/{project_id}/collaboration/delta")
async def get_delta(
    project_id: str,
    since: Optional[float] = None,
    hub=Depends(_get_hub),
):
    if since is None:
        since = time.time() - 7 * 86400  # default: 7 days
    delta = hub.snapshots.compute_delta(project_id, since=since)
    return ok({
        "since": delta.since,
        "until": delta.until,
        "hub_changes": delta.hub_changes,
        "module_changes": delta.module_changes,
        "is_empty": delta.is_empty,
    })


@router.get("/projects/{project_id}/collaboration/conflicts")
async def get_conflicts(
    project_id: str,
    hub=Depends(_get_hub),
):
    conflicts = hub.conflicts.get_active(project_id)
    return ok({"conflicts": [
        {
            "id": c.id, "file_path": c.file_path,
            "agent_a": c.agent_a, "agent_a_assessment": c.agent_a_assessment,
            "agent_b": c.agent_b, "agent_b_assessment": c.agent_b_assessment,
            "conflict_type": c.conflict_type,
            "resolution": c.resolution, "detected_at": c.detected_at,
        }
        for c in conflicts
    ]})


@router.post("/projects/{project_id}/collaboration/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    project_id: str,
    conflict_id: str,
    resolution: str = Query(...),
    hub=Depends(_get_hub),
):
    result = hub.conflicts.resolve(conflict_id, resolution)
    return ok({"resolved": result})


@router.get("/projects/{project_id}/collaboration/claims")
async def get_claims(
    project_id: str,
    hub=Depends(_get_hub),
):
    claims = hub.claims.get_active(project_id)
    return ok({"claims": [
        {
            "id": c.id, "agent_role": c.agent_role,
            "path": c.path, "reason": c.reason,
            "claimed_at": c.claimed_at, "expires_at": c.expires_at,
        }
        for c in claims
    ]})


@router.post("/projects/{project_id}/collaboration/claims")
async def create_claim(
    project_id: str,
    agent_role: str = Query(...),
    path: str = Query(...),
    reason: str = Query(""),
    hub=Depends(_get_hub),
):
    claim_id = hub.claims.claim(project_id, agent_role, path, reason)
    return ok({"id": claim_id})


@router.delete("/projects/{project_id}/collaboration/claims/{claim_id}")
async def release_claim(
    project_id: str,
    claim_id: str,
    hub=Depends(_get_hub),
):
    result = hub.claims.release(claim_id)
    return ok({"released": result})
```

- [ ] **Step 4: Add hub singleton to collaboration `__init__.py`**

Add to `src/prep/services/collaboration/__init__.py`:

```python
# Module-level singleton (initialized by daemon startup)
_hub: Optional[CollaborationHub] = None


def init_collaboration(db_path: Path) -> CollaborationHub:
    """Initialize the collaboration hub singleton. Called by daemon startup."""
    global _hub
    _hub = CollaborationHub(db_path)
    return _hub


def get_collaboration_hub() -> Optional[CollaborationHub]:
    """Return the hub singleton, or None if not initialized."""
    return _hub
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_collab_api.py -v`
Expected: All 6 tests PASS (may need adjusting the test fixture to match the dependency injection pattern — fix as needed).

- [ ] **Step 6: Commit**

```bash
git add src/prep/api/routers/collaboration.py src/prep/services/collaboration/__init__.py tests/test_collab_api.py
git commit -m "feat(collab): add FastAPI collaboration router — activity, delta, conflicts, claims endpoints"
```

---

### Task 10: MCP Collaboration Handlers (Resources)

**Files:**
- Create: `src/prep/mcp/collaboration_handlers.py`
- Test: `tests/test_collab_resources.py`

These handlers call the daemon HTTP API via `server._api_get()` — they do NOT access SQLite directly (Issue 6).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_collab_resources.py
"""Tests for MCP collaboration resource content generators."""
import pytest

from prep.mcp.collaboration_handlers import (
    get_collaboration_resources,
    format_activity_resource,
    format_memory_resource,
    format_delta_resource,
    format_conflicts_resource,
    parse_collaboration_uri,
)


def test_get_collaboration_resources_returns_5():
    resources = get_collaboration_resources("proj-1")
    assert len(resources) == 5
    uris = {r["uri"] for r in resources}
    assert "prep://proj-1/activity" in uris
    assert "prep://proj-1/conflicts" in uris


def test_parse_uri_activity():
    result = parse_collaboration_uri("activity")
    assert result == ("activity", {})


def test_parse_uri_memory_with_role():
    result = parse_collaboration_uri("memory/researcher")
    assert result == ("memory", {"role": "researcher"})


def test_parse_uri_agent_findings():
    result = parse_collaboration_uri("agents/custodian/findings")
    assert result == ("agent_findings", {"role": "custodian"})


def test_parse_uri_unknown():
    result = parse_collaboration_uri("structure")
    assert result is None


def test_format_activity_empty():
    md = format_activity_resource([])
    assert "No recent activity" in md


def test_format_activity_with_entries():
    entries = [
        {"agent_role": "pi/watchdog", "action": "delta_scan",
         "summary": "3 new findings", "created_at": 1712400000.0},
    ]
    md = format_activity_resource(entries)
    assert "pi/watchdog" in md
    assert "3 new findings" in md


def test_format_memory_empty():
    md = format_memory_resource("researcher", [])
    assert "No observations" in md


def test_format_delta_empty():
    delta = {"is_empty": True, "hub_changes": [], "module_changes": []}
    md = format_delta_resource(delta)
    assert "No structural changes" in md


def test_format_conflicts_empty():
    md = format_conflicts_resource([])
    assert "No active conflicts" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_collab_resources.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement collaboration_handlers.py**

```python
# src/prep/mcp/collaboration_handlers.py
"""MCP resource content generators + prompt handlers for collaboration.

All data is fetched from the daemon HTTP API via server._api_get().
This file contains NO direct SQLite access.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Resource Registration ──────────────────────────────────────

def get_collaboration_resources(project_id: str) -> List[Dict[str, Any]]:
    """Return resource descriptors for collaboration resources."""
    pid = project_id
    return [
        {
            "uri": f"prep://{pid}/memory/{{role}}",
            "name": "Agent Memory",
            "description": "An agent's own prior observations, filtered by role. Replace {role} with agent name (e.g. researcher, pi/watchdog).",
            "mimeType": "text/markdown",
        },
        {
            "uri": f"prep://{pid}/agents/{{role}}/findings",
            "name": "Cross-Agent Findings",
            "description": "Another agent's recent findings. Replace {role} with agent name.",
            "mimeType": "text/markdown",
        },
        {
            "uri": f"prep://{pid}/activity",
            "name": "Agent Activity Feed",
            "description": "Chronological timeline of all agent actions across the team.",
            "mimeType": "text/markdown",
        },
        {
            "uri": f"prep://{pid}/delta",
            "name": "Structural Delta",
            "description": "What changed structurally in the codebase graph in the last 7 days.",
            "mimeType": "text/markdown",
        },
        {
            "uri": f"prep://{pid}/conflicts",
            "name": "Agent Conflicts",
            "description": "Active disagreements between agents about the same files.",
            "mimeType": "text/markdown",
        },
    ]


# ── URI Parsing ──────────────────────────────────────────────

def parse_collaboration_uri(resource_type: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """Parse a collaboration resource URI path into (name, params).

    Args:
        resource_type: Everything after prep://{pid}/ (e.g. "memory/researcher").

    Returns:
        (resource_name, params) or None if not a collaboration resource.
    """
    if resource_type == "activity":
        return ("activity", {})
    if resource_type == "delta":
        return ("delta", {})
    if resource_type == "conflicts":
        return ("conflicts", {})
    if resource_type.startswith("memory/"):
        role = resource_type[len("memory/"):]
        if role:
            return ("memory", {"role": role})
    if resource_type.startswith("agents/") and resource_type.endswith("/findings"):
        # agents/{role}/findings
        middle = resource_type[len("agents/"):-len("/findings")]
        if middle:
            return ("agent_findings", {"role": middle})
    return None


# ── Content Formatters ──────────────────────────────────────

def format_activity_resource(entries: List[Dict[str, Any]]) -> str:
    """Format activity entries as markdown."""
    if not entries:
        return "## Agent Activity\n\nNo recent activity recorded."

    lines = [f"## Agent Activity ({len(entries)} entries)\n"]
    lines.append("| Time | Agent | Action | Summary |")
    lines.append("|---|---|---|---|")

    for e in entries:
        ts = e.get("created_at", 0)
        time_str = datetime.datetime.fromtimestamp(ts).strftime("%H:%M") if ts else "?"
        lines.append(
            f"| {time_str} | {e.get('agent_role', '?')} "
            f"| {e.get('action', '?')} | {e.get('summary', '')} |"
        )
    return "\n".join(lines)


def format_memory_resource(role: str, observations: List[Dict[str, Any]]) -> str:
    """Format per-role memory as markdown."""
    if not observations:
        return f"## {role.title()} Memory\n\nNo observations from this agent."

    lines = [f"## {role.title()} Memory ({len(observations)} observations)\n"]
    for obs in observations:
        ts = obs.get("created_at", 0)
        date_str = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "?"
        content = obs.get("content", "")
        file_path = obs.get("file_path", "")
        category = obs.get("category", "note")

        lines.append(f"- [{date_str}] {content}")
        if file_path:
            lines.append(f"  File: {file_path} | Category: {category}")
    return "\n".join(lines)


def format_delta_resource(delta: Dict[str, Any]) -> str:
    """Format structural delta as markdown."""
    if delta.get("is_empty", True):
        return "## Structural Delta\n\nNo structural changes detected."

    lines = ["## Structural Delta\n"]

    hub_changes = delta.get("hub_changes", [])
    if hub_changes:
        lines.append("### Hub Changes")
        for h in hub_changes:
            change = h.get("change", "?")
            path = h.get("path", "?")
            if change == "new":
                deps = h.get("dependents_count", 0)
                rank = h.get("rank", "?")
                lines.append(f"- **NEW:** {path} ({deps} dependents) — rank #{rank}")
            elif change == "removed":
                lines.append(f"- **REMOVED:** {path}")
            elif change == "rank_changed":
                lines.append(
                    f"- **RANK CHANGE:** {path} — "
                    f"#{h.get('old_rank', '?')} -> #{h.get('new_rank', '?')}"
                )
        lines.append("")

    mod_changes = delta.get("module_changes", [])
    if mod_changes:
        lines.append("### Module Changes")
        for m in mod_changes:
            change = m.get("change", "?")
            name = m.get("name", "?")
            if change == "new":
                lines.append(f"- **NEW:** {name} ({m.get('file_count', 0)} files)")
            elif change == "removed":
                lines.append(f"- **REMOVED:** {name}")
            elif change == "size_changed":
                lines.append(
                    f"- **SIZE CHANGE:** {name} — "
                    f"{m.get('old_file_count', '?')} -> {m.get('new_file_count', '?')} files"
                )

    return "\n".join(lines)


def format_conflicts_resource(conflicts: List[Dict[str, Any]]) -> str:
    """Format active conflicts as markdown."""
    if not conflicts:
        return "## Agent Conflicts\n\nNo active conflicts."

    lines = [f"## Active Agent Conflicts ({len(conflicts)} unresolved)\n"]
    for i, c in enumerate(conflicts, 1):
        lines.append(f"### {i}. {c.get('file_path', '?')}")
        lines.append(f"- **{c.get('agent_a', '?')}**: \"{c.get('agent_a_assessment', '')}\"")
        lines.append(f"- **{c.get('agent_b', '?')}**: \"{c.get('agent_b_assessment', '')}\"")
        lines.append(f"- **Type:** {c.get('conflict_type', '?')} | **Status:** {c.get('resolution', '?')}")
        lines.append("")

    return "\n".join(lines)


# ── Prompt Definitions ──────────────────────────────────────

def get_collaboration_prompts() -> List[Dict[str, Any]]:
    """Return prompt descriptors for collaboration prompts."""
    return [
        {
            "name": "prep-handoff",
            "description": "Transfer context from one agent to another — packages prior work, findings, and structural data",
            "arguments": [
                {"name": "from_role", "description": "Agent role handing off (e.g. 'researcher')", "required": True},
                {"name": "to_role", "description": "Agent role receiving (e.g. 'custodian')", "required": True},
                {"name": "task", "description": "Optional task context for the handoff", "required": False},
            ],
        },
        {
            "name": "prep-scope",
            "description": "Show what an agent role owns — modules, recent changes, open findings",
            "arguments": [
                {"name": "role", "description": "Agent role to scope (e.g. 'researcher')", "required": True},
            ],
        },
        {
            "name": "prep-triage",
            "description": "Triage agent findings — cluster by root cause, flag conflicts, suggest assignments",
            "arguments": [
                {"name": "focus", "description": "Optional area to focus triage on", "required": False},
            ],
        },
    ]


def get_collaboration_prompt_messages(
    name: str, arguments: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """Return prompt messages for a collaboration prompt, or None if not a collab prompt."""
    if name == "prep-handoff":
        from_role = arguments.get("from_role", "previous agent")
        to_role = arguments.get("to_role", "you")
        task = arguments.get("task", "")
        task_line = f"\nTask context: {task}\n" if task else ""
        return {
            "description": f"Handoff from {from_role} to {to_role}",
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"You are taking over a task from the {from_role} agent.{task_line}\n"
                        f"1. Review what {from_role} found — check @prep://memory/{from_role} "
                        f"for their observations and @prep://agents/{from_role}/findings for findings.\n"
                        f"2. Check @prep://activity for recent agent actions to understand the timeline.\n"
                        f"3. Check @prep://conflicts for any disagreements that need resolution.\n"
                        f"4. Call `prep_search` to deepen your understanding of the relevant code areas.\n"
                        f"5. Continue the work: summarize what you're picking up and your next steps."
                    ),
                },
            }],
        }

    elif name == "prep-scope":
        role = arguments.get("role", "agent")
        return {
            "description": f"Scope overview for {role}",
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Show me what the {role} agent owns and what's happening in their domain.\n\n"
                        f"1. Call `prep` for the structural overview, focusing on modules relevant to {role}.\n"
                        f"2. Check @prep://memory/{role} for the agent's recent observations.\n"
                        f"3. Check @prep://delta for structural changes that affect {role}'s scope.\n"
                        f"4. Check @prep://conflicts for any disputes involving {role}.\n"
                        f"5. Summarize: what modules does {role} own, what changed recently, what needs attention."
                    ),
                },
            }],
        }

    elif name == "prep-triage":
        focus = arguments.get("focus", "")
        focus_text = f" Focus on: {focus}." if focus else ""
        return {
            "description": "Triage agent findings",
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Triage the current agent findings and route them to the right agents.{focus_text}\n\n"
                        "1. Call `prep_audit` to get current findings.\n"
                        "2. Check @prep://activity for what agents have already worked on.\n"
                        "3. Check @prep://conflicts for unresolved disagreements.\n"
                        "4. Cluster findings by root cause — group related issues that share affected files.\n"
                        "5. For each cluster: recommend which agent role should handle it, "
                        "flag any conflicts, and note if multiple agents independently flagged the same area."
                    ),
                },
            }],
        }

    return None
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_collab_resources.py -v`
Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/mcp/collaboration_handlers.py tests/test_collab_resources.py
git commit -m "feat(collab): add MCP collaboration handlers — resource formatters + prompt templates"
```

---

### Task 11: Wire MCP Server to Collaboration Handlers

**Files:**
- Modify: `src/prep/mcp/server.py:2092-2184,2360-2400`

4 thin integration points — no new logic in server.py.

- [ ] **Step 1: Extend `handle_resources_list`**

At the top of `handle_resources_list` (around line 2092), after the existing resources list is built, extend it:

```python
    async def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            project_id = await self._resolve_project_id()
        except Exception:
            project_id = "default"

        # Existing resources
        resources = [
            # ... existing 4 resources unchanged ...
        ]

        # Phase 73.5: Collaboration resources
        from prep.mcp.collaboration_handlers import get_collaboration_resources
        resources.extend(get_collaboration_resources(project_id))

        return {"resources": resources}
```

- [ ] **Step 2: Extend `handle_resources_read` to try collaboration first**

In `handle_resources_read` (around line 2159), before the existing if/elif chain:

```python
        # Phase 73.5: Try collaboration resources first
        from prep.mcp.collaboration_handlers import parse_collaboration_uri
        collab_parsed = parse_collaboration_uri(resource_type)
        if collab_parsed is not None:
            content = await self._read_collaboration_resource(
                project_id, collab_parsed[0], collab_parsed[1]
            )
            return {
                "contents": [{"uri": uri, "mimeType": "text/markdown", "text": content}]
            }

        # Existing resource handling below...
        if resource_type == "structure":
```

Add the helper method to MCPServer:

```python
    async def _read_collaboration_resource(
        self, project_id: str, resource_name: str, params: Dict[str, str],
    ) -> str:
        """Fetch collaboration resource data from daemon and format as markdown."""
        from prep.mcp.collaboration_handlers import (
            format_activity_resource,
            format_memory_resource,
            format_delta_resource,
            format_conflicts_resource,
        )

        try:
            if resource_name == "activity":
                data = await self._api_get(
                    f"/projects/{project_id}/collaboration/activity"
                )
                return format_activity_resource((data or {}).get("entries", []))

            elif resource_name in ("memory", "agent_findings"):
                role = params.get("role", "")
                visibility = "shared" if resource_name == "agent_findings" else None
                url = f"/projects/{project_id}/collaboration/observations?created_by={role}"
                if visibility:
                    url += f"&visibility={visibility}"
                data = await self._api_get(url)
                return format_memory_resource(role, (data or {}).get("observations", []))

            elif resource_name == "delta":
                data = await self._api_get(
                    f"/projects/{project_id}/collaboration/delta"
                )
                return format_delta_resource(data or {})

            elif resource_name == "conflicts":
                data = await self._api_get(
                    f"/projects/{project_id}/collaboration/conflicts"
                )
                return format_conflicts_resource((data or {}).get("conflicts", []))

        except Exception as e:
            logger.debug("Collaboration resource %s failed: %s", resource_name, e)
            return f"(Collaboration resource unavailable: {e})"

        return "(Unknown collaboration resource)"
```

- [ ] **Step 3: Extend prompts list and handler**

In `_PROMPTS` class variable, after the existing prompts:

```python
    # At module level or in __init__, merge collaboration prompts
    # In handle_prompts_list:
    async def handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from prep.mcp.collaboration_handlers import get_collaboration_prompts
        return {"prompts": self._PROMPTS + get_collaboration_prompts()}
```

In `handle_prompts_get`, add at the top before existing branches:

```python
    async def handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Phase 73.5: Try collaboration prompts first
        from prep.mcp.collaboration_handlers import get_collaboration_prompt_messages
        collab_result = get_collaboration_prompt_messages(name, arguments)
        if collab_result is not None:
            return collab_result

        # Existing prompt handling below...
        if name == "prep-onboard":
```

- [ ] **Step 4: Run existing MCP tests to check for regressions**

Run: `.venv/bin/pytest tests/test_mcp_server.py -v --timeout=30`
Expected: All existing tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/mcp/server.py
git commit -m "feat(collab): wire MCP server to collaboration handlers — resources + prompts"
```

---

### Task 12: Register Collaboration Router in Daemon + Add `created_by` to MCP Tool Schema

**Files:**
- Modify: `src/prep/server.py:549-590`
- Modify: `src/prep/mcp_tools.py:698-736`

- [ ] **Step 1: Register router in daemon**

In `src/prep/server.py`, after the existing router imports (around line 568):

```python
from prep.api.routers.collaboration import router as collaboration_router
```

After the existing `app.include_router` calls (around line 590):

```python
app.include_router(collaboration_router)
```

In the `lifespan` function (around line 38), after existing initialization, add hub init:

```python
    # Phase 73.5: Initialize collaboration hub
    try:
        from prep.services.collaboration import init_collaboration
        from prep.services.settings_store import settings
        db_path = settings.db_path if hasattr(settings, 'db_path') else Path("prep_data/prep_settings.db")
        init_collaboration(db_path)
        logger.info("Collaboration hub initialized")
    except Exception:
        logger.debug("Collaboration hub init failed (non-fatal)", exc_info=True)
```

- [ ] **Step 2: Add `created_by` to MCP tool schema**

In `src/prep/mcp_tools.py`, in the `prep_save_observation` tool's `inputSchema.properties` (around line 720), add:

```python
                "created_by": {
                    "type": "string",
                    "description": "Agent role identifier for attribution (e.g. 'researcher', 'pi/watchdog'). Enables cross-agent collaboration features.",
                },
```

- [ ] **Step 3: Pass `created_by` through in tool handler**

In `src/prep/mcp/server.py`, find `tool_save_observation` (around line 1328) and add the parameter:

```python
    async def tool_save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        symbol: Optional[str] = None,
        category: str = "note",
        created_by: Optional[str] = None,  # NEW
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
```

Then pass it through to the API call (find the existing POST to `/observations`):

```python
        body = {"content": content, "category": category}
        if file_path:
            body["file_path"] = file_path
        if symbol:
            body["symbol"] = symbol
        if created_by:
            body["created_by"] = created_by
```

Also update `SaveObservationRequest` in `src/prep/api/routers/observations.py` to accept `created_by`:

```python
class SaveObservationRequest(BaseModel):
    content: str
    file_path: Optional[str] = None
    symbol: Optional[str] = None
    category: Optional[str] = "note"
    created_by: Optional[str] = None  # NEW
```

And pass it through in the `save_observation` endpoint:

```python
        obs_id = store.save(
            project_id=project_id,
            content=body.content,
            file_path=body.file_path,
            symbol_fqn=body.symbol,
            category=body.category or "note",
            created_by=body.created_by,  # NEW
        )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/ -k "mcp or observation" -v --timeout=30`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/server.py src/prep/mcp_tools.py src/prep/mcp/server.py src/prep/api/routers/observations.py
git commit -m "feat(collab): register collaboration router in daemon + add created_by to MCP tool schema"
```

---

## Phase C: Agent Engine Wiring

### Task 13: Wire Pi Agent — Attribution + Activity + Snapshots

**Files:**
- Modify: `src/prep/services/pi_agent.py:60-68,1118-1145`

- [ ] **Step 1: Add `collab_hub` to PiAgent init**

Update `__init__` (around line 60):

```python
    def __init__(
        self,
        project_id: str,
        index_dir: Path,
        project_root: Optional[Path] = None,
        collab_hub: Optional[Any] = None,
    ) -> None:
        self.project_id = project_id
        self.index_dir = Path(index_dir)
        self.project_root = Path(project_root) if project_root else None
        self._collab = collab_hub
        # ... rest of init unchanged ...
```

Update `init_pi_agent()` (around line 1157):

```python
def init_pi_agent(
    project_id: str,
    index_dir: Path,
    project_root: Optional[Path] = None,
    collab_hub: Optional[Any] = None,
) -> PiAgent:
    global _pi_agent
    _pi_agent = PiAgent(project_id, index_dir, project_root, collab_hub=collab_hub)
    return _pi_agent
```

- [ ] **Step 2: Update `_save_observation` with scenario attribution**

Update `_save_observation` (around line 1118):

```python
    def _save_observation(
        self,
        content: str,
        category: str = "note",
        query_tag: Optional[str] = None,
        scenario: Optional[str] = None,
    ) -> None:
        try:
            from prep.services.observation_store import observation_store
            if query_tag:
                tagged = f"[{query_tag}] {content}"
            else:
                tagged = content

            observation_store.save(
                self.project_id,
                tagged,
                category="note",
                created_by=scenario or "pi",
            )
        except Exception:
            logger.debug("Pi: failed to save observation", exc_info=True)
```

- [ ] **Step 3: Add activity logging helper**

Add after `_save_observation`:

```python
    def _log_activity(self, scenario: str, action: str, summary: str,
                      details: Optional[Dict[str, Any]] = None) -> None:
        """Log an activity entry if collaboration hub is available."""
        if self._collab:
            try:
                self._collab.activity.log(
                    self.project_id, f"pi/{scenario}", action, summary, details=details,
                )
            except Exception:
                logger.debug("Pi: failed to log activity", exc_info=True)
```

- [ ] **Step 4: Update Watchdog scenario calls**

Find the `_run_watchdog` method and update `_save_observation` calls to pass `scenario="pi/watchdog"`. Also add activity logging at the end of the scenario. For example, find the line that calls `self._save_observation(content=content, category="agent_scan")` (around line 1116) and update to:

```python
        self._save_observation(content=content, category="agent_scan", scenario="pi/watchdog")
        self._log_activity("watchdog", "delta_scan_complete", content)
```

Repeat the same pattern for other scenarios — each `_save_observation` call gets its scenario name added. The key scenarios are:
- `_run_watchdog` → `scenario="pi/watchdog"`
- `_run_doctor` → `scenario="pi/doctor"`
- `_run_geologist` → `scenario="pi/geologist"`
- `_run_dispatcher` → `scenario="pi/dispatcher"`
- `_run_librarian` → `scenario="pi/librarian"`
- `_run_architect` → `scenario="pi/architect"`
- `_run_scholar` → `scenario="pi/scholar"`

- [ ] **Step 5: Run existing Pi tests**

Run: `.venv/bin/pytest tests/ -k "pi_agent" -v --timeout=30`
Expected: All existing tests PASS (new params are optional, backward compatible).

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pi_agent.py
git commit -m "feat(collab): wire Pi agent — observation attribution + activity logging"
```

---

### Task 14: Wire Researcher + Custodian — Attribution + Claims

**Files:**
- Modify: `src/prep/agents/researcher/engine.py`
- Modify: `src/prep/agents/custodian/engine.py`

Per Issue 5: engines access hub through `self._core.collab`, not a separate reference.

- [ ] **Step 1: Update ResearcherEngine to use attribution + claims**

In `src/prep/agents/researcher/engine.py`, find `research_topic` method. At the start, add claim creation:

```python
    def research_topic(self, topic, llm_fn, ...):
        # Claim affected files if collaboration is available
        if self._core and self._core.collab:
            for fp in topic.affected_files[:5]:  # limit to avoid claim spam
                try:
                    self._core.collab.claims.claim(
                        self._project_id, "researcher", fp,
                        reason=f"Researching: {topic.title}",
                    )
                except Exception:
                    pass

        # Log activity
        if self._core and self._core.collab:
            try:
                self._core.collab.activity.log(
                    self._project_id, "researcher", "research_topic_start",
                    f"Researching: {topic.title}",
                )
            except Exception:
                pass

        # ... existing logic unchanged ...
```

Where the researcher saves observations (if it does via AgentCore), pass `created_by="researcher"`.

- [ ] **Step 2: Update CustodianEngine to check claims**

In `src/prep/agents/custodian/engine.py`, in the discovery/verification phase where files are checked for deletion safety, add claim checking:

```python
    def _is_claimable_for_deletion(self, file_path: str) -> bool:
        """Check if another agent has claimed this file."""
        if self._core and self._core.collab:
            try:
                if self._core.collab.claims.is_claimed(
                    self._project_id, file_path, exclude_agent="custodian"
                ):
                    logger.info("Skipping %s — claimed by another agent", file_path)
                    return False
            except Exception:
                pass
        return True
```

Call this before marking a file as `safe_to_delete` in the verification pipeline.

Also add activity logging at key stages (discover, verify, plan).

- [ ] **Step 3: Run existing agent tests**

Run: `.venv/bin/pytest tests/ -k "researcher or custodian" -v --timeout=30`
Expected: All existing tests PASS (hub access is guarded with `if self._core and self._core.collab`).

- [ ] **Step 4: Commit**

```bash
git add src/prep/agents/researcher/engine.py src/prep/agents/custodian/engine.py
git commit -m "feat(collab): wire Researcher + Custodian — attribution, claims, activity logging"
```

---

### Task 15: Wire PushEngine — Conflict Detection

**Files:**
- Modify: `src/prep/adapters/push_engine.py`
- Modify: `src/prep/adapters/pm_models.py`

- [ ] **Step 1: Add `conflicts` field to PushResult**

In `src/prep/adapters/pm_models.py`, add to `PushResult` (around line 95):

```python
    conflicts: List[Any] = field(default_factory=list)
```

And in `to_dict()`:

```python
            "conflicts": [
                {"id": c.id, "file_path": c.file_path, "agent_a": c.agent_a, "agent_b": c.agent_b}
                if hasattr(c, 'id') else c
                for c in self.conflicts
            ],
```

- [ ] **Step 2: Add conflict detection to PushEngine**

In `src/prep/adapters/push_engine.py`, update `__init__`:

```python
    def __init__(
        self,
        adapter: PMAdapter,
        consolidator: Optional[Consolidator] = None,
        conflict_detector: Optional[Any] = None,
        conflict_store: Optional[Any] = None,
    ) -> None:
        self.adapter = adapter
        self.consolidator = consolidator or Consolidator()
        self._conflict_detector = conflict_detector
        self._conflict_store = conflict_store
```

In `push()`, after consolidation but before the push loop, add:

```python
        # Phase 73.5: Detect conflicts between agent findings
        if self._conflict_detector and self._conflict_store:
            try:
                from prep.services.observation_store import observation_store
                obs = observation_store.get_by_agent(
                    prep_project_id, created_by="",  # get all attributed
                    include_stale=False, limit=200,
                )
                # Filter to only observations with created_by set
                attributed = [o for o in obs if o.created_by]
                conflicts = self._conflict_detector.detect_from_observations(
                    prep_project_id, attributed,
                )
                for c in conflicts:
                    self._conflict_store.save(c)
                result.conflicts = conflicts
            except Exception:
                logger.debug("Conflict detection failed (non-fatal)", exc_info=True)
```

- [ ] **Step 3: Run push engine tests**

Run: `.venv/bin/pytest tests/ -k "push" -v --timeout=30`
Expected: All existing tests PASS (new params are optional).

- [ ] **Step 4: Commit**

```bash
git add src/prep/adapters/push_engine.py src/prep/adapters/pm_models.py
git commit -m "feat(collab): wire PushEngine — conflict detection on push"
```

---

### Task 16: Final Integration — Pass Hub Through Init Chain

**Files:**
- Modify: `src/prep/server.py` (daemon startup)
- Modify: `src/prep/api/routers/agents.py` (AgentCore construction)

- [ ] **Step 1: Pass hub to Pi agent during daemon init**

Find where `init_pi_agent` is called in `src/prep/server.py` and pass the hub:

```python
    from prep.services.collaboration import get_collaboration_hub
    # ... existing pi init ...
    pi = init_pi_agent(project_id, index_dir, project_root,
                       collab_hub=get_collaboration_hub())
```

- [ ] **Step 2: Pass hub to AgentCore in API routes**

In `src/prep/api/routers/agents.py`, where `AgentCore(...)` is constructed (multiple call sites), add:

```python
    from prep.services.collaboration import get_collaboration_hub
    core = AgentCore(
        project_id=pid, index_dir=idx_dir, project_root=project_root,
        collab_hub=get_collaboration_hub(),
    )
```

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/pytest tests/ -v --timeout=60 -x`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/prep/server.py src/prep/api/routers/agents.py
git commit -m "feat(collab): wire CollaborationHub through daemon init chain"
```

---

## Summary

| Phase | Tasks | What It Delivers |
|---|---|---|
| **A: Foundation** | 1-8 | Observation attribution, ActivityStore, ClaimStore, GraphSnapshotStore, ConflictStore, CollaborationHub |
| **B: MCP Integration** | 9-12 | FastAPI routes, MCP resource handlers, MCP prompt handlers, daemon registration |
| **C: Agent Wiring** | 13-16 | Pi attribution + activity, Researcher claims, Custodian claim checks, PushEngine conflicts, init chain |

Total: 16 tasks across 3 phases. Each task is independently committable and testable.
