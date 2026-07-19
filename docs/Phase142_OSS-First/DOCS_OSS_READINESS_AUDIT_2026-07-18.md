# Docs-Site OSS-Readiness Audit — 2026-07-18

> **Status:** AUDIT + partial pass. Companion to `MARKETING_OSS_READINESS_BRIEFING.md`.
> Covers the public **docs website** only (`websites/apps/docs/`, the Next.js
> app router — 34 pages + shared config/layout). The marketing site was already
> passed on 2026-07-18 (`project_oss_marketing_branch` memory); the docs site had
> not been touched since May 2026 and still carried retired-tier, dead-flow, and
> wrong-repo-slug content.
>
> **Method:** 12-agent workflow (11 parallel reviewers over all pages + shared
> structure → 1 synthesizer), then a main-loop verification pass that reconciled
> agent findings against the live repo (CLI commands, license code, repo
> topology, marketing's current copy). Some agent-proposed "mechanical" fixes
> were **downgraded to UNCERTAIN** during verification — see §3.
>
> **Visibility:** PRIVATE — Phase 143 keep-private bucket (references the same
> strategic context as the marketing briefing).
> **Branch:** `main` (local only; not pushed — `[deploy]` gate respected).

---

## 0. TL;DR

The docs site is **close to OSS-launch-ready**. It is clean of codename leaks
(`CoDRAG`/`RunPrep`/`~/.runprep`: 0 hits) and makes **no** "open source" /
"Apache 2.0" product claim that would preempt the repo relicense — both
required invariants hold. Six safe mechanical fixes were applied this pass
(§2). The remaining work splits into:

- **1 license-gated item** (§1) — the paperclip page's "MIT-licensed" claim.
  Blocked on the Apache-2.0 relicense actually landing.
- **4 phone-home claims held after verification** (§3) — the agents flagged
  these as wrong based on the legacy `lemon_squeezy.py` polling code, but
  marketing's current security page already stakes a "no phone-home" stance
  and says the license crypto is being replaced. Docs match marketing; the
  real item is a **code-cleanup** task, not a docs edit.
- **7 dead `SourcePrep-deploy` deep links** (§4) — point at an empty subtree
  repo; the templates actually live at `public/sourceprep-deploy/` locally,
  but whether they're curated into the storefront is an Eric mirror-allowlist
  decision.
- **12 product-decision items** (§5) — tier paywalls under OSS, legacy/hidden
  pages still in the sidebar, an unverified Ollama slug, and a few voice/completeness
  nits. These are Eric's call; do not guess.

---

## 1. License-gated (1 item — blocked on the relicense)

The repo root `LICENSE` is still **proprietary commercial** ("COMMERCIAL SOFTWARE
LICENSE AGREEMENT … NO REDISTRIBUTION"). The Apache-2.0 + DCO decision
(2026-07-18, `LICENSING_RECOMMENDATION.md`) is **decided but not applied**.
Until it lands, no public page may assert a specific OSS license.

### L1. `mcp/paperclip/page.tsx:278` — false "MIT-licensed" claim
- **Current:** `…in the SourcePrep repository. It&apos;s MIT-licensed.`
- **Problem:** The plugin's `package.json` declares `license: "MIT"`, but there
  is **no LICENSE file** in `packages/paperclip-plugin-prep/` — the outbound
  license is the proprietary root LICENSE. So "MIT-licensed" is a false legal
  statement today. (The audit's three-way license-identity inconsistency:
  root LICENSE = proprietary, `pyproject.toml` = MIT, plan = Apache-2.0.)
- **Once relicensed, should read:** `…in the SourcePrep repository. It is
  licensed under Apache-2.0 (with a Developer Certificate of Origin sign-off
  requirement) — see the repository LICENSE for details.`
- **Optional safe interim:** replace with a license-neutral pointer
  (`…see the repository LICENSE for licensing details.`) that is true today
  regardless of which license is currently in the tree. **Not applied** because
  the marketing site already asserts "Apache 2.0" forward-looking; Eric may
  prefer docs match marketing once the relicense lands rather than carry a
  neutral placeholder now.

---

## 2. Mechanical fixes APPLIED this pass (6 edits, 5 files)

| # | File:line | Fix | Category |
|---|---|---|---|
| M1 | `getting-started/installation/page.tsx:81` | Removed retired **3-project Free tier** + "purchase a license" CTA; replaced with license-neutral "free to use, all features, unlimited projects, build it yourself from source; paid tiers coming soon." | OSS-readiness |
| M2 | `getting-started/installation/page.tsx:85` | Removed non-existent **Lemon Squeezy** activation flow + false "works fully offline" claim; replaced with "license activation/checkout for paid tiers not yet available." | Wrong fact |
| M3 | `how-it-works/compression/page.tsx:39` | "Free tier — available on all tiers including Free" → "No extra license — LOD compression is part of the core engine on every plan, including the $0 self-hosted build." | OSS-readiness |
| M4 | `guides/codebase-audit/page.tsx:347` | `prep audit` (not a real CLI command; verified absent in `cli.py` — only `opportunities` + `hr-audit` exist) → "trigger an audit via the MCP `prep_audit` tool, the REST API, or the dashboard Audit panel." Aligns with the page's own quick-start. | Wrong fact |
| M5 | `guides/enterprise-deploy/page.tsx:24` | Dropped "Requires a Team or Enterprise license." sentence. Under OSS the engine is full-featured; paid tiers are convenience/hosting/support, not gated engine features. | OSS-readiness |
| M6 | `app/ClientLayout.tsx:60` | Footer GitHub social link `MagneticAnomaly/SourcePrep-MCP` (stub to be archived per `REPO_TOPOLOGY.md`) → `MagneticAnomaly/SourcePrep` (storefront; matches marketing footer). | Wrong fact |

All replacements are **license-neutral** — none assert "open source" or
"Apache 2.0." Typecheck: docs app `tsc --noEmit` clean after edits (see commit).

---

## 3. Phone-home / offline claims — HELD (not a docs problem)

The workflow flagged four enterprise-deploy claims as `C_WRONG_FACT` and
proposed adding "periodic license-server recheck (~7 days)" detail. **Verification
downgraded all four to "no change needed"** — the proposed fix would have
**introduced** a contradiction with marketing.

### The conflict
- **Code** (`src/prep/core/lemon_squeezy.py:43-44`, `api/routers/license.py:214-217`):
  legacy license path validates every **7 days** and **downgrades after 30 days
  offline** (`VALIDATION_INTERVAL_SECONDS = 7d`, `GRACE_PERIOD_SECONDS = 30d`).
- **Marketing** (`marketing/src/app/security/page.tsx:142-148`, current after the
  2026-07-18 OSS pass): *"no keys, no activation, nothing that could phone home. Pro
  activation will be a single online key exchange; after that, SourcePrep will store
  a signed Ed25519 license file locally and verify it offline — **no periodic
  phone-home, no subscription heartbeat**. (Pro is coming soon; the current license
  crypto is being replaced before launch.)"*

Marketing has already staked the final position: **no phone-home.** The
`lemon_squeezy.py` polling code is the **old crypto being replaced**, not the
shipping behavior. The docs' current text is consistent with marketing:

| File:line | Current docs text | Verdict |
|---|---|---|
| `enterprise-deploy:248` | "No telemetry. SourcePrep does not phone home, collect usage data, or send any information to external servers." | **Keep** — matches marketing. |
| `enterprise-deploy:249` | "No cloud dependency. The GPU image includes everything needed to run completely offline." | **Keep** (enrichment-pipeline scope is accurate; license check is being removed). |
| `enterprise-deploy:252` | "Offline license activation … No internet required after activation." | **Keep** — matches marketing's "verify offline." |
| `enterprise-deploy:287` | "Ed25519-signed license files, no phone-home after activation." | **Keep** — matches marketing. |

### Real action item (CODE, not docs)
Before OSS launch, **remove or stub the legacy `lemon_squeezy.py` /
`api/routers/license.py` 7-day polling + 30-day downgrade path** so the code
matches the "no phone-home" claim marketing and docs both make. This is tracked
by Phase 146's license-crypto replacement, not by a docs edit. Flagged here so
the contradiction is visible in one place.

---

## 4. Dead `SourcePrep-deploy` links — HELD (Eric mirror-allowlist decision)

Seven links across `team-sync` and `enterprise-deploy` point at
`github.com/MagneticAnomaly/SourcePrep-deploy/tree/main/{modal,runpod,aws,…}`.
That GitHub repo is the **empty subtree-push target** (`HANDOFF.md:104`:
"both target repos are currently empty"). The deploy templates **actually live
locally** at `public/sourceprep-deploy/{modal,runpod,aws,github-actions}/`.

`REPO_TOPOLOGY.md` decides the storefront is `MagneticAnomaly/SourcePrep` but
does **not** say whether `public/sourceprep-deploy/` is in the curated mirror
allowlist. So the correct public URL for these templates is undecided.

**Links in question:**
- `guides/team-sync/page.tsx:191, 278, 385`
- `guides/enterprise-deploy/page.tsx:125, 171, 190, 446`

**Options for Eric:**
- (a) **Include `public/sourceprep-deploy/` in the storefront mirror** and
  repoint links to `https://github.com/MagneticAnomaly/SourcePrep/tree/main/public/sourceprep-deploy/{modal,runpod,aws}`.
  (Most consistent with "storefront = the public OSS subset.")
- (b) **Keep a separate `SourcePrep-deploy` repo** and populate it (push the
  subtree), leaving the links as-is.
- (c) **Remove the deploy-template deep links** from docs at launch (the prose
  still describes the setup; point users to the local `public/sourceprep-deploy/`
  path in the cloned repo instead of an external URL).

Not applied: repointing all seven to the flagship **root** (the synthesizer's
proposal) would turn "deployment templates" links into a generic repo link and
create a prose/link mismatch. Eric should pick the destination.

---

## 5. Product-decision / uncertain items (12 — Eric's call)

These are real but not safely auto-fixable. Do not edit without Eric's input.

### U1. `guides/team-sync/page.tsx:20` — headless indexing paywalled behind Team/Enterprise
"If you are on the Team or Enterprise tier, you can set up a headless indexing
server…" Under OSS the engine is full-featured, so paywalling a real feature is
misleading — but the Team Sync backend is stubs (Phase 2 "coming soon," not
buyable). The whole page may need a "coming soon" reframe, not just a tier-clause
drop. **Options:** (a) drop only the tier clause; (b) reframe the page as
"coming soon"; (c) reframe paid tiers as managed hosting + support.

### U2. `how-it-works/compression/page.tsx:294` — BERT language-compression paywalled + self-contradiction
"A future Pro feature will add language-aware compression…" but the roadmap box
at lines 299-301 says the feature "is built and available in the settings panel."
Title says "Coming Soon," body says "built and available." **Options:** (a) if it
ships in OSS, document as a core capability, drop "Pro"/"Coming Soon"; (b) if
unbuilt, describe as a roadmap item with no tier gating; (c) reconcile the
contradiction either way.

### U3. `guides/knowledge-scope/page.tsx:101` — auto-rebuild gated behind Pro
"Pro-tier users with auto-rebuild enabled get automatic debounced rebuilds."
Unknown whether auto-rebuild is actually license-gated in the OSS build or just
a Pro-default convenience. **Options:** (a) drop "Pro-tier" if it runs in OSS;
(b) keep but reframe as a convenience default, not a capability lock.

### U4. `how-it-works/dynamic-model-loading/page.tsx` — entire page may be legacy
The page documents dynamic model loading as a live feature and embeds a
`DemoAdvancedLLMSettings` panel. Per Eric's auto-memory this UI was classified
**LEGACY/hidden 2026-05-14** when LLM strategy shifted to Ollama-Cloud-first.
**Options:** (a) remove from docs nav + `sitemap.ts`; (b) rewrite to current
behavior; (c) relabel "Local LLM (Advanced)" and mark legacy.

### U5. `guides/models/page.tsx:121` — links to the legacy dynamic-model-loading page
The main models guide promotes a hidden feature. **Options:** (a) remove the
sentence; (b) replace with a neutral VRAM note; (c) keep if Eric confirms the
feature is still supported.

### U6. `config/docs.ts:28` — sidebar "Local LLM Setup" → legacy page
Sidebar top-level entry points at `/how-it-works/dynamic-model-loading`.
**Options:** (a) keep; (b) relabel "Local LLM (Advanced)"; (c) remove from
sidebar + `sitemap.ts`.

### U7. `config/docs.ts:58` — sidebar "BYOK Batch Processing" → legacy page
Per memory BYOK-batching was LEGACY/hidden 2026-05-14. The guide is still valid
how-to for users with their own keys. **Options:** (a) keep; (b) drop from
sidebar + `sitemap.ts`.

### U8. `how-it-works/embeddings/page.tsx:48` (also :189, `guides/models:151`, `embedder.py:64`) — unverified Ollama slug `manutic/nomic-embed-code`
`manutic` is not a known Ollama publisher; the public-registry slug for
nomic-embed-code is typically `nomic-embed-code` or `nomic-ai/nomic-embed-code`.
The slug is hardcoded in `embedder.py:64` as a dimension-mapping key, so it may
be an intentional private mirror — but the user-facing `ollama pull
manutic/nomic-embed-code` instruction would 404 on the public registry. **Needs
Eric to confirm the slug users should actually pull**, then update all four
sites consistently (docs + code).

### U9. `how-it-works/embeddings/page.tsx:38` — "Requires a GPU" too absolute
Ollama can run nomic-embed-code on CPU (slowly). Minor accuracy nit. **Options:**
(a) soften to "GPU recommended (CPU works but slowly)"; (b) keep if Ollama truly
refuses CPU for this model.

### U10. `guides/byok-batching/page.tsx:77` — "No data is sent to SourcePrep servers"
Narrowly true for BYOK build/code data (LLM API calls go direct to the user's
provider) but reads as a broad "no phone-home" assurance. Same legacy-polling
tension as §3. **Options:** (a) keep (the "Privacy Notice" context scopes it);
(b) scope explicitly ("your code is never sent — all LLM API calls go directly
to the provider you configured"); (c) add a license-polling footnote once §3
lands.

### U11. `app/page.tsx:63` — docs home lede leads with jargon
"Everything you need to build your epistemic graph." Voice rules say jargon is
supporting detail only. Borderline (it's a subhead, not h1; docs readers are
more technical). **Options:** (a) lead with outcome, demote "epistemic graph";
(b) keep — Eric's call on docs-home voice.

### U12. `cli/commands/page.tsx:99` — `--ide` value list incomplete
Docs list `cursor, windsurf, vscode, claude, all`; `mcp_config.py` also accepts
`claude-code, claude-desktop, jetbrains, gemini, antigravity, zed`. Every
listed value is valid — this is a completeness gap, not a wrong claim.
**Options:** (a) expand the list; (b) keep the curated subset and add "run
`prep mcp-config --help` for the full list."

---

## 6. What is already clean (no action)

- **Codename leaks:** 0 hits for `CoDRAG`/`RunPrep`/`~/.runprep` across the docs
  app. (The codename problem lives in adjacent surfaces the mirror pulls from —
  ~308 docs, `@codrag/ui` lockfile — not in docs-site copy.)
- **"Open source" / Apache / AGPL product claims:** none in docs. The two
  `open source` grep hits are false positives ("Open SourcePrep from your
  Applications folder" = verb phrase; "open-source models" = Qwen3/DeepSeek).
- **Entity name:** docs use "Magnetic Anomaly LLC" consistently (one `llc`
  casing nit at `ClientLayout.tsx:63` — `© 2026 Magnetic Anomaly llc.` should be
  `LLC`; not load-bearing, left for a cosmetic pass).
- **Internal sidebar links:** all sidebar `href`s resolve to real routes. The
  only orphan is `/guides/model-advisor` (routable, not in sidebar — legacy
  sibling of `/guides/models`; consider removing the route in a cleanup pass).
- **FAQ / Support sidebar links:** point at `MARKETING_URL/faq` and
  `/support`, both of which exist on the marketing app.

---

## 7. Recommended next steps (Eric-gated)

1. **Apply the relicense** (Apache-2.0 + DCO) to the repo, then apply **L1**
   (paperclip license line) and decide whether docs should mirror marketing's
   forward-looking "Apache 2.0" / "open source" framing in the installation
   Licensing section (currently license-neutral after M1/M2).
2. **Resolve §3** (legacy `lemon_squeezy.py` polling code) so the code matches
   the no-phone-home claim — this unblocks §3 docs and U10.
3. **Decide the deploy-template home** (§4 options a/b/c) and repoint the 7
   links.
4. **Decide the legacy-page set** (U4–U7): keep, demote, or remove
   dynamic-model-loading and byok-batching from the docs nav.
5. **Confirm the Ollama slug** (U8) and update docs + `embedder.py` together.
6. **Decide tier framing** (U1–U3) for features that are paywalled in docs but
   full-featured under OSS.