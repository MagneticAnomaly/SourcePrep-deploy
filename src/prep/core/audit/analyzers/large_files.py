"""Large file analyzer — flags files exceeding size thresholds."""
from __future__ import annotations

import os
from typing import List

from ..models import AuditContext, Finding
from . import BaseAnalyzer


# Thresholds (lines estimated from metadata.size / avg 40 bytes per line)
CRITICAL_BYTES = 80_000   # ~2000 lines
WARNING_BYTES = 40_000    # ~1000 lines

# Lock/generated files that are always large and never actionable.
# These are managed by package managers, not by developers.
_GENERATED_DIRS = ("/dist/", "/build/", "/out/", "/.next/", "/node_modules/",
                   "/__pycache__/", "/.tox/", "/target/", "/.nuxt/")

EXPECTED_LARGE_BASENAMES = frozenset({
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    "Gemfile.lock",
    "Cargo.lock",
    "poetry.lock",
    "composer.lock",
    "Podfile.lock",
    "go.sum",
    "Pipfile.lock",
    "flake.lock",
    "packages.lock.json",  # NuGet
    "pubspec.lock",        # Dart/Flutter
})


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

            # Skip expected-large lock/generated files
            basename = os.path.basename(file_path)
            if basename in EXPECTED_LARGE_BASENAMES:
                continue
            # Phase 73: Skip generic lock suffixes, generated, and minified files
            if basename.endswith((".lock", ".min.js", ".min.css", ".map", ".js.map", ".pb.go", ".generated.ts")):
                continue
            if basename.endswith("-lock.json") or basename.endswith("-lock.yaml"):
                continue
            # Phase 73: Skip generated/build output directories
            if any(seg in f"/{file_path}/" for seg in _GENERATED_DIRS):
                continue

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

            # Phase 73: Context-aware advice based on file type
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".md", ".rst", ".txt"):
                action = "Consider splitting into sub-documents or adding a table of contents."
            elif ext in (".json", ".yaml", ".yml", ".toml"):
                action = "Review whether this config can be split into per-environment or per-module files."
            elif ext in (".log",):
                action = "Consider adding to .gitignore or archiving old logs."
            elif severity == "critical":
                action = "Consider splitting into focused modules with clear responsibilities."
            else:
                action = "Review for extraction opportunities."

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
                suggested_action=action,
            ))

        findings.sort(key=lambda f: -f.evidence.get("bytes", 0))
        return findings
