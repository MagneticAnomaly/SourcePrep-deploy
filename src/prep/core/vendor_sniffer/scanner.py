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

            # Tier-3 user-code check: a project anchor (xcodeproj, package.json, Cargo.toml,
            # etc.) without a nested .git/ means this is the user's own code, not a vendor
            # dep. Skip entirely — don't propose, don't auto-exclude.
            anchor = has_project_anchor(entry)
            nested_git = has_nested_git_dir(entry)
            if anchor and not nested_git:
                continue

            # --- Tier 2 signals ---
            tier2_reason: str | None = None
            if nested_git:
                tier2_reason = "Nested git repo, possibly vendored"
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
