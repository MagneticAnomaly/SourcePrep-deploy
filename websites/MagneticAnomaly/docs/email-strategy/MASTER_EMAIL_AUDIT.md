# Cross-Product Email Touchpoint Audit — Second Pass

**Project:** Magnetic Anomaly LLC + portfolio apps  
**Date:** 2026-07-28 (first pass) / 2026-07-30 (second pass)  
**Scope:** All public websites, apps, backend code, and planning docs listed below  
**Goal:** Identify *every* email we have promised to users (or to ourselves), flag which are real needs, which are stale/dead, and why they exist.

---

## 1. Scope & Method

Two-pass audit.

- **Pass 1:** surface-level scan of website source for hardcoded emails, `mailto:` links, forms, and provider integrations.
- **Pass 2:** deep scan of all planning docs, backend code, native app code, `.env` files, and less obvious terms (`notify`, `alert`, `digest`, `broadcast`, `campaign`, `invite`, `waitlist`).

### Roots audited

| # | Product | Public site path | Native/backend/docs path | Tech |
|---|---------|-------------------|--------------------------|------|
| 1 | **MagneticAnomaly** | `/Volumes/4TB-BAD/HumanAI/CoDRAG/websites/MagneticAnomaly` | (none) | Vite + React |
| 2 | **SourcePrep** | `/Volumes/4TB-BAD/HumanAI/CoDRAG/websites/apps/{marketing,docs,support,payments}` | `/Volumes/4TB-BAD/HumanAI/CoDRAG/src/prep/`, `/Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/`, root trust docs | Next.js + Python |
| 3 | **Applivation** | `/Volumes/Thunderbolt/AI/ApplicationBrowser/web` | `/Volumes/Thunderbolt/AI/ApplicationBrowser/App/`, `Packages/`, `eval/`, `docs/` | Vite + React + Swift |
| 4 | **DebateHaus** | `/Volumes/Thunderbolt/XcodeProjects/DebateHaus/DH/marketing-site` | `/Volumes/Thunderbolt/XcodeProjects/DebateHaus/DH/DebateHaus/`, `DH 2/`, `Docs/` | Next.js + React Native + Firebase |
| 5 | **HomeColab** | `/Volumes/Thunderbolt/XcodeProjects/HomeColab/HomeColabWebsite`, `HomeColabProWebsite` | `/Volumes/Thunderbolt/XcodeProjects/HomeColab/HomeColabApp/`, `Docs/` | Next.js + Swift |
| 6 | **DinnerVision** | `/Volumes/Thunderbolt/XcodeProjects/DinnerVisionApp/DinnerVision/Docs/Marketing/Website/site` | `/Volumes/Thunderbolt/XcodeProjects/DinnerVisionApp/DinnerVision/` | Static HTML + React Native |

---

## 2. Executive Summary

| Metric | Count |
|--------|------:|
| Distinct customer-facing email aliases found | **~30** across `sourceprep.io`, `homecolab.app`, `applivation.app`, plus docs-only/planned addresses |
| Real backends that can send or receive email | **3** (MagneticAnomaly Formspree, Applivation Netlify Forms, SourcePrep support Resend bug-report route) |
| Backends that *send* email programmatically | **1** — SourcePrep support Resend route |
| `mailto:`-only support addresses | **Many** (Applivation, HomeColab, most SourcePrep surfaces) |
| Newsletter / waitlist systems | **0** implemented; **~5** promised in UI/copy/docs |
| Transactional / onboarding emails | **0** implemented; several planned/storyboarded |
| Dead-brand drift (`codag.io`, `runprep.io`, `prep.io`) | **~15 references** in old planning docs and one `.env.local.example` |
| Real mailboxes that must exist before launch | **~12** (see §4.1) |

**Key takeaway:** SourcePrep is the only product with any live email-sending machinery, but it advertises far more aliases than it has mailboxes for. The other products mostly have a single `support@x.app` placeholder. Several promised flows (newsletter, beta waitlist, license recovery, enterprise invitations) are UI fiction.

---

## 3. What Actually Sends Email Right Now

