# src/prep/agents/researcher/engine.py
"""Researcher Agent Engine — mines audit findings and formulates implementation plans.

Pipeline: ingest findings -> select topics -> research solutions -> formulate plans.
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
from prep.adapters.pm_models import PMGoal, PMIssue, PMProject
from prep.agents.shared.models import ResearchPlan, ResearchTopic

logger = logging.getLogger(__name__)

LLMFn = Callable[..., Tuple[str, int]]


class ResearcherEngine:
    """Mines Prep audit findings, researches solutions, formulates plans.

    Accepts either an AgentCore instance (preferred) or raw index_dir
    + project_id for lightweight / test usage.
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

        Raises ValueError if LLM returns unparseable response.
        """
        if not findings:
            return []

        atlas = self._load_atlas()
        prompt = render_topic_selection_prompt(
            findings=findings[:20],
            max_topics=max_topics,
            atlas_excerpt=atlas[:2000] if atlas else "",
        )

        response, _ = llm_fn(prompt, system=TOPIC_SELECTION_SYSTEM, json_mode=True)

        try:
            from prep.agents.shared.json_utils import extract_json
            selected = extract_json(response)
            if not isinstance(selected, list):
                selected = [selected]
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Failed to parse topic selection response: {exc}"
            ) from exc

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
        """Research a single topic and return the LLM's analysis."""
        # Phase 73.5: Claim affected files + log activity
        if self._core and self._core.collab:
            try:
                for fp in topic.affected_files[:5]:
                    self._core.collab.claims.claim(
                        self._project_id, "researcher", fp,
                        reason=f"Researching: {topic.title}",
                    )
                self._core.collab.activity.log(
                    self._project_id, "researcher",
                    "research_topic_start",
                    f"Researching: {topic.title}",
                )
            except Exception:
                pass
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

        Raises ValueError if LLM returns unparseable response.
        """
        prompt = render_plan_formulation_prompt(
            topic_title=topic.title,
            research_output=research_output,
            affected_files=topic.affected_files,
        )

        response, _ = llm_fn(prompt, system=PLAN_FORMULATION_SYSTEM, json_mode=True)

        try:
            from prep.agents.shared.json_utils import extract_json
            plan_data = extract_json(response)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
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
        """Execute the full research pipeline: select -> research -> formulate."""
        topics = self.select_topics(findings, llm_fn, max_topics=max_topics)
        if not topics:
            return []

        plans: List[ResearchPlan] = []
        for topic in topics:
            research_output = self.research_topic(topic, llm_fn)
            plan = self.formulate_plan(topic, research_output, llm_fn)
            plans.append(plan)

        self._history.save_run(topics=topics, plans=plans)
        return plans

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

    # -- History Access --

    @property
    def history(self) -> ResearchHistory:
        """Access the underlying research history."""
        return self._history
