# Guide: Accounts & Credentials Setup

> **Do this first.** Everything else in the deployment pipeline blocks on these accounts.
> Some (Apple Developer, Windows cert) have long lead times — start them immediately.

---

## ACC-1 — Apple Developer Program

**What:** Enrolls Magnetic Anomaly LLC as an Apple Developer, allowing you to code-sign
and notarize the macOS app. Without this, macOS shows a scary "unverified developer" warning
and Gatekeeper may block the app entirely.

**Cost:** $99/year

**Time:** Usually 24–48 hours, sometimes up to a week for business enrollment.

**Steps:**
1. Go to [developer.apple.com/programs/enroll](https://developer.apple.com/programs/enroll/)
2. Sign in with your Apple ID (create one for Magnetic Anomaly LLC if you don't have one)
3. Choose **"Enroll as an Organization"** (not Individual — you want the LLC name on the cert)
4. You'll need:
   - Your LLC's **D-U-N-S number** (free, request at [dnb.com](https://www.dnb.com/duns-number/lookup.html) — takes a few days if you don't have one)
   - Legal entity name: `Magnetic Anomaly LLC`
   - Your address, phone, website
5. Pay the $99/year fee with a credit card
6. Apple will verify the organization — they may call the phone number on file
7. Once approved, you'll receive an email. Log in to [developer.apple.com](https://developer.apple.com) to confirm access.

**After enrollment:**
- Go to **Certificates, Identifiers & Profiles**
- Create a **Developer ID Application** certificate (for direct distribution, not App Store)
- Download and double-click the `.cer` file to install it in your Keychain
- This cert is what the CI pipeline uses to sign the `.dmg`
- See `guides/04-code-signing.md` for the full cert setup walkthrough

---

## ACC-2 — Generate Ed25519 Auto-Updater Keypair

**What:** A cryptographic keypair used to sign app update bundles. Tauri verifies the
signature before installing any update — this prevents tampered updates from being installed.

**Steps:**
1. Open Terminal
2. Run:
   ```bash
   npx tauri signer generate -w ~/.tauri/codrag.key
   ```
3. You'll be prompted for a password — choose something strong and save it in your password manager
4. This creates two files:
   - `~/.tauri/codrag.key` — **private key** (secret, never commit this)
   - `~/.tauri/codrag.key.pub` — public key (safe to embed in the app)
5. **Back up the private key immediately:**
   - Copy `~/.tauri/codrag.key` to a secure location (encrypted drive, password manager attachment, or 1Password)
   - If you lose this key, you cannot ship updates that users can install — they'd need to reinstall manually

6. Note the public key content (it looks like a base64 string) — you'll embed it in `tauri.conf.json` at step UPD-1

---

## ACC-3 — Store Signing Key in GitHub Secrets

**What:** The CI pipeline needs your private key to sign release artifacts. GitHub Secrets
stores it encrypted, accessible only to your workflows.

**Steps:**
1. Go to [github.com/EricBintner/CoDRAG](https://github.com/EricBintner/CoDRAG)
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add:

   | Secret Name | Value |
   |-------------|-------|
   | `TAURI_PRIVATE_KEY` | Contents of `~/.tauri/codrag.key` (the whole file, including headers) |
   | `TAURI_KEY_PASSWORD` | The password you chose in ACC-2 |

4. Repeat for `TAURI_KEY_PASSWORD`

> These secrets are write-only — you can't read them back after saving, only replace them.

---

## ACC-4 — Windows EV Code Signing Certificate

**What:** Signs the Windows installer (`.msi`/`.exe`) so SmartScreen doesn't show a red
warning. An EV (Extended Validation) cert gives instant SmartScreen trust. An OV cert
works but requires building reputation over time (users will see yellow warnings initially).

**Cost:** ~$200–500/year depending on provider

**Time:** 1–5 business days for verification

**Recommended providers:**
- [DigiCert](https://www.digicert.com/signing/code-signing-certificates) — most reliable, widely used in CI
- [Sectigo](https://sectigo.com/ssl-certificates-tls/code-signing) — cheaper
- [SSL.com](https://www.ssl.com/code-signing/) — good CI support

**Steps:**
1. Purchase an EV Code Signing certificate from one of the providers above
2. You'll need to verify your LLC identity (they may call or ask for business documents)
3. **Important for CI:** EV certs are tied to a hardware token (USB). For CI signing,
   use **Azure Key Vault** to store the cert:
   - Provider will ask how you want to receive the cert — choose **Azure Key Vault** or **cloud HSM** if offered
   - DigiCert has a "KeyLocker" service; Sectigo offers "cloud-based" delivery
   - This is critical — a physical USB token cannot be used in GitHub Actions
4. After receiving the cert in Azure Key Vault, note:
   - Your Azure tenant ID, client ID, client secret
   - Key Vault name and certificate name
5. See `guides/04-code-signing.md` for configuring this in the Tauri release workflow

---

## ACC-5 — Microsoft Partner Center Account

**What:** Required to submit CoDRAG to the Microsoft Store.

**Cost:** Free (individuals) or $19 one-time fee (companies)

**Steps:**
1. Go to [partner.microsoft.com/dashboard](https://partner.microsoft.com/dashboard)
2. Sign in with a Microsoft account (create one for Magnetic Anomaly LLC)
3. Click **"Publish Windows apps and games"**
4. Register as a **Company** (Magnetic Anomaly LLC)
5. Pay the one-time $19 registration fee
6. Verification takes 1–3 business days
7. Once verified, you'll have access to create app submissions

> This can be done in parallel with other accounts — no dependencies.

---

## ACC-6 — Lemon Squeezy Account & Product Setup

**What:** Lemon Squeezy is your Merchant of Record — they handle payments, tax, compliance,
and refunds globally. You configure your products (license tiers) here.

**Steps:**

### 1. Create account
1. Go to [lemonsqueezy.com](https://www.lemonsqueezy.com)
2. Sign up and create a store for Magnetic Anomaly LLC
3. Connect a payout bank account (via their dashboard)

### 2. Create products for each tier
For each paid tier (Starter, Pro, Team), create a product:
1. **Dashboard → Products → Add Product**
2. Set:
   - **Name:** e.g., "CoDRAG Pro"
   - **Price:** Per your `DISTRIBUTION_AND_REVENUE_PLAN.md` §3
   - **Type:** Single payment (perpetual license) or subscription
   - **Description:** Describe what's included
3. Note the **Product ID** and **Variant ID** for each — you'll need them for the webhook

### 3. Configure the store
- Set your store URL (the checkout links embedded in the app)
- Note your **Store ID** — needed for `LEMONSQUEEZY_STORE_ID` env var
- Set up your **API key** under Account → API Keys — needed for `LEMONSQUEEZY_API_KEY`

### 4. Configure webhook (do this when the payments app is deployed — LIC-3)
After the payments site is live:
1. **Dashboard → Settings → Webhooks → Add Webhook**
2. URL: `https://payments.codrag.io/api/webhook/lemonsqueezy`
3. Events to subscribe: `order_created`, `subscription_created`
4. Note the **signing secret** — add it as `LEMONSQUEEZY_WEBHOOK_SECRET` in Netlify

---

## ACC-7 — Resend Account & Domain Verification

**What:** Resend sends transactional emails (license key delivery, bug report notifications).

**Cost:** Free tier: 3,000 emails/month, 100/day

**Steps:**

### 1. Create account
1. Go to [resend.com](https://resend.com)
2. Sign up with your Magnetic Anomaly LLC email

### 2. Add and verify domain
1. **Dashboard → Domains → Add Domain**
2. Enter `codrag.io`
3. Resend will show you DNS records to add — add these in Cloudflare:
   - A `TXT` record for SPF
   - A `CNAME` record for DKIM
   - (Optional) A `TXT` record for DMARC
4. Click **Verify** after adding records — verification is usually instant

### 3. Create API key
1. **Dashboard → API Keys → Create API Key**
2. Name it `codrag-production`
3. Copy the key — you'll add it as:
   - `RESEND_API_KEY` in Netlify environment variables for the **support** app
   - Also as a GitHub Secret if used in CI

### 4. Verify sending
- You can test sending from the Resend dashboard before going live

---

## ACC-8 — Netlify Account

> Detailed in `guides/07-cloudflare-netlify.md`. Quick steps here:

1. Go to [netlify.com](https://netlify.com)
2. Sign up → choose **"Start for free"**
3. Use Magnetic Anomaly LLC email
4. Connect GitHub (OAuth) during or after signup
5. Full setup in the Cloudflare + Netlify guide

---

## ACC-9 — PyPI Account & Token

**What:** Publishes the `codrag-engine` native Rust/Python wheels so they can be `pip install`-ed
independently (VS Code extension, advanced users).

**Steps:**

### 1. Create PyPI account
1. Go to [pypi.org](https://pypi.org) → **Register**
2. Use Magnetic Anomaly LLC email
3. Enable 2FA (required for trusted publishers)

### 2. Create API token
1. **Account Settings → API tokens → Add API token**
2. Scope: **Entire account** (or limit to `codrag-engine` project once created)
3. Copy the token

### 3. Add to GitHub Secrets
1. Go to [github.com/EricBintner/CoDRAG/settings/secrets/actions](https://github.com/EricBintner/CoDRAG/settings/secrets/actions)
2. **New repository secret**:
   - Name: `PYPI_TOKEN`
   - Value: the token you copied

> The CI wheel-publishing workflow uses this token to upload wheels on `engine-v*` tags.
