# Phase 142 — Open-Core Split

> The OSS / Pro / Teams / Enterprise boundary, the pricing table, the
> release sequencing, the IP inventory, and the Lemon Squeezy product
> configuration spec. This is the decision record for the open-core
> architecture. Supplements (does not replace) `DISTRIBUTION_AND_REVENUE_PLAN.md`.

**Status:** Decisions locked 2026-05-30 by Eric, then **re-hardened
2026-07-17/18** (see "Superseded 2026-05-30 decisions" below). This doc
is the **single source of truth** for pricing and the open-core boundary;
the pricing sections of `DISTRIBUTION_AND_REVENUE_PLAN.md` and
`PRODUCT_AND_BUSINESS_OVERVIEW.md` are **SUPERSEDED** by this doc.
Ready to execute once Phase 143 (docs cleanup + two-repo split) and
Phase 144 (legal/trademark/DCO) complete.

> **Superseded 2026-05-30 decisions (corrected 2026-07-19).** Several
> numbers/mechanics below were locked 2026-05-30 and later reversed by
> the 2026-07-17/18 hardening pass (`DECISION_MEMO_2026-07-17.md` Part 0,
> `LICENSING_RECOMMENDATION.md`, `REPO_TOPOLOGY.md`, live marketing
> pricing). Where a stale 2026-05-30 value survives in a paragraph below,
> the hardened value in the **TL;DR** and the **Pricing table** governs:
> - **Pro:** was $7/mo or $70 perpetual → **$29 one-time perpetual** (12
>   months auto-updates included; ~$15/yr optional thereafter; name-your-
>   price with $29 floor; **monthly subscription dropped**). NOT live at
>   the first OSS launch (checkout unwired, license crypto being replaced,
>   code-signing lead time) — Pro goes live once those land.
> - **Teams:** was $15/seat/mo or $144/yr → **$9/seat/mo or $97/seat/yr**
>   (10% off), 3-seat minimum.
> - **Enterprise:** was $50/seat/mo, 10-seat, $5k setup → **$24/seat/mo**
>   annual, **15-seat minimum**; setup **remote included · on-site from
>   $3,500 · air-gapped quoted**.
> - **Contributor agreement:** was Apache ICLA → **DCO** (`Signed-off-by`),
>   not a CLA. License is **permanent** (no AGPL fallback / no relicense).
> - **GitHub org:** was "reserve `sourceprep` org" → **stay under
>   `MagneticAnomaly`**; storefront = `MagneticAnomaly/SourcePrep`
>   (curated one-way mirror of the workshop repo). Defer a `sourceprep`
>   org to a possible future C-corp/VC path.
> - **Phase 1 scope:** was "OSS + Pro" → **OSS only** at the first launch.
>   Pro (and Teams/Enterprise) come online as their prerequisites land.
> The narrative paragraphs (three pillars, surface map, IP inventory)
> remain valid; only the pricing/mechanics above changed.

---

## TL;DR

1. **OSS surface** (Apache 2.0): full engine, daemon, CLI, MCP server,
   local dashboard, VS Code extension, AGENTS.md generator. Unlimited
   use. Single-user. Self-hosted.
2. **Pro** ($29 one-time perpetual; 12 months auto-updates included,
   ~$15/yr optional thereafter, name-your-price with $29 floor): signed/
   notarized Tauri installer + auto-update + license-keyed convenience
   features. Same engine. **Not live at the first OSS launch** — the
   checkout is unwired, the license crypto is being replaced, and code-
   signing has lead time.
3. **Teams** ($9/seat/mo or $97/seat annual, 3-seat minimum): hosted
   multi-user backend with org-shared indexes, SSO, RBAC, audit logs.
4. **Enterprise** ($24/seat/mo annual, 15-seat minimum; setup remote
   included · on-site from $3,500 · air-gapped quoted): everything in
   Teams + air-gapped deployment + dedicated support.
5. **Enterprise Plus** (negotiated, off-platform): >50 seats or custom
   contracts.
