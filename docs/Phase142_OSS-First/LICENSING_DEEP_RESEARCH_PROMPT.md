# Licensing Deep-Research — Dedicated Max-Effort Starter Prompt

> **Purpose:** hand this to a fresh, maximum-effort AI research session whose
> SOLE task is to produce a defensible outbound-license recommendation for
> SourcePrep. It is self-contained (assume the AI has no prior context). The
> license choice is the single most load-bearing, IRREVERSIBLE decision in the
> OSS conversion, so this warrants a dedicated deep dive beyond the first pass.
> Everything below the line is the prompt.

---

You are a senior open-source strategy + IP analyst. Your ONLY task this session
is to produce a rigorous, decision-grade recommendation for which outbound
license a specific product should launch under. Spend maximum effort: do
extensive current web research (2023–2026), read primary sources (license texts,
OSI, company relicensing announcements, M&A filings, law-firm analyses), cite
every load-bearing claim with a URL + date, adversarially stress-test your own
conclusion, and flag every place a licensed attorney is required. This is
research, not legal advice — state that.

## The product and the decider (self-contained context)
- **Product:** "SourcePrep" (code name `prep`) — a **local-first** codebase-
  intelligence tool / MCP (Model Context Protocol) server that builds semantic +
  structural indexes of a codebase and serves bounded, source-cited context to
  AI coding agents. Stack: **Rust** engine (tree-sitter parsing, graph build),
  **Python** daemon/backend (FastAPI, embeddings via ONNX, LLM augmentation),
  **TypeScript/React** dashboard, and a **Tauri** desktop app. Code never leaves
  the user's machine (local-first, privacy-preserving).
- **Decider:** a **solo developer**, sole owner of a US single-member LLC
  (Magnetic Anomaly LLC, formed May 2026). **ZERO public users. Never released.**
  Nothing is published yet — there is **no installed base and no community**, so
  "switching-cost" and "rug-pull-after-adoption" concerns do not yet apply.
- **Sole author today**, so copyright is currently consolidated in one person
  (subject to an IP-assignment to the LLC that is being executed separately).
