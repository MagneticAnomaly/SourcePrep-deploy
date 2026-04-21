# Auto-Update Strategy

## TL;DR

**Yes — Tauri has first-class auto-update support.** The built-in updater (v1) / updater plugin (v2) gives us the exact Windsurf-style UX: check for updates → show banner → download → restart updated. The Python sidecar is bundled inside the app, so it updates automatically with the shell — no separate sidecar update mechanism needed.

---

## How Tauri's Updater Works

### Architecture Overview

```
┌─────────────────────────────────┐
│  Prep Desktop App (running)   │
│                                 │
│  1. Poll update endpoint        │──────► Update Server
│  2. Compare versions (semver)   │◄────── (200 + JSON or 204 No Content)
│  3. Download signed bundle      │
│  4. Verify Ed25519 signature    │
│  5. Install (replace app)       │
│  6. Restart                     │
└─────────────────────────────────┘
```

### What Gets Updated

The updater replaces the **entire app bundle**:

| Platform | Update artifact | Contents |
|----------|----------------|----------|
| macOS | `Prep.app.tar.gz` | Tauri shell + frontend assets + sidecar binary |
| Windows | `Prep-setup.exe` (NSIS) | Installer re-runs silently, replaces everything |
| Linux | `Prep.AppImage` | Single file replacement |

**Critical insight:** The Python sidecar (`prep-daemon-<target-triple>`) lives inside the app bundle at `Prep.app/Contents/Resources/binaries/`. When the updater replaces the `.app`, the sidecar is replaced too. **No separate sidecar update mechanism is needed.**

### Signature Security

Tauri **mandates** Ed25519 signing for all updates. This cannot be disabled.

- **Private key** → Signs build artifacts during CI. Must be kept secret (GitHub Secrets / vault).
- **Public key** → Embedded in `tauri.conf.json`. App uses it to verify downloads before installing.
- Generate keypair: `npx tauri signer generate -w ~/.tauri/prep.key`

If the private key is lost, existing installs can never be updated via the updater — they'd need a fresh download. **Back up the private key securely.**

---

## Our Architecture Decision: Tauri v1 vs v2

### Current state

We are on **Tauri v1** (`tauri = "1"` in Cargo.toml). Tauri v1 has a built-in updater (no plugin needed), configured in `tauri.conf.json` under `tauri.updater`.

### Recommendation: Implement on v1 now, migrate to v2 later

| Aspect | Tauri v1 (current) | Tauri v2 |
|--------|-------------------|----------|
| Updater | Built-in, `tauri.updater` config | Plugin: `tauri-plugin-updater` |
| Signing | Ed25519, same mechanism | Ed25519, same mechanism |
| JS API | `@tauri-apps/api/updater` | `@tauri-apps/plugin-updater` |
| Artifacts | `.tar.gz` wrappers on all platforms | `.tar.gz` on macOS/Linux, native on Windows |
| UX control | Built-in dialog or custom dialog | Full programmatic control (recommended) |
| Migration | — | `createUpdaterArtifacts: "v1Compatible"` bridges the gap |

**Decision:** Build the updater on v1 now. When we migrate to Tauri v2 (separate sprint), the updater plugin is a near drop-in replacement. Tauri v2 even has a `v1Compatible` artifact mode for seamless transition.

---

## Update Server Strategy

### Option A: Static JSON on GitHub Releases (Recommended for MVP)

```
GitHub Release "app-v0.2.0"
├── Prep_0.2.0_aarch64.app.tar.gz        (macOS ARM update bundle)
├── Prep_0.2.0_aarch64.app.tar.gz.sig    (signature)
├── Prep_0.2.0_x64-setup.nsis.zip        (Windows update bundle)
├── Prep_0.2.0_x64-setup.nsis.zip.sig    (signature)
├── Prep_0.2.0_amd64.AppImage.tar.gz     (Linux update bundle)
├── Prep_0.2.0_amd64.AppImage.tar.gz.sig (signature)
└── latest.json                             (version manifest)
```

