# Phase 67 — Agent Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared `agents/` package with `AgentCore`, data models, CoDRAG data wrapper, Paperclip client wrapper, git client, and agent config — the foundation all three agent engines depend on.

**Architecture:** `AgentCore` is a facade that wraps existing CoDRAG services (OpportunityManager, CodebaseAtlas, TraceIndex, CodeIndex, PushEngine, ObservationStore, SettingsStore) into a clean interface for agent engines. It uses direct Python imports — no MCP/HTTP overhead. The `agents/` package is purely additive: nothing in the existing codebase imports from it.

**Tech Stack:** Python 3.11+, pytest with asyncio_mode="auto", existing CoDRAG services (no new dependencies)

---

## File Structure

```
src/codrag/agents/
├── __init__.py                     # Package marker, exports AgentCore
├── core.py                         # AgentCore facade class
└── shared/
    ├── __init__.py                 # Package marker
    ├── models.py                   # RoleSpec, ResearchTopic, ResearchPlan, CleanupCandidate, CleanupPlan, AgentConfig
    ├── codrag_data.py              # CoDRAGDataAccess: wraps OpportunityManager, atlas, trace, search
    ├── paperclip_client.py         # PaperclipClient: wraps PushEngine + PaperclipAdapter
    └── git_client.py               # GitClient: branch, commit, archive operations

tests/
├── test_agent_models.py            # Tests for shared data models
├── test_agent_codrag_data.py       # Tests for CoDRAG data wrapper
├── test_agent_paperclip_client.py  # Tests for Paperclip client wrapper
├── test_agent_git_client.py        # Tests for git client
└── test_agent_core.py              # Tests for AgentCore facade
```

**Responsibilities:**
- `models.py` — Pure data classes. No imports from CoDRAG internals. Serializable to/from dict.
- `codrag_data.py` — Read-only CoDRAG access. Wraps OpportunityManager, CodebaseAtlas, TraceIndex, CodeIndex. Takes `index_dir` and `project_root` in constructor.
- `paperclip_client.py` — Write access to Paperclip. Wraps `create_push_engine()` and `PaperclipAdapter`. Takes `PMPushConfig` in constructor.
- `git_client.py` — Git operations for Custodian (and future agents). Wraps subprocess git calls. Takes `repo_root` in constructor.
- `core.py` — Combines all of the above into a single `AgentCore` that agent engines consume.

---

### Task 1: Package Scaffolding

**Files:**
- Create: `src/codrag/agents/__init__.py`
- Create: `src/codrag/agents/shared/__init__.py`

- [ ] **Step 1: Create the agents package**

```python
# src/codrag/agents/__init__.py
"""CoDRAG autonomous agent subsystem.

Three agents share a common AgentCore:
- Staffing Agent (hr/) — generates and audits Paperclip agent roles
- Researcher Agent (researcher/) — mines audit findings, pushes research plans
- Digital Custodian (custodian/) — identifies and cleans dead code
"""
```

- [ ] **Step 2: Create the shared subpackage**

```python
# src/codrag/agents/shared/__init__.py
"""Shared infrastructure for all CoDRAG agents."""
```

- [ ] **Step 3: Verify the packages import**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -c "import codrag.agents; import codrag.agents.shared; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/codrag/agents/__init__.py src/codrag/agents/shared/__init__.py
git commit -m "feat(agents): scaffold agents/ package structure"
```

---

### Task 2: Shared Data Models

**Files:**
- Create: `src/codrag/agents/shared/models.py`
- Create: `tests/test_agent_models.py`

These are pure dataclasses with no CoDRAG imports. They define the data contracts between agent engines and the shared infrastructure.

- [ ] **Step 1: Write failing tests for RoleSpec**

```python
# tests/test_agent_models.py
"""Tests for agent shared data models."""

from codrag.agents.shared.models import (
    RoleSpec,
    ResearchTopic,
    ResearchPlan,
    CleanupCandidate,
    CleanupPlan,
    AgentConfig,
)


class TestRoleSpec:
    def test_create_minimal(self):
        spec = RoleSpec(slug="cto", display_name="CTO")
        assert spec.slug == "cto"
        assert spec.display_name == "CTO"
        assert spec.agents_md == ""
        assert spec.soul_md == ""
        assert spec.knowledge_md == ""
        assert spec.recommended_files == []
        assert spec.paperclip_agent_id == ""

    def test_roundtrip_dict(self):
        spec = RoleSpec(
            slug="qa_lead",
            display_name="QA Lead",
            agents_md="# QA Lead\nTest everything.",
            recommended_files=["tests/", "src/codrag/core/audit/"],
        )
        d = spec.to_dict()
        restored = RoleSpec.from_dict(d)
        assert restored.slug == "qa_lead"
        assert restored.display_name == "QA Lead"
        assert restored.agents_md == "# QA Lead\nTest everything."
        assert restored.recommended_files == ["tests/", "src/codrag/core/audit/"]

    def test_slug_normalization(self):
        spec = RoleSpec(slug="VP of Engineering", display_name="VP of Engineering")
        assert spec.slug == "vp_of_engineering"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_models.py::TestRoleSpec -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codrag.agents.shared.models'`

- [ ] **Step 3: Write failing tests for ResearchTopic and ResearchPlan**

Append to `tests/test_agent_models.py`:

```python
class TestResearchTopic:
    def test_create(self):
        topic = ResearchTopic(
            finding_id="HEALTH-a7b9",
            title="Circular dependency in core/",
            description="3 files form a cycle",
            affected_files=["src/codrag/core/a.py", "src/codrag/core/b.py"],
            priority="P1",
            impact_summary="14 transitive dependents",
        )
        assert topic.finding_id == "HEALTH-a7b9"
        assert topic.priority == "P1"
        assert len(topic.affected_files) == 2

    def test_roundtrip_dict(self):
        topic = ResearchTopic(
            finding_id="ADV-c3d4",
            title="Outdated dependency",
            description="pydantic v1 still in use",
            affected_files=["pyproject.toml"],
            priority="P2",
        )
        d = topic.to_dict()
        restored = ResearchTopic.from_dict(d)
        assert restored.finding_id == "ADV-c3d4"
        assert restored.title == "Outdated dependency"


class TestResearchPlan:
    def test_create(self):
        plan = ResearchPlan(
            topic_id="HEALTH-a7b9",
            title="Fix circular dependency in core/",
            root_cause="Shared utility functions imported bidirectionally",
            fix_steps=["Extract shared code to core/shared.py", "Update imports"],
            effort="medium",
            risk="low",
            testing_strategy="Run full test suite, verify no import cycles with ruff",
        )
        assert plan.effort == "medium"
        assert len(plan.fix_steps) == 2

    def test_roundtrip_dict(self):
        plan = ResearchPlan(
            topic_id="X",
            title="T",
            root_cause="R",
            fix_steps=["a", "b"],
            effort="small",
            risk="low",
            testing_strategy="pytest",
        )
        d = plan.to_dict()
        restored = ResearchPlan.from_dict(d)
        assert restored.topic_id == "X"
        assert restored.fix_steps == ["a", "b"]
```