- **Monetization (open-core):** three layers —
  1. **OSS engine** (the thing you're licensing): full Rust engine + Python
     daemon + CLI + MCP server + local dashboard + VS Code extension + AGENTS.md
     generator — free, forever.
  2. **Paid "Pro" tier** = a **signed/notarized packaged desktop app** (native
     folder picker, runs the daemon for you, auto-updates). An OSS user CAN
     self-build the same app unsigned/no-auto-update for free — so Pro is a
     **convenience** product, not a capability gate. (Pricing/model is being
     decided separately.)
  3. **Future proprietary "Teams/Enterprise" hosted multi-tenant backend**
     (org-shared indexes, SSO, RBAC, audit) — currently 100% stub, and it will
     stay a **separate proprietary/closed codebase regardless of the engine
     license**. This is the intended real moat.
- **Strategic goal: OPTIONALITY.** Primary near-term outcome sought is a
  **senior individual-contributor role at a frontier AI lab or AI-dev-tools
  company**, using the OSS project as a credibility/portfolio artifact; an
  **acqui-hire is treated as low-probability lottery upside**; **open-core
  revenue is a fallback**. Runway (months of personal financial runway) is a
  variable — produce a recommendation that is explicit about how it changes with
  runway.
- **Crypto/export note (already resolved, for your awareness):** the app uses
  Ed25519 only for authentication/signatures, so it is outside US encryption
  export controls (EAR99) — the license choice has no export-control
  interaction. Trademark for "SourcePrep" is being handled separately and is not
  your concern.

## The decision you must make
Recommend ONE of: **Apache-2.0**, **AGPL-3.0**, or a **dual-license** structure
(e.g. AGPL + commercial), for the **public engine**. AND recommend whether to
run a **Contributor License Agreement (CLA)** or a **Developer Certificate of
Origin (DCO)** or neither — and why. Treat the CLA/DCO question as first-class:
prior analysis suggested the CLA decision may matter more than the license
letter itself (it governs future relicense/dual-license/M&A optionality).

## Sub-questions you must answer exhaustively (research each)
1. **Adoption/reach cost of each license.** Quantify AGPL's enterprise-adoption
   penalty (corporate bans — Google et al.), and how much that matters for a
   tool whose value to the IC/acqui-hire path is *uptake among engineers*.
2. **The rug-pull dynamic and the switching question.** With zero users, is
   there any cost to choosing the more restrictive license (AGPL) NOW vs later?
   Is "Apache now, AGPL later as a fallback" itself the rug-pull pattern that
   triggers forks? Analyze the real relicensing episodes and their outcomes:
   HashiCorp→BUSL/OpenTofu, Redis→SSPL/RSAL→back-to-AGPL (2025), Elastic→SSPL→
   AGPL, MongoDB SSPL, Terraform/OpenTofu, Valkey, Grafana's Apache→AGPL, Sentry
   (BSL/FSL), FSL/Functional Source License, and any 2024–2026 cases. What
   distinguishes a survivable tightening (Grafana, OSI-approved) from a
   fork-triggering one?
3. **M&A / acqui-hire diligence.** Does a permissive vs copyleft engine change
   acquisition friction for a solo dev with a CLA? Does a CLA fully neutralize
   AGPL's M&A friction? Cite diligence practice.
4. **Open-core interaction.** Given the moat is a SEPARATE proprietary hosted
   backend (not the engine), does AGPL's network-copyleft actually buy anti-clone
   protection here, or is it moot because the engine is a **local desktop tool
   with no network service** for AGPL §13 to attach to? Would a hyperscaler even
   want to clone a local-first engine? Does the paid *convenience installer*
   need any license protection (it doesn't gate capability)?
5. **Dual-licensing mechanics.** If dual (AGPL + commercial): what does it
   require (consolidated copyright / CLA), who actually runs this successfully
   at solo scale, what's the sales/enforcement overhead, and does it fit a solo
   dev whose primary goal is a job (not running a license-sales business)?
6. **CLA vs DCO in depth.** Contributor-trust cost of a CLA (some contributors
   refuse), vs the optionality it preserves. Is a DCO enough for a solo project
   that wants relicense optionality? What do comparable projects use? Provide a
   concrete recommendation + where to get a vetted CLA/DCO template (Apache ICLA,
   Harmony Agreements, DCO/developercertificate.org).
7. **Enforcement reality.** For a solo dev, is AGPL enforceable in practice
   (cost, willingness), or is its value purely *signaling*? Does that change the
   calculus?
8. **Patent + trademark clauses.** Compare Apache-2.0's explicit patent grant/
   termination and trademark handling vs (A)GPL-3.0's. Which better fits a
   solo dev who is separately weighing a defensive-publication/patent posture?
9. **Contributor & credibility signaling.** Which license reads better to (a)
   frontier-lab hiring managers, (b) potential contributors, (c) the HN/OSS
   community for a launch — as a signal of judgment and good faith?
10. **The permissive alternatives beyond Apache** (MIT, BSD-3, MPL-2.0,
    BSL/FSL): rule each in or out with reasons, so the final recommendation is
    against the full option space, not just Apache-vs-AGPL.

## Constraints / ground rules
- Publication is **irreversible**; the recommendation must be one Eric can
  commit to at launch (a "fallback to switch later" that reads as a rug-pull is
  a defect, not a plan).
- The hosted backend stays proprietary regardless — do not recommend relying on
  the engine license to protect it.
- Be decisive. Hedged "it depends" is only acceptable as an explicit decision
  table keyed to runway and primary-goal.

## Required deliverable format
1. **RECOMMENDATION** (one line): license + CLA/DCO.
2. **Decision table** keyed to scenario: rows = {primary goal: IC-role / acqui-
   hire / revenue} × {runway: <6mo / 6–12mo / 12mo+}; cell = recommended license.
3. **Rationale** — the 5–8 load-bearing arguments, each with cited sources.
4. **The CLA/DCO decision** with a concrete template pointer.
5. **Relicense-path / optionality analysis** — what each choice keeps open or
   forecloses, and the clean way to change later if needed.
6. **Adversarial section** — the strongest case AGAINST your recommendation, and
   why it loses.
7. **What would change the recommendation** + **where an attorney is required.**
8. **Full source list** (URL + date).

Do not stop until every sub-question above has been researched and addressed.
