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
from typing import Literal

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
