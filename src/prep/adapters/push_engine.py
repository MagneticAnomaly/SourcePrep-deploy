"""
PushEngine — Orchestrates consolidation and PM push (Phase 65).

The full pipeline: ActionItems → Consolidate → Map to PM hierarchy → Push.

Usage:
    from prep.adapters.push_engine import PushEngine
    from prep.adapters.paperclip_adapter import PaperclipAdapter
    from prep.core.audit.consolidator import Consolidator

    adapter = PaperclipAdapter(url, company_id, api_key)
    engine = PushEngine(adapter, Consolidator())
    result = engine.push(items, project_id="pid")
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from prep.adapters.pm_adapter import PMAdapter
from prep.adapters.pm_models import PMGoal, PMIssue, PMProject, PMPushConfig, PushResult
from prep.core.audit.action_item import ActionItem
from prep.core.audit.consolidator import CATEGORY_LABELS, ConsolidatedGroup, Consolidator

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
        snapshot_store: Optional[Any] = None,
    ) -> None:
        self.adapter = adapter
        self.consolidator = consolidator or Consolidator()
        self._conflict_detector = conflict_detector
        self._conflict_store = conflict_store
        self._snapshot_store = snapshot_store

    def push(
        self,
        items: List[ActionItem],
        prep_project_id: str = "",
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
            prep_project_id: Prep project ID for address generation.
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
                from prep.services.observation_store import observation_store
                attributed = observation_store.get_all_attributed(
                    prep_project_id, limit=200,
                )
                if attributed:
                    conflicts = self._conflict_detector.detect_from_observations(
                        prep_project_id, attributed,
                    )
                    for c in conflicts:
                        self._conflict_store.save(c)
                    result.conflicts = conflicts

                    # Step 2c: Push conflicts to Paperclip as issues
                    for c in conflicts:
                        self._push_conflict_to_pm(c, prep_project_id)
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
        goal_title = "Prep: Codebase Health"
        goal_desc = (
            f"Automated codebase intelligence from Prep.\n"
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
                    prep_project_id=prep_project_id,
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
        prep_project_id: str,
        goal_id: str,
        project_root: str,
        result: PushResult,
    ) -> None:
        """Push a single consolidated group to the PM tool."""
        # Ensure a PM project exists for the group's category
        project_name = f"Prep: {group.label}"
        project_desc = (
            f"Automated findings from Prep codebase intelligence.\n"
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

        # Build the Prep address
        if len(group.items) == 1:
            single = group.items[0]
            prep_address = (
                f"prep://{prep_project_id}/{single.id}"
                if prep_project_id
                else f"prep://{single.id}"
            )
            mcp_command = single.mcp_command()
        else:
            # For consolidated groups, list all IDs
            ids = group.prep_item_ids
            prep_address = (
                f"prep://{prep_project_id}/group:{group.key}"
                if prep_project_id
                else f"prep://group:{group.key}"
            )
            # MCP command that fetches all items in the group
            id_list = ", ".join(f'"{i}"' for i in ids[:10])
            mcp_command = f'prep_audit action="refactor" finding_ids=[{id_list}]'

        # Build PMIssue
        pm_issue = PMIssue(
            title=group.title,
            description=group.description,
            priority=group.priority,
            category=group.category,
            effort=group.effort,
            prep_address=prep_address,
            mcp_command=mcp_command,
            affected_files=group.affected_files[:20],  # Cap file list
            sub_items=group.sub_items,
            project_id=project_id,
            goal_id=goal_id,
            item_count=len(group.items),
            prep_item_ids=group.prep_item_ids,
        )

        # Structural enrichment (Phase 73.5 Emergence)
        structural_ctx = self._enrich_with_structural_context(
            affected_files=group.affected_files[:20],
            project_id=prep_project_id,
        )
        if structural_ctx:
            pm_issue.structural_context = structural_ctx
            pm_issue.description += (
                f"\n\n---\n### Structural Context (Prep)\n"
                f"- **Complexity:** {structural_ctx.complexity_tier}\n"
            )
            if structural_ctx.hub_files_involved:
                hub_list = ", ".join(structural_ctx.hub_files_involved[:5])
                pm_issue.description += (
                    f"- **Hub files:** {hub_list}\n"
                    f"- **Blast radius:** {structural_ctx.total_dependents} total dependents\n"
                )
            if structural_ctx.cross_module:
                mod_list = ", ".join(structural_ctx.modules_spanned[:5])
                pm_issue.description += f"- **Modules spanned:** {mod_list}\n"

        # Consensus enrichment
        if prep_project_id:
            try:
                from prep.services.observation_store import observation_store
                consensus = observation_store.get_consensus_scores(
                    prep_project_id, min_agents=2, since_days=30,
                )
                affected_set = set(group.affected_files)
                matching = [
                    c for c in consensus
                    if c["file_path"] in affected_set
                ]
                if matching:
                    best = max(matching, key=lambda c: c["consensus_score"])
                    agents_str = ", ".join(best["agents"])
                    pm_issue.description += (
                        f"\n**Consensus:** {best['agent_count']}/{best['total_active_agents']} "
                        f"agents independently flagged files in this area "
                        f"({agents_str})\n"
                    )
            except Exception:
                pass  # Consensus is best-effort

        # Check for existing issue (dedup)
        existing_id = self.adapter.find_issue_by_prep_address(prep_address)
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

    # ── Conflict Push ───────────────────────────────────────────

    def _push_conflict_to_pm(self, conflict: Any, project_id: str) -> None:
        """Push a detected conflict to Paperclip as a tagged issue."""
        address = f"prep://{project_id}/CONFLICT-{conflict.id}"
        # Dedup: check if this conflict is already pushed
        existing = self.adapter.find_issue_by_prep_address(address)
        if existing:
            return

        title = (
            f"Prep Conflict: {conflict.file_path} "
            f"— {conflict.agent_a} vs {conflict.agent_b}"
        )
        desc = (
            f"Two agents disagree about this file:\n\n"
            f"**{conflict.agent_a}:** "
            f"\"{conflict.agent_a_assessment}\"\n\n"
            f"**{conflict.agent_b}:** "
            f"\"{conflict.agent_b_assessment}\"\n\n"
            f"**Type:** {conflict.conflict_type}\n\n"
            f"---\n"
            f"<!-- prep-address:{address} -->\n"
            f"<!-- prep-conflict:true -->"
        )
        try:
            issue = PMIssue(
                title=title,
                description=desc,
                priority="P2",
                category="conflict",
                prep_address=address,
            )
            self.adapter.create_issue(issue)
        except Exception:
            logger.debug(
                "Failed to push conflict %s to PM (non-fatal)",
                conflict.id, exc_info=True,
            )

    # ── Structural Enrichment ──────────────────────────────────

    def _enrich_with_structural_context(
        self,
        affected_files: List[str],
        project_id: str,
    ) -> Optional["StructuralContext"]:
        """Compute structural context for a set of affected files.

        Uses the latest graph snapshot to check hub involvement
        and module membership. Returns None if no snapshot available.
        """
        if not self._snapshot_store:
            return None

        from prep.adapters.pm_models import StructuralContext, compute_complexity_tier

        latest = self._snapshot_store.get_latest(project_id)
        if not latest:
            return None

        hub_paths = {h["path"]: h for h in latest.hubs}
        hub_files = [f for f in affected_files if f in hub_paths]
        total_deps = sum(
            hub_paths[f].get("dependents_count", 0) for f in hub_files
        )

        # Module detection from snapshot
        file_to_module: Dict[str, str] = {}
        for mod in latest.modules:
            for f in mod.get("files", []):
                file_to_module[f] = mod["name"]
        modules = list(set(
            file_to_module.get(f, "unknown") for f in affected_files
        ))

        ctx = StructuralContext(
            hub_files_involved=hub_files,
            hub_count=len(hub_files),
            total_dependents=total_deps,
            modules_spanned=modules,
            cross_module=len(modules) > 1,
        )
        ctx.complexity_tier = compute_complexity_tier(ctx)
        return ctx

    def push_significant_delta(
        self,
        delta: Any,
        project_id: str,
    ) -> int:
        """Push significant structural changes to Paperclip as issues.

        Only pushes new/removed hubs and modules. Rank changes and
        size changes are informational only.
        Returns the number of issues created.
        """
        from prep.adapters.pm_models import PMIssue

        significant = []
        for h in delta.hub_changes:
            if h.get("change") in ("new", "removed"):
                significant.append({**h, "type": "hub"})
        for m in delta.module_changes:
            if m.get("change") in ("new", "removed"):
                significant.append({**m, "type": "module"})

        if not significant:
            return 0

        created = 0
        for change in significant:
            change_type = change["type"]
            change_action = change["change"]

            if change_type == "hub":
                path = change.get("path", "unknown")
                address = f"prep://{project_id}/DELTA-hub-{hash(path) & 0xFFFFFFFF:08x}"
                if change_action == "new":
                    deps = change.get("dependents_count", 0)
                    rank = change.get("rank", "?")
                    title = f"Structural Change: {path} is a new hub ({deps} dependents)"
                    desc = (
                        f"A new hub file was detected after pipeline rebuild.\n\n"
                        f"**File:** {path}\n"
                        f"**Dependents:** {deps}\n"
                        f"**Rank:** #{rank}\n\n"
                        f"Hub files are central dependencies — many other files import from them. "
                        f"Changes to hub files have high blast radius.\n\n"
                        f"---\n"
                        f"<!-- prep-address:{address} -->\n"
                        f"<!-- prep-delta:true -->"
                    )
                else:
                    title = f"Structural Change: {path} is no longer a hub"
                    desc = (
                        f"A hub file was removed from the hub list after pipeline rebuild.\n\n"
                        f"**File:** {path}\n\n"
                        f"This file no longer has enough dependents to be a hub.\n\n"
                        f"---\n"
                        f"<!-- prep-address:{address} -->\n"
                        f"<!-- prep-delta:true -->"
                    )
            else:
                name = change.get("name", "unknown")
                address = f"prep://{project_id}/DELTA-module-{hash(name) & 0xFFFFFFFF:08x}"
                if change_action == "new":
                    file_count = change.get("file_count", 0)
                    title = f"Structural Change: new module '{name}' ({file_count} files)"
                    desc = (
                        f"A new module was detected after pipeline rebuild.\n\n"
                        f"**Module:** {name}\n"
                        f"**Files:** {file_count}\n\n"
                        f"---\n"
                        f"<!-- prep-address:{address} -->\n"
                        f"<!-- prep-delta:true -->"
                    )
                else:
                    title = f"Structural Change: module '{name}' removed"
                    desc = (
                        f"A module was removed after pipeline rebuild.\n\n"
                        f"**Module:** {name}\n\n"
                        f"---\n"
                        f"<!-- prep-address:{address} -->\n"
                        f"<!-- prep-delta:true -->"
                    )

            existing = self.adapter.find_issue_by_prep_address(address)
            if existing:
                continue

            try:
                issue = PMIssue(
                    title=title,
                    description=desc,
                    priority="P3",
                    category="architecture",
                    prep_address=address,
                )
                self.adapter.create_issue(issue)
                created += 1
            except Exception:
                logger.debug("Failed to push delta issue (non-fatal)", exc_info=True)

        return created

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
        from prep.adapters.paperclip_adapter import PaperclipAdapter
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
