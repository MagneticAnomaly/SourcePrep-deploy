# FOR ERIC: Manual Tasks & Account Setup

This document tracks all the manual tasks that cannot be automated by AI. These involve account creation, credentials, payments, and DNS changes.

## Guides Reference
Detailed step-by-step instructions for these tasks can be found in the guides directory:
- [Accounts & Credentials](Phase11_Deployment/guides/01-accounts-credentials.md)
- [Code Signing](Phase11_Deployment/guides/04-code-signing.md)
- [Cloudflare & Netlify](Phase11_Deployment/guides/07-cloudflare-netlify.md)
- [VS Code Marketplace](Phase11_Deployment/guides/08-vscode-marketplace.md)
- [Microsoft Store](Phase11_Deployment/guides/10-microsoft-store.md)

---

## 1. Accounts & Credentials (Critical Path)
*See: [guides/01-accounts-credentials.md](Phase11_Deployment/guides/01-accounts-credentials.md)*

- [x] ACC-1 Apple Developer Program enrollment (Magnetic Anomaly LLC)
- [x] ACC-2 Generate Ed25519 signing keypair for Tauri auto-updater
- [ ] ACC-3 Store updater private key in GitHub Secrets (`TAURI_PRIVATE_KEY`, `TAURI_KEY_PASSWORD`)
- [ ] ACC-4 Windows code signing certificate (EV recommended)
- [ ] ACC-5 Microsoft Partner Center developer account (Magnetic Anomaly LLC)
- [ ] ACC-7 Resend account + verified domain (`runprep.io`) for transactional email
- [ ] ACC-9 PyPI account + API token for `prep-engine` wheel publishing (`PYPI_TOKEN` in GitHub Secrets)

---

## 2. Payments & Licensing (Lemon Squeezy)
*Requires websites to be deployed first.*
*Code integration: Sprint 2 built `lemon_squeezy.py` + `license.py` endpoints. Ready for LS product IDs.*

### Create LS Products
- [ ] LS-01 Create Lemon Squeezy store at `lemonsqueezy.com`
- [ ] LS-02 Create LS **Monthly** product — $7/mo recurring subscription
  - Enable "License keys" in product settings
  - Set activation limit: **3** (3 machines per user)
- [ ] LS-03 Create LS **Perpetual** product — $79 one-time payment
  - Enable "License keys" in product settings
  - Set activation limit: **5** (5 machines per user)
- [ ] LS-04 Create LS **Team** product — $15/seat/mo recurring subscription
  - Enable "License keys" in product settings
  - Set activation limit: **1 per seat** (LS handles seat counting)
- [ ] LS-05 Create PPP discount codes (`PPP20`, `PPP40`, `PPP60`)

### Configure LS Integration
- [ ] LS-06 Configure LS webhook → `api.runprep.io/webhooks/lemonsqueezy`
  - Events needed: `order_created`, `subscription_updated`, `subscription_cancelled`, `license_key_created`
- [ ] LS-07 Set LS success redirect URL → `https://payments.runprep.io/success`
- [ ] LS-09 **After creating products, note down these IDs from LS dashboard:**
  - `STORE_ID` (your Lemon Squeezy store ID)
  - `PRODUCT_ID_MONTHLY` (Monthly Pro product)
  - `PRODUCT_ID_PERPETUAL` (Perpetual Pro product)
  - `PRODUCT_ID_TEAM` (Team product)
  - **Give these to AI to update `PRODUCT_TIER_MAP` in `src/prep/core/lemon_squeezy.py`**

### Ed25519 Keypair (Enterprise Offline Licenses)
- [ ] LS-10 Generate Ed25519 signing keypair:
  ```bash
  # Generate private key (KEEP SECRET — store in HSM or secure vault)
  openssl genpkey -algorithm ed25519 -out prep_license_private.pem
  # Extract public key (shipped in app binary)
  openssl pkey -in prep_license_private.pem -pubout -out prep_license_public.pem
  ```
- [ ] LS-11 Store private key securely (GitHub Secret `PREP_LICENSE_PRIVATE_KEY` or HSM)
- [ ] LS-12 Give public key to AI to embed in `src/prep/core/licensing.py`

### Testing
- [ ] LS-08 Test full purchase flow end-to-end (LS test mode)
- [ ] LS-13 Test activation: enter LS test key in Prep → verify tier activates
- [ ] LS-14 Test deactivation: click Deactivate → verify LS slot freed
- [ ] LS-15 Test grace period: disconnect internet → verify 30-day countdown works

---

## 3. Web Hosting & DNS (Cloudflare & Netlify)
*See: [guides/07-cloudflare-netlify.md](Phase11_Deployment/guides/07-cloudflare-netlify.md)*

