# Phase 142 — Acquirer & Employer Map

> Specific targets, integration angles, and outreach prep. Used in
> Part H of IMPLEMENTATION_PLAN.md.
>
> **Two parallel tracks:** acquirer conversations and senior IC role
> applications. Most companies on this list are both — apply for the
> role *and* reach out about the project. Don't treat them as
> exclusive.

## Tier 1 — Primary targets (strongest fit)

### Anthropic (top priority)

| | |
|---|---|
| **Why** | They built Claude Code. They built MCP. SourcePrep is MCP-native code intelligence — literally infrastructure for their flagship developer product. Already acquired Bun (Dec 2025) explicitly for "Claude Code infrastructure." |
| **Integration angle** | "Claude Code with SourcePrep MCP gets structural codebase context that doesn't fit in any practical context window — trace expansion, concept extraction, impact analysis. Demo video shows X% improvement on Y task." |
| **Outreach target** | Claude Code engineering team (look for engineers posting MCP-related work). MCP team specifically. AI engineer / dev-tools recruiters. |
| **How to find specific people** | Anthropic engineering blog authors, public MCP commits / specs, conference talks (NeurIPS, ICML, GTC), Twitter accounts of engineers who post about Claude Code. |
| **Role applications** | AI engineer, dev tools engineer, anything Claude Code adjacent. Repo + blog posts = the cover letter. |
| **Cold email opener** | "I built [link] — Apache 2.0 MCP server for codebase intelligence. The benchmark with Claude Code is here [link]. Open to chatting about whether the integration fits anything on your roadmap." |
| **Avoid** | Pitching as a competitor. Pitching as "you should buy us for $X." Begging. |

### OpenAI

