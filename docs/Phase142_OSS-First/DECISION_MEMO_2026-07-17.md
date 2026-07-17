# OSS-Conversion Decision Memo + Backlog — 2026-07-17

> **What this is:** research-backed recommendations for every open decision in the
> OSS conversion, plus a T-leveled backlog (T1 easiest → T3 hardest) with a
> starter prompt per item. Produced from a 7-agent web-research pass (license,
> Pro-tier, patents, acqui-hire, trademark, export-control, code-signing) on
> 2026-07-17. PRIVATE — Phase 143 keep-private bucket. Research, **not legal
> advice** — the legal items note where an attorney consult is warranted.

---

## Part 1 — Recommendations (one per decision)

### D1. License: Apache-2.0 vs AGPL-3.0 → **Apache-2.0 + a CLA from commit #1**
- Your binding constraint is **adoption/reach** (it feeds the IC/acqui-hire path). AGPL is blanket-banned by policy at Google and many enterprises — it caps the exact metric you need ([opensource.google/…/agpl-policy]).
- A restrictive license does **not** protect a **zero-revenue** project the way it protects a HashiCorp; for you a clean permissive IP story is worth more in diligence than "defensible-but-frictional."
- AGPL's SaaS-copyleft barely bites a **local-first desktop tool** (no network service for §13 to attach to); the real moat is the *future proprietary hosted backend*, which stays closed regardless of engine license.
- **The CLA matters more than the license letter.** With sole copyright (solo dev + CLA) you keep every door open: relicense clean for an acquirer, or later dual-license AGPL+commercial if revenue becomes primary (Grafana/Sentry model, survivable because OSI-approved). Without a CLA those options close the moment outside contributors arrive.
- **Switch to AGPL only if** near-term open-core *revenue* (not IC/acqui-hire) becomes the primary goal, or a concrete hyperscaler-clone threat to the hosted backend appears.
- **Confidence: med-high.** Owner: **Eric decides** (open question #4). *The engine metadata is wrong regardless (MIT today) — but I will not pick the license for you.*

### D2. Pro tier at launch vs defer → **Defer. Ship OSS alone at Phase 1**
- A convenience-only signed installer at ~$70 is a **priced tip jar.** Every model that actually converts gates **use** (Sublime), the **download** (Typora), or a **hosted service** (Obsidian Sync) — never "convenience over free-buildable source." SourcePrep Pro as specced gates none of those.
- Dev-tool freemium converts ~1–4%; ~70% of micro-SaaS earn <$1K MRR; median indie ≈ $500/mo. Against a base of **zero users** and a value prop of "the same free app, signed," expected revenue ≈ noise, and the Show-HN story becomes "they charge $70 for `npm run dev` + a signature."
- **The real paid tier is the hosted index-sync / team-shared-index backend** (the Obsidian-Sync analog). Build that as the capability gate; fold code-signing/auto-update in as an *included perk* of Teams, and let enterprise procurement's "must be notarized" requirement be a reason to buy Teams — not a standalone $7 SKU.
- **Confidence: high.** Owner: **Eric decides** (open question #3); recommendation = defer.

### D3. Patents: provisional vs defensive publication → **Prior-art check first; if AIMD-for-LLMs still looks novel, file a cheap US provisional BEFORE the public commit; else defensive-publish**
- **This is a pre-publication, irreversible decision, not an LOI-trigger one.** EU/UK/most-of-world enforce **absolute novelty — zero grace period**; the instant you push the public Apache/AGPL commit, worldwide patent rights are forfeit. US gives a 12-month §102(b)(1) grace but is first-to-file and the grace can still lapse before an LOI. "Revisit patents at acquirer time" is too late.
- A provisional is **cheap** (USPTO micro-entity fee ~$65; ~$1.5–3k with an attorney) and buys a priority date + 12-month PCT/worldwide optionality that publication otherwise destroys.
- **Biggest risk is novelty, not §101.** AIMD is 1980s prior art (Jacobson TCP congestion control); adaptive concurrency-limiters already exist in OSS. Only the **LLM-API-specific application** is arguably novel. §101/Alice odds are moderate and framing-dependent (frame it as a concrete technological improvement to a networked system, à la congestion control, not "adjust a number"). *Recentive Analytics v. Fox* (Fed. Cir. Apr 2025) is a fresh headwind for generic-ML claims.
- **Confidence: moderate.** Owner: **Eric decides** (open question #5), ideally after a 30–60 min attorney consult. The **prior-art search is AI-doable and the cheapest high-value next step** (see backlog E1).

### D4. Acqui-hire vs IC-role headline → **Lead with the senior-IC narrative** (apply the RESEARCH_ROUND_2 flip)
- For a solo dev with no company/cap-table, there is **structurally nothing to acqui-hire** — the 2024–2026 acqui-hire wave (Inflection, Adept, Character.AI, Windsurf, Scale) is all funded startups with investors to compensate. The one apparent solo-OSS case (Steinberger→OpenAI) was triple-confounded (prior $116M PSPDFKit exit, 196K stars in 3 months, competing bids) and was a **hire, not an acquisition.**
- IC-offer base rate (~8–15% in 6 mo, wider for a zero-user project) dominates acqui-hire (~1–3%, effectively ~0 without virality). Optimizing for IC **also** preserves the acqui-hire tail; optimizing for acqui-hire does not lift IC odds and reads as "not serious about the craft."
- Hiring-side signal that matters: **a rigorous benchmark + 2–3 decision writeups (ADRs)**, adoption depth, judgment — **not** GitHub stars (now a discredited, fakeable signal). Start the job funnel **Week 2, not Week 12** (frontier loops run 4–6 wks); target broadly (labs **and** Cursor/Sourcegraph/Vercel/Replit/Zed/Warp).
- **Confidence: moderate-high on direction.** Owner: **Eric decides** (open question #6); recommendation = flip to IC-first. Confirms applying the six-file revision.

### D5. Trademark "SourcePrep" → **Run the free federal search FIRST (Eric, 30 min); if clear, file 1(b) on the Principal Register before Show HN**
- **Corrects the audit's stale facts:** TESS was retired Nov 2023 → use **tmsearch.uspto.gov**. TEAS Plus/Standard tiers were **eliminated Jan 18 2025** → single base fee **$350/class**; classes 9 + 42 = **$700 floor, ~$1,000 realistic** (not $500). Old "$500 / TEAS Plus $250" numbers are dead.
- **Descriptiveness (§2(e)(1)) risk: MEDIUM.** "Source"+"prep" is a clean compound of two field-relevant terms (the pattern examiners refuse — removing the space doesn't cure descriptiveness), but suggestiveness is arguable and outcomes are examiner-dependent. Have an office-action response ready.
- Zero use → must file **1(b) intent-to-use** (no 1(a) specimen exists); 1(b) filing date = constructive nationwide priority, so **file before Show HN.** §2(f) acquired-distinctiveness is unavailable at zero users; Supplemental Register is a real fallback but requires actual use first.
- If the federal search surfaces a senior software mark: **rebrand now** — pre-launch/zero-users is the cheapest moment you will ever have.
- **Confidence: med on descriptiveness, high on fees/mechanics.** Owner: **Eric runs the search + files**; AI can prep the ID-Manual goods/services descriptions (backlog E2).

### D6. Export control (EAR/BIS) → **Near-nonissue: keep a one-page self-classification memo; file nothing**
- **Corrects the audit's H3 (overstated).** Ed25519 here is **authentication / digital signature only**, not data confidentiality — so it is **excluded from ECCN 5A002/5D002** by the §772.1 definition ("cryptography for data confidentiality" explicitly excludes authentication/signature/integrity). Classifies **EAR99** (or lightweight 5A992/5D992). No encryption license to publish.
- **No BIS/NSA notification email is required in 2026** — twice over: (1) the code isn't 5D002; (2) even for 5D002, §742.15(b) now limits the email to **non-standard cryptography**, and Ed25519/TLS/AES are published standards (RFC 8032 etc.). The old §740.13(e) TSU is now "[Reserved]" — publicly-available open-source crypto source is simply "not subject to the EAR." So there is no §740.17(e) TSU classification task as the audit framed it.
- **Minimal action:** a dated one-page memo documenting the authentication-only determination (AI-doable, backlog E3). Re-evaluate only if you ever add real data-confidentiality encryption.
- **Confidence: high.** Owner: AI drafts the memo; no filing.

### D7. Code-signing lead times (feeds Pro timeline; not critical-path since Pro deferred) → **macOS: LLC-org enrollment (start D-U-N-S today, ~2–4 wk); Windows: Azure Artifact Signing individual path (~$10/mo, days) or an OV cert for LLC-branded publisher**
- macOS org enrollment needs a **D-U-N-S** (free, ~5–7 business days) + Apple org verification (~1–2 wk); notarization itself is minutes. Individual enrollment is 1–2 days but seller = personal name.
- **Azure Artifact Signing org path is BLOCKED for you** — it requires **≥3 years** operating history (Apr 2025 rule); Magnetic Anomaly LLC (formed May 2026) doesn't qualify. The **individual-developer** path (US, no 3-year rule) works (~$10/mo, no hardware token) but signs under **Eric's personal name**. LLC-branded Windows publisher needs an **OV cert** (SSL.com/Sectigo/DigiCert; 1–3 days + brand-new-LLC validation lag).
- **SmartScreen reputation takes weeks regardless** (EV no longer bypasses it).
- **Confidence: high on mechanics.** Owner: **Eric** (identity/business verification). **Because Pro is deferred (D2), this is off the critical path** — but if Pro is ever greenlit, start the D-U-N-S request on day 1.

### Internal decisions (no web research needed)

- **D8. Git-history strategy → curated fresh-initial-commit public mirror** (per `OPERATIONS.md:18`). Drop the filter-repo/squash requirement for the OSS launch (audit H8). Remove **live-tree** secrets (`codrag.key` + the test key). Treat the private repo's 1639-commit history as permanently private. Reconstruct credibility via ADRs + HISTORY.md, not raw log. Owner: recommendation stands; AI builds the mirror tool (backlog C2).
- **D9. Free-tier project limit → retire it (unlimited for FREE under OSS).** Keep the `Tier` enum for forward-compat, but set `projects_max[FREE]` to unlimited / drop the gate. Propagate to the 3 docs + a pinning test. Owner: AI (backlog C3).
- **D10. Pricing → designate `OPEN_CORE_SPLIT.md` as the single source of truth**, mark the other two SUPERSEDED, delete the phantom Founder's Edition + $30/yr renewal (contradicts "never expires"). (Largely moot for launch since Pro is deferred, but reconcile for coherence.) Owner: AI (backlog D4).
- **D11. Timeline → two-phase re-baseline: prerequisite sprint ~6–9 wk + launch sprint ~8–12 wk; adopt a 12-month success window** (not 90 days). Follows from D4. Owner: AI (backlog D5).

---

## Part 2 — Backlog (T1 easiest → T3 hardest; starter prompt each)

Legend: **Owner** = who must act. **T** = complexity. Items marked *gated* wait on a decision above.

### A. Decisions only Eric can make (do these to unblock the rest)
| ID | Decision | T | Starter prompt / action |
|---|---|---|---|
| A1 | **License: Apache-2.0 or AGPL-3.0?** | — | Read `DECISION_MEMO_2026-07-17.md` §D1. Recommendation: Apache-2.0 + CLA. Reply "Apache" or "AGPL" to unblock the metadata flips + LICENSE swap. |
| A2 | **Ship Pro at launch or defer?** | — | Read §D2 (recommend defer). Reply to set launch scope. |
| A3 | **Patent provisional on AIMD-for-LLMs before publishing?** | — | Read §D3. Decide after the prior-art check (E1) + optional attorney consult. Irreversible once you push. |
| A4 | **Acqui-hire vs IC headline?** | — | Read §D4 (recommend IC-first). Approve applying the six-file RESEARCH_ROUND_2 revision (D6 backlog). |
| A5 | **Lemon Squeezy customer count?** | — | Log into Lemon Squeezy → confirm how many license keys/orders exist. If >0, we document terms + notice; if 0, we write the all-clear. Gates any public relicense. |
| A6 | **LLC status** — operating agreement signed? EIN? bank account open? | — | Confirm the LLC can legally accept an IP assignment. |
| A7 | **Record professional history + runway (months).** | — | Calibrates IC-offer odds and timeline aggressiveness. Save privately. |

### B. Eric-only external actions
| ID | Task | T | Starter prompt / action |
|---|---|---|---|
| B1 | **Run USPTO federal clearance search** for "SourcePrep" (+variants) in classes 9/42 | T1 | Go to https://tmsearch.uspto.gov, search `sourceprep`, `source prep`, `source-prep` (live marks, classes 009/042). 30 min, free. Report any senior software mark. |
| B2 | **File trademark 1(b)** (after B1 clears) | T2 | File intent-to-use, Principal Register, class 9 (+42 if budget), base fee $350/class, pick goods/services from the USPTO ID Manual to avoid surcharges. Do before Show HN. |
| B3 | **Sign the IP Assignment** (Eric individual → Magnetic Anomaly LLC) | T1 | Sign the DRAFT the AI prepares (E4), backdated to LLC formation. Both sides = Eric. |
| B4 | **(If Pro greenlit) Start D-U-N-S + Apple org enrollment; pick Windows signing path** | T2 | Request D-U-N-S for the LLC today; enroll Apple Developer (org); for Windows choose Azure Artifact Signing (individual) or an OV cert (LLC-branded). |
| B5 | **The public mirror push** (one-shot, irreversible) | T2 | Only after the full publish checklist (audit §8 EXECUTE-AT-PUBLISH) is green and ideally peer-reviewed. |

### C. AI-executable engineering
| ID | Task | T | Starter prompt |
|---|---|---|---|
| C1 | **Ed25519 crypto fix + license-generator repair** (the "license generator" item) | T2 | "Execute `docs/Phase146_SecurityAudit/CHANGE_PLAN_ed25519_crypto_fix.md`: env-read `PREP_LICENSE_PUBLIC_KEY` + fail-closed, reject unsigned paid licenses, remove the committed test key, reconcile generator↔verifier (finding N1), add tests with an in-memory dev keypair. Local commit only, no push. Restart daemon before validating." *(Gated on Eric approving the change plan.)* |
| C2 | **Build `tools/build_public_mirror.py`** (allowlist curation + denylist-regex gate) | T3 | "Write a script that assembles a curated public tree from an explicit allowlist, runs a denylist-regex gate (codrag, ACQUIRER, SCRUTINY, DISTRIBUTION_AND_REVENUE_PLAN, CLAUDE.md, .runprep, codrag.key, private-key markers, AUDIT_2026-07-17, HANDOFF_PROMPT, RESEARCH_ROUND_2), fails on any hit, and emits the fresh-initial-commit tree. Include a dry-run + a manifest of included/excluded files." |
| C3 | **Retire the Free project limit + pinning test** | T1 | "Per D9: set `feature_gate.py` `projects_max[FREE]` to unlimited (or remove the gate), update the docstring + the 3 business docs, add a test pinning the chosen value. `.venv/bin/pytest`." |
| C4 | **License metadata flips** (pyproject/Cargo/9 npm package.json) | T1 | *(Gated on A1.)* "Flip `pyproject.toml:10` + classifier, add `license` to `engine/crates/prep-selfheal/Cargo.toml`, add a `license` field to the 10 npm package.json files lacking one, to the chosen license." |
| C5 | **Root LICENSE swap** to verbatim Apache-2.0 (or AGPL) text | T1 | *(Gated on A1 + B3.)* "Replace root `LICENSE` with verbatim chosen-license text, Copyright (c) 2026 Magnetic Anomaly LLC." |
| C6 | **Rotate + untrack `codrag.key`** | T2 | "Untrack `src/prep/dashboard/src-tauri/.tauri/codrag.key`, add `.tauri/*.key` to `.gitignore`; hand Eric the Tauri-updater keygen step + `tauri.conf.json` pubkey update." *(Needs Eric offline keygen.)* |
| C7 | **Brand-hygiene sweep for public surfaces** | T2 | "Fix `docs_grounding.py` 'RunPrep' attribution, the paperclip-plugin tests asserting `manifest.id==='codrag'`, and `license.py`'s 7 hardcoded `~/.runprep` sites to use the Phase 128 `.sourceprep` resolver. Fix the stale `@codrag/ui` package-lock." |
| C8 | **CLAUDE.md frankness scrub / clean public AGENTS.md** | T2 | "Produce a public-safe AGENTS.md (no dogfooding/internal-frankness language) for the mirror; keep CLAUDE.md private via the denylist." |
| C9 | **Run `scancode-toolkit` source-license scan** (completes item 7 / M4) | T2 | "`pipx install scancode-toolkit`; scan src/ packages/ engine/ websites/ scripts/; inspect flagged files for GPL/CC-BY-SA copy-paste or LLM-generated matches; update `LICENSE-AUDIT.md`; finalize `NOTICE`." |

### D. AI-executable content / docs
| ID | Task | T | Starter prompt |
|---|---|---|---|
| D1 | **Reclassify Phase 144 blocker #2** | T1 | "Edit `PRE_LAUNCH_BLOCKERS.md`: drop the filter-repo/squash requirement (fresh-initial-commit mirror), split into (a) remove live-tree secrets, (b) verify-no-real-history-secrets (informational). Note `codrag.key` is live-tree + already on origin." |
| D2 | **Complete the NOTICE + LICENSE-AUDIT** | T1 | "Finalize `NOTICE.draft.md` → root `NOTICE` after A1; run a full `license-checker` monorepo pass to catch npm deps beyond packages/ui; fold in the scancode results (C9)." |
| D3 | **Export-control self-classification memo** | T1 | "Draft `docs/Phase144_LegalPreLaunch/EXPORT_CLASSIFICATION.md` documenting: Ed25519 = authentication-only → outside 5D002 → EAR99; standard published crypto → no §742.15(b) notification; cite §772.1, §742.15(b), §740.13(e)-Reserved. Add a short EXPORT note to the public README." |
| D4 | **Pricing reconciliation** | T1 | "Per D10: designate `OPEN_CORE_SPLIT.md` as SoT, mark the pricing sections of `PRODUCT_AND_BUSINESS_OVERVIEW.md` + `DISTRIBUTION_AND_REVENUE_PLAN.md` SUPERSEDED, delete the phantom $49 Founder's Edition + $30/yr renewal." |
| D5 | **Timeline re-baseline + dependency graph** | T2 | "Rewrite the Phase 142 timeline as prerequisite sprint ~6–9 wk + launch sprint ~8–12 wk, 12-month success window; redraw the dependency graph with Phase 143/144 prerequisite gates explicit." |
| D6 | **Apply the RESEARCH_ROUND_2 six-file revision** (IC-first) | T2 | *(Gated on A4.)* "Flip README/STRATEGY/ACQUIRER_MAP to lead with 'senior IC at a frontier lab'; reframe acqui-hire as lottery-ticket upside; 90d→12mo; applications Week 2; add SCRUTINY §21 (Cursor SDK threat); reopen license Decision A. Mark PROPOSED if A4 unanswered." |
| D7 | **Draft IP Assignment agreement** | T2 | "Draft `docs/Phase144_LegalPreLaunch/IP_ASSIGNMENT_DRAFT.md` from the Cooley GO / YC CIIAA / Stripe Atlas 9-element checklist in `RESEARCH.md` §3.2, Eric individual → Magnetic Anomaly LLC, backdated to LLC formation. Mark DRAFT — Eric signs." |
| D8 | **Draft ToS / Privacy / EULA + governance set** | T2 | "Draft Phase-1 ToS, Privacy, EULA from templates; create `CHARTER.md`, `ICLA.md`, `CCLA.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`; git-track `SECURITY.md`. Mark DRAFT for the legal-trigger review." |
| D9 | **Prior-art search for AIMD-for-LLMs** | T2 | "Research whether an AIMD/latency-aware adaptive concurrency limiter applied specifically to LLM-API request parallelism is anticipated by prior art (TCP AIMD/Vegas literature, existing OSS adaptive concurrency-limiter libs, rate-limiter patents). Report novelty verdict to inform A3." |
| D10 | **First 8 ADRs + HISTORY.md** | T3 | "Distill ADRs 0001–0008 from the highest-signal phases (113 daemon-state, 139 embedder memory, 117 scoped rebuild, 82 MCP dogfooding) + a one-page HISTORY.md framing the 142-phase arc as deliberate engineering evolution. This is the credibility artifact acquirers/hiring managers actually read." |
| D11 | **Benchmark (Phase 142 Part E.1 + E.2)** | T3 | "Design a reproducible benchmark: SourcePrep-augmented context vs grep vs naive RAG vs plain model on real code-retrieval/context tasks, with a runnable harness + methodology; produce the first vanilla data point. Highest-leverage IC-offer artifact." |
| D12 | **File-level triage of 1064 markdown docs** | T3 | "Triage every doc into keep-public / keep-private / delete (default keep-private when ambiguous, 5 min/file), producing the allowlist that feeds C2. Start with the strategic-IP denylist already known." |
