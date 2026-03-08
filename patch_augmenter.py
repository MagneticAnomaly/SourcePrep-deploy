import re

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/augmenter.py', 'r') as f:
    content = f.read()

# Fix 1: _generate_with_retry
p1 = r'num_predict=num_predict, num_ctx=num_ctx,\s*\)'
r1 = '''num_predict=num_predict, num_ctx=num_ctx,
                    max_chars=TASK_MAX_CHARS["augmentation"],
                )'''

# Fix 2: process_file_batch
p2 = r'response_schema=file_schema,\s*\)'
r2 = '''response_schema=file_schema,
                    max_chars=TASK_MAX_CHARS["augmentation"],
                )'''

# Fix 3: process_doc_batch
p3 = r'response_schema=doc_schema,\s*\)'
r3 = '''response_schema=doc_schema,
                    max_chars=TASK_MAX_CHARS["augmentation"],
                )'''

content = "from codrag.core.llm_client import TASK_MAX_CHARS\n" + content
content = re.sub(p1, r1, content)
content = re.sub(p2, r2, content)
content = re.sub(p3, r3, content)

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/augmenter.py', 'w') as f:
    f.write(content)
