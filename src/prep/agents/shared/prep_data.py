"""Read-only facade wrapping Prep's internal data sources for agent engines.

Provides a stable, simplified interface to OpportunityManager, CodebaseAtlas,
TraceIndex, and ObservationStore — shielding agent code from internal API changes.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from prep.core.index import CodeIndex
from prep.core.scope_resolver import path_matches_any_scope, resolve_mask

logger = logging.getLogger(__name__)


class PrepDataAccess:
    """Read-only wrapper around Prep internal data sources.

    Instantiate once per agent run, passing the project's index directory.

    Args:
        index_dir: Path to the Prep index directory (e.g. ``.sourceprep/`` or
            ``~/.local/share/sourceprep/projects/<slug>/``).
        project_root: Optional path to the project source root.  Used for
            audit refresh operations.
        project_id: Project ID used to scope observations.
    """

    def __init__(
        self,
        index_dir: Path,
        project_root: Optional[Path] = None,
        project_id: str = "",
    ) -> None:
        self._index_dir = Path(index_dir)
        self._project_root = Path(project_root) if project_root else None
        self._project_id = project_id

        # Opportunity manager
        from prep.core.audit.opportunity_manager import OpportunityManager
        self._opp_manager = OpportunityManager(self._index_dir)

        # Atlas
        from prep.core.atlas.generator import CodebaseAtlas
        self._atlas = CodebaseAtlas(self._index_dir, project_root=self._project_root)

        # Trace index — optional; may not be built yet
        self._trace_index = None
        try:
            from prep.core.trace.index import TraceIndex
            ti = TraceIndex(self._index_dir)
            if ti.exists() and ti.load():
                if ti.node_count() > 0:
                    self._trace_index = ti
        except Exception as exc:  # pragma: no cover
            logger.debug("TraceIndex unavailable (non-fatal): %s", exc)

        # Observation store singleton
        from prep.services.observation_store import observation_store
        self._observation_store = observation_store

    # ── Audit / Opportunities ────────────────────────────────────

    def get_audit_findings(
        self,
        min_priority: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ) -> list:
        """Return active (non-dismissed) audit findings.

        Args:
            min_priority: Minimum priority gate, e.g. ``"P1"`` returns P0 + P1.
            categories: Optional list of category strings to filter by.

        Returns:
            List of :class:`~prep.core.audit.action_item.ActionItem` instances.
        """
        kwargs: Dict[str, Any] = {"include_dismissed": False}
        if min_priority is not None:
            kwargs["min_priority"] = min_priority
        if categories is not None:
            kwargs["categories"] = categories
        return self._opp_manager.get_opportunities(**kwargs)

    def refresh_audit(
        self,
        categories: Optional[List[str]] = None,
    ) -> list:
        """Re-run scanners and return refreshed findings.

        Args:
            categories: Optional list of category strings to limit scanning.

        Returns:
            List of :class:`~prep.core.audit.action_item.ActionItem` instances.
        """
        kwargs: Dict[str, Any] = {"project_root": self._project_root}
        if categories is not None:
            kwargs["categories"] = categories
        return self._opp_manager.refresh(**kwargs)

    # ── Atlas ────────────────────────────────────────────────────

    def get_atlas(self, role: Optional[str] = None) -> str:
        """Return the cached atlas document content, or ``""`` if unavailable.

        If *role* is provided, returns a role-projected sub-atlas filtered
        through the role's lens (layer weights, domain affinity, detail level).
        """
        doc = self._atlas.load()
        if doc is None:
            return ""
        full_content = doc.content or ""

        if role and full_content:
            try:
                from prep.core.atlas.role_resolver import resolve_role
                from prep.core.atlas.role_projection import project_atlas_for_role

                role_vector = resolve_role(role)
                return project_atlas_for_role(
                    role_vector, self._index_dir, atlas_content=full_content
                )
            except Exception as exc:
                logger.debug("Role projection failed for %r: %s", role, exc)

        return full_content

    # ── Module Structure ──────────────────────────────────────────

    def get_module_structure(self) -> List[Dict[str, Any]]:
        """Get the current module cluster map with domain tags and layers.

        Returns list of module dicts with keys: name, summary, file_count,
        member_files, dependencies, domain_tags, component_status.
        Returns empty list if no module data exists.
        """
        modules_path = self._index_dir / "trace_modules.jsonl"
        if not modules_path.exists():
            return []
        import json

        modules: List[Dict[str, Any]] = []
        for line in modules_path.read_text().strip().splitlines():
            if line.strip():
                try:
                    modules.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return modules

    # ── Code Search ─────────────────────────────────────────────

    def search_code(
        self,
        query: str,
        k: int = 5,
        role: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic code search with optional role scoping.

        Returns list of dicts with ``"doc"`` and ``"score"`` keys.
        Returns empty list if no index is available.
        """
        try:
            idx = CodeIndex(self._index_dir)
            if not idx.is_ready():
                return []

            if role:
                try:
                    resolution = resolve_mask(self._project_id, scope=None, role=role)
                    mask = resolution.mask
                    if mask:
                        results = idx.search(query, k=k * 2)
                        filtered = [
                            {"doc": r.doc, "score": r.score}
                            for r in results
                            if path_matches_any_scope(r.doc.get("source_path", ""), mask)
                        ]
                        return filtered[:k]
                except Exception:
                    pass  # Fall through to unscoped search

            results = idx.search(query, k=k)
            return [{"doc": r.doc, "score": r.score} for r in results]
        except Exception as exc:
            logger.debug("CodeIndex search unavailable: %s", exc)
            return []

    # ── Role Vectors ────────────────────────────────────────────

    def get_role_vector(self, role_slug: str) -> Any:
        """Get or generate a RoleVector for scoring file relevance.

        Returns a RoleVector instance, or ``None`` if resolution fails.
        """
        try:
            from prep.core.atlas.role_resolver import resolve_role

            return resolve_role(role_slug)
        except Exception as exc:
            logger.debug("Role resolution failed for %r: %s", role_slug, exc)
            return None

    # ── Impact / Trace ───────────────────────────────────────────

    def get_impact_radius(
        self,
        file_path: str,
        max_hops: int = 2,
        max_nodes: int = 30,
    ) -> Dict[str, Any]:
        """Return the reverse-dependency impact graph for a file.

        Args:
            file_path: Source-relative or absolute file path.
            max_hops: BFS depth limit.
            max_nodes: Maximum dependent nodes to return.

        Returns:
            Dict with ``"target"`` and ``"dependents"`` keys.
            Returns ``{"target": None, "dependents": []}`` when trace is unavailable.
        """
        if self._trace_index is None:
            return {"target": None, "dependents": []}
        return self._trace_index.get_impact_graph(
            f"file:{file_path}",
            max_hops=max_hops,
            max_nodes=max_nodes,
        )

    # ── Observations ─────────────────────────────────────────────

    def save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        category: str = "note",
        created_by: Optional[str] = None,
        visibility: str = "shared",
    ) -> str:
        """Persist an agent observation and return its ID.

        Args:
            content: Observation text (max 2000 chars, will be truncated).
            file_path: Optional source file this observation relates to.
            category: One of ``note``, ``decision``, ``bug``, ``pattern``,
                ``assumption``.
            created_by: Agent role identifier (e.g. 'researcher').
            visibility: 'shared', 'private', or 'internal'.

        Returns:
            Observation UUID string.
        """
        return self._observation_store.save(
            self._project_id,
            content,
            file_path=file_path,
            category=category,
            created_by=created_by,
            visibility=visibility,
        )

    def get_observations(self, query: str, limit: int = 5) -> list:
        """Search stored observations and return matches.

        Args:
            query: Free-text query; uses FTS5 when available.
            limit: Maximum number of results.

        Returns:
            List of :class:`~prep.services.observation_store.Observation` instances.
        """
        return self._observation_store.get_for_query(
            self._project_id,
            query,
            limit=limit,
        )
