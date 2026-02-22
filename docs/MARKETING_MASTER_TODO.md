# Marketing + Websites — MASTER TODO

## Purpose
This file tracks **public-facing website work** (marketing/docs/support/payments) separately from the **product/app** backlog in `docs/MASTER_TODO.md`.

## Links
- Phase spec: `Phase12_Marketing-Documentation-Website/README.md`
- IA + wireframe: `Phase12_Marketing-Documentation-Website/WIREFRAME_AND_IA.md`
- Copy deck: `Phase12_Marketing-Documentation-Website/COPY_DECK.md`
- Deployment/DNS: `Phase12_Marketing-Documentation-Website/DEPLOYMENT.md`
- Design system / Storybook: `Phase13_Storybook/TODO.md`
- App backlog: `MASTER_TODO.md`
- Manual tasks (accounts, DNS, payments): `FOR_ERIC_TODO.md`

## Canonical decisions (locked unless explicitly changed)
- Canonical domain: `codrag.io`
- Subdomains (v0):
  - `docs.codrag.io`
  - `support.codrag.io`
  - `payments.codrag.io`

## Implementation plan (milestones)
- **MKT-M1: Local dev + build reliability** ✅
  - [x] Resolve the Next.js dev static asset 404 issue (ports 3000–3003). (Fixed via `scripts/run_websites.sh` and robust Vite proxying)
  - [x] Ensure `turbo dev` and `turbo build` succeed for all 4 apps.

- **MKT-M2: Marketing v0 pages ship (codrag.io)** ✅
  - [x] Home, Download, Pricing, Security/Privacy, Contact.
  - [x] Implemented "Radical Design Directions" (Swiss, Neo-Brutalist, Studio, etc.) for subpages.
  - [x] Copy aligned with `COPY_DECK.md` and "No LLM Required" messaging.

- **MKT-M3: Docs v0 scaffold ship (docs.codrag.io)** ✅
  - [x] Getting Started “10-minute trust loop”.
  - [x] Concepts + Guides + Troubleshooting scaffold.
  - [x] MCP setup guide (Cursor/Windsurf specific).

- **MKT-M4: Support + Payments v0 ship (support/payments subdomains)** ✅
  - [x] Support hub page (Github Issues/Discussions links).
  - [x] Payments hub + recovery flow (wired to `NEXT_PUBLIC_CODRAG_CHECKOUT_URL`).

- **MKT-M5: Deploy + DNS + launch checklist** (In Progress)
  - [x] Provider choice (Netlify — free tier, commercial OK).
  - [x] SEO basics (sitemap/robots/metadata created).
  - [x] Link validation (CI workflow).
  - [ ] Cloudflare DNS + redirects.
  - [x] Analytics integration (Plausible) ✅ — real per-site script bundles installed in all 4 layouts.

## Workstreams

### MKT-W0: Known blockers
- [x] Fix Next.js dev static asset 404s (`/_next/static/*`) across ports 3000–3003.

### MKT-W1: Shared UI + drift control
- [x] Keep “universal” marketing/docs components canonical in `@codrag/ui`.
- [x] Keep website apps thin: pages + routing + content wiring only.
- [x] Prefer Storybook-first UI iteration (`npm run storybook -w @codrag/ui`).
- [x] Theme contract:
  - [x] Visual direction via `data-codrag-theme="<id>"`.
  - [x] Reference: `packages/ui/.storybook/preview.tsx`.
- [x] Decide default `data-codrag-theme`: **Theme K (Inclusive Focus)** selected as default.
- [x] Implemented Atomic Design `Button` primitive across all sites.

### MKT-W2: Marketing site (`websites/apps/marketing`) codrag.io
- [x] `/` home: hero + loop + local-first trust block + integrations links.
- [x] `/download`: Platform cards + quick start + feature grid.
- [x] `/pricing`: Free/Starter/Pro/Team tiers + “no token markup” messaging.
- [x] `/security`: local-first + network behavior + data collection stance.
- [x] `/contact`: email + GitHub + enterprise interest.
- [x] `/careers`: Swiss Minimal layout (Direction F).
- [x] `/changelog`: Neo-Brutalist layout (Direction E).
- [x] `/blog`: Studio Collage layout (Direction I).
- [x] `/privacy`, `/terms`: Enterprise Console layout (Direction L).

