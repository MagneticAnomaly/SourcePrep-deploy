"""
PushEngine — Orchestrates consolidation and PM push (Phase 65).

The full pipeline: ActionItems → Consolidate → Map to PM hierarchy → Push.

Usage:
    from codrag.adapters.push_engine import PushEngine
    from codrag.adapters.paperclip_adapter import PaperclipAdapter
    from codrag.core.audit.consolidator import Consolidator

    adapter = PaperclipAdapter(url, company_id, api_key)
    engine = PushEngine(adapter, Consolidator())
    result = engine.push(items, project_id="pid")
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from codrag.adapters.pm_adapter import PMAdapter
from codrag.adapters.pm_models import PMGoal, PMIssue, PMProject, PMPushConfig, PushResult
from codrag.core.audit.action_item import ActionItem
from codrag.core.audit.consolidator import CATEGORY_LABELS, ConsolidatedGroup, Consolidator

logger = logging.getLogger(__name__)

# ── Priority filter ──────────────────────────────────────────────────

_PRIO_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


# ── PushEngine ───────────────────────────────────────────────────────

class PushEngine:
    """Orchestrates the full consolidation → push pipeline.

    1. Filter items by min_priority and excluded categories
    2. Consolidate using the configured strategy
    3. For each group: ensure PM project/goal, then create/update issue
    4. Return detailed PushResult
    """

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

    def push(
        self,
        items: List[ActionItem],
        codrag_project_id: str = "",
        *,
        strategy: str = "category",
        min_priority: str = "P2",
        exclude_categories: Optional[List[str]] = None,
        project_root: str = "",
        dry_run: bool = False,
    ) -> PushResult:
        """Full pipeline: filter → consolidate → push.

        Args:
            items: Raw ActionItems from OpportunityManager.
            codrag_project_id: CoDRAG project ID for address generation.
            strategy: Consolidation strategy ("category", "root_file", "severity_band").
            min_priority: Only push items at this priority or higher.
            exclude_categories: Categories to skip.
            project_root: Project root path (for PM workspace).
            dry_run: Preview without pushing.

        Returns:
            PushResult with detailed outcomes.
        """
        result = PushResult(total_action_items=len(items))
        excluded = set(exclude_categories or [])

        # ── Step 1: Filter ───────────────────────────────────────
        max_prio = _PRIO_ORDER.get(min_priority, 9)
        filtered = [
            item for item in items
            if item.state != "dismissed"
            and _PRIO_ORDER.get(item.priority, 9) <= max_prio
            and item.category not in excluded
        ]

        if not filtered:
            logger.info("No items to push after filtering (min_priority=%s)", min_priority)
            result.dry_run = dry_run
            return result

        # ── Step 2: Consolidate ──────────────────────────────────
        groups = self.consolidator.consolidate(filtered, strategy=strategy)
        result.consolidated_groups = len(groups)

        # ── Step 2b: Conflict detection (Phase 73.5) ────────────
        if self._conflict_detector and self._conflict_store:
            try:
                from codrag.services.observation_store import observation_store
                all_obs = observation_store.get_by_agent(
                    codrag_project_id, created_by="",
                    include_stale=False, limit=200,
                )
                attributed = [o for o in all_obs if o.created_by]
                if attributed:
                    conflicts = self._conflict_detector.detect_from_observations(
                        codrag_project_id, attributed,
                    )
                    for c in conflicts:
                        self._conflict_store.save(c)
                    result.conflicts = conflicts
            except Exception:
                logger.debug(
                    "Conflict detection failed (non-fatal)",
                    exc_info=True,
                )

        if dry_run:
            result.dry_run = True
            result.details = [g.to_dict() for g in groups]
            return result

        # ── Step 3: Ensure PM goal (one per push) ────────────────
        goal_title = "CoDRAG: Codebase Health"
        goal_desc = (
            f"Automated codebase intelligence from CoDRAG.\n"
            f"Last push: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Items: {len(filtered)} findings consolidated into {len(groups)} groups."
        )
        try:
            goal_id = self.adapter.ensure_goal(PMGoal(
                title=goal_title,
                description=goal_desc,
            ))
            result.goals_created += 1
        except RuntimeError as e:
            logger.warning("Could not ensure PM goal: %s", e)
            result.errors.append(f"Goal creation failed: {e}")
            goal_id = ""

        # ── Step 4: Push each group ──────────────────────────────
        for group in groups:
            try:
                self._push_group(
                    group,
                    codrag_project_id=codrag_project_id,
                    goal_id=goal_id,
                    project_root=project_root,
                    result=result,
                )
            except RuntimeError as e:
                error_msg = f"Failed to push group '{group.label}': {e}"
                logger.warning(error_msg)
                result.errors.append(error_msg)

        result.pushed = True
        logger.info(
            "Push complete: %d groups, %d issues created, %d updated, %d skipped, %d errors",
            result.consolidated_groups,
            result.issues_created,
            result.issues_updated,
            result.issues_skipped,
            len(result.errors),
        )
        return result

    def _push_group(
        self,
        group: ConsolidatedGroup,
        *,
        codrag_project_id: str,
        goal_id: str,
        project_root: str,
        result: PushResult,
    ) -> None:
        """Push a single consolidated group to the PM tool."""
        # Ensure a PM project exists for the group's category
        project_name = f"CoDRAG: {group.label}"
        project_desc = (
            f"Automated findings from CoDRAG codebase intelligence.\n"
            f"Category: {group.category}\n"
            f"Contains {len(group.items)} findings."
        )

        pm_project = PMProject(
            name=project_name,
            description=project_desc,
            workspace_path=project_root,
        )

        project_id = self.adapter.ensure_project(
            pm_project,
            goal_ids=[goal_id] if goal_id else None,
        )
        result.projects_created += 1

        # Build the CoDRAG address
        if len(group.items) == 1:
            single = group.items[0]
            codrag_address = (
                f"codrag://{codrag_project_id}/{single.id}"
                if codrag_project_id
                else f"codrag://{single.id}"
            )
            mcp_command = single.mcp_command()
        else:
            # For consolidated groups, list all IDs
            ids = group.codrag_item_ids
            codrag_address = (
                f"codrag://{codrag_project_id}/group:{group.key}"
                if codrag_project_id
                else f"codrag://group:{group.key}"
            )
            # MCP command that fetches all items in the group
            id_list = ", ".join(f'"{i}"' for i in ids[:10])
            mcp_command = f'codrag_audit action="refactor" finding_ids=[{id_list}]'

        # Build PMIssue
        pm_issue = PMIssue(
            title=group.title,
            description=group.description,
            priority=group.priority,
            category=group.category,
            effort=group.effort,
            codrag_address=codrag_address,
            mcp_command=mcp_command,
            affected_files=group.affected_files[:20],  # Cap file list
            sub_items=group.sub_items,
            project_id=project_id,
            goal_id=goal_id,
            item_count=len(group.items),
            codrag_item_ids=group.codrag_item_ids,
        )

        # Check for existing issue (dedup)
        existing_id = self.adapter.find_issue_by_codrag_address(codrag_address)
        if existing_id:
            # Update existing issue
            updated = self.adapter.update_issue(existing_id, {
                "description": self.adapter._build_description(pm_issue)  # type: ignore[attr-defined]
                if hasattr(self.adapter, "_build_description")
                else pm_issue.description,
            })
            if updated:
                result.issues_updated += 1
            else:
                result.issues_skipped += 1
            return

        # Create new issue
        self.adapter.create_issue(pm_issue)
        result.issues_created += 1

    # ── Push History ─────────────────────────────────────────────

    @staticmethod
    def record_push(
        index_dir: Any,
        result: PushResult,
        provider: str = "paperclip",
    ) -> None:
        """Record push result to disk for history tracking.

        Stored at: {index_dir}/audit/push_history.json
        """
        import json
        from pathlib import Path

        history_path = Path(index_dir) / "audit" / "push_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing history
        history: List[Dict[str, Any]] = []
        if history_path.exists():
            try:
                history = json.loads(history_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        # Append new entry
        entry = result.to_dict()
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        entry["provider"] = provider
        history.append(entry)

        # Keep last 100 entries
        history = history[-100:]

        history_path.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8",
        )


# ── Factory ──────────────────────────────────────────────────────────

def create_push_engine(config: PMPushConfig) -> PushEngine:
    """Create a PushEngine from configuration.

    Factory method that selects the right adapter based on provider.
    """
    if config.provider == "paperclip":
        from codrag.adapters.paperclip_adapter import PaperclipAdapter
        adapter = PaperclipAdapter(
            base_url=config.paperclip_url,
            company_id=config.paperclip_company_id,
            api_key=config.paperclip_api_key,
        )
    else:
        raise ValueError(
            f"Unsupported PM provider: {config.provider}. "
            f"Supported: paperclip"
        )

    return PushEngine(adapter, Consolidator())
