"""
Goalposts planner engine for CoDRAG (Phase 57).

Reads the Atlas, audit findings, and user product intent to generate
forward-looking goalpost proposals and design questions via an LLM call.

Architecture: Independent background job (like DeepAnalysisOrchestrator).
Prompt size: ~7K chars (Atlas ~4K + audit summary ~2K + intent ~500).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prep.core.goalposts_models import (
    GoalpostProposal,
    GoalpostQuestion,
    GoalpostTask,
    GoalpostsState,
    load_goalposts,
    save_goalposts,
)

logger = logging.getLogger(__name__)


# ── LLM prompt templates ─────────────────────────────────────────────

# P-1: North Star context + P-2: CoT scaffolding
GOALPOSTS_SYSTEM = """\
You are a Staff Engineer and product strategist analyzing a codebase.
Your job is to propose actionable milestones ("goalposts") that drive
the project toward its NORTH STAR goal.

You must think through THREE LENSES before proposing:
1. 🏗️ Architecture: structural health, decomposition, performance
2. 🎯 Product/UX: user experience, feature gaps, API surface
3. 🛡️ Risk: security, market positioning, research needs

For EACH proposal you must:
  a) Ground it in specific files/components from the Atlas
  b) Explain how it moves toward the North Star
  c) Assess business impact (revenue, user retention, reliability)
  d) Rate ethos alignment (how well it fits the product vision)

Be concrete — "add rate limiting to the API layer" not "improve security".
Produce valid JSON only. No markdown, no commentary outside the JSON."""

# P-3: Three-lens coverage + P-4: business_impact + P-5: ethos_alignment
GOALPOSTS_PROMPT = """\
# Codebase Identity (Atlas)

{atlas_content}

# Technical Debt & Gaps

{tech_debt_summary}

# Product Ethos (Vision & Values)

{product_intent}

# North Star Goal

{north_star_context}

# Sprint Velocity History

{velocity_context}

# Previously Approved Goalposts (do not re-propose)

{approved_summary}

# User Answers to Previous Questions

{answered_questions}

---

STEP 1 — THINK (internal reasoning, included in JSON as "_reasoning"):
- Which of the three lenses (architecture, product, risk) has the biggest gap?
- What would move the North Star goal forward most efficiently?
- What does the velocity history suggest about capacity?

STEP 2 — PROPOSE:

Produce a JSON object with:

1. "_reasoning": string (2-3 sentences: your chain of thought from Step 1)

2. "proposals": Array of 3–7 goalpost proposals, each with:
   - "title": string (concise milestone name)
   - "rationale": string (1-2 sentences: why this matters NOW)
   - "category": one of "architecture", "security", "feature", "tech_debt", "research", "product", "market"
   - "priority": one of "P0", "P1", "P2", "P3"
   - "business_impact": string (1 sentence: revenue/reliability/user impact)
   - "ethos_alignment": string (1 sentence: how this fits the product vision)
   - "tasks": array of 1-4 sub-tasks, each with:
     - "description": string
     - "file_paths": array of relevant file paths from the Atlas
     - "effort": one of "small", "medium", "large"

