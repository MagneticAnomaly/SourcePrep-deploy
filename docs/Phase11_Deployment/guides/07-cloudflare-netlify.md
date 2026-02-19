# Guide: Cloudflare DNS + Netlify Deployment

> **Prerequisites:** ACC-8 (Netlify account). Your domains (`codrag.io`, `codrag.ai`) are
> currently registered on GoDaddy. After this guide, GoDaddy's only role is annual renewal.
>
> **Time estimate:** ~1–2 hours of setup. DNS propagation adds up to 24 hrs (usually <30 min).

---

## Part 1: Cloudflare DNS Setup (CF-1 through CF-9)

### CF-1 — Create Cloudflare account

1. Go to [cloudflare.com](https://cloudflare.com) → **Sign Up**
2. Use Magnetic Anomaly LLC email
3. Choose the **Free plan**

### CF-2 — Add `codrag.io` to Cloudflare

1. After signing in, click **"Add a site"**
2. Enter `codrag.io` → **Continue**
3. Select **Free plan** → **Continue**
4. Cloudflare will scan your existing GoDaddy DNS records and show you what it found
5. Review the list — make sure any existing records (MX for email, etc.) are included
6. Click **Continue**
7. Cloudflare will show you **two nameserver addresses** (e.g., `ava.ns.cloudflare.com` and `bob.ns.cloudflare.com`)
   — **keep this tab open**, you'll need these in the next step

### CF-3 — Change nameservers in GoDaddy ⚠️ One-time handoff

> **This is the key step.** Once done, all DNS for `codrag.io` is managed in Cloudflare.
> GoDaddy only holds the domain registration going forward.

1. Log in to [godaddy.com](https://godaddy.com)
2. Go to **My Products → Domains → codrag.io**
3. Click **DNS** or **Manage DNS**
4. Scroll to **Nameservers** → click **Change**
5. Choose **"Enter my own nameservers"** (Custom)
6. Replace GoDaddy's nameservers with the two Cloudflare ones from CF-2:
   - Nameserver 1: (e.g., `ava.ns.cloudflare.com`)
   - Nameserver 2: (e.g., `bob.ns.cloudflare.com`)
7. Save

### CF-4 — Wait for propagation

- Back in Cloudflare, click **"Done, check nameservers"**
- Cloudflare polls automatically — the dashboard shows **"Active"** when complete
- Usually takes 10–30 minutes; worst case 24 hours
- You'll get an email from Cloudflare when it's active

### CF-5 — Add `codrag.ai` to Cloudflare

Repeat CF-2 and CF-3 for `codrag.ai`:
1. In Cloudflare: **Add a site → codrag.ai → Free plan**
2. Change nameservers in GoDaddy for `codrag.ai` to the same Cloudflare nameservers
   (or the new ones Cloudflare gives you — may be different)

### CF-6 — Redirect `codrag.ai` → `codrag.io`

Once `codrag.ai` is active in Cloudflare:

1. Go to **codrag.ai → Rules → Redirect Rules**
2. Click **Create Rule**
3. Set:
   - **Rule name:** `codrag.ai catch-all redirect`
   - **When incoming requests match:** Custom filter expression
   - **Field:** Hostname, **Operator:** equals, **Value:** `codrag.ai`
   - **Then:** Static Redirect
   - **Redirect URL:** `https://codrag.io`
   - **Status code:** 301
4. Save and deploy

### CF-7 — Add DNS records for all 4 Netlify sites

> **Do this after creating your Netlify sites in Part 2** — you need the `.netlify.app` URLs first.

In Cloudflare for `codrag.io` → **DNS → Records → Add record**:

| Type | Name | Content | Proxy | Purpose |
|------|------|---------|-------|---------|
| CNAME | `@` | `<marketing>.netlify.app` | Proxied ☁️ | Root domain |
| CNAME | `www` | `codrag.io` | Proxied ☁️ | www redirect |
| CNAME | `docs` | `<docs>.netlify.app` | Proxied ☁️ | Docs site |
| CNAME | `support` | `<support>.netlify.app` | Proxied ☁️ | Support site |
| CNAME | `payments` | `<payments>.netlify.app` | Proxied ☁️ | Payments site |

> Replace `<marketing>`, `<docs>`, etc. with the actual Netlify subdomain assigned to each site.
> You find these in the Netlify dashboard for each site under **Site settings → Site information → Site name**.
>
> **Important:** Set the proxy status to **Proxied** (orange cloud icon) — not DNS only.
> This routes traffic through Cloudflare's CDN.

### CF-8 — Set SSL/TLS to Full (Strict)

1. In Cloudflare for `codrag.io` → **SSL/TLS → Overview**
2. Change the encryption mode to **Full (strict)**
   - This ensures traffic between Cloudflare and Netlify is also encrypted
   - Netlify automatically provisions an SSL cert for your domain — this is what Full (strict) validates

### CF-9 — Add www redirect rule

1. **Rules → Redirect Rules → Create Rule**
2. Set:
   - **Rule name:** `www to apex redirect`
   - **When:** Hostname equals `www.codrag.io`
   - **Then:** Dynamic Redirect
   - **Expression:** `concat("https://codrag.io", http.request.uri.path)`
   - **Status code:** 301
3. Save and deploy

---

## Part 2: Netlify Setup (WEB-1 through WEB-5)

### WEB-1 — Create Netlify account

1. Go to [netlify.com](https://netlify.com) → **Start for free**
2. Sign up with your Magnetic Anomaly LLC email
3. During onboarding, choose **"Connect to GitHub"** — authorize the OAuth app
4. Select `EricBintner/CoDRAG` repository access

### WEB-2 — Connect GitHub repo

If not done during signup:
1. **Team Settings → Integrations → Git providers**
2. Connect GitHub and authorize access to `EricBintner/CoDRAG`

### WEB-3 — Create the 4 sites

For each site: **Sites → Add new site → Import an existing project → GitHub → EricBintner/CoDRAG**

Configure each site as follows:

---

#### Site 1: Marketing (`codrag.io`)

| Setting | Value |
|---------|-------|
| **Site name** | `codrag-marketing` (or similar — this becomes `codrag-marketing.netlify.app`) |
| **Branch** | `main` |
| **Base directory** | `websites/apps/marketing` |
| **Build command** | `cd ../../.. && npx turbo run build --filter=@codrag/marketing` |
| **Publish directory** | `websites/apps/marketing/.next` |

**Environment variables** (Site settings → Environment variables → Add variable):
| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_SITE_URL` | `https://codrag.io` |

**Custom domain** (after site is created):
1. **Site settings → Domain management → Add a domain**
2. Enter `codrag.io` → **Verify** → **Add domain**
3. Netlify will detect Cloudflare and ask you to add a DNS record — you already did this in CF-7

---

#### Site 2: Docs (`docs.codrag.io`)

| Setting | Value |
|---------|-------|
| **Site name** | `codrag-docs` |
| **Branch** | `main` |
| **Base directory** | `websites/apps/docs` |
| **Build command** | `cd ../../.. && npx turbo run build --filter=@codrag/docs` |
| **Publish directory** | `websites/apps/docs/.next` |

**Environment variables:**
| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_SITE_URL` | `https://docs.codrag.io` |

**Custom domain:** `docs.codrag.io`

---

#### Site 3: Support (`support.codrag.io`)

| Setting | Value |
|---------|-------|
| **Site name** | `codrag-support` |
| **Branch** | `main` |
| **Base directory** | `websites/apps/support` |
| **Build command** | `cd ../../.. && npx turbo run build --filter=@codrag/support` |
| **Publish directory** | `websites/apps/support/.next` |

**Environment variables:**
| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_SITE_URL` | `https://support.codrag.io` |
| `GITHUB_TOKEN` | Fine-grained PAT (read-only Discussions access — see below) |
| `RESEND_API_KEY` | From ACC-7 (Resend dashboard) |
| `BUG_REPORT_EMAIL` | `bugs@codrag.io` |

**Creating the `GITHUB_TOKEN`:**
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → **Fine-grained tokens → Generate new token**
2. Name: `codrag-support-discussions-read`
3. Expiration: 1 year (set a reminder to renew)
4. Repository access: **Only selected repositories → EricBintner/CoDRAG**
5. Permissions: **Repository permissions → Discussions → Read-only**
6. Generate and copy the token → paste as `GITHUB_TOKEN` in Netlify

**Custom domain:** `support.codrag.io`

---

#### Site 4: Payments (`payments.codrag.io`)

| Setting | Value |
|---------|-------|
| **Site name** | `codrag-payments` |
| **Branch** | `main` |
| **Base directory** | `websites/apps/payments` |
| **Build command** | `cd ../../.. && npx turbo run build --filter=@codrag/payments` |
| **Publish directory** | `websites/apps/payments/.next` |

**Environment variables:**
| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_SITE_URL` | `https://payments.codrag.io` |
| `NEXT_PUBLIC_CODRAG_CHECKOUT_URL` | Your Lemon Squeezy checkout URL (from ACC-6) |
| `LEMONSQUEEZY_API_KEY` | From ACC-6 (Lemon Squeezy → API Keys) |
| `LEMONSQUEEZY_STORE_ID` | From ACC-6 (Lemon Squeezy → Store settings) |

**Custom domain:** `payments.codrag.io`

---

### WEB-4 — Enable Deploy Previews

This should be on by default for all sites. Verify:
1. **Site settings → Build & deploy → Deploy contexts**
2. Confirm **"Deploy Previews"** is enabled for pull requests
3. This gives you a preview URL on every PR — great for testing UI changes before merging

### WEB-5 — Remove `vercel.json` files

Each app has a `vercel.json` that's no longer needed (and can confuse Netlify). I can do this — just ask.

---

## Verification checklist

After everything is set up:

- [ ] `https://codrag.io` loads the marketing site with HTTPS (no browser warnings)
- [ ] `https://docs.codrag.io` loads
- [ ] `https://support.codrag.io` loads
- [ ] `https://payments.codrag.io` loads
- [ ] `https://www.codrag.io` redirects to `https://codrag.io`
- [ ] `https://codrag.ai` redirects to `https://codrag.io`
- [ ] Cloudflare dashboard shows all domains as "Active"
- [ ] Netlify shows all 4 sites as "Published"
- [ ] SSL padlock visible in browser on all domains

## Troubleshooting

**"Too many redirects" error:**
- Check CF-8 — SSL mode should be **Full (strict)**, not Flexible

**Site shows Netlify's default "Site not found":**
- The CNAME record in Cloudflare is pointing to the wrong Netlify subdomain
- Check Site settings → Domain management in Netlify — it should list your custom domain as "primary"

**Build fails on Netlify:**
- Check that the base directory is correct (relative to repo root)
- The monorepo build command must `cd` up to repo root first before running turbo
- Check Netlify deploy logs for the specific error
