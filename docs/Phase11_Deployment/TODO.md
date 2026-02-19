# Phase 11 — Deployment TODO

> **Last updated:** 2026-02-18
>
> Organized by major task area, in recommended execution order.
> Each section is sequenced so that upstream blockers are resolved first.

## Links
- Spec: `README.md`
- Revenue & distribution strategy: `../DISTRIBUTION_AND_REVENUE_PLAN.md` (authoritative)
- Opportunities: `opportunities.md`
- Master orchestrator: `../MASTER_TODO.md`
- Tauri packaging: `../Phase08_Tauri_MVP/README.md`
- Decision log: `../DECISIONS.md`

---

## Section 1: Accounts & Credentials (do first — everything else blocks on these)

> 📖 Step-by-step instructions: [`guides/01-accounts-credentials.md`](guides/01-accounts-credentials.md)

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [x] | ACC-1 | Apple Developer Program enrollment (Magnetic Anomaly LLC) | Required for macOS signing + notarization |
| [ ] | ACC-2 | Generate Ed25519 signing keypair for Tauri auto-updater | `npx tauri signer generate -w ~/.tauri/codrag.key` — **back up private key securely** |
| [ ] | ACC-3 | Store updater private key in GitHub Secrets (`TAURI_PRIVATE_KEY`, `TAURI_KEY_PASSWORD`) | |
| [ ] | ACC-4 | Windows code signing certificate (EV recommended for instant SmartScreen trust) | OV cert works but needs reputation buildup |
| [ ] | ACC-5 | Microsoft Partner Center developer account (Magnetic Anomaly LLC) | For Microsoft Store listing (Channel B) |
| [ ] | ACC-6 | Lemon Squeezy account setup + product/tier configuration | See `DISTRIBUTION_AND_REVENUE_PLAN.md` §3 **requires website first** |
| [ ] | ACC-7 | Resend account + verified domain (`codrag.io`) for transactional email | License delivery, bug report notifications, etc. |
| [ ] | ACC-8 | Netlify team setup + connect GitHub repo for website deploys | 4 apps: marketing, docs, support, payments (see Section 7) |
| [ ] | ACC-9 | PyPI account + API token for `codrag-engine` wheel publishing | Store token in GitHub Secrets (`PYPI_TOKEN`) |

---

## Section 2: Python Sidecar Build (upstream of Tauri app)

The desktop app bundles the Python daemon as a sidecar binary (via PyInstaller).
This must work before the Tauri app can be assembled.

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [x] | SID-1 | Recreate dev venv with native ARM Python (not Rosetta x86_64) | `brew install python@3.11` + recreate `.venv` |
| [ ] | SID-2 | PyInstaller spec file (`codrag-daemon.spec`) — verify it produces a working standalone binary | Spec exists at repo root |
| [ ] | SID-3 | Test sidecar binary on macOS: starts daemon, responds to `/health`, processes SSE events | |
| [ ] | SID-4 | Test sidecar binary on Windows: same as above | Needs Windows dev environment or CI |
| [ ] | SID-5 | Sidecar binary includes native embedder deps (onnxruntime, tokenizers, huggingface-hub) | Large — verify bundle size is acceptable |
| [ ] | SID-6 | Sidecar binary naming convention: `codrag-daemon-{target-triple}` per Tauri requirement | e.g., `codrag-daemon-aarch64-apple-darwin` |

---

## Section 3: Rust Engine Wheels (upstream of sidecar + PyPI)

