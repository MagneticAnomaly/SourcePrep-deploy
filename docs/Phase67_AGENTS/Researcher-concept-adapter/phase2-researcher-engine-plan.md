# Phase 2: Researcher Agent Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Researcher Agent Engine that ingests Prep audit findings, uses an LLM to select high-impact topics, researches solutions, formulates structured implementation plans, and packages them for Paperclip push.

**Architecture:** The engine lives at `src/prep/agents/researcher/` as a self-contained subpackage. It accepts an `AgentCore` (or raw `index_dir` for tests) and an injectable LLM function — same pattern as Phase 1's StaffingEngine. The pipeline is: ingest → select → research → formulate → (optionally) push. The shared `ResearchTopic` and `ResearchPlan` models from Phase 0 are used as-is.

**Tech Stack:** Python 3.11+, AgentCore (Phase 0), LLMClient, Prep audit/search/impact APIs, PaperclipClient, JSON persistence.

**Build order:** Tasks 1-5 deliver the core engine. Task 6 adds push packaging. Task 7 adds run history. Task 8 is integration test.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/prep/agents/researcher/__init__.py` | Subpackage init, re-exports `ResearcherEngine` |
| `src/prep/agents/researcher/prompts.py` | LLM prompt templates for topic selection, research, plan formulation |
| `src/prep/agents/researcher/engine.py` | `ResearcherEngine` class: orchestrates the research pipeline |
| `src/prep/agents/researcher/history.py` | `ResearchHistory` class: JSON persistence for past research runs |
| `tests/test_researcher_prompts.py` | Prompt template tests |
| `tests/test_researcher_engine.py` | ResearcherEngine tests |
| `tests/test_researcher_history.py` | History persistence tests |
| `tests/test_researcher_integration.py` | Full pipeline integration tests |

---

### Task 1: Create researcher subpackage and prompt templates

**Files:**
- Create: `src/prep/agents/researcher/__init__.py`
- Create: `src/prep/agents/researcher/prompts.py`
- Create: `tests/test_researcher_prompts.py`

- [ ] **Step 1: Create subpackage init**

```python
# src/prep/agents/researcher/__init__.py
"""Researcher Agent Engine — mines audit findings, researches solutions, formulates plans."""
```

- [ ] **Step 2: Write tests for prompt templates**

```python
# tests/test_researcher_prompts.py
"""Tests for Researcher prompt template rendering."""
from prep.agents.researcher.prompts import (
    render_topic_selection_prompt,
    render_research_prompt,
    render_plan_formulation_prompt,
)


class TestTopicSelectionPrompt:
    def test_includes_findings(self) -> None:
        findings = [
            {"id": "f1", "title": "Dead imports", "priority": "P1",
             "description": "12 unused imports", "affected_files": ["a.py"]},
            {"id": "f2", "title": "Circular dep", "priority": "P0",
             "description": "core <-> api cycle", "affected_files": ["b.py"]},
        ]
        result = render_topic_selection_prompt(
            findings=findings,
            max_topics=3,
            atlas_excerpt="Python backend app",
        )
        assert "Dead imports" in result
        assert "Circular dep" in result
        assert "3" in result  # max_topics

    def test_includes_atlas_context(self) -> None:
        result = render_topic_selection_prompt(
            findings=[{"id": "f1", "title": "Bug", "priority": "P2",
                       "description": "desc", "affected_files": []}],
            max_topics=3,
            atlas_excerpt="React + FastAPI monolith",
        )
        assert "React + FastAPI" in result


class TestResearchPrompt:
    def test_includes_topic_details(self) -> None:
        result = render_research_prompt(
            topic_title="Circular dependency in core",
            topic_description="core imports api which imports core",
            affected_files=["src/core/main.py", "src/api/routes.py"],
            code_context="def main(): from api import routes",
            impact_summary="15 files affected",
        )
        assert "Circular dependency" in result
        assert "src/core/main.py" in result
        assert "15 files affected" in result

    def test_includes_code_context(self) -> None:
        result = render_research_prompt(
            topic_title="Bug",
            topic_description="desc",
            affected_files=[],
            code_context="class Foo: pass",
            impact_summary="",
        )
        assert "class Foo" in result


class TestPlanFormulationPrompt:
    def test_includes_research_output(self) -> None:
        result = render_plan_formulation_prompt(
            topic_title="Fix circular deps",
            research_output="Extract shared module to break cycle",
            affected_files=["a.py", "b.py"],
        )
        assert "Fix circular deps" in result
        assert "Extract shared module" in result
        assert "a.py" in result

    def test_requests_structured_output(self) -> None:
        result = render_plan_formulation_prompt(
            topic_title="T",
            research_output="R",
            affected_files=[],
        )
        assert "root_cause" in result
        assert "fix_steps" in result
        assert "effort" in result
        assert "risk" in result
```

- [ ] **Step 3: Implement prompt templates**

```python
# src/prep/agents/researcher/prompts.py
"""LLM prompt templates for Researcher Agent.

Three-stage pipeline: topic selection → research synthesis → plan formulation.
"""
from __future__ import annotations

