import re

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/cluster.py', 'r') as f:
    content = f.read()

# Fix 1: Module Synthesis
p1 = r'json_mode=False, think=False,\s*\)'
r1 = '''json_mode=False, think=False,
                max_chars=TASK_MAX_CHARS["augmentation"],
            )'''

# Fix 2: Batched Synthesis
p2 = r'response_schema=schema,\s*\)'
r2 = '''response_schema=schema,
                        max_chars=TASK_MAX_CHARS["augmentation"],
                    )'''

content = "from codrag.core.llm_client import TASK_MAX_CHARS\n" + content
content = re.sub(p1, r1, content)
content = re.sub(p2, r2, content)

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/cluster.py', 'w') as f:
    f.write(content)
