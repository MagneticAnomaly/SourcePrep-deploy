"""Tests for Phase 120: _build_managed_content emits a Scopes section."""
from __future__ import annotations


def test_managed_content_lists_scopes(tmp_settings, dummy_project):
    from prep.core.scope_store import scope_store

    scope_store.create(
        dummy_project.id, display_name="Marketing", paths=["websites/marketing/"]
    )
    scope_store.create(
        dummy_project.id, display_name="Data Cleaning", paths=["src/cleaners/"]
    )

    from prep.core.rules_generator import _build_managed_content

    md = _build_managed_content(
        project_name="Test",
        atlas_content="atlas body",
        included_paths=["src/"],
        is_preliminary=False,
        stats={},
        project_id=dummy_project.id,
    )

    # A Scopes section must appear
    assert "## Scopes" in md or "## Named Scopes" in md or "Scopes" in md
    # Both scope ids must appear (slugified from display_name)
    assert "marketing" in md
    assert "data_cleaning" in md
    # The scope= usage hint must appear
    assert "scope=" in md


def test_managed_content_no_scopes_section_when_none(tmp_settings, dummy_project):
    """If a project has no named scopes, the Scopes section is omitted."""
    from prep.core.rules_generator import _build_managed_content

    md = _build_managed_content(
        project_name="Test",
        atlas_content="atlas body",
        included_paths=["src/"],
        is_preliminary=False,
        stats={},
        project_id=dummy_project.id,
    )

    assert "## Scopes" not in md
    assert "## Named Scopes" not in md


def test_managed_content_scopes_omitted_without_project_id(tmp_settings):
    """When project_id is None, no Scopes section is emitted."""
    from prep.core.rules_generator import _build_managed_content

    md = _build_managed_content(
        project_name="Test",
        atlas_content="atlas body",
        included_paths=["src/"],
        is_preliminary=False,
        stats={},
        project_id=None,
    )

    assert "## Scopes" not in md
    assert "## Named Scopes" not in md


def test_managed_content_scopes_section_includes_global(tmp_settings, dummy_project):
    """The Scopes section always lists 'global' as an available scope."""
    from prep.core.scope_store import scope_store

    scope_store.create(dummy_project.id, display_name="Backend", paths=["src/backend/"])

    from prep.core.rules_generator import _build_managed_content

    md = _build_managed_content(
        project_name="Test",
        atlas_content="",
        included_paths=None,
        is_preliminary=False,
        stats={},
        project_id=dummy_project.id,
    )

    assert "global" in md
    assert "backend" in md
