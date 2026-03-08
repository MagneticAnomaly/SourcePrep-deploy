import re

with open('tests/test_pipeline_orchestrator.py', 'r') as f:
    content = f.read()

content = content.replace(
    'started = pipeline.run_fast_sync("proj-1")',
    'started = pipeline.run_fast_sync("proj-1")\n            if not started:\n                import logging\n                logging.error(pipeline.status("proj-1"))'
)

with open('tests/test_pipeline_orchestrator.py', 'w') as f:
    f.write(content)
