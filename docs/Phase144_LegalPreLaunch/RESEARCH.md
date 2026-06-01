# Phase 144 — Legal Research Questions

> **Read this first.** This doc is the canonical list of open legal
> questions, organized by topic. Each question records: what we need
> to know, who answers it (DIY vs attorney), the deliverable, and
> the current state of our answer. The implementation plan
> (`IMPLEMENTATION_PLAN.md`) executes against this list.
>
> **Operating rule:** every question here gets resolved before Phase
> 142 Part C ships. No "we'll figure it out later."

## How to use this doc

Each question has:

- **Q:** the question
- **Who:** DIY (we can answer with research) | Attorney (needs legal opinion) | Both
- **Deliverable:** what artifact closes the question
- **Status:** Open / Researching / Answered (with date)
- **Notes:** current state of our understanding

When a question is answered, fill in the answer inline and move on.
Do not delete answered questions — the record matters for future
audit.

---

## 1. Trademark

### 1.1 — Is "SourcePrep" available?

- **Q:** Are there same-or-similar marks already registered or in
  common-law use that would conflict with a SourcePrep trademark
  filing?
- **Who:** DIY for initial search; Attorney to confirm clearance
- **Deliverable:** documented search results from USPTO TESS,
  common-law search (Google, GitHub, PyPI, npm, crates.io,
  LinkedIn), and attorney clearance opinion
- **Status:** Open
- **Notes:** Memory says `sourceprep.io` is owned by Eric; confirm.
  STRATEGY.md notes the brand split between "SourcePrep" (user-
  facing) and "prep" (technical). Filing must be on "SourcePrep"
  as the consumer mark.

### 1.2 — Which USPTO classes?

- **Q:** Should we file in Class 9 (downloadable software) only,
  Class 42 (SaaS / software-as-a-service) only, or both?
- **Who:** Attorney
- **Deliverable:** attorney recommendation in writing
- **Status:** Open
- **Notes:** Recommendation in `IMPLEMENTATION_PLAN.md` Part D is
  both classes — Class 9 for the OSS/Pro Tauri downloadable; Class
  42 for the hosted backend launching in Phase 2. Fees: ~$700 total
  for two classes at TEAS Standard.

### 1.3 — TEAS Standard vs TEAS Plus?

- **Q:** TEAS Standard ($350/class, more flexibility) or TEAS Plus
  ($250/class, stricter goods/services description requirements)?
- **Who:** Attorney
- **Deliverable:** attorney recommendation
- **Status:** Open
- **Notes:** TEAS Plus saves $100/class but requires picking from
  USPTO ID Manual descriptions verbatim — fine for standard software
  but inflexible if description needs updating.

### 1.4 — International filings (Madrid Protocol)?

- **Q:** Do we need international trademark protection at Phase 1?
- **Who:** Attorney + business decision
- **Deliverable:** decision recorded with rationale
- **Status:** Open
- **Notes:** Recommendation: US-only at Phase 144. Defer EU/UK/JP
  to a later phase once revenue justifies the ~$5,000+ extension
  cost. Madrid Protocol filing must happen within 6 months of US
  filing to claim US priority date internationally — so this is
  revisitable but should be a *decision*, not a default.

### 1.5 — Defensive name variations?

- **Q:** Should we file "SourcePrep AI," "SourcePrep.io,"
  "SourcePrep Cloud," etc. as defensive marks?
- **Who:** Attorney
- **Deliverable:** decision recorded
- **Status:** Open
- **Notes:** Each additional mark adds fees. Cheap defensive filing
  is to register the primary mark broadly enough that variations
  fall under it. Defer until/unless someone files a conflicting
  variant.

### 1.6 — Logo trademark?

- **Q:** Is there a logo we want to register as a design mark
  separately from the word mark?
- **Who:** DIY (design status) + Attorney (filing strategy)
- **Deliverable:** decision recorded
- **Status:** Open
- **Notes:** Defer until brand visual identity is locked. Word mark
  filing is more urgent.

