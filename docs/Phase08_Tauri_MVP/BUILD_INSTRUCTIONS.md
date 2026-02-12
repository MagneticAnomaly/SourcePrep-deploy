# Tauri MVP Build Instructions

## Prerequisites

1.  **Node.js 20+**: Ensure you are using the correct Node version.
    ```bash
    nvm use 20
    ```
2.  **Rust (latest stable)**: Ensure `rustc` and `cargo` are in your path.
    ```bash
    export PATH="$HOME/.cargo/bin:$PATH"
    rustc --version  # Should be 1.70+
    ```
3.  **Python 3.10+**: Required for building the sidecar.
4.  **PyInstaller**: Required for bundling the sidecar.
    ```bash
    pip install pyinstaller packaging==23.2
    ```

## 1. Build the Sidecar

The Python daemon must be built into a standalone executable before building the Tauri app.

```bash
# From repo root
./scripts/build_sidecar.sh
```

This script will:
1.  Run `pyinstaller` on `src/codrag/server.py`.
2.  Detect your architecture (e.g., `x86_64-apple-darwin` or `aarch64-apple-darwin`).
3.  Move the binary to `src/codrag/dashboard/src-tauri/binaries/`.

**Verify:** Check that `src/codrag/dashboard/src-tauri/binaries/` contains `codrag-daemon-<target-triple>`.

## 2. Build the Frontend

Build the React/Vite dashboard.

```bash
cd src/codrag/dashboard
npm install
npm run build
```

**Verify:** Check that `src/codrag/dashboard/dist/index.html` exists.

## 3. Build the Tauri App

Build the native application bundle.

```bash
cd src/codrag/dashboard
# Ensure cargo is in PATH
export PATH="$HOME/.cargo/bin:$PATH"
npx tauri build
```

**Output:**
- **macOS:** `src/codrag/dashboard/src-tauri/target/release/bundle/macos/CoDRAG.app`
- **DMG:** `src/codrag/dashboard/src-tauri/target/release/bundle/dmg/CoDRAG_*.dmg` (may fail signing on dev machines)

## Troubleshooting

### "Sidecar not found"
Ensure the binary in `src/codrag/dashboard/src-tauri/binaries/` matches the target triple of the host.
Run `rustc -vV` to see the expected `host` triple.

### "Icon error"
Ensure `src/codrag/dashboard/src-tauri/icons/` is populated. If missing, run:
```bash
npx tauri icon path/to/icon.png
```

### "Signing failed"
On macOS, DMG creation requires signing identities. If you don't have them, the `.app` bundle is still valid for local testing but cannot be distributed cleanly.
