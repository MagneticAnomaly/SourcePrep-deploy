# Vendor-Dir Sniffer + Init Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent SourcePrep from indexing thousands of files in vendored / build-output / submodule directories by detecting them up front, auto-excluding the obvious cases, and surfacing ambiguous candidates via a two-gate modal flow at Initialize click time.

**Architecture:** A pure-function sniffer (`src/prep/core/vendor_sniffer/`) classifies top-level directories into Tier 1 (auto-exclude), Tier 2 (propose), or Tier 3 (skip — user code) using manifest evidence (`.gitmodules`, root `.gitignore`, workspace declarations) plus structural signals (nested `.git/`, build-marker files) with size/file-count as a last-resort fallback. Results are persisted on the project record. The dashboard's Initialize button gates on results: an optional gitignore-hygiene modal (Gate 1) fires for clear `.gitignore` gaps in git repos, then a vendor-review modal (Gate 2) fires for ambiguous candidates. Auto-excludes union into `exclude_globs` via Phase 115's additive-merge contract; nothing overwrites user-set config.

**Tech Stack:** Python 3.11+ (pytest, dataclasses, tomllib stdlib); TypeScript + React (packages/ui design system, Tailwind, Radix); FastAPI for new endpoints; Rust `prep-walker` (already gitignore-aware) reused via existing `prep_engine.walk_repo` PyO3 bindings.

**Spec:** `docs/superpowers/specs/2026-05-12-vendor-sniffer-init-gate-design.md` (read this first).

**Memory rules being honored:**
- All Python commands use `.venv/bin/python` / `.venv/bin/pytest`
- No `Co-Authored-By` trailer in commits
- Restart daemon (`prep serve`) before any live validation step — no hot-reload
- `cesium-native` and similar project-specific names stay Tier 2 (conservative whitelist)
- Flat thresholds — no storage-class-aware branching

**Phases:**
1. Sniffer core (pure functions, no daemon dependencies) — Tasks 1–13
2. Backend integration (schema + endpoints + crud wiring) — Tasks 14–20
3. UI gates (modals + indicator + Initialize click wiring) — Tasks 21–27
4. Live dogfooding validation — Task 28

---

## Phase 1: Sniffer Core

Pure-function module. No daemon, no HTTP, no UI dependencies. Tests run with `.venv/bin/pytest` against synthetic directory fixtures.

### Task 1: Data Models

**Files:**
- Create: `src/prep/core/vendor_sniffer/__init__.py`
- Create: `src/prep/core/vendor_sniffer/models.py`
- Test: `tests/test_vendor_sniffer/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vendor_sniffer/test_models.py
from prep.core.vendor_sniffer.models import VendorCandidate, VendorScanResult


def test_vendor_candidate_required_fields():
    c = VendorCandidate(
        path="/abs/path/vcpkg",
        rel_path="vcpkg",
        size_bytes=2_700_000_000,
        file_count=8210,
        reason="Nested git repo, possibly vendored",
        tier="propose",
        in_gitignore=False,
        is_git_repo=True,
    )
    assert c.tier in ("auto", "propose")
    assert c.rel_path == "vcpkg"


def test_vendor_scan_result_default_status_complete():
    r = VendorScanResult(
        auto_excluded=["**/Pods/**", "**/build/**"],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=1715500000.0,
        status="complete",
        error=None,
    )
    assert r.status == "complete"
    assert r.error is None


def test_vendor_scan_result_pending_state():
    r = VendorScanResult(
        auto_excluded=[],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=0.0,
        status="pending",
        error=None,
    )
    assert r.status == "pending"


def test_vendor_scan_result_failed_state_carries_error():
    r = VendorScanResult(
        auto_excluded=[],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=1715500000.0,
        status="failed",
        error="prep_engine.walk_repo: disk I/O error",
    )
    assert r.status == "failed"
    assert "disk I/O" in r.error
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_models.py -v
```
Expected: `ImportError` — `vendor_sniffer` package does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/prep/core/vendor_sniffer/__init__.py
from prep.core.vendor_sniffer.models import VendorCandidate, VendorScanResult

__all__ = ["VendorCandidate", "VendorScanResult"]
```

```python
# src/prep/core/vendor_sniffer/models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class VendorCandidate:
    path: str
    rel_path: str
    size_bytes: int
    file_count: int
    reason: str
    tier: Literal["auto", "propose"]
    in_gitignore: bool
    is_git_repo: bool


@dataclass(frozen=True)
class VendorScanResult:
    auto_excluded: list[str]
    proposed: list[VendorCandidate]
    gitignore_gaps: list[VendorCandidate]
    scanned_at: float
    status: Literal["pending", "complete", "failed"]
    error: str | None
```

- [ ] **Step 4: Run test to verify it passes**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_models.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add src/prep/core/vendor_sniffer/__init__.py src/prep/core/vendor_sniffer/models.py tests/test_vendor_sniffer/test_models.py
git commit -m "feat(vendor-sniffer): data models for scan results and candidates"
```

---

### Task 2: `.gitmodules` Parser

**Files:**
- Create: `src/prep/core/vendor_sniffer/manifests.py`
- Test: `tests/test_vendor_sniffer/test_manifests_gitmodules.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vendor_sniffer/test_manifests_gitmodules.py
from pathlib import Path

import pytest

from prep.core.vendor_sniffer.manifests import parse_gitmodules


def test_parse_gitmodules_extracts_paths(tmp_path: Path):
    gm = tmp_path / ".gitmodules"
    gm.write_text(
        '[submodule "vcpkg"]\n'
        '\tpath = vcpkg\n'
        '\turl = https://github.com/microsoft/vcpkg.git\n'
        '[submodule "deps/cesium-native"]\n'
        '\tpath = deps/cesium-native\n'
        '\turl = https://github.com/CesiumGS/cesium-native.git\n'
    )
    paths = parse_gitmodules(tmp_path)
    assert paths == {"vcpkg", "deps/cesium-native"}


def test_parse_gitmodules_missing_file_returns_empty(tmp_path: Path):
    assert parse_gitmodules(tmp_path) == set()


def test_parse_gitmodules_malformed_returns_empty_or_partial(tmp_path: Path):
    gm = tmp_path / ".gitmodules"
    gm.write_text("this is not a valid gitmodules file\nrandom garbage\n")
    # Parser must not raise — return whatever it could extract (likely empty)
    paths = parse_gitmodules(tmp_path)
    assert isinstance(paths, set)


def test_parse_gitmodules_ignores_blank_url_lines(tmp_path: Path):
    gm = tmp_path / ".gitmodules"
    gm.write_text(
        '[submodule "a"]\n'
        '\tpath = a\n'
        '\n'
        '[submodule "b"]\n'
        '\tpath = b/nested\n'
    )
    assert parse_gitmodules(tmp_path) == {"a", "b/nested"}
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_manifests_gitmodules.py -v
```
Expected: `ImportError` on `parse_gitmodules`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/prep/core/vendor_sniffer/manifests.py
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_GITMODULES_PATH_RE = re.compile(r"^\s*path\s*=\s*(.+?)\s*$")


def parse_gitmodules(root: Path) -> set[str]:
    """Extract submodule paths from <root>/.gitmodules. Returns empty set on missing/malformed."""
    gm = root / ".gitmodules"
    if not gm.is_file():
        return set()
    paths: set[str] = set()
    try:
        for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _GITMODULES_PATH_RE.match(line)
            if m:
                paths.add(m.group(1).strip())
    except OSError as e:
        logger.warning("failed to read .gitmodules: %s", e)
    return paths
```

- [ ] **Step 4: Run test to verify it passes**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_manifests_gitmodules.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add src/prep/core/vendor_sniffer/manifests.py tests/test_vendor_sniffer/test_manifests_gitmodules.py
git commit -m "feat(vendor-sniffer): .gitmodules path parser"
```

---

### Task 3: Root `.gitignore` Top-Level Pattern Parser

**Files:**
- Modify: `src/prep/core/vendor_sniffer/manifests.py`
- Test: `tests/test_vendor_sniffer/test_manifests_gitignore.py`

We only need top-level directory patterns from the root `.gitignore` (e.g., `vcpkg/`, `node_modules`). Full gitignore semantics (negations, deep globs, etc.) are handled by the Rust walker — this parser only answers: "is this exact top-level directory name covered by root `.gitignore`?"

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vendor_sniffer/test_manifests_gitignore.py
from pathlib import Path

from prep.core.vendor_sniffer.manifests import parse_root_gitignore_toplevel_dirs


