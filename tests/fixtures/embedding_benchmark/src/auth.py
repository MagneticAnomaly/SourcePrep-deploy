"""Authentication module — login, token verification, password hashing."""

import hashlib
import hmac
import secrets
import time
from typing import Optional, Dict, Any


SECRET_KEY = "super-secret-key-change-in-production"
TOKEN_EXPIRY_SECONDS = 3600


def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    """Hash a password using PBKDF2 with a random salt.

    Returns a dict with 'hash' and 'salt' keys.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return {"hash": dk.hex(), "salt": salt}


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against a stored hash and salt."""
    result = hash_password(password, salt=salt)
    return hmac.compare_digest(result["hash"], stored_hash)


def generate_token(user_id: str) -> str:
    """Generate a signed authentication token for a user.

    Token format: user_id:timestamp:signature
    """
    timestamp = str(int(time.time()))
    payload = f"{user_id}:{timestamp}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_token(token: str) -> Optional[str]:
    """Verify an authentication token and return the user_id if valid.

    Returns None if the token is invalid or expired.
    """
    parts = token.split(":")
    if len(parts) != 3:
        return None

    user_id, timestamp_str, signature = parts

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return None

    if time.time() - timestamp > TOKEN_EXPIRY_SECONDS:
        return None

    payload = f"{user_id}:{timestamp_str}"
    expected_sig = hmac.new(
        SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        return None

    return user_id


def login(username: str, password: str, user_store: Dict[str, Any]) -> Optional[str]:
    """Authenticate a user and return a token.

    Looks up the user in user_store, verifies the password,
    and returns a signed token on success. Returns None on failure.
    """
    user = user_store.get(username)
    if user is None:
        return None

    if not verify_password(password, user["password_hash"], user["salt"]):
        return None

    return generate_token(user["id"])
