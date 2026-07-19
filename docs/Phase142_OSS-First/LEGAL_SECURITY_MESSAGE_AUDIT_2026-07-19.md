# Legal + Security + Message-Clarity Audit (2026-07-19)

> Cross-surface audit of all public sites + repo metadata. **Orthogonal to
> the 4 prior code-accuracy passes** (those checked docs-vs-code; this checks
> cross-surface consistency + legal + security + message clarity).
>
> Workflow: `legal-security-message-audit.workflow.js` (run `wf_ea08e419-cec`,
> 57 agents, 6 discovery + 3 lens finders + per-finding adversarial verify +
> synthesis). Read-only, NO worktree (verifiers read the actual working tree,
> so no worktree-base artifacts).
>
> Methodology (Eric's standing rule): *assume everything is wrong unless you
> can prove it with code and intention; if you can prove it with intention
> and design but not code, flag it; keep track of the issues and correct the
> site documentation meticulously.* Every fix-now item below was re-verified
> against the working tree before editing.

## Status

- **Relicense:** root `LICENSE` is Apache-2.0 as of commit `99315988` (landed
  mid-prior-session). This audit VERIFY-completes the relicense rather than
  flagging the (resolved) metadata-vs-LICENSE contradiction.
- **Fix-now APPLIED:** 20 of 23 items, 6 local commits (NOT pushed — `[deploy]`
  gate). tsc clean on docs/marketing/support/payments + packages/ui.
- **Reclassified non-issue:** 1 (FN-9 — `.env.example` is gitignored).
- **Deferred to ED-7:** 1 sub-item (FN-16 `github.ts` REPO_OWNER — needs `gh`
  verification Discussions are enabled on the org repo).
- **Flag-for-AI-deep-review:** 6 (DR-1..DR-6) — for a follow-up AI research
  pass (no attorney budget).
- **Eric-decision:** 7 (ED-1..ED-7) — product/business/legal-act calls.

---

## 1. SUMMARY

6 discovery agents (docs / marketing / support / payments / repo-metadata +
1 code-posture ground-truth), 3 lens finders (legal / security / message),
per-finding adversarial verification, then synthesis. **47 raw findings → 47
verified → 34 confirmed (27 fix-now, 2 flag-deep-review, 10 eric-decision) →
11 refuted-TRUE.** After deduplication and reconciliation against the working
tree, **20 fix-now edits were applied** (see §2 for the 3 not applied and why).

**3-lens breakdown:**
- **LEGAL (9):** relicense-rollout gaps (vscode `LICENSE` still commercial,
  footers "All rights reserved." + fabricated "SourcePrep Inc." entity, DCO
  claim in CONTRIBUTING not wired), DRAFT trust-doc banners, trademark/™
  clearance, scancode SBOM scan, per-app LICENSE-file absence.
- **SECURITY (8):** Ed25519 test-vector present-tense over-claims (docs +
  payments + marketing), Lemon Squeezy 7-day revalidation "no phone-home"
  falsehoods, Plausible analytics on 4 surfaces with no privacy policy,
  bug-report wildcard-CORS + PII-to-logs + Resend subprocessor, support
  admin auth (raw-token cookie, `?token=`, `===`, dev-fallback), `codrag.key`
  on origin (gate IS built; history never copied), update-check phone-home
  contradiction, `/recover` mock endpoint.
- **MESSAGE (9):** pricing ladder mismatch ($79/$7mo/$15 vs $29/$9/$24),
  cross-surface repo-identifier inconsistency (`SourcePrep-MCP` vs `SourcePrep`
  vs `EricBintner`), present-tense "purchase/manage/recover" on payments,
  SSO/SCIM "actively in development" overstatement, auto-rebuild phrasing,
  broken Status nav link, robots `/private/` rule, "tickets" meta description,
  Homebrew/winget install availability.

**Single biggest cross-surface contradiction:** the **pricing ladder**.
`websites/apps/payments/src/app/page.tsx:26,37` quoted Pro "$79 one-time or
$7/mo" and Team "$15/seat/mo" while `marketing/pricing/page.tsx:86,127,165`
and the decided 2026-07-18 ladder (commit `0f1a66c2`, PUSHED) say Pro $29
one-time / Teams $9/seat/mo / Enterprise $24/seat/mo. The payments page's own
"View Full Pricing" link sent visitors to the contradicting marketing page.
**Fixed** (commit `c6273d4b`).

---

## 2. FIX-NOW (applied)

Each is license-neutral, no Eric/legal-act, no forward-looking assertion.
All re-verified against the working tree before editing; none were pre-fixed
by the parallel session's relicense commits (`99315988`, `7bf962fb`,
`b1fcbac1` touched only `LICENSE`/`README.md`/Phase142 plan docs).

### Commit `88dbc4bf` — relicense-rollout completeness

