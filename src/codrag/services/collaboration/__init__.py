"""Agent Collaboration Infrastructure — Phase 73.5.

Provides cross-agent awareness, coordination, and conflict detection.
All stores share the codrag_settings.db SQLite database.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


class CollaborationHub:
    """Single entry point for all collaboration infrastructure.

    Initialized once by the daemon. Agent engines, API routers,
    and MCP handlers access collaboration features through this hub.
    """

    def __init__(self, db_path: Path) -> None:
        from codrag.services.collaboration.activity import ActivityStore

        self.activity = ActivityStore(db_path)


# Module-level singleton (initialized by daemon startup)
_hub: Optional[CollaborationHub] = None


def init_collaboration(db_path: Path) -> CollaborationHub:
    """Initialize the collaboration hub singleton. Called by daemon startup."""
    global _hub
    _hub = CollaborationHub(db_path)
    return _hub


def get_collaboration_hub() -> Optional[CollaborationHub]:
    """Return the hub singleton, or None if not initialized."""
    return _hub
