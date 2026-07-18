# Enterprise Pricing Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the marketing pricing page to the new tier structure — Enterprise $24/seat (15-seat min), Teams $9/seat, and a new tiered setup-fee line on the Enterprise card.

**Architecture:** Single-file edit to `websites/apps/marketing/src/app/pricing/page.tsx` (a Next.js 14 client component). Four small JSX text edits. No data flow, no state, no API. Verification is typecheck + lint + production build + visual check — the marketing app has no test runner, and this is a static-content change, so unit tests are not applicable (adding a test harness would be disproportionate scope creep).

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind. Build via `npm run build` in `websites/apps/marketing`.

**Spec:** `docs/superpowers/specs/2026-07-18-enterprise-pricing-design.md`

**Pre-sweep result (already performed):** The only customer-facing file referencing the old numbers is `pricing/page.tsx`. The docs site (`websites/apps/docs/src`) has no pricing-number references. Internal `docs/*` planning/audit/phase records (e.g. `OPEN_CORE_SPLIT.md`, which still shows an earlier $50/seat era) are point-in-time or already-drifted internal artifacts and are intentionally left untouched — they are not customer surfaces.

---

### Task 1: Update the Teams card — per-seat price and annual discount

**Files:**
- Modify: `websites/apps/marketing/src/app/pricing/page.tsx` (Teams card, around lines 127–129 and 153)

- [ ] **Step 1: Edit the Teams per-seat price from $10 to $9**

In `websites/apps/marketing/src/app/pricing/page.tsx`, replace:

```tsx
              <span className="text-4xl font-bold">$10</span>
              <span className="text-text-muted ml-1">/ seat / month</span>
              <div className="mt-1 text-xs text-text-muted">3-seat minimum</div>
```

with:

```tsx
              <span className="text-4xl font-bold">$9</span>
              <span className="text-text-muted ml-1">/ seat / month</span>
              <div className="mt-1 text-xs text-text-muted">3-seat minimum</div>
```

- [ ] **Step 2: Edit the Teams annual discount from $96/seat/yr to $86/seat/yr**

In the same file, replace:

```tsx
                <span>Annual $96/seat/yr (20% off)</span>
```

with:

```tsx
                <span>Annual $86/seat/yr (20% off)</span>
```

Note: $9 × 12 = $108; 20% off = $86.40, rounded down to $86. The "20% off" framing is preserved exactly as on the existing page.

- [ ] **Step 3: Typecheck the marketing workspace**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing && npm run typecheck`
Expected: PASS (no output, exit 0). These are pure text changes with no type impact, so any failure indicates an accidental structural edit — investigate before continuing.

- [ ] **Step 4: Commit the Teams change**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add websites/apps/marketing/src/app/pricing/page.tsx
git commit -m "feat(pricing): Teams tier $10/seat -> $9/seat, annual $96 -> $86"
```

---

### Task 2: Update the Enterprise card — price, minimum, and setup-fee bullet

**Files:**
- Modify: `websites/apps/marketing/src/app/pricing/page.tsx` (Enterprise card, around lines 165–167 and 186–188)

- [ ] **Step 1: Edit the Enterprise per-seat price from $30 to $24**

In `websites/apps/marketing/src/app/pricing/page.tsx`, replace:

```tsx
              <span className="text-4xl font-bold">$30</span>
              <span className="text-text-muted ml-1">/ seat / month</span>
              <div className="mt-1 text-xs text-text-muted">Annual billing, 10-seat minimum</div>
```

with:

```tsx
              <span className="text-4xl font-bold">$24</span>
              <span className="text-text-muted ml-1">/ seat / month</span>
              <div className="mt-1 text-xs text-text-muted">Annual billing, 15-seat minimum</div>
```

- [ ] **Step 2: Replace the "Setup assistance available" bullet with the tiered setup line**

In the same file, replace:

```tsx
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Setup assistance available</span>
              </li>
```

with:

```tsx
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Setup: remote included · on-site from $3,500 · air-gapped quoted</span>
              </li>
```

Note: the `·` (middle dot, U+00B7) is used as the separator. Keep the existing checkmark glyph (`&#10003;`) and the surrounding `<li>` structure unchanged — only the inner `<span>` text changes.