- [ ] **Step 4: Write failing tests for CleanupCandidate, CleanupPlan, and AgentConfig**

Append to `tests/test_agent_models.py`:

```python
class TestCleanupCandidate:
    def test_create(self):
        candidate = CleanupCandidate(
            file_path="src/legacy/old_parser.py",
            finding_id="ARCH-17",
            dependent_count=0,
            classification="safe_to_delete",
            reason="Zero dependents, no dynamic imports detected",
        )
        assert candidate.classification == "safe_to_delete"
        assert candidate.dependent_count == 0

    def test_valid_classifications(self):
        for cls in ("safe_to_delete", "needs_review", "keep"):
            c = CleanupCandidate(
                file_path="x.py",
                finding_id="X",
                dependent_count=0,
                classification=cls,
            )
            assert c.classification == cls

    def test_roundtrip_dict(self):
        c = CleanupCandidate(
            file_path="a.py", finding_id="F", dependent_count=3,
            classification="needs_review", reason="Has 3 dependents",
        )
        restored = CleanupCandidate.from_dict(c.to_dict())
        assert restored.file_path == "a.py"
        assert restored.dependent_count == 3


class TestCleanupPlan:
    def test_create(self):
        plan = CleanupPlan(
            branch_name="custodian/cleanup-2026-04-01",
            candidates=[
                CleanupCandidate(
                    file_path="old.py", finding_id="A-1",
                    dependent_count=0, classification="safe_to_delete",
                ),
            ],
            archive_branch="custodian/archive",
            dry_run=True,
        )
        assert plan.dry_run is True
        assert len(plan.candidates) == 1

    def test_safe_candidates_filter(self):
        plan = CleanupPlan(
            branch_name="custodian/cleanup-2026-04-01",
            candidates=[
                CleanupCandidate(file_path="a.py", finding_id="1", dependent_count=0, classification="safe_to_delete"),
                CleanupCandidate(file_path="b.py", finding_id="2", dependent_count=1, classification="needs_review"),
                CleanupCandidate(file_path="c.py", finding_id="3", dependent_count=0, classification="safe_to_delete"),
            ],
        )
        safe = plan.safe_candidates()
        assert len(safe) == 2
        assert all(c.classification == "safe_to_delete" for c in safe)


class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.enabled is False
        assert cfg.adapter == "native"
        assert cfg.dry_run is True
        assert cfg.cooldown_seconds == 3600

    def test_from_dict_partial(self):
        cfg = AgentConfig.from_dict({"enabled": True, "adapter": "langgraph"})
        assert cfg.enabled is True
        assert cfg.adapter == "langgraph"
        assert cfg.dry_run is True  # default preserved

    def test_roundtrip_dict(self):
        cfg = AgentConfig(enabled=True, adapter="crewai", dry_run=False, cooldown_seconds=600)
        restored = AgentConfig.from_dict(cfg.to_dict())
        assert restored.enabled is True
        assert restored.adapter == "crewai"
        assert restored.cooldown_seconds == 600
```

- [ ] **Step 5: Implement all models**

