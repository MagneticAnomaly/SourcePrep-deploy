#!/usr/bin/env bash
set -euo pipefail

# GPU image entrypoint: start Ollama in background, then run codrag.
# Usage: docker run codrag/headless:gpu sync-headless --repo-path . ...

OLLAMA_TIMEOUT="${OLLAMA_STARTUP_TIMEOUT:-30}"

# Start Ollama server in background (only if model-provider is local)
if [[ "${1:-}" == "sync-headless" ]] && echo "$@" | grep -q "model-provider local"; then
    echo "[codrag-headless] Starting Ollama server..."
    ollama serve &
    OLLAMA_PID=$!

    # Wait for Ollama to be ready (fail loudly on timeout)
    OLLAMA_READY=false
    for i in $(seq 1 "$OLLAMA_TIMEOUT"); do
        if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            echo "[codrag-headless] Ollama ready (${i}s)."
            OLLAMA_READY=true
            break
        fi
        sleep 1
    done

    if [ "$OLLAMA_READY" = false ]; then
        echo "[codrag-headless] ERROR: Ollama failed to start within ${OLLAMA_TIMEOUT}s." >&2
        echo "[codrag-headless] Check GPU drivers, VRAM availability, and container GPU access." >&2
        exit 1
    fi
fi

# Run the codrag CLI with all arguments
exec codrag "$@"
