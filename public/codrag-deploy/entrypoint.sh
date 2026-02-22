#!/usr/bin/env bash
set -euo pipefail

# GPU image entrypoint: start Ollama in background, then run codrag.
# Usage: docker run codrag/headless:gpu sync-headless --repo-path . ...

# Start Ollama server in background (only if model-provider is local)
if [[ "${1:-}" == "sync-headless" ]] && echo "$@" | grep -q "model-provider local"; then
    echo "[codrag-headless] Starting Ollama server..."
    ollama serve &
    OLLAMA_PID=$!

    # Wait for Ollama to be ready
    for i in $(seq 1 30); do
        if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            echo "[codrag-headless] Ollama ready."
            break
        fi
        sleep 1
    done
fi

# Run the codrag CLI with all arguments
exec codrag "$@"
