import re

with open('src/codrag/core/augmenter.py', 'r') as f:
    content = f.read()

# Add imports if not present
if 'from codrag.core.context_config import PipelineTask, compute_optimal_settings' not in content:
    content = re.sub(
        r'from typing import ',
        r'from codrag.core.context_config import PipelineTask, compute_optimal_settings\nfrom typing import ',
        content
    )

def replace_retry(match):
    return """    def _llm_generate_with_retry(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_retries: int = 2,
        label: str = "item",
    ) -> Tuple[str, int]:
        \"\"\"Helper for robust single-item generation with retries.

        Returns (text, tokens_used).  Raises RuntimeError after max_retries
        or for immediate parsing failures that shouldn't be retried.  Logs
        the last exception.
        \"\"\"
        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUGMENT,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        last_err: Optional[Exception] = None
        for attempt in range(1 + max_retries):
            try:
                return self.llm.generate(
                    prompt, system=system, 
                    num_predict=num_predict, num_ctx=num_ctx,
                )"""

content = re.sub(
    r'    def _llm_generate_with_retry\([\s\S]*?return self\.llm\.generate\(prompt, system=system, num_predict=num_predict\)',
    replace_retry,
    content
)

def replace_code_batch(match):
    return """        def _call_code_batch(items):
            prompt = build_batched_file_prompt(items)
            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.AUGMENT,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=False,
            )
            try:
                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_FILE_SYSTEM, 
                    num_predict=num_predict, num_ctx=num_ctx,
                    response_schema=file_schema,
                )"""

content = re.sub(
    r'        def _call_code_batch\(items\):\n            prompt = build_batched_file_prompt\(items\)\n            try:\n                text, tokens = self\.llm\.generate\(\n                    prompt, system=BATCHED_FILE_SYSTEM, num_predict=batch_size \* 200,\n                    response_schema=file_schema,\n                \)',
    replace_code_batch,
    content
)

def replace_doc_batch(match):
    return """        def _call_doc_batch(items):
            prompt = build_batched_doc_prompt(items)
            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.AUGMENT,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=False,
            )
            try:
                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_DOC_SYSTEM, 
                    num_predict=num_predict, num_ctx=num_ctx,
                    response_schema=doc_schema,
                )"""

content = re.sub(
    r'        def _call_doc_batch\(items\):\n            prompt = build_batched_doc_prompt\(items\)\n            try:\n                text, tokens = self\.llm\.generate\(\n                    prompt, system=BATCHED_DOC_SYSTEM, num_predict=len\(items\) \* 200,\n                    response_schema=doc_schema,\n                \)',
    replace_doc_batch,
    content
)

with open('src/codrag/core/augmenter.py', 'w') as f:
    f.write(content)

