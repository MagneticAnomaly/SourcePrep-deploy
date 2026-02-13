# CLaRa-Remembers-It-All

🧠 **Like Ollama, but for Apple's CLaRa context compression model.**

Run `clara-server` once (locally or on a GPU box), then call it from any app over HTTP.

- **What it is**: A lightweight REST server that hosts the CLaRa model and exposes `POST /compress`.
- **What it isn't**: A Python library you import into your app; your app stays separate and just makes HTTP requests.

> *"Because CLaRa remembers it all... in 16x less space."*

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

---

## ⚡ Quick Start (Copy-Paste)

```bash
# One-liner setup
git clone https://github.com/EricBintner/CLaRa-Remembers-It-All.git && cd CLaRa-Remembers-It-All && python3 -m venv .venv && source .venv/bin/activate && pip install -e . && clara-server
```

Or step by step:
```bash
git clone https://github.com/EricBintner/CLaRa-Remembers-It-All.git
cd CLaRa-Remembers-It-All
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
clara-server
```

**First run downloads ~14GB model (5-10 min).** Server runs at `http://localhost:8765`

**Test it:**
```bash
curl http://localhost:8765/health
curl -X POST http://localhost:8765/compress -H "Content-Type: application/json" \
  -d '{"memories": ["User likes hiking", "User has a dog"], "query": "What are the user hobbies?"}'
```

> 📖 **AI assistants:** See [AI-SETUP.md](AI-SETUP.md) for platform-specific commands and troubleshooting.

---

## What Is This?

**CLaRa-Remembers-It-All** is a standalone HTTP server that provides **semantic context compression** for RAG (Retrieval-Augmented Generation) systems.

You send it a list of memories/documents and a query → it compresses them into a dense representation and returns an answer, using **16x to 128x fewer tokens** than the original text while preserving meaning.

```
┌─────────────────┐         ┌─────────────────────┐         ┌──────────────┐
│  Your RAG App   │  HTTP   │  CLaRa-Remembers-   │         │   Answer +   │
│  (any language) │ ──────► │     It-All Server   │ ──────► │  Compression │
│                 │  POST   │                     │         │    Stats     │
└─────────────────┘         └─────────────────────┘         └──────────────┘
     memories[]                   CLaRa Model                  "User enjoys
     + query                      (7B params)                   hiking..."
```

**Key point:** This is a *universal tool* - it works with any RAG system, any programming language, any framework. Just make HTTP calls.

---

## About CLaRa

[CLaRa](https://github.com/apple/ml-clara) (Continuous Latent Reasoning Architecture) is a 7B parameter model from Apple ML Research that performs **semantic context compression**. It takes a collection of documents and a question, compresses the documents into a dense representation, and generates an answer—all while using significantly fewer tokens than traditional approaches.

| Compression Level | Token Reduction | Use Case |
|-------------------|-----------------|----------|
| `compression-16` | **16x smaller** | Best quality, recommended |
| `compression-128` | **128x smaller** | Maximum compression |

**Example:** 20 documents totaling 2,000 tokens → compressed to ~125 tokens → model answers from the compressed context.

This is especially useful for RAG systems, long-context applications, and anywhere you want to fit more information into a fixed context window.

---

## Why This Server?

Apple released CLaRa as model weights on HuggingFace, but using it requires:
- Loading a 7B model into memory
- Writing PyTorch inference code
- Managing GPU/CPU resources

**CLaRa-Remembers-It-All** wraps all of this into a simple HTTP server:

| You get... | Instead of... |
|------------|---------------|
| `POST /compress` | Writing model loading code |
| Run on any machine, call from anywhere | Running locally only |
| CUDA, MPS, CPU auto-detection | Manual backend setup |
| Health checks, Docker, config | Building infrastructure |

**One machine runs the model, any application can use it over HTTP.**

---

## How It Works

### 1. Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    CLaRa-Remembers-It-All                      │
├────────────────────────────────────────────────────────────────┤
│  FastAPI Server (REST API)                                     │
│    ├── POST /compress  → Compress memories, generate answer    │
│    ├── GET  /status    → Model info, stats                     │
│    └── GET  /health    → Health check for load balancers       │
├────────────────────────────────────────────────────────────────┤
│  Model Layer                                                   │
│    ├── PyTorch Backend (CUDA/MPS)                              │
│    ├── MLX Backend (Apple Silicon native) [planned]            │
│    └── CPU Fallback                                            │
├────────────────────────────────────────────────────────────────┤
│  CLaRa Model (apple/CLaRa-7B-Instruct)                         │
│    └── 7B parameter model with compression layers              │
└────────────────────────────────────────────────────────────────┘
```

### 2. The Compression Process

When you call `/compress`:

1. **Input:** List of memory strings + query
2. **Encode:** Each memory is encoded into dense vectors
3. **Compress:** CLaRa's compression layers reduce 16-128 tokens → 1 token
4. **Generate:** Model generates answer from compressed representation
5. **Output:** Answer + compression statistics

### 3. Use Cases

- **Personal AI assistants** - Compress user history/preferences
- **Document Q&A** - Compress retrieved passages before answering
- **Chatbots with memory** - Store more context in less space
- **Cost optimization** - Reduce API token costs by 16x
- **Edge deployment** - Fit more context on smaller models

---

## Features

- 🔥 **FastAPI REST API** - Simple `/compress` endpoint
- 🐳 **Docker ready** - One command deployment
- 🍎 **Apple Silicon** - MPS backend, MLX coming soon
- 🖥️ **NVIDIA CUDA** - Full GPU acceleration
- 📊 **Production features** - Health checks, metrics, configurable
- 🌐 **Universal** - Use with any RAG system, any language
- 🔒 **Optional auth** - API key authentication
- ⚙️ **Configurable** - Environment variables for all settings

## Quick Start

### Docker (Recommended)

```bash
# NVIDIA GPU
docker run -p 8765:8765 --gpus all ghcr.io/ericbintner/clara-remembers-it-all

# Apple Silicon (coming soon)
docker run -p 8765:8765 ghcr.io/ericbintner/clara-remembers-it-all:mlx
```

### From Source

```bash
git clone https://github.com/ericbintner/CLaRa-Remembers-It-All.git
cd CLaRa-Remembers-It-All
pip install -e .
clara-server
```

## API Usage

### Compress Memories

```bash
curl -X POST http://localhost:8765/compress \
  -H "Content-Type: application/json" \
  -d '{
    "memories": [
      "User likes hiking in national parks.",
      "User works as a software engineer.",
      "User has a dog named Max."
    ],
    "query": "What outdoor activities does the user enjoy?",
    "keep_alive": 300
  }'
