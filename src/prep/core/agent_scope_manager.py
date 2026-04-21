"""
Agent Scope Manager — Phase 67 (Agent Knowledge Scopes)
=========================================================

Manages per-agent file selections for the Knowledge Scope (RAG index).

Each agent role (CEO, CTO, UX Designer, etc.) can have its own curated
file tree.  The selections are persisted in the settings_store under
the namespace ``agent_scope/<project_id>``.

**Key design decisions:**

1. **UI-Siloed, Backend-Pooled.**  The dashboard shows a separate file
   tree per agent, but the actual embedding index uses the *union* of
   all agent scopes + the global scope.  Files are only embedded once.

2. **Runtime Masking.**  When an agent calls ``codrag_search(role=...)``,
   the search results are filtered to only return hits from that agent's
   configured files.  Agents without a scope fall back to the global tree.

3. **Settings Store Persistence.**  Agent scopes are stored as JSON
   under the key ``agent_scope.<role>`` in the per-project settings
   namespace.  This keeps them alongside existing project config and
   survives restarts.

Usage::

    from prep.core.agent_scope_manager import agent_scope_manager

    # UI sets files for the CTO
    agent_scope_manager.set_agent_scope("proj-1", "cto", ["src/", "docs/ARCHITECTURE.md"])

    # At search time — get the mask
    mask = agent_scope_manager.get_agent_mask("proj-1", "cto")
    # → {"src/", "docs/ARCHITECTURE.md"}

    # For the embedding builder — get union of all scopes
    all_paths = agent_scope_manager.get_merged_rag_scope("proj-1")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Settings key prefix for agent scopes
_SCOPE_KEY_PREFIX = "agent_scope"


class AgentScopeManager:
    """Manages per-agent Knowledge Scope file selections.

    Backed by the SettingsStore (SQLite).  Each agent's file list is
    stored as a JSON array under ``agent_scope.<role>`` in the
    per-project settings namespace.
    """

    # ── Read ─────────────────────────────────────────────────────

    def get_agent_scope(self, project_id: str, role: str) -> List[str]:
        """Get the list of selected file paths for an agent role.

        Returns an empty list if no scope is configured for this role.
        """
        from prep.services.settings_store import settings
        key = f"{_SCOPE_KEY_PREFIX}.{_normalize_role(role)}"
        result = settings.project_get(project_id, key, default=[])
        if isinstance(result, list):
            return result
        return []

    def get_agent_mask(
        self, project_id: str, role: str
    ) -> Optional[Set[str]]:
        """Get the file mask for search filtering.

        Returns a set of file paths that the agent is allowed to see,
        or ``None`` if no agent-specific scope is configured (meaning
        the agent should fall back to the global scope).
        """
        paths = self.get_agent_scope(project_id, role)
        if not paths:
            return None  # No scope → fall back to global
        return set(paths)

    def list_agent_roles(self, project_id: str) -> List[str]:
        """List all roles that have a configured scope for this project."""
        from prep.services.settings_store import settings
        all_settings = settings.project_get_all(project_id)
        roles = []
        prefix = f"{_SCOPE_KEY_PREFIX}."
        for key in all_settings:
            if key.startswith(prefix):
                role = key[len(prefix):]
                if role:
                    roles.append(role)
        return sorted(roles)

    def get_all_agent_scopes(
        self, project_id: str
    ) -> Dict[str, List[str]]:
        """Get all agent scopes for a project.

        Returns ``{role: [paths]}`` for all configured roles.
        """
        from prep.services.settings_store import settings
        all_settings = settings.project_get_all(project_id)
        result: Dict[str, List[str]] = {}
        prefix = f"{_SCOPE_KEY_PREFIX}."
        for key, value in all_settings.items():
            if key.startswith(prefix):
                role = key[len(prefix):]
                if role and isinstance(value, list):
                    result[role] = value
        return result

    # ── Write ────────────────────────────────────────────────────

    def set_agent_scope(
        self, project_id: str, role: str, paths: List[str]
    ) -> List[str]:
        """Replace the entire scope for an agent role.

        Returns the new sorted path list.
        """
        from prep.services.settings_store import settings
        key = f"{_SCOPE_KEY_PREFIX}.{_normalize_role(role)}"
        clean = sorted(set(p for p in paths if p))
        settings.project_set(project_id, key, clean)
        logger.info(
            "Agent scope set: project=%s role=%s paths=%d",
            project_id, role, len(clean),
        )
        return clean

    def add_agent_paths(
        self, project_id: str, role: str, paths: List[str]
    ) -> List[str]:
        """Add paths to an agent's scope (merge with existing).

        Returns the new sorted path list.
        """
        current = set(self.get_agent_scope(project_id, role))
        for p in paths:
            if p:
                current.add(p)
                # Remove descendants — parent covers them
                prefix = p + "/"
                current = {x for x in current if not x.startswith(prefix) or x == p}
        return self.set_agent_scope(project_id, role, list(current))

    def remove_agent_paths(
        self, project_id: str, role: str, paths: List[str]
    ) -> List[str]:
        """Remove paths from an agent's scope.

        Returns the new sorted path list.
        """
        current = set(self.get_agent_scope(project_id, role))
        for p in paths:
            current.discard(p)
            # Also remove descendants
            prefix = p + "/"
            current = {x for x in current if not x.startswith(prefix)}
        return self.set_agent_scope(project_id, role, list(current))

    def delete_agent_scope(self, project_id: str, role: str) -> bool:
        """Delete the entire scope for an agent role.

        Returns True if the scope existed and was deleted.
        """
        from prep.services.settings_store import settings
        key = f"{_SCOPE_KEY_PREFIX}.{_normalize_role(role)}"
        deleted = settings.project_delete(project_id, key)
        if deleted:
            logger.info(
                "Agent scope deleted: project=%s role=%s", project_id, role
            )
        return deleted

    # ── Aggregation ──────────────────────────────────────────────

    def get_merged_rag_scope(self, project_id: str) -> Set[str]:
        """Get the union of all agent scopes + the global scope.

        This is what the KnowledgeIndex builder should embed — the
        deduplicated set of all files any agent might need.
        """
        from prep.services.project_helpers import require_project
        project = require_project(project_id)

        # Start with the global included_paths
        global_paths = set(
            (project.config or {}).get("included_paths", [])
        )

        # Union in all agent scopes
        all_scopes = self.get_all_agent_scopes(project_id)
        for role_paths in all_scopes.values():
            global_paths.update(role_paths)

        return global_paths

    def matches_agent_scope(
        self,
        project_id: str,
        role: str,
        file_path: str,
    ) -> bool:
        """Check if a file path is within the agent's configured scope.

        Handles both exact path matches and directory prefix matches
        (e.g., scope has ``src/`` and file_path is ``src/foo.py``).
        """
        mask = self.get_agent_mask(project_id, role)
        if mask is None:
            return True  # No scope = everything allowed
        return _path_matches_scope(file_path, mask)


def _normalize_role(role: str) -> str:
    """Normalize a role name for use as a settings key.

    Lowercase, replace spaces/special chars with underscores.
    """
    return re.sub(r"[^a-z0-9]+", "_", role.lower().strip()).strip("_")


def _path_matches_scope(file_path: str, scope_paths: Set[str]) -> bool:
    """Check if file_path is covered by any path in scope_paths.

    Matches exactly or as a directory prefix (scope entry ``src/``
    matches ``src/foo.py``).
    """
    if file_path in scope_paths:
        return True
    for sp in scope_paths:
        prefix = sp.rstrip("/") + "/"
        if file_path.startswith(prefix):
            return True
    return False


# ── Module-level singleton ───────────────────────────────────────
agent_scope_manager = AgentScopeManager()