from typing import Any, Dict, List


def render_topic_selection_prompt(
    findings: List[Dict[str, Any]],
    max_topics: int,
    atlas_excerpt: str,
) -> str:
    """Render the LLM prompt for selecting high-impact topics from audit findings."""
    findings_block = ""
    for i, f in enumerate(findings, 1):
        findings_block += (
            f"\n{i}. **[{f.get('priority', 'P2')}] {f.get('title', 'Untitled')}**\n"
            f"   ID: {f.get('id', '')}\n"
            f"   Description: {f.get('description', '')}\n"
            f"   Files: {', '.join(f.get('affected_files', []))}\n"
        )

    return f"""You are a technical PM reviewing codebase audit findings.

## Codebase Context

{atlas_excerpt}

## Audit Findings

{findings_block}

## Task

Select the top {max_topics} findings that would most benefit from deeper research
and a structured implementation plan. Prioritize by:
1. Impact — how many files/modules are affected
2. Severity — P0 > P1 > P2 > P3
3. Actionability — can a clear fix plan be formulated?

Return a JSON array of objects, each with:
- "finding_id": the ID from the list above
- "rationale": one sentence explaining why this topic is worth researching

Select exactly {max_topics} topics (or fewer if fewer findings exist)."""


TOPIC_SELECTION_SYSTEM = """You are an expert technical PM who triages codebase issues.
You output ONLY valid JSON — a JSON array of objects. No markdown, no explanations outside the JSON."""


def render_research_prompt(
    topic_title: str,
    topic_description: str,
    affected_files: List[str],
    code_context: str,
    impact_summary: str,
) -> str:
    """Render the LLM prompt for researching a solution to a specific topic."""
    files_block = "\n".join(f"- `{f}`" for f in affected_files) if affected_files else "(none)"

    return f"""Research a solution for this codebase issue:

## Issue

**Title:** {topic_title}
**Description:** {topic_description}

## Affected Files

{files_block}

## Impact

{impact_summary if impact_summary else "(not analyzed)"}

## Code Context

```
{code_context if code_context else "(no code context available)"}
```

## Task

Produce a detailed analysis covering:
1. **Root cause** — Why does this issue exist? What design decision or oversight led to it?
2. **Solution approach** — What is the best fix? Describe the concrete changes needed.
3. **Step-by-step procedure** — Ordered list of specific code changes to make.
4. **Risks** — What could go wrong? What should be tested carefully?
5. **Effort estimate** — small (< 1 hour), medium (1-4 hours), or large (> 4 hours)

Be specific. Reference actual files and code patterns from the context above."""


RESEARCH_SYSTEM = """You are an expert software engineer analyzing codebase issues.
You produce detailed, actionable technical analysis grounded in the provided code context.
Output clear markdown prose — no JSON wrapping."""


def render_plan_formulation_prompt(
    topic_title: str,
    research_output: str,
    affected_files: List[str],
) -> str:
    """Render the LLM prompt for structuring research into a formal plan."""
    files_block = "\n".join(f"- `{f}`" for f in affected_files) if affected_files else "(none)"

    return f"""Convert this research analysis into a structured implementation plan.

## Research: {topic_title}

{research_output}

## Affected Files

{files_block}

## Task

Output a JSON object with exactly these fields:
- "root_cause": string — one paragraph explaining the root cause
- "fix_steps": array of strings — ordered list of concrete implementation steps
- "effort": "small" | "medium" | "large"
- "risk": "low" | "medium" | "high"
- "testing_strategy": string — how to verify the fix works

Be specific in fix_steps. Each step should be a concrete action like
"Extract shared types from core/models.py into core/shared_types.py"."""


PLAN_FORMULATION_SYSTEM = """You are an expert at converting technical analysis into structured implementation plans.
You output ONLY valid JSON — a single JSON object. No markdown, no explanations outside the JSON."""
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_researcher_prompts.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/agents/researcher/__init__.py src/prep/agents/researcher/prompts.py tests/test_researcher_prompts.py
git commit -m "feat(researcher): add subpackage and LLM prompt templates"
```

---

### Task 2: Research history persistence

**Files:**
- Create: `src/prep/agents/researcher/history.py`
- Create: `tests/test_researcher_history.py`

- [ ] **Step 1: Write tests for history persistence**

```python
# tests/test_researcher_history.py
"""Tests for Researcher history persistence."""
import json
from pathlib import Path

import pytest

from prep.agents.researcher.history import ResearchHistory
from prep.agents.shared.models import ResearchPlan, ResearchTopic


@pytest.fixture
def history(tmp_path: Path) -> ResearchHistory:
    return ResearchHistory(tmp_path)


def _sample_topic() -> ResearchTopic:
    return ResearchTopic(
        finding_id="f1", title="Fix circular deps",
        description="core <-> api cycle",
        affected_files=["a.py"], priority="P1",
    )


def _sample_plan() -> ResearchPlan:
    return ResearchPlan(
        topic_id="f1", title="Fix circular deps",
        root_cause="Bidirectional import",
        fix_steps=["Extract shared types", "Update imports"],
        effort="medium", risk="low",
        testing_strategy="Run import checker",
    )


