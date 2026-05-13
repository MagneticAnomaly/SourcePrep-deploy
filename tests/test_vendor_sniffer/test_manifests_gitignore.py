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