---

## 2. Patents

### 2.1 — Which candidate methods are genuinely novel?

- **Q:** Of the candidate methods (anchor-overlap concept
  clustering, AIMD concurrency control, multi-pass concept synthesis
  with calibration tiers, trace graph + curated traceability), which
  are genuinely novel + non-obvious + commercially meaningful?
- **Who:** Attorney (1-hour novelty assessment consult)
- **Deliverable:** attorney opinion per method
- **Status:** Open
- **Notes:** Default action per method is **defensive publication
  via blog post**, not patent filing. Patent filings are only
  recommended for methods the attorney specifically flags as clearly
  novel AND commercially meaningful (i.e., something an acquirer
  would value owning).

### 2.2 — Should we file any provisional patents?

- **Q:** For any method the attorney flags in 2.1 as "file
  provisional," what's the cost/benefit?
- **Who:** Both (attorney recommendation + Eric business decision)
- **Deliverable:** decision per method
- **Status:** Open
- **Notes:** Provisional cost is $1,500–3,000 each (including
  attorney time). Buys 12-month priority window before non-
  provisional commitment. Worth doing if attorney is confident on
  novelty; skip if borderline.

### 2.3 — When does Apache 2.0 publication start the patent clock?

- **Q:** Once code embodying a method is published to the public
  mirror, when does the US 12-month window start?
- **Who:** Attorney
- **Deliverable:** documented clock-start rule for each candidate
  method
- **Status:** Open
- **Notes:** Default understanding: the on-sale-bar and prior-art
  rules apply at publication. International rights are typically
  forfeit at publication for jurisdictions without grace periods.
  Confirm with attorney before any public push.

### 2.4 — Defensive publication strategy

- **Q:** For methods we choose not to patent but want to protect
  from being patented by others, how do we establish prior art most
  reliably?
- **Who:** DIY (with attorney sanity-check)
- **Deliverable:** publication plan
- **Status:** Open
- **Notes:** Industry-standard approaches:
  1. Blog post on a dated URL (with publication date in plain text)
  2. arXiv preprint (formal academic timestamp)
  3. IP.com defensive publication service (~$200 per publication)
  4. Apache 2.0 source itself (publication via git commit history)
  Recommendation: blog posts at minimum (cost $0), arXiv for
  anything significant (cost $0), IP.com only if attorney recommends.

---

## 3. Corporate structure

### 3.1 — Is Magnetic Anomaly LLC operating agreement adequate?

- **Q:** Does the current operating agreement protect Eric's
  interests, enable clean acquisition, and align with single-member
  LLC best practices?
- **Who:** Attorney
- **Deliverable:** written attorney opinion + recommended amendments
- **Status:** Open
- **Notes:** Single-member LLCs often have very thin OAs (or just a
  template); attorney should specifically check for: (a) operating
  authority of the sole member, (b) provisions for adding members
  later if Eric brings on a cofounder/employee with equity, (c) IP
  ownership clauses, (d) dissolution/sale provisions.

### 3.2 — Is all SourcePrep IP owned by the LLC, not Eric personally?

- **Q:** Has the IP from work Eric did before forming the LLC, or
  in personal time during LLC operation, been formally assigned to
  the LLC?
- **Who:** Attorney
- **Deliverable:** IP assignment agreement (if needed)
- **Status:** Open
- **Notes:** Critical for acquisition diligence. Buyers want a clean
  chain: developer → LLC → buyer. If any IP is "owned by Eric
  personally" at sale, the buyer needs an extra assignment from Eric,
  which they may or may not agree to. Fix this proactively.

### 3.3 — LLC or convert to Delaware C-Corp?

- **Q:** Should we stay LLC or convert to a Delaware C-Corp before
  any potential acquisition conversation?
