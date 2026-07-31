# Public-Facing Email Strategy Research

**Project:** Magnetic Anomaly LLC + portfolio apps  
**Date:** 2026-07-28  
**Goal:** Determine (a) which of our ~30 email aliases are actually necessary, and (b) how to expose, protect, and manage public-facing email across a multi-product portfolio.

This doc summarizes web-research findings plus a critical evaluation of our own inventory from `MASTER_EMAIL_AUDIT.md`.

---

## 1. TL;DR — Recommended Architecture

For a solo/very-small team running multiple branded products, the simplest maintainable stack is:

- **Human/team email:** **Folio** ($29/mo unlimited domains) or **Fastmail Business** (~$6–10/mo, 100+ domains). Both handle many domains in one account and can reply from the correct receiving address.
- **Transactional + form backend:** **Resend** (free tier: 3k emails/mo, 1 domain; Pro: 10 domains, 50k/mo). Already used by SourcePrep support.
- **Support workflow (later):** **Help Scout** or **Front** only if support becomes multi-person.

For now: use **Folio or Fastmail** for role aliases, **Resend** for transactional sends and form submissions, and avoid catch-all addresses.

---

## 2. Which Email Addresses Does a SaaS/Product Company Actually Need?

The standard public role addresses are:

| Address | Purpose | Keep public? |
|---------|---------|--------------|
| `support@` | General customer support, product help | Yes, but prefer form as primary intake |
| `security@` | Vulnerability reports, responsible disclosure | Yes — required by RFC 2142 / trust norms |
| `privacy@` / `legal@` | Data-subject requests, DPA, legal | Yes, or route through `support@` with privacy tag |
| `billing@` | Invoices, payment failures, refunds | Usually merge into `support@` until volume justifies split |
| `sales@` / `enterprise@` | Sales and procurement | Keep separate if you actively sell enterprise |
| `hello@` / `info@` | Generic catch-all | **Consolidate into `support@`** — duplicates effort |
| `abuse@` | Abuse/spam reports | Only if you run email/infra product |
| `careers@` | Job applications | Only when careers page is live |

**Key principle:** publish the minimum set that satisfies legal/trust needs, then consolidate the rest into `support@` with filters/tags. Splitting aliases is cheap, but *monitoring* multiple inboxes is not.

**Sources:** Bublly Trust Center, Pullsy Security, Pieces Legal Policy, Mailgun/Truncus/Sendlio enterprise security pages; Serif, Keeping, Supportbench shared-inbox guides.

---

## 3. Critical Evaluation of Our Current Inventory

Based on `MASTER_EMAIL_AUDIT.md`, here is the minimum viable launch set and what to do with the rest.

### 3.1 Keep as real, monitored addresses (P0)

| Email | Why | Implementation |
|-------|-----|----------------|
| `support@sourceprep.io` | Referenced on 15+ public surfaces | Folio/Fastmail alias; auto-reply with SLA |
| `security@sourceprep.io` | Trust/launch credibility; `SECURITY.md` promises it | Dedicated alias; auto-forward to founder; add GPG + `security.txt` later |
| `enterprise@sourceprep.io` | Enterprise-deploy guide and sales | Route to founder/BD inbox with enterprise tag |
| `support@applivation.app` | Native diagnostics + marketing support | Folio/Fastmail alias |
| `support@homecolab.app` | Central contact across consumer + Pro sites | Folio/Fastmail alias |

### 3.2 Keep as aliases/routes into `support@` (P1)

| Email | Why | Implementation |
|-------|-----|----------------|
| `privacy@sourceprep.io` | Marketing security page | Alias to `support@` with privacy tag |
| `legal@sourceprep.io` | `NOTICE`, `CHARTER.md`, ToS | Google Group / alias to founder + attorney |
| `billing@sourceprep.io` | Marketing support page | Alias to `support@` with billing tag |
| `licenses@sourceprep.io` | Recovery fallback | Keep mailbox, but automate recovery first |
| `privacy@homecolab.app` | Privacy pages | Alias to `support@homecolab.app` |

