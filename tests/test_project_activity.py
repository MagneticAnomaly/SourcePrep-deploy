"""Tests for project activity status (Phase 41).

Pro tier: explicit active/inactive toggle via config.active
Free tier: 1 active + 2 frozen + rest locked, auto-determined by updated_at
"""

import pytest
from unittest.mock import patch, MagicMock
from codrag.core.project_registry import Project
from codrag.services.project_helpers import (
    is_project_active,
    get_free_tier_slots,
    get_project_activity_status,
    _FREE_ACTIVE_SLOTS,
)


def _make_project(pid: str, name: str = "test", updated_at: str = "2026-01-01T00:00:00", config: dict = None) -> Project:
    return Project(
        id=pid, name=name, path=f"/tmp/{pid}", mode="standalone",
        config=config or {}, created_at="2026-01-01T00:00:00", updated_at=updated_at,
    )


# ── is_project_active (Pro tier toggle) ──────────────────────


class TestIsProjectActive:
    def test_default_true(self):
        """Projects without explicit active field default to active."""
        proj = _make_project("p1", config={})
        assert is_project_active(proj) is True

    def test_explicit_true(self):
        proj = _make_project("p1", config={"active": True})
        assert is_project_active(proj) is True

    def test_explicit_false(self):
        proj = _make_project("p1", config={"active": False})
        assert is_project_active(proj) is False

    def test_none_config(self):
        """Project with None config defaults to active."""
        proj = Project(id="p1", name="t", path="/tmp/p1", mode="standalone",
                       config=None, created_at="", updated_at="")
        assert is_project_active(proj) is True

    def test_existing_config_preserved(self):
        """active field doesn't interfere with other config."""
        proj = _make_project("p1", config={"trace": {"enabled": True}, "active": False})
        assert is_project_active(proj) is False
        assert proj.config["trace"]["enabled"] is True


# ── get_free_tier_slots ──────────────────────────────────────


class TestFreeTierSlots:
    def test_single_project(self):
        projects = [_make_project("p1", updated_at="2026-02-28T12:00:00")]
        slots = get_free_tier_slots(projects)
        assert slots == {"p1": "active"}

    def test_three_projects_ordered(self):
        """Most recent = active, next 2 = frozen."""
        projects = [
            _make_project("p1", updated_at="2026-02-28T12:00:00"),
            _make_project("p2", updated_at="2026-02-27T12:00:00"),
            _make_project("p3", updated_at="2026-02-26T12:00:00"),
        ]
        slots = get_free_tier_slots(projects)
        assert slots["p1"] == "active"
        assert slots["p2"] == "active"
        assert slots["p3"] == "active"

    def test_four_projects_one_frozen(self):
        """4th project is frozen (was locked with 1-slot, now frozen with 3-slot)."""
        projects = [
            _make_project("p1", updated_at="2026-02-28T12:00:00"),
            _make_project("p2", updated_at="2026-02-27T12:00:00"),
            _make_project("p3", updated_at="2026-02-26T12:00:00"),
            _make_project("p4", updated_at="2026-02-25T12:00:00"),
        ]
        slots = get_free_tier_slots(projects)
        assert slots["p1"] == "active"
        assert slots["p2"] == "active"
        assert slots["p3"] == "active"
        assert slots["p4"] == "locked"

    def test_many_projects(self):
        """Only first 3 get slots, rest are locked."""
        projects = [
            _make_project(f"p{i}", updated_at=f"2026-02-{28-i:02d}T12:00:00")
            for i in range(10)
        ]
        slots = get_free_tier_slots(projects)
        active_count = sum(1 for s in slots.values() if s == "active")
        locked_count = sum(1 for s in slots.values() if s == "locked")
        assert active_count == _FREE_ACTIVE_SLOTS  # 3
        assert locked_count == 7  # 10 total - 3 active

    def test_empty_projects(self):
        slots = get_free_tier_slots([])
        assert slots == {}

    def test_sorting_by_updated_at(self):
        """Projects are sorted by updated_at, not insertion order."""
        projects = [
            _make_project("old", updated_at="2026-01-01T00:00:00"),
            _make_project("new", updated_at="2026-02-28T23:59:59"),
            _make_project("mid", updated_at="2026-02-15T12:00:00"),
        ]
        slots = get_free_tier_slots(projects)
        assert slots["new"] == "active"
        assert slots["mid"] == "active"
        assert slots["old"] == "active"

    def test_two_projects(self):
        """With 2 projects, both active, none frozen or locked."""
        projects = [
            _make_project("p1", updated_at="2026-02-28T12:00:00"),
            _make_project("p2", updated_at="2026-02-27T12:00:00"),
        ]
        slots = get_free_tier_slots(projects)
        assert slots["p1"] == "active"
        assert slots["p2"] == "active"

    def test_archived_projects_are_locked(self):
        projects = [
            _make_project("archived", updated_at="2026-02-28T12:00:00", config={"archived": True}),
            _make_project("p1", updated_at="2026-02-27T12:00:00"),
            _make_project("p2", updated_at="2026-02-26T12:00:00"),
            _make_project("p3", updated_at="2026-02-25T12:00:00"),
        ]
        slots = get_free_tier_slots(projects)
        assert slots["archived"] == "locked"
        assert slots["p1"] == "active"
        assert slots["p2"] == "active"
        assert slots["p3"] == "active"