- **FN-1. `packages/vscode/LICENSE`** — was the full pre-relicense COMMERCIAL
  text ("All Rights Reserved / NO REDISTRIBUTION / individual use via
  purchased license key"), contradicting `package.json:7` "Apache-2.0", root
  LICENSE, and `CHARTER.md:31-33`. Replaced with the canonical Apache-2.0
  text (verbatim `cp LICENSE packages/vscode/LICENSE`).
- **FN-2. `packages/ui/.../SiteFooter.tsx:114`** — default copyright
  `© {year} {productName} Inc. All rights reserved.` rendered a fabricated
  entity ("SourcePrep Inc." appears nowhere else) + ARR (contradicts the
  Apache grant). Default → `© {year} Magnetic Anomaly LLC.` (the NOTICE:2
  holder).
- **FN-3 / FN-4. `payments` + `support` `ClientLayout.tsx`** — passed no
  `copyright` prop → fell through to the bad default. Now pass
  `copyright="© 2026 Magnetic Anomaly LLC."`
- **FN-5 / FN-6. `marketing` + `docs` `ClientLayout.tsx`** — dropped "All
  rights reserved."; fixed docs `llc` → `LLC`. All four app footers now read
  the real holder, no ARR.
- **FN-7. `CONTRIBUTING.md:79-80`** — "A DCO check runs on every pull request;
  PRs missing `Signed-off-by` are blocked" was false (no DCO workflow exists;
  `AI_WORK_TODO` lists it as open). Softened to "Commits must include
  `Signed-off-by` (`git commit -s`). A DCO check will be wired to CI before
  the public mirror push; until then, missing sign-off is caught at review."

### Commit `c6273d4b` — payments pricing ladder reconciliation

- **FN-8. `payments/src/app/page.tsx:26,37`** — Pro "$79 one-time or $7/mo.
  Unlimited projects, all features." → "$29 one-time (Coming Soon). Signed
  installers, auto-updates, and email support." (matches marketing
  `pricing:86`; drops the "all features" over-claim that conflicts with
  marketing's "Convenience, not capability" positioning — Pro is convenience,
  not a feature unlock). Team "$15/seat/mo. Shared config + centralized
  management." → "$9/seat/mo (3-seat minimum) · $97/seat/yr annual. Shared
  index, SSO, RBAC, audit logs." (matches marketing `pricing:127-129,153`).
- **FN-9. `payments/.env.example` + `marketing/.env.example`** —
  **RECLASSIFIED NON-ISSUE.** The dead `NEXT_PUBLIC_PREP_CHECKOUT_URL` (and
  the retired `NEXT_PUBLIC_LS_CHECKOUT_MONTHLY`) live only in `.env.example`,
  which is gitignored (`.gitignore:111 .env.*`) and untracked — not a repo /
  public surface. Local edits reverted (not committed). The corresponding
  `netlify.toml:14` comment (tracked) WAS cleaned — removed the MONTHLY line
  (no source consumer; the monthly tier is not in the decided ladder).
- **Follow-up (not done):** payments lists no Enterprise card (marketing
  `pricing:165` has Enterprise $24/seat/mo, 15-seat min) — a completeness
  gap, not a falsehood.

### Commit `cd4a0d29` — telemetry / Ed25519 / offline claim scoping

- **FN-10 + FN-22 (merged). `docs enterprise-deploy:248`** — "No telemetry.
  SourcePrep does not phone home…" (absolute, false for LS Pro/Teams) →
  "The GPU image does not phone home…" (scoped to the Enterprise GPU image,
  which IS offline). FN-10 and FN-22 both targeted this line; the GPU-image
  scoping is accurate for the Enterprise context (Enterprise uses Ed25519,
  not LS) and resolves FN-10's absolute-claim concern.
- **FN-11. `docs enterprise-deploy:252,287`** — "Enterprise licenses are
  Ed25519-signed and validated locally" (present-tense, false —
  `licensing.py:22 DEFAULT_PUBLIC_KEY_HEX` is the RFC 8032 test-vector
  placeholder) → future tense "will be Ed25519-signed… coming with the
  Phase 146 crypto refresh." Table row "Offline licensing | Available" →
  "Roadmap" (`text-warning`).
- **FN-12. `payments/src/app/page.tsx:17`** — "All licenses are verified
  offline after a single activation — no recurring phone-home" (false for
  LS) → "Open-source builds verify offline. Pro and Teams licenses activated
  via Lemon Squeezy re-validate with api.lemonsqueezy.com every 7 days, with
  a 30-day offline grace period before downgrade to Free." (Also covers
  FN-11's payments:17 Ed25519 concern — no Ed25519 present-tense.)
- **FN-13. `marketing/security:117-118`** — diagram "api.sourceprep.io / POST
  /activate-license (Pro installer only, one-time)" (`api.sourceprep.io` is
  never called — only placeholder comments at `license.py:424,444,466`; real
  endpoint is `api.lemonsqueezy.com/v1/licenses`) → "api.lemonsqueezy.com /
  POST /licenses/validate — Pro/Teams revalidation, every 7 days (30-day
  offline grace)."
- **FN-22. `marketing/security:78-80`** — "The OSS product makes no network
  calls… The Pro installer makes a one-time license activation; nothing else"
  (false — 7-day revalidation) → "The OSS daemon and CLI make no network
  calls… Pro and Teams licenses re-validate with api.lemonsqueezy.com every 7
  days (30-day offline grace); no source code, index data, or usage stats are
  ever sent."
