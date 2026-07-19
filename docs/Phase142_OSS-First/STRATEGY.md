# Phase 142 — Strategy

> The decision framework, the four paths considered, the license choice,
> the positioning, and the tier-boundary architecture.

## The constraints we are optimizing under

| Constraint | Implication |
|---|---|
| Solo developer | Headcount = 1. Every hour spent on marketing is an hour not building. |
| No VC | Cannot subsidize free tier, cannot afford a sales team, cannot lose money. |
| No advertising budget | Demand must be earned via organic distribution (OSS + content). |
| Product still maturing | Polish is not the differentiator yet — *idea fit* is. |
| Eric prefers acqui-hire / role-landing over cash-cow gamble | The objective function is **optionality + a credible portfolio piece**, not MRR. |
| AI dev tool category is over-saturated with closed-source competition | Trust differentiation matters more than feature differentiation. |
| Code-intel acquisitions are happening **right now** (see RESEARCH.md) | Timing window is open. |

## The four paths we considered

| Path | Setup | Time-to-money | Acqui-hire odds | Job-landing odds | Burnout risk |
|---|---|---|---|---|---|
| **A. Closed indie SaaS** | Current `DISTRIBUTION_AND_REVENUE_PLAN.md` baseline | 3–6 mo to first dollars | ~0% | Low (private code isn't a portfolio) | High |
| **B. Open-core (AGPL + Pro)** | Warp model | 6–12 mo | Low (AGPL friction) | Medium | Medium |
| **C. OSS-first, optimize for acqui-hire** | Apache 2.0, no paid tier yet | $0 directly; possibly $X00k–$1M acqui-hire or $300–600k IC offer | **High** for our category | **High** | Low |
| **D. Hybrid: start C, keep B as fallback** | Apache 2.0 today, Pro tier remains specced but deferred 6 mo | Optionality preserved | High | High | Low |

**Selected: Path D.**

### Why not A (status quo, closed Tauri)

The category turned. In 2026, a closed-source AI tool that ingests
the user's entire codebase, computes embeddings, and routes to cloud
LLMs is fighting against `Cody`, `Continue`, `Aider`, `Tabby`, and a
dozen others that already ship under permissive licenses. Trust
became table stakes. A solo developer with no marketing budget cannot
overcome that headwind without burning a year of runway they don't
have.

### Why not B (open-core with AGPL today)

AGPL is **acquisition-hostile.** Every acqui-hire target in
RESEARCH.md was MIT or Apache. Copyleft creates legal review pain at
the acquirer; that pain frequently kills deals. AGPL is also overkill
for our defensive posture — we are not currently large enough for
hyperscalers to clone-and-host us (the Elastic/MongoDB problem). The
AGPL-flip fallback is **foreclosed** by the permanent Apache-2.0 + DCO
decision (CHARTER commits to no source-available flip). The real
fallback is **revenue**, not relicense: build the hosted Teams/Enterprise
backend (the Obsidian-Sync analog) on top of the permanent Apache-2.0
engine.

### Why not C alone

Pure C bets everything on a single binary outcome (acquisition or
hire). Path D keeps the Pro tier specced and ready so that if the
acqui-hire window doesn't open, we can flip to open-core monetization
in month 6 without re-architecting. Optionality has no premium when
you're free; we should take it.

### Why D wins

- Apache 2.0 maximizes both adoption *and* acquirability
- OSS is free distribution — exactly what a no-ad-budget solo dev needs
- The Pro tier remains valid future revenue if no acqui-hire materializes
- The portfolio outcome (a polished OSS codebase intel tool with traction)
  is the most reliable floor — even if nothing else lands, Eric has a
  resume-defining project
- Reverses zero outcomes that the closed path would have

## License choice: Apache 2.0

| Option | Verdict |
|---|---|
| **Apache 2.0** | ✅ **Selected.** Maximally permissive; explicit patent grant (defensive). Acquirers prefer it. Used by Astral (acquired by OpenAI), Bun (acquired by Anthropic). |
| MIT | Equivalent permissive grant but no patent clause. Apache is strictly stronger for the same adoption ceiling. |
| AGPL | Defensive copyleft. Used by Warp (not for sale, defending against hyperscaler hosting). Wrong tool for our goal. |
| BSL (Business Source License) | Sentry/CockroachDB style — proprietary today, auto-OSS in N years. Adds friction with no acquirer benefit. |
| SSPL | Aggressive but not OSI-approved; ecosystem allergy. Wrong fit. |

**Apache 2.0 with a NOTICE file** is the call. We will need a NOTICE
section for any third-party attribution (including any gstack-derived
patterns — see [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) Part A).

## Positioning: complementary to gstack, not competitive

Garry Tan's `gstack` (104k ⭐, MIT, TypeScript) is **not a competitor
to SourcePrep**. It is a curated bundle of Claude Code slash commands
and subagents that role-play CEO / Designer / Eng Manager / etc. —
a *meta-layer on top of Claude Code's prompt and skill system*.

- **gstack** tells Claude **what role to play**.
- **SourcePrep** tells Claude **what's actually in the codebase**.

A gstack-orchestrated "Eng Manager" agent or "QA" agent gets
dramatically better when it can call `prep` / `prep_search` /
`prep_impact` for grounded structural context instead of guessing or
re-grepping the repo on every turn.

**Positioning statement (one line, for README and pitches):**

> SourcePrep is the structural codebase intelligence MCP server.
> Works standalone. Supercharges gstack.

**What this changes downstream:**

- The OSS README leads with "MCP server for codebase intelligence,"
  not "AI coding tool" (which would invite the wrong comparison)
- The benchmark/demo (Part E) explicitly includes a `gstack` setup so
  Garry's audience sees the integration immediately
- The acquirer pitch (ACQUIRER_MAP.md) frames SourcePrep as
  "infrastructure for the agent layer" — same thesis Anthropic used
  when buying Bun, OpenAI used when buying Astral

## Attribution to gstack (suspected lineage)

Eric recalls adapting *some* code/pattern from gstack. The most likely
candidate based on inspection:

- **The `role` parameter on `prep()`** (`ceo` / `design engineer` /
  `security` / `intern` / etc.) maps closely onto gstack's role
  taxonomy (CEO / Designer / Eng Manager / Release Manager / Doc
  Engineer / QA). This may be conceptual influence rather than
  copied code.

**Action in Part A:** before publishing, audit `src/prep/core/atlas/`
and any role-related code for direct gstack lineage. If any code or
prose is genuinely adapted, add MIT-compatible attribution in NOTICE
and a code-comment pointer. Apache 2.0 + MIT are compatible — no
license conflict, but credit is required.

## Open-core layering: the OSS / Pro boundary

The premise of Path D is that we don't have to draw a hard line on
day one — but we *do* need a defensible default so the OSS surface
is coherent and the Pro tier has obvious value when we monetize it.

**Default OSS surface (Apache 2.0):**

| Layer | Why OSS |
|---|---|
| Rust engine (`engine/crates/*`) — walker, parser, graph, chunking, sanitize, selfheal | Inspectability is the trust moat for an AI tool reading private code |
| Python core (`src/prep/core/*`) — indexer, embeddings, trace graph, atlas | Same — this is what people audit before letting it touch their repo |
| MCP server (`src/prep/mcp/`, `src/prep/mcp_direct.py`, `src/prep/mcp_tools.py`) | MCP is a public protocol; the value is the integration, not the wire format |
| CLI (`src/prep/cli.py`) | Useless without the engine; ships together |
| Daemon (`src/prep/server.py`) | Useless without the engine; ships together |
| Basic dashboard (`src/prep/dashboard/`) — single-user, local | Same OSS posture as GitLab CE |
| AGENTS.md generator (`src/prep/core/rules_generator.py`) | This is the integration point — the whole point is for client projects to use it |
| `packages/ui` component library | Already structured as a public npm package boundary |

**Default Pro surface (proprietary, ships in Pro Tauri app or hosted):**

| Layer | Why Pro |
|---|---|
| Polished Tauri desktop installer (`packages/vscode`, signed installers, auto-updates) | Convenience layer — matches existing DISTRIBUTION_AND_REVENUE_PLAN.md |
| Hosted indexes (for repos that don't fit on a laptop) | Real SaaS infra cost |
| Premium prompt assets (concept synthesis prompts, T1/T2/T3 calibration prompts) | Quality moat lives here — ship a baseline OSS version, keep tuned ones Pro |
| Team features — SSO, RBAC, org-shared indexes, audit logs, hosted dashboards | Classic enterprise add-on bucket |
| Cloud LLM orchestration as a service (vs the OSS algorithm) | Algorithm OSS; running infrastructure Pro |
| Customer support, SLA, on-prem deploy assistance | Service layer |

**Open question to resolve in scrutiny:** does the AIMD concurrency
controller go OSS as an algorithm + reference impl, with the *managed
service* version (auto-discovery against the user's BYOK quota) as Pro?
Probably yes, but lock it in. See [SCRUTINY.md](./SCRUTINY.md).

## Brand and naming consistency

Per Eric's standing preference
(`feedback_marketing_voice.md`, `project_brand_split.md`):

- **SourcePrep** = user-facing brand (UI, marketing, `sourceprep.io`, `.sourceprep/`)
- **prep** = code-level (CLI command name, Python imports, MCP tool names, `@prep/*` packages, `PREP_*` env vars)
- "CoDRAG" is the **stale codename** of the directory only — never user-facing

The public README, GitHub repo name, package metadata, and Show HN
post must all use **SourcePrep** as the headline brand and **prep**
as the technical/CLI name. No mention of "CoDRAG" anywhere public-facing.

## What is intentionally not decided yet

These get resolved during execution, not in the plan:

- **Repo name on GitHub** — **DECIDED 2026-07-18:** stay under the existing
  **`MagneticAnomaly`** org (do NOT stand up a separate `sourceprep` org).
  REPO_TOPOLOGY: workshop repo `MagneticAnomaly/SourcePrep-Private` (full
  history, never published) → storefront repo `MagneticAnomaly/SourcePrep`
  (curated fresh-initial-commit public mirror via `tools/build_public_mirror.py`).
  See IMPLEMENTATION_PLAN Part B + `DECISION_MEMO_2026-07-17.md` C2/D8.
- **Whether to squash history before going public** — examined in
  SCRUTINY.md; Eric's call.
- **Whether to split into multiple repos** (engine, server, dashboard)
  or monorepo from day one — defaulting to monorepo for simplicity;
  can split later.
- **Exact Pro tier pricing changes** — out of scope for Phase 142; the
  existing pricing in `DISTRIBUTION_AND_REVENUE_PLAN.md` stands.
- **Whether to incorporate Magnetic Anomaly LLC as the OSS copyright
  holder or use individual copyright** — Eric's call with legal
  consultation; recommend LLC for clean ownership chain.