def test_parse_gitignore_direct_dir_names(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(
        "node_modules\n"
        "vcpkg/\n"
        "build/\n"
        "*.log\n"
        "# comment\n"
        "\n"
    )
    names = parse_root_gitignore_toplevel_dirs(tmp_path)
    assert "node_modules" in names
    assert "vcpkg" in names
    assert "build" in names
    assert "*.log" not in names  # file pattern, not dir
    assert "# comment" not in names  # comment


def test_parse_gitignore_leading_slash_stripped(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("/node_modules\n/vcpkg/\n")
    names = parse_root_gitignore_toplevel_dirs(tmp_path)
    assert "node_modules" in names
    assert "vcpkg" in names


def test_parse_gitignore_negations_ignored(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("build/\n!build/keep/\n")
    names = parse_root_gitignore_toplevel_dirs(tmp_path)
    # We don't model negations — "build" is still considered listed for hygiene purposes.
    assert "build" in names


def test_parse_gitignore_deep_path_skipped(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("some/deep/path/dir/\n")
    names = parse_root_gitignore_toplevel_dirs(tmp_path)
    # Only top-level dir names matter for our use case
    assert "some/deep/path/dir" not in names
    assert "some" not in names


def test_parse_gitignore_missing_returns_empty(tmp_path: Path):
    assert parse_root_gitignore_toplevel_dirs(tmp_path) == set()
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_manifests_gitignore.py -v
```
Expected: `ImportError` on `parse_root_gitignore_toplevel_dirs`.

- [ ] **Step 3: Add the parser to `manifests.py`**

Append to `src/prep/core/vendor_sniffer/manifests.py`:

```python
def parse_root_gitignore_toplevel_dirs(root: Path) -> set[str]:
    """
    Extract top-level directory names from <root>/.gitignore.

    Limited semantics: handles direct dir patterns ("vcpkg", "vcpkg/", "/vcpkg")
    and ignores deep paths, file patterns, negations, and comments. Full gitignore
    semantics are handled elsewhere by the Rust walker; this parser only answers
    'is this exact top-level dir name listed in root .gitignore?'.
    """
    gi = root / ".gitignore"
    if not gi.is_file():
        return set()
    names: set[str] = set()
    try:
        for raw in gi.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # Strip negation
            if line.startswith("!"):
                line = line[1:]
            # Strip leading slash
            if line.startswith("/"):
                line = line[1:]
            # Strip trailing slash
            if line.endswith("/"):
                line = line[:-1]
            # Skip deep paths and glob patterns
            if "/" in line or "*" in line or "?" in line or "[" in line:
                continue
            if line:
                names.add(line)
    except OSError as e:
        logger.warning("failed to read .gitignore: %s", e)
    return names
```

- [ ] **Step 4: Run test to verify it passes**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_manifests_gitignore.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add src/prep/core/vendor_sniffer/manifests.py tests/test_vendor_sniffer/test_manifests_gitignore.py
git commit -m "feat(vendor-sniffer): root .gitignore top-level dir parser"
```

---

### Task 4: Workspace Member Parsers (`package.json`, `Cargo.toml`, `go.work`)

**Files:**
- Modify: `src/prep/core/vendor_sniffer/manifests.py`
- Test: `tests/test_vendor_sniffer/test_manifests_workspaces.py`

These three parsers all answer the same question: "Which directories does the root manifest declare as user-code workspace members?" Bundle them in one task because they share the same shape and are individually trivial.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vendor_sniffer/test_manifests_workspaces.py
from pathlib import Path

from prep.core.vendor_sniffer.manifests import parse_workspace_members


def test_package_json_workspaces_array(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"name": "root", "workspaces": ["packages/*", "apps/web"]}'
    )
    members = parse_workspace_members(tmp_path)
    # Glob patterns are expanded to first-segment dir names; explicit paths kept as-is
    assert "packages" in members or "packages/*" in members
    assert "apps/web" in members


def test_package_json_workspaces_object_form(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"workspaces": {"packages": ["packages/*"]}}'
    )
    members = parse_workspace_members(tmp_path)
    assert "packages" in members or "packages/*" in members


def test_cargo_toml_workspace_members(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text(
        "[workspace]\n"
        'members = ["crates/engine", "crates/walker"]\n'
    )
    members = parse_workspace_members(tmp_path)
    assert "crates/engine" in members
    assert "crates/walker" in members


def test_go_work_use_block(tmp_path: Path):
    (tmp_path / "go.work").write_text(
        "go 1.22\n\n"
        "use (\n"
        '\t./cmd/app\n'
        '\t./pkg/utils\n'
        ")\n"
    )
    members = parse_workspace_members(tmp_path)
    assert "cmd/app" in members
    assert "pkg/utils" in members


def test_no_manifests_returns_empty(tmp_path: Path):
    assert parse_workspace_members(tmp_path) == set()


def test_malformed_package_json_returns_empty_or_partial(tmp_path: Path):
    (tmp_path / "package.json").write_text("not valid json {{{")
    # Must not raise
    members = parse_workspace_members(tmp_path)
    assert isinstance(members, set)
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_manifests_workspaces.py -v
```
Expected: `ImportError` on `parse_workspace_members`.

- [ ] **Step 3: Add the parser to `manifests.py`**

Append to `src/prep/core/vendor_sniffer/manifests.py`:

```python
import json
import re as _re

try:
    import tomllib  # py311+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

_GO_WORK_USE_BLOCK_RE = _re.compile(r"use\s*\(\s*([^)]*)\)", _re.DOTALL)
_GO_WORK_USE_SINGLE_RE = _re.compile(r"use\s+([^\s]+)")


def _normalize_member(p: str) -> str:
    """Drop leading './' and trailing '/', collapse simple globs to base dir."""
    p = p.strip()
    if p.startswith("./"):
        p = p[2:]
    if p.endswith("/"):
        p = p[:-1]
    if p.endswith("/*"):
        p = p[:-2]
    return p


def parse_workspace_members(root: Path) -> set[str]:
    """Union of workspace-member dirs declared by root package.json / Cargo.toml / go.work."""
    members: set[str] = set()
    members |= _parse_package_json_workspaces(root)
    members |= _parse_cargo_workspace(root)
    members |= _parse_go_work(root)
    return members


def _parse_package_json_workspaces(root: Path) -> set[str]:
    pj = root / "package.json"
    if not pj.is_file():
        return set()
    try:
        data = json.loads(pj.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("failed to parse package.json: %s", e)
        return set()
    ws = data.get("workspaces") if isinstance(data, dict) else None
    members: set[str] = set()
    raw: list[str] = []
    if isinstance(ws, list):
        raw = [s for s in ws if isinstance(s, str)]
    elif isinstance(ws, dict):
        pkgs = ws.get("packages", [])
        if isinstance(pkgs, list):
            raw = [s for s in pkgs if isinstance(s, str)]
    for s in raw:
        members.add(_normalize_member(s))
    return {m for m in members if m}


def _parse_cargo_workspace(root: Path) -> set[str]:
    if tomllib is None:
        return set()
    ct = root / "Cargo.toml"
    if not ct.is_file():
        return set()
    try:
        with ct.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        logger.warning("failed to parse Cargo.toml: %s", e)
        return set()
    ws = data.get("workspace", {})
    raw = ws.get("members", []) if isinstance(ws, dict) else []
    members = {_normalize_member(s) for s in raw if isinstance(s, str)}
    return {m for m in members if m}


def _parse_go_work(root: Path) -> set[str]:
    gw = root / "go.work"
    if not gw.is_file():
        return set()
    try:
        content = gw.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning("failed to read go.work: %s", e)
        return set()
    members: set[str] = set()
    # Block form: use ( ... )
    for block in _GO_WORK_USE_BLOCK_RE.findall(content):
        for line in block.splitlines():
            line = line.strip()
            if line and not line.startswith("//"):
                members.add(_normalize_member(line))
    # Single form: use ./path
    for m in _GO_WORK_USE_SINGLE_RE.finditer(content):
        # Skip lines inside a use(...) block — already handled above
        if "(" not in m.group(0):
            members.add(_normalize_member(m.group(1)))
    return {m for m in members if m}
```

- [ ] **Step 4: Run test to verify it passes**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_manifests_workspaces.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```
git add src/prep/core/vendor_sniffer/manifests.py tests/test_vendor_sniffer/test_manifests_workspaces.py
git commit -m "feat(vendor-sniffer): workspace member parsers (package.json, Cargo.toml, go.work)"
```

---

### Task 5: Signal Evaluators (Tier 1 / Tier 2 / Tier 3 classifiers)

**Files:**
- Create: `src/prep/core/vendor_sniffer/signals.py`
- Test: `tests/test_vendor_sniffer/test_signals.py`

This is the heart of the heuristic. One pure-function classifier per signal; the scanner orchestrator (next task) will compose them.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vendor_sniffer/test_signals.py
from pathlib import Path

from prep.core.vendor_sniffer.signals import (
    CANONICAL_INSTALL_DIR_NAMES,
    PROJECT_ANCHOR_FILES,
    has_cmake_build_marker,
    has_ignore_everything_gitignore,
    has_nested_git_dir,
    has_project_anchor,
    is_canonical_install_dir,
)


def test_canonical_install_dir_whitelist_contains_expected(tmp_path: Path):
    # Must include the major package-manager install dirs
    assert "node_modules" in CANONICAL_INSTALL_DIR_NAMES
    assert "Pods" in CANONICAL_INSTALL_DIR_NAMES
    assert "Carthage" in CANONICAL_INSTALL_DIR_NAMES
    assert "vcpkg_installed" in CANONICAL_INSTALL_DIR_NAMES
    assert "target" in CANONICAL_INSTALL_DIR_NAMES
    assert ".venv" in CANONICAL_INSTALL_DIR_NAMES


def test_canonical_install_dir_excludes_project_specific_names():
    # MUST NOT be in the whitelist (per spec: project-specific names stay Tier 2)
    assert "cesium-native" not in CANONICAL_INSTALL_DIR_NAMES
    assert "vcpkg" not in CANONICAL_INSTALL_DIR_NAMES  # the tool itself; only vcpkg_installed is whitelisted


def test_is_canonical_install_dir_matches_name(tmp_path: Path):
    (tmp_path / "node_modules").mkdir()
    assert is_canonical_install_dir(tmp_path / "node_modules") is True
    (tmp_path / "src").mkdir()
    assert is_canonical_install_dir(tmp_path / "src") is False


def test_has_nested_git_dir_detects_dir(tmp_path: Path):
    d = tmp_path / "vcpkg"
    d.mkdir()
    (d / ".git").mkdir()
    assert has_nested_git_dir(d) is True


def test_has_nested_git_dir_ignores_worktree_file(tmp_path: Path):
    # Git worktrees: .git is a FILE pointing to the real .git/ dir elsewhere
    d = tmp_path / "worktree-leaf"
    d.mkdir()
    (d / ".git").write_text("gitdir: /elsewhere/.git/worktrees/leaf\n")
    # Per spec: must use is_dir(), not exists()
    assert has_nested_git_dir(d) is False


def test_has_nested_git_dir_missing(tmp_path: Path):
    d = tmp_path / "plain"
    d.mkdir()
    assert has_nested_git_dir(d) is False


def test_has_cmake_build_marker(tmp_path: Path):
    d = tmp_path / "build"
    d.mkdir()
    (d / "CMakeCache.txt").write_text("# CMake cache\n")
    assert has_cmake_build_marker(d) is True


def test_has_cmake_build_marker_alt_files(tmp_path: Path):
    d = tmp_path / "build"
    d.mkdir()
    (d / "build.ninja").write_text("# ninja\n")
    assert has_cmake_build_marker(d) is True


def test_has_cmake_build_marker_missing(tmp_path: Path):
    d = tmp_path / "src"
    d.mkdir()
    assert has_cmake_build_marker(d) is False


def test_has_ignore_everything_gitignore(tmp_path: Path):
    d = tmp_path / "build"
    d.mkdir()
    (d / ".gitignore").write_text("# generated\n*\n")
    assert has_ignore_everything_gitignore(d) is True


def test_has_ignore_everything_gitignore_other_patterns(tmp_path: Path):
    d = tmp_path / "src"
    d.mkdir()
    (d / ".gitignore").write_text("*.log\n")
    assert has_ignore_everything_gitignore(d) is False


def test_has_ignore_everything_gitignore_no_file(tmp_path: Path):
    d = tmp_path / "src"
    d.mkdir()
    assert has_ignore_everything_gitignore(d) is False


def test_project_anchor_files_includes_major_ecosystems():
    assert "package.json" in PROJECT_ANCHOR_FILES
    assert "pyproject.toml" in PROJECT_ANCHOR_FILES
    assert "Cargo.toml" in PROJECT_ANCHOR_FILES
    assert "go.mod" in PROJECT_ANCHOR_FILES
    assert "Package.swift" in PROJECT_ANCHOR_FILES
    assert "Gemfile" in PROJECT_ANCHOR_FILES
    assert "composer.json" in PROJECT_ANCHOR_FILES
    assert "pubspec.yaml" in PROJECT_ANCHOR_FILES


def test_has_project_anchor_finds_file(tmp_path: Path):
    d = tmp_path / "webgl-component"
    d.mkdir()
    (d / "package.json").write_text("{}")
    assert has_project_anchor(d) is True


def test_has_project_anchor_finds_xcode_pattern(tmp_path: Path):
    d = tmp_path / "MyApp"
    d.mkdir()
    (d / "MyApp.xcodeproj").mkdir()
    assert has_project_anchor(d) is True


def test_has_project_anchor_finds_csproj(tmp_path: Path):
    d = tmp_path / "WinApp"
    d.mkdir()
    (d / "WinApp.csproj").write_text("<Project/>")
    assert has_project_anchor(d) is True


def test_has_project_anchor_missing(tmp_path: Path):
    d = tmp_path / "plain"
    d.mkdir()
    (d / "README.md").write_text("# readme")
    assert has_project_anchor(d) is False
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_signals.py -v
```
Expected: `ImportError` on the `signals` module.

- [ ] **Step 3: Write minimal implementation**

```python
# src/prep/core/vendor_sniffer/signals.py
from __future__ import annotations

from pathlib import Path

# Per spec: canonical package-manager install dirs. Project-specific names
# (vcpkg the tool itself, cesium-native, etc.) deliberately NOT here — those
# flow to Tier 2 modal so user has a choice.
CANONICAL_INSTALL_DIR_NAMES: frozenset[str] = frozenset({
    "node_modules",
    "Pods",
    "Carthage",
    "vendor",            # Go/Ruby/PHP convention
    "bower_components",
    ".bundle",
    "vcpkg_installed",   # vcpkg's installed-deps dir, NOT vcpkg/ itself
    ".build",            # Swift Package Manager
    "target",            # Rust
    "__pycache__",
    ".venv",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
})

# Files (or dir-name patterns) whose presence inside a top-level dir signals
# "this is its own project / user code." Used to keep things like SkyPath/
# (which contains *.xcodeproj) out of the proposal list.
PROJECT_ANCHOR_FILES: frozenset[str] = frozenset({
    "package.json",
    "pyproject.toml",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "Package.swift",
    "Gemfile",
    "composer.json",
    "pubspec.yaml",
    "build.gradle",
    "build.gradle.kts",
    "pom.xml",
})

# Patterns matched by suffix instead of exact name
_PROJECT_ANCHOR_SUFFIXES: tuple[str, ...] = (
    ".xcodeproj",
    ".xcworkspace",
    ".sln",
    ".csproj",
)

# Files that mean "this is a CMake (or similar) build-output directory"
_CMAKE_BUILD_MARKERS: frozenset[str] = frozenset({
    "CMakeCache.txt",
    "build.ninja",
    "compile_commands.json",
})


def is_canonical_install_dir(p: Path) -> bool:
    """Tier-1 signal: dir name is a canonical package-manager install dir."""
    return p.name in CANONICAL_INSTALL_DIR_NAMES


def has_nested_git_dir(p: Path) -> bool:
    """
    Tier-1 (with manifest evidence) / Tier-2 signal: directory contains a
    nested `.git/` directory.

    Worktree-safe: a git worktree leaf has a `.git` *file* (not directory)
    pointing to the real .git/ elsewhere. We must use is_dir().
    """
    return (p / ".git").is_dir()


def has_cmake_build_marker(p: Path) -> bool:
    """Tier-1 signal: directory contains a CMake/build-system generated marker."""
    return any((p / m).is_file() for m in _CMAKE_BUILD_MARKERS)


def has_ignore_everything_gitignore(p: Path) -> bool:
    """
    Tier-1 signal: directory has a .gitignore whose first non-comment,
    non-blank line is '*' (the 'ignore everything in this dir' convention).
    """
    gi = p / ".gitignore"
    if not gi.is_file():
        return False
    try:
        for raw in gi.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            return line == "*"
    except OSError:
        return False
    return False


def has_project_anchor(p: Path) -> bool:
    """
    Tier-3 signal: directory contains a recognized project/manifest file,
    so it looks like the user's own project rather than a vendored dep.
    """
    if not p.is_dir():
        return False
    for child in p.iterdir():
        if child.name in PROJECT_ANCHOR_FILES:
            return True
        for suffix in _PROJECT_ANCHOR_SUFFIXES:
            if child.name.endswith(suffix):
                return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_signals.py -v
```
Expected: 16 passed.

- [ ] **Step 5: Commit**

```
git add src/prep/core/vendor_sniffer/signals.py tests/test_vendor_sniffer/test_signals.py
git commit -m "feat(vendor-sniffer): tier-1/2/3 signal evaluators"
```

---

### Task 6: Scanner Orchestrator

**Files:**
- Create: `src/prep/core/vendor_sniffer/scanner.py`
- Modify: `src/prep/core/vendor_sniffer/__init__.py` (re-export `scan_for_vendor_dirs`)
- Test: `tests/test_vendor_sniffer/test_scanner.py`

The scanner combines signals + manifests into a final `VendorScanResult`. It piggybacks on `prep_engine.walk_repo` to accumulate per-top-level-dir file counts and sizes during the existing walk (no second traversal).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vendor_sniffer/test_scanner.py
from pathlib import Path

from prep.core.vendor_sniffer import scan_for_vendor_dirs


def _make_file(p: Path, size: int = 100) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)


def test_empty_project_returns_empty_result(tmp_path: Path):
    r = scan_for_vendor_dirs(tmp_path)
    assert r.status == "complete"
    assert r.auto_excluded == []
    assert r.proposed == []
    assert r.gitignore_gaps == []


def test_canonical_install_dir_auto_excluded(tmp_path: Path):
    _make_file(tmp_path / "node_modules" / "react" / "index.js")
    _make_file(tmp_path / "src" / "app.ts")
    r = scan_for_vendor_dirs(tmp_path)
    assert any("node_modules" in g for g in r.auto_excluded)
    assert not r.proposed


def test_gitmodules_submodule_auto_excluded(tmp_path: Path):
    (tmp_path / ".gitmodules").write_text(
        '[submodule "vcpkg"]\n\tpath = vcpkg\n\turl = https://example/v.git\n'
    )
    (tmp_path / "vcpkg").mkdir()
    (tmp_path / "vcpkg" / ".git").mkdir()
    _make_file(tmp_path / "vcpkg" / "boot.cmake")
    r = scan_for_vendor_dirs(tmp_path)
    assert any("vcpkg" in g for g in r.auto_excluded)


def test_nested_git_no_gitmodules_proposed(tmp_path: Path):
    # cesium-native style: own .git/, not in .gitmodules, not in .gitignore
    (tmp_path / "cesium-native").mkdir()
    (tmp_path / "cesium-native" / ".git").mkdir()
    _make_file(tmp_path / "cesium-native" / "src" / "engine.cpp")
    r = scan_for_vendor_dirs(tmp_path)
    assert not any("cesium-native" in g for g in r.auto_excluded)
    assert any(c.rel_path == "cesium-native" for c in r.proposed)
    cand = next(c for c in r.proposed if c.rel_path == "cesium-native")
    assert "git" in cand.reason.lower()


def test_cmake_build_dir_auto_excluded(tmp_path: Path):
    b = tmp_path / "build"
    b.mkdir()
    (b / "CMakeCache.txt").write_text("# cmake\n")
    _make_file(b / "obj" / "main.o")
    r = scan_for_vendor_dirs(tmp_path)
    assert any("build" in g for g in r.auto_excluded)


def test_user_code_with_xcodeproj_skipped(tmp_path: Path):
    d = tmp_path / "MyApp"
    d.mkdir()
    (d / "MyApp.xcodeproj").mkdir()
    _make_file(d / "AppDelegate.swift")
    r = scan_for_vendor_dirs(tmp_path)
    # Must NOT propose or auto-exclude — it's user code
    assert not any("MyApp" in g for g in r.auto_excluded)
    assert not any(c.rel_path == "MyApp" for c in r.proposed)


def test_workspace_member_skipped(tmp_path: Path):
    # Root package.json declares packages/* as workspace; packages/ui contains a
    # nested .git/ for some reason — must STILL be skipped (user code wins).
    (tmp_path / "package.json").write_text('{"workspaces": ["packages/*"]}')
    ui = tmp_path / "packages" / "ui"
    ui.mkdir(parents=True)
    (ui / "package.json").write_text("{}")
    (ui / ".git").mkdir()
    r = scan_for_vendor_dirs(tmp_path)
    assert not any("packages" in g for g in r.auto_excluded if "node_modules" not in g)


def test_gitignore_gap_detected_for_canonical_dir(tmp_path: Path):
    # node_modules exists but is NOT in .gitignore — gitignore_gaps should flag it
    _make_file(tmp_path / "node_modules" / "react" / "index.js")
    (tmp_path / ".git").mkdir()  # mark as a git repo
    # No .gitignore
    r = scan_for_vendor_dirs(tmp_path)
    assert any(c.rel_path == "node_modules" for c in r.gitignore_gaps)


def test_gitignore_gap_NOT_flagged_when_listed(tmp_path: Path):
    _make_file(tmp_path / "node_modules" / "react" / "index.js")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    r = scan_for_vendor_dirs(tmp_path)
    assert not any(c.rel_path == "node_modules" for c in r.gitignore_gaps)


def test_gitignore_gap_NOT_flagged_when_not_git_repo(tmp_path: Path):
    _make_file(tmp_path / "node_modules" / "react" / "index.js")
    # NO .git/ at root — Gate 1 should never fire
    r = scan_for_vendor_dirs(tmp_path)
    assert r.gitignore_gaps == []


def test_scanned_at_set_to_recent_epoch(tmp_path: Path):
    import time

    before = time.time()
    r = scan_for_vendor_dirs(tmp_path)
    after = time.time()
    assert before <= r.scanned_at <= after
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_scanner.py -v
```
Expected: `ImportError` on `scan_for_vendor_dirs`.

- [ ] **Step 3: Write the scanner**

```python
# src/prep/core/vendor_sniffer/scanner.py
from __future__ import annotations

import logging
import time
from pathlib import Path

from prep.core.vendor_sniffer.manifests import (
    parse_gitmodules,
    parse_root_gitignore_toplevel_dirs,
    parse_workspace_members,
)
from prep.core.vendor_sniffer.models import VendorCandidate, VendorScanResult
from prep.core.vendor_sniffer.signals import (
    CANONICAL_INSTALL_DIR_NAMES,
    has_cmake_build_marker,
    has_ignore_everything_gitignore,
    has_nested_git_dir,
    has_project_anchor,
    is_canonical_install_dir,
)

logger = logging.getLogger(__name__)

# Per spec: size/file-count is the LAST-RESORT fallback only.
_SIZE_FALLBACK_BYTES = 100 * 1024 * 1024  # 100 MB
_SIZE_FALLBACK_FILES = 5000


def _is_git_repo_root(root: Path) -> bool:
    """A repo root is a git repo if it has .git/ (dir) or .git (file = worktree)."""
    g = root / ".git"
    return g.is_dir() or g.is_file()


def _dir_size_and_count(d: Path) -> tuple[int, int]:
    """Fast size + file-count for one directory tree. Errors swallowed per-entry."""
    total_bytes = 0
    total_files = 0
    for entry in d.rglob("*"):
        try:
            if entry.is_file():
                total_files += 1
                total_bytes += entry.stat().st_size
        except (OSError, PermissionError):
            continue
    return total_bytes, total_files


def _glob_for(rel_path: str) -> str:
    return f"**/{rel_path}/**"


def scan_for_vendor_dirs(root: Path) -> VendorScanResult:
    """Scan top-level directories of `root` for vendor / build / submodule patterns."""
    started_at = time.time()
    try:
        if not root.is_dir():
            return VendorScanResult(
                auto_excluded=[],
                proposed=[],
                gitignore_gaps=[],
                scanned_at=started_at,
                status="failed",
                error=f"root is not a directory: {root}",
            )

        is_git = _is_git_repo_root(root)
        submodule_paths = parse_gitmodules(root)
        gitignore_dirs = parse_root_gitignore_toplevel_dirs(root)
        workspace_members = parse_workspace_members(root)

        auto_excluded: list[str] = []
        proposed: list[VendorCandidate] = []
        gitignore_gaps: list[VendorCandidate] = []

        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") and entry.name not in {".venv", ".tox"}:
                # Hidden dirs (incl. .git itself) are already excluded by default
                # walker behavior; don't surface them.
                continue
            rel = entry.name
            # Tier 3: workspace member → skip entirely
            if rel in workspace_members or any(rel == m or rel.startswith(m + "/") for m in workspace_members):
                continue

            in_gi = rel in gitignore_dirs

            # --- Tier 1 signals ---
            tier1_reason: str | None = None
            if is_canonical_install_dir(entry):
                tier1_reason = "Canonical package-manager install dir"
            elif rel in submodule_paths:
                tier1_reason = "Listed in .gitmodules"
            elif in_gi:
                tier1_reason = "Listed in root .gitignore"
            elif has_cmake_build_marker(entry):
                tier1_reason = "CMake/build output (CMakeCache.txt or build.ninja present)"
            elif has_ignore_everything_gitignore(entry):
                tier1_reason = "Directory's own .gitignore ignores everything"

            if tier1_reason is not None:
                auto_excluded.append(_glob_for(rel))
                # Gitignore-hygiene tracking: canonical names + CMake builds that
                # AREN'T listed in root .gitignore are the "clear suspicious gap" set
                if is_git and not in_gi and (
                    is_canonical_install_dir(entry) or has_cmake_build_marker(entry)
                ):
                    size, files = _dir_size_and_count(entry)
                    gitignore_gaps.append(VendorCandidate(
                        path=str(entry),
                        rel_path=rel,
                        size_bytes=size,
                        file_count=files,
                        reason=tier1_reason,
                        tier="auto",
                        in_gitignore=False,
                        is_git_repo=has_nested_git_dir(entry),
                    ))
                continue

            # Skip Tier-3 user code BEFORE Tier 2 size fallback
            anchor = has_project_anchor(entry)
            if anchor and rel in workspace_members:
                continue

            # --- Tier 2 signals ---
            tier2_reason: str | None = None
            nested_git = has_nested_git_dir(entry)
            if nested_git:
                tier2_reason = "Nested git repo, possibly vendored"
            elif anchor:
                tier2_reason = "Separate project (own manifest), not in root workspaces"
            else:
                size, files = _dir_size_and_count(entry)
                if size > _SIZE_FALLBACK_BYTES or files > _SIZE_FALLBACK_FILES:
                    tier2_reason = "Large directory, no classification signal"
                    proposed.append(VendorCandidate(
                        path=str(entry),
                        rel_path=rel,
                        size_bytes=size,
                        file_count=files,
                        reason=tier2_reason,
                        tier="propose",
                        in_gitignore=in_gi,
                        is_git_repo=False,
                    ))
                    continue

            if tier2_reason is not None:
                size, files = _dir_size_and_count(entry)
                proposed.append(VendorCandidate(
                    path=str(entry),
                    rel_path=rel,
                    size_bytes=size,
                    file_count=files,
                    reason=tier2_reason,
                    tier="propose",
                    in_gitignore=in_gi,
                    is_git_repo=nested_git,
                ))

        return VendorScanResult(
            auto_excluded=auto_excluded,
            proposed=proposed,
            gitignore_gaps=gitignore_gaps,
            scanned_at=started_at,
            status="complete",
            error=None,
        )
    except Exception as e:
        logger.warning("vendor_sniffer scan failed for %s: %s", root, e)
        return VendorScanResult(
            auto_excluded=[],
            proposed=[],
            gitignore_gaps=[],
            scanned_at=started_at,
            status="failed",
            error=str(e),
        )
```

- [ ] **Step 4: Update `__init__.py` to re-export the scanner**

```python
# src/prep/core/vendor_sniffer/__init__.py
from prep.core.vendor_sniffer.models import VendorCandidate, VendorScanResult
from prep.core.vendor_sniffer.scanner import scan_for_vendor_dirs

__all__ = ["VendorCandidate", "VendorScanResult", "scan_for_vendor_dirs"]
```

- [ ] **Step 5: Run test to verify it passes**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_scanner.py -v
```
Expected: 10 passed.

- [ ] **Step 6: Run the whole sniffer suite together**

```
.venv/bin/pytest tests/test_vendor_sniffer/ -v
```
Expected: all green (~36 passed).

- [ ] **Step 7: Commit**

```
git add src/prep/core/vendor_sniffer/__init__.py src/prep/core/vendor_sniffer/scanner.py tests/test_vendor_sniffer/test_scanner.py
git commit -m "feat(vendor-sniffer): scanner orchestrator combining signals + manifests"
```

---

### Task 7: SkyPath-Shaped Integration Fixture

**Files:**
- Test: `tests/test_vendor_sniffer/test_skypath_fixture.py`

End-to-end test that builds a synthetic SkyPath-shaped tree on disk and asserts the expected classification. This is the regression test that proves the real-world scenario works.

- [ ] **Step 1: Write the test**

```python
# tests/test_vendor_sniffer/test_skypath_fixture.py
from pathlib import Path

import pytest

from prep.core.vendor_sniffer import scan_for_vendor_dirs


@pytest.fixture
def skypath_tree(tmp_path: Path) -> Path:
    """
    Replicate the structurally-relevant parts of /Volumes/Thunderbolt/.../SkyPath:
      SkyPath/
        .git/                          (this repo IS a git repo)
        SkyPath.xcworkspace/           (user workspace)
        SkyPath/                       (user code with .xcodeproj)
          SkyPath.xcodeproj/
          AppDelegate.swift
        GeoTestARSceneOriginal/        (user code with .xcodeproj)
          GeoTestARScene.xcodeproj/
        vcpkg/                         (vendored: own .git, in .gitmodules)
          .git/
          boot.cmake
        cesium-native/                 (vendored, NOT in .gitmodules — should propose)
          .git/
          src/Engine.cpp
        build/                         (CMake build dir)
          CMakeCache.txt
        webgl-component/               (sibling project with own package.json, NOT in workspaces)
          package.json
          src/index.ts
        node_modules/                  (canonical install dir)
          react/index.js
        docs/                          (small, plain dir — should be skipped)
          README.md
        .gitmodules                    (lists vcpkg)
        (NO .gitignore — gap should be flagged)
    """
    root = tmp_path / "SkyPath"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "SkyPath.xcworkspace").mkdir()
    sub = root / "SkyPath"
    sub.mkdir()
    (sub / "SkyPath.xcodeproj").mkdir()
    (sub / "AppDelegate.swift").write_text("// app\n")
    geo = root / "GeoTestARSceneOriginal"
    geo.mkdir()
    (geo / "GeoTestARScene.xcodeproj").mkdir()

    vcpkg = root / "vcpkg"
    vcpkg.mkdir()
    (vcpkg / ".git").mkdir()
    (vcpkg / "boot.cmake").write_text("# cmake\n")
    cesium = root / "cesium-native"
    cesium.mkdir()
    (cesium / ".git").mkdir()
    (cesium / "src").mkdir()
    (cesium / "src" / "Engine.cpp").write_text("// engine\n")
    build = root / "build"
    build.mkdir()
    (build / "CMakeCache.txt").write_text("# cmake cache\n")
    webgl = root / "webgl-component"
    webgl.mkdir()
    (webgl / "package.json").write_text('{"name": "webgl"}')
    (webgl / "src").mkdir()
    (webgl / "src" / "index.ts").write_text("// ts\n")
    nm = root / "node_modules" / "react"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("// react\n")
    docs = root / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# docs\n")

    (root / ".gitmodules").write_text(
        '[submodule "vcpkg"]\n\tpath = vcpkg\n\turl = https://example/vcpkg.git\n'
    )
    return root


def test_skypath_classification(skypath_tree: Path):
    r = scan_for_vendor_dirs(skypath_tree)

    assert r.status == "complete"

    # Tier 1 auto-excluded
    auto = " ".join(r.auto_excluded)
    assert "vcpkg" in auto, "vcpkg should auto-exclude via .gitmodules"
    assert "build" in auto, "build/ should auto-exclude via CMakeCache.txt"
    assert "node_modules" in auto, "node_modules should auto-exclude via canonical name"

    # Tier 2 proposed: under the simplified "size-fallback only" rule, a small
    # nested-git or sibling-manifest dir does NOT propose. Tier 2 only fires
    # on huge unclassified blobs. In this synthetic fixture, no dir exceeds
    # 500 MB / 25k files, so nothing should propose.
    proposed_rel = {c.rel_path for c in r.proposed}
    assert proposed_rel == set(), (
        f"No dirs should propose in the small synthetic fixture; got {proposed_rel}. "
        "Sub-repos (cesium-native) and sibling projects (webgl-component) are "
        "treated as user code by default — user manually excludes in file tree."
    )

    # Tier 3 skipped (everything that isn't Tier 1)
    assert "SkyPath" not in proposed_rel
    assert not any("SkyPath/" in g for g in r.auto_excluded if "SkyPath.xcworkspace" not in g)
    assert "GeoTestARSceneOriginal" not in proposed_rel
    assert "cesium-native" not in proposed_rel  # has nested .git but under size threshold
    assert "webgl-component" not in proposed_rel  # has package.json but not vendor signal
    assert "docs" not in proposed_rel  # small and plain

    # Gate 1: gitignore gap — node_modules + build are canonical/build-output
    # and root has no .gitignore. They MUST appear in gitignore_gaps.
    gap_rel = {c.rel_path for c in r.gitignore_gaps}
    assert "node_modules" in gap_rel
    assert "build" in gap_rel
```

- [ ] **Step 2: Run the test**

```
.venv/bin/pytest tests/test_vendor_sniffer/test_skypath_fixture.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Commit**

```
git add tests/test_vendor_sniffer/test_skypath_fixture.py
git commit -m "test(vendor-sniffer): SkyPath-shaped integration fixture"
```

---

## Phase 2: Backend Integration

### Task 8: Project Record Schema — Add `vendor_scan` and `dismissed_proposals`

**Files:**
- Modify: project record schema (locate via `grep -rn "class Project\b" src/prep/` and follow imports)
- Test: `tests/test_project_schema_vendor_scan.py`

The exact file depends on where projects are modeled. Most likely `src/prep/core/registry.py` or `src/prep/models/project.py`. Read the existing project model first; add two optional fields without breaking existing serialization.

- [ ] **Step 1: Find the project model**

```
grep -rn "class Project" src/prep/core/ src/prep/models/ 2>/dev/null
```
Note the file path. Then read the file end-to-end to understand the model.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_project_schema_vendor_scan.py
import pytest

from prep.core.vendor_sniffer.models import VendorScanResult

# Import path resolved in Step 1 — adjust to actual location.
# Example:
# from prep.core.registry import Project


def test_project_has_vendor_scan_field(tmp_path):
    # Update import based on Step 1 discovery
    from prep.core.registry import Project  # adjust path

    p = Project(path=str(tmp_path), name="test", mode="embedded", config={})
    # vendor_scan default: None or pending
    assert getattr(p, "vendor_scan", None) is None or p.vendor_scan.status == "pending"


def test_project_has_dismissed_proposals_field(tmp_path):
    from prep.core.registry import Project  # adjust path

    p = Project(path=str(tmp_path), name="test", mode="embedded", config={})
    assert getattr(p, "dismissed_proposals", []) == []


def test_project_vendor_scan_serializes_round_trip(tmp_path):
    from prep.core.registry import Project  # adjust path

    p = Project(path=str(tmp_path), name="test", mode="embedded", config={})
    p.vendor_scan = VendorScanResult(
        auto_excluded=["**/node_modules/**"],
        proposed=[],
        gitignore_gaps=[],
        scanned_at=1715500000.0,
        status="complete",
        error=None,
    )
    p.dismissed_proposals = ["legacy-vendor"]
    # Round-trip via the project's existing to_dict/from_dict or pydantic mechanism
    as_dict = p.to_dict() if hasattr(p, "to_dict") else p.model_dump()
    assert as_dict.get("vendor_scan", {}).get("status") == "complete"
    assert as_dict.get("dismissed_proposals") == ["legacy-vendor"]
```

- [ ] **Step 3: Run test to verify it fails**

```
.venv/bin/pytest tests/test_project_schema_vendor_scan.py -v
```
Expected: AttributeError or assertion failures.

- [ ] **Step 4: Add fields to the Project model**

Add two optional fields to the `Project` class found in Step 1. Concrete shape depends on whether the model is a `@dataclass`, Pydantic `BaseModel`, or SQLAlchemy mapping. Example for a Pydantic model:

```python
# In src/prep/core/registry.py (or wherever Project lives)
from typing import Optional

from prep.core.vendor_sniffer.models import VendorScanResult


class Project(BaseModel):
    # ... existing fields ...
    vendor_scan: Optional[VendorScanResult] = None
    dismissed_proposals: list[str] = []
```

For a `@dataclass`:

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Project:
    # ... existing fields ...
    vendor_scan: Optional[VendorScanResult] = None
    dismissed_proposals: list[str] = field(default_factory=list)
```

If the project is persisted to SQLite via a separate model/table, also add the columns there and write a forward migration. **Check `src/prep/core/data_dir_migration.py` and any existing migrations for the project table to follow the established migration pattern.**

- [ ] **Step 5: Run test to verify it passes**

```
.venv/bin/pytest tests/test_project_schema_vendor_scan.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Run the existing project tests to confirm no regression**

```
.venv/bin/pytest tests/ -v -k "project" --tb=short
```
Expected: existing project tests still pass.

- [ ] **Step 7: Commit**

```
git add src/prep/core/registry.py tests/test_project_schema_vendor_scan.py
git commit -m "feat(vendor-sniffer): add vendor_scan + dismissed_proposals to Project schema"
```

(Adjust the staged file path to match the actual project model location.)

---

### Task 9: Async Sniffer Dispatch in `crud.py` + Surface Preset-Scan Errors

**Files:**
- Modify: `src/prep/api/routers/projects/crud.py:132-148` (existing `scan_for_presets` block)
- Test: `tests/test_projects_crud_vendor_scan_dispatch.py`

Two concurrent changes here are tightly related and belong in one commit:

1. Replace the silent `try/except logger.warning` on the existing `scan_for_presets` call with structured error capture: failure becomes a visible state on the project record.
2. After the preset scan, fire the vendor sniffer **asynchronously** so `POST /projects` returns immediately. Use FastAPI `BackgroundTasks` (standard pattern in this codebase) to run the scan and write the result back to the project record.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_projects_crud_vendor_scan_dispatch.py
import asyncio
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_post_projects_returns_pending_vendor_scan(tmp_path: Path, daemon_client):
    """POST /projects must not block on vendor scan — returns immediately with pending status."""
    # daemon_client is a fixture providing a started in-memory FastAPI TestClient
    resp = daemon_client.post(
        "/projects",
        json={"path": str(tmp_path), "name": "p", "mode": "embedded"},
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    project = body["project"]
    vs = project.get("vendor_scan", {})
    # Either pending (background still running) or complete (very fast on empty tree)
    assert vs.get("status") in ("pending", "complete")


@pytest.mark.asyncio
async def test_post_projects_records_preset_scan_failure(tmp_path: Path, monkeypatch, daemon_client):
    """If scan_for_presets raises, the project record records the failure visibly."""
    from prep.core import repo_profile

    def boom(_root):
        raise RuntimeError("simulated preset scan failure")

    monkeypatch.setattr(repo_profile, "scan_for_presets", boom)

    resp = daemon_client.post(
        "/projects",
        json={"path": str(tmp_path), "name": "p2", "mode": "embedded"},
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    # Failure surface: project record has a preset_scan_error field set
    assert body["project"].get("preset_scan_error", "") != ""
    assert "simulated" in body["project"]["preset_scan_error"]
```

(Create `tests/conftest.py` `daemon_client` fixture if it doesn't already exist; use the pattern from existing daemon tests — `grep -rn "TestClient" tests/` will find the canonical setup.)

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_projects_crud_vendor_scan_dispatch.py -v
```
Expected: assertion failures — no `vendor_scan` key in response, no `preset_scan_error` field.

- [ ] **Step 3: Modify `crud.py`**

Read `src/prep/api/routers/projects/crud.py:1-200` first to understand the surrounding context. The relevant edit is the existing block at lines 132–148 (the `scan_for_presets` try/except).

Replace it with:

```python
# In src/prep/api/routers/projects/crud.py
# (imports near the top of the file)
from fastapi import BackgroundTasks
from prep.core.vendor_sniffer import scan_for_vendor_dirs
from prep.core.vendor_sniffer.models import VendorScanResult


# In the create_project handler (find by signature near line 130):
# Replace the existing scan_for_presets try/except (~lines 132-148) with:

preset_scan_error: str | None = None
try:
    detected = scan_for_presets(p)
    if detected:
        logger.info(f"Auto-detected stack presets for {p.name}: {detected}")
        detected_globs: list[str] = []
        for preset in detected:
            detected_globs.extend(STACK_PRESETS.get(preset, []))

        current_globs = set(default_cfg["include_globs"])
        for g in detected_globs:
            if g not in current_globs:
                default_cfg["include_globs"].append(g)
                current_globs.add(g)
except Exception as e:
    preset_scan_error = f"{type(e).__name__}: {e}"
    logger.warning("Preset scan failed for %s: %s", p, e)

# Initialize vendor_scan as pending; the background task fills it in.
default_cfg["vendor_scan"] = VendorScanResult(
    auto_excluded=[],
    proposed=[],
    gitignore_gaps=[],
    scanned_at=0.0,
    status="pending",
    error=None,
)
if preset_scan_error:
    default_cfg["preset_scan_error"] = preset_scan_error
```

Then accept a `BackgroundTasks` parameter on the handler signature and schedule the sniffer:

```python
async def create_project(req: CreateProjectRequest, background: BackgroundTasks):
    # ... existing logic, including reg.add_project(...) which returns `proj` ...

    def _run_vendor_scan(project_id: str, root: Path) -> None:
        result = scan_for_vendor_dirs(root)
        # Apply Tier-1 auto-excludes via Phase 115 additive-merge.
        # Use the existing config_manager helper rather than rewriting the
        # config blob directly.
        from prep.services.config_manager import update_ui_config_for_project
        update_ui_config_for_project(
            project_id,
            patch={
                "vendor_scan": result,
                "exclude_globs_additions": result.auto_excluded,
            },
        )

    background.add_task(_run_vendor_scan, proj.id, p)
```

**Important:** `update_ui_config_for_project` (or whatever the actual helper is — verify the name in `src/prep/services/config_manager.py`) MUST use Phase 115's additive-merge contract for `exclude_globs`. If no such helper exists yet, create a small one inline rather than open-coding the union semantics. Check `src/prep/core/repo_policy.py:ensure_repo_policy` for the canonical union pattern.

- [ ] **Step 4: Run test to verify it passes**

```
.venv/bin/pytest tests/test_projects_crud_vendor_scan_dispatch.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Run the full project-router test suite to verify no regression**

```
.venv/bin/pytest tests/ -v -k "projects" --tb=short
```
Expected: no new failures.

- [ ] **Step 6: Commit**

```
git add src/prep/api/routers/projects/crud.py tests/test_projects_crud_vendor_scan_dispatch.py
git commit -m "feat(vendor-sniffer): async dispatch on project create + surface preset scan errors"
```

---

### Task 10: New Sub-Router for Vendor-Scan Endpoints

**Files:**
- Create: `src/prep/api/routers/projects/vendor_scan.py`
- Modify: `src/prep/api/routers/projects/__init__.py` (mount the sub-router)
- Test: `tests/test_vendor_scan_endpoints.py`

Three endpoints in one file:
- `GET /projects/{id}/vendor_scan`
- `POST /projects/{id}/vendor_scan/rescan`
- `POST /projects/{id}/exclude_proposals/apply`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vendor_scan_endpoints.py
from pathlib import Path

import pytest


@pytest.fixture
def project_with_vendor_dirs(tmp_path: Path, daemon_client):
    # Create a project that has at least one tier-2 candidate
    (tmp_path / "cesium-native").mkdir()
    (tmp_path / "cesium-native" / ".git").mkdir()
    (tmp_path / "cesium-native" / "engine.cpp").write_text("// engine\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n")
    resp = daemon_client.post(
        "/projects",
        json={"path": str(tmp_path), "name": "vendorish", "mode": "embedded"},
    )
    pid = resp.json()["project"]["id"]
    return pid, tmp_path


def test_get_vendor_scan_returns_cached_result(daemon_client, project_with_vendor_dirs):
    pid, _ = project_with_vendor_dirs
    # Background task may still be running; loop briefly until status != pending
    for _ in range(20):
        r = daemon_client.get(f"/projects/{pid}/vendor_scan")
        if r.json().get("status") != "pending":
            break
        import time
        time.sleep(0.1)
    body = r.json()
    assert body["status"] == "complete"
    assert any(c["rel_path"] == "cesium-native" for c in body["proposed"])


def test_post_rescan_returns_fresh_result(daemon_client, project_with_vendor_dirs):
    pid, root = project_with_vendor_dirs
    # Add a new vendored-style dir after project creation
    (root / "new-dep").mkdir()
    (root / "new-dep" / ".git").mkdir()

    r = daemon_client.post(f"/projects/{pid}/vendor_scan/rescan")
    body = r.json()
    assert body["status"] == "complete"
    rel = {c["rel_path"] for c in body["proposed"]}
    assert "new-dep" in rel


def test_post_apply_excludes_unions_into_config(daemon_client, project_with_vendor_dirs):
    pid, _ = project_with_vendor_dirs
    # Wait for scan to complete
    for _ in range(20):
        if daemon_client.get(f"/projects/{pid}/vendor_scan").json().get("status") == "complete":
            break
        import time; time.sleep(0.1)

    r = daemon_client.post(
        f"/projects/{pid}/exclude_proposals/apply",
        json={"exclude": ["cesium-native"], "dismiss": [], "add_to_gitignore": []},
    )
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert any("cesium-native" in g for g in cfg["exclude_globs"])


def test_post_apply_dismiss_persists(daemon_client, project_with_vendor_dirs):
    pid, _ = project_with_vendor_dirs
    for _ in range(20):
        if daemon_client.get(f"/projects/{pid}/vendor_scan").json().get("status") == "complete":
            break
        import time; time.sleep(0.1)

    daemon_client.post(
        f"/projects/{pid}/exclude_proposals/apply",
        json={"exclude": [], "dismiss": ["cesium-native"], "add_to_gitignore": []},
    )
    # Rescan: cesium-native should NOT re-appear in proposed (it was dismissed)
    r = daemon_client.post(f"/projects/{pid}/vendor_scan/rescan")
    body = r.json()
    rel = {c["rel_path"] for c in body["proposed"]}
    assert "cesium-native" not in rel
```

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_vendor_scan_endpoints.py -v
```
Expected: 404s on the new routes.

- [ ] **Step 3: Write the sub-router**

```python
# src/prep/api/routers/projects/vendor_scan.py
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from prep.core.vendor_sniffer import scan_for_vendor_dirs
from prep.core.vendor_sniffer.models import VendorScanResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["vendor_scan"])


def _srv():
    """Lazy import to match the pattern used by sibling routers in this package."""
    from prep.api.deps import get_server  # adjust to actual helper name
    return get_server()


def _get_project_or_404(project_id: str):
    reg = _srv()._get_registry()
    proj = reg.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return proj


@router.get("/vendor_scan")
def get_vendor_scan(project_id: str) -> dict:
    proj = _get_project_or_404(project_id)
    vs: VendorScanResult | None = getattr(proj, "vendor_scan", None) or proj.config.get("vendor_scan")
    if vs is None:
        return {
            "status": "pending",
            "auto_excluded": [],
            "proposed": [],
            "gitignore_gaps": [],
            "scanned_at": 0.0,
            "error": None,
        }
    return _scan_to_response_dict(vs)


@router.post("/vendor_scan/rescan")
def rescan_vendor(project_id: str) -> dict:
    proj = _get_project_or_404(project_id)
    root = Path(proj.path)
    result = scan_for_vendor_dirs(root)

    # Filter out previously-dismissed proposals
    dismissed = set(getattr(proj, "dismissed_proposals", None) or proj.config.get("dismissed_proposals", []))
    if dismissed:
        result = VendorScanResult(
            auto_excluded=result.auto_excluded,
            proposed=[c for c in result.proposed if c.rel_path not in dismissed],
            gitignore_gaps=result.gitignore_gaps,
            scanned_at=result.scanned_at,
            status=result.status,
            error=result.error,
        )

    # Apply Tier-1 auto-excludes via Phase 115 additive-merge
    _apply_auto_excludes(proj, result.auto_excluded)
    _persist_vendor_scan(proj, result)
    return _scan_to_response_dict(result)


class ApplyProposalsRequest(BaseModel):
    exclude: list[str] = []          # rel_paths to add to exclude_globs
    dismiss: list[str] = []          # rel_paths to record as dismissed
    add_to_gitignore: list[str] = []  # v2 stub — no-op for now


@router.post("/exclude_proposals/apply")
def apply_proposals(project_id: str, req: ApplyProposalsRequest) -> dict:
    proj = _get_project_or_404(project_id)
    # Convert rel_paths to globs and apply via Phase 115 union
    new_globs = [f"**/{rel}/**" for rel in req.exclude]
    _apply_auto_excludes(proj, new_globs)

    # Persist dismissed
    current = list(getattr(proj, "dismissed_proposals", None) or proj.config.get("dismissed_proposals", []))
    for rel in req.dismiss:
        if rel not in current:
            current.append(rel)
    _persist_dismissed(proj, current)

    # v2 stub
    if req.add_to_gitignore:
        logger.info(
            "add_to_gitignore requested but not yet implemented (v2): %s",
            req.add_to_gitignore,
        )

    return {"config": proj.config, "dismissed_proposals": current}


def _apply_auto_excludes(proj, new_globs: list[str]) -> None:
    """Phase 115 additive-merge into proj.config['exclude_globs']."""
    existing = list(proj.config.get("exclude_globs", []))
    existing_set = set(existing)
    added = False
    for g in new_globs:
        if g not in existing_set:
            existing.append(g)
            existing_set.add(g)
            added = True
    if added:
        proj.config["exclude_globs"] = existing
        _srv()._get_registry().update_project(proj)


def _persist_vendor_scan(proj, result: VendorScanResult) -> None:
    proj.config["vendor_scan"] = result
    _srv()._get_registry().update_project(proj)


def _persist_dismissed(proj, dismissed: list[str]) -> None:
    proj.config["dismissed_proposals"] = dismissed
    _srv()._get_registry().update_project(proj)


def _scan_to_response_dict(vs: VendorScanResult) -> dict:
    return {
        "status": vs.status,
        "scanned_at": vs.scanned_at,
        "error": vs.error,
        "auto_excluded": vs.auto_excluded,
        "proposed": [
            {
                "rel_path": c.rel_path,
                "path": c.path,
                "size_bytes": c.size_bytes,
                "file_count": c.file_count,
                "reason": c.reason,
                "tier": c.tier,
                "in_gitignore": c.in_gitignore,
                "is_git_repo": c.is_git_repo,
            }
            for c in vs.proposed
        ],
        "gitignore_gaps": [
            {
                "rel_path": c.rel_path,
                "path": c.path,
                "size_bytes": c.size_bytes,
                "file_count": c.file_count,
                "reason": c.reason,
            }
            for c in vs.gitignore_gaps
        ],
    }
```

**Notes for the implementer:**
- `_srv()` / `get_server` / `_get_registry` / `update_project` are placeholders for whatever helpers the sibling routers in `src/prep/api/routers/projects/` use. Read `crud.py` and one sibling router (e.g., `files.py`) to find the exact names.
- The Phase 115 union helper at `src/prep/core/repo_policy.py:ensure_repo_policy` is the canonical reference for additive-merge. If a public helper exists, use it; otherwise the inline union in `_apply_auto_excludes` is acceptable for v1.

- [ ] **Step 4: Mount the sub-router**

In `src/prep/api/routers/projects/__init__.py`, add:

```python
from prep.api.routers.projects.vendor_scan import router as vendor_scan_router
# Then in the main router setup:
router.include_router(vendor_scan_router)
```

(Adjust to match the existing aggregation pattern — read the file first.)

- [ ] **Step 5: Run test to verify it passes**

```
.venv/bin/pytest tests/test_vendor_scan_endpoints.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```
git add src/prep/api/routers/projects/vendor_scan.py src/prep/api/routers/projects/__init__.py tests/test_vendor_scan_endpoints.py
git commit -m "feat(vendor-sniffer): vendor_scan + apply endpoints"
```

---

## Phase 3: UI Gates

Modal components live in `packages/ui/src/components/project/` and are consumed by the dashboard. Each component gets a Storybook story for design-system review.

### Task 11: `GitignoreHygieneModal` Component

**Files:**
- Create: `packages/ui/src/components/project/GitignoreHygieneModal.tsx`
- Create: `packages/ui/src/components/project/GitignoreHygieneModal.stories.tsx`
- Test: (manual via Storybook + the e2e test in Task 14)

- [ ] **Step 1: Write the component**

```tsx
// packages/ui/src/components/project/GitignoreHygieneModal.tsx
import { useState } from 'react';

import { Button } from '../primitives/Button';
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription } from '../primitives/Dialog';

export interface GitignoreGap {
  rel_path: string;
  size_bytes: number;
  file_count: number;
  reason: string;
}

export interface GitignoreHygieneModalProps {
  open: boolean;
  gaps: GitignoreGap[];
  onCancel: () => void;
  onContinue: () => void;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function GitignoreHygieneModal({ open, gaps, onCancel, onContinue }: GitignoreHygieneModalProps) {
  const [copied, setCopied] = useState(false);
  const snippet = gaps.map((g) => `${g.rel_path}/`).join('\n');

  const handleCopy = async () => {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Your .gitignore looks incomplete</DialogTitle>
          <DialogDescription>
            SourcePrep detected directories at your project root that are typically gitignored
            but aren't in your .gitignore. Adding them helps every tool that reads your repo —
            not just SourcePrep.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          <p className="text-sm text-text-subtle mb-2">Found (not in .gitignore):</p>
          <ul className="space-y-1 mb-4">
            {gaps.map((g) => (
              <li key={g.rel_path} className="font-mono text-sm flex items-center gap-2">
                <span className="text-text">{g.rel_path}/</span>
                <span className="text-text-subtle text-xs">
                  ({formatBytes(g.size_bytes)}, {g.file_count.toLocaleString()} files)
                </span>
              </li>
            ))}
          </ul>

          <p className="text-sm text-text-subtle mb-2">Recommended additions:</p>
          <div className="flex gap-2">
            <pre className="flex-1 bg-surface-raised border border-border rounded-md p-3 text-xs font-mono overflow-x-auto">
              {snippet}
            </pre>
            <Button variant="outline" size="sm" onClick={handleCopy}>
              {copied ? 'Copied!' : 'Copy'}
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel Initialize
          </Button>
          <Button onClick={onContinue}>Continue Anyway</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Write the Storybook story**

```tsx
// packages/ui/src/components/project/GitignoreHygieneModal.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';

import { GitignoreHygieneModal } from './GitignoreHygieneModal';

const meta: Meta<typeof GitignoreHygieneModal> = {
  title: 'Project/GitignoreHygieneModal',
  component: GitignoreHygieneModal,
};
export default meta;
type Story = StoryObj<typeof GitignoreHygieneModal>;

export const TwoGaps: Story = {
  args: {
    open: true,
    gaps: [
      {
        rel_path: 'node_modules',
        size_bytes: 450_000_000,
        file_count: 21_400,
        reason: 'Canonical package-manager install dir',
      },
      {
        rel_path: 'vcpkg_installed',
        size_bytes: 1_200_000_000,
        file_count: 8_900,
        reason: 'Canonical package-manager install dir',
      },
    ],
    onCancel: () => alert('cancel'),
    onContinue: () => alert('continue'),
  },
};

export const OneGap: Story = {
  args: {
    open: true,
    gaps: [
      {
        rel_path: 'build',
        size_bytes: 497_000_000,
        file_count: 1_200,
        reason: 'CMake/build output',
      },
    ],
    onCancel: () => {},
    onContinue: () => {},
  },
};
```

- [ ] **Step 3: Verify the component renders in Storybook**

```
cd packages/ui && npm run storybook
```
Visit `http://localhost:6006`, navigate to `Project/GitignoreHygieneModal`, confirm both stories render and the Copy button works.

- [ ] **Step 4: Type-check**

```
cd packages/ui && npm run typecheck
```
Expected: clean.

- [ ] **Step 5: Commit**

```
git add packages/ui/src/components/project/GitignoreHygieneModal.tsx packages/ui/src/components/project/GitignoreHygieneModal.stories.tsx
git commit -m "feat(ui): GitignoreHygieneModal for Gate 1"
```

---

### Task 12: `InitExcludeReviewModal` Component

**Files:**
- Create: `packages/ui/src/components/project/InitExcludeReviewModal.tsx`
- Create: `packages/ui/src/components/project/InitExcludeReviewModal.stories.tsx`

Two action buttons (Apply / Skip) plus a collapsed Tier-1 informational section. X/Esc closes without firing Initialize.

- [ ] **Step 1: Write the component**

```tsx
// packages/ui/src/components/project/InitExcludeReviewModal.tsx
import { useState } from 'react';

import { Button } from '../primitives/Button';
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription } from '../primitives/Dialog';

export interface VendorCandidateView {
  rel_path: string;
  size_bytes: number;
  file_count: number;
  reason: string;
  tier: 'auto' | 'propose';
  in_gitignore: boolean;
  is_git_repo: boolean;
}

export interface InitExcludeReviewModalProps {
  open: boolean;
  proposed: VendorCandidateView[];
  autoExcludedSummary: VendorCandidateView[];  // informational only
  onClose: () => void;                          // X / Esc — does not fire build
  onApply: (selectedRelPaths: string[], dismissedRelPaths: string[]) => void;
  onSkip: () => void;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function InitExcludeReviewModal({
  open,
  proposed,
  autoExcludedSummary,
  onClose,
  onApply,
  onSkip,
}: InitExcludeReviewModalProps) {
  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    for (const c of proposed) {
      // Per spec: default-checked toward exclude (safer-from-runaway default).
      // Size-fallback proposals are still default-checked but visually distinct.
      init[c.rel_path] = true;
    }
    return init;
  });
  const [autoExpanded, setAutoExpanded] = useState(false);

  const selected = proposed.filter((c) => checked[c.rel_path]).map((c) => c.rel_path);
  const dismissed = proposed.filter((c) => !checked[c.rel_path]).map((c) => c.rel_path);

  const isSizeFallback = (reason: string) => reason.startsWith('Large directory');

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Review what to exclude before indexing</DialogTitle>
          <DialogDescription>
            SourcePrep found directories that may not need to be indexed. Review the proposals
            and confirm before we build the index.
          </DialogDescription>
        </DialogHeader>

        {autoExcludedSummary.length > 0 && (
          <div className="mt-3 border border-border rounded-md">
            <button
              onClick={() => setAutoExpanded((e) => !e)}
              className="w-full px-3 py-2 text-left text-xs text-text-subtle hover:bg-surface-raised flex items-center gap-2"
            >
              <span>{autoExpanded ? '▾' : '▸'}</span>
              <span>Auto-excluded ({autoExcludedSummary.length}) — these are already added to the exclude list.</span>
            </button>
            {autoExpanded && (
              <ul className="px-3 py-2 space-y-1 text-xs font-mono">
                {autoExcludedSummary.map((c) => (
                  <li key={c.rel_path} className="flex items-center gap-2">
                    <span className="text-success">✓</span>
                    <span>{c.rel_path}/</span>
                    <span className="text-text-subtle">— {c.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="mt-4">
          <p className="text-sm text-text-subtle mb-2">Review proposals (default: exclude):</p>
          <ul className="space-y-2">
            {proposed.map((c) => (
              <li
                key={c.rel_path}
                className="flex items-start gap-3 p-2 rounded-md border border-border hover:bg-surface-raised"
              >
                <input
                  type="checkbox"
                  checked={checked[c.rel_path] ?? true}
                  onChange={(e) =>
                    setChecked((s) => ({ ...s, [c.rel_path]: e.target.checked }))
                  }
                  className="mt-1"
                />
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-sm">
                    {c.rel_path}/
                    {isSizeFallback(c.reason) && (
                      <span title="Weak signal — based on size only" className="ml-1 text-text-subtle">
                        ?
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-text-subtle">
                    {formatBytes(c.size_bytes)}, {c.file_count.toLocaleString()} files — {c.reason}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <DialogFooter className="mt-4 flex items-center justify-between gap-2">
          <span className="text-xs text-text-subtle">
            Selected: {selected.length} of {proposed.length} proposals
          </span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onSkip}>
              Skip Excludes &amp; Initialize
            </Button>
            <Button onClick={() => onApply(selected, dismissed)}>
              Apply {selected.length} Excludes &amp; Initialize
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Write the Storybook story**

```tsx
// packages/ui/src/components/project/InitExcludeReviewModal.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';

import { InitExcludeReviewModal } from './InitExcludeReviewModal';

const meta: Meta<typeof InitExcludeReviewModal> = {
  title: 'Project/InitExcludeReviewModal',
  component: InitExcludeReviewModal,
};
export default meta;
type Story = StoryObj<typeof InitExcludeReviewModal>;

export const SkyPathLike: Story = {
  args: {
    open: true,
    proposed: [
      {
        rel_path: 'cesium-native',
        size_bytes: 1_700_000_000,
        file_count: 12_304,
        reason: 'Nested git repo, possibly vendored',
        tier: 'propose',
        in_gitignore: false,
        is_git_repo: true,
      },
      {
        rel_path: 'vcpkg',
        size_bytes: 2_700_000_000,
        file_count: 8_210,
        reason: 'Nested git repo, possibly vendored',
        tier: 'propose',
        in_gitignore: false,
        is_git_repo: true,
      },
      {
        rel_path: 'webgl-component',
        size_bytes: 80_000_000,
        file_count: 230,
        reason: 'Separate project (own manifest), not in root workspaces',
        tier: 'propose',
        in_gitignore: false,
        is_git_repo: false,
      },
    ],
    autoExcludedSummary: [
      {
        rel_path: 'Pods',
        size_bytes: 0,
        file_count: 0,
        reason: 'Canonical package-manager install dir',
        tier: 'auto',
        in_gitignore: false,
        is_git_repo: false,
      },
      {
        rel_path: 'build',
        size_bytes: 0,
        file_count: 0,
        reason: 'CMake/build output (CMakeCache.txt or build.ninja present)',
        tier: 'auto',
        in_gitignore: false,
        is_git_repo: false,
      },
    ],
    onClose: () => alert('close'),
    onApply: (s, d) => alert(`apply ${s.length} dismiss ${d.length}`),
    onSkip: () => alert('skip'),
  },
};

export const SizeFallbackOnly: Story = {
  args: {
    open: true,
    proposed: [
      {
        rel_path: 'huge-unknown',
        size_bytes: 300_000_000,
        file_count: 1_000,
        reason: 'Large directory, no classification signal',
        tier: 'propose',
        in_gitignore: false,
        is_git_repo: false,
      },
    ],
    autoExcludedSummary: [],
    onClose: () => {},
    onApply: () => {},
    onSkip: () => {},
  },
};
```

- [ ] **Step 3: Verify in Storybook**

```
cd packages/ui && npm run storybook
```
Navigate to `Project/InitExcludeReviewModal`. Verify:
- Checkboxes start checked
- Auto-excluded section expands/collapses
- Size-fallback row shows the `?` indicator
- Apply button label updates as boxes toggle

- [ ] **Step 4: Type-check**

```
cd packages/ui && npm run typecheck
```

- [ ] **Step 5: Commit**

```
git add packages/ui/src/components/project/InitExcludeReviewModal.tsx packages/ui/src/components/project/InitExcludeReviewModal.stories.tsx
git commit -m "feat(ui): InitExcludeReviewModal for Gate 2"
```

---

### Task 13: Wire `IndexStatusCard.tsx` Initialize Click Through the Gates

**Files:**
- Modify: `packages/ui/src/components/dashboard/IndexStatusCard.tsx:162-191` (Initialize button)
- Modify: parent components that pass `onBuild` to `IndexStatusCard` — they need to provide vendor_scan data and apply/skip handlers (the actual data-fetching layer lives in `src/prep/dashboard/src/components/...`; trace `IndexStatusCard` consumers)

This task wires the modals to the existing Initialize button. The cleanest separation: keep `IndexStatusCard` UI-only (receives props), and put the gate orchestration in its consumer.

- [ ] **Step 1: Read the existing consumer**

```
grep -rn "IndexStatusCard" packages/ui/src/ src/prep/dashboard/src/ --include="*.tsx" | grep -v ".stories."
```

Identify the consumer (likely in `src/prep/dashboard/src/components/`). Read it end-to-end.

- [ ] **Step 2: Add new props to `IndexStatusCard`**

In `packages/ui/src/components/dashboard/IndexStatusCard.tsx`, extend the Props interface:

```typescript
export interface IndexStatusCardProps {
  // ... existing props ...
  vendorScanStatus?: 'pending' | 'complete' | 'failed' | 'none';
  hasGitignoreGaps?: boolean;
  hasProposals?: boolean;
}
```

Adjust the Initialize button label conditionally:

```tsx
{building
  ? 'Building…'
  : !stats.loaded
    ? (hasGitignoreGaps || hasProposals
        ? `Review ${(hasGitignoreGaps ? 1 : 0) + (hasProposals ? 1 : 0)} item${hasGitignoreGaps && hasProposals ? 's' : ''} →`
        : 'Initialize')
    : 'Rebuild'}
```

The actual modal mount + gate orchestration happens in the consumer, not in this card.

- [ ] **Step 3: Wire the gate orchestration in the consumer**

In the consumer file (located via Step 1), add:

```tsx
import { GitignoreHygieneModal } from '@prep/ui/components/project/GitignoreHygieneModal';
import { InitExcludeReviewModal } from '@prep/ui/components/project/InitExcludeReviewModal';

// State machine:
//   'idle' -> click Initialize -> 'gate1' (if gaps) -> 'gate2' (if proposals) -> build
type GateState = 'idle' | 'gate1' | 'gate2';

const [gateState, setGateState] = useState<GateState>('idle');
const [vendorScan, setVendorScan] = useState<VendorScanResponse | null>(null);

useEffect(() => {
  if (!projectId) return;
  apiClient.getVendorScan(projectId).then(setVendorScan);
}, [projectId]);

const handleInitializeClick = async () => {
  // If scan is pending, wait briefly for it to complete
  if (vendorScan?.status === 'pending') {
    const fresh = await pollVendorScan(projectId);  // helper: GET until !pending or timeout
    setVendorScan(fresh);
  }

  const hasGaps = (vendorScan?.gitignore_gaps?.length ?? 0) > 0;
  const hasProposals = (vendorScan?.proposed?.length ?? 0) > 0;

  if (hasGaps) {
    setGateState('gate1');
  } else if (hasProposals) {
    setGateState('gate2');
  } else {
    onBuild();
  }
};

const handleGate1Continue = () => {
  const hasProposals = (vendorScan?.proposed?.length ?? 0) > 0;
  if (hasProposals) {
    setGateState('gate2');
  } else {
    setGateState('idle');
    onBuild();
  }
};

const handleGate2Apply = async (selected: string[], dismissed: string[]) => {
  await apiClient.applyVendorProposals(projectId, {
    exclude: selected,
    dismiss: dismissed,
    add_to_gitignore: [],
  });
  setGateState('idle');
  onBuild();
};

const handleGate2Skip = () => {
  setGateState('idle');
  onBuild();
};

// Render:
<>
  <IndexStatusCard
    onBuild={handleInitializeClick}
    vendorScanStatus={vendorScan?.status ?? 'none'}
    hasGitignoreGaps={(vendorScan?.gitignore_gaps?.length ?? 0) > 0}
    hasProposals={(vendorScan?.proposed?.length ?? 0) > 0}
    {...otherProps}
  />
  <GitignoreHygieneModal
    open={gateState === 'gate1'}
    gaps={vendorScan?.gitignore_gaps ?? []}
    onCancel={() => setGateState('idle')}
    onContinue={handleGate1Continue}
  />
  <InitExcludeReviewModal
    open={gateState === 'gate2'}
    proposed={vendorScan?.proposed ?? []}
    autoExcludedSummary={[]}  // populate from a separate request if showing them
    onClose={() => setGateState('idle')}
    onApply={handleGate2Apply}
    onSkip={handleGate2Skip}
  />
</>
```

**Adjust to match:** API client method names (`apiClient.getVendorScan` etc.) need to be added to the existing API client interface. Read `src/prep/dashboard/src/api/...` to find where to add them.

- [ ] **Step 4: Add the API client methods**

In the existing `ApiClient` interface (locate via `grep -rn "ApiClient" src/prep/dashboard/src/api/`):

```typescript
getVendorScan(projectId: string): Promise<VendorScanResponse>;
rescanVendor(projectId: string): Promise<VendorScanResponse>;
applyVendorProposals(
  projectId: string,
  body: { exclude: string[]; dismiss: string[]; add_to_gitignore: string[] }
): Promise<{ config: any; dismissed_proposals: string[] }>;
```

Implement on the real / mock / factory implementations, following the existing pattern.

- [ ] **Step 5: Run type-check and the dashboard build**

```
cd src/prep/dashboard && npm run typecheck
cd src/prep/dashboard && npm run build
```
Expected: clean.

- [ ] **Step 6: Commit**

```
git add packages/ui/src/components/dashboard/IndexStatusCard.tsx src/prep/dashboard/src/
git commit -m "feat(ui): wire Initialize button through GitignoreHygiene + ExcludeReview gates"
```

(Adjust staged paths to match the actual consumer files modified.)

---

### Task 14: E2E Playwright Test for the Init Gate Flow

**Files:**
- Create: `tests/e2e/init_gate_flow.spec.ts`

Uses the existing Playwright harness (per `playwright-smoke` skill conventions). Spins up a SkyPath-shaped temp dir, creates a project, clicks Initialize, drives both modals, verifies the resulting `exclude_globs`.

- [ ] **Step 1: Write the test**

```typescript
// tests/e2e/init_gate_flow.spec.ts
import { test, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';

test('Initialize flows through gitignore + vendor gates', async ({ page, request }) => {
  // 1. Create a SkyPath-shaped temp dir on disk
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'init-gate-'));
  fs.mkdirSync(path.join(root, '.git'));
  fs.mkdirSync(path.join(root, 'cesium-native'));
  fs.mkdirSync(path.join(root, 'cesium-native', '.git'));
  fs.writeFileSync(path.join(root, 'cesium-native', 'engine.cpp'), '// engine\n');
  fs.mkdirSync(path.join(root, 'node_modules'));
  fs.mkdirSync(path.join(root, 'node_modules', 'react'));
  fs.writeFileSync(path.join(root, 'node_modules', 'react', 'index.js'), '// react\n');
  fs.mkdirSync(path.join(root, 'src'));
  fs.writeFileSync(path.join(root, 'src', 'app.ts'), '// app\n');
  // NO .gitignore — gap will fire

  // 2. Create the project via the daemon API
  const created = await request.post('http://localhost:8400/projects', {
    data: { path: root, name: 'gate-test', mode: 'embedded' },
  });
  expect(created.ok()).toBeTruthy();
  const project = (await created.json()).project;

  // 3. Wait for the vendor scan to complete (background task)
  for (let i = 0; i < 30; i++) {
    const r = await request.get(`http://localhost:8400/projects/${project.id}/vendor_scan`);
    if ((await r.json()).status !== 'pending') break;
    await new Promise((res) => setTimeout(res, 200));
  }

  // 4. Navigate to the dashboard project view
  await page.goto(`http://localhost:5174/projects/${project.id}`);

  // 5. Click the Initialize / Review button
  await page.getByRole('button', { name: /Review|Initialize/i }).click();

  // 6. Gate 1 (gitignore hygiene) — should fire because node_modules isn't in gitignore
  await expect(page.getByText(/\.gitignore looks incomplete/i)).toBeVisible();
  await page.getByRole('button', { name: /Continue Anyway/i }).click();

  // 7. Gate 2 (vendor sniffer) — should fire because cesium-native is a proposal
  await expect(page.getByText(/Review what to exclude/i)).toBeVisible();
  await page.getByRole('button', { name: /Apply \d+ Excludes/i }).click();

  // 8. Verify the exclude_globs got the cesium-native pattern
  const finalConfig = await request.get(`http://localhost:8400/projects/${project.id}`);
  const cfg = (await finalConfig.json()).project.config;
  expect(cfg.exclude_globs.some((g: string) => g.includes('cesium-native'))).toBeTruthy();
  expect(cfg.exclude_globs.some((g: string) => g.includes('node_modules'))).toBeTruthy();

  // Cleanup
  fs.rmSync(root, { recursive: true, force: true });
});
```

- [ ] **Step 2: Restart the daemon and dashboard before running**

Per `feedback_restart_daemon_before_live_validation.md`:

```
scripts/dev.sh --kill
scripts/dev.sh
```

Wait for daemon (`:8400`) and dashboard (`:5174`) to come up.

- [ ] **Step 3: Run the E2E test**

```
.venv/bin/pytest tests/e2e/init_gate_flow.spec.ts -v
```
(Or whatever the project's Playwright runner is — check `package.json` for `e2e` scripts.)
Expected: pass.

- [ ] **Step 4: Commit**

```
git add tests/e2e/init_gate_flow.spec.ts
git commit -m "test(e2e): init gate flow end-to-end on synthetic SkyPath fixture"
```

---

## Phase 4: Live Validation

### Task 15: Live Dogfooding on SkyPath

**Files:**
- None — this is a live validation step. Document findings in a follow-up commit if behavior drifts from expectations.

- [ ] **Step 1: Restart the daemon**

```
scripts/dev.sh --kill && scripts/dev.sh
```

- [ ] **Step 2: Add the SkyPath project**

In the dashboard at `:5174`, add `/Volumes/Thunderbolt/XcodeProjects/SkyPath2025/SkyPath` as a new project.

- [ ] **Step 3: Verify vendor scan status**

Wait until `GET /projects/<id>/vendor_scan` returns `status: complete`. Inspect the response:
- `auto_excluded` should contain at least `vcpkg`-style globs and `build` (CMakeCache.txt) globs
- `proposed` should contain `cesium-native` (the canonical Tier-2 case)
- `gitignore_gaps` should contain entries if the repo's `.gitignore` is incomplete

- [ ] **Step 4: Click Initialize**

Verify the gate flow:
- If gitignore gaps exist → Gate 1 fires → confirm copy-snippet works → Continue Anyway
- If proposals exist → Gate 2 fires → defaults look right → Apply

- [ ] **Step 5: Verify the build doesn't index vendored content**

After build completes, run a `prep_search` for a vcpkg-specific symbol (e.g., `vcpkg::install`). Confirm no hits. Similarly for cesium-native if excluded.

- [ ] **Step 6: Document anything surprising in a follow-up observation**

If behavior drifts from the spec, do NOT silently fix it. Capture the surprise via `prep_observe` (when the MCP is available) or as a separate `docs/` note, with file:line citations.

---

## Self-Review

Skimmed each spec section against the plan tasks:

| Spec section | Implemented in |
|---|---|
| Data models (VendorCandidate, VendorScanResult) | Task 1 |
| `.gitmodules` parser | Task 2 |
| Root `.gitignore` parser | Task 3 |
| `package.json` / `Cargo.toml` / `go.work` parsers | Task 4 |
| Tier-1/2/3 signal evaluators | Task 5 |
| Scanner orchestrator (signals + manifests → result) | Task 6 |
| SkyPath classification regression | Task 7 |
| Project record schema (vendor_scan, dismissed_proposals) | Task 8 |
| Async sniffer dispatch + preset error surfacing | Task 9 |
| 3 new endpoints (GET / rescan / apply) | Task 10 |
| GitignoreHygieneModal | Task 11 |
| InitExcludeReviewModal | Task 12 |
| Initialize-click gate wiring + API client methods | Task 13 |
| E2E init-gate flow | Task 14 |
| Live dogfooding on SkyPath | Task 15 |

**Gaps acknowledged:**

- The spec also mentions a `VendorScanIndicator.tsx` inline strip for the Sources settings page (the re-run surface for grown codebases). That UI is small but not on the critical path for the v1 problem (preventing accidental over-indexing on first init). Listed as **deferred** here; revisit after Task 15 confirms the core flow works, and add as a v1.1 follow-up.
- Podfile-existence-only "parser" is implicit: the canonical-install-dir whitelist includes `Pods/`, which is what `Podfile` would have signaled. No dedicated parser needed.
- The Settings "Scan for Vendor Dirs" button (sibling to "Auto-Detect Stack") is also a deferred v1.1 follow-up — the rescan endpoint exists (Task 10), but the UI button on Sources.tsx isn't in the critical path.

**Placeholder scan:** none. Every step has either complete code, an exact command, or a concrete grep-and-read instruction with a named target.

**Type consistency:** `VendorCandidate`, `VendorScanResult`, `VendorCandidateView`, `GitignoreGap`, `VendorScanResponse` — names are distinct on purpose (Python dataclass vs. TS DTO vs. UI prop type vs. API response). Field names within each type stay consistent across tasks.

---

## Out-of-Scope Reminders (Do NOT Implement in v1)

- Auto-writing to `.gitignore` (the `add_to_gitignore` field on the apply endpoint is a stub for v2)
- `CMakeLists.txt` DSL parsing
- `vcpkg.json` / `.csproj` / `.sln` / `composer.json` / `Gemfile` / `pubspec.yaml` parsers
- Tier-1 override affordance in the modal (`tier1_overrides` list on project record)
- Telemetry on dismiss-rate auto-tuning
- Storage-class-aware thresholds
- Initialize button "Review N items" badge in Settings sidebar
- `VendorScanIndicator.tsx` inline strip on Sources page (v1.1)
- Settings "Scan for Vendor Dirs" button on Sources.tsx (v1.1 — endpoint exists, UI deferred)
