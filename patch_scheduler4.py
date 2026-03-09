with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/scheduler.py", "w") as f:
    f.write('''"""
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
        
    def release_slot(self, required_node_id: str):
        # The orchestrator calls pipeline_scheduler.release() directly now via _resume_queued_pipeline
        pass

_coordinator = MultiProjectCoordinator()

def get_coordinator() -> MultiProjectCoordinator:
    return _coordinator
''')
    print("Created stub coordinator in codrag/core/scheduler.py to bridge the old patch")
