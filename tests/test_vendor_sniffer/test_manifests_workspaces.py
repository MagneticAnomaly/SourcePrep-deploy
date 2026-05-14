from pathlib import Path

from prep.core.vendor_sniffer.manifests import parse_workspace_members


def test_package_json_workspaces_array(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"name": "root", "workspaces": ["packages/*", "apps/web"]}'
    )
    members = parse_workspace_members(tmp_path)
    # Glob patterns are expanded to first-segment dir names; explicit paths kept as-is
    assert "packages" in members or "packages/*" in members
    assert "apps/web" in members


def test_package_json_workspaces_object_form(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"workspaces": {"packages": ["packages/*"]}}'
    )
    members = parse_workspace_members(tmp_path)
    assert "packages" in members or "packages/*" in members


def test_cargo_toml_workspace_members(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text(
        "[workspace]\n"
        'members = ["crates/engine", "crates/walker"]\n'
    )
    members = parse_workspace_members(tmp_path)
    assert "crates/engine" in members
    assert "crates/walker" in members


def test_go_work_use_block(tmp_path: Path):
    (tmp_path / "go.work").write_text(
        "go 1.22\n\n"
        "use (\n"
        '\t./cmd/app\n'
        '\t./pkg/utils\n'
        ")\n"
    )
    members = parse_workspace_members(tmp_path)
    assert "cmd/app" in members
    assert "pkg/utils" in members


def test_no_manifests_returns_empty(tmp_path: Path):
    assert parse_workspace_members(tmp_path) == set()


def test_malformed_package_json_returns_empty_or_partial(tmp_path: Path):
    (tmp_path / "package.json").write_text("not valid json {{{")
    # Must not raise
    members = parse_workspace_members(tmp_path)
    assert isinstance(members, set)