6. **The old Free (3-projects) tier is retired** — OSS replaces it.
7. **Two-part release.** Phase 1 = **OSS only** (Pro comes online once
   checkout + license crypto + code-signing land). Phase 2 = Teams +
   Enterprise, 6–10 weeks after Pro goes live.

---

## Why this exists

The original `DISTRIBUTION_AND_REVENUE_PLAN.md` (2026-02-12,
AUTHORITATIVE) describes a closed-source Tauri product with a
5-tier model: Free (3 projects) / Monthly ($7) / Perpetual ($79) /
Team ($15/seat) / Enterprise (custom). That model assumes the engine
is closed and the project-count gate is the upgrade trigger.

Phase 142 inverts that — the engine ships Apache 2.0. The 3-project
gate becomes architecturally unenforceable (anyone who runs the OSS
has unlimited projects). The Free tier becomes incoherent and must
be retired. The Pro/Teams/Enterprise tiers must be repositioned from
*capability gates* to *infrastructure + services* — things an OSS
user cannot replicate by reading the source.

This doc records those repositioning decisions.

---

## The open-core boundary (surface map)

| Surface | OSS | Pro | Teams | Enterprise |
|---|---|---|---|---|
| Rust engine (`engine/crates/*`) | ✅ | ✅ | ✅ | ✅ |
| Python core (`src/prep/core/*`) | ✅ | ✅ | ✅ | ✅ |
| MCP server (`src/prep/mcp/`, `mcp_direct.py`, `mcp_tools.py`) | ✅ | ✅ | ✅ | ✅ |
| CLI (`src/prep/cli.py`) | ✅ | ✅ | ✅ | ✅ |
| Daemon (`src/prep/server.py`) | ✅ | ✅ | ✅ | ✅ |
| Local dashboard (`src/prep/dashboard/`, single-user) | ✅ | ✅ | ✅ | ✅ |
| AGENTS.md generator (`src/prep/core/rules_generator.py`) | ✅ | ✅ | ✅ | ✅ |
| `packages/ui` component library (`@prep/ui`) | ✅ | ✅ | ✅ | ✅ |
| VS Code extension (`packages/vscode`) | ✅ | ✅ | ✅ | ✅ |
| All prompts in `src/prep/services/*` | ✅ | ✅ | ✅ | ✅ |
| Signed/notarized Tauri installer + auto-update | — | ✅ | ✅ | ✅ |
| Hosted multi-tenant backend (org-shared indexes) | — | — | ✅ | ✅ |
| SSO (Google, Okta, Entra) | — | — | ✅ | ✅ |
| RBAC + audit log storage | — | — | ✅ | ✅ |
| Centralized policy + budget governance | — | — | ✅ | ✅ |
| Air-gapped deployment scripts | — | — | — | ✅ |
| Dedicated support contact + scheduled office hours | — | — | — | ✅ |
| On-prem deploy assistance (remote incl · on-site from $3,500) | — | — | — | ✅ |
| Custom contracts, multi-year, custom SLA | — | — | — | Plus only |

**The principle:** OSS is the full single-user product. Pro adds
distribution polish. Teams adds the multi-tenant infrastructure
(which lives in a separate proprietary backend repo). Enterprise
adds the regulated-buyer surface (air-gap + dedicated support).

**What is explicitly NOT gated:** prompts, algorithms, "premium
methods," any in-engine capability. Gating those would imply the OSS
is feature-limited, which kneecaps the launch narrative.

---

## The three Pro pillars

### Pillar 1 — Signed installer + auto-update (Pro tier)

**What it is.** Apple-notarized DMG / Microsoft-signed MSI built from
the OSS source, distributed from `sourceprep.io` (not GitHub
Releases), with embedded license-key validation and silent
auto-update.

