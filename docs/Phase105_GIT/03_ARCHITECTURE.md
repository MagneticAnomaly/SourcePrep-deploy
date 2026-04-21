# 03 — Architecture: `core/git_evidence.py`

Scoped for Option γ. One primitive plus two helpers (`classify_hub`,
`hot_zones`). Everything else deferred. The module is consumer-
agnostic; the TODO scanner and the Atlas both call the same API.

## Public surface — Phase 105 only

```python
# src/codrag/core/git_evidence.py

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


HubLabel = str   # "stable" | "evolving" | "fragile" | "unknown"


@dataclass(frozen=True)
class FileChurn:
    path: str                    # repo-relative POSIX
    commits: int                 # commits touching this file in window
    lines_added: int
    lines_removed: int
    first_seen: datetime         # first commit in window
    last_seen: datetime
    authors: int                 # distinct authors in window


class GitEvidence:
    def __init__(
        self,
        repo_root: Path,
        *,
        cache_dir: Path,
        default_window_days: int = 60,
        default_max_commits: int = 2000,
    ) -> None: ...

    # ── Primitive ─────────────────────────────────────────────────────
    def recent_churn_by_file(
        self, *, window_days: Optional[int] = None,
    ) -> Dict[str, FileChurn]:
        """Return {path: FileChurn} for every file touched in window."""

    def file_touched_in_window(
        self, path: str, *, window_days: Optional[int] = None,
    ) -> bool:
        """Quick boolean for TODO churn gating."""

    # ── Classification helpers ────────────────────────────────────────
    def classify_hub(
        self, path: str, *, window_days: Optional[int] = None,
    ) -> HubLabel:
        """Label a hub file based on churn. 'unknown' if unavailable."""

    def hot_zones(
        self, *, top_n: int = 5, window_days: Optional[int] = None,
        min_commits: int = 10,
    ) -> List[str]:
        """Return directories with highest commit count in window.

        Returns at most top_n entries; returns [] if fewer than 3
        directories clear min_commits (no 'hot zones' banner worth
        showing).
        """

    # ── Cache management ──────────────────────────────────────────────
    def refresh(self) -> None: ...
    def stats(self) -> Dict[str, int]: ...
```

## Classification thresholds (tunable)

```python
HUB_STABLE_MAX_COMMITS    = 3    # < this → stable
HUB_EVOLVING_MAX_COMMITS  = 15   # < this → evolving
HUB_FRAGILE_MIN_AUTHORS   = 3    # plus > EVOLVING_MAX → fragile
```

Rules:

- `commits < HUB_STABLE_MAX_COMMITS` → **stable**
- `HUB_STABLE_MAX_COMMITS <= commits <= HUB_EVOLVING_MAX_COMMITS` → **evolving**
- `commits > HUB_EVOLVING_MAX_COMMITS` and `authors >= HUB_FRAGILE_MIN_AUTHORS` → **fragile**
- Otherwise → **evolving** (high churn but single-author is not
  "fragile" — it's someone actively working alone)
- Path absent from churn map → **unknown**

Thresholds are module-level constants for now. Promote to settings in
a later phase if dogfood shows they need per-project tuning.

## Hot-zone aggregation

```python
def hot_zones(top_n=5, window_days=60, min_commits=10) -> List[str]:
    """
    1. Load churn map.
    2. Group by parent directory (2-3 levels deep, configurable).
    3. Sum commits per directory.
    4. Filter to dirs with >= min_commits.
    5. Sort by commit count descending, tie-break lex.
    6. Return first top_n as repo-relative POSIX paths.
    7. Return [] if fewer than 3 qualifying directories.
    """
```

Directory depth: default 3 (e.g., `src/codrag/api/routers/projects/`).
Trims to a useful granularity for the atlas — not so shallow it's
uninformative, not so deep it bloats the line.

## Deferred primitives (forward-compatible signatures)

Drafted so future phases don't refactor the module. Not implemented.

```python
# To be added in Phase 105.5 (Untraced commit grouping)
def last_commit_for_files(
    self, paths: List[str],
) -> Dict[str, Optional[CommitMessage]]: ...

# To be added in Phase 106 (roadmap retirement)
def commit_message_index(...) -> List[CommitMessage]: ...
def matching_commits_for_keywords(...) -> List[CommitMessage]: ...

# To be added in Phase 107 (co-change mining)
@dataclass(frozen=True)
class CoChangePair: ...
def cochange_pairs(...) -> List[CoChangePair]: ...
```

## Cache design

```
<project_index_dir>/git_evidence/
    signature.json     # {head_sha, window_days, max_commits, repo_root, schema_version}
    churn.json         # {path: FileChurn}
```

Staleness: cache valid iff signature matches. Any mismatch → refresh.

Future caches (`commits.json`, `cochange.json`) sit alongside with
their own signatures so enabling one doesn't force the others to
re-build.

**No SQLite.** Memory flags WAL unreliable on the 4TB-BAD USB drive.
JSON with atomic rename is immune. Cache size on this repo: <1 MB.

## Data source

Single subprocess call for churn:

```
git log --since="<N> days ago" --max-count=<cap> --numstat --no-merges \
    --format="COMMIT %H|%an|%aI|%s"
```

Streamed parse. Per-commit file cap: if a commit touches > 50 files,
count each file once but do not let the commit dominate any single
file's count (protects against prettier, codemods, lockfile
regenerations).