```python
# src/codrag/agents/shared/models.py
"""Shared data models for CoDRAG agents.

Pure dataclasses with no CoDRAG internal imports.
All models support dict roundtripping via to_dict() / from_dict().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _normalize_slug(raw: str) -> str:
    """Lowercase, replace non-alphanumeric with underscores, collapse runs."""
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return slug


@dataclass
class RoleSpec:
    """A Paperclip agent role definition generated by the Staffing Agent."""

    slug: str
    display_name: str
    agents_md: str = ""
    soul_md: str = ""
    knowledge_md: str = ""
    recommended_files: List[str] = field(default_factory=list)
    paperclip_agent_id: str = ""

    def __post_init__(self) -> None:
        self.slug = _normalize_slug(self.slug)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "agents_md": self.agents_md,
            "soul_md": self.soul_md,
            "knowledge_md": self.knowledge_md,
            "recommended_files": list(self.recommended_files),
            "paperclip_agent_id": self.paperclip_agent_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> RoleSpec:
        return cls(
            slug=d["slug"],
            display_name=d["display_name"],
            agents_md=d.get("agents_md", ""),
            soul_md=d.get("soul_md", ""),
            knowledge_md=d.get("knowledge_md", ""),
            recommended_files=d.get("recommended_files", []),
            paperclip_agent_id=d.get("paperclip_agent_id", ""),
        )


@dataclass
class ResearchTopic:
    """A topic selected by the Researcher Agent for deeper investigation."""

    finding_id: str
    title: str
    description: str
    affected_files: List[str] = field(default_factory=list)
    priority: str = "P2"
    impact_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "description": self.description,
            "affected_files": list(self.affected_files),
            "priority": self.priority,
            "impact_summary": self.impact_summary,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ResearchTopic:
        return cls(
            finding_id=d["finding_id"],
            title=d["title"],
            description=d["description"],
            affected_files=d.get("affected_files", []),
            priority=d.get("priority", "P2"),
            impact_summary=d.get("impact_summary", ""),
        )


@dataclass
class ResearchPlan:
    """A structured implementation plan produced by the Researcher Agent."""

    topic_id: str
    title: str
    root_cause: str
    fix_steps: List[str]
    effort: str = "medium"
    risk: str = "low"
    testing_strategy: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "root_cause": self.root_cause,
            "fix_steps": list(self.fix_steps),
            "effort": self.effort,
            "risk": self.risk,
            "testing_strategy": self.testing_strategy,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ResearchPlan:
        return cls(
            topic_id=d["topic_id"],
            title=d["title"],
            root_cause=d["root_cause"],
            fix_steps=d.get("fix_steps", []),
            effort=d.get("effort", "medium"),
            risk=d.get("risk", "low"),
            testing_strategy=d.get("testing_strategy", ""),
        )


@dataclass
class CleanupCandidate:
    """A file identified by the Digital Custodian as a potential cleanup target."""

    file_path: str
    finding_id: str
    dependent_count: int
    classification: str = "needs_review"  # safe_to_delete | needs_review | keep
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "finding_id": self.finding_id,
            "dependent_count": self.dependent_count,
            "classification": self.classification,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CleanupCandidate:
        return cls(
            file_path=d["file_path"],
            finding_id=d["finding_id"],
            dependent_count=d.get("dependent_count", 0),
            classification=d.get("classification", "needs_review"),
            reason=d.get("reason", ""),
        )


@dataclass
class CleanupPlan:
    """A cleanup plan produced by the Digital Custodian."""

    branch_name: str = ""
    candidates: List[CleanupCandidate] = field(default_factory=list)
    archive_branch: str = "custodian/archive"
    dry_run: bool = True

    def safe_candidates(self) -> List[CleanupCandidate]:
        """Return only candidates classified as safe_to_delete."""
        return [c for c in self.candidates if c.classification == "safe_to_delete"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_name": self.branch_name,
            "candidates": [c.to_dict() for c in self.candidates],
            "archive_branch": self.archive_branch,
            "dry_run": self.dry_run,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CleanupPlan:
        return cls(
            branch_name=d.get("branch_name", ""),
            candidates=[CleanupCandidate.from_dict(c) for c in d.get("candidates", [])],
            archive_branch=d.get("archive_branch", "custodian/archive"),
            dry_run=d.get("dry_run", True),
        )


@dataclass
class AgentConfig:
    """Per-agent configuration stored in settings_store."""

    enabled: bool = False
    adapter: str = "native"  # native | langgraph | crewai
    dry_run: bool = True
    cooldown_seconds: int = 3600
    max_topics_per_run: int = 3
    min_finding_priority: str = "P2"
    auto_push: bool = False
    max_files_per_run: int = 20
    exclude_paths: List[str] = field(default_factory=list)
    trigger: str = "manual"  # manual | post-pipeline

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "adapter": self.adapter,
            "dry_run": self.dry_run,
            "cooldown_seconds": self.cooldown_seconds,
            "max_topics_per_run": self.max_topics_per_run,
            "min_finding_priority": self.min_finding_priority,
            "auto_push": self.auto_push,
            "max_files_per_run": self.max_files_per_run,
            "exclude_paths": list(self.exclude_paths),
            "trigger": self.trigger,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AgentConfig:
        return cls(
            enabled=d.get("enabled", False),
            adapter=d.get("adapter", "native"),
            dry_run=d.get("dry_run", True),
            cooldown_seconds=d.get("cooldown_seconds", 3600),
            max_topics_per_run=d.get("max_topics_per_run", 3),
            min_finding_priority=d.get("min_finding_priority", "P2"),
            auto_push=d.get("auto_push", False),
            max_files_per_run=d.get("max_files_per_run", 20),
            exclude_paths=d.get("exclude_paths", []),
            trigger=d.get("trigger", "manual"),
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_models.py -v`
Expected: All 12 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/codrag/agents/shared/models.py tests/test_agent_models.py
git commit -m "feat(agents): add shared data models (RoleSpec, ResearchTopic, CleanupPlan, AgentConfig)"
```

---

### Task 3: CoDRAG Data Access Wrapper

**Files:**
- Create: `src/codrag/agents/shared/codrag_data.py`
- Create: `tests/test_agent_codrag_data.py`

This wraps CoDRAG's read-only data sources into a clean interface for agents.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agent_codrag_data.py
"""Tests for CoDRAG data access wrapper."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from codrag.agents.shared.codrag_data import CoDRAGDataAccess


@pytest.fixture
def mock_opp_manager():
    """Mock OpportunityManager."""
    mgr = MagicMock()
    mgr.get_opportunities.return_value = []
    mgr.refresh.return_value = []
    return mgr


@pytest.fixture
def data_access(tmp_path, mock_opp_manager):
    """Create a CoDRAGDataAccess with mocked internals."""
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()

    with patch(
        "codrag.agents.shared.codrag_data.OpportunityManager",
        return_value=mock_opp_manager,
    ):
        da = CoDRAGDataAccess(
            index_dir=index_dir,
            project_root=project_root,
        )
    da._opp_manager = mock_opp_manager
    return da


class TestGetAuditFindings:
    def test_returns_list(self, data_access, mock_opp_manager):
        mock_opp_manager.get_opportunities.return_value = ["finding1", "finding2"]
        result = data_access.get_audit_findings()
        assert result == ["finding1", "finding2"]
        mock_opp_manager.get_opportunities.assert_called_once()

    def test_with_priority_filter(self, data_access, mock_opp_manager):
        data_access.get_audit_findings(min_priority="P1")
        mock_opp_manager.get_opportunities.assert_called_once_with(
            min_priority="P1", include_dismissed=False,
        )

    def test_refresh_then_get(self, data_access, mock_opp_manager):
        mock_opp_manager.refresh.return_value = ["refreshed"]
        result = data_access.refresh_audit()
        assert result == ["refreshed"]
        mock_opp_manager.refresh.assert_called_once()


class TestGetAtlas:
    def test_returns_content_string(self, data_access):
        mock_atlas = MagicMock()
        mock_doc = MagicMock()
        mock_doc.content = "# Codebase Atlas\nThis is a Python project."
        mock_atlas.load.return_value = mock_doc

        with patch(
            "codrag.agents.shared.codrag_data.CodebaseAtlas",
            return_value=mock_atlas,
        ):
            da = CoDRAGDataAccess(
                index_dir=data_access._index_dir,
                project_root=data_access._project_root,
            )
            da._atlas = mock_atlas
            result = da.get_atlas()
            assert result == "# Codebase Atlas\nThis is a Python project."

    def test_returns_empty_when_no_atlas(self, data_access):
        data_access._atlas = MagicMock()
        data_access._atlas.load.return_value = None
        result = data_access.get_atlas()
        assert result == ""


class TestGetImpactRadius:
    def test_delegates_to_trace_index(self, data_access):
        mock_trace = MagicMock()
        mock_trace.get_impact_graph.return_value = {
            "target": {"id": "file:src/a.py"},
            "dependents": [{"path": "src/b.py", "distance": 1}],
        }
        data_access._trace_index = mock_trace
        result = data_access.get_impact_radius("src/a.py")
        assert result["target"]["id"] == "file:src/a.py"
        mock_trace.get_impact_graph.assert_called_once_with(
            "file:src/a.py", max_hops=2, max_nodes=30,
        )

    def test_returns_empty_when_no_trace(self, data_access):
        data_access._trace_index = None
        result = data_access.get_impact_radius("src/a.py")
        assert result == {"target": None, "dependents": []}


class TestSaveObservation:
    def test_delegates_to_observation_store(self, data_access):
        mock_obs = MagicMock()
        mock_obs.save.return_value = "obs-123"
        data_access._observation_store = mock_obs
        data_access._project_id = "proj-1"

        result = data_access.save_observation("Found a pattern", file_path="src/a.py")
        assert result == "obs-123"
        mock_obs.save.assert_called_once_with(
            "proj-1", "Found a pattern",
            file_path="src/a.py", category="note",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_codrag_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codrag.agents.shared.codrag_data'`

