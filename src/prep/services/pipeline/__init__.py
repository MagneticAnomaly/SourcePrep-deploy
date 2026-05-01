"""
Pipeline orchestrator subpackage — stages, workers, and orchestrator.

Re-exports all public symbols so that
``from prep.services.pipeline_orchestrator import X`` still works
via the backward-compat wrapper in the parent module.
"""
from .stages import (
    StageId,
    STAGE_BUILD_TYPE,
    FAST_SYNC_STAGES,
    SYNC_STAGES,
    ENRICH_STAGES,
    DEEP_ENRICHMENT_STAGES,
    FINALIZE_STAGES,
    FINALIZE_WAVES,
    STAGE_TASK_ID,
    STAGE_MODEL_SLOT,
    QueueType,
    STAGE_QUEUE_TYPE,
    OutputSpec,
    STAGE_OUTPUTS,
    PROJECT_META_ALLOWLIST,
    build_keep_set,
)
from .scheduler import PipelineScheduler, pipeline_scheduler
from .workers import (
    PipelineRunPhase,
    PipelineRun,
    WorkerFactory,
)
from .state_machine import (
    PipelineGroupStateMachine,
    PipelineState,
    Event,
    ActiveProjectGuard,
    StageSnapshot,
)
from .manifest_store import ManifestStore
from .post_flight import PostFlightActions
from .recovery import RecoveryManager
from .resume import ResumeStrategy
from .orchestrator import (
    PipelineOrchestrator,
    pipeline_orchestrator,
)

__all__ = [
    "StageId",
    "STAGE_BUILD_TYPE",
    "FAST_SYNC_STAGES",
    "SYNC_STAGES",
    "ENRICH_STAGES",
    "DEEP_ENRICHMENT_STAGES",
    "FINALIZE_STAGES",
    "FINALIZE_WAVES",
    "STAGE_TASK_ID",
    "STAGE_MODEL_SLOT",
    "QueueType",
    "STAGE_QUEUE_TYPE",
    "OutputSpec",
    "STAGE_OUTPUTS",
    "PROJECT_META_ALLOWLIST",
    "build_keep_set",
    "PipelineScheduler",
    "pipeline_scheduler",
    "PipelineRunPhase",
    "PipelineRun",
    "WorkerFactory",
    "PipelineGroupStateMachine",
    "PipelineState",
    "Event",
    "ActiveProjectGuard",
    "StageSnapshot",
    "ManifestStore",
    "PostFlightActions",
    "RecoveryManager",
    "ResumeStrategy",
    "PipelineOrchestrator",
    "pipeline_orchestrator",
]
