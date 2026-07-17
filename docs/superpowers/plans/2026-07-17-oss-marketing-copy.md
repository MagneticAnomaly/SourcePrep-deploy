# OSS Marketing Copy Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the marketing site from closed-beta proprietary positioning to the locked Phase 142 open-core positioning, on an isolated worktree with a local-only review environment — nothing pushed or deployed.

**Architecture:** One worktree (`.claude/worktrees/oss-marketing-copy`) on branch `marketing/oss-launch-copy` off local `main`. Copy-only changes inside `websites/apps/marketing/` (plus one new `src/lib/links.ts`). `IS_BETA_MODE` stays switchable; every page must read coherently in both states. Dev server runs from the worktree on port **3100** so it never collides with the main checkout's :3000.

**Tech Stack:** Next.js app router (marketing workspace), npm workspaces + Turbo, Node 20 (`.nvmrc`), Playwright MCP for visual checks.

**Spec:** `docs/superpowers/specs/2026-07-17-oss-marketing-copy-design.md` — tier facts, hard rules, and acceptance criteria live there. Prices and tier names MUST match it exactly.

**Hard rules (from spec, repeated because they gate every task):**
- Never imply the OSS is feature-limited. Paid = installer polish, hosted infra, support.
- No 3-project-cap / Free-tier residue anywhere.
- Hero (`packages/ui` yale variant) untouched; **no `packages/ui` edits at all**.
- Entity is Magnetic Anomaly LLC. Brand is "SourcePrep" in copy; `prep` only as CLI/tool names.
- Plain-language-first voice; trim redundancy while editing.
- No `git push`, ever, in this plan.

---

### Task 1: Worktree + branch

**Files:** none (git only)

- [ ] **Step 1:** Invoke `superpowers:using-git-worktrees` skill, then create the worktree off local `main`:

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git worktree add .claude/worktrees/oss-marketing-copy -b marketing/oss-launch-copy main
```

- [ ] **Step 2:** Verify isolation and base:

```bash
git -C .claude/worktrees/oss-marketing-copy log --oneline -1   # expect current local main tip
git -C .claude/worktrees/oss-marketing-copy status --porcelain  # expect empty
```

Do NOT touch the stash (protected `stash@{0}`), other worktrees, or the main working tree.

### Task 2: Isolated local viewing environment

**Files:** none (env only)

- [ ] **Step 1:** Install deps inside the worktree (USB drive — allow several minutes; use Node 20):

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/.claude/worktrees/oss-marketing-copy
npm install
```

- [ ] **Step 2:** Start the marketing dev server on port 3100 (background):

```bash
cd websites/apps/marketing && npm run dev -- -p 3100
```

- [ ] **Step 3:** Verify: `curl -sI http://localhost:3100` returns 200; Playwright-screenshot the home page as the "before" baseline. Save baselines to the session scratchpad.

- [ ] **Step 4:** Report the URL to Eric: **http://localhost:3100** is the isolated view; :3000/:5174 etc. remain untouched.

### Task 3: Shared links constant

**Files:** Create: `websites/apps/marketing/src/lib/links.ts`

- [ ] **Step 1:** Create the file:

```ts
// Public GitHub repo. Org name not final (OPERATIONS.md open question 1) —
// change here once, everything follows.
export const GITHUB_REPO_URL = "https://github.com/sourceprep/sourceprep";
```

- [ ] **Step 2:** `npm run typecheck` in the marketing workspace passes.
- [ ] **Step 3:** Commit: `git add src/lib/links.ts && git commit -m "feat(marketing): shared GitHub repo URL constant"` (run inside the worktree; all later commits likewise).

### Task 4: Pricing page

**Files:** Modify: `websites/apps/marketing/src/app/pricing/page.tsx`, `src/lib/pricing.ts`, `src/app/pricing/layout.tsx:5`