### MKT-W3: Docs site (`websites/apps/docs`) docs.codrag.io
- [x] `/getting-started`: “10-minute trust loop” (Install -> Serve -> Add -> Connect -> Verify).
- [x] `/mcp`: Cursor/Windsurf guides + manual vs auto configuration.
- [x] `/troubleshooting`: Connection issues + Native vs Ollama embeddings + Build debugging.
- [x] `/cli`: Core commands + mcp-config reference.
- [x] `/dashboard`: UI walkthrough (Knowledge/Context/Graph panels).
- [x] `/guides`: Added Path Weights, CLaRa, Native Embeddings guides.
- [x] `/faq`: Common questions (Privacy, GPU, Editors).
- [x] `/search`: Client-side search implementation.

### MKT-W4: Support site (`websites/apps/support`) support.codrag.io (`support@codrag.io`)
- [x] Support Hub: Troubleshooting, Bug Report, Q&A, Billing, Email, Security cards.
- [x] Wired to `support.codrag.io` in Vercel config.
- [x] "Headless GitHub" integration for Discussions/Issues.

### MKT-W5: Payments site (`websites/apps/payments`) payments.codrag.io
- [x] Wire `NEXT_PUBLIC_CODRAG_CHECKOUT_URL` and document local `.env` usage.
- [x] Recovery path: `/recover` route implemented.
- [x] Success page: `/success` route implemented with next steps.

### MKT-W6: Deploy + DNS (See FOR_ERIC_TODO.md for manual steps)
- [x] Create GitHub Actions workflow (`.github/workflows/websites-ci.yml`) for lint, build, and link validation.
- [x] Choose deploy provider (**Netlify** — free tier, commercial OK per ToS; Vercel Hobby was rejected due to commercial-use prohibition).
  - [x] Create `netlify.toml` for marketing, docs, support, payments ✅ — `vercel.json` files removed.
- [ ] Cloudflare DNS records + redirects (www + legacy domain). *See FOR_ERIC_TODO.md*
- [ ] Preview deployments enabled for PRs (Netlify branch deploys).
- [x] Custom 404 pages for all 4 sites (Marketing, Docs, Support, Payments) ✅ — `not-found.tsx` exists in all 4 apps.

### MKT-W7: Quality gates
- [x] Link checker script (`scripts/validate_links.js`) implemented and passing.
- [ ] Lighthouse pass (perf/a11y/SEO) for marketing home.
- [ ] Manual QA: Chrome/Safari/Firefox.
- [ ] Decide docs versioning strategy (latest vs versioned per release).

### MKT-W9: Final Polish & Ops (Pre-Launch)
- [x] **Analytics**: Plausible per-site script bundles active in all 4 `layout.tsx` files ✅.
- [x] **Socials**: Update SiteFooter with real Twitter/X and GitHub URLs.
- [x] **Careers**: Add "Not actively hiring" disclaimer (optional).
- [ ] **Legal**: External legal review of Privacy/Terms.
- [ ] **Email**: Configure `support@codrag.io` and `hello@codrag.io` catch-alls.

### MKT-W10: Phase 29 UX Audit — Copy & Messaging Corrections (Feb 2026)

