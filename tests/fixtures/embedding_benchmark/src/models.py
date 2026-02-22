"""Data models — User, Session, and Permission dataclasses."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import uuid


@dataclass
class User:
    """Represents a registered user in the system.

    Attributes:
        id: Unique user identifier (UUID).
        username: Unique login name.
        email: User's email address.
        password_hash: PBKDF2-hashed password.
        salt: Random salt used for password hashing.
        created_at: Account creation timestamp.
        permissions: List of permissions granted to this user.
    """

    username: str
    email: str
    password_hash: str
    salt: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    permissions: List["Permission"] = field(default_factory=list)

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if the user has a specific permission."""
        return any(
            p.resource == resource and p.action == action for p in self.permissions
        )


@dataclass
class Session:
    """Represents an active user session.

    Sessions are created on login and expire after a configurable duration.
    Each session holds a signed token that can be verified without database
    lookup for stateless authentication.

    Attributes:
        user_id: The ID of the authenticated user.
        token: Signed authentication token.
        created_at: When the session was created.
        expires_at: When the session expires.
        id: Unique session identifier.
    """

    user_id: str
    token: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=1)
    )
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def is_expired(self) -> bool:
        """Check if this session has expired."""
        return datetime.utcnow() > self.expires_at

    def refresh(self, duration_hours: int = 1) -> None:
        """Extend the session expiry."""
        self.expires_at = datetime.utcnow() + timedelta(hours=duration_hours)


@dataclass
class Permission:
    """Represents a permission grant for a user on a resource.

    Permissions follow a resource:action pattern, e.g.:
        - resource="users", action="read"
        - resource="projects", action="delete"
        - resource="admin", action="*"

    Attributes:
        user_id: The user this permission belongs to.
        resource: The resource being controlled (e.g., "users", "projects").
        action: The allowed action (e.g., "read", "write", "delete", "*").
        id: Unique permission identifier.
    """

    user_id: str
    resource: str
    action: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def matches(self, resource: str, action: str) -> bool:
        """Check if this permission matches a resource:action pair.

        Supports wildcard actions ("*").
        """
        if self.resource != resource:
            return False
        return self.action == "*" or self.action == action