Cross-platform `codrag_engine` native extension wheels.
See `NATIVE_ENGINE_BUILD_STRATEGY.md` for full details.

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | ENG-1 | GitHub Actions workflow: `.github/workflows/engine-wheels.yml` | 4 targets × 3 Python versions = 12 wheels |
| [ ] | ENG-2 | macOS ARM64 wheel builds (GitHub `macos-14` M1 runner) | |
| [ ] | ENG-3 | Windows x64 wheel builds | |
| [ ] | ENG-4 | Linux x64 + ARM64 wheel builds (manylinux) | |
| [ ] | ENG-5 | Publish wheels to PyPI on `engine-v*` tag | Requires ACC-9 |
| [ ] | ENG-6 | Integrate correct platform wheel into sidecar build (SID-2) | Pre-install wheel into frozen Python env |
| [x] | ENG-7 | Document target matrix and no-Intel-Mac decision | Done in `NATIVE_ENGINE_BUILD_STRATEGY.md` |

---

## Section 4: Tauri Desktop App Build & Signing

> 📖 Signing setup instructions: [`guides/04-code-signing.md`](guides/04-code-signing.md)

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | TAU-1 | Verify Tauri v1 builds locally (macOS `.dmg`) | |
| [ ] | TAU-2 | Configure `externalBin` in `tauri.conf.json` for sidecar | Points to `codrag-daemon-$TARGET_TRIPLE` |
| [ ] | TAU-3 | macOS code signing in CI (Developer ID Application cert) | Requires ACC-1 |
| [ ] | TAU-4 | macOS notarization in CI (Apple ID + app-specific password or App Store Connect API) | Requires ACC-1 |
| [ ] | TAU-5 | Windows code signing in CI (EV cert via Azure Key Vault or custom sign command) | Requires ACC-4 |
| [ ] | TAU-6 | GitHub Actions release workflow: `tauri-action` + sidecar build + signing | Trigger on `app-v*` tags |
| [ ] | TAU-7 | Release artifacts: `.dmg` (macOS), `.msi`/`.exe` (Windows) + checksums | Upload to GitHub Releases |
| [ ] | TAU-8 | Smoke test: fresh install → add project → build index → search works | Per-platform |

---

## Section 5: Auto-Update System

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | UPD-1 | Embed updater public key in `tauri.conf.json` | Requires ACC-2 |
| [ ] | UPD-2 | Configure updater endpoint → GitHub Releases `latest.json` | Static JSON, see `AUTO_UPDATE_STRATEGY.md` |
| [ ] | UPD-3 | `tauri-action` generates `latest.json` + signed artifacts per release | Part of TAU-6 |
| [ ] | UPD-4 | Rust-side update check: startup + periodic (30 min) | |
| [ ] | UPD-5 | `UpdateBanner.tsx` frontend component (banner + progress bar + restart button) | |
| [ ] | UPD-6 | Wire frontend to Tauri commands (`check_update`, `install_update`) | |
| [ ] | UPD-7 | E2E test: v0.1.0 → v0.2.0 in-app update | |
| [ ] | UPD-8 | "What's New" modal after update (reads release notes from `latest.json`) | Nice-to-have for MVP |
| [ ] | UPD-9 | Settings toggle: "Check for updates automatically" | Default: on |
| [ ] | UPD-10 | Enterprise config: `CODRAG_DISABLE_UPDATES` env var | |

---

## Section 6: Licensing & Feature Gating

Feature gating framework already exists (`src/codrag/core/feature_gate.py`).
This section covers the remaining licensing work.

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | LIC-1 | Ed25519 license signature verification (validate signed key payload) | See `LICENSING_IMPLEMENTATION.md` |
| [x] | LIC-2 | License file loading: `~/.codrag/license.json` or `CODRAG_TIER` env var | Already implemented in feature_gate.py |
| [ ] | LIC-3 | Lemon Squeezy webhook → license key generation service | Cloud function that signs + emails key |
| [ ] | LIC-4 | License activation UI in Tauri (paste key → validate → save) | |
| [ ] | LIC-5 | Frontend "Upgrade to Pro" prompts for FREE tier gated features | |
| [ ] | LIC-6 | License status view in Settings drawer | Show tier, expiry, features |
| [ ] | LIC-7 | `updates_until` enforcement: block auto-update if update entitlement expired | |
| [ ] | LIC-8 | Define "what CoDRAG contacts" statement (offline-first guarantee) | For privacy page + enterprise confidence |

