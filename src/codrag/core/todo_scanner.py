"""
TODO/FIXME/HACK scanner for codebase roadmap discovery (Phase 59).

Scans the project root for common annotation patterns and converts them
into RoadmapNode entries with source="todo_scan". Uses ripgrep (rg) if
available, falls back to Python-based grep.

Usage:
    from codrag.core.todo_scanner import scan_todos
    nodes = scan_todos(project_root, existing_ids=set())
"""
from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from codrag.core.goalposts_models import RoadmapNode

logger = logging.getLogger(__name__)

# ── Scan patterns ────────────────────────────────────────────────────

SCAN_PATTERNS: Dict[str, str] = {
    "TODO":     "feature",
    "FIXME":    "tech_debt",
    "HACK":     "tech_debt",
    "XXX":      "tech_debt",
    "OPTIMIZE": "architecture",
    "PERF":     "architecture",
    "BUG":      "tech_debt",
}

# Regex to match annotation lines: // TODO: ..., # FIXME ..., /* HACK: ... */
_PATTERN_RE = re.compile(
    r"(?://|#|/\*|\*)\s*("
    + "|".join(SCAN_PATTERNS.keys())
    + r")[\s:(\-]+(.+?)(?:\*/)?$",
    re.IGNORECASE,
)

# Directories to always skip — use centralized list from repo_profile
try:
    from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
    _SKIP_DIRS = DEFAULT_EXCLUDE_DIR_NAMES
except ImportError:
    _SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", ".codrag", "dist",
        "build", ".next", "target", "venv", ".venv", ".tox",
        "Pods", "Carthage", "DerivedData", "vendor", "bundle",
        "bower_components",
    }

# File extensions to scan
_SCAN_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go",
    ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp",
    ".rb", ".php", ".sh", ".bash", ".zsh",
}


# ── Core scanner ─────────────────────────────────────────────────────

def _make_todo_id(file_path: str, line_num: int, text: str) -> str:
    """Deterministic ID for a TODO annotation."""
    seed = f"todo:{file_path}:{line_num}:{text[:50]}"
    h = hashlib.sha256(seed.encode()).hexdigest()[:8]
    return f"RM-{h}"


def _priority_from_tag(tag: str) -> str:
    """Map annotation tags to priorities."""
    tag_upper = tag.upper()
    if tag_upper in ("BUG", "FIXME"):
        return "P1"
    if tag_upper in ("HACK", "XXX"):
        return "P2"
    return "P3"


def scan_todos(
    project_root: Path,
    *,
    existing_ids: Optional[Set[str]] = None,
    max_results: int = 100,
) -> List[RoadmapNode]:
    """Scan the project for TODO/FIXME/HACK annotations.

    Args:
        project_root: Path to the project root directory.
        existing_ids: Set of RoadmapNode IDs to skip (dedup).
        max_results: Maximum number of nodes to return.

    Returns:
        List of RoadmapNode with source="todo_scan" and tier="proposed".
    """
    project_root = Path(project_root)
    if not project_root.is_dir():
        logger.warning("TODO scanner: project root %s is not a directory", project_root)
        return []

    existing = existing_ids or set()

    # Try ripgrep first (much faster for large codebases)
    results = _scan_with_ripgrep(project_root, max_results * 2)
    if results is None:
        # Fallback to Python grep
        results = _scan_with_python(project_root, max_results * 2)

    # Convert to RoadmapNodes, deduplicating
    nodes: List[RoadmapNode] = []
    for file_path, line_num, tag, text in results:
        node_id = _make_todo_id(file_path, line_num, text)
        if node_id in existing:
            continue
        existing.add(node_id)

        category = SCAN_PATTERNS.get(tag.upper(), "feature")

        nodes.append(RoadmapNode(
            id=node_id,
            title=f"[{tag.upper()}] {text[:80]}",
            description=f"Found in `{file_path}` at line {line_num}:\n\n{tag.upper()}: {text}",
            tier="proposed",
            position=len(nodes),
            source="todo_scan",
            source_ref=f"{file_path}:{line_num}",
            category=category,
            priority=_priority_from_tag(tag),
            state="proposed",
        ))

        if len(nodes) >= max_results:
            break

    _apply_churn_gate(nodes, project_root)

    logger.info("TODO scanner: found %d annotations in %s", len(nodes), project_root)
    return nodes


# ── Ripgrep backend ──────────────────────────────────────────────────

