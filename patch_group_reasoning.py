import re

with open('src/codrag/core/group_reasoning.py', 'r') as f:
    content = f.read()

# Add imports if not present
if 'from codrag.core.context_config import PipelineTask, compute_optimal_settings' not in content:
    content = re.sub(
        r'from typing import ',
        r'from codrag.core.context_config import PipelineTask, compute_optimal_settings\nfrom typing import ',
        content
    )

# Patch generate
def replace_generate_call(match):
    return """            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.GROUP_REASONING,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=True,
            )

            text, tokens = self.llm.generate(
                prompt,
                system=GROUP_REASONING_SYSTEM,
                num_predict=num_predict,
                num_ctx=num_ctx,"""

content = re.sub(
    r'            text, tokens = self\.llm\.generate\(\n                prompt,\n                system=GROUP_REASONING_SYSTEM,\n                num_predict=\d+,',
    replace_generate_call,
    content
)

with open('src/codrag/core/group_reasoning.py', 'w') as f:
    f.write(content)

