import re

with open('src/codrag/core/deep_analysis.py', 'r') as f:
    content = f.read()

# Add imports if not present
if 'from codrag.core.context_config import PipelineTask, compute_optimal_settings' not in content:
    content = re.sub(
        r'from typing import ',
        r'from codrag.core.context_config import PipelineTask, compute_optimal_settings\nfrom typing import ',
        content
    )

def replace_generate_call(match):
    return """        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.EPISTEMIC,  # Deep analysis is similar to epistemic
            prompt_tokens=prompt_tokens,
            model=llm_client.model,
            think=False,
        )

        try:
            text, tokens = llm_client.generate(
                prompt, system=VALIDATION_SYSTEM, 
                num_predict=num_predict, num_ctx=num_ctx,
            )"""

content = re.sub(
    r'        try:\n            text, tokens = llm_client\.generate\(prompt, system=VALIDATION_SYSTEM, num_predict=2048\)',
    replace_generate_call,
    content
)

with open('src/codrag/core/deep_analysis.py', 'w') as f:
    f.write(content)

