import re

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/epistemic_enrichment.py', 'r') as f:
    content = f.read()

# Fix 1: Single file
p1 = r'json_mode=False, think=False,\s*\)'
r1 = '''json_mode=False, think=False,
                max_chars=TASK_MAX_CHARS["epistemic"],
            )'''

# Fix 2: Batched code
p2 = r'response_schema=code_schema,\s*\)'
r2 = '''response_schema=code_schema,
                    max_chars=TASK_MAX_CHARS["epistemic"],
                )'''

# Fix 3: Batched doc
p3 = r'response_schema=doc_schema,\s*\)'
r3 = '''response_schema=doc_schema,
                    max_chars=TASK_MAX_CHARS["epistemic"],
                )'''

content = "from codrag.core.llm_client import TASK_MAX_CHARS\n" + content
content = re.sub(p1, r1, content)
content = re.sub(p2, r2, content)
content = re.sub(p3, r3, content)

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/epistemic_enrichment.py', 'w') as f:
    f.write(content)
