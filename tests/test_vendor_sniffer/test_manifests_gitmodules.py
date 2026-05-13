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