def _scan_with_ripgrep(
    project_root: Path,
    max_results: int,
) -> Optional[List[Tuple[str, int, str, str]]]:
    """Use ripgrep for fast scanning. Returns None if rg is not available."""
    pattern = r"(?://|#|/\*|\*)\s*(?:TODO|FIXME|HACK|XXX|OPTIMIZE|PERF|BUG)[\s:(]"

    # Build --glob exclusion flags for vendor/dependency directories
    glob_flags: list[str] = []
    for d in sorted(_SKIP_DIRS):
        glob_flags.extend(["--glob", f"!{d}/**"])
    # Also exclude dotdirs not already covered
    glob_flags.extend(["--glob", "!.*/**"])

    try:
        result = subprocess.run(
            [
                "rg",
                "--no-heading",
                "--line-number",
                "--max-count", str(max_results),
                "--type-add", "code:*.py",
                "--type-add", "code:*.ts",
                "--type-add", "code:*.tsx",
                "--type-add", "code:*.js",
                "--type-add", "code:*.jsx",
                "--type-add", "code:*.rs",
                "--type-add", "code:*.go",
                "-i",  # case insensitive
                *glob_flags,
                pattern,
                str(project_root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return None  # rg not installed
    except subprocess.TimeoutExpired:
        logger.warning("TODO scanner: ripgrep timed out")
        return None

    if result.returncode not in (0, 1):  # 1 = no matches
        return None

    return _parse_grep_output(result.stdout, project_root)


# ── Python fallback ──────────────────────────────────────────────────

def _scan_with_python(
    project_root: Path,
    max_results: int,
) -> List[Tuple[str, int, str, str]]:
    """Pure Python fallback scanner (slower but always available)."""
    results: List[Tuple[str, int, str, str]] = []

    for path in project_root.rglob("*"):
        if len(results) >= max_results:
            break
        if not path.is_file():
            continue
        if path.suffix not in _SCAN_EXTENSIONS:
            continue
        # Skip ignored directories
        parts = path.relative_to(project_root).parts
        if any(p in _SKIP_DIRS for p in parts):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue

        rel_path = str(path.relative_to(project_root))
        for line_num, line in enumerate(text.splitlines(), 1):
            m = _PATTERN_RE.search(line)
            if m:
                tag = m.group(1).upper()
                message = m.group(2).strip().rstrip("*/").strip()
                if message:
                    results.append((rel_path, line_num, tag, message))
                    if len(results) >= max_results:
                        break

    return results


# ── Phase 105: churn gate ────────────────────────────────────────────

_STALE_WINDOW_DAYS = 180


def _apply_churn_gate(nodes: List[RoadmapNode], project_root: Path) -> None:
    """Demote TODOs whose source file has not been touched in the window.

    Fails open: if evidence is unavailable (not a git repo, shallow clone,
    settings disabled, subprocess error), this is a no-op. Mutates nodes
    in place.
    """
    try:
        from codrag.services.git_evidence_service import get_git_evidence
        evidence = get_git_evidence(project_root)
    except Exception:
        return
    if evidence is None:
        return

    try:
        churn = evidence.recent_churn_by_file(window_days=_STALE_WINDOW_DAYS)
    except Exception:
        return
    if not churn:
        return

    suffix = f" [stale: file not touched in {_STALE_WINDOW_DAYS}d]"
    for node in nodes:
        # source_ref shape for todo_scan nodes is "<path>:<line>"
        ref = node.source_ref or ""
        path = ref.rsplit(":", 1)[0] if ":" in ref else ""
        if not path:
            continue
        if path not in churn:
            node.priority = "P3"
            current_desc = node.description or ""
            if suffix not in current_desc:
                node.description = current_desc + suffix


# ── Shared parser ────────────────────────────────────────────────────

def _parse_grep_output(
    output: str,
    project_root: Path,
) -> List[Tuple[str, int, str, str]]:
    """Parse ripgrep output into (file, line, tag, message) tuples."""
    results: List[Tuple[str, int, str, str]] = []

    for line in output.splitlines():
        # ripgrep output: /path/to/file:123: content
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue

        file_path = parts[0]
        try:
            line_num = int(parts[1])
        except ValueError:
            continue
        content = parts[2].strip()

        m = _PATTERN_RE.search(content)
        if not m:
            continue

        tag = m.group(1).upper()
        message = m.group(2).strip().rstrip("*/").strip()
        if not message:
            continue

        # Make path relative to project root
        try:
            rel_path = str(Path(file_path).relative_to(project_root))
        except ValueError:
            rel_path = file_path

        results.append((rel_path, line_num, tag, message))

    return results
