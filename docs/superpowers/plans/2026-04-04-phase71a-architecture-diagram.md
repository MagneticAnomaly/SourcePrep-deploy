# Phase 71A: Core Architecture Diagram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive, layered architecture diagram for the CoDRAG dashboard that visualizes module structure, file dependencies, and user annotations using React Flow.

**Architecture:** Backend composes a read-only architecture graph from existing trace graph + module synthesis data, served via a new `/architecture` router. Frontend renders it as an interactive React Flow canvas inside the standard panel/detail-overlay pattern. Layout positions and user notes persist to the project's index directory via the API.

**Tech Stack:** React Flow (`@xyflow/react` v12), ELK.js (`elkjs`), FastAPI, Pydantic, Zustand (via React Flow internals)

**Design Document:** `docs/Phase71_MasterArchitectureDiagram/71_Design_Document.md`

---

## Scope

This plan covers **Phase A only** — the core diagram with layered drill-down, auto-layout, annotations, layout persistence, and panel integration. Phase B (Paperclip/ACR integration) and Phase C (agent governance) are separate future plans.

## File Map

### New Files — Backend (4 files)

| File | Responsibility |
|------|---------------|
| `src/codrag/api/routers/architecture.py` | REST endpoints: graph composition, notes CRUD, layout persistence, summary |
| `src/codrag/core/architecture_state.py` | Read/write architecture state (layouts, notes) from project index dir |
| `tests/test_architecture_router.py` | Backend endpoint tests |
| `tests/test_architecture_state.py` | Architecture state persistence tests |

### New Files — Frontend (12 files)

| File | Responsibility |
|------|---------------|
| `packages/ui/src/types/architecture.ts` | TypeScript types for architecture graph, nodes, edges, notes |
| `packages/ui/src/components/architecture/ModuleNode.tsx` | React Flow custom node: rounded rectangle with badges |
| `packages/ui/src/components/architecture/FileNode.tsx` | React Flow custom node: pill shape with metadata |
| `packages/ui/src/components/architecture/ExternalRefNode.tsx` | React Flow custom node: dashed border for cross-module refs |
| `packages/ui/src/components/architecture/AnnotationNode.tsx` | React Flow custom node: editable sticky note |
| `packages/ui/src/components/architecture/DependencyEdge.tsx` | React Flow custom edge: solid/dashed/dotted, color-coded |
| `packages/ui/src/components/architecture/ArchitectureDiagramPanel.tsx` | Overview card for dashboard grid |
| `packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx` | Fullscreen overlay with React Flow canvas, toolbar, sidebar, breadcrumb |
| `packages/ui/src/components/architecture/index.ts` | Barrel exports |
| `src/codrag/dashboard/src/hooks/useArchitectureSystem.ts` | Dashboard hook: fetch, state, layout save, notes CRUD |

### Modified Files (5 files)

| File | Change |
|------|--------|
| `packages/ui/package.json` | Add `@xyflow/react` and `elkjs` dependencies |
| `packages/ui/src/config/panelRegistry.ts` | Add `architecture` panel definition |
| `packages/ui/src/index.ts` | Export architecture components and types |
| `packages/ui/src/api/client.ts` | Add architecture API methods |
| `src/codrag/server.py` | Register architecture router |

### Files NOT modified (wiring deferred)

| File | Why deferred |
|------|-------------|
| `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` | This 1100+ line file wires all panels. Adding architecture wiring here is a mechanical step that depends on all components being built first. It's the final integration task. |
| `src/codrag/mcp/server.py` | MCP context injection is Phase A's last deliverable and depends on the backend being complete. |

---

## Task 1: Install Dependencies

**Files:**
- Modify: `packages/ui/package.json`

- [ ] **Step 1: Install React Flow and ELK.js**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui
npm install @xyflow/react@^12 elkjs@^0.9
```

- [ ] **Step 2: Verify installation**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui
node -e "require('@xyflow/react'); console.log('react-flow OK')"
node -e "require('elkjs'); console.log('elkjs OK')"
```

Expected: Both print OK.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/package.json packages/ui/package-lock.json
git commit -m "feat(ui): add @xyflow/react and elkjs dependencies for architecture diagram"
```

---

## Task 2: Architecture Types (Frontend)

**Files:**
- Create: `packages/ui/src/types/architecture.ts`
- Modify: `packages/ui/src/index.ts`

- [ ] **Step 1: Create the types file**

```typescript
// packages/ui/src/types/architecture.ts

/**
 * Architecture diagram types — Phase 71A
 *
 * These types define the data model for the interactive architecture diagram.
 * Backend returns ArchGraphResponse; frontend maps to React Flow nodes/edges.
 */

// ── API Response Types ─────────────────────────────────────────────

/** A module in the architecture graph (from module synthesis + trace) */
export interface ArchModule {
  id: string;
  name: string;
  description: string;
  file_count: number;
  member_files: string[];
  hub_files: string[];
  domain_tags: string[];
  architecture_layers: string[];
  component_status: string;
  avg_confidence: number;
  dependencies: string[];
}

/** A file node in the architecture graph */
export interface ArchFile {
  id: string;
  path: string;
  module_id: string;
  language: string;
  hub_score: number;
  confidence: number;
  summary: string;
  line_count: number;
}

/** An edge between modules or files */
export interface ArchEdge {
  source: string;
  target: string;
  kind: 'imports' | 'calls' | 'inferred';
  count: number;
}

/** Stats about the architecture graph */
export interface ArchStats {
  total_modules: number;
  total_files: number;
  total_edges: number;
  generated_at: string;
}

/** Full response from GET /projects/{id}/architecture/graph */
export interface ArchGraphResponse {
  exists: boolean;
  modules: ArchModule[];
  files: ArchFile[];
  edges: ArchEdge[];
  external_refs: ArchFile[];
  stats: ArchStats;
}

/** Summary response from GET /projects/{id}/architecture/summary */
export interface ArchSummaryResponse {
  exists: boolean;
  module_count: number;
  file_count: number;
  edge_count: number;
  note_count: number;
  last_edited: string | null;
}

// ── Notes ──────────────────────────────────────────────────────────

export type ArchNoteType = 'adr' | 'comment' | 'agent_note';

/** A user or agent annotation attached to a node */
export interface ArchNote {
  id: string;
  node_id: string;
  content: string;
  note_type: ArchNoteType;
  author: string;
  color: string;
  created_at: string;
  updated_at: string;
}

/** Request body for creating a note */
export interface ArchNoteCreate {
  node_id: string;
  content: string;
  note_type: ArchNoteType;
  author?: string;
  color?: string;
}

/** Request body for updating a note */
export interface ArchNoteUpdate {
  content?: string;
  color?: string;
}

// ── Layout Persistence ─────────────────────────────────────────────

/** Saved node position for a specific layer */
export interface ArchNodePosition {
  id: string;
  x: number;
  y: number;
}

/** Saved layout for one drill-down layer */
export interface ArchLayerLayout {
  layer_path: string;
  positions: ArchNodePosition[];
  viewport: { x: number; y: number; zoom: number };
}

/** Full persisted architecture state */
export interface ArchState {
  layouts: Record<string, ArchLayerLayout>;
  module_overrides: Record<string, { name?: string; description?: string }>;
}

// ── Frontend-only types ────────────────────────────────────────────

/** Breadcrumb segment for layer navigation */
export interface ArchBreadcrumb {
  label: string;
  layerPath: string[];
}

/** Node data passed to React Flow custom nodes */
export interface ModuleNodeData {
  label: string;
  description: string;
  fileCount: number;
  hubFiles: string[];
  domainTags: string[];
  componentStatus: string;
  confidence: number;
  noteCount: number;
  isHub: boolean;
}

export interface FileNodeData {
  label: string;
  path: string;
  language: string;
  hubScore: number;
  confidence: number;
  summary: string;
  lineCount: number;
  noteCount: number;
  isHub: boolean;
}

export interface ExternalRefNodeData {
  label: string;
  moduleId: string;
  description: string;
}

export interface AnnotationNodeData {
  noteId: string;
  content: string;
  noteType: ArchNoteType;
  author: string;
  color: string;
  onEdit?: (noteId: string, content: string) => void;
  onDelete?: (noteId: string) => void;
}
```

- [ ] **Step 2: Export types from index.ts**

Add to `packages/ui/src/index.ts` after the Roadmap types export block (around line 220):

```typescript
// Types - Architecture Diagram (Phase 71)
export type {
  ArchModule, ArchFile, ArchEdge, ArchStats, ArchGraphResponse,
  ArchSummaryResponse, ArchNoteType, ArchNote, ArchNoteCreate,
  ArchNoteUpdate, ArchNodePosition, ArchLayerLayout, ArchState,
  ArchBreadcrumb, ModuleNodeData, FileNodeData, ExternalRefNodeData,
  AnnotationNodeData,
} from './types/architecture';
```

- [ ] **Step 3: Verify types compile**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui
npx tsc --noEmit --pretty 2>&1 | head -20
```

