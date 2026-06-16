# Phase 144 — Legal Research Questions

> **Read this first.** This doc is the canonical list of open legal
> questions, organized by topic. Each question records: what we need
> to know, who answers it, the deliverable, and the current state of
> our answer. The implementation plan (`IMPLEMENTATION_PLAN.md`)
> executes against this list.
>
> **Operating rule:** every question here gets a decision (even a
> default decision) before Phase 142 Part C ships. The doc records
> our reasoning so a future reader (Eric, an acquirer's diligence
> team, or a future model session) can audit how we got there.
>
> **Reality check (2026-06-15):** SourcePrep has zero users, zero
> revenue, zero exposure, and a solo bootstrap budget. The legal
> risk profile at this stage is very different from "ready to take
> Series A." We use industry-standard defaults + DIY tools wherever
> defensible, and defer attorney review to *trigger events* (first
> paying customer, first external contributor, first acquirer LOI,
> first EU/regulated buyer) rather than treating every question as
> "need to pay a lawyer first."

## How to use this doc

Each question has:

- **Q:** the question
- **Who:** DIY / Attorney / Both / Pending Eric / Future-research
- **Deliverable:** what artifact closes the question
- **Status:** Open / Researching / Decided / Deferred / Answered / Pending Eric
- **Notes:** current state of our understanding

Status meanings:
- **Decided** — answered with sufficient confidence for current stage
- **Deferred** — explicit decision to revisit at a named trigger
- **Answered** — fully closed, no further action expected
- **Pending Eric** — only Eric can answer (needs his memory or his document)
- **Future-research** — saved for a deeper research pass with a more
  capable future model (the "Fabel AI" bucket)

When a question is answered, fill in the answer inline and move on.
Do not delete answered questions — the record matters for future audit.

---

## 1. Trademark

### 1.1 — Is "SourcePrep" available?

- **Q:** Are there same-or-similar marks already registered or in
  common-law use that would conflict with a SourcePrep trademark
  filing?
- **Who:** DIY for initial search; Attorney to confirm clearance
  before final filing
- **Deliverable:** documented search results from USPTO TESS,
  common-law search (Google, GitHub, PyPI, npm, crates.io,
  LinkedIn), and attorney clearance opinion at filing time
- **Status:** Researching (2026-06-08)
- **Notes:** Eric owns `sourceprep.io` and it is live. Common-law
  search across GitHub, PyPI, NPM, and Crates.io returned zero
  exact matches for "SourcePrep", which is a strong signal for
  clearance. STRATEGY.md notes the brand split between "SourcePrep"
  (user-facing) and "prep" (technical). Filing must be on
  "SourcePrep" as the consumer mark.
- **Remaining action:** USPTO TESS search at https://tmsearch.uspto.gov/
  (30 min, free). Search exact "SOURCEPREP" + phonetic variants
  in Classes 9 + 42. Document hits or all-clear in this doc.

### 1.2 — Which USPTO classes?

- **Q:** Should we file in Class 9 (downloadable software) only,
  Class 42 (SaaS / software-as-a-service) only, or both?
- **Who:** Decided (industry default)
- **Deliverable:** filing prepared for both classes
- **Status:** Decided (2026-06-15)
- **Notes:** **File both Class 9 + Class 42.** This is the standard
  pattern for products that ship both as downloadable software (the
  OSS CLI/daemon, the Pro Tauri installer) and as SaaS (the Phase 2
  Teams/Enterprise hosted backend). Comparable products
  (GitHub, JetBrains, Cody/Sourcegraph) file in both classes. Total
  fees: ~$500 (TEAS Plus, see 1.3) or ~$700 (TEAS Standard).

### 1.3 — TEAS Standard vs TEAS Plus?

- **Q:** TEAS Standard ($350/class, more flexibility) or TEAS Plus
  ($250/class, stricter goods/services description requirements)?
- **Who:** Decided (cost optimization)
- **Deliverable:** TEAS Plus filing prepared
- **Status:** Decided (2026-06-15)
- **Notes:** **TEAS Plus.** Saves $200 across two classes. TEAS Plus
  requires using descriptions from the USPTO Acceptable Identification
  of Goods and Services Manual verbatim, which has good entries for
  "computer software for code analysis" (Class 9) and "providing
  online non-downloadable software for code analysis" (Class 42).
  Standard software products fit comfortably; the flexibility cost
  of TEAS Plus is negligible at this stage.

### 1.4 — International filings (Madrid Protocol)?

- **Q:** Do we need international trademark protection at Phase 1?
- **Who:** Decided (business decision)
- **Deliverable:** decision recorded with revisit trigger
- **Status:** Deferred (2026-06-15)
- **Notes:** **US-only at Phase 1.** Madrid Protocol extension adds
  ~$5,000+ in fees. Defer until: (a) meaningful EU/UK/JP customer
  pipeline exists, OR (b) acquirer conversation requires international
  rights. **Trigger to revisit:** within 6 months of US filing (to
  preserve priority date if we choose to extend).

### 1.5 — Defensive name variations?

- **Q:** Should we file "SourcePrep AI," "SourcePrep.io,"
  "SourcePrep Cloud," etc. as defensive marks?
- **Who:** Decided
- **Deliverable:** decision recorded
- **Status:** Deferred (2026-06-15)
- **Notes:** **Skip.** The primary "SourcePrep" word mark filed
  broadly enough covers descriptive variants under the doctrine of
  trademark equivalents. Revisit only if someone files a confusingly
  similar variant.

### 1.6 — Logo trademark?

- **Q:** Is there a logo we want to register as a design mark
  separately from the word mark?
- **Who:** Pending Eric (design status)
- **Deliverable:** decision recorded
- **Status:** Deferred (2026-06-15)
- **Notes:** Defer until brand visual identity is locked. Word mark
  filing is more urgent. **Trigger to revisit:** when final logo
  ships on sourceprep.io.

---

## 2. Patents

### 2.1 — Which candidate methods are genuinely novel?