- [ ] **Step 3: Typecheck the marketing workspace**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing && npm run typecheck`
Expected: PASS (no output, exit 0).

- [ ] **Step 4: Lint the marketing workspace**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing && npm run lint`
Expected: PASS (no errors). The middle-dot character is valid UTF-8 in JSX text; ESLint should not flag it. If ESLint complains about encoding, confirm the file is saved as UTF-8 (it already is — the existing page uses `&#10003;` and `&#8594;` HTML entities and emoji without issue).

- [ ] **Step 5: Commit the Enterprise change**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add websites/apps/marketing/src/app/pricing/page.tsx
git commit -m "feat(pricing): Enterprise $30/seat -> $24/seat, 10-seat -> 15-seat min, tiered setup fee"
```

---

### Task 3: Production build and visual verification

**Files:**
- None modified (verification only)

- [ ] **Step 1: Run the production build**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing && npm run build`
Expected: build succeeds. The pricing page is statically rendered; confirm `/pricing` appears in the build output route list with no error. A build failure here means a JSX/escape issue in the new text — check the middle-dot and dollar characters are plain text inside the `<span>`.

- [ ] **Step 2: Start the dev server and visually verify the pricing page**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/marketing && npm run dev`
Then open `http://localhost:3000/pricing` in a browser (or use the Playwright MCP: `browser_navigate` to `http://localhost:3000/pricing`, then `browser_snapshot`).

Confirm all four:
- Teams card shows **$9** / seat / month, **3-seat minimum**, and the bullet **Annual $86/seat/yr (20% off)**.
- Enterprise card shows **$24** / seat / month and **Annual billing, 15-seat minimum**.
- Enterprise card's last bullet reads **Setup: remote included · on-site from $3,500 · air-gapped quoted** — and does not overflow or break the card layout at the default grid width (the text is longer than the old bullet; verify it wraps cleanly within the card).
- Open Source ($0) and Pro ($29 one-time) cards are unchanged.

- [ ] **Step 3: Stop the dev server**

Stop the running `npm run dev` process (Ctrl-C, or kill the background shell).

- [ ] **Step 4: Final stale-number sweep confirmation**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
grep -rln -e "10-seat" -e "96/seat" -e "30/seat" -e "10/seat" -e "Setup assistance available" websites/apps/marketing/src websites/apps/docs/src 2>/dev/null | grep -v node_modules | grep -v "/.next/"
```
Expected: **no output**. The old numbers are gone from all customer-facing surfaces. (Internal `docs/*` planning records are intentionally excluded from this grep's paths and remain untouched, per the spec.)

- [ ] **Step 5: Final commit (if any uncommitted verification artifacts)**

If the build or dev server created no stray uncommitted source changes, this step is a no-op — verify with `git status` (should be clean after Tasks 1 and 2). If `git status` shows anything unexpected in `src/`, do NOT commit it blindly; surface it for review.

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git status
```
Expected: `nothing to commit, working tree clean` (or only untracked build artifacts under `.next/`, which are gitignored).

---

## Done criteria

- [ ] Teams card: $9/seat/mo, $86/seat/yr annual (20% off), 3-seat min.
- [ ] Enterprise card: $24/seat/mo, 15-seat min, annual billing.
- [ ] Enterprise setup bullet replaced with the three-tier setup line.
- [ ] OSS and Pro cards unchanged.
- [ ] `npm run typecheck`, `npm run lint`, and `npm run build` all pass for `websites/apps/marketing`.
- [ ] Visual check confirms the new setup bullet wraps cleanly inside the Enterprise card.
- [ ] Stale-number sweep returns no customer-facing hits.
- [ ] Two commits made (Teams, then Enterprise), no push (per standing instruction — push only on explicit request).

## Notes for the implementer

- **Do not push.** The standing instruction is to commit locally and never push to `origin/main` without an explicit "push/deploy/ship" signal. Each push triggers Netlify builds.
- **No Co-Authored-By trailer** on commits.
- **The middle dot `·`** in the setup bullet is a literal UTF-8 character, not an HTML entity. It renders fine in JSX text. If your editor mangles it, use `&middot;` instead — either is acceptable, but pick one and keep it consistent.
- **Do not edit internal `docs/*` planning/audit/phase files** that still show old pricing numbers. Those are point-in-time records (some already drifted from an earlier $50/seat era) and are not customer-facing. Updating them would falsify history and is out of scope.
- **Do not add a test runner.** The marketing app has none, and this is a static-content change. Verification is typecheck + lint + build + visual, as specified.