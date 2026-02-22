"""API routes — user CRUD operations via HTTP-like handlers."""

from typing import Any, Dict, Optional, List


def create_user(
    username: str, email: str, password: str, db: Any
) -> Dict[str, Any]:
    """Create a new user account.

    Hashes the password, stores the user in the database,
    and returns the created user record.
    """
    import uuid
    from .auth import hash_password

    user_id = str(uuid.uuid4())
    pw = hash_password(password)

    db.execute(
        "INSERT INTO users (id, username, email, password_hash, salt) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, email, pw["hash"], pw["salt"]),
    )

    return {
        "id": user_id,
        "username": username,
        "email": email,
    }


def get_user(user_id: str, db: Any) -> Optional[Dict[str, Any]]:
    """Retrieve a user by their ID.

    Returns the user record without sensitive fields (password_hash, salt).
    Returns None if the user is not found.
    """
    from .database import query

    results = query(
        db, "SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,)
    )
    return results[0] if results else None


def list_users(db: Any, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """List users with pagination.

    Returns a list of user records sorted by creation date.
    """
    from .database import query

    return query(
        db,
        "SELECT id, username, email, created_at FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )


def update_user(
    user_id: str, db: Any, username: Optional[str] = None, email: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update a user's profile fields.

    Only non-None fields are updated. Returns the updated user record,
    or None if the user was not found.
    """
    from .database import execute

    updates = []
    params: list = []
    if username is not None:
        updates.append("username = ?")
        params.append(username)
    if email is not None:
        updates.append("email = ?")
        params.append(email)

    if not updates:
        return get_user(user_id, db)

    params.append(user_id)
    sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    execute(db, sql, tuple(params))

    return get_user(user_id, db)


def delete_user(user_id: str, db: Any) -> bool:
    """Delete a user account and all associated data.

    Removes the user's sessions, permissions, and user record.
    Returns True if the user was deleted, False if not found.
    """
    from .database import execute

    execute(db, "DELETE FROM sessions WHERE user_id = ?", (user_id,))
    execute(db, "DELETE FROM permissions WHERE user_id = ?", (user_id,))
    rows = execute(db, "DELETE FROM users WHERE id = ?", (user_id,))
    return rows > 0
