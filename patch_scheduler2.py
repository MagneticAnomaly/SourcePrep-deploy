with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/scheduler.py", "r") as f:
    text = f.read()

# Add a mock implementation of pipeline_scheduler if it exists, since orchestrator depends on it for backward compatibility
# But orchestrator actually imports pipeline_scheduler from codrag.services.pipeline.scheduler!