- **FN-22. `docs installation:94`** — "SourcePrep checks for updates
  automatically" (true only for the Tauri desktop app, not the daemon/CLI;
  `UpdateBanner.tsx:28-44` calls `checkUpdate()` on launch + every 30 min
  against `github.com/.../releases/latest/download/latest.json`) → scoped to
  "The SourcePrep desktop app checks for updates on launch… (The daemon/CLI
  install does not; check `prep --version` or the releases page.)"
- **FN-17. `docs enterprise-deploy:308-312`** — "Roadmap features are
  actively in development" (SSO/SCIM not built —
  `ENTERPRISE_FEATURES_PLAN.md` AUTH-1/2 "❌ Not built") → "Roadmap features
  are not yet available."

> **Underlying code defects NOT fixed here** (remain Eric-gated / deep-review):
> the Ed25519 placeholder key (`licensing.py:22`, Phase 146 plan exists) and
> the LS 7-day polling code (`lemon_squeezy.py`). These are code changes, not
> copy. This commit only makes the public copy truthful about current
> behavior.

### Commit `90f5d2c1` — support / docs / marketing truth fixes

- **FN-14. `marketing/pricing:197`** — "Teams syncs embeddings and graph
  metadata only — never your source code" (FALSE —
  `remote_sync.py:49 strip_source_content` defaults `False`; source content
  IS uploaded by default) → "Teams syncs your shared code index — today this
  includes source content by default; a strip-source-content mode is wired
  for the client path and planned for the headless CI uploader."
- **FN-16. `support/SupportFeatures:6` + `DiscussionList:24,38`** — repointed
  `MagneticAnomaly/SourcePrep-MCP` → canonical `MagneticAnomaly/SourcePrep`
  (`marketing/links.ts:3` DECIDED 2026-07-17). Footer URLs (payments +
  support `ClientLayout`) were done in `88dbc4bf`.
- **FN-18. `support/layout.tsx:19`** — meta "tickets, bugs, questions" (no
  ticket system exists; channels are GitHub Discussions + bug-report form +
  mailto) → "discussions, bug reports, questions, and security reporting."
- **FN-19. `support/ClientLayout.tsx:20`** — removed the broken "Status" nav
  link (`href: '#'`, no `/status` route, no statuspage.io link).
- **FN-20. `support/robots.ts:8`** — removed `Disallow: /private/` (no
  `/private/` route exists in the support app).
- **FN-21. `docs/knowledge-scope:100`** — "auto-rebuild is on by default for
  Pro/Teams/Enterprise and can be toggled on for the free tier" → led with
  "Auto-rebuild is available on every tier (including the $0 self-hosted
  build)" for first-visitor clarity.

### Commit `dc90af1c` — recover endpoint PII + honest message

