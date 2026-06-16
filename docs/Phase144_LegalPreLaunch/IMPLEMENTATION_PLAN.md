# Phase 144 — Implementation Plan

> Ordered work to land all legal pre-launch decisions before Phase 142
> Part C ships.

> **Reframe banner (2026-06-15).** The original plan below assumes
> an attorney-first sequencing (Parts B–C set up an attorney
> engagement). After the 2026-06-15 zero-users reframe (see
> `RESEARCH.md`), most decisions were closed with industry-standard
> defaults and DIY tools. **Parts B and C are no longer required to
> ship Phase 142 Part B or Part C.** Attorney review is queued at
> trigger events (first paying customer, first acquirer LOI, first
> EU prospect) rather than upfront. The remaining ordered work is
> consolidated into the **"Open actions for Eric"** section of
> `RESEARCH.md` — read that for the current ~1-week DIY checklist.
> The Parts A–K structure below is preserved as a fallback in case
> Eric chooses to engage an attorney earlier than triggers require.

## Part A — DIY pre-attorney research

**Goal:** answer everything that *doesn't* need an attorney, so the
billable attorney consult is laser-focused on the genuinely-legal
questions.

**Tasks:**

1. **USPTO TESS search** for "SourcePrep" — 30 min
   - Search exact mark + phonetic variations
   - Check Classes 9 and 42 specifically
   - Document any same-or-similar marks found
2. **Common-law trademark search** — 1 hour
   - Google "SourcePrep" (with quotes)
   - GitHub search for `SourcePrep` org/repo names
   - PyPI, npm, crates.io, Docker Hub search
   - LinkedIn company search
3. **Domain audit** — confirm Magnetic Anomaly LLC owns
   `sourceprep.io`, plus check `.com`, `.dev`, `.ai`, `.app`
   variants for defensive acquisition
4. **Dependency license audit (preliminary)**:
   - `cargo deny check licenses` on `engine/`
   - `pip-licenses --format=json` on Python deps
   - `license-checker --json` on npm workspaces
   - Tag any GPL/AGPL/SSPL/proprietary findings for attorney attention
5. **Magnetic Anomaly LLC document gather** — pull operating
   agreement, articles of organization, EIN letter; have ready
   for attorney
6. **List existing Lemon Squeezy customers** (per SCRUTINY §11) —
   if any exist, draft the customer-notice content for attorney review

**Deliverables:** `RESEARCH.md` updated with findings per topic.

**Acceptance:** every DIY-answerable question in `RESEARCH.md` has
a recorded answer.

## Part B — Consolidated attorney brief

**Goal:** a single document the attorney can read in 20 minutes that
contains every question we need legal input on.

**Brief contents:**

1. One-paragraph project summary
2. Apache 2.0 publication timeline (when public launch is targeted)
3. Trademark questions (filing strategy, class selection,
   international scope)
4. Patent questions (candidate methods + asking for novelty assessment)
5. Corporate structure questions (LLC operating agreement adequacy,
   IP assignment from Eric to LLC, future C-Corp conversion timing)
6. CLA questions (Apache ICLA template adequacy, corporate CLA
   needed?)
7. License hygiene findings (any dependency license red flags from
   Part A)
8. Public policy template review needs (ToS, Privacy, EULA, AUP)
9. Acquisition-readiness checklist questions

**Deliverable:** `ATTORNEY_BRIEF.md` (private). One document, 3–5
pages.

**Acceptance:** the brief is self-contained — an attorney reading
it cold can give actionable advice without needing to learn the
project from scratch.

## Part C — Attorney engagement

**Goal:** one consolidated engagement covering all questions.

**Engagement structure:**

1. **1-hour initial consult** with a tech/IP attorney — could be
   one attorney covering trademark + IP + corporate, or two
   (trademark specialist + corporate generalist). Prefer one for
   simplicity.
2. **Written follow-up summary** from the attorney, in email, that
   we file as the record of legal advice received