| # | Product | Mechanism | What it sends | To / from | Status | Blocker |
|---|---------|-----------|---------------|-----------|--------|---------|
| 1 | **SourcePrep support** | Resend API in `websites/apps/support/src/app/api/bug-report/route.ts:278` | Bug-report email with logs/diagnostics | From `bugs@sourceprep.io`, reply-to reporter | **Implemented but not reachable** | `support.sourceprep.io` currently serves Storybook instead of the support app |
| 2 | **MagneticAnomaly** | Formspree endpoint `xpwdgvkn` in `src/App.jsx:389` | Contact form submission | To Formspree forwarding rules | **Implemented and reachable** | Need to confirm production endpoint + sender address |
| 3 | **Applivation** | Netlify Forms in `web/marketing/src/pages/SupportPage.jsx` + `support.html` | Support form submission | To Netlify notification rules | **Implemented if Netlify form detection is on** | Not verified deployed |
| 4 | **Applivation native** | `MailtoComposer` in `App/Shared/DiagnosticsReport.swift:36` | Opt-in diagnostics email from inside iOS/macOS app | From user's mail client to `support@applivation.app` | **Implemented in app** | Requires user has a mail account configured |

Everything else is either a `mailto:` link, a hardcoded address with no backend, or planning text.

---

## 4. Email Inventory by Domain

### 4.1 Mailboxes that must be live before public launch

| Domain | Email | Used on / in | Why it exists | Status |
|--------|-------|--------------|---------------|--------|
| `sourceprep.io` | `support@sourceprep.io` | 15+ marketing/payments/docs/support pages, `SUPPORT.md`, blog, pricing, download, security offline help | General support | **Critical — live now or hide links** |
| `sourceprep.io` | `hello@sourceprep.io` | Marketing footer, docs nav, paperclip manifest, UI story | Same role as `support@` | **Duplicate — pick one or redirect** |
| `sourceprep.io` | `enterprise@sourceprep.io` | Docs enterprise-deploy guide | Sales / deployment inquiries | **Active need** |
| `sourceprep.io` | `licenses@sourceprep.io` | Payments recovery page + API response | License recovery fallback | **Active need** |
| `sourceprep.io` | `security@sourceprep.io` | `SECURITY.md`, marketing security page, `CODE_OF_CONDUCT.md`, support features | Security vulnerability reports | **Critical — explicitly called out as not yet live in `SECURITY.md`** |
| `sourceprep.io` | `privacy@sourceprep.io` | Marketing security page | Privacy/data requests | **Active need** |
| `sourceprep.io` | `legal@sourceprep.io` | `NOTICE`, `CHARTER.md`, marketing ToS page | Legal inquiries | **Active need** |
| `sourceprep.io` | `billing@sourceprep.io` | Marketing support page | Billing questions | **Active need** |
| `sourceprep.io` | `careers@sourceprep.io` | Marketing `_careers` page (currently underscore-prefixed, likely hidden) | Job applications | **Active if careers page goes live** |
| `sourceprep.io` | `bugs@sourceprep.io` | Support Resend route, `netlify.toml` | Internal bug-report routing | **Active need** |
| `applivation.app` | `support@applivation.app` | Marketing support/Terms/Privacy, native diagnostics composer | User support + diagnostics | **Active need** |
| `homecolab.app` | `support@homecolab.app` | Consumer + Pro marketing, support site, ToS, refund, privacy, download | User support | **Active need** |
| `homecolab.app` | `privacy@homecolab.app` | Privacy pages | Privacy questions | **Active need** |
| `dinnervision.app` | `support@dinnervision.app` | Docs `ToS.md` only | Planned support contact | **Not surfaced in shipped code yet** |
| `debatehaus.com` | `business@debatehaus.com` | Stale `.env.local.example` placeholder | Dead SendGrid contact idea | **Dead / ignore** |
| `debatehaus.com` | *(none)* | “Request Beta Access” CTA implies future email | Future beta signup | **Not decided yet** |
| `magneticanomaly.llc` | *(none public)* | Formspree form only | Agency contact | **Consider adding a reply-from address** |

### 4.2 Internal / staging / demo-only emails