| | |
|---|---|
| **Why** | They built Codex. Acquired Astral (Mar 2026) for Python dev tooling. Acqui-hired Steinberger / OpenClaw (Apr 2026). Demonstrably active acquirer of solo-dev OSS infrastructure in our category. |
| **Integration angle** | "Codex with SourcePrep would have structural code context for repos too large for chunked retrieval. Apache 2.0 means clean integration path." |
| **Outreach target** | Codex team. Dev tools / agents team. |
| **How to find specific people** | OpenAI Codex announcements (engineer credits), Astral-acquisition coverage (who's running dev tools post-acquisition). |
| **Role applications** | Member of technical staff, dev tools, Codex infra. |
| **Avoid** | Mentioning OpenClaw / Steinberger by name (presumes a comparison they may not flatter). |

### Cognition (Devin)

| | |
|---|---|
| **Why** | Building a full-stack AI software engineer. Acquired Windsurf. $26B valuation (May 2026) with cash to deploy. Need every layer of dev infrastructure. |
| **Integration angle** | "Devin needs codebase intelligence at every decision point. SourcePrep's trace graph + concept extraction = better grounded reasoning before edits." |
| **Outreach target** | Engineering leadership; AI infrastructure team. |
| **How to find specific people** | Cognition blog, Windsurf-acquisition coverage, Founders Fund partner intros if reachable. |
| **Role applications** | Member of technical staff, AI engineer, code intelligence. |
| **Avoid** | Framing as "Devin's missing piece" — that reads as criticism. Frame as "additive infrastructure." |

## Tier 2 — Strong fit (slightly different category)

### Cursor / Anysphere

| | |
|---|---|
| **Why** | Cursor's codebase indexing is a known weak point. $60B SpaceX option valuation (April 2026). Microsoft passed; they're shopping. |
| **Integration angle** | "Cursor's `@codebase` could call SourcePrep MCP for structural retrieval instead of the current embedding-only approach. Demo shows X." |
| **Outreach target** | Codebase team specifically. Founder if reachable via mutual. |
| **Role applications** | AI engineer, code intelligence. |
| **Tradeoff** | Cursor is competing with Anthropic for the same agent-IDE space; if Eric ends up at Cursor, the Anthropic ecosystem connection weakens. Worth knowing before optimizing. |

### Sourcegraph

| | |
|---|---|
| **Why** | Best code intelligence engine in industry. Open-sourced Cody. Could acquire a complementary MCP-native local-first tool. |
| **Integration angle** | "Local-first MCP companion to Cody. Different user — Cody is enterprise; SourcePrep is individual developer / OSS. Possibly distribution angle for Cody Pro." |
| **Outreach target** | Quinn Slack (founder/CEO, very accessible), Beyang Liu (founder/CTO, posts publicly). |
| **Role applications** | Cody engineer, code intelligence engineer. |
| **Tradeoff** | Direct overlap risk. If they see us as a competitor rather than a complement, the conversation goes cold fast. Pitch carefully. |

## Tier 3 — Distribution + secondary acquirer potential

### GitHub / Microsoft (Copilot)

| | |
|---|---|
| **Why** | Copilot Workspace and the new agent-mode features could use better codebase context. Microsoft has cash. |
| **Integration angle** | "Copilot Agents could call SourcePrep MCP for grounded structural context. Apache 2.0 = clean GitHub integration story." |
| **Outreach target** | GitHub Next team, Copilot engineering. |
| **Role applications** | Copilot AI engineer. |
| **Likelihood** | Lower than Anthropic/OpenAI for acqui-hire; higher for ecosystem distribution (Copilot marketplace, GitHub Actions integration). |

### JetBrains

| | |
|---|---|
| **Why** | Building AI Assistant + Junie (agent product). Need code intelligence. Historically conservative on acquisitions but uses OSS heavily. |
| **Integration angle** | "JetBrains plugin for SourcePrep — already have a `packages/vscode` extension; adding a JetBrains client is plausible." |
| **Outreach target** | AI Assistant team. |
| **Role applications** | AI engineer (most JetBrains roles require relocation — check). |
| **Likelihood** | Distribution > acquisition. |

### Replit

| | |
|---|---|
| **Why** | Replit Agent is in active development. Needs codebase context. Smaller team; could move fast. |
| **Integration angle** | "Replit Agent + SourcePrep MCP for grounded code context in workspaces." |
| **Outreach target** | Replit AI team. |
| **Likelihood** | Lower for acqui-hire; higher for integration partnership. |

## Tier 4 — Job-only targets (not likely acquirers but great employers for the resume)

If Phase 142 doesn't produce an acqui-hire, these are companies where
SourcePrep as a public project + blog posts is a credible cover
letter for a senior IC role:

- **Vercel** — Next.js, AI SDK, growing AI infra team
- **Linear** — engineering culture, internal tooling
- **Posthog** — engineering culture, OSS-first
- **Granola** — small AI team, dev-tool-adjacent
- **Continue.dev** — direct category overlap; possibly join the team
- **Tabby** — same category
- **Stripe** — large infra org, takes serious senior IC applications

These are *fallback*, not focus. Pursue if Tiers 1–3 cool off.

## Outreach hygiene

For every named contact in any tier:

- [ ] Researched 2 things about them: a public post, a project, or a public statement that lets the email reference them specifically
- [ ] Email ≤150 words
- [ ] One ask only — either "happy to chat" OR "want to see a demo" — not both
- [ ] Link the GitHub repo first, demo video second; don't link the marketing site as primary
- [ ] Don't follow up more than once. Silence is a no — move on.
- [ ] If they respond: have the resume, demo, and 1-on-1 calendar link ready within 24h

## What we don't do

- ❌ Cold-spray LinkedIn DMs. Recruiters auto-filter.
- ❌ Generic "I built a tool, want to chat?" emails. 0% response rate.
- ❌ Begging for an introduction without offering something specific in return.
- ❌ Naming a price ("would $X be acceptable?"). Let them name it; we negotiate from there.
- ❌ Public tweets tagging executives asking for a job / acquisition. Public begging is poison.

## Tracking

Per IMPLEMENTATION_PLAN.md H.3: maintain `OUTREACH_LOG.md` (private,
gitignored) with each conversation's date, contact, status, next step.
Phase 142 is not complete until this log exists and has entries.
