# Remote CLaRa Setup Guide

Complete guide for running CLaRa-Remembers-It-All on a remote machine and connecting clients.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           NETWORK SETUP                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────────┐                    ┌──────────────────┐          │
│   │  Linux Machine   │    Tailscale/LAN   │   Mac Studio     │          │
│   │  (HumanAI)       │ ◄─────────────────►│  (CLaRa Server)  │          │
│   │                  │                    │                  │          │
│   │  - RAG Database  │    HTTP :8765      │  - CLaRa Model   │          │
│   │  - Frontend UI   │                    │  - 64GB+ Memory  │          │
│   │  - Ollama LLMs   │                    │  - MPS Backend   │          │
│   └──────────────────┘                    └──────────────────┘          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Part 1: Server Setup (Mac Studio)

### 1.1 Install CLaRa-Remembers-It-All

```bash
# Clone the repository
git clone https://github.com/EricBintner/CLaRa-Remembers-It-All.git
cd CLaRa-Remembers-It-All

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .
```

### 1.2 First Run (Downloads Model)

The first run downloads the CLaRa model (~14GB). This takes 5-10 minutes:

```bash
# Start server (will download model on first run)
clara-server --port 8765

# You'll see:
# INFO: Loading CLaRa model from HuggingFace...
# INFO: Downloading apple/CLaRa-7B-Instruct...
# INFO: Model loaded in 42.3s
# INFO: Server running on http://0.0.0.0:8765
```

### 1.3 Verify Server

```bash
# From another terminal
curl http://localhost:8765/health
# {"status": "healthy", "model_loaded": true}

curl http://localhost:8765/status
# {"model": "apple/CLaRa-7B-Instruct", "backend": "mps", ...}
```

### 1.4 Run as Background Service

```bash
# Option 1: nohup
nohup clara-server --port 8765 > ~/clara-server.log 2>&1 &

# Option 2: tmux/screen
tmux new -s clara
clara-server --port 8765
# Ctrl+B, D to detach

# Option 3: launchd (macOS service)
# See docs/MACOS_SERVICE.md
```

### 1.5 Configure Firewall (if needed)

```bash
# Allow port 8765 through macOS firewall
# System Preferences > Security & Privacy > Firewall > Firewall Options
# Add clara-server or allow incoming connections
```

---

## Part 2: Network Configuration

### Option A: Tailscale (Recommended)

If both machines are on Tailscale:

```bash
# Get Mac's Tailscale IP
tailscale ip -4
# Example: 100.x.x.x

# Server URL for clients:
# http://100.x.x.x:8765
```

### Option B: Local Network

```bash
# Get Mac's local IP
ipconfig getifaddr en0
# Example: 192.168.1.42

# Server URL for clients:
# http://192.168.1.42:8765
```

### Option C: mDNS/Bonjour

```bash
# Use hostname (works on local network)
# http://mac-studio.local:8765
```

### Verify Connectivity

From the client machine:

```bash
# Test connection
curl http://100.x.x.x:8765/health

# Test compression
curl -X POST http://100.x.x.x:8765/compress \
  -H "Content-Type: application/json" \
  -d '{
    "memories": ["Test memory 1", "Test memory 2"],
    "query": "What do you know?"
  }'
```

---

## Part 3: Client Configuration

### 3.1 HumanAI Integration

Configure HumanAI to use the remote CLaRa server:

```bash
# Via API
curl -X POST http://localhost:5000/api/clara/config \
  -H "Content-Type: application/json" \
  -d '{
    "use_remote": true,
    "remote_url": "http://100.x.x.x:8765"
  }'

# Enable CLaRa
curl -X POST http://localhost:5000/api/clara/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Check health
curl http://localhost:5000/api/clara/remote/health
```

Or via the Settings UI in HumanAI:
1. Go to Settings → Knowledge
2. Enable "CLaRa Context Compression"
3. Enable "Use Remote Server"
4. Enter: `http://100.x.x.x:8765`
5. Click "Test Connection"

### 3.2 Python Client

```python
from clara_client import ClaraClient

client = ClaraClient("http://100.x.x.x:8765")

# Check health
print(client.health())

# Compress memories
result = client.compress(
    memories=["User likes hiking.", "User has a dog."],
    query="What activities does the user enjoy?"
)
print(result["answer"])
```

### 3.3 Any HTTP Client

```bash
# cURL
curl -X POST http://100.x.x.x:8765/compress \
  -H "Content-Type: application/json" \
  -d '{"memories": [...], "query": "..."}'

# Python requests
import requests
requests.post("http://100.x.x.x:8765/compress", json={...})

# JavaScript fetch
fetch("http://100.x.x.x:8765/compress", {method: "POST", ...})
```

---

## Part 4: Testing with Multiple RAG Databases

### 4.1 HumanAI Memory Database

HumanAI automatically uses CLaRa when:
- CLaRa is enabled
- Remote mode is configured
- Query retrieves more than `auto_compress_threshold` memories

Test manually:

```bash
# Get memories from HumanAI
curl http://localhost:5000/api/memory/search?query=hobbies&limit=10

# These are automatically compressed via CLaRa when used in conversation
```

### 4.2 IT App / Other Databases

Any application can use CLaRa-Remembers-It-All:

```python
import requests

# Your app retrieves documents from its database
documents = your_database.search("user query", limit=20)

# Send to CLaRa for compression
response = requests.post(
    "http://100.x.x.x:8765/compress",
    json={
        "memories": [doc.text for doc in documents],
        "query": "user query"
    }
)

compressed_answer = response.json()["answer"]
# Use compressed_answer in your LLM prompt
```

### 4.3 Benchmarking

```bash
# Run benchmark script
cd CLaRa-Remembers-It-All
python examples/benchmark.py --url http://100.x.x.x:8765 --memories 20

# Output:
# Memories: 20
# Original tokens: ~2600
# Compressed tokens: ~162
# Compression ratio: 16.0x
# Latency: 342ms
```

---

## Troubleshooting

### Server won't start

```bash
# Check port in use
lsof -i :8765

# Check logs
tail -f ~/clara-server.log

# Verify model downloaded
ls ~/.cache/clara-server/
```

### Can't connect from client

```bash
# Check server is running
curl http://localhost:8765/health  # on server

# Check firewall
sudo pfctl -sr | grep 8765

# Check Tailscale
tailscale status
```

### Slow compression

- First request is slower (model warm-up)
- MPS backend should give ~300-500ms per request
- If using CPU fallback, expect 5-10 seconds

### Out of memory

```bash
# Check memory usage
top -l 1 | grep clara

# CLaRa needs ~14GB unified memory
# Close other apps if needed
```

---

## Security Considerations

### API Key Authentication

```bash
# On server
export CLARA_API_KEY="your-secret-key"
clara-server --port 8765

# On client
curl -X POST http://server:8765/compress \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Tailscale (Recommended)

Tailscale provides:
- End-to-end encryption
- No exposed ports
- Access control lists

### Local Network Only

If not using Tailscale, bind to local interface:

```bash
clara-server --host 192.168.1.42 --port 8765
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `clara-server` | Start server on 0.0.0.0:8765 |
| `clara-server --port 9000` | Custom port |
| `clara-server --reload` | Dev mode with auto-reload |
| `curl .../health` | Health check |
| `curl .../status` | Full status |
| `curl -X POST .../compress` | Compress memories |

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CLARA_PORT` | 8765 | Server port |
| `CLARA_HOST` | 0.0.0.0 | Bind address |
| `CLARA_BACKEND` | auto | mps/cuda/cpu |
| `CLARA_API_KEY` | (none) | Auth key |
