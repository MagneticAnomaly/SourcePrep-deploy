import re

with open('src/codrag/core/inferred_edges.py', 'r') as f:
    content = f.read()

# Add imports if not present
if 'from codrag.core.context_config import PipelineTask, compute_optimal_settings' not in content:
    content = re.sub(
        r'from typing import ',
        r'from codrag.core.context_config import PipelineTask, compute_optimal_settings\nfrom typing import ',
        content
    )

def replace_generate_call_1(match):
    return """                prompt_tokens = len(prompt) // 4
                num_predict, num_ctx, warnings = compute_optimal_settings(
                    task=PipelineTask.AUGMENT,  # Treat similar to augment
                    prompt_tokens=prompt_tokens,
                    model=self.llm.model,
                    think=False,
                )

                try:
                    text, tokens = self.llm.generate(
                        prompt, system=BATCHED_INFERRED_EDGES_SYSTEM,
                        num_predict=num_predict, num_ctx=num_ctx,"""

content = re.sub(
    r'                try:\n                    text, tokens = self\.llm\.generate\(\n                        prompt, system=BATCHED_INFERRED_EDGES_SYSTEM,\n                        num_predict=len\(items\) \* 300,',
    replace_generate_call_1,
    content
)

def replace_generate_call_2(match):
    return """        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUGMENT,  # Treat similar to augment
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        text, tokens = self.llm.generate(
            prompt,
            system=INFERRED_EDGES_SYSTEM,
            num_predict=num_predict,
            num_ctx=num_ctx,"""

content = re.sub(
    r'        text, tokens = self\.llm\.generate\(\n            prompt,\n            system=INFERRED_EDGES_SYSTEM,\n            num_predict=1024,',
    replace_generate_call_2,
    content
)

with open('src/codrag/core/inferred_edges.py', 'w') as f:
    f.write(content)

