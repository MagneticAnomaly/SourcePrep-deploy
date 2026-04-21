"""
Sprint intelligence for CoDRAG Roadmap — Phase 59D-4.

Tracks velocity (nodes completed per time period) and provides
AI-powered sprint planning suggestions based on historical throughput.

Features:
  - Velocity calculation from completed node timestamps
  - Sprint capacity estimation
  - AI sprint suggestion generation (which nodes fit the next sprint)
  - Burndown data for visualization
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prep.core.goalposts_models import (
    PRIORITY_RANK,
    RoadmapNode,
    RoadmapState,
    load_roadmap,
)

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────

@dataclass
class SprintWindow:
    """A time window for sprint measurement."""
    start: datetime
    end: datetime
    label: str = ""  # e.g. "Sprint 23", "Week of Mar 17"

    @property
    def duration_days(self) -> float:
        return (self.end - self.start).total_seconds() / 86400


@dataclass
class VelocitySnapshot:
    """Velocity metrics for a sprint window."""
    window: SprintWindow
    completed_count: int = 0
    completed_nodes: List[str] = field(default_factory=list)  # node IDs
    added_count: int = 0
    p0_completed: int = 0
    p1_completed: int = 0
    categories: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_start": self.window.start.isoformat(),
            "window_end": self.window.end.isoformat(),
            "window_label": self.window.label,
            "duration_days": round(self.window.duration_days, 1),
            "completed_count": self.completed_count,
            "completed_nodes": self.completed_nodes,
            "added_count": self.added_count,
            "p0_completed": self.p0_completed,
            "p1_completed": self.p1_completed,
            "categories": self.categories,
        }


@dataclass
class SprintSuggestion:
    """AI-generated sprint plan."""
    sprint_label: str
    capacity: int  # estimated nodes that can be completed
    suggested_nodes: List[str]  # node IDs, priority-ordered
    rationale: str
    confidence: float  # 0.0-1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sprint_label": self.sprint_label,
            "capacity": self.capacity,
            "suggested_nodes": self.suggested_nodes,
            "rationale": self.rationale,
            "confidence": round(self.confidence, 2),
        }


# ── Velocity Calculator ─────────────────────────────────────────────

class VelocityTracker:
    """Calculate sprint velocity from roadmap history."""

    def __init__(self, state: RoadmapState):
        self.state = state
        self._completed = [
            n for n in state.nodes
            if n.tier == "completed" and n.completed_at
        ]
        self._completed.sort(key=lambda n: n.completed_at or "")

    def calculate_velocity(
        self,
        *,
        window_days: int = 14,
        num_windows: int = 6,
    ) -> List[VelocitySnapshot]:
        """Calculate velocity over rolling windows.

        Args:
            window_days: Duration of each sprint window in days.
            num_windows: Number of historical windows to compute.

        Returns:
            List of VelocitySnapshots, most recent first.
        """
        now = datetime.now(timezone.utc)
        snapshots: List[VelocitySnapshot] = []

        for i in range(num_windows):
            end = now - timedelta(days=i * window_days)
            start = end - timedelta(days=window_days)

            window = SprintWindow(
                start=start,
                end=end,
                label=f"Sprint {num_windows - i}",
            )

            # Find nodes completed in this window
            completed_in_window = []
            categories: Dict[str, int] = {}
            p0 = p1 = 0

            for node in self._completed:
                try:
                    completed_at = datetime.fromisoformat(
                        node.completed_at.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    continue

                if start <= completed_at < end:
                    completed_in_window.append(node.id)
                    cat = node.category
                    categories[cat] = categories.get(cat, 0) + 1
                    if node.priority == "P0":
                        p0 += 1
                    elif node.priority == "P1":
                        p1 += 1

            # Count nodes created in this window
            added = 0
            for node in self.state.nodes:
                try:
                    created_at = datetime.fromisoformat(
                        node.created_at.replace("Z", "+00:00")
                    )
                    if start <= created_at < end:
                        added += 1
                except (ValueError, AttributeError):
                    continue

            snapshots.append(VelocitySnapshot(
                window=window,
                completed_count=len(completed_in_window),
                completed_nodes=completed_in_window,
                added_count=added,
                p0_completed=p0,
                p1_completed=p1,
                categories=categories,
            ))

        return snapshots

    def average_velocity(self, window_days: int = 14, num_windows: int = 4) -> float:
        """Calculate average velocity (nodes per sprint window)."""
        snapshots = self.calculate_velocity(
            window_days=window_days, num_windows=num_windows,
        )
        if not snapshots:
            return 0.0
        return sum(s.completed_count for s in snapshots) / len(snapshots)

    def burndown_data(self) -> List[Dict[str, Any]]:
        """Generate burndown data points (remaining vs time).

        Returns:
            List of {"date": ISO str, "remaining": int, "completed": int}
        """
        # Build a timeline of events (node created, node completed)
        events: List[Tuple[str, int]] = []  # (date, delta)

        for node in self.state.nodes:
            if node.created_at:
                events.append((node.created_at[:10], +1))
            if node.completed_at:
                events.append((node.completed_at[:10], -1))

        if not events:
            return []

        events.sort(key=lambda e: e[0])

        # Accumulate
        remaining = 0
        completed = 0
        data_points: List[Dict[str, Any]] = []
        current_date = ""

        for date, delta in events:
            if date != current_date:
                if current_date:
                    data_points.append({
                        "date": current_date,
                        "remaining": remaining,
                        "completed": completed,
                    })
                current_date = date

            if delta > 0:
                remaining += 1
            else:
                remaining -= 1
                completed += 1

        # Final point
        if current_date:
            data_points.append({
                "date": current_date,
                "remaining": remaining,
                "completed": completed,
            })

        return data_points


# ── Sprint Planner ───────────────────────────────────────────────────

class SprintPlanner:
    """Suggests sprint plans based on velocity and node priority."""

    def __init__(self, state: RoadmapState, velocity_tracker: VelocityTracker):
        self.state = state
        self.tracker = velocity_tracker

    def suggest_sprint(
        self,
        *,
        window_days: int = 14,
    ) -> SprintSuggestion:
        """Generate a sprint suggestion based on historical velocity.

        Uses heuristic scoring (not LLM) for speed:
          1. Calculate average velocity over last 4 sprints
          2. Score each eligible node by priority + age
          3. Fill sprint up to capacity

        Args:
            window_days: Sprint duration for capacity estimation.

        Returns:
            SprintSuggestion with prioritized node list.
        """
        avg_velocity = self.tracker.average_velocity(window_days=window_days)
        capacity = max(1, round(avg_velocity))

        # Eligible = planned + active nodes, not dismissed
        eligible = [
            n for n in self.state.nodes
            if n.tier in ("planned", "active")
            and n.state not in ("completed", "dismissed")
        ]

        # Score: priority rank (lower=better) + age bonus
        now = datetime.now(timezone.utc)

        def score_node(node: RoadmapNode) -> float:
            priority_score = PRIORITY_RANK.get(node.priority, 9) * 10
            # Older nodes get slight priority boost
            try:
                created = datetime.fromisoformat(
                    node.created_at.replace("Z", "+00:00")
                )
                age_days = (now - created).days
                age_bonus = min(age_days * 0.1, 5.0)  # Max 5 point bonus
            except (ValueError, AttributeError):
                age_bonus = 0
            # Active nodes get priority over planned
            tier_bonus = -5 if node.tier == "active" else 0
            return priority_score - age_bonus + tier_bonus

        eligible.sort(key=score_node)
        selected = [n.id for n in eligible[:capacity]]

        # Confidence based on velocity data availability
        snapshots = self.tracker.calculate_velocity(
            window_days=window_days, num_windows=4,
        )
        non_zero = sum(1 for s in snapshots if s.completed_count > 0)
        confidence = non_zero / max(len(snapshots), 1)

        rationale = self._build_rationale(
            avg_velocity, capacity, len(eligible), selected, confidence,
        )

        return SprintSuggestion(
            sprint_label=f"Sprint (next {window_days}d)",
            capacity=capacity,
            suggested_nodes=selected,
            rationale=rationale,
            confidence=confidence,
        )

    def _build_rationale(
        self,
        avg_velocity: float,
        capacity: int,
        eligible_count: int,
        selected: List[str],
        confidence: float,
    ) -> str:
        """Build a human-readable rationale for the sprint suggestion."""
        lines = [
            f"Based on average velocity of {avg_velocity:.1f} nodes/sprint.",
            f"Estimated capacity: {capacity} nodes.",
            f"Selected {len(selected)} from {eligible_count} eligible items.",
        ]
        if confidence < 0.5:
            lines.append(
                "⚠ Low confidence — limited completion history. "
                "Velocity will stabilize as more sprints complete."
            )
        return " ".join(lines)


# ── AI Sprint Planning (LLM-enhanced) ───────────────────────────────

SPRINT_SYSTEM = """\
You are a sprint planner analyzing a software project's roadmap.
Given the velocity history, current backlog, and product ethos,
suggest which items to include in the next sprint.