- **Who:** Both (attorney + business decision)
- **Deliverable:** decision recorded with rationale + revisit trigger
- **Status:** Open
- **Notes:** Trade-offs:
  - **LLC:** pass-through taxation (simpler), lower ongoing cost,
    sufficient for most acquisitions
  - **C-Corp (Delaware):** standard for VC fundraising and most
    acquirer diligence, QSBS Section 1202 capital gains exclusion
    (potentially $10M+ tax savings if held 5+ years before sale)
  - **QSBS clock starts at C-Corp formation** — if we know we want
    QSBS, convert sooner rather than later
  - **Recommendation:** stay LLC at Phase 144; revisit when (a) an
    acquisition conversation gets to LOI stage, or (b) 6 months
    pass with Teams ARR growing, or (c) any VC conversation starts.
    Document this trigger in `RESEARCH.md`.

### 3.4 — Founder vesting / employment agreement?

- **Q:** Should Eric have a formal vesting schedule and/or
  employment agreement with the LLC?
- **Who:** Attorney
- **Deliverable:** decision + documents if needed
- **Status:** Open
- **Notes:** Acquirers generally prefer founders to have vesting
  agreements even when they own 100% — it signals professionalism
  and provides a template if a cofounder or early hire joins later.
  Standard founder vesting: 4 years, 1 year cliff.

### 3.5 — Bank account, tax setup, EIN

- **Q:** Are bank account, EIN, and federal/state tax registrations
  current and acquisition-friendly?
- **Who:** DIY (with accountant if needed)
- **Deliverable:** confirm everything is current
- **Status:** Open
- **Notes:** Lemon Squeezy handles VAT/sales tax as Merchant of
  Record. We need: business bank account in LLC name (not Eric
  personal), EIN, state tax registration if applicable, annual LLC
  report filed on schedule.

---

## 4. Contributor License Agreement (CLA)

### 4.1 — Apache ICLA template adequate?

- **Q:** Is the standard Apache ICLA (Individual Contributor License
  Agreement) sufficient for our needs?
- **Who:** Attorney
- **Deliverable:** attorney sign-off + customization if needed
- **Status:** Open
- **Notes:** Apache ICLA is the de facto standard for Apache 2.0
  projects. Should be sufficient as-is; attorney just needs to
  confirm we're using the right version and the assignment terms
  protect Magnetic Anomaly LLC.

### 4.2 — Corporate CLA needed?

- **Q:** Do we need a separate Corporate CLA for contributors
  acting on behalf of their employer?
- **Who:** Attorney
- **Deliverable:** decision + document if needed
- **Status:** Open
- **Notes:** Most serious OSS projects have both ICLA and CCLA.
  Recommendation: yes, use both, both Apache-standard templates.

### 4.3 — How is CLA sign-off enforced?

- **Q:** What tooling enforces CLA sign-off on PRs?
- **Who:** DIY
- **Deliverable:** GitHub Action configured + tested
- **Status:** Open
- **Notes:** Standard tools: CLA Assistant (cla-assistant.io),
  Salesforce CLA Bot, or EasyCLA. CLA Assistant is the most common
  free tool and supports both Apache ICLA and custom variants.

### 4.4 — DCO (Developer Certificate of Origin) vs CLA?

- **Q:** Should we use DCO sign-off instead of, or in addition to,
  CLA?
- **Who:** Attorney
- **Deliverable:** decision recorded
- **Status:** Open
- **Notes:** Linux kernel uses DCO; most enterprise OSS projects
  use CLA. CLA provides stronger IP chain (explicit license
  assignment); DCO is lighter-weight (just a sign-off). For
  acquisition readiness, CLA is preferred. Recommendation: CLA
  required, DCO optional/redundant.

---

## 5. License hygiene

### 5.1 — Any GPL/AGPL/SSPL/proprietary dependencies?

- **Q:** Does any transitive dependency in `engine/Cargo.lock`,
  `pyproject.toml` deps, or `package-lock.json` carry a license
  incompatible with Apache 2.0 outbound?
- **Who:** DIY (tools) + Attorney (confirmation of any findings)
- **Deliverable:** clean license report; replacement plan for any
  contamination
