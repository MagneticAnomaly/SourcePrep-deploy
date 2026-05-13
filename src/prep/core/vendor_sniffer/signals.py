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


def has_project_anchor(p: Path) -> bool:
    """
    Tier-3 signal: directory contains a recognized project/manifest file,
    so it looks like the user's own project rather than a vendored dep.
    """
    if not p.is_dir():
        return False
    try:
        for child in p.iterdir():
            if child.name in PROJECT_ANCHOR_FILES:
                return True
            for suffix in _PROJECT_ANCHOR_SUFFIXES:
                if child.name.endswith(suffix):
                    return True
    except OSError:
        return False
    return False