---

## Section 7: Websites Deployment (Netlify)

> 📖 Step-by-step instructions: [`guides/07-cloudflare-netlify.md`](guides/07-cloudflare-netlify.md)

All four Next.js apps deployed on **Netlify** (free tier: 100GB bandwidth, 300 build min/mo,
commercial use allowed). API routes work natively — no refactoring needed.

**Decision rationale:** Vercel Hobby tier prohibits commercial use ($20/mo for Pro).
Cloudflare Pages has edge-runtime limitations for Next.js API routes. Netlify free tier
allows commercial use, supports Next.js API routes natively, and is the simplest single-platform option.

> **GoDaddy's role after this section:** Just paying annually to keep your domain names
> registered. You change the nameservers once (step CF-3 below) and GoDaddy is otherwise
> hands-off forever. All DNS management moves to Cloudflare.

### 7a. Cloudflare DNS setup

Cloudflare sits between GoDaddy (domain registrar) and Netlify (host). It handles DNS,
free DDoS protection, edge caching, and redirect rules. Free plan is sufficient.

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | CF-1 | Create Cloudflare account at cloudflare.com (free plan) | Use Magnetic Anomaly LLC email |
| [ ] | CF-2 | Add site `codrag.io` to Cloudflare → Cloudflare scans existing DNS records | It will auto-import whatever GoDaddy has |
| [ ] | CF-3 | **Change nameservers in GoDaddy**: replace GoDaddy's nameservers with the two Cloudflare nameservers shown (e.g. `ava.ns.cloudflare.com`) | GoDaddy: Domains → DNS → Nameservers → Enter Custom. **This is the one-time hand-off.** |
| [ ] | CF-4 | Wait for nameserver propagation (~10 min – 24 hrs, usually fast) | Cloudflare dashboard shows "Active" when done |
| [ ] | CF-5 | Add site `codrag.ai` to Cloudflare the same way (legacy redirect domain) | |
| [ ] | CF-6 | In Cloudflare for `codrag.ai`: add a redirect rule → all traffic → 301 to `https://codrag.io` | Rules → Redirect Rules → "codrag.ai/*" → `https://codrag.io/$1` |
| [ ] | CF-7 | Add DNS records in Cloudflare for `codrag.io` (after Netlify sites exist — see WEB-M4, WEB-D4, WEB-S3, WEB-P3): | Fill in Netlify subdomain URLs once sites are created |
| | | `CNAME @ → <marketing-site>.netlify.app` (Proxied) | Root domain → marketing |
| | | `CNAME www → codrag.io` (Proxied) | www redirect |
| | | `CNAME docs → <docs-site>.netlify.app` (Proxied) | |
| | | `CNAME support → <support-site>.netlify.app` (Proxied) | |
| | | `CNAME payments → <payments-site>.netlify.app` (Proxied) | |
| [ ] | CF-8 | Set SSL/TLS mode in Cloudflare to **Full (Strict)** | SSL → Overview → Full (strict). Netlify provides the cert on their end. |
| [ ] | CF-9 | Add redirect rule: `www.codrag.io/*` → `https://codrag.io/$1` (301) | Rules → Redirect Rules |

### 7b. Netlify account & site setup

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | WEB-1 | Create Netlify account at netlify.com (free Starter plan) | Use Magnetic Anomaly LLC email |
| [ ] | WEB-2 | Connect GitHub: Netlify → Team Settings → Git → Connect `EricBintner/CoDRAG` | Authorize GitHub OAuth |
| [ ] | WEB-3 | Create 4 separate Netlify sites (one per app) — settings per site are in 7c below | "Add new site → Import from Git" for each |
| [ ] | WEB-4 | Enable Deploy Previews (on by default) — auto-preview URL on every PR | Useful for reviewing `packages/ui` changes across all sites |
| [ ] | WEB-5 | Remove `vercel.json` from each app (no longer needed) | `websites/apps/*/vercel.json` |

