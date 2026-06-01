# Phase 142 — Research Synthesis

> Market evidence for Path D. The acqui-hire and OSS-distribution
> patterns that justify the strategy, with citations preserved so
> future sessions don't have to re-research.

## TL;DR

In the last 12 months, the AI-tooling acquisition market has visibly
shifted toward **buying small OSS dev infrastructure plays**, both
as full acquisitions and as solo-founder acqui-hires. The pattern is:

1. OSS-licensed project (MIT or Apache)
2. Lands inside the acquirer's product stack (Claude Code, Codex, etc.)
3. Gets used by acquirer's existing customers
4. Acquirer makes an offer (60–180 days from public launch in the fastest cases)

SourcePrep — MCP-native, codebase intelligence, currently closed — is
in the right category at the right moment. The only thing missing
is **visibility**, which OSS solves and a closed-source repo cannot.

## Key data points

### Warp (May 2026) — open-sourcing the client, keeping the SaaS

- **What:** Warp open-sourced the terminal client under AGPL.
- **Kept proprietary:** Oz (cloud agent orchestration), backend services.
- **Why (CEO Zach Lloyd, verbatim):**
  > "We do not have the resources to compete on price or massively
  > subsidize usage — we need to build our business by offering the
  > best possible product."
- **Model:** Open-core. Client OSS for trust + adoption; the value-add
  SaaS stays revenue-generating.
- **Why AGPL (not MIT/Apache):** Warp is *not for sale.* AGPL prevents
  hyperscaler hosting (the Elastic problem) — Warp is building a moat,
  not an acquirable property. **Wrong template for us.**

### Anthropic acquires Bun (December 2025)

- **What:** Anthropic acquired the Bun JavaScript runtime team.
- **Framing:** Infrastructure for Claude Code and future AI coding
  products.
- **License of Bun before acquisition:** MIT.
- **Why this matters for us:** SourcePrep is *also* infrastructure for
  Claude Code and AI coding agents. Same thesis. Same acquirer profile.

### OpenAI announces acquisition of Astral (March 2026)

- **What:** OpenAI acquires Astral — makers of `uv`, `ruff`, etc.
- **Framing:** Python tooling for the Codex ecosystem.
- **License of Astral tools:** Apache 2.0.
- **Why this matters for us:** A pure dev-tools acquisition with no
  end-user product. The acquirer wanted the *team and the tools as
  infrastructure*, not a customer base. SourcePrep is closer to Astral
  than to Cursor in profile.

### OpenAI acqui-hires Peter Steinberger / OpenClaw (April 2026)

- **What:** OpenAI acqui-hires the creator of OpenClaw, a personal AI
  agent project he built in **two months** as a solo developer.
- **License:** MIT. Steinberger's non-negotiable was that OpenClaw
  remain open-source under an independent foundation post-acqui-hire.
- **Speed:** Solo developer → acqui-hire offer in **60 days from
  public launch.** Microsoft (Satya Nadella personally) and Meta also
  reached out.
- **Why this matters for us:** This is *the* template. Solo dev, OSS
  from day one, builds the right thing at the right moment, gets
  pulled into a top-tier AI lab. Eric's situation is structurally
  identical except SourcePrep targets a more institutional category
  (code intel) than OpenClaw's consumer-ish agent demo.

### Cognition acquires Windsurf (2025)

- **What:** Cognition (Devin) acquires AI coding startup Windsurf,
  after Windsurf's earlier acquisition plan with another buyer
  collapsed.
- **Why this matters:** Demonstrates Cognition is an active acquirer
  in our space — they want IDE + code intel for the agent platform
  they're building.

### Cognition raises at $26B valuation (May 2026)

- **What:** $1B raise led by Founders Fund at a $26B valuation, up
  from $10.2B in late 2025.
- **Why this matters:** They have cash to deploy. Their thesis is
  full-stack AI software engineer; they need every layer of dev
  infrastructure under their roof.

### SpaceX / Cursor strategic deal (April 2026)

- **What:** SpaceX announces a strategic partnership with an option
  to acquire Cursor for $60B (or $10B partnership deal). Microsoft
  reportedly looked and passed.
- **Why this matters:** Validates that the category is at peak
  acquisition value *and* that Microsoft is shopping. Microsoft = GitHub
  Copilot — they may also be a SourcePrep acquirer or hirer.

## The competing OSS landscape (what we are entering)

| Tool | License | Note |
|---|---|---|
| **Aider** | Apache 2.0 | Terminal-based AI coding agent. Solo creator (Paul Gauthier). Active OSS community. |
| **Continue.dev** | Apache 2.0 | IDE-integrated AI agent. Funded by Y Combinator. Active. |
| **Cody / Sourcegraph Amp** | Apache 2.0 (Cody itself) | Sourcegraph open-sourced Cody for trust. Sourcegraph engine and enterprise features remain proprietary. Cody works without Sourcegraph but is "smarter" with it. |
| **Tabby** | Apache 2.0 | Self-hosted coding assistant. |
| **Void Editor** | Apache 2.0 | Open-source Cursor alternative. |
| **Greptile** (YC W24) | Closed source | Codebase Q&A via API. |
| **Qodo / Codium** | Mixed | Code verification platform; raised $70M (March 2026). |