class TestResearchHistory:
    def test_save_and_load_run(self, history: ResearchHistory) -> None:
        run_id = history.save_run(
            topics=[_sample_topic()],
            plans=[_sample_plan()],
        )
        assert run_id  # non-empty string

        loaded = history.get_run(run_id)
        assert loaded is not None
        assert len(loaded["topics"]) == 1
        assert len(loaded["plans"]) == 1
        assert loaded["topics"][0]["title"] == "Fix circular deps"

    def test_list_runs(self, history: ResearchHistory) -> None:
        history.save_run(topics=[_sample_topic()], plans=[_sample_plan()])
        history.save_run(topics=[_sample_topic()], plans=[_sample_plan()])
        runs = history.list_runs()
        assert len(runs) == 2

    def test_empty_history(self, history: ResearchHistory) -> None:
        assert history.list_runs() == []
        assert history.get_run("nonexistent") is None

    def test_run_has_timestamp(self, history: ResearchHistory) -> None:
        run_id = history.save_run(topics=[], plans=[])
        loaded = history.get_run(run_id)
        assert "timestamp" in loaded

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        h1 = ResearchHistory(tmp_path)
        run_id = h1.save_run(topics=[_sample_topic()], plans=[_sample_plan()])
        h2 = ResearchHistory(tmp_path)
        assert h2.get_run(run_id) is not None

    def test_latest_run(self, history: ResearchHistory) -> None:
        history.save_run(topics=[], plans=[])
        run_id2 = history.save_run(
            topics=[_sample_topic()], plans=[_sample_plan()],
        )
        latest = history.get_latest()
        assert latest is not None
        assert latest["run_id"] == run_id2
```

- [ ] **Step 2: Implement ResearchHistory**

```python
# src/prep/agents/researcher/history.py
"""JSON-backed persistence for research run history.

Stores runs to ``<index_dir>/researcher_history.json``.
Each run captures the topics selected and plans formulated.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from prep.agents.shared.models import ResearchPlan, ResearchTopic

logger = logging.getLogger(__name__)

_HISTORY_FILENAME = "researcher_history.json"


class ResearchHistory:
    """Manages persistent history of research runs.

    Args:
        index_dir: Directory where ``researcher_history.json`` is stored.
    """

    def __init__(self, index_dir: Path) -> None:
        self._path = Path(index_dir) / _HISTORY_FILENAME
        self._runs: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._runs = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._runs = data.get("runs", [])
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load research history: %s", exc)
            self._runs = []

    def _save(self) -> None:
        data = {"runs": self._runs}
        fd, tmp = tempfile.mkstemp(
            dir=self._path.parent, suffix=".tmp", prefix=".researcher_history_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(tmp).replace(self._path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def save_run(
        self,
        topics: List[ResearchTopic],
        plans: List[ResearchPlan],
    ) -> str:
        """Save a research run and return its ID."""
        run_id = uuid.uuid4().hex[:12]
        run = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topics": [t.to_dict() for t in topics],
            "plans": [p.to_dict() for p in plans],
        }
        self._runs.append(run)
        self._save()
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run by ID, or None if not found."""
        for run in self._runs:
            if run["run_id"] == run_id:
                return run
        return None

    def list_runs(self) -> List[Dict[str, Any]]:
        """Return all runs, oldest first."""
        return list(self._runs)

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Return the most recent run, or None if empty."""
        return self._runs[-1] if self._runs else None
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_researcher_history.py -v`
Expected: All 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/prep/agents/researcher/history.py tests/test_researcher_history.py
git commit -m "feat(researcher): add ResearchHistory for run persistence"
```

---

### Task 3: ResearcherEngine — topic selection

**Files:**
- Create: `src/prep/agents/researcher/engine.py`
- Create: `tests/test_researcher_engine.py`

- [ ] **Step 1: Write tests for topic selection**

```python
# tests/test_researcher_engine.py
"""Tests for ResearcherEngine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from prep.agents.researcher.engine import ResearcherEngine
from prep.agents.shared.models import ResearchPlan, ResearchTopic


def _make_findings_jsonl(tmp_path: Path, count: int = 5) -> None:
    """Write fake audit findings the engine can load."""
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
    (tmp_path / "codebase_atlas.md").write_text(
        "# Test Project\nPython backend with REST API"
    )


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    """Fake LLM returning deterministic responses based on prompt content."""
    if "Select the top" in prompt or "select" in prompt.lower()[:50]:
        return json.dumps([
            {"finding_id": "f1", "rationale": "High impact circular dep"},
            {"finding_id": "f2", "rationale": "Security concern"},
        ]), 60
    if "Research a solution" in prompt:
        return (
            "## Root Cause\nBidirectional import between core and api.\n"
            "## Solution\nExtract shared types into a new module.\n"
            "## Steps\n1. Create shared_types.py\n2. Move types\n3. Update imports\n"
        ), 100
    if "Convert this research" in prompt:
        return json.dumps({
            "root_cause": "Bidirectional import between core and api",
            "fix_steps": ["Create shared_types.py", "Move types", "Update imports"],
            "effort": "medium",
            "risk": "low",
            "testing_strategy": "Run import cycle checker",
        }), 80
    return "ok", 10