### Cloudflare DNS
- [ ] CF-1 Create Cloudflare account (Magnetic Anomaly LLC)
- [ ] CF-2 Add site `runprep.io` to Cloudflare (auto-import GoDaddy DNS)
- [ ] CF-3 **Change nameservers in GoDaddy** to Cloudflare nameservers
- [ ] CF-4 Wait for nameserver propagation
- [ ] CF-5 Add site `runprep.io` to Cloudflare (legacy redirect domain)
- [ ] CF-6 Add redirect rule for `runprep.io/*` → `https://runprep.io/$1`
- [ ] CF-7 Add DNS records for `runprep.io` (CNAMEs to Netlify sites)
- [ ] CF-8 Set SSL/TLS mode in Cloudflare to **Full (Strict)**
- [ ] CF-9 Add redirect rule for `www.runprep.io/*` → `https://runprep.io/$1`

### Netlify Setup
- [ ] WEB-1 Create Netlify account (Starter plan, Magnetic Anomaly LLC)
- [ ] WEB-2 Connect GitHub: authorize OAuth and connect `EricBintner/Prep`
- [ ] WEB-3 Create 4 separate Netlify sites (marketing, docs, support, payments)
- [ ] WEB-4 Enable Deploy Previews
- [x] WEB-5 Remove `vercel.json` from each app

### Netlify Environment Variables
- [ ] ENV-01 Set `NEXT_PUBLIC_LS_CHECKOUT_MONTHLY` on marketing site
- [ ] ENV-02 Set `NEXT_PUBLIC_LS_CHECKOUT_PERPETUAL` on marketing site
- [ ] ENV-03 Set `NEXT_PUBLIC_LS_CHECKOUT_TEAM` on marketing site
- [ ] ENV-04 Set same checkout vars on payments site
- [ ] ENV-05 Set `LEMONSQUEEZY_API_KEY` on payments site
- [ ] ENV-06 Set `LEMONSQUEEZY_STORE_ID` on payments site
- [ ] WEB-S4 Set `GITHUB_TOKEN` on support site
- [ ] WEB-S5 Set `RESEND_API_KEY`, `BUG_REPORT_EMAIL` on support site

---

## 4. Verification & Testing
- [ ] VER-01 Test PPP pricing by visiting `/pricing?country=IN`
- [ ] VER-02 Test PPP pricing for Band 1 and Band 2
- [ ] VER-03 Test checkout flow: pricing page → LS checkout → success page → license email
- [ ] VER-04 Test license recovery flow: payments.runprep.io/recover

---

## 5. App Store Submissions

### VS Code Marketplace
*See: [guides/08-vscode-marketplace.md](Phase11_Deployment/guides/08-vscode-marketplace.md)*
- [ ] VSC-4 Publish extension to VS Code Marketplace (Requires Azure DevOps PAT)

### Microsoft Store
*See: [guides/10-microsoft-store.md](Phase11_Deployment/guides/10-microsoft-store.md)*
- [ ] MST-1 Register product in Microsoft Partner Center
- [ ] MST-2 Configure as EXE/MSI app with external licensing declaration
- [ ] MST-3 Submit code-signed installer
- [ ] MST-4 Store listing: screenshots, description, category
- [ ] MST-5 Test installation and license activation

## 6. Disabling Beta Mode & Launching to Prod
*When we are ready to move from waitlist/beta to real payments:*

- [ ] PROD-01 Open `websites/apps/marketing/src/app/page.tsx`
- [ ] PROD-02 Change `const IS_BETA_MODE = true;` to `const IS_BETA_MODE = false;`
- [ ] PROD-03 Open `websites/apps/marketing/src/app/pricing/page.tsx`
- [ ] PROD-04 Change `const IS_BETA_MODE = true;` to `const IS_BETA_MODE = false;`
- [ ] PROD-05 Open `packages/ui/src/components/marketing/MarketingHero.tsx`
- [ ] PROD-06 Change `export function MarketingHero({ variant = 'centered', isBetaMode = true }: MarketingHeroProps)` to `isBetaMode = false`
- [ ] PROD-07 Commit changes, push to `main` to trigger Netlify build.
- [ ] PROD-08 Verify that "Request Beta" buttons on the marketing site have reverted to "Download" and "Get Prep".
- [ ] PROD-09 Verify that "Request Beta" buttons on the pricing page now link out to the Lemon Squeezy checkout URLs.

## 7. App Update & Auto-Updater Infrastructure
*Before disabling beta mode, ensure the auto-updater URLs are ready:*
- [ ] UPD-01 Create AWS S3 bucket or Cloudflare R2 bucket for hosting `.exe`/`.app`/`.dmg` releases.
- [ ] UPD-02 Ensure `runprep.io/releases.json` (or similar endpoint) points to the correct signatures generated by Tauri.
- [ ] UPD-03 Verify that the public key generated in ACC-2 is embedded in the Tauri app (`tauri.conf.json`).