| Email | Where | Why it exists | Status |
|-------|-------|---------------|--------|
| `demo@dinnervision.test` | `DinnerVision/scripts/firebase/.env:12`, seed fixtures | Firebase demo user | Internal/dev only |
| `sarah@homecolab.com`, `newagent@homecolab.com`, etc. | HomeColab Pro mock data | UI prototype demo data | Mock only |
| Various `*@example.com`, `*@gmail.com` | Applivation tests/eval corpus, HomeColab mock data | Test fixtures | Internal only |
| `devops@debatehaus.com`, `devops-pager@debatehaus.com` | DebateHaus quality-gates docs | Ops placeholder | Planning-only, not implemented |
| `stats@<our-domain>` (unspecified) | Applivation success-measurement design doc | Planned stats sharing | Unimplemented |

---

## 5. Findings by Product

### 5.1 MagneticAnomaly (`magneticanomaly.llc`)

| Email / Provider | Purpose | Where | Status |
|------------------|---------|-------|--------|
| Formspree endpoint `xpwdgvkn` | Secure contact form (`email`, `subject`, `message`) | `src/App.jsx:386-483` | **Implemented UI + backend** |
| *(none public)* | No hardcoded public email | — | — |
| `href="#"` footer links | Privacy Policy / Terms of Service | `src/App.jsx:532-534` | **Dead links / TODO** |
| Waitlist copy | FAQ says “join our waitlist below” | `src/App.jsx:434-436` | **Routes to same contact form** |

**Why it exists:** Agency storefront. Single promised touchpoint is the CommLink contact form.

**Gaps:**
- No reply-from address exposed; users get Formspree auto-responder only.
- Privacy/terms pages missing.
- Waitlist is copy fiction.

---

### 5.2 SourcePrep (`sourceprep.io`)

#### 5.2.1 Live code that touches email

| What | Where | Status |
|------|-------|--------|
| Resend bug-report email sender | `websites/apps/support/src/app/api/bug-report/route.ts:207-287` | **Sends email, but site host is misconfigured** |
| License recovery endpoint (returns 501, tells user to email) | `websites/apps/payments/src/app/api/recover/route.ts:54` | **Not implemented** |
| Enterprise seat invitation (returns fake success, no email sent) | `src/prep/api/routers/license.py:419-455`; UI in `packages/ui/src/components/enterprise/EnterpriseAdminPanel.tsx` | **UI fiction** |
| License email validation/storage | `src/prep/api/routers/license.py:426-431` | **Backend stores email, never sends** |

#### 5.2.2 Public `mailto:` links and footer contacts

| Email | Surfaces | Why it exists |
|-------|----------|---------------|
| `support@sourceprep.io` | Marketing home, pricing, download, support, compare pages, changelog; payments site; docs nav; support app `SupportFeatures.tsx`; root `SUPPORT.md` | General support + beta waitlist substitute |
| `hello@sourceprep.io` | Marketing `ClientLayout.tsx`, docs `ClientLayout.tsx`, paperclip manifest, SiteFooter story | General contact (duplicates support) |
| `enterprise@sourceprep.io` | Docs enterprise-deploy guide | Enterprise sales |
| `security@sourceprep.io` | Marketing security page, support features, root `SECURITY.md`, `CODE_OF_CONDUCT.md` | Security disclosure |
| `privacy@sourceprep.io` | Marketing security page | Privacy/data requests |
| `legal@sourceprep.io` | Marketing terms page, root `NOTICE`, `CHARTER.md` | Legal |
| `billing@sourceprep.io` | Marketing support page | Billing |
| `careers@sourceprep.io` | Marketing `_careers` page | Hiring |
| `licenses@sourceprep.io` | Payments recovery page + API error message | License recovery fallback |

#### 5.2.3 Promised but not built

| Flow | Evidence | Gap |
|------|----------|-----|
| Newsletter / “Stay in the loop” | `marketing/src/app/blog/page.tsx:107-123` | Links to X + RSS only |
| Beta waitlist (replaces newsletter) | Pricing page `mailto:support@sourceprep.io?subject=...waitlist` | No list capture |
| License recovery email | `payments/api/recover/route.ts` | Returns 501 |
| Enterprise seat invitation email | `src/prep/api/routers/license.py` | Fakes success message |
| Monthly seat-reconciliation / budget-alert emails | `docs/Phase06_Team_And_Enterprise/ENTERPRISE_ADMIN_DESIGN.md:611,1234,1384` | Future feature |

#### 5.2.4 Stale brand drift

