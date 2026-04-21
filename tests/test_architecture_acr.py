"""Tests for architecture ACR and issue-link lifecycle."""
from pathlib import Path

import pytest

from prep.core.architecture_acr import ArchitectureACRManager


@pytest.fixture
def acr_mgr(tmp_path: Path) -> ArchitectureACRManager:
    return ArchitectureACRManager(tmp_path)


class TestACRLifecycle:
    def test_create_acr(self, acr_mgr: ArchitectureACRManager) -> None:
        acr = acr_mgr.create_acr(
            title="Split Core into Core + Utils",
            description="Core module has too many responsibilities",
            source_type="agent",
            source_agent="researcher",
            affected_nodes=["mod_core"],
        )
        assert acr["id"].startswith("acr_")
        assert acr["title"] == "Split Core into Core + Utils"
        assert acr["status"] == "proposed"
        assert acr["affected_nodes"] == ["mod_core"]

    def test_list_acrs(self, acr_mgr: ArchitectureACRManager) -> None:
        acr_mgr.create_acr("A", "desc", "user", "user", ["n1"])
        acr_mgr.create_acr("B", "desc", "agent", "researcher", ["n2"])
        acrs = acr_mgr.list_acrs()
        assert len(acrs) == 2

    def test_approve_acr(self, acr_mgr: ArchitectureACRManager) -> None:
        acr = acr_mgr.create_acr("A", "desc", "user", "user", ["n1"])
        approved = acr_mgr.approve_acr(acr["id"], approved_by="user")
        assert approved is not None
        assert approved["status"] == "approved"
        assert approved["approved_at"] is not None
        assert approved["approved_by"] == "user"

    def test_reject_acr(self, acr_mgr: ArchitectureACRManager) -> None:
        acr = acr_mgr.create_acr("A", "desc", "user", "user", ["n1"])
        rejected = acr_mgr.reject_acr(acr["id"])
        assert rejected is not None
        assert rejected["status"] == "rejected"

    def test_approve_nonexistent_returns_none(self, acr_mgr: ArchitectureACRManager) -> None:
        assert acr_mgr.approve_acr("acr_nope") is None

    def test_reject_nonexistent_returns_none(self, acr_mgr: ArchitectureACRManager) -> None:
        assert acr_mgr.reject_acr("acr_nope") is None

    def test_get_acrs_for_node(self, acr_mgr: ArchitectureACRManager) -> None:
        acr_mgr.create_acr("A", "d", "user", "user", ["n1", "n2"])
        acr_mgr.create_acr("B", "d", "user", "user", ["n2", "n3"])
        acr_mgr.create_acr("C", "d", "user", "user", ["n3"])
        assert len(acr_mgr.get_acrs_for_node("n2")) == 2
        assert len(acr_mgr.get_acrs_for_node("n1")) == 1


class TestIssueLinkLifecycle:
    def test_link_issue(self, acr_mgr: ArchitectureACRManager) -> None:
        link = acr_mgr.link_issue(
            node_id="mod_auth",
            paperclip_issue_id="PAPER-123",
            title="Migrate JWT to OAuth2",
            priority="P1",
            status="open",
        )
        assert link["node_id"] == "mod_auth"
        assert link["paperclip_issue_id"] == "PAPER-123"

    def test_list_issue_links(self, acr_mgr: ArchitectureACRManager) -> None:
        acr_mgr.link_issue("n1", "P-1", "Issue 1", "P1", "open")
        acr_mgr.link_issue("n1", "P-2", "Issue 2", "P2", "open")
        acr_mgr.link_issue("n2", "P-3", "Issue 3", "P1", "open")
        assert len(acr_mgr.get_issues_for_node("n1")) == 2
        assert len(acr_mgr.get_issues_for_node("n2")) == 1
        assert len(acr_mgr.list_issue_links()) == 3

    def test_unlink_issue(self, acr_mgr: ArchitectureACRManager) -> None:
        acr_mgr.link_issue("n1", "P-1", "Issue 1", "P1", "open")
        assert acr_mgr.unlink_issue("n1", "P-1") is True
        assert len(acr_mgr.get_issues_for_node("n1")) == 0

    def test_unlink_nonexistent_returns_false(self, acr_mgr: ArchitectureACRManager) -> None:
        assert acr_mgr.unlink_issue("n1", "NOPE") is False
