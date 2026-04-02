"""Read-only facade wrapping CoDRAG's internal data sources for agent engines.

Provides a stable, simplified interface to OpportunityManager, CodebaseAtlas,
TraceIndex, and ObservationStore — shielding agent code from internal API changes.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CoDRAGDataAccess:
    """Read-only wrapper around CoDRAG internal data sources.

    Instantiate once per agent run, passing the project's index directory.

    Args:
        index_dir: Path to the CoDRAG index directory (e.g. ``.codrag/`` or
            ``~/.local/share/codrag/projects/<slug>/``).
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
        from codrag.core.audit.opportunity_manager import OpportunityManager
        self._opp_manager = OpportunityManager(self._index_dir)

        # Atlas
        from codrag.core.atlas.generator import CodebaseAtlas
        self._atlas = CodebaseAtlas(self._index_dir, project_root=self._project_root)

        # Trace index — optional; may not be built yet
        self._trace_index = None
        try:
            from codrag.core.trace.index import TraceIndex
            ti = TraceIndex(self._index_dir)
            if ti.exists() and ti.load():
                if ti.node_count() > 0:
                    self._trace_index = ti
        except Exception as exc:  # pragma: no cover
            logger.debug("TraceIndex unavailable (non-fatal): %s", exc)

        # Observation store singleton
        from codrag.services.observation_store import observation_store
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
            List of :class:`~codrag.core.audit.action_item.ActionItem` instances.
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
            List of :class:`~codrag.core.audit.action_item.ActionItem` instances.
        """
        kwargs: Dict[str, Any] = {"project_root": self._project_root}
        if categories is not None:
            kwargs["categories"] = categories
        return self._opp_manager.refresh(**kwargs)

    # ── Atlas ────────────────────────────────────────────────────

    def get_atlas(self) -> str:
        """Return the cached atlas document content, or ``""`` if unavailable."""
        doc = self._atlas.load()
        if doc is None:
            return ""
        return doc.content or ""

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
    ) -> str:
        """Persist an agent observation and return its ID.

        Args:
            content: Observation text (max 2000 chars, will be truncated).
            file_path: Optional source file this observation relates to.
            category: One of ``note``, ``decision``, ``bug``, ``pattern``,
                ``assumption``.

        Returns:
            Observation UUID string.
        """
        return self._observation_store.save(
            self._project_id,
            content,
            file_path=file_path,
            category=category,
        )

    def get_observations(self, query: str, limit: int = 5) -> list:
        """Search stored observations and return matches.

        Args:
            query: Free-text query; uses FTS5 when available.
            limit: Maximum number of results.

        Returns:
            List of :class:`~codrag.services.observation_store.Observation` instances.
        """
        return self._observation_store.get_for_query(
            self._project_id,
            query,
            limit=limit,
        )
