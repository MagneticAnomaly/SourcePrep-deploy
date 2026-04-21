# Phase 08 Research: Packaging, Ports, and Data Strategy

## P08-R1: Packaging Approach

**Decision:** Use **PyInstaller** for the MVP Python sidecar.

**Rationale:**
1.  **Maturity**: PyInstaller is the industry standard for bundling Python apps. It supports macOS (app bundles), Windows (exe), and Linux (ELF).
2.  **Compatibility**: It handles complex dependencies like `numpy` and `pydantic` well via hooks.
3.  **Speed**: It is faster to set up than PyOxidizer, which requires more Rust-based configuration and has a steeper learning curve.
4.  **Tauri Integration**: The sidecar pattern in Tauri expects a binary executable. PyInstaller produces a single-file executable (`--onefile`) or a directory (`--onedir`) which can be renamed and placed in the Tauri `src-tauri/binaries` folder.

**Implementation Plan:**
- Create `scripts/build_sidecar.sh` (Mac/Linux) and `scripts/build_sidecar.bat` (Windows).
- Use `pyinstaller --name codrag-daemon --onefile src/codrag/server.py`.
- Configure hidden imports for dynamic loading (e.g., `codrag.core.embedder`).
- Sign the binary on macOS before bundling with Tauri.

---

## P08-R2: Port and Binding Strategy

**Decision:**
- **Default Port:** `8400`
- **Host:** `127.0.0.1` (Strict loopback for security, unless overridden by config).
- **Discovery:** Tauri app reads port from `codrag_config.json` or tries default.

**Conflict Resolution Strategy:**
1.  **Check 8400**: On startup, the Tauri app (Rust process) checks if port 8400 is in use.
2.  **Health Check**: If in use, make a `GET http://127.0.0.1:8400/health`.
    - If response is `{"status": "ok", "service": "codrag"}`, assume it is our daemon. **Action:** Connect to it. Do NOT start a new sidecar.
    - If response is anything else or timeout (but port is open), assume conflict. **Action:** Pick a random free port (e.g., port 0 binding) for the sidecar.
3.  **Communication**:
    - If sidecar is started on a random port, the Rust process captures the port from the sidecar's stdout (e.g. `[INFO] Listening on 127.0.0.1:56732`).
    - Pass this URL to the Frontend (WebView) via a Tauri Command `get_daemon_url()`.

**Single Instance:**
- The Tauri app itself should be single-instance (using `tauri-plugin-single-instance`).
- The daemon should effectively be single-instance per user session due to the port lock on 8400.

---

## P08-R3: Data Directory Strategy

**Decision:** Follow OS standards using `platformdirs` (Python) and `directories` (Rust/Tauri) logic.

**Locations:**

| OS | Path | Rationale |
|---|---|---|
| **macOS** | `~/Library/Application Support/CoDRAG/` | Standard macOS app data location. |
| **Windows** | `%APPDATA%\CoDRAG\` | Standard Roaming profile location. |
| **Linux** | `~/.local/share/prep/` | XDG Base Directory specification. |

**Subdirectories:**
- `logs/`: Daemon logs (`daemon.log`).
- `indexes/`: Storage for project indexes (default location if not inside project).
- `config/`: Global `config.json`, `license.json`.

**Migration:**
- Currently, CoDRAG uses `~/.prep` (hardcoded).
- **Action:** Update `codrag.core.config` to use `platformdirs.user_data_dir("CoDRAG", "HumanAI")`.
- **Backward Compatibility:** On startup, check if `~/.prep` exists. If yes, migrate it to the new location or continue using it with a warning (MVP: continue using it or symlink?).
- **MVP Decision:** Switch to standard paths for fresh installs. Legacy dev environments can keep `~/.prep` via env var `CODRAG_DATA_DIR`.

**Signing & Notarization (macOS):**
- Binary must be signed with "Developer ID Application".
- Tauri app bundle must be notarized by Apple.
- Entitlements: `com.apple.security.network.client`, `com.apple.security.network.server`.
- Sidecar binary must be signed *before* being bundled into the `.app`.
