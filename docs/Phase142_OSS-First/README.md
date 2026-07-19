# Phase 142 — OSS-First (Path D)

> **The bet:** SourcePrep ships under Apache 2.0 as MCP-native codebase
> intelligence infrastructure. OSS becomes the distribution channel a solo
> developer cannot otherwise afford. A paid Pro tier ($29 one-time) goes
> live once the Lemon Squeezy checkout, the Ed25519 license crypto, and
> code-signing land — it is not live at the first OSS launch; the primary
> near-term outcomes are (1) a senior IC role at a name-brand AI lab and/or
> (2) an acqui-hire conversation, with (3) hybrid open-core revenue as a
> fallback if neither lands.

## Why this phase exists

SourcePrep is being built by a single developer (Eric Bintner) with:

- **No VC runway.** Solo bootstrap; no investor pipeline.
- **No advertising budget.** Cannot buy demand against Cursor/Cognition.
- **Product still maturing.** Not "production-perfect" today.
- **A category that is being acquired *right now.*** Anthropic bought
  Bun (Dec 2025) for Claude Code infra. OpenAI bought Astral (Mar 2026)
  for Codex tooling. OpenAI acqui-hired Peter Steinberger / OpenClaw
  (Apr 2026) in **60 days from launch**. Cognition bought Windsurf.
- **A nearby OSS distribution channel with 100k+ developer reach:**
  Garry Tan's `gstack` (104k ⭐) — which is **complementary to
  SourcePrep, not competitive**.

The current authoritative business doc
(`docs/DISTRIBUTION_AND_REVENUE_PLAN.md`, last reviewed 2026-02-12)
assumes **closed-source Tauri desktop distribution** with Lemon Squeezy
licensing. Phase 142 does **not** invalidate that document — but it
inverts the ordering: OSS engine + MCP server ship first (and free),
the Pro Tauri app becomes the open-core monetization layer for users
who want the polished installer, hosted indexes, and team features.

See [STRATEGY.md](./STRATEGY.md) for the four paths considered and why
D won. See [RESEARCH.md](./RESEARCH.md) for the market evidence.

## Scope

In:

- **License decision and application** — Apache 2.0 for OSS surface
- **Repo hygiene** — secret audit, internal-doc scrub, attribution audit
  (specifically: any `gstack`-derived patterns get proper credit)
- **OSS surface decomposition** — what ships OSS vs what stays Pro
- **Public-repo readiness** — README, CONTRIBUTING, SECURITY, CI
- **`gstack` integration** — ship SourcePrep as a recommended MCP
  server in the gstack ecosystem; ideally land a PR upstream
- **One reproducible benchmark + demo video** — Claude Code with vs
  without SourcePrep on a hard codebase task
- **Show HN launch** — built around the benchmark, not the marketing site
- **2–3 technical blog posts** — trace graph, concept system, MCP
  architecture (these are the resume)
- **Direct outreach** — Anthropic / OpenAI / Cognition / Cursor /
  Sourcegraph DevRel and code-intel teams; senior IC role applications
- **Tier-boundary decisions** — which SourcePrep features stay Pro

Out:

- Building new product features (Phase 142 is distribution, not features)
- Replacing the existing DISTRIBUTION_AND_REVENUE_PLAN.md (that doc
  remains authoritative for the Pro tier; Phase 142 adds the OSS layer
  beneath it and updates the doc when complete)
- Pricing changes to the Pro tier (deferred to a later phase once
  OSS adoption data exists)