### 7c. Per-site deployment

Each site gets its own Netlify project with base directory + build command.

#### Marketing (`codrag.io`) — static, no API routes needed

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | WEB-M1 | Netlify site: base dir `websites/apps/marketing` | |
| [ ] | WEB-M2 | Build command: `cd ../../.. && npx turbo run build --filter=@codrag/marketing` | Or configure via `netlify.toml` |
| [ ] | WEB-M3 | Consider `output: 'export'` for pure static (optional — Netlify handles SSR too) | RSS route has hardcoded data, could be build-time |
| [ ] | WEB-M4 | Custom domain: `codrag.io` | |
| [ ] | WEB-M5 | Env vars: `NEXT_PUBLIC_SITE_URL=https://codrag.io` | |

#### Docs (`docs.codrag.io`) — static, zero API routes

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | WEB-D1 | Netlify site: base dir `websites/apps/docs` | |
| [ ] | WEB-D2 | Build command: `cd ../../.. && npx turbo run build --filter=@codrag/docs` | |
| [ ] | WEB-D3 | Consider `output: 'export'` for pure static | No server-side features needed |
| [ ] | WEB-D4 | Custom domain: `docs.codrag.io` | |
| [ ] | WEB-D5 | Env vars: `NEXT_PUBLIC_SITE_URL=https://docs.codrag.io` | |

#### Support (`support.codrag.io`) — has API routes (server-side)

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | WEB-S1 | Netlify site: base dir `websites/apps/support` | |
| [ ] | WEB-S2 | Build command: `cd ../../.. && npx turbo run build --filter=@codrag/support` | |
| [ ] | WEB-S3 | Custom domain: `support.codrag.io` | |
| [ ] | WEB-S4 | Env vars: `GITHUB_TOKEN` (read-only PAT for Discussions) | |
| [ ] | WEB-S5 | Env vars: `RESEND_API_KEY`, `BUG_REPORT_EMAIL` | For `/api/bug-report` route |
| [ ] | WEB-S6 | Verify API route `/api/bug-report` works on Netlify (POST + CORS) | |
| [x] | WEB-S7 | Fix support app styling (missing PostCSS config) | Added `postcss.config.js` |

#### Payments (`payments.codrag.io`) — has API routes (server-side)

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | WEB-P1 | Netlify site: base dir `websites/apps/payments` | |
| [ ] | WEB-P2 | Build command: `cd ../../.. && npx turbo run build --filter=@codrag/payments` | |
| [ ] | WEB-P3 | Custom domain: `payments.codrag.io` | |
| [ ] | WEB-P4 | Env vars: `NEXT_PUBLIC_CODRAG_CHECKOUT_URL`, `LEMONSQUEEZY_API_KEY`, `LEMONSQUEEZY_STORE_ID` | |
| [ ] | WEB-P5 | Verify API route `/api/recover` works on Netlify | |
| [ ] | WEB-P6 | Add Lemon Squeezy webhook endpoint when ready (LIC-3) | |

### 7d. Cross-site tasks

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [x] | WEB-X1 | Verify CI pipeline: `websites-ci.yml` runs lint + build on PR | Already exists |
| [ ] | WEB-X2 | Add Plausible or Umami analytics snippet to all sites | Currently TODO in layout.tsx |
| [ ] | WEB-X3 | Custom 404 pages for all sites | |
| [ ] | WEB-X4 | Add `netlify.toml` to each app (build settings, redirects, headers) | Optional — Netlify UI config is sufficient for MVP |

---

## Section 8: VS Code Extension