- [ ] **Step 3: Implement CoDRAGDataAccess**

```python
# src/codrag/agents/shared/codrag_data.py
"""Read-only access to CoDRAG's epistemic data for agent engines.

Wraps OpportunityManager, CodebaseAtlas, TraceIndex, and ObservationStore
into a clean interface. All methods are synchronous (agents run in threads).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from codrag.core.audit.opportunity_manager import OpportunityManager
from codrag.core.audit.action_item import ActionItem
from codrag.core.atlas.generator import CodebaseAtlas
from codrag.services.observation_store import observation_store


class CoDRAGDataAccess:
    """Read-only facade over CoDRAG's data sources for agent engines."""

    def __init__(
        self,
        index_dir: Path,
        project_root: Optional[Path] = None,
        project_id: str = "",
    ) -> None:
        self._index_dir = index_dir
        self._project_root = project_root
        self._project_id = project_id
        self._opp_manager = OpportunityManager(index_dir)
        self._atlas = CodebaseAtlas(index_dir, project_root=project_root)
        self._trace_index = self._load_trace_index()
        self._observation_store = observation_store

    def _load_trace_index(self) -> Any:
        """Try to load the TraceIndex. Returns None if unavailable."""
        try:
            from codrag.core.trace.index import TraceIndex

            ti = TraceIndex(self._index_dir)
            if ti.node_count > 0:
                return ti
        except Exception:
            pass
        return None

    # ── Audit Findings ──

    def get_audit_findings(
        self,
        min_priority: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ) -> List[ActionItem]:
        """Get current audit findings from the OpportunityManager."""
        kwargs: Dict[str, Any] = {"include_dismissed": False}
        if min_priority:
            kwargs["min_priority"] = min_priority
        if categories:
            kwargs["categories"] = categories
        return self._opp_manager.get_opportunities(**kwargs)

    def refresh_audit(
        self,
        categories: Optional[List[str]] = None,
    ) -> List[ActionItem]:
        """Re-run the audit scan and return fresh findings."""
        kwargs: Dict[str, Any] = {}
        if self._project_root:
            kwargs["project_root"] = self._project_root
        if categories:
            kwargs["categories"] = categories
        return self._opp_manager.refresh(**kwargs)

    # ── Atlas ──

    def get_atlas(self) -> str:
        """Get the codebase atlas overview text. Returns '' if not generated."""
        doc = self._atlas.load()
        if doc is None:
            return ""
        return doc.content

    # ── Impact Analysis ──

    def get_impact_radius(
        self,
        file_path: str,
        max_hops: int = 2,
        max_nodes: int = 30,
    ) -> Dict[str, Any]:
        """Get the dependency impact graph for a file."""
        if self._trace_index is None:
            return {"target": None, "dependents": []}
        node_id = f"file:{file_path}"
        return self._trace_index.get_impact_graph(
            node_id, max_hops=max_hops, max_nodes=max_nodes,
        )

    # ── Observations ──

    def save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        category: str = "note",
    ) -> str:
        """Save a cross-session observation. Returns the observation ID."""
        return self._observation_store.save(
            self._project_id,
            content,
            file_path=file_path,
            category=category,
        )

    def get_observations(self, query: str, limit: int = 5) -> list:
        """Search observations by content."""
        return self._observation_store.get_for_query(
            self._project_id, query, limit=limit,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_codrag_data.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/shared/codrag_data.py tests/test_agent_codrag_data.py
git commit -m "feat(agents): add CoDRAG data access wrapper"
```

---

### Task 4: Paperclip Client Wrapper

**Files:**
- Create: `src/codrag/agents/shared/paperclip_client.py`
- Create: `tests/test_agent_paperclip_client.py`

