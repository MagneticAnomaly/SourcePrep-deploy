"""
Backward-compat wrapper — re-exports everything from the pipeline subpackage.

All 26+ import sites that do ``from codrag.services.pipeline_orchestrator import X``
continue to work without modification.
"""
from codrag.services.pipeline import (  # noqa: F401
    StageId,
    STAGE_BUILD_TYPE,
    FAST_SYNC_STAGES,
    DEEP_ENRICHMENT_STAGES,
    STAGE_TASK_ID,
    STAGE_MODEL_SLOT,
    PipelineRunPhase,
    PipelineRun,
    WorkerFactory,
    PipelineOrchestrator,
    pipeline_orchestrator,
)
