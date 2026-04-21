# Phase 71B: Architecture Governance & Paperclip Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ACR governance, issue linking, agent briefings, and governance UI overlays to the existing Phase 71A architecture diagram.

**Architecture:** Phase A built the interactive ReactFlow canvas with modules, files, notes, and drill-down navigation. Phase B layers governance on top: a Python ACR lifecycle module, 8 new REST endpoints, new TypeScript types, and 3 new UI components (IssueBadge, ACRPanel, EntryPointNode) plus refactoring the monolithic ArchitectureDiagramDetail.tsx into extracted sub-components (DiagramSidebar, DiagramToolbar, BreadcrumbNav).

**Tech Stack:** Python/FastAPI backend, React/TypeScript frontend, @xyflow/react v12, JSON file persistence

---

## File Map

### New Files
| File | Purpose |
|------|---------|
| `src/prep/core/architecture_acr.py` | ACR + issue-link lifecycle (CRUD, approve, reject, link/unlink) |
| `packages/ui/src/components/architecture/BreadcrumbNav.tsx` | Extracted breadcrumb navigation component |
| `packages/ui/src/components/architecture/DiagramToolbar.tsx` | Extracted toolbar with layout/filter/stats controls |
| `packages/ui/src/components/architecture/DiagramSidebar.tsx` | Extracted sidebar inspector with notes, issues, ACRs |
| `packages/ui/src/components/architecture/EntryPointNode.tsx` | Diamond-shaped node for API surfaces |
| `packages/ui/src/components/architecture/IssueBadge.tsx` | Small overlay badge showing issue/ACR counts on nodes |
| `packages/ui/src/components/architecture/ACRPanel.tsx` | ACR review panel inside DiagramSidebar |
| `tests/test_architecture_acr.py` | Tests for ACR lifecycle module |
| `tests/test_architecture_api_phase_b.py` | Tests for Phase B API endpoints |

### Modified Files
| File | Changes |
|------|---------|
| `src/prep/core/architecture_state.py` | Add issue_links persistence (load/save/link/unlink) |
| `src/prep/api/routers/architecture.py` | Add 8 Phase B endpoints (ACRs, issues, create-task, briefing) |
| `packages/ui/src/types/architecture.ts` | Add ACR, LinkedIssue, EntryPointNodeData types |
| `packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx` | Replace inline breadcrumb/toolbar/sidebar with extracted components |
| `packages/ui/src/components/architecture/ModuleNode.tsx` | Add IssueBadge overlay |
| `packages/ui/src/components/architecture/FileNode.tsx` | Add IssueBadge overlay |
| `packages/ui/src/components/architecture/index.ts` | Export new components |
| `packages/ui/src/api/client.ts` | Add Phase B API methods |
| `src/prep/dashboard/src/hooks/useArchitectureSystem.ts` | Add ACR + issue state/actions |
| `src/prep/mcp/server.py` | Expand codegen context to include ACRs |

---

## Task 1: Add Phase B TypeScript Types

**Files:**
- Modify: `packages/ui/src/types/architecture.ts`

- [ ] **Step 1: Add ACR, LinkedIssue, and EntryPointNodeData types**

Append to `packages/ui/src/types/architecture.ts` after the existing `AnnotationNodeData` interface:

```typescript
// ── ACRs (Phase B) ────────────────────────────────────────────────

export type ACRStatus = 'proposed' | 'approved' | 'in_progress' | 'completed' | 'rejected';

/** Architecture Change Request */
export interface ACR {
  id: string;
  title: string;
  description: string;
  status: ACRStatus;
  source_type: 'agent' | 'user' | 'audit';
  source_agent: string;
  affected_nodes: string[];
  paperclip_issue_id?: string;
  created_at: string;
  approved_at?: string;
}

/** Request body for creating an ACR */
export interface ACRCreate {
  title: string;
  description: string;
  source_type: 'agent' | 'user' | 'audit';
  source_agent: string;
  affected_nodes: string[];
}

// ── Issue Linking (Phase B) ───────────────────────────────────────

export type IssuePriority = 'P0' | 'P1' | 'P2' | 'P3';
export type IssueStatus = 'open' | 'in_progress' | 'closed';

/** A Paperclip issue linked to a diagram node */
export interface LinkedIssue {
  paperclip_issue_id: string;
  title: string;
  priority: IssuePriority;
  status: IssueStatus;
  node_id: string;
}

/** Request body for linking an issue to a node */
export interface LinkIssueRequest {
  paperclip_issue_id: string;
  title: string;
  priority: IssuePriority;
  status: IssueStatus;
}

// ── Entry Point Node (Phase B) ────────────────────────────────────

export interface EntryPointNodeData {
  label: string;
  path: string;
  entryType: 'api_route' | 'cli_command' | 'main' | 'webhook';
  noteCount: number;
}
```

- [ ] **Step 2: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS (no errors in architecture.ts)

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/types/architecture.ts
git commit -m "feat(arch): add Phase B types — ACR, LinkedIssue, EntryPointNodeData"
```

---

## Task 2: Build ACR Lifecycle Module (Backend)

**Files:**
- Create: `src/prep/core/architecture_acr.py`
- Modify: `src/prep/core/architecture_state.py`
- Test: `tests/test_architecture_acr.py`

- [ ] **Step 1: Write failing tests for ACR lifecycle**

Create `tests/test_architecture_acr.py`:

```python
"""Tests for architecture ACR and issue-link lifecycle."""
import json
import tempfile
from pathlib import Path

import pytest

from prep.core.architecture_acr import ArchitectureACRManager


@pytest.fixture
def acr_mgr(tmp_path: Path) -> ArchitectureACRManager:
    return ArchitectureACRManager(tmp_path)


class TestACRLifecycle:
    def test_create_acr(self, acr_mgr: ArchitectureACRManager) -> None:
        acr = acr_mgr.create_acr(
            title="Split Core into Core + Utils",
            description="Core module has too many responsibilities",
            source_type="agent",
            source_agent="researcher",
            affected_nodes=["mod_core"],
        )
        assert acr["id"].startswith("acr_")
        assert acr["title"] == "Split Core into Core + Utils"
        assert acr["status"] == "proposed"
        assert acr["affected_nodes"] == ["mod_core"]

    def test_list_acrs(self, acr_mgr: ArchitectureACRManager) -> None:
        acr_mgr.create_acr("A", "desc", "user", "user", ["n1"])
        acr_mgr.create_acr("B", "desc", "agent", "researcher", ["n2"])
        acrs = acr_mgr.list_acrs()
        assert len(acrs) == 2

    def test_approve_acr(self, acr_mgr: ArchitectureACRManager) -> None:
        acr = acr_mgr.create_acr("A", "desc", "user", "user", ["n1"])
        approved = acr_mgr.approve_acr(acr["id"], approved_by="user")
        assert approved is not None
        assert approved["status"] == "approved"
        assert approved["approved_at"] is not None
        assert approved["approved_by"] == "user"

    def test_reject_acr(self, acr_mgr: ArchitectureACRManager) -> None:
        acr = acr_mgr.create_acr("A", "desc", "user", "user", ["n1"])
        rejected = acr_mgr.reject_acr(acr["id"])
        assert rejected is not None
        assert rejected["status"] == "rejected"

    def test_approve_nonexistent_returns_none(self, acr_mgr: ArchitectureACRManager) -> None:
        assert acr_mgr.approve_acr("acr_nope") is None

    def test_reject_nonexistent_returns_none(self, acr_mgr: ArchitectureACRManager) -> None:
        assert acr_mgr.reject_acr("acr_nope") is None

    def test_get_acrs_for_node(self, acr_mgr: ArchitectureACRManager) -> None:
        acr_mgr.create_acr("A", "d", "user", "user", ["n1", "n2"])
        acr_mgr.create_acr("B", "d", "user", "user", ["n2", "n3"])
        acr_mgr.create_acr("C", "d", "user", "user", ["n3"])
        assert len(acr_mgr.get_acrs_for_node("n2")) == 2
        assert len(acr_mgr.get_acrs_for_node("n1")) == 1


