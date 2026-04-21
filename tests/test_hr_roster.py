"""Tests for HR roster persistence."""
import json
from pathlib import Path

import pytest

from prep.agents.hr.roster import Roster
from prep.agents.shared.models import RoleSpec


@pytest.fixture
def roster_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def roster(roster_dir: Path) -> Roster:
    return Roster(roster_dir)


class TestRosterSaveLoad:
    def test_save_and_load_role(self, roster: Roster) -> None:
        role = RoleSpec(slug="backend_dev", display_name="Backend Developer",
                        agents_md="# Backend Dev", soul_md="# Soul")
        roster.save_role(role)
        loaded = roster.get_role("backend_dev")
        assert loaded is not None
        assert loaded.display_name == "Backend Developer"
        assert loaded.agents_md == "# Backend Dev"

    def test_list_roles(self, roster: Roster) -> None:
        roster.save_role(RoleSpec(slug="a", display_name="A"))
        roster.save_role(RoleSpec(slug="b", display_name="B"))
        slugs = roster.list_roles()
        assert set(slugs) == {"a", "b"}

    def test_remove_role(self, roster: Roster) -> None:
        roster.save_role(RoleSpec(slug="x", display_name="X"))
        assert roster.get_role("x") is not None
        roster.remove_role("x")
        assert roster.get_role("x") is None

    def test_remove_nonexistent_is_noop(self, roster: Roster) -> None:
        roster.remove_role("nonexistent")  # should not raise

    def test_overwrite_existing(self, roster: Roster) -> None:
        roster.save_role(RoleSpec(slug="r", display_name="V1", agents_md="old"))
        roster.save_role(RoleSpec(slug="r", display_name="V2", agents_md="new"))
        loaded = roster.get_role("r")
        assert loaded is not None
        assert loaded.display_name == "V2"
        assert loaded.agents_md == "new"

    def test_empty_roster(self, roster: Roster) -> None:
        assert roster.list_roles() == []
        assert roster.get_role("any") is None

    def test_persistence_across_instances(self, roster_dir: Path) -> None:
        r1 = Roster(roster_dir)
        r1.save_role(RoleSpec(slug="p", display_name="P"))
        r2 = Roster(roster_dir)
        assert r2.get_role("p") is not None

    def test_roster_file_is_valid_json(self, roster: Roster, roster_dir: Path) -> None:
        roster.save_role(RoleSpec(slug="j", display_name="J"))
        data = json.loads((roster_dir / "hr_roster.json").read_text())
        assert "roles" in data