`latest.json` example:
```json
{
  "version": "0.2.0",
  "notes": "Bug fixes and performance improvements",
  "pub_date": "2026-02-18T20:00:00Z",
  "platforms": {
    "darwin-aarch64": {
      "signature": "<base64 sig>",
      "url": "https://github.com/MagneticAnomaly/Prep-MCP/releases/download/app-v0.2.0/Prep_0.2.0_aarch64.app.tar.gz"
    },
    "windows-x86_64": {
      "signature": "<base64 sig>",
      "url": "https://github.com/MagneticAnomaly/Prep-MCP/releases/download/app-v0.2.0/Prep_0.2.0_x64-setup.nsis.zip"
    },
    "linux-x86_64": {
      "signature": "<base64 sig>",
      "url": "https://github.com/MagneticAnomaly/Prep-MCP/releases/download/app-v0.2.0/Prep_0.2.0_amd64.AppImage.tar.gz"
    }
  }
}
```

**Why GitHub Releases:**
- Free, reliable CDN for open-source and private repos
- `tauri-action` GitHub Action auto-generates `latest.json` + uploads artifacts
- No infrastructure to maintain
- Works with private repos (use a separate public releases repo if needed)

### Option B: Dynamic Update Server (Future — when we need channels)

A simple API endpoint that returns the same JSON format but can:
- Serve different versions per release channel (stable / beta / nightly)
- Gate updates by license tier (e.g., early access for Pro users)
- Implement gradual rollouts (canary %)
- Collect anonymous update telemetry (opt-in)

Could be a Cloudflare Worker, Vercel Edge Function, or a route on `api.runprep.io`.

**Endpoint contract:**
```
GET https://releases.runprep.io/{{target}}/{{arch}}/{{current_version}}
  → 200 + JSON (update available)
  → 204 (no update)
```

### Option C: CrabNebula Cloud (Tauri's official partner)

Managed update server with dashboard. Potentially useful for enterprise distribution. Evaluate when we have paying customers.

### Phased approach

| Phase | Server | Trigger |
|-------|--------|---------|
| MVP | GitHub Releases static JSON | Good enough for early adopters |
| Post-launch | Dynamic server on `releases.runprep.io` | When we need channels or license-gated updates |
| Enterprise | Self-hosted / CrabNebula | When enterprise customers need air-gapped update mirrors |

---

## UX Design: "Restart to Update"

### User Flow

```
App running normally
        │
        ▼
   ┌─────────────┐    (background, every 30 min)
   │ Check for   │───── 204 No Content ────► (nothing happens)
   │ updates     │
   └──────┬──────┘
          │ 200 + new version
          ▼
   ┌─────────────────────────────────────────────────┐
   │  Subtle banner (top of window, dismissible):    │
   │                                                 │
   │  🔄 Prep v0.2.0 is available.                │
   │     [View Changes]  [Update & Restart]  [Later] │
   │                                                 │
   └─────────────────────────────────────────────────┘
          │
          │ User clicks "Update & Restart"
          ▼
   ┌─────────────────────────────────────────────────┐
   │  Download progress overlay:                     │
   │                                                 │
   │  Downloading update... 45%                      │
   │  ████████████░░░░░░░░░░░░  12.3 MB / 27.1 MB   │
   │                                                 │
   └─────────────────────────────────────────────────┘
          │
          │ Download + verify complete
          ▼
   ┌─────────────────────────────────────────────────┐
   │  "Update ready. Restarting..."                  │
   │  (auto-restart after 2s, or immediate on click) │
   └─────────────────────────────────────────────────┘
          │
          ▼
   App restarts with new version
```

### Key UX principles

1. **Never interrupt work.** The banner is dismissible. "Later" means later — don't nag.
2. **Show release notes.** "View Changes" opens a modal or links to the release page.
3. **Progress feedback.** Download progress with bytes and percentage.
4. **Graceful sidecar shutdown.** Before restart, the app must cleanly kill the Python daemon (we already handle this in `RunEvent::Exit`).
5. **Post-update confirmation.** After restart, show a brief "Updated to v0.2.0" toast.
6. **Offline tolerance.** If the update check fails (no internet), silently retry next cycle. Never block the app.

### Enterprise override

Enterprise deployments may disable auto-update checks entirely:
- Config flag: `updates.enabled: false` (or `PREP_DISABLE_UPDATES=1` env var)
- IT manages updates via MDM / internal distribution
- The "check for updates" menu item is hidden when disabled