3. **Subsequent engagement** for execution: trademark filing,
   operating agreement amendments, policy template review

**Selection criteria for the attorney:**

- Experience with OSS/Apache 2.0 projects
- Experience with software trademark filings
- Experience with LLC → C-Corp conversions and/or acquisition prep
- Located in a state with predictable tech law (DE, CA, NY, WA)
- Hourly rate in $300–600/hr range (avoid biglaw rates)

**Sources to find one:**

- Recommendations from other indie OSS founders
- Cooley GO, Orrick Total Access, or similar startup-friendly firms
  with free initial consults
- State bar referral services

**Deliverable:** attorney engaged; consult completed; written
follow-up filed.

**Acceptance:** all attorney-required questions in `RESEARCH.md`
have written legal opinions.

## Part D — Trademark application

**Goal:** USPTO application filed for "SourcePrep" in Classes 9 and 42.

**Steps:**

1. Confirm clear search results from Part A
2. Decide TEAS Standard ($350/class) vs TEAS Plus ($250/class with
   stricter requirements) — attorney recommendation in Part C
3. File via USPTO TEAS portal (attorney files on our behalf)
4. Begin using ™ symbol immediately after filing
5. Calendar the response window for Office Actions (~3 months typical)
6. Calendar registration target (~8–12 months typical) — ® usable then

**International scope decision:**

- US filing covers US only
- Madrid Protocol filing extends to EU/UK/JP/etc. — additional
  ~$5,000+ in fees if pursued
- **Recommendation:** US-only at Phase 144. Defer international to
  a later phase once revenue justifies. Document the decision in
  `RESEARCH.md` so it's revisitable.

**Deliverable:** filed USPTO application; serial number recorded.

**Acceptance:** ™ usable on all public-facing properties.

## Part E — Patent decision

**Goal:** explicit decision per candidate method: skip / provisional
filing / defensive publication.

**Candidate methods to evaluate** (attorney-assisted in Part C):

1. Anchor-overlap clustering for concept promotion (`project_concept_promotion_strategy.md`)
2. AIMD concurrency control for cloud LLM rate discovery
3. Multi-pass concept synthesis with calibration tiers
4. Trace graph + curated traceability + concept overlay system
5. Embedder restart-to-reclaim with shared singleton pattern (probably not novel)
6. 15-stage pipeline state machine architecture (probably not novel)

**Decision framework per method:**

| If attorney says... | Action |
|---|---|
| "Clearly novel + commercially meaningful" | File provisional patent ($1,500–3,000); 12-month window to non-provisional |
| "Possibly novel but not commercially critical" | Defensive publication via blog post (establishes prior art at $0) |
| "Already well-known or pre-existing prior art" | No action |

**Default action:** defensive publication for everything except items
the attorney specifically flags as worth provisional filing.

**Deliverable:** `RESEARCH.md` has a recorded decision per method.

**Acceptance:** no method left undecided; defensive-publication
posts queued for Phase 142 Part G (the blog posts that ship at launch).

## Part F — Corporate structure review

**Goal:** Magnetic Anomaly LLC is structured to receive an
acquisition cleanly.

**Tasks:**

1. **Operating agreement review** — attorney reads the current OA;
   recommends amendments if any
2. **IP assignment from Eric to LLC** — confirm all SourcePrep IP is
   owned by the LLC, not Eric personally. If not, execute assignment
   agreement.
3. **Entity-type decision** — stay LLC or convert to Delaware C-Corp
   - LLC pros: pass-through taxation, simpler ongoing requirements
   - C-Corp pros: standard for VC/acquirer due diligence, QSBS tax
     advantage (Section 1202) on acquisition proceeds if held 5+ years
   - **Recommendation:** stay LLC for now; convert to C-Corp *only
     if* acquisition conversation gets serious. Most acquirers can
     handle either. Document the decision in `RESEARCH.md`.
