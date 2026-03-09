import re

file_path = "/Volumes/4TB-BAD/HumanAI/CoDRAG/docs/Phase46_large-context-window-research-reccommendations-tooling/GPU_VRAM_MODEL_REFERENCE.md"

with open(file_path, "r") as f:
    content = f.read()

# Update the recommendations
content = re.sub(
    r"\| \*\*M1/M2/M3 Air\*\* \| 16GB \(12GB GPU\) \| qwen3:8b Q4 \(5\.2GB\) \| ✅ \| Only small models fit \|",
    "| **M1/M2/M3 Air** | 16GB (12GB GPU) | qwen3.5:9b Q4 (5.5GB) | ✅ | Minimum viable model (replace 8b) |",
    content
)

content = re.sub(
    r"\| \*\*M-Pro 32GB\*\* \| 32GB \(24GB GPU\) \| 35b-a3b Q4 \(24GB\) \| ⚠️ Tight \| Model barely fits, little KV headroom \|",
    "| **M-Pro 32GB** | 32GB (24GB GPU) | 35b-a3b Q4 (24GB) | ⚠️ Tight | Use Q4 if low RAM; better than 9b |",
    content
)

content = re.sub(
    r"\| \*\*M-Pro 36GB\*\* \| 36GB \(27GB GPU\) \| 35b-a3b Q4 \(24GB\) \| ✅ \| ~3GB KV headroom \|",
    "| **M-Pro 36GB** | 36GB (27GB GPU) | 35b-a3b Q8 (39GB) | ✅ | Swap allows Q8; new baseline |",
    content
)

content = re.sub(
    r"\| \*\*M-Max 64GB\*\* \| 64GB \(48GB GPU\) \| 35b-a3b Q8 \(39GB\) \| ✅ \| ~9GB KV headroom \|",
    "| **M-Max 64GB** | 64GB (48GB GPU) | 35b-a3b Q8 (39GB) | ✅ | New baseline recommended model |",
    content
)

content = re.sub(
    r"\| \*\*RTX 4090 24GB\*\* \| 24GB VRAM \| 35b-a3b Q4 \(24GB\) \| ✅ \| Fits entirely in VRAM \|",
    "| **RTX 4090 24GB** | 24GB VRAM | 35b-a3b Q8 (39GB) | ⚠️ | Offload to RAM for Q8 baseline |",
    content
)

# Replace the CoDRAG Pipeline Task Recommendations
old_task_recs = """### CoDRAG Pipeline Task Recommendations

| Task | Best Model | Think | num_predict | Why |
|---|---|---|---|---|
| **Augmentation** (per-file) | 35b-a3b Q4 | OFF | 2048 | Fastest, simple JSON |
| **Epistemic** (per-file) | 35b-a3b Q4 | OFF | 2048 | Speed matters, good quality |
| **Group Reasoning** | 35b-a3b Q4 | **ON** | 8192 | Think genuinely improves patterns |
| **Atlas** (small repo) | 35b-a3b Q4 | OFF | 4096 | Model self-terminates |
| **Atlas** (large repo) | 35b-a3b Q4 | OFF | 32768 | Models utilize larger budget |
| **Audit** | 35b-a3b Q4 | OFF | 16384 | Generous for detailed report |

### If You Want Maximum Quality (and Have Time)

| Task | Premium Model | Think | Notes |
|---|---|---|---|
| Group Reasoning | 122b-a10b | ON | Deepest architectural insights |
| Atlas | 122b-a10b | OFF | Most accurate IDENTITY section |
| Epistemic | 27b Q8 (dense) | OFF | Richest tech debt analysis (22× slower) |"""

new_task_recs = """### CoDRAG Pipeline Task Recommendations

| Task | Best Model | Think | num_predict | Why |
|---|---|---|---|---|
| **Augmentation** (per-file) | 35b-a3b Q8 | OFF | 2048 | New baseline, high quality and fast |
| **Epistemic** (per-file) | kimi-k2.5:cloud | **ON** | 8192 | Cloud option handles high volume tasks extremely fast |
| **Group Reasoning** | kimi-k2.5:cloud | **ON** | 8192 | 1T param quantized model blows away local options |
| **Atlas** (small repo) | 35b-a3b Q8 | OFF | 4096 | Q8 is the clear winner for local |
| **Atlas** (large repo) | 35b-a3b Q8 | OFF | 32768 | Models utilize larger budget |
| **Audit** | 35b-a3b Q8 | OFF | 16384 | Q8 produces detailed, technically specific reports |

### If You Want Maximum Quality (and Have Time)

| Task | Premium Model | Think | Notes |
|---|---|---|---|
| Group Reasoning | kimi-k2.5:cloud | ON | Unmatched reasoning capabilities |
| Atlas | kimi-k2.5:cloud | OFF | Most accurate IDENTITY section |
| Epistemic | 27b Q8 (dense) | OFF | Richest tech debt analysis (local) |
| Coding Tasks | qwen3-coder-next Q8 | OFF | Winner for code-specific tasks |"""

content = content.replace(old_task_recs, new_task_recs)

with open(file_path, "w") as f:
    f.write(content)