**Why it's defensible.** Notarization requires our paid developer
certificates (Apple Developer Program: $99/year; Microsoft EV cert:
~$300/year). The OSS user *can* build their own Tauri app from
source, but it will be unsigned (triggering "unknown developer"
warnings on Mac/Windows) and have no auto-update. The OSS path
remains fully functional; the signed path is a convenience product.

**Distribution channel comparison:**

| Channel | OSS user gets | Pro user gets |
|---|---|---|
| `pip install prep` / `pipx install prep` | CLI + daemon + MCP, manual updates via `pipx upgrade` | Same |
| `brew install prep` | Same | Same |
| `git clone && cargo build` | Source-built Tauri app, unsigned, no auto-update | — |
| `sourceprep.io/download` | — | Signed DMG/MSI, license-key activation, auto-update |

**Implementation status.** Lemon Squeezy + Ed25519 license-key
infrastructure already specced in `DISTRIBUTION_AND_REVENUE_PLAN.md`
sections 5–6. The Ed25519 crypto is being replaced before Pro goes live
(`docs/Phase146_SecurityAudit/CHANGE_PLAN_ed25519_crypto_fix.md` — the
shipped verifier key is the all-zeros-seed public key and is forgeable;
the generator↔verifier keypair is mismatched). No new engineering
required beyond that fix — only reconfiguration to match the new
pricing ($29 one-time; monthly subscription dropped).

---

### Pillar 2 — Hosted multi-tenant backend (Teams + Enterprise tiers)

**What it is.** A proprietary backend service (separate from the OSS
repo) that provides:

- Org-shared indexes (one canonical, always-fresh index per repo
  per team — eliminates duplicate per-laptop indexing)
- SSO via SAML 2.0 + OIDC (Google Workspace, Okta, Microsoft Entra)
- Role-based access control over project visibility, audit log
  read access, policy editing
- Audit log storage (immutable, queryable, exportable)
- Centralized policy + budget governance (extends the existing
  Enterprise Policy & Budget Governance Engine module surfaced
  by `prep`)

**Why it's defensible.** The hosted backend is a *separate codebase
that is not published.* Apache 2.0 covers only what ships to the
public mirror — the multi-tenant server, billing integration, SSO
glue, and audit log store are 100% proprietary. The OSS daemon is
single-user by architecture; a team cannot fork the OSS into a
multi-tenant hosted product without writing the server themselves.

This is identical to the GitLab CE/EE, Sentry OSS/SaaS, and
Mattermost Team Ed/Enterprise patterns — well-trodden ground.

**Privacy posture.** Hosted indexes upload *embeddings + graph
metadata* derived from local indexing — never raw source code. The
OSS daemon does the indexing locally; only the resulting index
payload syncs to the hosted backend. This preserves the
"your code never leaves your machine" claim that differentiates
SourcePrep from Sourcegraph's hosted indexing.

**Sync architecture.** Local OSS daemon → push embeddings + graph
deltas via authenticated API → hosted backend stores per-org index
→ teammates pull index for queries. Standard pull/push semantics.

**Implementation status.** Not built. 6–10 weeks of engineering work
for Phase 2. Ships after Phase 1 OSS+Pro launch.

---

### Pillar 3 — Support + scoped consulting (Pro / Teams / Enterprise)

**Tier matrix:**

| Tier | Channel | Response target | Honest commitment |
|---|---|---|---|
| OSS / Community | GitHub Issues + Discussions | Best-effort | "I respond when I can; community helps." |
| Pro ($29 one-time) | `support@sourceprep.io` email | 5 business days | "I read every email. No SLA, but I care." |
| Teams ($9/seat/mo) | Private Slack/Discord channel + email | 2 business days | Same person, faster lane. No contractual SLA. |
| Enterprise ($24/seat/mo annual) | Dedicated channel + monthly office hours + named contact | Negotiated 24h business-day target | **"Founder direct line" today.** Converts to true contractual SLA when 2nd engineer joins. |

**On-prem help breakdown:**

