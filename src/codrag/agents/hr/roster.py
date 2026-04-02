"""JSON-backed roster persistence for generated agent roles.

Stores role specs to ``<index_dir>/hr_roster.json``.
Thread-safe via atomic write (write-to-temp then rename).
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from codrag.agents.shared.models import RoleSpec

logger = logging.getLogger(__name__)

_ROSTER_FILENAME = "hr_roster.json"


class Roster:
    """Manages the persistent roster of generated agent roles.

    Args:
        index_dir: Directory where ``hr_roster.json`` is stored.
    """

    def __init__(self, index_dir: Path) -> None:
        self._path = Path(index_dir) / _ROSTER_FILENAME
        self._roles: Dict[str, RoleSpec] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._roles = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._roles = {
                slug: RoleSpec.from_dict(rd)
                for slug, rd in data.get("roles", {}).items()
            }
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load roster from %s: %s", self._path, exc)
            self._roles = {}

    def _save(self) -> None:
        data = {"roles": {slug: role.to_dict() for slug, role in self._roles.items()}}
        fd, tmp = tempfile.mkstemp(
            dir=self._path.parent, suffix=".tmp", prefix=".hr_roster_"
        )
        try:
            import os
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(tmp).replace(self._path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def save_role(self, role: RoleSpec) -> None:
        """Save or overwrite a role in the roster."""
        self._roles[role.slug] = role
        self._save()

    def get_role(self, slug: str) -> Optional[RoleSpec]:
        """Get a role by slug, or None if not found."""
        return self._roles.get(slug)

    def list_roles(self) -> List[str]:
        """Return sorted list of all role slugs."""
        return sorted(self._roles.keys())

    def remove_role(self, slug: str) -> None:
        """Remove a role by slug. No-op if not found."""
        if slug in self._roles:
            del self._roles[slug]
            self._save()
