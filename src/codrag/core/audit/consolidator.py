"""
Consolidator — The anti-clutter layer for PM push (Phase 65).

Merges 50-200+ raw ActionItems into 5-15 meaningful consolidated
groups before pushing to any PM tool. This is the most important
piece of the push pipeline — without it, PM boards drown in noise.

Three consolidation strategies:

1. **category** (default) — Groups by ActionItem.category:
   "Architecture Health: 12 findings", "Tech Debt: 35 items", etc.

2. **root_file** — Groups by shared affected_files. If 5 findings
   all touch auth/login.py, they become 1 group with 5 sub-items.

3. **severity_band** — P0+P1 stay individual. P2+P3 get rolled into
   a single "Backlog" per category.

Usage:
    from codrag.core.audit.consolidator import Consolidator
    groups = Consolidator().consolidate(items, strategy="category")
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from codrag.core.audit.action_item import ActionItem

logger = logging.getLogger(__name__)

# ── Priority ordering ────────────────────────────────────────────────

_PRIO_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# ── Category labels for PM-friendly titles ───────────────────────────

CATEGORY_LABELS: Dict[str, str] = {
    "architecture": "Architecture Health",
    "security": "Security Remediation",
    "tech_debt": "Tech Debt Cleanup",
    "quality": "Code Quality",
    "naming": "Code Quality",           # Merged with quality
    "feature": "Feature Development",
    "testing": "Test Coverage",
    "coverage": "Test Coverage",         # Merged with testing
    "size": "File Size Issues",
    "research": "Research Items",
}


# ── Consolidated Group ───────────────────────────────────────────────

class ConsolidatedGroup:
    """A group of related ActionItems merged into one pushable unit.

    This is NOT an ActionItem — it's a higher-level construct that the
    PushEngine maps to a PMIssue before pushing to the target PM tool.
    """

    def __init__(
        self,
        key: str,
        label: str,
        category: str,
        items: Optional[List[ActionItem]] = None,
    ) -> None:
        self.key = key                   # Grouping key (e.g., "architecture")
        self.label = label               # PM-friendly label (e.g., "Architecture Health")
        self.category = category
        self.items: List[ActionItem] = items or []

    @property
    def title(self) -> str:
        """PM-friendly title including item count."""
        count = len(self.items)
        if count == 1:
            return self.items[0].title
        return f"{self.label}: {count} findings"

    @property
    def priority(self) -> str:
        """Highest priority in the group (P0 wins)."""
        if not self.items:
            return "P3"
        return min(self.items, key=lambda i: _PRIO_ORDER.get(i.priority, 9)).priority

    @property
    def effort(self) -> str:
        """Aggregate effort estimate."""
        efforts = [i.effort for i in self.items]
        if "large" in efforts:
            return "large"
        if "medium" in efforts:
            return "medium"
        return "small"

    @property
    def affected_files(self) -> List[str]:
        """Union of all affected files (deduped, sorted)."""
        seen: set = set()
        files: List[str] = []
        for item in self.items:
            for f in item.affected_files:
                if f not in seen:
                    seen.add(f)
                    files.append(f)
        return sorted(files)

    @property
    def codrag_item_ids(self) -> List[str]:
        """All original ActionItem IDs."""
        return [item.id for item in self.items]

    @property
    def description(self) -> str:
        """Build a rich description summarizing all items in the group."""
        if len(self.items) == 1:
            item = self.items[0]
            return item.description or item.suggested_action

        lines: List[str] = []
        lines.append(f"CoDRAG discovered **{len(self.items)} findings** in this area.")
        lines.append("")

        # Group by severity for the summary
        by_sev: Dict[str, int] = defaultdict(int)
        for item in self.items:
            by_sev[item.severity] += 1
        sev_parts = []
        for sev in ("critical", "warning", "info", "suggestion"):
            count = by_sev.get(sev, 0)
            if count:
                emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵", "suggestion": "⚪"}.get(sev, "")
                sev_parts.append(f"{emoji} {count} {sev}")
        if sev_parts:
            lines.append(" | ".join(sev_parts))
            lines.append("")

        # List individual items as sub-tasks
        lines.append("### Findings")
        for i, item in enumerate(self.items[:25], 1):  # Cap at 25 in description
            prio_badge = f"[{item.priority}]"
            lines.append(f"{i}. {prio_badge} **{item.title}**")
            if item.suggested_action:
                lines.append(f"   _{item.suggested_action}_")
        if len(self.items) > 25:
            lines.append(f"\n_...and {len(self.items) - 25} more items_")

        return "\n".join(lines)

    @property
    def sub_items(self) -> List[str]:
        """Flat list of sub-item descriptions for PM checklist."""
        return [
            f"[{item.priority}] {item.title}"
            for item in self.items
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for dry-run preview."""
        return {
            "key": self.key,
            "label": self.label,
            "title": self.title,
            "category": self.category,
            "priority": self.priority,
            "effort": self.effort,
            "item_count": len(self.items),
            "affected_files_count": len(self.affected_files),
            "codrag_item_ids": self.codrag_item_ids,
        }


