# Phase 1: Staffing Agent Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Staffing Agent Engine that computes codebase readiness, accepts user-specified roles (`list` mode), generates AGENTS.md / SOUL.md / KNOWLEDGE.md per role, and persists a roster. Then extend to `auto` mode (LLM-inferred roles), `auto+list` hybrid, drift detection, and org chart.

**Architecture:** The engine lives at `src/codrag/agents/hr/` as a self-contained subpackage. It consumes AgentCore (Phase 0) for CoDRAG data reads, LLM calls, and Paperclip push. Readiness scoring is a pure function over CoDRAG module/atlas data. Role file generation uses LLM prompts for AGENTS.md and SOUL.md, and templating for KNOWLEDGE.md. A JSON roster file in the index directory tracks generated roles.

**Tech Stack:** Python 3.11+, AgentCore (Phase 0), LLMClient, CoDRAG atlas/module/role APIs, JSON persistence.

**Build order:** Tasks 1-7 deliver `list` mode end-to-end. Tasks 8-11 add `auto` mode, drift detection, and org chart.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/codrag/agents/hr/__init__.py` | Subpackage init, re-exports `StaffingEngine` |
| `src/codrag/agents/hr/readiness.py` | Pure function: compute readiness score from CoDRAG data |
| `src/codrag/agents/hr/engine.py` | `StaffingEngine` class: orchestrates generation pipeline |
| `src/codrag/agents/hr/roster.py` | `Roster` class: JSON persistence for generated roles |
| `src/codrag/agents/hr/prompts.py` | Prompt templates for LLM generation |
| `tests/test_hr_readiness.py` | Readiness scoring tests |
| `tests/test_hr_roster.py` | Roster persistence tests |
| `tests/test_hr_engine.py` | StaffingEngine integration tests |
| `tests/test_hr_prompts.py` | Prompt template tests |

---

### Task 1: Create HR subpackage and readiness scoring

**Files:**
- Create: `src/codrag/agents/hr/__init__.py`
- Create: `src/codrag/agents/hr/readiness.py`
- Create: `tests/test_hr_readiness.py`

- [ ] **Step 1: Write failing tests for readiness scoring**

```python
# tests/test_hr_readiness.py
"""Tests for HR readiness scoring."""
from codrag.agents.hr.readiness import compute_readiness, ReadinessReport


class TestComputeReadiness:
    """Test the readiness scoring function."""

    def test_empty_data_scores_zero(self) -> None:
        report = compute_readiness(modules=[], atlas_content="", file_count=0)
        assert report.score == 0.0
        assert not report.ready_for_auto
        assert not report.ready_for_list

    def test_minimal_data_allows_list_mode(self) -> None:
        modules = [
            {"name": "core", "member_files": ["a.py", "b.py"] * 10, "domain_tags": ["backend"]},
            {"name": "api", "member_files": ["c.py"] * 10, "domain_tags": ["api"]},
        ]
        report = compute_readiness(
            modules=modules,
            atlas_content="# Project Atlas\nSome content here",
            file_count=30,
        )
        assert report.score >= 0.4
        assert report.ready_for_list
        # Not enough domain diversity for full auto
        assert not report.ready_for_auto

    def test_rich_data_allows_auto_mode(self) -> None:
        modules = [
            {"name": "core", "member_files": [f"core/{i}.py" for i in range(15)],
             "domain_tags": ["backend", "database"], "architecture_layer": "core"},
            {"name": "api", "member_files": [f"api/{i}.py" for i in range(10)],
             "domain_tags": ["api", "rest"], "architecture_layer": "api"},
            {"name": "ui", "member_files": [f"ui/{i}.tsx" for i in range(10)],
             "domain_tags": ["frontend", "react"], "architecture_layer": "presentation"},
        ]
        report = compute_readiness(
            modules=modules,
            atlas_content="# Atlas\n" + "x" * 200,
            file_count=50,
            has_hub_files=True,
            has_docs=True,
        )
        assert report.score >= 0.7
        assert report.ready_for_auto
        assert report.ready_for_list

    def test_report_has_dimension_breakdown(self) -> None:
        report = compute_readiness(modules=[], atlas_content="", file_count=0)
        assert "pipeline_completion" in report.dimensions
        assert "file_count" in report.dimensions
        assert "module_count" in report.dimensions
        assert "domain_coverage" in report.dimensions
        assert "layer_diversity" in report.dimensions
        assert "documentation" in report.dimensions
        assert "hub_files" in report.dimensions

    def test_missing_checklist_populated(self) -> None:
        report = compute_readiness(modules=[], atlas_content="", file_count=5)
        assert len(report.missing) > 0
        assert any("pipeline" in m.lower() or "file" in m.lower() for m in report.missing)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hr_readiness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codrag.agents.hr'`

- [ ] **Step 3: Create HR subpackage init**

```python
# src/codrag/agents/hr/__init__.py
"""Staffing Agent Engine — generates and manages AI agent role definitions."""
```

- [ ] **Step 4: Implement readiness scoring**

```python
# src/codrag/agents/hr/readiness.py
"""Epistemic readiness scoring for Staffing Agent generation.

Evaluates 7 dimensions of codebase knowledge to determine whether
role generation is viable. Pure function — no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ReadinessReport:
    """Result of readiness evaluation."""

    score: float  # 0.0–1.0 composite
    dimensions: Dict[str, float] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)

    @property
    def ready_for_auto(self) -> bool:
        return self.score >= 0.7

    @property
    def ready_for_list(self) -> bool:
        return self.score >= 0.4


# Dimension weights (must sum to 1.0)
_WEIGHTS: Dict[str, float] = {
    "pipeline_completion": 0.20,
    "file_count": 0.10,
    "module_count": 0.20,
    "domain_coverage": 0.15,
    "layer_diversity": 0.15,
    "documentation": 0.10,
    "hub_files": 0.10,
}


def compute_readiness(
    modules: List[Dict[str, Any]],
    atlas_content: str,
    file_count: int,
    has_hub_files: bool = False,
    has_docs: bool = False,
) -> ReadinessReport:
    """Compute epistemic readiness score from CoDRAG data.

    Args:
        modules: Module cluster dicts from ``get_module_structure()``.
        atlas_content: Raw atlas string from ``get_atlas()``.
        file_count: Total indexed file count.
        has_hub_files: Whether hub files have been identified.
        has_docs: Whether documentation files exist in the index.

    Returns:
        ReadinessReport with composite score, per-dimension scores, and missing items.
    """
    dims: Dict[str, float] = {}
    missing: List[str] = []

    # 1. Pipeline completion — atlas exists and has content
    dims["pipeline_completion"] = min(1.0, len(atlas_content) / 100) if atlas_content else 0.0
    if dims["pipeline_completion"] < 0.5:
        missing.append("Run the CoDRAG pipeline to generate atlas data")

    # 2. File count — need ≥20 files for meaningful analysis
    dims["file_count"] = min(1.0, file_count / 20)
    if file_count < 20:
        missing.append(f"Index more files (have {file_count}, need ≥20)")

    # 3. Module count — need ≥2 modules
    module_count = len(modules)
    dims["module_count"] = min(1.0, module_count / 2)
    if module_count < 2:
        missing.append(f"Need ≥2 module clusters (have {module_count})")

    # 4. Domain tag coverage — unique tags across modules
    all_tags: set = set()
    total_files = 0
    for m in modules:
        all_tags.update(m.get("domain_tags", []))
        total_files += len(m.get("member_files", []))
    tagged_ratio = len(all_tags) / max(1, total_files) if total_files else 0.0
    dims["domain_coverage"] = min(1.0, tagged_ratio * 10)  # scale: 10% unique-tag ratio = 1.0
    if len(all_tags) < 3:
        missing.append(f"Need more domain tag diversity (have {len(all_tags)} unique tags)")

    # 5. Layer diversity — distinct architecture_layer values
    layers: set = set()
    for m in modules:
        layer = m.get("architecture_layer", "")
        if layer:
            layers.add(layer)
    dims["layer_diversity"] = min(1.0, len(layers) / 3)
    if len(layers) < 3:
        missing.append(f"Need ≥3 architecture layers (have {len(layers)})")

    # 6. Documentation
    dims["documentation"] = 1.0 if has_docs else 0.0
    if not has_docs:
        missing.append("Index documentation files for richer role context")

    # 7. Hub files
    dims["hub_files"] = 1.0 if has_hub_files else 0.0
    if not has_hub_files:
        missing.append("Run deep enrichment to identify hub files")

    # Weighted composite
    score = sum(dims[k] * _WEIGHTS[k] for k in _WEIGHTS)
    score = round(min(1.0, max(0.0, score)), 3)

    return ReadinessReport(score=score, dimensions=dims, missing=missing)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hr_readiness.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/codrag/agents/hr/__init__.py src/codrag/agents/hr/readiness.py tests/test_hr_readiness.py
git commit -m "feat(hr): add readiness scoring with 7-dimension evaluation"
```

---

### Task 2: Roster persistence

**Files:**
- Create: `src/codrag/agents/hr/roster.py`
- Create: `tests/test_hr_roster.py`

- [ ] **Step 1: Write failing tests for roster**

```python
# tests/test_hr_roster.py
"""Tests for HR roster persistence."""
import json
from pathlib import Path

import pytest

from codrag.agents.hr.roster import Roster
from codrag.agents.shared.models import RoleSpec


@pytest.fixture
def roster_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def roster(roster_dir: Path) -> Roster:
    return Roster(roster_dir)


class TestRosterSaveLoad:
    def test_save_and_load_role(self, roster: Roster) -> None:
        role = RoleSpec(slug="backend_dev", display_name="Backend Developer",
                        agents_md="# Backend Dev", soul_md="# Soul")
        roster.save_role(role)
        loaded = roster.get_role("backend_dev")
        assert loaded is not None
        assert loaded.display_name == "Backend Developer"
        assert loaded.agents_md == "# Backend Dev"

    def test_list_roles(self, roster: Roster) -> None:
        roster.save_role(RoleSpec(slug="a", display_name="A"))
        roster.save_role(RoleSpec(slug="b", display_name="B"))
        slugs = roster.list_roles()
        assert set(slugs) == {"a", "b"}

    def test_remove_role(self, roster: Roster) -> None:
        roster.save_role(RoleSpec(slug="x", display_name="X"))
        assert roster.get_role("x") is not None
        roster.remove_role("x")
        assert roster.get_role("x") is None

    def test_remove_nonexistent_is_noop(self, roster: Roster) -> None:
        roster.remove_role("nonexistent")  # should not raise

    def test_overwrite_existing(self, roster: Roster) -> None:
        roster.save_role(RoleSpec(slug="r", display_name="V1", agents_md="old"))
        roster.save_role(RoleSpec(slug="r", display_name="V2", agents_md="new"))
        loaded = roster.get_role("r")
        assert loaded is not None
        assert loaded.display_name == "V2"
        assert loaded.agents_md == "new"

    def test_empty_roster(self, roster: Roster) -> None:
        assert roster.list_roles() == []
        assert roster.get_role("any") is None

    def test_persistence_across_instances(self, roster_dir: Path) -> None:
        r1 = Roster(roster_dir)
        r1.save_role(RoleSpec(slug="p", display_name="P"))
        r2 = Roster(roster_dir)
        assert r2.get_role("p") is not None

    def test_roster_file_is_valid_json(self, roster: Roster, roster_dir: Path) -> None:
        roster.save_role(RoleSpec(slug="j", display_name="J"))
        data = json.loads((roster_dir / "hr_roster.json").read_text())
        assert "roles" in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hr_roster.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codrag.agents.hr.roster'`

- [ ] **Step 3: Implement Roster class**

```python
# src/codrag/agents/hr/roster.py
"""JSON-backed roster persistence for generated agent roles.

Stores role specs to ``<index_dir>/hr_roster.json``.
Thread-safe via atomic write (write-to-temp then rename).
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from codrag.agents.shared.models import RoleSpec

logger = logging.getLogger(__name__)

_ROSTER_FILENAME = "hr_roster.json"


class Roster:
    """Manages the persistent roster of generated agent roles.

    Args:
        index_dir: Directory where ``hr_roster.json`` is stored.
    """

    def __init__(self, index_dir: Path) -> None:
        self._path = Path(index_dir) / _ROSTER_FILENAME
        self._roles: Dict[str, RoleSpec] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._roles = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._roles = {
                slug: RoleSpec.from_dict(rd)
                for slug, rd in data.get("roles", {}).items()
            }
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load roster from %s: %s", self._path, exc)
            self._roles = {}

    def _save(self) -> None:
        data = {"roles": {slug: role.to_dict() for slug, role in self._roles.items()}}
        # Atomic write
        fd, tmp = tempfile.mkstemp(
            dir=self._path.parent, suffix=".tmp", prefix=".hr_roster_"
        )
        try:
            import os
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(tmp).replace(self._path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def save_role(self, role: RoleSpec) -> None:
        """Save or overwrite a role in the roster."""
        self._roles[role.slug] = role
        self._save()

    def get_role(self, slug: str) -> Optional[RoleSpec]:
        """Get a role by slug, or None if not found."""
        return self._roles.get(slug)

    def list_roles(self) -> List[str]:
        """Return sorted list of all role slugs."""
        return sorted(self._roles.keys())

    def remove_role(self, slug: str) -> None:
        """Remove a role by slug. No-op if not found."""
        if slug in self._roles:
            del self._roles[slug]
            self._save()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hr_roster.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/hr/roster.py tests/test_hr_roster.py
git commit -m "feat(hr): add Roster class for JSON-backed role persistence"
```

---

### Task 3: LLM prompt templates

**Files:**
- Create: `src/codrag/agents/hr/prompts.py`
- Create: `tests/test_hr_prompts.py`

- [ ] **Step 1: Write failing tests for prompt templates**

