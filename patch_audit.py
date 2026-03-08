import re

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/audit/synthesizer.py', 'r') as f:
    content = f.read()

pattern = r'text, _ = self\.llm\.generate\(\s*prompt=prompt,\s*system=([^,]+),\s*num_predict=num_predict,\s*num_ctx=num_ctx,\s*json_mode=False,\s*temperature=0\.3,\s*think=think,\s*\)'

replacement = r'''from codrag.core.llm_client import TASK_MAX_CHARS
        text, _ = self.llm.generate(
            prompt=prompt,
            system=\1,
            num_predict=num_predict,
            num_ctx=num_ctx,
            json_mode=False,
            temperature=0.3,
            think=think,
            max_chars=TASK_MAX_CHARS["audit"],
        )'''

new_content = re.sub(pattern, replacement, content)

with open('/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/audit/synthesizer.py', 'w') as f:
    f.write(new_content)
