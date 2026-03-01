"""Test coverage analyzer — maps source files to test files and finds gaps."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from ..models import AuditContext, Finding
from . import BaseAnalyzer

# Heuristics for matching test → source
_TEST_PREFIXES = ("test_", "tests_")
_TEST_SUFFIXES = ("_test", "_spec", "_tests")
_TEST_DIR_HINTS = {"test", "tests", "spec", "specs", "__tests__"}


class TestCoverageAnalyzer(BaseAnalyzer):
    name = "test_coverage"
    category = "testing"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        # Partition file nodes into source and test files
        source_files: Dict[str, Dict] = {}
        test_files: Dict[str, Dict] = {}

        for nid, node in ctx.file_nodes.items():
            fp = node.get("file_path", "")
            lang = node.get("language", "")
            if not fp or lang in ("markdown",):
                continue

            if _is_test_file(fp):
                test_files[fp] = node
            else:
                source_files[fp] = node

        if not source_files:
            return findings

        # Build test → source mapping via heuristics
        tested_sources: Set[str] = set()
        for test_path in test_files:
            candidates = _infer_source_files(test_path, set(source_files.keys()))
            tested_sources.update(candidates)

        # Also check import edges: if a test file imports a source file, count it
        for edge in ctx.edges:
            if edge.get("kind") != "imports":
                continue
            src_node = ctx.nodes.get(edge.get("source", ""), {})
            tgt_node = ctx.nodes.get(edge.get("target", ""), {})
            src_path = src_node.get("file_path", "")
            tgt_path = tgt_node.get("file_path", "")
            if src_path in test_files and tgt_path in source_files:
                tested_sources.add(tgt_path)

        # Find untested source files
        untested = [fp for fp in source_files if fp not in tested_sources]

        # Filter: only flag code files with meaningful roles
        meaningful_untested = []
        for fp in untested:
            aug = ctx.augmentations.get(f"file:{fp}", {})
            role = aug.get("role", "")
            # Skip configs, scripts, __init__ files
            if role in ("config", "script", "documentation"):
                continue
            name = fp.rsplit("/", 1)[-1]
            if name in ("__init__.py", "conftest.py", "setup.py"):
                continue
            meaningful_untested.append(fp)

        if not meaningful_untested:
            return findings

        # Overall coverage finding
        total = len(source_files)
        covered = total - len(meaningful_untested)
        coverage_pct = round(100 * covered / total, 1) if total > 0 else 0.0

        severity = "warning" if coverage_pct < 50 else "info"

        findings.append(Finding(
            analyzer=self.name,
            severity=severity,
            category=self.category,
            title=f"Test coverage: {coverage_pct}% ({covered}/{total} source files have tests)",
            description=(
                f"{len(meaningful_untested)} source files have no associated test file. "
                f"Coverage is estimated at {coverage_pct}% based on filename matching "
                f"and import analysis."
            ),
            file_paths=meaningful_untested[:20],
            evidence={
                "total_source_files": total,
                "tested_files": covered,
                "untested_files": len(meaningful_untested),
                "coverage_pct": coverage_pct,
                "test_file_count": len(test_files),
            },
            suggested_action="Add tests for the untested files, prioritizing core and API modules.",
        ))

        # Per-module breakdown if modules exist
        if ctx.modules:
            module_coverage: Dict[str, Dict] = {}
            for mod in ctx.modules:
                mod_name = mod.get("name", mod.get("module_id", ""))
                members = mod.get("member_files", [])
                src_members = [f for f in members if f in source_files]
                untested_members = [f for f in src_members if f in meaningful_untested]
                if src_members:
                    mod_cov = round(100 * (len(src_members) - len(untested_members)) / len(src_members), 1)
                    if mod_cov < 30 and len(src_members) >= 3:
                        findings.append(Finding(
                            analyzer=self.name,
                            severity="warning",
                            category=self.category,
                            title=f"Low test coverage in module '{mod_name}': {mod_cov}%",
                            description=f"Only {mod_cov}% of files in '{mod_name}' have associated tests.",
                            file_paths=untested_members[:10],
                            evidence={"module": mod_name, "coverage_pct": mod_cov, "untested_count": len(untested_members)},
                            suggested_action=f"Prioritize testing for module '{mod_name}'.",
                        ))

        return findings


def _is_test_file(path: str) -> bool:
    """Check if a path looks like a test file."""
    parts = path.lower().split("/")
    # Check directory segments
    for part in parts[:-1]:
        if part in _TEST_DIR_HINTS:
            return True
    # Check filename
    name = parts[-1].rsplit(".", 1)[0] if "." in parts[-1] else parts[-1]
    if any(name.startswith(p) for p in _TEST_PREFIXES):
        return True
    if any(name.endswith(s) for s in _TEST_SUFFIXES):
        return True
    return False


def _infer_source_files(test_path: str, source_paths: Set[str]) -> List[str]:
    """Given a test file path, infer which source file(s) it tests."""
    matches: List[str] = []
    name = test_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    ext = test_path.rsplit(".", 1)[-1] if "." in test_path else ""

    # Strip test prefixes/suffixes to get the base name
    base = name
    for p in _TEST_PREFIXES:
        if base.startswith(p):
            base = base[len(p):]
            break
    for s in _TEST_SUFFIXES:
        if base.endswith(s):
            base = base[:-len(s)]
            break

    if not base:
        return matches

    # Look for source files matching the base name
    for sp in source_paths:
        sp_name = sp.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if sp_name == base:
            matches.append(sp)

    return matches