```python
# tests/test_hr_prompts.py
"""Tests for HR prompt template rendering."""
from codrag.agents.hr.prompts import (
    render_agents_md_prompt,
    render_soul_md_prompt,
    render_knowledge_md,
    render_auto_roles_prompt,
)


class TestAgentsMdPrompt:
    def test_includes_role_name(self) -> None:
        result = render_agents_md_prompt(
            role_name="Backend Developer",
            role_slug="backend_dev",
            atlas_excerpt="# Project\nPython backend",
            modules_summary="core (15 files), api (10 files)",
            recommended_files=["src/core/main.py", "src/api/routes.py"],
        )
        assert "Backend Developer" in result
        assert "backend_dev" in result

    def test_includes_atlas_excerpt(self) -> None:
        result = render_agents_md_prompt(
            role_name="Dev",
            role_slug="dev",
            atlas_excerpt="Python + FastAPI monolith",
            modules_summary="",
            recommended_files=[],
        )
        assert "Python + FastAPI monolith" in result

    def test_includes_recommended_files(self) -> None:
        result = render_agents_md_prompt(
            role_name="Dev",
            role_slug="dev",
            atlas_excerpt="",
            modules_summary="",
            recommended_files=["src/main.py", "src/config.py"],
        )
        assert "src/main.py" in result


class TestSoulMdPrompt:
    def test_includes_role_name(self) -> None:
        result = render_soul_md_prompt(
            role_name="CTO",
            role_slug="cto",
            atlas_excerpt="Large enterprise platform",
        )
        assert "CTO" in result

    def test_includes_context(self) -> None:
        result = render_soul_md_prompt(
            role_name="Dev",
            role_slug="dev",
            atlas_excerpt="React dashboard with charts",
        )
        assert "React dashboard" in result


class TestKnowledgeMd:
    def test_renders_template_with_tools(self) -> None:
        result = render_knowledge_md(
            role_name="Backend Developer",
            role_slug="backend_dev",
            atlas_snapshot="# Atlas\nPython backend",
            recommended_files=[("src/main.py", 0.95), ("src/config.py", 0.82)],
            domain_focus=["backend", "database"],
            project_id="proj_123",
        )
        assert "codrag" in result  # tool instructions
        assert "backend_dev" in result  # role param
        assert "src/main.py" in result
        assert "0.95" in result or "95" in result
        assert "proj_123" in result

    def test_no_llm_needed(self) -> None:
        """KNOWLEDGE.md is template-based, not LLM-generated."""
        result = render_knowledge_md(
            role_name="Dev",
            role_slug="dev",
            atlas_snapshot="atlas",
            recommended_files=[],
            domain_focus=[],
            project_id="p",
        )
        assert isinstance(result, str)
        assert len(result) > 50


class TestAutoRolesPrompt:
    def test_includes_codebase_stats(self) -> None:
        result = render_auto_roles_prompt(
            file_count=150,
            module_count=8,
            modules_summary="core (30 files), api (20 files), ui (25 files)",
            atlas_excerpt="Full-stack Python + React app",
            domain_tags=["backend", "frontend", "api", "database", "auth"],
            layer_distribution={"core": 30, "api": 20, "presentation": 25},
        )
        assert "150" in result  # file count
        assert "8" in result  # module count
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hr_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement prompt templates**

```python
# src/codrag/agents/hr/prompts.py
"""LLM prompt templates and KNOWLEDGE.md template for Staffing Agent.

AGENTS.md and SOUL.md generation require LLM calls — these functions
produce the system+user prompts. KNOWLEDGE.md is pure template rendering.
"""
from __future__ import annotations

from typing import Dict, List, Tuple


def render_agents_md_prompt(
    role_name: str,
    role_slug: str,
    atlas_excerpt: str,
    modules_summary: str,
    recommended_files: List[str],
) -> str:
    """Render the LLM prompt for generating an AGENTS.md file.

    Returns the user prompt. The system prompt should instruct the LLM
    to output markdown for an agent instruction file.
    """
    files_block = "\n".join(f"- `{f}`" for f in recommended_files) if recommended_files else "(none)"
    return f"""Generate an AGENTS.md instruction file for the **{role_name}** role (slug: `{role_slug}`).

## Codebase Context

{atlas_excerpt}

## Module Structure

{modules_summary}

## Key Files for This Role

{files_block}

## Requirements

Write a markdown document (~1500 tokens) that includes:
1. **Role Summary** — One paragraph defining this role's primary responsibility
2. **Priorities** — Numbered list of what this role focuses on, grounded in the codebase modules above
3. **Behavioral Guidelines** — How this role should approach tasks (e.g., "always check impact radius before modifying hub files")
4. **Knowledge Sources** — Which CoDRAG tools to use and when:
   - `codrag(role="{role_slug}")` for scoped structural overview
   - `codrag_search(query, role="{role_slug}")` for code search
   - `codrag_impact(file)` before modifying files
5. **Boundaries** — What this role should NOT do (stay in lane)

Ground every instruction in specific modules, files, or architectural patterns from the context above. Do not use generic advice."""


AGENTS_MD_SYSTEM = """You are an expert at writing AI agent instruction files (AGENTS.md).
You produce clear, specific, actionable markdown instructions grounded in codebase evidence.
Output ONLY the markdown content — no preamble, no code fences wrapping the whole output."""


def render_soul_md_prompt(
    role_name: str,
    role_slug: str,
    atlas_excerpt: str,
) -> str:
    """Render the LLM prompt for generating a SOUL.md identity file."""
    return f"""Generate a SOUL.md identity file for the **{role_name}** role (slug: `{role_slug}`).

## Codebase Context

{atlas_excerpt}

## Requirements

Write a markdown document (~600 tokens) that includes:
1. **Identity Statement** — "I am the {role_name}. My purpose is..." (one sentence)
2. **Core Values** — 3-5 values derived from what this role protects/optimizes in this codebase
3. **Communication Style** — How this role communicates (e.g., concise for operators, detailed for architects)
4. **Guardrails** — 2-3 things this role must never do
5. **Collaboration** — How this role relates to other roles on the team

Derive everything from the codebase context. A CTO of a React dashboard app has different values than a CTO of an embedded systems project."""


SOUL_MD_SYSTEM = """You are an expert at writing AI agent identity files (SOUL.md).
You produce concise, personality-defining markdown that gives an AI agent a coherent identity.
Output ONLY the markdown content — no preamble, no code fences wrapping the whole output."""


def render_knowledge_md(
    role_name: str,
    role_slug: str,
    atlas_snapshot: str,
    recommended_files: List[Tuple[str, float]],
    domain_focus: List[str],
    project_id: str,
) -> str:
    """Render KNOWLEDGE.md from template (no LLM needed).

    Args:
        recommended_files: List of (file_path, relevance_score) tuples.
        domain_focus: Domain tags relevant to this role.
    """
    files_table = ""
    if recommended_files:
        files_table = "| File | Relevance |\n|------|----------|\n"
        for path, score in recommended_files:
            files_table += f"| `{path}` | {score:.2f} |\n"
    else:
        files_table = "(No files scored yet — run auto-populate to generate.)"

    domains = ", ".join(domain_focus) if domain_focus else "(general)"

    return f"""# Knowledge Base — {role_name}

> Auto-generated by CoDRAG Staffing Agent. Do not edit manually.

## CoDRAG Tools

Use these tools to get live, role-scoped context:

| Tool | Usage |
|------|-------|
| `codrag(role="{role_slug}")` | Structural overview filtered for your role |
| `codrag_search(query, role="{role_slug}")` | Semantic code search scoped to your files |
| `codrag_impact(file)` | Check blast radius before modifying files |
| `codrag_audit()` | Review codebase health findings |
| `codrag_observe(content)` | Save observations for cross-session memory |

**Project ID:** `{project_id}`

## Architecture Snapshot

{atlas_snapshot}

## Key Files

{files_table}

## Domain Focus

{domains}

## Usage Notes

- Call `codrag(role="{role_slug}")` at the start of every task for scoped context
- Use `codrag_impact()` before modifying any file in the Key Files table
- Files with relevance ≥0.8 are your primary responsibility
- Files with relevance 0.4–0.8 are shared with other roles
"""


def render_auto_roles_prompt(
    file_count: int,
    module_count: int,
    modules_summary: str,
    atlas_excerpt: str,
    domain_tags: List[str],
    layer_distribution: Dict[str, int],
) -> str:
    """Render the LLM prompt for auto-inferring roles from codebase analysis."""
    tags_str = ", ".join(domain_tags) if domain_tags else "(none)"
    layers_str = ", ".join(f"{k}: {v} files" for k, v in layer_distribution.items()) if layer_distribution else "(none)"

    return f"""Analyze this codebase and recommend an optimal team of AI agent roles.

## Codebase Statistics

- **Total files:** {file_count}
- **Module clusters:** {module_count}
- **Domain tags:** {tags_str}
- **Architecture layers:** {layers_str}

## Module Structure

{modules_summary}

## Codebase Overview

{atlas_excerpt}

## Instructions

Based on the codebase structure above, recommend 2-6 agent roles. For each role provide:

1. **slug** — lowercase_underscore identifier
2. **display_name** — Human-readable role title
3. **justification** — Why this role is needed (cite specific modules/domains)
4. **primary_modules** — Which modules this role owns
5. **domain_focus** — Which domain tags this role covers

Respond as a JSON array of objects with these 5 fields. Do not include generic roles unless the codebase evidence supports them. Fewer focused roles are better than many overlapping ones.

Guidelines:
- Small codebases (<30 files): 2-3 generalist roles
- Medium codebases (30-100 files): 3-4 roles
- Large codebases (>100 files): 4-6 specialized roles
- Monorepos: Consider domain-owner roles per workspace"""


