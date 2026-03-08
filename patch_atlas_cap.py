import re

with open('src/codrag/core/atlas/generator.py', 'r') as f:
    content = f.read()

# Add import if missing
content = re.sub(
    r'from codrag.core.context_config import PipelineTask, compute_optimal_settings',
    r'from codrag.core.context_config import PipelineTask, compute_optimal_settings, compute_module_cap',
    content
)

def apply_cap(match):
    return """        modules = self._load_modules()

        if self.llm:
            from codrag.core.context_config import detect_available_vram_gb
            vram = detect_available_vram_gb()
            cap = compute_module_cap(len(modules), available_vram_gb=vram, model=self.llm.model)
            if cap < len(modules):
                # Sort by file count descending and take top N
                modules = sorted(modules, key=lambda x: -x.get("file_count", 0))[:cap]
                logger.info("Capped atlas modules at %d (from %d) due to VRAM", cap, len(modules))

        epistemic = self._load_epistemic_summary()"""

content = re.sub(
    r'        modules = self\._load_modules\(\)\n        epistemic = self\._load_epistemic_summary\(\)',
    apply_cap,
    content
)

with open('src/codrag/core/atlas/generator.py', 'w') as f:
    f.write(content)