- **Status:** Open — Phase 144 Part A executes
- **Notes:** Tools: `cargo deny check licenses`, `pip-licenses`,
  `license-checker`. Any GPL/AGPL contamination blocks launch until
  resolved (replace dep or change our license).

### 5.2 — gstack attribution lineage?

- **Q:** Does any code or pattern in `src/prep/core/atlas/` or the
  `role=` parameter on `prep()` derive from gstack in a way that
  requires attribution?
- **Who:** DIY (Eric inspection) + Attorney (legal opinion if
  borderline)
- **Deliverable:** documented audit + NOTICE attribution if any
- **Status:** Open
- **Notes:** Per STRATEGY.md §"Attribution to gstack," Eric recalls
  adapting some gstack pattern. Apache 2.0 + MIT (gstack license)
  are compatible — credit is the only requirement. Inspect, document,
  and credit in NOTICE if any genuine derivation found.

### 5.3 — LLM-generated code license risk?

- **Q:** Could any LLM-generated code in our codebase accidentally
  match copyrighted code (e.g., Stack Overflow CC-BY-SA, GPL kernel
  code) and create a hidden license-violation risk?
- **Who:** DIY (tools) + Attorney (if scancode flags anything)
- **Deliverable:** `licensee detect` or `scancode-toolkit` run on
  entire repo; manual inspection of any flags
- **Status:** Open
- **Notes:** Per SCRUTINY §16. Low probability but high-cost if hit.
  Run the tools, file findings.

### 5.4 — Apache 2.0 NOTICE file completeness?

- **Q:** What third-party attributions need to be in NOTICE?
- **Who:** DIY (compile from license audit)
- **Deliverable:** complete NOTICE file
- **Status:** Open
- **Notes:** NOTICE contains attribution required by upstream
  licenses (Apache 2.0 § 4(d)), trademark notices, etc. Compiled
  from the license audit findings.

---

## 6. Customer-facing terms

### 6.1 — Terms of Service for sourceprep.io?

- **Q:** Do we need a ToS, and what must it contain?
- **Who:** Both (template + attorney review)
- **Deliverable:** drafted ToS, attorney-reviewed, published before
  Phase 1 launch
- **Status:** Open
- **Notes:** Yes — required for any commercial site. Should cover:
  acceptable use, account terms, payment terms (reference Lemon
  Squeezy ToS), refund policy reference, governing law, liability
  limitation, indemnification.

### 6.2 — Privacy Policy?

- **Q:** What data do we collect at Phase 1 (OSS + Pro) and Phase 2
  (Teams hosted backend), and how must it be disclosed?
- **Who:** Both
- **Deliverable:** drafted Privacy Policy
- **Status:** Open
- **Notes:** Phase 1: minimal (license info, basic analytics on
  sourceprep.io). Phase 2: hosted backend stores embeddings + graph
  metadata. Must comply with GDPR (EU users), CCPA (CA users),
  similar. Privacy Policy must list third-party processors (Lemon
  Squeezy, hosting provider, etc.), data subject rights, retention
  periods, contact.

### 6.3 — EULA for Pro Tauri app?

- **Q:** Do we need a click-through EULA inside the Pro Tauri
  installer?
- **Who:** Attorney
- **Deliverable:** EULA text + integration in Tauri installer
- **Status:** Open
- **Notes:** Pro tier is a paid commercial product even though the
  engine source is Apache 2.0. EULA wraps the Pro binary, license
  key terms, and limits use to per-license-key activation.

### 6.4 — Refund policy?

- **Q:** What's our refund policy for Pro Monthly, Pro Perpetual,
  Teams, Enterprise?
- **Who:** Business decision + Attorney sanity check
- **Deliverable:** documented policy
- **Status:** Open
- **Notes:** Industry standard:
  - Pro Monthly: pro-rated refund within first 14 days
  - Pro Perpetual: 30-day full refund window, no refund after
  - Teams/Enterprise Annual: pro-rated refund within 30 days, no
    refund after
  - All refunds processed by Lemon Squeezy per their merchant
    rules; LS may have stricter policies.

