"""Phase 124 T2 — Markdown ↔ code cross-link extractor.

Walks .md files under a project root, extracts code-path mentions,
validates them against the indexed file set (or the file system if
no index is provided), and emits ``atlas_markdown_links.json`` in
the project's index directory.

Deterministic, no LLM, no embeddings. Runs in seconds on typical
repos. Output is consumed by:

- Atlas stage: ``docs_for_segment`` field per ``AtlasSegmentStatus`` (T3)
- Concept worker: ``relevant_docs`` in module context (T4)

The reverse index (``file → list of .md files mentioning it``) is
not persisted — it is rebuilt lazily at consume time so adding a
new doc doesn't require an atlas regeneration.

Usage as a library:

    from prep.core.atlas.markdown_links import extract, save, docs_for_module
    result = extract(project_root, indexed_files)
    save(result, idx_dir)
    relevant = docs_for_module(result, member_files=["src/foo.py"])

Usage as CLI:

    python -m prep.core.atlas.markdown_links \\
        --project-root /path/to/repo --idx-dir /path/.sourceprep
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

try:
    import prep_engine as _prep_engine  # Rust PyO3 walker
except ImportError:
    _prep_engine = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

# Path mention candidates inside markdown text. Permissive on purpose;
# validation against the indexed file set filters false positives.
_CODE_PATH_RE = re.compile(
    r"\b((?:[A-Za-z0-9_./\-]+/)?[A-Za-z0-9_./\-]+\.(?:py|ts|tsx|js|jsx|rs|mjs|cjs))\b"
)

# Markdown-link target: [label](path) — second group is the URL/path.
_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+?)\)")

# Inline code spans: `path/to/file.py`. We re-run the path regex
# inside the span so we don't double-collect noise like `cmd --flag`.
_INLINE_CODE_RE = re.compile(r"`([^`\n]{2,200})`")

# Directory prefixes excluded from the .md walk.
_WALK_EXCLUDES = (
    ".sourceprep",
    ".git",
    ".claude",       # git worktrees + agent state — parallel doc copies inflate counts
    ".cursor",
    ".windsurf",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".turbo",
    ".next",
    "dist",
    "build",
    "target",        # rust
    "tmp",
    "trash",
)


# ──────────────────────────────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────────────────────────────

@dataclass
class MarkdownLinkResult:
    """Per-md file → sorted list of validated code-file paths."""
    md_to_files: dict[str, list[str]] = field(default_factory=dict)
    extracted_at: str = ""
    project_root: str = ""
    md_count: int = 0
    valid_link_count: int = 0
    raw_mention_count: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema_version"] = 1
        return d


# ──────────────────────────────────────────────────────────────────────
# Extraction
# ──────────────────────────────────────────────────────────────────────

def _extract_candidates(text: str) -> set[str]:
    """Return the union of (regex-matched paths, link targets, code-span paths)."""
    cands: set[str] = set()

    # 1. Bare path mentions in prose.
    cands.update(_CODE_PATH_RE.findall(text))

    # 2. Markdown link targets — pull only the URL slot.
    for tgt in _MD_LINK_RE.findall(text):
        # Drop fragments / queries / external schemes.
        if tgt.startswith(("http://", "https://", "mailto:", "//", "#")):
            continue
        # Strip in-page anchor.
        tgt = tgt.split("#", 1)[0].split("?", 1)[0]
        if tgt:
            cands.update(_CODE_PATH_RE.findall(tgt))
            # The full path may itself be a valid file even if the
            # regex doesn't trigger (rare).
            if "." in tgt and "/" in tgt:
                cands.add(tgt)

    # 3. Inline code spans — re-run the regex inside.
    for span in _INLINE_CODE_RE.findall(text):
        cands.update(_CODE_PATH_RE.findall(span))

    cleaned: set[str] = set()
    for r in cands:
        r = r.strip()
        if r.startswith("./"):
            r = r[2:]
        if r.startswith(("http", "www.", "//")):
            continue
        # Bare filenames without a directory are too noisy to be useful.
        if "/" not in r:
            continue
        cleaned.add(r)
    return cleaned


def _walk_markdown(project_root: Path) -> list[Path]:
    """Return all .md files under project_root, skipping noise dirs."""
    # Phase 134: migrate to prep_engine.walk_repo for filter parity.
    _excl_globs = [f"**/{d}/**" for d in _WALK_EXCLUDES]
    entries = _prep_engine.walk_repo(
        str(project_root),
        include_globs=["**/*.md", "**/*.markdown"],
        exclude_globs=_excl_globs,
        max_file_bytes=500_000,
    )
    return sorted(Path(entry.abs_path) for entry in entries)


def extract(
    project_root: Path,
    indexed_files: Optional[Iterable[str]] = None,
) -> MarkdownLinkResult:
    """Walk .md files, extract code-path mentions, validate.

    Args:
        project_root: Root directory of the project under analysis.
        indexed_files: Optional set of known-indexed file paths
            (relative to project_root). When provided, only these
            paths count as valid links — everything else is dropped.
            When None, the file system itself is the validator
            (path is kept iff ``project_root / path`` exists).

    Returns:
        ``MarkdownLinkResult`` with the per-md → files mapping and
        run-statistics. Missing inputs return an empty result, never
        raise.
    """
    project_root = project_root.resolve()
    if not project_root.is_dir():
        logger.warning("project_root not found: %s", project_root)
        return MarkdownLinkResult(
            project_root=str(project_root),
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )

    indexed_set = set(indexed_files) if indexed_files is not None else None

    md_to_files: dict[str, list[str]] = {}
    raw_mentions = 0
    valid_links = 0

    for md in _walk_markdown(project_root):
        try:
            text = md.read_text(errors="replace")
        except Exception as e:
            logger.debug("skip unreadable md %s: %s", md, e)
            continue

        rel_md = str(md.relative_to(project_root))
        cands = _extract_candidates(text)
        raw_mentions += len(cands)

        validated: list[str] = []
        for cand in cands:
            if cand == rel_md:
                continue  # don't link a doc to itself
            if indexed_set is not None:
                if cand in indexed_set:
                    validated.append(cand)
            else:
                if (project_root / cand).is_file():
                    validated.append(cand)

        if validated:
            md_to_files[rel_md] = sorted(set(validated))
            valid_links += len(validated)

    return MarkdownLinkResult(
        md_to_files=md_to_files,
        extracted_at=datetime.now(timezone.utc).isoformat(),
        project_root=str(project_root),
        md_count=len(md_to_files),
        valid_link_count=valid_links,
        raw_mention_count=raw_mentions,
    )


# ──────────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────────

_OUTPUT_FILENAME = "atlas_markdown_links.json"


def save(result: MarkdownLinkResult, idx_dir: Path) -> Path:
    """Atomically write ``atlas_markdown_links.json`` to ``idx_dir``."""
    idx_dir = Path(idx_dir)
    idx_dir.mkdir(parents=True, exist_ok=True)
    out_path = idx_dir / _OUTPUT_FILENAME

    payload = result.to_dict()

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        dir=str(idx_dir),
        delete=False,
        encoding="utf-8",
    )
    try:
        json.dump(payload, tmp, indent=2, sort_keys=False)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.rename(tmp.name, out_path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise

    logger.info(
        "Saved markdown links: %d md → %d code files (raw mentions: %d) at %s",
        result.md_count, result.valid_link_count, result.raw_mention_count, out_path,
    )
    return out_path


def load(idx_dir: Path) -> Optional[MarkdownLinkResult]:
    """Load a previously saved markdown-links result, or None if missing."""
    path = Path(idx_dir) / _OUTPUT_FILENAME
    if not path.is_file():
        return None
    try:
        d = json.loads(path.read_text())
    except Exception as e:
        logger.warning("failed to load %s: %s", path, e)
        return None
    return MarkdownLinkResult(
        md_to_files=d.get("md_to_files") or {},
        extracted_at=d.get("extracted_at") or "",
        project_root=d.get("project_root") or "",
        md_count=d.get("md_count") or 0,
        valid_link_count=d.get("valid_link_count") or 0,
        raw_mention_count=d.get("raw_mention_count") or 0,
    )


# ──────────────────────────────────────────────────────────────────────
# Consumer-side helpers (lazy reverse index)
# ──────────────────────────────────────────────────────────────────────

def reverse_index(result: MarkdownLinkResult) -> dict[str, list[str]]:
    """Build ``code_file → list[md_file]`` index. Caller caches if needed."""
    rev: dict[str, list[str]] = {}
    for md_path, files in result.md_to_files.items():
        for f in files:
            rev.setdefault(f, []).append(md_path)
    for v in rev.values():
        v.sort()
    return rev


_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _section_for_line(line_idx: int, header_lines: list[int]) -> tuple[int, int]:
    """Return the half-open ``(start, end)`` line range for the section
    containing ``line_idx``. ``header_lines`` is a sorted list of line
    indices that start a markdown header (any depth).

    The section starts at the most-recent header at or before
    ``line_idx`` (or 0 if no header precedes the hit), and ends at the
    next header or end of file. Used by the section-aware excerpt
    extractor (Phase 124 T10) to surface coherent prose units instead
    of fixed line windows that can clip mid-paragraph.
    """
    if not header_lines:
        return (0, -1)  # caller substitutes EOF
    start = 0
    for h in header_lines:
        if h <= line_idx:
            start = h
        else:
            return (start, h)
    return (start, -1)


def extract_excerpt(
    md_path: Path,
    member_files: Iterable[str],
    *,
    window_lines: int = 4,
    max_chars: int = 500,
    section_aware: bool = True,
) -> str:
    """Return an excerpt from md_path showing context around mentions of member_files.

    Two extraction strategies (Phase 124 T4 → T10 progression):

    1. **section_aware=True (default, T10):** for each hit line, expand
       to the enclosing markdown section (most-recent ``#`` header
       through next header). Sections give coherent prose units —
       intent statements, decision rationales — instead of a fixed
       line window that can clip mid-paragraph.

    2. **section_aware=False (T4 v1):** simple line-window — N lines
       before/after each hit, merged on overlap. Useful when callers
       want a tight, predictable excerpt size.

    Both modes:
    - Merge overlapping/adjacent ranges.
    - Truncate at max_chars on a line boundary (no mid-word cut).
    - Return "" if the file is unreadable or no member is mentioned.
    """
    members = {m for m in member_files if isinstance(m, str)}
    if not members or not md_path.is_file():
        return ""
    try:
        lines = md_path.read_text(errors="replace").splitlines()
    except Exception:
        return ""

    hits: list[int] = []
    for i, line in enumerate(lines):
        if any(m in line for m in members):
            hits.append(i)
    if not hits:
        return ""

    n = len(lines)

    if section_aware:
        header_lines = [i for i, l in enumerate(lines) if _HEADER_RE.match(l)]
        ranges: list[tuple[int, int]] = []
        for h in hits:
            start, end = _section_for_line(h, header_lines)
            if end == -1:
                end = n
            if not header_lines:
                # No headers in the doc — fall back to small window.
                start = max(0, h - window_lines)
                end = min(n, h + window_lines + 1)
            if ranges and start <= ranges[-1][1]:
                ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
            else:
                ranges.append((start, end))
    else:
        ranges = []
        for h in hits:
            lo = max(0, h - window_lines)
            hi = min(n, h + window_lines + 1)
            if ranges and lo <= ranges[-1][1]:
                ranges[-1] = (ranges[-1][0], max(ranges[-1][1], hi))
            else:
                ranges.append((lo, hi))

    chunks: list[str] = []
    for lo, hi in ranges:
        chunks.append("\n".join(lines[lo:hi]).rstrip())

    excerpt = "\n…\n".join(chunks).strip()
    if len(excerpt) <= max_chars:
        return excerpt
    truncated = excerpt[:max_chars]
    cut = truncated.rfind("\n")
    if cut > max_chars * 0.5:
        truncated = truncated[:cut]
    return truncated.rstrip() + "\n…"


def aggregate_for_segments(
    result: MarkdownLinkResult,
    segments_manifest: list[dict],
    *,
    cap: int = 5,
) -> dict[str, list[dict]]:
    """For each segment, return top-N .md files by mention count.

    A `.md` file is attributed to a segment when at least one code
    path it mentions belongs to that segment's ``file_paths``. The
    ``mention_count`` is the number of segment files that the doc
    references — higher = more relevant to the segment.

    Args:
        result: Loaded ``MarkdownLinkResult`` (Phase 124 T2 output).
        segments_manifest: List of segment dicts from
            ``atlas_segments_manifest.json``. Each dict must have
            ``id`` (or ``segment_id``) and ``file_paths``.
        cap: Maximum docs returned per segment.

    Returns:
        ``{segment_id: [{"path": "docs/foo.md", "mention_count": N}, ...]}``.
        Segments with no relevant docs map to empty lists.
    """
    if not segments_manifest:
        return {}
    out: dict[str, list[dict]] = {}
    for seg in segments_manifest:
        sid = seg.get("id") or seg.get("segment_id")
        if not sid:
            continue
        seg_files = set(seg.get("file_paths") or [])
        if not seg_files:
            out[sid] = []
            continue
        scores: list[tuple[str, int]] = []
        for md_path, refs in result.md_to_files.items():
            n = sum(1 for r in refs if r in seg_files)
            if n:
                scores.append((md_path, n))
        scores.sort(key=lambda x: (-x[1], x[0]))
        out[sid] = [
            {"path": p, "mention_count": n}
            for p, n in scores[:cap]
        ]
    return out


def docs_for_module(
    result: MarkdownLinkResult,
    member_files: Iterable[str],
    *,
    cap: Optional[int] = None,
) -> list[str]:
    """Return .md files that mention any of ``member_files``.

    Sorted by mention count (most relevant first), tie-broken by
    path. Use ``cap`` to limit the result for prompt-budget control.
    """
    members = set(member_files)
    if not members:
        return []
    # mention count per md = number of member_files referenced
    counts: dict[str, int] = {}
    for md_path, files in result.md_to_files.items():
        overlap = len(set(files) & members)
        if overlap:
            counts[md_path] = overlap
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    out = [md for md, _ in ranked]
    if cap is not None:
        out = out[:cap]
    return out


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def load_indexed_files(idx_dir: Path) -> Optional[set[str]]:
    """Pull the indexed file set from trace_nodes.jsonl if present."""
    nodes_path = idx_dir / "trace_nodes.jsonl"
    if not nodes_path.is_file():
        return None
    files: set[str] = set()
    try:
        with nodes_path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    n = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if n.get("kind") == "file":
                    p = n.get("path") or n.get("file_path")
                    if isinstance(p, str):
                        files.add(p)
    except Exception as e:
        logger.warning("failed reading %s: %s", nodes_path, e)
        return None
    return files or None


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Extract markdown→code cross-links and write atlas_markdown_links.json",
    )
    p.add_argument("--project-root", required=True, help="Project root directory")
    p.add_argument(
        "--idx-dir",
        help="Index dir (where atlas_markdown_links.json will be written). "
             "Defaults to <project-root>/.sourceprep/.",
    )
    p.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip filesystem/trace-nodes validation (keep all path mentions)",
    )
    p.add_argument("--summary", action="store_true", help="Print top results to stdout")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    project_root = Path(args.project_root).resolve()
    idx_dir = Path(args.idx_dir).resolve() if args.idx_dir else project_root / ".sourceprep"

    indexed = None
    if not args.no_validate:
        indexed = load_indexed_files(idx_dir)
        if indexed is None:
            logger.info("no trace_nodes.jsonl — falling back to filesystem validation")

    result = extract(project_root, indexed_files=indexed)
    out_path = save(result, idx_dir)
    print(f"wrote {out_path}")
    print(
        f"  md files with ≥1 valid link: {result.md_count}",
    )
    print(f"  total validated links:       {result.valid_link_count}")
    print(f"  raw mention candidates:      {result.raw_mention_count}")

    if args.summary:
        ranked = sorted(
            result.md_to_files.items(), key=lambda x: -len(x[1]),
        )[:10]
        print("\nTop 10 md files by validated link count:")
        for md, files in ranked:
            print(f"  {len(files):>4}  {md}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
