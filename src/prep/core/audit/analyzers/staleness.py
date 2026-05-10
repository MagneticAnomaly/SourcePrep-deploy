"""Staleness analyzer — finds enrichments that are out of date."""
from __future__ import annotations

from pathlib import Path
from typing import List

from ..models import AuditContext, Finding
from . import BaseAnalyzer

# Phase 133: hash via the same primitive that compute_trace_coverage and
# TraceBuilder write. Comparing Python SHA-256 against BLAKE3-128 manifest
# hashes (post-cutover) would falsely flag every file stale on every
# audit run.
try:
    import prep_engine
except ImportError:
    prep_engine = None  # type: ignore[assignment]


class StalenessAnalyzer(BaseAnalyzer):
    name = "staleness"
    category = "quality"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        if not ctx.file_hashes or not ctx.project_root or prep_engine is None:
            return findings

        stale_files: List[str] = []

        # Phase 133 hot-fix: is_hash_stale graces hash-format mismatches
        # (SHA-256-64 vs BLAKE3-128) so the Phase 133 cutover does not
        # spam-flag every file as stale enrichment on every audit run.
        # Phase 134 deletes this analyzer's hash logic — the changeset
        # tells us what's stale.
        from prep.core.ids import is_hash_stale

        for rel_path, stored_hash in ctx.file_hashes.items():
            aug = None
            node_id = f"file:{rel_path}"
            if node_id in ctx.augmentations:
                aug_hash = ctx.augmentations[node_id].get("file_hash", "")
                if is_hash_stale(aug_hash, stored_hash):
                    stale_files.append(rel_path)
                    continue

            # Also check if file on disk differs from manifest hash
            abs_path = ctx.project_root / rel_path
            if not abs_path.exists():
                continue
            try:
                source = abs_path.read_text(encoding="utf-8", errors="ignore")
                current_hash = prep_engine.hash_content(source)
            except Exception:
                continue

            if is_hash_stale(stored_hash, current_hash):
                stale_files.append(rel_path)

        if not stale_files:
            return findings

        severity = "warning" if len(stale_files) > 10 else "info"

        findings.append(Finding(
            analyzer=self.name,
            severity=severity,
            category=self.category,
            title=f"{len(stale_files)} files have stale enrichments",
            description=(
                f"{len(stale_files)} files have been modified since their last "
                f"enrichment. Their augmentation summaries, epistemic data, and "
                f"module assignments may be outdated.\n"
                f"Top stale files: {', '.join(stale_files[:10])}"
            ),
            file_paths=stale_files[:20],
            evidence={
                "stale_count": len(stale_files),
                "total_hashed": len(ctx.file_hashes),
                "stale_pct": round(100 * len(stale_files) / max(len(ctx.file_hashes), 1), 1),
            },
            suggested_action="Run the enrichment pipeline to refresh stale nodes.",
        ))

        return findings
