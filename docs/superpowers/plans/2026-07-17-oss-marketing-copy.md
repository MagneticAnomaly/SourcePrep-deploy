# OSS Marketing Copy Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Amended 2026-07-17 evening** per the amended spec (DECISION_MEMO Part 0,
> REPO_TOPOLOGY, LICENSING_RECOMMENDATION, reality-check audit). Supersedes
> the morning version: $29 Pro (no subscription), no live checkout CTAs in
> any state, MagneticAnomaly/SourcePrep URLs, undated coming-soon, Apache 2.0
> + DCO wording, truthfulness fixes added (Task 11b).

**Goal:** Rewrite the marketing site to current open-core positioning on the isolated worktree, reviewed locally at :3100 — nothing pushed or deployed.

**Architecture:** Worktree `.claude/worktrees/oss-marketing-copy`, branch `marketing/oss-launch-copy` (off local `main` `8c24245c`). Copy-only changes in `websites/apps/marketing/` plus new `src/lib/links.ts`. `IS_BETA_MODE` switchable; both states coherent; **no reachable checkout link in either state**.

**Tech Stack:** Next.js app router, npm workspaces + Turbo, Node 20 (`source ~/.nvm/nvm.sh && nvm use 20` before npm commands), Playwright MCP.

**Spec:** `docs/superpowers/specs/2026-07-17-oss-marketing-copy-design.md` (amended) — tier facts, hard rules, acceptance. Prices/tier names MUST match it exactly: OSS $0 Apache 2.0 / Pro **$29 one-time** (name-your-price $29 floor, 12 mo updates, works forever, optional ~$15/yr, coming soon) / Teams $15/seat mo or $144/seat yr, 3-seat min, coming soon undated + waitlist / Enterprise $50/seat mo annual, 10-seat min, coming soon.

**Hard rules (gate every task):**
- Never imply the OSS is feature-limited. No project-cap language.
- **No live purchase/checkout links in any flag state** (crypto void + checkout unwired). Pro CTA = "Coming soon — get notified" mailto.
- No dated promises ("Q3 2026" is dead). Undated "coming soon".
- Apache 2.0 named; contribution mentions cite DCO sign-off, never CLA.
- Hero untouched; no `packages/ui` edits. Entity Magnetic Anomaly LLC. Brand "SourcePrep" (code names `prep` only). Plain-language-first; trim redundancy.
- No `git push`, ever. Commits inside the worktree only (Tasks 3+).

---

### Task 1: Worktree + branch — ✅ DONE
Worktree at `.claude/worktrees/oss-marketing-copy`, branch `marketing/oss-launch-copy` @ `8c24245c`, clean, git-ignored location.

### Task 2: Isolated local viewing environment — ✅ DONE
Deps installed (Node 20.20.1). Dev server: `cd websites/apps/marketing && npm run dev -- -p 3100` → http://localhost:3100 verified 200; baseline screenshot `.playwright-mcp/baseline-home-3100.png`.

### Task 3: Shared links constant

**Files:** Create: `websites/apps/marketing/src/lib/links.ts`

- [ ] **Step 1:** Create:

```ts
// Public GitHub repo (REPO_TOPOLOGY.md, DECIDED 2026-07-17).
// If the org/repo name changes, change it here only.
export const GITHUB_REPO_URL = "https://github.com/MagneticAnomaly/SourcePrep";
```

- [ ] **Step 2:** Marketing workspace `npm run typecheck` passes.
- [ ] **Step 3:** Commit: `feat(marketing): shared GitHub repo URL constant`.

### Task 4: Pricing page

**Files:** Modify: `websites/apps/marketing/src/app/pricing/page.tsx`, `src/lib/pricing.ts`, `src/app/pricing/layout.tsx:5`

- [ ] **Step 1:** Read all three files. Keep card/grid structure and `IS_BETA_MODE` (`page.tsx:29`).
- [ ] **Step 2:** Replace tier data (wording is the copy; map into existing card props):
  - **Open Source — $0 — "The full product. Apache 2.0."** Bullets: full engine, daemon, CLI, MCP server, dashboard, VS Code extension; unlimited projects — every capability and prompt ships open source; local-first — your code never leaves your machine; install with pip, brew, or build from source; community support on GitHub. CTA beta-ON: existing Request-Beta mailto; beta-OFF: "View on GitHub" → `GITHUB_REPO_URL`.
  - **Pro — $29 one-time — "Convenience, not capability."** Bullets: signed, notarized installers for macOS and Windows; automatic updates — 12 months included, the app is yours forever; keep updates coming for ~$15/yr after that (optional); pay what you want above the $29 floor; email support (5-business-day response); prefer to build from source? That stays free. CTA BOTH states: "Coming soon — get notified" mailto (subject `Pro notify`). No checkout link.
  - **Teams — $15/seat/mo, 3-seat minimum — "Coming soon."** Bullets: one shared, always-fresh index per repo; SSO (Google, Okta, Microsoft Entra); role-based access and audit logs; priority support channel; annual $144/seat/yr (20% off). CTA: "Join the waitlist" mailto (subject `Teams waitlist`).
  - **Enterprise — $50/seat/mo, annual, 10-seat minimum — "Coming soon."** Bullets: everything in Teams; air-gapped deployment; named contact + monthly office hours; setup assistance available. CTA: "Talk to us" mailto.
