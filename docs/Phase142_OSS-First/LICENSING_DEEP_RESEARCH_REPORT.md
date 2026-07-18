# SourcePrep Licensing — Deep-Research Report (supporting rationale)

> **Status: SUPPORTING RESEARCH.** The authoritative decision is recorded in
> [`LICENSING_RECOMMENDATION.md`](LICENSING_RECOMMENDATION.md) (DECIDED,
> confirmed by Eric 2026-07-18: **Apache-2.0 + DCO, permanent, no AGPL
> fallback**). This report is the completed validation deep-research pass that
> the decision-of-record anticipated; it **augments the rationale and does not
> reopen the decision**. Where this report differs — it had left a break-glass
> Apache→AGPL fallback (§5) and a "CLA at first external contributor"
> checkpoint (§4) open — the decision of record governs: permanence with no
> relicense option is accepted deliberately as an anti-rug-pull trust signal.
> PRIVATE — Phase 143 keep-private bucket.
>
> **Research prompt:** `LICENSING_DEEP_RESEARCH_PROMPT.md` · **Research dates:** 2026-07-17/18
> **Method:** Two-round multi-agent deep research. Round 1: 5 search angles → 23 sources fetched → 112 claims extracted → top 25 adversarially verified by 3-vote refutation panels (23 confirmed, 2 refuted). Round 2 (gap-fill on sub-questions 7, 8, 9, 10, the remaining Q2 episodes, and DCO-optionality): 6 research agents → 30 central claims, each adversarially verified by a dedicated source-fidelity/factual-accuracy/currency verifier (30 confirmed, several with precision corrections incorporated below). All primary policy pages (Google, GitLab, OCV, license texts, repo LICENSE files) were fetched live on 2026-07-17.
>
> **⚠️ This is research synthesis, not legal advice.** Section 7 lists where a licensed attorney is required before acting.

---

## 1. Research conclusion

**License the public SourcePrep engine Apache-2.0. Use the DCO (Developer Certificate of Origin), not a CLA. Treat the license as permanent — no "tighten later" plan. Register the copyright within 3 months of first publication, and publish a short trademark policy alongside.**

This matches the decision of record. Confidence: high on Apache-2.0 (every evidence axis converged, zero contrary verified findings). Moderate-to-high on DCO over CLA (a genuine trade-off exists; §4 states exactly what DCO gives up — the decision of record accepts that trade explicitly).

---

## 2. Decision table — goal × runway

The table is deliberately near-uniform. That is the finding, not a hedge: the engine license is **not the lever** that any of the three goals or any runway length actually pulls. Revenue comes from the Pro convenience app and the separate proprietary hosted backend, both of which are unaffected by the engine's license; reach and credibility come from permissive adoption.

| | Runway < 6 mo | Runway 6–12 mo | Runway 12 mo+ |
|---|---|---|---|
| **Primary: IC role at frontier lab** | **Apache-2.0 + DCO.** Short runway makes reach urgent; AGPL would block casual install by engineers at Google (verified ban) and reads as friction at every OSPO. Ship fast, permissive. | **Apache-2.0 + DCO.** Same, with time to cultivate contributors — where DCO's low friction compounds. | **Apache-2.0 + DCO.** Same; time allows building the contributor/traction story that is the actual hiring signal. |
| **Primary: acqui-hire** | **Apache-2.0 + DCO.** Permissive is the verified low-friction diligence category; copyleft is the flagged one. Sole-author + DCO sign-off chain is clean provenance. | **Apache-2.0 + DCO.** Same. | **Apache-2.0 + DCO.** Same. |
| **Primary: open-core revenue** | **Apache-2.0 + DCO** — *with a pre-launch checkpoint:* if the **engine itself** (not the separate backend) had to become the monetized, capability-gated artifact, that would have been the one scenario where **AGPL + CLA dual-license** was the coherent alternative — and it had to be chosen **before** first publication, never after. (Decision of record: not taken.) | **Apache-2.0 + DCO.** Same checkpoint logic; the planned moat (hosted backend) has time to materialize, making the pivot less likely. | **Apache-2.0 + DCO.** The funnel argument dominates: a permissive engine maximizes the top of the Pro/Teams funnel. |

Runway changes *sequencing* (how soon Pro and the hosted backend must ship), not the engine license. The only cell variant is a strategy pivot (engine-as-product), not a runway effect.

---

## 3. Load-bearing rationale (verified)

Each argument below survived adversarial verification; refuted claims were discarded (§8 lists the two).