```

**Response:**
```json
{
  "success": true,
  "answer": "The user enjoys hiking in national parks.",
  "original_tokens": 25,
  "compressed_tokens": 1,
  "compression_ratio": 16.0,
  "latency_ms": 342
}
```

### Check Status

```bash
curl http://localhost:8765/status
```

### Health Check

```bash
curl http://localhost:8765/health
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CLARA_MODEL` | `apple/CLaRa-7B-Instruct` | HuggingFace model ID |
| `CLARA_SUBFOLDER` | `compression-16` | Compression level (16 or 128) |
| `CLARA_PORT` | `8765` | Server port |
| `CLARA_HOST` | `0.0.0.0` | Bind address |
| `CLARA_BACKEND` | `auto` | Backend: `auto`, `cuda`, `mps`, `mlx`, `cpu` |
| `CLARA_KEEP_ALIVE` | `300` | Seconds to keep model loaded (0=immediate, -1=never) |
| `CLARA_CACHE` | `~/.cache/clara-server` | Model cache directory |

### Per-Request Keep-Alive

You can override the default keep-alive setting for a specific request by passing the `keep_alive` parameter in the API body:

```json
{
  "memories": ["..."],
  "query": "...",
  "keep_alive": 0
}
```

| Value | Behavior |
|-------|----------|
| `"keep_alive": 60` | Override: keep loaded 60s after this request |
| `"keep_alive": 0` | Unload immediately after this request |
| `"keep_alive": -1` | Never unload after this request |
| *(omitted)* | Use server default |

## Backends & Memory Options

### Compute Backends

| Backend | Platform | GPU Acceleration | Status |
|---------|----------|------------------|--------|
| **CUDA** | Linux/Windows + NVIDIA | ✅ Yes | ✅ Stable |
| **MPS** | macOS + Apple Silicon | ✅ Yes (Metal) | ✅ Stable |
| **MLX** | macOS + Apple Silicon | ✅ Yes (Metal) | 🔜 Planned |
| **MLX** | Linux | ❌ CPU only | ⚠️ Slow |
| **CPU** | Any | ❌ No | ⚠️ Slow |

> **Note on MLX + Linux:** MLX technically runs on Linux but only with CPU backend (no GPU). This is an MLX limitation, not CLaRa - MLX's GPU acceleration requires Apple's Metal API. For Linux, use CUDA with an NVIDIA GPU instead.

### Memory Configurations

| Mode | VRAM/RAM Required | Speed | Status |
|------|-------------------|-------|--------|
| **fp16** (default) | ~14GB GPU | Fast | ✅ Works |
| **fp32** | ~28GB CPU RAM | Slow | ✅ Works |
| **8-bit** (bitsandbytes) | ~7GB GPU | Medium | ❌ Broken* |
| **4-bit** (bitsandbytes) | ~4GB GPU | Medium | ❌ Broken* |
| **GPTQ** | ~4GB GPU | Fast | 🔜 Planned |
| **AWQ** | ~4GB GPU | Fast | 🔜 Planned |

*\*bitsandbytes quantization has device mismatch issues with CLaRa's custom architecture. See [QUANTIZATION.md](docs/QUANTIZATION.md) for details and workarounds.*

## Auto-Unload (Ollama-Style Memory Management)

CLaRa implements **Ollama-style auto-unload** to free RAM when the model is idle:

```
Request → Model Loads → Timer Starts → Idle Timeout → Model Unloads → RAM Free
              ↑                                              ↓
              └──────────── Next Request ←──────────────────┘
