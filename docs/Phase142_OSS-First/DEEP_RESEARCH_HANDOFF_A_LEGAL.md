# Deep-Research Handoff — Session A: Legal research (DR-2, DR-3 + ED-2/ED-3 prefixes)

> **Self-contained starter prompt** for a dedicated follow-up AI session.
> Part of the 2026-07-19 legal+security+message audit follow-up. Full audit
> context: `docs/Phase142_OSS-First/LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md`
> (read it for background, but everything you must DO is inline below).
>
> You are one of four parallel deep-research sessions (A=legal, B=security
> engineering, C=SBOM scan, D=codrag.key history). You do NOT need to wait on
> the others.

## What this session is

Pure **legal research** — no code mutation, no git mutation, no legal act.
You produce findings + framed decision-questions for Eric. Two full
deep-research items (DR-2 trademark, DR-3 Apache-2.0 §4 distribution) plus
the research-prefix halves of two Eric-decision items (ED-2 Terms gaps,
ED-3 Plausible/Resend data-posture).

## Hard rules

- **Read-only on git AND the filesystem** for this session. No `git` mutation,
  no file edits except your own output doc. No worktree needed.
- **License-neutral.** The relicense to Apache-2.0 is DECIDED + APPLIED
  (commit `99315988` landed; root `LICENSE` is canonical Apache-2.0). VERIFY
  completeness/consistency; do NOT assert a new license; do NOT perform any
  legal act (don't file a trademark, don't finalize Terms, don't publish a
  privacy policy). You RESEARCH and PROPOSE; Eric + an attorney sign off later.