Wraps the existing PushEngine and PaperclipAdapter for agent use.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agent_paperclip_client.py
"""Tests for Paperclip client wrapper."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from codrag.agents.shared.paperclip_client import PaperclipClient
from codrag.adapters.pm_models import PMProject, PMGoal, PMIssue, PMPushConfig, PushResult


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.ensure_project.return_value = "proj-123"
    adapter.ensure_goal.return_value = "goal-456"
    adapter.create_issue.return_value = "issue-789"
    adapter.health_check.return_value = True
    return adapter


@pytest.fixture
def mock_push_engine():
    engine = MagicMock()
    engine.push.return_value = PushResult(pushed=True, issues_created=3)
    return engine


@pytest.fixture
def client(mock_adapter, mock_push_engine):
    with patch(
        "codrag.agents.shared.paperclip_client.PaperclipAdapter",
        return_value=mock_adapter,
    ), patch(
        "codrag.agents.shared.paperclip_client.create_push_engine",
        return_value=mock_push_engine,
    ):
        c = PaperclipClient(
            config=PMPushConfig(
                enabled=True,
                paperclip_url="http://localhost:3100",
                paperclip_company_id="comp-1",
            ),
        )
    c._adapter = mock_adapter
    c._push_engine = mock_push_engine
    return c


class TestPushProject:
    def test_creates_project(self, client, mock_adapter):
        project = PMProject(name="Test Project", description="A test")
        result = client.push_project(project)
        assert result == "proj-123"
        mock_adapter.ensure_project.assert_called_once_with(project, goal_ids=None)

    def test_creates_project_with_goals(self, client, mock_adapter):
        project = PMProject(name="Test", description="")
        client.push_project(project, goal_ids=["g1", "g2"])
        mock_adapter.ensure_project.assert_called_once_with(project, goal_ids=["g1", "g2"])


class TestPushGoal:
    def test_creates_goal(self, client, mock_adapter):
        goal = PMGoal(title="Fix tech debt", description="Clean up core/")
        result = client.push_goal(goal)
        assert result == "goal-456"
        mock_adapter.ensure_goal.assert_called_once_with(goal)


class TestPushIssue:
    def test_creates_issue(self, client, mock_adapter):
        issue = PMIssue(title="Remove dead code", description="old_parser.py is unused")
        result = client.push_issue(issue)
        assert result == "issue-789"
        mock_adapter.create_issue.assert_called_once_with(issue)


class TestBulkPush:
    def test_pushes_action_items(self, client, mock_push_engine):
        items = [MagicMock(), MagicMock()]
        result = client.bulk_push(items, codrag_project_id="proj-1")
        assert result.pushed is True
        assert result.issues_created == 3
        mock_push_engine.push.assert_called_once()


class TestHealthCheck:
    def test_healthy(self, client, mock_adapter):
        assert client.is_healthy() is True
        mock_adapter.health_check.assert_called_once()

    def test_unhealthy(self, client, mock_adapter):
        mock_adapter.health_check.return_value = False
        assert client.is_healthy() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_paperclip_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement PaperclipClient**

```python
# src/codrag/agents/shared/paperclip_client.py
"""Write access to Paperclip for agent engines.

Thin wrapper around the existing PushEngine and PaperclipAdapter
from Phase 65. Provides a clean interface for agents to push
projects, goals, and issues to Paperclip.
"""

from __future__ import annotations

from typing import List, Optional

from codrag.adapters.paperclip_adapter import PaperclipAdapter
from codrag.adapters.push_engine import create_push_engine
from codrag.adapters.pm_models import (
    PMGoal,
    PMIssue,
    PMProject,
    PMPushConfig,
    PushResult,
)
from codrag.core.audit.action_item import ActionItem


class PaperclipClient:
    """Agent-facing interface for pushing work items to Paperclip."""

    def __init__(self, config: PMPushConfig) -> None:
        self._config = config
        self._adapter = PaperclipAdapter(
            base_url=config.paperclip_url,
            company_id=config.paperclip_company_id,
            api_key=config.paperclip_api_key,
        )
        self._push_engine = create_push_engine(config)

    def push_project(
        self,
        project: PMProject,
        goal_ids: Optional[List[str]] = None,
    ) -> str:
        """Create or update a project in Paperclip. Returns the project ID."""
        return self._adapter.ensure_project(project, goal_ids=goal_ids)

    def push_goal(self, goal: PMGoal) -> str:
        """Create a goal in Paperclip. Returns the goal ID."""
        return self._adapter.ensure_goal(goal)

    def push_issue(self, issue: PMIssue) -> str:
        """Create an issue in Paperclip. Returns the issue ID."""
        return self._adapter.create_issue(issue)

    def bulk_push(
        self,
        items: List[ActionItem],
        codrag_project_id: str = "",
        strategy: str = "category",
        min_priority: str = "P2",
        dry_run: bool = False,
    ) -> PushResult:
        """Push a batch of ActionItems through the PushEngine pipeline."""
        return self._push_engine.push(
            items,
            codrag_project_id=codrag_project_id,
            strategy=strategy,
            min_priority=min_priority,
            dry_run=dry_run,
        )

    def is_healthy(self) -> bool:
        """Check if Paperclip is reachable."""
        return self._adapter.health_check()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_paperclip_client.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/shared/paperclip_client.py tests/test_agent_paperclip_client.py
git commit -m "feat(agents): add Paperclip client wrapper"
```

---

### Task 5: Git Client

**Files:**
- Create: `src/codrag/agents/shared/git_client.py`
- Create: `tests/test_agent_git_client.py`

Git operations for the Digital Custodian (and future agents that need to write to the codebase).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agent_git_client.py
"""Tests for agent git client."""

from __future__ import annotations

import pytest
import subprocess
from pathlib import Path

from codrag.agents.shared.git_client import GitClient


@pytest.fixture
def git_repo(tmp_path):
    """Create a real temporary git repo for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, capture_output=True, check=True,
    )
    # Create initial commit so we have a branch
    (repo / "README.md").write_text("# Test repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True, check=True,
    )
    return repo


@pytest.fixture
def client(git_repo):
    return GitClient(repo_root=git_repo)


class TestCurrentBranch:
    def test_returns_main_or_master(self, client):
        branch = client.current_branch()
        assert branch in ("main", "master")


class TestCreateBranch:
    def test_creates_and_switches(self, client):
        client.create_branch("custodian/cleanup-2026-04-01")
        assert client.current_branch() == "custodian/cleanup-2026-04-01"

    def test_switch_back(self, client):
        original = client.current_branch()
        client.create_branch("test-branch")
        client.switch_branch(original)
        assert client.current_branch() == original


class TestCommit:
    def test_commit_files(self, client, git_repo):
        # Create a file and commit it
        (git_repo / "new_file.py").write_text("print('hello')\n")
        client.add_files(["new_file.py"])
        sha = client.commit("test: add new file")
        assert len(sha) == 40  # full SHA

    def test_commit_with_no_changes_returns_empty(self, client):
        sha = client.commit("empty commit attempt")
        assert sha == ""


class TestBranchExists:
    def test_existing_branch(self, client):
        branch = client.current_branch()
        assert client.branch_exists(branch) is True

    def test_nonexistent_branch(self, client):
        assert client.branch_exists("nonexistent-branch") is False


class TestDiff:
    def test_diff_returns_string(self, client, git_repo):
        (git_repo / "changed.txt").write_text("original\n")
        client.add_files(["changed.txt"])
        client.commit("add file")
        (git_repo / "changed.txt").write_text("modified\n")
        diff = client.diff()
        assert "modified" in diff
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_git_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement GitClient**