AUTO_ROLES_SYSTEM = """You are an expert at analyzing codebases and designing optimal AI agent team structures.
You output ONLY valid JSON — a JSON array of role objects. No markdown, no explanations outside the JSON."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hr_prompts.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/hr/prompts.py tests/test_hr_prompts.py
git commit -m "feat(hr): add LLM prompt templates and KNOWLEDGE.md template"
```

---

### Task 4: StaffingEngine — list mode (core pipeline)

**Files:**
- Create: `src/codrag/agents/hr/engine.py`
- Create: `tests/test_hr_engine.py`

This is the main orchestrator. For testability, the LLM is injected as a callable so tests can use a mock.

- [ ] **Step 1: Write failing tests for list-mode generation**

```python
# tests/test_hr_engine.py
"""Tests for StaffingEngine."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple
from unittest.mock import MagicMock

import pytest

from codrag.agents.hr.engine import StaffingEngine
from codrag.agents.hr.readiness import ReadinessReport
from codrag.agents.hr.roster import Roster
from codrag.agents.shared.models import RoleSpec


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    """Fake LLM that returns deterministic content based on the prompt."""
    if "AGENTS.md" in prompt:
        return "# Agent Instructions\n\nYou are the role.", 50
    if "SOUL.md" in prompt:
        return "# Soul\n\nI am the role.", 30
    if "Analyze this codebase" in prompt:
        import json
        return json.dumps([
            {"slug": "backend_dev", "display_name": "Backend Developer",
             "justification": "Core module has 30 files",
             "primary_modules": ["core"], "domain_focus": ["backend"]},
        ]), 80
    return "Unknown prompt", 10


