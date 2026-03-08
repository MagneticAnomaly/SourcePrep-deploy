import re

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/inferred_edges.py', 'r') as f:
    content = f.read()

# Fix 1: Batched
p1 = r'response_schema=schema,\s*\)'
r1 = '''response_schema=schema,
                        max_chars=TASK_MAX_CHARS["augmentation"],
                    )'''

# Fix 2: Single
p2 = r'temperature=0\.1,\s*\)'
r2 = '''temperature=0.1,
            max_chars=TASK_MAX_CHARS["augmentation"],
        )'''

content = "from codrag.core.llm_client import TASK_MAX_CHARS\n" + content
content = re.sub(p1, r1, content)
content = re.sub(p2, r2, content)

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/inferred_edges.py', 'w') as f:
    f.write(content)
