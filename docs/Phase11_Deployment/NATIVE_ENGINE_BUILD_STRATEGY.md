# Native Engine Build Strategy

## Purpose
Define how `codrag_engine` (the Rust/PyO3 native extension) is built, tested, and distributed across all supported platforms. This is a **gating dependency** — without the native engine, users fall back to the Python-only analyzer which only supports `.py` files and produces zero edges for all other languages.

## Decision: No Mac Intel release
CoDRAG will **not** ship a macOS x86_64 (Intel) build. All Mac users must be on Apple Silicon (M1+). Rationale:
- Apple stopped selling Intel Macs in 2022; the installed base is shrinking rapidly.
- Tree-sitter + PyO3 + Rust compile cleanly for `aarch64-apple-darwin`.
- Eliminates one build target and halves macOS CI time.

## Target matrix

| Platform              | Rust target triple           | Python versions | Ship? |
|-----------------------|------------------------------|-----------------|-------|
| macOS Apple Silicon   | `aarch64-apple-darwin`       | 3.11, 3.12, 3.13 | **Yes** |
| macOS Intel           | `x86_64-apple-darwin`        | —               | **No** |
| Windows x86_64        | `x86_64-pc-windows-msvc`    | 3.11, 3.12, 3.13 | **Yes** |
| Linux x86_64 (glibc)  | `x86_64-unknown-linux-gnu`   | 3.11, 3.12, 3.13 | **Yes** |
| Linux ARM64 (glibc)   | `aarch64-unknown-linux-gnu`  | 3.11, 3.12, 3.13 | **Yes** |
| Linux musl (Alpine)   | `x86_64-unknown-linux-musl`  | 3.11, 3.12, 3.13 | Later  |

### Python version policy
- **Minimum**: 3.11 (matches our `pyproject.toml` runtime requirement).
- **Maximum**: latest stable (currently 3.13).
- Each release produces wheels for 3.11, 3.12, and 3.13 per platform.

## Build toolchain

### Local development
```bash
# Prerequisites
rustup default stable            # Rust 1.75+
pip install maturin               # in your venv

# Build for current platform
maturin build --release --interpreter python

# Build + install in one step (dev)
maturin develop --release
```

### CI builds (GitHub Actions)
The standard approach for Python native extensions is **cibuildwheel** or **maturin's own GitHub Action**. We use maturin's action because it's purpose-built for Rust+PyO3.

**Recommended workflow**: `.github/workflows/engine-wheels.yml`

```yaml
name: Build Engine Wheels
on:
  push:
    tags: ['engine-v*']
  workflow_dispatch:

jobs:
  build:
    strategy:
      matrix:
        include:
          # ── macOS Apple Silicon ──────────────────────
          - os: macos-14          # M1 runner
            target: aarch64-apple-darwin
            label: macos-arm64

          # ── Windows x86_64 ──────────────────────────
          - os: windows-latest
            target: x86_64-pc-windows-msvc
            label: windows-x64

          # ── Linux x86_64 ───────────────────────────
          - os: ubuntu-latest
            target: x86_64-unknown-linux-gnu
            label: linux-x64

          # ── Linux ARM64 (cross-compile) ─────────────
          - os: ubuntu-latest
            target: aarch64-unknown-linux-gnu
            label: linux-arm64

    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: |
            3.11
            3.12
            3.13

      - name: Build wheels
        uses: PyO3/maturin-action@v1
        with:
          working-directory: engine
          target: ${{ matrix.target }}
          args: >-
            --release
            --interpreter python3.11 python3.12 python3.13
          manylinux: auto

      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.label }}
          path: engine/target/wheels/*.whl

  publish:
    needs: build
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/')
    steps:
      - uses: actions/download-artifact@v4
        with:
          pattern: wheels-*
          merge-multiple: true
          path: dist

      - name: Publish to PyPI
        uses: PyO3/maturin-action@v1
        with:
          command: upload
          args: --non-interactive dist/*.whl
        env:
          MATURIN_PYPI_TOKEN: ${{ secrets.PYPI_TOKEN }}
```

### Key CI details

- **macOS ARM**: GitHub's `macos-14` runners are M1-based (Apple Silicon native). No Rosetta needed.
- **Linux ARM64**: Cross-compiled on x86_64 Ubuntu using maturin's built-in `zig` linker or the `aarch64-unknown-linux-gnu` toolchain. The `manylinux: auto` flag handles this.
- **Windows**: Straightforward MSVC build on `windows-latest`.
- **Manylinux**: Linux wheels are automatically tagged `manylinux_2_17` (compatible with most distros from ~2018+).

## Distribution channels

### 1. PyPI (`pip install codrag-engine`)
Primary distribution for the native wheel. Users who install CoDRAG via `pip install codrag` can pull the engine as an optional dependency:
```toml
[project.optional-dependencies]
engine = ["codrag-engine>=0.1.0"]
```

### 2. Bundled in Tauri app
The Tauri desktop app bundles a frozen Python environment (via PyInstaller or similar). The correct platform wheel is pre-installed into that frozen env at build time. The CI matrix above produces the exact wheels needed.

### 3. Bundled in VS Code extension
The VS Code extension sidecar bundles the same frozen Python env. Platform detection uses VS Code's `process.platform` + `process.arch`.

## Fallback behavior
When `codrag_engine` is not installed:
- `src/codrag/core/__init__.py` detects absence and sets `_ENGINE = "python"`.
- `TraceBuilder` uses `PythonAnalyzer` (Python-only, no edges for non-Python files).
- The dashboard shows **"Python (limited)"** badge and a degraded-graph warning.
- This is acceptable for pure-Python projects but not for the general case.

## Local dev: fixing the Rosetta venv issue
The current dev venv was created with an x86_64 Python binary (running under Rosetta on Apple Silicon). This works but produces suboptimal native code and requires cross-compilation for the engine wheel.

**Fix**: Recreate the venv with a native ARM Python:
```bash
# Install ARM-native Python via Homebrew or python.org universal installer
brew install python@3.11   # Homebrew on ARM installs ARM binaries

# Recreate venv
rm -rf .venv
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Build native ARM wheel
maturin develop --release
```

After this, `file .venv/bin/python` should report `Mach-O 64-bit executable arm64`.

## Wheel naming conventions
Maturin produces standard PEP 427 wheel filenames:
```
codrag_engine-{version}-cp{pyver}-cp{pyver}-{platform}.whl
```

Examples:
- `codrag_engine-0.1.0-cp311-cp311-macosx_11_0_arm64.whl`
- `codrag_engine-0.1.0-cp312-cp312-win_amd64.whl`
- `codrag_engine-0.1.0-cp311-cp311-manylinux_2_17_x86_64.whl`
- `codrag_engine-0.1.0-cp311-cp311-manylinux_2_17_aarch64.whl`

## Testing strategy
- CI runs `cargo test --workspace` (41 Rust tests) on each platform before wheel build.
- CI runs `pytest tests/` with the built wheel installed on each platform.
- A smoke test imports `codrag_engine` and calls `version()`, `build_trace()`, `load_trace()`.

## Cost and timing
- GitHub Actions M1 runners: ~$0.16/min (3x Linux cost). Budget ~2min per wheel build.
- Full matrix (4 targets × 3 Python versions = 12 wheels): ~8min wall-clock with parallelism.
- Trigger on `engine-v*` tags only — not every push.