4. **Founder vesting agreement** — even as solo founder, having a
   formal vesting schedule on Eric's equity is acquisition-friendly.
   Attorney to advise.

**Deliverable:** operating agreement amendments filed if needed;
IP assignment executed if needed; entity-type decision recorded.

**Acceptance:** attorney confirms in writing that the LLC is
acquisition-ready as-is.

## Part G — Public policies (CLA, CHARTER, CONTRIBUTING, etc.)

**Goal:** every public-facing policy doc drafted, attorney-reviewed,
and ready to ship with the public mirror.

**Documents to produce:**

| Doc | Source | Customization needed |
|---|---|---|
| `LICENSE` | Apache 2.0 standard text | None — verbatim |
| `NOTICE` | Apache 2.0 NOTICE convention | Add any third-party attribution from Part H |
| `CONTRIBUTING.md` | Project-specific | Reference CLA process, code of conduct, signoff |
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1 template | Project name + contact only |
| `SECURITY.md` | Standard template | `security@sourceprep.io`, response SLA (5 business days), GPG key fingerprint |
| `CHARTER.md` | Anti-rug-pull commitment (SCRUTINY §10) | Spell out OSS-stays-Apache-forever commitment |
| `CLA.md` + GitHub Action | Apache ICLA template + CLA Assistant | Configure CLA Assistant; require sign-off |

**Deliverable:** all docs drafted, in `Phase144_LegalPreLaunch/` as
working copies. Final versions ship with Phase 142 Part C in the
public mirror.

**Acceptance:** attorney reviews and signs off on policy text;
CLA Assistant integration tested with one mock PR.

## Part H — License hygiene + dependency audit

**Goal:** confirm Apache 2.0 grant is legally valid (no GPL/AGPL/
SSPL contamination in any dependency); complete NOTICE file with
all third-party attribution.

**Tasks:**

1. **`cargo deny check licenses`** as a CI step — fail on GPL,
   AGPL, SSPL, custom proprietary
2. **`pip-licenses --fail-on=GPL`** for Python deps
3. **`license-checker --failOn 'GPL'`** for npm deps
4. **`licensee detect` or `scancode-toolkit`** on the entire
   source tree (catches copy-pasted code with embedded license headers)
5. **Manual inspection** of any flagged files
6. **gstack attribution audit** (per `STRATEGY.md`) — inspect
   `src/prep/core/atlas/` and any role-related code for gstack
   lineage; add MIT-compatible attribution in NOTICE if any genuine
   derivation found
7. **`LICENSE-AUDIT.md`** (private) — record audit date, tools used,
   findings, mitigations

**Deliverable:** clean license report; NOTICE file complete;
`LICENSE-AUDIT.md` recorded.

**Acceptance:** CI license-check step is green; NOTICE file is
complete; attorney confirms Apache 2.0 grant is legally sound.

## Part I — Customer-facing terms

**Goal:** every commercial transaction is backed by attorney-reviewed
terms.

**Documents to produce:**