- [ ] **Step 3:** Below grid, privacy line: "Teams syncs embeddings and graph metadata only — never your source code."
- [ ] **Step 4:** Remove 3-project/Free-tier/license-management framing, PPP band display, `$79`/`$7/mo` strings, and the trust-strip "macOS, Windows & Linux" (`:360`) → "macOS & Windows (Linux planned)". In `pricing.ts`: leave PPP/LS mechanics compiled but unreferenced by the page; comment at `LS_CHECKOUT_URLS`: `// Checkout deliberately unwired: license crypto void (Phase 146 N1) + LS products unconfigured. Do not re-link without fixing both.`
- [ ] **Step 5:** `layout.tsx:5` metadata → "SourcePrep is free and open source (Apache 2.0). Pro adds signed installers and auto-update — $29 one-time, coming soon."
- [ ] **Step 6:** Verify both flag states at :3100/pricing (restore `IS_BETA_MODE = true` before commit). `npm run typecheck`.
- [ ] **Step 7:** Commit: `feat(marketing): open-core pricing page ($29 Pro, no live checkout)`.

### Task 5: FAQ

**Files:** Modify: `websites/apps/marketing/src/app/faq/page.tsx` (anchors :20, :44-65, :275, :297, :334-342)

- [ ] **Step 1:** `:334-342` "Why pay for this?" →

> SourcePrep is free and open source under Apache 2.0 — the full product, not a limited edition. Pro is a $29 one-time purchase for convenience: signed installers, automatic updates, and email support. Teams adds hosted infrastructure — a shared index your whole team queries — that you'd otherwise run yourself. That's what funds development. Not your data.

- [ ] **Step 2:** `:275` → the open-source version makes no license calls; only the Pro installer makes a single HTTPS call during activation.
- [ ] **Step 3:** `:20` → "It works in the open-source version — every capability ships open source." Sweep the file: `rg -in 'free tier|3 projects|perpetual|\$79|\$70|\$7/mo' src/app/faq/` and fix hits with spec framing.
- [ ] **Step 4:** Truthfulness: `:297`, `:338` "15+ languages" → "Python, TypeScript/TSX, JavaScript, Go, Rust, Java, C, and C++"; `:44-65` scope the ~1,500-token figure to per-query search context and delete "under 1%" (ambient budgets reach ~12.5K tokens on Claude Code).
- [ ] **Step 5:** Verify :3100/faq both states. Commit: `feat(marketing): FAQ for open-core model + factual fixes`.

### Task 6: Security page

**Files:** Modify: `websites/apps/marketing/src/app/security/page.tsx` (anchors :116-117, :138-147, :250-252, :258-266, :281-282)

- [ ] **Step 1:** `:138-147` "Offline Verification" scoped to Pro installer; OSS has no license infrastructure.
- [ ] **Step 2:** `:116-117` outbound table: `/activate-license` marked "Pro installer only".
- [ ] **Step 3:** `:250-252` collected data: license key / machine ID "Pro only — the open-source version collects nothing."
- [ ] **Step 4:** `:258-266`, `:281-282` payments/retention kept, scoped to paid tiers.
- [ ] **Step 5:** Verify :3100/security. Commit: `feat(marketing): scope license/activation copy to Pro on security page`.

### Task 7: About + compare pages

**Files:** Modify: `websites/apps/marketing/src/app/about/page.tsx:104-108`, `src/app/compare/prep-vs-greptile/page.tsx:97,108`, `src/app/compare/prep-vs-cursor-indexing/page.tsx:106-107`

- [ ] **Step 1:** About card →

> Own your tools: SourcePrep is Apache 2.0 open source — you already own it. Pro and Teams fund development; they never unlock features.

- [ ] **Step 2:** Greptile `:108` → "SourcePrep is open source (Apache 2.0) with an optional $29 Pro convenience license, and fully supports Bring Your Own Key (BYOK)…"; `:97` sharpen open-source vs proprietary-dashboard contrast.
- [ ] **Step 3:** Compare beta CTA rows: surrounding copy coherent in both states.
- [ ] **Step 4:** Verify :3100/about + both compare pages. Commit: `feat(marketing): open-source framing on about and compare pages`.

### Task 8: Download page

**Files:** Modify: `websites/apps/marketing/src/app/download/page.tsx` (:83, :84), `src/app/download/layout.tsx:5`

- [ ] **Step 1:** `:84` badge → "Open source — Apache 2.0. No account, no license required."
- [ ] **Step 2:** Install paths per spec: OSS (pip/pipx, brew, build from source, GitHub Releases via `GITHUB_REPO_URL`) vs Pro signed DMG/MSI marked "coming soon". Gate live .dmg/.msi buttons on the beta flag for coherence.
- [ ] **Step 3:** Truthfulness: remove `:83` "Also on the Microsoft Store" (or "Coming to the Microsoft Store"); `layout.tsx:5` meta drops Linux ("for macOS and Windows").
- [ ] **Step 4:** Verify :3100/download both states. Commit: `feat(marketing): open-source install paths on download page`.

