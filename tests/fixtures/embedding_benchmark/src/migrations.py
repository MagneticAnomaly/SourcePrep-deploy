"""Database migration framework for schema versioning."""

import time
import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    """A single database migration step."""
    version: int
    name: str
    up: Callable
    down: Callable


class MigrationRunner:
    """Execute and track database schema migrations."""

    def __init__(self):
        self._migrations: List[Migration] = []
        self._current_version = 0

    def register(self, version: int, name: str, up: Callable, down: Callable):
        """Register a migration step."""
        self._migrations.append(Migration(version=version, name=name, up=up, down=down))
        self._migrations.sort(key=lambda m: m.version)

    def migrate_up(self, steps: int = 0) -> List[str]:
        """Run pending up migrations."""
        pending = [m for m in self._migrations if m.version > self._current_version]
        if steps > 0:
            pending = pending[:steps]
        applied = []
        for m in pending:
            logger.info("Applying migration %d: %s", m.version, m.name)
            m.up()
            self._current_version = m.version
            applied.append(m.name)
        return applied

    def migrate_down(self, steps: int = 1) -> List[str]:
        """Rollback migrations."""
        applied = [m for m in self._migrations if m.version <= self._current_version]
        to_rollback = list(reversed(applied))[:steps]
        rolled_back = []
        for m in to_rollback:
            logger.info("Rolling back migration %d: %s", m.version, m.name)
            m.down()
            self._current_version = m.version - 1
            rolled_back.append(m.name)
        return rolled_back

    @property
    def current_version(self) -> int:
        return self._current_version

    def get_status(self) -> Dict:
        return {
            "current_version": self._current_version,
            "total_migrations": len(self._migrations),
            "pending": len([m for m in self._migrations if m.version > self._current_version]),
        }