# ── Consolidator ─────────────────────────────────────────────────────

class Consolidator:
    """Merges ActionItems into ConsolidatedGroups for PM push.

    The goal is reducing 50-200 raw items into 5-15 meaningful groups
    that don't overwhelm a PM board.
    """

    def consolidate(
        self,
        items: List[ActionItem],
        *,
        strategy: str = "category",
    ) -> List[ConsolidatedGroup]:
        """Consolidate ActionItems using the specified strategy.

        Args:
            items: Raw ActionItems to consolidate.
            strategy: One of "category", "root_file", "severity_band".

        Returns:
            List of ConsolidatedGroup, sorted by priority.
        """
        if not items:
            return []

        if strategy == "root_file":
            groups = self._by_root_file(items)
        elif strategy == "severity_band":
            groups = self._by_severity_band(items)
        else:
            groups = self._by_category(items)

        # Sort by priority (P0 first)
        groups.sort(key=lambda g: _PRIO_ORDER.get(g.priority, 9))

        logger.info(
            "Consolidated %d items into %d groups (strategy=%s)",
            len(items), len(groups), strategy,
        )
        return groups

    # ── Strategy: By Category ────────────────────────────────────

    def _by_category(self, items: List[ActionItem]) -> List[ConsolidatedGroup]:
        """Group items by their category field.

        Produces ~6-10 groups (one per distinct category).
        Naming and quality are merged into a single "Code Quality" group.
        Testing and coverage are merged into "Test Coverage".
        """
        buckets: Dict[str, List[ActionItem]] = defaultdict(list)

        for item in items:
            # Merge related categories
            label = CATEGORY_LABELS.get(item.category, item.category.replace("_", " ").title())
            buckets[label].append(item)

        groups: List[ConsolidatedGroup] = []
        for label, bucket_items in buckets.items():
            # Use the most common category in the bucket as the key
            cat_counts: Dict[str, int] = defaultdict(int)
            for bi in bucket_items:
                cat_counts[bi.category] += 1
            primary_cat = max(cat_counts, key=cat_counts.get)  # type: ignore[arg-type]

            groups.append(ConsolidatedGroup(
                key=primary_cat,
                label=label,
                category=primary_cat,
                items=bucket_items,
            ))

        return groups

    # ── Strategy: By Root File ───────────────────────────────────

    def _by_root_file(self, items: List[ActionItem]) -> List[ConsolidatedGroup]:
        """Group items that share the same primary affected file.

        Items with no affected files go into a "General" group.
        If a file is shared by 3+ items, those items get grouped together.
        Remaining items fall back to category grouping.
        """
        # Build file → items index
        file_items: Dict[str, List[ActionItem]] = defaultdict(list)
        no_file_items: List[ActionItem] = []

        for item in items:
            if item.affected_files:
                # Use the first (primary) file as the grouping key
                primary = item.affected_files[0]
                file_items[primary].append(item)
            else:
                no_file_items.append(item)

        groups: List[ConsolidatedGroup] = []
        ungrouped: List[ActionItem] = []

        for file_path, file_group in file_items.items():
            if len(file_group) >= 2:
                # Enough items to justify a file-based group
                short_name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
                groups.append(ConsolidatedGroup(
                    key=file_path,
                    label=f"Improve: {short_name}",
                    category=file_group[0].category,
                    items=file_group,
                ))
            else:
                ungrouped.extend(file_group)

        # Ungrouped + no-file items fall back to category grouping
        fallback_items = ungrouped + no_file_items
        if fallback_items:
            fallback_groups = self._by_category(fallback_items)
            groups.extend(fallback_groups)

        return groups

    # ── Strategy: By Severity Band ───────────────────────────────

    def _by_severity_band(self, items: List[ActionItem]) -> List[ConsolidatedGroup]:
        """P0+P1 stay individual issues. P2+P3 get rolled into category groups.

        This produces the smallest number of PM issues — critical items
        get their own ticket while the rest is batched.
        """
        individual: List[ActionItem] = []
        batch: List[ActionItem] = []

        for item in items:
            if item.priority in ("P0", "P1"):
                individual.append(item)
            else:
                batch.append(item)

        groups: List[ConsolidatedGroup] = []

        # Each P0/P1 item becomes its own group (1:1)
        for item in individual:
            label = CATEGORY_LABELS.get(item.category, item.category.replace("_", " ").title())
            groups.append(ConsolidatedGroup(
                key=item.id,
                label=label,
                category=item.category,
                items=[item],
            ))

        # P2+P3 items get merged by category
        if batch:
            batch_groups = self._by_category(batch)
            # Prefix batch group labels to distinguish from individual items
            for bg in batch_groups:
                bg.label = f"{bg.label} (Backlog)"
            groups.extend(batch_groups)

        return groups
