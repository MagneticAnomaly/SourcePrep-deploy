"""
Backward-compat wrapper — re-exports everything from the pipeline subpackage.

All 26+ import sites that do ``from codrag.services.pipeline_orchestrator import X``
continue to work without modification.
"""
from codrag.services.pipeline import (  # noqa: F401
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
    PipelineRunPhase,
    PipelineRun,
    WorkerFactory,
    PipelineOrchestrator,
    pipeline_orchestrator,
)