- **NO attorney budget.** When you hit a decision that's Eric's (or an
  attorney's), STOP and surface it as a framed question with options + a
  recommended default. Do not decide.
- **Don't trust memory/notes for code claims** — verify against the repo.
- **SourcePrep = brand; prep = code.** Never CoDRAG/RunPrep/~/.runprep in any
  proposed public copy.
- **No image input** (model crashes on PNG Read). Verify text-only.
- **prep MCP:** call `prep` (no args) first for orientation; the project_id is
  in `.sourceprep/AGENT_CONTEXT.md` (or auto-detected). Use `prep_search` for
  code-side verification; for legal-text comparison use Read + grep (legal
  text has no graph).
- **Dogfooding:** this is the SourcePrep repo using its own MCP tools — note
  when prep results are unhelpful/wrong (product feedback).

## Items to research

### DR-2. Trademark clearance + ™/® signaling decision research
1. Search **USPTO TESS** (https://tmsearch.uspto.gov) for live
   applications/registrations matching "SourcePrep", "Source Prep",
   "SOURCEPREP" in IC 9 (software) and 42 (SaaS). Report owners + dates.
2. **Likelihood-of-confusion survey** on prior third-party uses of "source
   prep" / "SourcePrep" in dev-tools and code-indexing (web + GitHub search).
   Assess the **descriptiveness refusal risk** — the mark is SOURCE + PREP,
   which may be merely descriptive under §2(e)(1).
3. Recommend **® (post-approval under 15 U.S.C. §1065) vs ™ (common-law
   claim now)**, with reasoning.
4. **Draft a one-paragraph trademark policy** to append to NOTICE (per
   `LICENSING_DEEP_RESEARCH_REPORT.md:144`) stating what the mark covers, the
   common-law-pending-registration basis, and the permission-contact for fork
   naming.
5. **Cross-check** the policy text against `CHARTER.md:64-70` and
   `websites/apps/marketing/src/app/terms/page.tsx:118-124` so all three
   surfaces can use identical wording.
- **Open question to settle:** is "SourcePrep" registrable, or merely
  descriptive?

### DR-3. Per-app LICENSE/NOTICE file absence — Apache-2.0 §4 distribution analysis
1. **Confirm** whether Apache-2.0 §4 distribution obligation is triggered by
   Netlify SaaS deployment of a Next.js app (expected: no — Apache-2.0 is
   not AGPL; SaaS is not conveyance). Cite the license text + a precedent/FAQ.
2. **Document** the npm/Next.js community norm for monorepo app subtrees that
   assert `"license"` in `package.json` without a sibling LICENSE file (npm
   treats the field as metadata; no hard requirement a LICENSE file sit next
   to every package.json in a monorepo).
3. **Check** whether any of the four apps (docs/marketing/support/payments) is
   ever distributed as source/object — a downloadable bundle, a Docker image
   pushed to a public registry, or the planned public GitHub mirror of the
   subtree. The known gate is `tools/build_public_mirror.py` (allowlist +
   denylist, fails-closed at `:412-416`); check whether it's the only
   distribution channel. If any channel distributes an app subtree, §4 IS
   triggered and a LICENSE copy + NOTICE must accompany that distribution.
- **Open question to settle:** does any distribution channel trigger §4, or
  is SaaS-only deployment sufficient to skip per-app LICENSE files?
- Note: `packages/vscode/LICENSE` was already aligned to Apache-2.0 in audit
  commit `88dbc4bf`; the vscode extension IS published (marketplace) so its
  §4 posture is the most interesting — examine it specifically.

### ED-2 research prefix — Terms of Service gap analysis (research only; do NOT finalize)
Read `websites/apps/marketing/src/app/terms/page.tsx` fully. The Terms page
is DRAFT ("not yet in effect", line 27). Eric's recommended default is
**keep OSS-only until Terms finalized**. Your job is to **inventory the
missing clauses** so Eric knows what an attorney must add before any paid
sale. Specifically check for and report the absence of:
- Effective date
- Governing-law / jurisdiction clause
- Liability cap tying to the AS-IS warranty block (lines 209-216)
- Refund window (line 161 defers to "at time of purchase" — vague)
- Auto-update / termination terms for per-purchaser license keys (lines
  109-113)
- A reference to a standalone trademark policy from lines 119-124 (depends on
  DR-2's output — note the cross-link)
Produce a **gap list + a drafted minimum-clause proposal** (research/draft,
NOT a legal act) Eric can hand to an attorney. Frame the ED-2 decision:
"finalize these clauses + flip DRAFT, or keep OSS-only?" (Eric's recommended
default: keep OSS-only).

### ED-3 research prefix — Plausible + Resend subprocessor data-posture (research only)
Plausible analytics is loaded on all four public surfaces
(`support/layout.tsx:39`, `payments/layout.tsx:39`, `docs/layout.tsx:39`,
`marketing/layout.tsx:87`) with no privacy disclosure, and
`marketing/security/page.tsx:92-93,249` asserts "Telemetry: Not Collected /
Usage Analytics: DISABLED" (misleading to a tracked visitor). The bug-report
route uses Resend for email. Your job is to **gather the facts** so Eric can
decide (do NOT publish a privacy policy):
1. **Confirm Plausible Cloud's current data-processing posture** — EU-hosted?
   DPA available? sub-processor list? (see plausible.io/docs/data-policy).
   Cookieless? IP-truncated? Cross-site tracking? PII?
2. **Check whether any of the four Plausible site IDs is configured for
   cross-site linking** (grep the layout Script tags for `data-domain` /
   `data-linked-domains` / `plausible.io/js/script.*`).
3. **Verify whether the support bug-report route's Resend email subprocessor
   is already disclosed anywhere** (grep all surfaces for "Resend" /
   "resend.com"). It's almost certainly NOT — confirm.
4. Draft a **one-paragraph "Website Analytics" subsection** + a **one-line
   Resend subprocessor disclosure** (research/draft, NOT published) Eric can
   approve and place. Also draft the reworded `security/page.tsx:92-93,249`
   lines scoped to "the SourcePrep desktop product" (that rewording itself is
   a license-neutral fix-now Eric can bundle in — note it as such).
Frame the ED-3 decision with the 4 options from the audit (publish disclosure
/ self-host Plausible / switch provider / remove Plausible) + recommended
default (a — minimal disclosure, no cookie banner).

## What to PRODUCE

Write your findings to:
**`docs/Phase142_OSS-First/DEEP_RESEARCH_A_LEGAL_FINDINGS.md`**

Structure:
1. **DR-2 trademark** — TESS results table, confusion/descriptiveness
   analysis, ®/™ recommendation, drafted trademark policy paragraph,
   cross-surface wording alignment notes.
2. **DR-3 Apache §4** — the SaaS-vs-conveyance answer with citation, the
   npm-monorepo norm, the distribution-channel inventory per app (esp.
   vscode marketplace), and a per-app "LICENSE/NOTICE file needed?" verdict.
3. **ED-2 Terms gaps** — the missing-clause inventory + the drafted
   minimum-clause proposal + the framed decision.
4. **ED-3 Plausible/Resend** — the data-posture findings, cross-site-link
   check result, Resend-disclosure grep result, the drafted disclosure
   paragraphs, the scoped `security/page.tsx` rewording, the framed
   decision.

## STOP and surface to Eric when

- All four sections are written.
- Every decision point is framed as a question with options + recommended
  default (DR-2 ®/™, DR-3 per-app verdict, ED-2 finalize-or-keep-OSS, ED-3
  publish/self-host/switch/remove).
- You have NOT filed a trademark, finalized Terms, or published a privacy
  policy (those are Eric + attorney).

## Commit

Commit your findings doc locally (one commit): `git add` the findings doc +
`git commit -m "docs(phase142): deep-research A — legal (trademark, Apache §4, Terms gaps, Plausible posture)"`. **NEVER push** (no `[deploy]` signal).
**No Co-Authored-By.** **Never `git commit --amend` on main** — verify
`git log -1` is yours before any history op (concurrent sessions collide).