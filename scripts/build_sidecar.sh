#!/bin/bash
set -e

# Prep Sidecar Builder (Phase 08 MVP)
# Builds the Python daemon into a single-file executable using PyInstaller.
# Integrates the correct platform-specific Rust engine wheel.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Determine OS and architecture for wheel selection
OS="$(uname -s)"
ARCH=$(uname -m)
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')

# Map architecture names to wheel platform tags
case "${ARCH}" in
    x86_64) WHEEL_ARCH="x86_64" ;;
    amd64) WHEEL_ARCH="x86_64" ;;
    arm64) WHEEL_ARCH="arm64" ;;
    aarch64) WHEEL_ARCH="aarch64" ;;
    *) WHEEL_ARCH="${ARCH}" ;;
esac

# Map OS to platform tag
case "${OS}" in
    Darwin*) PLATFORM="macosx";;
    Linux*) PLATFORM="linux";;
    MINGW*) PLATFORM="win";;
    *) PLATFORM="unknown";;
esac

echo "Building Prep daemon sidecar..."
echo "Platform: ${OS} (${PLATFORM})"
echo "Architecture: ${ARCH} (${WHEEL_ARCH})"
echo "Python Version: ${PYTHON_VERSION}"

# Check if pyinstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "Error: pyinstaller not found. Please install it via 'pip install pyinstaller'."
    exit 1
fi

# Clean previous builds
rm -rf build/ dist/

# ENG-6: Integrate correct platform wheel
WHEEL_DIR="${REPO_ROOT}/engine/target/wheels"
WHEEL_PATTERN="prep_engine-*-cp${PYTHON_VERSION}-*.whl"

# Find the best matching wheel
WHEEL_FILE=""
if [ -d "$WHEEL_DIR" ]; then
    echo "Looking for wheels in: $WHEEL_DIR"
    echo "Pattern: $WHEEL_PATTERN"
    
    # List available wheels
    ls -la "$WHEEL_DIR"/*.whl 2>/dev/null || echo "No wheels found in $WHEEL_DIR"
    
    # Try to find exact platform match first
    if [[ "$PLATFORM" == "macosx" ]]; then
        # For macOS, try to match architecture
        if [[ "$WHEEL_ARCH" == "arm64" ]] || [[ "$WHEEL_ARCH" == "aarch64" ]]; then
            WHEEL_FILE=$(find "$WHEEL_DIR" -name "*arm64*.whl" -o -name "*aarch64*.whl" 2>/dev/null | grep "cp${PYTHON_VERSION}" | head -1)
        else
            WHEEL_FILE=$(find "$WHEEL_DIR" -name "*x86_64*.whl" 2>/dev/null | grep "cp${PYTHON_VERSION}" | head -1)
        fi
    elif [[ "$PLATFORM" == "linux" ]]; then
        WHEEL_FILE=$(find "$WHEEL_DIR" -name "*linux*.whl" 2>/dev/null | grep "cp${PYTHON_VERSION}" | head -1)
    elif [[ "$PLATFORM" == "win" ]]; then
        WHEEL_FILE=$(find "$WHEEL_DIR" -name "*win*.whl" 2>/dev/null | grep "cp${PYTHON_VERSION}" | head -1)
    fi
    
    # Fallback: any matching Python version wheel
    if [ -z "$WHEEL_FILE" ]; then
        echo "No exact platform match, trying any compatible wheel..."
        WHEEL_FILE=$(find "$WHEEL_DIR" -name "prep_engine-*-cp${PYTHON_VERSION}-*.whl" 2>/dev/null | head -1)
    fi
fi

# Install the wheel if found
if [ -n "$WHEEL_FILE" ] && [ -f "$WHEEL_FILE" ]; then
    echo "Found wheel: $WHEEL_FILE"
    echo "Installing wheel..."
    pip install --force-reinstall "$WHEEL_FILE" --quiet
    echo "Wheel installed successfully."
else
    echo "Warning: No compatible wheel found for cp${PYTHON_VERSION} ${PLATFORM}/${WHEEL_ARCH}"
    echo "Falling back to source-based build (slower)..."
    echo "To build the wheel first, run: cd ${REPO_ROOT}/engine && maturin build --release"
fi

# Build command
# --name: Output binary name
# --onefile: Single executable
# --clean: Clean cache
# --hidden-import: Ensure dynamic imports are included
# --collect-all: Collect packages that might have hidden data/binaries (like onnxruntime, tokenizers)
# Note: we might need more specific collects for onnxruntime/tokenizers depending on the platform.

pyinstaller \
    --name prep-daemon \
    --onefile \
    --clean \
    --hidden-import="prep.core.embedder" \
    --hidden-import="prep.core.compressor" \
    --hidden-import="prep_engine" \
    --collect-all="prep" \
    --collect-all="prep_engine" \
    --collect-all="uvicorn" \
    --collect-all="fastapi" \
    --collect-all="onnxruntime" \
    --collect-all="tokenizers" \
    src/prep/server.py

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
TAURI_BIN_DIR="src/prep/dashboard/src-tauri/binaries"
mkdir -p "$TAURI_BIN_DIR"

# Move and rename binary
SRC_BIN="dist/prep-daemon"
DEST_BIN="$TAURI_BIN_DIR/prep-daemon-$TARGET_TRIPLE"

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
