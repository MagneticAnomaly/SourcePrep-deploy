"""
Pipeline orchestrator subpackage — stages, workers, and orchestrator.

Re-exports all public symbols so that
``from codrag.services.pipeline_orchestrator import X`` still works
via the backward-compat wrapper in the parent module.
"""
from .stages import (
    StageId,
    STAGE_BUILD_TYPE,
    FAST_SYNC_STAGES,
    DEEP_ENRICHMENT_STAGES,
    STAGE_TASK_ID,
    STAGE_MODEL_SLOT,
)
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
)
from .orchestrator import (
    PipelineOrchestrator,
    pipeline_orchestrator,
)

__all__ = [
    "StageId",
    "STAGE_BUILD_TYPE",
    "FAST_SYNC_STAGES",
    "DEEP_ENRICHMENT_STAGES",
    "STAGE_TASK_ID",
    "STAGE_MODEL_SLOT",
    "PipelineRunPhase",
    "PipelineRun",
    "WorkerFactory",
    "PipelineGroupStateMachine",
    "PipelineState",
    "Event",
    "ActiveProjectGuard",
    "PipelineOrchestrator",
    "pipeline_orchestrator",
]
