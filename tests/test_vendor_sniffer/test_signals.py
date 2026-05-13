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
