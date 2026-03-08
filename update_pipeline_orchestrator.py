import re

with open('src/codrag/services/pipeline_orchestrator.py', 'r') as f:
    content = f.read()

# Add QueueType and STAGE_QUEUE_TYPE to the re-exports
content = re.sub(
    r'    STAGE_MODEL_SLOT,',
    r'    STAGE_MODEL_SLOT,\n    QueueType,\n    STAGE_QUEUE_TYPE,',
    content
)

with open('src/codrag/services/pipeline_orchestrator.py', 'w') as f:
    f.write(content)
