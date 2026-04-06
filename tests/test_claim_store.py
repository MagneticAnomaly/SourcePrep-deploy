"""Tests for ClaimStore — soft file claims with auto-expiry."""
import time

import pytest

from codrag.services.collaboration.claims import ClaimStore


@pytest.fixture
def store(tmp_path):
    s = ClaimStore(tmp_path / "test.db")
    yield s
    s.close()


def test_claim_returns_id(store):
    cid = store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    assert isinstance(cid, str)
    assert len(cid) > 0


def test_is_claimed_exact_path(store):
    store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    assert store.is_claimed("proj-1", "src/auth/login.py") is True
    assert store.is_claimed("proj-1", "src/other.py") is False


def test_is_claimed_directory_prefix(store):
    store.claim("proj-1", "researcher", "src/auth/", "Research")
    assert store.is_claimed("proj-1", "src/auth/login.py") is True
    assert store.is_claimed("proj-1", "src/auth/session.py") is True
    assert store.is_claimed("proj-1", "src/other.py") is False


def test_is_claimed_exclude_agent(store):
    store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    assert store.is_claimed(
        "proj-1", "src/auth/login.py", exclude_agent="researcher",
    ) is False
    assert store.is_claimed(
        "proj-1", "src/auth/login.py", exclude_agent="custodian",
    ) is True


def test_release_claim(store):
    cid = store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    assert store.is_claimed("proj-1", "src/auth/login.py") is True

    assert store.release(cid) is True
    assert store.is_claimed("proj-1", "src/auth/login.py") is False


def test_expired_claims_not_active(store):
    store.claim("proj-1", "researcher", "src/auth/login.py", "Research",
                ttl=0.0)
    time.sleep(0.01)
    assert store.is_claimed("proj-1", "src/auth/login.py") is False


def test_get_active_excludes_expired(store):
    store.claim("proj-1", "researcher", "src/old.py", "Old", ttl=0.0)
    time.sleep(0.01)
    store.claim("proj-1", "researcher", "src/new.py", "New", ttl=86400)

    active = store.get_active("proj-1")
    paths = [c.path for c in active]
    assert "src/new.py" in paths
    assert "src/old.py" not in paths


def test_cleanup_expired(store):
    store.claim("proj-1", "researcher", "src/old.py", "Old", ttl=0.0)
    time.sleep(0.01)
    cleaned = store.cleanup_expired("proj-1")
    assert cleaned >= 1


def test_get_claims_for_path(store):
    store.claim("proj-1", "researcher", "src/auth/login.py", "Research")
    store.claim("proj-1", "custodian", "src/auth/login.py", "Cleanup")

    claims = store.get_claims_for_path("proj-1", "src/auth/login.py")
    assert len(claims) == 2
    roles = {c.agent_role for c in claims}
    assert roles == {"researcher", "custodian"}