# ── get_project_activity_status (unified) ────────────────────


class TestProjectActivityStatus:
    @patch("codrag.core.feature_gate.get_license")
    def test_pro_tier_active(self, mock_lic):
        from codrag.core.feature_gate import Tier, License
        mock_lic.return_value = License(tier=Tier.PERPETUAL)
        proj = _make_project("p1", config={"active": True})

        with patch.object(get_project_activity_status, "__module__", "codrag.services.project_helpers"):
            pass  # just need the import path
        from codrag.services import project_helpers as ph
        orig_get_reg = ph.get_registry
        mock_reg = MagicMock()
        mock_reg.get_project.return_value = proj
        ph.get_registry = lambda: mock_reg
        try:
            status = get_project_activity_status("p1")
            assert status == "active"
        finally:
            ph.get_registry = orig_get_reg

    @patch("codrag.core.feature_gate.get_license")
    def test_pro_tier_inactive(self, mock_lic):
        from codrag.core.feature_gate import Tier, License
        mock_lic.return_value = License(tier=Tier.PERPETUAL)
        proj = _make_project("p1", config={"active": False})

        from codrag.services import project_helpers as ph
        orig = ph.get_registry
        mock_reg = MagicMock()
        mock_reg.get_project.return_value = proj
        ph.get_registry = lambda: mock_reg
        try:
            assert get_project_activity_status("p1") == "inactive"
        finally:
            ph.get_registry = orig

    @patch("codrag.core.feature_gate.get_license")
    def test_pro_tier_default_active(self, mock_lic):
        from codrag.core.feature_gate import Tier, License
        mock_lic.return_value = License(tier=Tier.MONTHLY)
        proj = _make_project("p1", config={})

        from codrag.services import project_helpers as ph
        orig = ph.get_registry
        mock_reg = MagicMock()
        mock_reg.get_project.return_value = proj
        ph.get_registry = lambda: mock_reg
        try:
            assert get_project_activity_status("p1") == "active"
        finally:
            ph.get_registry = orig

    @patch("codrag.core.feature_gate.get_license")
    def test_free_tier_slots(self, mock_lic):
        from codrag.core.feature_gate import Tier, License
        mock_lic.return_value = License(tier=Tier.FREE)
        projects = [
            _make_project("newest", updated_at="2026-02-28T23:00:00"),
            _make_project("middle", updated_at="2026-02-27T12:00:00"),
            _make_project("oldest", updated_at="2026-02-26T12:00:00"),
            _make_project("ancient", updated_at="2026-01-01T00:00:00"),
        ]

        from codrag.services import project_helpers as ph
        orig = ph.get_registry
        mock_reg = MagicMock()
        mock_reg.list_projects.return_value = projects
        mock_reg.get_project.side_effect = lambda x: next((p for p in projects if p.id == x), None)
        ph.get_registry = lambda: mock_reg
        try:
            assert get_project_activity_status("newest") == "active"
            assert get_project_activity_status("middle") == "active"
            assert get_project_activity_status("oldest") == "active"
            assert get_project_activity_status("ancient") == "locked"
        finally:
            ph.get_registry = orig

    @patch("codrag.core.feature_gate.get_license")
    def test_free_tier_unknown_project(self, mock_lic):
        from codrag.core.feature_gate import Tier, License
        mock_lic.return_value = License(tier=Tier.FREE)

        from codrag.services import project_helpers as ph
        orig = ph.get_registry
        mock_reg = MagicMock()
        mock_reg.list_projects.return_value = []
        ph.get_registry = lambda: mock_reg
        try:
            assert get_project_activity_status("nonexistent") == "locked"
        finally:
            ph.get_registry = orig

    @patch("codrag.core.feature_gate.get_license")
    def test_team_tier_uses_config_active(self, mock_lic):
        from codrag.core.feature_gate import Tier, License
        mock_lic.return_value = License(tier=Tier.TEAM)
        proj = _make_project("p1", config={"active": True})

        from codrag.services import project_helpers as ph
        orig = ph.get_registry
        mock_reg = MagicMock()
        mock_reg.get_project.return_value = proj
        ph.get_registry = lambda: mock_reg
        try:
            assert get_project_activity_status("p1") == "active"
        finally:
            ph.get_registry = orig


# ── Slot constants ───────────────────────────────────────────


class TestSlotConstants:
    def test_free_active_slots(self):
        assert _FREE_ACTIVE_SLOTS == 3