| Dead address | Where | Assessment |
|--------------|-------|------------|
| `support@codrag.io` | `docs/Phase42_BetaAccess/PLAN.md:19-20` | Dead brand |
| `support@runprep.io`, `security@runprep.io`, etc. | `docs/superpowers/specs/2026-04-21-prep-rename-design.md:348`; `docs/Phase20_support_strategy/README.md`; `docs/Phase27_bug-reporting/README.md` | Dead brand |
| `hello@runprep.io`, `billing@runprep.io`, `privacy@runprep.io`, `careers@runprep.io`, `legal@runprep.io` | `docs/Phase12_Marketing-Documentation-Website/OPEN_QUESTIONS.md:144-150` | Dead brand / historical plan |
| `bugs@runprep.io` | `docs/Phase27_bug-reporting/README.md`; `docs/Phase12_Marketing-Documentation-Website/DEPLOYMENT.md` | Dead brand |
| `bugs@prep.io` | `websites/apps/support/.env.local.example:9` (comment) | Stale default; code/netlify use `bugs@sourceprep.io` |

**Why these emails exist:** SourcePrep is the flagship product with the most customer touchpoints: sales, support, security, billing, legal, careers, licensing, and internal bug routing.

**Critical blockers:**
1. `support.sourceprep.io` serves Storybook — the bug-report API and admin dashboard are unreachable.
2. `security@sourceprep.io` is advertised but explicitly noted as not yet provisioned.
3. `hello@` and `support@` duplicate each other; `hello@` should probably become a redirect or be removed.
4. `.env.local.example` comment still says `bugs@prep.io`.

---

### 5.3 Applivation (`applivation.app`)

| Email / Provider | Purpose | Where | Status |
|------------------|---------|-------|--------|
| `support@applivation.app` | Marketing support/Terms/Privacy mailto | `web/marketing/src/pages/{Support,Terms,Privacy}Page.jsx` | **Active UI only** |
| Netlify Forms | Support form handler (`name`, `email`, `message`) | `web/marketing/src/pages/SupportPage.jsx`; `support.html` | **Implemented** |
| `MailtoComposer` | Native iOS/macOS diagnostics email | `App/Shared/DiagnosticsReport.swift:36`; `SettingsViews/DiagnosticsView.swift:90-96` | **Active in app** |
| `VITE_BETA_URL` | TestFlight/beta signup CTA (external URL, not email) | `web/marketing/.env.example`; `AppStoreBadge.jsx` | **Env-driven** |
| `stats@<our-domain>` | Planned stats sharing via mailto | `docs/Phase12_success_measurement/02_design.md:246` | **Unimplemented** |
| `support@applivation.app` | TODO to create mailbox | `TODO_2026-06-30_app_store_rollout.md:16` | **Planned** |

**Why it exists:** Native app needs support contact and opt-in diagnostics. Marketing site needs a support form.

**Gaps:**
- The mailbox itself is still a TODO in the app-store rollout doc.
- No newsletter, no welcome email, no beta email list.

---

### 5.4 DebateHaus

| Email / Provider | Purpose | Where | Status |
|------------------|---------|-------|--------|
| *(none in current marketing site)* | — | — | — |
| `business@debatehaus.com` | Stale SendGrid contact placeholder | `DebateHaus_web/.env.local.example:29-30` | **Dead / never wired** |
| `devops@debatehaus.com`, `devops-pager@debatehaus.com` | Ops placeholders | `DH/Docs/08-quality-gates/` | **Planning-only** |
| SendGrid | Email notifications (planned) | `DH 2/DebateHausBroken/docs/` and `functions/index.js` (channel declared, never used) | **Stale / dead code** |
| “Request Beta Access” CTA | Implies future waitlist | `DH/marketing-site/src/app/iterations/01-alpha/page.tsx:94-95` | **UI only** |

**Why it exists:** DebateHaus is a prototype. The only email need is an eventual beta-access/waitlist address.

**Recommendation:** Treat as future need; no mailboxes required now.

---

### 5.5 HomeColab (`homecolab.app`)

