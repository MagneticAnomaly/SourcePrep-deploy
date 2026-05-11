"""Phase 134: Worker base providing the changeset contract.

Workers need to know what files to process in this run. Pre-Phase-134
each worker independently re-derived staleness from hashes (Important
#3 cascade). Phase 134 centralizes that decision in a single
Changeset emitted by stage 1; WorkerFactory injects it here.

Note: pipeline workers in this codebase are closures (functions), not
class instances.  WorkerFactory.create_worker returns a Callable.
The Worker class below is used as:
  1. A base for explicit Worker subclasses in tests.
  2. The source of should_process logic — WorkerFactory copies this
     logic onto the returned callable via the injected .changeset attr.
"""
from __future__ import annotations

from prep.services.pipeline.changeset import Changeset


class Worker:
    """Base for pipeline stage workers. Phase 134 contract: workers
    receive `self.changeset` from WorkerFactory and use
    `self.should_process(path)` to gate per-file work."""

    changeset: Changeset | None = None

    def should_process(self, file_path: str) -> bool:
        """Return True iff this worker should run on this file in
        this run. Defensive: if changeset is None (orchestrator
        forgot to inject), process everything — the per-stage
        cutover tests verify the orchestrator DOES inject in
        practice, but failing closed here would be worse than
        failing open if the contract regresses."""
        if self.changeset is None:
            return True
        return self.changeset.should_process(file_path)