**R1 — AGPL forecloses the exact audience the primary goal targets.**
Google's live policy (fetched 2026-07-17, last updated 2025-06-10): AGPL code "MUST NOT be used at Google," and — decisive for a *developer tool* — "Do not install AGPL-licensed programs on your workstation, Google-issued laptop, or Google-issued phone without explicit authorization from the Open Source Programs Office." An AGPL SourcePrep cannot be casually adopted by engineers at at least one frontier lab; the IC-role strategy is *uptake among engineers*. MIT/BSD/Apache-2.0 all sit in Google's same freely-usable "notice" tier, so no permissive license beats Apache here.
Sources: [opensource.google AGPL policy](https://opensource.google/documentation/reference/using/agpl-policy); [Google third-party licenses](https://opensource.google/documentation/reference/thirdparty/licenses).

**R2 — AGPL's claimed benefit is architecturally moot for this product.**
AGPLv3 §13's remote-network clause triggers only where the software **has been modified** (license text: "if you modify the Program…"; Red Hat counsel Kaufman: unmodified deployments "simply do not trigger Section 13"; independently corroborated by Kyle Mitchell's clause-by-clause reading). SourcePrep's engine is a local desktop tool with no network service for §13 to attach to, and the real moat — the hosted Teams/Enterprise backend — stays proprietary regardless of the engine license (ground rule). The realistic integration path for third parties is the MCP protocol boundary (separate process), which even copyleft treats as arm's length. AGPL would therefore impose R1's adoption cost while buying approximately nothing.
Sources: [AGPLv3 text](https://www.gnu.org/licenses/agpl-3.0.en.html); [Kaufman, opensource.com](https://opensource.com/article/17/1/providing-corresponding-source-agplv3-license); [Mitchell, "Reading AGPL"](https://writing.kemitchell.com/2021/01/24/Reading-AGPL.html).

**R3 — Copyleft is the flagged category in M&A/acqui-hire diligence; permissive is the clean one.**
2026 law-firm practice notes (Morgan Lewis 2026-06; Morse 2026-04) treat copyleft mixed with proprietary code as able to "taint" it and "diminish the commercial value almost immediately," with AGPL under heightened scrutiny specifically for its deployment trigger; corroborated by Black Duck audit data (OSS in ~100% of deals, license conflicts in 94%). Nuance carried from verification: no court has ever ordered proprietary code open-sourced — the friction is acquirer perception and valuation, which is precisely what matters in an acqui-hire.
Sources: [Morgan Lewis](https://www.morganlewis.com/blogs/sourcingatmorganlewis/2026/06/open-source-software-common-areas-of-inquiry-in-m-and-a-due-diligence); [Morse](https://www.morse.law/news/open-source-issues/).

**R4 — The rug-pull direction is tightening-after-adoption; a permissive launch has no rug-pull exposure.**
Verified episode record: Elastic's 2021 Apache→SSPL move produced AWS's OpenSearch (LF-governed, never folded back even after Elastic added AGPL in 2024); Redis's 2024 BSD→RSAL/SSPL move produced Valkey (Linux-Foundation-backed, launched within days; AWS/Google/Oracle); Redis's 2025 AGPL return was widely judged "too late" (Percona: 83% of large enterprises adopted/exploring Valkey). HashiCorp's 2023 MPL→BUSL move produced OpenTofu (LF, MPL-2.0, production releases through Dec 2025) and Terraform remains BUSL with IBM as licensor after the Feb 2025 $6.4B close — at $35/share vs. an $80 IPO price, with RedMonk finding HashiCorp "struggled and seen their valuations drop post-license change" and no revenue-growth benefit from relicensing across MongoDB/Elastic/HashiCorp/Confluent. With **zero users**, choosing Apache now costs nothing and forecloses nothing a fork could punish; every documented harm came from *tightening after adoption*.
Sources: [InfoQ Elastic-AGPL](https://www.infoq.com/news/2024/09/elastic-open-source-agpl/); [InfoQ Redis-AGPL](https://www.infoq.com/news/2025/05/redis-agpl-license/); [LF Valkey launch](https://www.linuxfoundation.org/press/linux-foundation-launches-open-source-valkey-community); [LF OpenTofu](https://www.linuxfoundation.org/press/announcing-opentofu); [Terraform LICENSE (IBM, BUSL 1.1)](https://github.com/hashicorp/terraform/blob/main/LICENSE); [IBM close](https://newsroom.ibm.com/2025-02-27-ibm-completes-acquisition-of-hashicorp,-creates-comprehensive,-end-to-end-hybrid-cloud-platform); [RedMonk](https://redmonk.com/rstephens/2024/08/26/software-licensing-changes-and-their-impact-on-financial-outcomes/).

**R5 — The entire comparable cohort is permissive; AGPL is absent; the ecosystem norm *is* the signal.**
Verified census (GitHub license API / LICENSE files, 2026-07-17): Continue, Aider, Cline, Roo Code, and Goose (originated by Block, now Agentic AI Foundation) are **all Apache-2.0**. OpenHands and SWE-agent are MIT-family; tree-sitter is MIT; ripgrep MIT/Unlicense. The official MCP project (originated by Anthropic, now LF-governed) is MIT with the servers repo transitioning to Apache-2.0. The only copyleft comparable is Zed (GPL-3.0-or-later, VC-funded product company). Zero AGPL exists anywhere in the cohort. The one license-drama case ran permissive→**closed** (Sourcegraph's Cody to a private repo, Aug 2025), not permissive→copyleft. Launch-reception evidence matches: AGPL choices become the HN discussion itself (Oct 2023 front-page "AGPL is a non-starter" thread), while permissive launches draw zero license commentary (Plandex v2 Show HN, Apr 2025). For hiring: Anthropic's careers page tells candidates to put open-source work at the top of the resume; no evidence surfaced that the license letter itself is screened — the license matters *instrumentally*, through the adoption and contributor traction it enables.
Sources: [Continue license API](https://api.github.com/repos/continuedev/continue/license) (and per-repo equivalents); [MCP servers LICENSE](https://github.com/modelcontextprotocol/servers/blob/main/LICENSE); [Zed README](https://github.com/zed-industries/zed/blob/main/README.md); [cody-public-snapshot](https://github.com/sourcegraph/cody-public-snapshot); [HN AGPL thread](https://news.ycombinator.com/item?id=37903520); [Anthropic careers](https://www.anthropic.com/careers); [GitHub Open Source Survey](https://opensourcesurvey.org/2017/) (license = most important project documentation: 64% for use, 67% for contribution).

**R6 — AGPL enforcement is not a real capability for a solo LLC; its value would be pure signaling.**
Verified record: the best-documented solo AGPL enforcement (raymii.org, 2020) ended with the violator shutting down, never complying. SFC v. Vizio — the best-resourced US effort — filed 2021, reaches a jury trial only in Aug 2026, and seeks source disclosure, not money. Hellwig v. VMware died on German evidentiary-proof grounds after ~4 years with no GPL merits ruling. The lone significant money judgment (Entr'ouvert v. Orange, €860k, Paris Court of Appeal, Feb 2024) took ~13 years and a Cour de cassation round-trip. In the US, 17 U.S.C. §412 bars statutory damages and attorney's fees without timely registration, making contingency representation effectively unavailable and self-funded suits ($250k+) economically irrational. A solo developer choosing AGPL buys deterrence-by-reputation only — and R1 shows the price of that signaling.
Sources: [raymii.org](https://raymii.org/s/blog/I_enforced_the_AGPL_on_my_code_heres_how_it_went.html); [Baker Botts on SFC v. Vizio](https://www.bakerbotts.com/thought-leadership/publications/2026/may/when-consumers-enforce-open-source); [SFC on Hellwig](https://sfconservancy.org/news/2019/apr/02/vmware-no-appeal/); [DLA Piper on Entr'ouvert](https://www.dlapiper.com/en/insights/publications/2024/03/wakeup-call-for-open-source-users-french-court-awards-damages-for-gpl-violations); [17 U.S.C. §412](https://www.law.cornell.edu/uscode/text/17/412).
*Actionable rider:* register the copyright within 3 months of first publication — it cheaply preserves statutory-damages/fees optionality (and since 2020 the CASE Act small-claims board can award capped damages regardless).

**R7 — Apache-2.0's patent and trademark clauses fit a solo defensive posture better than MIT or (A)GPLv3.**
Apache-2.0 §3: express, irrevocable-except-as-stated patent grant from every contributor with *narrow* defensive termination (patent-suit aggressors lose only the patent license). §6: trademark permission withheld by default — the "SourcePrep" brand stays with the LLC without extra license text (a separate trademark policy is still advisable; §6 doesn't create trademark rights). GPLv3/AGPLv3 §11 has a comparable grant but blunter machinery (a patent suit is a license-wide breach via §10). MIT/BSD have **no** patent language — OSI's Dec 2025 analysis confirms the implied-license question "has not ever been resolved in court" — and the 2017 React BSD+Patents episode shows nonstandard patent terms destroying adoption until Facebook fled to plain MIT. Rust's own ecosystem convention ("MIT OR Apache-2.0", per the official API guidelines) exists precisely because "the Apache license includes important protection against patent aggression."
Sources: [Apache-2.0 text](https://www.apache.org/licenses/LICENSE-2.0); [GPLv3 text](https://www.gnu.org/licenses/gpl-3.0.en.html); [OSI patent analysis (McCoy Smith)](https://opensource.org/blog/patents-and-open-source-understanding-the-risks-and-available-solutions-2); [Facebook React relicense](https://engineering.fb.com/2017/09/22/open-source/relicensing-react-jest-flow-and-immutable-js/); [Rust API guidelines C-PERMISSIVE](https://rust-lang.github.io/api-guidelines/necessities.html).

**R8 — Open-core practice validates the permissive-core + DCO shape.**
GitLab — the canonical open-core precedent — requires only the DCO for its MIT-licensed core and reserves CLAs for its proprietary `ee/` tier (policy verified live 2026-07-17); the split-by-tier maps exactly onto SourcePrep (DCO for the engine; a CLA only if the proprietary backend ever accepts contributions). Open Core Ventures, the VC firm that professionally builds open-core companies, recommends a permissive core, recommends DCO over CLA (CLAs "discourage casual or first-time contributors"), and asserts competitive copying of open-source code has never in their observation killed a startup — "Startups die because no one cares enough about them" — with no counterexample found under adversarial check (documented clone targets Elastic/MongoDB/Redis/Confluent/Neo4j all survived; RethinkDB's postmortem blames market, not copying). Caveat carried: OCV is a single VC with a declared permissive thesis.
Sources: [GitLab DCO/CLA policy](https://about.gitlab.com/community/contribute/dco-cla/); [OCV licensing handbook](https://handbook.opencoreventures.com/startup-manual/fundamentals/licensing-and-distribution); [OCV "AGPL is a non-starter"](https://www.opencoreventures.com/blog/agpl-license-is-a-non-starter-for-most-companies).

---

## 4. The CLA/DCO analysis

**Research recommendation (adopted by the decision of record): DCO, from the first public commit, with sign-off enforced (`git commit -s` + the GitHub DCO check). No CLA for the engine. If the proprietary backend ever accepts outside contributions, use a CLA there (GitLab pattern).**

This was the closest call in the analysis, so here is the full trade, stated honestly:

**What the DCO gives you:** a per-commit provenance record (who asserts the right to submit what — exactly what M&A diligence wants to see), near-zero contributor friction (verified trust cost of CLAs: SFC calls them "dangerous to open source rights"; GitLab publicly dropped its CLA to remove friction; Ben Balter's practitioner analysis; OCV's recommendation), and alignment with the norms of the cohort SourcePrep will be benchmarked against.

**What the DCO does *not* give you (verified round-2 finding):** unilateral relicense power over third-party contributions. The theory that Apache-2.0's §2 sublicense right + §5 inbound=outbound lets an owner relicense contributions without consent is **contested and unresolved** — every practitioner analysis fetched (Kate Downing; Kyle Mitchell; GitHub's opensource.guide; producingoss) frames relicensing under inbound=outbound as requiring contributor consent-hunting. The real-world no-CLA relicenses show the cost *and* the escape hatch: LLVM needed approval from all copyright holders with a remove-or-rewrite fallback for holdouts; VLC contacted 230+ developers over ~1 year and dropped ~25 modules over 13 unreachable/refusing devs. Note: **Grafana is not a counterexample** — its 2021 relicense announcement says it updated to an ASF-style CLA as part of the move.

**Why DCO still wins for SourcePrep:** (1) The engine stays Apache forever — under the decision of record, relicense power is not merely unneeded but *deliberately discarded* as a trust signal. (2) Eric is the sole author today; any residual consent-hunt exposure applies only to *future external* contributions, and for a young project git history makes remove-or-rewrite cheap (the LLVM/VLC fallback, at trivial scale). (3) The CLA's optionality benefit accrues mostly to dual-license businesses; SourcePrep's monetization deliberately doesn't run through the engine's license. (4) Adding a CLA later is mechanically possible and reputationally dangerous *only after* a volunteer community exists — Muse Group's post-hoc Audacity CLA (2021) drew overwhelming backlash and forks.

*(Superseded nuance:* this report originally proposed a "CLA checkpoint at first external contributor" in case a dual-license need emerged. The decision of record forecloses relicensing entirely, which makes that checkpoint moot — recorded here because the Audacity/GitLab evidence behind it remains the reason a post-hoc CLA must never be attempted.)*

**Templates (vetted, standard):**
- DCO text: [developercertificate.org](https://developercertificate.org/) (use verbatim; wire up the [DCO GitHub app](https://github.com/apps/dco) and require `Signed-off-by`).
- If a CLA is ever needed for the proprietary tier: [Apache ICLA/CCLA](https://www.apache.org/licenses/contributor-agreements.html) as the drafting baseline, or the [Harmony Agreements](https://www.harmonyagreements.org/) generator — **attorney review required before adoption** (§7).

---

## 5. Relicense-path / optionality analysis

*(Research analysis; the decision of record supersedes the fallback framing — see banner.)*

What each launch choice keeps open or forecloses:

- **Apache-2.0 + DCO (chosen).** Keeps open: everyone's right to use/embed/fork (that's the point); the LLC's own proprietary Pro/Teams layers (Apache imposes nothing on the author, and the moat is a separate codebase anyway). As pure research: a **Grafana-style Apache→AGPL tightening** was the one survivable-tightening pattern in the record — OSI-approved destination (AGPL, the only community-credible copyleft: Grafana chose it *because* OSI-approved; Elastic and Redis both *returned* via it), a permissive perimeter kept around SDKs/plugins, a deep user-side community, trademark strength, honest process, and (verified) a CLA regime in place. Under DCO that move requires contributor consent or remove-and-rewrite — friction that grows with the contributor base. **The decision of record deliberately forecloses this path** and converts the DCO's relicense-friction from a cost into a credibility feature: the "we will never take this back" signal is load-bearing. Note the asymmetry either way: **permissive→copyleft with community consent was survivable (Grafana); anything→non-OSI is the fork trigger (Elastic, Redis, HashiCorp).**
- **AGPL-3.0 at launch.** Forecloses R1's audience immediately, buys R2's ~nothing, and — verified — going copyleft→permissive later is trivial legally for a sole author but the *adoption* lost in the interim doesn't come back (first impressions on HN are single-shot; the Oct 2023 thread pattern). Also forecloses easy embedding of engine components by the very ecosystem projects (all Apache/MIT) whose adoption would constitute the credibility win. Ruled out.
- **Dual-license AGPL+commercial at launch.** Requires consolidated copyright (i.e., a CLA) from day one, an enforcement/sales function a solo job-seeking dev doesn't want to run (verified: dual-licensing's overhead is a sales-and-compliance business), and inherits both AGPL's adoption penalty and the CLA's trust cost. It is the right structure for a *license-sales company*; it is the wrong structure for a portfolio artifact. Ruled out.
- **"Apache now, AGPL later" as a stated plan.** A stated tightening intention is the rug-pull pattern read in advance; the spec's ground rule stands, and the decision of record goes further by renouncing the fallback entirely. Launch Apache as permanent.

**The convenience installer (Pro) needs no license protection:** it gates no capability by design; its defensibility is identity-bound (Apple/Microsoft signing + notarization + auto-update infrastructure tied to the LLC), which no fork can replicate by copying code. Keep the Pro packaging/signing config out of the OSS repo for hygiene, not protection.

---

## 6. Adversarial section — the strongest case against, and why it loses

**The strongest case for AGPL (steel-manned):** "AGPL is now the predominant license choice for commercial open-source companies (Meeker, 2023). A permissive engine lets Cursor, Windsurf, GitHub, or a hyperscaler embed SourcePrep's engine into their closed products tomorrow, capture the entire value, out-market a solo dev, and owe nothing — with Apache's patent grant sweetening the deal. You are the only contributor; the 'contributor-friction' argument for DCO/Apache protects contributors who don't exist yet. Choose AGPL now, while there are zero users to upset; every future user opts in knowingly, and Grafana proves AGPL products thrive."

**Why it loses, on the verified record:**
1. **The threat model is misaligned with the goal.** For the primary goal (IC-role credibility), a major player embedding the engine is a *win condition*, not a loss — the portfolio artifact's value is demonstrated uptake. The goals that embedding would threaten (engine-revenue capture) are third-priority and deliberately routed around the engine.
2. **AGPL wouldn't stop the realistic clone anyway.** The verified §13 analysis plus the MCP-protocol integration boundary means a competitor can either integrate at arm's length (no copyleft trigger) or rebuild the engine (tree-sitter + embeddings + graph is replicable by a funded team; the durable moat was never the code — it's the hosted backend, which stays proprietary regardless). OCV's adversarially-checked claim stands: no documented case of competitive copying killing a startup.
3. **The cost side is not symmetric.** AGPL's penalty is verified, immediate, and structural (Google's install ban; M&A red-flag practice; zero AGPL in the comparable cohort; HN reception risk). Its benefit for *this architecture* is approximately zero. An option with real costs and ~no benefits doesn't become attractive because its costs are prepaid.
4. **"Grafana proves AGPL works" is the wrong direction.** Grafana *arrived* at AGPL from Apache, after building a dominant community under permissive terms, with a company behind it, keeping a permissive perimeter — and (verified correction) with a CLA regime in place. It does not support launching a zero-user solo project there.

**The strongest case for a CLA (steel-manned):** "Zero users means zero backlash — adopt the Apache ICLA on day one and keep unilateral relicense/dual-license/M&A power forever. The DCO demonstrably does not preserve it (round-2 finding), and Audacity shows you can't add it later."
**Why it loses:** the optionality a CLA preserves is optionality the strategy has renounced (moat outside the engine; license permanent by decision); its verified trust cost lands exactly on the contributor-traction the primary goal needs; and sole-authorship plus the LLVM/VLC remove-or-rewrite fallback covers residual provenance needs while the project is young. Under the decision of record's explicit permanence, the CLA's one remaining benefit evaporates entirely.

---

## 7. What would change the analysis, and where an attorney is required

**Tripwires (for awareness — the decision is made; these are the conditions under which the *evidence base* would shift):**
1. **Pre-launch strategy pivot to engine-as-product** (capability-gated engine revenue instead of the separate hosted backend) — was the one scenario favoring AGPL + CLA dual-license; must be decided before first publication if ever revisited. (Decision of record: not taken.)
2. **Broad enterprise AGPL-policy relaxation** (watch `opensource.google` — the ban page last changed 2025-06-10) → weakens R1, though R2–R7 would still carry Apache.
3. **A funded competitor shipping the engine wholesale in a closed product** — under the decision of record this is absorbed as a win-condition/accepted risk (see §6.1–6.2), not a relicense trigger.

**Attorney required (before or at launch):**
- The **IP assignment** from Eric to Magnetic Anomaly LLC (in flight) — foundational; everything else assumes the LLC owns the code.
- **Whether Apache-2.0 §5 + §2 alone preserves any unilateral relicense right over external contributions** — verified as *contested and unresolved* among practitioners; do not rely on it without counsel (moot under permanence, relevant to understanding what the DCO does and doesn't do).
- **CLA drafting**, if the proprietary backend ever accepts outside contributions (Apache ICLA/Harmony as baseline, never verbatim adoption without review).
- **US copyright registration** mechanics and timing (§412's 3-month window — cheap, do it at launch).
- **Trademark** ("SourcePrep") — separate track; verified §6 nuance: Apache-2.0 withholds trademark permission but creates no trademark rights; registration + a short trademark policy do that work.
- **Repo license hygiene at conversion:** LICENSE + NOTICE files, SPDX headers, third-party license inventory across the Rust/Python/TS monorepo (the Phase 142 audit found the repo legally proprietary today with blockers — that cleanup is a precondition; see the decision of record's execution checklist).

**Optional refinement (not required):** publish the Rust crates dual **"MIT OR Apache-2.0"** if/when they go to crates.io, per the official Rust API guidelines (C-PERMISSIVE) — ecosystem-native, adds GPLv2 compatibility, keeps the Apache patent grant. Apache-2.0-only remains a defensible whole-repo default.

---

## 8. Discarded claims (failed adversarial verification — do not cite)

1. *"Grafana's relicense was executed via an Apache-modeled CLA adopted expressly to avoid license incompatibilities — evidence a CLA made the relicense executable."* Refuted 0-3 as stated. The narrower verified version: Grafana's announcement says it updated to an ASF-style CLA as part of the change; the mechanics for past contributions are not detailed.
2. *"Google's AGPL-ban rationale is procedural/engineering-cost, not legal risk (DiBona framing)."* Refuted 0-3.

---

## 9. Full source list

Primary policy pages and license texts (fetched live 2026-07-17 unless noted):

| Source | Date | Used for |
|---|---|---|
| [Google AGPL policy](https://opensource.google/documentation/reference/using/agpl-policy) | updated 2025-06-10 | R1 |
| [Google third-party licenses](https://opensource.google/documentation/reference/thirdparty/licenses) | living page | R1, Q10 |
| [Apache-2.0 license text](https://www.apache.org/licenses/LICENSE-2.0) | 2004-01 | R7, §4 |
| [GPLv3 text](https://www.gnu.org/licenses/gpl-3.0.en.html) / [AGPLv3 text](https://www.gnu.org/licenses/agpl-3.0.en.html) | 2007 | R2, R7 |
| [BSL 1.1 text (MariaDB)](https://mariadb.com/bsl11/) | living page | Q10 |
| [BSD-3-Clause (OSI)](https://opensource.org/license/BSD-3-clause) | living page | Q10 |
| [GitLab DCO/CLA policy](https://about.gitlab.com/community/contribute/dco-cla/) | living page | R8, §4 |
| [OCV licensing handbook](https://handbook.opencoreventures.com/startup-manual/fundamentals/licensing-and-distribution) | living page | R8 |
| [Terraform LICENSE](https://github.com/hashicorp/terraform/blob/main/LICENSE) | retrieved 2026-07-17 | R4 |
| [MCP servers LICENSE](https://github.com/modelcontextprotocol/servers/blob/main/LICENSE) | retrieved 2026-07-17 | R5 |
| [Zed README (license)](https://github.com/zed-industries/zed/blob/main/README.md) | retrieved 2026-07-17 | R5 |
| [LLVM Developer Policy (relicensing)](https://llvm.org/docs/DeveloperPolicy.html) | cutover 2024-06-01 | §4 |
| [developercertificate.org](https://developercertificate.org/) | — | §4 |
| [Apache contributor agreements](https://www.apache.org/licenses/contributor-agreements.html) / [Harmony](https://www.harmonyagreements.org/) | — | §4 |
| [17 U.S.C. §412 (Cornell LII)](https://www.law.cornell.edu/uscode/text/17/412) | statute | R6 |

Company announcements and case records:

| Source | Date | Used for |
|---|---|---|
| [Grafana relicensing Q&A (CEO)](https://grafana.com/blog/2021/04/20/qa-with-our-ceo-on-relicensing/) | 2021-04-20 | R4, §5 |
| [Grafana relicense announcement](https://grafana.com/blog/2021/04/20/grafana-loki-tempo-relicensing-to-agplv3/) | 2021-04-20 | §4 (CLA correction) |
| [Elastic "open source again"](https://www.elastic.co/blog/elasticsearch-is-open-source-again) | 2024-08 | R4, §5 |
| [Redis AGPL announcement](https://redis.io/blog/agplv3/) + [antirez](http://antirez.com/news/151) | 2025-05 | R4, §5 |
| [LF Valkey launch](https://www.linuxfoundation.org/press/linux-foundation-launches-open-source-valkey-community) | 2024-03-28 | R4 |
| [LF OpenTofu announcement](https://www.linuxfoundation.org/press/announcing-opentofu) | 2023-09-20 | R4 |
| [OpenTofu fork announcement](https://opentofu.org/blog/opentofu-announces-fork-of-terraform/) | 2023-09 | Q10 |
| [CNCF OpenTofu (Sandbox)](https://www.cncf.io/projects/opentofu/) | 2025-04-23 | Q2 |
| [IBM completes HashiCorp acquisition](https://newsroom.ibm.com/2025-02-27-ibm-completes-acquisition-of-hashicorp,-creates-comprehensive,-end-to-end-hybrid-cloud-platform) | 2025-02-27 | R4 |
| [Sentry "Fair Source"](https://blog.sentry.io/sentry-is-now-fair-source/) | 2024-08-06 | Q10 |
| [MongoDB SSPL FAQ](https://www.mongodb.com/legal/licensing/server-side-public-license/faq) | living page | Q10 |
| [Facebook React relicense](https://engineering.fb.com/2017/09/22/open-source/relicensing-react-jest-flow-and-immutable-js/) | 2017-09-22 | R7 |
| [SFC: no appeal in Hellwig v. VMware](https://sfconservancy.org/news/2019/apr/02/vmware-no-appeal/) | 2019-04-02 | R6 |
| [Baker Botts: SFC v. Vizio](https://www.bakerbotts.com/thought-leadership/publications/2026/may/when-consumers-enforce-open-source) | 2026-05 | R6 |
| [DLA Piper: Entr'ouvert v. Orange](https://www.dlapiper.com/en/insights/publications/2024/03/wakeup-call-for-open-source-users-french-court-awards-damages-for-gpl-violations) | 2024-03-05 | R6 |
| [raymii.org AGPL enforcement](https://raymii.org/s/blog/I_enforced_the_AGPL_on_my_code_heres_how_it_went.html) | 2020-10-20 | R6 |
| [Audacity CLA discussion](https://github.com/audacity/audacity/discussions/932) | 2021-05-25 | §4 |
| [VLC relicensing (LWN)](https://lwn.net/Articles/525718/) | 2012-11-21 | §4 |
| [Sourcegraph cody-public-snapshot](https://github.com/sourcegraph/cody-public-snapshot) | archived 2025-08-01 | R5 |

Practitioner/analyst commentary:

| Source | Date | Used for |
|---|---|---|
| [Morgan Lewis M&A OSS diligence](https://www.morganlewis.com/blogs/sourcingatmorganlewis/2026/06/open-source-software-common-areas-of-inquiry-in-m-and-a-due-diligence) | 2026-06-05 | R3 |
| [Morse open-source issues](https://www.morse.law/news/open-source-issues/) | 2026-04-21 | R3 |
| [Kaufman, opensource.com (AGPL §13)](https://opensource.com/article/17/1/providing-corresponding-source-agplv3-license) | 2017-01 | R2 |
| [Mitchell, "Reading AGPL"](https://writing.kemitchell.com/2021/01/24/Reading-AGPL.html) | 2021-01-24 | R2 |
| [Mitchell, "CLAs Are Not a Sham"](https://writing.kemitchell.com/2018/01/06/CLAs-Are-Not-a-Sham.html) | 2018-01-06 | §4 |
| [Downing, DCO vs contributor agreement](https://katedowninglaw.com/2019/02/15/should-i-use-a-developers-certificate-of-origin-or-a-contributor-agreement/) | 2019-02-15 | §4 |
| [GitHub opensource.guide (legal)](https://opensource.guide/legal/) | living page | §4 |
| [SFC, "Why Your Project Doesn't Need a CLA"](https://sfconservancy.org/blog/2014/jun/09/do-not-need-cla/) | 2014-06-09 | §4 |
| [Balter, "Why you probably shouldn't add a CLA"](https://ben.balter.com/2018/01/02/why-you-probably-shouldnt-add-a-cla-to-your-open-source-project/) | 2018-01-02 | §4 |
| [OSI blog: patents & open source (McCoy Smith)](https://opensource.org/blog/patents-and-open-source-understanding-the-risks-and-available-solutions-2) | 2025-12-04 | R7, Q10 |
| [Peterson, MIT patent grant argument](https://opensource.com/article/18/3/patent-grant-mit-license) | 2018-03-23 | R7 (counterweight) |
| [Rust API guidelines (C-PERMISSIVE)](https://rust-lang.github.io/api-guidelines/necessities.html) | living page | R7, §7 |
| [RedMonk: licensing changes & financial outcomes](https://redmonk.com/rstephens/2024/08/26/software-licensing-changes-and-their-impact-on-financial-outcomes/) | 2024-08-26 | R4 |
| [Meeker, "AGPL in the light of day"](https://heathermeeker.com/2023/10/13/agpl-in-the-light-of-day/) | 2023-10-13 | §6 (steel-man) |
| [OCV, "AGPL is a non-starter"](https://www.opencoreventures.com/blog/agpl-license-is-a-non-starter-for-most-companies) | 2023-10 | R8 |
| [InfoQ: Elastic returns to open source](https://www.infoq.com/news/2024/09/elastic-open-source-agpl/) | 2024-09 | R4 |
| [InfoQ: Redis returns via AGPL](https://www.infoq.com/news/2025/05/redis-agpl-license/) | 2025-05 | R4 |
| [The Register: Neo4j v. PureThink appeal](https://www.theregister.com/software/2025/02/27/adverse-appeals-court-ruling-could-kill-gpl-software-license/430527) | 2025-02-27 | R6 |
| [gpl-violations.org](https://gpl-violations.org/about/) | ~2006 | R6 |
| [GitHub Open Source Survey](https://opensourcesurvey.org/2017/) | 2017 | R5 |
| [HN: "AGPL is a non-starter" thread](https://news.ycombinator.com/item?id=37903520) | 2023-10-16 | R5 |
| [GlitchTip contribute docs](https://glitchtip.com/documentation/contribute/) | living page | Q2 |
| [Wikipedia: SSPL](https://en.wikipedia.org/wiki/Server_Side_Public_License) / [Wikipedia: CLA](https://en.wikipedia.org/wiki/Contributor_License_Agreement) | living pages | Q10, §4 |