1. **Installation assistance** — scoped 1–2 week engagement to
   stand up air-gapped deployment. **Remote included; on-site from
   $3,500; air-gapped quoted.** Sold as an Enterprise add-on.
   Off-platform invoicing via Magnetic Anomaly LLC.
2. **Architecture review** — 2-week deep dive on how the customer
   uses SourcePrep at scale. **$25,000 scoped engagement.** Sold as
   Enterprise Plus only.
3. **Custom integrations** — declined by default. If a customer
   asks, negotiate a fixed-scope SoW; never open-ended hourly. Loss-
   leader risk unless tightly bounded.

**Solo-dev honesty.** Eric is a single engineer. Real contractual
SLAs require ≥2 humans for vacation/illness coverage. Enterprise
sells as "founder direct line" with this caveat clearly stated. True
SLAs become contractually valid only when headcount allows.

**`SECURITY.md` commitment** (OSS tier): "We respond to security
reports within 5 business days." Standard, cheap, builds trust.
Add in Phase 142 Part C of the implementation plan.

---

## What we cut: "Premium prompts" (was Pillar 2 in earlier drafts)

**Cut 2026-05-30.** Reasoning:

- Prompts in compiled Tauri builds are decompilable via `strings` —
  no real technical moat
- Prompts gated behind a paywall implies "OSS users get inferior
  output," which kneecaps the Phase 142 Part E launch benchmark
  (Show HN readers will rightly ask why the OSS doesn't match)
- "Pay us for better strings" is a weak pitch
- The Phase 140 prompt audit work is still iterating; gating an
  in-flux system creates Pro-user complaints
- Replacement ideas (Pro-first R&D cadence, benchmarks-as-service,
  YAML customization tooling) added complexity for marginal moat

**Decision:** all prompts ship OSS. No replacement Pro pillar. The
three pillars above (signed installer, hosted backend, support) are
the complete commercial surface.

---

## Pricing table (final, locked — re-hardened 2026-07-18)

| Tier | Price | Annual | Min seats | LS product? | Notes |
|---|---|---|---|---|---|
| Open Source | $0 | — | — | No | Apache 2.0; full single-user product |
| Pro Perpetual | $29 one-time | — | 1 | Yes | 12 months auto-updates included; ~$15/yr optional thereafter; name-your-price with $29 floor. **Monthly subscription dropped.** Not live at first OSS launch. |
| Teams Monthly | $9/seat/mo | $108/seat/yr | 3 | Yes | Per-seat variable subscription |
| Teams Annual | — | $97/seat/yr (≈ $8.08/seat/mo, 10% off) | 3 | Yes | Annual discount product |
| Enterprise | $24/seat/mo (annual contract only) | $288/seat/yr | 15 ($4,320/yr floor) | Yes | Annual recurring; includes everything in Teams + air-gap + named support |
| Enterprise Setup | Remote included · on-site from $3,500 · air-gapped quoted | — | — | No — off-platform | Scoped installation engagement |
| Enterprise Plus | Negotiated | Negotiated | 50+ | No — off-platform | Custom contracts, multi-year, custom SLA |

### Market positioning sanity check

| Comparable | Their individual | Their per-seat |
|---|---|---|
| Sublime Merge | $99 individual (one-time) | — |
| Aseprite | $19.99 (one-time) | — |
| Krita | $9.99 (one-time) | — |
| Cody (Sourcegraph) | $9/mo | $49/seat/mo enterprise |
| GitHub Copilot | $10/mo individual | $19/seat/mo business |
| Cursor | $20/mo | — |
| GitLab Premium | — | $29/seat/mo |
| JetBrains Teams | — | $24/seat/mo |
| **SourcePrep** | **$29 one-time (perpetual)** | **$9 Teams / $24 Enterprise** |

The Pro anchor is now **one-time-priced near-sublime tools** (Sublime
$99, Aseprite $19.99, Krita $9.99) — a signed, packaged binary of
otherwise-free-to-build software is a real, defensible one-time good;
local/convenience tools with no recurring-cost service should not be
subscriptions (the 2026-07-18 reversal of the monthly tier). Teams at $9
is intentionally well below Copilot Business ($19) and Sourcegraph
Enterprise ($49). Enterprise at $24/seat sits at JetBrains Teams parity
and below GitLab Premium ($29).

---

## Lemon Squeezy product configuration spec

**4 products to configure in Lemon Squeezy** (monthly Pro dropped
2026-07-18):

| LS Product Name | Type | Price | Variant | Webhook unlock |
|---|---|---|---|---|
| `prep-pro-perpetual` | One-time | $29 (name-your-price floor) | Single | `tier=pro`, `mode=perpetual` |
| `prep-teams-monthly` | Subscription, variable quantity | $9/seat/mo | Min qty 3 | `tier=teams`, `mode=monthly`, `seats=N` |
| `prep-teams-annual` | Subscription, variable quantity | $97/seat/yr | Min qty 3 | `tier=teams`, `mode=annual`, `seats=N` |
| `prep-enterprise-annual` | Subscription, variable quantity | $288/seat/yr | Min qty 15 | `tier=enterprise`, `mode=annual`, `seats=N` |

**Off-platform (Magnetic Anomaly LLC direct invoicing):**

- Enterprise Setup (remote included · on-site from $3,500 · air-gapped quoted)
- Enterprise Plus contracts (negotiated)
- Architecture review engagements ($25k)

**Phase 1 OSS launch needs 0 LS products configured** (Pro is not live
at the first launch). **Pro go-live needs only `prep-pro-perpetual`.**
**Phase 2 launch adds the remaining 3.**

> **Open item (Eric, A5):** confirm the current Lemon Squeezy customer
> count before the public relicense. If >0 paying customers exist, a
> customer notice is required before changing terms; if 0, document the
> all-clear. (`PRODUCT_TIER_MAP` in `lemon_squeezy.py` is empty, so the
> count is not derivable from code.)

---

## Two-part release sequencing

### Phase 1 — OSS launch (Pro comes online later)

**Ships when:** Phase 143 (docs cleanup + two-repo mirror) and Phase 144
(trademark + DCO + legal hygiene) are complete, the root `LICENSE` is
swapped to Apache-2.0 (after the IP Assignment), and the Ed25519
license crypto is fixed.

**Phase 1 scope = OSS only.** Pro does **not** go live at the first
launch: the Lemon Squeezy checkout is unwired (`PRODUCT_TIER_MAP`
empty), the Ed25519 license crypto is being replaced (forgeable shipped
verifier key + mismatched generator↔verifier keypair), and code-signing
has lead time (Apple org enrollment + D-U-N-S ~2–4 wk; Windows Azure
Artifact Signing org path is blocked for a new LLC — individual path or
OV cert). The marketing pricing page already reflects this (no live
"Buy Pro" CTAs).

**Engineering work required for OSS launch:**
- ✅ Root `LICENSE` → Apache-2.0; metadata flips (`pyproject`, `Cargo`,
  npm); `NOTICE`; `CONTRIBUTING` + DCO check; `SECURITY.md`; `CHARTER.md`
- ✅ Curated public mirror via `tools/build_public_mirror.py` (allowlist
  + denylist-regex gate + fresh initial commit)
- ✅ Public `README` + `CONTRIBUTING` + `SECURITY` + `HISTORY.md` + ADRs
- ✅ `oss-ci.yml` green on a fresh clone with no secrets

**Engineering work required before Pro goes live (post-OSS-launch):**
- Signed Tauri installer pipeline (Apple notarization, MS signing) — infra designed in `DISTRIBUTION_AND_REVENUE_PLAN.md`
- Ed25519 license key + Lemon Squeezy webhook integration — **after the Phase 146 crypto fix**
- `prep auth` CLI command for license activation
- 1 LS product configured (`prep-pro-perpetual`)

**Marketing/launch activities** (per existing
`IMPLEMENTATION_PLAN.md` Parts D–H):
- gstack integration (Part D)
- Reproducible benchmark + demo video (Part E)
- Show HN (Part F)
- Technical blog posts (Part G)
- Direct acquirer/employer outreach (Part H)

**Teams + Enterprise marketing posture during Phase 1:** "Coming
soon. Sign up for the Teams waitlist." Capture interest, build
demand, don't promise dates beyond "Q3 2026."

### Phase 2 — Teams + Enterprise launch

**Ships:** 6–10 weeks after Phase 1, targeting Q3 2026.

**Engineering work required:**
- Hosted multi-tenant backend (proprietary repo, new)
- Authenticated push API for OSS daemon → hosted backend (embeddings + graph deltas only, never source)
- SSO integration: Google Workspace, Okta SAML, Microsoft Entra
- RBAC system (project visibility, audit log read, policy editing)
- Audit log storage (immutable, queryable, exportable)
- Centralized policy + budget governance UI (extends existing engine module)
- Air-gapped deployment scripts (docker-compose + setup guide)
- 3 additional LS products configured (`prep-teams-monthly`, `prep-teams-annual`, `prep-enterprise-annual`)
- Off-platform invoicing playbook for Enterprise Setup engagements

**Marketing/launch activities:**
- Updated pricing page on sourceprep.io with all tiers visible
- Teams launch announcement (blog post, gstack community ping, direct outreach to waitlist)
- Enterprise pilot conversations (Eric direct, 3–5 named targets)
- One Enterprise installation engagement to validate the playbook

---

## IP inventory and acquisition framing

**What is salable (proprietary, never published):**

| Asset | Why it's salable |
|---|---|
| Trademark "SourcePrep" (after Phase 144 registration) | Buyer can't legally call their fork SourcePrep. Single most important salable IP asset. |
| Domain `sourceprep.io` + brand assets | Owned by Eric / Magnetic Anomaly LLC |
| Hosted multi-tenant backend codebase | Apache 2.0 only covers what's published; this stays proprietary |
| Tauri signing keys + notarization + auto-update server + license key infra | Proprietary cert chain + delivery infra |
| Customer list + active contracts | Never in repo |
| Private strategic/roadmap docs (Phase 142, ACQUIRER_MAP, DISTRIBUTION_AND_REVENUE_PLAN) | Stay private after Phase 143 docs cleanup |
| Eric's expertise + reputation | The acqui-hire asset |
| Community + GitHub stars + Show HN signal | Distribution position the buyer inherits |

**What is NOT salable (Apache 2.0 = anyone can fork):**

- The OSS engine, daemon, CLI, MCP server code itself
- All prompts in the OSS surface
- Documentation that ships in the public mirror

### Two deal shapes to optimize for

**Shape A — Acqui-hire** (primary Phase 142 thesis):

- Target: Anthropic, OpenAI, Cognition, Cursor, Sourcegraph
- Structure: Eric joins as senior IC ($300–800k TC), sign-on tied to deal
- Asset acquisition: Magnetic Anomaly LLC sells trademark, domain, hosted infra, customer book for $X00k–$3M (depending on Teams ARR at time of deal)
- Buyer gets: Eric + brand + community/distribution + the right to integrate or sunset the product
- Pattern reference: Astral → OpenAI (March 2026), Bun → Anthropic (December 2025), OpenClaw → OpenAI (April 2026)

**Shape B — Strategic asset acquisition** (less likely, larger):

- Target: Sourcegraph, JetBrains, GitHub-adjacent dev tool companies
- Structure: Asset purchase of trademark + hosted infra + customer book + integration rights
- Eric on 2–3 year earnout for transition
- Valuation tracks Teams/Enterprise ARR — 5–10x at modest ARR levels
- Requires Phase 2 paid tier traction first; not viable until 3–6 months post-Phase-2 launch

---

## Prerequisites

These phases must complete before Phase 1 ships:

### Phase 143 — Docs cleanup + two-repo split

1. Triage every doc in `docs/` into 4 buckets:
   - **Strategic IP** (never public): Phase 142 + Phase 143/144, DISTRIBUTION_AND_REVENUE_PLAN, ACQUIRER_MAP, PARALLEL_LANES
   - **Active engineering planning** (never public while in flight): current PhaseNN_* dirs for unshipped work
   - **Shipped engineering decisions** (public as ADRs): distill past phases into `docs/adr/NNNN-*.md` — Phase 113 (data dir), Phase 117 (scoped rebuild), Phase 139 (embedder), Phase 141 (swarm-cache integrity)
   - **Research/technical writing** (public, polished): EPISTEMOLOGY_SCORING, CURATED_TRACEABILITY_FRAMEWORK, RUST_ENRICHMENT_ANALYSIS → `docs/research/`
2. Set up two-repo structure:
   - Private dev repo stays at `/Volumes/4TB-BAD/HumanAI/CoDRAG/` — full history, all internal docs
   - Public mirror = new GitHub repo with single "Initial public release" commit
   - Establish sync workflow (curated public commits, periodic mirror updates)
3. Rewrite top-level `docs/README.md` as a clean front door
4. Decision: GitHub org name (`sourceprep` if available, fallback TBD)

### Phase 144 — Legal pre-launch

1. **Trademark filing** for "SourcePrep" — USPTO Class 9 + Class 42, ~$700 in fees + $1,500–3,000 attorney
   - Step 1: USPTO TESS search + common-law search (Google, GitHub, npm, PyPI) — 30 min
   - Step 2: 1-hour trademark attorney consult — $250–500
   - Step 3: File application before any public launch
2. **Patent attorney consult** (~$400–800, 1 hour) — assess whether anchor-overlap concept clustering, AIMD concurrency control, or other methods warrant provisional filings
   - Default action: skip patents, use defensive publication via blog posts (establishes prior art at $0 cost)
   - Carve-out: file provisional ($1,500–3,000) only if attorney identifies clearly novel + commercially meaningful method
3. **Magnetic Anomaly LLC** operating agreement review — ensure entity is structured to receive acquisition
4. **DCO (Developer Certificate of Origin)** setup — `Signed-off-by` per-commit sign-off (not a CLA); DCO check GitHub Action; see `LICENSING_RECOMMENDATION.md` (DCO, not CLA — permanent license, no relicense option preserved)
5. **ToS + privacy policy** for `sourceprep.io` (especially needed before Phase 2 hosted backend ships)
6. **Apache 2.0 NOTICE** + dependency license audit (`cargo deny check licenses`, `pip-licenses`, `license-checker`) — blocking CI step
7. **`LICENSE-AUDIT.md`** private doc recording the audit + date (legal defense if challenged)

**Total Phase 144 cost estimate:** $2,000–5,000 with one consolidated attorney engagement. ~2–3 weeks calendar (mostly waiting on attorney).

---

## Open questions (decide before Phase 1 ships)

1. **Hosted backend infra cost spike.** Before pricing locks for Phase 2, run a 1-week spike to put a daemon on Fly.io / Railway with one test repo and measure actual $/repo/month for indexing + serving. This validates the $15 Teams seat economics.
2. **Hosted backend privacy boundary.** Confirm: embeddings + graph metadata only, never raw source. Write the privacy doc before Phase 2 ships.
3. **GitHub org name.** **DECIDED 2026-07-17:** stay under `MagneticAnomaly` (matches the bank entity + `magneticanomaly.llc` brand); do **not** stand up a `sourceprep` org yet — optionally grab & sit on `github.com/sourceprep` for a future C-corp/VC path. Storefront = `MagneticAnomaly/SourcePrep` (curated one-way mirror of the `MagneticAnomaly/SourcePrep-Private` workshop). See `REPO_TOPOLOGY.md`.
4. **Repo name within org.** Workshop `MagneticAnomaly/SourcePrep-Private`; storefront `MagneticAnomaly/SourcePrep`.
5. **Existing paid customers** (per SCRUTINY §11). Audit Lemon Squeezy for any current Pro subscribers. If non-zero: customer notice + decide grandfathering. If zero: document the all-clear.
6. **Annual contracts processing.** Lemon Squeezy supports annual subscriptions but the Teams variable-quantity annual variant needs verification. Confirm before Phase 2 LS setup.
7. **Refund policy** for annual contracts. Industry standard: pro-rated refund within 30 days, none after. Confirm before listing.
8. **Per-seat-overage handling** for Teams. If a 3-seat customer adds a 4th teammate mid-cycle, does LS auto-bill the new seat or wait until renewal? Confirm with LS support.

---

## Open questions explicitly deferred to a later phase

- Federated identity beyond SSO (SCIM auto-provisioning)
- Multi-region hosted backend (US-only at launch)
- SOC 2 certification (likely required before $24/seat Enterprise customers will sign — budget $20-40k + ~6 months calendar for the Type 1 audit)
- Dedicated hosted instance for Enterprise (vs shared multi-tenant)

---

## Relationship to existing docs

| Existing doc | Phase 142 relationship |
|---|---|
| `docs/DISTRIBUTION_AND_REVENUE_PLAN.md` (AUTHORITATIVE, 2026-02-12) | Stays authoritative for Lemon Squeezy mechanics, Ed25519 license key design, Apple/MS App Store posture, payment flow. **Tier table in section 7 is superseded by this doc.** Section 9 ("Superseded Documents") to be updated at end of Phase 142 with pointer here. |
| `docs/Phase142_OSS-First/README.md` | Phase 142 framing. This doc is the open-core split sub-decision. |
| `docs/Phase142_OSS-First/STRATEGY.md` | Open-core layering principle (§"Open-core layering: the OSS / Pro boundary"). This doc finalizes the boundary table. |
| `docs/Phase142_OSS-First/SCRUTINY.md` | §6 (history rewrite), §10 (anti-rug-pull), §11 (existing customers), §18 (Pro tier awkwardness) — all addressed by decisions in this doc. |
| `docs/Phase142_OSS-First/IMPLEMENTATION_PLAN.md` | Parts A–H sequencing remains valid. Add: Phase 143 + Phase 144 as prerequisites; LS product reconfiguration step in Phase 1; hosted backend build in Phase 2. |

---

## Decision audit trail

- **2026-05-30** — Open-core boundary table finalized. Pro = $7/$70, Teams = $15/$144, Enterprise = $50/seat annual + 10-seat min + $5k setup. Premium prompts cut. Two-part release confirmed (Phase 1: OSS+Pro; Phase 2: Teams+Enterprise, 6–10 weeks later). CLA = Apache ICLA. Repo strategy = two-repo (fresh init for public mirror).
- **2026-07-17/18** — **Re-hardened** (`DECISION_MEMO_2026-07-17.md` Part 0, `LICENSING_RECOMMENDATION.md`, `REPO_TOPOLOGY.md`, live marketing pricing). Pro → $29 one-time perpetual (monthly dropped; not live at first OSS launch). Teams → $9/$97. Enterprise → $24/seat annual, 15-seat min, setup remote-included/on-site from $3,500. CLA → DCO (permanent, no relicense). Org → stay `MagneticAnomaly`. Phase 1 → OSS only. This doc designated the **single source of truth** for pricing; `DISTRIBUTION_AND_REVENUE_PLAN.md` + `PRODUCT_AND_BUSINESS_OVERVIEW.md` pricing sections SUPERSEDED.
- **2026-07-19** — Reconciliation applied to this file (stale 2026-05-30 paragraphs above may still carry old numbers; the TL;DR + Pricing table govern — full paragraph reflow deferred to the Stream 5 contradiction sweep).
- **Pending** — Phase 143 kickoff, Phase 144 kickoff, Ed25519 crypto fix (Phase 146), Lemon Squeezy reconfiguration to new pricing, Lemon Squeezy customer-count confirmation (Eric, A5).
