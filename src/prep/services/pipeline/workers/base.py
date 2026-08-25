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

Phase 135.5b: subclasses may also rely on `_resolve_changeset()` to
LAZY-LOAD the changeset from `<self.index_dir>/changeset.json` when
the worker is invoked from a non-pipeline path (API endpoints,
headless runner, post-flight, agent integration). Workers still
inject; non-workers get automatic on-disk resolution.
"""
from __future__ import annotations

from typing import Optional

from prep.services.pipeline.changeset import Changeset


class Worker:
    """Base for pipeline stage workers. Phase 134 contract: workers
    receive `self.changeset` from WorkerFactory and use
    `self.should_process(path)` to gate per-file work.

    Phase 135.5b: subclasses may also rely on `_resolve_changeset()` to
    LAZY-LOAD the changeset from `<self.index_dir>/changeset.json` when
    the worker is invoked from a non-pipeline path (API endpoints,
    headless runner, post-flight, agent integration). Workers still
    inject (cached path); non-workers get automatic on-disk resolution."""

    changeset: Optional[Changeset] = None
    # T-S1.3: per-stage profile gate, injected by WorkerFactory parallel to
    # `changeset`. None (default) ⇒ no profile gating ⇒ process everything,
    # identical to pre-profile behavior. The 5 per-file stages consult
    # `getattr(self, "profile_gate", None)` in their skip checks.
    profile_gate: Optional["object"] = None

    def _resolve_changeset(self) -> Optional[Changeset]:
        """Return the explicitly-injected changeset, or lazy-load from
        disk (`<self.index_dir>/changeset.json`) on first call.
        Caches the result on `self.changeset` so subsequent calls are O(1).

        Returns None only when both (a) no injection AND (b) no on-disk
        changeset AND (c) no `index_dir` attribute. Callers should treat
        None as 'changeset unavailable — be conservative.'"""
        if self.changeset is not None:
            return self.changeset
        idx_dir = getattr(self, "index_dir", None)
        if idx_dir is None:
            return None
        # Lazy import to avoid circular dependency (changeset module
        # doesn't import workers).
        from prep.services.pipeline.changeset import read_changeset
        cs = read_changeset(idx_dir)
        if cs is not None:
            self.changeset = cs  # cache
        return cs

    def should_process(self, file_path: str) -> bool:
        """Return True iff this worker should run on this file in
        this run. Phase 135.5b: uses _resolve_changeset() so non-pipeline
        callers automatically pick up the on-disk changeset.

        Defensive fallback (truly no changeset anywhere): process
        everything — failing open is safer than skipping real work."""
        cs = self._resolve_changeset()
        if cs is None:
            return True
        return cs.should_process(file_path)