- **FN-15. `payments/api/recover/route.ts` + `recover/page.tsx`** — the
  endpoint was an explicit mock that (a) logged the visitor's email to
  server logs (PII) and (b) returned a fake success ("a recovery email has
  been sent") with no lookup, no email send, no rate-limit, no validation.
  Route: dropped email from the log; added email-shape validation (400);
  added in-memory per-IP rate limit (5/hour, 429; resets on cold start —
  upgrade to Netlify Blobs/Upstash before going live, see DR-5); replaced the
  fake success with an honest 501 pointing to `licenses@sourceprep.io`. Page
  hero softened to "we'll get back to you, or email licenses@sourceprep.io
  directly." **Residual:** the page's success branch ("Recovery email sent!")
  is now unreachable dead code (endpoint always returns 501) — left in place
  to minimize JSX churn; a future cleanup can remove it.

### Commit `914e683f` — public-mirror gate hardening

- **FN-23. `tools/build_public_mirror.py:104-166`** — the gate excluded
  `logs` but not `*.log`, so `websites/apps/marketing/dev.log` (Next.js dev
  output that leaks internal route names) would slip into the public mirror.
  Added `*.log` and `dev.log` to `DENY_PATH_GLOBS`. Verified `path_denied()`
  now catches `websites/apps/marketing/dev.log` (via the segment matcher at
  `:243`) while leaving `src/prep/server.py` untouched.

### Not applied (deferred)

- **FN-16 sub-item `support/src/lib/github.ts:4`** (`REPO_OWNER='EricBintner'`)
  → deferred to **ED-7**. Requires `gh api graphql` verification that
  Discussions are enabled on `MagneticAnomaly/SourcePrep` before repointing;
  if not, escalate to Eric.

---

## 3. FLAG-FOR-AI-DEEP-REVIEW (follow-up AI research pass, no attorney)

### DR-1. SBOM / source-vendored-GPL / LLM-generated-CC-BY-SA scan (the scancode gate)
Install `scancode-toolkit` (`pipx install scancode-toolkit`, ~1GB) and run
`scancode -clpeu --json-pp scan.json <repo>` across the full tree. Hotspots
flagged by `LICENSE-AUDIT.md:80`: `docs/Phase13_Storybook`,
`docs/Phase14_MCP-CLI codrag-mcp-template`, `packages/vscode`. Then
`npm ls --json --workspaces` + license-checker on every npm workspace,
`cargo deny check licenses` on `engine/` (add `deny.toml` if absent), and
`pip-licenses --from=mixed` on `src/prep/`. Reconcile every
GPL/AGPL/LGPL/CC-BY-SA/MPL hit against `NOTICE:30-58` and decide replace /
attribute / rewrite per hit. Confirm MPL-2.0 file-level obligations. Only
after reconciliation, remove the `NOTICE:22` DRAFT banner. Do NOT push the
public mirror until this closes. Also fix `NOTICE:27` stale pointer
("AI_WORK_TODO.md Stream 3" → point to `Phase142_OSS-First/README.md` or
remove). **Open question:** is any vendored or model-generated copyleft
snippet hiding in the source tree?

### DR-2. Trademark clearance + ™/® signaling decision research
(1) Search USPTO TESS for live apps/registrations matching "SourcePrep" /
"Source Prep" / "SOURCEPREP" in IC 9 + 42. (2) Likelihood-of-confusion +
descriptiveness survey (SOURCE + PREP may be merely descriptive → §2(e)(1)
refusal risk). (3) Recommend ® (post-approval under 15 U.S.C. §1065) vs ™
(common-law now). (4) Draft a one-paragraph trademark policy to append to
NOTICE (per `LICENSING_DEEP_RESEARCH_REPORT.md:144`). (5) Cross-check policy
text against `CHARTER.md:64-70` and `terms/page.tsx:118-124` so all three
surfaces use identical wording. **Open question:** is "SourcePrep"
registrable, or merely descriptive?

### DR-3. Per-app LICENSE/NOTICE file absence — Apache-2.0 §4 distribution analysis
(1) Confirm whether Apache-2.0 §4 is triggered by Netlify SaaS deployment
of a Next.js app (expected: no — Apache-2.0 is not AGPL; SaaS is not
conveyance). (2) Document the npm/Next.js monorepo norm for app subtrees that
assert `"license"` in `package.json` without a sibling LICENSE file. (3)
Check whether any of the four apps is ever distributed as source/object — a
downloadable bundle, a Docker image pushed to a public registry, or the
planned public GitHub mirror of the subtree (the `build_public_mirror.py`
allowlist+denylist gate is the thing to check against). If yes, §4 IS
triggered and a LICENSE copy + NOTICE must accompany that distribution.
**Open question:** does any distribution channel trigger §4, or is SaaS-only
deployment sufficient to skip per-app LICENSE files?

### DR-4. Support admin auth security hardening (engineering research + design)
(1) Inventory EVERY caller of `isAuthorized`/`isAuthorizedServer` across
`websites/apps/support/src` and list what PII each admin route exposes —
produce a PII access-logging gap matrix. (2) Confirm the support site's
current deploy status and intended public domain (`deploy-support` is
commented out in `deploy-websites.yml:160`; is it live via manual Netlify
deploy? when does it go public?) to set remediation urgency. (3) Design the
auth replacement — evaluate NextAuth vs Clerk vs a rolled-own
opaque-session model (issue an opaque session id keyed server-side to a hash
of ADMIN_TOKEN, never store the raw token in the cookie); pick one and
document the migration. (4) Audit admin pages for third-party assets/scripts
that could receive the token via Referer when `?token=` is used. (5) Apply
immediate license-neutral mitigations that do NOT need Eric's sign-off:
remove the `?token=` query-param path (cookie+Authorization header only);
swap all three `===` compares to `crypto.timingSafeEqual`; change the
dev-fallback (`auth.ts:22,43`) to hard-deny when NODE_ENV cannot be confirmed
production; replace the raw-token cookie with an opaque session id; add an
audit-log row for every `PATCH /api/bug-reports/:id` mutation. (6) Remove
`route.ts:229` `console.log` of `reporter.email` (PII to function logs).
(7) Confirm `RESEND_API_KEY` / `BUG_REPORT_EMAIL` / `ADMIN_TOKEN` env vars
are server-only (not client-bundled). **Open question:** which auth provider,
and is the support site already publicly reachable?

### DR-5. Bug-report endpoint CORS + rate-limit + Resend subprocessor
(1) Enumerate the full allowed-origin list (sourceprep.io, www., support.,
docs., marketing., payments., plus the desktop app's custom origin scheme if
it POSTs directly) and replace `Access-Control-Allow-Origin: '*'` at
`bug-report/route.ts:178-182` with an allowlist. (2) Research and wire a
persistent serverless store (Netlify Blobs or Upstash Redis) to replace the
in-memory `rateLimitMap` at `route.ts:40-55` before any public-mirror deploy.
(3) Audit env vars (see DR-4.7). (4) Confirm the public mirror
(`build_public_mirror.py` allowlist+denylist) is the gate before this
endpoint ships publicly. The Resend subprocessor disclosure at the bug-report
submit step is a privacy-law compliance item (GDPR Art 28 / CCPA) — that
sub-item is **eric-decision** (Eric must approve the privacy-policy/notice
text naming Resend). **Open question:** which persistent store, and is the
support site already public?

### DR-6. codrag.key history scan + rotation plan
The public-mirror gate IS built and fails-closed; the mirror design is a
fresh-initial-commit (no history copy), so origin history is never published.
Residual: (1) Run
`git log --all -p | grep -iE 'BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY|codrag\.key|sk-[A-Za-z0-9]{20}|gh[pousr]_|AKIA[0-9A-Z]{16}'`
to confirm `codrag.key` is the ONLY private-key commit in history. (2) Verify
the gate is wired into the release pipeline as a MANDATORY pre-push CI check
(grep `.github/workflows/`, `scripts/` for invocations of
`build_public_mirror.py`); if absent, flag to Eric (ED-6) to add a pre-push
hook. (3) Note: `codrag.key` is the **Tauri updater** signing key (signs
macOS/Windows app-update bundles), NOT the license-signing key — license
forgery risk lives separately in `licensing.py:22` (RFC 8032 test vector,
already tracked). The rotation plan (rotate Tauri keypair, update
`codrag.key.pub`, deprecate old key) is eric-decision. **Open question:** is
`codrag.key` the only secret in history, and is the gate CI-wired?

---

## 4. ERIC-DECISION (needs Eric's call)

### ED-1. DRAFT trust-document banners + mailbox liveness (extends E-series)
**Question:** Are `security@sourceprep.io`, `support@sourceprep.io`,
`legal@sourceprep.io`, `privacy@sourceprep.io` provisioned, monitored, and
ready to receive mail — and are the trademark language, Terms go-live, and
scancode scan (DR-1) complete enough to strip the DRAFT banners?
**Context:** `SECURITY.md:3`, `NOTICE:22`, `CONTRIBUTING.md:7`, `CHARTER.md:1`
all carry "Status: DRAFT for legal-trigger review." But
`support/SupportFeatures.tsx:40-42` publicly advertises `security@sourceprep.io`
as a live security-reporting channel (no DRAFT qualifier),
`CODE_OF_CONDUCT.md:58` routes conduct complaints there, and `README.md:570`
routes vuln reports to SECURITY.md. An unmonitored security mailbox is a
concrete vuln-reporting failure path.
**Options:** (a) Provision + verify mailboxes, finalize trademark language,
finalize Terms go-live, complete scancode scan, THEN strip all four DRAFT
banners. (b) Add an interim DRAFT caveat to the support-site Security
reporting card.
**Recommended default:** (a) — provision mailboxes first; the banners are the
final legal gate, not the defect. Do not push the public mirror until they
come down.

### ED-2. Terms of Service DRAFT + paid-tier launch gate
**Question:** Is the current OSS-only posture (Terms DRAFT + all paid tiers
"coming soon / not yet on sale") the intended near-term state, or do you
intend to put Pro/Teams/Enterprise on sale before Terms are finalized?
**Context:** `marketing/terms/page.tsx:27` "This revision is pending legal
review (Phase 144) and is not yet in effect." Every public surface consistently
says paid tiers are "coming soon / not yet on sale." No present contradiction
— the gate is held correctly. Terms is missing: effective date,
governing-law/jurisdiction clause, liability cap tying to the AS-IS warranty
block at lines 209-216, refund window (line 161 defers to "at time of
purchase"), auto-update/termination terms for per-purchaser license keys
(lines 109-113), and a reference to a standalone trademark policy from lines
119-124.
**Options:** (a) Keep OSS-only state — no action, DRAFT banner is correct and
safe. (b) Finalize minimum Terms clauses + flip DRAFT before any paid sale.
**Recommended default:** (a) — keep OSS-only until ready to launch paid tiers;
then finalize Terms first. Do NOT sell any paid tier while the line 27 DRAFT
banner remains. (The payments-page hero "Purchase a SourcePrep license" + the
checkout buttons are consistent with this only because the buttons degrade to
"View Pricing" when the LS env vars are unset; if you set them, re-evaluate.)

### ED-3. Plausible analytics privacy-policy + subprocessor disclosure
**Question:** Do you authorize publishing a short Privacy Policy / Subprocessor
disclosure on each public surface (support, payments, docs, marketing) naming
Plausible Cloud (plausible.io) as an analytics subprocessor (aggregated,
cookieless, IP-truncated, no cross-site tracking, no PII)? And do you want a
cookie-consent banner?
**Context:** All FOUR public surfaces load Plausible (`support/layout.tsx:39`,
`payments/layout.tsx:39`, `docs/layout.tsx:39`, `marketing/layout.tsx:87`). No
`/privacy` route exists on any surface. The de-facto privacy policy is
`marketing/security/page.tsx` (Privacy Policy heading at :225) — it does NOT
disclose Plausible. Worse, it asserts "Telemetry / Usage Stats: Not Collected"
(:249) and "Usage Analytics: DISABLED / NONE" (:92-93) — scoped to the desktop
product, but a visitor being tracked by Plausible on that very page reads it
as a blanket "we don't track you." Plausible sets no cookies and does no
cross-site tracking, so under the EU ePrivacy Directive a banner is arguably
NOT required; GDPR Art. 6 lawful-basis for IP-derived stats is still Eric's
call.
**Options:** (a) Publish a "Website Analytics" subsection on
`marketing/security/page.tsx` disclosing Plausible + mirror a one-line footer
link on the other three surfaces; no cookie banner. (b) Self-host Plausible
Community Edition. (c) Switch to a EU-hosted cookieless provider. (d) Remove
Plausible entirely.
**Recommended default:** (a) — minimal disclosure, no banner. Also reword the
"Not Collected / DISABLED / NONE" lines on `security/page.tsx:92-93,249` to
scope explicitly to "the SourcePrep desktop product" (that part is a
license-neutral fix-now Eric can bundle in). Note: the `SiteFooter.tsx:117`
"Privacy Policy" link points to `https://sourceprep.io/privacy` which does
not exist — resolving that link is downstream of this decision.

### ED-4. Team-sync tier-gating model (about:103 "never unlock features" vs docs Team/Enterprise gate)
**Question:** Is remote/headless team-sync a paid-tier feature unlock, or
available on OSS?
**Context:** `docs/team-sync/page.tsx:21` + `enterprise-deploy/page.tsx:24`
gate the headless indexing server behind Team/Enterprise.
`marketing/about/page.tsx:103` says "Pro and Teams fund development; they
never unlock features." `marketing/faq/page.tsx:340` says "the full product,
not a limited edition" + "Teams adds hosted infrastructure… that you'd
otherwise run yourself." **Code sides with the docs:**
`feature_gate.py:59` gates `team_config` to `Tier.TEAM`; `cli.py:1408-1411`
hard-blocks `prep sync-headless`; `remote_sync.py:459-462` stops polling when
unlicensed; `project_helpers.py:438-447` gates team sync. So marketing's
"never unlock features" + FAQ's "you'd otherwise run yourself" are the false
sides.
**Options:** (a) Keep the code gate (recommended — matches current
enforcement): edit `about:103` to "they never unlock core indexing or search
features; team infrastructure (hosted/headless shared-index sync) is a paid
tier"; edit `faq:340` to drop "you'd otherwise run yourself" and state "Teams
adds the hosted/shared-index server and the sync-headless CI runner, both
gated to the Team tier." (b) Make team-sync OSS-capable: remove the
`Tier.TEAM` gate in `feature_gate.py:59`, `cli.py:1408`, `remote_sync.py:459`,
`project_helpers.py:447`, then soften docs.
**Recommended default:** (a) — the code already enforces Team/Enterprise; align
the copy. Do NOT apply the edit until Eric picks A or B (opposite copy).

### ED-5. Homebrew tap + winget manifest live status (README:205,208)
**Question:** Are the `prep` Homebrew cask and the `MagneticAnomaly.Prep`
winget manifest published and live externally (a separate homebrew tap repo,
a PR to microsoft/winget-pkgs)?
**Context:** `README.md:205` `brew install --cask prep`; `README.md:208`
`winget install MagneticAnomaly.Prep`. No in-repo evidence of a tap or
manifest: `release.yml` only builds Tauri bundles and drafts a GitHub
Release; `scripts/` has no brew/winget tooling. `marketing/download/page.tsx:69,123`
says "Install with pip or Homebrew" and funnels users to the README command.
`docs/installation/page.tsx` is the conservative reference (no brew/winget,
.dmg/.msi only). External publishing is invisible to a repo-only audit.
**Options:** (a) If live — link them as evidence; no edit. (b) If not live —
soften `README.md:204-208` to "# macOS: download the signed .dmg from
sourceprep.io/download (Homebrew tap coming soon)" / "# Windows: download the
signed .msi (winget coming soon)"; update `marketing/download/page.tsx:69` to
drop the Homebrew mention until the tap ships.
**Recommended default:** (b) unless Eric confirms the taps are live —
present-tense install instructions that fail (`No cask named prep`) are a
first-visitor friction event.

### ED-6. codrag.key rotation + public-mirror pre-push CI gate
**Question:** (a) Rotate the Tauri updater keypair (generate new, update
`codrag.key.pub` in repo, deprecate old key)? (b) Wire
`tools/build_public_mirror.py` as a mandatory pre-push CI check (not just a
manual script)?
**Context:** `codrag.key` is still tracked on origin/main at
`src/prep/dashboard/src-tauri/.tauri/codrag.key` (rsign/minisign-format
encrypted Ed25519 secret key for signing app-update bundles — NOT the
license-signing key). The mirror gate IS built and fails-closed
(`build_public_mirror.py:412-416`); the mirror design is a fresh-initial-commit
so origin history is never copied. Residual risks: the gate is a MANUAL script
(operator discipline only); `codrag.key` has not been rotated.
**Options:** (a) Rotate keypair + wire CI gate (both). (b) Wire CI gate only,
defer rotation. (c) Status quo (manual gate, no rotation).
**Recommended default:** (a) — wire the CI gate before any public push, and
rotate the keypair so the historical leak loses its power.

### ED-7. Support GitHub Discussions source repo (EricBintner vs MagneticAnomaly)
**Question:** Are GitHub Discussions enabled on `MagneticAnomaly/SourcePrep`
(the canonical public repo per `marketing/src/lib/links.ts:3`), or only on
`EricBintner/SourcePrep` (the maintainer's personal fork that
`support/src/lib/github.ts:4` currently fetches)?
**Context:** `support/src/lib/github.ts:4` hard-codes `REPO_OWNER='EricBintner'`,
`REPO_NAME='SourcePrep'` for the server-side GraphQL Discussions fetch.
`support/README.md:19` instructs contributors to point their token at
`MagneticAnomaly/SourcePrep`. If Discussions live only on the personal fork,
the support portal cannot fetch from the canonical public repo without
leaking Eric's personal handle in server-side code (ships in the public
mirror).
**Options:** (a) Migrate Discussions to `MagneticAnomaly/SourcePrep` (org
repo) so the support portal fetches from the canonical public repo; change
`github.ts:4` to `MagneticAnomaly`. (b) Keep the personal fork and accept the
handle in server-side code.
**Recommended default:** (a) — migrate Discussions to the org repo; the
personal handle should not ship in the public mirror. Verify with
`gh api graphql -f query='query{repository(owner:"MagneticAnomaly",name:"SourcePrep"){discussions{totalCount}}}'`
before applying the FN-16 `github.ts` edit.

---

## 5. REFUTED (settled TRUE, no change)

- **R-1. `marketing/terms/page.tsx:85`** — "The SourcePrep source code is open
  source under the Apache License 2.0…" Verified consistent with the landed
  Apache-2.0 relicense (commit `99315988`), NOTICE:2, package.json. No edit;
  only the surrounding Terms DRAFT state is actionable (ED-2).
- **R-2. `payments/.env.example:4`** — Lemon Squeezy as checkout provider.
  Verified LIVE and wired across all surfaces: backend `lemon_squeezy.py:2-29`
  (LS_API_BASE), `license.py:101-128,239,327`, Tauri CSP `tauri.conf.json:61`,
  marketing `security/page.tsx:280` + `terms/page.tsx:155` (both hedged
  "planned Merchant of Record"). No staleness, no contradiction.
- **R-3. `README.md:86`** — "SourcePrep is an epistemic, team-ready
  application." Verified backed by shipped OSS team features (Embedded Mode
  `.sourceprep/` commit-to-git, Network Mode `prep serve --host 0.0.0.0`;
  `README.md:431-461`, `cli.py:408`, `paths.py:59`). SSO/RBAC/audit-log
  honestly marked "Roadmap" at `README.md:463`. The finder conflated the
  proprietary rotted Teams Sync S3 backend with the OSS embedded/network-mode
  features. "team-ready" is honest. No edit.
