"""Phase 125c T1 — Auto-discover planning/design docs for the
Generate swarm's grounding load.

Produces ``<idx_dir>/docs_grounding.json``: top-N ``.md`` files in the
repo, each with a layered score (in-link rank + convention name +
folder concentration + hidden-agent-dir signal), an excerpt, and
extracted headings. Generate workers consume this as rich grounding;
nothing in the discoverer hits an LLM.

See ``docs/Phase125c_QualityCheckedConceptSwarm/README.md`` §2.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


# ── Catalogs ────────────────────────────────────────────────────────

# Filename stems (case-insensitive) that signal planning/design intent.
PLANNING_FILENAMES: frozenset[str] = frozenset({
    "ARCHITECTURE", "DESIGN", "ROADMAP", "VISION",
    "RFC", "ADR", "PROPOSAL", "SPEC", "PRD",
    "PLAN", "BACKLOG", "MASTER_TODO",
    "CLAUDE", "AGENTS", "GEMINI", "CURSOR", "WINDSURF",
})

# Folder prefixes (relative to repo root) that signal a planning area.
# Match is "path starts with one of these (with `/` separator)".
PLANNING_FOLDERS: frozenset[str] = frozenset({
    "docs/adr", "docs/decisions", "docs/rfcs", "docs/proposals",
    "docs/specs", "docs/sprints", "docs/phases",
    "rfcs", "adr", "specs", "prds", "product",
    ".cursor/rules", ".github/instructions", ".claude",
    ".windsurf", ".gemini", ".agents",
})

# Dirs we never descend into. Generated artifacts, vendored deps,
# per-tool internal state, test fixtures, and per-agent worktrees —
# none of it is planning material. Note: `.claude/worktrees/` is
# gitignored so the post-Phase-133 Rust walker would skip it natively;
# we list `worktrees` here as belt-and-suspenders for the current
# Python walker which doesn't read .gitignore.
EXCLUDED_DIRS: frozenset[str] = frozenset({
    "node_modules", "dist", "build", "target", "out",
    ".sourceprep", ".git", ".venv", "venv", "__pycache__",
    ".turbo", ".next", ".nuxt", ".cache", "coverage",
    "tmp", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    # Phase 125c noise reduction (post-T1 dogfood):
    "worktrees", ".worktrees",
    "tests", "__tests__", "specs", "fixtures",
})

# Hidden agent dirs we explicitly DO walk (despite leading dot).
# These are the OPPOSITE policy from the trace pipeline (which excludes
# them via repo_profile.DEFAULT_EXCLUDE_DIR_NAMES). Agent-instruction
# files like CLAUDE.md, .cursor/rules/*.mdc, and .agents/*.md are PRIME
# planning material for concept synthesis; they're noise for source
# indexing. The trace excludes are wired in src/prep/core/repo_profile.py
# and src/prep/core/trace/coverage.py.
ALLOWED_DOT_DIRS: frozenset[str] = frozenset({
    ".cursor", ".claude", ".github", ".windsurf", ".gemini", ".agents",
})

_PHASE_OR_SPRINT_RE = re.compile(r"(?:^|/)(?:Phase|Sprint)\d+[A-Za-z]*_", re.IGNORECASE)
_HEADING_RE = re.compile(r"^\s*#+\s*(.+?)\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)

# Score weights — sum capped at 1.0.
_WEIGHT_IN_LINK = 0.5
_WEIGHT_CONVENTION = 0.25
_WEIGHT_FOLDER = 0.15
_WEIGHT_HIDDEN_AGENT = 0.10

# Folder concentration threshold: ≥60% .md files in the immediate folder.
_FOLDER_CONCENTRATION_THRESHOLD = 0.60

# Default excerpt size — large enough for substantial grounding,
# small enough to fit many docs in one prompt.
_DEFAULT_EXCERPT_CHARS = 3000


# ── Data structures ─────────────────────────────────────────────────


@dataclass(frozen=True)
class DiscoveredDoc:
    path: str                          # repo-relative posix path
    score: float                       # 0.0-1.0
    signals: tuple[str, ...]           # which signals fired
    in_link_count: int                 # references from atlas_markdown_links
    size_bytes: int
    excerpt: str
    headings: tuple[str, ...]


@dataclass
class DocsGrounding:
    version: int = 1
    generated_at: float = 0.0
    docs: list[DiscoveredDoc] = field(default_factory=list)
    total_candidates_considered: int = 0
    selected_count: int = 0

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "docs": [
                {**asdict(d), "signals": list(d.signals), "headings": list(d.headings)}
                for d in self.docs
            ],
            "total_candidates_considered": self.total_candidates_considered,
            "selected_count": self.selected_count,
        }


# ── Pure helpers ────────────────────────────────────────────────────


def _is_phase_or_sprint_folder(rel_dir_path: str) -> bool:
    """True if any segment matches Phase\\d+_* or Sprint\\d+_* (case-insensitive).

    Matches `docs/Phase125c_Foo`, `Sprint5_Whatever`, etc. Used as an
    auxiliary convention signal — Phase docs ARE planning docs.
    """
    return bool(_PHASE_OR_SPRINT_RE.search("/" + rel_dir_path))


def _filename_is_convention(stem: str) -> bool:
    return stem.upper() in PLANNING_FILENAMES


def _path_in_planning_folder(rel_path: str) -> bool:
    rel_norm = rel_path.replace("\\", "/")
    for prefix in PLANNING_FOLDERS:
        if rel_norm.startswith(prefix + "/") or rel_norm == prefix:
            return True
    return False


def _path_in_hidden_agent_dir(rel_path: str) -> bool:
    rel_norm = rel_path.replace("\\", "/")
    parts = rel_norm.split("/")
    if not parts:
        return False
    head = parts[0]
    return head in ALLOWED_DOT_DIRS and head.startswith(".")


def score_doc(
    *,
    rel_path: str,
    in_link_count: int,
    in_link_max: int,
    folder_md_ratio: float,
) -> tuple[float, list[str]]:
    """Compute combined score + signal list for one candidate doc."""
    signals: list[str] = []
    score = 0.0

    # In-link rank (Phase 124 signal — the strongest)
    if in_link_count > 0 and in_link_max > 0:
        normalized = min(1.0, in_link_count / in_link_max)
        score += normalized * _WEIGHT_IN_LINK
        signals.append("in_link_rank")

    # Convention filename or phase-folder pattern
    rel_norm = rel_path.replace("\\", "/")
    parent = "/".join(rel_norm.split("/")[:-1])
    stem = Path(rel_norm).stem
    if _filename_is_convention(stem) or (parent and _is_phase_or_sprint_folder(parent)):
        score += _WEIGHT_CONVENTION
        signals.append("convention_match")

    # Folder concentration
    if folder_md_ratio >= _FOLDER_CONCENTRATION_THRESHOLD:
        score += _WEIGHT_FOLDER
        signals.append("folder_concentration")
    # Path in a known planning folder also gets the folder credit
    elif _path_in_planning_folder(rel_norm):
        score += _WEIGHT_FOLDER
        signals.append("folder_concentration")

    # Hidden agent dir
    if _path_in_hidden_agent_dir(rel_norm):
        score += _WEIGHT_HIDDEN_AGENT
        signals.append("hidden_agent_dir")

    return min(1.0, score), signals


def _extract_excerpt(body: str, *, max_chars: int = _DEFAULT_EXCERPT_CHARS) -> str:
    """Return the leading excerpt of `body`, truncated on a paragraph
    boundary. Strips a leading YAML frontmatter block if present."""
    body = _FRONTMATTER_RE.sub("", body, count=1)
    if len(body) <= max_chars:
        return body.rstrip()
    paragraphs = body.split("\n\n")
    out: list[str] = []
    total = 0
    for p in paragraphs:
        out.append(p)
        total += len(p) + 2
        if total >= max_chars:
            break
    return "\n\n".join(out).rstrip()


def _extract_headings(body: str) -> tuple[str, ...]:
    """Return all `# / ## / ###` heading texts in order."""
    return tuple(m.group(1).strip() for m in _HEADING_RE.finditer(body))


# ── File-system walk ────────────────────────────────────────────────


def _walk_md_files(root: Path) -> list[Path]:
    """Yield every `.md` file under `root` excluding generated dirs and
    non-allowlisted dot dirs. Returns absolute paths."""
    md_paths: list[Path] = []

    def _recurse(d: Path) -> None:
        try:
            entries = list(d.iterdir())
        except (OSError, PermissionError):
            return
        for e in entries:
            name = e.name
            if e.is_dir():
                if name in EXCLUDED_DIRS:
                    continue
                if name.startswith(".") and name not in ALLOWED_DOT_DIRS:
                    continue
                _recurse(e)
            elif e.is_file() and name.lower().endswith(".md"):
                md_paths.append(e)

    _recurse(root)
    return md_paths


def _folder_md_ratio(folder: Path) -> float:
    """Fraction of files in `folder` (non-recursive) that are .md."""
    try:
        files = [e for e in folder.iterdir() if e.is_file()]
    except (OSError, PermissionError):
        return 0.0
    if not files:
        return 0.0
    md_count = sum(1 for f in files if f.name.lower().endswith(".md"))
    return md_count / len(files)


# ── Discovery + grounding build ─────────────────────────────────────


def discover_planning_docs(
    project_root: Path,
    *,
    in_link_map: Optional[dict[str, list[str]]] = None,
    top_n: int = 30,
    excerpt_chars: int = _DEFAULT_EXCERPT_CHARS,
) -> list[DiscoveredDoc]:
    """Walk `project_root`, score every `.md` file, return the top-N.

    `in_link_map` is `atlas_markdown_links.json`'s `md_to_files` dict —
    the key is a repo-relative md path, the value is the list of
    source files that reference it. Pass None when atlas hasn't run yet.
    """
    md_files = _walk_md_files(project_root)
    in_link_map = in_link_map or {}

    # Normalize in-link map keys + compute max link count for scoring.
    link_counts = {k: len(v or []) for k, v in in_link_map.items()}
    in_link_max = max(link_counts.values(), default=0)

    # Cache folder ratios (one stat per parent directory).
    folder_ratio_cache: dict[Path, float] = {}

    candidates: list[DiscoveredDoc] = []
    for md_abs in md_files:
        try:
            rel = md_abs.relative_to(project_root).as_posix()
        except ValueError:
            continue
        parent = md_abs.parent
        if parent not in folder_ratio_cache:
            folder_ratio_cache[parent] = _folder_md_ratio(parent)
        ratio = folder_ratio_cache[parent]
        in_link_count = link_counts.get(rel, 0)

        score, signals = score_doc(
            rel_path=rel,
            in_link_count=in_link_count,
            in_link_max=in_link_max,
            folder_md_ratio=ratio,
        )
        if score <= 0.0:
            continue

        try:
            body = md_abs.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        excerpt = _extract_excerpt(body, max_chars=excerpt_chars)
        headings = _extract_headings(body)

        candidates.append(DiscoveredDoc(
            path=rel,
            score=score,
            signals=tuple(signals),
            in_link_count=in_link_count,
            size_bytes=len(body.encode("utf-8", errors="replace")),
            excerpt=excerpt,
            headings=headings,
        ))

    candidates.sort(key=lambda d: -d.score)
    return candidates[:top_n]


def build_docs_grounding(
    project_id: str,  # noqa: ARG001 — accepted for API symmetry
    *,
    project_root: Path,
    idx_dir: Path,
    top_n: int = 30,
) -> DocsGrounding:
    """Top-level orchestrator. Reads `atlas_markdown_links.json` (if
    present) and walks `project_root`, returns a DocsGrounding."""
    in_link_map: Optional[dict[str, list[str]]] = None
    ml_path = idx_dir / "atlas_markdown_links.json"
    if ml_path.is_file():
        try:
            data = json.loads(ml_path.read_text(encoding="utf-8"))
            md_to_files = data.get("md_to_files")
            if isinstance(md_to_files, dict):
                in_link_map = md_to_files
        except (json.JSONDecodeError, OSError):
            pass

    docs = discover_planning_docs(
        project_root, in_link_map=in_link_map, top_n=top_n,
    )
    # Total candidates is "every .md we walked" — useful in telemetry
    # to spot under-indexed repos.
    total = len(_walk_md_files(project_root))
    return DocsGrounding(
        version=1,
        generated_at=time.time(),
        docs=docs,
        total_candidates_considered=total,
        selected_count=len(docs),
    )


def write_docs_grounding(grounding: DocsGrounding, idx_dir: Path) -> None:
    """Persist `<idx_dir>/docs_grounding.json` (atomic write)."""
    idx_dir.mkdir(parents=True, exist_ok=True)
    out_path = idx_dir / "docs_grounding.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(grounding.to_dict(), indent=2), encoding="utf-8")
    tmp_path.replace(out_path)
