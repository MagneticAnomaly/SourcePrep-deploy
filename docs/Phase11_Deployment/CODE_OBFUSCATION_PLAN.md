# Prep Code Obfuscation & Protection Plan

**Status**: Planned for Phase 11 (Deployment)  
**Purpose**: Protect the proprietary Python backend (`prep-daemon`) from reverse engineering by compiling it to a native C binary, replacing the current PyInstaller approach.

---

## 1. The Vulnerability of PyInstaller

Currently, the Prep sidecar is bundled using **PyInstaller** (configured via `prep-daemon.spec`). 

**Why PyInstaller is insufficient for IP protection:**
PyInstaller does *not* compile or obfuscate code. It simply packages a standard Python interpreter alongside your unencrypted `.pyc` (bytecode) files into a self-extracting archive. 
- Attackers can easily unpack the executable using tools like `pyinstxtractor`.
- The resulting `.pyc` files can be trivially decompiled back into highly readable Python source code using `uncompyle6` or `decompyle3`.

---

## 2. Why Nuitka?

Nuitka is an Ahead-of-Time (AOT) compiler that translates Python code into C, and then compiles it into a native machine code binary using a C compiler (like GCC, Clang, or MSVC).

| Option | Protection Level | Reversibility | Performance |
|--------|------------------|---------------|-------------|
| **PyInstaller** | None (Packaging only) | Trivial (`pyinstxtractor`) | Same as Python |
| **PyArmor** | Good (Encrypted bytecode) | Hard but possible | Slower |
| **Nuitka** | **Excellent (Native Binary)** | **Practically Impossible** | **Faster** |

**Benefits for Prep:**
- Protects core IP (LOD Extraction, Epistemic Enrichment, Orchestrator logic).
- Runs faster, as the Python interpreter overhead is removed for compiled modules.
- Results in a standalone binary that drops right into Tauri's sidecar architecture.

---

## 3. Prep-Specific Build Strategy

Based on the existing `prep-daemon.spec`, we know there are several critical dependencies and hidden imports that Nuitka needs to be aware of:
- `fastapi` & `uvicorn` (Web server)
- `onnxruntime` & `tokenizers` (Local AI models)
- `prep_engine` (Custom Rust engine compiled via PyO3)
- `prep.core.embedder` & `prep.core.compressor`

### Nuitka Build Command (Proposed)

```bash
# Inside the Prep Python virtual environment
python -m nuitka \
    --standalone \
    --onefile \
    --follow-imports \
    --include-package=prep \
    --include-module=prep.core.embedder \
    --include-module=prep.core.compressor \
    --include-module=uvicorn \
    --include-module=fastapi \
    --include-package=prep_engine \
    --nofollow-import-to=onnxruntime \
    --include-data-dir=.venv/lib/python3.11/site-packages/onnxruntime=onnxruntime \
    --nofollow-import-to=tokenizers \
    --include-data-dir=.venv/lib/python3.11/site-packages/tokenizers=tokenizers \
    --output-dir=dist/nuitka \
    --output-filename=prep-daemon \
    --cache-dir=.nuitka-cache \
    src/prep/server.py
```

*Note: Heavy binary packages like `onnxruntime` and `tokenizers` should not be compiled by Nuitka. We use `--nofollow-import-to` and bundle them as raw data directories instead.*

---

## 4. Integration with Tauri (Desktop App)

Tauri expects sidecar binaries to be placed in `src-tauri/bin/` with a specific target triple suffix (e.g., `prep-daemon-aarch64-apple-darwin`).

### Build Flow:
1. Nuitka compiles `server.py` into `dist/nuitka/prep-daemon`.
2. A script renames the binary to match the active Tauri target triple.
3. The binary is copied to `src/prep/dashboard/src-tauri/bin/`.
4. `cargo tauri build` packages the UI and embeds the Nuitka-compiled sidecar.

---

## 5. Potential Challenges & Mitigations

### Challenge 1: The Rust Engine (`prep_engine`)
Nuitka must properly bundle the PyO3-compiled `.so` or `.dylib` files for `prep_engine`. If Nuitka fails to trace the Rust extension, we will need to explicitly include the shared library via `--include-data-file`.

### Challenge 2: Build Times
A full Nuitka build can take hours for large dependency trees.
**Mitigation:** 
- Keep the `.nuitka-cache` directory intact between local builds and CI/CD runs.
- Use GitHub Actions cache for `.nuitka-cache`.

### Challenge 3: File System Paths
Nuitka handles `__file__` differently than interpreted Python or PyInstaller. Any code in Prep relying on `__file__` to find adjacent data (like default configs, prompts, or DB schemas) must use the standard resource handling (e.g., `pkgutil` or Nuitka's compiled path conventions).

### Challenge 4: Code Signing (macOS & Windows)
Since Nuitka produces a completely new executable, it must be signed and notarized just like the Tauri wrapper. 
**Mitigation:** Ensure the CI pipeline signs the `prep-daemon` binary *before* Tauri bundles it.

---

## 6. Implementation Timeline

| Step | Task | Complexity |
|------|------|------------|
| **1. Local Proof of Concept** | Run Nuitka locally on macOS, fix missing imports. Verify the API boots up. | High |
| **2. Engine Integration** | Ensure `prep_engine` loads successfully in the compiled binary. | Medium |
| **3. Tauri Wiring** | Hook Nuitka output into the `src-tauri/bin/` target. Verify Tauri can spawn it. | Low |
| **4. CI/CD Migration** | Replace PyInstaller step in GitHub Actions (`.github/workflows/release.yml`) with Nuitka. | Medium |
| **5. Cross-Platform Testing** | Verify Windows (.exe) and Linux builds compile and run successfully. | High |

---

*Authored: March 2026*