class TestIssueLinkLifecycle:
    def test_link_issue(self, acr_mgr: ArchitectureACRManager) -> None:
        link = acr_mgr.link_issue(
            node_id="mod_auth",
            paperclip_issue_id="PAPER-123",
            title="Migrate JWT to OAuth2",
            priority="P1",
            status="open",
        )
        assert link["node_id"] == "mod_auth"
        assert link["paperclip_issue_id"] == "PAPER-123"

    def test_list_issue_links(self, acr_mgr: ArchitectureACRManager) -> None:
        acr_mgr.link_issue("n1", "P-1", "Issue 1", "P1", "open")
        acr_mgr.link_issue("n1", "P-2", "Issue 2", "P2", "open")
        acr_mgr.link_issue("n2", "P-3", "Issue 3", "P1", "open")
        assert len(acr_mgr.get_issues_for_node("n1")) == 2
        assert len(acr_mgr.get_issues_for_node("n2")) == 1
        assert len(acr_mgr.list_issue_links()) == 3

    def test_unlink_issue(self, acr_mgr: ArchitectureACRManager) -> None:
        acr_mgr.link_issue("n1", "P-1", "Issue 1", "P1", "open")
        assert acr_mgr.unlink_issue("n1", "P-1") is True
        assert len(acr_mgr.get_issues_for_node("n1")) == 0

    def test_unlink_nonexistent_returns_false(self, acr_mgr: ArchitectureACRManager) -> None:
        assert acr_mgr.unlink_issue("n1", "NOPE") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_architecture_acr.py -v`
Expected: FAIL (ModuleNotFoundError: cannot import 'architecture_acr')

- [ ] **Step 3: Implement ArchitectureACRManager**

Create `src/prep/core/architecture_acr.py`:

```python
"""
Architecture ACR and issue-link lifecycle — Phase 71B

Manages Architecture Change Requests (ACRs) and node-to-Paperclip-issue links.
Persists to JSON files in <index_dir>/architecture/.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ArchitectureACRManager:
    """CRUD for ACRs and issue links, stored as JSON in the architecture dir."""

    def __init__(self, index_dir: Path):
        self._arch_dir = Path(index_dir) / "architecture"
        self._acrs_path = self._arch_dir / "acrs.json"
        self._links_path = self._arch_dir / "issue_links.json"

    def _ensure_dir(self) -> None:
        self._arch_dir.mkdir(parents=True, exist_ok=True)

    # ── ACR persistence ────────────────────────────────────────────

    def _load_acrs(self) -> List[Dict[str, Any]]:
        if not self._acrs_path.exists():
            return []
        try:
            return json.loads(self._acrs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_acrs(self, acrs: List[Dict[str, Any]]) -> None:
        self._ensure_dir()
        self._acrs_path.write_text(
            json.dumps(acrs, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── ACR CRUD ───────────────────────────────────────────────────

    def list_acrs(self) -> List[Dict[str, Any]]:
        return self._load_acrs()

    def get_acrs_for_node(self, node_id: str) -> List[Dict[str, Any]]:
        return [a for a in self._load_acrs() if node_id in a.get("affected_nodes", [])]

    def create_acr(
        self,
        title: str,
        description: str,
        source_type: str,
        source_agent: str,
        affected_nodes: List[str],
    ) -> Dict[str, Any]:
        acrs = self._load_acrs()
        now = datetime.now(timezone.utc).isoformat()
        acr: Dict[str, Any] = {
            "id": f"acr_{uuid.uuid4().hex[:12]}",
            "title": title,
            "description": description,
            "status": "proposed",
            "source_type": source_type,
            "source_agent": source_agent,
            "affected_nodes": affected_nodes,
            "paperclip_issue_id": None,
            "created_at": now,
            "approved_at": None,
            "approved_by": "",
        }
        acrs.append(acr)
        self._save_acrs(acrs)
        return acr

    def approve_acr(
        self, acr_id: str, approved_by: str = "user"
    ) -> Optional[Dict[str, Any]]:
        acrs = self._load_acrs()
        for acr in acrs:
            if acr["id"] == acr_id:
                acr["status"] = "approved"
                acr["approved_at"] = datetime.now(timezone.utc).isoformat()
                acr["approved_by"] = approved_by
                self._save_acrs(acrs)
                return acr
        return None

    def reject_acr(self, acr_id: str) -> Optional[Dict[str, Any]]:
        acrs = self._load_acrs()
        for acr in acrs:
            if acr["id"] == acr_id:
                acr["status"] = "rejected"
                self._save_acrs(acrs)
                return acr
        return None

    def set_acr_issue(self, acr_id: str, paperclip_issue_id: str) -> Optional[Dict[str, Any]]:
        acrs = self._load_acrs()
        for acr in acrs:
            if acr["id"] == acr_id:
                acr["paperclip_issue_id"] = paperclip_issue_id
                self._save_acrs(acrs)
                return acr
        return None

    # ── Issue link persistence ─────────────────────────────────────

    def _load_links(self) -> List[Dict[str, Any]]:
        if not self._links_path.exists():
            return []
        try:
            return json.loads(self._links_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_links(self, links: List[Dict[str, Any]]) -> None:
        self._ensure_dir()
        self._links_path.write_text(
            json.dumps(links, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── Issue link CRUD ────────────────────────────────────────────

    def list_issue_links(self) -> List[Dict[str, Any]]:
        return self._load_links()

    def get_issues_for_node(self, node_id: str) -> List[Dict[str, Any]]:
        return [l for l in self._load_links() if l.get("node_id") == node_id]

    def link_issue(
        self,
        node_id: str,
        paperclip_issue_id: str,
        title: str,
        priority: str,
        status: str,
    ) -> Dict[str, Any]:
        links = self._load_links()
        link: Dict[str, Any] = {
            "node_id": node_id,
            "paperclip_issue_id": paperclip_issue_id,
            "title": title,
            "priority": priority,
            "status": status,
        }
        links.append(link)
        self._save_links(links)
        return link

    def unlink_issue(self, node_id: str, paperclip_issue_id: str) -> bool:
        links = self._load_links()
        original_len = len(links)
        links = [
            l for l in links
            if not (l.get("node_id") == node_id and l.get("paperclip_issue_id") == paperclip_issue_id)
        ]
        if len(links) < original_len:
            self._save_links(links)
            return True
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_architecture_acr.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/architecture_acr.py tests/test_architecture_acr.py
git commit -m "feat(arch): add ACR + issue-link lifecycle module with tests"
```

---

## Task 3: Add Phase B Backend Endpoints

**Files:**
- Modify: `src/prep/api/routers/architecture.py`
- Test: `tests/test_architecture_api_phase_b.py`

- [ ] **Step 1: Write failing tests for Phase B endpoints**

Create `tests/test_architecture_api_phase_b.py`:

```python
"""Tests for Phase 71B architecture API endpoints."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from prep.api.routers.architecture import router