```python
# src/codrag/agents/shared/git_client.py
"""Git operations for CoDRAG agents.

Wraps subprocess git calls for branch management, commits, and archive
operations. Used primarily by the Digital Custodian but available to
any agent that needs to write to the codebase.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional


class GitClient:
    """Safe git operations for agent use."""

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    def _run(
        self,
        args: List[str],
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a git command in the repo root."""
        return subprocess.run(
            ["git"] + args,
            cwd=self._root,
            capture_output=True,
            text=True,
            check=check,
        )

    def current_branch(self) -> str:
        """Get the current branch name."""
        result = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists locally."""
        result = self._run(
            ["rev-parse", "--verify", f"refs/heads/{branch_name}"],
            check=False,
        )
        return result.returncode == 0

    def create_branch(self, branch_name: str) -> None:
        """Create and switch to a new branch from current HEAD."""
        self._run(["checkout", "-b", branch_name])

    def switch_branch(self, branch_name: str) -> None:
        """Switch to an existing branch."""
        self._run(["checkout", branch_name])

    def add_files(self, paths: List[str]) -> None:
        """Stage files for commit."""
        self._run(["add"] + paths)

    def commit(self, message: str) -> str:
        """Commit staged changes. Returns the commit SHA, or '' if nothing to commit."""
        result = self._run(["commit", "-m", message], check=False)
        if result.returncode != 0:
            # Nothing to commit
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                return ""
            # Real error
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr,
            )
        # Extract SHA
        sha_result = self._run(["rev-parse", "HEAD"])
        return sha_result.stdout.strip()

    def diff(self, staged: bool = False) -> str:
        """Get the diff of unstaged (or staged) changes."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        result = self._run(args)
        return result.stdout

    def delete_files(self, paths: List[str]) -> None:
        """Remove files from the working tree and stage the deletions."""
        self._run(["rm"] + paths)

    def copy_to_branch(
        self,
        source_paths: List[str],
        target_branch: str,
        target_dir: str,
        commit_message: str,
    ) -> str:
        """Copy files to a target branch without switching the working tree.

        Creates the target branch if it doesn't exist.
        Returns the commit SHA on the target branch.
        """
        original_branch = self.current_branch()

        # Create target branch if needed (from current HEAD)
        if not self.branch_exists(target_branch):
            self._run(["branch", target_branch])

        # Switch to target, copy files, commit, switch back
        self.switch_branch(target_branch)
        try:
            target_path = self._root / target_dir
            target_path.mkdir(parents=True, exist_ok=True)

            for src in source_paths:
                src_path = self._root / src
                if not src_path.exists():
                    # File may have been deleted already on the original branch;
                    # try to get it from the original branch's HEAD
                    self._run(
                        ["show", f"{original_branch}:{src}"],
                        check=False,
                    )
                    continue
                dest = target_path / Path(src).name
                dest.write_bytes(src_path.read_bytes())

            self.add_files([target_dir])
            sha = self.commit(commit_message)
            return sha
        finally:
            self.switch_branch(original_branch)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_git_client.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/shared/git_client.py tests/test_agent_git_client.py
git commit -m "feat(agents): add git client for agent branch/commit operations"
```

---

### Task 6: AgentCore Facade

**Files:**
- Create: `src/codrag/agents/core.py`
- Create: `tests/test_agent_core.py`
- Modify: `src/codrag/agents/__init__.py`

The main class that agent engines consume. Combines CoDRAGDataAccess + PaperclipClient + GitClient + SettingsStore config.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agent_core.py
"""Tests for AgentCore facade."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from codrag.agents.core import AgentCore
from codrag.agents.shared.models import AgentConfig
from codrag.adapters.pm_models import PMProject, PMGoal, PMIssue, PMPushConfig


@pytest.fixture
def mock_data_access():
    da = MagicMock()
    da.get_audit_findings.return_value = []
    da.get_atlas.return_value = "# Atlas"
    da.get_impact_radius.return_value = {"target": None, "dependents": []}
    da.save_observation.return_value = "obs-1"
    da.get_observations.return_value = []
    return da


@pytest.fixture
def mock_paperclip():
    pc = MagicMock()
    pc.push_project.return_value = "proj-1"
    pc.push_goal.return_value = "goal-1"
    pc.push_issue.return_value = "issue-1"
    pc.is_healthy.return_value = True
    return pc


@pytest.fixture
def mock_git():
    return MagicMock()


@pytest.fixture
def core(mock_data_access, mock_paperclip, mock_git):
    with patch("codrag.agents.core.CoDRAGDataAccess", return_value=mock_data_access), \
         patch("codrag.agents.core.PaperclipClient", return_value=mock_paperclip), \
         patch("codrag.agents.core.GitClient", return_value=mock_git):
        c = AgentCore(
            project_id="test-proj",
            index_dir=Path("/tmp/index"),
            project_root=Path("/tmp/project"),
            pm_config=PMPushConfig(
                enabled=True,
                paperclip_url="http://localhost:3100",
                paperclip_company_id="comp-1",
            ),
        )
    c._data = mock_data_access
    c._paperclip = mock_paperclip
    c._git = mock_git
    return c


class TestCoDRAGReadAccess:
    def test_get_audit_findings(self, core, mock_data_access):
        core.get_audit_findings()
        mock_data_access.get_audit_findings.assert_called_once()

    def test_get_atlas(self, core, mock_data_access):
        result = core.get_atlas()
        assert result == "# Atlas"

    def test_get_impact_radius(self, core, mock_data_access):
        core.get_impact_radius("src/a.py")
        mock_data_access.get_impact_radius.assert_called_once_with("src/a.py")

    def test_save_observation(self, core, mock_data_access):
        result = core.save_observation("note", file_path="a.py")
        assert result == "obs-1"


class TestPaperclipWriteAccess:
    def test_push_project(self, core, mock_paperclip):
        project = PMProject(name="Test")
        result = core.push_project(project)
        assert result == "proj-1"

    def test_push_goal(self, core, mock_paperclip):
        goal = PMGoal(title="Fix it")
        result = core.push_goal(goal)
        assert result == "goal-1"

    def test_push_issue(self, core, mock_paperclip):
        issue = PMIssue(title="Bug", description="broken")
        result = core.push_issue(issue)
        assert result == "issue-1"


class TestAgentConfig:
    def test_get_config_defaults(self, core):
        with patch("codrag.agents.core.settings") as mock_settings:
            mock_settings.project_get.return_value = None
            cfg = core.get_agent_config("researcher")
            assert cfg.enabled is False
            assert cfg.adapter == "native"

    def test_get_config_from_settings(self, core):
        with patch("codrag.agents.core.settings") as mock_settings:
            mock_settings.project_get.return_value = {
                "enabled": True, "adapter": "langgraph",
            }
            cfg = core.get_agent_config("researcher")
            assert cfg.enabled is True
            assert cfg.adapter == "langgraph"

    def test_save_config(self, core):
        with patch("codrag.agents.core.settings") as mock_settings:
            cfg = AgentConfig(enabled=True, adapter="crewai")
            core.save_agent_config("custodian", cfg)
            mock_settings.project_set.assert_called_once_with(
                "test-proj", "agents_config.custodian", cfg.to_dict(),
            )


class TestGitAccess:
    def test_git_client_exposed(self, core, mock_git):
        assert core.git is mock_git
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_core.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement AgentCore**

```python
# src/codrag/agents/core.py
"""AgentCore — shared foundation for all CoDRAG-powered agents.