### 6.5 — Subscription terms (auto-renewal)?

- **Q:** How are auto-renewals disclosed and cancellable?
- **Who:** Both (Lemon Squeezy handles much of this)
- **Deliverable:** subscription terms doc
- **Status:** Open
- **Notes:** Lemon Squeezy handles the billing mechanics. Our terms
  must disclose: renewal cadence, notice before renewal, how to
  cancel, what happens on non-renewal (downgrade to OSS, license
  key deactivates).

### 6.6 — Acceptable Use Policy?

- **Q:** What uses are prohibited (especially for Phase 2 hosted
  backend)?
- **Who:** Attorney
- **Deliverable:** AUP document
- **Status:** Open
- **Notes:** Standard prohibitions: indexing third-party code without
  permission, attempting to bypass authentication, reverse-engineering,
  using the service for unlawful purposes, scraping. AUP is most
  relevant to Phase 2 (hosted backend); for Phase 1 OSS the Apache
  2.0 license is the operative document.

### 6.7 — Master Services Agreement template for Enterprise?

- **Q:** Do we need an MSA template ready for Enterprise customers
  whose procurement requires one?
- **Who:** Attorney
- **Deliverable:** MSA template
- **Status:** Open
- **Notes:** Most large customers have their own MSA they'll insist
  on; we react to theirs. But having our own template avoids being
  pushed into unfavorable terms when ours is silent. Defer until
  first Enterprise pipeline opportunity arises — but have a template
  ready before then.

### 6.8 — Data Processing Agreement (DPA) for EU Enterprise?

- **Q:** Do we need a GDPR-compliant DPA template before any EU
  Enterprise customer signs?
- **Who:** Attorney
- **Deliverable:** DPA template
- **Status:** Open
- **Notes:** Only matters once hosted backend ships (Phase 2). Use
  the EU Commission's Standard Contractual Clauses as the base.

---

## 7. Security disclosure infrastructure

### 7.1 — Vulnerability disclosure process

- **Q:** How do researchers report vulnerabilities? What's our SLA?
- **Who:** DIY
- **Deliverable:** `SECURITY.md` with reporting instructions
- **Status:** Open
- **Notes:** Use GitHub's private vulnerability reporting as primary;
  `security@sourceprep.io` email with GPG as secondary. Acknowledge
  within 5 business days. Coordinated disclosure window: 90 days.

### 7.2 — DMCA agent registration

- **Q:** Do we need a registered DMCA agent for safe harbor?
- **Who:** DIY (USPTO filing)
- **Deliverable:** DMCA agent registration confirmation
- **Status:** Open
- **Notes:** $6 USPTO fee, 30 min to file. Required for DMCA §512
  safe harbor on any user-generated content (GitHub Discussions,
  any future hosted backend with user submissions). Cheap; just do
  it.

### 7.3 — Bug bounty program?

- **Q:** Do we offer monetary rewards for vulnerability disclosure?
- **Who:** Business decision
- **Deliverable:** decision recorded
- **Status:** Open
- **Notes:** Recommendation: no formal bounty at Phase 1. Hall-of-
  fame acknowledgment only. Revisit when revenue justifies.

---

## 8. Tax + compliance

### 8.1 — Sales tax nexus

- **Q:** Do we have any sales tax nexus obligations not covered by
  Lemon Squeezy's Merchant-of-Record status?
- **Who:** Accountant or tax attorney
- **Deliverable:** confirmation
- **Status:** Open
- **Notes:** Lemon Squeezy handles VAT/sales tax on transactions
  they process. We need to confirm: any off-platform invoicing
  (Enterprise Setup engagements, Enterprise Plus contracts) requires
  us to handle sales tax. Likely accounting work, not legal.

### 8.2 — 1099 reporting for off-platform engagements

- **Q:** Do we need to issue 1099s or W-9s for anyone we pay (e.g.,
  attorney, contractor)?
- **Who:** Accountant
- **Deliverable:** standard process
- **Status:** Open — accounting workstream, not blocking

