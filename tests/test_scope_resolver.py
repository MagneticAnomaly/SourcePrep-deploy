from __future__ import annotations

from prep.core.scope_resolver import (
    path_matches_any_scope,
    resolve_mask,
)
from prep.core.scope_store import scope_store


def test_explicit_scope_known_returns_paths(tmp_settings, dummy_project):
    scope_store.create(
        dummy_project.id,
        display_name="Marketing",
        paths=["websites/marketing/"],
    )
    res = resolve_mask(dummy_project.id, scope="marketing", role=None)
    assert res.applied_scope == "marketing"
    assert res.mask == {"websites/marketing/"}
    assert res.warning is None


def test_explicit_scope_unknown_falls_back_to_global_with_warning(
    tmp_settings, dummy_project
):
    res = resolve_mask(dummy_project.id, scope="marketin", role=None)
    assert res.applied_scope == "global"
    assert res.mask is None  # global = no mask
    assert "marketin" in (res.warning or "")


def test_role_with_assigned_scope_uses_that_scope(tmp_settings, dummy_project):
    scope_store.create(
        dummy_project.id,
        display_name="Copy",
        paths=["docs/copy/"],
        assigned_to_role="copywriter",
    )
    res = resolve_mask(dummy_project.id, scope=None, role="copywriter")
    assert res.applied_scope == "copy"
    assert res.mask == {"docs/copy/"}


def test_role_without_assigned_scope_returns_global(tmp_settings, dummy_project):
    res = resolve_mask(dummy_project.id, scope=None, role="copywriter")
    assert res.applied_scope == "global"
    assert res.mask is None


def test_no_args_returns_global(tmp_settings, dummy_project):
    res = resolve_mask(dummy_project.id, scope=None, role=None)
    assert res.applied_scope == "global"
    assert res.mask is None


def test_explicit_scope_overrides_role_assignment(tmp_settings, dummy_project):
    scope_store.create(
        dummy_project.id,
        display_name="Copy",
        paths=["docs/copy/"],
        assigned_to_role="copywriter",
    )
    scope_store.create(
        dummy_project.id,
        display_name="Marketing",
        paths=["websites/marketing/"],
    )
    res = resolve_mask(dummy_project.id, scope="marketing", role="copywriter")
    assert res.applied_scope == "marketing"
    assert res.mask == {"websites/marketing/"}


def test_path_matches_any_scope_exact():
    assert path_matches_any_scope("src/foo.py", {"src/foo.py"}) is True


def test_path_matches_any_scope_prefix():
    assert path_matches_any_scope("src/foo.py", {"src/"}) is True


def test_path_matches_any_scope_no_match():
    assert path_matches_any_scope("docs/x.md", {"src/", "tests/"}) is False
