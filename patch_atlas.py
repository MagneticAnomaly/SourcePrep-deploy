import re

with open('src/codrag/core/atlas/generator.py', 'r') as f:
    content = f.read()

# Add imports
content = re.sub(
    r'from \.models import',
    r'from codrag.core.context_config import PipelineTask, compute_optimal_settings\nfrom .models import',
    content
)

# Patch generate
def replace_generate_call(match):
    return """        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.ATLAS,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        try:
            text, tokens = self.llm.generate(
                prompt, system=system, num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, temperature=0.3, think=False,"""

content = re.sub(
    r'        try:\n            text, tokens = self\.llm\.generate\(\n                prompt, system=system, num_predict=\d+,\n                json_mode=False, temperature=0\.3, think=False,',
    replace_generate_call,
    content
)

with open('src/codrag/core/atlas/generator.py', 'w') as f:
    f.write(content)