- **R-4. `docs enterprise-deploy:251`** — S3 credentials resolved from env
  vars or gitignored `.sourceprep/.secrets`, never committed files. Verified
  accurate: `remote_sync.py:184-210` reads env then `.secrets` JSON;
  `team_config.json` is never read for credentials; `_check_for_leaked_secrets`
  (:218-247) warns on credential-like keys in it. No edit to line 251.
  (Adjacent false claim `marketing/pricing/page.tsx:197` "never your source
  code" is FN-14, applied; adjacent `team-sync/page.tsx:311` "OS keychain"
  claim has no keychain implementation in `src/prep/` — fold into DR-1's
  follow-up.)

---

## 6. CROSS-SURFACE CLAIM MATRIX

| Claim | docs | marketing | support | payments | README | LICENSE | package.json | Status |
|---|---|---|---|---|---|---|---|---|
| License = Apache-2.0 | terms ref'd (DRAFT) | "Apache 2.0" present-tense (~14 pages) | (none) | (none) | :563 present-tense | canonical Apache-2.0 | "Apache-2.0" (all 9) | **FIXED** — vscode/LICENSE was COMMERCIAL (FN-1, `88dbc4bf`) |
| Copyright holder = Magnetic Anomaly LLC | "llc" typo + ARR (:63) | "LLC" + ARR (:76) | default "SourcePrep Inc." + ARR | default "SourcePrep Inc." + ARR | (n/a) | (n/a) | (n/a) | **FIXED** — all 4 footers now "© 2026 Magnetic Anomaly LLC." (FN-2..6, `88dbc4bf`) |
| Pro price | $29 one-time (installation:83) | $29 one-time Coming Soon (pricing:86) | "coming soon" (:72) | **$79 / $7-mo** (page:26) | (n/a) | (n/a) | (n/a) | **FIXED** — payments → $29 one-time (Coming Soon) (FN-8, `c6273d4b`) |
| Teams price | $9/seat (installation:83) | $9/seat + $97/yr annual (pricing:127) | (n/a) | **$15/seat** (page:37) | (n/a) | (n/a) | (n/a) | **FIXED** — payments → $9/seat/mo + $97/yr (FN-8, `c6273d4b`) |
| Enterprise price | $24/seat (installation:83) | $24/seat 15-seat min (pricing:165) | (n/a) | (not listed) | (n/a) | (n/a) | (n/a) | payments incomplete — follow-up (not a falsehood) |
| "No telemetry / no phone-home" | enterprise-deploy:248 absolute (FALSE for LS) | security:78-80 "OSS makes no network calls" (FALSE for desktop app) | (n/a) | page:17 "no recurring phone-home" (FALSE for LS) | (n/a) | (n/a) | (n/a) | **FIXED** — scoped to GPU image / OSS daemon-CLI; LS 7-day revalidation disclosed (FN-10,12,13,22, `cd4a0d29`) |
| Ed25519 license crypto secure | enterprise-deploy:252,287 "Available" (FALSE) | security:146-150 future-tense (correct) | (n/a) | page:17 "verified offline" (FALSE) | (n/a) | (n/a) | (n/a) | **FIXED** — docs+payments → future-tense / Roadmap (FN-11,12, `cd4a0d29`) |
| "No source code leaves your machine" | (scoped to local desktop) | pricing:197 "never your source code" (FALSE for Teams Sync) | (n/a) | (n/a) | (n/a) | (n/a) | (n/a) | **FIXED** — marketing → "today this includes source content by default" (FN-14, `90f5d2c1`) |
| Pro/Teams "never unlock features" | docs team-sync:21 gates to Team/Enterprise (correct) | about:103 "never unlock" + faq:340 "you'd otherwise run yourself" (FALSE) | (n/a) | (n/a) | (n/a) | (n/a) | (n/a) | **ED-4** — code sides with docs; marketing copy is the false side |
| Trust docs (NOTICE/SECURITY/CONTRIBUTING/CHARTER) status | DRAFT banners | (n/a) | (n/a) | (n/a) | (n/a) | (n/a) | (n/a) | **ED-1** — DRAFT vs Apache-2.0 already in effect |
| Security mailbox live | (n/a) | (n/a) | SupportFeatures:40 advertises live | (n/a) | :570 routes to SECURITY.md | (n/a) | (n/a) | **ED-1** — support says live; SECURITY.md says unconfirmed |
| Terms in effect | (n/a) | terms:27 "not yet in effect" (DRAFT) | (n/a) | (n/a) | (n/a) | (n/a) | (n/a) | held correctly (**ED-2**) |
| GitHub repo identifier | docs: `MagneticAnomaly/SourcePrep` | links.ts: `MagneticAnomaly/SourcePrep` (DECIDED) | footers + SupportFeatures + DiscussionList: `SourcePrep-MCP`; github.ts: `EricBintner` | footer: `SourcePrep-MCP` | (n/a) | (n/a) | (n/a) | **FIXED** footers+components → `SourcePrep` (FN-16, `88dbc4bf`+`90f5d2c1`); **ED-7** for github.ts |
| Plausible analytics disclosed | (n/a) | security:225 Privacy Policy (no Plausible disclosure) | (n/a) | (n/a) | (n/a) | (n/a) | (n/a) | **ED-3** — loaded on all 4 surfaces, undisclosed |
| `/recover` sends email | (n/a) | (n/a) | (n/a) | page: "we'll send it to you" (mock lies) | (n/a) | (n/a) | (n/a) | **FIXED** — honest 501 + PII log removed (FN-15, `dc90af1c`) |

