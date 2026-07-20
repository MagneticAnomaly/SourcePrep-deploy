# Deep-Research A — Legal Findings (DR-2, DR-3, ED-2, ED-3)

> **Session:** A (Legal) of the 2026-07-19 legal+security+message audit follow-up.
> Handoff: `DEEP_RESEARCH_HANDOFF_A_LEGAL.md`. Audit context:
> `LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md`.
> **Produced:** 2026-07-19. **Method:** 6 parallel research agents (web +
> code) → 4 adversarial verifiers (Apache §4 / ED-3 code / channel completeness /
> trademark descriptiveness), then synthesis against the repo's own legal text.
> **Nature:** RESEARCH + FRAMED DECISIONS only. Nothing filed, nothing finalized,
> nothing published. License-neutral (Apache-2.0 is DECIDED + APPLIED — root
> `LICENSE` verified verbatim Apache-2.0, commit `99315988`). Eric + an attorney
> sign off on every decision below.

---

## TL;DR — the four framed decisions

| Item | Open question | Answer / recommendation | Who decides |
|---|---|---|---|
| **DR-2** | Is "SourcePrep" registrable, or merely descriptive? What symbol? | **Borderline suggestive-to-descriptive; MODERATE §2(e)(1) refusal risk** (not low, not high). File **intent-to-use on the Principal Register in Classes 9 + 42 now**, budget for a first-action descriptiveness refusal, keep a Supplemental-Register/§2(f) fallback. Use **™ now; switch to ® only after a registration certificate issues**; file §15 incontestability at year 5. | Eric + TM attorney |
| **DR-3** | Does any distribution channel trigger Apache-2.0 §4, or is SaaS-only enough to skip per-app LICENSE files? | **SaaS hosting does NOT trigger §4** (verified high-confidence). The four web apps need **no per-app LICENSE/NOTICE files**. The real §4 gap in scope is the **published VS Code `.vsix` — it ships LICENSE but is MISSING NOTICE**. Fix: add `packages/vscode/NOTICE`. Three *out-of-scope* channels also trigger §4 and likely miss NOTICE (PyPI `prep-engine` wheel, GHCR Docker images, Tauri desktop installers) — flagged for Session B/C. | Eric (compliance fix) |
| **ED-2** | Finalize the Terms clauses + flip DRAFT, or keep OSS-only? | **Keep OSS-only until Terms are attorney-finalized** (Eric's recommended default). 7 hard-blocker clauses + ~11 recommended clauses are missing; no revenue depends on flipping the flag (paid tiers are "coming soon / not on sale"). | Eric + attorney |
| **ED-3** | Publish disclosure / self-host Plausible / switch provider / remove Plausible? | **(a) Publish a minimal disclosure, no cookie banner** (recommended default). Plausible is EU-hosted, cookieless, no-PII, auto-DPA — the least-cost fix is honesty, not removal. Separately, **Resend (US email subprocessor) is undisclosed** and needs a one-line disclosure. | Eric |

**License-neutral fix-now items** (safe for Eric to bundle without legal signoff — details in §4c and §2d):
1. **`security/page.tsx` rewording** — scope the "Usage Analytics: DISABLED/NONE" / "Telemetry: Not Collected" claims to *the SourcePrep desktop product/`prep` daemon* and honestly disclose the site's cookieless Plausible analytics. (Marketing-accuracy fix; touches no license terms.)
2. **Add `packages/vscode/NOTICE`** — Apache-2.0 §4(d) compliance for the published extension. (License-hygiene fix; adds a file, changes no terms.)

---

## Implementation status (updated 2026-07-20)

The two license-neutral fix-now items above — plus the DR-2 #4/#5 trademark work and a footer disclosure — have been **APPLIED locally** (commit `78dd6b3b`; footer follow-up in a later local commit; findings doc = `ae77fe20`). **Not pushed** — the marketing site is `[deploy]`-gated, so nothing is public until Eric pushes with `[deploy]`.

- ✅ `packages/vscode/NOTICE` added (Apache-2.0 §4(d) — the one in-scope gap).
- ✅ Root `NOTICE` Trademark section added; wording harmonized across `NOTICE`, `CHARTER.md`, and the Terms page (™ / common-law-pending / contact).
- ✅ `security/page.tsx` scoped to the desktop product; Plausible + Resend disclosed.
- ✅ Shared `SiteFooter` (all four public apps): a footer **trademark line** + a **cookieless-analytics note** (per Eric — ™ kept to legal contexts + footer only, no header-lockup ™; the analytics disclosure lives in the footer, not a banner).
- ⏸️ **Plausible provider decision (self-host / switch / keep paying / remove) DEFERRED** by Eric — cost-gated, revisit later. The footer + security disclosures stand regardless of provider.

## Legal Acts — what Eric + an attorney must do

Everything below requires a human decision or a licensed attorney. The agent has **not** filed, finalized, or published anything, and cannot.

**A. Requires a trademark / IP attorney**
1. **Clear + file the "SourcePrep" trademark.** Have counsel run the authoritative `tmsearch.uspto.gov` exact/phonetic search (the SPA blocked automated tools, so §1a's "none found" is a presumption, not a confirmed clear), then **file intent-to-use on the Principal Register, Classes 9 + 42.** Descriptiveness risk is **MODERATE** (§1c) — instruct counsel to (i) draft the goods/services ID so it does **not** recite "prepares source code" verbatim, and (ii) keep a Supplemental-Register / §2(f) fallback ready.
2. **Terms of Service — draft the 7 hard-blocker clauses** (§3) before ANY paid sale: effective date · governing law/venue · a real **liability cap** (the current AS-IS block is an unenforceable-for-paid total exclusion) · concrete refund window · license lifecycle · indemnification · acceptable-use.
3. **Register the U.S. copyright ≤ 3 months of first publication** (17 U.S.C. §412 — preserves statutory damages/fees).

**B. Eric's business decisions (no attorney strictly required)**
4. **™ / ® usage:** use **™** on "SourcePrep" now (applied in legal contexts + footer); switch to **®** only after a registration certificate issues; file §15 incontestability at year 5.
5. **Terms:** keep **OSS-only** — do **not** flip the `Terms_v2.0_DRAFT` flag until A2 is done (recommended default; no revenue depends on it).
6. **ED-3 analytics:** minimal disclosure is applied (footer + security page). The **provider decision** is **deferred** (cost-gated). Spot-check the Plausible dashboard for cross-domain linking (invisible to the repo).
7. **Review the security-page + footer disclosure wording** before pushing with `[deploy]` (privacy-policy content — worth an attorney glance).

**C. Route to the packaging / SBOM track (Session C) — out of Session A's four-item scope but real §4 gaps (§2c)**
8. PyPI `prep-engine` wheel (no `license` field in `engine/pyproject.toml`; no `engine/LICENSE`/`NOTICE`), GHCR Docker images (Dockerfiles don't `COPY LICENSE NOTICE`), and Tauri installers likely ship without LICENSE/NOTICE — bundle with Session C's "MPL NOTICE attribution" docket item.
9. Session C also flagged a **vendor-logo trademark** question (nominative fair use of third-party logos on the compare pages) to this legal track — outside the four items; worth a quick legal look.

**Then:** push the local commits (findings + fixes across the four DR sessions) when ready — with `[deploy]` only when the site should go live.

---

## 1. DR-2 — Trademark clearance + ™/® signaling

### (a) USPTO / registration search — NONE FOUND (with a real caveat)

No live or dead USPTO application or registration for **"SourcePrep," "Source Prep," or "SOURCEPREP"** in International Class 9 (downloadable software) or Class 42 (SaaS) was found in any database reachable by automated research.

| Mark searched | Class 9 | Class 42 | Any class | Sources checked |
|---|---|---|---|---|
| SOURCEPREP | none | none | none | USPTO landing, WebSearch, GitHub API |
| SOURCE PREP | none | none | none | Justia (site-scoped), WebSearch |
| SOURCEPREP (word/design) | none | none | none | Trademarkia, WebSearch |

**Search limitation (must be closed by counsel before filing):** the live USPTO "Trademark Search" system at `tmsearch.uspto.gov` is a JavaScript SPA backed by an API; automated fetch returns only the shell, so the **authoritative USPTO index could not be directly queried**. Third-party mirrors (`trademarks.justia.com`, `trademarkia.com`) returned HTTP 403 to automated fetch and were routed around with site-scoped web searches. This is a *presumption of clearance from negative searches*, **not** a confirmed clear. → **Counsel must run the exact word-mark + `SOURCE*PREP*` truncation + phonetic query in `tmsearch.uspto.gov`, and a `tsdr.uspto.gov` status pull on any hit, before filing.**

### (b) Likelihood-of-confusion survey — no genuine conflict in dev-tools

| Use | What it is | Field | Conflict | URL |
|---|---|---|---|---|
| **sourceprep.com** | Bespoke culinary *mise-en-place* meal-prep service; TLS cert **expired** (dormant). | Food services (~IC 43) | **Low** — unrelated goods/services/channels; no DuPont overlap. Same literal string, different market. | https://sourceprep.com/ |
| `MagneticAnomaly/SourcePrep-MCP`, `-deploy` | **Applicant's own repos** (use-in-commerce evidence). | Dev tools | None (self). | github.com/MagneticAnomaly |
| `TweyaYaw/SourcePrepared` | Different word, Lua repo, 0 stars, no product. | Hobby | Negligible. | github.com/TweyaYaw |
| `gitprep` (reneeb/bollwarm) | Self-hosted GitHub clone; different dominant term (GIT-). | Dev tools | Low/none. | github.com/reneeb/gitprep |

GitHub REST API `search/repositories?q=sourceprep` → **total_count = 3**, all accounted for (2 are Eric's, 1 is the unrelated "SourcePrepared"). **No competing dev-tool / code-indexing / RAG / AI-context product named "SourcePrep" exists in the searched sources.**

### (c) Descriptiveness under Lanham Act §2(e)(1) — BORDERLINE; MODERATE refusal risk

`SOURCEPREP` = **SOURCE** (source code) + **PREP** (clipped "prepare/preparation"), telescoped into one coined word. Standard: §2(e)(1) / TMEP §1209.01(b) (merely descriptive = "immediately conveys" a feature/function); TMEP §1209.01(a) (suggestive = "requires imagination"); TMEP §1209.03(d) (deleting the space between two descriptive words usually does **not** cure descriptiveness absent incongruity).

**Both the research pass and the adversarial verifier converged on MODERATE — here are the two sides:**

- *Toward suggestive (registrable):* the mark does **not** convey the actual function/output. "Prep of source" could mean linting, formatting, staging-for-commit, building, packaging — it does **not** tell you this is a semantic-index / RAG / MCP context engine for AI agents. That missing "what-is-prepared-and-for-whom" is a legitimate imaginative leap. The mark is also a coined, unspaced, non-dictionary word.
- *Toward descriptive (the verifier's sharpening):* the composite is **fully congruent** — "source + prep" reads as exactly "preparation of source," directly paralleling the *In re Gould (SCREENWIPE)* / *In re Tower Tech (SMARTTOWER)* line where combining two descriptive terms stays descriptive absent incongruity (contrast ROACH MOTEL). Telescoping + clipping is a thin departure examiners routinely disregard. **Worst, the applicant's own tagline — "prep the context before any AI call" — is descriptive-use evidence an examiner will cite**, and if the ID recites software that "prepares source code context," the examiner has a near-ready §2(e)(1) record.

**Verdict: borderline, MODERATE (not low, not high) probability of a first-action §2(e)(1) refusal**, overcomeable by argument and, if needed, §2(f) or the Supplemental Register.

**Fallbacks if refused:** (i) **§2(f) acquired distinctiveness** — ≥5 yrs substantially-exclusive continuous use is prima facie; earlier with sales/ad evidence + declaration. (ii) **Supplemental Register** — the mark is clearly *not generic* (no product genus "sourceprep"), so it stays SR-eligible; an SR registration issues, permits **®**, and bridges to the Principal Register once distinctiveness accrues.

**Counsel guidance (from the verifier):** file **intent-to-use on the Principal Register**, but (1) budget for a §2(e)(1) first-action refusal + response; (2) **strengthen the ID wording to avoid reciting "prepares source code" verbatim**; (3) keep a Supplemental-Register/§2(f) fallback ready; (4) build secondary-meaning evidence early.

### (d) ™ vs ® recommendation

**Use `™` immediately; file now to lock priority; switch to `®` only after the registration certificate issues; pursue §15 incontestability at year 5.**

1. **Adopt `™` today.** Common-law rights attach on use in commerce; `™` gives notice and begins building §2(f) evidence you may later need.
2. **Do NOT use `®` yet.** Under **15 U.S.C. §1111**, `®` may be used **only after** a federal registration issues; pre-registration use is improper and can be cited against the applicant. `®` is what unlocks §1111 statutory notice (recover profits/damages without proving actual notice).
3. **File the federal application now** (Class 9 + 42), §1(a) use-in-commerce if publicly shipping else §1(b) intent-to-use, to secure the constructive-use priority date. (Note: a **Supplemental Register** registration also issues a certificate → **®** becomes usable then too, so the descriptiveness question and ®-eligibility are linked.)
4. **After registration, adopt `®`.**
5. **At 5 yrs post-registration, file a §15 affidavit** for incontestable status under **15 U.S.C. §1065** — this forecloses a later "merely descriptive" challenge, converting a moderate-risk mark into a durable asset.

### (e) DR-2 #4 — DRAFTED trademark policy paragraph (for `NOTICE`)

`NOTICE` currently has **no** trademark paragraph (verified — it ends at the third-party attributions). Per `LICENSING_DEEP_RESEARCH_REPORT.md:144` ("registration + a short trademark policy do that work"), append the following. It states what the mark covers, the **common-law/pending-registration** basis (consistent with the ™-now recommendation), and the permission contact:

```
## Trademark

"SourcePrep"™ and the SourcePrep logo are trademarks of Magnetic Anomaly LLC.
Magnetic Anomaly LLC claims common-law rights in these marks and uses the ™
symbol pending federal registration. The Apache License 2.0 covers the source
code only and grants no trademark rights (see Apache-2.0 §6). You may not use
the "SourcePrep" name or logo to name or brand a fork or derivative product,
or in any way that suggests endorsement by or affiliation with Magnetic
Anomaly LLC, without prior written permission. Forks and derivative works are
welcome and encouraged — please choose a distinct name that does not
incorporate "SourcePrep." For permission or naming questions, contact
legal@sourceprep.io.
```

### (f) DR-2 #5 — cross-surface wording alignment (3 surfaces)

The trademark statement lives on three surfaces today. The drafted paragraph above is designed to be the **canonical** wording; the other two already say the same thing and need only light alignment (**do NOT edit in this session — read-only; these are proposals for Eric**):

| Surface | Current state | Alignment note |
|---|---|---|
| **`NOTICE`** | No trademark paragraph. | **Add** the canonical paragraph (§1e). |
| **`CHARTER.md:64–70`** | *""SourcePrep" is a trademark of Magnetic Anomaly LLC. The Apache-2.0 license grants no trademark rights; use of the name … to endorse or promote derivative works is not permitted without written permission. Forks are welcome and encouraged; please choose a distinct name. See the project Terms of Service for the full trademark notice."* | **Already consistent.** Optional: add the `™`/common-law-pending-registration phrasing + `logo` + `legal@sourceprep.io` contact so all three read identically. |
| **`terms/page.tsx:118–124`** | *"The "SourcePrep" name and logo are trademarks of Magnetic Anomaly LLC; the Apache License 2.0 does not grant trademark rights, and you may not use them to brand a fork or derivative product, or to suggest endorsement by Magnetic Anomaly LLC, without written permission."* | **Already consistent** (covers name **and logo**). Optional: add the common-law-pending phrasing + a link to a standalone Trademark Policy (see ED-2 gap). |

All three converge on the same substance: *marks belong to Magnetic Anomaly LLC; Apache-2.0 grants no TM rights; forks welcome under a distinct name; no endorsement; permission required.* The only true gap is that **`NOTICE` has no paragraph at all** — filling it makes the three surfaces uniform.

---

## 2. DR-3 — Apache-2.0 §4 distribution analysis

### (a) Q1 — Does Netlify SaaS deployment trigger §4? **NO** (verified high-confidence)

Serving a website is **public performance/display + use**, not "Redistribution of copies." Every §4 condition is textually gated on the verb **"distribute"** to **"recipients"**:

- §4 chapeau: *"You may reproduce and **distribute copies** of the Work … provided that You meet the following conditions."*
- (a) *"give any other **recipients** … a copy of this License"*; (c) *"retain, **in the Source form** of any Derivative Works **that You distribute** …"*; (d) *"any Derivative Works **that You distribute** must include … NOTICE …"*
- §2 grant enumerates *"publicly display, publicly perform, … **and distribute**"* as **separate** rights; §4's conditions attach only to the *distribute* branch.

Apache-2.0 is **not** a network-copyleft license and has **no AGPL §13 analog**. AGPL §13's very existence ("Notwithstanding any other provision …") proves network interaction is otherwise *not* a distribution event. GPLv3 §0 makes it explicit: *"Mere interaction with a user through a computer network, with no transfer of a copy, is not conveying."* Secondary authority agrees SaaS ≠ distribution for permissive licenses (FOSSA, Wiz, Black Duck SaaS white paper).

**The one real carve-out — the client-side JS bundle.** When a visitor loads the app, the server **transfers a copy** of the minified client JS to the browser — an **Object-form** transfer, so *in principle* within §4's chapeau. Walking the conditions against a minified Object artifact:
- **§4(c) does NOT bite** — it is expressly limited to *"the Source form"*; a minified bundle is Object form. (Verifier correction to the first pass, which had over-stated this.)
- **§4(b)** (mark modified files) is a Source-file concept, not engaged by a concatenated Object bundle.
- **§4(a)** + conditional **§4(d)** can attach **only to the extent the bundle embeds *third-party* Apache-2.0 code** (you are the Licensor of your own first-party code, so §4 imposes nothing on you for shipping it).

**Practical upshot:** the hosting act is a **clean NO** for §4. Where the client bundle embeds third-party Apache-2.0 code, the conservative posture is a reachable **`/third-party-notices` page** (aggregated third-party LICENSE text + any upstream NOTICE contents — the output of a `license-checker` / NOTICE-aggregation step; §4(d) expressly allows *"a display generated by the Derivative Works"*). **Concrete trigger to check:** the repo's own `NOTICE` lists **Tremor (`@tremor/react`) as Apache-2.0** on the frontend; if Tremor (or any Apache-2.0 dep) ships in a given app's client bundle, that app's `/third-party-notices` obligation is real, not hypothetical. React/Next.js themselves are MIT. Recommend a per-bundle `license-checker` pass to enumerate which Apache-2.0 deps actually ship. This is a **best-practice, not a copyleft trigger, and not a reason to place a LICENSE beside every `package.json`.**

### (b) Q2 — Does the npm/monorepo norm require a LICENSE beside every `package.json`? **NO**

`"license": "Apache-2.0"` is a complete **SPDX metadata** declaration. Per the npm `package.json` docs, a co-located LICENSE file is required **only** for a *custom* license via `"SEE LICENSE IN <file>"` — not for a standard SPDX id. The universal monorepo norm (React, Next.js, Babel, Turborepo, npm workspaces) is **one root LICENSE** + each workspace declaring the SPDX id. **Caveat that *strengthens* the verdict:** a workspace **published to npm** ships an isolated `npm pack` tarball (a §4 "distribute copies" event) — so *publishable* packages should bundle their own LICENSE/NOTICE. Internal/`private:true` workspaces need nothing beyond the root file.

### (c) Distribution-channel inventory (code-verified) + per-artifact §4 verdict

Root `/LICENSE` = verbatim Apache-2.0 (commit `99315988`); root `/NOTICE` present. §4 genuinely governs every channel below.

| # | Channel | Trigger | Form | Public | §4? | LICENSE in artifact | NOTICE in artifact |
|---|---|---|---|---|---|---|---|
| A | **Public GitHub source mirror** (`build_public_mirror.py` → `MagneticAnomaly/SourcePrep`) | manual emit | Source | yes | **YES → satisfied** | root ✓ | root ✓ |
| B | **VS Code Marketplace `.vsix`** (`vsce publish`, manual) | manual | Object | yes | **YES → GAP** | ✓ packed | **✗ MISSING** |
| C | **GHCR Docker images** (`docker-headless.yml`, `app-v*` → `ghcr.io/magneticanomaly/prep-headless:cpu/:gpu`) | CI | Object | yes | **YES → gap** | ✗ | ✗ |
| D | **PyPI `prep-engine` wheel + sdist** (`engine-wheels.yml`, `engine-v*`) | CI | Object+Source | yes | **YES → likely gap** | verify | **likely ✗** |
| E | **GitHub Releases — Tauri `.dmg`/`.exe`/`.msi`** (`release.yml`, `app-v*`, draft) | CI | Object | yes | **YES → verify** | verify | likely ✗ |
| F | **Netlify hosting** (`deploy-websites.yml`, `[deploy]`-gated) | CI | served HTML/JS | yes | **NO** (SaaS ≠ conveyance) | n/a | n/a |
| G | **npm registry** | — | — | — | **NONE ACTIVE** (no `npm publish` in CI; apps all `private:true`) | — | — |

**Per-app table (the four web apps):** each of `docs / marketing / support / payments` (`@prep/*`) asserts `"license": "Apache-2.0"`, is `"private": true`, and has **no sibling LICENSE/NOTICE** (verified: `find websites -iname 'license*' -o -iname 'notice*'` → nothing). **Verdict: no per-app files needed** — they are distributed only inside the single-root public mirror (root LICENSE+NOTICE satisfy §4) and otherwise only *served* via Netlify (support + payments aren't even deployed — those jobs are commented out).

**The one real §4 gap in scope — the VS Code `.vsix`:**
- `packages/vscode/LICENSE` exists, Apache-2.0 (11,357 B, aligned in audit commit `88dbc4bf`); `.vscodeignore` does **not** exclude it → **LICENSE ships** in the `.vsix` (vsce auto-includes it anyway). ✓
- `packages/vscode/NOTICE` **does not exist**, and `vsce` packages only `packages/vscode/` — the **repo-root `NOTICE` is out of scope and does NOT ship** in the `.vsix`. ✗
- §4(a) LICENSE = met; **§4(d) NOTICE/attribution = NOT met**. **→ ACTION: add `packages/vscode/NOTICE`** (carrying at least the root NOTICE's attributions relevant to the bundled deps), and keep it out of `.vscodeignore`. This is a compliance fix Eric can apply now (see fix-now list).

**Out-of-scope but flagged (Session B/C):** the completeness verifier found three *additional* armed §4-triggered channels the four-app-only scope would have missed:
- **PyPI `prep-engine` wheel/sdist** — `engine/pyproject.toml` has **NO `license` field**, no `license-files` config, and there is **no `engine/LICENSE` or `engine/NOTICE`** (Cargo.toml's `license="Apache-2.0"` is Rust-crate metadata, not the Python wheel's bundled files) → the published wheel/sdist **likely ships without LICENSE + NOTICE**.
- **GHCR Docker images** — `Dockerfile.cpu/gpu` `COPY` only `pyproject.toml`/`src`/`engine`, **not** LICENSE/NOTICE → neither ships in the image.
- **Tauri desktop installers** on GitHub Releases — verify NOTICE inclusion in the bundle.
(These are tag-gated/draft — armed channels, not proven past distributions — but §4 attaches the moment a tag is pushed, so they belong in the inventory.) Also latent: `@prep/ui` and `@prep/paperclip-plugin` have no `private` flag (npm-publishable, but no CI publishes them today).

### (d) DR-3 open question, answered

> **Does any distribution channel trigger §4, or is SaaS-only enough to skip per-app LICENSE files?**

**SaaS-only hosting is sufficient to skip per-app LICENSE files** — the four web apps need none. **But the project does NOT distribute SaaS-only:** the published **VS Code `.vsix` triggers §4 and is missing NOTICE** (the one in-scope fix), and PyPI/Docker/Tauri are additional §4-triggered Object-form channels that likely miss LICENSE/NOTICE (out of scope, flagged). **Recommendation:** add `packages/vscode/NOTICE` now; hand PyPI/Docker/Tauri LICENSE+NOTICE hygiene to the Session B/C SBOM/packaging track.

---

## 3. ED-2 — Terms of Service gap analysis (research only)

**Source:** `websites/apps/marketing/src/app/terms/page.tsx` (243 lines, read in full). **DRAFT** — banner line 27 *"pending legal review (Phase 144) and is not yet in effect"*; `Terms_v2.0_DRAFT`.

**Sections present (verbatim, document order):** 01 Overview · 02 Licensing (Open-source software / Paid products and services / Restrictions) · 03 Data Sovereignty · 04 Payments & Refunds · 05 Support · 06 Liability & Warranties · Legal Contact. *No Definitions, no boilerplate/General, no dispute-resolution section.*

### Task-specified clauses

| Clause | Status | Note |
|---|---|---|
| **Effective date** | **ABSENT** | Only a draft-updated date + explicit "not yet in effect." |
| **Governing-law / jurisdiction / venue** | **ABSENT** | None anywhere. |
| **Liability cap** (tied to AS-IS block 209–216) | **ABSENT (cap); disclaimer present** | Lines 211–214 are verbatim MIT/Apache-style *total exclusion* ("IN NO EVENT SHALL … BE LIABLE …"), **not** a monetary/fees-paid cap. A blanket total exclusion risks being **unenforceable for paid services** under consumer law — a substantive gap, not just a missing number. |
| **Refund window** (line 161) | **PRESENT but VAGUE** | "Refund terms … will be stated at the time of purchase" — no concrete window/conditions. |
| **License lifecycle** for per-purchaser keys (109–113) | **PARTIAL** | Issuance + non-transfer present; **missing** expiry, renewal, non-payment effect, "active" definition, when auto-update stops, key deactivation, grace period, perpetual-vs-subscription, termination-for-cause. |
| **Standalone trademark-policy reference** (119–124) | **ABSENT (as a link)** | Inline TM language present; no link to a standalone Trademark Policy. Cross-links **DR-2**. |

### Other standard SaaS/EULA clauses

**ABSENT:** indemnification (either direction), liability **cap**, arbitration/class-action waiver, **DPA**, subprocessor-list reference, acceptable-use policy, DMCA/notice-and-takedown, export-control/sanctions (signed builds are export-relevant), assignment, severability, entire-agreement/integration, price-change notice, hosted-tier data-retention & deletion, force majeure, modification-of-terms process, third-party/OSS-components notice.
**PRESENT:** warranty-disclaimer scope (AS-IS covers "software and services"), privacy-policy reference (`/security#data-collection`). **DISCLAIMED (not committed):** SLA/uptime — support "Response Targets" are explicitly "goals, not contractual guarantees."

### Minimum-clause proposal (research draft — NOT legal text)

**Hard blockers — do not take payment until these exist:**
1. **Effective date & acceptance** — date Terms take force; purchase/use = acceptance of that version (replaces the "not yet in effect" banner).
2. **Governing law, jurisdiction & venue** — Magnetic Anomaly LLC's home jurisdiction + exclusive courts.
3. **Limitation of liability WITH a cap** — keep AS-IS, add an enforceable monetary cap (e.g., fees paid in prior 12 months) + indirect/consequential exclusion, carved to survive consumer-law limits. Fixes the unenforceable-blanket-exclusion risk.
4. **Refund policy with a concrete window** — replace the deferral with a definite window/conditions, consistent with Lemon Squeezy Merchant-of-Record obligations.
5. **License term, renewal, auto-update & termination lifecycle** — the missing half of §02.
6. **Indemnification** — at minimum a customer indemnity for misuse/IP claims from customer content.
7. **Acceptable-use / paid-build restrictions** — prohibited/unlawful uses; limits on reverse-engineering paid signed builds that don't conflict with the Apache-2.0 source rights already carved out in §02.

**Strongly recommended (attorney advises which are mandatory per target market):** modification-of-terms process · boilerplate cluster (assignment, severability, entire-agreement, waiver) · force majeure · export control & sanctions · dispute resolution (arbitration + class-waiver *or* explicit litigation — a deliberate choice, not silence) · DPA + subprocessor-list reference (gate on hosted-tier launch; list Lemon Squeezy + Resend + hosting) · hosted data-retention & deletion · price-change notice · **standalone Trademark Policy link** (coordinate with DR-2) · third-party/OSS-components notice · SLA (only if a paid tier promises uptime).

### ED-2 decision framing

> **Finalize the hard-blocker clauses + flip `Terms_v2.0_DRAFT` → in-effect, OR keep OSS-only until Terms are attorney-finalized?**

- **Option A — Finalize + flip:** required before enabling *any* Pro/Teams/Enterprise sale. Needs an attorney to add the 7 hard blockers.
- **Option B — Keep OSS-only (RECOMMENDED DEFAULT):** paid tiers are already "coming soon / not yet on sale" (line 152) and **no revenue depends on flipping the flag**, so there is no cost to waiting for proper legal review. This is Eric's recommended default.

---

## 4. ED-3 — Plausible + Resend subprocessor data-posture (research only)

### (a) Plausible Cloud posture (vendor docs, fetched 2026-07-19)

| Question | Finding |
|---|---|
| **EU-hosted?** | **Yes** — data processed/stored entirely in the EU; primary infra **Hetzner, Falkenstein, Germany**. "Data never leaves the EU." |
| **DPA?** | **Yes, auto-executed** — "in place automatically for all customers," no signature/request; use = acceptance. Controller = customer, processor = Plausible. 48-hr breach notice. |
| **Sub-processors** | Data-touching (EU): **Hetzner** (DE, hosting), **UpCloud** (FI, DB), **Bunny** (SI, CDN/DNS). Payments **Paddle**; transactional email **Postmark** (tracking disabled). |
| **Cookieless?** | **Yes** — "no cookies, browser cache or local storage," "no persistent identifiers." |
| **IP handling** | Raw IPs **never stored**; daily hash `hash(daily_salt + domain + ip + UA)`, **salt rotated/deleted every 24 h**. |
| **Cross-site/device tracking?** | **No** — "isolated to a single day, a single website and a single device." |
| **PII?** | **No** — aggregate only. |
| **GDPR/CCPA/PECR + no-banner basis** | Positioned compliant with all three; no consent banner needed because it sets no cookies and stores no personal data / persistent identifiers (no PECR/ePrivacy consent trigger). |

**The new `pa-<id>.js` script format** (the site uses this, not legacy `script.js`+`data-domain`): the `<id>` is a **per-site identifier resolved server-side** in the Plausible dashboard; there is **no `data-domain` attribute** and no client-side linking config. Install settings live with the site record. Options go to `plausible.init({...})` (`customProperties`, `endpoint`, `fileDownloads`, etc.). **The new format cannot send stats to multiple dashboards simultaneously** (legacy script is required for that). **Privacy-posture impact vs legacy: none** — same cookieless/IP-hash/no-PII/no-cross-site collection endpoint. `plausible.io/docs/data-policy` 404s; canonical is `plausible.io/data-policy`.

### (b) Resend posture (support bug-report email subprocessor)

**US-based, AWS-hosted GDPR Art. 28 processor.** Receives the **full bug-report email payload** — reporter email (as `reply_to`), subject/HTML body, and the **full diagnostics report as a base64 JSON attachment**. Data stored in the **United States** (AWS; DB on PlanetScale/Supabase). Public subprocessor list (`resend.com/legal/subprocessors`, 20+ named, all USA). Click-through/downloadable **DPA with SCCs** (`resend.com/legal/dpa`) + **EU-US Data Privacy Framework** certification. → a disclosable Art. 28 subprocessor, but note **US data residency** and identifiable email/message content (contrast Plausible's EU/anonymous posture).

### (c) Code verification (read-only)

**Cross-site linking VERDICT: NO** (verifier-confirmed high). Each app injects Plausible once, inline in its own `layout.tsx`, with a **distinct** `pa-<id>.js` id and an **argument-less** `plausible.init()` (so `plausible.o={}` — no domain, no linked list):

| App | File:line | Script id |
|---|---|---|
| payments | `layout.tsx:39` | `pa-5z91JAc5U5PsKGy3Vw7kJ.js` |
| docs | `layout.tsx:39` | `pa-3CWngGnNeUfIgUQ7wL2mV.js` |
| support | `layout.tsx:39` | `pa-l4-40TTsH65-qynGLddpJ.js` |
| marketing | `layout.tsx:87` | `pa-EyiWunLuXsVDCxYAfsQ6-.js` |

Grep across all four `src` trees for `data-domain` / `data-linked-domains` / `data-linked` / `linkedDomains` → **zero matches**. No shared analytics component (`packages/ui` has zero Plausible refs), no env/config var. Four separate site IDs, nothing joining them. *(Caveat: cross-domain linking is also a server-side dashboard setting invisible to the repo; "NO" means nothing in code configures it, and four distinct IDs strongly imply separate/unlinked properties — the account-side config should be spot-checked by Eric.)*

**Resend disclosure VERDICT: NO** (verifier-confirmed high). Resend is a genuine subprocessor (`support/api/bug-report/route.ts` → `api.resend.com/emails`). The only "Processor" named in any legal page is **Lemon Squeezy** (`terms:154-155`, `security:282`). There is **no dedicated privacy/DPA page** beyond the merged Privacy Policy in `security/page.tsx`, and it lists no subprocessors. Every other "resend" hit is the English verb ("we'll resend your key"). **→ genuine undisclosed-subprocessor gap:** user-supplied bug-report content leaves to a third party (US) with no disclosure.

### (c-fix) Security-page rewording — LICENSE-NEUTRAL FIX-NOW

`security/page.tsx` §02 "Telemetry & Analytics" asserts, unqualified, **"Usage Analytics — DISABLED / NONE"** (lines 94–95) and lists **"Telemetry / Usage Stats"** as *Not Collected* (line 251) — **misleading to a website visitor, because the marketing site itself runs Plausible.** For the **desktop product / `prep` daemon** the claims are literally true (phones home to nothing; corroborated by the Network Isolation section, lines 108–129). The single load-bearing inaccuracy is the word **"Usage Analytics"** (Plausible *is* website usage analytics); "Crash Reporting" and "Behavioral Tracking" stay true for both (Plausible does neither). Proposed **scoped rewording** (Eric to apply — this session is read-only):

- **Line 89 header:** `02. Telemetry & Analytics` → **`02. Product Telemetry & Analytics`**
- **Line 94 row label:** `Usage Analytics` → **`In-App Usage Analytics`**
- **After line 105 (before `</section>`), insert a clarifier:** *"These guarantees describe the SourcePrep desktop app and the local `prep` daemon, which ship no telemetry, crash reporting, or behavioral tracking. This marketing website uses Plausible — a cookieless, privacy-friendly analytics service that records only anonymous, aggregate page views. No cookies, no cross-site tracking, no personal profiles."*
- **Line 251 Not-Collected item:** `Telemetry / Usage Stats` → **`Product Telemetry / Usage Stats`**

This corrects a marketing-accuracy issue (website-vs-product scope) and touches no license terms/obligations/behavior → **safe for the fix-now batch.** The **Resend non-disclosure** is a content/legal decision, not a one-liner — it stays in the ED-3 docket below.

### (d) ED-3 decision framing (4 options from the audit)

> **How to reconcile Plausible-on-all-surfaces + the "Not Collected" claims + the undisclosed Resend subprocessor?**

- **(a) Publish a minimal disclosure, no cookie banner — RECOMMENDED DEFAULT.** Add a one-paragraph "Website Analytics" subsection (Plausible: EU-hosted, cookieless, no-PII, auto-DPA — no consent banner required) + a one-line Resend subprocessor disclosure ("bug reports you submit are emailed via Resend, a US email processor, under an SCC/DPF-backed DPA"), and apply the §4c security-page rewording. Lowest cost; Plausible's posture makes honesty cheap.
- **(b) Self-host Plausible** — removes the third-party subprocessor for analytics but adds ops burden; disclosure still simplest.
- **(c) Switch analytics provider** — no clear benefit over (a) given Plausible's already-strong posture.
- **(d) Remove Plausible entirely** — makes the "Usage Analytics: NONE" claim literally true site-wide, at the cost of losing analytics. Only warranted if Eric wants zero third-party JS.

*(Draft disclosure paragraphs are facts-assembled in §4a/§4b above; final publication is Eric + attorney — not done here.)*

---

## Appendix — verification ledger & dogfooding note

**Adversarial verifier verdicts (4):**
1. *SaaS ≠ §4 conveyance* → **HOLDS, high.** Refinement: client-bundle §4 duty binds only for embedded *third-party* Apache code; §4(c) never applies to a minified Object bundle.
2. *Resend undisclosed AND no cross-site linking* → **HOLDS, high** (both sub-claims independently re-grepped).
3. *Channel inventory complete (vsix + mirror only)* → **DOES NOT HOLD, high** — found PyPI/GHCR/Tauri channels + `packages/vscode/NOTICE` gap + `engine/pyproject.toml` missing license field. **This is why the inventory in §2c is broader than the handoff's two named channels.**
4. *Trademark = clean suggestive/low-risk* → **DOES NOT HOLD, moderate** — corrected to **borderline / MODERATE** refusal risk (Gould/Tower-Tech congruity + the applicant's own descriptive tagline). §1c reflects the corrected rating.

**Dogfooding (SourcePrep MCP):** `prep` (Research Analyst role) returned only planning/methodology docs — nothing relevant to trademark law, Apache license text, Terms clauses, or vendor privacy posture. **Expected but worth noting:** legal text, license files, and third-party web-marketing copy are outside the code graph's strength, and there is no legal/compliance scope or concept anchor for this material. All DR-2/DR-3/ED-2/ED-3 grounding came from `Read`/`Grep` + web fetch, not the graph. Product feedback: a "legal/compliance" scope (LICENSE, NOTICE, CHARTER, terms/security pages, subprocessor config) would make this class of audit graph-assisted rather than grep-only.

**STOP — surfaced to Eric.** All four sections written; every decision framed with options + a recommended default. **No legal act performed** — no trademark application, no Terms flip, no published privacy policy; those remain in the *Legal Acts* list above (Eric + attorney). The license-neutral fix-now items (security-page rewording, `packages/vscode/NOTICE`, trademark-wording harmonization, footer disclosure) **have since been applied locally** at Eric's direction — see *Implementation status* above; still local-only, `[deploy]`-gated.