### Task 9: Support page

**Files:** Modify: `websites/apps/marketing/src/app/support/page.tsx` (:63, :76)

- [ ] **Step 1:** Pillar 3 matrix: Community (GitHub Issues + Discussions, best-effort) / Pro (email, 5 business days) / Teams (private channel + email, 2 business days) / Enterprise (dedicated channel + office hours, negotiated 24h business-day target).
- [ ] **Step 2:** `:76` license-activation phrasing scoped to Pro installer users.
- [ ] **Step 3:** Verify :3100/support. Commit: `feat(marketing): support matrix per open-core tiers`.

### Task 10: Terms draft rewrite (flagged for legal)

**Files:** Modify: `websites/apps/marketing/src/app/terms/page.tsx` (:72, :77-108, :150-160)

- [ ] **Step 1:** Banner at top of content:

> Draft — this revision is pending legal review (Phase 144) and is not yet in effect.

- [ ] **Step 2:** `:72` → "services provided by Magnetic Anomaly LLC".
- [ ] **Step 3:** `:77-108` → two-part structure:

> **Open-source software.** The SourcePrep source code is licensed under the Apache License 2.0. Your use, modification, and redistribution of the software itself are governed by that license, not by these terms.
>
> **Paid products and services.** These terms govern Pro, Teams, and Enterprise: license keys are issued per purchaser and may not be shared or redistributed; signed builds, auto-update, hosted services, and support are provided only to active license holders.

- [ ] **Step 4:** `:150-160` SLA table → Pillar 3 matrix (Community = GitHub, no SLA).
- [ ] **Step 5:** Verify :3100/terms. Commit: `feat(marketing): draft open-core terms (pending legal review)`.

### Task 11: Changelog + home light touch

**Files:** Modify: `websites/apps/marketing/src/app/changelog/page.tsx:15-17`, `src/app/page.tsx:35-42`

- [ ] **Step 1:** Changelog planned entry mentions open-source launch (Apache 2.0); factual, undated.
- [ ] **Step 2:** Home sr-only SEO block: add open-source to the description; fix "Kimi 2.6" → model-family naming. **No hero edits.**
- [ ] **Step 3:** Verify :3100 home; hero identical to baseline. Commit: `feat(marketing): open-source mentions in changelog and home SEO copy`.

### Task 11b: Sitewide truthfulness fixes

**Files:** Modify: `websites/apps/marketing/src/app/layout.tsx:24`, `src/app/page.tsx:52,221`, `src/app/claude-code/page.tsx:118-120,195`, `src/app/integrations/page.tsx:164`

- [ ] **Step 1:** `layout.tsx:24` JSON-LD `operatingSystem` → `"macOS, Windows"`.
- [ ] **Step 2:** `page.tsx:52,221` "3–20× more signal per token" → "up to 20× structural compression" framing (design-based figure; Phase 73 audit). Flag both spots in the handoff note for Eric's review.
- [ ] **Step 3:** `claude-code/page.tsx:118-120` → "generates the skills file and documents the one-line auto-approve config".
- [ ] **Step 4:** Codex bullets (`integrations:164`, `claude-code:195`) → "first-class AGENTS.md consumer"; drop mcpServers-config claim.
- [ ] **Step 5:** Verify affected pages at :3100. Commit: `fix(marketing): correct stale factual claims (platforms, languages, Codex, compression)`.

### Task 12: Full verification

- [ ] **Step 1:** In worktree: `npm run lint`, `npm run typecheck`, production `npm run build` (marketing workspace). All pass.
- [ ] **Step 2:** Acceptance greps over `websites/apps/marketing/src`, zero hits (except allowed "coming"/roadmap phrasing):

```bash
rg -in 'free tier|3 projects|three projects' src
rg -in '\$79|\$70|\$7/mo|Q3 2026' src
rg -in 'SourcePrep Inc|sourceprep/sourceprep' src
rg -in '15\+ languages|Microsoft Store' src
rg -in 'linux' src   # only "planned/coming" phrasing may remain
```

- [ ] **Step 3:** Playwright walk of every changed page in BOTH flag states; screenshots; confirm $29/$15/$144/$50, coming-soon posture, no reachable checkout link, terms banner, hero pixel-identical to baseline.
- [ ] **Step 4:** Adversarial content verify: independent read-only agents check each page vs the amended spec; fix confirmed findings; re-run Steps 2-3 if fixes made.
- [ ] **Step 5:** Ensure `IS_BETA_MODE = true` restored everywhere; final commit if needed.

### Task 13: Handoff for Eric's review

- [ ] **Step 1:** Report: branch, commit list (`git log --oneline main..marketing/oss-launch-copy`), dev-server command, :3100 URL, per-page checklist, how to flip `IS_BETA_MODE`, flagged items (3-20× reframe, terms legal banner, pre-deploy checklist from spec).
- [ ] **Step 2:** Nothing pushed. Deploy/merge is Eric's call, later.
