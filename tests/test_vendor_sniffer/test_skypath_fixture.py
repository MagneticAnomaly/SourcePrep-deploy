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
        cesium-native/                 (vendored, NOT in .gitmodules — small in fixture)
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