3. "questions": Array of 0-3 design questions where you need user input:
   - "question": string (the question)
   - "context": string (why you're asking — what ambiguity you detected)
   - "category": one of "architecture", "security", "feature", "tech_debt", "research", "product", "market"

CONSTRAINTS:
- Proposals MUST span at least 2 of the 3 lenses (architecture, product/UX, risk/security)
- At least one proposal should directly advance the North Star
- Order by priority (P0 first)
- Every proposal must include business_impact and ethos_alignment

Respond with ONLY the JSON object."""


# ── Main planner class ───────────────────────────────────────────────

class GoalpostsPlanner:
    """Generates goalpost proposals by analyzing existing codebase epistemology.

    This is a consumer of the existing pipeline output, NOT a pipeline stage.
    It reads Atlas, audit findings, and user intent, then makes a single LLM
    call to produce structured proposals.

    Usage:
        planner = GoalpostsPlanner(index_dir, llm_client)
        state = planner.generate(product_intent="Build a SaaS analytics dashboard")
    """

    def __init__(
        self,
        index_dir: Path,
        llm_client: Any,
        *,
        project_root: Optional[Path] = None,
    ):
        self.index_dir = Path(index_dir)
        self.llm = llm_client
        self.project_root = project_root

    def generate(
        self,
        product_intent: str = "",
        *,
        max_proposals: int = 7,
    ) -> GoalpostsState:
        """Run the goalposts planning pass.

        Loads existing state (to preserve approvals/dismissals), reads
        Atlas + audit data, calls the LLM, and merges new proposals into
        the existing state.

        Args:
            product_intent: User's description of their product direction.
            max_proposals: Maximum proposals to generate.

        Returns:
            Updated GoalpostsState with new proposals merged in.
        """
        t0 = time.monotonic()

        # Load existing state to preserve user decisions
        state = load_goalposts(self.index_dir)
        if product_intent:
            state.product_intent = product_intent
        elif not state.product_intent:
            state.product_intent = "(No product intent provided — analyze the codebase and suggest improvements based on what you see.)"

        # Gather context
        atlas_content = self._load_atlas()
        tech_debt = self._load_tech_debt_summary()
        approved = self._format_approved(state)
        answered = self._format_answered_questions(state)
        north_star_ctx = self._load_north_star_context()
        velocity_ctx = self._load_velocity_context()

        if not atlas_content:
            logger.warning("No Atlas found — generating goalposts without codebase identity")
            atlas_content = "(Atlas not yet generated. Analyze available audit data only.)"

        # Build prompt
        prompt = GOALPOSTS_PROMPT.format(
            atlas_content=atlas_content[:6000],  # Cap at ~6K chars
            tech_debt_summary=tech_debt[:3000],  # Cap at ~3K chars
            product_intent=state.product_intent[:1000],
            north_star_context=north_star_ctx or "(No North Star set — propose the most impactful direction.)",
            velocity_context=velocity_ctx or "(No velocity data yet.)",
            approved_summary=approved or "(none)",
            answered_questions=answered or "(none)",
        )

        # Compute optimal LLM settings
        from prep.core.context_config import PipelineTask, compute_optimal_settings
        prompt_tokens = len(prompt) // 4  # rough estimate
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUDIT,  # Similar output size to audit
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        from prep.core.llm_client import TASK_MAX_CHARS

        # Call LLM
        logger.info(
            "Generating goalposts: prompt=%d chars, intent=%d chars, atlas=%d chars",
            len(prompt), len(state.product_intent), len(atlas_content),
        )

        try:
            text, tokens = self.llm.generate(
                prompt=prompt,
                system=GOALPOSTS_SYSTEM,
                json_mode=True,
                temperature=0.4,  # Slightly creative for diverse proposals
                num_predict=num_predict,
                max_chars=TASK_MAX_CHARS.get("audit", 15_000),
                num_ctx=num_ctx,
            )
        except Exception as e:
            logger.error("Goalposts LLM call failed: %s", e)
            raise

        duration_ms = (time.monotonic() - t0) * 1000

        # Parse response
        new_proposals, new_questions = self._parse_response(text, max_proposals)

        # Merge into existing state: keep approved/dismissed, replace stale proposed
        state.proposals = [
            p for p in state.proposals
            if p.state in ('approved', 'dismissed')
        ]
        state.proposals.extend(new_proposals)
        state.questions.extend(new_questions)
        state.last_generated_at = datetime.now(timezone.utc).isoformat()
        state.model_used = self.llm.model
        state.generation_tokens = tokens
        state.generation_duration_ms = duration_ms

        # Persist
        save_goalposts(state, self.index_dir)

        logger.info(
            "Goalposts generated: %d proposals, %d questions in %.1fs (%d tokens)",
            len(new_proposals), len(new_questions),
            duration_ms / 1000, tokens,
        )

        return state

    # ── Data loading ─────────────────────────────────────────────────

    def _load_atlas(self) -> str:
        """Load the Atlas identity document content."""
        atlas_path = self.index_dir / "atlas.json"
        if not atlas_path.exists():
            return ""
        try:
            with open(atlas_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("content", "")
        except Exception as e:
            logger.warning("Failed to load atlas: %s", e)
            return ""

    def _load_tech_debt_summary(self) -> str:
        """Load audit findings and format as a tech debt summary."""
        findings_path = self.index_dir / "audit" / "findings.json"
        if not findings_path.exists():
            return "(No audit data available yet.)"

        try:
            with open(findings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return "(Failed to load audit findings.)"

        findings = data.get("findings", [])
        if not findings:
            return "(Audit ran but found no issues — codebase is clean.)"

        # Summarize findings by severity
        lines: List[str] = []
        severity_counts: Dict[str, int] = {}
        for f in findings:
            sev = f.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        lines.append(f"Total findings: {len(findings)}")
        for sev in ("critical", "warning", "info", "suggestion"):
            count = severity_counts.get(sev, 0)
            if count:
                lines.append(f"  {sev.title()}: {count}")
        lines.append("")

        # Include top findings (critical + warning first)
        priority_findings = sorted(
            findings,
            key=lambda f: {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}.get(
                f.get("severity", "info"), 4
            ),
        )

        for f in priority_findings[:15]:
            title = f.get("title", "")
            desc = f.get("description", "")[:150]
            files = ", ".join(f.get("file_paths", [])[:3])
            action = f.get("suggested_action", "")
            lines.append(f"[{f.get('severity', 'info').upper()}] {title}")
            if files:
                lines.append(f"  Files: {files}")
            lines.append(f"  {desc}")
            if action:
                lines.append(f"  Action: {action}")
            lines.append("")

        if len(findings) > 15:
            lines.append(f"... and {len(findings) - 15} more findings")

        return "\n".join(lines)

    def _format_approved(self, state: GoalpostsState) -> str:
        """Format previously approved proposals so the LLM doesn't re-propose them."""
        approved = state.approved_proposals
        if not approved:
            return ""
        lines = []
        for p in approved:
            lines.append(f"- [{p.category}] {p.title}")
        return "\n".join(lines)

    def _format_answered_questions(self, state: GoalpostsState) -> str:
        """Format user-answered questions to inform the next planning pass."""
        answered = [q for q in state.questions if q.answered]
        if not answered:
            return ""
        lines = []
        for q in answered:
            lines.append(f"Q: {q.question}")
            lines.append(f"A: {q.answer}")
            lines.append("")
        return "\n".join(lines)

    def _load_north_star_context(self) -> str:
        """Load North Star from roadmap state for P-1 prompt context."""
        try:
            from prep.core.goalposts_models import load_roadmap
            roadmap = load_roadmap(self.index_dir)
            ns = roadmap.north_star
            if ns:
                return (
                    f"Current North Star: {ns.title} ({ns.priority})\n"
                    f"Ethos: {roadmap.app_ethos[:500]}" if roadmap.app_ethos else
                    f"Current North Star: {ns.title} ({ns.priority})"
                )
        except Exception as e:
            logger.debug("Could not load North Star: %s", e)
        return ""

    def _load_velocity_context(self) -> str:
        """Load sprint velocity data for context-aware capacity suggestions."""
        try:
            from prep.core.goalposts_models import load_roadmap
            from prep.core.sprint_intelligence import VelocityTracker
            roadmap = load_roadmap(self.index_dir)
            tracker = VelocityTracker(roadmap)
            avg = tracker.average_velocity(window_days=14, num_windows=4)
            snapshots = tracker.calculate_velocity(window_days=14, num_windows=3)

            lines = [f"Average velocity: {avg:.1f} items per 2-week sprint"]
            for s in snapshots:
                lines.append(
                    f"  {s.window.label}: {s.completed_count} completed, "
                    f"{s.added_count} added"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Could not load velocity data: %s", e)
        return ""

    # ── Response parsing ─────────────────────────────────────────────

    def _parse_response(
        self, text: str, max_proposals: int
    ) -> Tuple[List[GoalpostProposal], List[GoalpostQuestion]]:
        """Parse the LLM JSON response into model objects."""
        from prep.core.llm_client import _parse_json_response

        data = _parse_json_response(text)
        if not data:
            logger.warning("Failed to parse goalposts response as JSON")
            return [], []

        proposals: List[GoalpostProposal] = []
        for raw in data.get("proposals", [])[:max_proposals]:
            try:
                tasks = []
                for rt in raw.get("tasks", []):
                    tasks.append(GoalpostTask(
                        description=rt.get("description", ""),
                        file_paths=rt.get("file_paths", []),
                        effort=rt.get("effort", "small"),
                    ))

                # P-4/P-5: Capture business_impact and ethos_alignment
                # Append to rationale for GoalpostProposal (legacy model)
                # The roadmap router will extract these into RoadmapNode fields
                rationale = raw.get("rationale", "")
                business_impact = raw.get("business_impact", "")
                ethos_alignment = raw.get("ethos_alignment", "")

                # Store P-4/P-5 data as tagged appendix in rationale
                if business_impact:
                    rationale += f" [IMPACT: {business_impact}]"
                if ethos_alignment:
                    rationale += f" [ETHOS: {ethos_alignment}]"

                proposal = GoalpostProposal(
                    title=raw.get("title", "Untitled"),
                    rationale=rationale,
                    category=raw.get("category", "feature"),
                    priority=raw.get("priority", "P2"),
                    tasks=tasks,
                )
                # Stash raw P-4/P-5 for downstream extraction
                proposal._business_impact = business_impact  # type: ignore
                proposal._ethos_alignment = ethos_alignment  # type: ignore
                proposals.append(proposal)
            except Exception as e:
                logger.warning("Failed to parse proposal: %s", e)
                continue

        questions: List[GoalpostQuestion] = []
        for raw in data.get("questions", [])[:3]:
            try:
                q = GoalpostQuestion(
                    question=raw.get("question", ""),
                    context=raw.get("context", ""),
                    category=raw.get("category", "feature"),
                )
                if q.question:
                    questions.append(q)
            except Exception as e:
                logger.warning("Failed to parse question: %s", e)
                continue

        return proposals, questions


# ── Availability check ───────────────────────────────────────────────

def can_generate_goalposts(index_dir: Path) -> Dict[str, Any]:
    """Check whether goalposts can be generated for a project.

    Returns:
        {
            "ready": bool,
            "has_atlas": bool,
            "has_audit": bool,
            "has_intent": bool,
            "missing": [str],   # what's missing
        }
    """
    index_dir = Path(index_dir)
    has_atlas = (index_dir / "atlas.json").exists()
    has_audit = (index_dir / "audit" / "findings.json").exists()

    state = load_goalposts(index_dir)
    has_intent = bool(state.product_intent.strip())

    missing = []
    if not has_atlas:
        missing.append("Atlas not generated (run deep enrichment first)")
    # Audit is optional — goalposts can work from Atlas alone

    return {
        "ready": has_atlas,  # Atlas is the minimum requirement
        "has_atlas": has_atlas,
        "has_audit": has_audit,
        "has_intent": has_intent,
        "missing": missing,
    }
