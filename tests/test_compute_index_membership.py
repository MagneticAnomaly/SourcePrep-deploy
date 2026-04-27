from __future__ import annotations

from prep.core.scope_store import scope_store
from prep.services.project_helpers import compute_index_membership


def test_membership_is_global_when_no_scopes(tmp_settings, dummy_project):
    dummy_project.config["included_paths"] = ["src/", "docs/"]
    members = compute_index_membership(dummy_project.id)
    assert members == {"src/", "docs/"}


def test_membership_unions_global_with_scope_paths(
    tmp_settings, dummy_project,
):
    dummy_project.config["included_paths"] = ["src/"]
    scope_store.create(dummy_project.id, display_name="Marketing",
                       paths=["websites/marketing/", "src/marketing.md"])
    members = compute_index_membership(dummy_project.id)
    assert members == {"src/", "websites/marketing/", "src/marketing.md"}


def test_membership_dedups_overlapping_paths(tmp_settings, dummy_project):
    dummy_project.config["included_paths"] = ["src/"]
    scope_store.create(dummy_project.id, display_name="A", paths=["src/"])
    scope_store.create(dummy_project.id, display_name="B", paths=["src/"])
    members = compute_index_membership(dummy_project.id)
    assert members == {"src/"}


def test_membership_with_no_global_returns_scope_union(
    tmp_settings, dummy_project,
):
    dummy_project.config["included_paths"] = []
    scope_store.create(dummy_project.id, display_name="Marketing",
                       paths=["websites/marketing/"])
    members = compute_index_membership(dummy_project.id)
    assert members == {"websites/marketing/"}
