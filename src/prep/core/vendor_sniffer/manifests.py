from __future__ import annotations

import json
import logging
import re
import re as _re
from pathlib import Path

try:
    import tomllib  # py311+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_GITMODULES_PATH_RE = re.compile(r"^\s*path\s*=\s*(.+?)\s*$")
_GO_WORK_USE_BLOCK_RE = _re.compile(r"use\s*\(\s*([^)]*)\)", _re.DOTALL)
_GO_WORK_USE_SINGLE_RE = _re.compile(r"use\s+([^\s]+)")


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
