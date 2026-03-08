import re

with open('src/codrag/core/audit/synthesizer.py', 'r') as f:
    content = f.read()

# Add imports if not present
if 'from codrag.core.context_config import PipelineTask, compute_optimal_settings' not in content:
    content = re.sub(
        r'from typing import ',
        r'from codrag.core.context_config import PipelineTask, compute_optimal_settings\nfrom typing import ',
        content
    )

# Patch generate calls
def replace_generate_call(match):
    return f"""        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUDIT,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        text, _ = self.llm.generate(
            prompt=prompt,
            system={match.group(1)},
            json_mode=False,
            temperature={match.group(2)},
            num_predict=num_predict,
            num_ctx=num_ctx,"""

content = re.sub(
    r'        text, _ = self\.llm\.generate\(\n            prompt=prompt,\n            system=(prompts\.[A-Z_]+_SYSTEM),\n            json_mode=False,\n            temperature=([0-9.]+),\n            num_predict=\d+,',
    replace_generate_call,
    content
)

with open('src/codrag/core/audit/synthesizer.py', 'w') as f:
    f.write(content)