@pytest.fixture
def engine_dir(tmp_path: Path) -> Path:
    """Create a minimal index directory with module data."""
    import json
    modules = [
        {"name": "core", "member_files": [f"core/{i}.py" for i in range(15)],
         "domain_tags": ["backend", "database"], "architecture_layer": "core",
         "summary": "Core business logic"},
        {"name": "api", "member_files": [f"api/{i}.py" for i in range(10)],
         "domain_tags": ["api", "rest"], "architecture_layer": "api",
         "summary": "REST API layer"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    (tmp_path / "codebase_atlas.md").write_text("# Test Project\nPython backend with REST API")
    return tmp_path


@pytest.fixture
def engine(engine_dir: Path) -> StaffingEngine:
    return StaffingEngine(index_dir=engine_dir, project_id="test_proj")


class TestReadiness:
    def test_check_readiness_returns_report(self, engine: StaffingEngine) -> None:
        report = engine.check_readiness()
        assert isinstance(report, ReadinessReport)
        assert report.score > 0

    def test_readiness_uses_module_data(self, engine: StaffingEngine) -> None:
        report = engine.check_readiness()
        assert report.dimensions["module_count"] > 0


class TestListMode:
    def test_generate_roles_returns_specs(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Backend Developer", "API Specialist"],
            llm_fn=_fake_llm,
        )
        assert len(roles) == 2
        assert all(isinstance(r, RoleSpec) for r in roles)
        assert roles[0].slug == "backend_developer"
        assert roles[1].slug == "api_specialist"

    def test_generate_roles_populates_agents_md(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Dev"],
            llm_fn=_fake_llm,
        )
        assert "Agent Instructions" in roles[0].agents_md

    def test_generate_roles_populates_soul_md(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Dev"],
            llm_fn=_fake_llm,
        )
        assert "Soul" in roles[0].soul_md

    def test_generate_roles_populates_knowledge_md(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Dev"],
            llm_fn=_fake_llm,
        )
        assert "codrag" in roles[0].knowledge_md
        assert "test_proj" in roles[0].knowledge_md

    def test_generate_roles_saves_to_roster(self, engine: StaffingEngine) -> None:
        engine.generate_roles(
            role_names=["Backend Developer"],
            llm_fn=_fake_llm,
        )
        roster = Roster(engine._index_dir)
        assert roster.get_role("backend_developer") is not None

    def test_generate_with_insufficient_readiness_raises(
        self, tmp_path: Path
    ) -> None:
        engine = StaffingEngine(index_dir=tmp_path, project_id="empty")
        with pytest.raises(ValueError, match="readiness"):
            engine.generate_roles(role_names=["Dev"], llm_fn=_fake_llm)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hr_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codrag.agents.hr.engine'`

- [ ] **Step 3: Implement StaffingEngine**

```python
# src/codrag/agents/hr/engine.py
"""Staffing Agent Engine — generates AI agent role definitions from codebase analysis.

Orchestrates readiness scoring, role generation (list/auto/hybrid modes),
and roster persistence. Uses AgentCore for CoDRAG data access and LLM calls.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from codrag.agents.hr.prompts import (
    AGENTS_MD_SYSTEM,
    SOUL_MD_SYSTEM,
    render_agents_md_prompt,
    render_knowledge_md,
    render_soul_md_prompt,
)
from codrag.agents.hr.readiness import ReadinessReport, compute_readiness
from codrag.agents.hr.roster import Roster
from codrag.agents.shared.models import RoleSpec, _normalize_slug

logger = logging.getLogger(__name__)

# Type alias for injectable LLM function
LLMFn = Callable[..., Tuple[str, int]]


class StaffingEngine:
    """Generates and manages AI agent role definitions.

    Args:
        index_dir: Path to the CoDRAG index directory.
        project_id: CoDRAG project identifier.
        project_root: Optional path to the project source root.
    """

    def __init__(
        self,
        index_dir: Path,
        project_id: str,
        project_root: Optional[Path] = None,
    ) -> None:
        self._index_dir = Path(index_dir)
        self._project_id = project_id
        self._project_root = project_root
        self._roster = Roster(self._index_dir)

    # ── Data Access Helpers ─────────────────────────────────────────

    def _load_modules(self) -> List[Dict[str, Any]]:
        modules_path = self._index_dir / "trace_modules.jsonl"
        if not modules_path.exists():
            return []
        modules: List[Dict[str, Any]] = []
        for line in modules_path.read_text().strip().splitlines():
            if line.strip():
                try:
                    modules.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return modules

    def _load_atlas(self) -> str:
        atlas_path = self._index_dir / "codebase_atlas.md"
        if atlas_path.exists():
            return atlas_path.read_text(encoding="utf-8")
        return ""

    def _count_indexed_files(self) -> int:
        modules = self._load_modules()
        return sum(len(m.get("member_files", [])) for m in modules)

    def _modules_summary(self, modules: List[Dict[str, Any]]) -> str:
        parts = []
        for m in modules:
            name = m.get("name", "unknown")
            count = len(m.get("member_files", []))
            summary = m.get("summary", "")
            tags = ", ".join(m.get("domain_tags", []))
            parts.append(f"- **{name}** ({count} files): {summary} [{tags}]")
        return "\n".join(parts) if parts else "(no modules)"

    # ── Readiness ───────────────────────────────────────────────────

    def check_readiness(self) -> ReadinessReport:
        """Evaluate codebase readiness for role generation."""
        modules = self._load_modules()
        atlas = self._load_atlas()
        file_count = sum(len(m.get("member_files", [])) for m in modules)

        # Check for hub files
        has_hub_files = any(
            m.get("hub_score", 0) > 0 or "hub" in str(m.get("domain_tags", []))
            for m in modules
        )

        # Check for docs
        has_docs = bool(atlas and len(atlas) > 50)

        return compute_readiness(
            modules=modules,
            atlas_content=atlas,
            file_count=file_count,
            has_hub_files=has_hub_files,
            has_docs=has_docs,
        )

    # ── List Mode Generation ────────────────────────────────────────

    def generate_roles(
        self,
        role_names: List[str],
        llm_fn: LLMFn,
        min_readiness: float = 0.3,
    ) -> List[RoleSpec]:
        """Generate role definitions for user-specified role names (list mode).

        Args:
            role_names: Display names for roles to generate.
            llm_fn: Callable with signature ``(prompt, system=, **kwargs) -> (text, tokens)``.
            min_readiness: Minimum readiness score required. Default 0.3 for list mode.

        Returns:
            List of generated RoleSpec instances.

        Raises:
            ValueError: If readiness score is below threshold.
        """
        report = self.check_readiness()
        if report.score < min_readiness:
            missing_str = "; ".join(report.missing[:3]) if report.missing else "insufficient data"
            raise ValueError(
                f"Codebase readiness too low for generation "
                f"(score={report.score:.2f}, need≥{min_readiness}). "
                f"Missing: {missing_str}"
            )

        modules = self._load_modules()
        atlas = self._load_atlas()
        modules_summary = self._modules_summary(modules)

        # Collect domain tags for KNOWLEDGE.md
        all_tags: List[str] = []
        for m in modules:
            all_tags.extend(m.get("domain_tags", []))

        roles: List[RoleSpec] = []
        for name in role_names:
            slug = _normalize_slug(name)
            role = self._generate_single_role(
                display_name=name,
                slug=slug,
                atlas=atlas,
                modules_summary=modules_summary,
                domain_tags=list(set(all_tags)),
                llm_fn=llm_fn,
            )
            self._roster.save_role(role)
            roles.append(role)

        return roles

    def _generate_single_role(
        self,
        display_name: str,
        slug: str,
        atlas: str,
        modules_summary: str,
        domain_tags: List[str],
        llm_fn: LLMFn,
    ) -> RoleSpec:
        """Generate all three files for a single role."""
        # Truncate atlas for prompt context
        atlas_excerpt = atlas[:2000] if atlas else "(no atlas available)"

        # 1. Generate AGENTS.md via LLM
        agents_prompt = render_agents_md_prompt(
            role_name=display_name,
            role_slug=slug,
            atlas_excerpt=atlas_excerpt,
            modules_summary=modules_summary,
            recommended_files=[],  # populated later via auto-populate
        )
        agents_md, _ = llm_fn(agents_prompt, system=AGENTS_MD_SYSTEM)

        # 2. Generate SOUL.md via LLM
        soul_prompt = render_soul_md_prompt(
            role_name=display_name,
            role_slug=slug,
            atlas_excerpt=atlas_excerpt,
        )
        soul_md, _ = llm_fn(soul_prompt, system=SOUL_MD_SYSTEM)

        # 3. Generate KNOWLEDGE.md via template (no LLM)
        knowledge_md = render_knowledge_md(
            role_name=display_name,
            role_slug=slug,
            atlas_snapshot=atlas_excerpt,
            recommended_files=[],  # populated later via auto-populate
            domain_focus=domain_tags,
            project_id=self._project_id,
        )

        return RoleSpec(
            slug=slug,
            display_name=display_name,
            agents_md=agents_md,
            soul_md=soul_md,
            knowledge_md=knowledge_md,
        )

    # ── Roster Access ───────────────────────────────────────────────

    @property
    def roster(self) -> Roster:
        """Access the underlying roster."""
        return self._roster
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hr_engine.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/hr/engine.py tests/test_hr_engine.py
git commit -m "feat(hr): add StaffingEngine with list-mode role generation"
```

---

### Task 5: Update HR `__init__.py` with public API and run full test suite

**Files:**
- Modify: `src/codrag/agents/hr/__init__.py`

- [ ] **Step 1: Update init with re-exports**

```python
# src/codrag/agents/hr/__init__.py
"""Staffing Agent Engine — generates and manages AI agent role definitions."""

from codrag.agents.hr.engine import StaffingEngine
from codrag.agents.hr.readiness import ReadinessReport, compute_readiness
from codrag.agents.hr.roster import Roster

__all__ = [
    "StaffingEngine",
    "ReadinessReport",
    "compute_readiness",
    "Roster",
]
```

- [ ] **Step 2: Run the full HR test suite**

Run: `.venv/bin/pytest tests/test_hr_readiness.py tests/test_hr_roster.py tests/test_hr_prompts.py tests/test_hr_engine.py -v`
Expected: All tests PASS (5 + 8 + 7 + 7 = 27 tests)

- [ ] **Step 3: Run all Phase 0 tests too to ensure no regressions**

Run: `.venv/bin/pytest tests/test_agent_*.py tests/test_hr_*.py -v`
Expected: All 149 tests PASS (122 Phase 0 + 27 Phase 1)

- [ ] **Step 4: Commit**

```bash
git add src/codrag/agents/hr/__init__.py
git commit -m "feat(hr): export public API from hr subpackage"
```

---

### Task 6: Update IMPLEMENTATION_STRATEGY.md — mark Phase 1 list-mode tasks complete

**Files:**
- Modify: `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`

- [ ] **Step 1: Update task 1.1 through 1.4 status to ☑ in the strategy doc**

Mark these as complete:
- 1.1: Create `agents/hr/` subpackage → ☑
- 1.2: Implement readiness scoring → ☑
- 1.3: Implement role generation (list mode only so far) → ☑ (partial — list mode done)
- 1.4: Implement AGENTS.md generation → ☑
- 1.5: Implement SOUL.md generation → ☑
- 1.6: Implement KNOWLEDGE.md generation → ☑
- 1.9: Create LLM prompts → ☑

- [ ] **Step 2: Commit**

```bash
git add docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md
git commit -m "docs: update Phase 1 progress — list mode complete"
```

---

### Task 7: Auto mode — LLM-inferred role generation

**Files:**
- Modify: `src/codrag/agents/hr/engine.py`
- Modify: `tests/test_hr_engine.py`

- [ ] **Step 1: Write failing tests for auto mode**

Add to `tests/test_hr_engine.py`:

```python
class TestAutoMode:
    def test_auto_generate_returns_roles(self, engine: StaffingEngine) -> None:
        roles = engine.auto_generate_roles(llm_fn=_fake_llm)
        assert len(roles) >= 1
        assert all(isinstance(r, RoleSpec) for r in roles)

    def test_auto_generate_uses_llm_for_role_inference(
        self, engine: StaffingEngine
    ) -> None:
        calls: list = []
        def tracking_llm(prompt: str, system: str | None = None, **kw) -> Tuple[str, int]:
            calls.append(prompt)
            return _fake_llm(prompt, system=system, **kw)

        engine.auto_generate_roles(llm_fn=tracking_llm)
        # First call should be the auto-roles inference prompt
        assert any("Analyze this codebase" in c for c in calls)

    def test_auto_generate_saves_to_roster(self, engine: StaffingEngine) -> None:
        engine.auto_generate_roles(llm_fn=_fake_llm)
        roster = Roster(engine._index_dir)
        assert len(roster.list_roles()) >= 1

    def test_auto_mode_requires_higher_readiness(self, tmp_path: Path) -> None:
        engine = StaffingEngine(index_dir=tmp_path, project_id="empty")
        with pytest.raises(ValueError, match="readiness"):
            engine.auto_generate_roles(llm_fn=_fake_llm)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hr_engine.py::TestAutoMode -v`
Expected: FAIL — `AttributeError: 'StaffingEngine' object has no attribute 'auto_generate_roles'`

- [ ] **Step 3: Implement auto_generate_roles**

Add to `src/codrag/agents/hr/engine.py`:

```python
# Add this import at the top
from codrag.agents.hr.prompts import AUTO_ROLES_SYSTEM, render_auto_roles_prompt

# Add these methods to StaffingEngine class:

    def auto_generate_roles(
        self,
        llm_fn: LLMFn,
        min_readiness: float = 0.5,
    ) -> List[RoleSpec]:
        """Auto-infer roles from codebase analysis, then generate files (auto mode).

        Args:
            llm_fn: Callable with signature ``(prompt, system=, **kwargs) -> (text, tokens)``.
            min_readiness: Minimum readiness score. Default 0.5 for auto mode.

        Returns:
            List of generated RoleSpec instances.

        Raises:
            ValueError: If readiness score is below threshold.
        """
        report = self.check_readiness()
        if report.score < min_readiness:
            missing_str = "; ".join(report.missing[:3]) if report.missing else "insufficient data"
            raise ValueError(
                f"Codebase readiness too low for auto generation "
                f"(score={report.score:.2f}, need≥{min_readiness}). "
                f"Missing: {missing_str}"
            )

        modules = self._load_modules()
        atlas = self._load_atlas()

        # Infer roles via LLM
        inferred = self._infer_roles(modules, atlas, llm_fn)

        # Generate files for each inferred role
        return self.generate_roles(
            role_names=[r["display_name"] for r in inferred],
            llm_fn=llm_fn,
            min_readiness=0.0,  # already checked above
        )

    def hybrid_generate_roles(
        self,
        required_names: List[str],
        llm_fn: LLMFn,
        min_readiness: float = 0.5,
    ) -> List[RoleSpec]:
        """Auto-infer roles but guarantee required_names are included (auto+list mode).

        Args:
            required_names: Role names that must be included.
            llm_fn: Callable LLM function.
            min_readiness: Minimum readiness score.

        Returns:
            List of generated RoleSpec instances.
        """
        report = self.check_readiness()
        if report.score < min_readiness:
            missing_str = "; ".join(report.missing[:3]) if report.missing else "insufficient data"
            raise ValueError(
                f"Codebase readiness too low for hybrid generation "
                f"(score={report.score:.2f}, need≥{min_readiness}). "
                f"Missing: {missing_str}"
            )

        modules = self._load_modules()
        atlas = self._load_atlas()

        # Infer roles via LLM
        inferred = self._infer_roles(modules, atlas, llm_fn)
        inferred_names = [r["display_name"] for r in inferred]

        # Merge: required names + any inferred names not already covered
        required_slugs = {_normalize_slug(n) for n in required_names}
        merged = list(required_names)
        for name in inferred_names:
            if _normalize_slug(name) not in required_slugs:
                merged.append(name)

        return self.generate_roles(
            role_names=merged,
            llm_fn=llm_fn,
            min_readiness=0.0,
        )

    def _infer_roles(
        self,
        modules: List[Dict[str, Any]],
        atlas: str,
        llm_fn: LLMFn,
    ) -> List[Dict[str, Any]]:
        """Use LLM to infer optimal roles from codebase analysis."""
        # Collect stats
        all_tags: List[str] = []
        layer_dist: Dict[str, int] = {}
        for m in modules:
            all_tags.extend(m.get("domain_tags", []))
            layer = m.get("architecture_layer", "unknown")
            layer_dist[layer] = layer_dist.get(layer, 0) + len(m.get("member_files", []))

        file_count = sum(len(m.get("member_files", [])) for m in modules)
        prompt = render_auto_roles_prompt(
            file_count=file_count,
            module_count=len(modules),
            modules_summary=self._modules_summary(modules),
            atlas_excerpt=atlas[:2000] if atlas else "",
            domain_tags=sorted(set(all_tags)),
            layer_distribution=layer_dist,
        )

        response, _ = llm_fn(prompt, system=AUTO_ROLES_SYSTEM, json_mode=True)

        try:
            roles = json.loads(response)
            if not isinstance(roles, list):
                roles = [roles]
            return roles
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse auto-roles LLM response: %s", exc)
            return [{"slug": "engineer", "display_name": "Engineer"}]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hr_engine.py -v`
Expected: All tests PASS (7 list-mode + 4 auto-mode = 11)

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/hr/engine.py tests/test_hr_engine.py
git commit -m "feat(hr): add auto and hybrid role generation modes"
```

---

### Task 8: Drift detection and audit

**Files:**
- Modify: `src/codrag/agents/hr/engine.py`
- Create: `tests/test_hr_drift.py`

- [ ] **Step 1: Write failing tests for drift detection**

```python
# tests/test_hr_drift.py
"""Tests for HR drift detection / audit."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from codrag.agents.hr.engine import StaffingEngine, DriftReport, RoleFitness
from codrag.agents.hr.roster import Roster
from codrag.agents.shared.models import RoleSpec


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "AGENTS.md" in prompt:
        return "# Agent\nBackend role.", 30
    if "SOUL.md" in prompt:
        return "# Soul\nI am backend.", 20
    return "ok", 10


@pytest.fixture
def engine_with_roles(tmp_path: Path) -> StaffingEngine:
    modules = [
        {"name": "core", "member_files": [f"core/{i}.py" for i in range(15)],
         "domain_tags": ["backend", "database"], "architecture_layer": "core",
         "summary": "Core logic"},
        {"name": "api", "member_files": [f"api/{i}.py" for i in range(10)],
         "domain_tags": ["api", "rest"], "architecture_layer": "api",
         "summary": "API layer"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    (tmp_path / "codebase_atlas.md").write_text("# Project\nPython backend")
    engine = StaffingEngine(index_dir=tmp_path, project_id="test")

    # Pre-populate roster
    roster = Roster(tmp_path)
    roster.save_role(RoleSpec(
        slug="backend_dev", display_name="Backend Developer",
        agents_md="# Backend Dev\nManages core module",
        soul_md="# Soul", knowledge_md="# Knowledge",
    ))
    roster.save_role(RoleSpec(
        slug="api_specialist", display_name="API Specialist",
        agents_md="# API Specialist\nManages api module",
        soul_md="# Soul", knowledge_md="# Knowledge",
    ))
    # Force reload
    engine._roster = Roster(tmp_path)
    return engine


class TestDriftDetection:
    def test_audit_returns_drift_report(
        self, engine_with_roles: StaffingEngine
    ) -> None:
        report = engine_with_roles.audit_roles()
        assert isinstance(report, DriftReport)
        assert len(report.role_fitness) == 2

    def test_role_fitness_has_score(
        self, engine_with_roles: StaffingEngine
    ) -> None:
        report = engine_with_roles.audit_roles()
        for rf in report.role_fitness:
            assert 0.0 <= rf.fitness_score <= 1.0
            assert rf.slug in ("backend_dev", "api_specialist")

    def test_role_fitness_has_recommendation(
        self, engine_with_roles: StaffingEngine
    ) -> None:
        report = engine_with_roles.audit_roles()
        for rf in report.role_fitness:
            assert rf.recommendation in (
                "healthy", "minor_drift", "significant_drift", "critical"
            )

    def test_empty_roster_returns_empty_report(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "trace_modules.jsonl").write_text("")
        (tmp_path / "codebase_atlas.md").write_text("# Atlas")
        engine = StaffingEngine(index_dir=tmp_path, project_id="test")
        report = engine.audit_roles()
        assert len(report.role_fitness) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hr_drift.py -v`
Expected: FAIL — `ImportError: cannot import name 'DriftReport'`

- [ ] **Step 3: Implement drift detection**

Add these dataclasses and methods to `src/codrag/agents/hr/engine.py`:

```python
# Add to imports at top:
from dataclasses import dataclass, field

# Add after LLMFn type alias:

@dataclass
class RoleFitness:
    """Fitness assessment for a single role."""

    slug: str
    display_name: str
    fitness_score: float  # 0.0–1.0
    recommendation: str  # healthy | minor_drift | significant_drift | critical
    details: str = ""

    @staticmethod
    def classify(score: float) -> str:
        if score > 0.8:
            return "healthy"
        if score > 0.6:
            return "minor_drift"
        if score > 0.4:
            return "significant_drift"
        return "critical"


@dataclass
class DriftReport:
    """Result of roster drift analysis."""

    role_fitness: List[RoleFitness] = field(default_factory=list)
    coverage_gaps: List[str] = field(default_factory=list)
    overlap_warnings: List[str] = field(default_factory=list)


# Add to StaffingEngine class:

    def audit_roles(self) -> DriftReport:
        """Analyze drift between existing roles and current codebase state.

        Computes a fitness score per role by checking whether the modules
        and domain tags referenced in the role's AGENTS.md still exist
        and are relevant.

        Returns:
            DriftReport with per-role fitness and cross-role analysis.
        """
        roles = self._roster.list_roles()
        if not roles:
            return DriftReport()

        modules = self._load_modules()
        module_names = {m.get("name", "").lower() for m in modules}
        all_tags = set()
        for m in modules:
            all_tags.update(t.lower() for t in m.get("domain_tags", []))

        fitness_list: List[RoleFitness] = []
        covered_modules: set = set()

        for slug in roles:
            role = self._roster.get_role(slug)
            if role is None:
                continue

            score = self._compute_role_fitness(role, module_names, all_tags)
            fitness_list.append(RoleFitness(
                slug=role.slug,
                display_name=role.display_name,
                fitness_score=score,
                recommendation=RoleFitness.classify(score),
            ))

            # Track which modules are covered
            for mn in module_names:
                if mn in role.agents_md.lower():
                    covered_modules.add(mn)

        # Coverage gaps — modules not mentioned by any role
        gaps = [mn for mn in module_names if mn not in covered_modules and mn]

        return DriftReport(
            role_fitness=fitness_list,
            coverage_gaps=gaps,
        )

    def _compute_role_fitness(
        self,
        role: RoleSpec,
        module_names: set,
        domain_tags: set,
    ) -> float:
        """Score how well a role's definition matches current codebase.

        Checks:
        - Do modules referenced in AGENTS.md still exist? (weight: 0.5)
        - Do domain tags in KNOWLEDGE.md still exist? (weight: 0.3)
        - Is the role's content non-empty? (weight: 0.2)
        """
        content = (role.agents_md + " " + role.knowledge_md).lower()

        # Module reference score
        referenced = sum(1 for mn in module_names if mn and mn in content)
        module_score = min(1.0, referenced / max(1, len(module_names) * 0.3))

        # Domain tag score
        tag_hits = sum(1 for t in domain_tags if t and t in content)
        tag_score = min(1.0, tag_hits / max(1, len(domain_tags) * 0.3))

        # Content completeness
        content_score = 1.0 if len(role.agents_md) > 50 and len(role.soul_md) > 20 else 0.5

        return round(module_score * 0.5 + tag_score * 0.3 + content_score * 0.2, 3)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hr_drift.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/hr/engine.py tests/test_hr_drift.py
git commit -m "feat(hr): add drift detection and role fitness scoring"
```

---

### Task 9: Org chart generation

**Files:**
- Modify: `src/codrag/agents/hr/engine.py`
- Modify: `tests/test_hr_engine.py`

- [ ] **Step 1: Write failing tests for org chart**

Add to `tests/test_hr_engine.py`:

```python
class TestOrgChart:
    def test_org_chart_returns_dict(self, engine: StaffingEngine) -> None:
        engine.generate_roles(role_names=["CTO", "Backend Dev"], llm_fn=_fake_llm)
        chart = engine.generate_org_chart()
        assert isinstance(chart, dict)
        assert "roles" in chart

    def test_org_chart_includes_all_roles(self, engine: StaffingEngine) -> None:
        engine.generate_roles(role_names=["CTO", "Backend Dev"], llm_fn=_fake_llm)
        chart = engine.generate_org_chart()
        slugs = {r["slug"] for r in chart["roles"]}
        assert "cto" in slugs
        assert "backend_dev" in slugs

    def test_org_chart_empty_roster(self, engine: StaffingEngine) -> None:
        chart = engine.generate_org_chart()
        assert chart["roles"] == []

    def test_org_chart_as_markdown(self, engine: StaffingEngine) -> None:
        engine.generate_roles(role_names=["CTO", "Backend Dev"], llm_fn=_fake_llm)
        md = engine.generate_org_chart_md()
        assert "CTO" in md or "cto" in md.lower()
        assert "Backend Dev" in md or "backend_dev" in md.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hr_engine.py::TestOrgChart -v`
Expected: FAIL — `AttributeError: 'StaffingEngine' object has no attribute 'generate_org_chart'`

- [ ] **Step 3: Implement org chart generation**

Add to `src/codrag/agents/hr/engine.py` `StaffingEngine` class:

```python
    def generate_org_chart(self) -> Dict[str, Any]:
        """Generate an org chart from the current roster.

        Returns a dict with structure:
        ```
        {
            "roles": [
                {"slug": "...", "display_name": "...", "collaborates_with": [...]},
                ...
            ]
        }
        ```

        Collaboration relationships are inferred from shared module/domain references.
        """
        slugs = self._roster.list_roles()
        if not slugs:
            return {"roles": []}

        roles_data: List[Dict[str, Any]] = []
        role_modules: Dict[str, set] = {}

        modules = self._load_modules()
        module_names = {m.get("name", "").lower() for m in modules}

        # Detect which modules each role references
        for slug in slugs:
            role = self._roster.get_role(slug)
            if role is None:
                continue
            content = (role.agents_md + " " + role.knowledge_md).lower()
            referenced = {mn for mn in module_names if mn and mn in content}
            role_modules[slug] = referenced

        # Build collaboration graph from shared modules
        for slug in slugs:
            role = self._roster.get_role(slug)
            if role is None:
                continue
            collaborators = []
            my_modules = role_modules.get(slug, set())
            for other_slug in slugs:
                if other_slug == slug:
                    continue
                other_modules = role_modules.get(other_slug, set())
                if my_modules & other_modules:
                    collaborators.append(other_slug)

            roles_data.append({
                "slug": slug,
                "display_name": role.display_name,
                "collaborates_with": collaborators,
                "modules": sorted(my_modules),
            })

        return {"roles": roles_data}

    def generate_org_chart_md(self) -> str:
        """Generate a markdown representation of the org chart."""
        chart = self.generate_org_chart()
        if not chart["roles"]:
            return "# Org Chart\n\n(No roles defined yet.)\n"

        lines = ["# Org Chart\n"]
        for r in chart["roles"]:
            lines.append(f"## {r['display_name']} (`{r['slug']}`)")
            if r["modules"]:
                lines.append(f"- **Modules:** {', '.join(r['modules'])}")
            if r["collaborates_with"]:
                lines.append(f"- **Collaborates with:** {', '.join(r['collaborates_with'])}")
            lines.append("")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hr_engine.py -v`
Expected: All tests PASS (11 existing + 4 org chart = 15)

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/hr/engine.py tests/test_hr_engine.py
git commit -m "feat(hr): add org chart generation from roster"
```

---

### Task 10: Edge case handling

**Files:**
- Modify: `src/codrag/agents/hr/engine.py`
- Modify: `tests/test_hr_engine.py`

- [ ] **Step 1: Write failing tests for edge cases**

Add to `tests/test_hr_engine.py`:

```python
class TestEdgeCases:
    def test_regenerate_overwrites_existing(self, engine: StaffingEngine) -> None:
        engine.generate_roles(role_names=["Dev"], llm_fn=_fake_llm)
        v1 = engine.roster.get_role("dev")
        assert v1 is not None

        # Re-generate same role
        engine.generate_roles(role_names=["Dev"], llm_fn=_fake_llm)
        v2 = engine.roster.get_role("dev")
        assert v2 is not None
        # Should still exist (overwritten, not duplicated)
        assert len(engine.roster.list_roles()) == 1

    def test_duplicate_slugs_in_list(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Backend Dev", "Backend Dev"],
            llm_fn=_fake_llm,
        )
        # Should deduplicate
        assert len(roles) == 1

    def test_empty_role_names_list(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(role_names=[], llm_fn=_fake_llm)
        assert roles == []

    def test_special_chars_in_role_name(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["C++ Backend (Senior)"],
            llm_fn=_fake_llm,
        )
        assert len(roles) == 1
        assert roles[0].slug == "c_backend_senior"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hr_engine.py::TestEdgeCases -v`
Expected: Some tests FAIL (dedup not yet implemented)

- [ ] **Step 3: Add deduplication to generate_roles**

In `src/codrag/agents/hr/engine.py`, update the `generate_roles` method — replace the loop section:

```python
    def generate_roles(
        self,
        role_names: List[str],
        llm_fn: LLMFn,
        min_readiness: float = 0.3,
    ) -> List[RoleSpec]:
        """Generate role definitions for user-specified role names (list mode).

        Args:
            role_names: Display names for roles to generate.
            llm_fn: Callable with signature ``(prompt, system=, **kwargs) -> (text, tokens)``.
            min_readiness: Minimum readiness score required. Default 0.3 for list mode.

        Returns:
            List of generated RoleSpec instances.

        Raises:
            ValueError: If readiness score is below threshold.
        """
        if not role_names:
            return []

        report = self.check_readiness()
        if report.score < min_readiness:
            missing_str = "; ".join(report.missing[:3]) if report.missing else "insufficient data"
            raise ValueError(
                f"Codebase readiness too low for generation "
                f"(score={report.score:.2f}, need≥{min_readiness}). "
                f"Missing: {missing_str}"
            )

        modules = self._load_modules()
        atlas = self._load_atlas()
        modules_summary = self._modules_summary(modules)

        all_tags: List[str] = []
        for m in modules:
            all_tags.extend(m.get("domain_tags", []))

        # Deduplicate by slug
        seen_slugs: set = set()
        unique_names: List[str] = []
        for name in role_names:
            slug = _normalize_slug(name)
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                unique_names.append(name)

        roles: List[RoleSpec] = []
        for name in unique_names:
            slug = _normalize_slug(name)
            role = self._generate_single_role(
                display_name=name,
                slug=slug,
                atlas=atlas,
                modules_summary=modules_summary,
                domain_tags=list(set(all_tags)),
                llm_fn=llm_fn,
            )
            self._roster.save_role(role)
            roles.append(role)

        return roles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hr_engine.py -v`
Expected: All tests PASS (15 + 4 = 19)

- [ ] **Step 5: Commit**

```bash
git add src/codrag/agents/hr/engine.py tests/test_hr_engine.py
git commit -m "feat(hr): handle edge cases — dedup, empty list, special chars"
```

---

### Task 11: Final integration test and strategy doc update

**Files:**
- Create: `tests/test_hr_integration.py`
- Modify: `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`

- [ ] **Step 1: Write integration test that exercises the full pipeline**

```python
# tests/test_hr_integration.py
"""Integration tests for the full Staffing Agent pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from codrag.agents.hr import StaffingEngine, ReadinessReport, Roster


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "AGENTS.md" in prompt:
        return "# Agent Instructions\n\nYou are the role. Focus on core module.", 50
    if "SOUL.md" in prompt:
        return "# Soul\n\nI am the role. I value code quality.", 30
    if "Analyze this codebase" in prompt:
        return json.dumps([
            {"slug": "backend_dev", "display_name": "Backend Developer",
             "justification": "Core module", "primary_modules": ["core"],
             "domain_focus": ["backend"]},
            {"slug": "api_eng", "display_name": "API Engineer",
             "justification": "API module", "primary_modules": ["api"],
             "domain_focus": ["api"]},
        ]), 80
    return "ok", 10


@pytest.fixture
def rich_index(tmp_path: Path) -> Path:
    """Create a realistic index directory."""
    modules = [
        {"name": "core", "member_files": [f"core/{i}.py" for i in range(20)],
         "domain_tags": ["backend", "database", "business_logic"],
         "architecture_layer": "core", "summary": "Core business logic"},
        {"name": "api", "member_files": [f"api/{i}.py" for i in range(15)],
         "domain_tags": ["api", "rest", "http"],
         "architecture_layer": "api", "summary": "REST API layer"},
        {"name": "workers", "member_files": [f"workers/{i}.py" for i in range(10)],
         "domain_tags": ["async", "background", "tasks"],
         "architecture_layer": "services", "summary": "Background workers"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    atlas = "# Project Atlas\n\nFull-stack Python application with REST API and background workers.\n" + "x" * 200
    (tmp_path / "codebase_atlas.md").write_text(atlas)
    return tmp_path


class TestFullPipeline:
    def test_list_mode_end_to_end(self, rich_index: Path) -> None:
        engine = StaffingEngine(index_dir=rich_index, project_id="integ_test")

        # 1. Check readiness
        report = engine.check_readiness()
        assert report.ready_for_list

        # 2. Generate roles
        roles = engine.generate_roles(
            role_names=["Backend Developer", "API Engineer"],
            llm_fn=_fake_llm,
        )
        assert len(roles) == 2

        # 3. Verify all three files populated
        for role in roles:
            assert len(role.agents_md) > 0
            assert len(role.soul_md) > 0
            assert len(role.knowledge_md) > 0
            assert "codrag" in role.knowledge_md

        # 4. Verify roster persistence
        roster = Roster(rich_index)
        assert set(roster.list_roles()) == {"backend_developer", "api_engineer"}

        # 5. Audit drift
        drift = engine.audit_roles()
        assert len(drift.role_fitness) == 2

        # 6. Org chart
        chart = engine.generate_org_chart()
        assert len(chart["roles"]) == 2

    def test_auto_mode_end_to_end(self, rich_index: Path) -> None:
        engine = StaffingEngine(index_dir=rich_index, project_id="integ_test")

        report = engine.check_readiness()
        # May or may not be ready for auto depending on score
        # Just verify it doesn't crash
        if report.score >= 0.5:
            roles = engine.auto_generate_roles(llm_fn=_fake_llm)
            assert len(roles) >= 1
        else:
            with pytest.raises(ValueError):
                engine.auto_generate_roles(llm_fn=_fake_llm)

    def test_roster_survives_engine_restart(self, rich_index: Path) -> None:
        e1 = StaffingEngine(index_dir=rich_index, project_id="test")
        e1.generate_roles(role_names=["Dev"], llm_fn=_fake_llm)

        e2 = StaffingEngine(index_dir=rich_index, project_id="test")
        assert e2.roster.get_role("dev") is not None
```

- [ ] **Step 2: Run full integration tests**

Run: `.venv/bin/pytest tests/test_hr_integration.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Run the complete test suite**

Run: `.venv/bin/pytest tests/test_agent_*.py tests/test_hr_*.py -v`
Expected: All tests PASS (Phase 0 + Phase 1)

- [ ] **Step 4: Update IMPLEMENTATION_STRATEGY.md — mark all Phase 1 tasks complete**

Mark tasks 1.1–1.9 as ☑. Leave 1.10 (Paperclip adapter) and 1.11 (edge cases from Doc 05) as ☐ — those depend on later phases.

- [ ] **Step 5: Commit**

```bash
git add tests/test_hr_integration.py docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md
git commit -m "feat(hr): complete Phase 1 — Staffing Agent Engine with list/auto/hybrid modes, drift detection, org chart"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Readiness scoring | 5 |
| 2 | Roster persistence | 8 |
| 3 | LLM prompt templates | 7 |
| 4 | StaffingEngine — list mode | 7 |
| 5 | Public API + regression check | 0 (run existing) |
| 6 | Strategy doc update | 0 |
| 7 | Auto + hybrid modes | 4 |
| 8 | Drift detection | 4 |
| 9 | Org chart | 4 |
| 10 | Edge cases | 4 |
| 11 | Integration test + final update | 3 |
| **Total** | | **~46 tests** |