| Doc | Applies to |
|---|---|
| Terms of Service (sourceprep.io) | All sourceprep.io visitors |
| Privacy Policy | All sourceprep.io visitors; expanded for Phase 2 hosted backend |
| Acceptable Use Policy | All sourceprep.io users, hosted backend users (Phase 2) |
| Subscription Terms | All Pro/Teams subscribers |
| Refund Policy | All paying customers (Lemon Squeezy's policy + ours) |
| EULA | Pro Tauri app users (shipped in installer) |
| Master Services Agreement (MSA) template | Enterprise customers (used only when their procurement requires) |
| Data Processing Agreement (DPA) | Enterprise EU customers (Phase 2 hosted backend) |

**Sources:**

- Template starting points: Termly, GetTerms, or Cooley GO templates
- Attorney review and project-specific customization

**Privacy Policy critical clauses:**

- What data is collected (none for OSS; license info for Pro; embeddings + graph metadata for Teams hosted backend)
- Where data is stored (US-only at Phase 2 launch)
- Third-party processors (Lemon Squeezy, hosting provider TBD,
  embedder model provider if applicable)
- Data subject rights (GDPR Article 15–22, CCPA equivalent)
- Retention periods
- Contact for data requests

**Deliverable:** all terms drafted, reviewed, ready to publish on
sourceprep.io before Phase 1 launch.

**Acceptance:** attorney sign-off; Lemon Squeezy product description
links to the new terms; all paid checkout flows show the terms
before payment.

## Part J — Security disclosure infrastructure

**Goal:** a well-defined responsible-disclosure process from day 1
of the public mirror.

**Tasks:**

1. Create `security@sourceprep.io` email alias (forwards to Eric)
2. Generate GPG key for `security@sourceprep.io`; publish fingerprint
   in `SECURITY.md`
3. Register **DMCA agent** with USPTO ($6 fee, 30 min) — required
   for DMCA safe harbor on any user-generated content (e.g., if
   GitHub Discussions or Show HN traffic generates content claims)
4. Set up `SECURITY.md` with:
   - Reporting instructions
   - Response SLA (5 business days acknowledgment)
   - Coordinated disclosure window (typical 90 days)
   - Hall of fame / acknowledgment policy
5. Document private incident response runbook (private only)
6. Consider GitHub's private vulnerability reporting feature — enable
   it as the primary channel

**Deliverable:** `SECURITY.md`; email alias; GPG key; DMCA
registration confirmation; incident runbook.

**Acceptance:** a test security report (sent by Eric to himself)
gets correct handling end-to-end.

## Part K — Insurance review

**Goal:** decide if E&O / Cyber liability insurance is needed now,
or deferred to Phase 2 / first Enterprise customer.

**Tasks:**

1. Get 2–3 quotes for tech E&O policies suitable for a single-employee
   LLC selling SaaS
2. Get 2–3 quotes for cyber liability (data breach coverage)
3. Decision:
   - **Skip at Phase 1** if (a) no hosted backend yet, (b) no
     Enterprise customers requiring proof of insurance in their MSA
   - **Purchase before Phase 2** if hosted backend launches (now
     handling customer data)
   - **Purchase immediately** if any pipeline Enterprise customer
     requires it in their MSA
4. Record decision in `RESEARCH.md`

**Deliverable:** 2–3 quotes on file; decision recorded.

**Acceptance:** decision is explicit and revisitable.

## Sequencing

```
A (DIY research) ──> B (attorney brief) ──> C (attorney consult) ──┬──> D (trademark file)
                                                                    ├──> E (patent decision)
                                                                    ├──> F (corporate review)
                                                                    └──> G (public policies)

H (license audit) — parallel; feeds NOTICE into G
I (customer terms) — depends on C
J (security infra) — parallel; feeds SECURITY.md into G
K (insurance) — parallel; quotes can run anytime
```

**Critical path:** A → B → C → D (trademark filing is the long-lead
item; everything else can complete while USPTO processes).

**Calendar estimate:** 3–4 weeks. Active Eric-time: ~1 week.

## Risks

| Risk | Mitigation |
|---|---|
| USPTO trademark search surfaces a conflicting mark | Pre-checked alternatives in `RESEARCH.md`; rebranding is painful but doable at this stage |
| Dependency license audit surfaces a GPL contamination | Replace the dep before launch; almost always a clean alternative exists; budget 1 week for swap |
| Attorney engagement takes longer than expected | Start Phase 144 Part A immediately; attorney calendar lag is the slow path |
| Patent attorney recommends multiple provisional filings (cost spike) | Stick to defensive-publication default unless commercial value is clear |
| Existing Lemon Squeezy customers exist (per SCRUTINY §11) | Customer notice + grandfathering plan; attorney drafts notice content |
| LLC operating agreement requires significant amendments | Attorney handles; budget extra $500–1,500 |
