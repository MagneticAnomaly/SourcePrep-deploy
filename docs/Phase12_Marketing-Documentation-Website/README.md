# Phase 12 — Marketing Website + Public Documentation

## Problem statement
Prep needs a credible public-facing website and documentation surface so we can:

- explain the product and its “local-first” posture
- onboard early adopters with a stable “getting started” path
- publish install/download guidance as the app becomes shippable
- provide a single canonical URL that future stakeholders can share

Right now, most of the product is unfinished, so the docs must be **scaffolded** (clear structure and intent, with honest placeholders) rather than pretending the app is complete.

## Goal
Launch a placeholder public website and a user-facing documentation site that:

- communicates Prep’s core value and positioning
- provides a structured documentation IA that can be filled in as features land
- is aligned with the dashboard’s UI stack and future design system work
- includes a domain + subdomain plan that won’t cause churn later

## Scope

### In scope
- Domain choice decision (`runprep.io` vs `runprep.io`) and redirect strategy
- Domain/subdomain infrastructure plan (DNS + hosting routing)
- Public website information architecture (IA) + initial content scaffold
- Public documentation IA + “loose” onboarding instructions
- Placeholder launch plan (minimal set of pages, launch checklist)

### Out of scope
- Shipping the actual dashboard/app UI
- Finalized pricing, packaging, and sales collateral
- A full content marketing program (blog cadence, SEO content ops)
- A fully polished brand system (handled after visual direction selection)

## Deliverables
- Domain decision + fallback plan
- Subdomain plan (what lives where, what is reserved)
- Website sitemap (v0 placeholder + v1 expanded)
- Documentation sitemap (v0 scaffold + v1 expanded)
- A publishable placeholder launch checklist
- **Deployment & DNS Strategy**: See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed Vercel/Netlify + Cloudflare setup instructions.

## Functional specification

### Domain decision: `runprep.io` vs `runprep.io`

#### Decision criteria
- Brand fit for an AI-native developer tool
- Trust for enterprise/security-conscious buyers
- Memorability and ease of typing
- Long-term flexibility (if the product expands beyond “AI” messaging)
- Operational simplicity (one canonical domain; no split-brain links)

#### Recommendation
- Primary domain: **`runprep.io`**
- Defensive purchase (if available): **`runprep.io`**
- Redirect: **`runprep.io` → `runprep.io`** (HTTP 301)

Rationale:
- `.io` is familiar and trusted for developer tools.
- `.ai` remains useful as a defensive purchase and a redirect to prevent confusion and protect backlinks.

Fallback (availability-driven):
- If `runprep.io` is unavailable or prohibitively expensive, use `runprep.io` as the primary and redirect the other.

### Domain + subdomain infrastructure

#### Principles
- Keep one canonical public domain.
- Keep docs at a stable subdomain (`docs.`) to avoid URL churn.
- Reserve obvious future subdomains even if unused (avoid future migrations).

#### Proposed subdomain map

- Root: `runprep.io`
  - marketing site
  - primary CTA(s): download/waitlist, docs
- `www.runprep.io`
  - optional; either canonicalize to root or to `www` (choose one)
- `docs.runprep.io` (alias: `doc.runprep.io`)
  - documentation site (versionable)
- `runprep.io/contact` (formerly `support.runprep.io`)
  - support hub (GitHub issues/discussions + email)
- `payments.runprep.io`
  - purchase + license delivery/recovery
- `get.runprep.io` (or `download.runprep.io`)
  - installers, release links, checksums
- `status.runprep.io`
  - service status page (future; even if product is local-first, the site itself can have uptime)
- `storybook.runprep.io`
  - UI component docs (may be private)
- `api.runprep.io`
  - reserved (future; do not use unless we ship a hosted service)

#### DNS + hosting approach (recommended)
- DNS + redirects: Cloudflare (simple redirects, TLS, HSTS, future WAF)
- Hosting for website/docs: Vercel or Netlify (static-first, easy previews)

Routing note:
- Prefer separate deploy targets for `runprep.io` and `docs.runprep.io` so docs can be versioned and deployed independently.

### Website information architecture

#### v0 placeholder (launch ASAP)
- Home (`/`)
  - value prop: "Your Code, Your Keys, Your Context."
  - “Local-first” trust messaging: "No Token Markup. No Cloud Index."
  - “How it works” (high-level)
  - CTA(s): “Read docs”, “Get Founder’s Edition”
- Docs (link to `docs.runprep.io`)
- Download (`/download`)
  - placeholder: “Not yet available” + links to GitHub releases when ready
- Pricing (`/pricing`)
  - **Founder’s Edition:** $49 (Limited time)
  - **Pro:** $79 (Perpetual)
  - **Team:** $12/mo
  - messaging: "Stop renting your context. Own your tools."
