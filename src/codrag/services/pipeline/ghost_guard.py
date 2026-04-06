"""
Ghost Guard — Phase 75
======================

Active cross-check that validates scheduler lock integrity against
build orchestrator thread liveness. Purges phantom scheduler locks
left behind by crashed worker threads.

Called on every queue read and on build transition failures to
guarantee the queue never deadlocks from ghost locks.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def purge_ghost_locks(
    scheduler=None,
    build_orchestrator=None,
    event_bus=None,
) -> int:
    """Cross-check scheduler locks against build orchestrator threads.

    For each project holding a scheduler slot, verify at least one
    build thread is alive via ``BuildOrchestrator.is_any_active()``.
    If the scheduler claims a lock but no threads exist, the lock
    is a ghost — purge it.

    Args:
        scheduler: PipelineScheduler instance. Defaults to module singleton.
        build_orchestrator: BuildOrchestrator instance. Defaults to module singleton.
        event_bus: EventBus instance. Defaults to module singleton.

    Returns:
        Number of ghost locks purged.
    """
    if scheduler is None:
        from codrag.services.pipeline.scheduler import pipeline_scheduler

        scheduler = pipeline_scheduler
    if build_orchestrator is None:
        from codrag.services.build_orchestrator import build_orchestrator as _bo

        build_orchestrator = _bo
    if event_bus is None:
        from codrag.core.events import get_event_bus

        event_bus = get_event_bus()

    status = scheduler.status()
    nodes = status.get("nodes", {})

    # Collect all unique project_ids that hold active slots
    locked_projects: set[str] = set()
    for node_info in nodes.values():
        active = node_info.get("active", {})
        locked_projects.update(active.keys())

    if not locked_projects:
        return 0

    purged = 0
    for project_id in locked_projects:
        if not build_orchestrator.is_any_active(project_id):
            logger.warning(
                "Ghost Guard: project %s holds scheduler lock but has no "
                "active build threads — purging ghost lock",
                project_id,
            )
            scheduler.clean_locks(project_id)
            purged += 1

    if purged > 0:
        event_bus.emit("queue_changed", {
            "reason": "ghost_purged",
            "purged_count": purged,
        })
        logger.info("Ghost Guard: purged %d ghost lock(s)", purged)

    return purged