**Sourcegraph's framing (from their Cody open-sourcing post):**
> "We never focused on monetizing individual developers — the
> economic opportunity is enterprise."

This is the most relevant business model template for SourcePrep:
free OSS for developers, enterprise dollars for the platform around it.

## The gstack ecosystem (positioning context)

Garry Tan (CEO, Y Combinator) ships a tightly-coupled OSS ecosystem
of Claude Code orchestration tools. **None of these compete with
SourcePrep directly** — they are at a different layer (skill /
role / prompt orchestration, not code intelligence).

| Repo | Stars | What it is |
|---|---|---|
| `garrytan/gstack` | 104k | 23 opinionated Claude Code slash commands / skills / subagents — CEO, Designer, Eng Manager, etc. MIT. |
| `garrytan/gbrain` | 19.7k | Garry's opinionated agent brain / memory config. |
| `garrytan/gbrain-evals` | 190 | Evaluation harness for gbrain. |
| `garrytan/alphaclaw` | 110 | Setup harness for OpenClaw. |
| `garrytan/openclaw` | 27 | Garry's own OpenClaw deployment. |

**Distribution mechanic:** Garry has ~600k Twitter followers and the
megaphone of YC's CEO. Repos he publishes typically hit ≥1k stars
within days and ride to ≥10k inside a quarter.

**SourcePrep angle:**

- Ship a `prep` slash command in gstack's format so gstack users get
  one-line install ("`./setup` then `prep status`").
- Add SourcePrep to gstack's recommended MCP server list via a PR
  (or, if a maintainer prefers, an issue describing the integration).
- Frame in the README: "Works with gstack out of the box."
- The 104k-star audience is exactly the developer population most
  likely to install another MCP server today.

## Trust + adoption: why OSS specifically matters for our category

From the trust + adoption searches:

- *"Open source can help earn trust quickly, especially in fields
  like security or infrastructure."* SourcePrep is both — it reads
  the user's entire codebase and routes parts of it to LLMs.
- *"For enterprise AI, open source needs cost, flexibility, and
  trust, with highly regulated industries turning to open source
  models because they need transparency and auditability."*
- AI-generated PR spam has reduced the "default trust" of OSS
  contributions, but that's a problem for *maintainers* not for
  *users* — for users, the read-the-code option only got more
  valuable.

**Bottom line:** an opaque binary that ingests private code and
routes to cloud LLMs is *harder* to sell in 2026 than 2022. OSS is
the only credible posture for our category.

## Sources

- [Warp is now open-source — Warp blog](https://www.warp.dev/blog/warp-is-now-open-source)
- [Warp's gamble: Going open source to take on closed-source rivals — The New Stack](https://thenewstack.io/warp-open-source-client/)
- [A Solo Developer's Side Project Got Acquired by OpenAI AND Meta — The OpenClaw Story](https://megaoneai.com/blog/openclaw-openai-meta-acquisition-story/)
- [OpenAI Acqui-Hires OpenClaw Creator: Agentic Future 2026](https://aitoolsreview.co.uk/insights/openai-acquihires-openclaw)
- [OpenAI to acquire developer tooling startup Astral — CNBC](https://www.cnbc.com/2026/03/19/openai-to-acquire-developer-tooling-startup-astral.html)
- [Why are AI companies buying the teams behind your favorite dev tools? — LogRocket](https://blog.logrocket.com/ai-companies-buying-teams-behind-dev-tools)
- [OpenAI Closes Six Acquisitions as AI Lab Consolidation Heats Up](https://ai2.work/blog/openai-closes-six-acquisitions-as-ai-lab-consolidation-heats-up)
- [AI coding startup Cognition secures $1B at $26B valuation](https://thetechportal.com/2026/05/27/ai-coding-startup-cognition-secures-1bn-in-funding-at-26bn-valuation/)
- [Open sourcing Cody — Sourcegraph Blog](https://sourcegraph.com/blog/open-sourcing-cody)
- [Open-core model — Wikipedia](https://en.wikipedia.org/wiki/Open-core_model)
- [Business models for open-source software — Wikipedia](https://en.wikipedia.org/wiki/Business_models_for_open-source_software)
- [Open-Source vs Closed AI: Trust, Security & Performance](https://www.index.dev/blog/open-source-vs-closed-ai-guide)
- [How to Monetize Open Source Software: 7 Proven Strategies](https://www.reo.dev/blog/monetize-open-source-software)
- [garrytan/gstack on GitHub](https://github.com/garrytan/gstack)
- [garrytan/ profile on GitHub](https://github.com/garrytan)
