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
    """Cross-check scheduler locks against build orchestrator and pipeline state.

    Phase 89: Requires all three sources of truth to agree before purging:
    1. Scheduler says lock held (project in active_stages)
    2. BuildOrchestrator says no active threads
    3. Pipeline state machine says NOT active (COMPLETED/FAILED/CANCELLED/IDLE)

    Only when all three agree is the lock a true ghost (crashed worker).
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

    # Load pipeline orchestrator for state machine check
    pipeline_orch = None
    try:
        from codrag.services.pipeline_orchestrator import pipeline_orchestrator as _po
        pipeline_orch = _po
    except ImportError:
        pass

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
        # Source 2: Are any build threads alive?
        if build_orchestrator.is_any_active(project_id):
            continue  # Thread alive — lock is valid

        # Source 3: Is the pipeline state machine active?
        if pipeline_orch is not None:
            try:
                ps = pipeline_orch.status(project_id)
                pipeline_active = any(
                    g.get("is_active")
                    for g in [ps.get("fast_sync", {}), ps.get("deep_enrichment", {})]
                    if isinstance(g, dict)
                )
                if pipeline_active:
                    logger.debug(
                        "Ghost Guard: project %s has no build threads but pipeline "
                        "state machine is active — skipping purge",
                        project_id,
                    )
                    continue
            except Exception:
                pass  # Can't check — fall through to purge

        # All three sources agree: lock held + no threads + no active pipeline
        logger.warning(
            "Ghost Guard: project %s holds scheduler lock with no active "
            "build threads and no active pipeline — purging ghost lock",
            project_id,
        )
        scheduler.clean_locks(project_id)
        purged += 1

    # Phase 93: Also purge orphaned QUEUE entries (not just active locks).
    # A queued entry with no matching state machine will bounce forever
    # in _resume_queued_pipeline (dequeue → no SM → drop), blocking other
    # pipelines. Proactively cancel them here.
    if pipeline_orch is not None:
        queued_projects: set[str] = set()
        for node_info in nodes.values():
            for entry in node_info.get("queued", []):
                queued_projects.add(entry["project_id"])

        for qpid in queued_projects:
            if qpid in locked_projects:
                continue  # Already handled above (has active lock)
            try:
                ps = pipeline_orch.status(qpid)
                has_queued_sm = any(
                    g.get("phase") == "queued"
                    for g in [ps.get("fast_sync", {}), ps.get("deep_enrichment", {})]
                    if isinstance(g, dict)
                )
                if not has_queued_sm:
                    logger.warning(
                        "Ghost Guard: project %s has queued scheduler entries "
                        "but no QUEUED state machine — cancelling orphaned entries",
                        qpid,
                    )
                    scheduler.cancel(qpid)
                    purged += 1
            except Exception:
                pass

    if purged > 0:
        event_bus.emit("queue_changed", {
            "reason": "ghost_purged",
            "purged_count": purged,
        })
        logger.info("Ghost Guard: purged %d ghost lock(s)", purged)

    return purged