| Email / Provider | Purpose | Where | Status |
|------------------|---------|-------|--------|
| `support@homecolab.app` | Central support email across consumer + Pro sites | `HomeColabWebsite/content/copy.ts`; footer, download, getting-started, ToS, refund pages; support site; Pro site | **Active UI only (`mailto:`)** |
| `privacy@homecolab.app` | Privacy page contact | Privacy pages in both sites | **Active UI only** |
| Mock agent emails | Pro dashboard demo data | `HomeColabProWebsite/lib/mock-*.ts` | **Mock only** |
| Daily briefing email (SendGrid) | BusinessAPP 2.0 planned feature | `HomeColabApp/Docs/2.0/BusinessAPP/Phase04_DESIGN/DAILY_BRIEFING_SPEC.md`; `MASTER_TODO.md` | **Planned / stale** |
| Firebase Extension + SendGrid | Planned email delivery | Same docs | **Never implemented** |
| “Resend Invite” button | In-app invite re-send (Firestore-based, not email) | `HomeColabApp/Views/Settings/SettingsView.swift:193-200` | **In-app only** |

**Why it exists:** Consumer/Pro marketing sites need a single support mailbox. Research docs explicitly chose `mailto:` link over contact form.

**Gaps:**
- No mailbox creation confirmed.
- BusinessAPP 2.0 daily briefing email is a future/unimplemented idea.

---

### 5.6 DinnerVision (`dinnervision.app`)

| Email / Provider | Purpose | Where | Status |
|------------------|---------|-------|--------|
| `support@dinnervision.app` | Planned support contact in ToS | `DinnerVision/Docs/Legal/ToS.md:97,180` | **Docs-only** |
| `demo@dinnervision.test` | Firebase demo user | `scripts/firebase/.env`; seed fixtures | **Dev-only** |
| “TestFlight beta access coming soon.” | Teaser, no signup | `site/placeholder.html:35` | **UI placeholder** |
| Footer “Support” link (`href="#"`) | Dead link | `site/index.html:186` | **TODO** |
| Planned footer contact email | Design spec | `ia_copy_and_storyboard.md:33` | **TODO** |

**Why it exists:** Marketing site is informational. Only need is a future support contact.

**Recommendation:** Create `support@dinnervision.app` and add it to footer once the static site is rebuilt.

---

## 6. Consolidated List of Promised-but-Unbuilt Email Flows

| # | Product | Promised flow | Evidence | Why it matters | Priority |
|---|---------|---------------|----------|----------------|----------|
| 1 | SourcePrep | License recovery email | `payments/api/recover/route.ts` returns 501 + mailto | Users already see a recovery form; it should work | **High** |
| 2 | SourcePrep | Newsletter / “Stay in the loop” | `marketing/blog/page.tsx` | Blog promises a loop; currently only social links | Medium |
| 3 | SourcePrep | Beta waitlist capture | Pricing page mailto subjects | Replace mailto with real waitlist | Medium |
| 4 | SourcePrep | Enterprise seat invitation email | `src/prep/api/routers/license.py` fakes success | Teams feature can't launch without real invites | **High** |
| 5 | SourcePrep | Bug-report form reachable on support site | Support site host serves Storybook | Existing backend can't be reached | **High** |
| 6 | SourcePrep | Monthly seat-reconciliation / budget alerts | `ENTERPRISE_ADMIN_DESIGN.md` | Future enterprise feature | Low |
| 7 | MagneticAnomaly | Waitlist backend | FAQ copy | Currently shares contact form | Low |
| 8 | DebateHaus | Beta waitlist | “Request Beta Access” CTA | Future need | Low |
| 9 | DinnerVision | Beta signup + footer contact | Placeholder + design spec | Future need | Low |
| 10 | HomeColab | Daily briefing email (BusinessAPP 2.0) | `DAILY_BRIEFING_SPEC.md` | Future feature, may be abandoned | Low |
| 11 | Applivation | Stats sharing via mailto | Success-measurement design doc | Unimplemented optional feature | Low |

---

## 7. Stale / Dead References to Ignore or Clean Up