- **Q:** Of the candidate methods (anchor-overlap concept
  clustering, AIMD concurrency control, multi-pass concept synthesis
  with calibration tiers, trace graph + curated traceability), which
  are genuinely novel + non-obvious + commercially meaningful?
- **Who:** Decided (engineer's self-assessment); Future-research for
  formal novelty opinion
- **Deliverable:** decision per method
- **Status:** Decided (2026-06-15) — skip patents; defensive
  publication only
- **Notes:** Honest engineer's-eye assessment:
  - **Anchor-overlap clustering for concept promotion:** the
    underlying algorithm (agglomerative clustering on Jaccard-style
    overlap) is decades old. The *application* to LLM-derived
    concept promotion is novel but likely faces Alice §101 abstract-
    idea scrutiny — software patents on "apply X clustering to Y
    domain" routinely lose at USPTO.
  - **AIMD concurrency control for LLM rate discovery:** AIMD itself
    is TCP-old (Jacobson 1988). The application to cloud LLM rate
    discovery is borderline; possibly defensible but not a slam-dunk.
  - **Multi-pass concept synthesis with calibration tiers:** the
    named-tier rubric pattern is interesting but well-trodden in
    LLM-eval circles.
  - **Trace graph + curated traceability:** traceability is a 30+
    year-old discipline; our specific combination is novel as an
    integration but not as a method.
  - **Conclusion:** none of these are slam-dunk patentable. A patent
    attorney *might* disagree on AIMD-for-LLMs specifically. Cost-
    benefit doesn't support filing at zero-revenue/zero-exposure
    stage when defensive publication is free.
- **Future-research trigger:** if an acquirer specifically values
  patent-protected IP, revisit with a patent attorney before LOI.

### 2.2 — Should we file any provisional patents?

- **Q:** For any method, what's the cost/benefit of provisional
  filing?
- **Who:** Decided
- **Deliverable:** decision per method
- **Status:** Decided (2026-06-15) — skip
- **Notes:** **Skip.** Per 2.1, none of the candidate methods rise
  to the level of "clearly novel + commercially critical." $1,500-
  3,000 per provisional × N methods is real money at bootstrap
  stage with no offsetting expected return.

### 2.3 — When does Apache 2.0 publication start the patent clock?

- **Q:** Once code embodying a method is published to the public
  mirror, when does the US 12-month window start?
- **Who:** Decided (general public knowledge)
- **Deliverable:** documented clock-start rule
- **Status:** Decided (2026-06-15)
- **Notes:** Standard rules:
  - **US:** 35 USC §102(b)(1) provides a 1-year grace period from
    the date of public disclosure (publication, sale, public use).
    First public commit to the public mirror under Apache 2.0
    starts this clock. After 12 months, the method enters the prior
    art and is unpatentable by anyone.
  - **EU / most international jurisdictions:** no grace period.
    Public disclosure forfeits patent rights immediately.
  - **Conclusion:** since we are not patenting (per 2.1, 2.2),
    the clock is moot. Defensive publication is the explicit goal —
    publish broadly, establish prior art at $0 cost, prevent others
    from patenting against us.

### 2.4 — Defensive publication strategy

- **Q:** How do we establish prior art most reliably for methods
  we're not patenting?
- **Who:** Decided (DIY)
- **Deliverable:** publication plan
- **Status:** Decided (2026-06-15)
- **Notes:** **Multi-channel publication for redundant timestamping:**
  1. Apache 2.0 source itself — git commit timestamps in the public
     mirror are legally cognizable prior art for the embodied methods
  2. Blog posts on sourceprep.io with explicit publication dates
     in plain-text headers (Phase 142 Part G blog posts cover this)
  3. arXiv preprint for any method substantial enough to warrant
     formal academic treatment (free, includes formal timestamp +
     DOI)
  4. IP.com defensive publication ($200/publication) — skip unless a
     specific method warrants belt-and-suspenders coverage
- **Action queued for Phase 142 Part G:** ensure each technical blog
  post explicitly describes one or more of the candidate methods so
  prior art is established at OSS launch.

---

## 3. Corporate structure

### 3.1 — Is Magnetic Anomaly LLC operating agreement adequate?

- **Q:** Does the current operating agreement protect Eric's
  interests, enable clean acquisition, and align with single-member
  LLC best practices?
- **Who:** Future-research (needs document inspection by attorney
  or capable AI with the OA in hand)
- **Deliverable:** written opinion + recommended amendments
- **Status:** Future-research (2026-06-15)
- **Notes:** Single-member LLCs often have very thin OAs (or just a
  template). At zero-users / zero-revenue, the OA mostly matters at
  acquisition time. **Trigger to escalate:** first acquirer LOI or
  first VC term sheet, whichever lands first. Until then, document
  inspection by a future research pass is sufficient.
  - **Checklist for that future review:** (a) operating authority of
    the sole member, (b) provisions for adding members later if
    Eric brings on a cofounder/employee with equity, (c) IP
    ownership clauses, (d) dissolution/sale provisions, (e) clean
    procedure for assignment to an acquirer.

### 3.2 — Is all SourcePrep IP owned by the LLC, not Eric personally?

- **Q:** Has the IP from work Eric did before forming the LLC been
  formally assigned to the LLC?
- **Who:** DIY (template-based execution); future AI session can
  draft the document from the checklist below
- **Deliverable:** Executed IP Assignment Agreement (Eric → Magnetic
  Anomaly LLC) covering all pre-LLC SourcePrep work, stored in LLC
  corporate records
- **Status:** Action queued (2026-06-16) — facts confirmed; assignment
  not yet executed
- **Notes:** **Facts (Eric, 2026-06-16):**
  - SourcePrep work began **January 2026** in Eric's personal
    capacity on his personal GitHub
  - Magnetic Anomaly LLC formed **May 2026**
  - All code has since been transferred from Eric's personal GitHub
    to the `magneticanomaly` GitHub organization
  - This means **~4 months of pre-LLC work (Jan–Apr 2026) was created
    by Eric in his individual capacity**

  **Important distinction.** Transferring a GitHub repository moves
  hosting; it does **not** transfer copyright. The IP from
  January–April 2026 legally belongs to Eric personally until a
  formal written assignment is executed. The public GitHub history
  showing Eric as original author is fine — it's *evidence of
  authorship*, not a problem. The assignment moves *ownership*; the
  authorship history is the chain that supports it.

  This is the most common solo-founder IP gap, and it's trivial to
  fix at zero-users stage. Acquirer diligence will flag it
  immediately if unfixed; once fixed, it's a checkmark.

  **Required action — execute an IP Assignment Agreement.** Required
  elements (checklist for the future AI session that drafts this):

  1. **Effective date.** Backdate to LLC formation date (May 2026
     — Eric to confirm exact date) for cleanest diligence chain.
     Note in the agreement that it memorializes the intent of the
     parties as of LLC formation.
  2. **Assignor:** Eric Bintner (individual capacity)
  3. **Assignee:** Magnetic Anomaly LLC
  4. **Scope of assignment** — ALL right, title, and interest in:
     - All software code, documentation, designs, methods, and
       artifacts comprising "SourcePrep" / "prep" created by Eric
       between January 2026 and the LLC formation date
     - All copyrights (existing and future, in all jurisdictions)
     - All trade secrets, know-how, and confidential information
     - All patent rights, whether or not perfected (including the
       right to file applications based on the assigned work)
     - All moral rights to the extent assignable; waiver of moral
       rights to the extent not assignable under applicable law
     - All derivative works and improvements
  5. **Consideration.** $1 + ongoing membership in the LLC (must be
     non-zero for the assignment to be legally valid; nominal cash
     consideration is industry-standard for founder assignments)
  6. **Representations and warranties from Eric:**
     - The assigned work is original to Eric (or properly licensed)
     - The work does not infringe third-party rights to Eric's
       knowledge
     - Eric has full authority to make the assignment
     - No prior assignments, encumbrances, or licenses conflict
  7. **Further-assurances clause** — Eric agrees to execute any
     additional documents reasonably needed to perfect the
     assignment (this is standard; acquirers love seeing it)
  8. **Signatures:**
     - Eric Bintner (in individual capacity)
     - Eric Bintner (as sole member / authorized signatory of
       Magnetic Anomaly LLC)
     - Two signature blocks on the same document — Eric signs both
  9. **Notarization** — state-dependent. Most US states do not
     require notarization for IP assignments, but it's belt-and-
     suspenders cheap. Eric to verify his state's requirements.

  **Template sources (free):**
  - **Cooley GO** "Founder IP Assignment" / "Technology Assignment":
    https://www.cooleygo.com/documents/ip-assignment-and-license/
  - **Y Combinator startup documents library:**
    Confidential Information and Invention Assignment Agreement
    (CIIAA) — the gold standard, used by basically every YC company
  - **Stripe Atlas** founder paperwork templates (if Eric has any
    Atlas account access; otherwise the Cooley templates are the
    same content)

  **What to file where:**
  - **NOT filed with USPTO.** Copyrights vest automatically at
    creation; assignment is a private contract. Patent rights are
    similarly assignable by private contract. No government filing
    needed for the assignment itself.
  - **Stored in LLC corporate records** alongside the operating
    agreement, EIN letter, articles of organization.
  - Optional: record copyright assignment with the US Copyright
    Office (~$125) only if Eric ever wants to register specific
    works for enhanced statutory damages — not needed at zero-users
    stage.

  **For the future AI session that drafts this document:**
  - All 9 checklist elements above are template-fillable
  - Eric only needs to confirm: (a) exact LLC formation date,
    (b) his current state of residence (governing law clause),
    (c) any pre-existing licenses or assignments to be carved out
    (e.g., if any pre-LLC code was open-sourced under a license)
  - Produce a 2-3 page Word/PDF document Eric can print, sign both
    times, scan, and store

  **Attorney trigger:** acquisition diligence (LOI) — at that point
  buyer's counsel will review the assignment language and possibly
  request specific representations. Until then, a template-based
  execution is sufficient and is far better than no assignment at all.

  **Side note — Eric's personal GitHub history is fine.** Acquirer
  diligence may pull blame/log history showing Eric as the original
  author. That's a *good* signal: it confirms the chain of title
  (Eric authored → Eric assigned to LLC → LLC owns). The absence of
  unrelated authorship is what matters.

### 3.3 — LLC or convert to Delaware C-Corp?

- **Q:** Should we stay LLC or convert to a Delaware C-Corp before
  any potential acquisition conversation?
- **Who:** Decided (business decision)
- **Deliverable:** decision with revisit trigger
- **Status:** Decided (2026-06-15) — stay LLC; revisit at trigger
- **Notes:** **Stay LLC at Phase 144.** Rationale:
  - LLC pass-through taxation is simpler and cheaper at solo-bootstrap
    stage
  - C-Corp conversion is a 1-2 week attorney exercise that can
    happen reactively, not proactively
  - QSBS Section 1202 5-year hold clock only matters if acquisition
    timing > 5 years out, which we don't expect
  - Most acquirers can handle either entity type
- **Trigger to revisit:** (a) acquisition conversation reaches LOI,
  OR (b) any VC term sheet, OR (c) decision to raise institutional
  capital. At trigger: 1-week attorney engagement to convert.

### 3.4 — Founder vesting / employment agreement?

- **Q:** Should Eric have a formal vesting schedule and/or
  employment agreement with the LLC?
- **Who:** Decided
- **Deliverable:** decision + documents at trigger
- **Status:** Deferred (2026-06-15)
- **Notes:** **Skip at solo zero-users stage.** Founder vesting is
  acquisition-friendly signal but mostly cosmetic when there is one
  member with 100% interest. **Trigger to revisit:** (a) first
  cofounder or employee with equity, OR (b) first acquirer LOI.
  Standard at trigger: 4-year vest, 1-year cliff, applied
  retroactively from founding date.

### 3.5 — Bank account, tax setup, EIN

- **Q:** Are bank account, EIN, and federal/state tax registrations
  current and acquisition-friendly?
- **Who:** DIY (with accountant at year-end)
- **Deliverable:** confirm everything is current
- **Status:** Researching (2026-06-08)
- **Notes:** Business bank account is nearly complete, but not yet
  finished. Lemon Squeezy handles VAT/sales tax as Merchant of
  Record. Need: business bank account in LLC name (not Eric
  personal), EIN, state tax registration if applicable, annual LLC
  report filed on schedule.

---

## 4. Contributor License Agreement (CLA)

### 4.1 — Apache ICLA template adequate?

- **Q:** Is the standard Apache ICLA sufficient for our needs?
- **Who:** Decided (industry default)
- **Deliverable:** ICLA file at repo root with project-specific
  customization (project name, copyright holder)
- **Status:** Decided (2026-06-15)
- **Notes:** **Yes.** Apache ICLA v2.0 is the de facto standard for
  Apache 2.0 projects (used by all ASF projects + most permissively-
  licensed enterprise OSS). Project-specific customization is name
  + copyright holder only. Source:
  https://www.apache.org/licenses/contributor-agreements.html#clas
- **Action queued:** check in `ICLA.md` based on the Apache template
  with "Magnetic Anomaly LLC" as the copyright holder.

### 4.2 — Corporate CLA needed?

- **Q:** Do we need a separate Corporate CLA for contributors
  acting on behalf of their employer?
- **Who:** Decided (industry default)
- **Deliverable:** CCLA file at repo root
- **Status:** Decided (2026-06-15)
- **Notes:** **Yes — use Apache CCLA template.** Required when
  contributors are submitting work-product on behalf of an employer.
  Without it, the employer could later claim contribution
  reversion. Source:
  https://www.apache.org/licenses/contributor-agreements.html#cclas
- **Action queued:** check in `CCLA.md` based on the Apache template.

### 4.3 — How is CLA sign-off enforced?

- **Q:** What tooling enforces CLA sign-off on PRs?
- **Who:** Decided (DIY)
- **Deliverable:** GitHub Action configured + tested
- **Status:** Decided (2026-06-15)
- **Notes:** **Use CLA Assistant** (https://cla-assistant.io/). Free,
  GitHub-integrated, supports both ICLA and CCLA, used by major OSS
  projects (Salesforce, SAP, Mercedes-Benz, etc.). Configuration is
  a 30-min setup. Alternative: EasyCLA (Linux Foundation, heavier).
  CLA Assistant is the right fit at our scale.
- **Action queued for Phase 142 Part C:** configure CLA Assistant
  on the public mirror before merging the first external PR.

### 4.4 — DCO (Developer Certificate of Origin) vs CLA?

- **Q:** Should we use DCO sign-off instead of, or in addition to,
  CLA?
- **Who:** Decided
- **Deliverable:** decision recorded
- **Status:** Decided (2026-06-15) — CLA only, no DCO
- **Notes:** **CLA only.** Rationale:
  - CLA provides explicit license assignment (stronger IP chain
    for acquisition diligence)
  - DCO is a sign-off ("I have the right to contribute this") but
    doesn't assign rights
  - Acquirer due diligence prefers CLA-backed projects
  - Adding DCO on top of CLA is redundant friction
  - Linux uses DCO because GPL doesn't require explicit assignment;
    we're Apache 2.0 + acquirer-targeted, different needs

---

## 5. License hygiene

### 5.1 — Any GPL/AGPL/SSPL/proprietary dependencies?

- **Q:** Does any transitive dependency in `engine/Cargo.lock`,
  `pyproject.toml` deps, or `package-lock.json` carry a license
  incompatible with Apache 2.0 outbound?
- **Who:** DIY (tools)
- **Deliverable:** clean license report; replacement plan for any
  contamination
- **Status:** Answered (2026-06-10)
- **Notes:** Audited with `pip-licenses` and `license-checker`;
  Rust workspace deps inspected directly (`cargo-deny` not installed).
  - **NPM**: clean — MIT/ISC/Apache-2.0/BSD throughout.
  - **Rust (`engine/`)**: clean — standard MIT/Apache-2.0 crates
    (serde, rayon, regex, blake3, etc.).
  - **Python runtime**: GPL contamination found and **resolved
    2026-06-10** — `igraph` (GPL-2.0) + `leidenalg` (GPL-3.0)
    replaced with Louvain via `networkx` (BSD-3-Clause) in
    `src/prep/core/cluster.py`. Both libraries removed from the
    venv and `uv.lock`. Regression guard: `tests/test_no_gpl_deps.py`.
  - **Python dev-only**: `pyinstaller` + `pyinstaller-hooks-contrib`
    are GPLv2 but live in the `dev` extra only — build tools, never
    distributed. PyInstaller's bootloader exception permits bundling
    apps under any license. **Decision (2026-06-15):** no action
    needed — PyInstaller's documented bootloader exception is well-
    established and covers our use case. Document the analysis in
    `LICENSE-AUDIT.md` for future reference; no attorney review
    needed for this specific case.

### 5.2 — gstack attribution lineage?

- **Q:** Does any code or pattern in `src/prep/core/atlas/` or the
  `role=` parameter on `prep()` derive from gstack in a way that
  requires attribution?
- **Who:** DIY (Eric inspection)
- **Deliverable:** documented audit + NOTICE attribution if any
- **Status:** Answered (2026-06-08)
- **Notes:** Code audit complete. `grep` across the repository
  shows that the word "gstack" only appears in documentation files
  (like `STRATEGY.md`, `IMPLEMENTATION_PLAN.md`, etc.), not in any
  source code files. While `src/prep/core/atlas/role_resolver.py`
  deals with roles (e.g., "design engineer"), there is no literal
  copy-pasted code from `gstack`. Because SourcePrep was built to
  be *complementary* to gstack (as an MCP server for it), any
  conceptual overlap does not constitute a copyright derivation
  requiring an MIT attribution notice. No action needed in `NOTICE`.

### 5.3 — LLM-generated code license risk?

- **Q:** Could any LLM-generated code in our codebase accidentally
  match copyrighted code (e.g., Stack Overflow CC-BY-SA, GPL kernel
  code) and create a hidden license-violation risk?
- **Who:** DIY (tools)
- **Deliverable:** `scancode-toolkit` run on entire repo; manual
  inspection of any flags
- **Status:** Decided (2026-06-15) — action queued
- **Notes:** **Action:** run `scancode-toolkit` (free, OSS:
  https://github.com/nexB/scancode-toolkit) against the repo. Flag
  any files with embedded copyright/license headers that don't
  match our expected set (Apache 2.0, MIT, BSD, project-original).
  Manual inspection of any flags. Document in `LICENSE-AUDIT.md`.
- **Risk profile at zero users:** low — even if a flag is found,
  remediation (rewrite or attribute) is straightforward at this
  stage. The cost of finding contamination *after* public launch
  is much higher.

### 5.4 — Apache 2.0 NOTICE file completeness?

- **Q:** What third-party attributions need to be in NOTICE?
- **Who:** DIY (compile from license audit)
- **Deliverable:** complete NOTICE file
- **Status:** Decided (2026-06-15) — template + audit-derived
- **Notes:** **NOTICE structure to use:**
  ```
  SourcePrep
  Copyright (c) 2024-2026 Magnetic Anomaly LLC

  This product includes software developed by:
    - The Apache Software Foundation (http://www.apache.org/)
    - <other Apache 2.0 deps that ship NOTICE files>

  Third-party components used under their respective licenses:
    - <list compiled from 5.1 audit>
  ```
- **Action queued for Phase 142 Part C:** scan all Apache-2.0
  dependencies for upstream NOTICE files; copy their attribution
  text into our root NOTICE. Most modern crates/packages don't ship
  a NOTICE; only attribute those that do.

---

## 6. Customer-facing terms

### 6.1 — Terms of Service for sourceprep.io?

- **Q:** Do we need a ToS, and what must it contain?
- **Who:** DIY (template-based draft); attorney review at trigger
- **Deliverable:** drafted ToS, published before first Pro
  transaction
- **Status:** Decided (2026-06-15) — template-based DIY draft
- **Notes:** **Use a free template + customize.** Recommended
  starting points:
  - **Cooley GO** (https://www.cooleygo.com/documents/) — high-
    quality startup ToS templates, free
  - **GitHub legal templates** for OSS-adjacent commercial sites
  - **GetTerms.io** ($10-30 one-time for a polished generated doc)
- **Required sections (industry standard):**
  - Acceptance of terms
  - Account terms (eventually — Phase 2)
  - License grants for the Pro tier
  - Payment terms (reference Lemon Squeezy ToS)
  - Refund policy reference (6.4)
  - Acceptable use (defer detailed AUP to 6.6 / Phase 2)
  - Disclaimer of warranties (provide "as-is")
  - Limitation of liability (cap at amount paid in last 12 months)
  - Indemnification
  - Governing law (Eric's home state)
  - Dispute resolution (binding arbitration)
  - Termination
  - Changes to terms (notice mechanism)
- **Attorney review trigger:** first paying customer OR before first
  Enterprise pipeline conversation, whichever comes first. Cost at
  trigger: ~$500-1,500 for a focused review pass.

### 6.2 — Privacy Policy?

- **Q:** What data do we collect at Phase 1 (OSS + Pro) and Phase 2
  (Teams hosted backend), and how must it be disclosed?
- **Who:** DIY (template-based draft); attorney review at Phase 2
  trigger
- **Deliverable:** drafted Privacy Policy
- **Status:** Decided (2026-06-15) — Phase 1 minimal version DIY
- **Notes:** **Phase 1 (minimal Privacy Policy):**
  - sourceprep.io collects: visitor analytics (use a privacy-
    respecting analytics provider — e.g., Plausible — to minimize
    GDPR/CCPA exposure)
  - Pro license activation: email + license key data, stored locally
    + in Lemon Squeezy
  - No telemetry from the OSS daemon (confirm and document)
  - Third-party processors: Lemon Squeezy (payments), analytics
    provider (visits)
  - Data subject rights: contact `privacy@sourceprep.io` to access /
    delete
  - Retention: while account is active + 90 days
- **Phase 2 (expanded Privacy Policy):** must add hosted backend
  data flows (embeddings + graph metadata, never raw source — see
  OPEN_CORE_SPLIT.md), hosting provider as processor, GDPR/CCPA
  data subject rights mechanics.
- **Attorney review trigger:** before Phase 2 hosted backend ships
  publicly. Cost at trigger: ~$500-1,500.

### 6.3 — EULA for Pro Tauri app?

- **Q:** Do we need a click-through EULA inside the Pro Tauri
  installer?
- **Who:** DIY (template-based draft)
- **Deliverable:** EULA text + integration in Tauri installer
- **Status:** Decided (2026-06-15) — template-based DIY draft
- **Notes:** **Yes, click-through EULA required.** The Apache 2.0
  source license doesn't cover the Pro Tauri binary as a packaged
  commercial product — the EULA wraps it. **Key clauses (standard
  pattern):**
  - License grant: non-exclusive, non-transferable, tied to
    license key + per-seat scope
  - Restrictions: no redistribution of the signed binary, no
    reverse engineering of the auto-update mechanism, no removal
    of license check
  - Underlying OSS components: explicitly note that the engine
    source is Apache 2.0 and unaffected by this EULA
  - Updates: silent auto-update consented to
  - Termination: license key revocation on non-payment, refund, etc.
  - Standard disclaimer, liability cap, governing law
- **Source templates:** TLDRLegal sample EULAs, GitHub legal repo
- **Attorney review trigger:** before first Pro purchase processes
  end-to-end. Same engagement as 6.1.

### 6.4 — Refund policy?

- **Q:** What's our refund policy for Pro Monthly, Pro Perpetual,
  Teams, Enterprise?
- **Who:** Decided (industry standard)
- **Deliverable:** documented policy + Lemon Squeezy alignment
- **Status:** Decided (2026-06-15)
- **Notes:** **Policy by tier (industry-standard refund windows):**
  - **Pro Monthly ($7/mo):** pro-rated refund within first 14 days;
    no refund after first 14 days of any billing cycle
  - **Pro Perpetual ($70):** full refund within 30 days; no refund
    after
  - **Teams Monthly ($15/seat/mo):** pro-rated refund within first
    14 days of initial subscription; no refund after
  - **Teams Annual ($144/seat/yr):** pro-rated refund within 30 days
    of initial purchase; no refund after
  - **Enterprise Annual ($50/seat/mo annual):** pro-rated refund
    within 30 days of initial contract; no refund after; subject to
    individual contract terms
  - **Enterprise Setup ($5k one-time):** non-refundable once work
    begins
- **Lemon Squeezy alignment:** LS handles refund mechanics; confirm
  these windows are configurable per product. LS may have stricter
  default windows we need to override or accept.

### 6.5 — Subscription terms (auto-renewal)?

- **Q:** How are auto-renewals disclosed and cancellable?
- **Who:** Decided (Lemon Squeezy default + disclosure)
- **Deliverable:** subscription terms section in ToS
- **Status:** Decided (2026-06-15)
- **Notes:** **Use Lemon Squeezy's standard subscription mechanics:**
  - Pro Monthly / Teams Monthly: auto-renew monthly
  - Pro Perpetual: no auto-renew (one-time)
  - Teams Annual / Enterprise Annual: auto-renew annually unless
    canceled ≥30 days before renewal
  - Notice before renewal: LS sends 7-day reminder by default
  - Cancellation: self-serve via LS customer portal at any time
  - Effect on cancel: license remains active until end of paid
    period; auto-renew stops
  - On expiration: Pro features deactivate; engine reverts to OSS
    behavior; user data preserved
- **Disclosure:** include this in ToS subscription section.

### 6.6 — Acceptable Use Policy?

- **Q:** What uses are prohibited (especially for Phase 2 hosted
  backend)?
- **Who:** DIY at Phase 2 trigger (template-based)
- **Deliverable:** AUP document
- **Status:** Deferred (2026-06-15)
- **Notes:** **Defer to Phase 2.** For Phase 1 OSS, the Apache 2.0
  license is the operative document (covers acceptable use very
  broadly). For Phase 1 Pro, the EULA covers Pro-specific
  restrictions. AUP becomes relevant only when we host a multi-
  tenant backend (Phase 2). At Phase 2 trigger: draft AUP with
  standard prohibitions (no malware, no abuse, no third-party
  rights infringement, no scraping, no anti-competitive use).

### 6.7 — Master Services Agreement template for Enterprise?

- **Q:** Do we need an MSA template ready for Enterprise customers
  whose procurement requires one?
- **Who:** DIY at trigger (template + attorney review)
- **Deliverable:** MSA template
- **Status:** Deferred (2026-06-15)
- **Notes:** **Defer until first Enterprise pipeline opportunity.**
  Most large customers have their own MSA they'll insist on; we
  react to theirs. Having our own template is acquisition-friendly
  signal but not blocking. **Trigger to draft:** first Enterprise
  prospect that asks "send us your MSA." Source: Cooley GO SaaS MSA
  template + attorney review pass (~$1,500).

### 6.8 — Data Processing Agreement (DPA) for EU Enterprise?

- **Q:** Do we need a GDPR-compliant DPA template before any EU
  Enterprise customer signs?
- **Who:** DIY at trigger (template-based)
- **Deliverable:** DPA template
- **Status:** Deferred (2026-06-15)
- **Notes:** **Defer to Phase 2 + first EU customer.** Use EU
  Commission's Standard Contractual Clauses (Decision 2021/914) as
  the base; widely accepted, free, regularly updated.

---

## 7. Security disclosure infrastructure

### 7.1 — Vulnerability disclosure process

- **Q:** How do researchers report vulnerabilities? What's our SLA?
- **Who:** DIY
- **Deliverable:** `SECURITY.md` with reporting instructions
- **Status:** Answered (2026-06-10)
- **Notes:** `SECURITY.md` drafted at repo root: GitHub private
  vulnerability reporting primary; `security@sourceprep.io`
  secondary (alias needs to be created); 5-business-day
  acknowledgment; 90-day coordinated disclosure; supported-versions
  table; scope note that SourcePrep reads local source code.
- **Remaining action:** create `security@sourceprep.io` email alias
  before public mirror ships.

### 7.2 — DMCA agent registration

- **Q:** Do we need a registered DMCA agent for safe harbor?
- **Who:** DIY (USPTO filing)
- **Deliverable:** DMCA agent registration confirmation
- **Status:** Decided (2026-06-15) — action queued for launch week
- **Notes:** **Yes, register.** $6 USPTO fee (renewable every 3
  years at $6), 30 min to file at
  https://www.copyright.gov/dmca-directory/. Required for DMCA §512
  safe harbor on any user-generated content (GitHub Discussions on
  the public mirror, any future hosted backend with user-submitted
  content). Cheap insurance.
- **Action queued for Phase 142 Part C launch week.**

### 7.3 — Bug bounty program?

- **Q:** Do we offer monetary rewards for vulnerability disclosure?
- **Who:** Business decision
- **Deliverable:** decision recorded
- **Status:** Answered (2026-06-08)
- **Notes:** No bug bounty program for now. Hall-of-fame
  acknowledgment in `SECURITY.md` only. Revisit when revenue
  justifies.

---

## 8. Tax + compliance

### 8.1 — Sales tax nexus

- **Q:** Do we have any sales tax nexus obligations not covered by
  Lemon Squeezy's Merchant-of-Record status?
- **Who:** DIY (Lemon Squeezy MoR covers most); accountant at
  year-end
- **Deliverable:** confirmation
- **Status:** Deferred (2026-06-15)
- **Notes:** **Lemon Squeezy handles VAT/sales tax on all
  transactions they process** — this is the entire value of using
  MoR over Stripe. Off-platform invoicing (Enterprise Setup
  engagements, Enterprise Plus contracts) is state-dependent and
  requires our own sales tax handling. **Trigger to address:** first
  off-platform invoice. Action at trigger: 30-min call with an
  accountant ($100-200) to confirm whether Eric's home state
  requires registration on B2B services revenue.

### 8.2 — 1099 reporting for off-platform engagements

- **Q:** Do we need to issue 1099s or W-9s for anyone we pay?
- **Who:** Accountant (year-end)
- **Deliverable:** standard process
- **Status:** Deferred (2026-06-15)
- **Notes:** **Standard year-end accountant workstream.** Not
  blocking for launch. Apply standard 1099-NEC rules for any
  contractor we pay >$600/year.

---

## 9. Insurance

### 9.1 — E&O / Cyber liability

- **Q:** Do we need professional liability or cyber insurance, and
  at what Phase?
- **Who:** DIY (quotes) at trigger
- **Deliverable:** quotes + decision at trigger
- **Status:** Deferred (2026-06-15)
- **Notes:** **Skip at Phase 1.** No hosted backend means no
  customer data liability. No Enterprise customer yet means no MSA
  requiring proof. **Triggers to revisit:**
  - Before Phase 2 hosted backend ships (hosted = customer data =
    real cyber exposure), OR
  - First Enterprise prospect MSA requiring proof of insurance,
    whichever comes first
- **Expected cost at trigger:** $1,500-4,000/year for E&O + cyber
  combined for a single-employee LLC selling SaaS.

### 9.2 — General liability

- **Q:** Do we need general business liability insurance?
- **Who:** DIY (quotes) at trigger
- **Deliverable:** quote
- **Status:** Deferred (2026-06-15)
- **Notes:** Often bundled with E&O/cyber. Quote all three together
  at the E&O trigger above.

---

## 10. Anti-rug-pull commitment

### 10.1 — CHARTER.md content

- **Q:** What does our "OSS surface stays Apache 2.0 in perpetuity"
  commitment say?
- **Who:** DIY (draft)
- **Deliverable:** `CHARTER.md`
- **Status:** Decided (2026-06-15) — content spec'd; draft queued
- **Notes:** **Draft `CHARTER.md` with these clauses:**
  1. **OSS commitment.** The components named as "OSS" in
     `OPEN_CORE_SPLIT.md` (Rust engine, Python core, MCP server, CLI,
     daemon, local dashboard, AGENTS.md generator, `packages/ui`,
     VS Code extension, all in-engine prompts) will remain available
     under Apache License 2.0 in perpetuity.
  2. **No retroactive re-licensing.** Code that has been published
     under Apache 2.0 remains Apache 2.0 forever; any future license
     change would apply only to *new code added after the change*.
  3. **Open-core boundary disclosure.** The components named as Pro,
     Teams, or Enterprise in `OPEN_CORE_SPLIT.md` are explicitly
     proprietary. This is not a bait-and-switch; it is the open-core
     boundary from day one.
  4. **Acquirer continuity.** If Magnetic Anomaly LLC is acquired or
     transferred, the Apache 2.0 commitment to existing OSS code
     transfers with the asset.
  5. **Charter amendment procedure.** Material amendments require
     30-day public notice and apply only forward.
- **Lessons from Elastic, HashiCorp, Redis:** community trusts
  projects that commit explicitly. Don't be vague about future
  licensing.

---

## 11. Existing-customer audit

### 11.1 — Are there current Lemon Squeezy customers?

- **Q:** Does Magnetic Anomaly LLC have any active Lemon Squeezy
  subscriptions or recent one-time purchases?
- **Who:** DIY (Lemon Squeezy dashboard)
- **Deliverable:** customer count + list
- **Status:** Answered (2026-06-08)
- **Notes:** Zero existing customers. Nothing officially launched
  yet.

### 11.2 — Customer notice content (if needed)

- **Q:** If current customers exist, what do we tell them about the
  OSS pivot?
- **Who:** N/A
- **Deliverable:** customer notice email + grandfathering policy
- **Status:** Answered (2026-06-08)
- **Notes:** Skipped. Zero existing customers per 11.1.

---

## Decision audit trail

- **2026-06-01** — Phase 144 scaffolded. All questions opened.
- **2026-06-08** — 1.1 common-law search: zero "SourcePrep" matches
  on GitHub/PyPI/NPM/Crates.io. `sourceprep.io` owned + live.
- **2026-06-08** — 5.2 gstack audit: no code derivation found; no
  NOTICE attribution needed.
- **2026-06-08** — 7.3 decided: no bug bounty at Phase 1.
- **2026-06-08** — 11.1/11.2 closed: zero existing customers; notice
  + grandfathering skipped.
- **2026-06-10** — 5.1 resolved: GPL deps (`igraph`, `leidenalg`)
  replaced with `networkx` Louvain; regression guard added.
  Remaining GPL (`pyinstaller`) is dev-only, non-shipping.
- **2026-06-10** — 7.1 SECURITY.md drafted at repo root.
- **2026-06-15** — Lenient-on-attorney reframe pass: zero-users
  context applied. Decisions made on 1.2, 1.3, 1.4, 1.5, 1.6, 2.1,
  2.2, 2.3, 2.4, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 5.3, 5.4, 6.1, 6.2,
  6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 7.2, 8.1, 8.2, 9.1, 9.2, 10.1.
  Remaining open: USPTO TESS search (1.1 finalization), 3.1, 3.2,
  3.5, scancode run (5.3 execution). See "Open actions for Eric"
  and "Deferred for future research" sections below.
- **2026-06-16** — 3.2 facts received from Eric: SourcePrep work
  began Jan 2026 (personal capacity, personal GitHub); Magnetic
  Anomaly LLC formed May 2026; code transferred to `magneticanomaly`
  GitHub org. Conclusion: ~4 months of pre-LLC work exists in Eric's
  individual capacity and requires a formal IP Assignment Agreement
  to transfer ownership to the LLC. 3.2 status: Action queued.
  Complete 9-element checklist + template sources + future-AI-
  session drafting guidance added to 3.2 notes. No attorney needed
  until acquisition diligence.

---

## Open actions for Eric (DIY, can be done now)

Things Eric can do directly without an attorney, before Phase 142
Part B can ship:

1. **USPTO TESS search** (30 min, free) — finalize 1.1 with the
   federal search results. https://tmsearch.uspto.gov/
2. **Execute IP Assignment Agreement (3.2)** — facts confirmed
   2026-06-16: ~4 months of pre-LLC work (Jan–Apr 2026) exist in
   Eric's individual capacity and require formal assignment to the
   LLC. Use the 9-element checklist + template sources documented in
   3.2. A future AI session can draft the document from the
   checklist; Eric needs to provide (a) exact LLC formation date,
   (b) current state of residence, (c) any pre-existing OSS licenses
   on pre-LLC code. Eric signs both sides (individual + LLC
   authorized signatory) and stores in LLC corporate records.
3. **Finish business bank account (3.5)** — currently in flight.
4. **Run `scancode-toolkit` (5.3)** — free OSS tool. Run against
   repo, inspect any flags, document in `LICENSE-AUDIT.md`.
5. **Compile NOTICE file (5.4)** — scan Apache-2.0 deps for
   upstream NOTICE files, copy attribution into root NOTICE.
6. **Draft `CHARTER.md` (10.1)** — using the clauses spec'd in 10.1.
7. **Draft `ICLA.md` + `CCLA.md`** (4.1, 4.2) — Apache templates
   with project-specific customization.
8. **Register DMCA agent (7.2)** — $6, 30 min, file at copyright.gov.
9. **Create `security@sourceprep.io` email alias** (7.1 remaining).
10. **Draft Phase 1 ToS, Privacy Policy, EULA** (6.1, 6.2, 6.3) —
    using template starting points; attorney review at trigger.
11. **Decide refund-policy text** for Lemon Squeezy product
    descriptions (6.4) — already spec'd above; just apply.

**Total Eric time:** ~1 week of focused work, mostly drafting from
templates + tool runs. Zero attorney cost at this stage.

---

## Deferred for future research (the harder questions)

Saved for a deeper research pass with a more capable future model
(Fabel AI / future Claude) or attorney engagement at a triggered
event:

1. **3.1 — Operating agreement adequacy review.** Needs document
   inspection. Trigger: first acquirer LOI or VC term sheet. Can be
   addressed with future-model assistance if Eric uploads the OA.
2. **3.2 — IP assignment drafting assistance.** Facts in
   (2026-06-16): pre-LLC work exists; assignment needs to be
   executed. The 9-element checklist + template sources in 3.2 are
   sufficient for a future AI session to produce the document.
   Future AI input needed: Eric's exact LLC formation date, current
   state of residence (governing law), any carve-outs for pre-LLC
   OSS licensing. Output: 2-3 page Word/PDF for Eric to sign.
3. **Attorney review of customer-facing terms (6.1, 6.2, 6.3).**
   Templates work for launch; attorney review at trigger (first
   paying customer or Enterprise pipeline).
4. **Patent novelty formal opinion (2.1).** Current decision is
   "skip patents." A patent attorney *might* disagree on
   AIMD-for-LLMs specifically. Revisit only if acquirer values
   patent-protected IP.
5. **International trademark extension (1.4).** Decision is US-only;
   revisit within 6 months of US filing if EU/UK pipeline emerges.
6. **3.3 — C-Corp conversion timing.** Decision is "stay LLC,
   revisit at trigger." Future-model assistance can model the QSBS
   tax math if/when the conversation gets real.
7. **6.6 — AUP for Phase 2 hosted backend.** Defer to Phase 2.
8. **6.7 — MSA template.** Defer until first Enterprise pipeline.
9. **6.8 — DPA template.** Defer to Phase 2 + EU customer.
10. **9.1, 9.2 — Insurance.** Defer to Phase 2 or first MSA-
    requiring prospect.

**No attorney engagement is required for Phase 142 Part B
(license + repo restructure) to ship.** The first attorney touch
becomes necessary only at: (a) USPTO trademark filing (consider
DIY via TEAS Plus to defer cost), or (b) first paying customer
review of ToS/Privacy/EULA, or (c) first acquirer LOI / VC term
sheet.

---

## Summary table — DIY vs Attorney vs Future-research

Re-tally after the 2026-06-15 lenient-attorney reframe:

| Section | DIY now | Future-research / Trigger |
|---|---|---|
| 1. Trademark | 1.1 (TESS search), 1.2, 1.3, 1.5, 1.6 | 1.4 (revisit ≤6mo of US filing) |
| 2. Patents | 2.1, 2.2, 2.3, 2.4 (defensive pub via blog posts) | 2.1 formal novelty opinion if acquirer values it |
| 3. Corporate | 3.2 (template execution), 3.3, 3.4, 3.5 | 3.1 (OA review at LOI/term-sheet) |
| 4. CLA | 4.1, 4.2, 4.3, 4.4 (all Apache templates + CLA Assistant) | — |
| 5. License hygiene | 5.1 ✅, 5.2 ✅, 5.3 (scancode run), 5.4 (NOTICE compile) | — |
| 6. Customer terms | 6.1, 6.2, 6.3 (template drafts), 6.4, 6.5 | 6.1-6.3 attorney review at first paying customer; 6.6 (Phase 2); 6.7 (first Enterprise); 6.8 (Phase 2 + EU) |
| 7. Security | 7.1 ✅, 7.2 (DMCA register), 7.3 ✅ | — |
| 8. Tax | 8.1, 8.2 (accountant year-end) | — |
| 9. Insurance | — | 9.1, 9.2 (at Phase 2 or first MSA) |
| 10. Anti-rug-pull | 10.1 (CHARTER draft) | — |
| 11. Existing customers | 11.1 ✅, 11.2 ✅ | — |

**Estimated attorney time required to ship Phase 142 Part B:** zero.
**Estimated attorney time required to ship Phase 142 Part C (Show HN):**
zero (USPTO TEAS Plus filing can be DIY; templates cover customer
terms with attorney review queued at first paying customer trigger).
**Estimated Eric DIY time remaining:** ~1 week of focused drafting +
tool runs.