### 3.3 Consolidate / remove (P1–P2)

| Email | Action | Rationale |
|-------|--------|-----------|
| `hello@sourceprep.io` | **Redirect to `support@`** | Duplicates `support@` across footer, docs nav, paperclip manifest, Storybook |
| `bugs@sourceprep.io` | **Keep as Resend sender only, not public contact** | Used internally by bug-report API |
| `careers@sourceprep.io` | **Hide / remove until careers page is live** | `_careers` page is underscore-prefixed |
| `support@dinnervision.app` | **Hide / remove until site is live** | Only in `ToS.md`; marketing site not shipped |
| `business@debatehaus.com` | **Delete** | Dead `.env.local.example` placeholder |
| Dead-brand emails (`*@codrag.io`, `*@runprep.io`, `*@prep.io`) | **Scrub from docs and `.env.local.example`** | Confusing and legally inaccurate |

### 3.4 Promised-but-unbuilt flows — keep, hide, or build?

| Flow | Verdict | Why |
|------|---------|-----|
| SourcePrep license recovery email | **Build (P0)** | UI already shows a recovery form; current API returns 501. Either make it work or hide the form. |
| SourcePrep enterprise seat invitation email | **Build (P0)** | `license.py` fakes success. A paid Teams/Enterprise tier cannot ship without real invites. |
| SourcePrep bug-report form reachable | **Fix (P0)** | Resend backend exists but `support.sourceprep.io` serves Storybook. |
| SourcePrep beta waitlist / newsletter | **Build or hide (P1)** | Replace `mailto` waitlist with real capture, or remove the promise. |
| MagneticAnomaly waitlist | **Hide or build (P2)** | FAQ copy is fiction; route to form or remove. |
| DebateHaus beta waitlist | **Hide (P2)** | Prototype only; no backend. |
| DinnerVision beta/contact | **Hide (P2)** | Site not live. |
| HomeColab BusinessAPP 2.0 daily briefing | **Remove / mark abandoned** | Never implemented. |

---

## 4. Public Email vs Contact Forms — What the Research Says

### 4.1 Should we use `mailto:` links or contact forms?

**Use both, contextually:**

- **Primary form** on homepage/contact pages for cold traffic and structured intake.
- **Primary `mailto:`** on pricing, docs, support, and team pages for high-intent users.
- Always provide a visible plain email fallback for users without a configured mail client.

**Conversion evidence:**
- `mailto:` can outperform forms by **+34% to +113%** on mobile/high-intent pages because it removes friction.
- Structured B2B forms can produce **20–30% more qualified leads** when qualification data matters.
- Every required form field reduces submissions by **4–8%**; a 6-field form can lose **30–40%** vs. a low-friction `mailto:`.
- However, only **30–45%** of desktop `mailto:` clicks and **20–35%** of mobile clicks actually result in a sent email.