- Security & Privacy (`/security`)
  - local-first posture; what we do/don’t collect
- Contact (`/contact`)


#### v1 expanded (after app becomes usable)
- Changelog (`/changelog`)
- Blog (`/blog`)
- Case studies / workflows (`/workflows/*`)
- Enterprise (`/enterprise`)

### Documentation information architecture

Docs should be honest: it’s OK to scaffold pages with “TBD”, as long as the structure is stable.

#### v0 docs scaffold
- Getting Started
  - What is Prep?
  - Installation (placeholder + prerequisites)
  - Quickstart (add → build → search → context)
- Concepts
  - Local-first model (what stays on disk)
  - Projects, indexes, and modes (standalone vs embedded)
  - Search vs Context vs Trace
- Guides
  - Indexing a repo (include/exclude patterns)
  - Using Prep with Cursor/Windsurf via MCP (scaffold; fill as Phase05 lands)
- Reference
  - CLI reference (scaffold; align with `README.md`)
  - HTTP API reference (link to `docs/API.md` in repo)
- Troubleshooting
  - Ollama not running
  - Build failures
  - Performance tips

#### Docs versioning strategy
- Default: `docs.runprep.io` shows “latest”.
- Once releases exist, optionally version docs by major/minor: `docs.runprep.io/v0.1/`, `docs.runprep.io/v0.2/`.

### Recommended implementation direction (for when we build the site)

Constraint:
- The dashboard stack is React + Tailwind + Tremor. Website + docs should align to avoid duplicating UI work.

Recommendation:
- Use a React-based static site so we can share UI primitives with the dashboard.

Candidate approaches:
- Next.js (marketing + docs via MDX)
- Astro (marketing + docs; can embed React components)
- Docusaurus (docs-first; marketing possible but less flexible)

Default recommendation:
- Start with **Next.js** for marketing + docs content (MDX), and plan to share a UI package with the dashboard (Phase 13).

### Current repo implementation status (scaffold)

The repo currently contains an initial website monorepo scaffold to support `runprep.io` and future subdomains.

Implemented:
- Root npm workspaces + Turborepo
  - Root `package.json` defines workspaces:
    - `packages/*`
    - `websites/apps/*`
  - Root `turbo.json` defines `dev`, `build`, `lint`, `typecheck` tasks.
- Shared Tailwind preset
  - `websites/tailwind.preset.cjs` is the shared Tailwind config used by website apps.
- Website apps (Next.js App Router)
  - `websites/apps/marketing`
    - `runprep.io`
  - `websites/apps/docs`
    - `docs.runprep.io`
  - `websites/apps/payments`
    - `payments.runprep.io`
  - All apps:
    - import shared styles from `@prep/ui/styles`
    - use shared Tailwind preset via `websites/tailwind.preset.cjs`
    - transpile `@prep/ui` via `transpilePackages`

Local dev (from repo root):
- `npm install`
- Run all workspaces: `npm run dev`
- Or run individually:
  - marketing: `npm run dev -w @prep/marketing` (port 3000)
  - docs: `npm run dev -w @prep/docs` (port 3001)
  - payments: `npm run dev -w @prep/payments` (port 3003)

### Placeholder launch checklist

- Domain registered (primary + redirect)
- DNS configured (root + docs + redirects)
- Hosting connected (preview deployments enabled)
- Placeholder pages published
- Basic SEO
  - title/description
  - sitemap
  - robots.txt
- Basic legal
  - privacy/security page (even if minimal)
- Link validation
  - no broken internal links

## Success criteria
- A public placeholder website is live on the chosen canonical domain.
- Docs IA exists and can onboard an early adopter through the conceptual loop (even if some steps are “coming soon”).
- The domain/subdomain plan is explicit and does not need to change when the app ships.

## Dependencies
- Phase 02 (Dashboard) — shared UI direction and Tremor usage
- Phase 05 (MCP Integration) — to fill in IDE integration docs
- Phase 13 (Storybook / design system) — to unify visual design across website and app
- `../WORKFLOW_RESEARCH.md` — trust invariants and onboarding flows

## Open questions
- Should we host docs inside the repo and publish via CI, or use a separate docs repo?
- Do we want a waitlist/signup (and if so, which provider)?
- Should the docs be versioned from day one or only after stable releases?
- Will we publish Storybook publicly or keep it private?

## Risks
- Website/Docs drift from the actual product behavior as the app evolves.
- Premature brand/design work that gets invalidated by product constraints.
- Over-scoping v0 and delaying the placeholder launch.

## Testing / evaluation plan
- Manual QA in latest Chrome/Safari/Firefox
- Lighthouse pass for:
  - performance
  - accessibility
  - SEO
- Link checker run before publishing

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 12 gates)
