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

from codrag.core.goalposts_models import (
    GoalpostProposal,
    GoalpostQuestion,
    GoalpostTask,
    GoalpostsState,
    load_goalposts,
    save_goalposts,
)

logger = logging.getLogger(__name__)


# ── LLM prompt templates ─────────────────────────────────────────────

GOALPOSTS_SYSTEM = """\
You are a Staff Engineer and product strategist analyzing a codebase.
Your job is to propose actionable milestones ("goalposts") based on:
1. What the codebase currently is (Atlas identity document).
2. What technical debt or gaps exist (audit findings).
3. Where the user wants to go (product intent).

Always ground proposals in specific files and components from the Atlas.
Be concrete — "add rate limiting to the API layer" not "improve security".
Produce valid JSON only. No markdown, no commentary outside the JSON."""

GOALPOSTS_PROMPT = """\
# Codebase Identity (Atlas)

{atlas_content}

# Technical Debt & Gaps

{tech_debt_summary}

# Product Intent

{product_intent}

# Previously Approved Goalposts (do not re-propose)

{approved_summary}

# User Answers to Previous Questions

{answered_questions}

---

Analyze this codebase and produce a JSON object with two arrays:

1. "proposals": Array of 3–7 goalpost proposals, each with:
   - "title": string (concise milestone name)
   - "rationale": string (1-2 sentences: why this matters NOW)
   - "category": one of "architecture", "security", "feature", "tech_debt", "research"
   - "priority": one of "P0", "P1", "P2", "P3"
   - "tasks": array of 1-4 sub-tasks, each with:
     - "description": string
     - "file_paths": array of relevant file paths from the Atlas
     - "effort": one of "small", "medium", "large"

2. "questions": Array of 0-3 design questions where you need user input:
   - "question": string (the question)
   - "context": string (why you're asking — what ambiguity you detected)
   - "category": one of "architecture", "security", "feature", "tech_debt", "research"

Order proposals by priority (P0 first). Only include questions when genuine ambiguity exists.

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

        if not atlas_content:
            logger.warning("No Atlas found — generating goalposts without codebase identity")
            atlas_content = "(Atlas not yet generated. Analyze available audit data only.)"

        # Build prompt
        prompt = GOALPOSTS_PROMPT.format(
            atlas_content=atlas_content[:6000],  # Cap at ~6K chars
            tech_debt_summary=tech_debt[:3000],  # Cap at ~3K chars
            product_intent=state.product_intent[:1000],
            approved_summary=approved or "(none)",
            answered_questions=answered or "(none)",
        )

        # Compute optimal LLM settings
        from codrag.core.context_config import PipelineTask, compute_optimal_settings
        prompt_tokens = len(prompt) // 4  # rough estimate
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUDIT,  # Similar output size to audit
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        from codrag.core.llm_client import TASK_MAX_CHARS

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

    # ── Response parsing ─────────────────────────────────────────────

    def _parse_response(
        self, text: str, max_proposals: int
    ) -> Tuple[List[GoalpostProposal], List[GoalpostQuestion]]:
        """Parse the LLM JSON response into model objects."""
        from codrag.core.llm_client import _parse_json_response

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

                proposal = GoalpostProposal(
                    title=raw.get("title", "Untitled"),
                    rationale=raw.get("rationale", ""),
                    category=raw.get("category", "feature"),
                    priority=raw.get("priority", "P2"),
                    tasks=tasks,
                )
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
