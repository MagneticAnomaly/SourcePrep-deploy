"""Phase 134 — Staleness analyzer rewrite.

Pre-Phase-134 this analyzer hashed every file and compared against
the manifest's file_hashes (per-stage staleness check, the bug class
Phase 134 deletes). Post-Phase-134 the analyzer consults the
changeset for two narrow, well-scoped checks:

1. Orphan check: files in changeset.deleted that still have
   augmentation entries on disk. These are leftover state from
   files the user removed; the augmentation pipeline should clean
   them up.
2. Coverage-gap check: files in changeset.added | modified that
   the augmenter didn't process by run end. These indicate the
   augmenter silently failed for some inputs.
"""
from __future__ import annotations

from typing import List

from ..models import AuditContext, Finding
from . import BaseAnalyzer


class StalenessAnalyzer(BaseAnalyzer):
    name = "staleness"
    category = "quality"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []
        if ctx.changeset is None:
            return findings

        # Check 1: orphan augmentations (deleted files with lingering entries)
        deleted_paths = ctx.changeset.deleted
        orphan_node_ids: List[str] = []
        for node_id in ctx.augmentations.keys():
            file_path = node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
            if file_path and file_path in deleted_paths:
                orphan_node_ids.append(node_id)

        if orphan_node_ids:
            severity = "warning" if len(orphan_node_ids) > 10 else "info"
            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"{len(orphan_node_ids)} orphan augmentations (deleted files)",
                description=(
                    f"{len(orphan_node_ids)} augmentation entries reference "
                    f"files that were deleted in this run. Cleanup pass "
                    f"should remove them.\n"
                    f"Top orphans: {', '.join(orphan_node_ids[:10])}"
                ),
                file_paths=[
                    node_id.replace("file:", "", 1) for node_id in orphan_node_ids[:20]
                ],
                evidence={"orphan_count": len(orphan_node_ids)},
                suggested_action="Run augmentation cleanup to remove orphan entries.",
            ))

        # Check 2: coverage gap (added/modified files not present in augmentations)
        expected_processed = ctx.changeset.added | ctx.changeset.modified
        actually_processed = {
            node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
            for node_id in ctx.augmentations.keys()
        }
        gap = expected_processed - actually_processed
        if gap:
            severity = "warning" if len(gap) > 5 else "info"
            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"{len(gap)} files added/modified but not augmented",
                description=(
                    f"{len(gap)} files are in this run's changeset (added "
                    f"or modified) but no augmentation entry exists for "
                    f"them. The augmenter may have silently failed.\n"
                    f"Top missing: {', '.join(sorted(gap)[:10])}"
                ),
                file_paths=sorted(gap)[:20],
                evidence={"gap_count": len(gap)},
                suggested_action="Re-run augmentation for the affected files.",
            ))

        return findings