Expected: No errors related to architecture types.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/types/architecture.ts packages/ui/src/index.ts
git commit -m "feat(ui): add architecture diagram TypeScript types"
```

---

## Task 3: Backend — Architecture State Persistence

**Files:**
- Create: `src/codrag/core/architecture_state.py`
- Create: `tests/test_architecture_state.py`

- [ ] **Step 1: Write tests for architecture state**

```python
# tests/test_architecture_state.py
"""Tests for architecture state persistence (layouts, notes)."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from codrag.core.architecture_state import ArchitectureState


@pytest.fixture
def arch_state(tmp_path: Path) -> ArchitectureState:
    return ArchitectureState(tmp_path)


class TestArchitectureState:
    """State persistence to <index_dir>/architecture/."""

    def test_empty_state(self, arch_state: ArchitectureState):
        """Fresh project has empty state."""
        state = arch_state.load_state()
        assert state["layouts"] == {}
        assert state["module_overrides"] == {}

    def test_save_and_load_state(self, arch_state: ArchitectureState):
        state = {
            "layouts": {
                "root": {
                    "layer_path": "",
                    "positions": [{"id": "mod_1", "x": 100, "y": 200}],
                    "viewport": {"x": 0, "y": 0, "zoom": 1.0},
                }
            },
            "module_overrides": {"mod_1": {"name": "Auth"}},
        }
        arch_state.save_state(state)
        loaded = arch_state.load_state()
        assert loaded["layouts"]["root"]["positions"][0]["x"] == 100
        assert loaded["module_overrides"]["mod_1"]["name"] == "Auth"

    def test_creates_directory(self, arch_state: ArchitectureState):
        arch_state.save_state({"layouts": {}, "module_overrides": {}})
        assert (arch_state.base_dir / "architecture").is_dir()


class TestNotes:
    """Notes CRUD operations."""

    def test_list_notes_empty(self, arch_state: ArchitectureState):
        assert arch_state.list_notes() == []

    def test_create_note(self, arch_state: ArchitectureState):
        note = arch_state.create_note(
            node_id="mod_1",
            content="Migrating to OAuth2",
            note_type="adr",
            author="user",
            color="yellow",
        )
        assert note["id"]
        assert note["node_id"] == "mod_1"
        assert note["content"] == "Migrating to OAuth2"
        assert note["note_type"] == "adr"

    def test_list_notes_after_create(self, arch_state: ArchitectureState):
        arch_state.create_note("mod_1", "Note 1", "comment", "user")
        arch_state.create_note("mod_2", "Note 2", "adr", "user")
        notes = arch_state.list_notes()
        assert len(notes) == 2

    def test_update_note(self, arch_state: ArchitectureState):
        note = arch_state.create_note("mod_1", "Draft", "comment", "user")
        updated = arch_state.update_note(note["id"], content="Final version")
        assert updated["content"] == "Final version"
        assert updated["id"] == note["id"]

    def test_update_note_not_found(self, arch_state: ArchitectureState):
        result = arch_state.update_note("nonexistent", content="x")
        assert result is None

    def test_delete_note(self, arch_state: ArchitectureState):
        note = arch_state.create_note("mod_1", "Temp", "comment", "user")
        deleted = arch_state.delete_note(note["id"])
        assert deleted is True
        assert arch_state.list_notes() == []

    def test_delete_note_not_found(self, arch_state: ArchitectureState):
        assert arch_state.delete_note("nonexistent") is False

    def test_get_notes_for_node(self, arch_state: ArchitectureState):
        arch_state.create_note("mod_1", "Note A", "comment", "user")
        arch_state.create_note("mod_2", "Note B", "adr", "user")
        arch_state.create_note("mod_1", "Note C", "adr", "user")
        mod1_notes = arch_state.get_notes_for_node("mod_1")
        assert len(mod1_notes) == 2
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
.venv/bin/pytest tests/test_architecture_state.py -v 2>&1 | tail -20
```

Expected: ImportError — `codrag.core.architecture_state` does not exist.

- [ ] **Step 3: Implement ArchitectureState**

```python
# src/codrag/core/architecture_state.py
"""
Architecture state persistence — Phase 71A