| Reference | Where | Why it can be ignored |
|-----------|-------|----------------------|
| `support@codrag.io` | `docs/Phase42_BetaAccess/PLAN.md` | Dead brand, old doc |
| `*@runprep.io` family | Multiple Phase 12/20/27 docs | Dead brand |
| `bugs@prep.io` default comment | `websites/apps/support/.env.local.example:9` | Code/netlify use `bugs@sourceprep.io`; fix the comment |
| `business@debatehaus.com` + SendGrid placeholder | `DebateHaus_web/.env.local.example` | Never consumed by code; old prototype |
| SendGrid email notifications in DebateHausBroken | `DH 2/.../functions/index.js` | Dead/abandoned codebase |
| `devops@debatehaus.com` | Quality-gates docs | Internal ops placeholder |
| Mock/example emails (`*@example.com`, `*@gmail.com`) | Tests, eval corpus, mock data | Not user-facing |
| `user@example.com` placeholders | Storybook legacy research, research docs | Not live |
| `stats@<our-domain>` | Applivation design doc | Unimplemented optional feature |

**Action:** do a cleanup pass on docs to remove dead-brand email references and fix the `.env.local.example` comment.

---

## 8. Recommendations

1. **Provision mailboxes first.** The minimum viable set is:
   - `support@sourceprep.io` (drop or redirect `hello@`)
   - `security@sourceprep.io`
   - `enterprise@sourceprep.io`
   - `legal@sourceprep.io`
   - `billing@sourceprep.io`
   - `licenses@sourceprep.io`
   - `bugs@sourceprep.io`
   - `privacy@sourceprep.io`
   - `support@applivation.app`
   - `support@homecolab.app`
   - `privacy@homecolab.app`
   - `support@dinnervision.app` (when site is live)
2. **Consolidate SourcePrep public addresses.** `hello@` and `support@` should not both be public. Pick `support@sourceprep.io` as canonical and make `hello@` a redirect.
3. **Fix the support site host.** `support.sourceprep.io` serving Storybook blocks the bug-report form and admin dashboard.
4. **Fix license recovery.** The `/api/recover` route should send the key automatically or the page should be hidden.
5. **Implement real enterprise seat invitations.** The fake success message in `src/prep/api/routers/license.py` is a liability.
6. **Choose one provider.** Resend is already in use for SourcePrep; standardize on it across the portfolio to simplify DNS/SPF/DKIM.
7. **Add waitlist/newsletter capture where promised.** SourcePrep blog/pricing, DebateHaus beta, DinnerVision beta, MagneticAnomaly waitlist.
8. **Scrub dead-brand references.** `codrag.io`, `runprep.io`, `prep.io` in docs and `.env.local.example`.
9. **Create per-product roadmaps.** Start with SourcePrep because it has the most urgency and existing infrastructure.

---

## 9. Next Steps

1. Eric confirms the mailbox matrix above (which aliases, which inboxes, Google Workspace vs Resend forwarding).
2. Fix immediately:
   - `support.sourceprep.io` DNS/hosting
   - `websites/apps/support/.env.local.example` comment (`bugs@prep.io` → `bugs@sourceprep.io`)
   - Decide `hello@` vs `support@`
3. Write per-product implementation plans:
   - `SOURCEPREP_EMAIL_ROADMAP.md`
   - `APPLIVATION_EMAIL_ROADMAP.md`
   - `HOMECOLAB_EMAIL_ROADMAP.md`
   - `DINNERVISION_EMAIL_ROADMAP.md`
   - `DEBATEHAUS_EMAIL_ROADMAP.md`
   - `MAGNETICANOMALY_EMAIL_ROADMAP.md`

---

## 10. Appendix: Raw Audit Source Notes

This master doc consolidates findings from six parallel subagent sweeps. Key files that were surfaced:

- SourcePrep Resend bug route: `websites/apps/support/src/app/api/bug-report/route.ts:207-287`
- SourcePrep license recovery: `websites/apps/payments/src/app/api/recover/route.ts`
- SourcePrep enterprise seat invite: `src/prep/api/routers/license.py:419-455`
- Applivation native mailto: `App/Shared/DiagnosticsReport.swift:36`
- DebateHaus dead SendGrid placeholder: `DebateHaus_web/.env.local.example:29-30`
- HomeColab BusinessAPP email spec: `HomeColabApp/Docs/2.0/BusinessAPP/Phase04_DESIGN/DAILY_BRIEFING_SPEC.md`
- DinnerVision ToS support address: `DinnerVision/Docs/Legal/ToS.md:97,180`
- Dead brand references: `docs/Phase42_BetaAccess/PLAN.md`, `docs/Phase12_.../OPEN_QUESTIONS.md`, `docs/Phase27_bug-reporting/README.md`, `websites/apps/support/.env.local.example`