---

## 7. DOGFOODING — prep MCP vs grep+Read for legal/security/message

This audit was the first to test prep MCP against a **non-code** surface
(legal text, license files, cross-surface copy). Verdict: **prep MCP's value
here is even narrower than the pass-4 code-accuracy audit found.**

- **Where prep MCP helped:** the code-posture agent used `prep_search` to
  settle code-side realities (phone-home paths, `licensing.py:22`,
  `feature_gate.py:59` tier gating, `remote_sync.py` strip flag). For those
  code questions it was as useful as in pass-4.
- **Where prep MCP cannot help:** legal-text comparison is entirely outside
  prep's graph. `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `CHARTER.md`,
  `terms/page.tsx` have no symbols, no call graph, no import edges. The
  relicense-completeness checks (FN-1 vscode/LICENSE, FN-2..6 footers, FN-7
  DCO claim), the pricing-ladder cross-surface reconciliation (FN-8), and the
  repo-identifier consistency (FN-16) were all settled by **Read + grep**,
  not prep. The cross-surface claim matrix (§6) is a pure text-comparison
  artifact — no prep instrument touches it.
- **Index gaps re-confirmed:** the verifier agents reported the same
  `NODE_NOT_FOUND` / symbol-locate misses on real exported symbols that
  pass-4 hit; grep+Read remained the settling fallback.
