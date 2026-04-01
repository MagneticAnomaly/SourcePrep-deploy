"""
OpportunityManager — Unified opportunity aggregator for CoDRAG (Phase 63).

Aggregates ActionItems from all analysis sources (Health Scanner,
Spaghetti Scorer, Advisor, TODO Scanner) into a single queryable
stream with filtering, dismissal, and multi-format export.

This is the central orchestrator for all opportunity discovery.
It follows the hexagonal architecture: the manager owns the core
logic, and adapters (SARIF, JSON, CSV, MCP, A2A) handle serialization.

Storage: per-project JSON file at {index_dir}/audit/opportunities.json
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .action_item import ActionItem

logger = logging.getLogger(__name__)

# ── Priority / severity sort keys ───────────────────────────────────

_PRIO_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
_SEV_ORDER = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}


def _sort_key(item: ActionItem) -> Tuple[int, int]:
    return (
        _PRIO_ORDER.get(item.priority, 9),
        _SEV_ORDER.get(item.severity, 9),
    )


# ── OpportunityManager ──────────────────────────────────────────────

class OpportunityManager:
    """Aggregates, queries, and exports ActionItems from all analysis sources.

    Usage:
        mgr = OpportunityManager(index_dir)
        items = mgr.refresh(project_root=root)
        critical = mgr.get_opportunities(min_priority="P0")
        sarif = mgr.export("sarif")
    """

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = Path(index_dir)
        self._opportunities: List[ActionItem] = []
        self._dismissed_ids: Set[str] = set()
        self._last_refresh: Optional[str] = None
        self._storage_path = self.index_dir / "audit" / "opportunities.json"

        # Load existing state from disk
        self._load_state()

    # ── Refresh (aggregate from all sources) ────────────────────

    def refresh(
        self,
        project_root: Optional[Path] = None,
        categories: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        extra_exclude_globs: Optional[List[str]] = None,
    ) -> List[ActionItem]:
        """Run all scanners and merge results into the opportunity list.

        Sources (in execution order):
        1. Health Scanner — audit analyzers (11 built-in analyzers)
        2. Spaghetti Scorer — refactoring urgency scoring
        3. TODO Scanner — in-code TODOs and FIXMEs (future)

        Note: Advisor (LLM-generated) proposals are added separately
        via add_items() since they require async LLM calls.

        Deduplication: Hash-based on ActionItem.id to prevent duplicates.
        Dismiss state is preserved across refreshes.

        Args:
            project_root: Path to the project root.
            categories: Optional filter for audit categories.
            progress_callback: Optional (phase, current, total) reporter.
            extra_exclude_globs: Additional exclude globs from Exclude Tree.

        Returns:
            Merged, deduplicated, sorted list of all active ActionItems.
        """
        start = time.monotonic()
        new_items: List[ActionItem] = []

        # Source 1+2: Health Scanner (includes spaghetti)
        try:
            from .runner import run_health_scan
            health_items = run_health_scan(
                index_dir=self.index_dir,
                project_root=project_root,
                categories=categories,
                include_spaghetti=True,
                progress_callback=progress_callback,
                extra_exclude_globs=extra_exclude_globs,
            )
            new_items.extend(health_items)
            logger.info("Health scan produced %d items", len(health_items))
        except Exception as e:
            logger.warning("Health scanner failed during refresh: %s", e)

        # Source 3: TODO Scanner (future — stub for now)
        # todo_items = todo_scanner.scan(project_root)
        # new_items.extend(todo_items)

        # Merge with existing (preserve dismiss state, deduplicate)
        self._merge(new_items)

        # Record refresh time
        self._last_refresh = datetime.now(timezone.utc).isoformat()

        # Persist
        self._save_state()

        # Phase 63: Auto-update AGENTS.md for headless agent integration
        if project_root:
            try:
                from codrag.core.agents_writer import write_agents_md
                write_agents_md(project_root, self._opportunities)
            except Exception as e:
                logger.debug("AGENTS.md auto-write failed (non-fatal): %s", e)

        elapsed = (time.monotonic() - start) * 1000
        active_count = sum(1 for i in self._opportunities if i.state != "dismissed")
        logger.info(
            "Opportunity refresh complete: %d total, %d active, %d dismissed in %.1fms",
            len(self._opportunities), active_count,
            len(self._dismissed_ids), elapsed,
        )

        return self.get_opportunities()

    def add_items(self, items: List[ActionItem]) -> None:
        """Add externally-generated ActionItems (e.g., from Advisor LLM).

        Merges with existing opportunities, preserving dismiss state.
        """
        self._merge(items)
        self._save_state()

    # ── Query ───────────────────────────────────────────────────

    def get_opportunities(
        self,
        *,
        categories: Optional[List[str]] = None,
        min_priority: Optional[str] = None,
        sources: Optional[List[str]] = None,
        include_dismissed: bool = False,
    ) -> List[ActionItem]:
        """Query opportunities with filters.

        Args:
            categories: Filter by category (architecture, quality, etc.)
            min_priority: Minimum priority (P0 = highest). P2 returns P0, P1, P2.
            sources: Filter by source (health, spaghetti, advisor, todo_scanner).
            include_dismissed: Include dismissed items (default: False).

        Returns:
            Filtered, sorted list of ActionItems.
        """
        items = list(self._opportunities)

        # Filter dismissed
        if not include_dismissed:
            items = [i for i in items if i.state != "dismissed"]

        # Filter by category
        if categories:
            cat_set = set(categories)
            items = [i for i in items if i.category in cat_set]

        # Filter by minimum priority
        if min_priority:
            max_prio = _PRIO_ORDER.get(min_priority, 9)
            items = [i for i in items if _PRIO_ORDER.get(i.priority, 9) <= max_prio]

        # Filter by source
        if sources:
            src_set = set(sources)
            items = [i for i in items if i.source in src_set]

        # Sort
        items.sort(key=_sort_key)
        return items

    def get_summary(self) -> Dict[str, Any]:
        """Return aggregate stats for the opportunity list."""
        active = [i for i in self._opportunities if i.state != "dismissed"]
        by_priority: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        by_source: Dict[str, int] = {}
        by_analyzer: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}

        for item in active:
            by_priority[item.priority] = by_priority.get(item.priority, 0) + 1
            by_category[item.category] = by_category.get(item.category, 0) + 1
            by_source[item.source] = by_source.get(item.source, 0) + 1
            by_analyzer[item.analyzer] = by_analyzer.get(item.analyzer, 0) + 1
            by_severity[item.severity] = by_severity.get(item.severity, 0) + 1

        # Phase 65: Actionable = critical + warning only (not info/suggestion)
        actionable_count = by_severity.get("critical", 0) + by_severity.get("warning", 0)

        # Top 5 analyzer groups by count
        top_analyzers = sorted(by_analyzer.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total": len(active),
            "dismissed": len(self._dismissed_ids),
            "by_priority": by_priority,
            "by_category": by_category,
            "by_source": by_source,
            "by_analyzer": by_analyzer,
            "by_severity": by_severity,
            "top_analyzers": [{"analyzer": a, "count": c} for a, c in top_analyzers],
            "actionable_count": actionable_count,
            "critical": by_severity.get("critical", 0),
            "warning": by_severity.get("warning", 0),
            "info": by_severity.get("info", 0) + by_severity.get("suggestion", 0),
            "last_refresh": self._last_refresh,
        }

    # ── Actions ─────────────────────────────────────────────────

    def dismiss(self, item_id: str) -> bool:
        """Mark an opportunity as dismissed.

        Returns True if the item was found and dismissed.
        """
        for item in self._opportunities:
            if item.id == item_id:
                item.dismiss()
                self._dismissed_ids.add(item_id)
                self._save_state()
                logger.info("Dismissed opportunity: %s", item_id)
                return True
        logger.warning("Opportunity not found for dismiss: %s", item_id)
        return False

    def restore(self, item_id: str) -> bool:
        """Restore a dismissed opportunity.

        Returns True if the item was found and restored.
        """
        for item in self._opportunities:
            if item.id == item_id:
                item.restore()
                self._dismissed_ids.discard(item_id)
                self._save_state()
                logger.info("Restored opportunity: %s", item_id)
                return True
        return False

    # ── Export ──────────────────────────────────────────────────

    def export(
        self,
        format: str = "json",
        **filters: Any,
    ) -> str:
        """Export opportunities in the specified format.

        Args:
            format: One of "json", "sarif", "csv", "md", "ai_prompt".
            **filters: Passed to get_opportunities() for filtering.

        Returns:
            Serialized string in the requested format.
        """
        items = self.get_opportunities(**filters)

        if format == "json":
            return self._export_json(items)
        elif format == "sarif":
            return self._export_sarif(items)
        elif format == "csv":
            return self._export_csv(items)
        elif format == "md" or format == "markdown":
            return self._export_markdown(items)
        elif format == "ai_prompt":
            return self._export_ai_prompt(items)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_json(self, items: List[ActionItem]) -> str:
        """Export as clean JSON array."""
        return json.dumps(
            [item.to_export_json() for item in items],
            indent=2,
        )

    def _export_sarif(self, items: List[ActionItem]) -> str:
        """Export as SARIF 2.1.0 JSON."""
        from .sarif_exporter import sarif_to_json_string
        return sarif_to_json_string(items)

    def _export_csv(self, items: List[ActionItem]) -> str:
        """Export as CSV text."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(ActionItem.CSV_HEADER)
        for item in items:
            writer.writerow(item.to_csv_row())
        return output.getvalue()

    def _export_markdown(self, items: List[ActionItem]) -> str:
        """Export as Markdown summary."""
        summary = self.get_summary()
        lines = [
            "# CoDRAG Opportunities",
            "",
            f"**{summary['total']}** findings | "
            f"**{summary['critical']}** critical | "
            f"**{summary['warning']}** warnings | "
            f"**{summary['info']}** info",
            f"Last refreshed: {summary['last_refresh'] or 'never'}",
            "",
        ]

        # Group by priority
        current_prio = None
        for item in items:
            if item.priority != current_prio:
                current_prio = item.priority
                prio_labels = {
                    "P0": "🔴 Critical (P0)",
                    "P1": "🟡 Warning (P1)",
                    "P2": "🔵 Info (P2)",
                    "P3": "⚪ Suggestion (P3)",
                }
                lines.append(f"## {prio_labels.get(current_prio, current_prio)}")
                lines.append("")

            file_str = f" ({len(item.affected_files)} files)" if item.affected_files else ""
            lines.append(f"- **{item.id}**: {item.title}{file_str} [{item.effort}]")

        lines.append("")
        lines.append("---")
        lines.append("*Generated by CoDRAG codebase intelligence engine*")

        return "\n".join(lines)

    def _export_ai_prompt(self, items: List[ActionItem]) -> str:
        """Export as a single paste-ready AI prompt."""
        lines = [
            "# CoDRAG Codebase Opportunities",
            "",
            "The following opportunities were discovered by CoDRAG's "
            "codebase intelligence engine. Please review and address "
            "them in priority order.",
            "",
        ]
        for item in items:
            lines.append(item.to_ai_prompt())
            lines.append("")
            lines.append("---")
            lines.append("")
        return "\n".join(lines)

    # ── Persistence ─────────────────────────────────────────────

    def _merge(self, new_items: List[ActionItem]) -> None:
        """Merge new items with existing opportunities.

        Rules:
        - New items with unseen IDs are added as active
        - Existing items are updated (description, files, etc.)
        - Dismiss state is preserved (dismissed items stay dismissed)
        """
        existing_by_id = {item.id: item for item in self._opportunities}

        for new_item in new_items:
            if new_item.id in self._dismissed_ids:
                # Preserve dismiss state
                new_item.state = "dismissed"
                new_item.dismissed_at = (
                    existing_by_id[new_item.id].dismissed_at
                    if new_item.id in existing_by_id
                    else datetime.now(timezone.utc).isoformat()
                )
            existing_by_id[new_item.id] = new_item

        self._opportunities = sorted(existing_by_id.values(), key=_sort_key)

    def _save_state(self) -> None:
        """Persist opportunity state to disk."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "last_refresh": self._last_refresh,
            "dismissed_ids": sorted(self._dismissed_ids),
            "item_count": len(self._opportunities),
            "items": [item.to_dict() for item in self._opportunities],
        }

        _atomic_write_json(self._storage_path, data)

    def _load_state(self) -> None:
        """Load opportunity state from disk."""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._last_refresh = data.get("last_refresh")
            self._dismissed_ids = set(data.get("dismissed_ids", []))
            self._opportunities = [
                ActionItem.from_dict(d) for d in data.get("items", [])
            ]
            logger.debug(
                "Loaded %d opportunities (%d dismissed) from %s",
                len(self._opportunities), len(self._dismissed_ids),
                self._storage_path,
            )
        except Exception as e:
            logger.warning("Failed to load opportunity state: %s", e)
            self._opportunities = []
            self._dismissed_ids = set()


# ── Utility ─────────────────────────────────────────────────────────

def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically via temp file + rename."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=str(path.parent),
        delete=False, encoding="utf-8",
    )
    try:
        json.dump(data, tmp, indent=2, sort_keys=True)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.rename(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise
