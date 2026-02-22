# CoDRAG Tauri App Security Audit & Recommendations

**Date:** February 21, 2026
**Scope:** Tauri desktop application build process, configuration, and CI/CD pipeline.

This document outlines the findings of a security audit performed on the CoDRAG Tauri application and provides actionable recommendations to align with industry standard security practices.

---

## 1. Content Security Policy (CSP)

**Finding:** The `tauri.conf.json` explicitly sets `"security": { "csp": null }`. 
**Risk Level:** **CRITICAL**
**Analysis:** Without a Content Security Policy, the application is highly vulnerable to Cross-Site Scripting (XSS) attacks. Given that CoDRAG ingests, parses, and displays arbitrary source code, markdown documentation, and AI-generated text, an XSS vulnerability could allow an attacker to execute arbitrary scripts within the WebView context. If an attacker breaches the WebView, they could potentially bridge to the Tauri API.
**Recommendation:** Implement a strict CSP. Since CoDRAG uses Vite/React, it requires specific directives.
*   **Action:** Update `tauri.conf.json`:
    ```json
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://127.0.0.1:8400 ws://127.0.0.1:8400 https://api.lemonsqueezy.com https://github.com; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'"
    }
    ```
    *(Note: adjust endpoints based on exact LemonSqueezy, analytics, and auto-update URL requirements).*

## 2. Tauri API Allowlist & IPC Attack Surface

**Finding:** The allowlist is mostly well-restricted (`all: false`, `shell.all: false`). However, `Cargo.toml` includes the `process-command-api` feature.
**Risk Level:** **MEDIUM**
**Analysis:** The `process-command-api` feature is historically used to allow the frontend to spawn arbitrary commands. According to internal documentation, it is included solely to enable the `relaunch()` function. However, if the frontend allowlist ever mistakenly enables `shell.execute`, it would grant arbitrary command execution.
**Recommendation:** 
*   **Action:** Verify that `tauri.allowlist.shell.execute` remains completely absent or `false` in `tauri.conf.json`.
*   **Action:** Ensure the `http` scope (`["http://127.0.0.1:8400/*"]`) is strictly maintained so the Tauri HTTP client cannot be tricked into hitting arbitrary internal network IPs (SSRF).

## 3. Sidecar Communication Security (Local API Access)

**Finding:** The Tauri frontend communicates with the Python sidecar daemon via `http://127.0.0.1:8400`.
**Risk Level:** **HIGH**
**Analysis:** By binding an unauthenticated API to `127.0.0.1`, **any** application running on the user's computer can make requests to `http://127.0.0.1:8400`. This means malware or a malicious browser script (via DNS rebinding/fetch) could potentially query the user's code index, trigger rebuilds, or extract the local trace graph.
**Recommendation:** Implement a dynamic Shared Secret / Auth Token.
*   **Action:** The Tauri Rust backend should generate a cryptographically secure random token on startup.
*   **Action:** Pass this token to the Python sidecar as a command-line argument or environment variable (e.g., `CODRAG_DAEMON_TOKEN`).
*   **Action:** Expose this token to the frontend via the existing `get_daemon_config` Tauri command.
*   **Action:** The frontend HTTP client (`api/client.ts`) must attach this token as an `Authorization: Bearer <token>` header on all requests.
*   **Action:** The Python FastAPI server must enforce this token on all routes (except perhaps `/health`).

## 4. Supply Chain & CI/CD Hardening

**Finding:** `.github/workflows/release.yml` uses mutable tags (e.g., `@v4`, `@stable`, `@v0`) and uncommented code signing.
**Risk Level:** **MEDIUM**
**Analysis:** Standard supply chain security dictates pinning dependencies and CI actions to immutable SHAs. If a third-party action provider is compromised and an attacker moves the `@v4` tag, malicious code could run in our release pipeline and steal signing keys.
**Recommendation:**
*   **Action:** Pin all GitHub Actions to specific commit SHAs (e.g., `uses: actions/checkout@1d96c772d19495a3b5c517cd2bc0cb401ea0529f # v4.1.1`).
*   **Action:** Enforce `--locked` on cargo commands to guarantee `Cargo.lock` deterministic builds.
*   **Action:** Ensure `npm ci` is used (already implemented, which is excellent).

## 5. Code Signing & Notarization (Release Readiness)

**Finding:** Code signing variables in the CI workflow are commented out.
**Risk Level:** **HIGH (for production UX and Security posture)**
**Analysis:** Without code signing, macOS Gatekeeper and Windows SmartScreen will flag the application as malicious/untrusted, preventing many users from installing it and triggering severe OS warnings.
**Recommendation:**
*   **Action:** For macOS: Obtain an Apple Developer ID Application certificate. Enable the "Hardened Runtime" entitlement (`"macOS": { "entitlements": "entitlements.mac.plist" }`), which is mandatory for Notarization. You will need to allow JIT compilation if the WebView requires it.
*   **Action:** For Windows: Obtain an Authenticode certificate (EV preferred for immediate SmartScreen reputation) and configure the `windows` signing block in the release workflow.
*   **Action:** Uncomment the signing steps in `.github/workflows/release.yml`.

## 6. Frontend Dependency and Output Sanitization

**Finding:** The frontend renders code snippets, markdown, and AI generated content.
**Risk Level:** **MEDIUM**
**Analysis:** React generally escapes strings, preventing XSS. However, if any component uses `dangerouslySetInnerHTML` to render markdown (e.g., the docs or chat outputs), it must be strictly sanitized.
**Recommendation:**
*   **Action:** Audit the `@codrag/ui` library for `dangerouslySetInnerHTML`. If found, ensure a robust sanitization library like `DOMPurify` is applied to the payload *before* rendering.

---
### Summary of Next Steps
1. ~~Configure `csp` in `tauri.conf.json`.~~ (Completed)
2. ~~Implement local IPC Auth Token between Tauri, UI, and Sidecar.~~ (Completed)
3. ~~Pin GitHub Actions to SHAs.~~ (Completed)
4. ~~Prepare Apple and Windows code signing certificates.~~ (Completed CI configuration)
5. ~~Audit React components for raw HTML rendering.~~ (Completed - no `dangerouslySetInnerHTML` found in UI components, only in Plausible analytics script which is safe)
