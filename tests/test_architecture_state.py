"""Tests for architecture state persistence (layouts, notes)."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from prep.core.architecture_state import ArchitectureState


@pytest.fixture
def arch_state(tmp_path: Path) -> ArchitectureState:
    return ArchitectureState(tmp_path)


class TestArchitectureState:
    """State persistence to <index_dir>/architecture/."""

    def test_empty_state(self, arch_state: ArchitectureState):
        """Fresh project has empty state."""
        state = arch_state.load_state()
        assert state["layouts"] == {}
        assert state["module_overrides"] == {}

    def test_save_and_load_state(self, arch_state: ArchitectureState):
        state = {
            "layouts": {
                "root": {
                    "layer_path": "",
                    "positions": [{"id": "mod_1", "x": 100, "y": 200}],
                    "viewport": {"x": 0, "y": 0, "zoom": 1.0},
                }
            },
            "module_overrides": {"mod_1": {"name": "Auth"}},
        }
        arch_state.save_state(state)
        loaded = arch_state.load_state()
        assert loaded["layouts"]["root"]["positions"][0]["x"] == 100
        assert loaded["module_overrides"]["mod_1"]["name"] == "Auth"

    def test_creates_directory(self, arch_state: ArchitectureState):
        arch_state.save_state({"layouts": {}, "module_overrides": {}})
        assert (arch_state.base_dir / "architecture").is_dir()


class TestNotes:
    """Notes CRUD operations."""

    def test_list_notes_empty(self, arch_state: ArchitectureState):
        assert arch_state.list_notes() == []

    def test_create_note(self, arch_state: ArchitectureState):
        note = arch_state.create_note(
            node_id="mod_1",
            content="Migrating to OAuth2",
            note_type="adr",
            author="user",
            color="yellow",
        )
        assert note["id"]
        assert note["node_id"] == "mod_1"
        assert note["content"] == "Migrating to OAuth2"
        assert note["note_type"] == "adr"

    def test_list_notes_after_create(self, arch_state: ArchitectureState):
        arch_state.create_note("mod_1", "Note 1", "comment", "user")
        arch_state.create_note("mod_2", "Note 2", "adr", "user")
        notes = arch_state.list_notes()
        assert len(notes) == 2

    def test_update_note(self, arch_state: ArchitectureState):
        note = arch_state.create_note("mod_1", "Draft", "comment", "user")
        updated = arch_state.update_note(note["id"], content="Final version")
        assert updated["content"] == "Final version"
        assert updated["id"] == note["id"]

    def test_update_note_not_found(self, arch_state: ArchitectureState):
        result = arch_state.update_note("nonexistent", content="x")
        assert result is None

    def test_delete_note(self, arch_state: ArchitectureState):
        note = arch_state.create_note("mod_1", "Temp", "comment", "user")
        deleted = arch_state.delete_note(note["id"])
        assert deleted is True
        assert arch_state.list_notes() == []

    def test_delete_note_not_found(self, arch_state: ArchitectureState):
        assert arch_state.delete_note("nonexistent") is False

    def test_get_notes_for_node(self, arch_state: ArchitectureState):
        arch_state.create_note("mod_1", "Note A", "comment", "user")
        arch_state.create_note("mod_2", "Note B", "adr", "user")
        arch_state.create_note("mod_1", "Note C", "adr", "user")
        mod1_notes = arch_state.get_notes_for_node("mod_1")
        assert len(mod1_notes) == 2
