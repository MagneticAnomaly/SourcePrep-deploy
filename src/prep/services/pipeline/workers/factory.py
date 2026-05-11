"""Phase 134: Re-export shim so tests can import from the submodule path.

The real implementation lives in prep.services.pipeline.workers (the
package __init__). This shim exists so the test suite and any future
consumers can also write:

    from prep.services.pipeline.workers.factory import WorkerFactory
"""
from __future__ import annotations

from prep.services.pipeline.workers import WorkerFactory  # noqa: F401

__all__ = ["WorkerFactory"]
