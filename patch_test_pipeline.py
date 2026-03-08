import re

with open('tests/test_pipeline_orchestrator.py', 'r') as f:
    content = f.read()

content = content.replace('def test_deep_enrichment_has_5_stages():', 'def test_deep_enrichment_has_6_stages():')
content = content.replace('assert len(DEEP_ENRICHMENT_STAGES) == 5', 'assert len(DEEP_ENRICHMENT_STAGES) == 6')

with open('tests/test_pipeline_orchestrator.py', 'w') as f:
    f.write(content)