- Pursuing VC funding (Path D's premise is bootstrap-friendly)
- Mac App Store work (already deferred in the authoritative doc)
- Reset of internal phase numbering or history (history-rewrite tradeoff
  examined in [SCRUTINY.md](./SCRUTINY.md))

## Status

Hardened decisions (2026-07-17/18) are marked ✅. Execution items still open are marked [ ].

- [x] Strategy brainstormed — see STRATEGY.md
- [x] Market research synthesized — see RESEARCH.md
- [x] Implementation plan drafted — see IMPLEMENTATION_PLAN.md
- [x] Adversarial scrutiny drafted — see SCRUTINY.md
- [x] Acquirer + employer map drafted — see ACQUIRER_MAP.md
- [x] **License decided** — Apache-2.0 + DCO, permanent (no AGPL fallback). See `DECISION_MEMO_2026-07-17.md` Part 0 D1 + `LICENSING_RECOMMENDATION.md`.
- [x] **Pricing source-of-truth reconciled** — `OPEN_CORE_SPLIT.md` re-baselanced to the 2026-07-18 ladder ($0 / $29 one-time / $9 / $24); marked SoT.
- [x] **Repo topology decided** — stay under `MagneticAnomaly` org; workshop `SourcePrep-Private` → storefront `SourcePrep` (fresh-initial-commit mirror). See `REPO_TOPOLOGY.md`.
- [x] **History strategy decided (D8)** — fresh-initial-commit public mirror; no workshop history rewrite. See `SCRUTINY.md` §6 + `PRE_LAUNCH_BLOCKERS.md` §2.
- [x] **License artifact alignment** — root `LICENSE` swapped to verbatim Apache-2.0; pyproject + Cargo + 13 npm package.json metadata flipped; governance DRAFTs (NOTICE/CONTRIBUTING/CHARTER/COC/SECURITY) authored; public README badge + License section landed.
- [ ] **Scrutiny review complete** (Eric — adversarial pass on the plan)
- [ ] **Tier boundaries locked** (decide OSS vs Pro line per module)
- [ ] Pre-OSS hygiene complete (Part A — live-tree secrets removal via `tools/build_public_mirror.py` denylist gate)
- [ ] Repo restructured (Part B — public mirror tooling + first fresh-initial-commit)
- [ ] Public CONTRIBUTING/SECURITY out of DRAFT + `SECURITY.md` linked from public README (Part C)
- [ ] gstack integration shipped (Part D)
- [ ] Benchmark + demo video published (Part E)
- [ ] Show HN posted (Part F)
- [ ] Technical blog posts shipped (Part G)
- [ ] Direct outreach + applications sent (Part H)
- [ ] Post-launch retro + DISTRIBUTION_AND_REVENUE_PLAN.md update

## Files in this phase

| File | Purpose |
|---|---|
| `README.md` | This file — phase summary and status |
| `STRATEGY.md` | The four paths considered, why D won, license + positioning |
| `RESEARCH.md` | Market evidence — Warp, OpenClaw, Bun, Astral, gstack, citations |
| `RESEARCH_ROUND_2.md` | Second-pass research (acqui-hire vs IC, patent, trademark) |
| `IMPLEMENTATION_PLAN.md` | Ordered work (Parts A–H) with deliverables and acceptance criteria |
| `SCRUTINY.md` | Adversarial review — what kills this plan, what to do then |
| `ACQUIRER_MAP.md` | Specific targets, integration angles, outreach contacts |
| `DECISION_MEMO_2026-07-17.md` | Hardened decisions D1–D11 (license, patents, trademark, export, code-signing) |
| `LICENSING_RECOMMENDATION.md` | Decision-of-record: Apache-2.0 + DCO, permanent |
| `LICENSING_DEEP_RESEARCH_REPORT.md` | Verified research backing the licensing decision |
| `OPEN_CORE_SPLIT.md` | **Pricing source-of-truth** — the $0/$29/$9/$24 ladder + OSS/Pro tier boundary |
| `REPO_TOPOLOGY.md` | Workshop → storefront mirror model (stay under `MagneticAnomaly`) |
| `AI_WORK_TODO.md` | Master TODO — sequenced work streams (the AI execution queue) |
| `STARTER_PROMPT.md` | Durable session entry-point (one-line state + done-commits + next-work queue) |
| `AUDIT_2026-07-17.md` | 66-agent deep audit findings (contradictions + blockers) |
| `AUDIT_VERIFICATION_2026-07-17.md` | Verification of the audit findings |
| `LICENSE-AUDIT.md` | Dependency-license audit notes |
| `NOTICE.draft.md` | NOTICE file draft (copyright holder + third-party attributions) |
| `DOCS_OSS_READINESS_AUDIT_2026-07-18.md` | Docs-site OSS-readiness sweep |
| `MARKETING_OSS_READINESS_BRIEFING.md` | Marketing-site OSS-readiness briefing |

> Additional handoff/audit prompts (`HANDOFF_PROMPT_*.md`, `DOCS_OSS_HANDOFF_PROMPT_*.md`,
> `LEGAL_SECURITY_MESSAGE_AUDIT_HANDOFF_*.md`, `*.workflow.js`) are session artifacts, not
> durable plan docs.

## Relationship to existing docs

| Existing doc | Phase 142 relationship |
|---|---|
| `docs/DISTRIBUTION_AND_REVENUE_PLAN.md` (AUTHORITATIVE, 2026-02-12) | Phase 142 **layers OSS distribution underneath** the closed-source Tauri Pro app. No tier price changes. The authoritative doc gets a section-9 update at end of Phase 142 reflecting the open-core split. |
| `docs/PRODUCT_AND_BUSINESS_OVERVIEW.md` | Already frames SourcePrep as "local-first context engine" — Phase 142 is consistent. No edits required. |
| `docs/Phase10_Business_And_Competitive_Research/` | Historical research. Phase 142 supersedes any specific recommendations there that conflict with Path D. |
| `docs/Phase141 — silent swarm-cache truncation` (shipped 2026-05-28, recorded in `PARALLEL_LANES_2026-05-26.md`) | Unrelated. Phase 141 was engineering hardening; Phase 142 is strategic distribution. |

## Success criteria for this phase

Phase 142 is **complete** when:

1. SourcePrep core (engine, indexer, MCP server, CLI, daemon) is
   public on GitHub under Apache 2.0 with a credible README, working
   `git clone && setup` flow, CONTRIBUTING.md, and SECURITY.md.
2. One reproducible benchmark exists showing measurable Claude Code
   improvement with SourcePrep MCP enabled on a non-trivial codebase
   (≥10k LOC), with a recorded demo video.
3. A Show HN post and ≥2 technical blog posts are live.
4. SourcePrep is discoverable from the gstack ecosystem (PR landed,
   docs link, or recommended-MCP-server listing).
5. Direct outreach has been sent to ≥5 specific contacts across
   ≥3 named acquirer/employer targets in
   [ACQUIRER_MAP.md](./ACQUIRER_MAP.md).
6. The authoritative `DISTRIBUTION_AND_REVENUE_PLAN.md` has been
   updated to reflect the open-core layering.

Phase 142 is **successful** if, within 12 months of Show HN:

- ≥1 inbound conversation from a named acquirer target, **or**
- ≥1 senior IC offer at a named employer target, **or**
- ≥500 GitHub stars and a clear distribution flywheel (whichever
  triggers first — these are non-exclusive outcomes).

If none of the above occur within 12 months, the fallback is **revenue,
not relicense**: build the hosted Teams/Enterprise backend (the
Obsidian-Sync analog) on top of the permanent Apache-2.0 engine — the
AGPL-flip / Path-B-open-core relicense is foreclosed by the permanent
Apache-2.0 + DCO decision (see `STRATEGY.md` "Why not B" + `CHARTER.md`).
For the *pre-launch* "the benchmark doesn't show improvement" killer
scenario, see `SCRUTINY.md` §5.
