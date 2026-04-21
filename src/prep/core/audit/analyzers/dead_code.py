"""Dead code analyzer — finds files/symbols with zero importers that aren't entry points."""
from __future__ import annotations

from typing import Dict, List, Set

from ..models import AuditContext, Finding
from . import BaseAnalyzer

# Roles that are expected to have zero importers (they're entry points, not libraries)
ENTRY_POINT_ROLES = frozenset({
    "entry_point", "script", "test", "config", "documentation",
})

# File name patterns that are expected to have zero importers
ENTRY_POINT_PATTERNS = (
    "__main__", "__init__", "conftest", "setup", "manage",
    "main", "cli", "app", "server", "wsgi", "asgi",
)


class DeadCodeAnalyzer(BaseAnalyzer):
    name = "dead_code"
    category = "quality"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        # Build set of all nodes that are import targets
        imported_files: Set[str] = set()
        for edge in ctx.edges:
            if edge.get("kind") == "imports":
                tgt = edge.get("target", "")
                if tgt:
                    imported_files.add(tgt)

        for nid, node in ctx.file_nodes.items():
            file_path = node.get("file_path", "")
            if not file_path:
                continue

            # Skip if this file is imported by anything
            if nid in imported_files:
                continue

            # Skip known entry points by role
            aug = ctx.augmentations.get(nid, {})
            role = aug.get("role", "")
            if role in ENTRY_POINT_ROLES:
                continue

            # Skip known entry points by filename pattern
            name = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
            if any(pat in name for pat in ENTRY_POINT_PATTERNS):
                continue

            # Skip test files
            if "/test" in file_path or "test_" in name or "_test" in name:
                continue

            # Skip markdown/docs
            lang = node.get("language", "")
            if lang in ("markdown",):
                continue

            # This file has no importers and isn't an entry point
            summary = aug.get("summary", "")
            findings.append(Finding(
                analyzer=self.name,
                severity="info",
                category=self.category,
                title=f"Potentially unused: {file_path}",
                description=(
                    f"{file_path} has no import edges targeting it and is not "
                    f"classified as an entry point (role={role or 'unknown'})."
                    + (f" Summary: {summary}" if summary else "")
                ),
                file_paths=[file_path],
                evidence={
                    "in_degree": 0,
                    "role": role,
                    "language": lang,
                },
                suggested_action=(
                    "Verify if this file is still needed. It may be a standalone "
                    "script, or it may be dead code that can be removed."
                ),
            ))

        findings.sort(key=lambda f: f.file_paths[0] if f.file_paths else "")
        return findings