---

## Sidecar Update Considerations

### Why it "just works"

The sidecar binary is at a fixed relative path inside the app bundle:
- macOS: `Prep.app/Contents/Resources/binaries/prep-daemon-aarch64-apple-darwin`
- Windows: `Prep/binaries/prep-daemon-x86_64-pc-windows-msvc.exe`
- Linux: `Prep/binaries/prep-daemon-x86_64-unknown-linux-gnu`

When the updater replaces the app bundle, the sidecar binary inside it is replaced too.

### Data persistence across updates

The updater replaces the **application binary**, not user data. These survive updates:
- `prep_data/` directory (registry, settings, indexes) — stored in OS data dir, not inside the app bundle
- Project configurations
- License keys
- User preferences

### Sidecar version compatibility

**Risk:** A new sidecar version might change API contracts, requiring frontend changes. Since both are updated atomically (same bundle), this is safe — the new frontend always ships with its matching sidecar.

**Risk:** A running sidecar from the old version might still be alive during the update. **Mitigation:** Our existing `RunEvent::Exit` handler kills the sidecar before the app exits for update installation. On restart, the new sidecar binary is launched.

---

## CI/CD Pipeline

### GitHub Actions Workflow (MVP)

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'app-v*'

jobs:
  build-and-release:
    permissions:
      contents: write
    strategy:
      fail-fast: false
      matrix:
        include:
          - platform: macos-latest
            args: '--target aarch64-apple-darwin'
          - platform: windows-latest
            args: ''
          # - platform: ubuntu-22.04    # when we support Linux
          #   args: ''

    runs-on: ${{ matrix.platform }}
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Rust stable
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.platform == 'macos-latest' && 'aarch64-apple-darwin' || '' }}

      - name: Rust cache
        uses: swatinem/rust-cache@v2
        with:
          workspaces: 'src/prep/dashboard/src-tauri -> target'

      # Build Python sidecar
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Build sidecar
        run: bash scripts/build_sidecar.sh
        env:
          PYINSTALLER_DIST: src/prep/dashboard/src-tauri/binaries

      # Install frontend deps
      - name: Install dependencies
        run: npm ci

      # Build + release
      - uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
          TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}
          # macOS signing (when ready)
          # APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}
          # APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}
          # APPLE_SIGNING_IDENTITY: ${{ secrets.APPLE_SIGNING_IDENTITY }}
          # APPLE_ID: ${{ secrets.APPLE_ID }}
          # APPLE_PASSWORD: ${{ secrets.APPLE_PASSWORD }}
          # APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
        with:
          tagName: app-v__VERSION__
          releaseName: 'Prep v__VERSION__'
          releaseBody: 'See the assets to download and install.'
          releaseDraft: true
          prerelease: false
          projectPath: src/prep/dashboard
          args: ${{ matrix.args }}
