import re

with open('tests/test_pipeline_orchestrator.py', 'r') as f:
    content = f.read()

# Replace all occurrences of pipeline.run_fast_sync and pipeline.run_deep_enrichment
# to mock get_project_activity_status around them, OR better:
# mock get_project_activity_status at the fixture level.

def replace_fixture(match):
    return """@pytest.fixture
def pipeline(orchestrator):
    \"\"\"PipelineOrchestrator wired to a real BuildOrchestrator.\"\"\"
    with patch("codrag.services.project_helpers.get_project_activity_status", return_value="active"):
        yield PipelineOrchestrator(orchestrator=orchestrator)"""

content = re.sub(
    r'@pytest\.fixture\ndef pipeline\(orchestrator\):\n    \"\"\"PipelineOrchestrator wired to a real BuildOrchestrator\.\"\"\"\n    return PipelineOrchestrator\(orchestrator=orchestrator\)',
    replace_fixture,
    content
)

with open('tests/test_pipeline_orchestrator.py', 'w') as f:
    f.write(content)
