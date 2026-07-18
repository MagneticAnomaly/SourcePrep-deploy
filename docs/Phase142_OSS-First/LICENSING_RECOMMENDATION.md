# Licensing Recommendation — Decision of Record

> **Status:** DECIDED. Confirmed by Eric 2026-07-18. This is the authoritative
> record of the outbound-license decision the marketing site and specs cite.
> It consolidates a decision that was previously recorded only piecemeal
> (Phase 144 `RESEARCH.md` "Decided 2026-06-15"; the 2026-07-17 OSS marketing
> spec/plan). A separate validation deep-research pass (prompt:
> `LICENSING_DEEP_RESEARCH_PROMPT.md`) may augment this rationale but does **not**
> reopen the decision. PRIVATE — Phase 143 keep-private bucket.

## Decision (one line)

**The SourcePrep engine ships under Apache License 2.0, with contributions under
the Developer Certificate of Origin (DCO) — not a CLA — and the license is
permanent (no AGPL fallback).**

## The three sub-decisions and why

1. **Apache-2.0 over AGPL-3.0.** The binding constraint is adoption/reach among
   the engineers whose uptake feeds the IC-role / credibility path. AGPL is
   blanket-banned by policy at many enterprises (Google et al.), which caps that
   reach. AGPL's network-copyleft also barely applies to a **local-first desktop
   tool** (no hosted network service for §13 to attach to). The real moat is the
   future **proprietary hosted backend** (Teams/Enterprise), which stays closed
   regardless of the engine license — so AGPL buys little here while costing
   adoption.

2. **DCO, not a CLA.** DCO is a lightweight per-commit sign-off (`Signed-off-by`)
   that asserts the contributor has the right to submit — low friction, no rights
   assignment, contributor-friendly. A CLA would have preserved the option to
   relicense later (e.g. dual-license AGPL+commercial), but we are deliberately
   **not** preserving that option (see #3).

3. **Permanent — no AGPL fallback / no relicense plan.** Committing to Apache
   permanently is a deliberate anti-rug-pull trust signal. The known **tradeoff:
   with DCO (no CLA), relicensing later is effectively impossible** — every
   contributor holds their own copyright and would have to agree. That is
   accepted: we would rather send a credible "we will never take this back"
   signal than hold a relicense option we do not intend to use.

## What is NOT affected by this

- The paid **Pro** tier ($29 one-time convenience installer) needs no license
  protection — it gates convenience, not capability, and self-build stays free.
- The **hosted Teams/Enterprise backend** is a separate proprietary codebase and
  is unaffected by the engine's Apache license.
- **Trademark** ("SourcePrep") is handled separately; Apache-2.0 grants no
  trademark rights (state this in the ToS, which already does).

## Open execution items (this decision is made; these carry it out)

- [ ] **Swap the root `LICENSE`** from the current commercial-proprietary text to
  verbatim Apache-2.0 (Copyright (c) 2026 Magnetic Anomaly LLC) — sequence
  **after** the IP Assignment (so the LLC owns what Apache grants). *Root
  `LICENSE` is still commercial today.*
- [ ] Flip `pyproject.toml`/Cargo/npm metadata to `Apache-2.0`.
- [ ] Add `NOTICE` (draft: `NOTICE.draft.md`) with third-party attributions.
- [ ] Add a `DCO`/`CONTRIBUTING.md` explaining `Signed-off-by` sign-off (and a
  DCO check on the public repo).

## Provenance

Apache-2.0 has been the working outbound license since **2026-06-15** (Phase 144
`RESEARCH.md` §2). The DCO-not-CLA + permanent nuance was set in the 2026-07-17
OSS marketing spec. Eric confirmed "Apache is final" on **2026-07-18**. The
marketing site's Apache 2.0 copy is therefore correct and unblocked.
