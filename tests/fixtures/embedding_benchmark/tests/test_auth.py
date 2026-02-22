"""Tests for the authentication module."""

from src.auth import hash_password, verify_password, generate_token, verify_token, login


def test_login_success():
    """Test that a valid username and password returns a token."""
    pw = hash_password("secret123")
    user_store = {
        "alice": {
            "id": "user-1",
            "password_hash": pw["hash"],
            "salt": pw["salt"],
        }
    }
    token = login("alice", "secret123", user_store)
    assert token is not None
    assert verify_token(token) == "user-1"


def test_login_wrong_password():
    """Test that a wrong password returns None."""
    pw = hash_password("secret123")
    user_store = {
        "alice": {
            "id": "user-1",
            "password_hash": pw["hash"],
            "salt": pw["salt"],
        }
    }
    assert login("alice", "wrong", user_store) is None


def test_hash_password_produces_different_salts():
    """Test that hashing the same password twice produces different salts."""
    result1 = hash_password("password")
    result2 = hash_password("password")
    assert result1["salt"] != result2["salt"]
    assert result1["hash"] != result2["hash"]


def test_verify_token_expired():
    """Test that an expired token returns None."""
    import time
    # Manually craft a token with old timestamp
    token = "user-1:1000000000:fakesig"
    assert verify_token(token) is None