def _sample_findings() -> List[Dict[str, Any]]:
    return [
        {"id": "f1", "title": "Circular dependency", "priority": "P0",
         "description": "core <-> api import cycle", "severity": "high",
         "affected_files": ["src/core/main.py", "src/api/routes.py"],
         "category": "architecture"},
        {"id": "f2", "title": "Hardcoded secrets", "priority": "P1",
         "description": "API key in config.py", "severity": "high",
         "affected_files": ["src/config.py"],
         "category": "security"},
        {"id": "f3", "title": "Dead code", "priority": "P2",
         "description": "Unused helper functions", "severity": "low",
         "affected_files": ["src/utils.py"],
         "category": "maintenance"},
    ]


@pytest.fixture
def engine_dir(tmp_path: Path) -> Path:
    _make_findings_jsonl(tmp_path)
    return tmp_path


@pytest.fixture
def engine(engine_dir: Path) -> ResearcherEngine:
    return ResearcherEngine(index_dir=engine_dir, project_id="test_proj")


class TestTopicSelection:
    def test_select_topics_returns_research_topics(
        self, engine: ResearcherEngine
    ) -> None:
        topics = engine.select_topics(
            findings=_sample_findings(),
            llm_fn=_fake_llm,
            max_topics=2,
        )
        assert len(topics) == 2
        assert all(isinstance(t, ResearchTopic) for t in topics)

    def test_select_topics_uses_finding_data(
        self, engine: ResearcherEngine
    ) -> None:
        topics = engine.select_topics(
            findings=_sample_findings(),
            llm_fn=_fake_llm,
            max_topics=2,
        )
        assert topics[0].finding_id == "f1"
        assert topics[0].title == "Circular dependency"

    def test_select_topics_with_no_findings(
        self, engine: ResearcherEngine
    ) -> None:
        topics = engine.select_topics(
            findings=[],
            llm_fn=_fake_llm,
            max_topics=3,
        )
        assert topics == []

    def test_select_topics_caps_at_max(
        self, engine: ResearcherEngine
    ) -> None:
        topics = engine.select_topics(
            findings=_sample_findings(),
            llm_fn=_fake_llm,
            max_topics=1,
        )
        assert len(topics) <= 1

    def test_select_topics_raises_on_bad_llm_json(
        self, engine: ResearcherEngine
    ) -> None:
        def bad_llm(prompt: str, **kw) -> Tuple[str, int]:
            return "not json", 10
        with pytest.raises(ValueError, match="topic selection"):
            engine.select_topics(
                findings=_sample_findings(),
                llm_fn=bad_llm,
                max_topics=2,
            )
