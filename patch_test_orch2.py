import re

with open('tests/test_pipeline_orchestrator.py', 'r') as f:
    content = f.read()

content = content.replace(
    'started = pipeline.run_fast_sync("proj-1")',
    'import codrag.services.project_helpers\n            with patch("codrag.services.project_helpers.get_project_activity_status", return_value="active"):\n                started = pipeline.run_fast_sync("proj-1")'
)

with open('tests/test_pipeline_orchestrator.py', 'w') as f:
    f.write(content)
