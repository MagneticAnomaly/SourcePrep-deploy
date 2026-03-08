import re

with open('src/codrag/core/epistemic_enrichment.py', 'r') as f:
    content = f.read()

# Add imports if not present
if 'from codrag.core.context_config import PipelineTask, compute_optimal_settings' not in content:
    content = re.sub(
        r'from typing import ',
        r'from codrag.core.context_config import PipelineTask, compute_optimal_settings\nfrom typing import ',
        content
    )

def replace_generate_call_1(match):
    return """            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.EPISTEMIC,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=False,
            )

            text, tokens = self.llm.generate(
                prompt, system=EPISTEMIC_SYSTEM, num_predict=num_predict, num_ctx=num_ctx,"""

content = re.sub(
    r'            text, tokens = self\.llm\.generate\(\n                prompt, system=EPISTEMIC_SYSTEM, num_predict=4096,',
    replace_generate_call_1,
    content
)

def replace_generate_call_2(match):
    return """                prompt_tokens = len(prompt) // 4
                num_predict, num_ctx, warnings = compute_optimal_settings(
                    task=PipelineTask.EPISTEMIC,
                    prompt_tokens=prompt_tokens,
                    model=self.llm.model,
                    think=False,
                )

                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_EPISTEMIC_CODE_SYSTEM,
                    num_predict=num_predict, num_ctx=num_ctx,"""

content = re.sub(
    r'                text, tokens = self\.llm\.generate\(\n                    prompt, system=BATCHED_EPISTEMIC_CODE_SYSTEM,\n                    num_predict=len\(items\) \* 400,',
    replace_generate_call_2,
    content
)

def replace_generate_call_3(match):
    return """                prompt_tokens = len(prompt) // 4
                num_predict, num_ctx, warnings = compute_optimal_settings(
                    task=PipelineTask.EPISTEMIC,
                    prompt_tokens=prompt_tokens,
                    model=self.llm.model,
                    think=False,
                )

                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_EPISTEMIC_DOC_SYSTEM,
                    num_predict=num_predict, num_ctx=num_ctx,"""

content = re.sub(
    r'                text, tokens = self\.llm\.generate\(\n                    prompt, system=BATCHED_EPISTEMIC_DOC_SYSTEM,\n                    num_predict=len\(items\) \* 400,',
    replace_generate_call_3,
    content
)

with open('src/codrag/core/epistemic_enrichment.py', 'w') as f:
    f.write(content)