- [ ] **Step 1:** Read all three files fully. Keep the existing card/grid component structure and the `IS_BETA_MODE` flag (`page.tsx:29`) exactly where it is.
- [ ] **Step 2:** Replace the tier data with the four open-core tiers. Content (map into the existing card props; wording below is the copy):
  - **Open Source — $0 — "The full product. Apache 2.0."** Bullets: full engine, daemon, CLI, MCP server, dashboard, VS Code extension; unlimited projects — every capability and prompt ships open source; local-first: your code never leaves your machine; install with pip, brew, or build from source; community support on GitHub. CTA beta-ON: existing Request-Beta mailto. CTA beta-OFF: "View on GitHub" → `GITHUB_REPO_URL`.
  - **Pro — $7/mo or $70 one-time — "Convenience, not capability."** Bullets: signed, notarized installers for macOS and Windows; automatic updates; email support (5-business-day response); same engine as open source — no feature gates. CTA beta-ON: Request-Beta mailto. CTA beta-OFF: existing checkout links. Keep a "Best value" badge on perpetual ($70 ≈ 10 months of monthly).
  - **Teams — $15/seat/mo, 3-seat minimum — "Coming soon — Q3 2026."** Bullets: one shared, always-fresh index per repo; SSO (Google, Okta, Microsoft Entra); role-based access and audit logs; priority support channel; annual $144/seat/yr (20% off). CTA (both states): "Join the waitlist" mailto (reuse the site's existing contact address, subject `Teams waitlist`).
  - **Enterprise — $50/seat/mo, annual, 10-seat minimum — "Coming soon."** Bullets: everything in Teams; air-gapped deployment; named contact + monthly office hours; scoped setup engagement available. CTA: "Talk to us" mailto.
- [ ] **Step 3:** Below the grid, one privacy line: "Teams syncs embeddings and graph metadata only — never your source code."
- [ ] **Step 4:** Remove all 3-project/Free-tier/license-management framing from the page. In `pricing.ts`: keep PPP bands and `LS_CHECKOUT_URLS` mechanics; change displayed perpetual price to $70; add comment at the perpetual URL: `// LS product still configured at $79 — Eric must reconfigure Lemon Squeezy before deploy`.
- [ ] **Step 5:** `layout.tsx:5` metadata → `"SourcePrep is free and open source (Apache 2.0). Pro adds signed installers, auto-update, and support — $7/mo or $70 one-time."`
- [ ] **Step 6:** Check both flag states at http://localhost:3100/pricing (flip `IS_BETA_MODE` locally, restore to `true` before commit). Run `npm run typecheck`.
- [ ] **Step 7:** Commit: `feat(marketing): open-core pricing page (OSS/Pro/Teams/Enterprise)`.

### Task 5: FAQ

**Files:** Modify: `websites/apps/marketing/src/app/faq/page.tsx` (anchors :20, :275, :334-342)

- [ ] **Step 1:** Rewrite the "Why pay for this?" answer (:334-342):

> SourcePrep is free and open source under Apache 2.0 — the full product, not a limited edition. Pro exists for convenience: signed installers, automatic updates, and email support. Teams adds hosted infrastructure — a shared index your whole team queries — that you'd otherwise run yourself. That's what funds development. Not your data.

- [ ] **Step 2:** Fix the cloud-call answer (:275): the open-source version makes no license calls at all; only the Pro installer makes a single HTTPS call during license activation.
- [ ] **Step 3:** Fix :20: "It works in the open-source version — every capability ships open source." Scan the rest of the FAQ for tier/Free residue (`rg -in 'free tier|3 projects|perpetual|\$79' src/app/faq/`) and fix hits with the same framing.
- [ ] **Step 4:** Verify at :3100/faq, both flag states. Commit: `feat(marketing): FAQ answers for open-core model`.

### Task 6: Security page

**Files:** Modify: `websites/apps/marketing/src/app/security/page.tsx` (anchors :116-117, :138-147, :250-252, :258-266, :281-282)

- [ ] **Step 1:** Section 05 "Offline Verification" (:138-147): retitle scope — applies to the **Pro installer** only; open-source builds contain no license infrastructure.
- [ ] **Step 2:** Allowed-outbound table (:116-117): mark `api.sourceprep.io /activate-license` as "Pro installer only".
- [ ] **Step 3:** Collected-data table (:250-252): License Key / Machine ID rows annotated "Pro only — the open-source version collects nothing."
- [ ] **Step 4:** Payments (:258-266) and license-record retention (:281-282): keep, scoped to paid tiers.
- [ ] **Step 5:** Verify at :3100/security. Commit: `feat(marketing): scope license/activation copy to Pro on security page`.

### Task 7: About + compare pages

**Files:** Modify: `websites/apps/marketing/src/app/about/page.tsx:104-108`, `src/app/compare/prep-vs-greptile/page.tsx:97,108`, `src/app/compare/prep-vs-cursor-indexing/page.tsx:106-107`

- [ ] **Step 1:** About "Own your tools" card →

> Own your tools: SourcePrep is Apache 2.0 open source — you already own it. Pro and Teams fund development; they never unlock features.

- [ ] **Step 2:** Greptile compare :108 → "SourcePrep is open source (Apache 2.0) with an optional Pro perpetual license, and fully supports Bring Your Own Key (BYOK)…". :97: sharpen the contrast — their proprietary web dashboard vs. our open-source local product.
- [ ] **Step 3:** Compare-page beta CTA rows: leave the mechanic; ensure surrounding copy works in both flag states.
- [ ] **Step 4:** Verify :3100/about and both compare pages. Commit: `feat(marketing): open-source framing on about and compare pages`.

### Task 8: Download page

**Files:** Modify: `websites/apps/marketing/src/app/download/page.tsx` (anchor :84)

- [ ] **Step 1:** Badge :84 → "Open source — Apache 2.0. No account, no license required."
- [ ] **Step 2:** Present the two install paths (per OPEN_CORE_SPLIT distribution table): **Open source** — pip/pipx, brew, build from source, GitHub Releases (link via `GITHUB_REPO_URL`); **Pro** — signed DMG/MSI from sourceprep.io with auto-update. Follow the page's existing layout components.
- [ ] **Step 3:** Verify at :3100/download, both flag states. Commit: `feat(marketing): open-source install paths on download page`.

### Task 9: Support page

**Files:** Modify: `websites/apps/marketing/src/app/support/page.tsx` (anchors :63, :76)

- [ ] **Step 1:** Replace tier phrasing with the Pillar 3 matrix: Community (GitHub Issues + Discussions, best-effort) / Pro (email, 5 business days) / Teams (private channel + email, 2 business days) / Enterprise (dedicated channel + office hours, negotiated 24h business-day target).
- [ ] **Step 2:** ":76 issues with your license activation" → scoped to Pro installer users.
- [ ] **Step 3:** Verify at :3100/support. Commit: `feat(marketing): support matrix per open-core tiers`.

### Task 10: Terms draft rewrite (flagged for legal)

**Files:** Modify: `websites/apps/marketing/src/app/terms/page.tsx` (anchors :72, :77-108, :150-160)

- [ ] **Step 1:** Visible banner at top of page content:

> Draft — this revision is pending legal review (Phase 144) and is not yet in effect.

- [ ] **Step 2:** Entity :72 → "services provided by Magnetic Anomaly LLC".
- [ ] **Step 3:** License Grant/Restrictions (:77-108) → two-part structure:

> **Open-source software.** The SourcePrep source code is licensed under the Apache License 2.0. Your use, modification, and redistribution of the software itself are governed by that license, not by these terms.
>
> **Paid products and services.** These terms govern Pro, Teams, and Enterprise: license keys are issued per purchaser and may not be shared or redistributed; signed builds, auto-update, hosted services, and support are provided only to active license holders.

- [ ] **Step 4:** SLA table (:150-160) → same Pillar 3 matrix as Task 9 (Community tier = GitHub, no SLA).
- [ ] **Step 5:** Verify at :3100/terms. Commit: `feat(marketing): draft open-core terms (pending legal review)`.

### Task 11: Changelog + home light touch

**Files:** Modify: `websites/apps/marketing/src/app/changelog/page.tsx:15-17`, `src/app/page.tsx:35-42`

- [ ] **Step 1:** Changelog planned entry: mention the open-source launch (Apache 2.0) alongside the planned release; keep it factual.
- [ ] **Step 2:** Home sr-only SEO block (:35-42): add "open-source" to the product description. **Do not touch the hero component or its props beyond what exists.**
- [ ] **Step 3:** Verify at :3100 (home renders identically above the fold; hero unchanged). Commit: `feat(marketing): open-source mentions in changelog and home SEO copy`.

### Task 12: Full verification

**Files:** none (checks only)

- [ ] **Step 1:** In the worktree: `npm run lint`, `npm run typecheck`, and a production `npm run build` for the marketing workspace. All pass.
- [ ] **Step 2:** Acceptance greps (marketing app only), expect zero hits:

```bash
rg -in 'free tier|3 projects|three projects|\$79' websites/apps/marketing/src
rg -in 'SourcePrep Inc' websites/apps/marketing/src
```

- [ ] **Step 3:** Playwright walk of every changed page in BOTH flag states; screenshot each; confirm prices ($7 / $70 / $15 / $144 / $50), "coming soon" posture on Teams/Enterprise, terms banner present, hero pixel-identical to baseline.
- [ ] **Step 4:** Adversarial content verify: independent read-only agents check each changed page against the spec's tier table and hard rules; fix anything confirmed; re-run Step 2-3 if fixes were made.
- [ ] **Step 5:** Restore `IS_BETA_MODE = true` everywhere if any flip survived; final commit if needed.

### Task 13: Handoff for Eric's review

- [ ] **Step 1:** Report: worktree path, branch, commit list (`git log --oneline main..marketing/oss-launch-copy`), dev-server command, and the :3100 URL with per-page checklist. Include how to flip `IS_BETA_MODE` to preview launch state.
- [ ] **Step 2:** Nothing is pushed. Deploy/merge decisions are Eric's, later.
