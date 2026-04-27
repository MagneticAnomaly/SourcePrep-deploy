from __future__ import annotations

import pytest

from prep.services.project_helpers import mutate_global_scope


def test_add_paths_to_global(tmp_settings, dummy_project_in_registry):
    new_paths = mutate_global_scope(dummy_project_in_registry.id, "add", ["src/", "docs/"])
    assert set(new_paths) == {"src/", "docs/"}


def test_remove_paths_from_global(tmp_settings, dummy_project_in_registry):
    mutate_global_scope(dummy_project_in_registry.id, "add", ["src/", "docs/"])
    new_paths = mutate_global_scope(dummy_project_in_registry.id, "remove", ["docs/"])
    assert set(new_paths) == {"src/"}


def test_add_prunes_descendants_already_present(
    tmp_settings, dummy_project_in_registry,
):
    mutate_global_scope(dummy_project_in_registry.id, "add", ["src/foo.py"])
    new_paths = mutate_global_scope(dummy_project_in_registry.id, "add", ["src/"])
    assert set(new_paths) == {"src/"}


def test_invalid_action_raises(tmp_settings, dummy_project_in_registry):
    with pytest.raises(ValueError):
        mutate_global_scope(dummy_project_in_registry.id, "frobnicate", ["x"])