Manages layout positions, module overrides, and annotation notes
stored as JSON files in <index_dir>/architecture/.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ArchitectureState:
    """Read/write architecture diagram state for a project."""

    def __init__(self, index_dir: Path):
        self.base_dir = Path(index_dir)
        self._arch_dir = self.base_dir / "architecture"
        self._state_path = self._arch_dir / "graph_state.json"
        self._notes_path = self._arch_dir / "notes.json"

    def _ensure_dir(self) -> None:
        self._arch_dir.mkdir(parents=True, exist_ok=True)

    # ── State (layouts + overrides) ─────────────────────────────────

    def load_state(self) -> Dict[str, Any]:
        if not self._state_path.exists():
            return {"layouts": {}, "module_overrides": {}}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt architecture state at %s, returning empty", self._state_path)
            return {"layouts": {}, "module_overrides": {}}

    def save_state(self, state: Dict[str, Any]) -> None:
        self._ensure_dir()
        self._state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Notes ───────────────────────────────────────────────────────

    def _load_notes(self) -> List[Dict[str, Any]]:
        if not self._notes_path.exists():
            return []
        try:
            return json.loads(self._notes_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_notes(self, notes: List[Dict[str, Any]]) -> None:
        self._ensure_dir()
        self._notes_path.write_text(
            json.dumps(notes, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list_notes(self) -> List[Dict[str, Any]]:
        return self._load_notes()

    def get_notes_for_node(self, node_id: str) -> List[Dict[str, Any]]:
        return [n for n in self._load_notes() if n.get("node_id") == node_id]

    def create_note(
        self,
        node_id: str,
        content: str,
        note_type: str,
        author: str,
        color: str = "yellow",
    ) -> Dict[str, Any]:
        notes = self._load_notes()
        now = datetime.now(timezone.utc).isoformat()
        note: Dict[str, Any] = {
            "id": f"note_{uuid.uuid4().hex[:12]}",
            "node_id": node_id,
            "content": content,
            "note_type": note_type,
            "author": author,
            "color": color,
            "created_at": now,
            "updated_at": now,
        }
        notes.append(note)
        self._save_notes(notes)
        return note

    def update_note(
        self,
        note_id: str,
        content: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        notes = self._load_notes()
        for note in notes:
            if note["id"] == note_id:
                if content is not None:
                    note["content"] = content
                if color is not None:
                    note["color"] = color
                note["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save_notes(notes)
                return note
        return None

    def delete_note(self, note_id: str) -> bool:
        notes = self._load_notes()
        original_len = len(notes)
        notes = [n for n in notes if n["id"] != note_id]
        if len(notes) < original_len:
            self._save_notes(notes)
            return True
        return False
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
.venv/bin/pytest tests/test_architecture_state.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/architecture_state.py tests/test_architecture_state.py
git commit -m "feat(core): add architecture state persistence for layouts and notes"
```

---

## Task 4: Backend — Architecture Router

**Files:**
- Create: `src/codrag/api/routers/architecture.py`
- Modify: `src/codrag/server.py`
- Create: `tests/test_architecture_router.py`

- [ ] **Step 1: Write router tests**

```python
# tests/test_architecture_router.py
"""Tests for architecture router endpoints."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create a minimal FastAPI app with the architecture router."""
    from fastapi import FastAPI
    from codrag.api.routers.architecture import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_project(tmp_path):
    """Mock project with trace modules data."""
    proj = MagicMock()
    proj.id = "test-project"
    proj.path = str(tmp_path / "repo")

    # Create index dir with module synthesis data
    idx_dir = tmp_path / "index"
    idx_dir.mkdir()

    modules = [
        {
            "module_id": "mod_auth",
            "name": "Authentication",
            "summary": "User auth and session management",
            "member_files": ["src/auth/login.py", "src/auth/session.py"],
            "domain_tags": ["security", "auth"],
            "architecture_layers": ["service"],
            "component_status": "complete",
            "file_count": 2,
            "avg_epistemic_confidence": 0.85,
            "dependencies": ["mod_db"],
        },
        {
            "module_id": "mod_db",
            "name": "Database",
            "summary": "Database access layer",
            "member_files": ["src/db/connection.py"],
            "domain_tags": ["data"],
            "architecture_layers": ["infrastructure"],
            "component_status": "complete",
            "file_count": 1,
            "avg_epistemic_confidence": 0.92,
            "dependencies": [],
        },
    ]
    modules_path = idx_dir / "trace_modules.jsonl"
    with open(modules_path, "w") as f:
        for m in modules:
            f.write(json.dumps(m) + "\n")

    # Create trace data
    nodes = [
        {"id": "file:src/auth/login.py", "kind": "file", "name": "login.py", "path": "src/auth/login.py"},
        {"id": "file:src/auth/session.py", "kind": "file", "name": "session.py", "path": "src/auth/session.py"},
        {"id": "file:src/db/connection.py", "kind": "file", "name": "connection.py", "path": "src/db/connection.py"},
    ]
    edges = [
        {"source": "file:src/auth/login.py", "target": "file:src/db/connection.py", "kind": "imports"},
        {"source": "file:src/auth/session.py", "target": "file:src/db/connection.py", "kind": "imports"},
    ]

    nodes_path = idx_dir / "trace_nodes.jsonl"
    with open(nodes_path, "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")

    edges_path = idx_dir / "trace_edges.jsonl"
    with open(edges_path, "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")

    manifest = {"built_at": "2026-04-04T00:00:00Z", "node_count": 3, "edge_count": 2}
    (idx_dir / "trace_manifest.json").write_text(json.dumps(manifest))

    return proj, idx_dir


class TestGetArchitectureGraph:
    def test_returns_modules_and_edges(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.get(f"/projects/{proj.id}/architecture/graph")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["exists"] is True
        assert len(data["modules"]) == 2
        assert data["stats"]["total_modules"] == 2

    def test_returns_empty_when_no_modules(self, client, mock_project):
        proj, idx_dir = mock_project
        (idx_dir / "trace_modules.jsonl").unlink()
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.get(f"/projects/{proj.id}/architecture/graph")
        data = resp.json()["data"]
        assert data["exists"] is False
        assert data["modules"] == []


class TestArchitectureSummary:
    def test_returns_summary(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.get(f"/projects/{proj.id}/architecture/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["module_count"] == 2


class TestNotesEndpoints:
    def test_create_and_list_notes(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            # Create
            resp = client.post(
                f"/projects/{proj.id}/architecture/notes",
                json={"node_id": "mod_auth", "content": "Migrating to OAuth2", "note_type": "adr", "author": "user"},
            )
            assert resp.status_code == 200
            note = resp.json()["data"]
            assert note["content"] == "Migrating to OAuth2"

            # List
            resp = client.get(f"/projects/{proj.id}/architecture/notes")
            assert len(resp.json()["data"]) == 1

    def test_update_note(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.post(
                f"/projects/{proj.id}/architecture/notes",
                json={"node_id": "mod_auth", "content": "Draft", "note_type": "comment", "author": "user"},
            )
            note_id = resp.json()["data"]["id"]

            resp = client.put(
                f"/projects/{proj.id}/architecture/notes/{note_id}",
                json={"content": "Final"},
            )
            assert resp.json()["data"]["content"] == "Final"

    def test_delete_note(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.post(
                f"/projects/{proj.id}/architecture/notes",
                json={"node_id": "mod_auth", "content": "Temp", "note_type": "comment", "author": "user"},
            )
            note_id = resp.json()["data"]["id"]

            resp = client.delete(f"/projects/{proj.id}/architecture/notes/{note_id}")
            assert resp.json()["data"]["deleted"] is True

            resp = client.get(f"/projects/{proj.id}/architecture/notes")
            assert len(resp.json()["data"]) == 0


class TestStatePersistence:
    def test_save_and_load_state(self, client, mock_project):
        proj, idx_dir = mock_project
        state = {
            "layouts": {
                "root": {
                    "layer_path": "",
                    "positions": [{"id": "mod_auth", "x": 100, "y": 200}],
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                }
            },
            "module_overrides": {},
        }
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.put(f"/projects/{proj.id}/architecture/state", json=state)
            assert resp.status_code == 200

            resp = client.get(f"/projects/{proj.id}/architecture/state")
            loaded = resp.json()["data"]
            assert loaded["layouts"]["root"]["positions"][0]["x"] == 100
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
.venv/bin/pytest tests/test_architecture_router.py -v 2>&1 | tail -10
```

Expected: ImportError — `codrag.api.routers.architecture` does not exist.

- [ ] **Step 3: Implement the architecture router**

```python
# src/codrag/api/routers/architecture.py
"""
CoDRAG Architecture Router — Phase 71A
=======================================

REST endpoints for the interactive architecture diagram.

Endpoints:
  GET    /projects/{id}/architecture/graph     — Composed graph (modules + edges)
  GET    /projects/{id}/architecture/summary   — Quick stats
  GET    /projects/{id}/architecture/state     — Persisted layout + overrides
  PUT    /projects/{id}/architecture/state     — Save layout + overrides
  GET    /projects/{id}/architecture/notes     — List all notes
  POST   /projects/{id}/architecture/notes     — Create a note
  PUT    /projects/{id}/architecture/notes/{nid} — Update a note
  DELETE /projects/{id}/architecture/notes/{nid} — Delete a note
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["architecture"])


def _require_project(project_id: str):
    from codrag.server import _require_project as rp
    return rp(project_id)


def _project_index_dir(proj) -> Path:
    from codrag.core.project_registry import project_index_dir
    return project_index_dir(proj)


def _get_arch_state(idx_dir: Path):
    from codrag.core.architecture_state import ArchitectureState
    return ArchitectureState(idx_dir)


# ── Request Models ──────────────────────────────────────────────────

class NoteCreate(BaseModel):
    node_id: str
    content: str
    note_type: str = "comment"
    author: str = "user"
    color: str = "yellow"


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    color: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────────────

def _load_modules(idx_dir: Path) -> List[Dict[str, Any]]:
    """Load module synthesis results from trace_modules.jsonl."""
    modules_path = idx_dir / "trace_modules.jsonl"
    if not modules_path.exists():
        return []
    modules: List[Dict[str, Any]] = []
    try:
        with open(modules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        modules.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return modules


def _load_trace_edges(idx_dir: Path) -> List[Dict[str, Any]]:
    """Load trace edges from trace_edges.jsonl."""
    edges_path = idx_dir / "trace_edges.jsonl"
    if not edges_path.exists():
        return []
    edges: List[Dict[str, Any]] = []
    try:
        with open(edges_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        edges.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return edges


def _build_file_to_module_map(modules: List[Dict[str, Any]]) -> Dict[str, str]:
    """Map file paths to their module IDs."""
    mapping: Dict[str, str] = {}
    for m in modules:
        for f in m.get("member_files", []):
            mapping[f] = m["module_id"]
    return mapping


def _aggregate_module_edges(
    trace_edges: List[Dict[str, Any]],
    file_to_module: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Aggregate file-level trace edges into module-level edges."""
    agg: Dict[str, Dict[str, Any]] = {}
    for edge in trace_edges:
        src_path = edge.get("source", "").replace("file:", "")
        tgt_path = edge.get("target", "").replace("file:", "")
        src_mod = file_to_module.get(src_path)
        tgt_mod = file_to_module.get(tgt_path)
        if not src_mod or not tgt_mod or src_mod == tgt_mod:
            continue
        key = f"{src_mod}::{tgt_mod}"
        kind = edge.get("kind", "imports")
        if key not in agg:
            agg[key] = {
                "source": src_mod,
                "target": tgt_mod,
                "kind": kind,
                "count": 0,
            }
        agg[key]["count"] += 1
    return list(agg.values())


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/graph")
def get_architecture_graph(
    project_id: str,
    layer_path: str = "",
) -> Dict[str, Any]:
    """Compose the architecture graph from modules + trace edges."""
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)

    modules = _load_modules(idx_dir)
    if not modules:
        return ok({
            "exists": False,
            "modules": [],
            "files": [],
            "edges": [],
            "external_refs": [],
            "stats": {"total_modules": 0, "total_files": 0, "total_edges": 0, "generated_at": ""},
        })

    trace_edges = _load_trace_edges(idx_dir)
    file_to_module = _build_file_to_module_map(modules)

    if not layer_path:
        # Layer 0: System overview — modules + aggregated edges
        module_edges = _aggregate_module_edges(trace_edges, file_to_module)
        return ok({
            "exists": True,
            "modules": modules,
            "files": [],
            "edges": module_edges,
            "external_refs": [],
            "stats": {
                "total_modules": len(modules),
                "total_files": sum(m.get("file_count", 0) for m in modules),
                "total_edges": len(module_edges),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    # Layer 1+: Drill into a specific module
    target_module = None
    for m in modules:
        if m["module_id"] == layer_path:
            target_module = m
            break

    if not target_module:
        raise ApiException(404, "MODULE_NOT_FOUND", f"Module '{layer_path}' not found")

    # Build file nodes for this module
    member_files = target_module.get("member_files", [])
    files: List[Dict[str, Any]] = []
    for fp in member_files:
        files.append({
            "id": f"file:{fp}",
            "path": fp,
            "module_id": target_module["module_id"],
            "language": _guess_language(fp),
            "hub_score": 0,
            "confidence": target_module.get("avg_epistemic_confidence", 0),
            "summary": "",
            "line_count": 0,
        })

    # File-level edges within this module + external refs
    internal_paths = set(member_files)
    file_edges: List[Dict[str, Any]] = []
    ext_modules: set = set()

    for edge in trace_edges:
        src = edge.get("source", "").replace("file:", "")
        tgt = edge.get("target", "").replace("file:", "")
        if src in internal_paths or tgt in internal_paths:
            file_edges.append({
                "source": f"file:{src}",
                "target": f"file:{tgt}",
                "kind": edge.get("kind", "imports"),
                "count": 1,
            })
            # Track external modules referenced
            if src not in internal_paths:
                ext_mod = file_to_module.get(src)
                if ext_mod:
                    ext_modules.add(ext_mod)
            if tgt not in internal_paths:
                ext_mod = file_to_module.get(tgt)
                if ext_mod:
                    ext_modules.add(ext_mod)

    external_refs = []
    for ext_mod_id in ext_modules:
        for m in modules:
            if m["module_id"] == ext_mod_id:
                external_refs.append({
                    "id": ext_mod_id,
                    "path": "",
                    "module_id": ext_mod_id,
                    "language": "",
                    "hub_score": 0,
                    "confidence": 0,
                    "summary": m.get("summary", ""),
                    "line_count": 0,
                })
                break

    return ok({
        "exists": True,
        "modules": [],
        "files": files,
        "edges": file_edges,
        "external_refs": external_refs,
        "stats": {
            "total_modules": 0,
            "total_files": len(files),
            "total_edges": len(file_edges),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    })


def _guess_language(path: str) -> str:
    ext_map = {
        ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript",
        ".jsx": "jsx", ".rs": "rust", ".go": "go", ".java": "java",
        ".rb": "ruby", ".css": "css", ".html": "html", ".md": "markdown",
    }
    for ext, lang in ext_map.items():
        if path.endswith(ext):
            return lang
    return "unknown"


@router.get("/projects/{project_id}/architecture/summary")
def get_architecture_summary(project_id: str) -> Dict[str, Any]:
    """Quick stats about the architecture."""
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    modules = _load_modules(idx_dir)
    arch = _get_arch_state(idx_dir)
    notes = arch.list_notes()

    return ok({
        "exists": len(modules) > 0,
        "module_count": len(modules),
        "file_count": sum(m.get("file_count", 0) for m in modules),
        "edge_count": 0,  # Computed on demand in graph endpoint
        "note_count": len(notes),
        "last_edited": None,
    })


# ── State persistence ──────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/state")
def get_architecture_state(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    return ok(arch.load_state())


@router.put("/projects/{project_id}/architecture/state")
def save_architecture_state(project_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    arch.save_state(body)
    return ok({"saved": True})


# ── Notes CRUD ─────────────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/notes")
def list_notes(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    return ok(arch.list_notes())


@router.post("/projects/{project_id}/architecture/notes")
def create_note(project_id: str, body: NoteCreate) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    note = arch.create_note(
        node_id=body.node_id,
        content=body.content,
        note_type=body.note_type,
        author=body.author,
        color=body.color,
    )
    return ok(note)


@router.put("/projects/{project_id}/architecture/notes/{note_id}")
def update_note(project_id: str, note_id: str, body: NoteUpdate) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    updated = arch.update_note(note_id, content=body.content, color=body.color)
    if not updated:
        raise ApiException(404, "NOTE_NOT_FOUND", f"Note '{note_id}' not found")
    return ok(updated)


@router.delete("/projects/{project_id}/architecture/notes/{note_id}")
def delete_note(project_id: str, note_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    arch = _get_arch_state(idx_dir)
    deleted = arch.delete_note(note_id)
    if not deleted:
        raise ApiException(404, "NOTE_NOT_FOUND", f"Note '{note_id}' not found")
    return ok({"deleted": True})
```

- [ ] **Step 4: Register the router in server.py**

Add after line 565 in `src/codrag/server.py`:

```python
from codrag.api.routers.architecture import router as architecture_router
```

Add after line 583:

```python
app.include_router(architecture_router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
.venv/bin/pytest tests/test_architecture_router.py -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/api/routers/architecture.py src/codrag/server.py tests/test_architecture_router.py
git commit -m "feat(api): add architecture graph, notes, and state endpoints"
```

---

## Task 5: API Client Methods (Frontend)

**Files:**
- Modify: `packages/ui/src/api/client.ts`

- [ ] **Step 1: Add architecture methods to CodragApiClient**

Add these methods to the `CodragApiClient` class (after the existing endpoint methods, around line 600):

```typescript
// ── Architecture (Phase 71) ────────────────────────────────────────

async getArchitectureGraph(projectId: string, layerPath?: string): Promise<ArchGraphResponse> {
  const query: Record<string, string> = {};
  if (layerPath) query.layer_path = layerPath;
  return this.requestEnvelope<ArchGraphResponse>(
    `/projects/${encodeURIComponent(projectId)}/architecture/graph`,
    { query },
  );
}

async getArchitectureSummary(projectId: string): Promise<ArchSummaryResponse> {
  return this.requestEnvelope<ArchSummaryResponse>(
    `/projects/${encodeURIComponent(projectId)}/architecture/summary`,
  );
}

async getArchitectureState(projectId: string): Promise<ArchState> {
  return this.requestEnvelope<ArchState>(
    `/projects/${encodeURIComponent(projectId)}/architecture/state`,
  );
}

async saveArchitectureState(projectId: string, state: ArchState): Promise<{ saved: boolean }> {
  return this.requestEnvelope<{ saved: boolean }>(
    `/projects/${encodeURIComponent(projectId)}/architecture/state`,
    { method: 'PUT', body: state },
  );
}

async listArchitectureNotes(projectId: string): Promise<ArchNote[]> {
  return this.requestEnvelope<ArchNote[]>(
    `/projects/${encodeURIComponent(projectId)}/architecture/notes`,
  );
}

async createArchitectureNote(projectId: string, note: ArchNoteCreate): Promise<ArchNote> {
  return this.requestEnvelope<ArchNote>(
    `/projects/${encodeURIComponent(projectId)}/architecture/notes`,
    { method: 'POST', body: note },
  );
}

async updateArchitectureNote(projectId: string, noteId: string, updates: ArchNoteUpdate): Promise<ArchNote> {
  return this.requestEnvelope<ArchNote>(
    `/projects/${encodeURIComponent(projectId)}/architecture/notes/${encodeURIComponent(noteId)}`,
    { method: 'PUT', body: updates },
  );
}

async deleteArchitectureNote(projectId: string, noteId: string): Promise<{ deleted: boolean }> {
  return this.requestEnvelope<{ deleted: boolean }>(
    `/projects/${encodeURIComponent(projectId)}/architecture/notes/${encodeURIComponent(noteId)}`,
    { method: 'DELETE' },
  );
}
```

Also add the type imports at the top of `client.ts`:

```typescript
import type {
  ArchGraphResponse, ArchSummaryResponse, ArchState,
  ArchNote, ArchNoteCreate, ArchNoteUpdate,
} from '../types/architecture';
```

- [ ] **Step 2: Verify types compile**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui
npx tsc --noEmit --pretty 2>&1 | head -20
```

Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/api/client.ts
git commit -m "feat(ui): add architecture API client methods"
```

---

## Task 6: Custom React Flow Nodes

**Files:**
- Create: `packages/ui/src/components/architecture/ModuleNode.tsx`
- Create: `packages/ui/src/components/architecture/FileNode.tsx`
- Create: `packages/ui/src/components/architecture/ExternalRefNode.tsx`
- Create: `packages/ui/src/components/architecture/AnnotationNode.tsx`
- Create: `packages/ui/src/components/architecture/DependencyEdge.tsx`

- [ ] **Step 1: Create ModuleNode**

```tsx
// packages/ui/src/components/architecture/ModuleNode.tsx
import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { ModuleNodeData } from '../../types/architecture';

function ModuleNodeInner({ data, selected }: NodeProps & { data: ModuleNodeData }) {
  const statusColor = data.componentStatus === 'complete' ? 'border-blue-500' :
    data.componentStatus === 'deprecated' ? 'border-red-500' : 'border-amber-500';

  return (
    <div
      className={`
        rounded-lg border-2 bg-zinc-900 shadow-md px-4 py-3 min-w-[180px] max-w-[260px]
        transition-all duration-150
        ${statusColor}
        ${selected ? 'ring-2 ring-blue-400 shadow-blue-500/20' : ''}
        ${data.isHub ? 'shadow-purple-500/30 shadow-lg' : ''}
      `}
    >
      <Handle type="target" position={Position.Top} className="!bg-zinc-500 !w-2 !h-2" />

      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs text-zinc-500">{'📦'}</span>
        <span className="text-sm font-semibold text-zinc-100 truncate">{data.label}</span>
      </div>

      <div className="text-xs text-zinc-400 truncate mb-2">
        {data.description}
      </div>

      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <span>{data.fileCount} files</span>
        {data.noteCount > 0 && <span>{'💬'} {data.noteCount}</span>}
        {data.isHub && <span className="text-purple-400">{'★'} hub</span>}
      </div>

      {data.domainTags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {data.domainTags.slice(0, 3).map((tag) => (
            <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
              {tag}
            </span>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-zinc-500 !w-2 !h-2" />
    </div>
  );
}

export const ModuleNode = memo(ModuleNodeInner);
```

- [ ] **Step 2: Create FileNode**

```tsx
// packages/ui/src/components/architecture/FileNode.tsx
import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { FileNodeData } from '../../types/architecture';

const LANG_ICONS: Record<string, string> = {
  python: '🐍', typescript: '📘', tsx: '📘', javascript: '📒',
  rust: '🦀', go: '🐹', java: '☕', ruby: '💎',
};

function FileNodeInner({ data, selected }: NodeProps & { data: FileNodeData }) {
  const icon = LANG_ICONS[data.language] ?? '📄';

  return (
    <div
      className={`
        rounded-full border bg-zinc-900 shadow-sm px-4 py-2 min-w-[140px] max-w-[220px]
        transition-all duration-150
        ${selected ? 'border-blue-400 ring-2 ring-blue-400/50' : 'border-zinc-700'}
        ${data.isHub ? 'border-purple-500 shadow-purple-500/20' : ''}
      `}
    >
      <Handle type="target" position={Position.Top} className="!bg-zinc-500 !w-2 !h-2" />

      <div className="flex items-center gap-2">
        <span className="text-xs">{icon}</span>
        <span className="text-sm text-zinc-200 truncate">{data.label}</span>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-1">
        {data.lineCount > 0 && <span>{data.lineCount} lines</span>}
        {data.isHub && <span className="text-purple-400">{'★'} hub</span>}
        {data.noteCount > 0 && <span>{'💬'} {data.noteCount}</span>}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-zinc-500 !w-2 !h-2" />
    </div>
  );
}

export const FileNode = memo(FileNodeInner);
```

- [ ] **Step 3: Create ExternalRefNode**

```tsx
// packages/ui/src/components/architecture/ExternalRefNode.tsx
import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { ExternalRefNodeData } from '../../types/architecture';

function ExternalRefNodeInner({ data }: NodeProps & { data: ExternalRefNodeData }) {
  return (
    <div className="rounded-lg border-2 border-dashed border-zinc-600 bg-zinc-900/50 px-4 py-3 min-w-[160px] max-w-[220px] opacity-70">
      <Handle type="target" position={Position.Top} className="!bg-zinc-600 !w-2 !h-2" />

      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs text-zinc-500">{'→'}</span>
        <span className="text-sm text-zinc-400 truncate">{data.label}</span>
      </div>
      <div className="text-xs text-zinc-500 italic">click to navigate</div>

      <Handle type="source" position={Position.Bottom} className="!bg-zinc-600 !w-2 !h-2" />
    </div>
  );
}

export const ExternalRefNode = memo(ExternalRefNodeInner);
```

- [ ] **Step 4: Create AnnotationNode**

```tsx
// packages/ui/src/components/architecture/AnnotationNode.tsx
import React, { memo, useState, useCallback } from 'react';
import type { NodeProps } from '@xyflow/react';
import type { AnnotationNodeData } from '../../types/architecture';

const COLOR_MAP: Record<string, string> = {
  yellow: 'bg-yellow-900/40 border-yellow-700',
  blue: 'bg-blue-900/40 border-blue-700',
  green: 'bg-green-900/40 border-green-700',
  red: 'bg-red-900/40 border-red-700',
};

function AnnotationNodeInner({ data }: NodeProps & { data: AnnotationNodeData }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(data.content);
  const colorClass = COLOR_MAP[data.color] ?? COLOR_MAP.yellow;

  const typeLabel = data.noteType === 'adr' ? '📌 ADR' :
    data.noteType === 'agent_note' ? '🤖 Agent' : '💬 Note';

  const handleSave = useCallback(() => {
    setEditing(false);
    data.onEdit?.(data.noteId, draft);
  }, [data, draft]);

  return (
    <div className={`rounded-lg border ${colorClass} px-3 py-2 min-w-[160px] max-w-[240px] shadow-sm`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-zinc-300">{typeLabel}</span>
        <div className="flex gap-1">
          {data.onEdit && (
            <button
              onClick={() => setEditing(!editing)}
              className="text-[10px] text-zinc-500 hover:text-zinc-300 nodrag"
            >
              {editing ? 'cancel' : 'edit'}
            </button>
          )}
          {data.onDelete && (
            <button
              onClick={() => data.onDelete?.(data.noteId)}
              className="text-[10px] text-zinc-500 hover:text-red-400 nodrag"
            >
              {'×'}
            </button>
          )}
        </div>
      </div>

      {editing ? (
        <div className="nodrag">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleSave(); }}
            className="w-full bg-transparent border border-zinc-600 rounded text-xs text-zinc-200 p-1 resize-none"
            rows={3}
            autoFocus
          />
          <button
            onClick={handleSave}
            className="mt-1 text-[10px] px-2 py-0.5 bg-zinc-700 rounded text-zinc-300 hover:bg-zinc-600"
          >
            Save
          </button>
        </div>
      ) : (
        <div className="text-xs text-zinc-300 whitespace-pre-wrap">{data.content}</div>
      )}

      <div className="text-[10px] text-zinc-500 mt-1">— {data.author}</div>
    </div>
  );
}

export const AnnotationNode = memo(AnnotationNodeInner);
```

- [ ] **Step 5: Create DependencyEdge**

```tsx
// packages/ui/src/components/architecture/DependencyEdge.tsx
import React, { memo } from 'react';
import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react';

interface DependencyEdgeData {
  kind: 'imports' | 'calls' | 'inferred';
  count: number;
}

const KIND_STYLES: Record<string, { stroke: string; dashArray?: string }> = {
  imports: { stroke: '#3b82f6' },
  calls: { stroke: '#22c55e', dashArray: '6 3' },
  inferred: { stroke: '#f59e0b', dashArray: '3 3' },
};

function DependencyEdgeInner(props: EdgeProps & { data?: DependencyEdgeData }) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data } = props;
  const kind = data?.kind ?? 'imports';
  const count = data?.count ?? 1;
  const style = KIND_STYLES[kind] ?? KIND_STYLES.imports;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition,
  });

  return (
    <>
      <BaseEdge
        path={edgePath}
        style={{
          stroke: style.stroke,
          strokeWidth: count > 5 ? 3 : count > 1 ? 2 : 1.5,
          strokeDasharray: style.dashArray,
        }}
        markerEnd="url(#arrow)"
      />
      {count > 1 && (
        <foreignObject x={labelX - 12} y={labelY - 10} width={24} height={20} className="pointer-events-none">
          <div className="flex items-center justify-center w-full h-full">
            <span className="text-[10px] bg-zinc-800 text-zinc-400 px-1 rounded border border-zinc-700">
              {count}
            </span>
          </div>
        </foreignObject>
      )}
    </>
  );
}

export const DependencyEdge = memo(DependencyEdgeInner);
```

- [ ] **Step 6: Verify types compile**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui
npx tsc --noEmit --pretty 2>&1 | head -30
```

Expected: No errors from architecture components.

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/components/architecture/ModuleNode.tsx \
       packages/ui/src/components/architecture/FileNode.tsx \
       packages/ui/src/components/architecture/ExternalRefNode.tsx \
       packages/ui/src/components/architecture/AnnotationNode.tsx \
       packages/ui/src/components/architecture/DependencyEdge.tsx
git commit -m "feat(ui): add React Flow custom nodes and edges for architecture diagram"
```

---

## Task 7: Architecture Panel (Overview Card)

**Files:**
- Create: `packages/ui/src/components/architecture/ArchitectureDiagramPanel.tsx`

- [ ] **Step 1: Create the overview panel**

This is the small card shown in the dashboard grid. It displays a summary and a "View Diagram" button.

```tsx
// packages/ui/src/components/architecture/ArchitectureDiagramPanel.tsx
import React from 'react';
import type { ArchSummaryResponse } from '../../types/architecture';

export interface ArchitectureDiagramPanelProps {
  summary: ArchSummaryResponse | null;
  loading: boolean;
  error: string | null;
  onOpenDetail: () => void;
}

export function ArchitectureDiagramPanel({
  summary,
  loading,
  error,
  onOpenDetail,
}: ArchitectureDiagramPanelProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
        Loading architecture...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-sm">
        <span className="text-red-400">Failed to load architecture</span>
        <span className="text-zinc-500 text-xs">{error}</span>
      </div>
    );
  }

  if (!summary || !summary.exists) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-sm text-zinc-500">
        <span>No architecture data yet</span>
        <span className="text-xs">Run the pipeline to generate module synthesis</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-zinc-100">{summary.module_count}</div>
          <div className="text-xs text-zinc-500">Modules</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-zinc-100">{summary.file_count}</div>
          <div className="text-xs text-zinc-500">Files</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-zinc-100">{summary.note_count}</div>
          <div className="text-xs text-zinc-500">Notes</div>
        </div>
      </div>

      <button
        onClick={onOpenDetail}
        className="mt-auto w-full py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
      >
        Open Architecture Diagram
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/ui/src/components/architecture/ArchitectureDiagramPanel.tsx
git commit -m "feat(ui): add architecture diagram overview panel card"
```

---

## Task 8: Architecture Detail Overlay (Main Canvas)

**Files:**
- Create: `packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx`

This is the fullscreen overlay containing the React Flow canvas, toolbar, sidebar, and breadcrumb.

- [ ] **Step 1: Create the detail overlay**

```tsx
// packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx
import React, { useCallback, useMemo, useState, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  MiniMap,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  BackgroundVariant,
  type OnNodesChange,
  type Viewport,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import ELK from 'elkjs/lib/elk.bundled.js';

import type {
  ArchGraphResponse, ArchNote, ArchModule,
  ModuleNodeData, FileNodeData, ExternalRefNodeData, AnnotationNodeData,
  ArchBreadcrumb, ArchNoteCreate,
} from '../../types/architecture';
import { ModuleNode } from './ModuleNode';
import { FileNode } from './FileNode';
import { ExternalRefNode } from './ExternalRefNode';
import { AnnotationNode } from './AnnotationNode';
import { DependencyEdge } from './DependencyEdge';

const elk = new ELK();

const nodeTypes: NodeTypes = {
  module: ModuleNode as any,
  file: FileNode as any,
  externalRef: ExternalRefNode as any,
  annotation: AnnotationNode as any,
};

const edgeTypes: EdgeTypes = {
  dependency: DependencyEdge as any,
};

export interface ArchitectureDiagramDetailProps {
  graph: ArchGraphResponse | null;
  notes: ArchNote[];
  layerPath: string[];
  loading: boolean;
  onDrillInto: (moduleId: string) => void;
  onNavigateToLayer: (path: string[]) => void;
  onSavePositions: (positions: Array<{ id: string; x: number; y: number }>, viewport: Viewport) => void;
  onCreateNote: (note: ArchNoteCreate) => void;
  onUpdateNote: (noteId: string, content: string) => void;
  onDeleteNote: (noteId: string) => void;
  onSelectNode: (nodeId: string | null) => void;
  selectedNodeId: string | null;
  savedPositions?: Array<{ id: string; x: number; y: number }>;
  savedViewport?: Viewport;
}

function noteCountForNode(nodeId: string, notes: ArchNote[]): number {
  return notes.filter((n) => n.node_id === nodeId).length;
}

function buildFlowNodes(
  graph: ArchGraphResponse,
  notes: ArchNote[],
  savedPositions?: Array<{ id: string; x: number; y: number }>,
): Node[] {
  const posMap = new Map(savedPositions?.map((p) => [p.id, p]) ?? []);
  const flowNodes: Node[] = [];

  // Module nodes (Layer 0)
  for (const mod of graph.modules) {
    const pos = posMap.get(mod.id);
    flowNodes.push({
      id: mod.id,
      type: 'module',
      position: pos ? { x: pos.x, y: pos.y } : { x: 0, y: 0 },
      data: {
        label: mod.name,
        description: mod.description,
        fileCount: mod.file_count,
        hubFiles: mod.hub_files ?? [],
        domainTags: mod.domain_tags ?? [],
        componentStatus: mod.component_status ?? 'complete',
        confidence: mod.avg_confidence ?? 0,
        noteCount: noteCountForNode(mod.id, notes),
        isHub: (mod.hub_files?.length ?? 0) > 0,
      } satisfies ModuleNodeData,
    });
  }

  // File nodes (Layer 1+)
  for (const file of graph.files) {
    const pos = posMap.get(file.id);
    const name = file.path.split('/').pop() ?? file.path;
    flowNodes.push({
      id: file.id,
      type: 'file',
      position: pos ? { x: pos.x, y: pos.y } : { x: 0, y: 0 },
      data: {
        label: name,
        path: file.path,
        language: file.language,
        hubScore: file.hub_score,
        confidence: file.confidence,
        summary: file.summary,
        lineCount: file.line_count,
        noteCount: noteCountForNode(file.id, notes),
        isHub: file.hub_score > 5,
      } satisfies FileNodeData,
    });
  }

  // External ref nodes
  for (const ext of graph.external_refs) {
    const pos = posMap.get(ext.id);
    flowNodes.push({
      id: ext.id,
      type: 'externalRef',
      position: pos ? { x: pos.x, y: pos.y } : { x: 0, y: 0 },
      data: {
        label: ext.summary || ext.id,
        moduleId: ext.module_id,
        description: ext.summary,
      } satisfies ExternalRefNodeData,
    });
  }

  return flowNodes;
}

function buildFlowEdges(graph: ArchGraphResponse): Edge[] {
  return graph.edges.map((e, i) => ({
    id: `edge-${i}`,
    source: e.source,
    target: e.target,
    type: 'dependency',
    data: { kind: e.kind, count: e.count },
  }));
}

async function autoLayout(nodes: Node[], edges: Edge[]): Promise<Node[]> {
  const elkGraph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '60',
      'elk.layered.spacing.nodeNodeBetweenLayers': '80',
    },
    children: nodes.map((n) => ({
      id: n.id,
      width: 220,
      height: n.type === 'module' ? 120 : n.type === 'annotation' ? 80 : 60,
    })),
    edges: edges.map((e) => ({
      id: e.id,
      sources: [e.source],
      targets: [e.target],
    })),
  };

  const laid = await elk.layout(elkGraph);
  const posMap = new Map(laid.children?.map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]) ?? []);
  return nodes.map((n) => {
    const pos = posMap.get(n.id);
    return pos ? { ...n, position: pos } : n;
  });
}

function DiagramCanvas(props: ArchitectureDiagramDetailProps) {
  const {
    graph, notes, layerPath, loading,
    onDrillInto, onNavigateToLayer, onSavePositions,
    onCreateNote, onUpdateNote, onDeleteNote,
    onSelectNode, selectedNodeId,
    savedPositions, savedViewport,
  } = props;

  const initialNodes = useMemo(
    () => graph ? buildFlowNodes(graph, notes, savedPositions) : [],
    [graph, notes, savedPositions],
  );
  const initialEdges = useMemo(
    () => graph ? buildFlowEdges(graph) : [],
    [graph],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [needsLayout, setNeedsLayout] = useState(!savedPositions?.length);

  // Sync when graph data changes
  useEffect(() => {
    const newNodes = graph ? buildFlowNodes(graph, notes, savedPositions) : [];
    const newEdges = graph ? buildFlowEdges(graph) : [];
    setNodes(newNodes);
    setEdges(newEdges);
    setNeedsLayout(!savedPositions?.length);
  }, [graph, notes, savedPositions, setNodes, setEdges]);

  // Auto-layout on first render if no saved positions
  useEffect(() => {
    if (needsLayout && nodes.length > 0) {
      autoLayout(nodes, edges).then((laid) => {
        setNodes(laid);
        setNeedsLayout(false);
      });
    }
  }, [needsLayout, nodes.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAutoLayout = useCallback(async () => {
    const laid = await autoLayout(nodes, edges);
    setNodes(laid);
  }, [nodes, edges, setNodes]);

  const handleNodeDoubleClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.type === 'module') {
      onDrillInto(node.id);
    } else if (node.type === 'externalRef') {
      const data = node.data as ExternalRefNodeData;
      onNavigateToLayer([data.moduleId]);
    }
  }, [onDrillInto, onNavigateToLayer]);

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    onSelectNode(node.id);
  }, [onSelectNode]);

  const handlePaneClick = useCallback(() => {
    onSelectNode(null);
  }, [onSelectNode]);

  // Build breadcrumbs
  const breadcrumbs: ArchBreadcrumb[] = useMemo(() => {
    const crumbs: ArchBreadcrumb[] = [{ label: 'System Overview', layerPath: [] }];
    for (let i = 0; i < layerPath.length; i++) {
      crumbs.push({
        label: layerPath[i],
        layerPath: layerPath.slice(0, i + 1),
      });
    }
    return crumbs;
  }, [layerPath]);

  // Selected node details for sidebar
  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );
  const selectedNodeNotes = useMemo(
    () => selectedNodeId ? notes.filter((n) => n.node_id === selectedNodeId) : [],
    [notes, selectedNodeId],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500">
        Loading architecture diagram...
      </div>
    );
  }

  if (!graph || !graph.exists) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-zinc-500">
        <span className="text-lg">No architecture data</span>
        <span className="text-sm">Run the pipeline to generate module synthesis first.</span>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Main canvas area */}
      <div className="flex-1 flex flex-col">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1 px-4 py-2 border-b border-zinc-800 bg-zinc-950 text-sm">
          {breadcrumbs.map((crumb, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="text-zinc-600 mx-1">{'›'}</span>}
              <button
                onClick={() => onNavigateToLayer(crumb.layerPath)}
                className={`px-2 py-0.5 rounded hover:bg-zinc-800 transition-colors ${
                  i === breadcrumbs.length - 1 ? 'text-zinc-200 font-medium' : 'text-zinc-500'
                }`}
              >
                {crumb.label}
              </button>
            </React.Fragment>
          ))}
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 bg-zinc-950">
          <button
            onClick={handleAutoLayout}
            className="text-xs px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
          >
            Auto-layout
          </button>
          {layerPath.length > 0 && (
            <button
              onClick={() => onNavigateToLayer(layerPath.slice(0, -1))}
              className="text-xs px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
            >
              {'← Back'}
            </button>
          )}
          <div className="ml-auto text-xs text-zinc-500">
            {graph.stats.total_modules > 0 && `${graph.stats.total_modules} modules · `}
            {graph.stats.total_files > 0 && `${graph.stats.total_files} files · `}
            {graph.stats.total_edges} edges
          </div>
        </div>

        {/* React Flow Canvas */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeDoubleClick={handleNodeDoubleClick}
            onNodeClick={handleNodeClick}
            onPaneClick={handlePaneClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            defaultViewport={savedViewport ?? { x: 0, y: 0, zoom: 0.8 }}
            fitView={!savedViewport}
            colorMode="dark"
            minZoom={0.1}
            maxZoom={2}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#27272a" />
            <MiniMap
              nodeColor={(n) => n.type === 'module' ? '#3b82f6' : n.type === 'externalRef' ? '#6b7280' : '#a855f7'}
              className="!bg-zinc-900 !border-zinc-700"
            />
            <Controls className="!bg-zinc-900 !border-zinc-700 [&>button]:!bg-zinc-800 [&>button]:!border-zinc-700 [&>button]:!text-zinc-400" />

            {/* Arrow marker definition */}
            <svg>
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#6b7280" />
                </marker>
              </defs>
            </svg>
          </ReactFlow>
        </div>
      </div>

      {/* Sidebar */}
      {selectedNode && (
        <div className="w-80 border-l border-zinc-800 bg-zinc-950 overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-zinc-200 truncate">
                {(selectedNode.data as any).label}
              </h3>
              <button
                onClick={() => onSelectNode(null)}
                className="text-zinc-500 hover:text-zinc-300 text-xs"
              >
                {'×'}
              </button>
            </div>

            {/* Description */}
            {(selectedNode.data as any).description && (
              <p className="text-xs text-zinc-400 mb-4">{(selectedNode.data as any).description}</p>
            )}

            {/* Metadata */}
            <div className="text-xs text-zinc-500 space-y-1 mb-4">
              {selectedNode.type === 'module' && (
                <>
                  <div>Files: {(selectedNode.data as ModuleNodeData).fileCount}</div>
                  <div>Status: {(selectedNode.data as ModuleNodeData).componentStatus}</div>
                  <div>Confidence: {((selectedNode.data as ModuleNodeData).confidence * 100).toFixed(0)}%</div>
                </>
              )}
              {selectedNode.type === 'file' && (
                <>
                  <div>Path: {(selectedNode.data as FileNodeData).path}</div>
                  <div>Language: {(selectedNode.data as FileNodeData).language}</div>
                  <div>Lines: {(selectedNode.data as FileNodeData).lineCount}</div>
                </>
              )}
            </div>

            {/* Notes section */}
            <div className="border-t border-zinc-800 pt-3">
              <h4 className="text-xs font-medium text-zinc-400 mb-2">
                Notes ({selectedNodeNotes.length})
              </h4>
              {selectedNodeNotes.map((note) => (
                <div key={note.id} className="mb-2 p-2 rounded bg-zinc-900 border border-zinc-800">
                  <div className="flex justify-between items-start">
                    <span className="text-[10px] text-zinc-500">
                      {note.note_type === 'adr' ? '📌 ADR' : note.note_type === 'agent_note' ? '🤖 Agent' : '💬'}
                    </span>
                    <button
                      onClick={() => onDeleteNote(note.id)}
                      className="text-[10px] text-zinc-600 hover:text-red-400"
                    >
                      delete
                    </button>
                  </div>
                  <p className="text-xs text-zinc-300 mt-1">{note.content}</p>
                  <span className="text-[10px] text-zinc-600">— {note.author}</span>
                </div>
              ))}

              {/* Add note form */}
              <AddNoteForm nodeId={selectedNodeId!} onCreateNote={onCreateNote} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AddNoteForm({ nodeId, onCreateNote }: { nodeId: string; onCreateNote: (n: ArchNoteCreate) => void }) {
  const [content, setContent] = useState('');
  const [noteType, setNoteType] = useState<'comment' | 'adr'>('comment');

  const handleSubmit = useCallback(() => {
    if (!content.trim()) return;
    onCreateNote({ node_id: nodeId, content: content.trim(), note_type: noteType, author: 'user' });
    setContent('');
  }, [content, noteType, nodeId, onCreateNote]);

  return (
    <div className="mt-2">
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Add a note..."
        className="w-full bg-zinc-900 border border-zinc-700 rounded text-xs text-zinc-200 p-2 resize-none"
        rows={2}
      />
      <div className="flex items-center gap-2 mt-1">
        <select
          value={noteType}
          onChange={(e) => setNoteType(e.target.value as 'comment' | 'adr')}
          className="text-[10px] bg-zinc-800 border border-zinc-700 rounded px-1 py-0.5 text-zinc-400"
        >
          <option value="comment">Comment</option>
          <option value="adr">ADR</option>
        </select>
        <button
          onClick={handleSubmit}
          disabled={!content.trim()}
          className="text-[10px] px-2 py-0.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-white"
        >
          Add
        </button>
      </div>
    </div>
  );
}

export function ArchitectureDiagramDetail(props: ArchitectureDiagramDetailProps) {
  return (
    <ReactFlowProvider>
      <DiagramCanvas {...props} />
    </ReactFlowProvider>
  );
}
```

- [ ] **Step 2: Verify types compile**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui
npx tsc --noEmit --pretty 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx
git commit -m "feat(ui): add architecture diagram detail overlay with React Flow canvas"
```

---

## Task 9: Barrel Exports and Panel Registry

**Files:**
- Create: `packages/ui/src/components/architecture/index.ts`
- Modify: `packages/ui/src/config/panelRegistry.ts`
- Modify: `packages/ui/src/index.ts`

- [ ] **Step 1: Create barrel exports**

```typescript
// packages/ui/src/components/architecture/index.ts
export { ModuleNode } from './ModuleNode';
export { FileNode } from './FileNode';
export { ExternalRefNode } from './ExternalRefNode';
export { AnnotationNode } from './AnnotationNode';
export { DependencyEdge } from './DependencyEdge';
export { ArchitectureDiagramPanel } from './ArchitectureDiagramPanel';
export type { ArchitectureDiagramPanelProps } from './ArchitectureDiagramPanel';
export { ArchitectureDiagramDetail } from './ArchitectureDiagramDetail';
export type { ArchitectureDiagramDetailProps } from './ArchitectureDiagramDetail';
```

- [ ] **Step 2: Add panel to registry**

In `packages/ui/src/config/panelRegistry.ts`:

Add to the icon imports at the top:
```typescript
import { ..., Network } from 'lucide-react';
```

Add before the closing `];` of the `PANEL_REGISTRY` array:
```typescript
  {
    id: 'architecture',
    title: 'Architecture',
    description: 'Interactive architecture diagram: visualize modules, dependencies, and annotations. Drill down from system overview to individual files.',
    icon: Network,
    minHeight: 6,
    defaultHeight: 8,
    category: 'context',
    closeable: true,
    resizable: true,
    fullWidth: true,
  },
```

- [ ] **Step 3: Add exports to main index.ts**

Add to `packages/ui/src/index.ts` after the Roadmap component exports (around line 219):

```typescript
// Components - Architecture Diagram (Phase 71)
export { ArchitectureDiagramPanel, ArchitectureDiagramDetail } from './components/architecture';
export type { ArchitectureDiagramPanelProps, ArchitectureDiagramDetailProps } from './components/architecture';
```

- [ ] **Step 4: Verify everything compiles**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui
npx tsc --noEmit --pretty 2>&1 | head -20
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/architecture/index.ts \
       packages/ui/src/config/panelRegistry.ts \
       packages/ui/src/index.ts
git commit -m "feat(ui): register architecture panel and export components"
```

---

## Task 10: useArchitectureSystem Hook

**Files:**
- Create: `src/codrag/dashboard/src/hooks/useArchitectureSystem.ts`

This is the main dashboard hook that manages state, API calls, and persistence for the architecture diagram.

- [ ] **Step 1: Create the hook**

```typescript
// src/codrag/dashboard/src/hooks/useArchitectureSystem.ts
import { useCallback, useEffect, useRef, useState } from 'react';
import { useApiClient } from '@prep/ui';
import type {
  ArchGraphResponse, ArchSummaryResponse, ArchNote,
  ArchState, ArchNoteCreate, ArchNodePosition,
} from '@prep/ui';
import type { Viewport } from '@xyflow/react';

export interface UseArchitectureSystemReturn {
  // Data
  summary: ArchSummaryResponse | null;
  graph: ArchGraphResponse | null;
  notes: ArchNote[];
  // Navigation
  layerPath: string[];
  // UI State
  loading: boolean;
  error: string | null;
  selectedNodeId: string | null;
  // Saved layout
  savedPositions: ArchNodePosition[];
  savedViewport: Viewport | undefined;
  // Actions
  drillInto: (moduleId: string) => void;
  navigateToLayer: (path: string[]) => void;
  selectNode: (nodeId: string | null) => void;
  savePositions: (positions: ArchNodePosition[], viewport: Viewport) => void;
  createNote: (note: ArchNoteCreate) => void;
  updateNote: (noteId: string, content: string) => void;
  deleteNote: (noteId: string) => void;
}

export function useArchitectureSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal },
): UseArchitectureSystemReturn {
  const api = useApiClient();

  const [summary, setSummary] = useState<ArchSummaryResponse | null>(null);
  const [graph, setGraph] = useState<ArchGraphResponse | null>(null);
  const [notes, setNotes] = useState<ArchNote[]>([]);
  const [archState, setArchState] = useState<ArchState | null>(null);
  const [layerPath, setLayerPath] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const saveDebounce = useRef<NodeJS.Timeout | null>(null);

  // ── Hydrate on project change ────────────────────────────────────

  useEffect(() => {
    setSummary(null);
    setGraph(null);
    setNotes([]);
    setArchState(null);
    setLayerPath([]);
    setError(null);
    setSelectedNodeId(null);

    if (!selectedProjectId) return;

    setLoading(true);

    Promise.all([
      api.getArchitectureSummary(selectedProjectId),
      api.getArchitectureGraph(selectedProjectId),
      api.listArchitectureNotes(selectedProjectId),
      api.getArchitectureState(selectedProjectId),
    ])
      .then(([sum, g, n, s]) => {
        if (options?.signal?.aborted) return;
        setSummary(sum);
        setGraph(g);
        setNotes(n);
        setArchState(s);
      })
      .catch((err) => {
        if (options?.signal?.aborted) return;
        setError(err.message ?? 'Failed to load architecture');
      })
      .finally(() => {
        if (!options?.signal?.aborted) setLoading(false);
      });
  }, [selectedProjectId, api]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Navigation ───────────────────────────────────────────────────

  const fetchGraph = useCallback(
    (path: string[]) => {
      if (!selectedProjectId) return;
      setLoading(true);
      const layerParam = path.length > 0 ? path[path.length - 1] : undefined;
      api
        .getArchitectureGraph(selectedProjectId, layerParam)
        .then((g) => {
          if (!options?.signal?.aborted) setGraph(g);
        })
        .catch((err) => {
          if (!options?.signal?.aborted) setError(err.message);
        })
        .finally(() => {
          if (!options?.signal?.aborted) setLoading(false);
        });
    },
    [selectedProjectId, api, options?.signal],
  );

  const drillInto = useCallback(
    (moduleId: string) => {
      const newPath = [...layerPath, moduleId];
      setLayerPath(newPath);
      setSelectedNodeId(null);
      fetchGraph(newPath);
    },
    [layerPath, fetchGraph],
  );

  const navigateToLayer = useCallback(
    (path: string[]) => {
      setLayerPath(path);
      setSelectedNodeId(null);
      fetchGraph(path);
    },
    [fetchGraph],
  );

  // ── Layout persistence ───────────────────────────────────────────

  const savePositions = useCallback(
    (positions: ArchNodePosition[], viewport: Viewport) => {
      if (!selectedProjectId || !archState) return;

      const layerKey = layerPath.length === 0 ? 'root' : layerPath.join('/');
      const newState: ArchState = {
        ...archState,
        layouts: {
          ...archState.layouts,
          [layerKey]: {
            layer_path: layerKey,
            positions,
            viewport,
          },
        },
      };
      setArchState(newState);

      // Debounced save
      if (saveDebounce.current) clearTimeout(saveDebounce.current);
      saveDebounce.current = setTimeout(() => {
        api.saveArchitectureState(selectedProjectId, newState).catch(() => {});
      }, 1000);
    },
    [selectedProjectId, archState, layerPath, api],
  );

  // ── Notes CRUD ───────────────────────────────────────────────────

  const createNote = useCallback(
    (note: ArchNoteCreate) => {
      if (!selectedProjectId) return;
      api
        .createArchitectureNote(selectedProjectId, note)
        .then((created) => {
          setNotes((prev) => [...prev, created]);
        })
        .catch(() => {});
    },
    [selectedProjectId, api],
  );

  const updateNote = useCallback(
    (noteId: string, content: string) => {
      if (!selectedProjectId) return;
      // Optimistic update
      setNotes((prev) =>
        prev.map((n) => (n.id === noteId ? { ...n, content } : n)),
      );
      api.updateArchitectureNote(selectedProjectId, noteId, { content }).catch((err) => {
        // Revert on error
        api.listArchitectureNotes(selectedProjectId).then(setNotes).catch(() => {});
      });
    },
    [selectedProjectId, api],
  );

  const deleteNote = useCallback(
    (noteId: string) => {
      if (!selectedProjectId) return;
      // Optimistic delete
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
      api.deleteArchitectureNote(selectedProjectId, noteId).catch(() => {
        api.listArchitectureNotes(selectedProjectId).then(setNotes).catch(() => {});
      });
    },
    [selectedProjectId, api],
  );

  // ── Derived: saved layout for current layer ──────────────────────

  const layerKey = layerPath.length === 0 ? 'root' : layerPath.join('/');
  const currentLayout = archState?.layouts[layerKey];
  const savedPositions = currentLayout?.positions ?? [];
  const savedViewport = currentLayout?.viewport as Viewport | undefined;

  return {
    summary,
    graph,
    notes,
    layerPath,
    loading,
    error,
    selectedNodeId,
    savedPositions,
    savedViewport,
    drillInto,
    navigateToLayer,
    selectNode: setSelectedNodeId,
    savePositions,
    createNote,
    updateNote,
    deleteNote,
  };
}
```

- [ ] **Step 2: Verify types compile**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
npx tsc --noEmit --project src/codrag/dashboard/tsconfig.json 2>&1 | head -20
```

If the dashboard doesn't have its own tsconfig, try:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
npm run typecheck 2>&1 | head -40
```

- [ ] **Step 3: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useArchitectureSystem.ts
git commit -m "feat(dashboard): add useArchitectureSystem hook for architecture diagram state"
```

---

## Task 11: Wire into useDashboardPanels

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`

This task wires the architecture panel into the dashboard's panel content and detail maps. This requires reading the current file to find exact insertion points.

- [ ] **Step 1: Read useDashboardPanels.tsx**

Read the file to find:
1. Where other system hooks are called (e.g., `useRoadmapSystem`)
2. Where `panelContent` entries are defined
3. Where `panelDetails` entries are defined

- [ ] **Step 2: Add useArchitectureSystem hook call**

At the top of `useDashboardPanels`, alongside other system hook calls:

```typescript
import { useArchitectureSystem } from './useArchitectureSystem';
```

Inside the function body, alongside other hook calls:
```typescript
const archProps = useArchitectureSystem(selectedProjectId, { signal: abortSignal });
```

- [ ] **Step 3: Add panelContent entry**

In the `panelContent` useMemo, add:

```typescript
architecture: (
  <ArchitectureDiagramPanel
    summary={archProps.summary}
    loading={archProps.loading}
    error={archProps.error}
    onOpenDetail={() => layoutApi?.openDetails('architecture')}
  />
),
```

Also import the panel component:
```typescript
import { ArchitectureDiagramPanel, ArchitectureDiagramDetail } from '@prep/ui';
```

- [ ] **Step 4: Add panelDetails entry**

In the `panelDetails` useMemo, add:

```typescript
architecture: (
  <ArchitectureDiagramDetail
    graph={archProps.graph}
    notes={archProps.notes}
    layerPath={archProps.layerPath}
    loading={archProps.loading}
    onDrillInto={archProps.drillInto}
    onNavigateToLayer={archProps.navigateToLayer}
    onSavePositions={archProps.savePositions}
    onCreateNote={archProps.createNote}
    onUpdateNote={archProps.updateNote}
    onDeleteNote={archProps.deleteNote}
    onSelectNode={archProps.selectNode}
    selectedNodeId={archProps.selectedNodeId}
    savedPositions={archProps.savedPositions}
    savedViewport={archProps.savedViewport}
  />
),
```

- [ ] **Step 5: Verify compilation**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
npm run typecheck 2>&1 | head -40
```

- [ ] **Step 6: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useDashboardPanels.tsx
git commit -m "feat(dashboard): wire architecture diagram into panel system"
```

---

## Task 12: Add React Flow CSS and Smoke Test

**Files:**
- Possibly modify: `src/codrag/dashboard/src/App.tsx` or main CSS file

- [ ] **Step 1: Verify React Flow CSS is loaded**

React Flow's CSS is imported inside `ArchitectureDiagramDetail.tsx` via `import '@xyflow/react/dist/style.css'`. Check that Vite bundles it correctly:

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
npm run build 2>&1 | tail -20
```

If the import fails, add it to the dashboard's main CSS imports instead.

- [ ] **Step 2: Start dev server and smoke test**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
npm run dev
```

Manual verification:
1. Open dashboard at `http://localhost:5174`
2. Select a project with completed pipeline
3. Architecture panel should appear in the panel picker
4. Add the Architecture panel to the grid
5. Panel should show module/file/note counts
6. Click "Open Architecture Diagram" to open the detail overlay
7. Module nodes should appear with ELK auto-layout
8. Double-click a module to drill into it (shows file nodes)
9. Use breadcrumb to navigate back
10. Click a node to open sidebar with notes
11. Add a note — it should persist across page reloads

- [ ] **Step 3: Run all tests**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
.venv/bin/pytest tests/test_architecture_state.py tests/test_architecture_router.py -v
npm run typecheck
```

Expected: All backend tests pass, no type errors.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix(dashboard): resolve architecture diagram integration issues"
```

---

## Task 13: MCP Context Integration

**Files:**
- Modify: `src/codrag/mcp/server.py`

This adds user-curated architecture context to the `codrag` MCP tool response so that AI agents see module structure and annotations.

- [ ] **Step 1: Read the MCP server's tool_context method**

Read `src/codrag/mcp/server.py` around the `tool_context` method (lines 827-938) to find exactly where to add architecture context.

- [ ] **Step 2: Add architecture context assembly**

Create a helper that formats architecture data as markdown for MCP responses. Add this to `src/codrag/api/routers/architecture.py`:

```python
@router.get("/projects/{project_id}/architecture/context")
def get_architecture_context(project_id: str) -> Dict[str, Any]:
    """Return user-curated architecture as structured text for MCP consumption."""
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)

    modules = _load_modules(idx_dir)
    if not modules:
        return ok({"text": "", "exists": False})

    arch = _get_arch_state(idx_dir)
    notes = arch.list_notes()
    trace_edges = _load_trace_edges(idx_dir)
    file_to_module = _build_file_to_module_map(modules)
    module_edges = _aggregate_module_edges(trace_edges, file_to_module)

    # Build notes index by node_id
    notes_by_node: Dict[str, List[Dict[str, Any]]] = {}
    for n in notes:
        nid = n.get("node_id", "")
        notes_by_node.setdefault(nid, []).append(n)

    # Build dependency map
    dep_map: Dict[str, List[str]] = {}
    for e in module_edges:
        dep_map.setdefault(e["source"], []).append(e["target"])

    lines: List[str] = []
    lines.append(f"### Architecture ({len(modules)} modules, user-curated)")
    lines.append("")

    for m in sorted(modules, key=lambda x: -x.get("file_count", 0)):
        mid = m["module_id"]
        name = m.get("name", mid)
        fc = m.get("file_count", 0)
        deps = dep_map.get(mid, [])
        dep_str = ", ".join(deps) if deps else "none"
        line = f"- **{name}** ({fc} files) → depends on: {dep_str}"
        lines.append(line)

        # Add notes for this module
        for note in notes_by_node.get(mid, []):
            nt = note.get("note_type", "comment")
            prefix = "📌" if nt == "adr" else "🤖" if nt == "agent_note" else "💬"
            lines.append(f"  {prefix} \"{note.get('content', '')}\"")

    lines.append("")

    return ok({"text": "\n".join(lines), "exists": True})
```

- [ ] **Step 3: Inject architecture context into MCP tool_context**

In `src/codrag/mcp/server.py`, in the `tool_context` method, after the main context is assembled and before `result["_to_markdown"]` is built, add:

```python
# Phase 71: Architecture context (user-curated)
try:
    arch_data = await self._api_get(f"/projects/{project_id}/architecture/context")
    if isinstance(arch_data, dict) and arch_data.get("exists"):
        arch_text = arch_data.get("text", "")
        if arch_text:
            md_parts.append("\n---\n")
            md_parts.append(arch_text)
except Exception as e:
    logger.debug("Architecture context failed: %s", e)
```

- [ ] **Step 4: Run backend tests**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
.venv/bin/pytest tests/test_architecture_router.py tests/test_architecture_state.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/codrag/api/routers/architecture.py src/codrag/mcp/server.py
git commit -m "feat(mcp): inject user-curated architecture context into codrag tool response"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Install dependencies | `package.json` |
| 2 | TypeScript types | `types/architecture.ts`, `index.ts` |
| 3 | Backend state persistence | `architecture_state.py`, tests |
| 4 | Backend router | `architecture.py`, `server.py`, tests |
| 5 | API client methods | `client.ts` |
| 6 | Custom React Flow nodes/edges | 5 component files |
| 7 | Panel overview card | `ArchitectureDiagramPanel.tsx` |
| 8 | Detail overlay (main canvas) | `ArchitectureDiagramDetail.tsx` |
| 9 | Barrel exports + registry | `index.ts`, `panelRegistry.ts` |
| 10 | Dashboard hook | `useArchitectureSystem.ts` |
| 11 | Wire into dashboard | `useDashboardPanels.tsx` |
| 12 | Smoke test + build | CSS, manual verification |
| 13 | MCP context integration | `architecture.py`, `server.py` |

Total: ~16 new files, 5 modified files, 13 tasks, ~13 commits.