Consider:
1. Priority (P0 > P1 > P2 > P3)
2. Dependencies (items that unblock others)
3. Category balance (don't overload one area)
4. Team capacity based on historical velocity
5. North Star alignment

Respond with ONLY a JSON object."""

SPRINT_PROMPT = """\
# Product Ethos
{ethos}

# Velocity History (last 4 sprints)
{velocity_data}

# Current North Star
{north_star}

# Eligible Backlog Items (planned + active)
{backlog}

---

Suggest a sprint plan as JSON:
{{
  "sprint_label": "Sprint N",
  "capacity": <estimated items>,
  "suggested_nodes": [<list of node IDs in priority order>],
  "rationale": "<2-3 sentence explanation>",
  "confidence": <0.0-1.0>
}}"""


def generate_ai_sprint_plan(
    state: RoadmapState,
    llm_client: Any,
    *,
    window_days: int = 14,
) -> SprintSuggestion:
    """Generate an LLM-enhanced sprint plan.

    Falls back to heuristic-based plan if LLM fails.
    """
    tracker = VelocityTracker(state)
    planner = SprintPlanner(state, tracker)

    # Prepare context for LLM
    velocity_snapshots = tracker.calculate_velocity(
        window_days=window_days, num_windows=4,
    )
    velocity_data = json.dumps(
        [s.to_dict() for s in velocity_snapshots], indent=2
    )

    eligible = [
        n for n in state.nodes
        if n.tier in ("planned", "active")
        and n.state not in ("completed", "dismissed")
    ]
    backlog = json.dumps([
        {
            "id": n.id,
            "title": n.title,
            "priority": n.priority,
            "category": n.category,
            "tier": n.tier,
            "tasks": len(n.tasks),
        }
        for n in eligible
    ], indent=2)

    ns = state.north_star
    north_star = f"{ns.title} ({ns.priority})" if ns else "(none)"

    prompt = SPRINT_PROMPT.format(
        ethos=state.app_ethos or "(not set)",
        velocity_data=velocity_data[:3000],
        north_star=north_star,
        backlog=backlog[:4000],
    )

    try:
        text, _tokens = llm_client.generate(
            prompt=prompt,
            system=SPRINT_SYSTEM,
            json_mode=True,
            temperature=0.3,
            num_predict=1000,
            max_chars=5000,
        )

        from prep.core.llm_client import _parse_json_response
        data = _parse_json_response(text)

        if data:
            return SprintSuggestion(
                sprint_label=data.get("sprint_label", "Next Sprint"),
                capacity=data.get("capacity", 3),
                suggested_nodes=data.get("suggested_nodes", []),
                rationale=data.get("rationale", ""),
                confidence=data.get("confidence", 0.5),
            )
    except Exception as e:
        logger.warning("AI sprint planning failed, using heuristic: %s", e)

    # Fallback to heuristic
    return planner.suggest_sprint(window_days=window_days)