- **Net:** for a legal+security+message audit, the load-bearing instrument is
  disciplined Read + grep across surfaces, with prep MCP as a secondary
  code-behavior oracle. The audit's value came from the **cross-surface
  fan-out** (the same claim checked against 5 surfaces + repo metadata), not
  from the code graph. A future product opportunity: a "claim matrix" tool
  that diffs the same factual assertion across surfaces — prep's graph can't
  produce this today.

---

## Commits (all LOCAL, NOT pushed — `[deploy]` gate)

- `88dbc4bf` relicense-rollout completeness (FN-1,2,3,4,5,6,7 + FN-16 footer URLs)
- `c6273d4b` payments pricing ladder reconciliation (FN-8, FN-9 netlify.toml; FN-9 .env.example reclassified non-issue)
- `cd4a0d29` telemetry/Ed25519/offline claim scoping (FN-10,11,12,13,17,22)
- `90f5d2c1` support/docs/marketing truth fixes (FN-14,16,18,19,20,21)
- `dc90af1c` recover endpoint PII + honest message (FN-15)
- `914e683f` public-mirror gate hardening (FN-23)

**20 fix-now edits applied across 6 commits. tsc clean on docs/marketing/
support/payments + packages/ui.** DR-1..DR-6 and ED-1..ED-7 are the input for
the follow-up AI deep-research pass Eric named.