@pytest.fixture
def tmp_index(tmp_path: Path) -> Path:
    """Create a minimal index dir with module synthesis data."""
    # Write one module to trace_modules.jsonl
    modules_path = tmp_path / "trace_modules.jsonl"
    mod = {
        "module_id": "mod_auth",
        "name": "Auth",
        "summary": "Authentication module",
        "file_count": 3,
        "member_files": ["auth/login.py", "auth/session.py", "auth/jwt.py"],
        "hub_files": ["auth/login.py"],
        "domain_tags": ["auth"],
        "architecture_layers": ["backend"],
        "component_status": "complete",
        "avg_epistemic_confidence": 0.85,
        "dependencies": [],
    }
    modules_path.write_text(json.dumps(mod) + "\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def app(tmp_index: Path) -> FastAPI:
    """FastAPI app with architecture router and mocked project lookup."""
    test_app = FastAPI()
    test_app.include_router(router)

    mock_proj = MagicMock()
    mock_proj.project_id = "test-proj"

    with patch("prep.api.routers.architecture._require_project", return_value=mock_proj), \
         patch("prep.api.routers.architecture._project_index_dir", return_value=tmp_index):
        yield test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestACREndpoints:
    def test_list_acrs_empty(self, client: TestClient) -> None:
        r = client.get("/projects/test-proj/architecture/acrs")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_create_and_list_acr(self, client: TestClient) -> None:
        body = {
            "title": "Split Core",
            "description": "Too many responsibilities",
            "source_type": "user",
            "source_agent": "user",
            "affected_nodes": ["mod_core"],
        }
        r = client.post("/projects/test-proj/architecture/acrs", json=body)
        assert r.status_code == 200
        acr = r.json()["data"]
        assert acr["title"] == "Split Core"
        assert acr["status"] == "proposed"

        r2 = client.get("/projects/test-proj/architecture/acrs")
        assert len(r2.json()["data"]) == 1

    def test_approve_acr(self, client: TestClient) -> None:
        body = {"title": "A", "description": "d", "source_type": "user", "source_agent": "user", "affected_nodes": ["n1"]}
        acr_id = client.post("/projects/test-proj/architecture/acrs", json=body).json()["data"]["id"]
        r = client.put(f"/projects/test-proj/architecture/acrs/{acr_id}/approve")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "approved"

    def test_reject_acr(self, client: TestClient) -> None:
        body = {"title": "A", "description": "d", "source_type": "user", "source_agent": "user", "affected_nodes": ["n1"]}
        acr_id = client.post("/projects/test-proj/architecture/acrs", json=body).json()["data"]["id"]
        r = client.put(f"/projects/test-proj/architecture/acrs/{acr_id}/reject")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "rejected"

    def test_approve_nonexistent_returns_404(self, client: TestClient) -> None:
        r = client.put("/projects/test-proj/architecture/acrs/acr_nope/approve")
        assert r.status_code == 200  # ApiException wraps as 200 with error
        # Depends on envelope — may be 404 if ApiException raises HTTP 404


class TestIssueLinkEndpoints:
    def test_link_and_unlink_issue(self, client: TestClient) -> None:
        body = {"paperclip_issue_id": "P-1", "title": "Fix JWT", "priority": "P1", "status": "open"}
        r = client.post("/projects/test-proj/architecture/nodes/mod_auth/link-issue", json=body)
        assert r.status_code == 200
        assert r.json()["data"]["linked"] is True

        r2 = client.delete("/projects/test-proj/architecture/nodes/mod_auth/link-issue/P-1")
        assert r2.status_code == 200
        assert r2.json()["data"]["unlinked"] is True


class TestBriefingEndpoint:
    def test_briefing_returns_text(self, client: TestClient) -> None:
        r = client.post(
            "/projects/test-proj/architecture/briefing",
            json={"node_id": "mod_auth", "scope": "module"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert "briefing" in data
        assert "Auth" in data["briefing"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_architecture_api_phase_b.py -v`
Expected: FAIL (404 for missing endpoints)

- [ ] **Step 3: Add Phase B request models and endpoints to architecture.py**

Append to `src/prep/api/routers/architecture.py` after the existing `NoteUpdate` model (around line 63):

```python
class ACRCreate(BaseModel):
    title: str
    description: str
    source_type: str = "user"
    source_agent: str = "user"
    affected_nodes: List[str] = []


class LinkIssueBody(BaseModel):
    paperclip_issue_id: str
    title: str
    priority: str = "P2"
    status: str = "open"


class BriefingRequest(BaseModel):
    node_id: str
    scope: str = "module"
```

Add a helper to get the ACR manager (after the existing `_get_arch_state` helper):

```python
def _get_acr_mgr(idx_dir: Path):
    from prep.core.architecture_acr import ArchitectureACRManager
    return ArchitectureACRManager(idx_dir)
```

Append all Phase B endpoints after the existing `get_architecture_context` endpoint at the end of the file:

```python
# ── ACR CRUD (Phase B) ────────────────────────────────────────────

@router.get("/projects/{project_id}/architecture/acrs")
def list_acrs(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    return ok(mgr.list_acrs())


@router.post("/projects/{project_id}/architecture/acrs")
def create_acr(project_id: str, body: ACRCreate) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    acr = mgr.create_acr(
        title=body.title,
        description=body.description,
        source_type=body.source_type,
        source_agent=body.source_agent,
        affected_nodes=body.affected_nodes,
    )
    return ok(acr)


@router.put("/projects/{project_id}/architecture/acrs/{acr_id}/approve")
def approve_acr(project_id: str, acr_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    acr = mgr.approve_acr(acr_id)
    if not acr:
        raise ApiException(404, "ACR_NOT_FOUND", f"ACR '{acr_id}' not found")
    return ok(acr)


@router.put("/projects/{project_id}/architecture/acrs/{acr_id}/reject")
def reject_acr(project_id: str, acr_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    acr = mgr.reject_acr(acr_id)
    if not acr:
        raise ApiException(404, "ACR_NOT_FOUND", f"ACR '{acr_id}' not found")
    return ok(acr)


# ── Issue Linking (Phase B) ───────────────────────────────────────

@router.post("/projects/{project_id}/architecture/nodes/{node_id}/link-issue")
def link_issue(project_id: str, node_id: str, body: LinkIssueBody) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    mgr.link_issue(
        node_id=node_id,
        paperclip_issue_id=body.paperclip_issue_id,
        title=body.title,
        priority=body.priority,
        status=body.status,
    )
    return ok({"linked": True})


@router.delete("/projects/{project_id}/architecture/nodes/{node_id}/link-issue/{issue_id}")
def unlink_issue(project_id: str, node_id: str, issue_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    removed = mgr.unlink_issue(node_id, issue_id)
    if not removed:
        raise ApiException(404, "LINK_NOT_FOUND", f"No link for issue '{issue_id}' on node '{node_id}'")
    return ok({"unlinked": True})


# ── Agent Briefing (Phase B) ──────────────────────────────────────

@router.post("/projects/{project_id}/architecture/briefing")
def generate_briefing(project_id: str, body: BriefingRequest) -> Dict[str, Any]:
    """Generate a structured text briefing for an agent about a node."""
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)

    modules = _load_modules(idx_dir)
    arch = _get_arch_state(idx_dir)
    acr_mgr = _get_acr_mgr(idx_dir)

    # Find the target module
    target = None
    for m in modules:
        if m["module_id"] == body.node_id:
            target = m
            break

    if not target:
        raise ApiException(404, "NODE_NOT_FOUND", f"Node '{body.node_id}' not found")

    notes = arch.get_notes_for_node(body.node_id)
    acrs = acr_mgr.get_acrs_for_node(body.node_id)
    issues = acr_mgr.get_issues_for_node(body.node_id)

    # Build dependency info
    trace_edges = _load_trace_edges(idx_dir)
    file_to_module = _build_file_to_module_map(modules)
    module_edges = _aggregate_module_edges(trace_edges, file_to_module)

    deps = [e["target"] for e in module_edges if e["source"] == body.node_id]
    dependents = [e["source"] for e in module_edges if e["target"] == body.node_id]

    lines: List[str] = []
    name = target.get("name", body.node_id)
    lines.append(f"## Agent Briefing: {name}")
    lines.append("")
    lines.append(f"**Module:** {name} ({target.get('file_count', 0)} files)")
    lines.append(f"**Description:** {target.get('summary', 'No description')}")
    lines.append(f"**Dependencies:** {', '.join(deps) if deps else 'none'}")
    lines.append(f"**Depended on by:** {', '.join(dependents) if dependents else 'none'}")

    if notes:
        lines.append("")
        lines.append("**Annotations:**")
        for n in notes:
            prefix = "\U0001f4cc" if n.get("note_type") == "adr" else "\U0001f4ac"
            lines.append(f"  {prefix} {n.get('content', '')}")

    if acrs:
        lines.append("")
        lines.append("**Active ACRs:**")
        for a in acrs:
            lines.append(f"  \u26a0\ufe0f {a['id']}: {a['title']} ({a['status']})")

    if issues:
        lines.append("")
        lines.append("**Linked Issues:**")
        for i in issues:
            lines.append(f"  \U0001f3ab {i['paperclip_issue_id']}: {i['title']} [{i['priority']}] ({i['status']})")

    member_files = target.get("member_files", [])
    if member_files:
        lines.append("")
        lines.append("**Files:**")
        for f in member_files[:20]:
            lines.append(f"  - {f}")
        if len(member_files) > 20:
            lines.append(f"  ... and {len(member_files) - 20} more")

    return ok({"briefing": "\n".join(lines)})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_architecture_api_phase_b.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/architecture.py tests/test_architecture_api_phase_b.py
git commit -m "feat(arch): add Phase B API endpoints — ACRs, issue linking, briefing"
```

---

## Task 4: Add Phase B API Client Methods

**Files:**
- Modify: `packages/ui/src/api/client.ts`

- [ ] **Step 1: Add Phase B methods to the API client**

Find the end of the architecture methods section in `packages/ui/src/api/client.ts` (after `deleteArchitectureNote`) and append:

```typescript
  // ── Architecture: ACRs (Phase B) ─────────────────────────────────

  async listACRs(projectId: string): Promise<ACR[]> {
    return this.requestEnvelope<ACR[]>(
      `/projects/${encodeURIComponent(projectId)}/architecture/acrs`,
    );
  }

  async createACR(projectId: string, acr: ACRCreate): Promise<ACR> {
    return this.requestEnvelope<ACR>(
      `/projects/${encodeURIComponent(projectId)}/architecture/acrs`,
      { method: 'POST', body: acr },
    );
  }

  async approveACR(projectId: string, acrId: string): Promise<ACR> {
    return this.requestEnvelope<ACR>(
      `/projects/${encodeURIComponent(projectId)}/architecture/acrs/${encodeURIComponent(acrId)}/approve`,
      { method: 'PUT' },
    );
  }

  async rejectACR(projectId: string, acrId: string): Promise<ACR> {
    return this.requestEnvelope<ACR>(
      `/projects/${encodeURIComponent(projectId)}/architecture/acrs/${encodeURIComponent(acrId)}/reject`,
      { method: 'PUT' },
    );
  }

  // ── Architecture: Issue Linking (Phase B) ────────────────────────

  async linkIssue(projectId: string, nodeId: string, body: LinkIssueRequest): Promise<{ linked: boolean }> {
    return this.requestEnvelope<{ linked: boolean }>(
      `/projects/${encodeURIComponent(projectId)}/architecture/nodes/${encodeURIComponent(nodeId)}/link-issue`,
      { method: 'POST', body },
    );
  }

  async unlinkIssue(projectId: string, nodeId: string, issueId: string): Promise<{ unlinked: boolean }> {
    return this.requestEnvelope<{ unlinked: boolean }>(
      `/projects/${encodeURIComponent(projectId)}/architecture/nodes/${encodeURIComponent(nodeId)}/link-issue/${encodeURIComponent(issueId)}`,
      { method: 'DELETE' },
    );
  }

  // ── Architecture: Briefing (Phase B) ─────────────────────────────

  async generateBriefing(projectId: string, nodeId: string, scope: 'module' | 'file' = 'module'): Promise<{ briefing: string }> {
    return this.requestEnvelope<{ briefing: string }>(
      `/projects/${encodeURIComponent(projectId)}/architecture/briefing`,
      { method: 'POST', body: { node_id: nodeId, scope } },
    );
  }
```

Also add the new type imports at the top of the file where existing architecture types are imported:

```typescript
import type {
  ArchGraphResponse, ArchSummaryResponse, ArchState,
  ArchNote, ArchNoteCreate, ArchNoteUpdate,
  ACR, ACRCreate, LinkIssueRequest, LinkedIssue,
} from '../types/architecture';
```

- [ ] **Step 2: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/api/client.ts
git commit -m "feat(arch): add Phase B API client methods — ACRs, issues, briefing"
```

---

## Task 5: Extract BreadcrumbNav Component

**Files:**
- Create: `packages/ui/src/components/architecture/BreadcrumbNav.tsx`
- Modify: `packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx`
- Modify: `packages/ui/src/components/architecture/index.ts`

- [ ] **Step 1: Create BreadcrumbNav.tsx**

Extract the breadcrumb rendering from `ArchitectureDiagramDetail.tsx` lines 381-395 into a standalone component:

```tsx
import { Fragment, memo } from 'react';
import type { ArchBreadcrumb } from '../../types/architecture';

export interface BreadcrumbNavProps {
  breadcrumbs: ArchBreadcrumb[];
  onNavigateToLayer: (path: string[]) => void;
}

function BreadcrumbNavInner({ breadcrumbs, onNavigateToLayer }: BreadcrumbNavProps) {
  return (
    <div className="flex items-center gap-1 px-4 py-2 border-b border-zinc-800 bg-zinc-950 text-sm">
      {breadcrumbs.map((crumb, i) => (
        <Fragment key={i}>
          {i > 0 && <span className="text-zinc-600 mx-1">{'›'}</span>}
          <button
            onClick={() => onNavigateToLayer(crumb.layerPath)}
            className={`px-2 py-0.5 rounded hover:bg-zinc-800 transition-colors ${
              i === breadcrumbs.length - 1 ? 'text-zinc-200 font-medium' : 'text-zinc-500'
            }`}
          >
            {crumb.label}
          </button>
        </Fragment>
      ))}
    </div>
  );
}

export const BreadcrumbNav = memo(BreadcrumbNavInner);
```

- [ ] **Step 2: Replace inline breadcrumb in ArchitectureDiagramDetail.tsx**

In `DiagramCanvas`, replace the breadcrumb JSX block (lines 381-395) with:

```tsx
<BreadcrumbNav breadcrumbs={breadcrumbs} onNavigateToLayer={onNavigateToLayer} />
```

Add the import at the top:

```tsx
import { BreadcrumbNav } from './BreadcrumbNav';
```

Remove the `Fragment` import if it's no longer used elsewhere in the file.

- [ ] **Step 3: Export from index.ts**

Add to `packages/ui/src/components/architecture/index.ts`:

```typescript
export { BreadcrumbNav } from './BreadcrumbNav';
export type { BreadcrumbNavProps } from './BreadcrumbNav';
```

- [ ] **Step 4: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/architecture/BreadcrumbNav.tsx \
       packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx \
       packages/ui/src/components/architecture/index.ts
git commit -m "refactor(arch): extract BreadcrumbNav from ArchitectureDiagramDetail"
```

---

## Task 6: Extract DiagramToolbar Component

**Files:**
- Create: `packages/ui/src/components/architecture/DiagramToolbar.tsx`
- Modify: `packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx`
- Modify: `packages/ui/src/components/architecture/index.ts`

- [ ] **Step 1: Create DiagramToolbar.tsx**

Extract the toolbar from `ArchitectureDiagramDetail.tsx` lines 398-418:

```tsx
import { memo } from 'react';
import type { ArchStats } from '../../types/architecture';

export interface DiagramToolbarProps {
  onAutoLayout: () => void;
  onGoBack: (() => void) | null;
  stats: ArchStats;
}

function DiagramToolbarInner({ onAutoLayout, onGoBack, stats }: DiagramToolbarProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 bg-zinc-950">
      <button
        onClick={onAutoLayout}
        className="text-xs px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
      >
        Auto-layout
      </button>
      {onGoBack && (
        <button
          onClick={onGoBack}
          className="text-xs px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
        >
          {'← Back'}
        </button>
      )}
      <div className="ml-auto text-xs text-zinc-500">
        {stats.total_modules > 0 && `${stats.total_modules} modules · `}
        {stats.total_files > 0 && `${stats.total_files} files · `}
        {stats.total_edges} edges
      </div>
    </div>
  );
}

export const DiagramToolbar = memo(DiagramToolbarInner);
```

- [ ] **Step 2: Replace inline toolbar in ArchitectureDiagramDetail.tsx**

Replace the toolbar JSX block (lines 398-418) with:

```tsx
<DiagramToolbar
  onAutoLayout={handleAutoLayout}
  onGoBack={layerPath.length > 0 ? () => onNavigateToLayer(layerPath.slice(0, -1)) : null}
  stats={graph.stats}
/>
```

Add the import:

```tsx
import { DiagramToolbar } from './DiagramToolbar';
```

- [ ] **Step 3: Export from index.ts**

Add to `packages/ui/src/components/architecture/index.ts`:

```typescript
export { DiagramToolbar } from './DiagramToolbar';
export type { DiagramToolbarProps } from './DiagramToolbar';
```

- [ ] **Step 4: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/architecture/DiagramToolbar.tsx \
       packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx \
       packages/ui/src/components/architecture/index.ts
git commit -m "refactor(arch): extract DiagramToolbar from ArchitectureDiagramDetail"
```

---

## Task 7: Extract DiagramSidebar Component

**Files:**
- Create: `packages/ui/src/components/architecture/DiagramSidebar.tsx`
- Modify: `packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx`
- Modify: `packages/ui/src/components/architecture/index.ts`

- [ ] **Step 1: Create DiagramSidebar.tsx**

Extract the sidebar from `ArchitectureDiagramDetail.tsx` lines 459-518. Move `SidebarNoteCard` and `AddNoteForm` helper components into the same file since they are sidebar-specific:

```tsx
import { memo, useState, useCallback } from 'react';
import type { Node } from '@xyflow/react';
import type {
  ArchNote, ArchNoteCreate, ACR, LinkedIssue,
  ModuleNodeData, FileNodeData,
} from '../../types/architecture';

// ── Note card ─────────────────────────────────────────────────────

function SidebarNoteCard({ note, onUpdate, onDelete }: { note: ArchNote; onUpdate: (content: string) => void; onDelete: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.content);

  const handleSave = useCallback(() => {
    if (draft.trim() && draft !== note.content) {
      onUpdate(draft.trim());
    }
    setEditing(false);
  }, [draft, note.content, onUpdate]);

  return (
    <div className="mb-2 p-2 rounded bg-zinc-900 border border-zinc-800">
      <div className="flex justify-between items-start">
        <span className="text-[10px] text-zinc-500">
          {note.note_type === 'adr' ? '📌 ADR' : note.note_type === 'agent_note' ? '🤖 Agent' : '💬'}
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => { setEditing(!editing); setDraft(note.content); }}
            className="text-[10px] text-zinc-600 hover:text-zinc-300"
          >
            {editing ? 'cancel' : 'edit'}
          </button>
          <button onClick={onDelete} className="text-[10px] text-zinc-600 hover:text-red-400">
            delete
          </button>
        </div>
      </div>
      {editing ? (
        <>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleSave(); }}
            className="w-full mt-1 bg-transparent border border-zinc-600 rounded text-xs text-zinc-200 p-1 resize-none"
            rows={3}
            autoFocus
          />
          <button
            onClick={handleSave}
            className="mt-1 text-[10px] px-2 py-0.5 bg-zinc-700 rounded text-zinc-300 hover:bg-zinc-600"
          >
            Save
          </button>
        </>
      ) : (
        <p className="text-xs text-zinc-300 mt-1">{note.content}</p>
      )}
      <span className="text-[10px] text-zinc-600">— {note.author}</span>
    </div>
  );
}

// ── Add note form ─────────────────────────────────────────────────

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

// ── Main sidebar ──────────────────────────────────────────────────

export interface DiagramSidebarProps {
  selectedNode: Node;
  notes: ArchNote[];
  acrs: ACR[];
  issueLinks: LinkedIssue[];
  onClose: () => void;
  onCreateNote: (note: ArchNoteCreate) => void;
  onUpdateNote: (noteId: string, content: string) => void;
  onDeleteNote: (noteId: string) => void;
}

function DiagramSidebarInner({
  selectedNode, notes, acrs, issueLinks,
  onClose, onCreateNote, onUpdateNote, onDeleteNote,
}: DiagramSidebarProps) {
  const nodeNotes = notes.filter((n) => n.node_id === selectedNode.id);
  const nodeACRs = acrs.filter((a) => a.affected_nodes.includes(selectedNode.id));
  const nodeIssues = issueLinks.filter((l) => l.node_id === selectedNode.id);

  return (
    <div className="w-80 border-l border-zinc-800 bg-zinc-950/90 backdrop-blur-sm overflow-y-auto">
      <div className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-zinc-200 truncate">
            {(selectedNode.data as any).label}
          </h3>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-300 text-xs"
          >
            {'x'}
          </button>
        </div>

        {/* Description */}
        {(selectedNode.data as any).description && (
          <p className="text-xs text-zinc-400 mb-4">{(selectedNode.data as any).description}</p>
        )}

        {/* Node metadata */}
        <div className="text-xs text-zinc-500 space-y-1 mb-4">
          {selectedNode.type === 'module' && (() => {
            const d = selectedNode.data as unknown as ModuleNodeData;
            return (
              <>
                <div>Files: {d.fileCount}</div>
                <div>Status: {d.componentStatus}</div>
                <div>Confidence: {(d.confidence * 100).toFixed(0)}%</div>
              </>
            );
          })()}
          {selectedNode.type === 'file' && (() => {
            const d = selectedNode.data as unknown as FileNodeData;
            return (
              <>
                <div>Path: {d.path}</div>
                <div>Language: {d.language}</div>
                <div>Lines: {d.lineCount}</div>
              </>
            );
          })()}
        </div>

        {/* Linked Issues */}
        {nodeIssues.length > 0 && (
          <div className="border-t border-zinc-800 pt-3 mb-3">
            <h4 className="text-xs font-medium text-zinc-400 mb-2">
              Issues ({nodeIssues.length})
            </h4>
            {nodeIssues.map((issue) => (
              <div key={issue.paperclip_issue_id} className="mb-1.5 p-2 rounded bg-zinc-900 border border-zinc-800">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-bold ${
                    issue.priority === 'P0' || issue.priority === 'P1' ? 'text-red-400' : 'text-amber-400'
                  }`}>
                    {issue.priority}
                  </span>
                  <span className="text-xs text-zinc-300 truncate">{issue.title}</span>
                </div>
                <span className="text-[10px] text-zinc-500">{issue.paperclip_issue_id} - {issue.status}</span>
              </div>
            ))}
          </div>
        )}

        {/* ACRs */}
        {nodeACRs.length > 0 && (
          <div className="border-t border-zinc-800 pt-3 mb-3">
            <h4 className="text-xs font-medium text-zinc-400 mb-2">
              ACRs ({nodeACRs.length})
            </h4>
            {nodeACRs.map((acr) => (
              <div key={acr.id} className="mb-1.5 p-2 rounded bg-zinc-900 border border-amber-800/50">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] text-amber-400">{'\u26a0\ufe0f'}</span>
                  <span className="text-xs text-zinc-200 truncate">{acr.title}</span>
                </div>
                <p className="text-[10px] text-zinc-400 mb-1">{acr.description}</p>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    acr.status === 'approved' ? 'bg-green-900/50 text-green-400' :
                    acr.status === 'rejected' ? 'bg-red-900/50 text-red-400' :
                    acr.status === 'completed' ? 'bg-blue-900/50 text-blue-400' :
                    'bg-amber-900/50 text-amber-400'
                  }`}>
                    {acr.status}
                  </span>
                  <span className="text-[10px] text-zinc-500">by {acr.source_agent}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Notes */}
        <div className="border-t border-zinc-800 pt-3">
          <h4 className="text-xs font-medium text-zinc-400 mb-2">
            Notes ({nodeNotes.length})
          </h4>
          {nodeNotes.map((note) => (
            <SidebarNoteCard
              key={note.id}
              note={note}
              onUpdate={(content) => onUpdateNote(note.id, content)}
              onDelete={() => onDeleteNote(note.id)}
            />
          ))}

          <AddNoteForm nodeId={selectedNode.id} onCreateNote={onCreateNote} />
        </div>
      </div>
    </div>
  );
}

export const DiagramSidebar = memo(DiagramSidebarInner);
```

- [ ] **Step 2: Replace inline sidebar in ArchitectureDiagramDetail.tsx**

Replace the sidebar JSX block (lines 459-518) in `DiagramCanvas` with:

```tsx
{selectedNode && (
  <DiagramSidebar
    selectedNode={selectedNode}
    notes={notes}
    acrs={[]}
    issueLinks={[]}
    onClose={() => onSelectNode(null)}
    onCreateNote={onCreateNote}
    onUpdateNote={onUpdateNote}
    onDeleteNote={onDeleteNote}
  />
)}
```

Remove the now-unused `SidebarNoteCard` and `AddNoteForm` functions from `ArchitectureDiagramDetail.tsx`, and the `selectedNodeNotes` memo (the sidebar computes its own filter now).

Add the import:

```tsx
import { DiagramSidebar } from './DiagramSidebar';
```

- [ ] **Step 3: Export from index.ts**

Add to `packages/ui/src/components/architecture/index.ts`:

```typescript
export { DiagramSidebar } from './DiagramSidebar';
export type { DiagramSidebarProps } from './DiagramSidebar';
```

- [ ] **Step 4: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/architecture/DiagramSidebar.tsx \
       packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx \
       packages/ui/src/components/architecture/index.ts
git commit -m "refactor(arch): extract DiagramSidebar with issue + ACR panels"
```

---

## Task 8: Build EntryPointNode Component

**Files:**
- Create: `packages/ui/src/components/architecture/EntryPointNode.tsx`
- Modify: `packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx`
- Modify: `packages/ui/src/components/architecture/index.ts`

- [ ] **Step 1: Create EntryPointNode.tsx**

```tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { EntryPointNodeData } from '../../types/architecture';

const TYPE_ICONS: Record<string, string> = {
  api_route: '🌐',
  cli_command: '⌨️',
  main: '▶️',
  webhook: '🔗',
};

function EntryPointNodeInner({ data, selected }: NodeProps & { data: EntryPointNodeData }) {
  const icon = TYPE_ICONS[data.entryType] ?? '◇';

  return (
    <div
      className={`
        relative w-[140px] h-[80px] flex items-center justify-center
        transition-all duration-150
        ${selected ? 'drop-shadow-[0_0_8px_rgba(59,130,246,0.5)]' : ''}
      `}
    >
      <Handle type="target" position={Position.Top} className="!bg-zinc-500 !w-2 !h-2" />

      {/* Diamond shape via rotated square */}
      <div
        className={`
          absolute inset-[10px] rotate-45 rounded-[4px]
          border-2 bg-zinc-900 shadow-md
          ${selected ? 'border-blue-400' : 'border-emerald-500'}
        `}
        style={{
          background: 'linear-gradient(135deg, #18181b 0%, #1e293b 100%)',
        }}
      />

      {/* Content (not rotated) */}
      <div className="relative z-10 flex flex-col items-center text-center px-2">
        <span className="text-xs">{icon}</span>
        <span className="text-[11px] font-medium text-zinc-200 truncate max-w-[100px]">
          {data.label}
        </span>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-zinc-500 !w-2 !h-2" />
    </div>
  );
}

export const EntryPointNode = memo(EntryPointNodeInner);
```

- [ ] **Step 2: Register in ArchitectureDiagramDetail.tsx**

Add to the `nodeTypes` object:

```tsx
import { EntryPointNode } from './EntryPointNode';

const nodeTypes: NodeTypes = {
  module: ModuleNode as any,
  file: FileNode as any,
  externalRef: ExternalRefNode as any,
  annotation: AnnotationNode as any,
  entryPoint: EntryPointNode as any,
};
```

Update the `autoLayout` function's height calculation to include entryPoint:

```tsx
height: n.type === 'module' ? 120 : n.type === 'annotation' ? 80 : n.type === 'entryPoint' ? 80 : 60,
```

- [ ] **Step 3: Export from index.ts**

Add to `packages/ui/src/components/architecture/index.ts`:

```typescript
export { EntryPointNode } from './EntryPointNode';
```

- [ ] **Step 4: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/architecture/EntryPointNode.tsx \
       packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx \
       packages/ui/src/components/architecture/index.ts
git commit -m "feat(arch): add EntryPointNode diamond shape for API surfaces"
```

---

## Task 9: Build IssueBadge Component and Add to Nodes

**Files:**
- Create: `packages/ui/src/components/architecture/IssueBadge.tsx`
- Modify: `packages/ui/src/components/architecture/ModuleNode.tsx`
- Modify: `packages/ui/src/components/architecture/FileNode.tsx`
- Modify: `packages/ui/src/types/architecture.ts`
- Modify: `packages/ui/src/components/architecture/index.ts`

- [ ] **Step 1: Create IssueBadge.tsx**

```tsx
import { memo } from 'react';

export interface IssueBadgeProps {
  issueCount: number;
  acrCount: number;
  maxPriority: 'P0' | 'P1' | 'P2' | 'P3' | null;
}

function IssueBadgeInner({ issueCount, acrCount, maxPriority }: IssueBadgeProps) {
  if (issueCount === 0 && acrCount === 0) return null;

  return (
    <div className="absolute -top-1 -right-1 flex items-center gap-0.5 z-10">
      {issueCount > 0 && (
        <span
          className={`
            text-[9px] font-bold leading-none rounded-full min-w-[16px] h-[16px]
            flex items-center justify-center px-1
            ${maxPriority === 'P0' || maxPriority === 'P1'
              ? 'bg-red-500 text-white animate-pulse'
              : 'bg-amber-500 text-zinc-900'}
          `}
        >
          {issueCount}
        </span>
      )}
      {acrCount > 0 && (
        <span className="text-[10px] leading-none text-amber-400">{'\u26a0\ufe0f'}</span>
      )}
    </div>
  );
}

export const IssueBadge = memo(IssueBadgeInner);
```

- [ ] **Step 2: Add overlay fields to node data types**

In `packages/ui/src/types/architecture.ts`, extend `ModuleNodeData`:

```typescript
// Add to the end of ModuleNodeData interface:
  issueCount: number;
  acrCount: number;
  maxPriority: 'P0' | 'P1' | 'P2' | 'P3' | null;
```

Extend `FileNodeData` similarly:

```typescript
// Add to the end of FileNodeData interface:
  issueCount: number;
  acrCount: number;
  maxPriority: 'P0' | 'P1' | 'P2' | 'P3' | null;
```

- [ ] **Step 3: Add IssueBadge to ModuleNode.tsx**

```tsx
import { IssueBadge } from './IssueBadge';

// In ModuleNodeInner, wrap the outer div with position relative and add the badge:
function ModuleNodeInner({ data, selected }: NodeProps & { data: ModuleNodeData }) {
  const statusColor = data.componentStatus === 'complete' ? 'border-blue-500' :
    data.componentStatus === 'deprecated' ? 'border-red-500' : 'border-amber-500';

  return (
    <div
      className={`
        relative rounded-lg border-2 bg-zinc-900 shadow-md px-4 py-3 min-w-[180px] max-w-[260px]
        transition-all duration-150
        ${statusColor}
        ${selected ? 'ring-2 ring-blue-400 shadow-blue-500/20' : ''}
        ${data.isHub ? 'shadow-purple-500/30 shadow-lg' : ''}
      `}
    >
      <IssueBadge issueCount={data.issueCount} acrCount={data.acrCount} maxPriority={data.maxPriority} />
      <Handle type="target" position={Position.Top} className="!bg-zinc-500 !w-2 !h-2" />
      {/* ... rest unchanged ... */}
```

- [ ] **Step 4: Add IssueBadge to FileNode.tsx**

```tsx
import { IssueBadge } from './IssueBadge';

// Add relative class to outer div and add IssueBadge:
function FileNodeInner({ data, selected }: NodeProps & { data: FileNodeData }) {
  const icon = LANG_ICONS[data.language] ?? '📄';

  return (
    <div
      className={`
        relative rounded-full border bg-zinc-900 shadow-sm px-4 py-2 min-w-[140px] max-w-[220px]
        transition-all duration-150
        ${selected ? 'border-blue-400 ring-2 ring-blue-400/50' : 'border-zinc-700'}
        ${data.isHub ? 'border-purple-500 shadow-purple-500/20' : ''}
      `}
    >
      <IssueBadge issueCount={data.issueCount} acrCount={data.acrCount} maxPriority={data.maxPriority} />
      <Handle type="target" position={Position.Top} className="!bg-zinc-500 !w-2 !h-2" />
      {/* ... rest unchanged ... */}
```

- [ ] **Step 5: Update buildFlowNodes to pass overlay data**

In `ArchitectureDiagramDetail.tsx`, update the `buildFlowNodes` function to accept ACR and issue data, and pass the new fields. For now, pass defaults (0, 0, null) — wiring to real data happens in Task 10:

In the `ModuleNodeData` satisfies block, add:

```typescript
issueCount: 0,
acrCount: 0,
maxPriority: null,
```

In the `FileNodeData` satisfies block, add:

```typescript
issueCount: 0,
acrCount: 0,
maxPriority: null,
```

- [ ] **Step 6: Export from index.ts**

Add to `packages/ui/src/components/architecture/index.ts`:

```typescript
export { IssueBadge } from './IssueBadge';
export type { IssueBadgeProps } from './IssueBadge';
```

- [ ] **Step 7: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add packages/ui/src/components/architecture/IssueBadge.tsx \
       packages/ui/src/components/architecture/ModuleNode.tsx \
       packages/ui/src/components/architecture/FileNode.tsx \
       packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx \
       packages/ui/src/components/architecture/index.ts \
       packages/ui/src/types/architecture.ts
git commit -m "feat(arch): add IssueBadge overlay to ModuleNode and FileNode"
```

---

## Task 10: Wire ACR + Issue State into useArchitectureSystem Hook

**Files:**
- Modify: `src/prep/dashboard/src/hooks/useArchitectureSystem.ts`

- [ ] **Step 1: Add ACR + issue state and actions**

Update `useArchitectureSystem.ts` to fetch and manage ACRs and issue links. Add these imports:

```typescript
import type {
  ArchGraphResponse, ArchSummaryResponse, ArchNote,
  ArchState, ArchNoteCreate, ArchNodePosition,
  ACR, ACRCreate, LinkedIssue, LinkIssueRequest,
} from '@prep/ui';
```

Add to the `UseArchitectureSystemReturn` interface:

```typescript
  acrs: ACR[];
  issueLinks: LinkedIssue[];
  createACR: (acr: ACRCreate) => void;
  approveACR: (acrId: string) => void;
  rejectACR: (acrId: string) => void;
  linkIssue: (nodeId: string, body: LinkIssueRequest) => void;
  unlinkIssue: (nodeId: string, issueId: string) => void;
```

Add state variables:

```typescript
const [acrs, setACRs] = useState<ACR[]>([]);
const [issueLinks, setIssueLinks] = useState<LinkedIssue[]>([]);
```

Update the hydration `Promise.all` to also fetch ACRs and issue links:

```typescript
Promise.all([
  api.getArchitectureSummary(selectedProjectId),
  api.getArchitectureGraph(selectedProjectId),
  api.listArchitectureNotes(selectedProjectId),
  api.getArchitectureState(selectedProjectId),
  api.listACRs(selectedProjectId),
  // issue links come from the same source as ACRs (fetched together)
])
  .then(([sum, g, n, s, acrList]) => {
    if (options?.signal?.aborted) return;
    setSummary(sum);
    setGraph(g);
    setNotes(n);
    setArchState(s);
    setACRs(acrList);
  })
```

Note: `listACRs` needs to exist on the API client (added in Task 4). Issue links are not fetched as a separate list endpoint yet — they are served per-node. For a first pass, initialize `issueLinks` to `[]` and populate when the sidebar loads for a selected node. Alternatively, add a `listIssueLinks` endpoint. For simplicity, we'll leave `issueLinks` populated via the existing ACR manager's `list_issue_links()`.

Add the action callbacks:

```typescript
const createACR = useCallback(
  (acr: ACRCreate) => {
    if (!selectedProjectId) return;
    api.createACR(selectedProjectId, acr)
      .then((created) => setACRs((prev) => [...prev, created]))
      .catch((err) => setError(`ACR creation failed: ${err.message}`));
  },
  [selectedProjectId, api],
);

const approveACR = useCallback(
  (acrId: string) => {
    if (!selectedProjectId) return;
    api.approveACR(selectedProjectId, acrId)
      .then((updated) => setACRs((prev) => prev.map((a) => a.id === acrId ? updated : a)))
      .catch((err) => setError(`ACR approve failed: ${err.message}`));
  },
  [selectedProjectId, api],
);

const rejectACR = useCallback(
  (acrId: string) => {
    if (!selectedProjectId) return;
    api.rejectACR(selectedProjectId, acrId)
      .then((updated) => setACRs((prev) => prev.map((a) => a.id === acrId ? updated : a)))
      .catch((err) => setError(`ACR reject failed: ${err.message}`));
  },
  [selectedProjectId, api],
);

const linkIssueAction = useCallback(
  (nodeId: string, body: LinkIssueRequest) => {
    if (!selectedProjectId) return;
    api.linkIssue(selectedProjectId, nodeId, body)
      .then(() => {
        setIssueLinks((prev) => [...prev, { ...body, node_id: nodeId }]);
      })
      .catch((err) => setError(`Issue link failed: ${err.message}`));
  },
  [selectedProjectId, api],
);

const unlinkIssueAction = useCallback(
  (nodeId: string, issueId: string) => {
    if (!selectedProjectId) return;
    api.unlinkIssue(selectedProjectId, nodeId, issueId)
      .then(() => {
        setIssueLinks((prev) => prev.filter(
          (l) => !(l.node_id === nodeId && l.paperclip_issue_id === issueId)
        ));
      })
      .catch((err) => setError(`Issue unlink failed: ${err.message}`));
  },
  [selectedProjectId, api],
);
```

Add to the return object:

```typescript
acrs,
issueLinks,
createACR,
approveACR,
rejectACR,
linkIssue: linkIssueAction,
unlinkIssue: unlinkIssueAction,
```

Also reset `acrs` and `issueLinks` in the cleanup at the top of the hydration effect:

```typescript
setACRs([]);
setIssueLinks([]);
```

- [ ] **Step 2: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/prep/dashboard/src/hooks/useArchitectureSystem.ts
git commit -m "feat(arch): wire ACR + issue state into useArchitectureSystem hook"
```

---

## Task 11: Wire DiagramSidebar to Live ACR + Issue Data

**Files:**
- Modify: `packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx`

- [ ] **Step 1: Update ArchitectureDiagramDetailProps to accept ACRs and issues**

Add to the `ArchitectureDiagramDetailProps` interface:

```typescript
acrs: ACR[];
issueLinks: LinkedIssue[];
```

Add the import:

```typescript
import type { ACR, LinkedIssue } from '../../types/architecture';
```

- [ ] **Step 2: Pass data through to DiagramSidebar**

In `DiagramCanvas`, destructure the new props and pass them to `DiagramSidebar`:

```tsx
const { acrs, issueLinks, ...rest } = props;

// In the sidebar JSX:
{selectedNode && (
  <DiagramSidebar
    selectedNode={selectedNode}
    notes={notes}
    acrs={acrs}
    issueLinks={issueLinks}
    onClose={() => onSelectNode(null)}
    onCreateNote={onCreateNote}
    onUpdateNote={onUpdateNote}
    onDeleteNote={onDeleteNote}
  />
)}
```

- [ ] **Step 3: Update buildFlowNodes to compute overlay counts**

Update the `buildFlowNodes` function signature to accept ACRs and issue links:

```typescript
function buildFlowNodes(
  graph: ArchGraphResponse,
  notes: ArchNote[],
  acrs: ACR[],
  issueLinks: LinkedIssue[],
  savedPositions?: Array<{ id: string; x: number; y: number }>,
): Node[] {
```

Add helper computations at the top of the function:

```typescript
const issuesByNode = new Map<string, LinkedIssue[]>();
for (const link of issueLinks) {
  const existing = issuesByNode.get(link.node_id) ?? [];
  existing.push(link);
  issuesByNode.set(link.node_id, existing);
}

const acrsByNode = new Map<string, ACR[]>();
for (const acr of acrs) {
  for (const nid of acr.affected_nodes) {
    const existing = acrsByNode.get(nid) ?? [];
    existing.push(acr);
    acrsByNode.set(nid, existing);
  }
}

function getMaxPriority(nodeId: string): 'P0' | 'P1' | 'P2' | 'P3' | null {
  const nodeIssues = issuesByNode.get(nodeId) ?? [];
  if (nodeIssues.length === 0) return null;
  const priorities: string[] = nodeIssues.map((i) => i.priority);
  if (priorities.includes('P0')) return 'P0';
  if (priorities.includes('P1')) return 'P1';
  if (priorities.includes('P2')) return 'P2';
  return 'P3';
}
```

Then in each node's data block, replace the placeholder values:

```typescript
issueCount: (issuesByNode.get(mod.id) ?? []).length,
acrCount: (acrsByNode.get(mod.id) ?? []).length,
maxPriority: getMaxPriority(mod.id),
```

Same pattern for file nodes using `file.id`.

Update all call sites of `buildFlowNodes` to pass `acrs` and `issueLinks`.

- [ ] **Step 4: Verify types compile**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/architecture/ArchitectureDiagramDetail.tsx
git commit -m "feat(arch): wire live ACR + issue data into sidebar and node badges"
```

---

## Task 12: Add listIssueLinks to Backend + Client

**Files:**
- Modify: `src/prep/api/routers/architecture.py`
- Modify: `packages/ui/src/api/client.ts`

- [ ] **Step 1: Add GET endpoint for all issue links**

In `architecture.py`, add after the existing issue linking endpoints:

```python
@router.get("/projects/{project_id}/architecture/issue-links")
def list_issue_links(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx_dir = _project_index_dir(proj)
    mgr = _get_acr_mgr(idx_dir)
    return ok(mgr.list_issue_links())
```

- [ ] **Step 2: Add client method**

In `client.ts`, add:

```typescript
async listIssueLinks(projectId: string): Promise<LinkedIssue[]> {
  return this.requestEnvelope<LinkedIssue[]>(
    `/projects/${encodeURIComponent(projectId)}/architecture/issue-links`,
  );
}
```

- [ ] **Step 3: Update useArchitectureSystem to fetch issue links on hydration**

In the `Promise.all` hydration block, add `api.listIssueLinks(selectedProjectId)`:

```typescript
Promise.all([
  api.getArchitectureSummary(selectedProjectId),
  api.getArchitectureGraph(selectedProjectId),
  api.listArchitectureNotes(selectedProjectId),
  api.getArchitectureState(selectedProjectId),
  api.listACRs(selectedProjectId),
  api.listIssueLinks(selectedProjectId),
])
  .then(([sum, g, n, s, acrList, links]) => {
    if (options?.signal?.aborted) return;
    setSummary(sum);
    setGraph(g);
    setNotes(n);
    setArchState(s);
    setACRs(acrList);
    setIssueLinks(links);
  })
```

- [ ] **Step 4: Verify types compile and tests pass**

Run: `cd /Volumes/4TB-BAD/HumanAI/Prep && npm run typecheck`
Run: `.venv/bin/pytest tests/test_architecture_acr.py tests/test_architecture_api_phase_b.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/architecture.py \
       packages/ui/src/api/client.ts \
       src/prep/dashboard/src/hooks/useArchitectureSystem.ts
git commit -m "feat(arch): add listIssueLinks endpoint and wire hydration"
```

---

## Task 13: Expand MCP codegen Context with ACRs

**Files:**
- Modify: `src/prep/api/routers/architecture.py`

- [ ] **Step 1: Update get_architecture_context to include ACRs and issues**

In the `get_architecture_context` endpoint, after building the notes index, also load ACRs and issue links:

```python
acr_mgr = _get_acr_mgr(idx_dir)
all_acrs = acr_mgr.list_acrs()
all_links = acr_mgr.list_issue_links()

# Build ACR index by node_id
acrs_by_node: Dict[str, List[Dict[str, Any]]] = {}
for a in all_acrs:
    for nid in a.get("affected_nodes", []):
        acrs_by_node.setdefault(nid, []).append(a)

# Build issue index by node_id
issues_by_node: Dict[str, List[Dict[str, Any]]] = {}
for link in all_links:
    nid = link.get("node_id", "")
    issues_by_node.setdefault(nid, []).append(link)
```

Then in the per-module loop, after the notes, add:

```python
        # Add ACRs for this module
        for acr in acrs_by_node.get(mid, []):
            lines.append(f"  \u26a0\ufe0f ACR: \"{acr.get('title', '')}\" ({acr.get('status', '')})")

        # Add issue count
        node_issues = issues_by_node.get(mid, [])
        if node_issues:
            open_count = sum(1 for i in node_issues if i.get("status") != "closed")
            lines.append(f"  \U0001f3ab {open_count} open issue(s)")
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `.venv/bin/pytest tests/test_architecture_api_phase_b.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/prep/api/routers/architecture.py
git commit -m "feat(arch): expand MCP architecture context with ACRs and issues"
```

---

## Summary

| Task | Component | Type |
|------|-----------|------|
| 1 | TypeScript types | Types |
| 2 | ArchitectureACRManager | Backend + Tests |
| 3 | Phase B API endpoints | Backend + Tests |
| 4 | API client methods | Frontend |
| 5 | BreadcrumbNav extraction | Refactor |
| 6 | DiagramToolbar extraction | Refactor |
| 7 | DiagramSidebar extraction | Refactor |
| 8 | EntryPointNode | Frontend |
| 9 | IssueBadge overlay | Frontend |
| 10 | Hook wiring | Frontend |
| 11 | Sidebar live data | Frontend |
| 12 | Issue links endpoint | Full-stack |
| 13 | MCP context expansion | Backend |

**Dependency chain:** Tasks 1-4 (types + backend + client) must come first. Tasks 5-8 (frontend refactoring + new nodes) are independent of each other. Tasks 9-11 (overlays + wiring) depend on tasks 1-8. Tasks 12-13 (polish) come last.
