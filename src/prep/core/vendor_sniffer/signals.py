from __future__ import annotations

from pathlib import Path

# Canonical package-manager install dirs and conventional build-system symlinks.
# Project-specific names (vcpkg the tool, cesium-native, etc.) deliberately
# NOT here — those flow through to Tier 2 size-fallback if huge enough, or
# stay as user code if not. List cross-checked against GitHub Linguist's
# vendor.yml; we include only top-level conventions, not nested patterns
# like gradle/wrapper (which lives inside the user-edited gradle/ dir).
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
    "bazel-out",         # Bazel build outputs (top-level symlinks)
    "bazel-bin",
    "bazel-testlogs",
})

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
    try:
        return any((p / m).is_file() for m in _CMAKE_BUILD_MARKERS)
    except OSError:
        return False


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


