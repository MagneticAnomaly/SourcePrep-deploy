# Prep Deployment & DNS Strategy

> **Decision (2026-02-18):** All websites deploy on **Netlify** (free tier).
> Vercel was rejected because its Hobby tier prohibits commercial use ($20/mo for Pro).
> Cloudflare Pages was considered but has edge-runtime limitations for Next.js API routes.

## Overview

All four Prep web applications (`marketing`, `docs`, `support`, `payments`) deploy on
**Netlify** free tier (100 GB bandwidth, 300 build min/mo, commercial use allowed).
**Cloudflare** manages DNS and edge caching.

## Domain Structure

- **Primary Domain**: `runprep.io` (Marketing site)
- **Subdomains**:
  - `docs.runprep.io` (Documentation)
  - `support.runprep.io` (Support portal + bug report API)
  - `payments.runprep.io` (Licensing & checkout)
- **Legacy Redirect**: `runprep.io` → `runprep.io` (Cloudflare Page Rules)

## Site Classification

| Site | Domain | API Routes | Static exportable? |
|------|--------|-----------|-------------------|
| Marketing | `runprep.io` | `/rss` (hardcoded data, build-time OK) | Yes |
| Docs | `docs.runprep.io` | None | Yes |
| Support | `support.runprep.io` | `/api/bug-report` (POST → Resend) | Pages yes, API needs server |
| Payments | `payments.runprep.io` | `/api/recover` (POST → Lemon Squeezy) | Pages yes, API needs server |

Marketing and Docs could use `output: 'export'` for pure static builds, but Netlify handles
Next.js SSR natively so this is optional.

## Netlify Configuration

### Per-site setup (monorepo)

Each app is a separate Netlify site connected to the same GitHub repo.

| Site | Base Directory | Build Command | Publish Dir |
|------|---------------|---------------|-------------|
| Marketing | `websites/apps/marketing` | `cd ../../.. && npx turbo run build --filter=@prep/marketing` | `.next` |
| Docs | `websites/apps/docs` | `cd ../../.. && npx turbo run build --filter=@prep/docs` | `.next` |
| Support | `websites/apps/support` | `cd ../../.. && npx turbo run build --filter=@prep/support` | `.next` |
| Payments | `websites/apps/payments` | `cd ../../.. && npx turbo run build --filter=@prep/payments` | `.next` |

Alternatively, add a `netlify.toml` to each app for deprep-compresstive config.

### Next.js on Netlify

Netlify's `@netlify/plugin-nextjs` (auto-installed) handles:
- Server-side rendering (App Router)
- API routes (deployed as Netlify Functions)
- ISR / on-demand revalidation
- Image optimization (via Netlify Image CDN)

No special configuration needed beyond the standard Next.js build.

## DNS Configuration

DNS currently on **GoDaddy** — Cloudflare is optional (adds DDoS protection, edge caching)
but not required to launch. GoDaddy DNS pointing directly to Netlify works fine.

### Main Records (add in GoDaddy or any DNS provider)

| Type | Name | Content | Purpose |
|:-----|:-----|:--------|:--------|
| CNAME | `@` / `www` | `<marketing>.netlify.app` | Root domain (marketing) |
| CNAME | `docs` | `<docs>.netlify.app` | Docs subdomain |
| CNAME | `support` | `<support>.netlify.app` | Support subdomain |
| CNAME | `payments` | `<payments>.netlify.app` | Payments subdomain |

> Replace `<site>.netlify.app` with the actual Netlify subdomain after creating each site.
> Netlify auto-provisions SSL via Let's Encrypt — no cert purchase needed.

### Redirect Rules

- `runprep.io/*` → `https://runprep.io/$1` (301) — set in GoDaddy domain forwarding or Netlify redirects
- `www.runprep.io/*` → `https://runprep.io/$1` (301) — set in Netlify `_redirects` file or `netlify.toml`

### Optional: Migrate DNS to Cloudflare (post-launch)

Benefits: free DDoS protection, WAF, edge caching, Page Rules for redirects.
Not a launch blocker — GoDaddy works fine for MVP.

## Environment Variables

Set these in the Netlify dashboard for each site:

**Global (All Apps):**
- `NEXT_PUBLIC_SITE_URL`: The production URL (e.g., `https://docs.runprep.io`)

**Support App:**
- `GITHUB_TOKEN`: Fine-grained PAT with read-only Discussions access
- `RESEND_API_KEY`: For bug report email notifications
- `BUG_REPORT_EMAIL`: Destination for bug report alerts (default: `bugs@runprep.io`)

**Payments App:**
- `NEXT_PUBLIC_PREP_CHECKOUT_URL`: Lemon Squeezy checkout URL
- `LEMONSQUEEZY_API_KEY`: (Secret) API key for license recovery
- `LEMONSQUEEZY_STORE_ID`: Store ID

## Preview Deployments

Enable **Deploy Previews** on Netlify for PRs. This auto-deploys preview URLs for every
pull request, allowing visual review of `packages/ui` changes across all sites before merging.

## Migration from Vercel config

The existing `vercel.json` files in each app should be removed and replaced with
`netlify.toml` if deprep-compresstive config is needed. The `vercel.json` build/dev commands
are Vercel-specific and won't apply on Netlify.
