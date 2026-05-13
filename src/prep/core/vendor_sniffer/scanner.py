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
    has_cmake_build_marker,
    has_ignore_everything_gitignore,
    has_nested_git_dir,
    is_canonical_install_dir,
)

logger = logging.getLogger(__name__)

# Size/file-count is the LAST-RESORT Tier 2 trigger only. Thresholds set
# deliberately high so the modal only fires on genuine outliers (e.g. a
# 1.7GB vendored cesium-native checkout) — not on legitimate user content
# like assets/ or media/ directories. False-positive cost (excluding user
# code) is worse than false-negative (missing a vendored thing the user
# can manually exclude in the file tree).
_SIZE_FALLBACK_BYTES = 500 * 1024 * 1024  # 500 MB
_SIZE_FALLBACK_FILES = 25_000


def _is_git_repo_root(root: Path) -> bool:
    """A repo root is a git repo if it has .git/ (dir) or .git (file = worktree)."""
    g = root / ".git"
    return g.is_dir() or g.is_file()


def _dir_size_and_count(d: Path) -> tuple[int, int]:
    """
    Size + file-count for one directory tree.

    Short-circuits as soon as either threshold is crossed — we only need to
    answer "is this bigger than the fallback threshold?", not "how much
    bigger". Skips symlinks entirely (don't follow into external mounts or
    chase cycles). Per-entry errors are swallowed.
    """
    if d.is_symlink():
        return 0, 0
    total_bytes = 0
    total_files = 0
    for entry in d.rglob("*"):
        try:
            if entry.is_symlink():
                continue
            if entry.is_file():
                total_files += 1
                total_bytes += entry.stat().st_size
                if total_bytes > _SIZE_FALLBACK_BYTES or total_files > _SIZE_FALLBACK_FILES:
                    return total_bytes, total_files
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

            # Default to "user code" unless the size-fallback fires.
            # Per design: sub-repos (nested .git/) and sibling projects (own manifest)
            # are assumed user code — the cost of falsely excluding user code is worse
            # than letting a small vendored thing slip through. Users can manually
            # exclude via the file tree if needed.
            size, files = _dir_size_and_count(entry)
            if size > _SIZE_FALLBACK_BYTES or files > _SIZE_FALLBACK_FILES:
                proposed.append(VendorCandidate(
                    path=str(entry),
                    rel_path=rel,
                    size_bytes=size,
                    file_count=files,
                    reason="Large directory, no classification signal",
                    tier="propose",
                    in_gitignore=in_gi,
                    is_git_repo=has_nested_git_dir(entry),
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
