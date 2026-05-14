from pathlib import Path

from prep.core.vendor_sniffer import scan_for_vendor_dirs


def _make_file(p: Path, size: int = 100) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)


def test_empty_project_returns_empty_result(tmp_path: Path):
    r = scan_for_vendor_dirs(tmp_path)
    assert r.status == "complete"
    assert r.auto_excluded == []
    assert r.proposed == []
    assert r.gitignore_gaps == []


def test_canonical_install_dir_auto_excluded(tmp_path: Path):
    _make_file(tmp_path / "node_modules" / "react" / "index.js")
    _make_file(tmp_path / "src" / "app.ts")
    r = scan_for_vendor_dirs(tmp_path)
    assert any("node_modules" in g for g in r.auto_excluded)
    assert not r.proposed


def test_gitmodules_submodule_auto_excluded(tmp_path: Path):
    (tmp_path / ".gitmodules").write_text(
        '[submodule "vcpkg"]\n\tpath = vcpkg\n\turl = https://example/v.git\n'
    )
    (tmp_path / "vcpkg").mkdir()
    (tmp_path / "vcpkg" / ".git").mkdir()
    _make_file(tmp_path / "vcpkg" / "boot.cmake")
    r = scan_for_vendor_dirs(tmp_path)
    assert any("vcpkg" in g for g in r.auto_excluded)


def test_nested_git_dir_proposed_as_likely_vendored(tmp_path: Path):
    # cesium-native style: own .git/, not in .gitmodules. Nested .git is a
    # strong vendor signal — propose regardless of size, regardless of
    # anchor. The user reviews via the file tree's pre-excluded state and
    # unchecks if they're actively developing on this sub-repo.
    (tmp_path / "cesium-native").mkdir()
    (tmp_path / "cesium-native" / ".git").mkdir()
    _make_file(tmp_path / "cesium-native" / "src" / "engine.cpp")
    r = scan_for_vendor_dirs(tmp_path)
    assert not any("cesium-native" in g for g in r.auto_excluded)
    cands = [c for c in r.proposed if c.rel_path == "cesium-native"]
    assert len(cands) == 1
    assert ".git" in cands[0].reason


def test_nested_git_wins_over_project_anchor(tmp_path: Path):
    # cesium-native real-world case: has BOTH package.json AND its own .git/.
    # The nested-.git signal wins — propose as likely vendored even though
    # the anchor would otherwise mark it as user code.
    d = tmp_path / "cesium-native"
    d.mkdir()
    (d / ".git").mkdir()
    (d / "package.json").write_text('{"name": "cesium-native"}')
    _make_file(d / "src" / "engine.cpp")
    r = scan_for_vendor_dirs(tmp_path)
    cands = [c for c in r.proposed if c.rel_path == "cesium-native"]
    assert len(cands) == 1, "nested .git/ must override the anchor skip"


def test_huge_unclassified_dir_triggers_size_fallback_proposal(tmp_path: Path):
    # The size-fallback Tier 2 path is the ONLY trigger for proposal-with-
    # confirmation. A directory with no manifest signal AND > 25,000 files
    # gets proposed — the modal copy makes the weak signal honest.
    huge = tmp_path / "huge-blob"
    # 25,001 small files crosses the file-count threshold without needing
    # to actually write 500 MB on disk.
    for i in range(25_001):
        _make_file(huge / f"shard_{i // 100}" / f"f_{i}.bin", size=1)
    r = scan_for_vendor_dirs(tmp_path)
    cands = [c for c in r.proposed if c.rel_path == "huge-blob"]
    assert len(cands) == 1
    assert "Large directory" in cands[0].reason


def test_separate_subproject_with_own_manifest_is_skipped(tmp_path: Path):
    # webgl-component style: has its own package.json, no nested .git/, not
    # in root workspaces. Under our rule, this is user code (a sibling sub-
    # project they're developing). Skip it; the user can manually exclude
    # if it turns out to be vendored.
    d = tmp_path / "webgl-component"
    d.mkdir()
    (d / "package.json").write_text('{"name": "webgl"}')
    _make_file(d / "src" / "index.ts")
    r = scan_for_vendor_dirs(tmp_path)
    assert not any("webgl-component" in g for g in r.auto_excluded)
    assert not any(c.rel_path == "webgl-component" for c in r.proposed)


def test_cmake_build_dir_auto_excluded(tmp_path: Path):
    b = tmp_path / "build"
    b.mkdir()
    (b / "CMakeCache.txt").write_text("# cmake\n")
    _make_file(b / "obj" / "main.o")
    r = scan_for_vendor_dirs(tmp_path)
    assert any("build" in g for g in r.auto_excluded)


def test_user_code_with_xcodeproj_skipped(tmp_path: Path):
    d = tmp_path / "MyApp"
    d.mkdir()
    (d / "MyApp.xcodeproj").mkdir()
    _make_file(d / "AppDelegate.swift")
    r = scan_for_vendor_dirs(tmp_path)
    # Must NOT propose or auto-exclude — it's user code
    assert not any("MyApp" in g for g in r.auto_excluded)
    assert not any(c.rel_path == "MyApp" for c in r.proposed)


def test_workspace_member_skipped(tmp_path: Path):
    # Root package.json declares packages/* as workspace; packages/ui contains a
    # nested .git/ for some reason — must STILL be skipped (user code wins).
    (tmp_path / "package.json").write_text('{"workspaces": ["packages/*"]}')
    ui = tmp_path / "packages" / "ui"
    ui.mkdir(parents=True)
    (ui / "package.json").write_text("{}")
    (ui / ".git").mkdir()
    r = scan_for_vendor_dirs(tmp_path)
    assert not any("packages" in g for g in r.auto_excluded if "node_modules" not in g)


def test_gitignore_gap_detected_for_canonical_dir(tmp_path: Path):
    # node_modules exists but is NOT in .gitignore — gitignore_gaps should flag it
    _make_file(tmp_path / "node_modules" / "react" / "index.js")
    (tmp_path / ".git").mkdir()  # mark as a git repo
    # No .gitignore
    r = scan_for_vendor_dirs(tmp_path)
    assert any(c.rel_path == "node_modules" for c in r.gitignore_gaps)


def test_gitignore_gap_NOT_flagged_when_listed(tmp_path: Path):
    _make_file(tmp_path / "node_modules" / "react" / "index.js")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    r = scan_for_vendor_dirs(tmp_path)
    assert not any(c.rel_path == "node_modules" for c in r.gitignore_gaps)


def test_gitignore_gap_NOT_flagged_when_not_git_repo(tmp_path: Path):
    _make_file(tmp_path / "node_modules" / "react" / "index.js")
    # NO .git/ at root — Gate 1 should never fire
    r = scan_for_vendor_dirs(tmp_path)
    assert r.gitignore_gaps == []


def test_scanned_at_set_to_recent_epoch(tmp_path: Path):
    import time

    before = time.time()
    r = scan_for_vendor_dirs(tmp_path)
    after = time.time()
    assert before <= r.scanned_at <= after
