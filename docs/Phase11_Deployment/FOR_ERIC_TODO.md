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
- [ ] ACC-7 Resend account + verified domain (`codrag.io`) for transactional email
- [ ] ACC-9 PyPI account + API token for `codrag-engine` wheel publishing (`PYPI_TOKEN` in GitHub Secrets)

---

## 2. Payments & Licensing (Lemon Squeezy)
*Requires websites to be deployed first.*

- [ ] LS-01 Create Lemon Squeezy store at `lemonsqueezy.com`
- [ ] LS-02 Create LS **Monthly** product — $7/mo recurring subscription
- [ ] LS-03 Create LS **Perpetual** product — $79 one-time payment
- [ ] LS-04 Create LS **Team** product — $15/seat/mo recurring subscription
- [ ] LS-05 Create PPP discount codes (`PPP20`, `PPP40`, `PPP60`)
- [ ] LS-06 Configure LS webhook → `api.codrag.io` for license generation
- [ ] LS-07 Set LS success redirect URL → `https://payments.codrag.io/success`
- [ ] LS-08 Test full purchase flow end-to-end (LS test mode)

---

## 3. Web Hosting & DNS (Cloudflare & Netlify)
*See: [guides/07-cloudflare-netlify.md](Phase11_Deployment/guides/07-cloudflare-netlify.md)*

### Cloudflare DNS
- [ ] CF-1 Create Cloudflare account (Magnetic Anomaly LLC)
- [ ] CF-2 Add site `codrag.io` to Cloudflare (auto-import GoDaddy DNS)
- [ ] CF-3 **Change nameservers in GoDaddy** to Cloudflare nameservers
- [ ] CF-4 Wait for nameserver propagation
- [ ] CF-5 Add site `codrag.ai` to Cloudflare (legacy redirect domain)
- [ ] CF-6 Add redirect rule for `codrag.ai/*` → `https://codrag.io/$1`
- [ ] CF-7 Add DNS records for `codrag.io` (CNAMEs to Netlify sites)
- [ ] CF-8 Set SSL/TLS mode in Cloudflare to **Full (Strict)**
- [ ] CF-9 Add redirect rule for `www.codrag.io/*` → `https://codrag.io/$1`

### Netlify Setup
- [ ] WEB-1 Create Netlify account (Starter plan, Magnetic Anomaly LLC)
- [ ] WEB-2 Connect GitHub: authorize OAuth and connect `EricBintner/CoDRAG`
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
- [ ] VER-04 Test license recovery flow: payments.codrag.io/recover

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