**Deliverability/trust:**
- Forms are more reliable (independent of visitor's mail client) and easier to protect with honeypots/CAPTCHA.
- `mailto:` signals “real humans” and is expected by technical audiences, but delivery depends on the visitor's client and spam filters.

**Sources:** Flyn, MailtoMaker, Pryce Digital, Montana Banana, Formsprung, Danish Lead Co.

### 4.2 Our current mix

- **SourcePrep:** mostly `mailto:` links on marketing surfaces, one real Resend form (bug report) hidden behind a misconfigured host, one dead form (license recovery).
- **MagneticAnomaly:** real Formspree form, no public email.
- **Applivation:** Netlify form + native `mailto:` diagnostics.
- **HomeColab:** only `mailto:` links.

**Recommendation:** keep `mailto:` as fallback, but make the **form the primary path** on support/contact pages. Add a visible plain-email fallback below the form.

---

## 5. Spam, Harvesting, and Abuse Protection

### 5.1 Do spammers still harvest `mailto:` links?

**Yes.** A 2026 honeypot benchmark found that a bare `mailto:` link was harvested by **100% of observed spammers**. HTML-entity-encoded links blocked **100%** in that same test, but headless-browser bots and AI-assisted scrapers defeat most simple tricks.

**Sources:** Daniliants / noclickbait.news honeypot, OpenReplay, Ross Yanez, Freemail.ai.

### 5.2 Obfuscation effectiveness ranking

| Technique | Effectiveness | Notes |
|-----------|-------------|-------|
| Bare `mailto:` / plain text | ❌ Useless | Harvested by virtually all bots |
| HTML entity / URL encoding | ⚠️ 95–100% vs. simple bots | Fails against headless browsers/DOM parsers |
| CSS `display:none` decoys | ✅ ~100% vs. simple bots | Bots cannot apply stylesheets |
| JS string assembly | ✅ vs. simple bots, weak vs. headless | Address may still appear in source |
| JS interaction-triggered decoding | ✅ Stronger | Requires click before reveal |
| Server-side contact form | ✅ Gold standard | No address exposed in page |

**Recommendation:** do not rely on obfuscation alone. Use a **contact form as the primary path** and layer obfuscation on any exposed `mailto:` links. Avoid CSS reversal tricks — they break accessibility.

### 5.3 Form anti-spam stack

Best practice is **defense in depth**:

1. **Honeypot field** — zero UX friction, blocks ~70–80% of naive bots.
2. **Time-to-submit check** — reject submissions completed in <2–3 seconds.
3. **Rate limiting** — per IP / email / endpoint.
4. **Cloudflare Turnstile** — invisible, no cookies, ~89% spam blocked, ~1% false positives.
5. **Server-side validation** — format, length, referer.
6. **Disposable email detection** — for signup/waitlist forms.
7. **AI/content classifier** (Akismet, CleanTalk) — for high-volume forms.

Double opt-in is appropriate for **newsletter/waitlist** forms, not support forms (delays help).

**Sources:** Daniliants honeypot, Splitforms CAPTCHA comparison, FORMLOVA, Addmoxie, Formester, Creator Security Stack, EmailAlias.io, Barracuda 2025 report.

### 5.4 Protecting a public support inbox

If a real `support@` address must be public:

- Use SPF/DKIM/DMARC on the domain.
- Put the visitor's address in `Reply-To`, not `From`.
- Do not echo user content in auto-replies (spam/phishing injection risk).
- Quarantine suspicious inbound mail for review.
- Consider AI classifiers for triage.

**Sources:** eesel AI (Zendesk spam-relay attack), Mailgun deliverability report, Barracuda 2025 report.

### 5.5 `security@` and responsible disclosure

Best practice is to offer **both a web form and `mailto:security@`**, listed in order of preference via `/.well-known/security.txt` (RFC 9116). For small/new VDPs, a monitored `security@` alias is acceptable; add a form later.

Support it with:
- PGP key for confidential reports
- Clear policy with safe-harbor language
- Acknowledgment within 1–2 business days
- `Expires` field refreshed yearly

**Sources:** RFC 9116, SiteGrade, itrpoka, ResponsibleDisclosure.io, CRA Evidence guide, plus real policies from GACS, Iterate.ai, WeSolve, Casa, LicenseIQ.

---

## 6. Provider Architecture for Multiple Domains

### 6.1 Google Workspace vs Fastmail vs Zoho vs Proton vs Folio vs Migadu

| Provider | Best for | Caveat |
|----------|----------|--------|
| **Google Workspace** | Full collaboration suite (Docs/Meet/Drive) | 30 aliases/user cap; all domains share one tenant/reputation |
| **Fastmail** | Many domains, clean UI, strong aliases | Not a full office suite |
| **Zoho** | Lowest per-user cost | 30-alias cap; utilitarian UI |
| **Proton for Business** | Privacy/E2EE requirement | Most expensive; complicates automated workflows |
| **Folio** | Solo operator with many brands | Flat $29/mo unlimited domains; auto reply-from receiving domain; per-domain reputation |
| **Migadu** | Flat-rate IMAP/SMTP for many domains | Usage/storage soft caps; less hand-holding |

For this portfolio, **Folio or Fastmail** is the right fit: a single account can own all the product domains without per-alias cost explosions.

**Sources:** StackScored, AZDIGI, Google Workspace alias docs, Zoho rates/limits, Fastmail account limits, Proton for Business, Folio comparison, Migadu/Purelymail pricing.

### 6.2 Can Resend/Postmark/SendGrid handle inbound mail too?

Yes — all three support inbound email parsing via webhooks:

- **Resend:** `email.received` webhook; metadata-only, fetch body separately. Free tier: 1 domain; Pro: 10 domains.
- **Postmark:** Full JSON payload including body/attachments. Pro/Platform plans only.
- **SendGrid:** Inbound Parse Webhook. Paid plans with domain auth.

**Caveat:** these are APIs, not human inboxes. You still need a hosted email provider or helpdesk for human replies.

**Sources:** Resend receiving docs, Postmark inbound docs, SendGrid inbound parse docs.

### 6.3 How to reply from the correct domain

Three patterns:

1. **Hosted provider with cross-domain aliases (Folio/Fastmail):** verify each domain, create aliases, set “send-as” identity. Folio does this automatically by receiving domain.
2. **Helpdesk (Help Scout, Front):** add each `support@<domain>` as a mailbox alias/channel; replies go out from the alias automatically.
3. **Custom ESP inbound + app dashboard:** receive via Resend/Postmark webhook, store in your app, send replies via same ESP with correct `From:` domain.

**Recommendation:** start with **Option A (Folio/Fastmail)** and move to Help Scout only when support becomes multi-person.

### 6.4 Catch-all vs explicit aliases

**Use explicit aliases.** Catch-all addresses are a spam magnet, can hurt sender reputation via backscatter, and break DMARC alignment on forwarded mail. If you must use a catch-all, route it to a quarantine mailbox and review it weekly.

### 6.5 SPF / DKIM / DMARC across many domains

- **SPF:** one record per domain, merge includes. Avoid the 10-DNS-lookup limit by using subdomains for different mail streams (e.g., `mail.sourceprep.io` for app mail).
- **DKIM:** separate selectors per service/domain; no lookup limit.
- **DMARC:** start at `p=none; rua=mailto:dmarc@sourceprep.io`, review reports for 2–8 weeks, then move to `quarantine`, then `reject`.
- **Bulk-sender requirements (Gmail/Yahoo):** if any product sends >5,000 emails/day, you need DMARC, aligned SPF+DKIM, valid PTR, one-click unsubscribe, and spam complaint rate <0.3%.

**Sources:** Mailflow Authority, SenderReputation, DeliverabilityChecker, Google sender guidelines, Valimail.

---

## 7. Specific Recommendations for Our Portfolio

### 7.1 Minimum viable launch setup

Provision only these 5 inboxes/aliases:

1. `support@sourceprep.io` (with `hello@`, `billing@`, `licenses@` as aliases/tags)
2. `security@sourceprep.io` (dedicated)
3. `enterprise@sourceprep.io` (route to founder/BD)
4. `support@applivation.app`
5. `support@homecolab.app` (with `privacy@` as alias)

Add later as products ship:
- `support@dinnervision.app` (when site is live)
- `hello@magneticanomaly.llc` or keep Formspree-only
- `hello@debatehaus.com` / beta waitlist (when DebateHaus is real)

### 7.2 Immediate fixes (this week)

1. Fix `support.sourceprep.io` DNS/hosting so it serves the support app, not Storybook.
2. Fix `websites/apps/support/.env.local.example` comment: `bugs@prep.io` → `bugs@sourceprep.io`.
3. Remove or hide `careers@`, DinnerVision `support@`, DebateHaus beta promise, and HomeColab daily-briefing references.
4. Scrub dead-brand emails from old planning docs.

### 7.3 Short-term builds (next 2–4 weeks)

1. Implement automated SourcePrep license recovery via Resend.
2. Implement real enterprise seat invitation emails via Resend.
3. Replace SourcePrep beta waitlist `mailto:` with a real waitlist capture (Resend audiences or loops.so).
4. Add Turnstile + honeypot to MagneticAnomaly Formspree form and Applivation Netlify form.
5. Add visible plain-email fallback under every primary contact form.

### 7.4 Medium-term (next quarter)

1. Set up `security.txt` with PGP key and disclosure policy.
2. Move to `p=quarantine` DMARC after monitoring reports.
3. Evaluate Help Scout if support volume becomes multi-person.
4. Add newsletter signup to SourcePrep blog if you actually plan to send one.

---

## 8. Cost Estimate

| Layer | Provider | Monthly cost |
|-------|----------|-------------:|
| Human/team email (6+ domains) | Folio Holding Co. | ~$29 |
| Transactional + inbound (6+ domains) | Resend Pro | ~$20 |
| Support workflow (if needed) | Help Scout | ~$20–50/user |
| **Starting total** | | **~$49/mo** |

Compare to Google Workspace per product: ~$6–12/mo × separate tenants = quickly becomes $60+/mo just for email identity separation.

---

## 9. Sources

- [Bublly Trust Center](https://www.bublly.com/trust)
- [Pullsy Security](https://pullsy.com/security-at-pullsy/)
- [Pieces Legal Policy](https://github.com/pieces-app/soc-II-policy/blob/main/LEGAL_POLICY_2025_COUNSEL_VERIFIED.md)
- [Mailgun Enterprise Security](https://www.mailgun.com/enterprise/security/)
- [Serif — Shared Inbox Best Practices](https://www.serif.ai/guides/shared-inbox-best-practices)
- [Keeping — Shared Inbox Ultimate Guide](https://www.keeping.com/content/shared-inbox/)
- [TermsFeed — Legal Anatomy of a Contact Form](https://www.termsfeed.com/blog/contact-forms-consent/)
- [CleanTalk — Email Obfuscation in 2026](https://blog.cleantalk.org/email-obfuscation-guide/)
- [OpenReplay — Email Obfuscation Techniques](https://blog.openreplay.com/email-obfuscation-techniques/)
- [Daniliants — Email Address Obfuscation: What Works in 2026](https://daniliants.com/insights/email-address-obfuscation-what-works-in-2026/)
- [Splitforms — Best CAPTCHA for Contact Form](https://splitforms.com/blog/best-captcha-for-contact-form)
- [Splitforms — Stop Contact Form Spam](https://splitforms.com/blog/stop-contact-form-spam)
- [eesel AI — Zendesk Email Spam Filter](https://www.eesel.ai/blog/zendesk-email-spam-filter)
- [RFC 9116 — security.txt](https://www.rfc-editor.org/rfc/rfc9116.html)
- [RFC 2142 — Mailbox Names for Common Services](https://www.rfc-editor.org/rfc/rfc2142.html)
- [Folio — Google Workspace Alternative for Multiple Businesses](https://folioinbox.com/compare/google-workspace-alternative-multiple-businesses)
- [Folio — Single User Multiple Domains](https://folioinbox.com/blog/single-user-multiple-domains-email)
- [Fastmail Account Limits](https://www.fastmail.help/hc/en-us/articles/1500000277382-Account-limits)
- [Resend Receiving Email Docs](https://resend.com/docs/dashboard/receiving/introduction)
- [Postmark Inbound Webhook](https://postmarkapp.com/developer/webhooks/inbound-webhook)
- [Help Scout Mailbox Aliases](https://docs.helpscout.com/article/60-mailbox-aliases)
- [Google Sender Guidelines](https://support.google.com/mail/answer/81126)
- [Mailflow Authority — SPF/DKIM/DMARC for Multiple Senders](https://mailflowauthority.com/email-authentication/spf-dkim-dmarc-multiple-senders)

---

## 10. Related Docs

- `MASTER_EMAIL_AUDIT.md` — the raw inventory of every email alias, provider, form, and promised flow.
- (Future) `SOURCEPREP_EMAIL_ROADMAP.md` — implementation plan for SourcePrep.
