#!/bin/bash
set -e

# CoDRAG Sidecar Builder (Phase 08 MVP)
# Builds the Python daemon into a single-file executable using PyInstaller.

# Check if pyinstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "Error: pyinstaller not found. Please install it via 'pip install pyinstaller'."
    exit 1
fi

echo "Building CoDRAG daemon sidecar..."

# Clean previous builds
rm -rf build/ dist/

# Determine OS for specific flags if needed
OS="$(uname -s)"
case "${OS}" in
    Darwin*)    echo "Target: macOS";;
    Linux*)     echo "Target: Linux";;
    MINGW*)     echo "Target: Windows";;
    *)          echo "Target: Unknown (${OS})";;
esac

# Build command
# --name: Output binary name
# --onefile: Single executable
# --clean: Clean cache
# --hidden-import: Ensure dynamic imports are included
# --collect-all: Collect packages that might have hidden data/binaries (like onnxruntime, tokenizers)
# Note: we might need more specific collects for onnxruntime/tokenizers depending on the platform.

pyinstaller \
    --name codrag-daemon \
    --onefile \
    --clean \
    --hidden-import="codrag.core.embedder" \
    --hidden-import="codrag.core.compressor" \
    --collect-all="codrag" \
    --collect-all="uvicorn" \
    --collect-all="fastapi" \
    --collect-all="onnxruntime" \
    --collect-all="tokenizers" \
    src/codrag/server.py

echo "Build complete."

# Determine Target Triple for Tauri
if command -v rustc &> /dev/null; then
    TARGET_TRIPLE=$(rustc -vV | grep "host:" | cut -d " " -f 2)
else
    # Fallback detection
    ARCH=$(uname -m)
    if [[ "$OS" == "Darwin"* ]]; then
        if [[ "$ARCH" == "arm64" ]]; then
            ARCH="aarch64"
        fi
        TARGET_TRIPLE="${ARCH}-apple-darwin"
    elif [[ "$OS" == "Linux"* ]]; then
        TARGET_TRIPLE="${ARCH}-unknown-linux-gnu"
    elif [[ "$OS" == "MINGW"* ]]; then
        TARGET_TRIPLE="${ARCH}-pc-windows-msvc"
    else
        echo "Error: Could not determine target triple. Please install rustc."
        exit 1
    fi
fi

echo "Detected target triple: $TARGET_TRIPLE"

# Target directory for Tauri binaries
TAURI_BIN_DIR="src/codrag/dashboard/src-tauri/binaries"
mkdir -p "$TAURI_BIN_DIR"

# Move and rename binary
SRC_BIN="dist/codrag-daemon"
DEST_BIN="$TAURI_BIN_DIR/codrag-daemon-$TARGET_TRIPLE"

if [[ "$OS" == "MINGW"* ]]; then
    SRC_BIN="${SRC_BIN}.exe"
    DEST_BIN="${DEST_BIN}.exe"
fi

if [ -f "$SRC_BIN" ]; then
    echo "Moving binary to $DEST_BIN"
    mv "$SRC_BIN" "$DEST_BIN"
    
    # chmod if on unix
    if [[ "$OS" == "Darwin"* ]] || [[ "$OS" == "Linux"* ]]; then
        chmod +x "$DEST_BIN"
    fi
else
    echo "Error: Built binary not found at $SRC_BIN"
    exit 1
fi

echo "Sidecar prepared successfully."
