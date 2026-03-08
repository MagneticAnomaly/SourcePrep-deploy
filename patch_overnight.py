import re

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/scripts/benchmark_comprehensive_overnight.py', 'r') as f:
    content = f.read()

# Make sure we use the split think configs
pattern = r'def test_atlas\(client, think, .*?\):'
replacement = r'def test_atlas(client, think, \g<0>'

content = re.sub(r'def test_atlas\(client, think,', r'def test_atlas(client, think,', content)

# But wait, we can just run the multi-repo script which is already up to date!