Provides read-only access to CoDRAG's epistemic knowledge and
write access to Paperclip's project management API. This is the
single interface that all agent engines (Staffing, Researcher,
Custodian) and all orchestration adapters (native, LangGraph,
CrewAI) consume.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from codrag.adapters.pm_models import (
    PMGoal,
    PMIssue,
    PMProject,
    PMPushConfig,
    PushResult,
)
from codrag.agents.shared.codrag_data import CoDRAGDataAccess
from codrag.agents.shared.git_client import GitClient
from codrag.agents.shared.models import AgentConfig
from codrag.agents.shared.paperclip_client import PaperclipClient
from codrag.core.audit.action_item import ActionItem
from codrag.services.settings_store import settings


class AgentCore:
    """Shared foundation for all CoDRAG-powered agents.

    Provides read-only access to CoDRAG's epistemic knowledge and
    write access to Paperclip's project management API.
    """

    def __init__(
        self,
        project_id: str,
        index_dir: Path,
        project_root: Optional[Path] = None,
        pm_config: Optional[PMPushConfig] = None,
    ) -> None:
        self.project_id = project_id
        self._index_dir = index_dir
        self._project_root = project_root

        # CoDRAG read access (the brain)
        self._data = CoDRAGDataAccess(
            index_dir=index_dir,
            project_root=project_root,
            project_id=project_id,
        )

        # Paperclip write access (the office)
        self._paperclip: Optional[PaperclipClient] = None
        if pm_config and pm_config.enabled:
            self._paperclip = PaperclipClient(config=pm_config)

        # Git access (for Custodian and future agents)
        self._git: Optional[GitClient] = None
        if project_root:
            self._git = GitClient(repo_root=project_root)

    # ── CoDRAG Read Access (Brain) ──

    def get_audit_findings(
        self,
        min_priority: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ) -> List[ActionItem]:
        """Pull the latest audit findings from CoDRAG's opportunity manager."""
        return self._data.get_audit_findings(
            min_priority=min_priority, categories=categories,
        )

    def refresh_audit(
        self,
        categories: Optional[List[str]] = None,
    ) -> List[ActionItem]:
        """Re-run the audit scan and return fresh findings."""
        return self._data.refresh_audit(categories=categories)

    def get_atlas(self) -> str:
        """Get a structural overview of the codebase."""
        return self._data.get_atlas()

    def get_impact_radius(self, file_path: str) -> Dict[str, Any]:
        """Trace what depends on a given file."""
        return self._data.get_impact_radius(file_path)

    def save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        category: str = "note",
    ) -> str:
        """Persist a cross-session observation."""
        return self._data.save_observation(
            content, file_path=file_path, category=category,
        )

    def get_observations(self, query: str, limit: int = 5) -> list:
        """Search observations by content."""
        return self._data.get_observations(query, limit=limit)

    # ── Paperclip Write Access (Office) ──

    def push_project(
        self,
        project: PMProject,
        goal_ids: Optional[List[str]] = None,
    ) -> str:
        """Create or update a project in Paperclip. Returns the project ID."""
        if not self._paperclip:
            raise RuntimeError("Paperclip not configured (pm_config.enabled is False)")
        return self._paperclip.push_project(project, goal_ids=goal_ids)

    def push_goal(self, goal: PMGoal) -> str:
        """Create a goal in Paperclip. Returns the goal ID."""
        if not self._paperclip:
            raise RuntimeError("Paperclip not configured")
        return self._paperclip.push_goal(goal)

    def push_issue(self, issue: PMIssue) -> str:
        """Create an issue in Paperclip. Returns the issue ID."""
        if not self._paperclip:
            raise RuntimeError("Paperclip not configured")
        return self._paperclip.push_issue(issue)

    def bulk_push(
        self,
        items: List[ActionItem],
        strategy: str = "category",
        min_priority: str = "P2",
        dry_run: bool = False,
    ) -> PushResult:
        """Push a batch of ActionItems through the PushEngine pipeline."""
        if not self._paperclip:
            raise RuntimeError("Paperclip not configured")
        return self._paperclip.bulk_push(
            items,
            codrag_project_id=self.project_id,
            strategy=strategy,
            min_priority=min_priority,
            dry_run=dry_run,
        )

    # ── Git Access ──

    @property
    def git(self) -> Optional[GitClient]:
        """Access the git client for branch/commit operations."""
        return self._git

    # ── Agent Configuration ──

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """Load an agent's config from the settings store."""
        raw = settings.project_get(
            self.project_id, f"agents_config.{agent_name}",
        )
        if raw is None:
            return AgentConfig()
        return AgentConfig.from_dict(raw)

    def save_agent_config(self, agent_name: str, config: AgentConfig) -> None:
        """Save an agent's config to the settings store."""
        settings.project_set(
            self.project_id, f"agents_config.{agent_name}", config.to_dict(),
        )
```

- [ ] **Step 4: Update `__init__.py` to export AgentCore**

```python
# src/codrag/agents/__init__.py
"""CoDRAG autonomous agent subsystem.

Three agents share a common AgentCore:
- Staffing Agent (hr/) — generates and audits Paperclip agent roles
- Researcher Agent (researcher/) — mines audit findings, pushes research plans
- Digital Custodian (custodian/) — identifies and cleans dead code
"""

