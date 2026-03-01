"""Large file analyzer — flags files exceeding size thresholds."""
from __future__ import annotations

from typing import List

from ..models import AuditContext, Finding
from . import BaseAnalyzer


# Thresholds (lines estimated from metadata.size / avg 40 bytes per line)
CRITICAL_BYTES = 80_000   # ~2000 lines
WARNING_BYTES = 40_000    # ~1000 lines


class LargeFileAnalyzer(BaseAnalyzer):
    name = "large_files"
    category = "size"

    def __init__(
        self,
        critical_bytes: int = CRITICAL_BYTES,
        warning_bytes: int = WARNING_BYTES,
    ):
        self.critical_bytes = critical_bytes
        self.warning_bytes = warning_bytes

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        for nid, node in ctx.file_nodes.items():
            size = node.get("metadata", {}).get("size", 0)
            if not size:
                continue

            file_path = node.get("file_path", "")
            lang = node.get("language", "unknown")
            est_lines = size // 40

            if size >= self.critical_bytes:
                severity = "critical"
            elif size >= self.warning_bytes:
                severity = "warning"
            else:
                continue

            # Enrich with augmentation data if available
            aug = ctx.augmentations.get(nid, {})
            role = aug.get("role", "unknown")
            summary = aug.get("summary", "")

            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"Large file: {file_path} (~{est_lines} lines)",
                description=(
                    f"{file_path} is {size:,} bytes (~{est_lines} lines). "
                    f"Language: {lang}, Role: {role}."
                    + (f" Summary: {summary}" if summary else "")
                ),
                file_paths=[file_path],
                evidence={
                    "bytes": size,
                    "estimated_lines": est_lines,
                    "language": lang,
                    "role": role,
                },
                suggested_action=(
                    "Consider splitting into a subpackage with focused modules."
                    if severity == "critical"
                    else "Review for extraction opportunities."
                ),
            ))

        findings.sort(key=lambda f: -f.evidence.get("bytes", 0))
        return findings
