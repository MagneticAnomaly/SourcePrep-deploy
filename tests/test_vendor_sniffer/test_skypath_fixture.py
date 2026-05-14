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
        cesium-native/                 (vendored, NOT in .gitmodules; small in fixture)
                                         NOTE: nested .git no longer triggers proposal by itself
                                         per Task 6 simplification — Tier 2 is size-fallback only,
                                         so even a real 1.7GB cesium-native checkout would propose
                                         via size, never via nested-.git signal.
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

    # Tier 2 proposed: nested .git/ is a primary signal — propose cesium-native
    # (own .git/, not in .gitmodules) even though it's small in the fixture.
    # vcpkg is in .gitmodules so it's Tier-1 auto-excluded, not proposed.
    proposed_rel = {c.rel_path for c in r.proposed}
    assert "cesium-native" in proposed_rel, "nested .git/ should propose cesium-native"
    assert "vcpkg" not in proposed_rel, "vcpkg is in .gitmodules → Tier 1 auto-exclude, not propose"

    # Tier 3 skipped (everything that isn't Tier 1 or Tier 2). Use the dir-name
    # parse of each glob ("**/NAME/**" → NAME) so we assert the real
    # classification, not a substring match that could pass vacuously.
    auto_excluded_names = {g.split("/")[1] for g in r.auto_excluded if "/" in g}
    assert "SkyPath" not in auto_excluded_names, "user-code SkyPath/ must not auto-exclude"
    assert "GeoTestARSceneOriginal" not in auto_excluded_names
    assert "SkyPath" not in proposed_rel
    assert "GeoTestARSceneOriginal" not in proposed_rel  # has .xcodeproj, no nested .git
    assert "webgl-component" not in proposed_rel  # has package.json, no nested .git
    assert "docs" not in proposed_rel  # small and plain

    # Gate 1: gitignore gap — node_modules + build are canonical/build-output
    # and root has no .gitignore. They MUST appear in gitignore_gaps.
    # vcpkg is in .gitmodules (not the canonical/cmake gap signal set), so
    # it must NOT appear in gitignore_gaps even though it's auto-excluded.
    gap_rel = {c.rel_path for c in r.gitignore_gaps}
    assert "node_modules" in gap_rel
    assert "build" in gap_rel
    assert "vcpkg" not in gap_rel
