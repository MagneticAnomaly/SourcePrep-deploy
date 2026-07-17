# OSS Marketing-Site Readiness Briefing — 2026-07-17

> **Status:** briefing for the marketing team + Eric. PRIVATE — Phase 143
> keep-private bucket. Produced from a read-only audit of the marketing/docs/
> payments sites, the OSS-marketing worktrees, and the design spec.
>
> **HARDENING UPDATE (2026-07-17):** two items below are now decided and override
> the original text:
> - **Pricing:** Pro is **$29 one-time perpetual** (no subscription). Wherever this
>   briefing says "correct $79 → $70," the real target is **"$29 one-time, drop the
>   $7/mo entirely."** No Founder's Edition.
> - **Pro at launch:** Pro is **kept** (not "deferred forever"), BUT it will **not
>   be live at the first OSS launch** — checkout is unwired, license crypto is void,
>   code-signing has lead time. So the guidance is unchanged in practice: **no live
>   Buy-Pro CTAs / checkout at Phase 1**; frame Pro as "coming — a $29 one-time
>   packaged app," not as buyable yet.
> - **License** is still undecided (deep-research underway) — no OSS-license badge
>   or "open source" claim until it lands.

---

## 1. Bottom line

The marketing team is **blocked from publishing and only partially clear to start
drafting.** They can begin scoped, review-locally work in the OSS worktrees —
reframing copy, reconciling every price, deleting false claims — but they **cannot
finalize or deploy a single OSS-facing page**, because the core positioning
depends on decisions only Eric can make. **The single biggest gate is the license
decision (Apache vs AGPL);** until it's answered *and the repo relicenses*, "open
source" is not yet a true statement (root `LICENSE` is still commercial). Four more
gates sit alongside: Pro live-vs-not at launch, the customer-count relicense audit,
the GitHub org/repo name + public mirror (doesn't exist yet), and trademark
(now settled). Net: **start the reframe, publish nothing.**

## 2. Must finalize first

**Eric-gated (no copy can be finalized without these):**
- **License: Apache vs AGPL** — every OSS badge, footer license line, LICENSE link,
  Terms rewrite, and the ~6 spec'd pages that hardcode "Apache 2.0" are undeployable
  until the name is fixed; any "open source" claim is false today.
- **Pro live at launch or not** — determines whether the pricing page shows a
  buyable Pro tier and whether `/download` shows a Pro path. (Hardened: kept but
  not live at Phase 1.)
- **Customer-count / relicense audit** — any "now open source" post relicenses
  previously-sold proprietary licenses; if ≥1 customer bought, that's a
  notice/grandfather/refund obligation *before* any public relicense message.
- **Public repo name + mirror** — the site links pervasively to
  `MagneticAnomaly/SourcePrep-MCP`; per `REPO_TOPOLOGY.md` the flagship is
  `MagneticAnomaly/SourcePrep` and the stub is archived — links must update, and
  the curated public mirror doesn't exist yet.

**We can finalize for them now (mechanical, not Eric-gated):**
- One canonical price sheet (Pro **$29 one-time**, no subscription, no Founder's
  Edition; Teams/Enterprise = Phase-2 "coming soon").
- A "retire the 3-project free tier" copy spec → unlimited, self-hosted OSS.
- Accuracy fixes that need no decision: correct "no phone-home" (code polls every
  7 days), remove the false "Also on the Microsoft Store" pill, reconcile the
  entity name ("Magnetic Anomaly LLC" vs "SourcePrep Inc."), and pick one install
  story (`/download` vs `/setup` disagree).

## 3. Must communicate — DO / DON'T

**DON'T:** publish any OSS-license badge/name yet · ship live Buy-Pro/checkout CTAs
· flip `IS_BETA_MODE` to false (it exposes the whole paid ladder + checkout) ·
present Teams/Enterprise as buyable (Phase 2; backend is stubs) · post any "now open
source / now free" announcement before the customer-count all-clear · publish
technical method deep-dives (AIMD concurrency) — forfeits patents · touch the home
hero · push `main`/trigger Netlify (each push = ~4 builds; deploy only on the
explicit flag).

**DO:** price only from the canonical sheet (Pro **$29 one-time**) · delete every
3-project/Free-tier claim · reframe paid as *convenience + hosting + support*, never
"OSS is the crippled version" · lead with plain-language outcomes (jargon is
supporting detail) · keep acqui-hire/IC framing off public copy · keep codenames out
(`CoDRAG`/`RunPrep`/`~/.runprep`) · fix the flat-wrong claims (phone-home, MS Store,
install story) · batch changes into one gated deploy.

## 4. In-flight work status

There is **no drafted OSS copy** — the entire in-flight artifact is a 184-line
design spec (`docs/superpowers/specs/2026-07-17-oss-marketing-copy-design.md`).
Both worktrees are effectively at `main` (`oss-launch-copy` == main; `oss-open-source`
== main + only the spec commit). **Wasted-effort risk is low** (nothing shipped),
but the spec bakes in two now-wrong assumptions and must be revised before anyone
writes pages:
- ⚠️ Hardcodes "Apache 2.0" across ~6 pages — blocked on the license decision.
- ⚠️ Treats Pro as a live Phase-1 tier with working checkout — wrong; Pro isn't live
  at launch and checkout is unwired. (Also update Pro pricing to $29 one-time.)
- ✅ Gets right (preserve): retires the 3-project Free tier, single-source pricing,
  SourcePrep/prep brand split, "Magnetic Anomaly LLC" entity, plain-language voice.

## 5. File-level gotchas (wrong claims live today)

- **Stale price** (was $79; now $29 one-time): `marketing/src/lib/pricing.ts:27`,
  `marketing/src/app/faq/page.tsx:339`, `payments/src/app/page.tsx:26`.
- **Retired 3-project free claim:** `marketing/src/app/pricing/page.tsx:79,84`;
  `terms/page.tsx:86`; `download/page.tsx:84`;
  `docs/src/app/getting-started/installation/page.tsx:81` (also sells a non-existent
  Lemon Squeezy activation flow — the single most out-of-date block on the site).
- **False/undecided license claims:** root `LICENSE:1` (proprietary today);
  `pyproject.toml:10` (falsely "MIT"); `docs/src/app/mcp/paperclip/page.tsx:278`
  ("It's MIT-licensed"); `payments/` has no LICENSE file; `terms/page.tsx:104`
  forbids reverse-engineering/redistribution.
- **Live-looking Pro CTAs (unwired checkout):** `pricing/page.tsx:160,200,255`
  behind `IS_BETA_MODE`; `pricing.ts:160` placeholder checkout URLs;
  `payments/src/app/page.tsx:28`; `payments/src/app/api/recover/route.ts:14` is an
  unconditional mock ("MVP: Simulate success").
- **"No phone-home" contradiction:** `security/page.tsx:143`, `pricing/page.tsx:300`,
  `faq/page.tsx:339` (code polls every 7 days, downgrades after 30).
- **False availability / paid-gate docs:** `download/page.tsx:83` ("Also on the
  Microsoft Store"); `docs/cli/config/page.tsx:82` (`PREP_TIER`); several docs
  guides paywall real features / require Team/Enterprise license activation.
- **Codename leaks:** live marketing/docs/payments copy is **CLEAN** (0 hits). The
  codename problem lives in adjacent surfaces the mirror pulls from (~308 docs,
  `@codrag/ui` lockfile, `~/.runprep` paths, live-tree `codrag.key`) — a
  mirror-build concern, not marketing copy.
- **Inconsistencies:** entity name drift; three different GitHub repo slugs
  (`SourcePrep-MCP`, `SourcePrep`, `SourcePrep-deploy`) — all resolve to
  `MagneticAnomaly/SourcePrep` per `REPO_TOPOLOGY.md`.

## 6. Ready-to-send note to the marketing team

> **Subject: OSS site work — start drafting, publish nothing yet**
>
> Team — we're converting SourcePrep to open source. You can start reframing copy
> in the OSS worktrees now, but a few things are still my call, so nothing goes
> live until I say. Read locally, don't push.
>
> **DON'T:** call it "open source" or put any license badge on the site yet (license
> isn't final; repo is still proprietary today) · build any "Buy Pro"/checkout
> buttons (Pro's coming but not live at launch — checkout is half-built and points
> nowhere real) · flip `IS_BETA_MODE` off · market Teams/Enterprise as buyable (later
> phase — "coming soon/waitlist," no dates past Q3) · post any "we're now open source"
> announcement (I need to check prior-sales first) · publish technical deep-dives on
> our methods (can cost us patents) · touch the home hero · push to `main`/trigger
> Netlify (every push = ~4 builds; I'll deploy).
>
> **DO:** fix pricing to **$29 one-time** (Pro is a one-time purchase now, not a
> subscription — it's wrong in a few places) · delete every "3 projects/Free tier"
> limit (under OSS it's the full product, unlimited, self-hosted) · frame paid as
> *convenience + hosting + support*, never "OSS is the crippled version" · lead with
> what it does for the user in plain language · keep codenames out ("SourcePrep"
> everywhere users can see) · fix the wrong claims ("no phone-home" — we do poll;
> "Microsoft Store" — not yet; and pick one install story).
>
> The design spec is a good start but assumes Apache + Pro-at-launch — treat those
> as TBD until I confirm. Questions to me first.
>
> — Eric