```

- [ ] **Step 2: Implement ResearcherEngine with topic selection**

```python
# src/prep/agents/researcher/engine.py
"""Researcher Agent Engine — mines audit findings and formulates implementation plans.

Pipeline: ingest findings → select topics → research solutions → formulate plans.
Uses AgentCore for Prep data access when available.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from prep.agents.researcher.history import ResearchHistory
from prep.agents.researcher.prompts import (
    PLAN_FORMULATION_SYSTEM,
    RESEARCH_SYSTEM,
    TOPIC_SELECTION_SYSTEM,
    render_plan_formulation_prompt,
    render_research_prompt,
    render_topic_selection_prompt,
)
from prep.agents.shared.models import ResearchPlan, ResearchTopic

logger = logging.getLogger(__name__)

# Type alias for injectable LLM function
LLMFn = Callable[..., Tuple[str, int]]


class ResearcherEngine:
    """Mines Prep audit findings, researches solutions, formulates plans.

    Accepts either an ``AgentCore`` instance (preferred) or raw ``index_dir``
    + ``project_id`` for lightweight / test usage.

    Args:
        core: AgentCore instance.
        index_dir: Path to the Prep index directory (fallback).
        project_id: Prep project identifier (fallback).
    """

    def __init__(
        self,
        core: Optional[Any] = None,
        *,
        index_dir: Optional[Path] = None,
        project_id: str = "",
    ) -> None:
        if core is not None:
            self._core = core
            self._index_dir = core._data._index_dir
            self._project_id = core.project_id
        elif index_dir is not None:
            self._core = None
            self._index_dir = Path(index_dir)
            self._project_id = project_id
        else:
            raise ValueError("Provide either 'core' (AgentCore) or 'index_dir'")

        self._history = ResearchHistory(self._index_dir)

    # -- Data Access --

    def _load_atlas(self) -> str:
        if self._core is not None:
            return self._core.get_atlas()
        atlas_path = self._index_dir / "codebase_atlas.md"
        if atlas_path.exists():
            return atlas_path.read_text(encoding="utf-8")
        return ""

    def _search_code(self, query: str) -> str:
        if self._core is not None:
            results = self._core.search_code(query, k=3)
            return "\n".join(
                r.get("doc", {}).get("content", str(r))
                for r in results
            ) if results else ""
        return ""

    def _get_impact(self, file_path: str) -> str:
        if self._core is not None:
            result = self._core.get_impact_radius(file_path)
            deps = result.get("dependents", [])
            if deps:
                return f"{len(deps)} dependents: {', '.join(str(d) for d in deps[:5])}"
            return "No dependents found"
        return ""

    # -- Stage 1: Topic Selection --

    def select_topics(
        self,
        findings: List[Dict[str, Any]],
        llm_fn: LLMFn,
        max_topics: int = 3,
    ) -> List[ResearchTopic]:
        """Select high-impact topics from audit findings using LLM.

        Args:
            findings: Raw audit findings (dicts with id, title, description,
                priority, affected_files).
            llm_fn: Injectable LLM function.
            max_topics: Maximum number of topics to select.

        Returns:
            List of ResearchTopic instances.

        Raises:
            ValueError: If LLM returns unparseable response.
        """
        if not findings:
            return []

        atlas = self._load_atlas()
        prompt = render_topic_selection_prompt(
            findings=findings[:20],  # Cap to avoid token explosion
            max_topics=max_topics,
            atlas_excerpt=atlas[:2000] if atlas else "",
        )

        response, _ = llm_fn(prompt, system=TOPIC_SELECTION_SYSTEM, json_mode=True)

        try:
            selected = json.loads(response)
            if not isinstance(selected, list):
                selected = [selected]
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                f"Failed to parse topic selection response: {exc}"
            ) from exc

        # Map selected IDs back to finding data
        findings_by_id = {f.get("id", ""): f for f in findings}
        topics: List[ResearchTopic] = []
        for sel in selected[:max_topics]:
            fid = sel.get("finding_id", "")
            finding = findings_by_id.get(fid)
            if finding is None:
                continue
            topics.append(ResearchTopic(
                finding_id=fid,
                title=finding.get("title", ""),
                description=finding.get("description", ""),
                affected_files=list(finding.get("affected_files", [])),
                priority=finding.get("priority", "P2"),
                impact_summary=sel.get("rationale", ""),
            ))

        return topics

    # -- Stage 2: Research Synthesis --

    def research_topic(
        self,
        topic: ResearchTopic,
        llm_fn: LLMFn,
    ) -> str:
        """Research a single topic and return the LLM's analysis.

        Args:
            topic: The topic to research.
            llm_fn: Injectable LLM function.

        Returns:
            Raw research output string from the LLM.
        """
        # Gather context from Prep
        code_context = self._search_code(topic.title)
        impact_summary = ""
        if topic.affected_files:
            impact_summary = self._get_impact(topic.affected_files[0])

        prompt = render_research_prompt(
            topic_title=topic.title,
            topic_description=topic.description,
            affected_files=topic.affected_files,
            code_context=code_context,
            impact_summary=impact_summary or topic.impact_summary,
        )

        response, _ = llm_fn(prompt, system=RESEARCH_SYSTEM)
        return response

    # -- Stage 3: Plan Formulation --

    def formulate_plan(
        self,
        topic: ResearchTopic,
        research_output: str,
        llm_fn: LLMFn,
    ) -> ResearchPlan:
        """Convert research output into a structured ResearchPlan.

        Args:
            topic: The topic that was researched.
            research_output: Raw LLM research analysis.
            llm_fn: Injectable LLM function.

        Returns:
            ResearchPlan instance.

        Raises:
            ValueError: If LLM returns unparseable response.
        """
        prompt = render_plan_formulation_prompt(
            topic_title=topic.title,
            research_output=research_output,
            affected_files=topic.affected_files,
        )

        response, _ = llm_fn(prompt, system=PLAN_FORMULATION_SYSTEM, json_mode=True)

        try:
            plan_data = json.loads(response)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                f"Failed to parse plan formulation response: {exc}"
            ) from exc

        return ResearchPlan(
            topic_id=topic.finding_id,
            title=topic.title,
            root_cause=plan_data.get("root_cause", ""),
            fix_steps=list(plan_data.get("fix_steps", [])),
            effort=plan_data.get("effort", "medium"),
            risk=plan_data.get("risk", "low"),
            testing_strategy=plan_data.get("testing_strategy", ""),
        )

    # -- Full Pipeline --

    def run(
        self,
        findings: List[Dict[str, Any]],
        llm_fn: LLMFn,
        max_topics: int = 3,
    ) -> List[ResearchPlan]:
        """Execute the full research pipeline: select → research → formulate.

        Args:
            findings: Raw audit findings.
            llm_fn: Injectable LLM function.
            max_topics: Maximum topics to research.

        Returns:
            List of ResearchPlan instances.
        """
        # Stage 1: Select topics
        topics = self.select_topics(findings, llm_fn, max_topics=max_topics)
        if not topics:
            return []

        # Stages 2 + 3: Research and formulate each topic
        plans: List[ResearchPlan] = []
        for topic in topics:
            research_output = self.research_topic(topic, llm_fn)
            plan = self.formulate_plan(topic, research_output, llm_fn)
            plans.append(plan)

        # Save to history
        self._history.save_run(topics=topics, plans=plans)

        return plans

    # -- History Access --

    @property
    def history(self) -> ResearchHistory:
        """Access the underlying research history."""
        return self._history
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_researcher_engine.py -v`
Expected: All 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/prep/agents/researcher/engine.py tests/test_researcher_engine.py
git commit -m "feat(researcher): add ResearcherEngine with topic selection"
```

---

### Task 4: Research synthesis and plan formulation tests

**Files:**
- Modify: `tests/test_researcher_engine.py`

- [ ] **Step 1: Add tests for research and plan formulation stages**

Append to `tests/test_researcher_engine.py`:

```python
class TestResearchSynthesis:
    def test_research_topic_returns_string(
        self, engine: ResearcherEngine
    ) -> None:
        topic = ResearchTopic(
            finding_id="f1", title="Circular dependency",
            description="core <-> api cycle",
            affected_files=["src/core/main.py"],
        )
        result = engine.research_topic(topic, llm_fn=_fake_llm)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_research_includes_analysis(
        self, engine: ResearcherEngine
    ) -> None:
        topic = ResearchTopic(
            finding_id="f1", title="Circular dependency",
            description="core <-> api cycle",
            affected_files=["src/core/main.py"],
        )
        result = engine.research_topic(topic, llm_fn=_fake_llm)
        assert "Root Cause" in result or "Solution" in result


class TestPlanFormulation:
    def test_formulate_returns_research_plan(
        self, engine: ResearcherEngine
    ) -> None:
        topic = ResearchTopic(
            finding_id="f1", title="Fix circular deps",
            description="core <-> api cycle",
        )
        plan = engine.formulate_plan(
            topic=topic,
            research_output="Extract shared module to break cycle",
            llm_fn=_fake_llm,
        )
        assert isinstance(plan, ResearchPlan)
        assert plan.topic_id == "f1"
        assert plan.title == "Fix circular deps"

    def test_plan_has_fix_steps(
        self, engine: ResearcherEngine
    ) -> None:
        topic = ResearchTopic(
            finding_id="f1", title="Fix it",
            description="desc",
        )
        plan = engine.formulate_plan(
            topic=topic,
            research_output="Do this thing",
            llm_fn=_fake_llm,
        )
        assert len(plan.fix_steps) > 0

    def test_plan_has_effort_and_risk(
        self, engine: ResearcherEngine
    ) -> None:
        topic = ResearchTopic(finding_id="f1", title="T", description="D")
        plan = engine.formulate_plan(
            topic=topic,
            research_output="Research output",
            llm_fn=_fake_llm,
        )
        assert plan.effort in ("small", "medium", "large")
        assert plan.risk in ("low", "medium", "high")

    def test_formulate_raises_on_bad_json(
        self, engine: ResearcherEngine
    ) -> None:
        def bad_llm(prompt: str, **kw) -> Tuple[str, int]:
            return "not json", 10
        topic = ResearchTopic(finding_id="f1", title="T", description="D")
        with pytest.raises(ValueError, match="plan formulation"):
            engine.formulate_plan(topic=topic, research_output="R", llm_fn=bad_llm)
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/test_researcher_engine.py -v`
Expected: All 11 tests PASS (5 existing + 6 new)

- [ ] **Step 3: Commit**

```bash
git add tests/test_researcher_engine.py
git commit -m "test(researcher): add research synthesis and plan formulation tests"
```

---

### Task 5: Full pipeline run + history integration

**Files:**
- Modify: `tests/test_researcher_engine.py`

- [ ] **Step 1: Add tests for full pipeline and history**

Append to `tests/test_researcher_engine.py`:

```python
class TestFullPipeline:
    def test_run_produces_plans(
        self, engine: ResearcherEngine
    ) -> None:
        plans = engine.run(
            findings=_sample_findings(),
            llm_fn=_fake_llm,
            max_topics=2,
        )
        assert len(plans) == 2
        assert all(isinstance(p, ResearchPlan) for p in plans)

    def test_run_saves_to_history(
        self, engine: ResearcherEngine
    ) -> None:
        engine.run(
            findings=_sample_findings(),
            llm_fn=_fake_llm,
            max_topics=2,
        )
        latest = engine.history.get_latest()
        assert latest is not None
        assert len(latest["plans"]) == 2

    def test_run_with_empty_findings(
        self, engine: ResearcherEngine
    ) -> None:
        plans = engine.run(findings=[], llm_fn=_fake_llm)
        assert plans == []

    def test_multiple_runs_accumulate_history(
        self, engine: ResearcherEngine
    ) -> None:
        engine.run(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=1)
        engine.run(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=1)
        assert len(engine.history.list_runs()) == 2
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/test_researcher_engine.py -v`
Expected: All 15 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_researcher_engine.py
git commit -m "test(researcher): add full pipeline and history integration tests"
```

---

### Task 6: Push packaging

**Files:**
- Modify: `src/prep/agents/researcher/engine.py`
- Modify: `tests/test_researcher_engine.py`

- [ ] **Step 1: Add tests for push packaging**

Append to `tests/test_researcher_engine.py`:

```python
from prep.adapters.pm_models import PMProject, PMGoal, PMIssue


class TestPushPackaging:
    def test_package_plans_returns_pm_models(
        self, engine: ResearcherEngine
    ) -> None:
        plans = engine.run(
            findings=_sample_findings(),
            llm_fn=_fake_llm,
            max_topics=2,
        )
        project, goals, issues = engine.package_for_push(plans)
        assert isinstance(project, PMProject)
        assert len(issues) >= 1

    def test_project_has_research_title(
        self, engine: ResearcherEngine
    ) -> None:
        plans = [ResearchPlan(
            topic_id="f1", title="Fix circular deps",
            root_cause="Cycle", fix_steps=["Step 1"],
            effort="medium", risk="low",
        )]
        project, _, _ = engine.package_for_push(plans)
        assert "Research" in project.name

    def test_issues_have_plan_details(
        self, engine: ResearcherEngine
    ) -> None:
        plans = [ResearchPlan(
            topic_id="f1", title="Fix it",
            root_cause="Bad design",
            fix_steps=["Step A", "Step B"],
            effort="large", risk="high",
            testing_strategy="Integration tests",
        )]
        _, _, issues = engine.package_for_push(plans)
        assert len(issues) == 1
        assert "Fix it" in issues[0].title
        assert "Bad design" in issues[0].description

    def test_empty_plans_returns_empty(
        self, engine: ResearcherEngine
    ) -> None:
        project, goals, issues = engine.package_for_push([])
        assert project.name  # still has a project name
        assert issues == []
```

- [ ] **Step 2: Implement package_for_push method**

Add to `ResearcherEngine` class in `engine.py`, before the `history` property. Also add import at the top:

```python
# Add to imports at top of engine.py:
from prep.adapters.pm_models import PMGoal, PMIssue, PMProject

# Add method to ResearcherEngine:

    def package_for_push(
        self,
        plans: List[ResearchPlan],
    ) -> Tuple[PMProject, List[PMGoal], List[PMIssue]]:
        """Convert research plans into Paperclip-ready PM models.

        Args:
            plans: Research plans to package.

        Returns:
            Tuple of (PMProject, goals, issues).
        """
        project = PMProject(
            name=f"Research Findings — {self._project_id}",
            description=(
                f"Auto-generated research plans from {len(plans)} topics. "
                f"Each issue contains root cause analysis, fix steps, "
                f"effort/risk estimates, and testing strategy."
            ),
        )

        goals: List[PMGoal] = []
        issues: List[PMIssue] = []

        for plan in plans:
            description_parts = [
                f"**Root Cause:** {plan.root_cause}",
                "",
                "**Fix Steps:**",
            ]
            for i, step in enumerate(plan.fix_steps, 1):
                description_parts.append(f"{i}. {step}")
            description_parts.extend([
                "",
                f"**Effort:** {plan.effort}",
                f"**Risk:** {plan.risk}",
            ])
            if plan.testing_strategy:
                description_parts.append(f"**Testing:** {plan.testing_strategy}")

            issue = PMIssue(
                title=f"Research: {plan.title}",
                description="\n".join(description_parts),
                priority=self._finding_priority(plan),
                category="research",
                effort=plan.effort,
                prep_address=f"prep://{self._project_id}/research/{plan.topic_id}",
            )
            issues.append(issue)

        return project, goals, issues

    @staticmethod
    def _finding_priority(plan: ResearchPlan) -> str:
        """Map effort/risk to a PM priority."""
        if plan.risk == "high":
            return "P1"
        if plan.effort == "large":
            return "P1"
        if plan.effort == "small":
            return "P3"
        return "P2"
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_researcher_engine.py -v`
Expected: All 19 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/prep/agents/researcher/engine.py tests/test_researcher_engine.py
git commit -m "feat(researcher): add push packaging for Paperclip integration"
```

---

### Task 7: Public API exports + update __init__.py

**Files:**
- Modify: `src/prep/agents/researcher/__init__.py`

- [ ] **Step 1: Update init with re-exports**

```python
# src/prep/agents/researcher/__init__.py
"""Researcher Agent Engine — mines audit findings, researches solutions, formulates plans."""

from prep.agents.researcher.engine import ResearcherEngine
from prep.agents.researcher.history import ResearchHistory

__all__ = [
    "ResearcherEngine",
    "ResearchHistory",
]
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/pytest tests/test_agent_*.py tests/test_hr_*.py tests/test_researcher_*.py -q`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/prep/agents/researcher/__init__.py
git commit -m "feat(researcher): export public API from researcher subpackage"
```

---

### Task 8: Integration test + strategy doc update

**Files:**
- Create: `tests/test_researcher_integration.py`
- Modify: `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`

- [ ] **Step 1: Create integration test**

```python
# tests/test_researcher_integration.py
"""Integration tests for the full Researcher Agent pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from prep.agents.researcher import ResearcherEngine, ResearchHistory
from prep.agents.shared.models import ResearchPlan


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "Select the top" in prompt or "select" in prompt.lower()[:50]:
        return json.dumps([
            {"finding_id": "f1", "rationale": "Critical arch issue"},
            {"finding_id": "f2", "rationale": "Security risk"},
        ]), 60
    if "Research a solution" in prompt:
        return "## Analysis\nRoot cause is bad coupling.\n## Fix\nExtract module.", 100
    if "Convert this research" in prompt:
        return json.dumps({
            "root_cause": "Bad coupling between modules",
            "fix_steps": ["Extract shared types", "Update imports", "Add tests"],
            "effort": "medium",
            "risk": "low",
            "testing_strategy": "Run full test suite after refactor",
        }), 80
    return "ok", 10