```

### Release flow

1. Bump version in `package.json`, `Cargo.toml`, `tauri.conf.json` (keep in sync)
2. `git tag app-v0.2.0 && git push --tags`
3. CI builds all platforms, signs artifacts, creates draft GitHub Release with `latest.json`
4. Review draft release, edit release notes, publish
5. All running Prep instances pick up the update on next check cycle

---

## Implementation Plan

### Phase 1: Foundation (MVP)

| ID | Task | Effort |
|----|------|--------|
| AU-1 | Generate Ed25519 signing keypair, store private key in GitHub Secrets | 15 min |
| AU-2 | Enable updater in `tauri.conf.json` (pubkey, endpoint pointing to GitHub Releases) | 15 min |
| AU-3 | Add `tauri-plugin-process` or enable `process-relaunch` feature for `app.restart()` | 15 min |
| AU-4 | Implement Rust-side update check on app startup + periodic timer (30 min) | 1 hr |
| AU-5 | Create `UpdateBanner.tsx` React component (banner + progress + restart) | 2 hr |
| AU-6 | Wire frontend to Rust via Tauri commands (`check_update`, `install_update`) | 1 hr |
| AU-7 | Create GitHub Actions release workflow with sidecar build + `tauri-action` | 2 hr |
| AU-8 | End-to-end test: build v0.1.0, release v0.2.0, verify in-app update | 1 hr |

**Total estimate: ~8 hours**

### Phase 2: Polish

| ID | Task |
|----|------|
| AU-9 | "What's New" modal after update (parse release notes from `latest.json`) |
| AU-10 | Settings toggle: "Check for updates automatically" (default: on) |
| AU-11 | Manual "Check for Updates" menu item |
| AU-12 | macOS notarization in CI (requires Apple Developer account) |
| AU-13 | Windows code signing in CI (requires EV certificate or Azure Trusted Signing) |

### Phase 3: Advanced

| ID | Task |
|----|------|
| AU-14 | Dynamic update server on `releases.runprep.io` |
| AU-15 | Release channels (stable / beta) with user opt-in |
| AU-16 | License-gated early access (Pro users get beta channel) |
| AU-17 | Enterprise: disable update checks via config / env var |
| AU-18 | Rollback support (allow downgrade via `version_comparator` override) |

---

## Configuration Changes Required

### `tauri.conf.json` (v1 format)

```json
{
  "tauri": {
    "updater": {
      "active": true,
      "dialog": false,
      "pubkey": "<CONTENTS OF prep.key.pub>",
      "endpoints": [
        "https://github.com/MagneticAnomaly/Prep-MCP/releases/latest/download/latest.json"
      ]
    }
  }
}
```

- `active: true` — enables the updater
- `dialog: false` — we handle the UX ourselves (custom banner, not Tauri's built-in dialog)
- `pubkey` — Ed25519 public key for signature verification
- `endpoints` — where to check for updates (GitHub Releases static JSON)

### Environment variables for CI builds

```bash
TAURI_SIGNING_PRIVATE_KEY="<private key content or path>"
TAURI_SIGNING_PRIVATE_KEY_PASSWORD="<optional password>"
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Private signing key lost | Low | **Critical** — can never push updates to existing installs | Store in vault + offline backup. Document recovery procedure. |
| Update server unreachable | Medium | Low — app works fine, just can't update | Graceful failure, retry on next cycle. Multiple endpoint fallback. |
| Corrupted download | Low | None — Ed25519 signature verification prevents installation | Built into Tauri, no action needed. |
| Update breaks sidecar compat | Low | Medium — app crashes on start | Atomic bundle update ensures frontend + sidecar always match. |
| macOS Gatekeeper blocks unsigned update | High (pre-notarization) | High — users can't update | Prioritize Apple notarization (AU-12). |
| Windows SmartScreen flags update | High (pre-signing) | Medium — scary warning | Prioritize Windows code signing (AU-13). Budget ~$200-500/yr for EV cert or use Azure Trusted Signing. |
| Enterprise blocks outbound GitHub | Medium | Medium — can't receive updates | Enterprise config to disable checks + provide manual update path. |

---

## Open Questions

- **Q1:** Should we use the Tauri v1 built-in updater dialog (quick win) or go straight to custom UI (better UX but more work)?
  - **Recommendation:** Custom UI from the start. The built-in dialog is bare-bones and doesn't show download progress.

- **Q2:** Should the update endpoint point to the main Prep repo or a separate releases repo?
  - If Prep repo is private, we need a public releases repo for the `latest.json` to be accessible.
  - If Prep repo is public, use it directly.

- **Q3:** When should we invest in Apple notarization and Windows code signing?
  - **Recommendation:** Before any public release. Unsigned apps are a dealbreaker for adoption.

- **Q4:** Should we support delta/differential updates?
  - **Not for MVP.** Full bundle replacement is fine. The bundle is ~30-50MB. Differential updates add significant complexity.

---

## References

- [Tauri v1 Updater Guide](https://v1.tauri.app/v1/guides/distribution/updater/)
- [Tauri v2 Updater Plugin](https://v2.tauri.app/plugin/updater/)
- [tauri-action GitHub Action](https://github.com/tauri-apps/tauri-action)
- [Tauri GitHub CI/CD Pipeline](https://v2.tauri.app/distribute/pipelines/github/)
- [CrabNebula Cloud (managed updates)](https://docs.crabnebula.dev/cloud/guides/auto-updates-tauri/)
- [Tauri Signer CLI](https://v2.tauri.app/reference/cli/#signer-generate)