> 📖 Marketplace publishing instructions: [`guides/08-vscode-marketplace.md`](guides/08-vscode-marketplace.md)

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | VSC-1 | Extension sidecar: bundle Python daemon binary (same as SID-2 output) | Platform detection via `process.platform + process.arch` |
| [ ] | VSC-2 | Integrate correct engine wheel into extension sidecar | Same as ENG-6 but for VS Code packaging |
| [ ] | VSC-3 | `vsce package` produces working `.vsix` | |
| [ ] | VSC-4 | Publish to VS Code Marketplace | Requires Azure DevOps PAT |
| [ ] | VSC-5 | Extension auto-update (handled by VS Code marketplace natively) | No custom work needed |

---

## Section 9: Upgrade Safety & Data Migration

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | UPG-1 | `format_version` in index/trace manifests — detect incompatibility on load | Surface "Full Rebuild" as single remediation |
| [ ] | UPG-2 | Define what persists across upgrades: registry, config, index, trace data | Document in user-facing docs |
| [ ] | UPG-3 | Define what may break: format changes, new required fields | |
| [ ] | UPG-4 | Install/uninstall test per OS (clean install + upgrade-in-place) | |
| [ ] | UPG-5 | Air-gapped sanity test: app fully functional without internet | |

---

## Section 10: Microsoft Store Submission (post-launch or alongside)

> 📖 Submission walkthrough: [`guides/10-microsoft-store.md`](guides/10-microsoft-store.md)

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | MST-1 | Register product in Microsoft Partner Center | Requires ACC-5 |
| [ ] | MST-2 | Configure as EXE/MSI app with external licensing declaration | Per MS Store Policy 10.8.1 |
| [ ] | MST-3 | Submit code-signed installer | Requires TAU-5 |
| [ ] | MST-4 | Store listing: screenshots, description, category | |
| [ ] | MST-5 | Test: install from Store → activate license via Lemon Squeezy → features unlock | |

---

## Section 11: Mac App Store (DEFERRED)

**Compliance blocker:** Apple requires IAP for feature unlocks (Guideline 3.1.1).
External license keys are prohibited. This requires a separate payment flow.
See `DISTRIBUTION_AND_REVENUE_PLAN.md` §6 for full analysis.

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | MAS-1 | Decide: pursue Mac App Store or defer indefinitely | Depends on user demand |
| [ ] | MAS-2 | If yes: implement Apple IAP integration | |
| [ ] | MAS-3 | If yes: App Sandbox testing (repo access, sidecar execution) | High risk of rejection |

---

## Section 12: Enterprise Distribution (post-MVP)

| Done | ID | Task | Notes |
|--------|----|------|-------|
| [ ] | ENT-1 | Air-gapped build variant: disable all internet calls (updates, telemetry) | `CODRAG_DISABLE_UPDATES` + `CODRAG_OFFLINE` |
| [ ] | ENT-2 | MDM-friendly license deployment (`~/.codrag/license.key` via config management) | |
| [ ] | ENT-3 | Audit logging (local file or syslog) | |
| [ ] | ENT-4 | Shared team configuration export/import | |
| [ ] | ENT-5 | Document enterprise deployment guide | |

---

## Recommended Execution Order (Critical Path)

```
Accounts & Creds (ACC-1..9)     ← do first, long lead times
         │
         ├─► Rust Engine Wheels (ENG-1..6)
         │         │
         ├─► Python Sidecar Build (SID-1..6)
         │         │
         │         ▼
         ├─► Tauri Desktop App (TAU-1..8)
         │         │
         │         ├─► Auto-Update (UPD-1..10)
         │         └─► Licensing UI (LIC-4..7)
         │
         ├─► Websites Deploy (WEB-1..10)  ← can be parallel
         │
         ├─► VS Code Extension (VSC-1..5)  ← can be parallel
         │
         └─► Microsoft Store (MST-1..5)    ← after desktop app ships
```

## Notes / blockers
- [x] Dev venv is x86_64 (Rosetta) — needs recreation with native ARM Python
- [x] Decided: Mac App Store is NOT a target for MVP (deferred due to IAP compliance blocker)
- [ ] Windows dev environment needed for SID-4 and TAU-5 (or rely entirely on CI)