@pytest.fixture
def rich_index(tmp_path: Path) -> Path:
    modules = [
        {"name": "core", "member_files": [f"core/{i}.py" for i in range(20)],
         "domain_tags": ["backend", "database"], "architecture_layer": "core",
         "summary": "Core logic"},
        {"name": "api", "member_files": [f"api/{i}.py" for i in range(15)],
         "domain_tags": ["api", "rest"], "architecture_layer": "api",
         "summary": "REST API"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    (tmp_path / "codebase_atlas.md").write_text(
        "# Atlas\nFull-stack Python app.\n" + "x" * 200
    )
    return tmp_path


def _findings():
    return [
        {"id": "f1", "title": "Circular dependency", "priority": "P0",
         "description": "core <-> api", "severity": "high",
         "affected_files": ["core/main.py"], "category": "architecture"},
        {"id": "f2", "title": "Hardcoded secret", "priority": "P1",
         "description": "API key in source", "severity": "high",
         "affected_files": ["config.py"], "category": "security"},
        {"id": "f3", "title": "Dead code", "priority": "P3",
         "description": "Unused utils", "severity": "low",
         "affected_files": ["utils.py"], "category": "maintenance"},
    ]


class TestResearcherEndToEnd:
    def test_full_pipeline(self, rich_index: Path) -> None:
        engine = ResearcherEngine(index_dir=rich_index, project_id="integ_test")

        # Run full pipeline
        plans = engine.run(findings=_findings(), llm_fn=_fake_llm, max_topics=2)

        # Verify plans
        assert len(plans) == 2
        for plan in plans:
            assert isinstance(plan, ResearchPlan)
            assert plan.root_cause
            assert len(plan.fix_steps) > 0
            assert plan.effort in ("small", "medium", "large")

        # Verify history
        latest = engine.history.get_latest()
        assert latest is not None
        assert len(latest["plans"]) == 2

        # Verify push packaging
        project, _, issues = engine.package_for_push(plans)
        assert "Research" in project.name
        assert len(issues) == 2

    def test_history_survives_restart(self, rich_index: Path) -> None:
        e1 = ResearcherEngine(index_dir=rich_index, project_id="test")
        e1.run(findings=_findings(), llm_fn=_fake_llm, max_topics=1)

        e2 = ResearcherEngine(index_dir=rich_index, project_id="test")
        assert len(e2.history.list_runs()) == 1

    def test_stage_by_stage_execution(self, rich_index: Path) -> None:
        """Verify each stage can be called independently."""
        engine = ResearcherEngine(index_dir=rich_index, project_id="test")

        # Stage 1
        topics = engine.select_topics(_findings(), _fake_llm, max_topics=1)
        assert len(topics) == 1

        # Stage 2
        research = engine.research_topic(topics[0], _fake_llm)
        assert len(research) > 0

        # Stage 3
        plan = engine.formulate_plan(topics[0], research, _fake_llm)
        assert plan.topic_id == topics[0].finding_id
```

- [ ] **Step 2: Run integration tests + full suite**

Run: `.venv/bin/pytest tests/test_researcher_integration.py -v`
Expected: All 3 tests PASS

Run: `.venv/bin/pytest tests/test_agent_*.py tests/test_hr_*.py tests/test_researcher_*.py -q`
Expected: All tests PASS

- [ ] **Step 3: Update IMPLEMENTATION_STRATEGY.md — mark Phase 2 tasks complete**

Mark tasks 2.1–2.6 as ☑. Leave 2.7 (Paperclip adapter), 2.8 (Pi Agent wiring), 2.9 (observation categories) as ☐ — those depend on later phases.

- [ ] **Step 4: Commit**

```bash
git add tests/test_researcher_integration.py docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md
git commit -m "feat(researcher): complete Phase 2 — Researcher Agent Engine with topic selection, research, plan formulation, push packaging"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Subpackage + prompt templates | 6 |
| 2 | Research history persistence | 6 |
| 3 | ResearcherEngine + topic selection | 5 |
| 4 | Research synthesis + plan formulation tests | 6 |
| 5 | Full pipeline + history tests | 4 |
| 6 | Push packaging | 4 |
| 7 | Public API exports | 0 (run existing) |
| 8 | Integration test + strategy update | 3 |
| **Total** | | **~34 tests** |
