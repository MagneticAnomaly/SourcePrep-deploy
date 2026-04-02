"""JSON-backed persistence for research run history.

Stores runs to ``<index_dir>/researcher_history.json``.
Each run captures the topics selected and plans formulated.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from codrag.agents.shared.models import ResearchPlan, ResearchTopic

logger = logging.getLogger(__name__)

_HISTORY_FILENAME = "researcher_history.json"


class ResearchHistory:
    """Manages persistent history of research runs.

    Args:
        index_dir: Directory where ``researcher_history.json`` is stored.
    """

    def __init__(self, index_dir: Path) -> None:
        self._path = Path(index_dir) / _HISTORY_FILENAME
        self._runs: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._runs = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._runs = data.get("runs", [])
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load research history: %s", exc)
            self._runs = []

    def _save(self) -> None:
        data = {"runs": self._runs}
        fd, tmp = tempfile.mkstemp(
            dir=self._path.parent, suffix=".tmp", prefix=".researcher_history_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(tmp).replace(self._path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def save_run(
        self,
        topics: List[ResearchTopic],
        plans: List[ResearchPlan],
    ) -> str:
        """Save a research run and return its ID."""
        run_id = uuid.uuid4().hex[:12]
        run = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topics": [t.to_dict() for t in topics],
            "plans": [p.to_dict() for p in plans],
        }
        self._runs.append(run)
        self._save()
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run by ID, or None if not found."""
        for run in self._runs:
            if run["run_id"] == run_id:
                return run
        return None

    def list_runs(self) -> List[Dict[str, Any]]:
        """Return all runs, oldest first."""
        return list(self._runs)

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Return the most recent run, or None if empty."""
        return self._runs[-1] if self._runs else None