**Completed:**
- [x] Fix Atlas panel description: remove "injected into every AI query" → "pre-retrieval routing". (`packages/ui/src/config/panelRegistry.ts`)
- [x] Fix pricing page: Free = 1 project + manual only + no CLaRa. Starter = full Pro with 4-month time limit (not "3 projects"). (`websites/apps/marketing/src/app/pricing/page.tsx`)
- [x] Fix pricing "every plan includes" strip: "100% local" → "Local-first" to acknowledge BYOK. (`websites/apps/marketing/src/app/pricing/page.tsx`)
- [x] Fix homepage trust strip: "0 bytes sent to cloud" → "Local-first — your code stays on your machine". (`websites/apps/marketing/src/app/page.tsx`)
- [x] Fix About page: rewrite outdated copy to match current positioning (multiple retrieval methods, MCP backend, BYOK). (`websites/apps/marketing/src/app/about/page.tsx`)
- [x] Fix FeatureBlocks: Structural Code Graph badge from "Pro" → "Built-in" (trace_index is FREE per feature_gate.py). (`packages/ui/src/components/marketing/FeatureBlocks.tsx`)
- [x] Fix FeatureBlocks: Graph Enrichment "multi-pass" → "9-stage pipeline" (verified from pipeline_orchestrator.py). (`packages/ui/src/components/marketing/FeatureBlocks.tsx`)
- [x] Fix FeatureBlocks: "epistemic scoring" → "confidence scoring" in feature description. (`packages/ui/src/components/marketing/FeatureBlocks.tsx`)
- [x] Fix Dashboard App.tsx: remove incorrect Starter 3-project hardcode (Starter = Pro). (`src/codrag/dashboard/src/App.tsx`)

**Remaining:**
- [ ] **Support portal scope**: Define private/priority support for Pro/Team/Enterprise (email flow? SLA?). May not be MVP.
- [x] **Debug log export**: Added "Bug Reports & Debug Logs" section to Security page + FAQ entry ✅.
- [ ] **Perpetual license messaging**: Research how comparable products (Sublime Text, JetBrains perpetual fallback, Sketch) phrase perpetual licenses. Align homepage copy.
- [ ] **Lemon Squeezy post-purchase flow**: Investigate what Lemon Squeezy shows on the success page. Determine if we need custom copy about offline license.json delivery.
- [ ] **Homepage screenshots**: Create/capture the top 3 dashboard screenshots for the homepage placeholders (suggested: Knowledge Query results, Code Graph Explorer, Graph Enrichment Pipeline).
- [ ] **Docs: Codebase Atlas concept page**: Create `/concepts/atlas-routing` once Phase 29B implementation is complete.
- [x] **Docs: Pipeline stage count**: Docs site `/concepts/graph-enrichment` and `/dashboard` both reflect 9-stage pipeline ✅.
- [x] **Docs: Getting Started verification step**: Added Free tier note about manual trace build requirement ✅.

### MKT-W11: Pricing & Payments Setup (Pre-Launch)

**Strategy doc:** `Phase10_Business_And_Competitive_Research/Pricing/GLOBAL_PRICING.md`

**Code complete (website):**
- [x] `lib/pricing.ts` — PPP utility (4 bands, 100+ countries, price lookup, checkout URL builder).
- [x] `pricing/page.tsx` — Dynamic prices per region (silent enterprise UX, no banners/strikethroughs).
- [x] `middleware.ts` — Next.js middleware reads `request.geo.country` → sets `visitor_country` cookie.
- [x] `payments/page.tsx` — Per-product checkout cards (Monthly/Perpetual/Team) with env var URLs.
- [x] `.env.example` files for marketing + payments apps with all env var names documented.

**Manual tasks (Eric):** See `FOR_ERIC_TODO.md` §2 (Lemon Squeezy), §3 (Netlify env vars + DNS), §4 (Verification).

**License infrastructure (AI-implementable):**
- [ ] **LIC-01**: Deploy `api.codrag.io` serverless function for Ed25519 license signing.
- [ ] **LIC-04**: Implement license recovery API (replace mock in `payments/api/recover/route.ts`).

### MKT-W8: Later (post-v0 / 2.0)
- [ ] **Support 2.0**: Full Helpdesk.
  - [ ] Auth / Ticketing system.
  - [ ] Secure file uploads for debug traces.
- [ ] **Blog 2.0**: Migrate from JSON/TS to MDX (`@next/mdx`).
- [ ] `/workflows/*` case studies
- [ ] Public vs private Storybook decision + hosting if public
- [ ] Interactive dashboard demo (separate demo app; mock-only)
