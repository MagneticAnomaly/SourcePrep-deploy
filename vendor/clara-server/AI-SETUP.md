# AI Assistant Quick Setup Guide

**For AI assistants helping users set up CLaRa-Remembers-It-All.**

This document provides copy-paste commands for the fastest possible setup.

---

## One-Command Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/EricBintner/CLaRa-Remembers-It-All/main/setup.sh | bash
```

---

## Manual Setup (3 Commands)

```bash
git clone https://github.com/EricBintner/CLaRa-Remembers-It-All.git && cd CLaRa-Remembers-It-All
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
clara-server
```

---

## Platform-Specific Commands

### macOS (Apple Silicon)

```bash
# Setup
git clone https://github.com/EricBintner/CLaRa-Remembers-It-All.git
cd CLaRa-Remembers-It-All
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run (uses MPS backend automatically)
clara-server --port 8765
```

### Linux (NVIDIA GPU)

```bash
# Setup
git clone https://github.com/EricBintner/CLaRa-Remembers-It-All.git
cd CLaRa-Remembers-It-All
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run (uses CUDA backend automatically)
clara-server --port 8765
```

### Docker (Any Platform)

```bash
# NVIDIA GPU
docker run -p 8765:8765 --gpus all ghcr.io/ericbintner/clara-remembers-it-all

# CPU only (slow)
docker run -p 8765:8765 ghcr.io/ericbintner/clara-remembers-it-all:cpu
```

---

## Verify Installation

```bash
# Health check
curl http://localhost:8765/health

# Expected: {"status": "healthy", "model_loaded": true}

# Test compression
curl -X POST http://localhost:8765/compress \
  -H "Content-Type: application/json" \
  -d '{"memories": ["User likes coffee", "User works remotely"], "query": "What does the user prefer?"}'
```

---

## Run as Background Service

### macOS/Linux (tmux)

```bash
tmux new -s clara -d 'cd CLaRa-Remembers-It-All && source .venv/bin/activate && clara-server'
```

### macOS/Linux (nohup)

```bash
cd CLaRa-Remembers-It-All
source .venv/bin/activate
nohup clara-server > clara.log 2>&1 &
```

---

## Connect Client Application

### Configure Remote Mode (HumanAI example)

```bash
# Set remote URL (replace IP with server's IP)
curl -X POST http://localhost:5000/api/clara/config \
  -H "Content-Type: application/json" \
  -d '{"use_remote": true, "remote_url": "http://SERVER_IP:8765"}'

# Enable CLaRa
curl -X POST http://localhost:5000/api/clara/toggle \
  -d '{"enabled": true}'
```

### Python Client

```python
import requests

def compress(memories, query, url="http://localhost:8765"):
    return requests.post(f"{url}/compress", json={
        "memories": memories,
        "query": query
    }).json()

result = compress(["fact 1", "fact 2"], "question?")
print(result["answer"])
```

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Port in use | `clara-server --port 9000` |
| CUDA not found | Verify `nvidia-smi` works, reinstall PyTorch with CUDA |
| Out of memory | Need 16GB+ unified (Mac) or 14GB+ VRAM (NVIDIA) |
| Slow first request | Normal - model warming up, subsequent requests faster |

---

## Requirements Summary

| Platform | Memory | GPU |
|----------|--------|-----|
| macOS | 16GB+ unified | M1/M2/M3 |
| Linux | 14GB+ VRAM | NVIDIA (CUDA) |
| CPU-only | 28GB+ RAM | None (slow) |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/status` | Model info |
| POST | `/compress` | Compress memories |

### POST /compress

```json
{
  "memories": ["string array of documents"],
  "query": "question to answer from memories",
  "max_new_tokens": 128,
  "keep_alive": 300
}
```

Response:
```json
{
  "success": true,
  "answer": "compressed answer",
  "original_tokens": 500,
  "compressed_tokens": 31,
  "compression_ratio": 16.0
}
```