```

| Setting | Value | Behavior |
|---------|-------|----------|
| `--keep-alive 300` | 5 minutes (default) | Unload after 5 min idle |
| `--keep-alive 0` | 0 seconds | Unload immediately after each request |
| `--keep-alive -1` | Never | Keep loaded forever (old behavior) |

**Examples:**
```bash
# Default: 5 minute keep-alive (like Ollama)
clara-server

# Aggressive memory savings: unload immediately
clara-server --keep-alive 0

# Never unload (persistent)
clara-server --keep-alive -1

# Environment variable
CLARA_KEEP_ALIVE=60 clara-server
```

The `/status` endpoint shows auto-unload timing:
```json
{
  "initialized": true,
  "keep_alive_seconds": 300,
  "last_activity": "2024-01-15T10:30:00Z",
  "will_unload_at": "2024-01-15T10:35:00Z",
  "seconds_until_unload": 180
}
```

## Integration Examples

### Python Client

```python
import requests

def compress_memories(memories: list, query: str, url: str = "http://localhost:8765"):
    response = requests.post(f"{url}/compress", json={
        "memories": memories,
        "query": query
    })
    return response.json()

# Example
result = compress_memories(
    memories=["User likes coffee.", "User works remotely."],
    query="What does the user prefer?"
)
print(result["answer"])
```

### JavaScript/TypeScript

```typescript
async function compressMemories(memories: string[], query: string): Promise<any> {
  const response = await fetch("http://localhost:8765/compress", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ memories, query })
  });
  return response.json();
}
```

### LangChain Integration

```python
from langchain.retrievers import BaseRetriever

class ClaraCompressedRetriever(BaseRetriever):
    clara_url: str = "http://localhost:8765"
    
    def _get_relevant_documents(self, query: str):
        # Your retrieval logic + clara compression
        pass
```

## Deployment

### Docker Compose

```yaml
version: "3.8"
services:
  clara:
    image: ghcr.io/ericbintner/clara-remembers-it-all
    ports:
      - "8765:8765"
    volumes:
      - clara-cache:/root/.cache/clara-server
    environment:
      - CLARA_MODEL=apple/CLaRa-7B-Instruct
      - CLARA_SUBFOLDER=compression-16
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  clara-cache:
```

### Kubernetes

See [docs/kubernetes.md](docs/kubernetes.md) for Helm chart and deployment manifests.

## Requirements

- **CUDA**: NVIDIA GPU with 14GB+ VRAM (RTX 3090, RTX 4090, A100, etc.)
- **Apple Silicon**: Mac with 16GB+ unified memory (M1 Pro/Max, M2, M3, Mac Studio)
- **CPU**: 28GB+ RAM (not recommended for production)
- Python 3.10+

## Development

```bash
# Clone
git clone https://github.com/ericbintner/CLaRa-Remembers-It-All.git
cd CLaRa-Remembers-It-All

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Run server in dev mode
clara-server --reload
```

## Roadmap

**Core:**
- [x] FastAPI REST server
- [x] CUDA backend (NVIDIA GPUs)
- [x] MPS backend (Apple Silicon via PyTorch)
- [x] Docker deployment

**In Progress:**
- [ ] MLX backend (native Apple Silicon, faster than MPS)
- [ ] GPTQ quantization (4GB VRAM)
- [ ] AWQ quantization (4GB VRAM)

**Planned:**
- [ ] Batching for higher throughput
- [ ] Prometheus metrics endpoint
- [ ] Multi-GPU support
- [ ] Kubernetes Helm chart
- [ ] bitsandbytes fix (pending upstream)

## Known Issues

### Quantization Limitations

4-bit and 8-bit quantization via bitsandbytes currently causes device mismatch errors with CLaRa's custom model architecture. This is due to how bitsandbytes handles CPU↔GPU tensor placement combined with CLaRa's `index_select` operations.

**Workarounds:**
- Use fp16 with sufficient VRAM (14GB+)
- Use Apple Silicon with MPS backend (unified memory avoids the issue)
- Run as a network service on a machine with sufficient resources
- Wait for GPTQ/AWQ support (keeps all weights on GPU)

See [QUANTIZATION.md](docs/QUANTIZATION.md) for technical details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## License

Apache 2.0 - Same as [Apple's ml-clara](https://github.com/apple/ml-clara).

## Acknowledgments

- [Apple ML Research](https://github.com/apple/ml-clara) for the CLaRa model
- [HuggingFace](https://huggingface.co/apple) for model hosting
- The open-source RAG community

## Citation

If you use clara-server in your research, please cite the original CLaRa paper:

```bibtex
@article{clara2024,
  title={CLaRa: Bridging Retrieval and Generation with Continuous Latent Reasoning},
  author={Apple ML Research},
  year={2024}
}
```
