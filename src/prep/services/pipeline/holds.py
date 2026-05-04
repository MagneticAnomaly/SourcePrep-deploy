"""Phase 127: soft-hold primitive shared by exclusive priority and swarm-drain.

A soft-hold tells a worker dispatch loop "no new LLM calls for this
(project, endpoint) pair; let in-flight finish and pause." Workers
poll ``PipelineScheduler.is_held()`` between dispatches and pause when
True. The hold is cleared (by exclusive lift, swarm window close, or
explicit clear) and workers resume from their last checkpoint.

This file holds the data types only — the live state and the
set/clear/is_held methods live on PipelineScheduler in scheduler.py
to keep them under the same lock as the rest of scheduler state.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

# A hold can come from one of three causes.  ``exclusive`` and
# ``swarm`` are the user-facing causes; ``manual`` is reserved for
# tests and admin tooling.
HoldReason = Literal["exclusive", "swarm", "manual"]


@dataclass(frozen=True)
class HoldKey:
    """Unique key identifying a single hold."""
    project_id: str
    endpoint_id: str  # scheduler node_id (e.g., "cloud:default_ollama")


@dataclass
class HoldEntry:
    """A single active hold with provenance."""
    reason: HoldReason
    set_by_project: str  # the project that triggered the hold
    held_since: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "reason": self.reason,
            "set_by_project": self.set_by_project,
            "held_since": self.held_since,
        }


class HoldPausedError(Exception):
    """Raised when an LLM dispatch is paused due to a soft-hold.

    Callers should catch this at a run-loop boundary and treat it as
    'pause, checkpoint, retry on next run' — NOT as a permanent failure.
    The error carries the (project_id, endpoint_id) tuple that was held
    so callers can log a single descriptive message.
    """

    def __init__(self, project_id: str, endpoint_id: str):
        self.project_id = project_id
        self.endpoint_id = endpoint_id
        super().__init__(
            f"Dispatch paused on soft-hold (project={project_id!r}, endpoint={endpoint_id!r})"
        )


def resolve_endpoint_id_for_llm(llm: Any) -> str:
    """Best-effort resolution of the scheduler node id this LLM client
    will dispatch against.

    A bare ``llm.endpoint_id`` is just a logical name like
    ``default_ollama`` — scheduler nodes (and hold keys) are
    prefixed (``cloud:default_ollama`` / ``local:default_ollama``).
    Delegates to the LLM client's existing resolver so the hold key
    matches the gate the request will actually traverse.

    Returns empty string when resolution fails — callers treat that
    as "no matching hold" (safe default).
    """
    try:
        resolver = getattr(llm, "_resolve_scheduler_node_id", None)
        if callable(resolver):
            resolved = resolver()
            if resolved:
                return str(resolved)
    except Exception:  # pragma: no cover — defensive
        pass
    return ""


def hold_paused_for_llm(
    llm: Any,
    project_id: Optional[str],
    logger_: Any,
) -> bool:
    """Return True if this (project, llm-endpoint) is soft-held.

    Resolves the LLM client's actual scheduler-prefixed node id
    (e.g. ``cloud:default_ollama`` not bare ``default_ollama``) and
    checks ``pipeline_scheduler.is_held()``.  Logs at DEBUG when
    paused — callers should also emit one INFO at run level if they
    want operator visibility.

    Returns False (i.e. "proceed, do not pause") if:
    - project_id is empty/None
    - LLM client doesn't expose ``_resolve_scheduler_node_id``
    - resolver returns None / empty string
    - ``is_held`` returns False

    Fail-open posture: any unexpected exception falls through to
    "proceed" so a bug in the hold layer cannot stall enrichment.
    """
    if not project_id:
        return False
    try:
        endpoint_id = resolve_endpoint_id_for_llm(llm)
        if not endpoint_id:
            return False
        from prep.services.pipeline.scheduler import pipeline_scheduler
        if pipeline_scheduler.is_held(project_id, endpoint_id):
            logger_.debug(
                "LLM dispatch paused on hold (project=%s endpoint=%s)",
                project_id, endpoint_id,
            )
            return True
        return False
    except Exception:  # pragma: no cover — defensive
        return False