---

## 9. Insurance

### 9.1 — E&O / Cyber liability

- **Q:** Do we need professional liability or cyber insurance, and
  at what Phase?
- **Who:** DIY (quotes) + Business decision
- **Deliverable:** quotes + decision
- **Status:** Open
- **Notes:** Recommendation: skip at Phase 1 (no hosted backend, no
  Enterprise customer requiring proof). Revisit before Phase 2 ships
  (hosted backend = customer data = increased liability surface).
  Many Enterprise customers will require proof of insurance in their
  MSA — get quotes ready for when that conversation arises.

### 9.2 — General liability

- **Q:** Do we need general business liability insurance?
- **Who:** DIY (quotes)
- **Deliverable:** quote
- **Status:** Open
- **Notes:** Often bundled with E&O for small tech LLCs. Quote both
  together.

---

## 10. Anti-rug-pull commitment

### 10.1 — CHARTER.md content

- **Q:** What does our "OSS surface stays Apache 2.0 in perpetuity"
  commitment say?
- **Who:** DIY (draft) + Attorney (review)
- **Deliverable:** `CHARTER.md`
- **Status:** Open
- **Notes:** Per SCRUTINY §10. Lessons from Elastic, HashiCorp, Redis:
  community trusts you more if you commit explicitly to not flipping
  licenses. Should state: (a) the OSS components named in
  OPEN_CORE_SPLIT.md will remain Apache 2.0; (b) the Pro/Teams/
  Enterprise components are explicitly proprietary; (c) no plans to
  re-license the OSS components; (d) any change to this commitment
  would only apply to new code, never retroactively.

---

## 11. Existing-customer audit

### 11.1 — Are there current Lemon Squeezy customers?

- **Q:** Does Magnetic Anomaly LLC have any active Lemon Squeezy
  subscriptions or recent one-time purchases?
- **Who:** DIY (Lemon Squeezy dashboard)
- **Deliverable:** customer count + list
- **Status:** Open
- **Notes:** Per SCRUTINY §11. If any exist: customer notice
  required + grandfathering decision. If zero: document the
  all-clear.

### 11.2 — Customer notice content (if needed)

- **Q:** If current customers exist, what do we tell them about the
  OSS pivot?
- **Who:** Attorney (review the notice content)
- **Deliverable:** customer notice email + grandfathering policy
- **Status:** Open
- **Notes:** Skip if 11.1 returns zero.

---

## Decision audit trail

- **2026-06-01** — Phase 144 scaffolded. All questions opened.
- (subsequent entries record decisions as they land)

---

## Summary table — DIY vs Attorney

For quick reference: which questions can Eric answer alone vs which
need legal counsel.

| Section | DIY questions | Attorney questions |
|---|---|---|
| 1. Trademark | 1.1 (initial search) | 1.1 (clearance), 1.2, 1.3, 1.4, 1.5, 1.6 |
| 2. Patents | 2.4 (publication mechanics) | 2.1, 2.2, 2.3 |
| 3. Corporate | 3.5 | 3.1, 3.2, 3.3, 3.4 |
| 4. CLA | 4.3 (tooling) | 4.1, 4.2, 4.4 |
| 5. License hygiene | 5.1 (tools), 5.2 (audit), 5.3 (tools), 5.4 | 5.1 (review findings), 5.2 (if borderline), 5.3 (if flagged) |
| 6. Customer terms | (drafts from templates) | All — review every doc |
| 7. Security | 7.1, 7.2, 7.3 | (review SECURITY.md text) |
| 8. Tax | 8.1, 8.2 (accountant) | — |
| 9. Insurance | 9.1, 9.2 (quotes) | — |
| 10. Anti-rug-pull | 10.1 (draft) | 10.1 (review) |
| 11. Existing customers | 11.1 | 11.2 |

**Estimated attorney time:** 3–5 hours total, $1,200–3,000.
**Estimated DIY time:** ~1 week of Eric's focused work.