Complexity O(commits × files_per_commit); bounded by caps. On this repo
with defaults: ~500 commits × ~5 files avg = 2500 rows. Sub-second parse.

## Exclusions

Paths excluded from the churn map:

- `DEFAULT_EXCLUDE_DIR_NAMES` from `repo_profile.py` (shared source).
- CoDRAG-managed files: `AGENTS.md`, `CLAUDE.md`, `.prep/**`,
  `.cursor/**` (per memory — auto-regenerated noise).
- Lockfiles: `package-lock.json`, `yarn.lock`, `poetry.lock`,
  `Cargo.lock`, `*.lock`.
- Media: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.pdf`, `*.bin`.

Defined once in `git_evidence._CHURN_EXCLUDE_EXTRA`.

## Service wrapper

```python
# src/codrag/services/git_evidence_service.py

_EVIDENCE_BY_PROJECT: Dict[str, GitEvidence] = {}
_LOCK = threading.Lock()

def get_git_evidence(project_id_or_root: Union[str, Path]) -> Optional[GitEvidence]:
    """Return the GitEvidence for a project, or None if unavailable.

    Resolves project root via the project registry. Returns None if:
    - project not found
    - project root is not a git repo
    - git is not installed
    - settings.git_evidence.enabled is False
    """
```

Atlas generator and TODO scanner both call `get_git_evidence(...)`.

## Error-handling matrix

| Condition | Behavior |
|-----------|----------|
| Not a git repo | Service returns `None`. Callers fail open. |
| Git binary missing | Same as above. |
| Shallow clone | Service returns instance; churn queries return `{}`; one-time warning. Atlas falls back to baseline format. |
| `settings.git_evidence.enabled = false` | Service returns `None`. |
| `settings.git_evidence.atlas_decoration = false` | Service still active; atlas skips classification call. |
| Subprocess non-zero exit | Log, mark cache unavailable, return empty. Retry on next `refresh()`. |
| Corrupt JSON cache | Delete cache file, rebuild. |
| Concurrent access | Lock around cache read/write. |

## Consumer integration points

**Single place in each consumer:**

| Consumer | File | Line (approx) | What it does |
|----------|------|---------------|--------------|
| TODO scanner | `core/todo_scanner.py` | after annotation loop | Demote stale TODOs (see `04_INTEGRATION_TODO_GATING.md`) |
| Atlas hub formatting | `core/atlas/generator.py:469` | in `_generate_root_atlas` | Replace edge-count suffix with label grouping |
| Atlas hot zones | `core/atlas/generator.py:~480` | in `cross_parts` assembly | Append "Active zones" line |

Three integration sites. All fail-open if evidence is unavailable.

## Explicit non-goals for Phase 105

- No HTTP/MCP endpoints for evidence.
- No new pipeline stage.
- No LLM prompt changes.
- No dashboard changes.
- No integration with `concept_store`, `github_push`,
  `sprint_intelligence`, `opportunity_manager`, `roadmap_miner`.
- No co-change mining, retirement, concept promotion, or commit-
  message indexing.

All deferred to later phases — see `06_FUTURE_PATH.md`.

## Tests (Phase 105)

Module-level in `tests/core/test_git_evidence.py`:

1. Fixture-repo smoke: commit files at different dates, assert
   `recent_churn_by_file` reports correct counts and timestamps.
2. Exclusion list: AGENTS.md / `.prep/` committed but absent from
   churn map.
3. Per-commit file cap: single 60-file commit does not inflate counts.
4. Window boundary: file last touched 200d ago with 180d window →
   absent.
5. `classify_hub` thresholds: synthetic FileChurn inputs cover all
   four labels.
6. `hot_zones`: aggregation, cap, min_commits, lex tiebreak.
7. Non-git dir: service returns `None`.
8. Cache invalidation: HEAD change → refresh.
9. Destroy cleanup: `index_destroy_project` removes `git_evidence/`.

Atlas-level in `tests/core/test_atlas_evidence.py`:

10. Hub formatting grouping: mixed labels produce grouped output.
11. Hot-zone line inclusion / exclusion based on `min_commits`.
12. Fallback: evidence disabled → atlas byte-for-byte matches baseline
    (golden file).
13. Token growth: with evidence enabled on fixture repo, atlas text
    grows < 50 tokens.

Scanner integration tested in `04_INTEGRATION_TODO_GATING.md`.