from codrag.agents.core import AgentCore

__all__ = ["AgentCore"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_core.py -v`
Expected: All 11 tests PASS

- [ ] **Step 6: Run all agent tests together**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_*.py -v`
Expected: All tests across all 4 test files PASS

- [ ] **Step 7: Commit**

```bash
git add src/codrag/agents/core.py src/codrag/agents/__init__.py tests/test_agent_core.py
git commit -m "feat(agents): add AgentCore facade combining data access, Paperclip, git, and config"
```

---

### Task 7: Integration Smoke Test

**Files:**
- Create: `tests/test_agent_integration.py`

A lightweight integration test that verifies AgentCore can be constructed with real CoDRAG classes (mocking only external I/O).

- [ ] **Step 1: Write integration test**

```python
# tests/test_agent_integration.py
"""Integration smoke test for the agents package.

Verifies AgentCore can be constructed with real CoDRAG classes,
mocking only external I/O (Paperclip HTTP, git subprocess, LLM).
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from codrag.agents import AgentCore
from codrag.agents.shared.models import (
    AgentConfig,
    RoleSpec,
    ResearchTopic,
    ResearchPlan,
    CleanupCandidate,
    CleanupPlan,
)
from codrag.adapters.pm_models import PMPushConfig


class TestAgentCoreConstruction:
    def test_creates_without_paperclip(self, tmp_path):
        """AgentCore works without Paperclip configured."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        core = AgentCore(
            project_id="test",
            index_dir=index_dir,
            project_root=tmp_path,
        )
        assert core.project_id == "test"
        assert core._paperclip is None
        assert core.git is not None

    def test_creates_with_paperclip_disabled(self, tmp_path):
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        core = AgentCore(
            project_id="test",
            index_dir=index_dir,
            pm_config=PMPushConfig(enabled=False),
        )
        assert core._paperclip is None

    def test_get_atlas_returns_string(self, tmp_path):
        """Atlas returns empty string when no atlas has been generated."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        core = AgentCore(
            project_id="test",
            index_dir=index_dir,
            project_root=tmp_path,
        )
        result = core.get_atlas()
        assert isinstance(result, str)

    def test_get_audit_findings_returns_list(self, tmp_path):
        """Audit findings returns list (empty if no index data)."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        core = AgentCore(
            project_id="test",
            index_dir=index_dir,
            project_root=tmp_path,
        )
        result = core.get_audit_findings()
        assert isinstance(result, list)

    def test_push_without_config_raises(self, tmp_path):
        """Pushing to Paperclip without config raises RuntimeError."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        core = AgentCore(project_id="test", index_dir=index_dir)

        from codrag.adapters.pm_models import PMProject
        with pytest.raises(RuntimeError, match="Paperclip not configured"):
            core.push_project(PMProject(name="X"))

    def test_agent_config_roundtrip(self, tmp_path):
        """Agent config can be saved and loaded."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        core = AgentCore(project_id="test-roundtrip", index_dir=index_dir)
        cfg = AgentConfig(enabled=True, adapter="langgraph", cooldown_seconds=120)
        core.save_agent_config("researcher", cfg)

        loaded = core.get_agent_config("researcher")
        assert loaded.enabled is True
        assert loaded.adapter == "langgraph"
        assert loaded.cooldown_seconds == 120


class TestModelsImportable:
    """Verify all models are importable from the public API."""

    def test_all_models_importable(self):
        assert RoleSpec is not None
        assert ResearchTopic is not None
        assert ResearchPlan is not None
        assert CleanupCandidate is not None
        assert CleanupPlan is not None
        assert AgentConfig is not None
```

- [ ] **Step 2: Run integration test**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_integration.py -v`
Expected: All 7 tests PASS

- [ ] **Step 3: Run the complete agent test suite**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && python -m pytest tests/test_agent_*.py -v --tb=short`
Expected: All tests across all 5 test files PASS (approximately 37 tests total)

- [ ] **Step 4: Commit**

```bash
git add tests/test_agent_integration.py
git commit -m "test(agents): add integration smoke tests for AgentCore"
```

---

### Task 8: Update IMPLEMENTATION_STRATEGY.md

**Files:**
- Modify: `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`

Check off Phase 0 tasks and update status.

- [ ] **Step 1: Update the Phase 0 checkboxes**

In `IMPLEMENTATION_STRATEGY.md`, change all Phase 0 task checkboxes from `☐` to `☑`:

```markdown
| 0.1 | Create `agents/` package structure | `src/codrag/agents/__init__.py` | ☑ |
| 0.2 | Create `agents/shared/` subpackage | `agents/shared/__init__.py` | ☑ |
| 0.3 | Implement `AgentCore` class | `agents/core.py` | ☑ |
| 0.4 | Create shared data models | `agents/shared/models.py` | ☑ |
| 0.5 | Create CoDRAG data access wrapper | `agents/shared/codrag_data.py` | ☑ |
| 0.6 | Create Paperclip client wrapper | `agents/shared/paperclip_client.py` | ☑ |
| 0.7 | Create shared git client | `agents/shared/git_client.py` | ☑ |
| 0.8 | Add agent config namespace to settings | (settings_store integration) | ☑ |
```

- [ ] **Step 2: Commit**

```bash
git add docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md
git commit -m "docs: mark Phase 0 (Agent Foundation) as complete"
```

---

## Summary

| Task | What | Tests | Files Created |
|------|------|-------|---------------|
| 1 | Package scaffolding | 0 (import check) | 2 `__init__.py` |
| 2 | Shared data models | 12 | `models.py` + `test_agent_models.py` |
| 3 | CoDRAG data wrapper | 7 | `codrag_data.py` + `test_agent_codrag_data.py` |
| 4 | Paperclip client | 6 | `paperclip_client.py` + `test_agent_paperclip_client.py` |
| 5 | Git client | 7 | `git_client.py` + `test_agent_git_client.py` |
| 6 | AgentCore facade | 11 | `core.py` + `test_agent_core.py` |
| 7 | Integration smoke | 7 | `test_agent_integration.py` |
| 8 | Update strategy doc | 0 | (modify existing) |
| **Total** | | **~50 tests** | **7 new source files, 5 test files** |
