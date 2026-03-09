"""
MultiProjectCoordinator (Phase 45D stub)
Provides the singleton requested by PipelineOrchestrator.
Actually delegates to the real pipeline_scheduler.
"""
import logging
from typing import Optional
from codrag.services.pipeline.scheduler import pipeline_scheduler
from codrag.services.pipeline.stages import StageId

logger = logging.getLogger(__name__)

class QueuedTask:
    def __init__(self, project_id: str, stage: str):
        self.project_id = project_id
        self.stage = stage

class MultiProjectCoordinator:
    def request_slot(self, project_id: str, stage_str: str, required_node_id: str) -> bool:
        # Delegate to the real scheduler
        stage = StageId(stage_str)
        if pipeline_scheduler.can_start(project_id, stage, required_node_id):
            return pipeline_scheduler.acquire(project_id, stage, required_node_id)
        
        # Enqueue if we can't start
        pipeline_scheduler.enqueue(project_id, stage, required_node_id)
        return False
        
    def release_slot(self, project_id: str, stage_str: str, required_node_id: str):
        """Release a compute slot and resume any queued pipeline."""
        stage = StageId(stage_str)
        next_entry = pipeline_scheduler.release(project_id, stage, required_node_id)
        if next_entry:
            logger.info(
                "Scheduler: slot freed on %s, resuming %s/%s",
                required_node_id, next_entry.project_id, next_entry.stage.value,
            )
            # Signal the orchestrator to resume the queued pipeline
            try:
                from codrag.services.pipeline.orchestrator import pipeline_orchestrator
                pipeline_orchestrator._resume_queued_pipeline(next_entry.project_id, next_entry.stage)
            except Exception as e:
                logger.warning("Failed to resume queued pipeline: %s", e)

_coordinator = MultiProjectCoordinator()

def get_coordinator() -> MultiProjectCoordinator:
    return _coordinator
