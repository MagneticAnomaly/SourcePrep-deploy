# CLaRa Quantization Support

**Status:** ⚠️ Limited  
**Last Updated:** 2026-01-05

## Overview

CLaRa's custom model architecture has compatibility issues with certain quantization methods. This document explains the current state and workarounds.

## Current Support

| Method | Status | Notes |
|--------|--------|-------|
| **fp16** | ✅ Works | Default, requires ~14GB VRAM |
| **fp32** | ✅ Works | CPU fallback, ~28GB RAM |
| **bitsandbytes 4-bit** | ❌ Broken | Device mismatch errors |
| **bitsandbytes 8-bit** | ❌ Broken | Device mismatch errors |
| **GPTQ** | 🔜 Planned | Requires quantized weights |
| **AWQ** | 🔜 Planned | Requires quantized weights |

## The Problem with bitsandbytes

### Error Message

```
RuntimeError: Expected all tensors to be on the same device, but got index is on cuda:0, 
different from other tensors on cpu (when checking argument in method wrapper_CUDA__index_select)
```

### Root Cause

1. **bitsandbytes** stores quantized weights on CPU and moves them to GPU during computation
2. **CLaRa's custom code** uses `index_select` operations that expect all tensors on the same device
3. The model's `generate_from_text()` method references `self.decoder.device` but this doesn't account for the CPU-GPU split

### Affected Code

In CLaRa's `modeling_clara.py`:
```python
def generate_from_text(self, questions, documents, max_new_tokens=128):
    device = self.decoder.device  # Returns cuda:0
    enc_input_ids = input_encoder['input_ids'].to(device)  # Moves to cuda:0
    # But quantized weight tensors are on CPU - causes mismatch
```

## Workarounds

### Option 1: Use fp16 with Sufficient VRAM

If you have 14GB+ VRAM (RTX 3090, RTX 4090, etc.), use fp16:

```bash
CLARA_BACKEND=cuda clara-server
```

### Option 2: Use Apple Silicon

Mac Studio/Pro with 16GB+ unified memory works well:

```bash
CLARA_BACKEND=mps clara-server
```

### Option 3: Remote Server

Run clara-server on a machine with sufficient resources:

```bash
# On server with good GPU
clara-server --port 8765

# From client
curl http://server-ip:8765/compress ...
```

### Option 4: CPU (Slow)

For testing only - very slow:

```bash
CLARA_BACKEND=cpu clara-server
```

## Future Plans

### GPTQ/AWQ Support

These quantization methods keep all weights on GPU, avoiding the device mismatch issue. However, they require:

1. Pre-quantized model weights
2. Someone to create and publish quantized CLaRa weights

We plan to add support when quantized weights become available.

### Upstream Fix

We're monitoring:
- [apple/ml-clara](https://github.com/apple/ml-clara) for updates
- [huggingface/peft](https://github.com/huggingface/peft/issues/1831) for similar issues
- [bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes) for fixes

## Memory Requirements

| Mode | GPU VRAM | System RAM |
|------|----------|------------|
| fp16 (CUDA) | ~14GB | ~4GB |
| fp16 (MPS) | ~14GB unified | N/A |
| fp32 (CPU) | 0 | ~28GB |
| 4-bit (if working) | ~4GB | ~4GB |
| 8-bit (if working) | ~7GB | ~4GB |

## Testing Quantization

If you want to test whether quantization works in your environment:

```python
import torch
from transformers import AutoModel, BitsAndBytesConfig

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

model = AutoModel.from_pretrained(
    "path/to/clara/compression-16",
    trust_remote_code=True,
    quantization_config=bnb_config,
    device_map="auto",
)

# Test inference
try:
    output = model.generate_from_text(
        questions=["Test query"],
        documents=[["Test document"]],
        max_new_tokens=32,
    )
    print("✓ Quantization works!")
except RuntimeError as e:
    print(f"✗ Device mismatch: {e}")
```

## Contributing

If you find a solution to the quantization issue, please:
1. Open an issue describing your fix
2. Submit a PR with tests
3. Document any requirements or limitations

We especially welcome:
- Patches to CLaRa's modeling code for device handling
- Pre-quantized GPTQ/AWQ weights
- Alternative quantization approaches
