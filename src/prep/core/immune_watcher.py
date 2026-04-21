"""Watcher-driven antibody evaluation for the codebase immune system.

When the file watcher detects changes, this module evaluates all active
antibodies against the changed files and pushes alerts to the global
alert queue.

**Usage (from watcher callback):**
  ``from prep.core.immune_watcher import evaluate_changes``
  ``count = evaluate_changes(project_id, changed_paths)``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from prep.core.alert_queue import Alert, alert_queue
from prep.core.antibodies import TriggerType, evaluate_trigger

if TYPE_CHECKING:
    from prep.services.antibody_store import AntibodyStore

logger = logging.getLogger(__name__)


def evaluate_changes(
    project_id: str,
    changed_paths: List[str],
    antibody_store: Optional["AntibodyStore"] = None,
) -> int:
    """Evaluate active antibodies against changed files.

    Reads file content for IMPORT_ADDED and PATTERN_MATCH triggers.
    Pushes alerts to the global alert_queue.
    Returns number of alerts generated.

    Args:
        project_id: The project to evaluate antibodies for.
        changed_paths: List of changed file paths (relative or absolute).
        antibody_store: Optional store override (for testing). If None,
            uses the global singleton.
    """
    if antibody_store is None:
        from prep.services.antibody_store import antibody_store as _default_store
        antibody_store = _default_store

    # Only evaluate active antibodies
    try:
        antibodies = antibody_store.list_antibodies(project_id, status="active")
    except Exception:
        logger.debug("Failed to load antibodies for %s", project_id, exc_info=True)
        return 0

    if not antibodies:
        return 0

    alert_count = 0

    for file_path in changed_paths:
        # Read file content lazily (only if needed by a trigger type)
        file_content: Optional[str] = None

        for ab in antibodies:
            needs_content = ab.trigger.type in (
                TriggerType.IMPORT_ADDED,
                TriggerType.PATTERN_MATCH,
            )

            if needs_content and file_content is None:
                file_content = _read_file_safe(file_path)

            fired = evaluate_trigger(
                ab.trigger,
                file_path,
                file_content=file_content or "",
            )

            if fired:
                alert = Alert(
                    antibody_id=ab.id,
                    antibody_name=ab.name,
                    severity=ab.severity.value,
                    message=ab.response.message,
                    file_path=file_path,
                )
                pushed = alert_queue.push(alert)
                if pushed:
                    alert_count += 1
                    try:
                        antibody_store.record_trigger(ab.id)
                    except Exception:
                        logger.debug(
                            "Failed to record trigger for %s", ab.id, exc_info=True
                        )
                    logger.info(
                        "Antibody fired: %s on %s [%s]",
                        ab.name, file_path, ab.severity.value,
                    )

    return alert_count


def _read_file_safe(file_path: str) -> str:
    """Read file content, returning empty string on any error."""
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
